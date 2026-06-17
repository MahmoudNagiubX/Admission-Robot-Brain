"""
Small defensive OpenAI client wrapper for grounded RAG answers.
"""

import json
import os
from typing import Any


try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()

from config import (
    GROQ_API_KEY_ENV,
    GROQ_BASE_URL,
    GROQ_MODEL,
    LLM_PROVIDER,
    LLM_TIMEOUT_SECONDS,
    MAIN_LLM_MODEL,
    OPENAI_API_KEY_ENV,
)


class LLMClient:
    """
    Calls OpenAI only when configuration and SDK support are available.
    """

    def __init__(
        self,
        provider: str = LLM_PROVIDER,
        timeout_seconds: int = LLM_TIMEOUT_SECONDS,
    ) -> None:
        self.provider = provider if provider in {"groq", "openai"} else "groq"
        self.model = self._resolve_model()
        self.api_key_env = self._resolve_api_key_env()
        self.timeout_seconds = timeout_seconds
        self.api_key = os.getenv(self.api_key_env)
        self.client = self._create_client()
        self.route_notes = [
            f"llm_provider:{self.provider}",
            f"llm_model:{self.model}",
        ]

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
            return self._call_text_model(prompt)
        except Exception:
            return None

        return None

    def extract_registration_fields(
        self,
        text: str,
        current_form: dict[str, Any],
        language: str,
    ) -> dict[str, Any] | None:
        """
        Extract allowed registration fields as JSON, or None on any failure.
        """

        if not self.client or not self.api_key:
            return None

        prompt = self._build_registration_prompt(text, current_form, language)

        try:
            response_text = self._call_text_model(prompt)
        except Exception:
            return None

        if not response_text:
            return None

        return self._parse_json_object(response_text)

    def correct_registration_value(
        self,
        field_id: str,
        raw_text: str,
        language: str = "en",
        current_value: Any = None,
        field_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Attempt to correct or normalize a single registration field value.
        Returns a safe structured dict. Never raises exceptions.
        """
        default_response = {
            "field_id": field_id,
            "candidate_value": None,
            "confidence": 0.0,
            "action": "ask_retry",
            "reason": "LLM unavailable or failed"
        }

        if not self.client or not self.api_key:
            return default_response

        prompt = self._build_correction_prompt(field_id, raw_text, language)

        try:
            response_text = self._call_text_model(prompt)
            if not response_text:
                return default_response
                
            parsed = self._parse_json_object(response_text)
            if not parsed or "candidate_value" not in parsed:
                return default_response
                
            return parsed
        except Exception:
            return default_response

    def extract_name_pair(
        self,
        text: str,
        language: str = "en",
    ) -> dict[str, Any] | None:
        """
        Phonetically transliterate a name into both Arabic and English.
        Returns JSON: { "name_ar": "...", "name_en": "...", "confidence": 0.9 }
        """
        if not self.client or not self.api_key:
            return None

        prompt = (
            "You are a phonetic name transliterator for ECU Admission Robot.\n"
            "Extract the student full name from the text and provide both Arabic and English phonetic versions.\n"
            "Rules:\n"
            "1. PHONETIC TRANSLITERATION ONLY. Do not translate meanings (e.g., 'Nour' remains 'Nour', not 'Light').\n"
            "2. Arabic name must be in Arabic script.\n"
            "3. English name must be in Latin script.\n"
            "4. Remove prefixes like 'my name is', 'اسمي', etc.\n"
            "5. Return JSON only. No markdown.\n"
            "Format:\n"
            "{\n"
            '  "name_ar": "...",\n'
            '  "name_en": "...",\n'
            '  "confidence": 0.0\n'
            "}\n\n"
            f"User text: {text}\n"
            f"Source language: {language}"
        )

        try:
            response_text = self._call_text_model(prompt)
            return self._parse_json_object(response_text)
        except Exception:
            return None

    def _call_text_model(self, prompt: str) -> str | None:
        if self.provider == "groq":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            return self._extract_chat_completion_text(response)

        if hasattr(self.client, "responses"):
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
            )
            return self._extract_response_text(response)

        return None

    def _create_client(self) -> Any | None:
        if not self.api_key:
            return None

        try:
            from openai import OpenAI

            if self.provider == "groq":
                return OpenAI(
                    api_key=self.api_key,
                    base_url=GROQ_BASE_URL,
                    timeout=self.timeout_seconds,
                )

            return OpenAI(
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
        except Exception:
            return None

    def _resolve_model(self) -> str:
        if self.provider == "openai":
            return MAIN_LLM_MODEL

        return GROQ_MODEL

    def _resolve_api_key_env(self) -> str:
        if self.provider == "openai":
            return OPENAI_API_KEY_ENV

        return GROQ_API_KEY_ENV

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

    def _build_registration_prompt(
        self,
        text: str,
        current_form: dict[str, Any],
        language: str,
    ) -> str:
        allowed_fields = [
            "full_name_en",
            "full_name_ar",
            "school_name",
            "certificate",
            "guardian_name",
            "relationship",
            "address",
            "city",
            "country",
            "college_preference_1",
            "college_preference_2",
            "college_preference_3",
            "college_preference_4",
            "college_preference_5",
            "college_preference_6",
        ]

        known_faculty_ids = [
            "engineering_and_technology",
            "pharmacy_and_drug_technology",
            "physical_therapy",
            "computers_and_information_systems",
            "economics_and_international_trade",
            "arts_and_design",
            "veterinary_medicine",
            "mass_communication",
        ]

        return (
            "You extract ECU registration form fields.\n"
            "Return JSON only. No markdown. No explanation.\n"
            "Only include fields explicitly present in the user text.\n"
            "Do not guess missing values.\n"
            f"Allowed fields: {json.dumps(allowed_fields)}\n"
            f"Known faculty ids: {json.dumps(known_faculty_ids)}\n"
            "Use canonical faculty ids for college preferences when clear.\n"
            "Use certificate values like American, STEM, IGCSE, Thanaweya Amma, Al-Azhar.\n"
            "Use relationship values like Father, Mother, Brother, Sister, Guardian.\n"
            f"Language: {language}\n"
            f"Current form JSON: {json.dumps(current_form, ensure_ascii=False)}\n"
            f"User text: {text}"
        )

    def _build_correction_prompt(
        self,
        field_id: str,
        text: str,
        language: str,
    ) -> str:
        transliteration_instruction = ""
        if field_id == "full_name_ar":
            transliteration_instruction = (
                "SPECIAL RULE: If the user provided an Arabic name in English letters (transliteration), "
                "YOU MUST convert it to proper Arabic letters. Example: 'Mohammed' -> 'محمد'.\n"
            )
        elif field_id == "full_name_en":
            transliteration_instruction = (
                "SPECIAL RULE: If the user provided an Arabic name in Arabic letters, "
                "YOU MUST convert it to proper English letters (transliteration). Example: 'محمد' -> 'Mohamed'.\n"
            )

        return (
            "You are a registration data cleaner for ECU Admission Robot.\n"
            "Your job is to extract or correct a SINGLE field from messy text.\n"
            f"Target Field: {field_id}\n"
            f"User Text: {text}\n"
            f"Language: {language}\n\n"
            "Rules:\n"
            "1. Return JSON only. No explanation.\n"
            "2. If the text contains a correction for the field, extract it.\n"
            "3. Normalize names, certificates, and job titles.\n"
            f"{transliteration_instruction}"
            "4. For dates, return YYYY-MM-DD.\n"
            "5. If you cannot find a valid value for this specific field, return null for candidate_value.\n"
            "6. DO NOT invent IDs, phone numbers, or emails. If they are missing or too short, return null.\n"
            "7. Do NOT extract other fields. Focus ONLY on the Target Field.\n\n"
            "Required JSON format:\n"
            "{\n"
            '  "field_id": "...",\n'
            '  "candidate_value": "...",\n'
            '  "confidence": 0.0,\n'
            '  "action": "use_candidate | ask_retry | no_change",\n'
            '  "reason": "short reason"\n'
            "}"
        )

    def _parse_json_object(self, text: str) -> dict[str, Any] | None:
        text = text.strip()

        if text.startswith("```"):
            text = text.strip("`").strip()

            if text.startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
        except Exception:
            return None

        if not isinstance(parsed, dict):
            return None

        return parsed

    def _extract_chat_completion_text(self, response: Any) -> str | None:
        try:
            choices = getattr(response, "choices", [])

            if not choices:
                return None

            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)

            if isinstance(content, str) and content.strip():
                return content.strip()
        except Exception:
            return None

        return None

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
