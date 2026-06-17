
import unittest
from registration import RegistrationEngine
from models import ProcessedText

class TestManualCorrection(unittest.TestCase):
    def setUp(self):
        self.engine = RegistrationEngine()
        self.session_id = "test_session_correction"
        # Reset session
        if self.session_id in self.engine.sessions:
            del self.engine.sessions[self.session_id]

    def _process_text(self, text, language="ar"):
        processed = ProcessedText(
            raw_text=text,
            normalized_text=text,
            protected_text=text,
            corrected_text=text,
            search_query=text,
            language=language,
            entities={}
        )
        return self.engine.process(self.session_id, processed, language)

    def _setup_pending_confirmation(self, fields_values, language="ar"):
        state = self.engine._get_or_create_session_state(self.session_id)
        # Mark ALL fields as confirmed by default
        for field_id in self.engine.field_order:
            state["fields"][field_id] = "some value"
            state["metadata"][field_id] = {"confirmed": True}
        
        # Now set the pending ones
        state["latest_sensitive_fields"] = list(fields_values.keys())
        state["guided_flow"] = True
        for field, val in fields_values.items():
            state["fields"][field] = val
            state["metadata"][field] = {"confirmed": False, "needs_confirmation": True}
            
        # Re-sync current field
        self.engine._sync_current_field(state, language)
        return state

    def test_pending_name_correction_last_name_arabic(self):
        # Setup with name fields NOT confirmed yet
        state = self.engine._get_or_create_session_state(self.session_id)
        # Clear fields for fresh start
        state["fields"] = {}
        state["metadata"] = {}
        
        state["fields"]["full_name_ar"] = "محمود أحمد نجيل"
        state["fields"]["full_name_en"] = "Mahmoud Ahmed Njyl"
        state["metadata"]["full_name_ar"] = {"confirmed": False, "needs_confirmation": True}
        state["metadata"]["full_name_en"] = {"confirmed": False, "needs_confirmation": True}
        state["latest_sensitive_fields"] = ["full_name_ar", "full_name_en"]
        state["guided_flow"] = True
        state["current_field"] = "full_name_ar"

        result = self._process_text("لا، الاسم الأخير نجيب")
        state = self.engine.sessions[self.session_id]
        # The correction might return a normalized version without hamza or with different hamza
        # but "نجيب" and "Nagib" must be there.
        self.assertTrue(any("نجيب" in str(v) for v in state["fields"].values()))
        self.assertTrue(any("Nagib" in str(v) for v in state["fields"].values()))
        self.assertTrue(result["needs_confirmation"])

    def test_pending_name_correction_full_arabic_name(self):
        self._setup_pending_confirmation({
            "full_name_ar": "محمود أحمد نجيل",
            "full_name_en": "Mahmoud Ahmed Njyl"
        })
        result = self._process_text("صححه إلى محمود محمد نجيب")
        state = self.engine.sessions[self.session_id]
        self.assertIn("محمود", state["fields"]["full_name_ar"])
        self.assertIn("محمد", state["fields"]["full_name_ar"])
        self.assertIn("نجيب", state["fields"]["full_name_ar"])
        self.assertTrue(result["needs_confirmation"])

    def test_pending_name_correction_full_english_name(self):
        self._setup_pending_confirmation({
            "full_name_ar": "محمود أحمد نجيل",
            "full_name_en": "Mahmoud Ahmed Njyl"
        })
        result = self._process_text("correct it to Mahmoud Ahmed Nagib", language="en")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["full_name_en"], "Mahmoud Ahmed Nagib")
        # Check that AR name is also updated and looks correct
        self.assertIn("محمود", state["fields"]["full_name_ar"])
        self.assertIn("نجيب", state["fields"]["full_name_ar"])
        self.assertTrue(result["needs_confirmation"])

    def test_pending_date_correction_arabic_month(self):
        self._setup_pending_confirmation({"date_of_birth": "2005-12-11"})
        result = self._process_text("لا، 12 نوفمبر 2005")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["date_of_birth"], "2005-11-12")
        self.assertTrue(result["needs_confirmation"])

    def test_pending_date_correction_compact_digits(self):
        self._setup_pending_confirmation({"date_of_birth": "2005-12-15"})
        result = self._process_text("لا، التاريخ 11122005")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["date_of_birth"], "2005-12-11")
        self.assertTrue(result["needs_confirmation"])

    def test_pending_mobile_correction(self):
        self._setup_pending_confirmation({"student_mobile_no": "01012345678"})
        result = self._process_text("لا، الرقم 01112345678")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["student_mobile_no"], "01112345678")
        self.assertTrue(result["needs_confirmation"])

    def test_pending_id_correction(self):
        self._setup_pending_confirmation({"id_or_passport": "30510201012345"})
        result = self._process_text("لا، البطاقة 30510201012346")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["id_or_passport"], "30510201012346")
        self.assertTrue(result["needs_confirmation"])

    def test_pending_city_correction_english_to_arabic(self):
        self._setup_pending_confirmation({"city": "مدينة نصر"})
        result = self._process_text("change it to New Cairo", language="en")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["city"], "القاهرة الجديدة")
        self.assertTrue(result["needs_confirmation"])

    def test_pending_address_correction_arabic(self):
        self._setup_pending_confirmation({"address": "20 شارع نجاتي سراج"})
        result = self._process_text("لا، العنوان 25 شارع عباس العقاد مدينة نصر")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["address"], "25 شارع عباس العقاد مدينة نصر")
        self.assertTrue(result["needs_confirmation"])

    def test_pending_general_field_correction_profession(self):
        self._setup_pending_confirmation({"guardian_profession": "مهندس"})
        result = self._process_text("صححها إلى طبيب")
        state = self.engine.sessions[self.session_id]
        self.assertEqual(state["fields"]["guardian_profession"], "طبيب")
        self.assertTrue(result["needs_confirmation"])

    def test_reject_without_value_repeats_question(self):
        state = self._setup_pending_confirmation({"student_mobile_no": "01012345678"})
        result = self._process_text("لا")
        state = self.engine.sessions[self.session_id]
        self.assertNotIn("student_mobile_no", state["fields"])
        self.assertFalse(result["needs_confirmation"])
        # Use partial match for the question to be safe
        self.assertTrue(any(word in result["next_question"] for word in ["موبايل", "mobile"]))

    def test_ambiguous_confirmation_asks_clarification(self):
        self._setup_pending_confirmation({"student_mobile_no": "01012345678"})
        result = self._process_text("مش عارف")
        self.assertTrue(result["needs_confirmation"])
        self.assertTrue(any(word in result["next_question"] for word in ["تأكيد", "تعديل", "confirm", "correct"]))

    def test_corrected_field_still_requires_confirmation(self):
        self._setup_pending_confirmation({"guardian_profession": "مهندس"})
        self._process_text("صححها إلى طبيب")
        state = self.engine.sessions[self.session_id]
        self.assertFalse(state["metadata"]["guardian_profession"]["confirmed"])
        self.assertTrue(state["metadata"]["guardian_profession"]["needs_confirmation"])

if __name__ == "__main__":
    unittest.main()
