"""
Main AI Brain module.

Current complete modules:
1. Text Intelligence Layer
2. Session Memory
3. FAQ Routing
4. Local Knowledge Base Search

Next modules:
- LLM answer generation from retrieved context
- Registration engine
- TTS engine
"""

from datetime import datetime
from pathlib import Path

from answer_composer import AnswerComposer
from config import ENABLE_LLM_RAG, SUPPORTED_LANGUAGES, SUPPORTED_MODES
from faq_router import FAQRouter
from knowledge_base import KnowledgeBase
from memory import MemoryManager
from models import BrainInput, BrainOutput
from registration import RegistrationEngine
from text_processor import TextProcessor


class ECUBrain:
    """
    Main class for the ECU Admission Robot AI Brain.
    """

    def __init__(self) -> None:
        self.text_processor = TextProcessor()
        self.memory_manager = MemoryManager(max_turns=3)
        self.faq_router = FAQRouter()
        self.knowledge_base = KnowledgeBase()
        self.registration_engine = RegistrationEngine()
        self.answer_composer = AnswerComposer()

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

        if brain_input.mode == "registration":
            registration_result = self.registration_engine.process(
                session_id=brain_input.session_id,
                processed_text=processed_text,
                language=brain_input.language,
            )
            next_question = registration_result["next_question"]
            is_basic_registration_complete = not registration_result[
                "missing_required_fields"
            ]
            answer_text = next_question or self._registration_complete_text(
                brain_input.language
            )

            if is_basic_registration_complete:
                answer_text = self.registration_engine.get_review_summary(
                    session_id=brain_input.session_id,
                    language=brain_input.language,
                )

            return BrainOutput(
                mode=brain_input.mode,
                answer_text=answer_text,
                speech_text=answer_text,
                confidence=1.0,
                current_topic="registration",
                audio_path=None,
                form_updates=registration_result["form_updates"],
                route_taken=[
                    "input_received",
                    "basic_validation_done",
                    *processed_text.route_notes,
                    *registration_result["route_notes"],
                    "faq_and_knowledge_base_skipped_for_registration",
                ],
                next_question=next_question,
                needs_confirmation=registration_result["needs_confirmation"],
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

        knowledge_match = self.knowledge_base.search(
            processed_text=processed_text,
            language=brain_input.language,
        )

        if knowledge_match["matched"]:
            answer_result = {
                "answer_text": knowledge_match["answer_text"],
                "speech_text": knowledge_match["speech_text"],
                "confidence": knowledge_match["confidence"],
                "route_notes": [],
            }

            if ENABLE_LLM_RAG:
                answer_result = self.answer_composer.compose_from_kb(
                    question=processed_text.raw_text,
                    kb_result=knowledge_match,
                    language=brain_input.language,
                )

            return BrainOutput(
                mode=brain_input.mode,
                answer_text=answer_result["answer_text"],
                speech_text=answer_result["speech_text"],
                confidence=answer_result["confidence"],
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
                    "knowledge_base_checked",
                    "knowledge_base_match_found",
                    f"section_id:{knowledge_match['section_id']}",
                    *knowledge_match["reasons"],
                    *answer_result["route_notes"],
                ],
            )

        self._log_unanswered_query(
            session_id=brain_input.session_id,
            language=brain_input.language,
            raw_text=brain_input.text,
            reason="no_faq_or_knowledge_base_source",
        )

        return BrainOutput(
            mode=brain_input.mode,
            answer_text=knowledge_match["answer_text"],
            speech_text=knowledge_match["speech_text"],
            confidence=knowledge_match["confidence"],
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
                "knowledge_base_checked",
                "no_knowledge_base_match_found",
                "safe_fallback_returned",
                "no_source_logged",
                *knowledge_match["reasons"],
            ],
            )

    def reset_session(self, session_id: str) -> None:
        """
        Reset one user session.
        """

        self.memory_manager.reset_session(session_id)

    def _registration_complete_text(self, language: str) -> str:
        if language == "ar":
            return "تم إدخال البيانات الأساسية. من فضلك راجع البيانات على الشاشة قبل الإرسال النهائي."

        return "Basic registration data is complete. Please review the information on screen before final submission."

    def _log_unanswered_query(
        self,
        session_id: str,
        language: str,
        raw_text: str,
        reason: str,
    ) -> None:
        logs_folder = Path("logs")
        logs_folder.mkdir(exist_ok=True)
        log_path = logs_folder / "unanswered_queries.log"
        timestamp = datetime.now().isoformat(timespec="seconds")
        safe_text = raw_text.replace("\n", " ").replace("|", "/")
        log_line = f"{timestamp} | {session_id} | {language} | {safe_text} | {reason}\n"

        with open(log_path, "a", encoding="utf-8") as file:
            file.write(log_line)

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
