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


import unittest
from confirmation_location_tests import TestUniversalConfirmation, TestArabicLocationStorage

def run_unittest_suite(test_class):
    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    return result.wasSuccessful()

def run_test(name: str, check) -> bool:
    try:
        check()
    except AssertionError as error:
        import traceback
        print(f"FAIL: {name}")
        traceback.print_exc()
        return False
    except Exception as error:
        import traceback
        print(f"FAIL: {name} - unexpected error:")
        traceback.print_exc()
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
        "and my email is ahmed@test.com",
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

    assert output.form_updates.get("full_name_ar") == "أحمد محمد"
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

    assert output.form_updates.get("full_name_ar") == "أحمد محمد علي"
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
    assert output.form_updates.get("certificate") == "American Diploma"


def test_id_or_passport_rejects_partial() -> None:
    brain = ECUBrain()
    session_id = "id-partial"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "305201", mode="registration", session_id=session_id)
    assert "id_or_passport" not in output.form_updates
    assert "registration_validation_failed:id_or_passport" in output.route_taken
    assert "retry" in output.next_question.lower() or "الرقم القومي" in output.next_question


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
    assert "retry" in output.next_question.lower() or "رقم موبايل" in output.next_question


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
    assert "retry" in output.next_question.lower() or "البريد الإلكتروني" in output.next_question


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
        "my email is wrong, change it to new@test.com",
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
    # 39 guided fields + 3 auto fields = 42
    assert len(fields) == 42, f"Expected 42 fields, got {len(fields)}"

    sections = {}
    for f in fields:
        sections[f["section"]] = sections.get(f["section"], 0) + 1
        
    assert sections["Personal Data"] == 8
    assert sections["Contact"] == 9
    assert sections["Academic"] == 7
    assert sections["Guardian"] == 14
    assert sections["Faculty"] == 1


def test_guided_voice_field_count() -> None:
    brain = ECUBrain()
    guided_order = brain.registration_engine._guided_field_order("en")
    assert len(guided_order) == 39


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
    assert "Please say your full name" in question


def test_guardian_address_same_as_me() -> None:
    brain = ECUBrain()
    session_id = "same-address-session"
    # Fill student address first (using Arabic to ensure it's saved)
    process_text(brain, "عنواني 20 شارع النصر", mode="registration", session_id=session_id, language="ar")
    
    # Set current field to guardian_address
    brain.registration_engine.sessions[session_id]["current_field"] = "guardian_address"
    brain.registration_engine.sessions[session_id]["guided_flow"] = True
    
    output = process_text(brain, "نفس عنواني", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("guardian_address") == "20 شارع النصر"


def test_governorate_normalization() -> None:
    brain = ECUBrain()
    
    session_id_1 = "gov-norm-en"
    brain.registration_engine.sessions[session_id_1] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "governorate", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "I live in Cairo", mode="registration", session_id=session_id_1)
    gov = output.form_updates.get("governorate")
    assert gov == "القاهرة", f"Expected القاهرة, got {gov}"
    
    session_id_2 = "gov-norm-ar"
    brain.registration_engine.sessions[session_id_2] = {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "governorate", "guided_flow": True, "skipped_fields": set()}
    output = process_text(brain, "ساكن في الجيزة", mode="registration", session_id=session_id_2, language="ar")
    gov = output.form_updates.get("governorate")
    assert gov == "الجيزة", f"Expected الجيزة, got {gov}"


def test_stt_engine_imports_and_fails_safely_without_voice() -> None:
    stt_engine = STTEngine()
    assert stt_engine.is_available() is False


