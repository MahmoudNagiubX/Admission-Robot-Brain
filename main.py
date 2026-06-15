"""
Local test runner for Admission Robot AI Brain.

This file simulates text coming from the STT system.
You can test Arabic or English text directly from the terminal.
"""

import json

from brain import ECUBrain
from config import DEFAULT_LANGUAGE, DEFAULT_MODE, SUPPORTED_LANGUAGES, SUPPORTED_MODES
from llm_client import LLMClient
from models import BrainInput
from stt_engine import STTEngine


def run_local_test() -> None:
    brain = ECUBrain()
    stt_engine = STTEngine()

    session_id = "test-session-001"
    language = DEFAULT_LANGUAGE
    mode = DEFAULT_MODE

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
    print("  review form          -> print registration review summary")
    print("  export form          -> print flat registration values")
    print("  status form          -> print registration status")
    print("  test llm             -> test configured LLM provider")
    print("  listen / voice       -> record one utterance and process transcript")
    print("  list mics            -> list available microphone input devices")
    print("=" * 70)

    while True:
        user_text = input(f"\n[{language} | {mode}] User text: ").strip()

        if user_text.lower() in {"exit", "quit"}:
            print("Stopping local test.")
            break

        if user_text.lower() == "validate kb":
            print_validation_report(brain.knowledge_base.get_validation_report())
            continue

        if user_text.lower() == "show form":
            print_form_debug_view(
                brain.registration_engine.get_form_debug_view(session_id)
            )
            continue

        if user_text.lower() == "review form":
            print("\nRegistration Review Summary")
            print("-" * 70)
            print(brain.registration_engine.get_review_summary(session_id, language))
            continue

        if user_text.lower() == "export form":
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

        if user_text.lower() == "status form":
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

        if user_text.lower() == "test llm":
            run_llm_test()
            continue

        if user_text.lower() == "list mics":
            print_microphones(stt_engine)
            continue

        if user_text.lower() in {"listen", "voice"}:
            transcript = run_voice_input(stt_engine, language)

            if not transcript:
                continue

            user_text = transcript

        if user_text.lower().startswith("lang "):
            new_language = user_text.lower().replace("lang ", "").strip()

            if new_language in SUPPORTED_LANGUAGES:
                language = new_language
                print(f"Language changed to: {language}")
            else:
                print(f"Unsupported language. Use one of: {SUPPORTED_LANGUAGES}")

            continue

        if user_text.lower().startswith("mode "):
            new_mode = user_text.lower().replace("mode ", "").strip()

            if new_mode in SUPPORTED_MODES:
                mode = new_mode
                print(f"Mode changed to: {mode}")
            else:
                print(f"Unsupported mode. Use one of: {SUPPORTED_MODES}")

            continue

        brain_input = BrainInput(
            session_id=session_id,
            text=user_text,
            language=language,
            mode=mode,
        )

        try:
            output = brain.process(brain_input)
            print_brain_output(output)

        except Exception as error:
            print(f"\nError: {error}")


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

    print(f"Transcript: {transcript}")
    return transcript


def print_brain_output(output) -> None:
    print("\nBrain Output")
    print("-" * 70)
    print(f"Mode: {output.mode}")
    print(f"Answer Text:\n{output.answer_text}")
    print(f"Speech Text: {output.speech_text}")
    print(f"Confidence: {output.confidence}")
    print(f"Current Topic: {output.current_topic}")
    print(f"Audio Path: {output.audio_path}")
    print(f"Form Updates: {output.form_updates}")
    print(f"Next Question: {output.next_question}")
    print(f"Needs Confirmation: {output.needs_confirmation}")
    print(f"Route Taken: {output.route_taken}")


def run_llm_test() -> None:
    llm_client = LLMClient()
    response = llm_client.generate_grounded_answer(
        question="Say ready in one short sentence.",
        context="This is a safe local health check. The only expected answer is readiness.",
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


if __name__ == "__main__":
    run_local_test()
