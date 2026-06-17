
import json
import csv
import os
import re
from pathlib import Path

def normalize_arabic(text):
    if not text: return ""
    # Remove diacritics
    text = re.sub(r"[\u064B-\u065F]", "", text)
    # Remove tatweel
    text = text.replace("\u0640", "")
    # Normalize alef
    text = re.sub(r"[أإآٱ]", "ا", text)
    # Normalize yeh
    text = text.replace("ى", "ي")
    # Normalize waw
    text = text.replace("ؤ", "و")
    # Normalize hamza on yeh
    text = text.replace("ئ", "ي")
    # Optionally normalize teh marbuta to heh for matching only
    # match_text = text.replace("ة", "ه")
    
    # Remove punctuation and collapse spaces
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", "", text).strip() # Remove spaces for matching
    return text

def normalize_english(text):
    if not text: return ""
    text = text.lower()
    # Normalize hyphen/underscore to space
    text = text.replace("-", " ").replace("_", " ")
    # Remove punctuation except spaces
    text = re.sub(r"[^a-z\s]", " ", text)
    # Collapse spaces and trim
    text = re.sub(r"\s+", " ", text).strip()
    return text

class NameLexiconBuilder:
    def __init__(self):
        self.entries = {} # Key: primary_ar
        self.raw_folder = Path("data/raw_names")
        if not self.raw_folder.exists():
            self.raw_folder = Path("data/romames")
        
        self.output_path = Path("data/name_lexicon.json")
        self.stats = {
            "raw_folder_used": str(self.raw_folder),
            "files_found": [],
            "sources": {}
        }

    def add_entry(self, ar, en, gender=None, source="unknown", entry_type="given_name"):
        if not ar or not en: return
        
        ar_norm = normalize_arabic(ar)
        en_norm = normalize_english(en)
        
        if not ar_norm or not en_norm: return

        if ar_norm not in self.entries:
            self.entries[ar_norm] = {
                "ar": ar, # Keep original as display
                "en_primary": en, # Keep original as display
                "en_aliases": {en_norm},
                "ar_aliases": {ar_norm},
                "type": entry_type,
                "gender": gender,
                "source": {source}
            }
        else:
            entry = self.entries[ar_norm]
            entry["en_aliases"].add(en_norm)
            entry["ar_aliases"].add(ar_norm)
            entry["source"].add(source)
            if gender and not entry["gender"]:
                entry["gender"] = gender

    def load_starter_lexicon(self):
        starter = [
            # Male
            ("محمد", "Mohamed", ["mohammed", "muhammad", "mohammad"]),
            ("محمود", "Mahmoud", ["mahamud", "mahmud"]),
            ("أحمد", "Ahmed", ["ahmad", "ahman"]),
            ("نجيب", "Nagib", ["naguib", "nageeb", "najib"]),
            ("محسن", "Mohsen", ["mohsin"]),
            ("علي", "Ali", []),
            ("عمر", "Omar", []),
            ("عمرو", "Amr", []),
            ("زياد", "Zeyad", ["zyad", "ziyad"]),
            ("يوسف", "Youssef", ["yousef", "yosef"]),
            ("مصطفى", "Mostafa", ["mustafa"]),
            ("حسن", "Hassan", []),
            ("حسين", "Hussein", []),
            ("طارق", "Tarek", []),
            ("كريم", "Karim", ["kareem"]),
            ("فاروق", "Farouk", ["farooq"]),
            ("مينا", "Mina", ["mena"]),
            ("بيتر", "Peter", []),
            ("بيشوي", "Bishoy", []),
            ("جورج", "George", []),
            ("فادي", "Fady", []),
            ("رامي", "Ramy", []),
            ("هاني", "Hany", []),
            ("إيهاب", "Ehab", ["ihab"]),
            ("إسلام", "Islam", []),
            ("حمزة", "Hamza", []),
            ("سيف", "Seif", ["saif"]),
            ("ياسين", "Yassin", ["yaseen"]),
            ("آدم", "Adam", []),
            ("إياد", "Iyad", ["eyad"]),
            ("مازن", "Mazen", []),
            ("مالك", "Malek", ["malik"]),
            ("مروان", "Marwan", []),
            ("عبد الله", "Abdallah", ["abdullah"]),
            ("عبد الرحمن", "Abdelrahman", ["abdulrahman", "abdul rahman", "abdel rahman"]),
            ("عبد العزيز", "Abdelaziz", []),
            ("عبد الحميد", "Abdelhamid", []),
            ("عبد السلام", "Abdelsalam", []),
            ("عبد الرحيم", "Abdelrahim", []),
            ("عبد الناصر", "Abdelnasser", []),
            ("صلاح", "Salah", []),
            ("خالد", "Khaled", []),
            ("وليد", "Walid", []),
            ("حسام", "Hossam", []),
            ("هشام", "Hesham", []),
            ("شريف", "Sherif", []),
            ("أشرف", "Ashraf", []),
            ("سمير", "Samir", []),
            ("سامح", "Sameh", []),
            ("أسامة", "Osama", []),
            ("أيمن", "Ayman", []),
            ("علاء", "Alaa", []),
            ("وائل", "Wael", []),
            ("مجدي", "Magdy", []),
            ("عادل", "Adel", []),
            ("عماد", "Emad", ["imad"]),
            ("نادر", "Nader", []),
            ("حاتم", "Hatem", []),
            ("حازم", "Hazem", []),
            ("معتز", "Moataz", ["motaz"]),
            ("تامر", "Tamer", []),
            ("شادي", "Shady", []),
            ("كيرو", "Kiro", []),
            ("كيرلس", "Kirollos", []),
            ("شنودة", "Shenouda", []),
            
            # Female
            ("مريم", "Mariam", ["maryam"]),
            ("سلمى", "Salma", []),
            ("سما", "Sama", []),
            ("سماء", "Samaa", []),
            ("نور", "Nour", ["noor"]),
            ("جنى", "Jana", []),
            ("جنة", "Janna", []),
            ("ملك", "Malak", []),
            ("حبيبة", "Habiba", []),
            ("فريدة", "Farida", []),
            ("فاطمة", "Fatma", ["fatima"]),
            ("عائشة", "Aisha", ["aicha"]),
            ("آية", "Aya", ["ayah"]),
            ("منة", "Menna", []),
            ("منة الله", "Menatallah", []),
            ("ندى", "Nada", []),
            ("يارا", "Yara", []),
            ("سارة", "Sara", ["sarah"]),
            ("هنا", "Hana", []),
            ("هناء", "Hanaa", []),
            ("هاجر", "Hagar", []),
            ("نورهان", "Nourhan", ["norhan"]),
            ("شهد", "Shahd", []),
            ("ريم", "Reem", []),
            ("رنيم", "Raneem", []),
            ("ميار", "Mayar", []),
            ("ليلى", "Laila", ["layla"]),
            ("هدير", "Hadeer", []),
            ("رضوى", "Radwa", []),
            ("بسنت", "Passant", ["basant"]),
            ("إسراء", "Esraa", ["israa"]),
            ("دعاء", "Doaa", ["duaa"]),
            ("رنا", "Rana", []),
            ("روان", "Rawan", []),
            ("إنجي", "Engy", ["ingy"]),
            ("ساندي", "Sandy", []),
            ("ياسمين", "Yasmin", ["yasmine"]),
            ("أسماء", "Asmaa", []),
            ("رؤى", "Roaa", []),
            ("رقية", "Rokaia", ["ruqaya"]),
            ("خديجة", "Khadija", ["khadiga"]),
            ("جودي", "Joudy", ["judy"]),
            ("لجين", "Lojain", ["logain"]),
            ("هالة", "Hala", []),
            ("هبة", "Heba", []),
            ("دينا", "Dina", []),
            ("دنيا", "Donia", []),
            ("داليا", "Dalia", []),
            ("شيماء", "Shaimaa", []),
            ("مي", "Mai", ["may"]),
            ("مروة", "Marwa", []),
            ("نسمة", "Nesma", []),
            ("بسمة", "Basma", []),
            ("تسنيم", "Tasneem", ["tasnim"]),
            
            # Compounds
            ("نور الدين", "Nour El Din", []),
            ("سيف الدين", "Seif El Din", []),
            ("صلاح الدين", "Salah El Din", []),
        ]
        
        count = 0
        for ar, en, aliases in starter:
            self.add_entry(ar, en, source="starter", entry_type="compound_name" if " " in ar else "given_name")
            for alias in aliases:
                self.add_entry(ar, alias, source="starter")
            count += 1
        
        self.stats["sources"]["starter"] = count

    def process_muslim_names_json(self):
        path = self.raw_folder / "muslim_names.json"
        if not path.exists(): return
        
        self.stats["files_found"].append(path.name)
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Assuming list of objects with english_name, arabic_name, gender
                for item in data:
                    ar = item.get("arabic_name")
                    en = item.get("english_name")
                    gender = item.get("gender")
                    if ar and en:
                        self.add_entry(ar, en, gender=gender, source="muslim_names_json")
                        count += 1
        except Exception as e:
            print(f"Error loading {path}: {e}")
        
        self.stats["sources"]["muslim_names_json"] = count

    def process_muslim_names_csv(self):
        path = self.raw_folder / "muslim_names.csv"
        if not path.exists(): return
        
        self.stats["files_found"].append(path.name)
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ar = row.get("arabic_name")
                    en = row.get("english_name")
                    gender = row.get("gender")
                    if ar and en:
                        self.add_entry(ar, en, gender=gender, source="muslim_names_csv")
                        count += 1
        except Exception as e:
            print(f"Error loading {path}: {e}")
            
        self.stats["sources"]["muslim_names_csv"] = count

    def process_train_en_ar(self):
        path_en = self.raw_folder / "trainEN.csv"
        path_ar = self.raw_folder / "trainAR.csv"
        if not path_en.exists() or not path_ar.exists(): return
        
        self.stats["files_found"].extend([path_en.name, path_ar.name])
        count = 0
        try:
            with open(path_en, "r", encoding="utf-8") as fe, open(path_ar, "r", encoding="utf-8") as fa:
                # Assuming these are simple line-by-line files or CSV with one column
                lines_en = fe.readlines()
                lines_ar = fa.readlines()
                
                if len(lines_en) != len(lines_ar):
                    print(f"Warning: trainEN ({len(lines_en)}) and trainAR ({len(lines_ar)}) have different line counts.")
                
                for en_line, ar_line in zip(lines_en, lines_ar):
                    en = en_line.strip().strip('"').strip("'")
                    ar = ar_line.strip().strip('"').strip("'")
                    if en and ar:
                        self.add_entry(ar, en, source="train_en_ar")
                        count += 1
        except Exception as e:
            print(f"Error loading trainEN/AR: {e}")
            
        self.stats["sources"]["train_en_ar"] = count

    def process_dict_final(self):
        path = self.raw_folder / "dict_FINAL.json"
        if not path.exists(): return
        
        self.stats["files_found"].append(path.name)
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Dictionary: English key -> Arabic value
                if isinstance(data, dict):
                    for en, ar in data.items():
                        if isinstance(ar, str) and ar and en:
                            self.add_entry(ar, en, source="dict_final", entry_type="unknown")
                            count += 1
        except Exception as e:
            print(f"Error loading {path}: {e}")
            
        self.stats["sources"]["dict_final"] = count

    def process_full_names_list(self):
        path = self.raw_folder / "Full-Names-List.csv"
        if not path.exists(): return
        
        self.stats["files_found"].append(path.name)
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Arabic-only names. We'll add them with en_primary=None or skip if no translation?
                # Prompt says: keep Arabic side, generate English using lexicon/fallback/LLM later
                # We can add it with a placeholder or just as an ar_alias to an entry if it matches
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        ar = row[0].strip()
                        if ar:
                            ar_norm = normalize_arabic(ar)
                            if ar_norm and ar_norm not in self.entries:
                                # We need an English primary. Since we don't have it, we might skip
                                # OR we can use a basic phonetic transliteration as a placeholder
                                # But for now, let's only add if we have some way to map it.
                                # Actually, if it's a full name, we might want to split it.
                                pass
                            elif ar_norm in self.entries:
                                self.entries[ar_norm]["ar_aliases"].add(ar_norm)
                                self.entries[ar_norm]["source"].add("full_names_list")
                                count += 1
        except Exception as e:
            print(f"Error loading {path}: {e}")
            
        self.stats["sources"]["full_names_list"] = count

    def build(self):
        print(f"Building lexicon from {self.raw_folder}...")
        self.load_starter_lexicon()
        self.process_muslim_names_json()
        self.process_muslim_names_csv()
        self.process_train_en_ar()
        self.process_dict_final()
        self.process_full_names_list()
        
        final_entries = []
        alias_count = 0
        for ar_norm, data in self.entries.items():
            entry = {
                "ar": data["ar"],
                "en_primary": data["en_primary"],
                "en_aliases": sorted(list(data["en_aliases"])),
                "ar_aliases": sorted(list(data["ar_aliases"])),
                "type": data["type"],
                "gender": data["gender"],
                "source": sorted(list(data["source"]))
            }
            final_entries.append(entry)
            alias_count += len(entry["en_aliases"]) + len(entry["ar_aliases"])
            
        output = {
            "version": 1,
            "source_files": self.stats["files_found"],
            "stats": {
                "entry_count": len(final_entries),
                "alias_count": alias_count,
                "sources": self.stats["sources"]
            },
            "entries": final_entries
        }
        
        os.makedirs(self.output_path.parent, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            
        print(f"Lexicon built successfully at {self.output_path}")
        print(f"Final Entry Count: {len(final_entries)}")
        print(f"Final Alias Count: {alias_count}")
        print(f"Stats: {json.dumps(self.stats, indent=2)}")

if __name__ == "__main__":
    builder = NameLexiconBuilder()
    builder.build()
