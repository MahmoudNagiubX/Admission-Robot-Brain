"""
Deepgram speech-to-text engine for local Admission Robot demos.

This version supports Voice Activity Detection (VAD) / silence-based recording,
waiting for speech to start and automatically stopping after silence.
"""

from __future__ import annotations

import collections
import io
import json
import os
import struct
import time
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
    VOICE_CHANNELS,
    VOICE_CHUNK_MS,
    VOICE_ENERGY_THRESHOLD,
    VOICE_MAX_RECORD_SECONDS,
    VOICE_MIN_RECORD_SECONDS,
    VOICE_PRE_ROLL_MS,
    VOICE_RECORD_MODE,
    VOICE_RECORD_SECONDS,
    VOICE_SAMPLE_RATE,
    VOICE_SILENCE_STOP_SECONDS,
    VOICE_START_TIMEOUT_SECONDS,
)


class STTEngine:
    """
    Minimal Deepgram microphone transcription wrapper with VAD support.
    """

    SAMPLE_WIDTH = 2
    DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"

    def __init__(self) -> None:
        if load_dotenv is not None:
            load_dotenv()

        self.provider = STT_PROVIDER
        self.api_key = os.getenv(DEEPGRAM_API_KEY_ENV)
        self.microphone_device_index = MICROPHONE_DEVICE_INDEX
        self.sample_rate = VOICE_SAMPLE_RATE
        self.channels = VOICE_CHANNELS
        self.record_seconds = VOICE_RECORD_SECONDS
        self.record_mode = VOICE_RECORD_MODE
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

        # Tiny delay to ensure TTS playback has fully stopped and released resources
        time.sleep(0.2)

        audio_bytes = self._record_wav_once()

        if audio_bytes is None:
            return None

        transcript = self._send_to_deepgram(audio_bytes, language)
        if transcript:
            print(f"Transcript: {transcript}")
        return transcript

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
            return None

        if self.record_mode == "fixed":
            return self._record_fixed(pyaudio)

        return self._record_vad(pyaudio)

    def _record_fixed(self, pyaudio: Any) -> bytes | None:
        audio = None
        stream = None
        chunk_size = 1024

        try:
            print(f"Listening for one utterance...")
            print(f"Recording for {self.record_seconds} seconds (fixed mode)...")
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.microphone_device_index,
                frames_per_buffer=chunk_size,
            )
            frames = []
            total_chunks = int(self.sample_rate / chunk_size * self.record_seconds)

            for _ in range(total_chunks):
                frames.append(stream.read(chunk_size, exception_on_overflow=False))

            return self._build_wav(b"".join(frames))
        except Exception as error:
            self.last_error = f"Fixed recording failed: {error}"
            return None
        finally:
            self._cleanup_audio(audio, stream)

    def _record_vad(self, pyaudio: Any) -> bytes | None:
        audio = None
        stream = None
        
        # Calculate chunk size based on VOICE_CHUNK_MS
        chunk_samples = int(self.sample_rate * VOICE_CHUNK_MS / 1000)
        
        # Pre-roll buffer
        pre_roll_chunks = int(VOICE_PRE_ROLL_MS / VOICE_CHUNK_MS)
        pre_roll_buffer = collections.deque(maxlen=max(1, pre_roll_chunks))
        
        try:
            print("Listening... speak now.")
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.microphone_device_index,
                frames_per_buffer=chunk_samples,
            )
            
            speech_started = False
            start_time = time.time()
            speech_start_time = 0
            silence_start_time = 0
            recorded_frames = []
            
            print("Waiting for speech...")
            
            while True:
                data = stream.read(chunk_samples, exception_on_overflow=False)
                energy = self._calculate_rms(data)
                
                now = time.time()
                
                if not speech_started:
                    pre_roll_buffer.append(data)
                    if energy >= VOICE_ENERGY_THRESHOLD:
                        speech_started = True
                        speech_start_time = now
                        recorded_frames.extend(list(pre_roll_buffer))
                        print("Speech detected...")
                    elif now - start_time > VOICE_START_TIMEOUT_SECONDS:
                        print("I did not hear anything. Please try again.")
                        return None
                else:
                    recorded_frames.append(data)
                    
                    if energy < VOICE_ENERGY_THRESHOLD:
                        if silence_start_time == 0:
                            silence_start_time = now
                        elif now - silence_start_time >= VOICE_SILENCE_STOP_SECONDS:
                            print("Silence detected. Processing...")
                            break
                    else:
                        silence_start_time = 0
                        
                    if now - speech_start_time > VOICE_MAX_RECORD_SECONDS:
                        print("Maximum recording length reached. Processing...")
                        break
            
            speech_bytes = b"".join(recorded_frames)
            duration = len(speech_bytes) / (self.sample_rate * self.SAMPLE_WIDTH * self.channels)
            
            if duration < VOICE_MIN_RECORD_SECONDS:
                print("Captured audio too short. Please try again.")
                return None
                
            return self._build_wav(speech_bytes)
            
        except Exception as error:
            self.last_error = f"VAD recording failed: {error}"
            return None
        finally:
            self._cleanup_audio(audio, stream)

    def _calculate_rms(self, chunk_data: bytes) -> float:
        """
        Calculate RMS energy of an audio chunk.
        """
        count = len(chunk_data) // 2
        if count == 0:
            return 0.0
        
        shorts = struct.unpack(f"{count}h", chunk_data)
        
        sum_squares = sum(s**2 for s in shorts)
        return (sum_squares / count) ** 0.5

    def _build_wav(self, audio_data: bytes) -> bytes:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.SAMPLE_WIDTH)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)
        return wav_buffer.getvalue()

    def _cleanup_audio(self, audio: Any, stream: Any) -> None:
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