def test_guided_order_after_full_name_ar_next_is_date_of_birth() -> None:
    brain = ECUBrain()
    session_id = "guided-order-1"
    brain.registration_engine.start_guided_form(session_id, "ar")
    output = process_text(brain, "محمود محمد نجيب", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("full_name_ar") == "محمود محمد نجيب"
    # New behavior: both names filled, skip full_name_en
    assert output.form_updates.get("full_name_en") == "Mahmoud Mohamed Nagib"
    assert output.needs_confirmation is True
    assert "محمود محمد نجيب" in output.next_question
    assert "Mahmoud Mohamed Nagib" in output.next_question


def test_name_intake_english_phrase_extracts_name_only() -> None:
    brain = ECUBrain()
    session_id = "name-intake-phrase"
    brain.registration_engine.start_guided_form(session_id, "en")
    output = process_text(brain, "My full name in Arabic is Mahmoud Ahmed Nagib", mode="registration", session_id=session_id)
    assert output.form_updates.get("full_name_en") == "Mahmoud Ahmed Nagib"
    assert output.form_updates.get("full_name_ar") == "محمود أحمد نجيب"


def test_name_intake_arabic_script_english_phrase_extracts_name_only() -> None:
    brain = ECUBrain()
    session_id = "name-intake-ar-script-en"
    brain.registration_engine.start_guided_form(session_id, "ar")
    # "ماي فول ني من أربيك إذ محمود أحمد نجيب"
    output = process_text(brain, "ماي فول ني من أربيك إذ محمود أحمد نجيب", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("full_name_ar") == "محمود أحمد نجيب"
    assert output.form_updates.get("full_name_en") == "Mahmoud Ahmed Nagib"


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


def test_invalid_short_national_id_is_rejected() -> None:
    brain = ECUBrain()
    session_id = "id-short"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "3051020", mode="registration", session_id=session_id)
    assert "id_or_passport" not in output.form_updates
    assert "14 digits" in output.next_question


def test_valid_14_digit_national_id_is_accepted_and_requires_confirmation() -> None:
    brain = ECUBrain()
    session_id = "id-14-valid"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "id_or_passport", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "30510201012345", mode="registration", session_id=session_id)
    assert output.form_updates.get("id_or_passport") == "30510201012345"
    assert output.needs_confirmation is True


def test_invalid_phone_too_short_is_rejected() -> None:
    brain = ECUBrain()
    session_id = "phone-short"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "student_mobile_no", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "010123", mode="registration", session_id=session_id)
    assert "student_mobile_no" not in output.form_updates
    assert "11 digits" in output.next_question


def test_valid_egyptian_mobile_is_accepted_and_requires_confirmation() -> None:
    brain = ECUBrain()
    session_id = "phone-valid"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "student_mobile_no", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "01012345678", mode="registration", session_id=session_id)
    assert output.form_updates.get("student_mobile_no") == "01012345678"
    assert output.needs_confirmation is True


def test_invalid_email_incomplete_is_rejected() -> None:
    brain = ECUBrain()
    session_id = "email-inc"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "email_address", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "mahmoud at gmail", mode="registration", session_id=session_id)
    assert "email_address" not in output.form_updates
    assert "incomplete" in output.next_question or "incorrect" in output.next_question


def test_spoken_email_is_normalized_and_validated() -> None:
    brain = ECUBrain()
    session_id = "email-spoken-norm"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "email_address", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "mahmoud dot nagib zero nine at gmail dot com", mode="registration", session_id=session_id)
    assert output.form_updates.get("email_address") == "mahmoud.nagib09@gmail.com"


def test_date_slash_format_normalizes_to_iso_hard() -> None:
    brain = ECUBrain()
    session_id = "date-norm-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "15/08/2005", mode="registration", session_id=session_id)
    assert output.form_updates.get("date_of_birth") == "2005-08-15"


def test_future_date_is_rejected_hard() -> None:
    brain = ECUBrain()
    session_id = "date-future-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "date_of_birth", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "15/08/2030", mode="registration", session_id=session_id)
    assert "date_of_birth" not in output.form_updates
    assert "unclear" in output.next_question or "تاريخ الميلاد" in output.next_question


def test_percentage_above_100_is_rejected_hard() -> None:
    brain = ECUBrain()
    session_id = "perc-above-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "percentage", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "105", mode="registration", session_id=session_id)
    assert "percentage" not in output.form_updates
    assert "0 to 100" in output.next_question


