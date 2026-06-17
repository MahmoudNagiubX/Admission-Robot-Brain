import os
import sys
import time
import argparse
import threading
import subprocess
from pathlib import Path
from console_utils import format_for_terminal


PROJECT_DIR = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_DIR / "main.py"


# Full 39-field Arabic registration flow
# Important:
# EVERY field now needs confirmation after it.
FAKE_REGISTRATION_INPUTS = [
    # Start system
    "lang ar",
    "mode registration",
    "start form",

    # 1. Personal Data
    "محمود محمد نجيب",          # full_name_ar (fills both ar and en)
    "نعم",                     # confirm name pair

    "15/08/2005",              # date_of_birth
    "نعم",                     # confirm DOB

    "القاهرة",                 # place_of_birth
    "نعم",                     # confirm place_of_birth

    "مصري",                    # nationality
    "نعم",                     # confirm nationality

    "30510201012345",          # id_or_passport
    "نعم",                     # confirm ID

    "ذكر",                     # gender
    "نعم",                     # confirm gender

    "أعزب",                    # marital_status
    "نعم",                     # confirm marital_status

    # 2. Contact
    "مصر",                     # country
    "نعم",                     # confirm country

    "القاهرة",                 # governorate
    "نعم",                     # confirm governorate

    "الحي الثامن",             # district
    "نعم",                     # confirm district

    "مدينة نصر",               # city
    "نعم",                     # confirm city

    "20 شارع نجاتي سراج الحي الثامن مدينة نصر",  # address
    "نعم",                     # confirm address

    "0223456789",              # home_phone
    "نعم",                     # confirm home_phone

    "01012345678",             # student_mobile_no
    "نعم",                     # confirm student mobile

    "01123456789",             # mobile_no_2
    "نعم",                     # confirm mobile 2

    "mahmoud.nagib09@gmail.com",  # email_address
    "نعم",                        # confirm email

    # 3. Academic
    "مدرسة النصر",             # school_name
    "نعم",                     # confirm school_name

    "ثانوية عامة",             # certificate
    "نعم",                     # confirm certificate

    "علمي رياضة",              # sector
    "نعم",                     # confirm sector

    "2024",                    # year_of_completion
    "نعم",                     # confirm year

    "92.5",                    # percentage
    "نعم",                     # confirm percentage

    "385",                     # total_marks
    "نعم",                     # confirm total_marks

    "123456",                  # seat_number
    "نعم",                     # confirm seat_number

    # 4. Guardian
    "محمد نجيب",               # guardian_name
    "نعم",                     # confirm guardian_name

    "الأب",                    # relationship
    "نعم",                     # confirm relationship

    "27501010123456",          # guardian_id_or_passport
    "نعم",                     # confirm guardian ID

    "مهندس",                   # guardian_profession
    "نعم",                     # confirm profession

    "شركة المقاولون العرب",    # guardian_employer
    "نعم",                     # confirm employer

    "مصري",                    # guardian_nationality
    "نعم",                     # confirm guardian nationality

    "مصر",                     # guardian_country
    "نعم",                     # confirm guardian country

    "الحي الثامن",             # guardian_district
    "نعم",                     # confirm guardian district

    "نفس العنوان",             # guardian_address, should copy student address
    "نعم",                     # confirm guardian address

    "10 شارع عباس العقاد مدينة نصر", # guardian_work_address
    "نعم",                     # confirm guardian work address

    "01112345678",             # guardian_mobile_no
    "نعم",                     # confirm guardian mobile

    "0223456789",              # guardian_home_phone
    "نعم",                     # confirm guardian home phone

    "0222223333",              # guardian_work_no
    "نعم",                     # confirm guardian work phone

    "guardian@example.com",    # guardian_email_address
    "نعم",                     # confirm guardian email

    # 5. Faculty
    "هندسة",                   # college_preference_1
    "نعم",                     # confirm faculty

    # Debug / final output
    "show form",
    "export form",
    "status form",
    "exit",
]


def reader_loop(proc: subprocess.Popen) -> None:
    """Print main.py output live."""
    assert proc.stdout is not None

    for line in proc.stdout:
        print(format_for_terminal(line), end="", flush=True)


def start_main_process() -> subprocess.Popen:
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"main.py not found at: {MAIN_FILE}")

    env = os.environ.copy()

    # Make test faster and avoid robot voice during fake text test.
    env["ENABLE_TTS"] = "false"
    env["ENABLE_VOICE_INPUT"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    return subprocess.Popen(
        [sys.executable, "-u", str(MAIN_FILE)],
        cwd=str(PROJECT_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )


def send(proc: subprocess.Popen, text: str, delay: float) -> None:
    if proc.poll() is not None:
        print("[Fake Test] main.py already stopped.")
        return

    assert proc.stdin is not None

    print(format_for_terminal(f"\n[Fake Test -> main.py] {text}"), flush=True)
    proc.stdin.write(text + "\n")
    proc.stdin.flush()
    time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fake text test for Admission Robot full 39-field registration flow."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between inputs in seconds.",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Admission Robot — Fake Text Registration Test")
    print("=" * 70)
    print("This will run main.py and fill the full 39-field registration")
    print("using fake TEXT inputs, not voice.")
    print()
    print("TTS and voice input are disabled for this test.")
    print("=" * 70)

    proc = start_main_process()

    reader = threading.Thread(target=reader_loop, args=(proc,), daemon=True)
    reader.start()

    try:
        # Give main.py time to print help menu.
        time.sleep(1.0)

        for item in FAKE_REGISTRATION_INPUTS:
            send(proc, item, args.delay)

        # Wait a little for final output.
        time.sleep(2.0)

    except KeyboardInterrupt:
        print("\n[Fake Test] Stopped by user.", flush=True)

    finally:
        if proc.poll() is None:
            try:
                send(proc, "exit", 0.2)
            except Exception:
                pass
            proc.terminate()


if __name__ == "__main__":
    main()