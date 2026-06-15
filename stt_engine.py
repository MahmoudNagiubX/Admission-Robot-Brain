"""
Deepgram speech-to-text engine for local Admission Robot demos.

The engine records one short microphone utterance and sends it to Deepgram.
All optional dependencies and API failures are handled as unavailable STT
instead of crashing the main AI Brain flow.
"""

from __future__ import annotations

import io
import json
import os
import urllib.parse
import urllib.request
import wave
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from config import (
    DEEPGRAM_API_KEY_ENV,
    ENABLE_VOICE_INPUT,
    MICROPHONE_DEVICE_INDEX,
    STT_PROVIDER,
)


class STTEngine:
    """
    Minimal Deepgram microphone transcription wrapper.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024
    SAMPLE_WIDTH = 2
    RECORD_SECONDS = 6
    DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"

    def __init__(self) -> None:
        if load_dotenv is not None:
            load_dotenv()

        self.provider = STT_PROVIDER
        self.api_key = os.getenv(DEEPGRAM_API_KEY_ENV)
        self.microphone_device_index = MICROPHONE_DEVICE_INDEX
        self.last_error: str | None = None

    def is_available(self) -> bool:
        self.last_error = None

        if not ENABLE_VOICE_INPUT:
            self.last_error = "Voice input is disabled."
            return False

        if self.provider != "deepgram":
            self.last_error = f"Unsupported STT provider: {self.provider}"
            return False

        if not self.api_key:
            self.last_error = "Deepgram API key is missing."
            return False

        if self._load_pyaudio() is None:
            self.last_error = "Microphone dependency is missing: pyaudio."
            return False

        return True

    def transcribe_once(self, language: str) -> str | None:
        if not self.is_available():
            return None

        audio_bytes = self._record_wav_once()

        if audio_bytes is None:
            return None

        return self._send_to_deepgram(audio_bytes, language)

    def list_microphones(self) -> list[dict[str, Any]]:
        pyaudio = self._load_pyaudio()

        if pyaudio is None:
            self.last_error = "Microphone dependency is missing: pyaudio."
            return []

        devices: list[dict[str, Any]] = []
        audio = None

        try:
            audio = pyaudio.PyAudio()

            for index in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(index)

                if int(device_info.get("maxInputChannels", 0)) <= 0:
                    continue

                devices.append(
                    {
                        "index": index,
                        "name": device_info.get("name"),
                        "max_input_channels": device_info.get("maxInputChannels"),
                        "default_sample_rate": device_info.get("defaultSampleRate"),
                    }
                )

            return devices
        except Exception as error:
            self.last_error = f"Could not list microphones: {error}"
            return []
        finally:
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass

    def _record_wav_once(self) -> bytes | None:
        pyaudio = self._load_pyaudio()

        if pyaudio is None:
            self.last_error = "Microphone dependency is missing: pyaudio."
            return None

        audio = None
        stream = None

        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                input_device_index=self.microphone_device_index,
                frames_per_buffer=self.CHUNK_SIZE,
            )
            frames = []
            total_chunks = int(self.SAMPLE_RATE / self.CHUNK_SIZE * self.RECORD_SECONDS)

            for _ in range(total_chunks):
                frames.append(stream.read(self.CHUNK_SIZE, exception_on_overflow=False))

            wav_buffer = io.BytesIO()

            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(self.CHANNELS)
                wav_file.setsampwidth(self.SAMPLE_WIDTH)
                wav_file.setframerate(self.SAMPLE_RATE)
                wav_file.writeframes(b"".join(frames))

            return wav_buffer.getvalue()
        except Exception as error:
            self.last_error = f"Microphone recording failed: {error}"
            return None
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass

            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass

    def _send_to_deepgram(self, audio_bytes: bytes, language: str) -> str | None:
        deepgram_language = self._deepgram_language(language)
        query = urllib.parse.urlencode(
            {
                "model": "nova-3",
                "language": deepgram_language,
                "smart_format": "true",
                "punctuate": "true",
            }
        )
        request = urllib.request.Request(
            f"{self.DEEPGRAM_URL}?{query}",
            data=audio_bytes,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            self.last_error = f"Deepgram transcription failed: {error}"
            return None

        transcript = self._extract_transcript(payload)

        if not transcript:
            self.last_error = "Deepgram returned no transcript."
            return None

        return transcript

    def _extract_transcript(self, payload: dict[str, Any]) -> str | None:
        try:
            alternatives = payload["results"]["channels"][0]["alternatives"]
            transcript = alternatives[0].get("transcript", "").strip()
        except (KeyError, IndexError, TypeError):
            return None

        return transcript or None

    def _deepgram_language(self, language: str) -> str:
        if language == "ar":
            return "ar"

        return "en-US"

    def _load_pyaudio(self):
        try:
            import pyaudio
        except Exception:
            return None

        return pyaudio
