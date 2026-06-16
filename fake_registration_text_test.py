import os
import sys
import time
import argparse
import threading
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_DIR / "main.py"


# Full 24-field Arabic registration flow
# Important:
# Sensitive fields need confirmation after them.
FAKE_REGISTRATION_INPUTS = [
    # Start system
    "lang ar",
    "mode registration",
    "start form",

    # 1. Personal Data
    "محمود محمد نجيب",          # full_name_ar
    "Mahmoud Mohamed Nagib",   # full_name_en
    "15/08/2005",              # date_of_birth
    "القاهرة",                 # place_of_birth
    "مصري",                    # nationality

    "30510201012345",          # id_or_passport
    "نعم",                     # confirm ID

    "ذكر",                     # gender
    "أعزب",                    # marital_status

    # 2. Contact
    "القاهرة",                 # governorate
    "مدينة نصر",               # city
    "20 شارع نجاتي سراج الحي الثامن مدينة نصر",  # address

    "01012345678",             # student_mobile_no
    "نعم",                     # confirm student mobile

    "mahmoud.nagib09@gmail.com",  # email_address
    "نعم",                        # confirm email

    # 3. Academic
    "مدرسة النصر",             # school_name
    "ثانوية عامة",             # certificate
    "2024",                    # year_of_completion

    "92.5",                    # percentage
    "نعم",                     # confirm percentage

    # 4. Guardian
    "محمد نجيب",               # guardian_name
    "الأب",                    # relationship
    "مهندس",                   # guardian_profession
    "مصري",                    # guardian_nationality
    "نفس العنوان",             # guardian_address, should copy student address

    "01112345678",             # guardian_mobile_no
    "نعم",                     # confirm guardian mobile

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
        print(line, end="", flush=True)


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

    print(f"\n[Fake Test -> main.py] {text}", flush=True)
    proc.stdin.write(text + "\n")
    proc.stdin.flush()
    time.sleep(delay)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fake text test for Admission Robot full 24-field registration flow."
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
    print("This will run main.py and fill the full 24-field registration")
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