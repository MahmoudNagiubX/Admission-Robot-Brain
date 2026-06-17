import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from brain import ECUBrain
from models import BrainInput

class TestManualFallback(unittest.TestCase):
    def setUp(self):
        self.brain = ECUBrain()
        self.test_name = self.id().split('.')[-1]
        self.session_id = f"test-session-{self.test_name}"
        # Start registration mode
        self.brain.registration_engine.start_guided_form(self.session_id, "ar")

    def process(self, text, language="ar"):
        return self.brain.process(BrainInput(self.session_id, text, language, "registration"))

    def _fill_mandatory_name(self):
        self.process("محمود أحمد نجيب")
        self.process("نعم")

    def test_first_confirmation_rejection_repeats_question(self):
        # Fill name
        self.process("محمود أحمد نجيب")
        # Reject once
        output = self.process("لا")
        self.assertFalse(output.manual_input_required)
        self.assertIn("اسمك", output.next_question) # Should ask name again

    def test_second_confirmation_rejection_triggers_manual_mode(self):
        # Fill name
        self.process("محمود أحمد نجيب")
        # Reject once
        self.process("لا")
        # Fill name again
        self.process("محمود أحمد نجيب")
        # Reject twice
        output = self.process("لا")
        self.assertTrue(output.manual_input_required)
        self.assertEqual(output.manual_field, "full_name_ar")
        self.assertIn("اكتب اسمك الكامل يدويًا", output.next_question)

    def test_manual_name_after_two_rejections(self):
        self.process("محمود أحمد نجيب")
        self.process("لا")
        self.process("محمود أحمد نجيب")
        self.process("لا")
        
        # Manual input
        output = self.process("محمود أحمد نجيب")
        # For name_pair, both fields should be updated
        self.assertEqual(output.form_updates.get("full_name_ar"), "محمود أحمد نجيب")
        self.assertEqual(output.form_updates.get("full_name_en"), "Mahmoud Ahmed Nagib")
        self.assertTrue(output.needs_confirmation)
        self.assertIn("سجلت اسمك", output.next_question)
        
        # Confirm manual input
        output = self.process("نعم")
        self.assertFalse(output.manual_input_required)
        self.assertIn("تاريخ ميلادك", output.next_question) # Move to next field

    def test_manual_date_after_two_invalid_attempts(self):
        # Move to DOB
        self._fill_mandatory_name()
        
        # Invalid DOB 1
        self.process("مش فاهم")
        # Invalid DOB 2
        output = self.process("تاريخ غير صحيح")
        
        self.assertTrue(output.manual_input_required)
        self.assertEqual(output.manual_field, "date_of_birth")
        self.assertIn("اكتب تاريخ الميلاد يدويًا", output.next_question)
        
        # Manual input
        output = self.process("11/12/2005")
        self.assertEqual(output.form_updates.get("date_of_birth"), "2005-12-11")
        
        # Confirm
        output = self.process("نعم")
        self.assertFalse(output.manual_input_required)

    def test_manual_mobile_after_two_invalid_attempts(self):
        # Fill previous mandatory fields or use skip field to reach student_mobile_no
        self._fill_mandatory_name()
        
        # Instead of skipping all fields, we can just force the current_field 
        # but we must ensure we don't have missing mandatory fields that _sync_current_field would pick.
        # But name is the only one before DOB.
        
        # Reach student_mobile_no
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = "student_mobile_no"
        # Mark all fields before student_mobile_no as skipped or filled
        for field_id in self.brain.registration_engine.field_order:
            if field_id == "student_mobile_no":
                break
            if field_id not in state["fields"]:
                state["skipped_fields"].add(field_id)

        # Invalid 1
        self.process("رقم غلط")
        # Invalid 2
        output = self.process("123")
        
        self.assertTrue(output.manual_input_required)
        self.assertEqual(output.manual_field, "student_mobile_no")
        self.assertIn("اكتب رقم الموبايل 11 رقم", output.next_question)
        
        # Manual input
        output = self.process("01012345678")
        self.assertEqual(output.form_updates.get("student_mobile_no"), "01012345678")
        
        # Confirm
        output = self.process("نعم")
        self.assertFalse(output.manual_input_required)

    def test_manual_id_after_two_invalid_attempts(self):
        self._fill_mandatory_name()
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = "id_or_passport"
        for field_id in self.brain.registration_engine.field_order:
            if field_id == "id_or_passport":
                break
            if field_id not in state["fields"]:
                state["skipped_fields"].add(field_id)
        
        # Invalid 1
        self.process("بطاقة")
        # Invalid 2
        output = self.process("no id")
        
        self.assertTrue(output.manual_input_required)
        self.assertEqual(output.manual_field, "id_or_passport")
        
        # Manual input
        output = self.process("30510201012345")
        self.assertEqual(output.form_updates.get("id_or_passport"), "30510201012345")

    def test_manual_email_after_two_invalid_attempts(self):
        self._fill_mandatory_name()
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = "email_address"
        for field_id in self.brain.registration_engine.field_order:
            if field_id == "email_address":
                break
            if field_id not in state["fields"]:
                state["skipped_fields"].add(field_id)
        
        # Invalid 1
        self.process("ايميل")
        # Invalid 2
        output = self.process("not an email")
        
        self.assertTrue(output.manual_input_required)
        self.assertEqual(output.manual_field, "email_address")
        
        # Manual input
        output = self.process("mahmoud.nagib@gmail.com")
        self.assertEqual(output.form_updates.get("email_address"), "mahmoud.nagib@gmail.com")

    def test_manual_location_still_arabic(self):
        self._fill_mandatory_name()
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = "city"
        for field_id in self.brain.registration_engine.field_order:
            if field_id == "city":
                break
            if field_id not in state["fields"]:
                state["skipped_fields"].add(field_id)
        
        # Invalid 1 (rejection works too)
        self.process("مدينة")
        self.process("لا")
        self.process("مدينة")
        output = self.process("لا")
        
        self.assertTrue(output.manual_input_required)
        
        # Manual input in English
        output = self.process("Nasr City")
        # Should be normalized to Arabic
        self.assertEqual(output.form_updates.get("city"), "مدينة نصر")

    def test_manual_input_does_not_bypass_validation(self):
        self._fill_mandatory_name()
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = "student_mobile_no"
        for field_id in self.brain.registration_engine.field_order:
            if field_id == "student_mobile_no":
                break
            if field_id not in state["fields"]:
                state["skipped_fields"].add(field_id)
        
        self.process("invalid")
        self.process("invalid")
        
        # Manual input invalid
        output = self.process("123")
        self.assertTrue(output.manual_input_required)
        self.assertIn("يدويًا", output.next_question)
        self.assertNotIn("student_mobile_no", output.form_updates)

    def test_successful_confirmation_resets_manual_counters(self):
        # Trigger manual for name
        self.process("محمود")
        self.process("لا")
        self.process("محمود")
        output = self.process("لا")
        self.assertTrue(output.manual_input_required)
        
        # Valid manual + confirm
        self.process("محمود أحمد")
        self.process("نعم")
        
        # Check counters reset
        state = self.brain.registration_engine.sessions[self.session_id]
        self.assertEqual(state["confirmation_rejection_counts"].get("full_name_ar", 0), 0)
        self.assertFalse(state["manual_input_required"])

    def test_manual_mode_is_per_field_not_global(self):
        # Trigger manual for name
        self.process("محمود")
        self.process("لا")
        self.process("محمود")
        self.process("لا")
        
        # Confirm name manually
        self.process("محمود أحمد")
        self.process("نعم")
        
        # Next field should NOT be in manual mode
        output = self.process("15/08/2005")
        self.assertFalse(output.manual_input_required)

if __name__ == "__main__":
    unittest.main()
