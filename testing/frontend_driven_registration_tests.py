import unittest
from pathlib import Path
from unittest.mock import patch

from brain_service import AdmissionBrainService

class TestFrontendDrivenRegistration(unittest.TestCase):
    def setUp(self):
        self.service = AdmissionBrainService()
        self.session = self.service.create_session()
        self.session_id = self.session["session_id"]

    def test_invalid_field_id(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="invalid_field",
            transcript="test",
            language="en"
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "INVALID_FIELD_ID")

    def test_valid_field_id_is_accepted(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["field_id"], "date_of_birth")

    def test_field_scoped_date_input(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["status"], "confirmation_required")
        self.assertEqual(result["data"]["normalized_value"], "2005-11-12")
        self.assertEqual(result["data"]["form_updates"]["date_of_birth"], "2005-11-12")

    def test_field_scoped_mobile_input(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="student_mobile_no",
            transcript="01012345678",
            language="en"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["normalized_value"], "01012345678")
        self.assertEqual(result["data"]["form_updates"]["student_mobile_no"], "01012345678")

    def test_city_input_nasr_city(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City",
            language="en"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["normalized_value"], "مدينة نصر")

    def test_frontend_mode_does_not_return_next_question(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City",
            language="en"
        )
        self.assertTrue(result["success"])
        self.assertNotIn("next_question", result["data"])
        self.assertNotIn("next_field_id", result["data"])

    def test_frontend_mode_does_not_return_next_field_id(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="student_mobile_no",
            transcript="01012345678",
            language="en"
        )
        self.assertTrue(result["success"])
        self.assertNotIn("next_field_id", result["data"])

    def test_frontend_mode_does_not_automatically_advance_current_field(self):
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City",
            language="en"
        )
        state = self.service.brain.registration_engine.sessions[self.session_id]
        self.assertIsNone(state.get("current_field"))
        self.assertEqual(state.get("pending_frontend_field"), "city")

    def test_valid_input_returns_confirmation_required(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        self.assertEqual(result["data"]["status"], "confirmation_required")

    def test_yes_confirmation_returns_confirmed(self):
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="yes",
            language="en",
            interaction="confirmation"
        )
        self.assertEqual(result["data"]["status"], "confirmed")
        self.assertTrue(result["data"]["allow_frontend_next"])

    def test_first_no_confirmation_returns_retry(self):
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="no",
            language="en",
            interaction="confirmation"
        )
        self.assertEqual(result["data"]["status"], "retry_required")
        self.assertEqual(result["data"]["ui_action"], "SHOW_RETRY")

    def test_second_no_confirmation_returns_manual_input(self):
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="no",
            language="en",
            interaction="confirmation"
        )
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="no",
            language="en",
            interaction="confirmation"
        )
        self.assertEqual(result["data"]["status"], "manual_input_required")
        self.assertTrue(result["data"]["manual_input"]["required"])

    def test_manual_date_input_requests_confirmation(self):
        # Trigger manual input state
        self.service.brain.registration_engine.sessions[self.session_id] = {
            "fields": {},
            "metadata": {},
            "manual_input_required": True,
            "manual_field": "date_of_birth"
        }
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="11122005",
            language="en",
            interaction="manual_input"
        )
        self.assertEqual(result["data"]["status"], "confirmation_required")
        self.assertEqual(result["data"]["normalized_value"], "2005-12-11")

    def test_invalid_manual_mobile_remains_in_manual(self):
        self.service.brain.registration_engine.sessions[self.session_id] = {
            "fields": {},
            "metadata": {},
            "manual_input_required": True,
            "manual_field": "student_mobile_no"
        }
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="student_mobile_no",
            transcript="123", # invalid
            language="en",
            interaction="manual_input"
        )
        self.assertEqual(result["data"]["status"], "manual_input_required")

    def test_name_input_updates_both_ar_and_en(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="full_name_en",
            transcript="Ali Fady",
            language="en"
        )
        self.assertEqual(result["data"]["status"], "confirmation_required")
        self.assertIn("full_name_en", result["data"]["form_updates"])
        self.assertIn("full_name_ar", result["data"]["form_updates"])

    def test_city_input_cannot_fill_governorate(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City Cairo",
            language="en"
        )
        # Should only update city
        self.assertIn("city", result["data"]["form_updates"])
        self.assertNotIn("governorate", result["data"]["form_updates"])

    def test_confirmation_wrong_field_returns_mismatch(self):
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="date_of_birth",
            transcript="12 November 2005",
            language="en"
        )
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="yes",
            language="en",
            interaction="confirmation"
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "FIELD_STATE_MISMATCH")

    def test_manual_input_wrong_field_returns_mismatch(self):
        self.service.brain.registration_engine.sessions[self.session_id] = {
            "fields": {},
            "metadata": {},
            "manual_input_required": True,
            "manual_field": "date_of_birth"
        }
        
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City",
            language="en",
            interaction="manual_input"
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "FIELD_STATE_MISMATCH")

    @patch('tts_engine._generate_only')
    def test_generate_audio_false_does_not_call_tts(self, mock_generate):
        self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City",
            language="en",
            generate_audio=False
        )
        mock_generate.assert_not_called()

    def test_speech_text_is_returned(self):
        result = self.service.process_registration_field(
            session_id=self.session_id,
            field_id="city",
            transcript="Nasr City",
            language="en"
        )
        self.assertTrue(result["data"].get("speech_text"))

if __name__ == "__main__":
    unittest.main()
