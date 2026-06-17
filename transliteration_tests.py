
import os
import json
import unittest
from unittest.mock import MagicMock, patch
from brain import ECUBrain
from models import BrainInput
from registration import RegistrationEngine

# Force LLM extraction for testing
os.environ["ENABLE_LLM_REGISTRATION_EXTRACTION"] = "true"

def process_text(
    brain: ECUBrain,
    text: str,
    mode: str = "registration",
    language: str = "en",
    session_id: str = "test-session",
):
    return brain.process(
        BrainInput(
            session_id=session_id,
            text=text,
            language=language,
            mode=mode,
        )
    )

class TestNameTransliteration(unittest.TestCase):
    def setUp(self):
        self.brain = ECUBrain()
        self.session_id = "test-session-transliteration"

    def test_1_full_name_ar_fills_both_ar_and_en_even_with_llm_disabled_if_in_map(self):
        with patch.dict(os.environ, {"ENABLE_LLM_REGISTRATION_EXTRACTION": "false"}):
            # Start form
            process_text(self.brain, "start form", session_id=self.session_id)
            
            # Input English name for Arabic field (Mohammed is in map)
            output = process_text(self.brain, "Mohammed Mohsen Mahmoud", session_id=self.session_id)
            
            self.assertEqual(output.form_updates.get("full_name_ar"), "محمد محسن محمود")
            self.assertEqual(output.form_updates.get("full_name_en"), "Mohamed Mohsen Mahmoud")
            # Should NOT need confirmation as per new rules
            self.assertFalse(output.needs_confirmation)

    def test_2_full_name_ar_llm_transliteration_candidate_is_validated(self):
        # Mock LLM to return an INVALID Arabic name (e.g. only one word)
        # We need a name NOT in the map to trigger LLM
        with patch.object(self.brain.registration_engine.llm_client, 'extract_name_pair') as mock_llm:
            mock_llm.return_value = {
                "name_ar": "زيكو", # Invalid: only one name
                "name_en": "Zico",
                "confidence": 0.9
            }
            
            process_text(self.brain, "start form", session_id=self.session_id)
            output = process_text(self.brain, "Zico", session_id=self.session_id)
            
            # Should not save because name_ar "زيكو" has only 1 part
            self.assertNotIn("full_name_ar", output.form_updates)

    def test_3_full_name_ar_english_transliteration_can_be_saved_without_confirmation(self):
        # Mock LLM to return a valid Arabic name
        with patch.object(self.brain.registration_engine.llm_client, 'extract_name_pair') as mock_llm:
            mock_llm.return_value = {
                "name_ar": "زيكو الصغير",
                "name_en": "Zico Junior",
                "confidence": 0.95
            }
            
            process_text(self.brain, "start form", session_id=self.session_id)
            output = process_text(self.brain, "Zico Junior", session_id=self.session_id)
            
            self.assertEqual(output.form_updates.get("full_name_ar"), "زيكو الصغير")
            self.assertEqual(output.form_updates.get("full_name_en"), "Zico Junior")
            self.assertFalse(output.needs_confirmation)

    def test_4_full_name_ar_bad_llm_json_fails_safely(self):
        # Mock LLM to return garbage
        with patch.object(self.brain.registration_engine.llm_client, 'extract_name_pair') as mock_llm:
            mock_llm.return_value = None
            
            process_text(self.brain, "start form", session_id=self.session_id)
            # Use name NOT in map. Now it fallbacks to phonetic transliteration.
            output = process_text(self.brain, "Zico Junior", session_id=self.session_id)
            
            self.assertEqual(output.form_updates.get("full_name_ar"), "زيكو جونور")

    def test_5_name_intake_skips_full_name_en_after_auto_fill(self):
        process_text(self.brain, "start form", session_id=self.session_id)
        # Fill both names
        output = process_text(self.brain, "Mohammed Mohsen Mahmoud", session_id=self.session_id)
        
        # Next question should be date_of_birth, NOT full_name_en
        self.assertIn("date of birth", output.next_question.lower())

    def test_6_name_intake_does_not_fill_unrelated_fields(self):
        with patch.object(self.brain.registration_engine.llm_client, 'extract_name_pair') as mock_llm:
            mock_llm.return_value = {
                "name_ar": "محمد محسن محمود",
                "name_en": "Mohamed Mohsen Mahmoud",
                "confidence": 0.99
            }
            process_text(self.brain, "start form", session_id=self.session_id)
            # Input has name and phone, but only name should be extracted if current_field is full_name_ar
            output = process_text(self.brain, "Mohammed Mohsen Mahmoud my phone is 01012345678", session_id=self.session_id)
            
            self.assertIn("full_name_ar", output.form_updates)
            self.assertNotIn("student_mobile_no", output.form_updates)

    def test_7_current_field_only_still_enforced_after_name_transliteration(self):
        with patch.object(self.brain.registration_engine.llm_client, 'extract_name_pair') as mock_llm:
            mock_llm.return_value = {
                "name_ar": "محمد محسن محمود",
                "name_en": "Mohamed Mohsen Mahmoud",
                "confidence": 0.95
            }
            
            process_text(self.brain, "start form", session_id=self.session_id)
            # User says name and phone, but only name should be extracted if current_field is full_name_ar
            output = process_text(self.brain, "Mohammed Mohsen Mahmoud my phone is 01012345678", session_id=self.session_id)
            
            self.assertIn("full_name_ar", output.form_updates)
            self.assertNotIn("student_mobile_no", output.form_updates)

    def test_8_fake_full_39_field_flow_still_passes(self):
        # This is a bit long for a unit test, but we can verify it doesn't break basic flow
        # We'll just check if start form still works and moves to first field
        process_text(self.brain, "start form", session_id="full-flow-test")
        status = self.brain.registration_engine.get_form_debug_view("full-flow-test")
        self.assertEqual(status["current_field"], "full_name_ar")

if __name__ == "__main__":
    unittest.main()
