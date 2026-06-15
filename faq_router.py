"""
FAQ Router for Admission Robot AI Brain.

This module handles fast answers for common admission questions.

Why this exists:
- FAQ answers are faster than RAG.
- FAQ answers are safer than LLM generation.
- Common questions should be answered instantly.
"""

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from config import FAQ_MEDIUM_CONFIDENCE
from models import ProcessedText


class FAQRouter:
    """
    Fast FAQ matching system.

    Matching order:
    1. Faculty + intent match
    2. General intent match
    3. Paraphrase exact/fuzzy match
    """

    def __init__(self, faq_path: str = "data/faqs.json") -> None:
        self.faq_path = Path(faq_path)
        self.faq_items = self._load_faqs()

    def find_best_match(
        self,
        processed_text: ProcessedText,
        language: str,
    ) -> dict[str, Any]:
        """
        Find the best FAQ match for the current processed text.
        """

        best_match: dict[str, Any] | None = None

        for item in self.faq_items:
            score, reasons = self._score_faq_item(item, processed_text, language)

            if best_match is None or score > best_match["confidence"]:
                best_match = {
                    "matched": score >= FAQ_MEDIUM_CONFIDENCE,
                    "confidence": round(score, 3),
                    "faq_id": item.get("faq_id"),
                    "topic": item.get("topic"),
                    "answer_text": self._get_language_value(item, "answer", language),
                    "speech_text": self._get_language_value(item, "speech", language),
                    "needs_staff_verification": item.get(
                        "needs_staff_verification", False
                    ),
                    "source_url": item.get("source_url"),
                    "reasons": reasons,
                    "raw_item": item,
                }

        if best_match is None:
            return self._no_match(language)

        if not best_match["matched"]:
            return self._no_match(language, best_match)

        return best_match

    def _load_faqs(self) -> list[dict[str, Any]]:
        """
        Load FAQ items from JSON file.
        """

        if not self.faq_path.exists():
            return []

        with open(self.faq_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("data/faqs.json must contain a list of FAQ objects.")

        return data

    def _score_faq_item(
        self,
        item: dict[str, Any],
        processed_text: ProcessedText,
        language: str,
    ) -> tuple[float, list[str]]:
        """
        Score one FAQ item against the processed user text.
        """

        reasons: list[str] = []
        score = 0.0

        faculty = processed_text.entities.get("faculty")
        intent = processed_text.entities.get("intent")

        detected_faculty_id = faculty.get("id") if faculty else None
        detected_intent_id = intent.get("id") if intent else None

        item_faculty_id = item.get("faculty_id")
        item_intent_id = item.get("intent_id")

        # Strongest path: exact faculty + exact intent.
        if (
            item_faculty_id is not None
            and item_faculty_id == detected_faculty_id
            and item_intent_id == detected_intent_id
        ):
            score = max(score, 1.0)
            reasons.append("faculty_and_intent_matched")

        # General FAQ path: intent match with no specific faculty.
        elif item_faculty_id is None and item_intent_id == detected_intent_id:
            score = max(score, 0.90)
            reasons.append("general_intent_matched")

        # Partial faculty match.
        elif item_faculty_id is not None and item_faculty_id == detected_faculty_id:
            score = max(score, 0.70)
            reasons.append("faculty_matched_only")

        # Partial intent match.
        elif item_intent_id == detected_intent_id:
            score = max(score, 0.78)
            reasons.append("intent_matched_only")

        paraphrase_score, paraphrase_reason = self._score_paraphrases(
            item=item,
            text=processed_text.normalized_text,
            language=language,
        )

        if paraphrase_score > score:
            score = paraphrase_score
            reasons.append(paraphrase_reason)

        return score, reasons

    def _score_paraphrases(
        self,
        item: dict[str, Any],
        text: str,
        language: str,
    ) -> tuple[float, str]:
        """
        Score FAQ paraphrases against user text.
        """

        text_normalized = text.lower().strip()

        paraphrases = item.get("paraphrases", {})
        language_phrases = paraphrases.get(language, [])

        best_score = 0.0
        best_reason = "no_paraphrase_match"

        for phrase in language_phrases:
            phrase_normalized = phrase.lower().strip()

            if not phrase_normalized:
                continue

            # Exact or substring match.
            if phrase_normalized == text_normalized:
                return 0.98, f"exact_paraphrase_match:{phrase}"

            if (
                phrase_normalized in text_normalized
                or text_normalized in phrase_normalized
            ) and self._substring_tokens(text_normalized) == self._substring_tokens(
                phrase_normalized
            ):
                best_score = max(best_score, 0.92)
                best_reason = f"substring_paraphrase_match:{phrase}"
                continue

            fuzzy_score = SequenceMatcher(
                None, text_normalized, phrase_normalized
            ).ratio()

            if fuzzy_score >= 0.86 and not self._has_safe_token_overlap(
                text_normalized,
                phrase_normalized,
            ):
                continue

            if fuzzy_score > best_score:
                best_score = fuzzy_score
                best_reason = f"fuzzy_paraphrase_match:{phrase}"

        # Do not allow weak fuzzy matches to trigger FAQ.
        if best_score >= 0.90:
            return min(best_score, 0.88), best_reason

        return 0.0, "no_safe_paraphrase_match"

    def _has_safe_token_overlap(self, text: str, phrase: str) -> bool:
        """
        Keep fuzzy FAQ matches from jumping to a different subject.
        """

        text_tokens = self._meaningful_tokens(text)
        phrase_tokens = self._meaningful_tokens(phrase)

        if not text_tokens or not phrase_tokens:
            return False

        overlap = text_tokens.intersection(phrase_tokens)

        return len(overlap) >= 2 or (
            len(overlap) == 1
            and len(text_tokens) == 1
            and len(phrase_tokens) == 1
        )

    def _meaningful_tokens(self, text: str) -> set[str]:
        text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text.lower())
        tokens = {token for token in text.split() if len(token) >= 2}

        stopwords = {
            "the", "is", "are", "and", "or", "of", "to", "in", "for", "what",
            "where", "how", "can", "i", "me", "my", "a", "an", "does", "have",
            "about", "tell", "faculty", "engineering",
            "في", "من", "عن", "على", "الى", "إلى", "ايه", "ما", "هو", "هي",
            "عايز", "اعرف", "كام", "فين", "كلية", "هندسة",
        }

        return tokens.difference(stopwords)

    def _substring_tokens(self, text: str) -> Counter[str]:
        text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text.lower())
        tokens = [token for token in text.split() if len(token) >= 2]

        stopwords = {
            "the", "is", "are", "and", "or", "of", "to", "in", "for", "what",
            "where", "how", "can", "i", "me", "my", "a", "an", "does", "have",
            "about", "tell",
            "في", "من", "عن", "على", "الى", "إلى", "ايه", "ما", "هو", "هي",
            "عايز", "اعرف", "كام", "فين",
        }

        return Counter(token for token in tokens if token not in stopwords)

    def _get_language_value(
        self,
        item: dict[str, Any],
        field_name: str,
        language: str,
    ) -> str:
        """
        Get answer/speech in locked session language.
        """

        field_value = item.get(field_name, {})

        if not isinstance(field_value, dict):
            return str(field_value)

        value = field_value.get(language)

        if value:
            return value

        # Language-safe fallback.
        if language == "ar":
            return "هذه المعلومة تحتاج إلى مراجعة موظف القبول للتأكيد."

        return "This information needs to be confirmed with the Admission Office."

    def _no_match(
        self,
        language: str,
        best_attempt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Return a safe no-match result.
        """

        if language == "ar":
            answer = (
                "لم أجد إجابة مؤكدة في الأسئلة الشائعة. "
                "سيتم البحث عنها في قاعدة المعرفة في الخطوة القادمة."
            )
        else:
            answer = (
                "I did not find a confirmed FAQ answer. "
                "This will be handled by the knowledge base in the next step."
            )

        return {
            "matched": False,
            "confidence": best_attempt["confidence"] if best_attempt else 0.0,
            "faq_id": None,
            "topic": None,
            "answer_text": answer,
            "speech_text": answer,
            "needs_staff_verification": False,
            "source_url": None,
            "reasons": best_attempt["reasons"] if best_attempt else [],
            "raw_item": None,
        }
