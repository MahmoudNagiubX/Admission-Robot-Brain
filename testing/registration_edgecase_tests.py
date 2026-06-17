
import unittest
import re
from registration import RegistrationEngine
from models import ProcessedText

class TestRegistrationEdgeCases(unittest.TestCase):
    def setUp(self):
        self.engine = RegistrationEngine()
        self.session_id = "test_session"
        # Reset session
        if self.session_id in self.engine.sessions:
            del self.engine.sessions[self.session_id]

    def _process_text(self, text, current_field=None, language="ar"):
        processed = ProcessedText(
            raw_text=text,
            normalized_text=text, # Simplified for tests
            protected_text=text,
            corrected_text=text,
            search_query=text,
            language=language,
            entities={}
        )
        
        # Set current field in session
        state = self.engine._get_or_create_session_state(self.session_id)
        state["current_field"] = current_field
        state["guided_flow"] = True
        
        # Ensure metadata exists for already filled fields in form_state
        for field_name, value in state["fields"].items():
            if field_name not in state["metadata"]:
                state["metadata"][field_name] = {
                    "value": value,
                    "confidence": 1.0,
                    "confirmed": True,
                    "needs_confirmation": False
                }
        
        return self.engine.process(self.session_id, processed, language)

    # --- 1. NAME INTAKE (10 tests) ---
    def test_name_ar_basic(self):
        res = self._process_text("محمود أحمد نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")

    def test_name_ar_prefix(self):
        res = self._process_text("اسمي هو محمود أحمد نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")

    def test_name_en_basic(self):
        res = self._process_text("Mahmoud Ahmed Nagib", "full_name_en", "en")
        self.assertEqual(res["form_state"].get("full_name_en"), "Mahmoud Ahmed Nagib")

    def test_name_en_prefix(self):
        res = self._process_text("my name is Mahmoud Ahmed Nagib", "full_name_en", "en")
        self.assertEqual(res["form_state"].get("full_name_en"), "Mahmoud Ahmed Nagib")

    def test_name_pair_generation_from_ar(self):
        res = self._process_text("محمود أحمد نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")
        self.assertEqual(res["form_state"].get("full_name_en"), "Mahmoud Ahmed Nagib")

    def test_name_pair_generation_from_en_transliterated(self):
        res = self._process_text("Mahmoud Ahmed Nagib", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")
        self.assertEqual(res["form_state"].get("full_name_en"), "Mahmoud Ahmed Nagib")

    def test_name_reject_single_part(self):
        res = self._process_text("محمود", "full_name_ar")
        self.assertIsNone(res["form_state"].get("full_name_ar"))

    def test_name_reject_digits_only(self):
        res = self._process_text("123456", "full_name_ar")
        self.assertIsNone(res["form_state"].get("full_name_ar"))

    def test_name_reject_mixed_digits(self):
        res = self._process_text("محمود 123", "full_name_ar")
        self.assertIsNone(res["form_state"].get("full_name_ar"))

    def test_name_cleaning_noise_words(self):
        res = self._process_text("الاسم بالكامل هو محمود أحمد نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")

    # --- 2. DATE OF BIRTH (10 tests) ---
    def test_date_iso(self):
        res = self._process_text("2005-12-11", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-12-11")

    def test_date_compact_8(self):
        res = self._process_text("11122005", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-12-11")

    def test_date_compact_8_order(self):
        res = self._process_text("12112005", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-11-12")

    def test_date_slashes(self):
        res = self._process_text("11/12/2005", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-12-11")

    def test_date_spaces(self):
        res = self._process_text("11 12 2005", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-12-11")

    def test_date_spoken_ar(self):
        res = self._process_text("اتناشر حداشر الفين وخمسة", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-11-12")

    def test_date_month_name_ar(self):
        res = self._process_text("12 نوفمبر 2005", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-11-12")

    def test_date_invalid_day(self):
        res = self._process_text("32122005", "date_of_birth")
        self.assertIsNone(res["form_state"].get("date_of_birth"))

    def test_date_invalid_month(self):
        res = self._process_text("11132005", "date_of_birth")
        self.assertIsNone(res["form_state"].get("date_of_birth"))

    def test_date_noise_prefix(self):
        res = self._process_text("تاريخ ميلادي اتناشر حداشر الفين وخمسة", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-11-12")

    # --- 3. LOCATION & ADDRESS (12 tests) ---
    def test_place_of_birth_cairo(self):
        res = self._process_text("Cairo", "place_of_birth")
        self.assertEqual(res["form_state"].get("place_of_birth"), "القاهرة")

    def test_place_of_birth_nasr_city(self):
        res = self._process_text("مدينة نصر", "place_of_birth")
        self.assertEqual(res["form_state"].get("place_of_birth"), "مدينة نصر")

    def test_country_egypt_en(self):
        res = self._process_text("Egypt", "country")
        self.assertEqual(res["form_state"].get("country"), "مصر")

    def test_governorate_giza(self):
        res = self._process_text("Giza", "governorate")
        self.assertEqual(res["form_state"].get("governorate"), "الجيزة")

    def test_district_heliopolis(self):
        res = self._process_text("Heliopolis", "district")
        self.assertEqual(res["form_state"].get("district"), "مصر الجديدة")

    def test_city_6october(self):
        res = self._process_text("6 October", "city")
        self.assertEqual(res["form_state"].get("city"), "السادس من أكتوبر")

    def test_address_mixed(self):
        res = self._process_text("20 Nagati Serag St", "address")
        addr = res["form_state"].get("address")
        self.assertIn("شارع", addr)

    def test_address_with_prefix(self):
        res = self._process_text("عنواني ٢٠ شارع نجاتي سراج", "address")
        self.assertEqual(res["form_state"].get("address"), "٢٠ شارع نجاتي سراج")

    def test_location_reject_numbers_only(self):
        res = self._process_text("123456", "city")
        self.assertIsNone(res["form_state"].get("city"))

    def test_location_preserve_ar(self):
        res = self._process_text("الشيخ زايد", "city")
        self.assertEqual(res["form_state"].get("city"), "الشيخ زايد")
        
    def test_nationality_egyptian_en(self):
        res = self._process_text("Egyptian", "nationality")
        self.assertEqual(res["form_state"].get("nationality"), "مصري")
        
    def test_nationality_masr_ar(self):
        res = self._process_text("مصر", "nationality")
        self.assertEqual(res["form_state"].get("nationality"), "مصري")

    # --- 4. IDENTITY (5 tests) ---
    def test_id_14_digits(self):
        res = self._process_text("30510201012345", "id_or_passport")
        self.assertEqual(res["form_state"].get("id_or_passport"), "30510201012345")

    def test_id_spaced(self):
        res = self._process_text("305 1020 1012345", "id_or_passport")
        self.assertEqual(res["form_state"].get("id_or_passport"), "30510201012345")

    def test_id_invalid_length(self):
        res = self._process_text("1234567890", "id_or_passport")
        self.assertIsNone(res["form_state"].get("id_or_passport"))

    def test_passport_valid(self):
        res = self._process_text("A12345678", "id_or_passport")
        self.assertEqual(res["form_state"].get("id_or_passport"), "A12345678")

    def test_id_reject_text_no_alnum(self):
        res = self._process_text("بطاقة رقم", "id_or_passport")
        self.assertIsNone(res["form_state"].get("id_or_passport"))

    # --- 5. GENDER & MARITAL (5 tests) ---
    def test_gender_male(self):
        res = self._process_text("ذكر", "gender")
        self.assertEqual(res["form_state"].get("gender"), "Male")

    def test_gender_female(self):
        res = self._process_text("female", "gender")
        self.assertEqual(res["form_state"].get("gender"), "Female")

    def test_marital_single(self):
        res = self._process_text("single", "marital_status")
        self.assertEqual(res["form_state"].get("marital_status"), "أعزب")

    def test_marital_married_ar(self):
        res = self._process_text("متزوج", "marital_status")
        self.assertEqual(res["form_state"].get("marital_status"), "متزوج")

    def test_gender_reject_invalid(self):
        res = self._process_text("other", "gender")
        self.assertIsNone(res["form_state"].get("gender"))

    # --- 6. CONTACT (10 tests) ---
    def test_mobile_010(self):
        res = self._process_text("01012345678", "student_mobile_no")
        self.assertEqual(res["form_state"].get("student_mobile_no"), "01012345678")

    def test_mobile_011(self):
        res = self._process_text("01112345678", "student_mobile_no")
        self.assertEqual(res["form_state"].get("student_mobile_no"), "01112345678")

    def test_mobile_invalid_prefix(self):
        res = self._process_text("01912345678", "student_mobile_no")
        self.assertIsNone(res["form_state"].get("student_mobile_no"))

    def test_mobile_invalid_length(self):
        res = self._process_text("010123456", "student_mobile_no")
        self.assertIsNone(res["form_state"].get("student_mobile_no"))

    def test_email_basic(self):
        res = self._process_text("test@example.com", "email_address")
        self.assertEqual(res["form_state"].get("email_address"), "test@example.com")

    def test_email_spoken_tokens(self):
        res = self._process_text("test at example dot com", "email_address")
        self.assertEqual(res["form_state"].get("email_address"), "test@example.com")

    def test_email_ar_tokens(self):
        res = self._process_text("محمود ات جيميل دوت كوم", "email_address")
        self.assertEqual(res["form_state"].get("email_address"), "محمود@جيميل.كوم")

    def test_home_phone_valid(self):
        res = self._process_text("0222678901", "home_phone")
        self.assertEqual(res["form_state"].get("home_phone"), "0222678901")

    def test_mobile_2_same_as(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["student_mobile_no"] = "01012345678"
        res = self._process_text("نفس الرقم", "mobile_no_2")
        self.assertEqual(res["form_state"].get("mobile_no_2"), "01012345678")

    def test_contact_reject_no_digits_email(self):
        res = self._process_text("رقمي هو", "student_mobile_no")
        self.assertIsNone(res["form_state"].get("student_mobile_no"))

    # --- 7. ACADEMIC (10 tests) ---
    def test_school_name_ar(self):
        res = self._process_text("مدرسة النصر", "school_name")
        self.assertEqual(res["form_state"].get("school_name"), "النصر")

    def test_certificate_thanaweya_ar(self):
        res = self._process_text("ثانوية عامة", "certificate")
        self.assertEqual(res["form_state"].get("certificate"), "Thanaweya Amma")

    def test_certificate_ig(self):
        res = self._process_text("IG", "certificate")
        self.assertEqual(res["form_state"].get("certificate"), "IGCSE")

    def test_sector_science(self):
        res = self._process_text("علمي علوم", "sector")
        self.assertEqual(res["form_state"].get("sector"), "science")

    def test_sector_math(self):
        res = self._process_text("علمي رياضة", "sector")
        self.assertEqual(res["form_state"].get("sector"), "math")

    def test_year_2024(self):
        res = self._process_text("2024", "year_of_completion")
        self.assertEqual(res["form_state"].get("year_of_completion"), 2024)

    def test_percentage_95(self):
        res = self._process_text("95%", "percentage")
        self.assertEqual(res["form_state"].get("percentage"), 95.0)

    def test_marks_410(self):
        res = self._process_text("410", "total_marks")
        self.assertEqual(res["form_state"].get("total_marks"), 410.0)

    def test_seat_number_valid(self):
        res = self._process_text("123456", "seat_number")
        self.assertEqual(res["form_state"].get("seat_number"), "123456")

    def test_academic_reject_low_percentage(self):
        res = self._process_text("101", "percentage")
        self.assertIsNone(res["form_state"].get("percentage"))

    # --- 8. GUARDIAN (12 tests) ---
    def test_guardian_name_ar(self):
        res = self._process_text("محمود محمد نجيب", "guardian_name")
        self.assertEqual(res["form_state"].get("guardian_name"), "محمود محمد نجيب")

    def test_relationship_father_en(self):
        res = self._process_text("Father", "relationship")
        self.assertEqual(res["form_state"].get("relationship"), "Father")

    def test_guardian_id_valid(self):
        res = self._process_text("28010201012345", "guardian_id_or_passport")
        self.assertEqual(res["form_state"].get("guardian_id_or_passport"), "28010201012345")

    def test_guardian_profession_ar(self):
        res = self._process_text("مهندس", "guardian_profession")
        self.assertEqual(res["form_state"].get("guardian_profession"), "مهندس")

    def test_guardian_employer_ar(self):
        res = self._process_text("شركة المقاولون العرب", "guardian_employer")
        self.assertIn("المقاولون العرب", res["form_state"].get("guardian_employer"))

    def test_guardian_address_same(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["address"] = "القاهرة"
        res = self._process_text("نفس العنوان", "guardian_address")
        self.assertEqual(res["form_state"].get("guardian_address"), "القاهرة")

    def test_guardian_mobile_valid(self):
        res = self._process_text("01098765432", "guardian_mobile_no")
        self.assertEqual(res["form_state"].get("guardian_mobile_no"), "01098765432")

    def test_relationship_reject_profession(self):
        res = self._process_text("مهندس", "relationship")
        self.assertIsNone(res["form_state"].get("relationship"))

    def test_profession_reject_relationship(self):
        res = self._process_text("الأب", "guardian_profession")
        self.assertIsNone(res["form_state"].get("guardian_profession"))

    def test_guardian_email_valid(self):
        res = self._process_text("guardian@example.com", "guardian_email_address")
        self.assertEqual(res["form_state"].get("guardian_email_address"), "guardian@example.com")
        
    def test_guardian_nationality_ar(self):
        res = self._process_text("مصري", "guardian_nationality")
        self.assertEqual(res["form_state"].get("guardian_nationality"), "مصري")
        
    def test_guardian_work_address_ar(self):
        res = self._process_text("القرية الذكية", "guardian_work_address")
        self.assertEqual(res["form_state"].get("guardian_work_address"), "القرية الذكية")

    # --- 9. FACULTY (5 tests) ---
    def test_faculty_engineering(self):
        res = self._process_text("engineering", "college_preference_1")
        self.assertEqual(res["form_state"].get("college_preference_1"), "engineering_and_technology")

    def test_faculty_pharmacy_ar(self):
        res = self._process_text("صيدلة", "college_preference_1")
        self.assertEqual(res["form_state"].get("college_preference_1"), "pharmacy_and_drug_technology")

    def test_faculty_business_en(self):
        res = self._process_text("business", "college_preference_1")
        self.assertEqual(res["form_state"].get("college_preference_1"), "economics_and_international_trade")

    def test_faculty_mass_comm_ar(self):
        res = self._process_text("اعلام", "college_preference_1")
        self.assertEqual(res["form_state"].get("college_preference_1"), "mass_communication")

    def test_faculty_reject_unknown(self):
        res = self._process_text("طب بشري", "college_preference_1")
        self.assertIsNone(res["form_state"].get("college_preference_1"))

    # --- 10. CONFIRMATION & CORRECTION (10 tests) ---
    def test_confirm_yes(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        state["metadata"]["student_mobile_no"] = {"value": "01012345678", "needs_confirmation": True}
        res = self._process_text("ايوه", "student_mobile_no")
        self.assertFalse(res["needs_confirmation"])

    def test_confirm_no(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["student_mobile_no"] = "01012345678"
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("لا", "student_mobile_no")
        self.assertNotIn("student_mobile_no", res["form_state"])

    def test_correction_name(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["full_name_ar"] = "محمود أحمد نجيل"
        state["latest_sensitive_fields"] = ["full_name_ar"]
        res = self._process_text("لا، الاسم محمود أحمد نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")

    def test_correction_mobile(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["student_mobile_no"] = "01012345678"
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("لأ الرقم هو 01112345678", "student_mobile_no")
        self.assertEqual(res["form_state"].get("student_mobile_no"), "01112345678")

    def test_correction_date(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["date_of_birth"] = "2005-12-11"
        state["latest_sensitive_fields"] = ["date_of_birth"]
        res = self._process_text("لا 12 نوفمبر 2005", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2005-11-12")

    def test_correction_id(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["id_or_passport"] = "30510201012345"
        state["latest_sensitive_fields"] = ["id_or_passport"]
        res = self._process_text("لا الرقم 30610201012345", "id_or_passport")
        self.assertEqual(res["form_state"].get("id_or_passport"), "30610201012345")

    def test_correction_city(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["city"] = "القاهرة"
        state["latest_sensitive_fields"] = ["city"]
        res = self._process_text("لا مدينة نصر", "city")
        self.assertEqual(res["form_state"].get("city"), "مدينة نصر")

    def test_correction_email(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["email_address"] = "test@gmial.com"
        state["latest_sensitive_fields"] = ["email_address"]
        res = self._process_text("لا الايميل test@gmail.com", "email_address")
        self.assertEqual(res["form_state"].get("email_address"), "test@gmail.com")

    def test_confirm_ok(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("ok", "student_mobile_no")
        self.assertFalse(res["needs_confirmation"])

    def test_confirm_صح(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("صح", "student_mobile_no")
        self.assertFalse(res["needs_confirmation"])

    # --- 11. EXTRA EDGE CASES (16 tests) ---
    def test_compact_date_leap_year(self):
        res = self._process_text("29022004", "date_of_birth")
        self.assertEqual(res["form_state"].get("date_of_birth"), "2004-02-29")
        
    def test_compact_date_invalid_leap(self):
        res = self._process_text("29022005", "date_of_birth")
        self.assertIsNone(res["form_state"].get("date_of_birth"))
        
    def test_mobile_with_dashes(self):
        res = self._process_text("010-1234-5678", "student_mobile_no")
        self.assertEqual(res["form_state"].get("student_mobile_no"), "01012345678")
        
    def test_mobile_spoken_digits_mix(self):
        res = self._process_text("زيرو واحد صفر 12345678", "student_mobile_no")
        self.assertEqual(res["form_state"].get("student_mobile_no"), "01012345678")
        
    def test_email_with_underscore_spoken(self):
        res = self._process_text("mahmoud underscore nagib at gmail dot com", "email_address")
        self.assertEqual(res["form_state"].get("email_address"), "mahmoud_nagib@gmail.com")
        
    def test_percentage_with_decimal_spoken(self):
        res = self._process_text("خمسة وتسعين ونص", "percentage")
        self.assertEqual(res["form_state"].get("percentage"), 95.5)
        
    def test_marks_out_of(self):
        res = self._process_text("390 من 410", "total_marks")
        self.assertEqual(res["form_state"].get("total_marks"), 390.0)
        
    def test_guardian_name_with_relationship_prefix(self):
        res = self._process_text("والدي محمود محمد نجيب", "guardian_name")
        self.assertEqual(res["form_state"].get("guardian_name"), "محمود محمد نجيب")
        
    def test_address_english_to_arabic_transliteration(self):
        # This might use LLM or direct map. 
        # Since we have "Maadi" in map, let's test it.
        res = self._process_text("20 Road 9 Maadi", "address")
        addr = res["form_state"].get("address")
        self.assertIn("المعادي", addr)
        self.assertIn("طريق", addr)
        
    def test_year_spoken_ar(self):
        res = self._process_text("سنة الفين اربعة وعشرين", "year_of_completion")
        self.assertEqual(res["form_state"].get("year_of_completion"), 2024)
        
    def test_marital_widow_ar(self):
        res = self._process_text("أرملة", "marital_status")
        self.assertEqual(res["form_state"].get("marital_status"), "أرمل")
        
    def test_relationship_sister_ar(self):
        res = self._process_text("أختي", "relationship")
        self.assertEqual(res["form_state"].get("relationship"), "Sister")
        
    def test_nationality_reject_profession(self):
        res = self._process_text("مهندس", "nationality")
        self.assertIsNone(res["form_state"].get("nationality"))
        
    def test_profession_reject_relationship(self):
        res = self._process_text("الأب", "guardian_profession")
        self.assertIsNone(res["form_state"].get("guardian_profession"))
        
    def test_correction_last_name_only(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["full_name_ar"] = "محمود أحمد نجيل"
        state["fields"]["full_name_en"] = "Mahmoud Ahmed Njyl"
        state["latest_sensitive_fields"] = ["full_name_ar"]
        res = self._process_text("لا الاسم الاخير نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")
        self.assertEqual(res["form_state"].get("full_name_en"), "Mahmoud Ahmed Nagib")
        
    def test_correction_english_name_only(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["full_name_ar"] = "محمود أحمد نجيب"
        state["fields"]["full_name_en"] = "Mahmoud Ahmed Nagib"
        state["latest_sensitive_fields"] = ["full_name_ar"]
        res = self._process_text("لا الاسم بالانجليزي Nagib", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_en"), "Mahmoud Ahmed Nagib")

    # --- 12. FLOW & STATE (5 tests) ---
    def test_guided_flow_advances(self):
        # 1. Fill name
        res = self._process_text("محمود أحمد نجيب", "full_name_ar")
        self.assertEqual(res["form_state"].get("full_name_ar"), "محمود أحمد نجيب")
        # 2. Confirm
        res = self._process_text("تمام", "full_name_ar")
        # 3. Next should be date_of_birth
        self.assertEqual(self.engine.sessions[self.session_id]["current_field"], "date_of_birth")

    def test_ambiguous_confirmation_clarifies(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("مش عارف", "student_mobile_no")
        self.assertIn("تأكيد", res["next_question"])

    def test_reject_clears_field(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["student_mobile_no"] = "01012345678"
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("لا غلط", "student_mobile_no")
        self.assertNotIn("student_mobile_no", res["form_state"])

    def test_correction_re_asks_confirmation(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["student_mobile_no"] = "01012345678"
        state["latest_sensitive_fields"] = ["student_mobile_no"]
        res = self._process_text("لا الرقم 01112345678", "student_mobile_no")
        self.assertTrue(res["needs_confirmation"])
        self.assertIn("01112345678", res["next_question"])

    def test_missing_required_fields_list(self):
        state = self.engine._get_or_create_session_state(self.session_id)
        state["fields"]["full_name_ar"] = "محمود أحمد نجيب"
        # Many are missing
        missing = self.engine._missing_required_fields(state["fields"])
        self.assertIn("date_of_birth", missing)

if __name__ == "__main__":
    unittest.main()
