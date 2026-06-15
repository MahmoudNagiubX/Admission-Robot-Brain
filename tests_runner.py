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


def test_english_name_does_not_consume_phone() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my name is Ahmed Mohamed Ali and my phone is 01012345678",
        mode="registration",
        session_id="stress-english-name-session",
    )

    assert output.form_updates.get("full_name_en") == "Ahmed Mohamed Ali"
    assert output.form_updates.get("student_mobile_no") == "01012345678"


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


def test_arabic_name_does_not_consume_phone_or_percentage() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "اسمي احمد محمد علي ورقمي 01012345678 ومجموعي 92.5%",
        mode="registration",
        language="ar",
        session_id="stress-arabic-name-session",
    )

    assert output.form_updates.get("full_name_ar") == "احمد محمد علي"
    assert output.form_updates.get("student_mobile_no") == "01012345678"
    assert output.form_updates.get("percentage") == 92.5


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


def test_spaced_phone_extracted() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my phone is 010 1234 5678",
        mode="registration",
        session_id="spaced-phone-session",
    )

    assert output.form_updates.get("student_mobile_no") == "01012345678"


def test_invalid_phone_prefix_rejected() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my phone is 01912345678",
        mode="registration",
        session_id="invalid-prefix-phone-session",
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


def test_email_correction_updates_email() -> None:
    brain = ECUBrain()
    session_id = "email-correction-session"
    process_text(
        brain,
        "my email is old@test.com",
        mode="registration",
        session_id=session_id,
    )
    output = process_text(
        brain,
        "my email is wrong, change it to [new@test.com](mailto:new@test.com)",
        mode="registration",
        session_id=session_id,
    )
    state = brain.registration_engine.export_form_state(session_id)

    assert output.form_updates.get("email_address") == "new@test.com"
    assert state["fields"]["email_address"]["confirmed"] is False


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


def test_arabic_phone_correction_updates_phone() -> None:
    brain = ECUBrain()
    session_id = "arabic-phone-correction-session"
    process_text(
        brain,
        "رقمي 01012345678",
        mode="registration",
        language="ar",
        session_id=session_id,
    )
    output = process_text(
        brain,
        "لا رقمي غلط رقمي 01112345678",
        mode="registration",
        language="ar",
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


def test_reject_command_does_not_confirm_sensitive_fields() -> None:
    brain = ECUBrain()
    session_id = "reject-sensitive-session"
    process_text(
        brain,
        "my phone is 01012345678",
        mode="registration",
        session_id=session_id,
    )
    output = process_text(
        brain,
        "wrong",
        mode="registration",
        session_id=session_id,
    )
    state = brain.registration_engine.export_form_state(session_id)

    assert "registration_confirmation_rejected" in output.route_taken
    assert state["fields"]["student_mobile_no"]["confirmed"] is False


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


def test_guardian_arabic_name_and_phone() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "اسم ولي الامر محمد علي ورقمه 01112345678",
        mode="registration",
        language="ar",
        session_id="guardian-arabic-session",
    )

    assert output.form_updates.get("guardian_name") == "محمد علي"
    assert output.form_updates.get("guardian_mobile_no") == "01112345678"


def test_guardian_english_name_and_phone() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my father name is Mohamed Ali and his phone is 01112345678",
        mode="registration",
        session_id="guardian-english-session",
    )

    assert output.form_updates.get("guardian_name") == "Mohamed Ali"
    assert output.form_updates.get("guardian_mobile_no") == "01112345678"


def test_percentage_valid() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my percentage is 88.7%",
        mode="registration",
        session_id="valid-percentage-session",
    )

    assert output.form_updates.get("percentage") == 88.7


def test_percentage_invalid_over_100_rejected() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my percentage is 105%",
        mode="registration",
        session_id="invalid-percentage-105-session",
    )

    assert "percentage" not in output.form_updates
    assert "registration_validation_failed:percentage" in output.route_taken


def test_year_valid() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "I graduated in 2024",
        mode="registration",
        session_id="valid-year-session",
    )

    assert output.form_updates.get("year_of_completion") == 2024


