"""
Main AI Brain module.

Current complete modules:
1. Text Intelligence Layer
2. Session Memory

Next modules:
- FAQ routing
- Knowledge base / RAG
- Registration engine
- TTS engine
"""

from config import SUPPORTED_LANGUAGES, SUPPORTED_MODES
from memory import MemoryManager
from models import BrainInput, BrainOutput
from text_processor import TextProcessor


class ECUBrain:
    """
    Main class for the ECU Admission Robot AI Brain.
    """

    def __init__(self) -> None:
        self.text_processor = TextProcessor()
        self.memory_manager = MemoryManager(max_turns=3)

    def process(self, brain_input: BrainInput) -> BrainOutput:
        """
        Process one user message and return structured output.
        """

        self._validate_input(brain_input)

        session = self.memory_manager.get_or_create_session(
            session_id=brain_input.session_id,
            language=brain_input.language,
            mode=brain_input.mode,
        )

        processed_text = self.text_processor.process(
            raw_text=brain_input.text,
            language=brain_input.language,
        )

        processed_text = self.memory_manager.enrich_with_memory(
            session=session,
            processed_text=processed_text,
        )

        session = self.memory_manager.update_after_turn(
            session=session,
            processed_text=processed_text,
        )

        memory_debug = self.memory_manager.get_memory_debug_view(session)

        return BrainOutput(
            mode=brain_input.mode,
            answer_text=(
                "Text Intelligence Layer + Memory are running successfully.\n"
                f"Raw: {processed_text.raw_text}\n"
                f"Normalized: {processed_text.normalized_text}\n"
                f"Protected: {processed_text.protected_text}\n"
                f"Corrected: {processed_text.corrected_text}\n"
                f"Search Query: {processed_text.search_query}\n"
                f"Entities: {processed_text.entities}\n"
                f"Memory: {memory_debug}"
            ),
            speech_text=(
                "Memory system is running successfully. "
                "Next module will be FAQ routing."
            ),
            confidence=1.0,
            current_topic=session.current_topic,
            audio_path=None,
            form_updates={},
            route_taken=[
                "input_received",
                "basic_validation_done",
                *processed_text.route_notes,
                "session_memory_updated",
                "debug_response_returned",
            ],
        )

    def reset_session(self, session_id: str) -> None:
        """
        Reset one user session.
        """

        self.memory_manager.reset_session(session_id)

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