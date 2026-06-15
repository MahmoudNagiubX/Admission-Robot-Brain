"""
Small regression test runner for Admission Robot AI Brain.

Uses only the Python standard library.
"""

import json
import os
import sys
from pathlib import Path

os.environ["ENABLE_LLM_RAG"] = "false"
os.environ["ENABLE_LLM_REGISTRATION_EXTRACTION"] = "false"
os.environ["ENABLE_VOICE_INPUT"] = "false"

from brain import ECUBrain
from models import BrainInput
from stt_engine import STTEngine


REGISTRATION_FIELDS_PATH = Path("data/registration_fields.json")


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


def load_registration_fields() -> list[dict]:
    with REGISTRATION_FIELDS_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assert isinstance(data, list)
    return data


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


def test_registration_fields_json_valid() -> None:
    fields = load_registration_fields()

    assert fields, "registration_fields.json should contain fields"


def test_registration_fields_have_ui_contract_keys() -> None:
    fields = load_registration_fields()
    required_keys = {"field_id", "section", "label_en", "label_ar", "input_method"}

    for field in fields:
        missing_keys = required_keys - set(field)
        assert not missing_keys, f"{field.get('field_id') or field}: {missing_keys}"


def test_registration_fields_no_duplicate_field_id() -> None:
    fields = load_registration_fields()
    field_ids = [field["field_id"] for field in fields]

    assert len(field_ids) == len(set(field_ids))


def test_registration_schema_sections_present() -> None:
    fields = load_registration_fields()
    sections = {field["section"] for field in fields}

    assert "Personal Data" in sections
    assert "Family Information" in sections
    assert "Received Papers" in sections
    assert "College Preferences" in sections
    assert "Final bottom fields" in sections


def test_registration_required_fields_are_basic_voice_fields_only() -> None:
    fields = load_registration_fields()
    required_fields = {field["field_id"] for field in fields if field.get("required")}
    expected_required = {
        "id_or_passport",
        "student_mobile_no",
        "email_address",
        "school_name",
        "certificate",
        "year_of_completion",
        "percentage",
        "college_preference_1",
        "guardian_name",
        "relationship",
        "guardian_mobile_no",
        "address",
        "city",
        "country",
    }
    name_group_fields = {
        field["field_id"]
        for field in fields
        if field.get("required_group") == "student_name"
    }
    guided_required_fields = {
        field["field_id"]
        for field in fields
        if field.get("required_for_basic_registration") is True
    }

    assert required_fields == expected_required
    assert name_group_fields == {"full_name_en", "full_name_ar"}
    assert guided_required_fields == expected_required | {"full_name_en", "full_name_ar"}
    assert all(
        field["input_method"] == "voice"
        for field in fields
        if field["field_id"] in expected_required or field["field_id"] in name_group_fields
    )


def test_password_is_ui_and_sensitive() -> None:
    fields = load_registration_fields()
    password = next(field for field in fields if field["field_id"] == "password")

    assert password["input_method"] == "ui"
    assert password.get("sensitive") is True


def test_received_paper_fields_are_not_voice() -> None:
    fields = load_registration_fields()
    received_fields = [
        field for field in fields if field["section"] == "Received Papers"
    ]

    assert received_fields
    assert all(field["input_method"] in {"staff", "ui"} for field in received_fields)


def test_final_fields_are_auto() -> None:
    fields = load_registration_fields()
    field_map = {field["field_id"]: field for field in fields}

    for field_id in {"final_student_name", "academic_year", "final_college"}:
        assert field_map[field_id]["input_method"] == "auto"
        assert field_map[field_id].get("required") is False


def test_export_form_state_includes_metadata() -> None:
    brain = ECUBrain()
    session_id = "export-state-metadata-session"
    process_text(
        brain,
        "my name is Ahmed Mohamed and my phone is 01012345678",
        mode="registration",
        session_id=session_id,
    )
    state = brain.registration_engine.export_form_state(session_id)

    assert "fields" in state
    assert "student_mobile_no" in state["fields"]
    assert state["fields"]["student_mobile_no"]["value"] == "01012345678"
    assert "confidence" in state["fields"]["student_mobile_no"]
    assert "confirmed" in state["fields"]["student_mobile_no"]
    assert "needs_confirmation" in state["fields"]["student_mobile_no"]
    assert "source" in state["fields"]["student_mobile_no"]


