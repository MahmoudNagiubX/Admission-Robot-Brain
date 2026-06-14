# 🗺️ Master Plan: ECU Interactive Admission Assistant (The AI Brain)

## Section 1: System Overview & Core Responsibilities
The AI Brain acts as the central orchestrator of the entire robot. It receives raw text from the STT module, processes it using stateful logic, and outputs clean, structured payloads to the Flutter application.

### Core Objectives:
* **Minimize Latency:** Keep total processing time under 1 second per turn.
* **Contextual Awareness:** Remember what the user is talking about across multiple sentences.
* **Absolute Reliability:** Never make up facts (hallucinate) about university requirements or fees.
* **Clean Team Handoff:** Provide highly predictable API responses so the Flutter UI can update dynamically without breaking.

---

## Section 2: The Tiered "Thinking" & Routing Engine
To prevent the robot from behaving like a rigid, keyword-matching program, the brain uses a three-tier semantic routing pipeline. Every incoming phrase is parsed for its intent and meaning, ignoring minor typos and slang.
```
Incoming Text ➔ Clean Text & History ➔ Semantic Intent Analyzer
│
┌──────────────────────────────────────┼──────────────────────────────────────┐
▼                                      ▼                                      ▼
[Tier 1: FAQ Cache]                    [Tier 2: Local JSON RAG]               [Tier 3: Guardrail Fallback]
Confidence >= 0.85                     Confidence 0.50 – 0.84                 Confidence < 0.50
Instant pre-mapped answer              Context pulled from scraped files     Safe, protective human escalation
```

### 1. Tier 1: The Fast FAQ Cache (High Confidence)
* **Mechanic:** A dictionary of the top ~200 most frequently asked questions stored directly in the system's memory.
* **Trigger:** Triggered when the semantic analyzer determines an exact or highly certain match (e.g., matching "فين هندسة" or "طريق مبنى هندسة" to the engineering_location intent).
* **Target Latency:** Under 50ms.

### 2. Tier 2: The Local JSON RAG Index (Medium Confidence)
* **Mechanic:** An in-memory search engine that scans pre-structured JSON files containing crawled data from the ECU website.
* **Trigger:** Triggered when a student asks a specific, dynamic question that isn't in the top FAQs (e.g., asking about a specific professor, a niche course requirement, or current lab equipment).
* **Processing:** The system extracts the top relevant text paragraphs from the JSON files and passes them to Claude Haiku as context to formulate a short, crisp answer.
* **Target Latency:** 200ms – 500ms.

### 3. Tier 3: Out-of-Scope Guardrail (Low Confidence)
* **Mechanic:** A strict algorithmic blocker that stops the AI from generating answers if it doesn't find the information in the FAQs or local JSON files.
* **Trigger:** Triggered if confidence drops across the board or if the question is irrelevant to ECU (e.g., "How do I bake a cake?").
* **Action:** The system bypasses data generation entirely and issues a safe, fixed fallback response to connect the user with a human staff member.

---

## Section 3: Stateful Conversation Memory Management
A conversational AI must understand context. If a user asks a follow-up question, the brain must resolve ambiguous pronouns by looking at the recent history.

### 1. The Session Cache Map
Every student interaction is tracked using a unique session_id generated when they choose their language.
The brain maintains a fast, active memory state for each active session containing:
* **The Active Mode:** (Whether the user is currently in Q&A mode or REGISTRATION mode).
* **The Conversation Window:** The exact text of the last 2 to 3 dialogue turns.
* **The Current Topic Pointer:** A tag tracking the active subject (e.g., faculty_of_pharmacy, tuition_fees, housing).

### 2. Pronoun & Reference Resolution
* When a user inputs a vague prompt like "How much is it?", the brain passes the incoming text plus the conversation window to the semantic processor.
* The processor uses the history to deduce that "it" refers to the faculty_of_engineering discussed in the previous turn, routing the request to the correct tuition data.

---

## Section 4: Transactional Registration Extraction Engine
Answering questions requires a completely different cognitive architecture than filling out a form. When the user enters Registration Mode, the brain stops acting as a Q&A engine and switches to a strict Information Extraction pipeline.

