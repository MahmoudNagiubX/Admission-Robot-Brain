"""
Main AI Brain module.

Current complete modules:
1. Text Intelligence Layer
2. Session Memory
3. FAQ Routing

Next modules:
- Knowledge base / RAG
- Registration engine
- TTS engine
"""

from config import SUPPORTED_LANGUAGES, SUPPORTED_MODES
from faq_router import FAQRouter
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
        self.faq_router = FAQRouter()

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

        faq_match = self.faq_router.find_best_match(
            processed_text=processed_text,
            language=brain_input.language,
        )

        if faq_match["matched"]:
            return BrainOutput(
                mode=brain_input.mode,
                answer_text=faq_match["answer_text"],
                speech_text=faq_match["speech_text"],
                confidence=faq_match["confidence"],
                current_topic=session.current_topic,
                audio_path=None,
                form_updates={},
                route_taken=[
                    "input_received",
                    "basic_validation_done",
                    *processed_text.route_notes,
                    "session_memory_updated",
                    "faq_router_checked",
                    "faq_match_found",
                    f"faq_id:{faq_match['faq_id']}",
                    *faq_match["reasons"],
                ],
            )

        return BrainOutput(
            mode=brain_input.mode,
            answer_text=faq_match["answer_text"],
            speech_text=faq_match["speech_text"],
            confidence=faq_match["confidence"],
            current_topic=session.current_topic,
            audio_path=None,
            form_updates={},
            route_taken=[
                "input_received",
                "basic_validation_done",
                *processed_text.route_notes,
                "session_memory_updated",
                "faq_router_checked",
                "no_faq_match_found",
                "next_step_should_be_rag",
                *faq_match["reasons"],
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