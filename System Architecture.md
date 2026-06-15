# System Architecture — Admission Robot AI Brain

> **Final working document** for the `Admission Robot` project.  
> This file should replace the old `Structure.md` as the main reference file.  
> Recommended filename inside the project: `System_Architecture.md`

---

## 0. Document Purpose

This document explains the full architecture and implementation plan for the **Admission Robot AI Brain**.

The goal is that any AI assistant, developer, or teammate can read this single file and understand:

- what the system is
- what our part is responsible for
- what our part is **not** responsible for
- how the text enters the brain
- how the text is cleaned and corrected
- how the brain understands different question wording
- how known questions are answered quickly
- how unknown but answerable questions use local JSON/RAG
- how `gpt-5-mini` is used safely
- how registration form filling works
- how TTS output is prepared
- how the files are organized
- how the execution phases and Git commits are named

This document is the source of truth for our standalone AI Brain module.

---

## 1. Project Identity

### Project folder name

The project folder is named exactly:

```text
Admission Robot
```

Because the folder name contains a space, use quotes in terminal commands:

```bash
cd "Admission Robot"
```

### Project type

This is a:

```text
Standalone Python AI Brain module
```

It is **not** a full backend project.  
It is **not** a frontend project.  
It is **not** the STT module.  
It is **not** the React Native tablet application.

---

## 2. Our Exact Responsibility

Our AI Brain receives text that already came from the STT teammate.

The input may be clean, or it may contain:

- spelling mistakes
- STT mistakes
- wrong word recognition
- mixed Arabic and English
- missing punctuation
- spoken numbers instead of written digits
- Arabic-Indic digits
- student slang
- different wording for the same question
- incomplete registration answers
- user corrections like “no, my phone is...”

Our module must:

1. receive the text
2. clean and normalize it
3. protect sensitive values before correction
4. detect entities like faculty, fees, documents, phone, ID, grade
5. understand the intent even if the wording is different
6. use memory for follow-up questions
7. answer from known FAQ if possible
8. search local ECU JSON data when needed
9. use `gpt-5-mini` only when needed
10. produce a short natural answer
11. fill registration fields when in registration mode
12. validate and confirm important fields
13. prepare `speech_text` for TTS
14. optionally generate audio through `tts_engine.py`
15. log unanswered or unsafe questions

---

## 3. What We Are Not Responsible For Now

We are **not** currently responsible for:

- React Native tablet UI
- Deepgram STT implementation
- microphone capture
- frontend buttons
- visual form rendering
- robot movement/navigation
- a complex FastAPI backend
- deployment server architecture
- user authentication
- cloud database dashboard

Later, the integration teammate can connect our AI Brain to STT, React Native, or any backend by calling our module.

---

## 4. Final High-Level Flow

```text
STT Transcript Text
        ↓
Text Intelligence Layer
        ↓
Session Memory
        ↓
AI Brain Router
        ├── Registration Mode
        ├── FAQ / Known Question Cache
        ├── Local Knowledge / RAG Search
        └── Guardrail / Staff Fallback
        ↓
Answer Composer
        ↓
TTS Engine
        ↓
BrainOutput
```

The AI Brain should never act like a random chatbot.

It should act like a controlled admission assistant:

```text
Clean → Protect → Understand → Retrieve → Validate → Answer → Speak
```

---

## 5. Simple Project Structure

We agreed to keep the project simple, clean, and not over-engineered.

Current folder structure:

```text
Admission Robot/
│
├── main.py
├── config.py
├── models.py
├── text_processor.py
├── brain.py
├── memory.py
├── knowledge_base.py
├── registration.py
├── tts_engine.py
├── utils.py
├── requirements.txt
├── System_Architecture.md
│
├── data/
│   ├── faqs.json
│   ├── registration_fields.json
│   └── faculties/
│       └── engineering_and_technology.json
│
└── logs/
    └── unanswered_queries.log
```

No extra API folders.  
No routes folder.  
No backend-style repository/service layers.  
The system should remain easy to understand.

---

## 6. Responsibility of Each File

| File | Responsibility |
|---|---|
| `main.py` | Local test runner. Simulates text coming from STT. |
| `config.py` | Constants: model name, thresholds, modes, languages, paths. |
| `models.py` | Shared input/output dataclasses and structured objects. |
| `text_processor.py` | Cleans STT text, normalizes Arabic/English, protects entities, detects domain hints. |
| `brain.py` | Main decision engine: decides registration vs FAQ vs RAG vs fallback. |
| `memory.py` | Stores short-term session context: mode, last topic, last turns, current field. |
| `knowledge_base.py` | Loads FAQ and faculty JSON files and searches them. |
| `registration.py` | Handles form extraction, validation, confirmation, and next-question logic. |
| `tts_engine.py` | Converts `speech_text` into audio or returns placeholder audio path. |
| `utils.py` | Small helper functions used by other files. |
| `data/faqs.json` | Known questions and safe verified answers. |
| `data/faculties/*.json` | Faculty data collected from ECU website. |
| `data/registration_fields.json` | Full registration form field order and prompts. |
| `logs/unanswered_queries.log` | Stores questions the brain could not answer safely. |

