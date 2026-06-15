"""
Fixed registration form engine for the Admission Robot AI Brain.

This module keeps in-memory form state per session and extracts a first set of
core registration fields using deterministic rules.
"""

import json
import re
from pathlib import Path
from typing import Any

from models import ProcessedText


class RegistrationEngine:
    """
    Fill a fixed registration form using rule-based extraction.
    """

    REQUIRED_CORE_FIELDS = [
        "full_name_en",
        "full_name_ar",
        "id_or_passport",
        "student_mobile_no",
        "email_address",
        "school_name",
        "certificate",
        "year_of_completion",
        "percentage",
        "college_preference_1",
        "guardian_name",
        "relationship",
        "guardian_mobile_no",
        "address",
        "city",
        "country",
    ]

    SENSITIVE_FIELDS = {
        "id_or_passport",
        "student_mobile_no",
        "email_address",
        "percentage",
        "guardian_mobile_no",
        "guardian_email_address",
    }

    GUARDIAN_WORDS = {
        "guardian",
        "parent",
        "father",
        "mother",
        "dad",
        "mom",
        "ولي",
        "والد",
        "والدي",
        "والدة",
        "والدتي",
        "ابويا",
        "امي",
        "الأب",
        "الاب",
        "الأم",
        "الام",
    }

    def __init__(self, fields_path: str = "data/registration_fields.json") -> None:
        self.fields_path = Path(fields_path)
        self.field_definitions = self._load_field_definitions()
        self.field_order = [field["field_name"] for field in self.field_definitions]
        self.prompts = {
            field["field_name"]: {
                "en": field.get("prompt_en", f"Please provide {field['field_name']}."),
                "ar": field.get("prompt_ar", f"من فضلك أدخل {field['field_name']}."),
            }
            for field in self.field_definitions
        }
        self.sessions: dict[str, dict[str, Any]] = {}

    def process(
        self,
        session_id: str,
        processed_text: ProcessedText,
        language: str,
    ) -> dict[str, Any]:
        form_state = self.sessions.setdefault(session_id, {})
        route_notes = ["registration_engine_checked"]
        extracted_updates = self._extract_updates(processed_text, form_state)

        form_updates: dict[str, Any] = {}
        needs_confirmation = False

        for field_name, value in extracted_updates.items():
            if value in {None, ""}:
                continue

            form_state[field_name] = value
            form_updates[field_name] = value
            route_notes.append(f"field_filled:{field_name}")

            if field_name in self.SENSITIVE_FIELDS:
                needs_confirmation = True
                route_notes.append(f"confirmation_needed:{field_name}")

        missing_required_fields = self._missing_required_fields(form_state)
        completion_percentage = self._completion_percentage(form_state)
        next_question = self._next_question(missing_required_fields, language)

        if not form_updates:
            route_notes.append("no_registration_fields_extracted")

        return {
            "form_updates": form_updates,
            "next_question": next_question,
            "needs_confirmation": needs_confirmation,
            "completion_percentage": completion_percentage,
            "missing_required_fields": missing_required_fields,
            "route_notes": route_notes,
            "form_state": dict(form_state),
        }

    def _load_field_definitions(self) -> list[dict[str, Any]]:
        with open(self.fields_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("data/registration_fields.json must contain a list.")

        return [field for field in data if isinstance(field, dict) and field.get("field_name")]

    def _extract_updates(
        self,
        processed_text: ProcessedText,
        form_state: dict[str, Any],
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        raw_text = processed_text.raw_text.strip()
        normalized_text = processed_text.normalized_text.strip()
        text_lower = normalized_text.lower()
        guardian_context = self._has_guardian_context(text_lower)

        self._extract_protected_entities(processed_text.entities, updates, guardian_context)
        self._extract_names(raw_text, normalized_text, updates)
        self._extract_school(raw_text, normalized_text, updates)
        self._extract_certificate(text_lower, updates)
        self._extract_college_preference(processed_text.entities, form_state, updates)

        return updates

    def _extract_protected_entities(
        self,
        entities: dict[str, Any],
        updates: dict[str, Any],
        guardian_context: bool,
    ) -> None:
        phones = entities.get("phones") or []
        emails = entities.get("emails") or []
        national_ids = entities.get("national_ids") or []
        percentages = entities.get("percentages") or []
        years = entities.get("years") or []

        if phones:
            field_name = "guardian_mobile_no" if guardian_context else "student_mobile_no"
            updates[field_name] = phones[0]["value"]

        if emails:
            field_name = "guardian_email_address" if guardian_context else "email_address"
            updates[field_name] = emails[0]["value"]

        if national_ids:
            field_name = "guardian_id_or_passport" if guardian_context else "id_or_passport"
            updates[field_name] = national_ids[0]["value"]

        if percentages:
            updates["percentage"] = percentages[0]["value"]

        if years:
            updates["year_of_completion"] = years[0]["value"]

    def _extract_names(
        self,
        raw_text: str,
        normalized_text: str,
        updates: dict[str, Any],
    ) -> None:
        english_match = re.search(
            r"\b(?:my name is|name is|i am)\s+(.+?)(?=\s+(?:and|,|my phone|my email|phone|email)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if english_match:
            name = self._clean_value(english_match.group(1))

            if name:
                updates["full_name_en"] = name

        arabic_match = re.search(
            r"(?:انا اسمي|اسمي)\s+(.+?)(?=\s+و(?:رقمي|مجموعي|ايميلي|مدرستي|اسمي)|\s*,|$)",
            normalized_text,
        )

        if arabic_match:
            name = self._clean_value(arabic_match.group(1))

            if name:
                updates["full_name_ar"] = name

    def _extract_school(
        self,
        raw_text: str,
        normalized_text: str,
        updates: dict[str, Any],
    ) -> None:
        english_match = re.search(
            r"\b(?:my school is|school name is)\s+(.+?)(?=\s+(?:and|,)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if english_match:
            school_name = self._clean_value(english_match.group(1))

            if school_name:
                updates["school_name"] = school_name

        arabic_match = re.search(
            r"(?:مدرستي|اسم المدرسة)\s+(.+?)(?=\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_match:
            school_name = self._clean_value(arabic_match.group(1))

            if school_name:
                updates["school_name"] = school_name

    def _extract_certificate(self, text_lower: str, updates: dict[str, Any]) -> None:
        certificate_patterns = [
            (r"\bamerican\b|امريكان|امريكي", "American"),
            (r"\bstem\b|المتفوقين", "STEM"),
            (r"\bigcse\b|\big\b|اي جي", "IGCSE"),
            (r"ثانوية عامة|\bsecondary\b", "Thanaweya Amma"),
            (r"ازهر|أزهر|al[-\s]?azhar", "Al-Azhar"),
        ]

        for pattern, certificate in certificate_patterns:
            if re.search(pattern, text_lower):
                updates["certificate"] = certificate
                return

    def _extract_college_preference(
        self,
        entities: dict[str, Any],
        form_state: dict[str, Any],
        updates: dict[str, Any],
    ) -> None:
        faculty = entities.get("faculty")

        if not faculty:
            return

        faculty_id = faculty.get("id")

        if not faculty_id:
            return

        for index in range(1, 7):
            field_name = f"college_preference_{index}"

            if not form_state.get(field_name) and field_name not in updates:
                updates[field_name] = faculty_id
                return

    def _has_guardian_context(self, text_lower: str) -> bool:
        return any(word in text_lower for word in self.GUARDIAN_WORDS)

    def _missing_required_fields(self, form_state: dict[str, Any]) -> list[str]:
        return [
            field_name
            for field_name in self.REQUIRED_CORE_FIELDS
            if not form_state.get(field_name)
        ]

    def _completion_percentage(self, form_state: dict[str, Any]) -> int:
        required_count = len(self.REQUIRED_CORE_FIELDS)
        filled_count = required_count - len(self._missing_required_fields(form_state))

        return round((filled_count / required_count) * 100)

    def _next_question(self, missing_required_fields: list[str], language: str) -> str | None:
        if not missing_required_fields:
            if language == "ar":
                return "تم إدخال البيانات الأساسية. من فضلك راجع البيانات للتأكيد."

            return "The core registration details are complete. Please review them for confirmation."

        field_name = missing_required_fields[0]
        prompts = self.prompts.get(field_name, {})

        if language == "ar":
            return prompts.get("ar") or prompts.get("en")

        return prompts.get("en") or prompts.get("ar")

    def _clean_value(self, value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" .,،")
        value = re.sub(r"\b(?:and|my|phone|email|school)\b.*$", "", value, flags=re.IGNORECASE)
        return value.strip(" .,،")
