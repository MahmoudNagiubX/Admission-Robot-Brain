"""
Fixed registration form engine for the Admission Robot AI Brain.

This module keeps in-memory form state per session and extracts a first set of
core registration fields using deterministic rules.
"""

import json
import re
import difflib
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

    PROFESSION_WORDS = {
        "مهندس", "طبيب", "دكتور", "مدرس", "معلم", "محاسب", "مدير", "عامل", "فني",
        "engineer", "doctor", "teacher", "accountant", "manager", "worker", "technician"
    }

    # Local safe name correction map for common Egyptian/Arabic names (Emergency fallback only).
    NAME_CORRECTION_MAP = {
        "mohamed": ("Mohamed", "محمد"),
        "ahmed": ("Ahmed", "أحمد"),
        "mahmoud": ("Mahmoud", "محمود"),
    }

    # Location and Address Mappings for Arabic Storage
    LOCATION_MAP = {
        # Countries
        "egypt": "مصر", "masr": "مصر", "misr": "مصر", "مصر": "مصر",
        
        # Governorates
        "cairo": "القاهرة", "giza": "الجيزة", "alexandria": "الإسكندرية",
        "dakahlia": "الدقهلية", "sharqia": "الشرقية", "gharbia": "الغربية",
        "monufia": "المنوفية", "menofia": "المنوفية", "qalyubia": "القليوبية",
        "beheira": "البحيرة", "fayoum": "الفيوم", "beni suef": "بني سويف",
        "minya": "المنيا", "assiut": "أسيوط", "sohag": "سوهاج", "qena": "قنا",
        "luxor": "الأقصر", "aswan": "أسوان", "red sea": "البحر الأحمر",
        "new valley": "الوادي الجديد", "matrouh": "مطروح", "north sinai": "شمال سيناء",
        "south sinai": "جنوب سيناء", "port said": "بورسعيد", "suez": "السويس",
        "ismailia": "الإسماعيلية", "damietta": "دمياط", "kafr el sheikh": "كفر الشيخ",

        # Arabic variants for governorates
        "القاهره": "القاهرة", "الجيزه": "الجيزة", "الاسكندرية": "الإسكندرية",
        "الاسكندريه": "الإسكندرية", "اسكندرية": "الإسكندرية", "اسكندريه": "الإسكندرية",
        "الدقهليه": "الدقهلية", "الشرقيه": "الشرقية", "الغربيه": "الغربية",
        "المنوفيه": "المنوفية", "القليوبيه": "القليوبية", "البحيره": "البحيرة",
        "الفيوم": "الفيوم", "بنى سويف": "بني سويف", "المنيا": "المنيا",
        "اسيوط": "أسيوط", "سوهاج": "سوهاج", "قنا": "قنا", "الاقصر": "الأقصر",
        "اسوان": "أسوان", "الاسماعيلية": "الإسماعيلية", "الاسماعيليه": "الإسماعيلية",
        "دمياط": "دمياط", "كفر الشيخ": "كفر الشيخ",

        # Common Cairo/Giza districts/cities
        "nasr city": "مدينة نصر", "new cairo": "القاهرة الجديدة",
        "fifth settlement": "التجمع الخامس", "first settlement": "التجمع الأول",
        "heliopolis": "مصر الجديدة", "maadi": "المعادي", "zamalek": "الزمالك",
        "downtown": "وسط البلد", "shubra": "شبرا", "abbasiya": "العباسية",
        "mokattam": "المقطم", "6th of october": "السادس من أكتوبر",
        "sheikh zayed": "الشيخ زايد", "haram": "الهرم", "faisal": "فيصل",
        "dokki": "الدقي", "mohandessin": "المهندسين", "agouza": "العجوزة",
        "imbaba": "إمبابة",
    }

    ADDRESS_WORDS_MAP = {
        "street": "شارع", "st": "شارع", "district": "الحي", "area": "منطقة",
        "building": "عمارة", "floor": "الدور", "apartment": "شقة", "tower": "برج",
        "square": "ميدان", "road": "طريق", "no": "رقم",
    }

    LOCATION_FIELDS = {
        "place_of_birth", "country", "governorate", "district", "city", "address",
        "guardian_country", "guardian_district", "guardian_address", "guardian_work_address"
    }

    LLM_ALLOWED_FIELDS = {
        "full_name_en",
        "full_name_ar",
        "school_name",
        "certificate",
        "sector",
        "guardian_name",
        "relationship",
        "address",
        "city",
        "country",
        "district",
        "governorate",
        "college_preference_1",
    }

    FRONTEND_FIELD_MAP = {
        "full_name_ar": "fullNameAr",
        "full_name_en": "fullNameEn",
        "date_of_birth": "dateOfBirth",
        "place_of_birth": "placeOfBirth",
        "nationality": "nationality",
        "id_or_passport": "nationalId",
        "gender": "gender",
        "marital_status": "maritalStatus",
        "country": "country",
        "governorate": "governorate",
        "district": "district",
        "city": "city",
        "address": "address",
        "home_phone": "homePhone",
        "student_mobile_no": "mobile",
        "mobile_no_2": "mobileNo2",
        "email_address": "email",
        "school_name": "schoolName",
        "certificate": "certificateType",
        "sector": "sector",
        "year_of_completion": "yearOfCompletion",
        "percentage": "percentage",
        "total_marks": "totalMarks",
        "seat_number": "seatNumber",
        "guardian_name": "guardianName",
        "relationship": "guardianRelationship",
        "guardian_id_or_passport": "guardianNationalId",
        "guardian_profession": "guardianProfession",
        "guardian_employer": "guardianEmployer",
        "guardian_nationality": "guardianNationality",
        "guardian_country": "guardianCountry",
        "guardian_district": "guardianDistrict",
        "guardian_address": "guardianAddress",
        "guardian_work_address": "guardianWorkAddress",
        "guardian_mobile_no": "guardianMobile",
        "guardian_home_phone": "guardianHomePhone",
        "guardian_work_no": "guardianWorkPhone",
        "guardian_email_address": "guardianEmail",
        "college_preference_1": "faculty",
        "final_student_name": "finalStudentName",
        "final_college": "finalCollege",
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
        
        # Load Name Lexicon
        self.name_lexicon = self._load_name_lexicon()
        self.name_lookup_en = {} # Normalized EN -> (Primary EN, Primary AR)
        self.name_lookup_ar = {} # Normalized AR -> (Primary EN, Primary AR)
        self._build_lexicon_lookups()

    def _load_name_lexicon(self) -> dict[str, Any]:
        lexicon_path = Path("data/name_lexicon.json")
        if lexicon_path.exists():
            try:
                with open(lexicon_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"entries": []}
        return {"entries": []}

    def _build_lexicon_lookups(self) -> None:
        if not self.name_lexicon or "entries" not in self.name_lexicon:
            return
            
        # First pass: All entries
        for entry in self.name_lexicon["entries"]:
            primary_ar = entry.get("ar")
            primary_en = entry.get("en_primary")
            if not primary_ar or not primary_en:
                continue
                
            pair = (primary_en, primary_ar)
            
            for en_alias in entry.get("en_aliases", []):
                # Don't overwrite if existing is from starter
                if en_alias in self.name_lookup_en:
                    # We'll handle precedence in second pass
                    pass
                self.name_lookup_en[en_alias] = pair
                
            for ar_alias in entry.get("ar_aliases", []):
                self.name_lookup_ar[ar_alias] = pair
                
        # Second pass: Overwrite with starter lexicon for precedence
        for entry in self.name_lexicon["entries"]:
            if "starter" in entry.get("source", []):
                primary_ar = entry.get("ar")
                primary_en = entry.get("en_primary")
                pair = (primary_en, primary_ar)
                
                for en_alias in entry.get("en_aliases", []):
                    self.name_lookup_en[en_alias] = pair
                for ar_alias in entry.get("ar_aliases", []):
                    self.name_lookup_ar[ar_alias] = pair

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

        # 1. Handle explicit confirmation commands (Yes/No)
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

        # 2. Extract updates (Strictly current-field-only if in guided flow)
        extracted_updates = self._extract_updates(
            processed_text=processed_text,
            form_state=form_state,
            current_field=current_field,
            correction_requested=correction_requested,
        )
        
        # Disable broad semantic extraction during guided flow to stay on target
        semantic_updates, semantic_route_notes = {}, []
        if not current_field or correction_requested:
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
        validation_errors = []

        # 3. Process and Validate updates
        for field_name, value in extracted_updates.items():
            if value in {None, ""}:
                continue

            # Skip if field is already filled and no correction requested
            if not self._can_update_field(
                field_name=field_name,
                form_state=form_state,
                correction_requested=correction_requested,
            ):
                route_notes.append(f"registration_update_skipped_existing:{field_name}")
                continue

            # Deterministic Validation
            normalized_value, is_valid = self._validate_field_value(field_name, value)

            # 4. LLM Correction Fallback (Only for current field if deterministic fails)
            is_transliterated = False
            if not is_valid and field_name == current_field and ENABLE_LLM_REGISTRATION_EXTRACTION:
                route_notes.append(f"deterministic_validation_failed:{field_name}")
                llm_correction_func = getattr(self.llm_client, "correct_registration_value", None)
                if llm_correction_func:
                    llm_candidate = llm_correction_func(
                        field_id=field_name,
                        raw_text=processed_text.raw_text,
                        language=language,
                    )
                    if llm_candidate and llm_candidate.get("candidate_value"):
                        # RE-VALIDATE LLM candidate deterministically
                        val = llm_candidate["candidate_value"]
                        normalized_value, is_valid = self._validate_field_value(field_name, val)
                        if is_valid:
                            route_notes.append(f"llm_correction_accepted:{field_name}")
                            # Detect if this was a transliteration for name fields
                            if field_name in {"full_name_ar", "full_name_en"}:
                                raw_text = processed_text.raw_text
                                if field_name == "full_name_ar" and bool(re.search(r"[A-Za-z]", raw_text)):
                                    is_transliterated = True
                                elif field_name == "full_name_en" and bool(re.search(r"[\u0600-\u06FF]", raw_text)):
                                    is_transliterated = True
                        else:
                            route_notes.append(f"llm_correction_invalid:{field_name}")
                else:
                    route_notes.append("llm_correction_unavailable")

            if not is_valid:
                route_notes.append(f"registration_validation_failed:{field_name}")
                if field_name == current_field:
                    validation_errors.append(field_name)
                continue

            # 5. Apply valid update
            form_state[field_name] = normalized_value
            form_updates[field_name] = normalized_value
            
            # Universal confirmation for all guided fields
            is_guided = session_state.get("guided_flow", False)
            requires_confirmation = is_guided or field_name in self.sensitive_fields or is_transliterated
            
            field_metadata = self._build_field_state(
                value=normalized_value,
                confidence=0.90,
                needs_confirmation=requires_confirmation,
                source="registration_extraction",
                source_text=processed_text.raw_text,
            )
            if is_transliterated:
                field_metadata["is_transliterated"] = True
                
            session_state["metadata"][field_name] = field_metadata
            route_notes.append(f"field_filled:{field_name}")

            if requires_confirmation:
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
        
        # 6. Determine Next Question / Retry Prompt
        if needs_confirmation:
            next_question = self._confirmation_question(latest_sensitive_fields, session_state, language)
        elif validation_errors:
            # Current field failed both deterministic and LLM correction
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

    def export_form_values_frontend(self, session_id: str) -> dict[str, Any]:
        """
        Export form values using camelCase keys for frontend compatibility.
        """
        snake_values = self.export_form_values(session_id)
        camel_values = {}
        
        for snake_key, value in snake_values.items():
            camel_key = self.FRONTEND_FIELD_MAP.get(snake_key)
            if camel_key:
                camel_values[camel_key] = value
                
        return camel_values

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
        unconfirmed_fields = self._unconfirmed_fields(form_state, metadata)
        unconfirmed_sensitive_fields = self._unconfirmed_sensitive_fields(form_state, metadata)
        completion_percentage = self._completion_percentage(form_state)

        return {
            "is_basic_registration_complete": self._is_registration_complete(form_state, metadata),
            "completion_percentage": completion_percentage,
            "missing_required_fields": missing_required_fields,
            "unconfirmed_fields": unconfirmed_fields,
            "unconfirmed_sensitive_fields": unconfirmed_sensitive_fields,
        }

    def get_form_debug_view(self, session_id: str) -> dict[str, Any]:
        session_state = self.sessions.get(session_id, {})
        form_state = session_state.get("fields", {})
        metadata = session_state.get("metadata", {})
        missing_required_fields = self._missing_required_fields(form_state)
        unconfirmed_fields = self._unconfirmed_fields(form_state, metadata)
        unconfirmed_sensitive_fields = self._unconfirmed_sensitive_fields(form_state, metadata)
        completion_percentage = self._completion_percentage(form_state)

        return {
            "filled_fields": dict(form_state),
            "missing_required_fields": missing_required_fields,
            "unconfirmed_fields": unconfirmed_fields,
            "unconfirmed_sensitive_fields": unconfirmed_sensitive_fields,
            "completion_percentage": completion_percentage,
            "latest_sensitive_fields": list(
                session_state.get("latest_sensitive_fields", [])
            ),
            "current_field": session_state.get("current_field"),
            "is_basic_registration_complete": self._is_registration_complete(form_state, metadata),
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

    def _normalize_location_to_arabic(self, field_id: str, value: str, language: str) -> str:
        """
        Normalize location and address fields to Arabic.
        """
        if not value:
            return ""
            
        text = value.strip().lower()
        
        # 1. Check direct mapping
        if text in self.LOCATION_MAP:
            return self.LOCATION_MAP[text]
            
        # 2. Handle address words if it's an address field
        if field_id in {"address", "guardian_address", "guardian_work_address"}:
            words = text.split()
            normalized_words = []
            for word in words:
                # Check mapping for each word
                clean_word = word.strip(".,")
                if clean_word in self.ADDRESS_WORDS_MAP:
                    normalized_words.append(self.ADDRESS_WORDS_MAP[clean_word])
                elif clean_word in self.LOCATION_MAP:
                    normalized_words.append(self.LOCATION_MAP[clean_word])
                else:
                    normalized_words.append(word)
            
            res = " ".join(normalized_words)
            # If it's mostly English and not Arabic, we might need LLM refinement
            has_arabic = bool(re.search(r"[\u0600-\u06FF]", res))
            if not has_arabic and ENABLE_LLM_REGISTRATION_EXTRACTION:
                llm_res = self.llm_client.correct_registration_value(
                    field_id=field_id,
                    raw_text=value,
                    language=language,
                )
                if llm_res and llm_res.get("candidate_value"):
                    return llm_res["candidate_value"]
            return res
            
        # 3. If no mapping found and LLM is enabled, try LLM for unknown location
        if ENABLE_LLM_REGISTRATION_EXTRACTION:
            llm_res = self.llm_client.correct_registration_value(
                field_id=field_id,
                raw_text=value,
                language=language,
            )
            if llm_res and llm_res.get("candidate_value"):
                return llm_res["candidate_value"]
                
        # 4. Fallback to original if no better option
        return value

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
        
        # Strictly follow the current_field only if in guided flow
        if current_field and not correction_requested:
            self._extract_current_field_answer(
                field_name=current_field,
                processed_text=processed_text,
                updates=updates,
                form_state=form_state,
            )
            return updates

        # Broad extraction is ONLY for corrections or if not in a specific guided field
        guardian_context = self._has_guardian_context(text_lower)
        self._extract_protected_entities(processed_text.entities, updates, guardian_context)
        self._extract_loose_sensitive_values(raw_text, updates, guardian_context)
        self._extract_relationship(text_lower, updates)
        self._extract_names(raw_text, normalized_text, updates, guardian_context)
        self._extract_address(raw_text, normalized_text, updates)
        self._extract_school(raw_text, normalized_text, updates)
        self._extract_certificate(text_lower, updates)
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

        if field_name == "full_name_ar":
            name_pair = self._generate_name_pair(normalized_text, "en" if bool(re.search(r"[A-Za-z]", normalized_text)) else "ar")
            if name_pair:
                updates.update(name_pair)
            else:
                cleaned = self._clean_answer_fallback(normalized_text)
                if cleaned:
                    updates[field_name] = cleaned
            return

        if field_name == "full_name_en":
            # If we are here, it means full_name_ar didn't fill it or we are specifically asking for it.
            cleaned = self._clean_answer_fallback(raw_text)
            if cleaned:
                updates[field_name] = cleaned
            return

        if field_name == "guardian_name":
            cleaned = self._clean_answer_fallback(raw_text)
            if cleaned:
                updates[field_name] = cleaned
            return

        if field_name in {
            "student_mobile_no", "guardian_mobile_no", "mobile_no_2",
            "home_phone", "guardian_work_no", "guardian_home_phone",
            "id_or_passport", "guardian_id_or_passport", "seat_number"
        }:
            normalized_digits = self._normalize_digits(raw_text)
            digits = re.sub(r"\D", "", normalized_digits)
            if digits:
                updates[field_name] = digits
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

        if field_name == "sector":
            sector_updates: dict[str, Any] = {}
            self._extract_sector(normalized_text.lower(), sector_updates)

            if "sector" in sector_updates:
                updates[field_name] = sector_updates["sector"]
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
            "guardian_profession", "guardian_employer", "guardian_nationality",
            "guardian_city", "guardian_district", "guardian_work_address", "guardian_address"
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
            r"إسمي هو",
            r"إسمي",
            r"الاسم هو",
            r"الاسم",
            r"انا اسمي",
            r"أنا اسمي",
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

    def _is_name_intake_field(self, field_id: str) -> bool:
        return field_id == "full_name_ar"

    def _extract_name_only_from_phrase(self, text: str) -> str:
        """
        Remove common prefixes and noise words from name intake phrases.
        """
        text = text.strip(" .,،!؟?")
        
        noise_patterns = [
            # English Phrases
            r"\bmy full name in (?:arabic|english) is\b",
            r"\bmy full name is\b",
            r"\bmy name is\b",
            r"\bfull name is\b",
            r"\bname is\b",
            r"\bit is\b",
            r"\bi am\b",
            
            # Arabic Phrases
            r"اسمي باللغة (?:العربية|الإنجليزية)",
            r"اسمي الكامل",
            r"انا اسمي",
            r"أنا اسمي",
            r"إسمي هو",
            r"إسمي",
            r"اسمي هو",
            r"اسمي",
            r"إسمى هو",
            r"إسمى",
            r"اسمى هو",
            r"اسمى",
            r"الاسم هو",
            r"اسم هو",
            r"انا من",
            r"انا",
            r"أنا",
            r"\bهو\b",
            r"\bهي\b",
            r"\bهوا\b",
            r"\bهيا\b",
            r"\bإذ\b",
            r"\bاذ\b",

            
            # Transcription noise (Phonetic English-to-Arabic errors)
            r"ماي فول نيم ان (?:اربيك|انجلش)",
            r"ماي فول نيم",
            r"ماي فول ني",
            r"ماي نيم",
            r"من (?:اربيك|أربيك)",
            r"ان (?:اربيك|إن اربيك)",
            r"اربك",
            r"اربيك",
            r"انجلش",
            r"إنجلش",
            r"إذ",
            r"اذ",
            r"از",
            r"إز",
            r"فقط",
            r"only",
        ]
        
        cleaned = text
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE).strip()
            
        return re.sub(r"\s+", " ", cleaned).strip(" .,،!؟?")

    def _normalize_ar_for_match(self, text: str) -> str:
        if not text: return ""
        text = re.sub(r"[\u064B-\u065F]", "", text) # Remove diacritics
        text = text.replace("\u0640", "") # Remove tatweel
        text = re.sub(r"[أإآٱ]", "ا", text)
        text = text.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", "", text).strip() # Remove spaces for matching

    def _normalize_en_for_match(self, text: str) -> str:
        if not text: return ""
        text = text.lower().replace("-", " ").replace("_", " ")
        text = re.sub(r"[^a-z\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _phonetic_transliterate(self, text: str, to_language: str) -> str:
        """
        Simple phonetic fallback rules for unknown names.
        """
        if to_language == "ar":
            # EN -> AR
            rules = [
                (r"sh", "ش"), (r"ch", "تش"), (r"kh", "خ"), (r"gh", "غ"),
                (r"ph", "ف"), (r"th", "ث"), (r"ee", "ي"), (r"oo", "و"),
                (r"ou", "و"), (r"ea", "ي"), (r"ai", "اي"), (r"ay", "اي"),
                (r"b", "ب"), (r"t", "ت"), (r"g", "ج"), (r"d", "د"),
                (r"r", "ر"), (r"z", "ز"), (r"s", "س"), (r"f", "ف"),
                (r"k", "ك"), (r"q", "ق"), (r"l", "ل"), (r"m", "م"),
                (r"n", "ن"), (r"h", "ه"), (r"w", "و"), (r"y", "ي"),
                (r"j", "ج"), (r"p", "ب"), (r"v", "ف"), (r"x", "كس"),
                (r"c", "ك"), (r"a", "ا"), (r"e", "ي"), (r"i", "ي"),
                (r"o", "و"), (r"u", "و"),
            ]
            res = text.lower()
            for pattern, rep in rules:
                res = re.sub(pattern, rep, res)
            return res
        else:
            # AR -> EN
            rules = [
                ("ش", "sh"), ("خ", "kh"), ("غ", "gh"), ("ف", "f"),
                ("ق", "q"), ("ك", "k"), ("ج", "j"), ("ت", "t"),
                ("د", "d"), ("ب", "b"), ("م", "m"), ("ن", "n"),
                ("ه", "h"), ("ز", "z"), ("س", "s"), ("ر", "r"),
                ("ل", "l"), ("ع", "a"), ("ح", "h"), ("ط", "t"),
                ("ص", "s"), ("ض", "d"), ("و", "w"), ("ي", "y"),
                ("ا", "a"), ("أ", "a"), ("إ", "a"), ("آ", "a"),
                ("ئ", "y"), ("ؤ", "w"), ("ة", "h"), ("ث", "th"),
                ("ذ", "th"),
            ]
            res = text
            for ar, en in rules:
                res = res.replace(ar, en)
            return res.capitalize()

    def _generate_name_pair(self, text: str, language: str) -> dict[str, str]:
        """
        Multi-layered name intake logic.
        """
        cleaned_name = self._extract_name_only_from_phrase(text)
        if not cleaned_name:
            return {}
            
        parts = cleaned_name.split()
        if len(parts) < 2:
            return {}
            
        names_en = []
        names_ar = []
        
        # Layer 2 & 3: Lexicon & Fuzzy/Phonetic
        idx = 0
        while idx < len(parts):
            found = False
            # Try compound matching first (max 3 words)
            for window in range(min(3, len(parts) - idx), 0, -1):
                phrase = " ".join(parts[idx:idx+window])
                
                # Try exact lookup
                en_norm = self._normalize_en_for_match(phrase)
                ar_norm = self._normalize_ar_for_match(phrase)
                
                pair = self.name_lookup_en.get(en_norm) or self.name_lookup_ar.get(ar_norm)
                
                if not pair and idx == 0: # Try emergency map
                    pair = self.NAME_CORRECTION_MAP.get(phrase.lower())
                
                if pair:
                    names_en.append(pair[0])
                    names_ar.append(pair[1])
                    idx += window
                    found = True
                    break
                    
                # Try fuzzy matching if single word and no exact match
                if window == 1:
                    # Fuzzy match EN
                    en_matches = difflib.get_close_matches(en_norm, self.name_lookup_en.keys(), n=1, cutoff=0.9)
                    if en_matches:
                        pair = self.name_lookup_en[en_matches[0]]
                        names_en.append(pair[0])
                        names_ar.append(pair[1])
                        idx += 1
                        found = True
                        break
                    
                    # Fuzzy match AR
                    ar_matches = difflib.get_close_matches(ar_norm, self.name_lookup_ar.keys(), n=1, cutoff=0.9)
                    if ar_matches:
                        pair = self.name_lookup_ar[ar_matches[0]]
                        names_en.append(pair[0])
                        names_ar.append(pair[1])
                        idx += 1
                        found = True
                        break
            
            if not found:
                # Layer 3: Phonetic Fallback
                part = parts[idx]
                is_arabic = bool(re.search(r"[\u0600-\u06FF]", part))
                if is_arabic:
                    names_ar.append(part)
                    names_en.append(self._phonetic_transliterate(part, "en"))
                else:
                    names_en.append(part.capitalize())
                    names_ar.append(self._phonetic_transliterate(part, "ar"))
                idx += 1

        # Layer 4: LLM Fallback (if any part was not in lexicon)
        # Check if all parts were found in lexicon by checking sources if we kept them, 
        # but simpler: if we used phonetic fallback, try LLM.
        # Actually, let's always try LLM if ENABLE_LLM_REGISTRATION_EXTRACTION is true 
        # and we have unknown parts.
        
        full_ar = " ".join(names_ar)
        full_en = " ".join(names_en)
        
        # Validation
        if len(names_ar) < 2:
            return {}

        if ENABLE_LLM_REGISTRATION_EXTRACTION:
            # Check if name looks "good enough" or needs LLM refinement
            # If phonetic fallback was used, names might be slightly off.
            # For now, let's trust the lexicon + phonetic but allow LLM to improve.
            llm_res = self.llm_client.extract_name_pair(text=text, language=language)
            if llm_res and llm_res.get("name_ar") and llm_res.get("name_en"):
                # Validate LLM result
                ar_val, ar_ok = self._validate_arabic_name(llm_res["name_ar"])
                en_val, en_ok = self._validate_english_name(llm_res["name_en"])
                if ar_ok and en_ok:
                    return {
                        "full_name_ar": ar_val,
                        "full_name_en": en_val,
                    }

        return {
            "full_name_ar": full_ar,
            "full_name_en": full_en,
        }

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
                if guardian_context:
                    updates["guardian_name"] = name
                else:
                    # In broad extraction, try to generate pair
                    name_pair = self._generate_name_pair(name, "en")
                    if name_pair:
                        updates.update(name_pair)
                    else:
                        updates["full_name_en"] = name

        arabic_match = re.search(
            r"(?:انا اسمي|اسمي)\s+(.+?)(?=\s+و(?:رقمي|مجموعي|البريد|ايميلي|مدرستي|انا|اسمي)|\s+و|\s*,|$)",
            normalized_text,
        )

        if arabic_match:
            name = self._clean_value(arabic_match.group(1))

            if name and not is_bad_name(name):
                if guardian_context:
                    updates["guardian_name"] = name
                else:
                    # In broad extraction, try to generate pair
                    name_pair = self._generate_name_pair(name, "ar")
                    if name_pair:
                        updates.update(name_pair)
                    else:
                        updates["full_name_ar"] = name

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
        if "college_preference_1" in updates:
            return

        faculty = entities.get("faculty")

        if not faculty:
            return

        faculty_id = faculty.get("id")

        if not faculty_id:
            return

        if not form_state.get("college_preference_1"):
            updates["college_preference_1"] = faculty_id

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

        if validation_type == "mobile" or field_name in {"student_mobile_no", "guardian_mobile_no", "mobile_no_2"}:
            return self._validate_mobile(value)

        if validation_type == "phone" or field_name in {"home_phone", "guardian_home_phone", "guardian_work_no"}:
            return self._validate_phone_generic(value)

        if validation_type == "email" or field_name in {"email_address", "guardian_email_address"}:
            return self._validate_email(value)

        if validation_type == "id_or_passport" or field_name in {"id_or_passport", "guardian_id_or_passport"}:
            return self._validate_id_or_passport(value)

        if validation_type == "percentage":
            return self._validate_percentage(value)

        if validation_type == "total_marks" or field_name == "total_marks":
            return self._validate_total_marks(value)

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

        if validation_type == "sector" or field_name == "sector":
            return self._validate_sector(value)

        if field_name == "guardian_profession":
            return self._validate_guardian_profession(value)

        if field_name == "guardian_nationality":
            return self._validate_guardian_nationality(value)

        if field_name in self.LOCATION_FIELDS:
            return self._validate_location(field_name, value)

        return value, True

    def _validate_location(self, field_name: str, value: Any) -> tuple[str | None, bool]:
        """
        Validate and normalize location fields to Arabic.
        """
        # We don't have a specific language here, so we'll use a default or try to detect
        # But _normalize_location_to_arabic will handle both anyway.
        # Since we don't pass the session language here, we might need it.
        # Actually, let's just assume Arabic target.
        arabic_value = self._normalize_location_to_arabic(field_name, str(value), "ar")
        
        # Validation: Must contain Arabic letters or be an address with numbers
        is_valid = bool(re.search(r"[\u0600-\u06FF]", arabic_value)) or \
                   (field_name in {"address", "guardian_address", "guardian_work_address"} and bool(re.search(r"\d", arabic_value)))
                   
        return arabic_value if is_valid else None, is_valid

    def _validate_phone_generic(self, value: Any) -> tuple[str | None, bool]:
        digits = re.sub(r"\D", "", str(value))
        # Reasonable length for phone numbers (e.g. 7 to 11 digits)
        is_valid = 7 <= len(digits) <= 12
        return digits if is_valid else None, is_valid

    def _validate_total_marks(self, value: Any) -> tuple[float | None, bool]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None, False

        is_valid = number > 0
        return number if is_valid else None, is_valid

    def _validate_sector(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip().lower()
        
        # Normalize: science, math, literary
        mapping = {
            "science": ["science", "علمي علوم", "علوم"],
            "math": ["math", "علمي رياضة", "رياضة"],
            "literary": ["literary", "أدبي", "ادبي"]
        }
        
        for canonical, aliases in mapping.items():
            if text == canonical or any(alias in text for alias in aliases):
                return canonical, True
                
        return None, False

    def _extract_sector(self, text_lower: str, updates: dict[str, Any]) -> None:
        patterns = [
            (r"علمي علوم|علوم|\bscience\b", "science"),
            (r"علمي رياضة|رياضة|\bmath\b", "math"),
            (r"أدبي|ادبي|\bliterary\b", "literary")
        ]
        
        for pattern, sector in patterns:
            if re.search(pattern, text_lower):
                updates["sector"] = sector
                return

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
        # Clean repeated spaces
        name = re.sub(r"\s+", " ", name)
        # Arabic letters and spaces
        is_arabic = re.fullmatch(r"[\u0600-\u06FF\s]+", name) is not None
        # Reject English letters
        has_english = bool(re.search(r"[A-Za-z]", name))
        # At least 2 names
        parts = name.split()
        has_two_names = len(parts) >= 2
        # No numbers
        no_numbers = not any(c.isdigit() for c in name)
        
        # No noise words
        noise_words = {"ماي", "فول", "نيم", "نيمز", "اربيك", "انجلش", "اسمي", "الاسم", "هو", "انا", "فقط"}
        has_noise = any(part in noise_words for part in parts)

        is_valid = is_arabic and not has_english and has_two_names and no_numbers and not has_noise
        return name if is_valid else None, is_valid

    def _validate_english_name(self, value: Any) -> tuple[str | None, bool]:
        name = str(value).strip()
        # Clean repeated spaces
        name = re.sub(r"\s+", " ", name)
        # English letters and spaces
        is_english = re.fullmatch(r"[A-Za-z\s]+", name) is not None
        # Reject Arabic letters
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", name))
        # At least 2 names
        parts = name.split()
        has_two_names = len(parts) >= 2
        # No numbers
        no_numbers = not any(c.isdigit() for c in name)
        
        # No noise words
        noise_words = {"my", "name", "full", "arabic", "english", "is", "i", "am", "only"}
        has_noise = any(part.lower() in noise_words for part in parts)

        is_valid = is_english and not has_arabic and has_two_names and no_numbers and not has_noise
        return name if is_valid else None, is_valid

    def _validate_guardian_profession(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip()
        text_lower = text.lower()
        
        # Reject relationship words
        if self._has_guardian_context(text_lower):
            return None, False
            
        # Minimum meaningful length
        is_valid = len(text) >= 2 and not any(c.isdigit() for c in text)
        return text if is_valid else None, is_valid

    def _validate_guardian_nationality(self, value: Any) -> tuple[str | None, bool]:
        text = str(value).strip()
        text_lower = text.lower()
        
        # Reject relationship words or job titles
        if self._has_guardian_context(text_lower) or self._has_profession_context(text_lower):
            return None, False
            
        is_valid = len(text) >= 2 and not any(c.isdigit() for c in text)
        return text if is_valid else None, is_valid

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
                return "الرقم القومي يجب أن يكون 14 رقمًا، أو أدخل رقم جواز سفر صحيح."
            return "National ID must be 14 digits, or enter a valid passport number."
            
        if field_name in {"student_mobile_no", "guardian_mobile_no"}:
            if language == "ar":
                return "لم أسمع رقم موبايل صحيح. من فضلك قل 11 رقم يبدأ بـ 010 أو 011 أو 012 أو 015."
            return "I did not hear a valid mobile number. Please say 11 digits starting with 010, 011, 012, or 015."
            
        if field_name in {"email_address", "guardian_email_address"}:
            if language == "ar":
                return "البريد الإلكتروني غير كامل أو غير صحيح. من فضلك قل البريد مرة أخرى مثل name at gmail dot com."
            return "The email address is incomplete or incorrect. Please say it again like: name at gmail dot com."
            
        if field_name == "date_of_birth":
            if language == "ar":
                return "تاريخ الميلاد غير واضح. من فضلك قل التاريخ مثل 15/08/2005."
            return "Date of birth is unclear. Please say it like: 15/08/2005."

        if field_name in {"percentage", "science_score", "math_score", "literary_score"}:
            if language == "ar":
                return "النسبة يجب أن تكون رقمًا من 0 إلى 100."
            return "Percentage must be a number from 0 to 100."

        if field_name == "full_name_ar":
            if language == "ar":
                return "من فضلك قل أو اكتب اسمك الكامل باللغة العربية."
            return "Please say or type your full name in Arabic."

        if field_name == "full_name_en":
            if language == "ar":
                return "من فضلك قل اسمك الكامل باللغة الإنجليزية، أو اكتبه بحروف إنجليزية."
            return "Please say your full name in English, or type it using English letters."

        if field_name == "guardian_profession":
            if language == "ar":
                return "أحتاج وظيفة ولي الأمر، مثل مهندس أو طبيب أو مدرس."
            return "I need the guardian's profession, such as engineer, doctor, or teacher."

        if field_name == "guardian_nationality":
            if language == "ar":
                return "أحتاج جنسية ولي الأمر، مثل مصري."
            return "I need the guardian's nationality, such as Egyptian."
            
        return self._question_for_field(field_name, language)

    def _has_correction_words(self, text: str) -> bool:
        text_lower = text.lower()
        normalized = self._normalize_preference_text(text_lower)
        for word in self.CORRECTION_WORDS:
            norm_word = self._normalize_preference_text(word)
            if f" {norm_word} " in f" {normalized} " or normalized == norm_word or normalized.startswith(f"{norm_word} ") or normalized.endswith(f" {norm_word}"):
                return True
        return False

    def _has_guardian_context(self, text_lower: str) -> bool:
        normalized = self._normalize_preference_text(text_lower)
        for word in self.GUARDIAN_WORDS:
            norm_word = self._normalize_preference_text(word)
            if f" {norm_word} " in f" {normalized} " or normalized == norm_word:
                return True
        return False

    def _has_profession_context(self, text_lower: str) -> bool:
        normalized = self._normalize_preference_text(text_lower)
        for word in self.PROFESSION_WORDS:
            norm_word = self._normalize_preference_text(word)
            if f" {norm_word} " in f" {normalized} " or normalized == norm_word:
                return True
        return False

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
            
            # Clear the rejected fields
            for field_name in latest_sensitive_fields:
                if field_name in session_state["fields"]:
                    del session_state["fields"][field_name]
                if field_name in session_state["metadata"]:
                    del session_state["metadata"][field_name]
                
                # Special case for name pair: clear both
                if field_name == "full_name_ar":
                    if "full_name_en" in session_state["fields"]:
                        del session_state["fields"]["full_name_en"]
                    if "full_name_en" in session_state["metadata"]:
                        del session_state["metadata"]["full_name_en"]
            
            # Re-sync current field to the first missing field (which should be the one we just cleared)
            session_state["current_field"] = None
            current_field = self._sync_current_field(session_state, language)
            
            session_state["latest_sensitive_fields"] = []
            
            if language == "ar":
                next_question = "من فضلك أعد إدخال هذه المعلومة بشكل صحيح."
            else:
                next_question = "Please provide the information again."

            # If we know the original question, maybe use it? 
            # Or just let _retry_question handle it?
            if current_field:
                next_question = self._question_for_field(current_field, language)

            return {
                "needs_confirmation": False,
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

        # Every field now requires confirmation in guided flow
        return not metadata.get(field_name, {}).get("confirmed", False)

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
        session_state: dict[str, Any],
        language: str,
    ) -> str:
        if not latest_sensitive_fields:
            return "Please confirm if this is correct."

        field_name = latest_sensitive_fields[0]
        field_val = session_state.get("fields", {}).get(field_name)
        
        # Special case for name pair
        if field_name == "full_name_ar" and "full_name_en" in session_state.get("fields", {}):
            full_name_ar = session_state["fields"].get("full_name_ar")
            full_name_en = session_state["fields"].get("full_name_en")
            if language == "ar":
                return f"سجلت اسمك كالتالي: العربي: {full_name_ar}، الإنجليزي: {full_name_en}. هل هذا صحيح؟ قل نعم للتأكيد أو لا للإعادة."
            else:
                return f"I recorded your name as: Arabic: {full_name_ar}, English: {full_name_en}. Is this correct? Say yes to confirm or no to repeat."

        # Get label for other fields
        field_def = next((f for f in self.field_definitions if f["field_id"] == field_name), {})
        label = field_def.get("label_ar" if language == "ar" else "label_en", field_name)

        if language == "ar":
            return f"سجلت {label} كالتالي: {field_val}. هل هذا صحيح؟ قل نعم للتأكيد أو لا للإعادة."
        else:
            return f"I recorded {label} as: {field_val}. Is this correct? Say yes to confirm or no to repeat."

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
            missing_fields.append("full_name_ar")

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

    def _unconfirmed_fields(
        self,
        form_state: dict[str, Any],
        metadata: dict[str, Any],
    ) -> list[str]:
        unconfirmed: list[str] = []

        # Check all filled fields in the order they appear in field_order
        for field_name in self.field_order:
            if field_name not in form_state:
                continue

            field_metadata = metadata.get(field_name, {})

            if not field_metadata.get("confirmed", False):
                unconfirmed.append(field_name)

        return unconfirmed

    def _unconfirmed_sensitive_fields(
        self,
        form_state: dict[str, Any],
        metadata: dict[str, Any],
    ) -> list[str]:
        # For backward compatibility, return all unconfirmed fields for now if simple, 
        # or specifically the ones marked sensitive.
        # The prompt says: it is okay to return both unconfirmed_fields and unconfirmed_sensitive_fields.
        unconfirmed = self._unconfirmed_fields(form_state, metadata)
        return [f for f in unconfirmed if f in self.sensitive_fields]

    def _is_registration_complete(self, form_state: dict[str, Any], metadata: dict[str, Any]) -> bool:
        missing = self._missing_required_fields(form_state)
        if missing:
            return False
            
        # Check if all required fields are confirmed
        unconfirmed = self._unconfirmed_fields(form_state, metadata)
        required_set = set(self.required_core_fields) | set(self.REQUIRED_NAME_FIELDS)
        
        for field in unconfirmed:
            if field in required_set:
                return False
                
        return True

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