---

## 7. Main Python Interface

The final AI Brain should be callable like this:

```python
from brain import ECUBrain
from models import BrainInput

brain = ECUBrain()

brain_input = BrainInput(
    session_id="session_001",
    text="عايز اعرف مصاريف هندسة كام",
    language="ar",
    mode="qa",
)

result = brain.process(brain_input)

print(result.answer_text)
print(result.speech_text)
print(result.audio_path)
print(result.form_updates)
```

The integration teammate can later call this from any backend or app.

---

## 8. Input and Output Contract

### BrainInput

```python
BrainInput(
    session_id: str,
    text: str,
    language: str,   # "ar" or "en"
    mode: str = "qa" # "qa", "registration", or "confirmation"
)
```

### BrainOutput

```python
BrainOutput(
    mode: str,
    answer_text: str,
    speech_text: str,
    confidence: float,
    current_topic: str | None,
    audio_path: str | None,
    form_updates: dict,
    route_taken: list[str]
)
```

### Output example for Q&A

```json
{
  "mode": "qa",
  "answer_text": "Engineering fees must be confirmed from the Admission Office because they may change by academic year.",
  "speech_text": "Engineering fees must be confirmed from the Admission Office.",
  "confidence": 0.86,
  "current_topic": "engineering_and_technology_fees",
  "audio_path": "outputs/audio/session_001_answer_001.mp3",
  "form_updates": {},
  "route_taken": ["text_processed", "rag_search", "llm_answer_composed"]
}
```

### Output example for registration

```json
{
  "mode": "registration",
  "answer_text": "I captured your name and school system. Please confirm them on the screen.",
  "speech_text": "I captured your name and school system. What is your mobile number?",
  "confidence": 0.91,
  "current_topic": "registration",
  "audio_path": "outputs/audio/session_001_prompt_002.mp3",
  "form_updates": {
    "full_name_en": "Ahmed Mohamed Ali",
    "certificate_type": "STEM"
  },
  "route_taken": ["text_processed", "registration_mode", "field_extraction", "next_question_selected"]
}
```

---

## 9. Core Design Rules

### Rule 1 — Raw text must never be destroyed

The raw STT text must always remain stored for debugging.

The system should keep several forms of the same input:

```json
{
  "raw_text": "اصل انا عايز اعرف هندسه مصاريفها كام",
  "normalized_text": "اصل انا عايز اعرف هندسه مصاريفها كام",
  "protected_text": "اصل انا عايز اعرف هندسه مصاريفها كام",
  "corrected_text": "انا عايز اعرف كلية الهندسة المصروفات كام",
  "search_query": "faculty engineering tuition fees",
  "entities": {
    "faculty": "engineering_and_technology",
    "intent_hint": "fees"
  }
}
```

### Rule 2 — Do not blindly correct sensitive data

Before spelling correction, protect:

- full names
- national ID
- passport number
- mobile number
- email
- date of birth
- grades / percentage
- seat number

Names, IDs, emails, and numbers should be corrected only with confirmation.

### Rule 3 — Same meaning should map to the same intent

The system must understand that all these may mean the same thing:

```text
فين هندسة؟
مكان كلية الهندسة فين؟
اروح مبنى هندسة ازاي؟
Where is engineering?
How can I reach the Engineering building?
```

They should map to one intent:

```text
engineering_location
```

### Rule 4 — Known answer should be fast

If the question maps to a high-confidence FAQ, answer immediately.

### Rule 5 — Unknown but answerable questions use local data

If the answer is not directly cached, search the local faculty JSON/RAG sections.

### Rule 6 — No source means no answer

The model must not invent ECU facts.

If no source exists, return safe staff fallback.

### Rule 7 — Natural answer variation is allowed, facts are not

The robot should not sound like a fixed script every time.  
However, the factual content must stay the same.

Good:

```text
Version 1: Engineering fees may change by academic year, so please confirm the official amount with the Admission Office.
Version 2: For Engineering fees, the safest answer is to check with Admission Office because the official amount can change each year.
```

Bad:

```text
Engineering fees are 70,000 EGP.
```

