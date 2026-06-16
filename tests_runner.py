"""
Small regression test runner for Admission Robot AI Brain - Updated for 24-field flow.

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


def test_guided_full_name_en_plain() -> None:
    brain = ECUBrain()
    session_id = "guided-plain-name"
    brain.registration_engine.start_guided_form(session_id, "en")
    # Force set field because start_guided_form starts with full_name_ar
    brain.registration_engine.sessions[session_id]["current_field"] = "full_name_en"
    output = process_text(brain, "Mahmoud Nagib", mode="registration", session_id=session_id)
    assert output.form_updates.get("full_name_en") == "Mahmoud Nagib"


def test_guided_full_name_en_conversational() -> None:
    brain = ECUBrain()
    session_id = "guided-conv-name"
    brain.registration_engine.sessions[session_id] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "full_name_en", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "My full name in English is Mahmoud Nagib", mode="registration", session_id=session_id)
    assert output.form_updates.get("full_name_en") == "Mahmoud Nagib"


def test_guided_full_name_ar_conversational() -> None:
    brain = ECUBrain()
    session_id = "guided-conv-name-ar"
    brain.registration_engine.start_guided_form(session_id, "ar")
    output = process_text(brain, "اسمي محمود نجيب", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("full_name_ar") == "محمود نجيب"


def test_guided_phone_extraction_conversational() -> None:
    brain = ECUBrain()
    session_id = "guided-conv-phone"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "student_mobile_no", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "My phone number is 01012345678", mode="registration", session_id=session_id)
    assert output.form_updates.get("student_mobile_no") == "01012345678"
    assert output.needs_confirmation is True


def test_guided_percentage_extraction_conversational() -> None:
    brain = ECUBrain()
    session_id = "guided-conv-perc"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "percentage", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "I got 92.5 percent", mode="registration", session_id=session_id)
    assert output.form_updates.get("percentage") == 92.5
    assert output.needs_confirmation is True


def test_guided_certificate_normalization() -> None:
    brain = ECUBrain()
    session_id = "guided-conv-cert"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "certificate", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "My certificate is American diploma", mode="registration", session_id=session_id)
    assert output.form_updates.get("certificate") == "American"


def test_id_or_passport_rejects_partial() -> None:
    brain = ECUBrain()
    session_id = "id-partial"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "305201", mode="registration", session_id=session_id)
    assert "id_or_passport" not in output.form_updates
    assert "registration_validation_failed:id_or_passport" in output.route_taken
    assert "retry" in output.next_question.lower() or "did not hear" in output.next_question.lower()


def test_id_or_passport_accepts_14_digits() -> None:
    brain = ECUBrain()
    session_id = "id-valid"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "30510201012345", mode="registration", session_id=session_id)
    assert output.form_updates.get("id_or_passport") == "30510201012345"


def test_id_or_passport_accepts_passport() -> None:
    brain = ECUBrain()
    session_id = "passport-valid"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "A1234567", mode="registration", session_id=session_id)
    assert output.form_updates.get("id_or_passport") == "A1234567"


def test_separated_digits_id() -> None:
    brain = ECUBrain()
    session_id = "sep-digits-id"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "3 0 5 1 0 2 0 1 0 1 2 3 4 5", mode="registration", session_id=session_id)
    assert output.form_updates.get("id_or_passport") == "30510201012345"


def test_separated_digits_mobile() -> None:
    brain = ECUBrain()
    session_id = "sep-digits-mobile"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "student_mobile_no", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "0 1 0 1 2 3 4 5 6 7 8", mode="registration", session_id=session_id)
    assert output.form_updates.get("student_mobile_no") == "01012345678"


def test_incomplete_mobile_rejected() -> None:
    brain = ECUBrain()
    session_id = "mobile-inc"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "student_mobile_no", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "010123", mode="registration", session_id=session_id)
    assert "student_mobile_no" not in output.form_updates
    assert "retry" in output.next_question.lower() or "did not hear" in output.next_question.lower()


def test_spoken_email_normalization() -> None:
    brain = ECUBrain()
    session_id = "spoken-email"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "email_address", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "mahmoud dot nagib zero nine at gmail dot com", mode="registration", session_id=session_id)
    assert output.form_updates.get("email_address") == "mahmoud.nagib09@gmail.com"


def test_incomplete_spoken_email_rejected() -> None:
    brain = ECUBrain()
    session_id = "spoken-email-inc"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "email_address", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "mahmoud dot nagib zero nine at", mode="registration", session_id=session_id)
    assert "email_address" not in output.form_updates
    assert "retry" in output.next_question.lower() or "could not hear" in output.next_question.lower()


def test_arabic_spoken_email_normalization() -> None:
    brain = ECUBrain()
    session_id = "spoken-email-ar"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "email_address", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "mahmoud نقطة nagib ات gmail دوت com", mode="registration", session_id=session_id)
    assert output.form_updates.get("email_address") == "mahmoud.nagib@gmail.com"


def test_invalid_id_no_overwrite() -> None:
    brain = ECUBrain()
    session_id = "id-no-overwrite"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {"id_or_passport": "30510201012345"}, "metadata": {"id_or_passport": {"confirmed": True}}, "latest_sensitive_fields": [], "current_field": "student_mobile_no", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "305201", mode="registration", session_id=session_id)
    values = brain.registration_engine.export_form_values(session_id)
    assert values.get("id_or_passport") == "30510201012345"


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


def test_college_preference_first_choice() -> None:
    brain = ECUBrain()
    output = process_text(
        brain,
        "I want engineering as first choice",
        mode="registration",
        session_id="college-first-session",
    )

    assert output.form_updates.get("college_preference_1") == "engineering_and_technology"


def test_registration_fields_json_valid() -> None:
    fields = load_registration_fields()
    assert fields, "registration_fields.json should contain fields"


def test_registration_schema_sections_present() -> None:
    fields = load_registration_fields()
    sections = {field["section"] for field in fields}

    assert "Personal Data" in sections
    assert "Contact" in sections
    assert "Academic" in sections
    assert "Guardian" in sections
    assert "Faculty" in sections


def test_registration_schema_counts() -> None:
    fields = load_registration_fields()
    # 24 guided fields + 3 auto fields = 27
    assert len(fields) == 27, f"Expected 27 fields, got {len(fields)}"

    sections = {}
    for f in fields:
        sections[f["section"]] = sections.get(f["section"], 0) + 1
        
    assert sections["Personal Data"] == 8
    assert sections["Contact"] == 5
    assert sections["Academic"] == 4
    assert sections["Guardian"] == 6
    assert sections["Faculty"] == 1


def test_guided_voice_field_count() -> None:
    brain = ECUBrain()
    guided_order = brain.registration_engine._guided_field_order("en")
    assert len(guided_order) == 24


def test_guided_voice_order() -> None:
    brain = ECUBrain()
    guided_order = brain.registration_engine._guided_field_order("en")
    
    assert guided_order[0] == "full_name_ar"
    assert guided_order[1] == "full_name_en"
    assert guided_order[-1] == "college_preference_1"


def test_guided_start_returns_first_question() -> None:
    brain = ECUBrain()
    question = brain.registration_engine.start_guided_form(
        session_id="guided-start-session",
        language="en",
    )
    assert question == "What is your full name in Arabic?"


def test_guardian_address_same_as_me() -> None:
    brain = ECUBrain()
    session_id = "same-address-session"
    # Fill student address first
    process_text(brain, "My address is 123 Main St", mode="registration", session_id=session_id)
    
    # Set current field to guardian_address
    brain.registration_engine.sessions[session_id]["current_field"] = "guardian_address"
    brain.registration_engine.sessions[session_id]["guided_flow"] = True
    
    output = process_text(brain, "same as my address", mode="registration", session_id=session_id)
    assert output.form_updates.get("guardian_address") == "123 Main St"


def test_governorate_normalization() -> None:
    brain = ECUBrain()
    
    session_id_1 = "gov-norm-en"
    brain.registration_engine.sessions[session_id_1] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "governorate", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "I live in Cairo", mode="registration", session_id=session_id_1)
    gov = output.form_updates.get("governorate")
    assert gov == "Cairo", f"Expected Cairo, got {gov}"
    
    session_id_2 = "gov-norm-ar"
    brain.registration_engine.sessions[session_id_2] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "governorate", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "ساكن في الجيزة", mode="registration", session_id=session_id_2, language="ar")
    gov = output.form_updates.get("governorate")
    assert gov == "Giza", f"Expected Giza, got {gov}"


def test_stt_engine_imports_and_fails_safely_without_voice() -> None:
    stt_engine = STTEngine()
    assert stt_engine.is_available() is False


def test_guided_order_after_full_name_ar_next_is_full_name_en() -> None:
    brain = ECUBrain()
    session_id = "guided-order-1"
    brain.registration_engine.start_guided_form(session_id, "ar")
    output = process_text(brain, "محمود نجيب", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("full_name_ar") == "محمود نجيب"
    assert output.next_question == brain.registration_engine.prompts["full_name_en"]["ar"]

def test_guided_order_after_full_name_en_next_is_date_of_birth() -> None:
    brain = ECUBrain()
    session_id = "guided-order-2"
    brain.registration_engine.start_guided_form(session_id, "en")
    # Set full_name_ar as filled
    brain.registration_engine.sessions[session_id]["fields"]["full_name_ar"] = "محمود نجيب"
    brain.registration_engine.sessions[session_id]["current_field"] = "full_name_en"
    
    output = process_text(brain, "Mahmoud Nagib", mode="registration", session_id=session_id)
    assert output.form_updates.get("full_name_en") == "Mahmoud Nagib"
    assert output.next_question == brain.registration_engine.prompts["date_of_birth"]["en"]

def test_date_of_birth_accepts_formats() -> None:
    brain = ECUBrain()
    
    # DD/MM/YYYY
    session_id_1 = "dob-test-1"
    brain.registration_engine.sessions[session_id_1] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "15/08/2005", mode="registration", session_id=session_id_1)
    dob = output.form_updates.get("date_of_birth")
    assert dob == "2005-08-15", f"Expected 2005-08-15, got {dob}"
    
    # DD-MM-YYYY
    session_id_2 = "dob-test-2"
    brain.registration_engine.sessions[session_id_2] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "15-08-2005", mode="registration", session_id=session_id_2)
    dob = output.form_updates.get("date_of_birth")
    assert dob == "2005-08-15", f"Expected 2005-08-15, got {dob}"

def test_invalid_date_does_not_advance() -> None:
    brain = ECUBrain()
    session_id = "dob-invalid"
    brain.registration_engine.sessions[session_id] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()}
    
    output = process_text(brain, "35/08/2005", mode="registration", session_id=session_id)
    assert "date_of_birth" not in output.form_updates
    assert brain.registration_engine.sessions[session_id]["current_field"] == "date_of_birth"

def test_strict_field_priority_prevents_leakage() -> None:
    brain = ECUBrain()
    session_id = "leakage-test"
    brain.registration_engine.sessions[session_id] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()}
    
    # Input meant for ID, should not fill certificate or ID while waiting for DOB
    output = process_text(brain, "30510201012345", mode="registration", session_id=session_id)
    assert "date_of_birth" not in output.form_updates
    assert "certificate" not in output.form_updates
    assert "id_or_passport" not in output.form_updates

def test_guardian_profession_priority() -> None:
    brain = ECUBrain()
    session_id = "prof-priority"
    brain.registration_engine.sessions[session_id] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "guardian_profession", "guided_flow": True, "skipped_fields": set()}
    
    output = process_text(brain, "مهندس", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("guardian_profession") == "مهندس"
    assert "guardian_name" not in output.form_updates

def test_while_current_field_date_of_birth_do_not_fill_certificate_from_14_digit_id() -> None:
    brain = ECUBrain()
    session_id = "leakage-cert-test"
    brain.registration_engine.sessions[session_id] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()}
    
    # Input meant for ID, should not fill certificate
    output = process_text(brain, "30510201012345", mode="registration", session_id=session_id)
    assert "certificate" not in output.form_updates
    assert brain.registration_engine.sessions[session_id]["current_field"] == "date_of_birth"

def test_sensitive_fields_still_require_confirmation() -> None:
    brain = ECUBrain()
    session_id = "sens-confirm"
    brain.registration_engine.sessions[session_id] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()}
    
    output = process_text(brain, "30510201012345", mode="registration", session_id=session_id)
    assert output.form_updates.get("id_or_passport") == "30510201012345"
    assert output.needs_confirmation is True

def test_confirmation_advances_to_next_field() -> None:
    brain = ECUBrain()
    session_id = "conf-advance"
    brain.registration_engine.sessions[session_id] = {
        "fields": {"id_or_passport": "30510201012345"}, 
        "metadata": {"id_or_passport": {"confirmed": False, "needs_confirmation": True}}, 
        "latest_sensitive_fields": ["id_or_passport"], 
        "current_field": "id_or_passport", 
        "guided_flow": True, 
        "skipped_fields": {"full_name_ar", "full_name_en", "date_of_birth", "place_of_birth", "nationality"}
    }
    
    output = process_text(brain, "نعم", mode="registration", session_id=session_id, language="ar")
    assert output.needs_confirmation is False
    # Next field after id_or_passport (6) is gender (7)
    assert brain.registration_engine.sessions[session_id]["current_field"] == "gender"

def main() -> int:
    tests = [
        ("QA FAQ", test_qa_faq),
        ("QA KB/RAG", test_qa_kb_rag),
        ("QA no source", test_qa_no_source),
        ("Registration English", test_registration_english),
        ("Registration Arabic", test_registration_arabic),
        ("Registration schema counts", test_registration_schema_counts),
        ("Registration schema sections present", test_registration_schema_sections_present),
        ("Guided voice field count is 24", test_guided_voice_field_count),
        ("Guided voice order", test_guided_voice_order),
        ("Guided start returns first question", test_guided_start_returns_first_question),
        ("Guided order: after name_ar is name_en", test_guided_order_after_full_name_ar_next_is_full_name_en),
        ("Guided order: after name_en is DOB", test_guided_order_after_full_name_en_next_is_date_of_birth),
        ("Date of birth formats", test_date_of_birth_accepts_formats),
        ("Invalid date stays on field", test_invalid_date_does_not_advance),
        ("Strict priority prevents leakage", test_strict_field_priority_prevents_leakage),
        ("Leakage: ID does not fill certificate", test_while_current_field_date_of_birth_do_not_fill_certificate_from_14_digit_id),
        ("Sensitive fields require confirmation", test_sensitive_fields_still_require_confirmation),
        ("Confirmation advances to next field", test_confirmation_advances_to_next_field),
        ("Guardian profession priority", test_guardian_profession_priority),
        ("Guardian address same as me", test_guardian_address_same_as_me),
        ("Governorate normalization", test_governorate_normalization),
        ("Spoken email normalization", test_spoken_email_normalization),
        ("Arabic spoken email normalization", test_arabic_spoken_email_normalization),
        ("ID accepts 14 digits", test_id_or_passport_accepts_14_digits),
        ("Separated digits mobile normalized", test_separated_digits_mobile),
        ("Confirm marks sensitive fields confirmed", test_confirm_marks_sensitive_fields_confirmed),
    ]
    results = [run_test(name, check) for name, check in tests]
    passed = sum(1 for result in results if result)
    total = len(results)

    print("-" * 70)
    print(f"Summary: {passed}/{total} passed")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
