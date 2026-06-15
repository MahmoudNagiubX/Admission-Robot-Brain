"""
Small defensive OpenAI client wrapper for grounded RAG answers.
"""

import os
from typing import Any


try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()

from config import LLM_TIMEOUT_SECONDS, MAIN_LLM_MODEL, OPENAI_API_KEY_ENV


class LLMClient:
    """
    Calls OpenAI only when configuration and SDK support are available.
    """

    def __init__(
        self,
        model: str = MAIN_LLM_MODEL,
        api_key_env: str = OPENAI_API_KEY_ENV,
        timeout_seconds: int = LLM_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        self.api_key = os.getenv(api_key_env)
        self.client = self._create_client()

    def generate_grounded_answer(
        self,
        question: str,
        context: str,
        language: str,
    ) -> str | None:
        """
        Return a short grounded answer, or None if LLM is unavailable.
        """

        if not self.client or not self.api_key:
            return None

        prompt = self._build_prompt(question, context, language)

        try:
            if hasattr(self.client, "responses"):
                response = self.client.responses.create(
                    model=self.model,
                    input=prompt,
                )
                return self._extract_response_text(response)
        except Exception:
            return None

        return None

    def _create_client(self) -> Any | None:
        if not self.api_key:
            return None

        try:
            from openai import OpenAI

            return OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        except Exception:
            return None

    def _build_prompt(self, question: str, context: str, language: str) -> str:
        language_rule = "Arabic only" if language == "ar" else "English only"

        return (
            "You are ECU Admission Robot AI Brain.\n"
            "Use only the provided verified ECU context.\n"
            "Do not invent fees, deadlines, locations, admission rules, or requirements.\n"
            "If context is insufficient, say the Admission Office should confirm.\n"
            f"Respond in {language_rule}.\n"
            "Keep the answer short and suitable for a robot screen and voice.\n\n"
            f"Question:\n{question}\n\n"
            f"Verified ECU context:\n{context}"
        )

    def _extract_response_text(self, response: Any) -> str | None:
        output_text = getattr(response, "output_text", None)

        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        try:
            output = getattr(response, "output", [])

            for item in output:
                for content in getattr(item, "content", []):
                    text = getattr(content, "text", None)

                    if isinstance(text, str) and text.strip():
                        return text.strip()
        except Exception:
            return None

        return None
