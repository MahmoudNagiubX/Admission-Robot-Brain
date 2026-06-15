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