unless that number exists in verified data.

---

## 10. Text Intelligence Layer

This is one of the most important parts of the whole system.

File:

```text
text_processor.py
```

### Purpose

The Text Intelligence Layer prepares messy STT text before the brain routes it.

It handles:

- spelling mistakes
- STT word mistakes
- Arabic normalization
- English normalization
- Arabic-Indic digit conversion
- spoken number conversion
- domain term correction
- faculty detection
- intent hint detection
- sensitive entity protection

---

## 11. Text Processor Pipeline

```text
raw_text
    ↓
strip spaces and normalize Unicode
    ↓
normalize Arabic letters
    ↓
normalize Arabic/English digits
    ↓
convert spoken numbers
    ↓
protect sensitive entities
    ↓
remove filler words
    ↓
correct domain terms
    ↓
detect entities and intent hints
    ↓
produce TextProcessingResult
```

---

## 12. TextProcessingResult Model

The text processor should return:

```python
TextProcessingResult(
    raw_text: str,
    normalized_text: str,
    protected_text: str,
    corrected_text: str,
    search_query: str,
    detected_language: str,
    entities: dict,
    corrections: list[str],
    confidence_hints: dict
)
```

Example:

```json
{
  "raw_text": "انا عايز هندسه مصريفها كام",
  "normalized_text": "انا عايز هندسه مصريفها كام",
  "protected_text": "انا عايز هندسه مصريفها كام",
  "corrected_text": "انا عايز كلية الهندسة مصاريفها كام",
  "search_query": "engineering tuition fees",
  "detected_language": "ar",
  "entities": {
    "faculty": "engineering_and_technology",
    "intent_hint": "fees"
  },
  "corrections": [
    "هندسه -> كلية الهندسة",
    "مصريفها -> مصاريفها"
  ],
  "confidence_hints": {
    "faculty_detection": 0.94,
    "intent_detection": 0.88
  }
}
```

---

## 13. Arabic Text Normalization

Arabic text from STT may include different forms of the same letters.

For matching only, normalize:

| Input | Normalized |
|---|---|
| أ / إ / آ | ا |
| ى | ي |
| ؤ | و |
| ئ | ي |
| ـ | removed |
| tashkeel | removed |

Important: do not overwrite the original raw text.

---

## 14. Digit Normalization

The system should convert Arabic-Indic digits:

```text
٠ ١ ٢ ٣ ٤ ٥ ٦ ٧ ٨ ٩
```

to:

```text
0 1 2 3 4 5 6 7 8 9
```

Example:

```text
المجموع ٩٤٫٥
```

becomes:

```text
المجموع 94.5
```

---

## 15. Spoken Number Normalization

STT may produce phone numbers as words:

```text
صفر واحد صفر اتنين تلاتة
zero one zero two three
زيرو وان زيرو تو ثري
```

The system should convert them to digits when they appear in phone/ID contexts.

Example:

```text
رقمي صفر واحد صفر اتنين تلاتة اربعة خمسة ستة سبعة تمانية تسعة
```

becomes:

```text
رقمي 01023456789
```

---

## 16. Protected Entities

Before correction, extract and protect:

| Entity | Example | Rule |
|---|---|---|
| `phone_number` | 01012345678 | 11 digits, starts 010/011/012/015 |
| `national_id` | 30101011234567 | 14 digits, usually starts 2 or 3 |
| `email` | test@gmail.com | email pattern |
| `percentage` | 94.5% | 0–100 |
| `year` | 2024 | valid year |
| `date` | 10/05/2006 | date pattern |
| `passport` | A1234567 | alphanumeric, confirm |

Protected values should not be “corrected” by fuzzy matching.

---

## 17. Domain Dictionary

Use domain terms to fix common mistakes and detect entities.

File can be inside `config.py` or a later JSON file.

Example domain dictionary:

```python
DOMAIN_TERMS = {
    "engineering_and_technology": {
        "aliases_ar": ["هندسة", "كلية الهندسة", "هندسه", "هندسة وتكنولوجيا"],
        "aliases_en": ["engineering", "engineering faculty", "faculty of engineering", "eng"],
    },
    "fees": {
        "aliases_ar": ["مصاريف", "مصروفات", "تكلفة", "بكام"],
        "aliases_en": ["fees", "tuition", "cost", "price"],
    },
    "location": {
        "aliases_ar": ["فين", "مكان", "اروح", "مبنى"],
        "aliases_en": ["where", "location", "building", "reach", "go to"],
    },
    "documents": {
        "aliases_ar": ["ورق", "اوراق", "مستندات", "المطلوب"],
        "aliases_en": ["papers", "documents", "required documents", "what should i bring"],
    },
}
```

