"""
Service Layer for ECU Admission AI Brain.
Wraps the core ECUBrain to provide a clean API for backend integration.
"""

from dataclasses import asdict
from typing import Any
import uuid

from brain import ECUBrain
from models import BrainInput, BrainOutput


class AdmissionBrainService:
    """
    High-level service for interacting with the AI Brain.
    Designed for use by Flask/FastAPI backend developers.
    """

    def __init__(self) -> None:
        self.brain = ECUBrain()
        # Default settings per session
        self.session_configs: dict[str, dict[str, str]] = {}

    def create_session(self) -> dict[str, str]:
        """
        Initialize a new session.
        """
        session_id = str(uuid.uuid4())
        self.session_configs[session_id] = {
            "language": "ar",
            "mode": "qa"
        }
        return {"session_id": session_id}

    def set_language(self, session_id: str, language: str) -> None:
        """
        Set language for a specific session.
        """
        if session_id not in self.session_configs:
            self.session_configs[session_id] = {"mode": "qa"}
        self.session_configs[session_id]["language"] = language

    def set_mode(self, session_id: str, mode: str) -> None:
        """
        Set operational mode (qa or registration) for a session.
        """
        if session_id not in self.session_configs:
            self.session_configs[session_id] = {"language": "ar"}
        self.session_configs[session_id]["mode"] = mode

    def process_text(self, session_id: str, text: str) -> dict[str, Any]:
        """
        Process user text input and return structured response.
        """
        config = self.session_configs.get(session_id, {"language": "ar", "mode": "qa"})
        
        brain_input = BrainInput(
            session_id=session_id,
            text=text,
            language=config.get("language", "ar"),
            mode=config.get("mode", "qa")
        )
        
        output: BrainOutput = self.brain.process(brain_input)
        return asdict(output)

    def process_voice_transcript(self, session_id: str, transcript: str) -> dict[str, Any]:
        """
        Handle STT transcript. Currently same as process_text.
        """
        return self.process_text(session_id, transcript)

    def start_registration(self, session_id: str) -> dict[str, Any]:
        """
        Explicitly start the registration flow.
        """
        self.set_mode(session_id, "registration")
        config = self.session_configs.get(session_id, {"language": "ar"})
        lang = config.get("language", "ar")
        
        # We simulate a "start registration" command
        start_cmd = "ابدأ التسجيل" if lang == "ar" else "start registration"
        return self.process_text(session_id, start_cmd)

    def submit_registration_answer(self, session_id: str, answer: str) -> dict[str, Any]:
        """
        Submit an answer specifically for the current registration field.
        """
        self.set_mode(session_id, "registration")
        return self.process_text(session_id, answer)

    def get_form_status(self, session_id: str) -> dict[str, Any]:
        """
        Return the current registration form completion status.
        """
        return self.brain.registration_engine.get_registration_status(session_id)

    def get_form_values(self, session_id: str) -> dict[str, Any]:
        """
        Return current form values with internal snake_case keys.
        """
        return self.brain.registration_engine.export_form_values(session_id)

    def get_form_values_frontend(self, session_id: str) -> dict[str, Any]:
        """
        Return current form values with frontend camelCase keys.
        """
        return self.brain.registration_engine.export_form_values_frontend(session_id)

    def get_current_question(self, session_id: str) -> str | None:
        """
        Return the question for the current missing field.
        """
        config = self.session_configs.get(session_id, {"language": "ar"})
        return self.brain.registration_engine.get_current_question(
            session_id, config.get("language", "ar")
        )

    def get_field_order(self) -> list[str]:
        """
        Return the order of fields in the registration process.
        """
        # Internal method accessed for documentation/UI purposes
        return self.brain.registration_engine._guided_field_order("en")

    def reset_session(self, session_id: str) -> None:
        """
        Completely reset a user session (memory and registration).
        """
        self.brain.reset_session(session_id)
        if session_id in self.session_configs:
            self.session_configs[session_id]["mode"] = "qa"

    def reset_registration(self, session_id: str) -> None:
        """
        Reset only the registration state for a session.
        """
        self.brain.registration_engine.reset_session(session_id)

    def review_form(self, session_id: str) -> str:
        """
        Return a summary string of all entered registration data.
        """
        config = self.session_configs.get(session_id, {"language": "ar"})
        return self.brain.registration_engine.get_review_summary(
            session_id, config.get("language", "ar")
        )

    def get_field_profiles(self) -> dict[str, Any]:
        """
        Return metadata about all registration fields.
        """
        # registration_field_profiles.py is likely where these are defined
        try:
            from registration_field_profiles import FIELD_PROFILES
            return FIELD_PROFILES
        except ImportError:
            return {}

    def validate_knowledge_base(self) -> list[dict[str, Any]]:
        """
        Run validation on all faculty JSON files and return the report.
        """
        return self.brain.knowledge_base.get_validation_report()

    def health_check(self) -> dict[str, str]:
        """
        Simple health check for the brain service.
        """
        return {"status": "healthy", "version": "1.0.0"}
