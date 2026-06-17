import os
import sys
import time
import argparse
import threading
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_DIR / "main.py"


def send_command(proc: subprocess.Popen, command: str) -> None:
    """Send one command to main.py stdin."""
    if proc.poll() is not None:
        return

    if proc.stdin:
        print(f"\n[Runner -> main.py] {command}", flush=True)
        proc.stdin.write(command + "\n")
        proc.stdin.flush()


def should_auto_listen(line: str) -> bool:
    """
    Auto-send listen after robot questions/prompts.
    We trigger only on Robot: lines.
    """
    clean = line.strip()

    if not clean.startswith("Robot:"):
        return False

    # Avoid listening after non-question/debug phrases if needed later.
    blocked_phrases = [
        "This is a test voice",
    ]

    return not any(phrase in clean for phrase in blocked_phrases)


def reader_loop(proc: subprocess.Popen, args, state: dict) -> None:
    """
    Read main.py output and auto-send listen after every Robot question.
    """
    assert proc.stdout is not None

    for raw_line in proc.stdout:
        print(raw_line, end="", flush=True)

        line = raw_line.strip()

        if args.auto_listen and should_auto_listen(line):
            if state["listen_count"] >= args.max_listens:
                print("\n[Runner] Max auto-listen count reached. Stop with Ctrl+C.", flush=True)
                continue

            state["listen_count"] += 1

            # main.py usually prints Robot: before/while TTS plays.
            # The command will wait in stdin until main.py asks for input again.
            time.sleep(args.listen_delay)
            send_command(proc, "listen")


def start_main_process() -> subprocess.Popen:
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"main.py not found at: {MAIN_FILE}")

    env = os.environ.copy()
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start Admission Robot main.py directly in Arabic registration voice mode."
    )
    parser.add_argument(
        "--listen-delay",
        type=float,
        default=0.7,
        help="Seconds to wait before auto-sending listen after each Robot line.",
    )
    parser.add_argument(
        "--max-listens",
        type=int,
        default=80,
        help="Maximum number of automatic listen commands before stopping auto-listen.",
    )
    parser.add_argument(
        "--no-auto-listen",
        action="store_true",
        help="Only start Arabic registration, but do not auto-send listen.",
    )

    args = parser.parse_args()
    args.auto_listen = not args.no_auto_listen

    print("=" * 70)
    print("Admission Robot Voice Demo Runner")
    print("=" * 70)
    print("This runner will start main.py and automatically send:")
    print("  lang ar")
    print("  mode registration")
    print("  start form")
    print()
    print("Then, after each Robot question, it will auto-send:")
    print("  listen")
    print()
    print("You only answer by voice.")
    print("Press Ctrl+C to stop.")
    print("=" * 70)

    proc = start_main_process()
    state = {"listen_count": 0}

    reader = threading.Thread(
        target=reader_loop,
        args=(proc, args, state),
        daemon=True,
    )
    reader.start()

    try:
        # Give main.py time to boot.
        time.sleep(1.0)

        send_command(proc, "lang en")
        time.sleep(0.4)

        send_command(proc, "mode registration")
        time.sleep(0.4)

        send_command(proc, "start form")

        while proc.poll() is None:
            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n[Runner] Stopping demo...", flush=True)
        send_command(proc, "exit")
        time.sleep(0.5)

        if proc.poll() is None:
            proc.terminate()

    finally:
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()