---

## 18. Same Question, Different Wording

The brain must solve this problem:

```text
15 users ask the same question in 15 different ways.
```

Solution:

1. Normalize the text.
2. Detect faculty and topic hints.
3. Compare against FAQ paraphrases.
4. Search RAG if FAQ is not confident enough.
5. Use memory for follow-up references.

Examples:

| User text | Internal meaning |
|---|---|
| فين هندسة؟ | engineering_location |
| مكان مبنى هندسة | engineering_location |
| Where is engineering? | engineering_location |
| How can I reach ENG? | engineering_location |
| هندسة في أنهي مبنى؟ | engineering_location |

---

## 19. Brain Modes

The AI Brain has three main modes:

```text
qa
registration
confirmation
```

### QA Mode

Used for questions about:

- university
- faculties
- admission
- documents
- fees
- locations
- departments
- programs
- certificate tracks

### Registration Mode

Used when user wants to fill the admission form.

### Confirmation Mode

Used when the system needs the user to confirm:

- phone
- national ID
- email
- grade
- name spelling
- faculty preference

---

## 20. Brain Router

File:

```text
brain.py
```

Routing logic:

```text
process(input)
    ↓
text_processor.process(input.text)
    ↓
memory.load(session_id)
    ↓
if active mode is registration:
    registration_engine.process()
else:
    try FAQ cache
    if high confidence:
        answer from known data
    else:
        try knowledge/RAG search
        if useful source found:
            use gpt-5-mini to compose answer
        else:
            staff fallback
    ↓
compose output
    ↓
tts_engine.generate(speech_text)
    ↓
return BrainOutput
```

---

## 21. Confidence Thresholds

Use these thresholds:

| Case | Score | Action |
|---|---:|---|
| High-confidence FAQ | `>= 0.90` | Return known answer fast |
| Medium FAQ | `0.82–0.89` | Use if margin from second match is clear |
| RAG answerable | `>= 0.60` | Retrieve source and compose answer |
| Clarification zone | `0.45–0.59` | Ask one short clarification |
| Unsafe / unknown | `< 0.45` | Staff fallback and log question |

Sensitive registration fields need stronger rules:

| Field | Confirmation rule |
|---|---|
| phone | always confirm |
| national ID | always confirm, do not speak full ID |
| email | always confirm |
| percentage | always confirm |
| faculty choice | always confirm |
| name | confirm if confidence is not high |

---

## 22. FAQ / Known Answer Cache

File:

```text
data/faqs.json
```

### Purpose

Answer common questions immediately.

This reduces latency and avoids unnecessary LLM calls.

### Important behavior

The FAQ answer contains verified facts.  
The final wording may vary naturally using answer templates, but facts must not change.

### FAQ structure

```json
[
  {
    "intent_id": "engineering_location",
    "topic": "engineering_and_technology_location",
    "faculty_id": "engineering_and_technology",
    "category": "location",
    "priority": 1,
    "questions_ar": [
      "فين كلية الهندسة؟",
      "مكان هندسة فين؟",
      "اروح مبنى هندسة ازاي؟"
    ],
    "questions_en": [
      "Where is the Faculty of Engineering?",
      "How can I reach engineering?",
      "Where is the engineering building?"
    ],
    "facts": {
      "ar": ["كلية الهندسة موجودة في ..."],
      "en": ["The Faculty of Engineering is located at ..."]
    },
    "answer_variants_ar": [
      "كلية الهندسة موجودة في ...",
      "تقدر تروح كلية الهندسة من ..."
    ],
    "answer_variants_en": [
      "The Faculty of Engineering is located at ...",
      "You can reach the Faculty of Engineering by going to ..."
    ],
    "source_url": "https://ecu.edu.eg/faculties/engineering-and-technology/",
    "safe_to_answer": true,
    "needs_staff_verification": false,
    "tts_cacheable": true
  }
]
```

---

## 23. Natural Answer Variation

The user should not feel the robot is reading the same script every time.

For FAQ answers, use:

- multiple answer variants
- short templates
- optional style selector

Example:

```python
ANSWER_STYLES = [
    "direct",
    "friendly",
    "short_guidance"
]
```

For the same facts, the answer composer can choose different wording.

Important:

```text
Only style changes. Facts do not change.
```

For RAG answers, `gpt-5-mini` can compose natural answers from retrieved context.

---

## 24. Local Knowledge Base / RAG

File:

```text
knowledge_base.py
```

Data folder:

```text
data/faculties/
```

### Purpose

When the question is not directly found in FAQ, the brain searches local JSON files.

