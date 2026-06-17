import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from brain import ECUBrain
from models import BrainInput

class TestGeneralization(unittest.TestCase):
    def setUp(self):
        self.brain = ECUBrain()
        self.test_name = self.id().split('.')[-1]
        self.session_id = f"test-session-{self.test_name}"

    def process(self, text, language="ar"):
        return self.brain.process(BrainInput(self.session_id, text, language, "registration"))

    def start_guided(self, field_id):
        self.brain.registration_engine.start_guided_form(self.session_id, "ar")
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = field_id
        for field in self.brain.registration_engine.field_order:
            if field == field_id:
                break
            if field not in state["fields"]:
                state["skipped_fields"].add(field)

    # --- Name generalization ---
    def test_name_random_common_arabic_name_1(self):
        self.start_guided("full_name_ar")
        output = self.process("اسمي عمر خالد حسن")
        self.assertEqual(output.form_updates.get("full_name_ar"), "عمر خالد حسن")
        self.assertEqual(output.form_updates.get("full_name_en"), "Omar Khaled Hassan")

    def test_name_random_common_english_name_1(self):
        self.start_guided("full_name_en")
        output = self.process("my name is Kareem Tarek Hassan")
        # Depending on dictionary, Kareem may normalize to Karim
        self.assertIn(output.form_updates.get("full_name_en"), ["Kareem Tarek Hassan", "Karim Tarek Hassan"])
        self.assertEqual(output.form_updates.get("full_name_ar"), "كريم طارق حسن")

    def test_name_not_only_mahmoud(self):
        self.start_guided("full_name_ar")
        output = self.process("Ahmed Samir Adel")
        self.assertEqual(output.form_updates.get("full_name_en"), "Ahmed Samir Adel")
        self.assertEqual(output.form_updates.get("full_name_ar"), "أحمد سمير عادل")

    def test_name_unknown_preserved_phonetically(self):
        self.start_guided("full_name_ar")
        output = self.process("Zalaf Hatem")
        self.assertEqual(output.form_updates.get("full_name_en"), "Zalaf Hatem")
        self.assertEqual(output.form_updates.get("full_name_ar"), "زالاف حاتم")

    # --- Date generalization ---
    def test_compact_date_different_value_01012006(self):
        self.start_guided("date_of_birth")
        output = self.process("01012006")
        self.assertEqual(output.form_updates.get("date_of_birth"), "2006-01-01")

    def test_compact_date_different_value_31122004(self):
        self.start_guided("date_of_birth")
        output = self.process("31122004")
        self.assertEqual(output.form_updates.get("date_of_birth"), "2004-12-31")

    def test_spaced_date_different_value_05062007(self):
        self.start_guided("date_of_birth")
        output = self.process("05 06 2007")
        self.assertEqual(output.form_updates.get("date_of_birth"), "2007-06-05")

    def test_month_name_different_value(self):
        self.start_guided("date_of_birth")
        output = self.process("7 مارس 2006")
        self.assertEqual(output.form_updates.get("date_of_birth"), "2006-03-07")

    def test_invalid_numeric_dates_still_rejected(self):
        self.start_guided("date_of_birth")
        out1 = self.process("32122005")
        self.assertNotIn("date_of_birth", out1.form_updates)
        out2 = self.process("11132005")
        self.assertNotIn("date_of_birth", out2.form_updates)
        out3 = self.process("12 15 2005")
        self.assertNotIn("date_of_birth", out3.form_updates)

    # --- Phone/ID generalization ---
    def test_mobile_different_valid_prefix_011(self):
        self.start_guided("student_mobile_no")
        output = self.process("01198765432")
        self.assertEqual(output.form_updates.get("student_mobile_no"), "01198765432")

    def test_mobile_different_valid_prefix_012(self):
        self.start_guided("student_mobile_no")
        output = self.process("01222223333")
        self.assertEqual(output.form_updates.get("student_mobile_no"), "01222223333")

    def test_mobile_invalid_prefix_rejected(self):
        self.start_guided("student_mobile_no")
        output = self.process("01312345678")
        self.assertNotIn("student_mobile_no", output.form_updates)

    def test_national_id_different_valid_14_digits(self):
        self.start_guided("id_or_passport")
        output = self.process("29901011234567")
        self.assertEqual(output.form_updates.get("id_or_passport"), "29901011234567")

    # --- Email generalization ---
    def test_email_different_normal(self):
        self.start_guided("email_address")
        output = self.process("student.test2026@yahoo.com")
        self.assertEqual(output.form_updates.get("email_address"), "student.test2026@yahoo.com")

    def test_email_spoken_different(self):
        self.start_guided("email_address")
        output = self.process("omar dot ali at outlook dot com")
        self.assertEqual(output.form_updates.get("email_address"), "omar.ali@outlook.com")

    def test_email_invalid_no_domain_rejected(self):
        self.start_guided("email_address")
        output = self.process("test@domain")
        self.assertNotIn("email_address", output.form_updates)

    # --- Location generalization ---
    def test_city_new_cairo(self):
        self.start_guided("city")
        output = self.process("New Cairo")
        self.assertEqual(output.form_updates.get("city"), "القاهرة الجديدة")

    def test_city_sheikh_zayed(self):
        self.start_guided("city")
        output = self.process("Sheikh Zayed")
        self.assertEqual(output.form_updates.get("city"), "الشيخ زايد")

    def test_governorate_alexandria(self):
        self.start_guided("governorate")
        output = self.process("Alexandria")
        self.assertEqual(output.form_updates.get("governorate"), "الإسكندرية")

    def test_address_different_english_address(self):
        self.start_guided("address")
        output = self.process("25 Abbas El Akkad Street Nasr City")
        # Ensure it contains main transliterated tokens
        arabic_address = output.form_updates.get("address", "")
        self.assertIn("25", arabic_address)
        self.assertIn("شارع", arabic_address)
        self.assertIn("مدينة نصر", arabic_address)

    # --- Academic generalization ---
    def test_percentage_different_integer(self):
        self.start_guided("percentage")
        output = self.process("88")
        self.assertEqual(output.form_updates.get("percentage"), 88.0)

    def test_percentage_different_decimal(self):
        self.start_guided("percentage")
        output = self.process("88.5")
        self.assertEqual(output.form_updates.get("percentage"), 88.5)

    def test_percentage_spoken_different(self):
        self.start_guided("percentage")
        output = self.process("ثمانية وتمانين")
        self.assertEqual(output.form_updates.get("percentage"), 88.0)

    def test_total_marks_different(self):
        self.start_guided("total_marks")
        output = self.process("375 من 410")
        self.assertEqual(output.form_updates.get("total_marks"), 375.0)

    def test_seat_number_different(self):
        self.start_guided("seat_number")
        output = self.process("987654")
        self.assertEqual(output.form_updates.get("seat_number"), "987654")

    # --- Guardian generalization ---
    def test_guardian_profession_different(self):
        self.start_guided("guardian_profession")
        output = self.process("طبيب")
        self.assertEqual(output.form_updates.get("guardian_profession"), "طبيب")

    def test_guardian_profession_english_different(self):
        self.start_guided("guardian_profession")
        output = self.process("accountant")
        self.assertEqual(output.form_updates.get("guardian_profession"), "محاسب")

    def test_relationship_uncle(self):
        self.start_guided("relationship")
        output = self.process("عمي")
        self.assertEqual(output.form_updates.get("relationship"), "Uncle")

    def test_guardian_address_same_as_student_general(self):
        self.start_guided("address")
        self.process("شارع الهرم")
        self.process("نعم")
        
        state = self.brain.registration_engine.sessions[self.session_id]
        state["current_field"] = "guardian_address"
        output = self.process("نفس العنوان")
        self.assertEqual(output.form_updates.get("guardian_address"), "شارع الهرم")

    # --- Faculty generalization ---
    def test_faculty_pharmacy(self):
        self.start_guided("college_preference_1")
        output = self.process("صيدلة")
        self.assertEqual(output.form_updates.get("college_preference_1"), "pharmacy_and_drug_technology")

    def test_faculty_physical_therapy(self):
        self.start_guided("college_preference_1")
        output = self.process("علاج طبيعي")
        self.assertEqual(output.form_updates.get("college_preference_1"), "physical_therapy")

    def test_faculty_unknown_rejected(self):
        self.start_guided("college_preference_1")
        output = self.process("زراعة")
        self.assertNotIn("college_preference_1", output.form_updates)

    # --- Manual Fallback Generalization ---
    def test_manual_fallback_not_field_specific(self):
        # field 1
        self.start_guided("percentage")
        self.process("invalid")
        self.process("invalid")
        out1 = self.process("88")
        self.assertEqual(out1.form_updates.get("percentage"), 88.0)
        self.process("نعم")
        
        # We need a new session to avoid skipped_fields conflicts from start_guided
        self.session_id = f"{self.session_id}-2"
        self.brain.registration_engine.sessions.pop(self.session_id, None)
        # field 2
        self.start_guided("email_address")
        out_fail1 = self.process("invalid") # fail 1
        out_fail2 = self.process("invalid") # fail 2 -> triggers manual
        self.assertTrue(out_fail2.manual_input_required)

        out2 = self.process("student@example.com")
        self.assertEqual(out2.form_updates.get("email_address"), "student@example.com")

    def test_manual_input_still_validates(self):
        self.start_guided("student_mobile_no")
        self.process("invalid")
        self.process("invalid")
        out = self.process("123")
        self.assertNotIn("student_mobile_no", out.form_updates)
        self.assertTrue(out.manual_input_required)

if __name__ == "__main__":
    unittest.main()
