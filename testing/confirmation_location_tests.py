
import unittest
import os
import json
from brain import ECUBrain
from models import BrainInput
from registration import RegistrationEngine

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

class TestUniversalConfirmation(unittest.TestCase):
    def setUp(self):
        self.brain = ECUBrain()
        self.session_id = "test-confirmation-session"

    def _fill_preceding_fields(self, field_id):
        # Mark all fields before field_id in field_definitions as filled and confirmed
        for field in self.brain.registration_engine.field_definitions:
            if field["field_id"] == field_id:
                break
            self.brain.registration_engine.sessions[self.session_id]["fields"][field["field_id"]] = "already filled"
            self.brain.registration_engine.sessions[self.session_id]["metadata"][field["field_id"]] = {"confirmed": True}

    def test_every_guided_field_requires_confirmation_after_fill(self):
        # 1. Start form
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        
        # 2. Fill city (usually not sensitive)
        self._fill_preceding_fields("city")
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "city"
        output = process_text(self.brain, "Nasr City", session_id=self.session_id)
        
        # Should now require confirmation even if not sensitive
        self.assertTrue(output.needs_confirmation)
        self.assertIn("مدينة نصر", output.next_question)

    def test_confirmation_yes_advances_to_next_field(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        self._fill_preceding_fields("city")
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "city"
        process_text(self.brain, "Nasr City", session_id=self.session_id)
        
        # Confirm
        output = process_text(self.brain, "yes", session_id=self.session_id)
        
        # Should not need confirmation anymore and move to next field
        self.assertFalse(output.needs_confirmation)
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertIn("city", status["filled_fields"])
        self.assertNotIn("city", status["unconfirmed_fields"])

    def test_confirmation_no_repeats_same_field(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        
        # Fill preceding fields
        self._fill_preceding_fields("city")
        
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "city"
        process_text(self.brain, "Nasr City", session_id=self.session_id)
        
        # Reject
        output = process_text(self.brain, "no", session_id=self.session_id)
        
        # Should ask for city again
        self.assertFalse(output.needs_confirmation)
        self.assertIn("city", output.next_question.lower() or "")
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertNotIn("city", status["filled_fields"])

    def test_name_pair_confirmation_confirms_both_names(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        process_text(self.brain, "Zeyad Omar Farouk", session_id=self.session_id)
        
        # Confirm
        process_text(self.brain, "yes", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertIn("full_name_ar", status["filled_fields"])
        self.assertIn("full_name_en", status["filled_fields"])
        self.assertNotIn("full_name_ar", status["unconfirmed_fields"])
        self.assertNotIn("full_name_en", status["unconfirmed_fields"])

    def test_name_pair_rejection_clears_both_names(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        process_text(self.brain, "Zeyad Omar Farouk", session_id=self.session_id)
        
        # Reject
        process_text(self.brain, "no", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertNotIn("full_name_ar", status["filled_fields"])
        self.assertNotIn("full_name_en", status["filled_fields"])

class TestArabicLocationStorage(unittest.TestCase):
    def setUp(self):
        self.brain = ECUBrain()
        self.session_id = "test-location-session"

    def test_place_of_birth_cairo_stored_arabic(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "place_of_birth"
        process_text(self.brain, "Cairo", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertEqual(status["filled_fields"]["place_of_birth"], "القاهرة")

    def test_country_egypt_stored_arabic(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "country"
        process_text(self.brain, "Egypt", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertEqual(status["filled_fields"]["country"], "مصر")

    def test_city_nasr_city_stored_arabic(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "city"
        process_text(self.brain, "Nasr City", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertEqual(status["filled_fields"]["city"], "مدينة نصر")

    def test_address_english_transliterated_or_rejected(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "address"
        # 20 Nagati Serag Street
        process_text(self.brain, "20 Nagati Serag Street", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        val = status["filled_fields"].get("address", "")
        # Should contain "شارع" because of ADDRESS_WORDS_MAP
        self.assertIn("شارع", val)
        # Numbers should be preserved
        self.assertIn("20", val)

    def test_guardian_address_same_as_address_copies_arabic_address(self):
        self.brain.registration_engine.start_guided_form(self.session_id, "en")
        
        # 1. Fill student address
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "address"
        process_text(self.brain, "Nasr City", session_id=self.session_id)
        process_text(self.brain, "yes", session_id=self.session_id)
        
        # 2. Fill guardian address "same as mine"
        self.brain.registration_engine.sessions[self.session_id]["current_field"] = "guardian_address"
        process_text(self.brain, "same as my address", session_id=self.session_id)
        
        status = self.brain.registration_engine.get_form_debug_view(self.session_id)
        self.assertEqual(status["filled_fields"]["guardian_address"], "مدينة نصر")

if __name__ == "__main__":
    unittest.main()
