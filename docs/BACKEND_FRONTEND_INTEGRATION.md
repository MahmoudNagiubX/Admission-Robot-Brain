# Backend Frontend Integration

## Architecture

```text
Frontend -> Flask Backend -> AdmissionBrainService -> AI Brain
```

The frontend owns the registration wizard UI. The Flask backend owns HTTP,
authentication, persistence, and serving media. The AI Brain owns QA,
registration extraction, validation, normalization, confirmation, and manual
fallback.

## Session Lifecycle

1. Backend creates a service session with `create_session()`.
2. Frontend displays one field and sends transcript plus `field_id`.
3. AI Brain returns confirmation, retry, or manual-input action metadata.
4. Frontend sends confirmation or manual input for the same field.
5. Backend exports final values when the frontend wizard is complete.
6. Backend persists final form data to its database.

## Service Methods

Import only:

```python
from brain_service import AdmissionBrainService
```

Public methods:

```python
create_session(language="ar", mode="qa") -> dict
reset_session(session_id) -> dict
get_session_state(session_id) -> dict
set_language(session_id, language) -> dict
set_mode(session_id, mode) -> dict
process_text(session_id, text, language=None, mode=None, generate_audio=False) -> dict
process_registration_field(session_id, field_id, transcript, language="ar", interaction="answer", generate_audio=False, question_text=None) -> dict
get_registration_status(session_id) -> dict
review_registration(session_id) -> dict
export_registration(session_id) -> dict
export_registration_frontend(session_id) -> dict
```

Supported languages are `ar` and `en`. Supported modes are `qa`,
`registration`, and `confirmation`. Supported frontend registration
interactions are `answer`, `confirmation`, and `manual_input`.

## Registration Examples

Answer:

```python
service.process_registration_field(
    session_id=session_id,
    field_id="date_of_birth",
    transcript="12 November 2005",
    language="en",
    interaction="answer",
)
```

Confirmation:

```python
service.process_registration_field(
    session_id=session_id,
    field_id="date_of_birth",
    transcript="yes",
    language="en",
    interaction="confirmation",
)
```

Correction:

```python
service.process_registration_field(
    session_id=session_id,
    field_id="date_of_birth",
    transcript="no, correct it to 11 December 2005",
    language="en",
    interaction="confirmation",
)
```

Manual input:

```python
service.process_registration_field(
    session_id=session_id,
    field_id="date_of_birth",
    transcript="11122005",
    language="en",
    interaction="manual_input",
)
```

Invalid field ID:

```json
{
  "success": false,
  "error": "INVALID_FIELD_ID",
  "message": "Unknown registration field."
}
```

Stale confirmation field mismatch:

```json
{
  "success": false,
  "error": "FIELD_STATE_MISMATCH",
  "message": "This field does not match the pending registration interaction."
}
```

## Recommended Flask Endpoint Map

Documentation only. Do not implement these routes in the AI Brain repo.

```text
POST /api/brain/sessions
POST /api/brain/messages
POST /api/brain/registration/field
GET  /api/brain/registration/status
GET  /api/brain/registration/review
GET  /api/brain/registration/export
POST /api/brain/sessions/{session_id}/reset
```

## Response Contract

Successful frontend-driven registration responses include:

```json
{
  "success": true,
  "session_id": "student-session-123",
  "data": {
    "field_id": "date_of_birth",
    "interaction": "answer",
    "status": "confirmation_required",
    "field_completed": false,
    "allow_frontend_next": false,
    "form_updates": {
      "date_of_birth": "2005-11-12"
    },
    "frontend_form_updates": {
      "dateOfBirth": "2005-11-12"
    },
    "normalized_value": "2005-11-12",
    "response_text": "I recorded Date of Birth as: 2005-11-12. Is this correct? Say yes to confirm or no to repeat.",
    "speech_text": "I recorded Date of Birth as: 2005-11-12. Is this correct? Say yes to confirm or no to repeat.",
    "confirmation": {
      "required": true,
      "field_id": "date_of_birth",
      "display_value": "2005-11-12"
    },
    "manual_input": {
      "required": false,
      "field_id": null,
      "prompt": null,
      "input_mode": null
    },
    "ui_action": "SHOW_CONFIRMATION",
    "audio": {
      "generated": false,
      "path": null,
      "content_type": null
    }
  }
}
```

Statuses: `confirmation_required`, `retry_required`,
`manual_input_required`, `confirmed`, `field_state_mismatch`, `error`.

UI actions: `SHOW_CONFIRMATION`, `SHOW_RETRY`,
`REQUEST_MANUAL_INPUT`, `ALLOW_FRONTEND_NEXT`, `SHOW_ERROR`.

Errors:

```text
SESSION_NOT_FOUND
INVALID_LANGUAGE
INVALID_MODE
INVALID_FIELD_ID
INVALID_INTERACTION
INVALID_TRANSCRIPT
FIELD_STATE_MISMATCH
INTERNAL_SERVICE_ERROR
```

Public errors do not include stack traces, API keys, model names, local absolute
paths, or raw provider errors.

## Audio Integration

Service methods never play audio. `generate_audio=False` returns:

```json
{
  "generated": false,
  "path": null,
  "content_type": null
}
```

When `generate_audio=True`, the service may generate an MP3 file and return a
relative path plus `content_type: "audio/mpeg"`. The Flask backend should turn
that local generated-audio path into a served media URL before returning it to a
browser or mobile app.

## Privacy Note

Registration data can include national IDs, phone numbers, addresses, emails,
and guardian details. The backend should protect it with authentication,
transport security, access controls, database encryption where appropriate, and
careful logging policies. Avoid logging raw applicant values in public logs.
