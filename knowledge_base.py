# Loads faculty JSON files and searches them.
"""
Local Knowledge Base Search for Admission Robot AI Brain.

This module searches the verified JSON files prepared by the data team.

Important:
- This module does not use an LLM.
- It does not guess.
- It only answers from local JSON knowledge sections.
- If no useful section is found, it returns a safe no-match result.

Expected data folder:
data/faculties/*.json
"""

import json
import re
from pathlib import Path
from typing import Any

from config import RAG_MIN_CONFIDENCE
from data_validator import KnowledgeBaseValidator
from models import ProcessedText


class KnowledgeBase:
    """
    Loads and searches local faculty JSON files.
    """

    def __init__(self, faculties_folder: str = "data/faculties") -> None:
        self.faculties_folder = Path(faculties_folder)
        self.validator = KnowledgeBaseValidator()
        self.validation_results: list[dict[str, Any]] = []
        self.sections = self._load_all_sections()

    def search(
        self,
        processed_text: ProcessedText,
        language: str,
    ) -> dict[str, Any]:
        """
        Search local knowledge sections and return best matching answer.
        """

        if not self.sections:
            return self._no_match(language, reason="no_knowledge_sections_loaded")

        query = processed_text.search_query
        query_tokens = self._tokenize(query)

        faculty = processed_text.entities.get("faculty")
        intent = processed_text.entities.get("intent")

        detected_faculty_id = faculty.get("id") if faculty else None
        detected_intent_id = intent.get("id") if intent else None

        best_result: dict[str, Any] | None = None

        for section in self.sections:
            score, reasons = self._score_section(
                section=section,
                query_tokens=query_tokens,
                detected_faculty_id=detected_faculty_id,
                detected_intent_id=detected_intent_id,
                language=language,
            )

            if best_result is None or score > best_result["confidence"]:
                best_result = {
                    "matched": score >= RAG_MIN_CONFIDENCE,
                    "confidence": round(score, 3),
                    "section_id": section.get("section_id"),
                    "section_type": section.get("section_type"),
                    "faculty_id": section.get("faculty_id"),
                    "title": self._get_language_value(section.get("title", {}), language),
                    "answer_text": self._build_answer(section, language),
                    "speech_text": self._build_speech(section, language),
                    "source_url": section.get("source_url"),
                    "reasons": reasons,
                    "raw_section": section,
                }

        if best_result is None:
            return self._no_match(language, reason="no_best_result")

        if not best_result["matched"]:
            return self._no_match(
                language=language,
                reason="best_score_below_threshold",
                best_attempt=best_result,
            )

        return best_result

    def get_validation_report(self) -> list[dict[str, Any]]:
        """
        Return validation summaries collected while loading faculty files.
        """

        return self.validation_results

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all_sections(self) -> list[dict[str, Any]]:
        """
        Load all faculty JSON files and extract searchable RAG sections.
        """

        all_sections: list[dict[str, Any]] = []

        if not self.faculties_folder.exists():
            return all_sections

        for json_path in self.faculties_folder.glob("*.json"):
            try:
                with open(json_path, "r", encoding="utf-8") as file:
                    faculty_data = json.load(file)
            except Exception as error:
                validation_result = {
                    "file_name": json_path.name,
                    "is_valid": False,
                    "errors": [f"Could not load JSON file: {error}"],
                    "warnings": [],
                }
                self.validation_results.append(validation_result)
                self._print_validation_messages(validation_result)
                continue

            validation_result = self.validator.validate_faculty_file(
                file_path=json_path,
                data=faculty_data,
            )
            self.validation_results.append(validation_result)
            self._print_validation_messages(validation_result)

            if not validation_result["is_valid"]:
                continue

            faculty_id = (
                faculty_data.get("faculty_identity", {}).get("faculty_id")
                or faculty_data.get("faculty_id")
                or json_path.stem
            )

            all_sections.extend(
                self._extract_sections_from_faculty(
                    faculty_data=faculty_data,
                    faculty_id=faculty_id,
                    file_name=json_path.name,
                )
            )

        return all_sections

    def _print_validation_messages(self, validation_result: dict[str, Any]) -> None:
        file_name = validation_result["file_name"]

        if validation_result["errors"]:
            print(f"[KnowledgeBase Validation] Skipping invalid file: {file_name}")

            for error in validation_result["errors"]:
                print(f"  ERROR: {error}")

        if validation_result["warnings"]:
            print(f"[KnowledgeBase Validation] Warnings for {file_name}:")

            for warning in validation_result["warnings"]:
                print(f"  WARNING: {warning}")

    def _extract_sections_from_faculty(
        self,
        faculty_data: dict[str, Any],
        faculty_id: str,
        file_name: str,
    ) -> list[dict[str, Any]]:
        """
        Convert one faculty JSON file into searchable sections.

        Preferred source:
        - rag_sections

        Also supports:
        - overview fields
        - academic_structure departments/programs
        """

        sections: list[dict[str, Any]] = []

        for section in faculty_data.get("rag_sections", []):
            if not isinstance(section, dict):
                continue

            section_copy = dict(section)
            section_copy["faculty_id"] = section_copy.get("faculty_id", faculty_id)
            section_copy["source_file"] = file_name
            sections.append(section_copy)

        sections.extend(
            self._extract_overview_sections(
                faculty_data=faculty_data,
                faculty_id=faculty_id,
                file_name=file_name,
            )
        )

        sections.extend(
            self._extract_academic_structure_sections(
                faculty_data=faculty_data,
                faculty_id=faculty_id,
                file_name=file_name,
            )
        )

        return sections

    def _extract_overview_sections(
        self,
        faculty_data: dict[str, Any],
        faculty_id: str,
        file_name: str,
    ) -> list[dict[str, Any]]:
        """
        Extract overview, description, vision, and mission as searchable sections.
        """

        sections: list[dict[str, Any]] = []
        overview = faculty_data.get("overview", {})

        for key in ["welcome_summary", "description", "vision", "mission"]:
            value = overview.get(key)

            if not isinstance(value, dict):
                continue

            content = {
                "en": value.get("en"),
                "ar": value.get("ar"),
            }

            if not content.get("en") and not content.get("ar"):
                continue

            sections.append(
                {
                    "section_id": self._overview_section_id(faculty_id, key),
                    "section_type": key,
                    "faculty_id": faculty_id,
                    "title": {
                        "en": key.replace("_", " ").title(),
                        "ar": self._arabic_title_for_key(key),
                    },
                    "content": content,
                    "tags": [faculty_id, key],
                    "source_url": value.get("source_url")
                    or faculty_data.get("faculty_identity", {}).get("website_url"),
                    "source_file": file_name,
                }
            )

        return sections

    def _extract_academic_structure_sections(
        self,
        faculty_data: dict[str, Any],
        faculty_id: str,
        file_name: str,
    ) -> list[dict[str, Any]]:
        """
        Extract departments and programs as searchable sections.
        """

        sections: list[dict[str, Any]] = []
        academic_structure = faculty_data.get("academic_structure", {})

        departments = academic_structure.get("departments", [])
        programs = academic_structure.get("programs", [])

        if departments:
            sections.append(
                {
                    "section_id": f"{faculty_id}_departments",
                    "section_type": "departments",
                    "faculty_id": faculty_id,
                    "title": {
                        "en": "Departments",
                        "ar": "الأقسام",
                    },
                    "content": {
                        "en": self._list_to_sentence(departments, "en"),
                        "ar": self._list_to_sentence(departments, "ar"),
                    },
                    "tags": [faculty_id, "departments", "specializations"],
                    "source_url": faculty_data.get("faculty_identity", {}).get("website_url"),
                    "source_file": file_name,
                }
            )

        if programs:
            sections.append(
                {
                    "section_id": f"{faculty_id}_programs",
                    "section_type": "programs",
                    "faculty_id": faculty_id,
                    "title": {
                        "en": "Programs",
                        "ar": "البرامج",
                    },
                    "content": {
                        "en": self._list_to_sentence(programs, "en"),
                        "ar": self._list_to_sentence(programs, "ar"),
                    },
                    "tags": [faculty_id, "programs"],
                    "source_url": faculty_data.get("faculty_identity", {}).get("website_url"),
                    "source_file": file_name,
                }
            )

        return sections

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_section(
        self,
        section: dict[str, Any],
        query_tokens: set[str],
        detected_faculty_id: str | None,
        detected_intent_id: str | None,
        language: str,
    ) -> tuple[float, list[str]]:
        """
        Score section relevance.

        This is simple lexical scoring for now.
        Later we can replace or enhance this with embeddings/Qdrant.
        """

        reasons: list[str] = []
        score = 0.0

        section_faculty_id = section.get("faculty_id")
        section_type = section.get("section_type")

        if detected_faculty_id and section_faculty_id == detected_faculty_id:
            score += 0.25
            reasons.append("faculty_matched")

        if detected_intent_id and self._intent_matches_section_type(
            detected_intent_id,
            section_type,
            section.get("tags", []),
        ):
            score += 0.35
            reasons.append("intent_matched_section_type")

        searchable_text = self._build_searchable_text(section, language)
        section_tokens = self._tokenize(searchable_text)
        meaningful_query_tokens = self._remove_faculty_only_tokens(
            query_tokens=query_tokens,
            detected_faculty_id=detected_faculty_id,
        )

        if meaningful_query_tokens and section_tokens:
            overlap = meaningful_query_tokens.intersection(section_tokens)
            overlap_ratio = len(overlap) / max(len(meaningful_query_tokens), 1)

            if overlap:
                score += min(0.40, overlap_ratio)
                reasons.append(f"token_overlap:{len(overlap)}")

        if not reasons:
            reasons.append("no_relevance_signal")

        return min(score, 1.0), reasons

    def _intent_matches_section_type(
        self,
        intent_id: str,
        section_type: str | None,
        tags: list[str],
    ) -> bool:
        """
        Map intent names to knowledge section types.
        """

        tags_set = set(tags or [])

        intent_to_section_types = {
            "fees": {"fees", "tuition", "payment"},
            "location": {"location", "building", "navigation"},
            "departments": {"departments", "programs", "specializations", "majors"},
            "admission_requirements": {"admission", "requirements", "accepted_certificates"},
            "documents": {"documents", "required_documents", "papers"},
            "registration": {"registration", "form", "application"},
        }

        allowed_types = intent_to_section_types.get(intent_id, set())

        return section_type in allowed_types or bool(tags_set.intersection(allowed_types))

    def _build_searchable_text(self, section: dict[str, Any], language: str) -> str:
        """
        Combine title, content, tags, and type into searchable text.
        """

        title = self._get_language_value(section.get("title", {}), language)
        content = self._get_language_value(section.get("content", {}), language)
        tags = " ".join(section.get("tags", []))
        section_type = section.get("section_type", "")

        return f"{title} {content} {tags} {section_type}"

    def _tokenize(self, text: str) -> set[str]:
        """
        Simple tokenizer for Arabic/English mixed text.
        """

        text = text.lower()
        text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text)
        tokens = {
            self._normalize_token(token.strip())
            for token in text.split()
            if len(token.strip()) >= 2
        }

        stopwords = {
            "the", "is", "are", "and", "or", "of", "to", "in", "for", "what",
            "where", "how", "can", "i", "me", "my", "a", "an",
            "في", "من", "عن", "على", "الى", "إلى", "ايه", "ما", "هو", "هي",
            "عايز", "اعرف", "كام", "فين",
        }

        return tokens.difference(stopwords)

    def _normalize_token(self, token: str) -> str:
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
            token = token.replace(old, new)

        if re.fullmatch(r"ال[\u0600-\u06FF]{2,}", token):
            return token[2:]

        return token

    def _overview_section_id(self, faculty_id: str, key: str) -> str:
        if faculty_id == "engineering_and_technology" and key in {"vision", "mission"}:
            return f"engineering_{key}_001"

        return f"{faculty_id}_{key}"

    def _remove_faculty_only_tokens(
        self,
        query_tokens: set[str],
        detected_faculty_id: str | None,
    ) -> set[str]:
        """
        Keep faculty detection from becoming the whole KB relevance signal.
        """

        if not detected_faculty_id:
            return query_tokens

        faculty_only_tokens = {
            detected_faculty_id,
            *detected_faculty_id.split("_"),
            "faculty",
            "engineering",
            "technology",
            "كلية",
            "هندسة",
            "الهندسة",
            "تكنولوجيا",
        }

        return query_tokens.difference(faculty_only_tokens)

    # ------------------------------------------------------------------
    # Answer building
    # ------------------------------------------------------------------

    def _build_answer(self, section: dict[str, Any], language: str) -> str:
        """
        Build display answer from section content.
        """

        title = self._get_language_value(section.get("title", {}), language)
        content = self._get_language_value(section.get("content", {}), language)

        if not content:
            return self._fallback_answer(language)

        if title:
            return f"{title}: {content}"

        return content

    def _build_speech(self, section: dict[str, Any], language: str) -> str:
        """
        Build shorter speech answer.
        """

        content = self._get_language_value(section.get("content", {}), language)

        if not content:
            return self._fallback_answer(language)

        return content

    def _get_language_value(self, value: Any, language: str) -> str:
        """
        Return value in locked language.
        """

        if isinstance(value, dict):
            return value.get(language) or value.get("en") or value.get("ar") or ""

        if isinstance(value, str):
            return value

        return ""

    def _no_match(
        self,
        language: str,
        reason: str,
        best_attempt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Safe no-match result.
        """

        return {
            "matched": False,
            "confidence": best_attempt["confidence"] if best_attempt else 0.0,
            "section_id": None,
            "section_type": None,
            "faculty_id": None,
            "title": None,
            "answer_text": self._fallback_answer(language),
            "speech_text": self._fallback_answer(language),
            "source_url": None,
            "reasons": [reason],
            "raw_section": None,
        }

    def _fallback_answer(self, language: str) -> str:
        if language == "ar":
            return (
                "لم أجد هذه المعلومة في البيانات المؤكدة المتاحة لدي. "
                "من فضلك راجع إدارة القبول للتأكيد."
            )

        return (
            "I could not find this information in the verified data available to me. "
            "Please check with the Admission Office for confirmation."
        )

    def _arabic_title_for_key(self, key: str) -> str:
        mapping = {
            "welcome_summary": "نبذة مختصرة",
            "description": "الوصف",
            "vision": "الرؤية",
            "mission": "الرسالة",
        }

        return mapping.get(key, key)

    def _list_to_sentence(self, items: list[Any], language: str) -> str:
        """
        Convert a list of strings or dict names into a readable sentence.
        """

        names: list[str] = []

        for item in items:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name")

                if isinstance(name, dict):
                    names.append(name.get(language) or name.get("en") or name.get("ar") or "")
                elif isinstance(name, str):
                    names.append(name)

        names = [name for name in names if name]

        if not names:
            return ""

        if language == "ar":
            return "، ".join(names)

        return ", ".join(names)
