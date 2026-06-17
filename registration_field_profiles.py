
"""
Field-aware profiles for the Admission Robot registration system.
Defines parsing, normalization, and validation rules for each of the 39 fields.
"""

FIELD_PROFILES = {
    # --- PERSONAL DATA ---
    "full_name_ar": {
        "type": "name_pair",
        "section": "Personal Data",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["اسمي هو", "اسمي", "الاسم هو", "الاسم", "ماي نيم از", "ماي نيم"],
        "retry_ar": "من فضلك قل اسمك بالكامل (3 أسماء على الأقل) بدون أرقام.",
        "retry_en": "Please say your full name (at least 3 parts) without digits."
    },
    "full_name_en": {
        "type": "name_pair",
        "section": "Personal Data",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["my name is", "name is", "full name is"],
        "retry_ar": "من فضلك قل اسمك بالكامل بالإنجليزية.",
        "retry_en": "Please say your full name in English."
    },
    "date_of_birth": {
        "type": "date",
        "section": "Personal Data",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["تاريخ ميلادي هو", "اتولدت يوم", "تاريخ الميلاد", "birth date is", "born on"],
        "retry_ar": "التاريخ غير صحيح. من فضلك قل تاريخ ميلادك مثل: 11 12 2005 أو 11122005.",
        "retry_en": "Invalid date. Please say your date of birth like: 11 12 2005 or 11122005."
    },
    "place_of_birth": {
        "type": "location_ar",
        "section": "Personal Data",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["مكان الميلاد", "اتولدت في", "birth place is", "born in"],
        "retry_ar": "من فضلك قل محل ميلادك (المحافظة أو المدينة).",
        "retry_en": "Please say your place of birth (governorate or city)."
    },
    "nationality": {
        "type": "nationality",
        "section": "Personal Data",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["الجنسية", "جنسيتي هي", "nationality is"],
        "retry_ar": "من فضلك قل جنسيتك (مثلاً: مصري).",
        "retry_en": "Please say your nationality (e.g., Egyptian)."
    },
    "id_or_passport": {
        "type": "id_or_passport",
        "section": "Personal Data",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["رقم البطاقة", "رقم القومي", "البطاقة", "id number is", "passport number"],
        "retry_ar": "من فضلك قل الرقم القومي (14 رقم) أو رقم جواز السفر.",
        "retry_en": "Please say your national ID (14 digits) or passport number."
    },
    "gender": {
        "type": "gender",
        "section": "Personal Data",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["النوع", "الجنس", "gender is"],
        "retry_ar": "من فضلك قل النوع (ذكر أو أنثى).",
        "retry_en": "Please say your gender (male or female)."
    },
    "marital_status": {
        "type": "marital_status",
        "section": "Personal Data",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["الحالة الاجتماعية", "marital status is"],
        "retry_ar": "من فضلك قل الحالة الاجتماعية (أعزب، متزوج، مطلق، أرمل).",
        "retry_en": "Please say your marital status (single, married, divorced, widowed)."
    },

    # --- CONTACT ---
    "country": {
        "type": "country_ar",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["الدولة", "بلد الإقامة", "country is", "live in"],
        "retry_ar": "من فضلك قل الدولة التي تعيش فيها.",
        "retry_en": "Please say the country you live in."
    },
    "governorate": {
        "type": "location_ar",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["المحافظة", "محافظتي هي", "governorate is"],
        "retry_ar": "من فضلك قل المحافظة.",
        "retry_en": "Please say the governorate."
    },
    "district": {
        "type": "location_ar",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["الحي", "منطقتي هي", "district is"],
        "retry_ar": "من فضلك قل الحي أو المنطقة.",
        "retry_en": "Please say the district."
    },
    "city": {
        "type": "location_ar",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["المدينة", "مدينتي هي", "city is"],
        "retry_ar": "من فضلك قل المدينة.",
        "retry_en": "Please say the city."
    },
    "address": {
        "type": "address_ar",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["العنوان", "عنواني هو", "عنواني", "address is", "my address is"],
        "retry_ar": "من فضلك قل العنوان بالتفصيل.",
        "retry_en": "Please say your full address."
    },
    "home_phone": {
        "type": "phone",
        "section": "Contact",
        "required": False,
        "is_strict": False,
        "noise_prefixes": ["تليفون البيت", "رقم البيت", "home phone is"],
        "retry_ar": "من فضلك قل رقم تليفون المنزل.",
        "retry_en": "Please say your home phone number."
    },
    "student_mobile_no": {
        "type": "mobile",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["رقم الموبايل", "موبايلي", "mobile number is"],
        "retry_ar": "من فضلك قل رقم الموبايل (11 رقم يبدأ بـ 010 أو 011 أو 012 أو 015).",
        "retry_en": "Please say your mobile number (11 digits starting with 010, 011, 012, or 015)."
    },
    "mobile_no_2": {
        "type": "mobile",
        "section": "Contact",
        "required": False,
        "is_strict": True,
        "noise_prefixes": ["الرقم التاني", "موبايل تاني", "second mobile"],
        "retry_ar": "من فضلك قل رقم الموبايل الثاني أو قل 'لا يوجد'.",
        "retry_en": "Please say your second mobile number or say 'none'."
    },
    "email_address": {
        "type": "email",
        "section": "Contact",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["الايميل", "بريدي الإلكتروني", "email is"],
        "retry_ar": "من فضلك قل البريد الإلكتروني بشكل واضح.",
        "retry_en": "Please say your email address clearly."
    },

    # --- ACADEMIC ---
    "school_name": {
        "type": "free_text",
        "section": "Academic",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["اسم المدرسة", "مدرستي هي", "مدرستي", "مدرسة", "school is"],
        "retry_ar": "من فضلك قل اسم المدرسة.",
        "retry_en": "Please say your school name."
    },
    "certificate": {
        "type": "certificate",
        "section": "Academic",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["الشهادة", "نوع الشهادة", "certificate is"],
        "retry_ar": "من فضلك قل نوع الشهادة (مثلاً: ثانوية عامة، IG، American).",
        "retry_en": "Please say your certificate type (e.g., Thanaweya Amma, IG, American)."
    },
    "sector": {
        "type": "sector",
        "section": "Academic",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["الشعبة", "شعبة", "sector is"],
        "retry_ar": "من فضلك قل الشعبة (علمي علوم، علمي رياضة، أدبي).",
        "retry_en": "Please say your academic sector (Science, Math, Literary)."
    },
    "year_of_completion": {
        "type": "year",
        "section": "Academic",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["سنة التخرج", "سنة الحصول على الشهادة", "year of completion"],
        "retry_ar": "من فضلك قل سنة التخرج (مثلاً: 2024).",
        "retry_en": "Please say the year of completion (e.g., 2024)."
    },
    "percentage": {
        "type": "percentage",
        "section": "Academic",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["النسبة المئوية", "مجموعي", "percentage is"],
        "retry_ar": "من فضلك قل النسبة المئوية (من 0 لـ 100).",
        "retry_en": "Please say your percentage (0 to 100)."
    },
    "total_marks": {
        "type": "marks",
        "section": "Academic",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["المجموع", "درجاتي", "total marks is"],
        "retry_ar": "من فضلك قل مجموع الدرجات.",
        "retry_en": "Please say your total marks."
    },
    "seat_number": {
        "type": "seat_number",
        "section": "Academic",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["رقم الجلوس", "seat number is"],
        "retry_ar": "من فضلك قل رقم الجلوس.",
        "retry_en": "Please say your seat number."
    },

    # --- GUARDIAN ---
    "guardian_name": {
        "type": "personal_name",
        "section": "Guardian",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["اسم ولي الأمر", "ولي أمري هو", "guardian is"],
        "retry_ar": "من فضلك قل اسم ولي الأمر بالكامل.",
        "retry_en": "Please say your guardian's full name."
    },
    "relationship": {
        "type": "relationship",
        "section": "Guardian",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["صلة القرابة", "relationship is"],
        "retry_ar": "من فضلك قل صلة القرابة (أب، أم، إلخ).",
        "retry_en": "Please say your relationship to the guardian."
    },
    "guardian_id_or_passport": {
        "type": "id_or_passport",
        "section": "Guardian",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["رقم بطاقة ولي الأمر", "id number is"],
        "retry_ar": "من فضلك قل الرقم القومي لولي الأمر (14 رقم).",
        "retry_en": "Please say your guardian's national ID (14 digits)."
    },
    "guardian_profession": {
        "type": "profession",
        "section": "Guardian",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["وظيفة ولي الأمر", "بيشتغل", "profession is"],
        "retry_ar": "من فضلك قل وظيفة ولي الأمر.",
        "retry_en": "Please say your guardian's profession."
    },
    "guardian_employer": {
        "type": "free_text",
        "section": "Guardian",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["جهة العمل", "بيشتغل في", "employer is"],
        "retry_ar": "من فضلك قل جهة عمل ولي الأمر.",
        "retry_en": "Please say your guardian's employer."
    },
    "guardian_nationality": {
        "type": "nationality",
        "section": "Guardian",
        "required": True,
        "is_strict": False,
        "noise_prefixes": ["جنسية ولي الأمر", "nationality is"],
        "retry_ar": "من فضلك قل جنسية ولي الأمر.",
        "retry_en": "Please say your guardian's nationality."
    },
    "guardian_country": {
        "type": "country_ar",
        "section": "Guardian",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["دولة ولي الأمر", "country is"],
        "retry_ar": "من فضلك قل الدولة التي يعيش فيها ولي الأمر.",
        "retry_en": "Please say the country your guardian lives in."
    },
    "guardian_district": {
        "type": "location_ar",
        "section": "Guardian",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["حي ولي الأمر", "district is"],
        "retry_ar": "من فضلك قل الحي أو المنطقة التي يعيش فيها ولي الأمر.",
        "retry_en": "Please say the district your guardian lives in."
    },
    "guardian_address": {
        "type": "address_ar",
        "section": "Guardian",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["عنوان ولي الأمر", "address is"],
        "retry_ar": "من فضلك قل عنوان ولي الأمر.",
        "retry_en": "Please say your guardian's address."
    },
    "guardian_work_address": {
        "type": "address_ar",
        "section": "Guardian",
        "required": False,
        "is_strict": True,
        "noise_prefixes": ["عنوان العمل", "work address is"],
        "retry_ar": "من فضلك قل عنوان عمل ولي الأمر أو قل 'لا يوجد'.",
        "retry_en": "Please say your guardian's work address or say 'none'."
    },
    "guardian_mobile_no": {
        "type": "mobile",
        "section": "Guardian",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["موبايل ولي الأمر", "mobile number is"],
        "retry_ar": "من فضلك قل رقم موبايل ولي الأمر (11 رقم).",
        "retry_en": "Please say your guardian's mobile number (11 digits)."
    },
    "guardian_home_phone": {
        "type": "phone",
        "section": "Guardian",
        "required": False,
        "is_strict": False,
        "noise_prefixes": ["تليفون البيت", "home phone is"],
        "retry_ar": "من فضلك قل رقم تليفون منزل ولي الأمر.",
        "retry_en": "Please say your guardian's home phone number."
    },
    "guardian_work_no": {
        "type": "phone",
        "section": "Guardian",
        "required": False,
        "is_strict": False,
        "noise_prefixes": ["تليفون العمل", "work number is"],
        "retry_ar": "من فضلك قل رقم تليفون عمل ولي الأمر.",
        "retry_en": "Please say your guardian's work phone number."
    },
    "guardian_email_address": {
        "type": "email",
        "section": "Guardian",
        "required": False,
        "is_strict": True,
        "noise_prefixes": ["ايميل ولي الأمر", "email is"],
        "retry_ar": "من فضلك قل البريد الإلكتروني لولي الأمر.",
        "retry_en": "Please say your guardian's email address."
    },

    # --- FACULTY ---
    "college_preference_1": {
        "type": "faculty",
        "section": "Faculty",
        "required": True,
        "is_strict": True,
        "noise_prefixes": ["عايز أدخل", "حلمي أدخل", "college is", "faculty is"],
        "retry_ar": "من فضلك قل الكلية التي تريد التقديم لها (هندسة، حاسبات، صيدلة، إلخ).",
        "retry_en": "Please say the faculty you want to apply for (Engineering, Computer Science, Pharmacy, etc.)."
    }
}