def test_get_registration_status_required_keys() -> None:
    brain = ECUBrain()
    status = brain.registration_engine.get_registration_status("empty-status-session")

    assert set(status) == {
        "is_basic_registration_complete",
        "completion_percentage",
        "missing_required_fields",
        "unconfirmed_sensitive_fields",
    }


def test_auto_final_fields_exported() -> None:
    brain = ECUBrain()
    session_id = "auto-final-fields-session"
    process_text(
        brain,
        "my name is Ahmed Mohamed and I want engineering as first choice",
        mode="registration",
        session_id=session_id,
    )
    values = brain.registration_engine.export_form_values(session_id)
    state = brain.registration_engine.export_form_state(session_id)

    assert values.get("final_student_name") == "Ahmed Mohamed"
    assert values.get("final_college") == "engineering_and_technology"
    assert "academic_year" not in values
    assert state["fields"]["final_student_name"]["source"] == "auto"
    assert state["fields"]["final_college"]["source"] == "auto"


def test_registration_name_requirement_accepts_either_language() -> None:
    brain = ECUBrain()
    session_id = "name-requirement-session"
    process_text(
        brain,
        "my name is Ahmed Mohamed",
        mode="registration",
        session_id=session_id,
    )
    status = brain.registration_engine.get_registration_status(session_id)

    assert "full_name_en" not in status["missing_required_fields"]
    assert "full_name_ar" not in status["missing_required_fields"]


def test_stt_engine_imports_and_fails_safely_without_voice() -> None:
    stt_engine = STTEngine()

    assert stt_engine.is_available() is False
    assert stt_engine.transcribe_once("en") is None
    assert stt_engine.last_error


def test_guided_start_returns_first_question() -> None:
    brain = ECUBrain()
    question = brain.registration_engine.start_guided_form(
        session_id="guided-start-session",
        language="en",
    )
    debug_view = brain.registration_engine.get_form_debug_view("guided-start-session")

    assert question == "What is your full name in English?"
    assert debug_view["current_field"] == "full_name_en"


def test_guided_answer_first_name_fills_current_field() -> None:
    brain = ECUBrain()
    session_id = "guided-name-session"
    brain.registration_engine.start_guided_form(session_id=session_id, language="en")
    output = process_text(
        brain,
        "Ahmed Mohamed Ali",
        mode="registration",
        session_id=session_id,
    )
    values = brain.registration_engine.export_form_values(session_id)

    assert output.form_updates.get("full_name_en") == "Ahmed Mohamed Ali"
    assert values.get("full_name_en") == "Ahmed Mohamed Ali"


def test_guided_next_question_moves_forward_after_name() -> None:
    brain = ECUBrain()
    session_id = "guided-next-session"
    brain.registration_engine.start_guided_form(session_id=session_id, language="en")
    output = process_text(
        brain,
        "Ahmed Mohamed Ali",
        mode="registration",
        session_id=session_id,
    )

    assert output.next_question == "What is your national ID or passport number?"
    assert (
        brain.registration_engine.get_form_debug_view(session_id)["current_field"]
        == "id_or_passport"
    )


def test_guided_phone_question_fills_student_mobile() -> None:
    brain = ECUBrain()
    session_id = "guided-phone-session"
    session_state = brain.registration_engine._get_or_create_session_state(session_id)
    session_state["guided_flow"] = True
    session_state["current_field"] = "student_mobile_no"
    session_state["skipped_fields"] = {
        "full_name_en",
        "full_name_ar",
        "id_or_passport",
        "country",
        "city",
        "address",
        "email_address",
    }
    output = process_text(
        brain,
        "01012345678",
        mode="registration",
        session_id=session_id,
    )

    assert output.form_updates.get("student_mobile_no") == "01012345678"