def test_percentage_valid_requires_confirmation_hard() -> None:
    brain = ECUBrain()
    session_id = "perc-valid-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "percentage", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "92.5", mode="registration", session_id=session_id)
    assert output.form_updates.get("percentage") == 92.5
    assert output.needs_confirmation is True


def test_misspelled_governorate_cairo_normalizes_hard() -> None:
    brain = ECUBrain()
    session_id = "gov-miss-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "governorate", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "القاهره", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("governorate") == "القاهرة"


def test_certificate_arabic_thanaweya_normalizes_hard() -> None:
    brain = ECUBrain()
    session_id = "cert-ar-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "certificate", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "ثانوية عامة", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("certificate") == "Thanaweya Amma"


def test_relationship_arabic_father_normalizes_hard() -> None:
    brain = ECUBrain()
    session_id = "rel-ar-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "relationship", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "الأب", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("relationship") == "Father"

def test_guardian_profession_rejects_relationship_word_hard() -> None:
    brain = ECUBrain()
    session_id = "prof-reject-rel-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "guardian_profession", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "الأب", mode="registration", session_id=session_id, language="ar")
    assert "guardian_profession" not in output.form_updates, f"Expected rejection, got updates: {output.form_updates}"
    assert "أحتاج وظيفة" in str(output.next_question), f"Expected retry prompt, got: {output.next_question}"


def test_guardian_nationality_rejects_profession_word_hard() -> None:
    brain = ECUBrain()
    session_id = "nat-reject-prof-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "guardian_nationality", "guided_flow": True, "skipped_fields": set()})
    # Input is job title but field is nationality
    output = process_text(brain, "مهندس", mode="registration", session_id=session_id, language="ar")
    assert "guardian_nationality" not in output.form_updates, f"Expected rejection, got updates: {output.form_updates}"
    assert "أحتاج جنسية" in str(output.next_question), f"Expected retry prompt, got: {output.next_question}"


def test_guardian_address_same_as_address_copies_student_address_hard() -> None:
    brain = ECUBrain()
    session_id = "addr-copy-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {"address": "20 شارع نجاتي سراج"}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "guardian_address", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "نفس العنوان", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("guardian_address") == "20 شارع نجاتي سراج"


def test_current_field_only_prevents_extra_llm_fields_hard() -> None:
    brain = ECUBrain()
    session_id = "strict-field-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "city", "guided_flow": True, "skipped_fields": set()})
    # Input has city AND name. Should only fill city.
    output = process_text(brain, "مدينة نصر واسمي محمود", mode="registration", session_id=session_id, language="ar")
    assert "full_name_ar" not in output.form_updates


def test_college_preference_1_does_not_fill_college_preference_2_hard() -> None:
    brain = ECUBrain()
    session_id = "pref-1-only-hard"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "college_preference_1", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "هندسة", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("college_preference_1") == "engineering_and_technology"
    assert "college_preference_2" not in output.form_updates


def test_fake_full_39_field_flow_completes() -> None:
    # This is a meta-test, we'll just check if we can run it or if it passes
    import subprocess
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run([sys.executable, "fake_registration_text_test.py", "--delay", "0"], capture_output=True, env=env)
    assert result.returncode == 0, f"Script failed with code {result.returncode}, stderr: {result.stderr.decode('utf-8', errors='replace')}"
    # Search for completion success in logs or stdout
    output = result.stdout.decode('utf-8', errors='replace')
    assert '"is_basic_registration_complete": true' in output or '"is_basic_registration_complete": True' in output, f"Completion not found in output: {output[-500:]}"


