"""
Local test runner for Admission Robot AI Brain.

This file simulates text coming from the STT system.
You can test Arabic or English text directly from the terminal.
"""

import json
import os
from brain import ECUBrain
from config import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODE,
    EDGE_TTS_VOICE_AR,
    EDGE_TTS_VOICE_EN,
    ENABLE_TTS,
    ENABLE_VOICE_INPUT,
    STT_PROVIDER,
    SUPPORTED_LANGUAGES,
    SUPPORTED_MODES,
    TTS_PROVIDER,
)
from llm_client import LLMClient
from models import BrainInput
from stt_engine import STTEngine
from tts_engine import speak_text
from console_utils import format_for_terminal


def run_local_test() -> None:
    brain = ECUBrain()
    stt_engine = STTEngine()

    session_id = "test-session-001"
    language = DEFAULT_LANGUAGE
    mode = DEFAULT_MODE
    voice_failure_counter = 0

    def normalize_command(text: str) -> str:
        """
        Normalize known commands by trimming punctuation and quotes.
        """
        known_commands = {
            "listen", "voice", "exit", "quit", "lang en", "lang ar", 
            "mode qa", "mode registration", "start form", "next question", 
            "skip field", "show form", "show field order", "export form", "review form", 
            "status form", "test tts", "audio status", "list mics", 
            "validate kb", "test llm"
        }
        
        # Trim common trailing punctuation and quotes
        trimmed = text.strip().strip("'\".,!؟?")
        
        if trimmed.lower() in known_commands:
            return trimmed.lower()
            
        # Also check for lang/mode prefix
        if trimmed.lower().startswith("lang ") or trimmed.lower().startswith("mode "):
            return trimmed.lower()
            
        return text.strip()

    print("=" * 70)
    print("Admission Robot AI Brain - Local Test")
    print("=" * 70)
    print("Commands:")
    print("  exit                 -> stop")
    print("  lang ar              -> switch to Arabic")
    print("  lang en              -> switch to English")
    print("  mode qa              -> Q&A mode")
    print("  mode registration    -> registration mode")
    print("  validate kb          -> print knowledge base validation report")
    print("  show form            -> print registration form debug view")
    print("  show field order     -> print registration field sequence")
    print("  review form          -> print registration review summary")
    print("  export form          -> print flat registration values")
    print("  status form          -> print registration status")
    print("  start form           -> start guided registration questions")
    print("  next question        -> print current registration question")
    print("  skip field           -> skip current guided field")
    print("  test llm             -> test configured LLM provider")
    print("  test tts             -> test robot voice output")
    print("  audio status         -> check audio and environment setup")
    print("  listen / voice       -> record one utterance and process transcript")
    print("  list mics            -> list available microphone input devices")
    print("=" * 70)

    def process_user_text(text: str) -> None:
        brain_input = BrainInput(
            session_id=session_id,
            text=text,
            language=language,
            mode=mode,
        )

        try:
            output = brain.process(brain_input)
            print_brain_output(output)

            # Determine what to speak
            text_to_speak = (
                output.next_question or output.speech_text or output.answer_text
            )
            if text_to_speak:
                speak_text(text_to_speak, language=language)

        except Exception as error:
            print(f"\nError: {error}")

    while True:
        raw_input = input(f"\n[{language} | {mode}] User text: ")
        user_input = normalize_command(raw_input)

        if user_input in {"exit", "quit"}:
            print("Stopping local test.")
            break

        if user_input == "validate kb":
            print_validation_report(brain.knowledge_base.get_validation_report())
            continue

        if user_input == "show form":
            print_form_debug_view(
                brain.registration_engine.get_form_debug_view(session_id)
            )
            continue

        if user_input == "show field order":
            print("\nRegistration Field Sequence")
            print("-" * 70)
            print(brain.registration_engine.show_field_order())
            continue

        if user_input == "review form":
            print("\nRegistration Review Summary")
            print("-" * 70)
            summary = brain.registration_engine.get_review_summary(session_id, language)
            speak_text(summary, language=language)
            continue

        if user_input == "export form":
            print("\nRegistration Form Export")
            print("-" * 70)
            print(
                json.dumps(
                    brain.registration_engine.export_form_values(session_id),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            continue

        if user_input == "status form":
            print("\nRegistration Status")
            print("-" * 70)
            print(
                json.dumps(
                    brain.registration_engine.get_registration_status(session_id),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            continue

        if user_input == "start form":
            mode = "registration"
            question = brain.registration_engine.start_guided_form(
                session_id=session_id,
                language=language,
            )
            print("\nGuided Registration")
            print("-" * 70)
            text_to_print = question or "No registration question is available."
            speak_text(text_to_print, language=language)
            continue

        if user_input == "next question":
            question = brain.registration_engine.get_current_question(
                session_id=session_id,
                language=language,
            )
            print("\nNext Registration Question")
            print("-" * 70)
            text_to_print = question or "No registration question is available."
            speak_text(text_to_print, language=language)
            continue

        if user_input == "skip field":
            question = brain.registration_engine.skip_current_field(
                session_id=session_id,
                language=language,
            )
            print("\nNext Registration Question")
            print("-" * 70)
            text_to_print = question or "No more guided registration questions."
            speak_text(text_to_print, language=language)
            continue

        if user_input == "test llm":
            run_llm_test()
            continue

        if user_input == "test tts":
            speak_text("This is a test voice from Admission Robot.", language=language)
            continue

        if user_input == "audio status":
            print_audio_status()
            continue

        if user_input == "list mics":
            print_microphones(stt_engine)
            continue

        if user_input in {"listen", "voice"}:
            stt_language = language
            # If in registration mode, check current field to optimize STT language
            if mode == "registration":
                status = brain.registration_engine.get_form_debug_view(session_id)
                current_field = status.get("current_field")
                if current_field == "full_name_ar":
                    stt_language = "ar"
                elif current_field == "full_name_en":
                    stt_language = "en"
            
            transcript = run_voice_input(stt_engine, stt_language)

            if transcript:
                process_user_text(transcript)
                voice_failure_counter = 0
            else:
                voice_failure_counter += 1
                if voice_failure_counter == 1:
                    if language == "ar":
                        retry_msg = "لم أسمعك بوضوح. من فضلك أعد الإجابة."
                    else:
                        retry_msg = "I could not hear you clearly. Please repeat your answer."
                else:
                    if language == "ar":
                        retry_msg = "لسه الصوت غير واضح. ممكن تكتب الإجابة يدويًا أو تقرب من الميكروفون."
                    else:
                        retry_msg = "The audio is still unclear. You can type the answer manually or move closer to the microphone."

                if mode == "registration":
                    current_question = brain.registration_engine.get_current_question(session_id, language)
                    if current_question:
                        retry_msg = f"{retry_msg} {current_question}"

                print(format_for_terminal(f"\nRobot: {retry_msg}"))
                speak_text(retry_msg, language=language)

            continue

        if user_input.startswith("lang "):
            new_language = user_input.replace("lang ", "").strip()

            if new_language in SUPPORTED_LANGUAGES:
                language = new_language
                print(f"Language changed to: {language}")
            else:
                print(f"Unsupported language. Use one of: {SUPPORTED_LANGUAGES}")

            continue

        if user_input.startswith("mode "):
            new_mode = user_input.replace("mode ", "").strip()

            if new_mode in SUPPORTED_MODES:
                mode = new_mode
                print(f"Mode changed to: {mode}")
            else:
                print(f"Unsupported mode. Use one of: {SUPPORTED_MODES}")

            continue

        if not user_input:
            continue

        # Process normal typed input
        process_user_text(user_input)
        voice_failure_counter = 0


def print_validation_report(report: list[dict]) -> None:
    print("\nKnowledge Base Validation Report")
    print("-" * 70)

    if not report:
        print("No faculty files were validated.")
        return

    for result in report:
        status = "valid" if result.get("is_valid") else "invalid"
        print(f"File: {result.get('file_name')} | Status: {status}")

        errors = result.get("errors", [])
        warnings = result.get("warnings", [])

        if errors:
            print("Errors:")

            for error in errors:
                print(f"  - {error}")

        if warnings:
            print("Warnings:")

            for warning in warnings:
                print(f"  - {warning}")

        if not errors and not warnings:
            print("No errors or warnings.")

        print("-" * 70)


def print_form_debug_view(debug_view: dict) -> None:
    print("\nRegistration Form Debug View")
    print("-" * 70)
    print(json.dumps(debug_view, ensure_ascii=False, indent=2))


def print_microphones(stt_engine: STTEngine) -> None:
    microphones = stt_engine.list_microphones()

    print("\nAvailable Microphones")
    print("-" * 70)

    if not microphones:
        print(stt_engine.last_error or "No microphone input devices found.")
        return

    for microphone in microphones:
        print(
            f"Index {microphone.get('index')}: {microphone.get('name')} "
            f"| channels={microphone.get('max_input_channels')} "
            f"| rate={microphone.get('default_sample_rate')}"
        )


def run_voice_input(stt_engine: STTEngine, language: str) -> str | None:
    if not stt_engine.is_available():
        print(f"\nSTT unavailable: {stt_engine.last_error}")
        return None

    print("\nListening for one utterance...")
    transcript = stt_engine.transcribe_once(language)

    if not transcript:
        print(f"STT unavailable: {stt_engine.last_error or 'No transcript returned.'}")
        return None

    print(format_for_terminal(f"Transcript: {transcript}"))
    return transcript


def print_brain_output(output) -> None:
    print("\nBrain Output")
    print("-" * 70)
    print(f"Mode: {output.mode}")
    print(format_for_terminal(f"Answer Text:\n{output.answer_text}"))
    print(format_for_terminal(f"Speech Text: {output.speech_text}"))
    print(f"Confidence: {output.confidence}")
    print(f"Current Topic: {output.current_topic}")
    print(f"Audio Path: {output.audio_path}")
    print(format_for_terminal(f"Form Updates: {output.form_updates}"))
    print(format_for_terminal(f"Next Question: {output.next_question}"))
    print(f"Needs Confirmation: {output.needs_confirmation}")
    if output.manual_input_required:
        print(f"Manual Input Required: {output.manual_input_required}")
        print(f"Manual Field: {output.manual_field}")
    print(f"Route Taken: {output.route_taken}")


def run_llm_test() -> None:
    llm_client = LLMClient()
    response = llm_client.generate_grounded_answer(
        question="Say ready in one short sentence.",
        context="This is a safe local health health check. The only expected answer is readiness.",
        language="en",
    )
    succeeded = bool(response)

    print("\nLLM Provider Test")
    print("-" * 70)
    print(f"Provider: {llm_client.provider}")
    print(f"Model: {llm_client.model}")
    print(f"Succeeded: {succeeded}")

    if succeeded:
        print(f"Response: {response}")


def print_audio_status() -> None:
    print("\nAudio and Environment Status")
    print("-" * 70)
    print(f"ENABLE_TTS: {ENABLE_TTS}")
    print(f"TTS_PROVIDER: {TTS_PROVIDER}")
    print(f"EDGE_TTS_VOICE_EN: {EDGE_TTS_VOICE_EN}")
    print(f"EDGE_TTS_VOICE_AR: {EDGE_TTS_VOICE_AR}")
    print(f"ENABLE_VOICE_INPUT: {ENABLE_VOICE_INPUT}")
    print(f"STT_PROVIDER: {STT_PROVIDER}")

    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    has_deepgram = bool(deepgram_key and deepgram_key.strip())
    print(f"DEEPGRAM_API_KEY configured: {has_deepgram}")
    print("-" * 70)


if __name__ == "__main__":
    run_local_test()
