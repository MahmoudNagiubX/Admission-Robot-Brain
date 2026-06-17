
import re

def parse_spoken_numbers(text: str) -> str:
    """
    Convert spoken Arabic and English number words into digits.
    Supports 0-31 for dates, common years (1900-2029), and simple numbers.
    """
    if not text:
        return ""

    # Arabic Numbers Map
    arabic_map = {
        "صفر": 0, "واحد": 1, "اول": 1, "الأول": 1, "الاولى": 1, "الأولى": 1,
        "اتنين": 2, "اثنين": 2, "تاني": 2, "الثاني": 2,
        "تلاتة": 3, "ثلاثة": 3, "تالت": 3, "الثالث": 3,
        "اربعة": 4, "أربعة": 4, "رابع": 4, "الرابع": 4,
        "خمسة": 5, "خمسه": 5, "خامس": 5, "الخامس": 5,
        "ستة": 6, "سته": 6, "سادس": 6, "السادس": 6,
        "سبعة": 7, "سبعه": 7, "سابع": 7, "السابع": 7,
        "تمانية": 8, "تمانيه": 8, "ثمانية": 8, "تمنية": 8, "ثامن": 8, "الثامن": 8,
        "تسعة": 9, "تسعه": 9, "تاسع": 9, "التاسع": 9,
        "عشرة": 10, "عشره": 10, "عاشر": 10, "العاشر": 10,
        "احداشر": 11, "حداشر": 11, "احدى عشر": 11, "إحدى عشر": 11,
        "اتناشر": 12, "اثناشر": 12, "اثني عشر": 12, "اثنى عشر": 12,
        "تلتاشر": 13, "ثلاثة عشر": 13,
        "اربعتاشر": 14, "أربعة عشر": 14,
        "خمستاشر": 15, "خمسة عشر": 15,
        "ستاشر": 16, "ستة عشر": 16,
        "سبعتاشر": 17, "سبعة عشر": 17,
        "تمنتاشر": 18, "ثمانية عشر": 18,
        "تسعتاشر": 19, "تسعة عشر": 19,
        "عشرين": 20,
        "تلاتين": 30, "ثلاثين": 30,
    }

    # English Numbers Map
    english_map = {
        "zero": 0, "one": 1, "first": 1,
        "two": 2, "second": 2,
        "three": 3, "third": 3,
        "four": 4, "fourth": 4,
        "five": 5, "fifth": 5,
        "six": 6, "sixth": 6,
        "seven": 7, "seventh": 7,
        "eight": 8, "eighth": 8,
        "nine": 9, "ninth": 9,
        "ten": 10, "tenth": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19,
        "twenty": 20, "thirty": 30,
    }

    # Year specific words
    year_map = {
        "ألفين": 2000, "الفين": 2000,
        "ألف وتسعمية": 1900, "الف وتسعمية": 1900,
        "الف وتسعمائه": 1900, "ألف وتسعمئة": 1900,
    }

    # Normalize text
    text = text.lower()
    
    # Handle compound numbers like "واحد وعشرين" (21)
    def replace_compound_ar(match):
        ones = arabic_map.get(match.group(1))
        tens = arabic_map.get(match.group(2))
        if ones is not None and tens is not None:
            return str(tens + ones)
        return match.group(0)

    text = re.sub(r"(\w+)\s+و\s*(عشرين|تلاتين|ثلاثين)", replace_compound_ar, text)

    # Handle years like "ألفين وخمسة" or "الف وتسعمية خمسة وتسعين"
    def replace_year_ar(match):
        base_text = match.group(1)
        base = year_map.get(base_text)
        offset_text = match.group(2)
        offset = arabic_map.get(offset_text)
        
        if base is not None and offset is not None:
            return str(base + offset)
        return match.group(0)

    # First handle years with "و" (and)
    text = re.sub(r"(ألفين|الفين|ألف وتسعمية|الف وتسعمية|الف وتسعمائه|ألف وتسعمئة)\s+و\s*(\w+)", replace_year_ar, text)
    # Then handle years without "و"
    text = re.sub(r"(ألفين|الفين|ألف وتسعمية|الف وتسعمية|الف وتسعمائه|ألف وتسعمئة)\s+(\w+)", replace_year_ar, text)
    
    # Single word years
    for word, val in year_map.items():
        text = text.replace(word, str(val))

    # Replace single words
    tokens = text.split()
    result_tokens = []
    for token in tokens:
        clean_token = token.strip(" .,،")
        if clean_token in arabic_map:
            result_tokens.append(str(arabic_map[clean_token]))
        elif clean_token in english_map:
            result_tokens.append(str(english_map[clean_token]))
        else:
            result_tokens.append(token)

    return " ".join(result_tokens)

def extract_digit_sequence(text: str) -> str:
    """
    Extract all digit sequences and join them.
    Useful for phone numbers and national IDs.
    """
    # First parse spoken numbers
    text = parse_spoken_numbers(text)
    # Then extract all digits
    digits = re.findall(r"\d+", text)
    return "".join(digits)