def test_certificate_english() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "my certificate is American diploma",
        mode="registration",
        session_id="certificate-english-session",
    )

    assert output.form_updates.get("certificate") == "American"


def test_certificate_arabic() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "شهادتي ثانوية عامة",
        mode="registration",
        language="ar",
        session_id="certificate-arabic-session",
    )

    assert output.form_updates.get("certificate") == "Thanaweya Amma"


def test_college_preference_first_choice() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "I want engineering as first choice",
        mode="registration",
        session_id="college-first-session",
    )

    assert output.form_updates.get("college_preference_1") == "engineering_and_technology"


def test_multiple_college_preferences() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "I want engineering first and computers second",
        mode="registration",
        session_id="college-multiple-session",
    )

    assert output.form_updates.get("college_preference_1") == "engineering_and_technology"
    assert (
        output.form_updates.get("college_preference_2")
        == "computers_and_information_systems"
    )


def test_export_values_flat() -> None:
    brain = ECUBrain()
    session_id = "export-values-session"
    process_text(
        brain,
        "my name is Ahmed Mohamed and my phone is 01012345678",
        mode="registration",
        session_id=session_id,
    )
    values = brain.registration_engine.export_form_values(session_id)

    assert values.get("full_name_en") == "Ahmed Mohamed"
    assert values.get("student_mobile_no") == "01012345678"
    assert not isinstance(values.get("student_mobile_no"), dict)


def test_registration_status_shape() -> None:
    brain = ECUBrain()
    session_id = "status-shape-session"
    process_text(
        brain,
        "my phone is 01012345678",
        mode="registration",
        session_id=session_id,
    )
    status = brain.registration_engine.get_registration_status(session_id)

    assert isinstance(status.get("missing_required_fields"), list)
    assert isinstance(status.get("unconfirmed_sensitive_fields"), list)
    assert "student_mobile_no" in status["unconfirmed_sensitive_fields"]


def main() -> int:
    tests = [
        ("QA FAQ", test_qa_faq),
        ("QA KB/RAG", test_qa_kb_rag),
        ("QA no source", test_qa_no_source),
        ("Registration English", test_registration_english),
        (
            "Registration English name boundary",
            test_english_name_does_not_consume_phone,
        ),
        ("Registration Arabic", test_registration_arabic),
        (
            "Registration Arabic name boundary",
            test_arabic_name_does_not_consume_phone_or_percentage,
        ),
        ("Registration spaced phone", test_spaced_phone_extracted),
        ("Registration invalid phone rejected", test_invalid_phone_rejected),
        (
            "Registration invalid phone prefix rejected",
            test_invalid_phone_prefix_rejected,
        ),
        ("Registration invalid percentage rejected", test_invalid_percentage_rejected),
        (
            "Registration invalid percentage over 100 rejected",
            test_percentage_invalid_over_100_rejected,
        ),
        ("Registration email correction", test_email_correction_updates_email),
        ("Registration correction updates phone", test_correction_updates_phone),
        (
            "Registration Arabic correction updates phone",
            test_arabic_phone_correction_updates_phone,
        ),
        (
            "Registration confirm marks sensitive fields confirmed",
            test_confirm_marks_sensitive_fields_confirmed,
        ),
        (
            "Registration reject keeps sensitive fields unconfirmed",
            test_reject_command_does_not_confirm_sensitive_fields,
        ),
        ("Registration guardian phone routed", test_guardian_phone_routed),
        ("Registration Arabic guardian name and phone", test_guardian_arabic_name_and_phone),
        ("Registration English guardian name and phone", test_guardian_english_name_and_phone),
        ("Registration valid percentage", test_percentage_valid),
        ("Registration valid year", test_year_valid),
        ("Registration English certificate", test_certificate_english),
        ("Registration Arabic certificate", test_certificate_arabic),
        ("Registration first college preference", test_college_preference_first_choice),
        ("Registration multiple college preferences", test_multiple_college_preferences),
        ("Registration export values flat", test_export_values_flat),
        ("Registration status shape", test_registration_status_shape),
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
