# Main decision engine: FAQ, RAG, registration, fallback.
""" Main AI Brain module.

This file will later control:
- text processing
- memory
- FAQ matching
- RAG search
- registration extraction
- TTS generation

For Phase 1 / Step 1, it only returns a safe placeholder response."""

from config import DEFAULT_MODE, SUPPORTED_LANGUAGES, SUPPORTED_MODES
from models import BrainInput, BrainOutput
class ECUBrain:
   # Main class for the ECU Admission Robot AI Brain.

    def process(self, brain_input: BrainInput) -> BrainOutput:
        """ Process one user message and return a structured brain output.
        For now, this is only a placeholder. """

        self._validate_input(brain_input)

        return BrainOutput(
            mode = brain_input.mode,
            answer_text=(
                "AI Brain skeleton is running successfully. "
                "Next step will be text processing."
            ),
            speech_text=(
                "AI Brain skeleton is running successfully. "
                "Next step will be text processing."
            ),
            confidence=1.0,
            current_topic=None,
            audio_path=None,
            form_updates={},
            route_taken=[
                "input_received",
                "basic_validation_done",
                "placeholder_response_returned",
            ],
        )

    def _validate_input(self, brain_input: BrainInput) -> None:
        # Validate the basic input before processing.

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