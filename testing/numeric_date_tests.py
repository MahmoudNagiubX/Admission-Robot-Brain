
import unittest
from registration import RegistrationEngine
from models import ProcessedText

class TestNumericDateParsing(unittest.TestCase):
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
        
        return self.engine.process(self.session_id, processed, language)

    # Date Parsing Tests
    def test_date_numeric_spaces_dd_mm_yyyy(self):
        result = self._process_text("11 12 2005", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-12-11")

    def test_date_with_arabic_phrase(self):
        result = self._process_text("تاريخ ميلادي هو 11 12 2005", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-12-11")

    def test_date_arabic_month_name(self):
        result = self._process_text("12 نوفمبر 2005", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-11-12")

    def test_date_arabic_month_spoken_year(self):
        result = self._process_text("12 نوفمبر ألفين وخمسة", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-11-12")

    def test_date_arabic_spoken_day_month_year(self):
        result = self._process_text("اتناشر نوفمبر ألفين وخمسة", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-11-12")

    def test_date_invalid_month_rejected(self):
        result = self._process_text("12 15 2005", "date_of_birth")
        self.assertIsNone(result["form_state"].get("date_of_birth"))

    # Compact Date Tests
    def test_compact_date_ddmmyyyy(self):
        result = self._process_text("11122005", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-12-11")

    def test_compact_date_12112005(self):
        result = self._process_text("12112005", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-11-12")

    def test_compact_date_inside_arabic_phrase(self):
        result = self._process_text("تاريخ ميلادي 11122005", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-12-11")

    def test_compact_date_invalid_month_rejected(self):
        result = self._process_text("11132005", "date_of_birth")
        self.assertIsNone(result["form_state"].get("date_of_birth"))

    def test_compact_date_invalid_day_rejected(self):
        result = self._process_text("32122005", "date_of_birth")
        self.assertIsNone(result["form_state"].get("date_of_birth"))

    # Colloquial Arabic Date Tests
    def test_colloquial_arabic_numeric_date_words(self):
        result = self._process_text("اتناشر حداشر الفين وخمسة", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-11-12")

    def test_colloquial_arabic_phrase_date_words(self):
        result = self._process_text("انا اتولدت يوم اتناشر حداشر الفين وخمسة", "date_of_birth")
        self.assertEqual(result["form_state"].get("date_of_birth"), "2005-11-12")

    def test_retry_prompt_mentions_compact_date(self):
        # Trigger retry for date_of_birth
        processed = ProcessedText(
            raw_text="invalid date",
            normalized_text="invalid date",
            protected_text="invalid date",
            corrected_text="invalid date",
            search_query="invalid date",
            language="ar",
            entities={}
        )
        state = self.engine._get_or_create_session_state(self.session_id)
        state["current_field"] = "date_of_birth"
        state["guided_flow"] = True
        
        result = self.engine.process(self.session_id, processed, "ar")
        self.assertIn("11122005", result["next_question"])

    # Phone Parsing Tests
    def test_mobile_compact_digits(self):
        result = self._process_text("01012345678", "student_mobile_no")
        self.assertEqual(result["form_state"].get("student_mobile_no"), "01012345678")

    def test_mobile_spaced_digits(self):
        result = self._process_text("0 1 0 1 2 3 4 5 6 7 8", "student_mobile_no")
        self.assertEqual(result["form_state"].get("student_mobile_no"), "01012345678")

    def test_mobile_arabic_spoken_digits(self):
        result = self._process_text("صفر واحد صفر واحد اتنين تلاتة اربعة خمسة ستة سبعة تمانية", "student_mobile_no")
        self.assertEqual(result["form_state"].get("student_mobile_no"), "01012345678")

    def test_mobile_incomplete_rejected(self):
        result = self._process_text("010123", "student_mobile_no")
        self.assertIsNone(result["form_state"].get("student_mobile_no"))

    # National ID Tests
    def test_national_id_14_digits(self):
        result = self._process_text("30510201012345", "id_or_passport")
        self.assertEqual(result["form_state"].get("id_or_passport"), "30510201012345")

    def test_national_id_spaced_digits(self):
        result = self._process_text("305 1020 1012345", "id_or_passport")
        self.assertEqual(result["form_state"].get("id_or_passport"), "30510201012345")

    def test_national_id_incomplete_rejected(self):
        result = self._process_text("305201", "id_or_passport")
        self.assertIsNone(result["form_state"].get("id_or_passport"))

    # Confirmation Tests
    def test_confirmation_yes_variants_arabic(self):
        variants = ["نعم", "أيوه", "تمام", "صح", "مظبوط"]
        for variant in variants:
            # Setup a pending confirmation
            state = self.engine._get_or_create_session_state(self.session_id)
            state["latest_sensitive_fields"] = ["student_mobile_no"]
            state["fields"]["student_mobile_no"] = "01012345678"
            state["metadata"]["student_mobile_no"] = {"confirmed": False}
            
            result = self._process_text(variant, language="ar")
            self.assertTrue(state["metadata"]["student_mobile_no"]["confirmed"])

    def test_confirmation_no_variants_arabic(self):
        variants = ["لا", "لأ", "غلط", "مش صح", "غير صحيح"]
        for variant in variants:
            test_session_id = f"{self.session_id}-{variant}"
            state = self.engine._get_or_create_session_state(test_session_id)
            state["latest_sensitive_fields"] = ["student_mobile_no"]
            state["fields"]["student_mobile_no"] = "01012345678"
            state["metadata"]["student_mobile_no"] = {"confirmed": False}
            
            processed = ProcessedText(
                raw_text=variant,
                normalized_text=variant,
                protected_text=variant,
                corrected_text=variant,
                search_query=variant,
                language="ar",
                entities={}
            )
            result = self.engine.process(test_session_id, processed, "ar")
            with self.subTest(variant=variant):
                self.assertNotIn("student_mobile_no", state["fields"])

    def test_confirmation_yes_variants_english(self):
        variants = ["yes", "ok", "correct", "confirm"]
        for variant in variants:
            test_session_id = f"{self.session_id}-{variant}"
            state = self.engine._get_or_create_session_state(test_session_id)
            state["latest_sensitive_fields"] = ["student_mobile_no"]
            state["fields"]["student_mobile_no"] = "01012345678"
            state["metadata"]["student_mobile_no"] = {"confirmed": False}
            
            processed = ProcessedText(
                raw_text=variant,
                normalized_text=variant,
                protected_text=variant,
                corrected_text=variant,
                search_query=variant,
                language="en",
                entities={}
            )
            result = self.engine.process(test_session_id, processed, "en")
            self.assertTrue(state["metadata"]["student_mobile_no"]["confirmed"])

    def test_confirmation_no_variants_english(self):
        variants = ["no", "wrong", "incorrect", "retry"]
        for variant in variants:
            test_session_id = f"{self.session_id}-{variant}"
            state = self.engine._get_or_create_session_state(test_session_id)
            state["latest_sensitive_fields"] = ["student_mobile_no"]
            state["fields"]["student_mobile_no"] = "01012345678"
            state["metadata"]["student_mobile_no"] = {"confirmed": False}
            
            processed = ProcessedText(
                raw_text=variant,
                normalized_text=variant,
                protected_text=variant,
                corrected_text=variant,
                search_query=variant,
                language="en",
                entities={}
            )
            result = self.engine.process(test_session_id, processed, "en")
            self.assertNotIn("student_mobile_no", state["fields"])

if __name__ == "__main__":
    unittest.main()