### Local RAG flow

```text
corrected question
    ↓
extract topic/faculty hints
    ↓
search faculty JSON rag_sections
    ↓
find relevant source sections
    ↓
if enough confidence:
        send context to gpt-5-mini
    else:
        fallback / clarification
```

### Rule

Do not scrape the website live during conversation.

The data team collects JSON data from the ECU website.  
Our brain loads these files locally.

---

## 25. Faculty JSON Format Summary

Each faculty should have its own JSON file.

Example:

```text
data/faculties/engineering_and_technology.json
```

Recommended structure:

```json
{
  "faculty_id": "engineering_and_technology",
  "name": {
    "en": "Engineering and Technology",
    "ar": "كلية الهندسة والتكنولوجيا"
  },
  "aliases": {
    "en": ["engineering", "faculty of engineering", "eng"],
    "ar": ["هندسة", "كلية الهندسة", "هندسه"]
  },
  "overview": {
    "en": "...",
    "ar": "..."
  },
  "departments": [],
  "programs": [],
  "admission_information": {},
  "fees": {
    "tuition_fee": null,
    "needs_staff_verification": true,
    "safe_answer": {
      "en": "Fees must be confirmed from the Admission Office.",
      "ar": "المصروفات لازم تتأكد من إدارة القبول."
    }
  },
  "faq_items": [],
  "rag_sections": [],
  "data_quality": {
    "missing_data": [],
    "needs_manual_review": []
  }
}
```

The most important parts for the AI Brain are:

```text
aliases
faq_items
rag_sections
source_url
needs_staff_verification
data_quality
```

---

## 26. LLM Usage

Main LLM:

```text
gpt-5-mini
```

Use `gpt-5-mini` for:

- RAG answer generation
- registration semantic extraction
- short clarification generation
- natural answer composition from verified facts

Do not use LLM for:

- basic validation
- phone extraction
- national ID extraction
- exact FAQ cache hits when a prepared answer variant exists
- simple routing that can be solved by rules

### LLM safety rule

The LLM must answer only from provided context.

Prompt idea:

```text
You are the ECU Admission Robot AI Brain.
Use only the provided ECU context.
Do not invent fees, deadlines, requirements, or acceptance rules.
Respond only in the session language.
Return a short natural answer.
If the answer is not in the context, say that admission staff should confirm it.
```

---

## 27. Registration Form Engine

File:

```text
registration.py
```

The registration engine is separate from Q&A.

It handles:

- field extraction
- field validation
- field confirmation
- current field tracking
- next-question selection
- correction handling
- final form state

---

## 28. Full Registration Form Fields

The ECU registration paper form contains these main sections:

1. Personal Data
2. Family Information
3. Received Papers
4. College Preferences

### Personal Data fields

```text
full_name_en
full_name_ar
date_of_birth
place_of_birth
nationality
id_or_passport
gender
marital_status
country
district
city
home_phone
address
email_address
mobile_no_2
student_mobile_no
school_name
certificate
year_of_completion
percentage
total_marks
seat_number
sector
science_branch
math_branch
literary_branch
username
password
```

### Family Information fields

```text
guardian_name
guardian_id_or_passport
relationship
guardian_employer
guardian_profession
guardian_nationality
guardian_country
guardian_district
guardian_city
guardian_work_address
guardian_work_no
guardian_mobile_no
guardian_home_phone
guardian_email_address
```

### Received Papers fields

```text
passport_or_id_copy
passport_or_id_original
guardian_id_copy
guardian_id_original
high_school_certificate_copy
high_school_certificate_original
birth_certificate_copy
birth_certificate_original
personal_photos_4_copy
personal_photos_4_original
```

### College Preference fields

```text
college_preference_1
college_preference_2
college_preference_3
college_preference_4
college_preference_5
college_preference_6
```

---

## 29. Registration Field Object

Every field should have metadata.

```json
{
  "field_name": "student_mobile_no",
  "value": "01012345678",
  "confidence": 0.96,
  "confirmed": false,
  "needs_confirmation": true,
  "source_text": "رقمي صفر واحد صفر..."
}
```

This helps with:

- debugging
- form review
- confirmation
- preventing silent mistakes

---

## 30. Registration Extraction Strategy

Use a hybrid strategy.

### Phase A — deterministic extraction

Use Python regex and rules for:

- phone
- national ID
- email
- percentage
- year
- date
- seat number

### Phase B — semantic extraction with `gpt-5-mini`

Use LLM for:

- full name
- school name
- certificate type
- guardian name
- address
- college preferences

### Phase C — validation

Use Python validation rules.

