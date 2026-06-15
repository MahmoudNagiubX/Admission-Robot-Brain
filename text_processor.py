"""
Text Intelligence Layer for Admission Robot.

This file is responsible for preparing raw STT text before it enters the AI Brain.

Main jobs:
1. Preserve raw text for debugging.
2. Normalize Arabic and English text.
3. Normalize Arabic/Persian digits to English digits.
4. Convert simple spoken digit sequences into numeric strings.
5. Extract and protect sensitive entities:
   - emails
   - Egyptian phone numbers
   - Egyptian national IDs
   - percentages
   - years
6. Detect ECU faculties and intent hints.
7. Build a search query for FAQ/RAG routing.

This module does not answer questions.
It only prepares text safely.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from config import FACULTY_ALIASES, INTENT_ALIASES
from models import ProcessedText


class TextProcessor:
    """
    Prepares raw STT text for brain routing.
    """

    def process(self, raw_text: str, language: str) -> ProcessedText:
        """
        Convert raw text into a complete processed package.
        """

        normalized_text = self._normalize_text(raw_text, language)
        protected_text, protected_entities = self._extract_and_protect_entities(normalized_text)
        domain_entities = self._detect_domain_entities(normalized_text)

        entities: dict[str, Any] = {
            **protected_entities,
            **domain_entities,
        }

        corrected_text = self._build_corrected_text(normalized_text, entities)
        search_query = self._build_search_query(corrected_text, entities)

        return ProcessedText(
            raw_text=raw_text,
            normalized_text=normalized_text,
            protected_text=protected_text,
            corrected_text=corrected_text,
            search_query=search_query,
            language=language,
            entities=entities,
            route_notes=[
                "raw_text_saved",
                "unicode_normalized",
                "arabic_letters_normalized",
                "arabic_diacritics_removed",
                "digits_normalized",
                "spoken_digit_sequences_normalized",
                "punctuation_normalized",
                "extra_spaces_removed",
                "protected_entities_extracted",
                "faculty_and_intent_detected",
                "search_query_built",
                "text_intelligence_layer_completed",
            ],
        )

    # ---------------------------------------------------------------------
    # Normalization
    # ---------------------------------------------------------------------

    def _normalize_text(self, text: str, language: str) -> str:
        """
        Run the complete safe normalization pipeline.
        """

        text = self._normalize_unicode(text)
        text = self._normalize_digits(text)
        text = self._remove_arabic_diacritics(text)
        text = self._remove_tatweel(text)
        text = self._normalize_arabic_letters(text)
        text = self._normalize_punctuation(text)
        text = self._normalize_spaces(text)
        text = self._normalize_spoken_digit_sequences(text)
        text = self._normalize_spaces(text)

        if language == "en":
            text = text.lower()

        return text

    def _normalize_unicode(self, text: str) -> str:
        return unicodedata.normalize("NFKC", text)

    def _normalize_digits(self, text: str) -> str:
        """
        Convert Arabic-Indic and Persian digits to English digits.
        """

        digit_map = {
            "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
            "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
            "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
            "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
        }

        return "".join(digit_map.get(char, char) for char in text)

    def _remove_arabic_diacritics(self, text: str) -> str:
        arabic_diacritics_pattern = re.compile(
            r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]"
        )
        return re.sub(arabic_diacritics_pattern, "", text)

    def _remove_tatweel(self, text: str) -> str:
        return text.replace("ـ", "")

    def _normalize_arabic_letters(self, text: str) -> str:
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
        Normalize punctuation safely.

        Important:
        We do not add spaces after dots because that breaks:
        - emails: test@example.com
        - decimals: 92.5
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

        # Reduce repeated punctuation except dot.
        text = re.sub(r"([?!,;])\1+", r"\1", text)

        # Remove space before punctuation.
        text = re.sub(r"\s+([?!.,;])", r"\1", text)

        # Add one space after punctuation except dot.
        text = re.sub(r"([?!,;])([^\s])", r"\1 \2", text)

        return text

    def _normalize_spaces(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    # ---------------------------------------------------------------------
    # Spoken digit normalization
    # ---------------------------------------------------------------------

    def _normalize_spoken_digit_sequences(self, text: str) -> str:
        """
        Convert clear spoken digit sequences into normal digits.

        Examples:
        zero one zero one two three four five six seven eight -> 01012345678
        صفر واحد صفر واحد اتنين -> 01012

        Rule:
        Convert only sequences of at least 3 digit words to avoid changing normal phrases.
        """

        digit_words = {
            # English
            "zero": "0", "oh": "0", "o": "0",
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "nine": "9",

            # Arabic common forms after normalization
            "صفر": "0", "زيرو": "0",
            "واحد": "1", "واحدة": "1",
            "اتنين": "2", "اثنين": "2", "تنين": "2",
            "تلاتة": "3", "ثلاثة": "3", "تلات": "3",
            "اربعة": "4", "اربعه": "4",
            "خمسة": "5", "خمسه": "5",
            "ستة": "6", "سته": "6",
            "سبعة": "7", "سبعه": "7",
            "تمانية": "8", "ثمانية": "8", "تمانيه": "8",
            "تسعة": "9", "تسعه": "9",
        }

        tokens = text.split()
        output_tokens: list[str] = []
        index = 0

        while index < len(tokens):
            sequence_digits: list[str] = []
            sequence_start = index

            while index < len(tokens):
                clean_token = re.sub(r"[^\w\u0600-\u06FF]", "", tokens[index]).lower()

                if clean_token not in digit_words:
                    break

                sequence_digits.append(digit_words[clean_token])
                index += 1

            if len(sequence_digits) >= 3:
                output_tokens.append("".join(sequence_digits))
            else:
                output_tokens.extend(tokens[sequence_start:index])

            if index < len(tokens):
                output_tokens.append(tokens[index])
                index += 1

        return " ".join(output_tokens)

    # ---------------------------------------------------------------------
    # Protected entity extraction
    # ---------------------------------------------------------------------

    def _extract_and_protect_entities(self, text: str) -> tuple[str, dict[str, Any]]:
        """
        Extract important values and replace them with placeholders.
        """

        matches: list[dict[str, Any]] = []

        self._collect_email_matches(text, matches)
        self._collect_national_id_matches(text, matches)
        self._collect_phone_matches(text, matches)
        self._collect_percentage_matches(text, matches)
        self._collect_year_matches(text, matches)

        matches = self._remove_overlapping_matches(matches)
        matches = sorted(matches, key=lambda item: item["start"])

        entities: dict[str, Any] = {
            "emails": [],
            "phones": [],
            "national_ids": [],
            "percentages": [],
            "years": [],
        }

        counters = {
            "email": 0,
            "phone": 0,
            "national_id": 0,
            "percentage": 0,
            "year": 0,
        }

        for match in matches:
            entity_type = match["type"]
            counters[entity_type] += 1
            placeholder = f"<{entity_type.upper()}_{counters[entity_type]}>"
            match["placeholder"] = placeholder

            entities[self._entity_list_name(entity_type)].append(
                {
                    "value": match["value"],
                    "raw_value": match["raw_value"],
                    "placeholder": placeholder,
                    "confidence": match["confidence"],
                    "start": match["start"],
                    "end": match["end"],
                }
            )

        protected_text = text

        # Replace from the end to keep spans stable.
        for match in sorted(matches, key=lambda item: item["start"], reverse=True):
            protected_text = (
                protected_text[: match["start"]]
                + match["placeholder"]
                + protected_text[match["end"] :]
            )

        protected_text = self._normalize_spaces(protected_text)

        return protected_text, entities

    def _collect_email_matches(self, text: str, matches: list[dict[str, Any]]) -> None:
        email_pattern = re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        )

        for found in email_pattern.finditer(text):
            matches.append(
                {
                    "type": "email",
                    "value": found.group(0),
                    "raw_value": found.group(0),
                    "confidence": 1.0,
                    "start": found.start(),
                    "end": found.end(),
                }
            )

    def _collect_phone_matches(self, text: str, matches: list[dict[str, Any]]) -> None:
        """
        Detect Egyptian mobile numbers.

        Accepts:
        01012345678
        010 1234 5678
        +201012345678
        00201012345678
        """

        phone_pattern = re.compile(
            r"(?<!\d)(?:(?:\+?20|0020)\s?)?0?1[0125](?:[\s\-]?\d){8}(?!\d)"
        )

        for found in phone_pattern.finditer(text):
            raw_value = found.group(0)
            digits_only = re.sub(r"\D", "", raw_value)

            if digits_only.startswith("0020"):
                digits_only = digits_only[4:]

            if digits_only.startswith("20") and len(digits_only) == 12:
                digits_only = digits_only[2:]

            if re.fullmatch(r"1[0125]\d{8}", digits_only):
                digits_only = "0" + digits_only

            if re.fullmatch(r"01[0125]\d{8}", digits_only):
                matches.append(
                    {
                        "type": "phone",
                        "value": digits_only,
                        "raw_value": raw_value,
                        "confidence": 1.0,
                        "start": found.start(),
                        "end": found.end(),
                    }
                )

    def _collect_national_id_matches(self, text: str, matches: list[dict[str, Any]]) -> None:
        """
        Detect Egyptian 14-digit national ID.
        Allows spaces/dashes between digits.
        """

        national_id_pattern = re.compile(r"(?<!\d)[23](?:[\s\-]?\d){13}(?!\d)")

        for found in national_id_pattern.finditer(text):
            raw_value = found.group(0)
            digits_only = re.sub(r"\D", "", raw_value)

            if re.fullmatch(r"[23]\d{13}", digits_only):
                matches.append(
                    {
                        "type": "national_id",
                        "value": digits_only,
                        "raw_value": raw_value,
                        "confidence": 1.0,
                        "start": found.start(),
                        "end": found.end(),
                    }
                )

    def _collect_percentage_matches(self, text: str, matches: list[dict[str, Any]]) -> None:
        percentage_pattern = re.compile(
            r"(?<!\d)(\d{1,3}(?:\.\d{1,2})?)\s*"
            r"(?:%|percent|percentage|في المية|في الميه|بالمية|بالمئه|بالمئة)(?!\w)"
        )

        for found in percentage_pattern.finditer(text):
            try:
                numeric_value = float(found.group(1))
            except ValueError:
                continue

            if 0 <= numeric_value <= 100:
                matches.append(
                    {
                        "type": "percentage",
                        "value": numeric_value,
                        "raw_value": found.group(0),
                        "confidence": 0.95,
                        "start": found.start(),
                        "end": found.end(),
                    }
                )

    def _collect_year_matches(self, text: str, matches: list[dict[str, Any]]) -> None:
        year_pattern = re.compile(r"(?<!\d)(20[0-4]\d)(?!\d)")

        for found in year_pattern.finditer(text):
            matches.append(
                {
                    "type": "year",
                    "value": int(found.group(1)),
                    "raw_value": found.group(0),
                    "confidence": 0.90,
                    "start": found.start(),
                    "end": found.end(),
                }
            )

    def _remove_overlapping_matches(self, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Remove overlapping matches using priority.
        """

        priority = {
            "national_id": 1,
            "phone": 2,
            "email": 3,
            "percentage": 4,
            "year": 5,
        }

        sorted_matches = sorted(
            matches,
            key=lambda item: (
                item["start"],
                priority.get(item["type"], 99),
                -(item["end"] - item["start"]),
            ),
        )

        accepted: list[dict[str, Any]] = []

        for match in sorted_matches:
            is_overlapping = any(
                not (
                    match["end"] <= accepted_match["start"]
                    or match["start"] >= accepted_match["end"]
                )
                for accepted_match in accepted
            )

            if not is_overlapping:
                accepted.append(match)

        return accepted

    def _entity_list_name(self, entity_type: str) -> str:
        mapping = {
            "email": "emails",
            "phone": "phones",
            "national_id": "national_ids",
            "percentage": "percentages",
            "year": "years",
        }

        return mapping[entity_type]

    # ---------------------------------------------------------------------
    # Domain detection
    # ---------------------------------------------------------------------

    def _detect_domain_entities(self, text: str) -> dict[str, Any]:
        """
        Detect ECU-specific faculty and intent hints.
        """

        faculty_match = self._detect_best_alias(text, FACULTY_ALIASES)
        intent_match = self._detect_best_alias(text, INTENT_ALIASES)

        return {
            "faculty": faculty_match,
            "intent": intent_match,
        }

    def _detect_best_alias(self, text: str, alias_map: dict[str, list[str]]) -> dict[str, Any] | None:
        """
        Detect exact or fuzzy alias match.

        Exact substring match is preferred.
        Fuzzy matching is only used with conservative threshold.
        """

        text_for_match = f" {text.lower()} "

        # Exact alias match first.
        for canonical_id, aliases in alias_map.items():
            for alias in aliases:
                alias_normalized = self._normalize_text(alias, "en").lower()

                if self._contains_alias(text_for_match, alias_normalized):
                    return {
                        "id": canonical_id,
                        "matched_alias": alias,
                        "match_type": "exact",
                        "confidence": 1.0,
                    }

        # Conservative fuzzy fallback.
        words = text.lower().split()
        candidate_phrases = self._generate_ngrams(words, max_size=4)

        best_match: dict[str, Any] | None = None

        for canonical_id, aliases in alias_map.items():
            for alias in aliases:
                alias_normalized = self._normalize_text(alias, "en").lower()

                for phrase in candidate_phrases:
                    score = SequenceMatcher(None, phrase, alias_normalized).ratio()

                    if best_match is None or score > best_match["confidence"]:
                        best_match = {
                            "id": canonical_id,
                            "matched_alias": alias,
                            "matched_text": phrase,
                            "match_type": "fuzzy",
                            "confidence": round(score, 3),
                        }

        if best_match and best_match["confidence"] >= 0.86:
            return best_match

        return None

    def _contains_alias(self, text: str, alias: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) is not None

    def _generate_ngrams(self, words: list[str], max_size: int) -> list[str]:
        ngrams: list[str] = []

        for size in range(1, max_size + 1):
            for index in range(0, len(words) - size + 1):
                ngrams.append(" ".join(words[index : index + size]))

        return ngrams

    # ---------------------------------------------------------------------
    # Corrected text and search query
    # ---------------------------------------------------------------------

    def _build_corrected_text(self, normalized_text: str, entities: dict[str, Any]) -> str:
        """
        Build a corrected text version.

        For now, we do not rewrite the user's full sentence aggressively.
        We only keep normalized text and rely on entities for routing.
        """

        return normalized_text

    def _build_search_query(self, corrected_text: str, entities: dict[str, Any]) -> str:
        """
        Build a search-friendly query for FAQ/RAG.

        This makes retrieval easier later.
        """

        query_parts: list[str] = []

        faculty = entities.get("faculty")
        intent = entities.get("intent")

        if faculty:
            query_parts.append(f"faculty:{faculty['id']}")

        if intent:
            query_parts.append(f"intent:{intent['id']}")

        query_parts.append(corrected_text)

        return " | ".join(query_parts)
