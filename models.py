# Shared data structures/classes for input/output.

"""Shared data models for the AI Brain.
These models define the shape of input and output used inside the system.
For now, we use dataclasses to keep the project simple and lightweight."""

from dataclasses import dataclass, field
from typing import Any
@dataclass
class BrainInput:
    """ Input received by the AI Brain.
    This text will later come from the STT system,
    but for now we will type it manually in main.py."""
    
    session_id: str
    text: str
    language: str
    mode: str = "qa"

@dataclass
class BrainOutput:
    """ Final output returned by the AI Brain.
    Later this output will include real answer text, form updates,
    and TTS audio path."""

    mode: str
    answer_text: str
    speech_text: str
    confidence: float
    current_topic: str | None = None
    audio_path: str | None = None
    form_updates: dict[str, Any] = field(default_factory = dict)
    route_taken: list[str] = field(default_factory = list)