### Phase D — confirmation

Ask the user to confirm important fields.

---

## 31. Registration Validators

### Egyptian mobile number

Valid if:

```text
11 digits
starts with 010, 011, 012, or 015
```

### Egyptian national ID

Valid if:

```text
14 digits
usually starts with 2 or 3
```

Do not speak the full national ID loudly.

### Email

Must match email format.

### Percentage

Must be:

```text
0 <= percentage <= 100
```

### Year

Should be realistic, for example:

```text
2015 <= year <= current_year
```

### Certificate type

Normalize to one of:

```text
Thanaweya Amma
STEM
American Diploma
IGCSE
Al-Azhar
Arab Certificate
Foreign Certificate
Other
```

---

## 32. Registration Flow

```text
User says: I want to apply
    ↓
Brain switches to registration mode
    ↓
Registration engine checks missing fields
    ↓
Robot asks next required question
    ↓
User answers naturally
    ↓
Text processor cleans and protects answer
    ↓
Registration engine extracts fields
    ↓
Validators run
    ↓
Important fields require confirmation
    ↓
Form state updates
    ↓
Robot asks next missing field
```

---

## 33. Registration Over-Informing

The user may provide multiple fields in one answer.

Example:

```text
My name is Ahmed Mohamed Ali, I graduated from STEM in 2024 with 94 percent.
```

The system should extract:

```json
{
  "full_name_en": "Ahmed Mohamed Ali",
  "certificate": "STEM",
  "year_of_completion": 2024,
  "percentage": 94.0
}
```

Then the next question should skip those completed fields.

---

## 34. Registration Corrections

The user may correct previous data.

Example:

```text
No, my phone is 01098765432.
```

The system should:

1. detect correction intent
2. update the old phone value
3. mark it as unconfirmed
4. ask confirmation again

---

## 35. Staff Fallback and Guardrails

The robot must not hallucinate.

Fallback triggers:

- low confidence
- no source found
- fees not verified
- admission minimum not verified
- user asks for official final decision
- user asks unrelated question
- sensitive answer requires staff

English fallback:

```text
I am not fully sure about this information. Please check with the Admission Office for the official answer.
```

Arabic fallback:

```text
أنا لست متأكدًا من هذه المعلومة بشكل كافٍ. من فضلك راجع إدارة القبول للتأكيد الرسمي.
```

---

## 36. Session Memory

File:

```text
memory.py
```

Session memory stores:

```json
{
  "session_id": "session_001",
  "language": "ar",
  "active_mode": "qa",
  "current_topic": "engineering_and_technology",
  "current_field": null,
  "last_turns": [],
  "registration_state": {}
}
```

### Why memory matters

User:

```text
Tell me about engineering.
```

Then:

```text
How much is it?
```

The brain should know:

```text
it = engineering
```

---

## 37. Language Lock

The user selects Arabic or English manually at the beginning.

The brain must always respond in the selected language.

Even if the user says mixed text, output should follow the selected language.

If `language = "ar"`:

```text
Output Arabic only.
```

If `language = "en"`:

```text
Output English only.
```

---

## 38. TTS Engine

File:

```text
tts_engine.py
```

### Input

```text
speech_text
```

### Output

```text
audio_path
```

or placeholder until real TTS integration.

### TTS rules

- Keep sentences short.
- Avoid long paragraphs.
- Do not speak full national ID.
- Do not speak full private data loudly.
- For phone/ID confirmation, say: “Please confirm it on the screen.”
- Use `speech_text`, not `answer_text`, for voice.

---

## 39. Answer Text vs Speech Text

Always separate display text and speech text.

### answer_text

Used for screen/display/logging.

Can contain:

- short bullet points
- field values
- source note
- confirmation prompt

### speech_text

Used for TTS.

Should be:

- shorter
- easier to pronounce
- privacy-safe
- natural

Example:

```json
{
  "answer_text": "I captured your national ID: ************4567. Please confirm it on the screen.",
  "speech_text": "I captured your national ID. Please confirm it on the screen."
}
```

---

## 40. Logging

File:

```text
logs/unanswered_queries.log
```

Log when:

- confidence is low
- no source is found
- user asks unsupported question
- extraction fails
- validation fails repeatedly

Example line:

```text
2026-06-15 | session_001 | ar | فين عيادة الجامعة | low_confidence | no_source_found
```

This log helps improve:

- FAQs
- faculty JSON data
- domain terms
- correction rules

---

## 41. Current Implementation Phases

We will implement the project step by step.

Each step has a Git commit message.

---

# Phase 1 — Simple AI Brain Foundation

Goal:

```text
Create a simple standalone Python project that runs locally.
```

