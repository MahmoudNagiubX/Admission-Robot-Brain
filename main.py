# Simple test runner. We enter text and see the brain output.
""" Local test runner for Admission Robot AI Brain.
    This file is only for testing your AI Brain locally.
    It simulates text coming from the STT system. """

from brain import ECUBrain
from config import DEFAULT_LANGUAGE, DEFAULT_MODE
from models import BrainInput

def run_local_test() -> None:
    brain = ECUBrain()
    print("=" * 60)
    print("Admission Robot AI Brain - Local Test")
    print("Type 'exit' to stop.")
    print("=" * 60)
    session_id = "test-session-001"

    while True:
        user_text = input("\nUser text: ").strip()

        if user_text.lower() in {"exit", "quit"}:
            print("Stopping local test.")
            break

        brain_input = BrainInput(
            session_id=session_id,
            text=user_text,
            language=DEFAULT_LANGUAGE,
            mode=DEFAULT_MODE,
        )

        try:
            output = brain.process(brain_input)

            print("\nBrain Output")
            print("-" * 60)
            print(f"Mode: {output.mode}")
            print(f"Answer Text: {output.answer_text}")
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