#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Εκκίνηση με ένα κλικ (το καλούν τα run.bat / run.sh).

  1. Ελέγχει την έκδοση Python (3.10+).
  2. Εγκαθιστά τις βιβλιοθήκες ΜΟΝΟ όταν αλλάξει το requirements.txt
     (όχι σε κάθε εκκίνηση — γρηγορότερο και χωρίς internet μετά την 1η φορά).
  3. Αν ο server τρέχει ήδη, απλώς ανοίγει τη σελίδα.
  4. Αλλιώς ξεκινά τον server και ανοίγει τον browser μόλις είναι έτοιμος.
  5. Στα Windows προσφέρει (μία φορά) συντόμευση στην επιφάνεια εργασίας.

    python launcher.py                 # κανονική εκκίνηση
    python launcher.py --no-browser    # χωρίς άνοιγμα browser
    python launcher.py --shortcut      # μόνο δημιουργία συντόμευσης (Windows)

Ασφάλεια: ο server ακούει ΜΟΝΟ στο 127.0.0.1 (όχι στο δίκτυο)· ο έλεγχος
«τρέχει ήδη;» γίνεται απευθείας στο 127.0.0.1 χωρίς proxy· οι διαδρομές για τη
συντόμευση περνούν στο PowerShell ως μεταβλητές περιβάλλοντος, όχι μέσα στην
εντολή (όχι injection από ονόματα φακέλων).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 5000
URL = f"http://localhost:{PORT}/"
HEALTH = f"http://127.0.0.1:{PORT}/health"
MIN_PYTHON = (3, 10)
MARKER = Path(sys.prefix) / ".ai_detector_requirements.sha256"
SHORTCUT_ASKED = Path(sys.prefix) / ".ai_detector_shortcut_asked"


def say(el: str, en: str) -> None:
    print(f"{el}\n  ({en})", flush=True)


def check_python() -> bool:
    if sys.version_info >= MIN_PYTHON:
        return True
    say(f"❌ Χρειάζεται Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} ή νεότερη "
        f"(βρέθηκε {sys.version.split()[0]}). Κατέβασέ την από https://www.python.org/downloads/",
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.")
    return False


def requirements_hash() -> str:
    return hashlib.sha256((ROOT / "requirements.txt").read_bytes()).hexdigest()


def ensure_requirements() -> bool:
    wanted = requirements_hash()
    try:
        if MARKER.read_text(encoding="utf-8").strip() == wanted:
            return True
    except OSError:
        pass
    say("📚 Εγκατάσταση βιβλιοθηκών (μόνο την πρώτη φορά ή μετά από ενημέρωση)…",
        "Installing dependencies (first run or after an update)…")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                             "-q", "-r", str(ROOT / "requirements.txt")])
    if result.returncode != 0:
        say("❌ Η εγκατάσταση απέτυχε. Έλεγξε τη σύνδεση στο internet και ξαναδοκίμασε.",
            "Installation failed. Check your internet connection and try again.")
        return False
    try:
        MARKER.write_text(wanted, encoding="utf-8")
    except OSError:
        pass
    return True


def server_status() -> str:
    """'ours' = τρέχει ήδη ο detector, 'other' = η θύρα είναι πιασμένη από άλλο
    πρόγραμμα, 'free' = δεν απαντά τίποτα."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(HEALTH, timeout=2) as r:
            data = json.loads(r.read(64 * 1024))
            return "ours" if isinstance(data, dict) and data.get("status") == "ok" else "other"
    except (ValueError, json.JSONDecodeError):
        return "other"
    except urllib.error.HTTPError:
        return "other"
    except OSError:
        return "free"


def open_browser_when_ready(timeout: float = 60.0) -> None:
    def wait_and_open():
        deadline = time.time() + timeout
        while time.time() < deadline:
            if server_status() == "ours":
                webbrowser.open(URL)
                return
            time.sleep(0.5)
    threading.Thread(target=wait_and_open, daemon=True).start()


def create_shortcut() -> bool:
    """Συντόμευση «AI Detector» στην επιφάνεια εργασίας (μόνο Windows)."""
    if os.name != "nt":
        return False
    env = dict(os.environ, AID_TARGET=str(ROOT / "run.bat"), AID_DIR=str(ROOT))
    script = ("$d=[Environment]::GetFolderPath('Desktop');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'AI Detector.lnk'));"
              "$s.TargetPath=$env:AID_TARGET;$s.WorkingDirectory=$env:AID_DIR;"
              "$s.Description='AI Content Detector';$s.Save()")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                                env=env, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def offer_shortcut() -> None:
    if os.name != "nt" or SHORTCUT_ASKED.exists() or not sys.stdin or not sys.stdin.isatty():
        return
    try:
        SHORTCUT_ASKED.write_text("1", encoding="utf-8")
        answer = input("➕ Θέλεις συντόμευση «AI Detector» στην επιφάνεια εργασίας; [Ν/ο] "
                       "(Desktop shortcut? [Y/n]) ").strip().lower()
    except (OSError, EOFError):
        return
    if answer in ("", "ν", "ναι", "y", "yes"):
        if create_shortcut():
            say("✅ Η συντόμευση δημιουργήθηκε.", "Shortcut created.")
        else:
            say("⚠ Δεν δημιουργήθηκε η συντόμευση (δεν πειράζει).", "Could not create the shortcut.")


def main() -> int:
    ap = argparse.ArgumentParser(description="AI Content Detector launcher")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--shortcut", action="store_true")
    args = ap.parse_args()

    if not check_python():
        return 1
    if args.shortcut:
        ok = create_shortcut()
        say("✅ Η συντόμευση δημιουργήθηκε." if ok else "⚠ Δεν δημιουργήθηκε η συντόμευση.",
            "Shortcut created." if ok else "Could not create the shortcut.")
        return 0 if ok else 1
    if not ensure_requirements():
        return 1

    status = server_status()
    if status == "ours":
        say(f"ℹ Ο detector τρέχει ήδη — ανοίγω τη σελίδα {URL}",
            "The detector is already running — opening the page.")
        if not args.no_browser:
            webbrowser.open(URL)
        return 0
    if status == "other":
        say(f"❌ Η θύρα {PORT} χρησιμοποιείται από άλλο πρόγραμμα. Κλείσ' το και ξαναδοκίμασε.",
            f"Port {PORT} is used by another program. Close it and try again.")
        return 1

    offer_shortcut()
    if not args.no_browser:
        open_browser_when_ready()
    sys.path.insert(0, str(ROOT))
    import ai_detector_server
    ai_detector_server.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
