"""
Local test runner for Admission Robot AI Brain.

This file simulates text coming from the STT system.
You can test Arabic or English text directly from the terminal.
"""

from brain import ECUBrain
from config import DEFAULT_LANGUAGE, DEFAULT_MODE, SUPPORTED_LANGUAGES, SUPPORTED_MODES
from models import BrainInput


def run_local_test() -> None:
    brain = ECUBrain()

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
    print("=" * 70)

    while True:
        user_text = input(f"\n[{language} | {mode}] User text: ").strip()

        if user_text.lower() in {"exit", "quit"}:
            print("Stopping local test.")
            break

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

            print("\nBrain Output")
            print("-" * 70)
            print(f"Mode: {output.mode}")
            print(f"Answer Text:\n{output.answer_text}")
            print(f"Speech Text: {output.speech_text}")
            print(f"Confidence: {output.confidence}")
            print(f"Current Topic: {output.current_topic}")
            print(f"Audio Path: {output.audio_path}")
            print(f"Form Updates: {output.form_updates}")
            print(f"Route Taken: {output.route_taken}")

        except Exception as error:
            print(f"\nError: {error}")


if __name__ == "__main__":
    run_local_test()
