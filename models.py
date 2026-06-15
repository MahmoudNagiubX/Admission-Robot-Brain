"""
Shared data models for the AI Brain.

We use dataclasses now to keep the project simple and lightweight.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrainInput:
    """
    Input received by the AI Brain.

    In production, text will come from the STT module.
    For local testing, we type the text manually in main.py.
    """

    session_id: str
    text: str
    language: str
    mode: str = "qa"


@dataclass
class ProcessedText:
    """
    Complete text package created before routing.

    Important:
    We keep all versions because every version has a different purpose.
    """

    raw_text: str
    normalized_text: str
    protected_text: str
    corrected_text: str
    search_query: str
    language: str
    entities: dict[str, Any] = field(default_factory=dict)
    route_notes: list[str] = field(default_factory=list)


@dataclass
class ConversationTurn:
    """
    One stored user turn inside session memory.
    """

    user_text: str
    normalized_text: str
    faculty_id: str | None = None
    intent_id: str | None = None
    topic: str | None = None
    mode: str = "qa"
    language: str = "en"


@dataclass
class SessionMemory:
    """
    Short-term memory for one user session.

    This is not permanent storage.
    It only helps the robot understand follow-up questions.
    """

    session_id: str
    language: str
    mode: str
    current_faculty_id: str | None = None
    current_intent_id: str | None = None
    current_topic: str | None = None
    turns: list[ConversationTurn] = field(default_factory=list)


@dataclass
class BrainOutput:
    """
    Final output returned by the AI Brain.

    Later this will include real RAG answers, registration updates, and TTS audio.
    """

    mode: str
    answer_text: str
    speech_text: str
    confidence: float
    current_topic: str | None = None
    audio_path: str | None = None
    form_updates: dict[str, Any] = field(default_factory=dict)
    route_taken: list[str] = field(default_factory=list)