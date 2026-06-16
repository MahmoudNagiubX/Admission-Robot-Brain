"""
Fixed registration form engine for the Admission Robot AI Brain.

This module keeps in-memory form state per session and extracts a first set of
core registration fields using deterministic rules.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import ENABLE_LLM_REGISTRATION_EXTRACTION, FACULTY_ALIASES
from llm_client import LLMClient
from models import ProcessedText


class RegistrationEngine:
    """
    Fill a fixed registration form using rule-based extraction.
    """

    REQUIRED_NAME_FIELDS = ("full_name_en", "full_name_ar")

    GUARDIAN_WORDS = {
        "guardian",
        "father",
        "mother",
        "parent",
        "dad",
        "mom",
        "ولي الامر",
        "ولى الامر",
        "الاب",
        "الأب",
        "الام",
        "الأم",
        "والدي",
        "والدتي",
    }

    CONFIRM_WORDS = {"confirm", "yes", "correct", "تمام", "ايوه", "نعم", "صح"}
    REJECT_WORDS = {"no", "wrong", "incorrect", "لا", "غلط", "مش صح"}
    CORRECTION_WORDS = REJECT_WORDS.union(
        {"change", "update", "replace", "غير", "عدل"}
    )
    LLM_ALLOWED_FIELDS = {
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
    }

    def __init__(self, fields_path: str = "data/registration_fields.json") -> None:
        self.fields_path = Path(fields_path)
        self.field_definitions = self._load_field_definitions()
        
        # Sort fields by defined order
        self.field_definitions.sort(key=lambda x: x.get("order", 999))
        
        self.field_order = [field["field_id"] for field in self.field_definitions]
        
        self.prompts = {
            field["field_id"]: {
                "en": field.get("question_en", f"Please provide {field['field_id']}."),
                "ar": field.get("question_ar", f"من فضلك أدخل {field['field_id']}."),
            }
            for field in self.field_definitions
        }
        
        self.required_core_fields = [
            field["field_id"] for field in self.field_definitions
            if field.get("required_for_basic_registration")
        ]
        
        self.sensitive_fields = {
            field["field_id"] for field in self.field_definitions
            if field.get("sensitive")
        }
        
        self.auto_fields = {
            field["field_id"] for field in self.field_definitions
            if field.get("input_method") == "auto"
        }

        self.sessions: dict[str, dict[str, Any]] = {}
        self.llm_client = LLMClient()

    def process(
        self,
        session_id: str,
        processed_text: ProcessedText,
        language: str,
    ) -> dict[str, Any]:
        session_state = self.sessions.setdefault(
            session_id,
            {
                "fields": {},
                "metadata": {},
                "latest_sensitive_fields": [],
                "current_field": None,
                "guided_flow": False,
                "skipped_fields": set(),
            },
        )
        form_state = session_state["fields"]
        route_notes = ["registration_engine_checked"]

        confirmation_result = self._handle_confirmation_command(
            processed_text.normalized_text,
            session_state,
            language,
        )

        if confirmation_result is not None:
            missing_required_fields = self._missing_required_fields(form_state)
            completion_percentage = self._completion_percentage(form_state)
            current_field = self._sync_current_field(
                session_state=session_state,
                language=language,
            )
            next_question = (
                confirmation_result["next_question"]
                or self._question_for_field(current_field, language)
                or self._next_question(missing_required_fields, language)
            )

            return {
                "form_updates": {},
                "next_question": next_question,
                "needs_confirmation": confirmation_result["needs_confirmation"],
                "completion_percentage": completion_percentage,
                "missing_required_fields": missing_required_fields,
                "route_notes": route_notes + confirmation_result["route_notes"],
                "form_state": dict(form_state),
            }

        correction_requested = self._has_correction_words(processed_text.normalized_text)
        current_field = session_state.get("current_field")

        extracted_updates = self._extract_updates(
            processed_text=processed_text,
            form_state=form_state,
            current_field=current_field,
            correction_requested=correction_requested,
        )
        
        # Disable LLM extraction during guided flow if current_field is active
        # unless it's an explicit correction
        if current_field and not correction_requested:
            semantic_updates, semantic_route_notes = {}, []
        else:
            semantic_updates, semantic_route_notes = self._extract_semantic_updates(
                processed_text=processed_text,
                form_state=form_state,
                deterministic_updates=extracted_updates,
                language=language,
            )
            
        route_notes.extend(semantic_route_notes)
        extracted_updates.update(semantic_updates)

        form_updates: dict[str, Any] = {}
        needs_confirmation = False
        latest_sensitive_fields: list[str] = []
        correction_requested = self._has_correction_words(processed_text.normalized_text)

        validation_errors = []

        for field_name, value in extracted_updates.items():
            if value in {None, ""}:
                continue

            if not self._can_update_field(
                field_name=field_name,
                form_state=form_state,
                correction_requested=correction_requested,
            ):
                route_notes.append(f"registration_update_skipped_existing:{field_name}")
                continue

            normalized_value, is_valid = self._validate_field_value(field_name, value)

            if not is_valid:
                route_notes.append(f"registration_validation_failed:{field_name}")
                if field_name == session_state.get("current_field"):
                    validation_errors.append(field_name)
                continue

            form_state[field_name] = value
            form_updates[field_name] = normalized_value
            form_state[field_name] = normalized_value
            session_state["metadata"][field_name] = self._build_field_state(
                value=normalized_value,
                confidence=0.90,
                needs_confirmation=field_name in self.sensitive_fields,
                source="registration_extraction",
                source_text=processed_text.raw_text,
            )
            route_notes.append(f"field_filled:{field_name}")

            if field_name in self.sensitive_fields:
                needs_confirmation = True
                latest_sensitive_fields.append(field_name)
                route_notes.append(f"confirmation_needed:{field_name}")

        if latest_sensitive_fields:
            session_state["latest_sensitive_fields"] = latest_sensitive_fields
        missing_required_fields = self._missing_required_fields(form_state)
        completion_percentage = self._completion_percentage(form_state)
        current_field = self._sync_current_field(
            session_state=session_state,
            language=language,
        )
        
        # Determine next question
        if needs_confirmation:
            next_question = self._confirmation_question(latest_sensitive_fields, language)
        elif validation_errors:
            # If current field failed validation, use retry prompt
            next_question = self._retry_question(validation_errors[0], language)
        else:
            next_question = self._question_for_field(current_field, language)
            if not next_question:
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


    def start_guided_form(self, session_id: str, language: str) -> str | None:
        session_state = self._get_or_create_session_state(session_id)
        session_state["guided_flow"] = True
        session_state.setdefault("skipped_fields", set())
        current_field = self._sync_current_field(
            session_state=session_state,
            language=language,
        )

        return self._question_for_field(current_field, language)

    def get_current_question(self, session_id: str, language: str) -> str | None:
        session_state = self._get_or_create_session_state(session_id)
        current_field = self._sync_current_field(
            session_state=session_state,
            language=language,
        )

        return self._question_for_field(current_field, language)

    def skip_current_field(self, session_id: str, language: str) -> str | None:
        session_state = self._get_or_create_session_state(session_id)
        current_field = session_state.get("current_field")

        if current_field:
            skipped_fields = session_state.setdefault("skipped_fields", set())
            skipped_fields.add(current_field)

        session_state["current_field"] = None
        next_field = self._sync_current_field(
            session_state=session_state,
            language=language,
        )

        return self._question_for_field(next_field, language)

    def _build_field_state(
        self,
        value: Any,
        confidence: float,
        needs_confirmation: bool,
        source: str,
        source_text: str,
    ) -> dict[str, Any]:
        return {
            "value": value,
            "confidence": confidence,
            "confirmed": not needs_confirmation,
            "needs_confirmation": needs_confirmation,
            "source": source,
            "source_text": source_text,
        }

    def export_form_values(self, session_id: str) -> dict[str, Any]:
        session_state = self.sessions.get(session_id, {})
        raw_values = self._form_state_with_auto_fields(session_state.get("fields", {}))
        
        # Strictly filter to only schema fields or allowed auto fields
        schema_ids = {f["field_id"] for f in self.field_definitions}
        allowed_auto = {"final_student_name", "final_college", "academic_year"}
        
        return {
            k: v for k, v in raw_values.items()
            if k in schema_ids or k in allowed_auto
        }

    def export_form_state(self, session_id: str) -> dict[str, Any]:
        session_state = self.sessions.get(session_id, {})
        raw_form_state = self._form_state_with_auto_fields(session_state.get("fields", {}))
        metadata = session_state.get("metadata", {})

        schema_ids = {f["field_id"] for f in self.field_definitions}
        allowed_auto = {"final_student_name", "final_college", "academic_year"}

        fields: dict[str, dict[str, Any]] = {}

        for field_name, value in raw_form_state.items():
            if field_name not in schema_ids and field_name not in allowed_auto:
                continue

            field_metadata = metadata.get(field_name)

            if isinstance(field_metadata, dict):
                fields[field_name] = {
                    "value": field_metadata.get("value", value),
                    "confidence": field_metadata.get("confidence", 0.0),
                    "confirmed": field_metadata.get("confirmed", False),
                    "needs_confirmation": field_metadata.get(
                        "needs_confirmation",
                        field_name in self.sensitive_fields,
                    ),
                    "source": field_metadata.get("source"),
                    "source_text": field_metadata.get("source_text"),
                }
            elif field_name in self.auto_fields or field_name in allowed_auto:
                fields[field_name] = {
                    "value": value,
                    "confidence": 1.0,
                    "confirmed": True,
                    "needs_confirmation": False,
                    "source": "auto",
                    "source_text": None,
                }
            else:
                fields[field_name] = {
                    "value": value,
                    "confidence": 0.0,
                    "confirmed": field_name not in self.sensitive_fields,
                    "needs_confirmation": field_name in self.sensitive_fields,
                    "source": "legacy",
                    "source_text": None,
                }

        return {
            "fields": fields,
            "latest_sensitive_fields": list(
                session_state.get("latest_sensitive_fields", [])
            ),
            "current_field": session_state.get("current_field"),
            "status": self.get_registration_status(session_id),
        }

    def get_registration_status(self, session_id: str) -> dict[str, Any]:
        session_state = self.sessions.get(session_id, {})
        form_state = session_state.get("fields", {})
        metadata = session_state.get("metadata", {})
        missing_required_fields = self._missing_required_fields(form_state)

        return {
            "is_basic_registration_complete": not missing_required_fields,
            "completion_percentage": self._completion_percentage(form_state),
            "missing_required_fields": missing_required_fields,
            "unconfirmed_sensitive_fields": self._unconfirmed_sensitive_fields(
                form_state,
                metadata,
            ),
        }

    def get_form_debug_view(self, session_id: str) -> dict[str, Any]:
        session_state = self.sessions.get(session_id, {})
        form_state = session_state.get("fields", {})
        metadata = session_state.get("metadata", {})
        missing_required_fields = self._missing_required_fields(form_state)

        return {
            "filled_fields": dict(form_state),
            "missing_required_fields": missing_required_fields,
            "unconfirmed_sensitive_fields": self._unconfirmed_sensitive_fields(
                form_state,
                metadata,
            ),
            "completion_percentage": self._completion_percentage(form_state),
            "latest_sensitive_fields": list(
                session_state.get("latest_sensitive_fields", [])
            ),
            "current_field": session_state.get("current_field"),
            "is_basic_registration_complete": not missing_required_fields,
        }

    def get_review_summary(self, session_id: str, language: str) -> str:
        debug_view = self.get_form_debug_view(session_id)
        filled_fields = debug_view["filled_fields"]
        missing_required_fields = debug_view["missing_required_fields"]
        unconfirmed_sensitive_fields = debug_view["unconfirmed_sensitive_fields"]

        if language == "ar":
            return self._arabic_review_summary(
                filled_fields=filled_fields,
                missing_required_fields=missing_required_fields,
                unconfirmed_sensitive_fields=unconfirmed_sensitive_fields,
            )

        return self._english_review_summary(
            filled_fields=filled_fields,
            missing_required_fields=missing_required_fields,
            unconfirmed_sensitive_fields=unconfirmed_sensitive_fields,
        )

    def _load_field_definitions(self) -> list[dict[str, Any]]:
        with open(self.fields_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("data/registration_fields.json must contain a list.")

        field_definitions: list[dict[str, Any]] = []

        for field in data:
            if not isinstance(field, dict):
                continue

            field_id = field.get("field_id") or field.get("field_name")

            if not field_id:
                continue

            normalized_field = dict(field)
            normalized_field["field_id"] = field_id
            normalized_field["field_name"] = field.get("field_name") or field_id
            field_definitions.append(normalized_field)

        return field_definitions

    def _get_or_create_session_state(self, session_id: str) -> dict[str, Any]:
        return self.sessions.setdefault(
            session_id,
            {
                "fields": {},
                "metadata": {},
                "latest_sensitive_fields": [],
                "current_field": None,
                "guided_flow": False,
                "skipped_fields": set(),
            },
        )

    def _extract_updates(
        self,
        processed_text: ProcessedText,
        form_state: dict[str, Any],
        current_field: str | None = None,
        correction_requested: bool = False,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        raw_text = processed_text.raw_text.strip()
        normalized_text = processed_text.normalized_text.strip()
        text_lower = normalized_text.lower()
        guardian_context = self._has_guardian_context(text_lower)

        if current_field:
            self._extract_current_field_answer(
                field_name=current_field,
                processed_text=processed_text,
                updates=updates,
                form_state=form_state,
            )
            
            # In guided mode, if we have a current_field, we STICK to it.
            # Do NOT run extra extraction if we're not correcting.
            if not correction_requested:
                return updates

        # extra extraction is only for corrections or non-guided fills
        self._extract_protected_entities(processed_text.entities, updates, guardian_context)
        self._extract_loose_sensitive_values(raw_text, updates, guardian_context)
        self._extract_relationship(text_lower, updates)
        self._extract_names(raw_text, normalized_text, updates, guardian_context)
        self._extract_address(raw_text, normalized_text, updates)
        self._extract_school(raw_text, normalized_text, updates)
        self._extract_certificate(text_lower, updates)
        self._extract_ranked_college_preferences(
            raw_text=raw_text,
            normalized_text=normalized_text,
            form_state=form_state,
            updates=updates,
        )
        self._extract_college_preference(processed_text.entities, form_state, updates)

        return updates

    def _extract_current_field_answer(
        self,
        field_name: str,
        processed_text: ProcessedText,
        updates: dict[str, Any],
        form_state: dict[str, Any],
    ) -> None:
        raw_text = processed_text.raw_text.strip()
        normalized_text = processed_text.normalized_text.strip()

        if not raw_text:
            return

        # Do not save command words as field values
        commands = {"listen", "voice", "next question", "skip field", "start form", "exit", "quit"}
        if raw_text.lower() in commands:
            return

        if field_name in {"full_name_en", "full_name_ar", "guardian_name"}:
            cleaned = self._clean_answer_fallback(raw_text)
            if cleaned:
                updates[field_name] = cleaned
            return

        if field_name in {"student_mobile_no", "guardian_mobile_no", "home_phone", "guardian_work_no", "guardian_home_phone"}:
            normalized_digits = self._normalize_digits(raw_text)
            # Try extraction from sentence first
            phone_match = re.search(r"\b(01[0125][0-9\s-]{8,11})\b", normalized_digits)
            if phone_match:
                updates[field_name] = re.sub(r"\D", "", phone_match.group(1))
            else:
                digits = re.sub(r"\D", "", normalized_digits)
                if digits:
                    updates[field_name] = digits
            return

        if field_name in {"id_or_passport", "guardian_id_or_passport"}:
            normalized_digits = self._normalize_digits(raw_text)
            # If it's mostly digits, treat as ID
            digits = re.sub(r"\D", "", normalized_digits)
            if digits and len(digits) >= 10:
                updates[field_name] = digits
            else:
                cleaned = self._clean_answer_fallback(raw_text)
                if cleaned:
                    updates[field_name] = cleaned
            return

        if field_name in {"email_address", "guardian_email_address"}:
            normalized_email_text = self._normalize_email_transcript(raw_text)
            email_match = re.search(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                normalized_email_text,
            )

            if email_match:
                updates[field_name] = email_match.group(0).lower()
            elif "@" in normalized_email_text:
                # Partial email detected, trigger validation failure
                updates[field_name] = normalized_email_text

            return

        if field_name in {"percentage", "total_marks", "science_score", "math_score", "literary_score"}:
            normalized_digits = self._normalize_digits(raw_text)
            number_match = re.search(r"(\d{1,3}(?:\.\d{1,2})?)", normalized_digits)

            if number_match:
                updates[field_name] = float(number_match.group(1))

            return

        if field_name == "year_of_completion":
            normalized_digits = self._normalize_digits(raw_text)
            year_match = re.search(r"\b20\d{2}\b", normalized_digits)

            if year_match:
                updates[field_name] = int(year_match.group(0))

            return

        if field_name == "certificate":
            certificate_updates: dict[str, Any] = {}
            self._extract_certificate(normalized_text.lower(), certificate_updates)

            if "certificate" in certificate_updates:
                updates[field_name] = certificate_updates["certificate"]
            else:
                cleaned = self._clean_answer_fallback(raw_text)
                if cleaned:
                    updates[field_name] = cleaned

            return

        if field_name.startswith("college_preference_"):
            faculty = processed_text.entities.get("faculty")

            if faculty and faculty.get("id"):
                updates[field_name] = faculty["id"]
            else:
                cleaned = self._clean_answer_fallback(raw_text)
                if cleaned:
                    updates[field_name] = cleaned

            return

        if field_name == "relationship":
            relationship_updates: dict[str, Any] = {}
            self._extract_relationship(normalized_text.lower(), relationship_updates)

            if "relationship" in relationship_updates:
                updates[field_name] = relationship_updates["relationship"]
            else:
                cleaned = self._clean_answer_fallback(raw_text)
                if cleaned:
                    updates[field_name] = cleaned

            return

        if field_name == "date_of_birth":
            # Extract date formats from raw text
            date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})|(\d{4}-\d{1,2}-\d{1,2})", raw_text)
            if date_match:
                updates[field_name] = date_match.group(0)
                return
            
            cleaned = self._clean_answer_fallback(raw_text)
            if cleaned:
                updates[field_name] = cleaned
            return

        if field_name in {"country", "guardian_country", "school_country"}:
            cleaned = self._clean_country_prefix(raw_text)
            if cleaned:
                updates[field_name] = cleaned
            return

        if field_name == "guardian_address":
            same_as_me = {
                "same as my address", "same address", "same as mine",
                "نفس العنوان", "نفس عنواني", "زي عنواني", "نفس المكان"
            }
            if any(phrase in normalized_text.lower() for phrase in same_as_me):
                address = form_state.get("address")
                if address:
                    updates[field_name] = address
                    return
            
            cleaned = self._clean_answer_fallback(raw_text)
            if cleaned:
                updates[field_name] = cleaned
            return

        if field_name in {
            "school_name", "address", "city", "district", "governorate",
            "place_of_birth", "nationality", "gender", "marital_status",
            "guardian_profession", "guardian_nationality", "guardian_city",
            "guardian_district", "guardian_work_address"
        }:
            cleaned = self._clean_answer_fallback(raw_text)
            if cleaned:
                updates[field_name] = cleaned

    def _clean_answer_fallback(self, text: str) -> str:
        """
        Clean common answer prefixes for current field fallback extraction.
        """
        text = text.strip(" .,،!؟?")

        # Common prefixes to remove (longest first)
        prefixes = [
            r"my full name in english is",
            r"my full name in arabic is",
            r"my full name is",
            r"my name is",
            r"my phone number is",
            r"my phone is",
            r"my mobile is",
            r"my email is",
            r"my percentage is",
            r"my certificate is",
            r"the certificate is",
            r"it is",
            r"it's",
            r"i am",
            r"i'm",
            r"i got",
            r"i scored",
            r"اسمي هو",
            r"اسمي",
            r"انا اسمي",
            r"انا",
            r"رقم تليفوني",
            r"رقمي",
            r"ايميلي",
            r"بريدي",
            r"مجموعي",
            r"انا جبت",
            r"جبت",
            r"i live in",
            r"my governorate is",
            r"my city is",
            r"i am from",
            r"انا من",
            r"أنا من",
            r"انا ساكن في",
            r"أنا ساكن في",
            r"ساكن في",
            r"محافظتي هي",
            r"محافظتي",
            r"مدينتي هي",
            r"مدينتي",
            r"شهادتي هي",
            r"شهادتي",
        ]

        cleaned = text
        for prefix in prefixes:
            # Match prefix at start (case-insensitive)
            pattern = rf"^{prefix}\s*"
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
                break  # Remove only one prefix

        return cleaned.strip(" .,،!؟?")

    def _normalize_digits(self, text: str) -> str:
        """
        Convert digit words to digits and join separated digit sequences.
        """
        digit_map = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
            "زيرو": "0", "صفر": "0", "واحد": "1", "اتنين": "2", "اثنين": "2",
            "تلاتة": "3", "ثلاثة": "3", "اربعة": "4", "أربعة": "4", "خمسة": "5",
            "ستة": "6", "سبعة": "7", "تمنية": "8", "ثمانية": "8", "تسعة": "9"
        }
        
        words = text.lower().split()
        normalized_words = []
        for word in words:
            normalized_words.append(digit_map.get(word, word))
        
        joined_text = " ".join(normalized_words)
        
        # Join sequences of digits separated by spaces
        # e.g. "3 0 5" -> "305"
        def join_digits(match):
            return match.group(0).replace(" ", "")
            
        return re.sub(r"\b\d(?:\s+\d)+\b", join_digits, joined_text)

    def _normalize_email_transcript(self, text: str) -> str:
        """
        Normalize spoken email phrases.
        """
        text = text.lower()
        
        # Normalize spoken words to symbols
        replacements = [
            (r"\s+at(\s+|$)", "@"), (r"\s+dot(\s+|$)", "."), (r"\s+underscore(\s+|$)", "_"),
            (r"\s+dash(\s+|$)", "-"), (r"\s+hyphen(\s+|$)", "-"),
            (r"\s+آت(\s+|$)", "@"), (r"\s+ات(\s+|$)", "@"), (r"\s+على(\s+|$)", "@"),
            (r"\s+دوت(\s+|$)", "."), (r"\s+نقطة(\s+|$)", "."),
            (r"\s+شرطة(\s+|$)", "-"), (r"\s+اندرسكور(\s+|$)", "_")
        ]
        
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)
            
        # Also replace digit words
        digit_map = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
        }
        for word, digit in digit_map.items():
            text = re.sub(rf"\b{word}\b", digit, text)
            
        # Remove all remaining spaces from the email
        text = text.replace(" ", "")
        
        return text.strip()

    def _clean_country_prefix(self, text: str) -> str:
        text = text.strip(" .,،!؟?")
        prefixes = [
            r"i live in", r"i am from", r"my country is", r"country is",
            r"انا من", r"أنا من", r"بلدي", r"الدولة"
        ]
        
        cleaned = text
        for prefix in prefixes:
            pattern = rf"^{prefix}\s*"
            if re.search(pattern, cleaned, flags=re.IGNORECASE):
                cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
                break
                
        return cleaned.strip(" .,،!؟?")

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

    def _extract_loose_sensitive_values(
        self,
        raw_text: str,
        updates: dict[str, Any],
        guardian_context: bool,
    ) -> None:
        if "student_mobile_no" not in updates and "guardian_mobile_no" not in updates:
            phone_match = re.search(
                r"(?:phone|mobile|رقمي|رقمه|موبايل)\D*([0-9][0-9\s\-]{4,20})",
                raw_text,
                flags=re.IGNORECASE,
            )

            if phone_match:
                field_name = (
                    "guardian_mobile_no" if guardian_context else "student_mobile_no"
                )
                updates[field_name] = re.sub(r"\D", "", phone_match.group(1))

        if "percentage" not in updates:
            percentage_match = re.search(
                r"(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent|percentage|مجموعي)",
                raw_text,
                flags=re.IGNORECASE,
            )

            if percentage_match:
                try:
                    updates["percentage"] = float(percentage_match.group(1))
                except ValueError:
                    pass

    def _extract_names(
        self,
        raw_text: str,
        normalized_text: str,
        updates: dict[str, Any],
        guardian_context: bool,
    ) -> None:
        # Avoid filling names with generic job titles or short words if not explicitly current field
        def is_bad_name(name: str) -> bool:
            bad_words = {"مهندس", "طبيب", "مدرس", "طالب", "engineer", "doctor", "teacher", "student"}
            return name.lower() in bad_words or len(name.split()) < 2

        guardian_english_match = re.search(
            r"\b(?:my\s+)?(?:father|mother|parent|guardian)\s+name\s+is\s+(.+?)(?=\s+(?:and|,|phone|email|his|her|my)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if guardian_english_match:
            name = self._clean_value(guardian_english_match.group(1))

            if name and not is_bad_name(name):
                updates["guardian_name"] = name

            return

        guardian_arabic_match = re.search(
            r"(?:اسم\s+(?:ولي الامر|ولى الامر|الاب|الأب|الام|الأم|والدي|والدتي)|(?:ولي الامر|ولى الامر|الاب|الأب|الام|الأم|والدي|والدتي)\s+اسمه?)\s+(.+?)(?=\s+و(?:رقمه|رقمها|ايميله|ايميلها|البريد)|\s+و|\s*,|$)",
            normalized_text,
        )

        if guardian_arabic_match:
            name = self._clean_value(guardian_arabic_match.group(1))

            if name and not is_bad_name(name):
                updates["guardian_name"] = name

            return

        english_match = re.search(
            r"\b(?:my name is|name is|i am)\s+(.+?)(?=\s+(?:and|,|my phone|phone|my email|email)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if english_match:
            name = self._clean_value(english_match.group(1))

            if name and not is_bad_name(name):
                updates["guardian_name" if guardian_context else "full_name_en"] = name

        arabic_match = re.search(
            r"(?:انا اسمي|اسمي)\s+(.+?)(?=\s+و(?:رقمي|مجموعي|البريد|ايميلي|مدرستي|انا|اسمي)|\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_match:
            name = self._clean_value(arabic_match.group(1))

            if name and not is_bad_name(name):
                updates["guardian_name" if guardian_context else "full_name_ar"] = name

    def _extract_relationship(self, text_lower: str, updates: dict[str, Any]) -> None:
        relationship_patterns = [
            (r"\bguardian\b|(?<!\w)(?:ولي الامر|ولى الامر)(?!\w)", "Guardian"),
            (r"\bfather\b|\bdad\b|(?<!\w)(?:والد|الاب|الأب)(?!\w)", "Father"),
            (r"\bmother\b|\bmom\b|(?<!\w)(?:والدة|الام|الأم)(?!\w)", "Mother"),
            (r"\bbrother\b|(?<!\w)(?:اخ|أخ)(?!\w)", "Brother"),
            (r"\bsister\b|(?<!\w)(?:اخت|أخت)(?!\w)", "Sister"),
        ]

        for pattern, relationship in relationship_patterns:
            if re.search(pattern, text_lower):
                updates["relationship"] = relationship
                return

    def _extract_address(
        self,
        raw_text: str,
        normalized_text: str,
        updates: dict[str, Any],
    ) -> None:
        city_match = re.search(
            r"\b(?:i live in|my city is)\s+(.+?)(?=\s+(?:and|,|my country|my address)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if city_match:
            city = self._clean_value(city_match.group(1))

            if city:
                updates["city"] = city

        country_match = re.search(
            r"\bmy country is\s+(.+?)(?=\s+(?:and|,|my city|my address)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if country_match:
            country = self._clean_value(country_match.group(1))

            if country:
                updates["country"] = country

        address_match = re.search(
            r"\bmy address is\s+(.+?)(?=\s+(?:and|,|my city|my country)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if address_match:
            address = self._clean_value(address_match.group(1))

            if address:
                updates["address"] = address

        arabic_city_match = re.search(
            r"(?:انا ساكن في|مدينتي)\s+(.+?)(?=\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_city_match:
            city = self._clean_value(arabic_city_match.group(1))

            if city:
                updates["city"] = city

        arabic_country_match = re.search(
            r"بلدي\s+(.+?)(?=\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_country_match:
            country = self._clean_value(arabic_country_match.group(1))

            if country:
                updates["country"] = country

        arabic_address_match = re.search(
            r"عنواني\s+(.+?)(?=\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_address_match:
            address = self._clean_value(arabic_address_match.group(1))

            if address:
                updates["address"] = address

    def _extract_school(
        self,
        raw_text: str,
        normalized_text: str,
        updates: dict[str, Any],
    ) -> None:
        english_match = re.search(
            r"\b(?:my school is|school name is|i studied at|i graduated from)\s+(.+?)(?=\s+(?:and|,|in 20)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if english_match:
            school_name = self._clean_value(english_match.group(1))

            if school_name:
                updates["school_name"] = school_name

        arabic_match = re.search(
            r"(?:انا خريج مدرسة|انا في مدرسة|مدرستي|اسم المدرسة)\s+(.+?)(?=\s+و|\s*,|$)",
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
        if any(field_name.startswith("college_preference_") for field_name in updates):
            return

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

    def _extract_ranked_college_preferences(
        self,
        raw_text: str,
        normalized_text: str,
        form_state: dict[str, Any],
        updates: dict[str, Any],
    ) -> None:
        searchable_text = self._normalize_preference_text(
            f"{raw_text} {normalized_text}"
        )
        rank_words = {
            1: ["first", "1st", "one", "اول", "الاولي", "الأولى", "اولى"],
            2: ["second", "2nd", "two", "ثاني", "الثانية", "التانية"],
            3: ["third", "3rd", "three", "ثالث", "الثالثة", "التالتة"],
            4: ["fourth", "4th", "four", "رابع", "الرابعة"],
            5: ["fifth", "5th", "five", "خامس", "الخامسة"],
            6: ["sixth", "6th", "six", "سادس", "السادسة"],
        }

        for faculty_id, aliases in FACULTY_ALIASES.items():
            for alias in aliases:
                alias_text = self._normalize_preference_text(alias)

                if not alias_text:
                    continue

                for match in re.finditer(
                    rf"(?<!\w){re.escape(alias_text)}(?!\w)",
                    searchable_text,
                ):
                    window_start = max(0, match.start() - 45)
                    window_end = min(len(searchable_text), match.end() + 45)
                    window = searchable_text[window_start:window_end]
                    rank = self._preference_rank_from_window(
                        window=window,
                        rank_words=rank_words,
                        alias_start=match.start() - window_start,
                        alias_end=match.end() - window_start,
                    )

                    if not rank:
                        continue

                    field_name = f"college_preference_{rank}"

                    if not form_state.get(field_name) and field_name not in updates:
                        updates[field_name] = faculty_id

    def _preference_rank_from_window(
        self,
        window: str,
        rank_words: dict[int, list[str]],
        alias_start: int,
        alias_end: int,
    ) -> int | None:
        nearest_rank: int | None = None
        nearest_distance: int | None = None

        for rank, words in rank_words.items():
            for word in words:
                normalized_word = self._normalize_preference_text(word)

                for match in re.finditer(
                    rf"(?<!\w){re.escape(normalized_word)}(?!\w)",
                    window,
                ):
                    if match.end() <= alias_start:
                        distance = alias_start - match.end()
                    elif match.start() >= alias_end:
                        distance = match.start() - alias_end
                    else:
                        distance = 0

                    if nearest_distance is None or distance < nearest_distance:
                        nearest_distance = distance
                        nearest_rank = rank

        return nearest_rank

    def _normalize_preference_text(self, text: str) -> str:
        normalized = text.lower()
        normalized = re.sub(r"[أإآٱ]", "ا", normalized)
        normalized = normalized.replace("ى", "ي")
        normalized = normalized.replace("ؤ", "و")
        normalized = normalized.replace("ئ", "ي")
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)

        return normalized.strip()

    def _extract_semantic_updates(
        self,
        processed_text: ProcessedText,
        form_state: dict[str, Any],
        deterministic_updates: dict[str, Any],
        language: str,
    ) -> tuple[dict[str, Any], list[str]]:
        if not ENABLE_LLM_REGISTRATION_EXTRACTION:
            return {}, []

        missing_allowed_fields = [
            field_name
            for field_name in self.LLM_ALLOWED_FIELDS
            if not form_state.get(field_name) and field_name not in deterministic_updates
        ]

        if not missing_allowed_fields:
            return {}, []

        route_notes = [
            "llm_registration_extraction_checked",
            *self.llm_client.route_notes,
        ]
        current_form = {
            **form_state,
            **deterministic_updates,
        }
        extracted = self.llm_client.extract_registration_fields(
            text=processed_text.raw_text,
            current_form=current_form,
            language=language,
        )

        if not extracted:
            return {}, route_notes + ["llm_registration_extraction_failed"]

        correction_requested = self._has_correction_words(processed_text.normalized_text)
        validated_updates: dict[str, Any] = {}

        for field_name, value in extracted.items():
            if field_name not in self.LLM_ALLOWED_FIELDS:
                continue

            if value in {None, ""}:
                continue

            if (
                not correction_requested
                and (form_state.get(field_name) or deterministic_updates.get(field_name))
            ):
                continue

            cleaned_value = self._validate_llm_field_value(field_name, value)

            if cleaned_value in {None, ""}:
                continue

            validated_updates[field_name] = cleaned_value

        if not validated_updates:
            return {}, route_notes + ["llm_registration_extraction_failed"]

        return validated_updates, route_notes + ["llm_registration_fields_extracted"]

    def _validate_llm_field_value(self, field_name: str, value: Any) -> Any:
        if isinstance(value, str):
            value = self._clean_value(value)

        if value in {None, ""}:
            return None

        if field_name.startswith("college_preference_"):
            return self._faculty_id_from_value(str(value))

        return value

    def _faculty_id_from_value(self, value: str) -> str | None:
        normalized_value = value.strip().lower()

        if normalized_value in FACULTY_ALIASES:
            return normalized_value

        for faculty_id, aliases in FACULTY_ALIASES.items():
            if normalized_value == faculty_id:
                return faculty_id

            for alias in aliases:
                if normalized_value == alias.lower():
                    return faculty_id

        return None

    def _can_update_field(
        self,
        field_name: str,
        form_state: dict[str, Any],
        correction_requested: bool,
    ) -> bool:
        if correction_requested:
            return True

        return not form_state.get(field_name)

    def _validate_field_value(self, field_name: str, value: Any) -> tuple[Any, bool]:
        # Get field definition for validation_type
        field_def = next((f for f in self.field_definitions if f["field_id"] == field_name), {})
        validation_type = field_def.get("validation_type")

        if validation_type == "mobile" or field_name in {"student_mobile_no", "guardian_mobile_no"}:
            return self._validate_mobile(value)

        if validation_type == "email" or field_name in {"email_address", "guardian_email_address"}:
            return self._validate_email(value)

        if validation_type == "id_or_passport" or field_name in {"id_or_passport", "guardian_id_or_passport"}:
            return self._validate_id_or_passport(value)

        if validation_type == "percentage" or field_name in {"percentage", "science_score", "math_score", "literary_score"}:
            return self._validate_percentage(value)

        if validation_type == "year" or field_name == "year_of_completion":
            return self._validate_year(value)

        if validation_type == "date" or field_name == "date_of_birth":
            return self._validate_date(value)

        if validation_type == "faculty" or field_name.startswith("college_preference_"):
            faculty_id = self._faculty_id_from_value(str(value))
            return faculty_id, faculty_id is not None

        if validation_type == "arabic_name":
            return self._validate_arabic_name(value)

        if validation_type == "english_name":
            return self._validate_english_name(value)

        if validation_type == "gender":
            return self._validate_gender(value)

        if validation_type == "relationship":
            return self._validate_relationship(value)

        if field_name == "governorate":
            return self._normalize_governorate(value)

        return value, True

    def _validate_date(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip()
        # Supported formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
        patterns = [
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
            r"(\d{4})-(\d{1,2})-(\d{1,2})"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if len(groups[0]) == 4: # YYYY-MM-DD
                    year, month, day = map(int, groups)
                else: # DD/MM/YYYY
                    day, month, year = map(int, groups)
                
                try:
                    dt = datetime(year, month, day)
                    if dt > datetime.now():
                        return None, False
                    return dt.strftime("%Y-%m-%d"), True
                except ValueError:
                    continue
        
        return None, False

    def _validate_arabic_name(self, value: Any) -> tuple[str | None, bool]:
        name = str(value).strip()
        # Arabic letters and spaces
        is_arabic = re.fullmatch(r"[\u0600-\u06FF\s]+", name) is not None
        # At least 2 names
        has_two_names = len(name.split()) >= 2
        # No numbers
        no_numbers = not any(c.isdigit() for c in name)

        is_valid = is_arabic and has_two_names and no_numbers
        return name if is_valid else None, is_valid

    def _validate_english_name(self, value: Any) -> tuple[str | None, bool]:
        name = str(value).strip()
        # English letters and spaces
        is_english = re.fullmatch(r"[A-Za-z\s]+", name) is not None
        # At least 2 names
        has_two_names = len(name.split()) >= 2
        # No numbers
        no_numbers = not any(c.isdigit() for c in name)

        is_valid = is_english and has_two_names and no_numbers
        return name if is_valid else None, is_valid

    def _validate_gender(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip().lower()
        male_words = {"male", "ذكر", "ولد", "راجل"}
        female_words = {"female", "أنثى", "انثى", "بنت", "ست"}

        if text in male_words:
            return "Male", True
        if text in female_words:
            return "Female", True

        return None, False

    def _validate_relationship(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip().lower()
        rel_map = {
            "father": ["father", "dad", "أب", "اب", "والد"],
            "mother": ["mother", "mom", "أم", "ام", "والدة"],
            "brother": ["brother", "أخ", "اخ"],
            "sister": ["sister", "أخت", "اخت"],
            "uncle": ["uncle", "عم", "خال"],
            "aunt": ["aunt", "عمة", "خالة"],
            "grandfather": ["grandfather", "جد"],
            "grandmother": ["grandmother", "جدة"],
            "other": ["other", "أخرى", "اخرى"]
        }

        for canonical, aliases in rel_map.items():
            if text == canonical or any(alias in text for alias in aliases):
                return canonical.capitalize(), True

        return None, False

    def _normalize_governorate(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip().lower()
        gov_map = {
            "Cairo": ["cairo", "القاهرة", "قاهره"],
            "Giza": ["giza", "الجيزة", "جيزة"],
            "Alexandria": ["alexandria", "الإسكندرية", "اسكندرية"],
            "Dakahlia": ["dakahlia", "الدقهلية"],
            "Red Sea": ["red sea", "البحر الأحمر"],
            "Beheira": ["beheira", "البحيرة"],
            "Fayoum": ["fayoum", "الفيوم"],
            "Gharbiya": ["gharbiya", "الغربية"],
            "Ismailia": ["ismailia", "الإسماعيلية"],
            "Monufiya": ["monufiya", "المنوفية"],
            "Minya": ["minya", "المنيا"],
            "Qalyubiya": ["qalyubiya", "القليوبية"],
            "New Valley": ["new valley", "الوادي الجديد"],
            "Suez": ["suez", "السويس"],
            "Aswan": ["aswan", "أسوان"],
            "Assiut": ["assiut", "أسيوط"],
            "Beni Suef": ["beni suef", "بني سويف"],
            "Port Said": ["port said", "بورسعيد"],
            "Damietta": ["damietta", "دمياط"],
            "Sharkia": ["sharkia", "الشرقية"],
            "South Sinai": ["south sinai", "جنوب سيناء"],
            "Kafr El Sheikh": ["kafr el sheikh", "كفر الشيخ"],
            "Matrouh": ["matrouh", "مطروح"],
            "Luxor": ["luxor", "الأقصر"],
            "Qena": ["qena", "قنا"],
            "North Sinai": ["north sinai", "شمال سيناء"],
            "Sohag": ["sohag", "سوهاج"]
        }

        for canonical, aliases in gov_map.items():
            if text == canonical.lower() or any(alias in text for alias in aliases):
                return canonical, True

        return value, True # Allow if not in map but keep as is

    def _validate_mobile(self, value: Any) -> tuple[str | None, bool]:
        digits = re.sub(r"\D", "", str(value))
        is_valid = (
            len(digits) == 11
            and digits.startswith(("010", "011", "012", "015"))
        )

        return digits if is_valid else None, is_valid

    def _validate_email(self, value: Any) -> tuple[str | None, bool]:
        email = str(value).strip()
        is_valid = re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            email,
        ) is not None

        return email if is_valid else None, is_valid

    def _validate_id_or_passport(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip()
        digits = re.sub(r"\D", "", text)

        # Egyptian ID: Exactly 14 digits
        if digits and len(digits) == len(text):
            if len(digits) == 14:
                return digits, True
            return None, False

        # Passport: alphanumeric, at least one letter, length 6-20
        if 6 <= len(text) <= 20 and any(c.isalpha() for c in text) and text.isalnum():
            return text, True

        return None, False

    def _validate_percentage(self, value: Any) -> tuple[float | None, bool]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None, False

        is_valid = 0 <= number <= 100

        return number if is_valid else None, is_valid

    def _validate_year(self, value: Any) -> tuple[int | None, bool]:
        try:
            year = int(value)
        except (TypeError, ValueError):
            return None, False

        current_year = datetime.now().year
        is_valid = 2015 <= year <= current_year + 1

        return year if is_valid else None, is_valid

    def _retry_question(self, field_name: str, language: str) -> str:
        if field_name in {"id_or_passport", "guardian_id_or_passport"}:
            if language == "ar":
                return "لم أسمع الرقم القومي كاملًا. من فضلك قل الـ 14 رقم ببطء، أو اكتبه يدويًا."
            return "I did not hear the full national ID. Please say the 14 digits slowly, or type it manually."
            
        if field_name in {"student_mobile_no", "guardian_mobile_no"}:
            if language == "ar":
                return "لم أسمع الرقم كاملًا. من فضلك قل الـ 11 رقم ببطء، أو اكتبه يدويًا."
            return "I did not hear the full mobile number. Please say the 11 digits slowly, or type it manually."
            
        if field_name in {"email_address", "guardian_email_address"}:
            if language == "ar":
                return "لم أسمع البريد الإلكتروني كاملًا. من فضلك قل البريد مرة أخرى مثل: name at gmail dot com، أو اكتبه يدويًا."
            return "I could not hear the full email address. Please say it again like: name at gmail dot com, or type it manually."
            
        return self._question_for_field(field_name, language)

    def _has_correction_words(self, text: str) -> bool:
        text_lower = text.lower()

        return any(word in text_lower for word in self.CORRECTION_WORDS)

    def _has_guardian_context(self, text_lower: str) -> bool:
        return any(
            re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text_lower)
            for word in self.GUARDIAN_WORDS
        )

    def _handle_confirmation_command(
        self,
        normalized_text: str,
        session_state: dict[str, Any],
        language: str,
    ) -> dict[str, Any] | None:
        command_text = normalized_text.strip().lower()

        if command_text in self.CONFIRM_WORDS:
            latest_sensitive_fields = session_state.get("latest_sensitive_fields", [])

            for field_name in latest_sensitive_fields:
                metadata = session_state["metadata"].setdefault(field_name, {})
                metadata["confirmed"] = True
                metadata["needs_confirmation"] = False

            session_state["latest_sensitive_fields"] = []
            self._sync_current_field(
                session_state=session_state,
                language=language,
            )

            return {
                "needs_confirmation": False,
                "next_question": None,
                "route_notes": [
                    "registration_confirmation_received",
                    *[
                        f"field_confirmed:{field_name}"
                        for field_name in latest_sensitive_fields
                    ],
                ],
            }

        if command_text in self.REJECT_WORDS:
            latest_sensitive_fields = session_state.get("latest_sensitive_fields", [])
            field_label = latest_sensitive_fields[0] if latest_sensitive_fields else "the field"

            if language == "ar":
                next_question = "من فضلك أعد إدخال هذه المعلومة بشكل صحيح."
            else:
                next_question = f"Please repeat {field_label} correctly."

            return {
                "needs_confirmation": True,
                "next_question": next_question,
                "route_notes": ["registration_confirmation_rejected"],
            }

        return None

    def _sync_current_field(
        self,
        session_state: dict[str, Any],
        language: str,
    ) -> str | None:
        current_field = session_state.get("current_field")
        form_state = session_state.get("fields", {})
        metadata = session_state.get("metadata", {})
        skipped_fields = session_state.setdefault("skipped_fields", set())

        if isinstance(skipped_fields, list):
            skipped_fields = set(skipped_fields)
            session_state["skipped_fields"] = skipped_fields

        if current_field and self._guided_field_needs_answer(
            field_name=current_field,
            form_state=form_state,
            metadata=metadata,
            skipped_fields=skipped_fields,
        ):
            return current_field

        next_field = self._next_guided_field(
            form_state=form_state,
            metadata=metadata,
            skipped_fields=skipped_fields,
            language=language,
        )
        session_state["current_field"] = next_field

        return next_field

    def _next_guided_field(
        self,
        form_state: dict[str, Any],
        metadata: dict[str, Any],
        skipped_fields: set[str],
        language: str,
    ) -> str | None:
        for field_name in self._guided_field_order(language):
            if self._guided_field_needs_answer(
                field_name=field_name,
                form_state=form_state,
                metadata=metadata,
                skipped_fields=skipped_fields,
            ):
                return field_name

        return None

    def _guided_field_order(self, language: str) -> list[str]:
        return [
            field["field_id"]
            for field in self.field_definitions
            if field.get("ask_in_guided_voice") is True
        ]

    def _guided_field_needs_answer(
        self,
        field_name: str,
        form_state: dict[str, Any],
        metadata: dict[str, Any],
        skipped_fields: set[str],
    ) -> bool:
        if field_name in skipped_fields:
            return False

        if not form_state.get(field_name):
            return True

        if field_name in self.sensitive_fields:
            return not metadata.get(field_name, {}).get("confirmed", False)

        return False

    def _question_for_field(self, field_name: str | None, language: str) -> str | None:
        if not field_name:
            return None

        prompts = self.prompts.get(field_name, {})

        if language == "ar":
            return prompts.get("ar") or prompts.get("en")

        return prompts.get("en") or prompts.get("ar")

    def _confirmation_question(
        self,
        latest_sensitive_fields: list[str],
        language: str,
    ) -> str:
        field_name = latest_sensitive_fields[0] if latest_sensitive_fields else "the field"

        if language == "ar":
            return "هل هذه المعلومة صحيحة؟ قل نعم للتأكيد أو لا للتعديل."

        return f"Please confirm {field_name}. Say confirm if it is correct."

    def _form_state_with_auto_fields(self, form_state: dict[str, Any]) -> dict[str, Any]:
        values = dict(form_state)

        if not values.get("final_student_name"):
            student_name = values.get("full_name_ar") or values.get("full_name_en")

            if student_name:
                values["final_student_name"] = student_name

        if not values.get("final_college") and values.get("college_preference_1"):
            values["final_college"] = values["college_preference_1"]

        return values

    def _missing_required_fields(self, form_state: dict[str, Any]) -> list[str]:
        missing_fields: list[str] = []

        if not any(form_state.get(field_name) for field_name in self.REQUIRED_NAME_FIELDS):
            missing_fields.append("full_name_en")

        missing_fields.extend(
            field_name
            for field_name in self.required_core_fields
            if not form_state.get(field_name) and field_name not in self.REQUIRED_NAME_FIELDS
        )

        return missing_fields

    def _completion_percentage(self, form_state: dict[str, Any]) -> int:
        required_count = len(self.required_core_fields) + 1
        filled_count = required_count - len(self._missing_required_fields(form_state))

        return round((filled_count / required_count) * 100)

    def _unconfirmed_sensitive_fields(
        self,
        form_state: dict[str, Any],
        metadata: dict[str, Any],
    ) -> list[str]:
        unconfirmed_fields: list[str] = []

        for field_name in self.sensitive_fields:
            if field_name not in form_state:
                continue

            field_metadata = metadata.get(field_name, {})

            if not field_metadata.get("confirmed", False):
                unconfirmed_fields.append(field_name)

        return [
            field_name
            for field_name in self.field_order
            if field_name in unconfirmed_fields
        ]

    def _english_review_summary(
        self,
        filled_fields: dict[str, Any],
        missing_required_fields: list[str],
        unconfirmed_sensitive_fields: list[str],
    ) -> str:
        full_name = filled_fields.get("full_name_en") or filled_fields.get("full_name_ar")

        lines = [
            "Please review your registration data:",
            "",
            f"* Full Name: {self._display_value(full_name)}",
            f"* Mobile Number: {self._display_value(filled_fields.get('student_mobile_no'))}",
            f"* Email: {self._display_value(filled_fields.get('email_address'))}",
            f"* National ID / Passport: {self._display_value(filled_fields.get('id_or_passport'))}",
            f"* School Name: {self._display_value(filled_fields.get('school_name'))}",
            f"* Certificate: {self._display_value(filled_fields.get('certificate'))}",
            f"* Percentage: {self._display_value(filled_fields.get('percentage'))}",
            f"* First College Preference: {self._display_value(filled_fields.get('college_preference_1'))}",
            f"Missing required fields: {self._display_list(missing_required_fields)}",
            f"Unconfirmed sensitive fields: {self._display_list(unconfirmed_sensitive_fields)}",
        ]

        return "\n".join(lines)

    def _arabic_review_summary(
        self,
        filled_fields: dict[str, Any],
        missing_required_fields: list[str],
        unconfirmed_sensitive_fields: list[str],
    ) -> str:
        full_name = filled_fields.get("full_name_ar") or filled_fields.get("full_name_en")

        lines = [
            "من فضلك راجع بيانات التسجيل:",
            "",
            f"* الاسم: {self._display_value(full_name, missing_text='غير مدخل')}",
            f"* رقم الموبايل: {self._display_value(filled_fields.get('student_mobile_no'), missing_text='غير مدخل')}",
            f"* البريد الإلكتروني: {self._display_value(filled_fields.get('email_address'), missing_text='غير مدخل')}",
            f"* الرقم القومي / جواز السفر: {self._display_value(filled_fields.get('id_or_passport'), missing_text='غير مدخل')}",
            f"* المدرسة: {self._display_value(filled_fields.get('school_name'), missing_text='غير مدخل')}",
            f"* الشهادة: {self._display_value(filled_fields.get('certificate'), missing_text='غير مدخل')}",
            f"* المجموع: {self._display_value(filled_fields.get('percentage'), missing_text='غير مدخل')}",
            f"* الرغبة الأولى: {self._display_value(filled_fields.get('college_preference_1'), missing_text='غير مدخل')}",
            f"البيانات الناقصة: {self._display_list(missing_required_fields, empty_text='لا توجد')}",
            f"البيانات التي تحتاج تأكيد: {self._display_list(unconfirmed_sensitive_fields, empty_text='لا توجد')}",
        ]

        return "\n".join(lines)

    def _next_question(self, missing_required_fields: list[str], language: str) -> str | None:
        if not missing_required_fields:
            if language == "ar":
                return "تم إدخال البيانات الأساسية. من فضلك راجع البيانات على الشاشة قبل الإرسال النهائي."

            return "Basic registration data is complete. Please review the information on screen before final submission."

        field_name = missing_required_fields[0]
        return self._question_for_field(field_name, language)

    def _clean_value(self, value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" .,،")
        value = re.sub(r"\b(?:and|my|phone|email|school)\b.*$", "", value, flags=re.IGNORECASE)
        return value.strip(" .,،")

    def _display_value(self, value: Any, missing_text: str = "Not provided") -> str:
        if value in {None, ""}:
            return missing_text

        return str(value)

    def _display_list(self, values: list[str], empty_text: str = "None") -> str:
        if not values:
            return empty_text

        return ", ".join(values)

    def show_field_order(self) -> str:
        """
        Print all fields in order grouped by section.
        """
        sections: dict[str, list[dict[str, Any]]] = {}
        for field in self.field_definitions:
            section = field.get("section", "Other")
            sections.setdefault(section, []).append(field)
            
        output = []
        for section, fields in sections.items():
            output.append(f"SECTION: {section}")
            for field in fields:
                voice_tag = "[VOICE]" if field.get("ask_in_guided_voice") else ""
                output.append(f"  {field.get('order', '?')}. {field['field_id']} {voice_tag}")
            output.append("")
            
        return "\n".join(output)
