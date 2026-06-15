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
        "guardian_id_or_passport",
        "student_mobile_no",
        "guardian_mobile_no",
        "email_address",
        "guardian_email_address",
        "percentage",
        "total_marks",
        "password",
    }

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
        session_state = self.sessions.setdefault(
            session_id,
            {
                "fields": {},
                "metadata": {},
                "latest_sensitive_fields": [],
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
            next_question = (
                confirmation_result["next_question"]
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

        extracted_updates = self._extract_updates(processed_text, form_state)

        form_updates: dict[str, Any] = {}
        needs_confirmation = False
        latest_sensitive_fields: list[str] = []

        for field_name, value in extracted_updates.items():
            if value in {None, ""}:
                continue

            form_state[field_name] = value
            form_updates[field_name] = value
            session_state["metadata"][field_name] = {
                "value": value,
                "confirmed": False,
                "needs_confirmation": field_name in self.SENSITIVE_FIELDS,
                "source_text": processed_text.raw_text,
            }
            route_notes.append(f"field_filled:{field_name}")

            if field_name in self.SENSITIVE_FIELDS:
                needs_confirmation = True
                latest_sensitive_fields.append(field_name)
                route_notes.append(f"confirmation_needed:{field_name}")

        session_state["latest_sensitive_fields"] = latest_sensitive_fields
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
        self._extract_relationship(text_lower, updates)
        self._extract_names(raw_text, normalized_text, updates, guardian_context)
        self._extract_address(raw_text, normalized_text, updates)
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
        guardian_context: bool,
    ) -> None:
        guardian_english_match = re.search(
            r"\b(?:my\s+)?(?:father|mother|parent|guardian)\s+name\s+is\s+(.+?)(?=\s+(?:and|,|phone|email|his|her|my)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if guardian_english_match:
            name = self._clean_value(guardian_english_match.group(1))

            if name:
                updates["guardian_name"] = name

            return

        guardian_arabic_match = re.search(
            r"(?:اسم\s+(?:ولي الامر|ولى الامر|الاب|الأب|الام|الأم|والدي|والدتي)|(?:ولي الامر|ولى الامر|الاب|الأب|الام|الأم|والدي|والدتي)\s+اسمه?)\s+(.+?)(?=\s+و(?:رقمه|رقمها|ايميله|ايميلها|البريد)|\s+و|\s*,|$)",
            normalized_text,
        )

        if guardian_arabic_match:
            name = self._clean_value(guardian_arabic_match.group(1))

            if name:
                updates["guardian_name"] = name

            return

        english_match = re.search(
            r"\b(?:my name is|name is|i am)\s+(.+?)(?=\s+(?:and|,|my phone|phone|my email|email)\b|$)",
            raw_text,
            flags=re.IGNORECASE,
        )

        if english_match:
            name = self._clean_value(english_match.group(1))

            if name:
                updates["guardian_name" if guardian_context else "full_name_en"] = name

        arabic_match = re.search(
            r"(?:انا اسمي|اسمي)\s+(.+?)(?=\s+و(?:رقمي|مجموعي|البريد|ايميلي|مدرستي|انا|اسمي)|\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_match:
            name = self._clean_value(arabic_match.group(1))

            if name:
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

    def _unconfirmed_sensitive_fields(
        self,
        form_state: dict[str, Any],
        metadata: dict[str, Any],
    ) -> list[str]:
        unconfirmed_fields: list[str] = []

        for field_name in self.SENSITIVE_FIELDS:
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
        prompts = self.prompts.get(field_name, {})

        if language == "ar":
            return prompts.get("ar") or prompts.get("en")

        return prompts.get("en") or prompts.get("ar")

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