def test_export_contains_only_39_fields_plus_auto_fields() -> None:
    brain = ECUBrain()
    session_id = "export-limit-hard"
    # Set current field to ensure extraction works for single word
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "full_name_ar", "guided_flow": True, "skipped_fields": set()})
    # Fill some fields
    process_text(brain, "محمود محمد", mode="registration", session_id=session_id, language="ar") # name_ar
    # Add a legacy field manually to form_state
    brain.registration_engine.sessions[session_id]["fields"]["college_preference_2"] = "pharmacy"
    
    exported = brain.registration_engine.export_form_values(session_id)
    assert "full_name_ar" in exported, f"Missing full_name_ar in {exported}, schema ids: {[f['field_id'] for f in brain.registration_engine.field_definitions]}"
    assert "college_preference_2" not in exported, f"Leaked legacy field in {exported}"

def test_frontend_camel_case_export() -> None:
    brain = ECUBrain()
    session_id = "camel-export"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {"full_name_ar": "محمود محمد", "college_preference_1": "engineering_and_technology"}, "metadata": {}, "latest_sensitive_fields": [], "current_field": None, "guided_flow": False, "skipped_fields": set()})
    
    exported = brain.registration_engine.export_form_values_frontend(session_id)
    assert exported.get("fullNameAr") == "محمود محمد"
    assert exported.get("faculty") == "engineering_and_technology"
    assert "full_name_ar" not in exported

def test_sector_normalization_science() -> None:
    brain = ECUBrain()
    session_id = "sector-sci"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "sector", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "علمي علوم", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("sector") == "science"

def test_sector_normalization_math() -> None:
    brain = ECUBrain()
    session_id = "sector-math"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "sector", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "رياضة", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("sector") == "math"

def test_total_marks_validation() -> None:
    brain = ECUBrain()
    session_id = "marks-val"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "total_marks", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "385", mode="registration", session_id=session_id)
    assert output.form_updates.get("total_marks") == 385.0
    assert output.needs_confirmation is True

def test_mobile_no_2_validation() -> None:
    brain = ECUBrain()
    session_id = "mob2-val"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "mobile_no_2", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "01123456789", mode="registration", session_id=session_id)
    assert output.form_updates.get("mobile_no_2") == "01123456789"
    assert output.needs_confirmation is True

def test_guardian_home_phone_validation() -> None:
    brain = ECUBrain()
    session_id = "ghome-val"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "guardian_home_phone", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "0223456789", mode="registration", session_id=session_id)
    assert output.form_updates.get("guardian_home_phone") == "0223456789"
    assert output.needs_confirmation is True

def test_arabic_name_prefix_is_cleaned_1() -> None:
    brain = ECUBrain()
    session_id = "ar-name-clean-1"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "full_name_ar", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "إسمي هو عمر أحمد جودة", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("full_name_ar") == "عمر أحمد جودة", f"Prefix not cleaned properly: {output.form_updates}"

def test_arabic_name_prefix_is_cleaned_2() -> None:
    brain = ECUBrain()
    session_id = "ar-name-clean-2"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "full_name_ar", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "انا اسمي محمود محمد نجيب", mode="registration", session_id=session_id, language="ar")
    assert output.form_updates.get("full_name_ar") == "محمود محمد نجيب", f"Prefix not cleaned properly: {output.form_updates}"

def test_arabic_input_for_english_name_rejected() -> None:
    brain = ECUBrain()
    session_id = "en-name-reject-ar"
    brain.registration_engine.sessions.setdefault(session_id, {"fields": {}, "metadata": {}, "latest_sensitive_fields": [], "current_field": "full_name_en", "guided_flow": True, "skipped_fields": set()})
    output = process_text(brain, "عمر أحمد جودة", mode="registration", session_id=session_id, language="en")
    assert "full_name_en" not in output.form_updates, f"Arabic text accepted for English name: {output.form_updates}"
    assert "English letters" in str(output.next_question) or "بحروف إنجليزية" in str(output.next_question), f"Wrong retry prompt: {output.next_question}"

