# Admission Robot — ECU Admission AI Brain

## Overview

* This is the standalone Python AI Brain for the ECU Admission Robot.
* It supports **QA mode** and **registration mode**.
* It receives text or STT transcript and returns structured output.
* It is not a Flask/FastAPI backend.
* A backend developer can import `AdmissionBrainService` from `brain_service.py`.

## Project Responsibilities

This repository is responsible for AI Brain logic.
It handles:
* Registration flow (39 guided fields)
* Field extraction and normalization
* Validation (Mobile, ID, Dates, etc.)
* Confirmation logic
* QA routing (FAQs and Knowledge Base)
* Frontend-ready export (camelCase)

It does **NOT** handle:
* Flask/FastAPI routes
* Frontend UI
* Database persistence
* Robot navigation
* Deployment server

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

## Environment Setup

1. Copy `.env.example` to `.env`.
2. Configure your API keys and provider settings.

**Important Variables:**
* `LLM_PROVIDER`: `groq` or `openai`
* `GROQ_API_KEY`: Required if using Groq
* `OPENAI_API_KEY`: Required if using OpenAI
* `ENABLE_LLM_REGISTRATION_EXTRACTION`: `True`/`False`
* `ENABLE_TTS`: Enable/Disable local speech output
* `TTS_PROVIDER`: `edge-tts` (recommended)
* `STT_PROVIDER`: `deepgram` (recommended)
* `DEEPGRAM_API_KEY`: Required for STT

> **Note:** Do not commit real `.env` files. Keep API keys private.

## Running Locally (Terminal Demo)

```bash
python main.py
```

**Useful Commands:**
* `lang ar` / `lang en`: Switch language
* `mode qa` / `mode registration`: Switch mode
* `start form`: Start the registration wizard
* `listen` / `voice`: Trigger microphone input
* `show form`: View current registration values
* `export form`: View frontend-ready JSON export
* `status form`: View completion percentage

## Service Layer Integration

Import `AdmissionBrainService` to integrate the Brain into your backend.

```python
from brain_service import AdmissionBrainService

service = AdmissionBrainService()

# 1. Create a session for a new user
session = service.create_session()
session_id = session["session_id"]

# 2. Configure session
service.set_language(session_id, "ar")
service.set_mode(session_id, "registration")

# 3. Start registration
response = service.start_registration(session_id)
print(response["answer_text"]) # "ما هو اسمك بالكامل؟"

# 4. Submit answers
response = service.submit_registration_answer(session_id, "محمود محمد نجيب")
print(response["answer_text"]) # Next question...

# 5. Get current state
status = service.get_form_status(session_id)
frontend_values = service.get_form_values_frontend(session_id)
```

## Flask Backend Integration Example

This is a documentation-only example showing how to wrap the service in a Flask API.

```python
from flask import Flask, request, jsonify
from brain_service import AdmissionBrainService

app = Flask(__name__)
brain = AdmissionBrainService()

@app.post("/sessions")
def create_session():
    result = brain.create_session()
    return jsonify(result)

@app.post("/brain/process")
def process_text():
    data = request.get_json()
    session_id = data["session_id"]
    text = data["text"]
    result = brain.process_text(session_id, text)
    return jsonify(result)

@app.post("/registration/start")
def start_registration():
    data = request.get_json()
    result = brain.start_registration(data["session_id"])
    return jsonify(result)

@app.post("/registration/answer")
def answer_registration():
    data = request.get_json()
    result = brain.submit_registration_answer(data["session_id"], data["answer"])
    return jsonify(result)

@app.get("/registration/status/<session_id>")
def registration_status(session_id):
    return jsonify(brain.get_form_status(session_id))

@app.get("/registration/export/frontend/<session_id>")
def registration_export_frontend(session_id):
    return jsonify(brain.get_form_values_frontend(session_id))
```

## Recommended Backend Endpoint Mapping

| Backend Endpoint                        | Brain Service Method       |
| --------------------------------------- | -------------------------- |
| POST /sessions                          | create_session             |
| POST /sessions/{id}/language            | set_language               |
| POST /sessions/{id}/mode                | set_mode                   |
| POST /brain/process                     | process_text               |
| POST /brain/voice-transcript            | process_voice_transcript   |
| POST /registration/start                | start_registration         |
| POST /registration/answer               | submit_registration_answer |
| GET /registration/status/{id}           | get_form_status            |
| GET /registration/export/{id}           | get_form_values            |
| GET /registration/export/frontend/{id}  | get_form_values_frontend   |
| GET /registration/current-question/{id} | get_current_question       |
| GET /registration/field-order           | get_field_order            |
| GET /health                             | health_check               |

## Response Shape (BrainOutput)

Methods like `process_text` return a structured dictionary containing:
* `mode`: Current session mode (`qa` or `registration`)
* `answer_text`: The text response to display on screen
* `speech_text`: The text version optimized for TTS
* `confidence`: 0.0 to 1.0 confidence score
* `current_topic`: Detected topic (e.g., `fees`, `location`)
* `form_updates`: Key-value pairs of extracted registration fields
* `next_question`: The next guided registration question (if in registration mode)
* `needs_confirmation`: Boolean indicating if the last extraction needs user confirmation
* `route_taken`: List of internal logic steps for debugging

## Registration Flow Summary

* **39 guided fields**: One field at a time.
* **Double Confirmation**: Every critical field requires confirmation.
* **Smart Name Intake**: Name is asked once and fills both Arabic and English names via phonetic transliteration.
* **Location Handling**: Address fields are normalized to Arabic.
* **Date Normalization**: All dates are normalized to `YYYY-MM-DD`.
* **Strict Validation**: Mobile (11 digits), National ID (14 digits), and email formats are strictly checked.
* **Frontend Export**: Uses `camelCase` keys for easier JS integration.

## Registration Export

The service provides two ways to export the registration form data:

* `get_form_values(session_id)`: Returns internal `snake_case` keys. Best for debugging or Python-side tools.
* `get_form_values_frontend(session_id)`: Returns `camelCase` keys. **Recommended** for handoff to the frontend/UI.

Example export:
```json
{
  "fullNameAr": "محمود محمد نجيب",
  "fullNameEn": "Mahmoud Mohamed Naguib",
  "mobile": "01234567890",
  "nationalId": "12345678901234"
}
```

## Data Files

* `data/registration_fields.json`: Field definitions and questions.
* `data/name_lexicon.json`: Phonetic name database.
* `data/faqs.json`: Fast-path FAQ answers.
* `data/faculties/`: Detailed faculty-specific information.

## Testing

```bash
# Run all core tests
python tests_runner.py

# Specialized logic tests
python transliteration_tests.py
python numeric_date_tests.py
python confirmation_location_tests.py

# Simulation test
python fake_registration_text_test.py --delay 0.5
```

## Notes for Backend Developer

* Keep **one instance** of `AdmissionBrainService` alive in your application.
* Use `session_id` to maintain context for different users.
* **Do not call `main.py`** from Flask; import `brain_service.py` directly.
* Store final exported form values in your own database; the Brain memory is short-term (RAM).
* Backend should pass user transcripts directly into `process_text` or `submit_registration_answer`.

## Troubleshooting

* **Missing API key**: Ensure `.env` is correctly configured.
* **TTS/STT Errors**: Check internet connection and API quotas (Deepgram/Edge-TTS).
* **PyAudio Errors**: Ensure your microphone is connected and the `DEVICE_INDEX` in `config.py` matches your hardware.
* **Arabic Display**: If the terminal shows broken Arabic, ensure you use a font that supports RTL/Arabic (e.g., Cascadia Code).