## Phase 1 / Step 1

Create basic skeleton:

- `main.py`
- `config.py`
- `models.py`
- `brain.py`
- `requirements.txt`

Commit:

```bash
git commit -m "phase-1/step-1: create standalone ai brain skeleton"
```

## Phase 1 / Step 2

Add text package models:

- `TextProcessingResult`
- `ProtectedEntities`
- text processor placeholder

Commit:

```bash
git commit -m "phase-1/step-2: add text processor input package"
```

## Phase 1 / Step 3

Connect text processor placeholder to brain.

Commit:

```bash
git commit -m "phase-1/step-3: connect text processor to brain flow"
```

---

# Phase 2 — Text Intelligence Layer

Goal:

```text
Clean and prepare messy STT text before routing.
```

## Phase 2 / Step 1

Add basic text normalization.

Commit:

```bash
git commit -m "phase-2/step-1: add basic text normalization"
```

## Phase 2 / Step 2

Add Arabic letter and diacritics normalization.

Commit:

```bash
git commit -m "phase-2/step-2: add arabic text normalization"
```

## Phase 2 / Step 3

Add Arabic/English digit normalization.

Commit:

```bash
git commit -m "phase-2/step-3: add digit normalization"
```

## Phase 2 / Step 4

Add spoken-number conversion.

Commit:

```bash
git commit -m "phase-2/step-4: add spoken number normalization"
```

## Phase 2 / Step 5

Add protected entity extraction.

Commit:

```bash
git commit -m "phase-2/step-5: add protected entity extraction"
```

## Phase 2 / Step 6

Add domain term and faculty detection.

Commit:

```bash
git commit -m "phase-2/step-6: add domain term detection"
```

## Phase 2 / Step 7

Add correction output and search query generation.

Commit:

```bash
git commit -m "phase-2/step-7: add corrected text and search query generation"
```

---

# Phase 3 — Session Memory

Goal:

```text
Remember current topic and recent conversation context.
```

## Phase 3 / Step 1

Add session memory class.

Commit:

```bash
git commit -m "phase-3/step-1: add short term session memory"
```

## Phase 3 / Step 2

Track current topic and mode.

Commit:

```bash
git commit -m "phase-3/step-2: track current topic and active mode"
```

## Phase 3 / Step 3

Handle follow-up questions.

Commit:

```bash
git commit -m "phase-3/step-3: add follow up context handling"
```

---

# Phase 4 — FAQ / Known Question Cache

Goal:

```text
Answer known repeated questions fast.
```

## Phase 4 / Step 1

Create FAQ JSON structure.

Commit:

```bash
git commit -m "phase-4/step-1: add faq data structure"
```

## Phase 4 / Step 2

Load FAQ data.

Commit:

```bash
git commit -m "phase-4/step-2: add faq loader"
```

## Phase 4 / Step 3

Add simple matching.

Commit:

```bash
git commit -m "phase-4/step-3: add simple faq matching"
```

## Phase 4 / Step 4

Add paraphrase/same-meaning matching.

Commit:

```bash
git commit -m "phase-4/step-4: add faq paraphrase matching"
```

## Phase 4 / Step 5

Add natural answer variant selection.

Commit:

```bash
git commit -m "phase-4/step-5: add natural faq answer variants"
```

---

# Phase 5 — Knowledge Base / RAG

Goal:

```text
Search local faculty JSON data and answer from verified context.
```

## Phase 5 / Step 1

Create faculty JSON loader.

Commit:

```bash
git commit -m "phase-5/step-1: add faculty json loader"
```

## Phase 5 / Step 2

Search RAG sections by keyword/entity.

Commit:

```bash
git commit -m "phase-5/step-2: add local knowledge section search"
```

## Phase 5 / Step 3

Add source-based answer composer.

Commit:

```bash
git commit -m "phase-5/step-3: add source based answer composer"
```

## Phase 5 / Step 4

Add `gpt-5-mini` RAG answer generation.

Commit:

```bash
git commit -m "phase-5/step-4: add gpt mini rag answer generation"
```

## Phase 5 / Step 5

Add no-source guardrail fallback.

Commit:

```bash
git commit -m "phase-5/step-5: add no source fallback guardrail"
```

---

# Phase 6 — Registration Form Engine

Goal:

```text
Extract, validate, confirm, and update registration fields.
```

## Phase 6 / Step 1

Add registration field schema.

Commit:

```bash
git commit -m "phase-6/step-1: add registration form schema"
```

## Phase 6 / Step 2

Add deterministic field extraction.

Commit:

```bash
git commit -m "phase-6/step-2: add deterministic registration extraction"
```