def main() -> int:
    tests = [
        ("QA FAQ", test_qa_faq),
        ("QA KB/RAG", test_qa_kb_rag),
        ("QA no source", test_qa_no_source),
        ("Registration English", test_registration_english),
        ("Registration Arabic", test_registration_arabic),
        ("Registration schema counts", test_registration_schema_counts),
        ("Registration schema sections present", test_registration_schema_sections_present),
        ("Guided voice field count is 39", test_guided_voice_field_count),
        ("Guided voice order", test_guided_voice_order),
        ("Guided start returns first question", test_guided_start_returns_first_question),
        ("Guided order: after name_ar is DOB", test_guided_order_after_full_name_ar_next_is_date_of_birth),
        ("Name intake: English phrase", test_name_intake_english_phrase_extracts_name_only),
        ("Name intake: Arabic script EN phrase", test_name_intake_arabic_script_english_phrase_extracts_name_only),
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
        
        # New Hardening Tests
        ("Invalid short ID rejected", test_invalid_short_national_id_is_rejected),
        ("Valid 14-digit ID accepted", test_valid_14_digit_national_id_is_accepted_and_requires_confirmation),
        ("Invalid phone too short rejected", test_invalid_phone_too_short_is_rejected),
        ("Valid mobile accepted", test_valid_egyptian_mobile_is_accepted_and_requires_confirmation),
        ("Invalid email rejected", test_invalid_email_incomplete_is_rejected),
        ("Spoken email norm & val", test_spoken_email_is_normalized_and_validated),
        ("Date slash norm to ISO (Hardening)", test_date_slash_format_normalizes_to_iso_hard),
        ("Future date rejected (Hardening)", test_future_date_is_rejected_hard),
        ("Percentage > 100 rejected (Hardening)", test_percentage_above_100_is_rejected_hard),
        ("Percentage valid & confirm (Hardening)", test_percentage_valid_requires_confirmation_hard),
        ("Misspelled gov normalizes (Hardening)", test_misspelled_governorate_cairo_normalizes_hard),
        ("Cert Arabic Thanaweya normalizes (Hardening)", test_certificate_arabic_thanaweya_normalizes_hard),
        ("Rel Arabic Father normalizes (Hardening)", test_relationship_arabic_father_normalizes_hard),
        ("Guardian profession rejects relationship (Hardening)", test_guardian_profession_rejects_relationship_word_hard),
        ("Guardian nationality rejects profession (Hardening)", test_guardian_nationality_rejects_profession_word_hard),
        ("Guardian address same as student (Hardening)", test_guardian_address_same_as_address_copies_student_address_hard),
        ("Strict field prevents LLM leakage (Hardening)", test_current_field_only_prevents_extra_llm_fields_hard),
        ("Pref 1 does not fill Pref 2 (Hardening)", test_college_preference_1_does_not_fill_college_preference_2_hard),
        ("Arabic prefix cleaned 1", test_arabic_name_prefix_is_cleaned_1),
        ("Arabic prefix cleaned 2", test_arabic_name_prefix_is_cleaned_2),
        ("Arabic input for EN name rejected", test_arabic_input_for_english_name_rejected),
        
        # 39-field specific tests
        ("Sector normalization Science", test_sector_normalization_science),
        ("Sector normalization Math", test_sector_normalization_math),
        ("Total marks validation", test_total_marks_validation),
        ("Mobile No 2 validation", test_mobile_no_2_validation),
        ("Guardian home phone validation", test_guardian_home_phone_validation),
        ("Frontend camelCase export", test_frontend_camel_case_export),
        ("Export limit to 39 + auto", test_export_contains_only_39_fields_plus_auto_fields),
        ("Full 39-field flow still completes", test_fake_full_39_field_flow_completes),
        ("Universal Confirmation Suite", lambda: run_unittest_suite(TestUniversalConfirmation)),
        ("Arabic Location Storage Suite", lambda: run_unittest_suite(TestArabicLocationStorage)),
    ]
    results = [run_test(name, check) for name, check in tests]
    passed = sum(1 for result in results if result)
    total = len(results)

    print("-" * 70)
    print(f"Summary: {passed}/{total} passed")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
