"""
Shared data models for the AI Brain.

These models define the shape of input, processed text, and output
used inside the system.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrainInput:
    """
    Input received by the AI Brain.

    This text will later come from the STT system,
    but for now we type it manually in main.py.
    """

    session_id: str
    text: str
    language: str
    mode: str = "qa"


@dataclass
class ProcessedText:
    """
    Text package created by text_processor.py before entering the brain logic.

    Important rule:
    We always keep raw_text so we can debug STT mistakes later.
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

    Later this output will include real answer text, form updates,
    and TTS audio path.
    """

    mode: str
    answer_text: str
    speech_text: str
    confidence: float
    current_topic: str | None = None
    audio_path: str | None = None
    form_updates: dict[str, Any] = field(default_factory=dict)
    route_taken: list[str] = field(default_factory=list)