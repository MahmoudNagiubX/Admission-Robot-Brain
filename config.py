# API keys, model name, thresholds, language settings.

""" Project configuration for Admission Robot AI Brain.
This file stores system-wide constants such as model name,
default language, supported modes, and confidence thresholds."""

PROJECT_NAME = "Admission Robot"

# Main LLM model to use for all interactions. This can be overridden in specific modules if needed.
MAIN_LLM_MODEL = "gpt-5-mini"

# Supported languages.
LANGUAGE_AR = "ar"
LANGUAGE_EN = "en"
SUPPORTED_LANGUAGES = {LANGUAGE_AR, LANGUAGE_EN}

# Brain modes.
MODE_QA = "qa"
MODE_REGISTRATION = "registration"
MODE_CONFIRMATION = "confirmation"

SUPPORTED_MODES = {
    MODE_QA,
    MODE_REGISTRATION,
    MODE_CONFIRMATION,
}

# Default values.
DEFAULT_LANGUAGE = LANGUAGE_EN
DEFAULT_MODE = MODE_QA

# Confidence thresholds.
FAQ_HIGH_CONFIDENCE = 0.90
FAQ_MEDIUM_CONFIDENCE = 0.82
RAG_MIN_CONFIDENCE = 0.60
CLARIFICATION_MIN_CONFIDENCE = 0.45