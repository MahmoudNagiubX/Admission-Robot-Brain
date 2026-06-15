"""
Text Intelligence Layer.

This file prepares raw STT text before it enters the AI Brain.

Current step:
- keep raw text
- normalize Unicode text
- normalize Arabic letters
- remove Arabic diacritics
- remove tatweel
- normalize Arabic/Persian digits to English digits
- normalize punctuation
- remove extra spaces

Future steps:
- spoken number conversion
- phone / ID / email protection
- faculty name detection
- fuzzy correction
"""

import re
import unicodedata

from models import ProcessedText


class TextProcessor:
    """
    Cleans and prepares text before brain routing.
    """

    def process(self, raw_text: str, language: str) -> ProcessedText:
        """
        Process raw STT text into a clean structured package.
        """

        normalized_text = self._normalize_text(raw_text, language)

        # For now, these are still the same.
        # Later:
        # protected_text will preserve phone, ID, email, grades, etc.
        # corrected_text will include domain-specific fixes.
        # search_query will become optimized for FAQ/RAG search.
        protected_text = normalized_text
        corrected_text = normalized_text
        search_query = normalized_text

        return ProcessedText(
            raw_text=raw_text,
            normalized_text=normalized_text,
            protected_text=protected_text,
            corrected_text=corrected_text,
            search_query=search_query,
            language=language,
            entities={},
            route_notes=[
                "raw_text_saved",
                "unicode_normalized",
                "digits_normalized",
                "punctuation_normalized",
                "arabic_text_normalized",
                "extra_spaces_removed",
                "phase_2_step_1_text_normalization_completed",
            ],
        )

    def _normalize_text(self, text: str, language: str) -> str:
        """
        Run the full normalization pipeline.
        """

        text = self._normalize_unicode(text)
        text = self._normalize_digits(text)
        text = self._remove_arabic_diacritics(text)
        text = self._remove_tatweel(text)
        text = self._normalize_arabic_letters(text)
        text = self._normalize_punctuation(text)
        text = self._normalize_spaces(text)

        if language == "en":
            text = text.lower()

        return text

    def _normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode characters to a consistent form.
        """

        return unicodedata.normalize("NFKC", text)

    def _normalize_digits(self, text: str) -> str:
        """
        Convert Arabic-Indic and Persian digits to English digits.

        Examples:
        ١٢٣ → 123
        ۱۲۳ → 123
        """

        digit_map = {
            "٠": "0",
            "١": "1",
            "٢": "2",
            "٣": "3",
            "٤": "4",
            "٥": "5",
            "٦": "6",
            "٧": "7",
            "٨": "8",
            "٩": "9",
            "۰": "0",
            "۱": "1",
            "۲": "2",
            "۳": "3",
            "۴": "4",
            "۵": "5",
            "۶": "6",
            "۷": "7",
            "۸": "8",
            "۹": "9",
        }

        return "".join(digit_map.get(char, char) for char in text)

    def _remove_arabic_diacritics(self, text: str) -> str:
        """
        Remove Arabic tashkeel/diacritics.

        Example:
        كُلِّيَّة → كلية
        """

        arabic_diacritics_pattern = re.compile(
            r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
        )
        return re.sub(arabic_diacritics_pattern, "", text)

    def _remove_tatweel(self, text: str) -> str:
        """
        Remove Arabic tatweel character.

        Example:
        كليــــة → كلية
        """

        return text.replace("ـ", "")

    def _normalize_arabic_letters(self, text: str) -> str:
        """
        Normalize common Arabic letter variants.

        This helps search and matching.
        We keep it moderate, not too aggressive.
        """

        replacements = {
            "أ": "ا",
            "إ": "ا",
            "آ": "ا",
            "ٱ": "ا",
            "ى": "ي",
            "ؤ": "و",
            "ئ": "ي",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def _normalize_punctuation(self, text: str) -> str:
        """
        Normalize punctuation characters and repeated punctuation.
        """

        replacements = {
            "،": ",",
            "؛": ";",
            "؟": "?",
            "“": '"',
            "”": '"',
            "‘": "'",
            "’": "'",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Reduce repeated punctuation.
        text = re.sub(r"([?!.,;])\1+", r"\1", text)

        # Remove space before punctuation.
        text = re.sub(r"\s+([?!.,;])", r"\1", text)

        # Ensure one space after punctuation if followed by text.
        text = re.sub(r"([?!.,;])([^\s])", r"\1 \2", text)

        return text

    def _normalize_spaces(self, text: str) -> str:
        """
        Remove leading/trailing spaces and replace multiple spaces with one space.
        """

        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text