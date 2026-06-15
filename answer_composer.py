"""
Compose final QA answers from verified local knowledge base context.
"""

from typing import Any

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
        route_notes = ["llm_rag_checked"]

        generated_answer = self.llm_client.generate_grounded_answer(
            question=question,
            context=context,
            language=language,
        )

        if generated_answer:
            return {
                "answer_text": generated_answer,
                "speech_text": generated_answer,
                "confidence": kb_result["confidence"],
                "route_notes": route_notes + ["llm_rag_answer_generated"],
            }

        return {
            "answer_text": kb_result["answer_text"],
            "speech_text": kb_result["speech_text"],
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

    def _get_language_value(self, value: Any, language: str) -> str:
        if isinstance(value, dict):
            return value.get(language) or value.get("en") or value.get("ar") or ""

        if isinstance(value, str):
            return value

        return ""
