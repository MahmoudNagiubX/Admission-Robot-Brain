"""
Configuration file for Admission Robot AI Brain.

Keep project constants here so the rest of the code stays clean.
"""

PROJECT_NAME = "Admission Robot"

# Main LLM model agreed for the real AI steps.
MAIN_LLM_MODEL = "gpt-5-mini"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
LLM_TIMEOUT_SECONDS = 15
ENABLE_LLM_RAG = True

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