## Phase 6 / Step 3

Add LLM semantic extraction.

Commit:

```bash
git commit -m "phase-6/step-3: add semantic registration extraction"
```

## Phase 6 / Step 4

Add validation rules.

Commit:

```bash
git commit -m "phase-6/step-4: add registration field validation"
```

## Phase 6 / Step 5

Add confirmation logic.

Commit:

```bash
git commit -m "phase-6/step-5: add sensitive field confirmation logic"
```

## Phase 6 / Step 6

Add next-question selection.

Commit:

```bash
git commit -m "phase-6/step-6: add registration next question logic"
```

---

# Phase 7 — TTS Output

Goal:

```text
Prepare speech-safe output and generate or return TTS audio path.
```

## Phase 7 / Step 1

Add TTS placeholder.

Commit:

```bash
git commit -m "phase-7/step-1: add tts engine placeholder"
```

## Phase 7 / Step 2

Add speech text cleaning.

Commit:

```bash
git commit -m "phase-7/step-2: add speech text normalization"
```

## Phase 7 / Step 3

Add real TTS integration.

Commit:

```bash
git commit -m "phase-7/step-3: add tts audio generation"
```

---

# Phase 8 — Testing and Final Review

Goal:

```text
Make sure the brain works with messy realistic text.
```

## Phase 8 / Step 1

Add Q&A test cases.

Commit:

```bash
git commit -m "phase-8/step-1: add qa test cases"
```

## Phase 8 / Step 2

Add messy STT test cases.

Commit:

```bash
git commit -m "phase-8/step-2: add messy stt test cases"
```

## Phase 8 / Step 3

Add registration test cases.

Commit:

```bash
git commit -m "phase-8/step-3: add registration test cases"
```

## Phase 8 / Step 4

Finalize demo-ready AI Brain.

Commit:

```bash
git commit -m "phase-8/step-4: finalize ai brain system"
```

---

## 42. Test Cases We Must Support

### Q&A examples

```text
فين هندسة؟
هندسة مكانها فين؟
Where is engineering?
What papers do I need?
ايه الورق المطلوب؟
مصاريف هندسة كام؟
Can I apply with American diploma?
هل ينفع أقدم من STEM؟
```

### Same question different wording

```text
فين مبنى هندسة؟
مكان كلية الهندسة؟
هندسة فين؟
اروح هندسة ازاي؟
Where can I find engineering?
How can I reach Faculty of Engineering?
```

### Follow-up examples

```text
Tell me about engineering.
How much is it?
Where is it?
What papers do I need for it?
```

### Registration examples

```text
My name is Ahmed Mohamed Ali.
I graduated from STEM in 2024 with 94 percent.
My phone is zero one zero two three four five six seven eight nine.
No, my email is ahmed@gmail.com.
I want engineering as my first choice and computers as my second choice.
```

---

## 43. Quality Rules

The system should be:

- simple
- structured
- easy to debug
- safe
- fast
- not over-engineered
- not backend-heavy
- not frontend-dependent

The core quality requirement:

```text
The AI Brain should understand meaning, not just exact words.
```

---

## 44. Final Development Agreement

We will not rush.

For every implementation step:

1. Explain what we are doing.
2. Fill only the needed files.
3. Test the result.
4. Give a clean Git commit message.
5. Move to the next step only when the previous step works.

---

## 45. Immediate Current Step

Current next step:

```text
Phase 1 / Step 1 — create standalone ai brain skeleton
```

Files involved:

```text
main.py
config.py
models.py
brain.py
requirements.txt
```

Commit message:

```bash
git commit -m "phase-1/step-1: create standalone ai brain skeleton"
```

---

## 46. Final One-Line System Summary

```text
Admission Robot AI Brain receives messy STT text, cleans and understands it, answers ECU questions from verified data, fills the admission form safely, and returns natural text plus TTS-ready output.
```

---

## 47. How To Use This File With an AI Assistant

When continuing implementation, give the AI assistant this file and say:

```text
Read System_Architecture.md first. Continue implementation from the current phase and step. Keep the project simple and only edit the files needed for the current step.
```

The AI assistant should then:

- respect the project scope
- avoid backend/frontend complexity
- follow the phase plan
- provide commit messages
- keep code simple and readable
- focus on AI Brain logic

---

## 48. Final Notes

This document intentionally focuses on the standalone AI Brain, not full system deployment.

The integration layer can later wrap this brain inside:

- FastAPI
- Flask
- Node.js
- React Native bridge
- local robot controller

But that is not our current implementation responsibility.

Our deliverable is the clean Python AI Brain module.
