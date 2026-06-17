
import unittest
import os
import json
from registration import RegistrationEngine
from models import ProcessedText

class TestNameLexiconSystem(unittest.TestCase):
    def setUp(self):
        self.engine = RegistrationEngine()
        self.session_id = "test-lexicon-session"

    def test_name_question_does_not_use_only(self):
        question_en = self.engine.prompts["full_name_ar"]["en"]
        question_ar = self.engine.prompts["full_name_ar"]["ar"]
        self.assertNotIn("only", question_en.lower())
        self.assertNotIn("فقط", question_ar)

    def test_name_lexicon_file_exists_and_loads(self):
        self.assertTrue(os.path.exists("data/name_lexicon.json"))
        self.assertGreater(len(self.engine.name_lookup_en), 100)
        self.assertGreater(len(self.engine.name_lookup_ar), 100)

    def test_name_intake_zeyad_omar_farouk_generates_arabic(self):
        res = self.engine._generate_name_pair("Zeyad Omar Farouk", "en")
        self.assertEqual(res.get("full_name_ar"), "زياد عمر فاروق")
        self.assertEqual(res.get("full_name_en"), "Zeyad Omar Farouk")

    def test_name_intake_arabic_omar_zeyad_farouk_generates_english(self):
        res = self.engine._generate_name_pair("عمر زياد فاروق", "ar")
        self.assertEqual(res.get("full_name_en"), "Omar Zeyad Farouk")
        self.assertEqual(res.get("full_name_ar"), "عمر زياد فاروق")

    def test_name_intake_abdelrahman_compound_supported(self):
        res = self.engine._generate_name_pair("Abdelrahman Ahmed", "en")
        self.assertIn("عبد الرحمن", res.get("full_name_ar"))

    def test_name_intake_abdullah_compound_supported(self):
        res = self.engine._generate_name_pair("Abdullah Mohamed", "en")
        self.assertIn("عبد الله", res.get("full_name_ar"))

    def test_name_intake_mina_george_fady_supported(self):
        res = self.engine._generate_name_pair("Mina George Fady", "en")
        self.assertEqual(res.get("full_name_ar"), "مينا جورج فادي")

    def test_fuzzy_name_mahamud_maps_to_mahmoud(self):
        res = self.engine._generate_name_pair("Mahamud Ahmed", "en")
        self.assertEqual(res.get("full_name_en"), "Mahmoud Ahmed")

    def test_fuzzy_name_ahman_maps_to_ahmed(self):
        res = self.engine._generate_name_pair("Ahman Mahmoud", "en")
        self.assertEqual(res.get("full_name_en"), "Ahmed Mahmoud")

    def test_fuzzy_name_farok_maps_to_farouk(self):
        res = self.engine._generate_name_pair("Zeyad Farok", "en")
        self.assertEqual(res.get("full_name_en"), "Zeyad Farouk")

    def test_name_intake_removes_messy_prefix_still_works(self):
        input_text = "ماي فول ني من أربيك إذ زياد عمر فاروق"
        res = self.engine._generate_name_pair(input_text, "ar")
        self.assertEqual(res.get("full_name_ar"), "زياد عمر فاروق")
        # en primary for زياد is Zeyad in my builder
        self.assertEqual(res.get("full_name_en"), "Zeyad Omar Farouk")

    def test_noise_words_not_saved_in_validation(self):
        val, ok = self.engine._validate_arabic_name("زياد عمر فاروق فقط")
        self.assertFalse(ok)
        
        val, ok = self.engine._validate_english_name("Zeyad Omar Farouk only")
        self.assertFalse(ok)

    def test_unknown_name_uses_phonetic_fallback(self):
        # Using a name unlikely to be in lexicon: "Zalaf"
        res = self.engine._generate_name_pair("Zalaf Ahmed", "en")
        self.assertEqual(res.get("full_name_ar"), "زالاف أحمد")

    def test_compound_arabic_matching(self):
        res = self.engine._generate_name_pair("عبد الرحمن محمد", "ar")
        self.assertEqual(res.get("full_name_en"), "Abdelrahman Mohamed")

    def test_mahmoud_mohamed_nagib(self):
        res = self.engine._generate_name_pair("محمود محمد نجيب", "ar")
        # print(f"DEBUG: {res}")
        self.assertEqual(res.get("full_name_en"), "Mahmoud Mohamed Nagib")

if __name__ == "__main__":
    unittest.main()
