import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from brain_service import AdmissionBrainService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestIntegrationReadiness(unittest.TestCase):
    def setUp(self):
        self.service = AdmissionBrainService()
        self.session = self.service.create_session(language="en", mode="qa")
        self.session_id = self.session["session_id"]

    def assert_json_serializable(self, value):
        json.dumps(value, ensure_ascii=False)

    def test_service_import_and_session_startup(self):
        self.assertTrue(self.session["success"])
        self.assertTrue(self.session_id)
        self.assert_json_serializable(self.session)

    def test_public_method_responses_are_json_serializable(self):
        responses = [
            self.service.get_session_state(self.session_id),
            self.service.set_language(self.session_id, "ar"),
            self.service.set_mode(self.session_id, "qa"),
            self.service.process_text(self.session_id, "Where is engineering?", language="en", mode="qa"),
            self.service.get_registration_status(self.session_id),
            self.service.review_registration(self.session_id),
            self.service.export_registration(self.session_id),
            self.service.export_registration_frontend(self.session_id),
        ]
        for response in responses:
            self.assert_json_serializable(response)

        reset_response = self.service.reset_session(self.session_id)
        self.assert_json_serializable(reset_response)

    def test_session_isolation_and_single_reset(self):
        first = self.service.create_session(language="en", mode="registration")["session_id"]
        second = self.service.create_session(language="en", mode="registration")["session_id"]

        self.service.process_registration_field(first, "date_of_birth", "12 November 2005", "en")
        self.service.process_registration_field(second, "date_of_birth", "13 November 2005", "en")

        confirm_first = self.service.process_registration_field(
            first, "date_of_birth", "yes", "en", interaction="confirmation"
        )
        self.assertEqual(confirm_first["data"]["status"], "confirmed")

        first_export = self.service.export_registration(first)["data"]
        second_export = self.service.export_registration(second)["data"]
        self.assertEqual(first_export.get("date_of_birth"), "2005-11-12")
        self.assertEqual(second_export.get("date_of_birth"), "2005-11-13")

        first_state = self.service.brain.registration_engine.sessions[first]
        second_state = self.service.brain.registration_engine.sessions[second]
        self.assertTrue(first_state["metadata"]["date_of_birth"]["confirmed"])
        self.assertFalse(second_state["metadata"]["date_of_birth"]["confirmed"])

        self.service.reset_session(first)
        self.assertFalse(self.service.export_registration(first)["success"])
        self.assertEqual(self.service.export_registration(second)["data"].get("date_of_birth"), "2005-11-13")

    def test_unknown_session_returns_safe_error(self):
        result = self.service.process_text("missing", "hello")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "SESSION_NOT_FOUND")

    def test_invalid_language_mode_interaction_transcript_and_field(self):
        self.assertEqual(
            self.service.set_language(self.session_id, "fr")["error"],
            "INVALID_LANGUAGE",
        )
        self.assertEqual(
            self.service.set_mode(self.session_id, "demo")["error"],
            "INVALID_MODE",
        )
        self.assertEqual(
            self.service.process_registration_field(
                self.session_id,
                "date_of_birth",
                "12 November 2005",
                "en",
                interaction="bad",
            )["error"],
            "INVALID_INTERACTION",
        )
        self.assertEqual(
            self.service.process_registration_field(
                self.session_id,
                "date_of_birth",
                "",
                "en",
            )["error"],
            "INVALID_TRANSCRIPT",
        )
        self.assertEqual(
            self.service.process_registration_field(
                self.session_id,
                "not_a_field",
                "value",
                "en",
            )["error"],
            "INVALID_FIELD_ID",
        )

    def test_date_updates_only_date_and_returns_frontend_alias(self):
        result = self.service.process_registration_field(
            self.session_id,
            "dateOfBirth",
            "12 November 2005",
            "en",
        )
        data = result["data"]
        self.assertEqual(data["field_id"], "date_of_birth")
        self.assertEqual(data["status"], "confirmation_required")
        self.assertEqual(data["form_updates"], {"date_of_birth": "2005-11-12"})
        self.assertEqual(data["frontend_form_updates"], {"dateOfBirth": "2005-11-12"})
        self.assertNotIn("next_question", data)
        self.assertNotIn("next_field_id", data)

    def test_mobile_updates_only_mobile(self):
        result = self.service.process_registration_field(
            self.session_id,
            "student_mobile_no",
            "01012345678",
            "en",
        )
        self.assertEqual(result["data"]["form_updates"], {"student_mobile_no": "01012345678"})

    def test_city_nasr_city_is_arabic_and_scoped(self):
        result = self.service.process_registration_field(
            self.session_id,
            "city",
            "Nasr City",
            "en",
        )
        expected_city = self.service.brain.registration_engine.LOCATION_MAP["nasr city"]
        self.assertEqual(result["data"]["normalized_value"], expected_city)
        self.assertEqual(result["data"]["form_updates"], {"city": expected_city})

    def test_confirmation_rejection_and_manual_flow(self):
        self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "12 November 2005",
            "en",
        )

        retry = self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "no",
            "en",
            interaction="confirmation",
        )
        self.assertEqual(retry["data"]["status"], "retry_required")
        self.assertEqual(retry["data"]["ui_action"], "SHOW_RETRY")

        manual = self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "no",
            "en",
            interaction="confirmation",
        )
        self.assertEqual(manual["data"]["status"], "manual_input_required")
        self.assertEqual(manual["data"]["ui_action"], "REQUEST_MANUAL_INPUT")

        manual_retry = self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "bad-date",
            "en",
            interaction="manual_input",
        )
        self.assertEqual(manual_retry["data"]["status"], "manual_input_required")

        manual_valid = self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "11122005",
            "en",
            interaction="manual_input",
        )
        self.assertEqual(manual_valid["data"]["status"], "confirmation_required")
        self.assertEqual(manual_valid["data"]["normalized_value"], "2005-12-11")

    def test_yes_confirmation_allows_frontend_next(self):
        self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "12 November 2005",
            "en",
        )
        result = self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "yes",
            "en",
            interaction="confirmation",
        )
        self.assertEqual(result["data"]["status"], "confirmed")
        self.assertTrue(result["data"]["allow_frontend_next"])
        self.assertEqual(result["data"]["ui_action"], "ALLOW_FRONTEND_NEXT")

    def test_name_intake_may_update_both_names(self):
        result = self.service.process_registration_field(
            self.session_id,
            "full_name_en",
            "Ali Fady",
            "en",
        )
        self.assertIn("full_name_en", result["data"]["form_updates"])
        self.assertIn("full_name_ar", result["data"]["form_updates"])

    def test_wrong_field_confirmation_and_manual_mismatch(self):
        self.service.process_registration_field(
            self.session_id,
            "date_of_birth",
            "12 November 2005",
            "en",
        )
        mismatch = self.service.process_registration_field(
            self.session_id,
            "city",
            "yes",
            "en",
            interaction="confirmation",
        )
        self.assertEqual(mismatch["error"], "FIELD_STATE_MISMATCH")

        manual_session = self.service.create_session(language="en", mode="registration")["session_id"]
        self.service.brain.registration_engine.sessions[manual_session] = {
            "fields": {},
            "metadata": {},
            "manual_input_required": True,
            "manual_field": "date_of_birth",
        }
        manual_mismatch = self.service.process_registration_field(
            manual_session,
            "city",
            "Nasr City",
            "en",
            interaction="manual_input",
        )
        self.assertEqual(manual_mismatch["error"], "FIELD_STATE_MISMATCH")

    @patch("tts_engine._play_audio")
    @patch("tts_engine.generate_tts_audio")
    def test_generate_audio_false_does_not_trigger_audio(self, mock_generate, mock_play):
        result = self.service.process_registration_field(
            self.session_id,
            "city",
            "Nasr City",
            "en",
            generate_audio=False,
        )
        self.assertFalse(result["data"]["audio"]["generated"])
        mock_generate.assert_not_called()
        mock_play.assert_not_called()

    @patch("tts_engine.generate_tts_audio", side_effect=RuntimeError("network failed"))
    def test_audio_failure_still_returns_text(self, mock_generate):
        result = self.service.process_registration_field(
            self.session_id,
            "city",
            "Nasr City",
            "en",
            generate_audio=True,
        )
        self.assertTrue(result["data"]["speech_text"])
        self.assertFalse(result["data"]["audio"]["generated"])

    def test_successful_service_responses_have_speech_text(self):
        result = self.service.process_registration_field(
            self.session_id,
            "city",
            "Nasr City",
            "en",
        )
        self.assertTrue(result["data"]["speech_text"])

    def test_qa_output_is_safe_and_serializable(self):
        result = self.service.process_text(
            self.session_id,
            "does engineering have dorm rooms",
            language="en",
            mode="qa",
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["answer_text"])
        self.assert_json_serializable(result)

    def test_core_imports_resolve_from_project_root(self):
        command = [
            sys.executable,
            "-c",
            "import main, brain, brain_service, registration, models; print('ok')",
        ]
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("ok", completed.stdout)

    def test_main_starts_from_project_root_without_pythonpath(self):
        completed = subprocess.run(
            [sys.executable, "main.py"],
            cwd=PROJECT_ROOT,
            input="exit\n",
            text=True,
            capture_output=True,
            timeout=30,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Admission Robot AI Brain - Local Test", completed.stdout)
        self.assertIn("Commands:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
