import re

def norm(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"[أإآٱ]", "ا", normalized)
    normalized = normalized.replace("ى", "ي")
    normalized = normalized.replace("ؤ", "و")
    normalized = normalized.replace("ئ", "ي")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()

GUARDIAN_WORDS = {
    "guardian", "father", "mother", "parent", "dad", "mom",
    "ولي الامر", "ولى الامر", "الاب", "الأب", "الام", "الأم",
    "والدي", "والدتي"
}

def has_context(text: str, words: set[str]) -> bool:
    normalized = norm(text)
    for word in words:
        norm_word = norm(word)
        if f" {norm_word} " in f" {normalized} " or normalized == norm_word:
            return True
    return False

text = "الأب"
result = has_context(text, GUARDIAN_WORDS)
print(f"Text: '{text}', Result: {result}")
print(f"Normalized Text: '{norm(text)}'")
print(f"Guardian Words (normalized): {[norm(w) for w in GUARDIAN_WORDS]}")
