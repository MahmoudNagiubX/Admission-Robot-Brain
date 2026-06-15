"""
Validation helpers for local knowledge base JSON files.

The validator checks structure only. It does not modify data and it does not
decide answers.
"""

from pathlib import Path
from typing import Any


class KnowledgeBaseValidator:
    """
    Validate faculty JSON files before KnowledgeBase loads their sections.
    """

    def validate_faculty_file(self, file_path: Path, data: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        self._validate_top_level(data, errors)
        self._validate_faculty_identity(data, errors, warnings)
        self._validate_rag_sections(data, errors, warnings)
        self._validate_academic_structure(data, warnings)

        return {
            "file_name": file_path.name,
            "is_valid": not errors,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_top_level(self, data: dict[str, Any], errors: list[str]) -> None:
        for field_name in ["schema_version", "document_type", "faculty_identity"]:
            if field_name not in data:
                errors.append(f"Missing required top-level field: {field_name}")

        if "faculty_identity" in data and not isinstance(data["faculty_identity"], dict):
            errors.append("faculty_identity must be an object")

    def _validate_faculty_identity(
        self,
        data: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        faculty_identity = data.get("faculty_identity")

        if not isinstance(faculty_identity, dict):
            return

        faculty_id = faculty_identity.get("faculty_id")

        if not isinstance(faculty_id, str) or not faculty_id.strip():
            errors.append("faculty_identity.faculty_id must exist and be non-empty")

        if "name" not in faculty_identity:
            warnings.append("faculty_identity.name should exist")

        if not faculty_identity.get("website_url"):
            warnings.append("faculty_identity.website_url should exist")

    def _validate_rag_sections(
        self,
        data: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        rag_sections = data.get("rag_sections")

        if not isinstance(rag_sections, list):
            errors.append("rag_sections should exist and be a list")
            return

        seen_section_ids: set[str] = set()

        for index, section in enumerate(rag_sections):
            section_label = f"rag_sections[{index}]"

            if not isinstance(section, dict):
                errors.append(f"{section_label} must be an object")
                continue

            section_id = section.get("section_id")

            if not isinstance(section_id, str) or not section_id.strip():
                errors.append(f"{section_label}.section_id is required")
            elif section_id in seen_section_ids:
                errors.append(f"Duplicate section_id inside file: {section_id}")
            else:
                seen_section_ids.add(section_id)

            for field_name in ["section_type", "title", "content"]:
                if field_name not in section:
                    errors.append(f"{section_label}.{field_name} is required")

            self._validate_language_field(
                value=section.get("title"),
                field_label=f"{section_label}.title",
                errors=errors,
            )
            self._validate_language_field(
                value=section.get("content"),
                field_label=f"{section_label}.content",
                errors=errors,
            )

            if not self._has_language_text(section.get("content")):
                errors.append(f"{section_label}.content must not be empty in both languages")

            if not section.get("source_url"):
                warnings.append(f"{section_label}.source_url should exist")

            tags = section.get("tags")

            if tags is not None and not isinstance(tags, list):
                warnings.append(f"{section_label}.tags should be a list if present")

    def _validate_academic_structure(
        self,
        data: dict[str, Any],
        warnings: list[str],
    ) -> None:
        academic_structure = data.get("academic_structure")

        if academic_structure is None:
            return

        if not isinstance(academic_structure, dict):
            warnings.append("academic_structure should be an object if present")
            return

        departments = academic_structure.get("departments")
        programs = academic_structure.get("programs")

        if departments is not None and not isinstance(departments, list):
            warnings.append("academic_structure.departments should be a list if present")

        if programs is not None and not isinstance(programs, list):
            warnings.append("academic_structure.programs should be a list if present")

        if isinstance(departments, list):
            for index, department in enumerate(departments):
                if not isinstance(department, dict):
                    warnings.append(
                        f"academic_structure.departments[{index}] should be an object"
                    )
                    continue

                if not department.get("department_id") and not department.get("name"):
                    warnings.append(
                        "academic_structure.departments"
                        f"[{index}] should have department_id or name"
                    )

    def _validate_language_field(
        self,
        value: Any,
        field_label: str,
        errors: list[str],
    ) -> None:
        if not isinstance(value, dict):
            errors.append(f"{field_label} should be a dict with at least en or ar")
            return

        if "en" not in value and "ar" not in value:
            errors.append(f"{field_label} should include at least en or ar")

    def _has_language_text(self, value: Any) -> bool:
        if not isinstance(value, dict):
            return False

        for language in ["en", "ar"]:
            text = value.get(language)

            if isinstance(text, str) and text.strip():
                return True

        return False
