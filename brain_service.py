"""
Service Layer for ECU Admission AI Brain.

This module is the public integration boundary for backend teams. It keeps CLI
concerns out of service calls and returns safe JSON-serializable dictionaries.
"""

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
import uuid

from brain import ECUBrain
from config import SUPPORTED_LANGUAGES, SUPPORTED_MODES
from models import BrainInput, BrainOutput


class AdmissionBrainService:
    """
    High-level service for backend integration.

    Backend code should import this class only. It should not need ECUBrain,
    RegistrationEngine, CLI helpers, microphone code, or pygame playback.
    """

    MAX_TRANSCRIPT_CHARS = 4000
    VALID_INTERACTIONS = {"answer", "confirmation", "manual_input"}

    def __init__(self) -> None:
        self.brain = ECUBrain()
        self.session_configs: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Public session API
    # ------------------------------------------------------------------

    def create_session(self, language: str = "ar", mode: str = "qa") -> dict[str, Any]:
        language_error = self._validate_language(language)
        if language_error:
            return language_error

        mode_error = self._validate_mode(mode)
        if mode_error:
            return mode_error

        session_id = str(uuid.uuid4())
        self.session_configs[session_id] = {
            "language": language,
            "mode": mode,
        }
        return {
            "success": True,
            "session_id": session_id,
            "language": language,
            "mode": mode,
        }

    def reset_session(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        self.brain.reset_session(session_id)
        self.brain.registration_engine.reset_session(session_id)
        self.session_configs.pop(session_id, None)
        return {"success": True, "session_id": session_id, "reset": True}

    def get_session_state(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        config = dict(self.session_configs[session_id])
        registration_status = self.brain.registration_engine.get_registration_status(session_id)
        has_memory = session_id in self.brain.memory_manager.sessions
        has_registration = session_id in self.brain.registration_engine.sessions

        return self._json_ready({
            "success": True,
            "session_id": session_id,
            "language": config.get("language", "ar"),
            "mode": config.get("mode", "qa"),
            "has_memory": has_memory,
            "has_registration": has_registration,
            "registration_status": registration_status,
        })

    def set_language(self, session_id: str, language: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        language_error = self._validate_language(language)
        if language_error:
            return language_error

        self.session_configs[session_id]["language"] = language
        return {
            "success": True,
            "session_id": session_id,
            "language": language,
        }

    def set_mode(self, session_id: str, mode: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        mode_error = self._validate_mode(mode)
        if mode_error:
            return mode_error

        self.session_configs[session_id]["mode"] = mode
        return {
            "success": True,
            "session_id": session_id,
            "mode": mode,
        }

    # ------------------------------------------------------------------
    # Public processing API
    # ------------------------------------------------------------------

    def process_text(
        self,
        session_id: str,
        text: str,
        language: str | None = None,
        mode: str | None = None,
        generate_audio: bool = False,
    ) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        text_result = self._clean_transcript(text)
        if not text_result["success"]:
            return text_result
        clean_text = text_result["text"]

        config = self.session_configs[session_id]
        active_language = language if language is not None else config.get("language", "ar")
        active_mode = mode if mode is not None else config.get("mode", "qa")

        language_error = self._validate_language(active_language)
        if language_error:
            return language_error

        mode_error = self._validate_mode(active_mode)
        if mode_error:
            return mode_error

        config["language"] = active_language
        config["mode"] = active_mode

        try:
            brain_input = BrainInput(
                session_id=session_id,
                text=clean_text,
                language=active_language,
                mode=active_mode,
            )
            output: BrainOutput = self.brain.process(brain_input)
            payload = asdict(output)
            speech_text = payload.get("speech_text") or payload.get("answer_text") or ""
            audio = self._build_audio_metadata(
                session_id=session_id,
                text=speech_text,
                language=active_language,
                generate_audio=generate_audio,
            )
            payload["audio"] = audio
            payload["audio_path"] = audio["path"]
            return self._json_ready({
                "success": True,
                "session_id": session_id,
                "data": payload,
            })
        except Exception:
            return self._error(
                "INTERNAL_SERVICE_ERROR",
                "The AI Brain could not process this request safely.",
            )

    def process_voice_transcript(self, session_id: str, transcript: str) -> dict[str, Any]:
        return self.process_text(session_id, transcript)

    def process_registration_field(
        self,
        session_id: str,
        field_id: str,
        transcript: str,
        language: str = "ar",
        interaction: str = "answer",
        generate_audio: bool = False,
        question_text: str | None = None,
    ) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        language_error = self._validate_language(language)
        if language_error:
            return language_error

        if interaction not in self.VALID_INTERACTIONS:
            return self._error("INVALID_INTERACTION", "Unknown registration interaction.")

        text_result = self._clean_transcript(transcript)
        if not text_result["success"]:
            return text_result
        clean_transcript = text_result["text"]

        canonical_field_id = self._canonical_field_id(field_id)
        if canonical_field_id is None:
            return self._error("INVALID_FIELD_ID", "Unknown registration field.")

        self.session_configs[session_id]["mode"] = "registration"
        self.session_configs[session_id]["language"] = language

        try:
            processed_text = self.brain.text_processor.process(
                raw_text=clean_transcript,
                language=language,
            )
            result = self.brain.registration_engine.process_frontend_field(
                session_id=session_id,
                field_id=canonical_field_id,
                processed_text=processed_text,
                language=language,
                interaction=interaction,
            )
        except Exception:
            return self._error(
                "INTERNAL_SERVICE_ERROR",
                "The registration field could not be processed safely.",
            )

        if "error" in result:
            code = result.get("error") or "INTERNAL_SERVICE_ERROR"
            if code == "INVALID_INTERACTION":
                return self._error("INVALID_INTERACTION", "Unknown registration interaction.")
            if code == "FIELD_STATE_MISMATCH":
                return self._error(
                    "FIELD_STATE_MISMATCH",
                    "This field does not match the pending registration interaction.",
                )
            return self._error(code, result.get("message", "Registration request failed."))

        data = self._frontend_registration_data(
            session_id=session_id,
            requested_field_id=canonical_field_id,
            requested_interaction=interaction,
            result=result,
            language=language,
            generate_audio=generate_audio,
        )
        return self._json_ready({
            "success": True,
            "session_id": session_id,
            "data": data,
        })

    # ------------------------------------------------------------------
    # Public registration API
    # ------------------------------------------------------------------

    def get_registration_status(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        return self._json_ready({
            "success": True,
            "session_id": session_id,
            "data": self.brain.registration_engine.get_registration_status(session_id),
        })

    def review_registration(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        language = self.session_configs[session_id].get("language", "ar")
        review_text = self.brain.registration_engine.get_review_summary(session_id, language)
        return {
            "success": True,
            "session_id": session_id,
            "data": {
                "review_text": review_text,
                "speech_text": review_text,
            },
        }

    def export_registration(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        return self._json_ready({
            "success": True,
            "session_id": session_id,
            "data": self.brain.registration_engine.export_form_values(session_id),
        })

    def export_registration_frontend(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error

        return self._json_ready({
            "success": True,
            "session_id": session_id,
            "data": self.brain.registration_engine.export_form_values_frontend(session_id),
        })

    # ------------------------------------------------------------------
    # Backward-compatible convenience methods
    # ------------------------------------------------------------------

    def start_registration(self, session_id: str) -> dict[str, Any]:
        set_result = self.set_mode(session_id, "registration")
        if not set_result.get("success"):
            return set_result

        language = self.session_configs[session_id].get("language", "ar")
        start_cmd = "ابدأ التسجيل" if language == "ar" else "start registration"
        result = self.process_text(session_id, start_cmd)
        if result.get("success") and "data" in result:
            return result["data"]
        return result

    def submit_registration_answer(self, session_id: str, answer: str) -> dict[str, Any]:
        set_result = self.set_mode(session_id, "registration")
        if not set_result.get("success"):
            return set_result

        result = self.process_text(session_id, answer)
        if result.get("success") and "data" in result:
            return result["data"]
        return result

    def get_form_status(self, session_id: str) -> dict[str, Any]:
        result = self.get_registration_status(session_id)
        return result.get("data", result)

    def get_form_values(self, session_id: str) -> dict[str, Any]:
        result = self.export_registration(session_id)
        return result.get("data", result)

    def get_form_values_frontend(self, session_id: str) -> dict[str, Any]:
        result = self.export_registration_frontend(session_id)
        return result.get("data", result)

    def reset_registration(self, session_id: str) -> dict[str, Any]:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error
        self.brain.registration_engine.reset_session(session_id)
        return {"success": True, "session_id": session_id, "reset_registration": True}

    def review_form(self, session_id: str) -> str | dict[str, Any]:
        result = self.review_registration(session_id)
        if result.get("success"):
            return result["data"]["review_text"]
        return result

    def get_current_question(self, session_id: str) -> str | dict[str, Any] | None:
        session_error = self._require_session(session_id)
        if session_error:
            return session_error
        language = self.session_configs[session_id].get("language", "ar")
        return self.brain.registration_engine.get_current_question(session_id, language)

    def get_field_order(self) -> list[str]:
        return self.brain.registration_engine._guided_field_order("en")

    def get_field_profiles(self) -> dict[str, Any]:
        try:
            from registration_field_profiles import FIELD_PROFILES
            return FIELD_PROFILES
        except ImportError:
            return {}

    def validate_knowledge_base(self) -> list[dict[str, Any]]:
        return self.brain.knowledge_base.get_validation_report()

    def health_check(self) -> dict[str, str]:
        return {"status": "healthy", "version": "1.0.0"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _frontend_registration_data(
        self,
        session_id: str,
        requested_field_id: str,
        requested_interaction: str,
        result: dict[str, Any],
        language: str,
        generate_audio: bool,
    ) -> dict[str, Any]:
        form_updates = result.get("form_updates") or {}
        frontend_updates = self._frontend_form_updates(form_updates)
        speech_text = result.get("speech_text") or result.get("response_text") or ""
        audio = self._build_audio_metadata(
            session_id=session_id,
            text=speech_text,
            language=language,
            generate_audio=generate_audio,
        )

        return {
            "field_id": requested_field_id,
            "interaction": requested_interaction,
            "status": result.get("status", "error"),
            "field_completed": result.get("field_completed", False),
            "allow_frontend_next": result.get("allow_frontend_next", False),
            "form_updates": form_updates,
            "frontend_form_updates": frontend_updates,
            "normalized_value": result.get("normalized_value"),
            "response_text": result.get("response_text") or speech_text,
            "speech_text": speech_text,
            "confirmation": result.get("confirmation") or {
                "required": False,
                "field_id": None,
                "display_value": None,
            },
            "manual_input": result.get("manual_input") or {
                "required": False,
                "field_id": None,
                "prompt": None,
                "input_mode": None,
            },
            "ui_action": result.get("ui_action") or "SHOW_ERROR",
            "audio": audio,
        }

    def _build_audio_metadata(
        self,
        session_id: str,
        text: str,
        language: str,
        generate_audio: bool,
    ) -> dict[str, Any]:
        audio = {
            "generated": False,
            "path": None,
            "content_type": None,
        }

        if not generate_audio or not text:
            return audio

        try:
            from tts_engine import generate_tts_audio
            output_dir = Path("data/generated_audio") / session_id
            path = generate_tts_audio(text, language, output_dir=output_dir)
        except Exception:
            path = None

        if path:
            safe_path = Path(path)
            try:
                safe_path = safe_path.relative_to(Path.cwd())
            except ValueError:
                pass
            audio.update({
                "generated": True,
                "path": safe_path.as_posix(),
                "content_type": "audio/mpeg",
            })

        return audio

    def _canonical_field_id(self, field_id: Any) -> str | None:
        if not isinstance(field_id, str):
            return None

        candidate = field_id.strip()
        if not candidate:
            return None

        field_ids = {
            field["field_id"]
            for field in self.brain.registration_engine.field_definitions
        }
        if candidate in field_ids:
            return candidate

        frontend_map = self.brain.registration_engine.FRONTEND_FIELD_MAP
        alias_to_field = {
            frontend_id: canonical_id
            for canonical_id, frontend_id in frontend_map.items()
        }
        canonical = alias_to_field.get(candidate)
        if canonical in field_ids:
            return canonical
        return None

    def _frontend_form_updates(self, form_updates: dict[str, Any]) -> dict[str, Any]:
        frontend_map = self.brain.registration_engine.FRONTEND_FIELD_MAP
        return {
            frontend_map[field_id]: value
            for field_id, value in form_updates.items()
            if field_id in frontend_map
        }

    def _require_session(self, session_id: Any) -> dict[str, Any] | None:
        if not isinstance(session_id, str) or not session_id.strip():
            return self._error("SESSION_NOT_FOUND", "The requested session does not exist.")
        if session_id not in self.session_configs:
            return self._error("SESSION_NOT_FOUND", "The requested session does not exist.")
        return None

    def _validate_language(self, language: Any) -> dict[str, Any] | None:
        if not isinstance(language, str) or language not in SUPPORTED_LANGUAGES:
            return self._error("INVALID_LANGUAGE", "Unsupported language.")
        return None

    def _validate_mode(self, mode: Any) -> dict[str, Any] | None:
        if not isinstance(mode, str) or mode not in SUPPORTED_MODES:
            return self._error("INVALID_MODE", "Unsupported mode.")
        return None

    def _clean_transcript(self, transcript: Any) -> dict[str, Any]:
        if not isinstance(transcript, str):
            return self._error("INVALID_TRANSCRIPT", "Transcript must be a string.")

        text = transcript.strip()
        if not text:
            return self._error("INVALID_TRANSCRIPT", "Transcript cannot be empty.")

        if len(text) > self.MAX_TRANSCRIPT_CHARS:
            return self._error("INVALID_TRANSCRIPT", "Transcript is too long.")

        return {"success": True, "text": text}

    def _error(self, code: str, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": code,
            "message": message,
        }

    def _json_ready(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._json_ready(asdict(value))

        if isinstance(value, dict):
            return {str(key): self._json_ready(item) for key, item in value.items()}

        if isinstance(value, (list, tuple)):
            return [self._json_ready(item) for item in value]

        if isinstance(value, set):
            return sorted(self._json_ready(item) for item in value)

        if isinstance(value, Path):
            return value.as_posix()

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        return str(value)
