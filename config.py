"""
Configuration file for Admission Robot AI Brain.

Keep project constants here so the rest of the code stays clean.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    ENV_PATH = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    load_dotenv = None


PROJECT_NAME = "Admission Robot"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return None

    try:
        return int(value)
    except ValueError:
        return None


# Main LLM model agreed for the real AI steps.
LLM_PROVIDER_ENV = "LLM_PROVIDER"
DEFAULT_LLM_PROVIDER = "groq"
LLM_PROVIDER = os.getenv(LLM_PROVIDER_ENV, DEFAULT_LLM_PROVIDER).strip().lower()
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
MAIN_LLM_MODEL = os.getenv("MAIN_LLM_MODEL", "gpt-5-mini")
GROQ_API_KEY_ENV = "GROQ_API_KEY"
GROQ_MODEL_ENV = "GROQ_MODEL"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_MODEL = os.getenv(GROQ_MODEL_ENV, DEFAULT_GROQ_MODEL)
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
LLM_TIMEOUT_SECONDS = _env_int("LLM_TIMEOUT_SECONDS", 15)
ENABLE_LLM_RAG = _env_bool("ENABLE_LLM_RAG", True)
ENABLE_LLM_REGISTRATION_EXTRACTION = _env_bool(
    "ENABLE_LLM_REGISTRATION_EXTRACTION",
    True,
)
RAG_MAX_ANSWER_CHARS = 700
RAG_INCLUDE_SOURCE_NOTE = True

# Speech-to-text
STT_PROVIDER = os.getenv("STT_PROVIDER", "deepgram").strip().lower()
DEEPGRAM_API_KEY_ENV = "DEEPGRAM_API_KEY"
ENABLE_VOICE_INPUT = _env_bool("ENABLE_VOICE_INPUT", True)
MICROPHONE_DEVICE_INDEX = _env_optional_int("MICROPHONE_DEVICE_INDEX")

# Voice recording settings
VOICE_RECORD_MODE = os.getenv("VOICE_RECORD_MODE", "vad").strip().lower()
VOICE_RECORD_SECONDS = _env_int("VOICE_RECORD_SECONDS", 7)
VOICE_SAMPLE_RATE = _env_int("VOICE_SAMPLE_RATE", 16000)
VOICE_CHANNELS = _env_int("VOICE_CHANNELS", 1)
VOICE_CHUNK_MS = _env_int("VOICE_CHUNK_MS", 30)

# VAD settings
VOICE_START_TIMEOUT_SECONDS = _env_int("VOICE_START_TIMEOUT_SECONDS", 8)
VOICE_MAX_RECORD_SECONDS = _env_int("VOICE_MAX_RECORD_SECONDS", 15)
VOICE_MIN_RECORD_SECONDS = float(os.getenv("VOICE_MIN_RECORD_SECONDS", "0.4"))
VOICE_SILENCE_STOP_SECONDS = float(os.getenv("VOICE_SILENCE_STOP_SECONDS", "1.0"))
VOICE_ENERGY_THRESHOLD = _env_int("VOICE_ENERGY_THRESHOLD", 500)
VOICE_PRE_ROLL_MS = _env_int("VOICE_PRE_ROLL_MS", 300)


# Text-to-speech
ENABLE_TTS = _env_bool("ENABLE_TTS", False)
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").strip().lower()

# edge-tts settings
EDGE_TTS_VOICE_EN = os.getenv("EDGE_TTS_VOICE_EN", "en-US-ChristopherNeural")
EDGE_TTS_VOICE_AR = os.getenv("EDGE_TTS_VOICE_AR", "ar-EG-SalmaNeural")
EDGE_TTS_RATE = os.getenv("EDGE_TTS_RATE", "-10%")
EDGE_TTS_RATE_AR = os.getenv("EDGE_TTS_RATE_AR", "-3%")

# Legacy Azure settings (kept for compatibility or if provider is azure)
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
AZURE_TTS_VOICE_EN = os.getenv("AZURE_TTS_VOICE_EN", "en-US-JennyNeural")
AZURE_TTS_VOICE_AR = os.getenv("AZURE_TTS_VOICE_AR", "ar-EG-SalmaNeural")
TTS_RATE = os.getenv("TTS_RATE", "0%")

TTS_FALLBACK_PHRASE = os.getenv(
    "TTS_FALLBACK_PHRASE",
    "Sorry, I had a small audio issue. Please ask me again.",
)

# Languages
LANGUAGE_AR = "ar"
LANGUAGE_EN = "en"
SUPPORTED_LANGUAGES = {LANGUAGE_AR, LANGUAGE_EN}
DEFAULT_LANGUAGE = LANGUAGE_EN

# Modes
MODE_QA = "qa"
MODE_REGISTRATION = "registration"
MODE_CONFIRMATION = "confirmation"
SUPPORTED_MODES = {MODE_QA, MODE_REGISTRATION, MODE_CONFIRMATION}
DEFAULT_MODE = MODE_QA

# Confidence thresholds
FAQ_HIGH_CONFIDENCE = 0.90
FAQ_MEDIUM_CONFIDENCE = 0.82
RAG_MIN_CONFIDENCE = 0.60
CLARIFICATION_MIN_CONFIDENCE = 0.45

# ECU faculties and common aliases.
# This helps the TextProcessor understand that different user phrases may mean the same faculty.
FACULTY_ALIASES = {
    "engineering_and_technology": [
        "engineering",
        "engineering and technology",
        "faculty of engineering",
        "eng",
        "هندسة",
        "الهندسة",
        "كلية الهندسة",
        "هندسة وتكنولوجيا",
        "كلية الهندسة والتكنولوجيا",
    ],
    "pharmacy_and_drug_technology": [
        "pharmacy",
        "pharmacy and drug technology",
        "faculty of pharmacy",
        "صيدلة",
        "الصيدلة",
        "كلية الصيدلة",
        "صيدلة وتكنولوجيا الدواء",
    ],
    "physical_therapy": [
        "physical therapy",
        "faculty of physical therapy",
        "علاج طبيعي",
        "العلاج الطبيعي",
        "كلية العلاج الطبيعي",
    ],
    "computers_and_information_systems": [
        "computers",
        "computer science",
        "computers and information systems",
        "cis",
        "حاسبات",
        "حاسبات ومعلومات",
        "كلية حاسبات",
        "كلية الحاسبات والمعلومات",
    ],
    "economics_and_international_trade": [
        "economics",
        "international trade",
        "economics and international trade",
        "business",
        "اقتصاد",
        "تجارة",
        "تجارة دولية",
        "اقتصاد وتجارة دولية",
        "كلية الاقتصاد والتجارة الدولية",
    ],
    "arts_and_design": [
        "arts",
        "design",
        "arts and design",
        "art and design",
        "فنون",
        "تصميم",
        "فنون وتصميم",
        "كلية الفنون والتصميم",
    ],
    "veterinary_medicine": [
        "veterinary",
        "veterinary medicine",
        "vet",
        "طب بيطري",
        "الطب البيطري",
        "كلية الطب البيطري",
    ],
    "mass_communication": [
        "mass communication",
        "media",
        "communication",
        "اعلام",
        "الإعلام",
        "كلية الاعلام",
        "كلية الإعلام",
    ],
    "nursing": [
        "nursing",
        "faculty of nursing",
        "تمريض",
        "التمريض",
        "كلية التمريض",
    ],
    "literary_studies": [
        "literary studies",
        "literature",
        "دراسات ادبية",
        "الدراسات الادبية",
        "كلية الدراسات الادبية",
    ],
    "law": [
        "law",
        "faculty of law",
        "حقوق",
        "قانون",
        "كلية الحقوق",
        "كلية القانون",
    ],
    "humanities": [
        "humanities",
        "humanities faculty",
        "علوم انسانية",
        "العلوم الانسانية",
        "كلية العلوم الانسانية",
    ],
}

# Intent aliases used for routing hints.
INTENT_ALIASES = {
    "fees": [
        "fees",
        "tuition",
        "price",
        "cost",
        "how much",
        "مصاريف",
        "مصروفات",
        "تكلفة",
        "سعر",
        "كام",
        "بكام",
    ],
    "location": [
        "where",
        "location",
        "building",
        "place",
        "go to",
        "فين",
        "مكان",
        "مبنى",
        "اروح",
        "اوصل",
    ],
    "departments": [
        "departments",
        "specializations",
        "majors",
        "programs",
        "اقسام",
        "تخصصات",
        "برامج",
    ],
    "admission_requirements": [
        "requirements",
        "admission",
        "minimum",
        "accepted",
        "apply",
        "شروط",
        "قبول",
        "تنسيق",
        "حد ادنى",
        "اقدم",
    ],
    "documents": [
        "documents",
        "papers",
        "required papers",
        "اوراق",
        "ورق",
        "مستندات",
        "الاوراق المطلوبة",
    ],
    "registration": [
        "register",
        "registration",
        "apply now",
        "form",
        "اسجل",
        "تسجيل",
        "استمارة",
        "اقدم",
    ],
}
