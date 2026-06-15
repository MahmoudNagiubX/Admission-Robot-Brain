"""
Main AI Brain module.

This file controls the main flow:
1. Validate input.
2. Process text using TextProcessor.
3. Return a structured output.

Current version focuses on the Text Intelligence Layer.
FAQ, RAG, registration, and TTS will be connected later.
"""

from config import SUPPORTED_LANGUAGES, SUPPORTED_MODES
from models import BrainInput, BrainOutput
from text_processor import TextProcessor


class ECUBrain:
    """
    Main class for the ECU Admission Robot AI Brain.
    """

    def __init__(self) -> None:
        self.text_processor = TextProcessor()

    def process(self, brain_input: BrainInput) -> BrainOutput:
        """
        Process one user message and return structured output.
        """

        self._validate_input(brain_input)

        processed_text = self.text_processor.process(
            raw_text=brain_input.text,
            language=brain_input.language,
        )

        return BrainOutput(
            mode=brain_input.mode,
            answer_text=(
                "Text Intelligence Layer is running successfully.\n"
                f"Raw: {processed_text.raw_text}\n"
                f"Normalized: {processed_text.normalized_text}\n"
                f"Protected: {processed_text.protected_text}\n"
                f"Corrected: {processed_text.corrected_text}\n"
                f"Search Query: {processed_text.search_query}\n"
                f"Entities: {processed_text.entities}"
            ),
            speech_text=(
                "Text intelligence layer is running successfully. "
                "Next module will be memory or FAQ routing."
            ),
            confidence=1.0,
            current_topic=self._extract_current_topic(processed_text.entities),
            audio_path=None,
            form_updates={},
            route_taken=[
                "input_received",
                "basic_validation_done",
                *processed_text.route_notes,
                "debug_response_returned",
            ],
        )

    def _validate_input(self, brain_input: BrainInput) -> None:
        if not brain_input.session_id.strip():
            raise ValueError("session_id cannot be empty.")

        if not brain_input.text.strip():
            raise ValueError("text cannot be empty.")

        if brain_input.language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {brain_input.language}. "
                f"Supported languages: {SUPPORTED_LANGUAGES}"
            )

        if brain_input.mode not in SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported mode: {brain_input.mode}. "
                f"Supported modes: {SUPPORTED_MODES}"
            )

    def _extract_current_topic(self, entities: dict) -> str | None:
        faculty = entities.get("faculty")
        intent = entities.get("intent")

        if faculty and intent:
            return f"{faculty['id']}:{intent['id']}"

        if faculty:
            return faculty["id"]

        if intent:
            return intent["id"]

        return None
