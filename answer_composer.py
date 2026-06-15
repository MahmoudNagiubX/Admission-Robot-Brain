"""
Compose final QA answers from verified local knowledge base context.
"""

import re
from typing import Any

from config import RAG_INCLUDE_SOURCE_NOTE, RAG_MAX_ANSWER_CHARS
from llm_client import LLMClient


class AnswerComposer:
    """
    Uses an LLM to rewrite retrieved KB context into a short natural answer.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def compose_from_kb(
        self,
        question: str,
        kb_result: dict[str, Any],
        language: str,
    ) -> dict[str, Any]:
        context = self._build_context(kb_result, language)
        route_notes = [
            "llm_rag_checked",
            f"source_section_id:{kb_result.get('section_id')}",
        ]

        generated_answer = self.llm_client.generate_grounded_answer(
            question=question,
            context=context,
            language=language,
        )

        if generated_answer:
            is_valid, validation_notes = self._validate_llm_answer(
                answer=generated_answer,
                context=context,
                language=language,
            )
            route_notes.extend(validation_notes)

            if not is_valid:
                answer_text, speech_text = self._kb_direct_answer(kb_result, language)

                return {
                    "answer_text": answer_text,
                    "speech_text": speech_text,
                    "confidence": kb_result["confidence"],
                    "route_notes": route_notes
                    + [
                        "rag_answer_rejected",
                        "kb_direct_answer_used_after_rag_rejection",
                    ],
                }

            answer_text = self._with_source_note(
                answer=generated_answer,
                kb_result=kb_result,
                language=language,
            )

            return {
                "answer_text": answer_text,
                "speech_text": generated_answer,
                "confidence": kb_result["confidence"],
                "route_notes": route_notes
                + [
                    "rag_answer_validated",
                    "llm_rag_answer_generated",
                ],
            }

        answer_text, speech_text = self._kb_direct_answer(kb_result, language)

        return {
            "answer_text": answer_text,
            "speech_text": speech_text,
            "confidence": kb_result["confidence"],
            "route_notes": route_notes + ["llm_unavailable_kb_direct_answer_used"],
        }

    def _build_context(self, kb_result: dict[str, Any], language: str) -> str:
        raw_section = kb_result.get("raw_section") or {}

        title = self._get_language_value(raw_section.get("title", {}), language)
        content = self._get_language_value(raw_section.get("content", {}), language)
        section_type = raw_section.get("section_type") or kb_result.get("section_type") or ""
        source_url = raw_section.get("source_url") or kb_result.get("source_url") or ""

        return (
            f"Section ID: {kb_result.get('section_id')}\n"
            f"Section Type: {section_type}\n"
            f"Title: {title}\n"
            f"Content: {content}\n"
            f"Source URL: {source_url}"
        )

    def _validate_llm_answer(
        self,
        answer: str,
        context: str,
        language: str,
    ) -> tuple[bool, list[str]]:
        route_notes = ["rag_safety_checked"]

        if not answer.strip():
            return False, route_notes

        if len(answer) > RAG_MAX_ANSWER_CHARS:
            return False, route_notes

        if self._wrong_language(answer, language):
            return False, route_notes

        if self._has_unsupported_sensitive_numbers(answer, context):
            return False, route_notes

        if self._has_unsupported_official_claim(answer, context):
            return False, route_notes

        return True, route_notes

    def _wrong_language(self, answer: str, language: str) -> bool:
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", answer))
        has_latin = bool(re.search(r"[A-Za-z]", answer))

        if language == "ar":
            return not has_arabic

        return has_arabic and not has_latin

    def _has_unsupported_sensitive_numbers(self, answer: str, context: str) -> bool:
        sensitive_terms = {
            "fee",
            "fees",
            "tuition",
            "deadline",
            "deadlines",
            "date",
            "dates",
            "مصروفات",
            "مصاريف",
            "رسوم",
            "موعد",
            "مواعيد",
        }
        answer_lower = answer.lower()

        if not any(term in answer_lower for term in sensitive_terms):
            return False

        answer_numbers = set(re.findall(r"\d+(?:[.,]\d+)?%?", answer))
        context_numbers = set(re.findall(r"\d+(?:[.,]\d+)?%?", context))

        return any(number not in context_numbers for number in answer_numbers)

    def _has_unsupported_official_claim(self, answer: str, context: str) -> bool:
        claim_terms = [
            "must",
            "guaranteed",
            "official deadline",
            "final admission",
            "minimum score",
            "required documents",
            "لازم",
            "مضمون",
            "الموعد الرسمي",
            "القبول النهائي",
            "الحد الأدنى",
            "الأوراق المطلوبة",
        ]
        answer_lower = answer.lower()
        context_lower = context.lower()

        return any(
            term in answer_lower and term not in context_lower
            for term in claim_terms
        )

    def _kb_direct_answer(
        self,
        kb_result: dict[str, Any],
        language: str,
    ) -> tuple[str, str]:
        answer_text = self._with_source_note(
            answer=kb_result["answer_text"],
            kb_result=kb_result,
            language=language,
        )

        return answer_text, kb_result["speech_text"]

    def _with_source_note(
        self,
        answer: str,
        kb_result: dict[str, Any],
        language: str,
    ) -> str:
        if not RAG_INCLUDE_SOURCE_NOTE:
            return answer

        title = kb_result.get("title")

        if not title:
            return answer

        if language == "ar":
            return f"{answer}\n\nالمصدر: {title}"

        return f"{answer}\n\nSource: {title}"

    def _get_language_value(self, value: Any, language: str) -> str:
        if isinstance(value, dict):
            return value.get(language) or value.get("en") or value.get("ar") or ""

        if isinstance(value, str):
            return value

        return ""
