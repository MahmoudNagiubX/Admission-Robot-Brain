from brain_service import AdmissionBrainService
import json

def test_service():
    service = AdmissionBrainService()
    
    print("\n--- Testing Service Layer ---")
    
    # 1. Health check
    print(f"Health check: {service.health_check()}")
    
    # 2. Create session
    session = service.create_session()
    session_id = session["session_id"]
    print(f"Created session: {session_id}")
    
    # 3. Set language and mode
    service.set_language(session_id, "ar")
    service.set_mode(session_id, "registration")
    print(f"Language set to 'ar', mode set to 'registration'")
    
    # 4. Start registration
    response = service.start_registration(session_id)
    print(f"Start registration response: {response['answer_text']}")
    
    # 5. Submit an answer
    response = service.submit_registration_answer(session_id, "محمود محمد نجيب")
    print(f"Submit answer response: {response['answer_text']}")
    
    # 6. Get form status
    status = service.get_form_status(session_id)
    print(f"Form status: {status['completion_percentage']}% complete")
    
    # 7. Get field order
    order = service.get_field_order()
    print(f"Field order count: {len(order)}")
    
    # 8. Export frontend values
    frontend_values = service.get_form_values_frontend(session_id)
    print(f"Frontend values: {json.dumps(frontend_values, ensure_ascii=False)}")
    
    # 9. Test missing methods added
    print(f"Review form: {service.review_form(session_id)}")
    print(f"Field profiles count: {len(service.get_field_profiles())}")
    print(f"KB validation report length: {len(service.validate_knowledge_base())}")
    
    print("\n--- Service Layer Verification PASS ---")

if __name__ == "__main__":
    test_service()
