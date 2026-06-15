"""
Main AI Brain module.

This file controls the main flow:
- validate input
- prepare text
- route to the correct brain logic
- return structured output

For Phase 1 / Step 2, it connects the TextProcessor
and still returns a placeholder response.
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
        Process one user message and return a structured brain output.
        """

        self._validate_input(brain_input)

        processed_text = self.text_processor.process(
            raw_text=brain_input.text,
            language=brain_input.language,
        )

        return BrainOutput(
            mode=brain_input.mode,
            answer_text=(
                "Text processor is connected successfully. "
                f"I received: {processed_text.corrected_text}"
            ),
            speech_text=(
                "Text processor is connected successfully. "
                "Next step will be entity detection."
            ),
            confidence=1.0,
            current_topic=None,
            audio_path=None,
            form_updates={},
            route_taken=[
                "input_received",
                "basic_validation_done",
                *processed_text.route_notes,
                "placeholder_response_returned",
            ],
        )

    def _validate_input(self, brain_input: BrainInput) -> None:
        """
        Validate the basic input before processing.
        """

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