### 1. Hybrid Extraction Strategy
To save API tokens and maximize speed, data extraction is split into two phases:
* **Phase A (Deterministic Regex Filters):** The system instantly scans the incoming text for rigid, patterned data. It uses regex patterns to extract 14-digit National IDs and standard Egyptian mobile phone formats (e.g., numbers starting with 010, 011, 012, or 015) without sending that specific text to the LLM.
* **Phase B (Semantic LLM Extraction):** Free-text information like the applicant's full name, high school name, and GPA is processed by Claude Haiku.

### 2. Categorization & Auto-Mapping
* High school systems are incredibly varied. The extraction engine is instructed to listen to how a user describes their school (e.g., "انا في مدرسة المتفوقين", "خلصت امريكان دبلومة", "انا ثانوية عامة") and cleanly normalize it into a fixed database key: Thanaweya Amma, STEM, IGCSE, American, Al-Azhar, or Other.

### 3. Progress Tracking & Next-Question Logic
* The brain reviews the 13 required fields after every input.
* It identifies the very first empty field in the database and generates a targeted, natural spoken question to prompt the student for that specific missing piece of information (e.g., "Great, I've got your name. Now, what is your 14-digit National ID?").

---

## Section 5: System Guardrails & Confidence Thresholds
To ensure the robot is bulletproof, we establish explicit boundaries that the system cannot cross.

### 1. Math-Driven Gating Thresholds
We assign hard mathematical rules to the semantic router's confidence output:
* **Score >= 0.85:** Execute a Tier 1 Cache Hit. Completely safe, completely static.
* **Score 0.50 to 0.84:** Execute a Tier 2 JSON RAG search. Pull official data, pass to Claude Haiku to summarize.
* **Score < 0.50:** Execute Tier 3 Guardrail. Do not allow the LLM to think; output the human-escalation message.

### 2. Strict Script Language Lock
* Speech-to-Text outputs can be messy, sometimes mixing English words into Arabic sentences or typing Arabic names in English characters.
* Regardless of the input script format, the system prompt contains a hard code restriction locked to the user's initial selection. If the session is locked to ar, the output strings must be pure Arabic. If locked to en, the output strings must be pure English. This prevents the robot from speaking in mixed scripts.

---

## Section 6: Analytics, Logging, & Continuous Improvement
A critical feature of a smart system is its ability to learn from its shortfalls without needing system restarts.

### 1. Unanswered Query Strategy
* Every single time a query triggers a Confidence Score < 0.50, the brain catches the event and writes it to a local log file named unanswered_queries.log.
* The log records: `Timestamp | Session ID | Raw STT Input Text | Calculated Confidence`.

### 2. Knowledge Base Evolution Roadmaps
* This log file acts as a direct goldmine for your development team. By opening this file at the end of admission day 1, you can see exactly what students are asking that the robot doesn't know yet (e.g., "Where is the campus clinic?" or "Can I pay in installments?").
* You can instantly add those answers to your static FAQ cache or your local JSON files, making the robot noticeably smarter for day 2 without modifying any core application logic.

---

## Section 7: Inter-Module API Contracts (Team Integration)
To keep your work perfectly synced with your friends working on STT and Flutter, the brain exposes a single unified endpoint with highly predictable data structures.

### 1. What the Brain Expects (Input Payload from STT)
Your backend will listen for a clean data payload containing:
* `session_id`: A unique session identifier string.
* `text_input`: The raw text transcript string processed by your friend's STT module.
* `language`: The manual language toggle indicator string (set to "ar" or "en").
* `mode_override`: An optional state override string used if the Flutter app wants to manually push the brain into FAQ or Registration mode via an on-screen button tap.

### 2. What the Brain Outputs (Response Payload to Flutter)
Your backend will return a comprehensive payload containing:
* `status`: A status execution key showing the path taken (e.g., "cache_hit", "llm_generated", "active_registration", "escalate_to_human").
* `text_to_display`: A highly scannable, nicely formatted text string containing bullet points or short paragraphs for the main tablet screen.
* `text_to_speak`: A perfectly clean text string completely stripped of markdown, stars, or bullet symbols, optimized for the text-to-speech engine to read aloud smoothly.
* `current_topic`: A tracking string showing the active topic context.
