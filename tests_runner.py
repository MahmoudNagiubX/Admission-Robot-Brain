"""
Small regression test runner for Admission Robot AI Brain.

Uses only the Python standard library.
"""

import os
import sys

os.environ["ENABLE_LLM_RAG"] = "false"
os.environ["ENABLE_LLM_REGISTRATION_EXTRACTION"] = "false"

from brain import ECUBrain
from models import BrainInput


def run_test(name: str, check) -> bool:
    try:
        check()
    except AssertionError as error:
        print(f"FAIL: {name} - {error}")
        return False
    except Exception as error:
        print(f"FAIL: {name} - unexpected error: {error}")
        return False

    print(f"PASS: {name}")
    return True


def process_text(
    brain: ECUBrain,
    text: str,
    mode: str = "qa",
    language: str = "en",
    session_id: str = "test-session",
):
    return brain.process(
        BrainInput(
            session_id=session_id,
            text=text,
            language=language,
            mode=mode,
        )
    )


def test_qa_faq() -> None:
    brain = ECUBrain()
    output = process_text(brain, "where is engineering")

    assert "faq_match_found" in output.route_taken, output.route_taken


def test_qa_kb_rag() -> None:
    brain = ECUBrain()
    output = process_text(brain, "what is engineering vision")

    assert "knowledge_base_match_found" in output.route_taken, output.route_taken


def test_qa_no_source() -> None:
    brain = ECUBrain()
    output = process_text(brain, "does engineering have dorm rooms")

    assert (
        "safe_fallback_returned" in output.route_taken
        or "no_knowledge_base_match_found" in output.route_taken
    ), output.route_taken


def test_registration_english() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my name is Ahmed Mohamed and my phone is 01012345678 "
        "and my email is [ahmed@test.com](mailto:ahmed@test.com)",
        mode="registration",
    )

    assert output.form_updates.get("full_name_en") == "Ahmed Mohamed"
    assert output.form_updates.get("student_mobile_no") == "01012345678"
    assert output.form_updates.get("email_address") == "ahmed@test.com"


def test_registration_arabic() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "اسمي احمد محمد ورقمي 01012345678 ومجموعي 92.5% سنة 2024",
        mode="registration",
        language="ar",
    )

    assert output.form_updates.get("full_name_ar") == "احمد محمد"
    assert output.form_updates.get("student_mobile_no") == "01012345678"
    assert output.form_updates.get("percentage") == 92.5
    assert output.form_updates.get("year_of_completion") == 2024


def test_registration_skips_qa_stack() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my name is Ahmed Mohamed and my phone is 01012345678",
        mode="registration",
    )

    forbidden_notes = {
        "faq_router_checked",
        "knowledge_base_checked",
        "llm_rag_checked",
    }
    assert forbidden_notes.isdisjoint(output.route_taken), output.route_taken
    assert "faq_and_knowledge_base_skipped_for_registration" in output.route_taken


def test_invalid_phone_rejected() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my phone is 12345",
        mode="registration",
        session_id="invalid-phone-session",
    )

    assert "student_mobile_no" not in output.form_updates
    assert "registration_validation_failed:student_mobile_no" in output.route_taken


def test_invalid_percentage_rejected() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my percentage is 150%",
        mode="registration",
        session_id="invalid-percentage-session",
    )

    assert "percentage" not in output.form_updates
    assert "registration_validation_failed:percentage" in output.route_taken


def test_correction_updates_phone() -> None:
    brain = ECUBrain()
    session_id = "correction-session"
    process_text(
        brain,
        "my phone is 01012345678",
        mode="registration",
        session_id=session_id,
    )
    output = process_text(
        brain,
        "No, my phone is 01112345678",
        mode="registration",
        session_id=session_id,
    )
    values = brain.registration_engine.export_form_values(session_id)

    assert output.form_updates.get("student_mobile_no") == "01112345678"
    assert values.get("student_mobile_no") == "01112345678"


def test_confirm_marks_sensitive_fields_confirmed() -> None:
    brain = ECUBrain()
    session_id = "confirm-session"
    process_text(
        brain,
        "my phone is 01012345678 and my email is test@example.com",
        mode="registration",
        session_id=session_id,
    )
    output = process_text(
        brain,
        "confirm",
        mode="registration",
        session_id=session_id,
    )
    state = brain.registration_engine.export_form_state(session_id)

    assert "field_confirmed:student_mobile_no" in output.route_taken
    assert "field_confirmed:email_address" in output.route_taken
    assert state["fields"]["student_mobile_no"]["confirmed"] is True
    assert state["fields"]["email_address"]["confirmed"] is True


def test_guardian_phone_routed() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my father phone is 01112345678",
        mode="registration",
        session_id="guardian-phone-session",
    )

    assert output.form_updates.get("guardian_mobile_no") == "01112345678"
    assert "student_mobile_no" not in output.form_updates


def main() -> int:
    tests = [
        ("QA FAQ", test_qa_faq),
        ("QA KB/RAG", test_qa_kb_rag),
        ("QA no source", test_qa_no_source),
        ("Registration English", test_registration_english),
        ("Registration Arabic", test_registration_arabic),
        ("Registration invalid phone rejected", test_invalid_phone_rejected),
        ("Registration invalid percentage rejected", test_invalid_percentage_rejected),
        ("Registration correction updates phone", test_correction_updates_phone),
        (
            "Registration confirm marks sensitive fields confirmed",
            test_confirm_marks_sensitive_fields_confirmed,
        ),
        ("Registration guardian phone routed", test_guardian_phone_routed),
        ("Registration skips FAQ/KB/RAG", test_registration_skips_qa_stack),
    ]
    results = [run_test(name, check) for name, check in tests]
    passed = sum(1 for result in results if result)
    total = len(results)

    print("-" * 70)
    print(f"Summary: {passed}/{total} passed")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
