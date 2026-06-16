"""
Edge-TTS engine for local Admission Robot demos.

This module handles robot voice output using edge-tts and pygame for playback.
It supports both English and Arabic with configurable voices and rates.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

from config import (
    EDGE_TTS_RATE,
    EDGE_TTS_RATE_AR,
    EDGE_TTS_VOICE_AR,
    EDGE_TTS_VOICE_EN,
    ENABLE_TTS,
    TTS_FALLBACK_PHRASE,
    TTS_PROVIDER,
)

# Optional dependencies
try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import pygame
except ImportError:
    pygame = None


def speak_text(text: str, language: str = "en") -> None:
    """
    Generate and play speech for the given text.
    Fails safely if TTS is disabled or dependencies are missing.
    """
    print(f"Robot: {text}")

    if not ENABLE_TTS:
        return

    if TTS_PROVIDER != "edge":
        # We only implement edge-tts for now as per instructions.
        return

    if edge_tts is None:
        print("[Warning] edge-tts package is missing. Skipping voice output.")
        return

    if not text.strip():
        return

    try:
        asyncio.run(_generate_and_play(text, language))
    except Exception as error:
        print(f"[Warning] TTS playback failed: {error}")
        if TTS_FALLBACK_PHRASE:
            print(f"Robot: {TTS_FALLBACK_PHRASE}")


async def _generate_and_play(text: str, language: str) -> None:
    """
    Inner async helper to communicate with edge-tts and play via pygame.
    """
    voice = EDGE_TTS_VOICE_AR if language == "ar" else EDGE_TTS_VOICE_EN
    rate = EDGE_TTS_RATE_AR if language == "ar" else EDGE_TTS_RATE

    communicate = edge_tts.Communicate(text, voice, rate=rate)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        tmp_path = tmp_file.name

    try:
        await communicate.save(tmp_path)
        _play_audio(tmp_path)
    finally:
        # Try to delete the temp file after a short delay to ensure it's not locked
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _play_audio(file_path: str) -> None:
    """
    Play an audio file using pygame.
    """
    if pygame is None:
        print("[Warning] pygame package is missing. Skipping audio playback.")
        return

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        pygame.mixer.music.unload()
    except Exception as error:
        print(f"[Warning] Pygame playback error: {error}")