def test_guided_sensitive_phone_needs_confirmation() -> None:
    brain = ECUBrain()
    session_id = "guided-phone-confirmation-session"
    session_state = brain.registration_engine._get_or_create_session_state(session_id)
    session_state["guided_flow"] = True
    session_state["current_field"] = "student_mobile_no"
    session_state["skipped_fields"] = {
        "full_name_en",
        "full_name_ar",
        "id_or_passport",
        "country",
        "city",
        "address",
        "email_address",
    }
    output = process_text(
        brain,
        "01012345678",
        mode="registration",
        session_id=session_id,
    )

    assert output.needs_confirmation is True
    assert "confirmation_needed:student_mobile_no" in output.route_taken
    assert "confirm" in output.next_question.lower()


def test_guided_confirm_phone_moves_forward() -> None:
    brain = ECUBrain()
    session_id = "guided-confirm-phone-session"
    session_state = brain.registration_engine._get_or_create_session_state(session_id)
    session_state["guided_flow"] = True
    session_state["current_field"] = "student_mobile_no"
    session_state["skipped_fields"] = {
        "full_name_en",
        "full_name_ar",
        "id_or_passport",
        "country",
        "city",
        "address",
        "email_address",
    }
    process_text(
        brain,
        "01012345678",
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

    assert state["fields"]["student_mobile_no"]["confirmed"] is True
    assert output.next_question == "What is your school name?"
    assert state["current_field"] == "school_name"


def test_guided_skip_field_moves_to_next() -> None:
    brain = ECUBrain()
    session_id = "guided-skip-session"
    brain.registration_engine.start_guided_form(session_id=session_id, language="en")
    question = brain.registration_engine.skip_current_field(
        session_id=session_id,
        language="en",
    )
    debug_view = brain.registration_engine.get_form_debug_view(session_id)

    assert question == "What is your full name in Arabic?"
    assert debug_view["current_field"] == "full_name_ar"


def test_guided_never_asks_password_received_papers_or_auto_fields() -> None:
    brain = ECUBrain()
    guided_fields = brain.registration_engine._guided_field_order("en")
    forbidden_fields = {"password", "final_student_name", "academic_year", "final_college"}
    received_paper_fields = {
        field["field_id"]
        for field in load_registration_fields()
        if field["section"] == "Received Papers"
    }

    assert forbidden_fields.isdisjoint(guided_fields)
    assert received_paper_fields.isdisjoint(guided_fields)


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
        ("Registration fields JSON valid", test_registration_fields_json_valid),
        (
            "Registration field UI contract keys",
            test_registration_fields_have_ui_contract_keys,
        ),
        (
            "Registration no duplicate field IDs",
            test_registration_fields_no_duplicate_field_id,
        ),
        ("Registration schema sections present", test_registration_schema_sections_present),
        (
            "Registration required fields are basic voice fields only",
            test_registration_required_fields_are_basic_voice_fields_only,
        ),
        ("Registration password is UI sensitive", test_password_is_ui_and_sensitive),
        (
            "Registration received paper fields are not voice",
            test_received_paper_fields_are_not_voice,
        ),
        ("Registration final fields are auto", test_final_fields_are_auto),
        (
            "Registration export state includes metadata",
            test_export_form_state_includes_metadata,
        ),
        (
            "Registration status returns required keys",
            test_get_registration_status_required_keys,
        ),
        ("Registration auto final fields exported", test_auto_final_fields_exported),
        (
            "Registration name requirement accepts either language",
            test_registration_name_requirement_accepts_either_language,
        ),
        ("STT engine safe init", test_stt_engine_imports_and_fails_safely_without_voice),
        ("Guided form starts with first question", test_guided_start_returns_first_question),
        (
            "Guided answer fills current name field",
            test_guided_answer_first_name_fills_current_field,
        ),
        (
            "Guided next question moves forward",
            test_guided_next_question_moves_forward_after_name,
        ),
        (
            "Guided phone question fills student mobile",
            test_guided_phone_question_fills_student_mobile,
        ),
        (
            "Guided sensitive phone needs confirmation",
            test_guided_sensitive_phone_needs_confirmation,
        ),
        (
            "Guided confirm phone moves forward",
            test_guided_confirm_phone_moves_forward,
        ),
        ("Guided skip field moves forward", test_guided_skip_field_moves_to_next),
        (
            "Guided never asks password papers or auto fields",
            test_guided_never_asks_password_received_papers_or_auto_fields,
        ),
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
