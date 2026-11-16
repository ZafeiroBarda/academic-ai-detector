#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ενημέρωση σε νέα έκδοση χωρίς να χαθούν οι ρυθμίσεις και τα δεδομένα σου.

Αν ο φάκελος είναι git clone → `git pull` (τίποτα άλλο δεν χρειάζεται).

Αν κατέβασες ZIP: αποσυμπίεσε τη ΝΕΑ έκδοση σε νέο φάκελο, τρέξε εκεί το
update.bat (ή `python tools/update.py`) και δώσε τον ΠΑΛΙΟ φάκελο. Μεταφέρονται:
  • search_config.json   (κλειδιά OpenAlex / Brave / Google)
  • binoculars_config.json, calibration_profile.json (βαθμονομήσεις)
  • .web_cache.sqlite3   (cache εξωτερικών ελέγχων)
  • .analysis_history.sqlite3 (ιστορικό αναλύσεων)
  • corpus/              (παλιές εργασίες για σύγκριση)
Το venv ΔΕΝ μεταφέρεται (φτιάχνεται ξανά αυτόματα με το run.bat).

Ασφάλεια: αντιγράφονται ΜΟΝΟ τα παραπάνω, όχι συντομεύσεις/symlinks, μόνο
αρχεία εργασιών στο corpus (.docx/.pdf/.txt/.md)· τίποτα δεν
αντικαθίσταται — αν υπάρχει ήδη αρχείο στον νέο φάκελο, μένει όπως είναι.
Τα αρχεία με κλειδιά παίρνουν δικαιώματα μόνο για τον χρήστη.

    python tools/update.py                         # ρωτά τον παλιό φάκελο
    python tools/update.py --from "C:\\...\\ai-detector-main-old"
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_FILES = ("search_config.json", "binoculars_config.json", "calibration_profile.json")
DATA_FILES = (".web_cache.sqlite3", ".analysis_history.sqlite3")
CORPUS_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}


def say(el: str, en: str) -> None:
    print(f"{el}\n  ({en})", flush=True)


def is_app_folder(path: Path) -> bool:
    return (path / "ai_detector_server.py").is_file() and (path / "detector_engine.py").is_file()


def git_pull() -> int:
    say("🔄 Ο φάκελος είναι git clone — κάνω git pull…", "Git clone detected — running git pull…")
    try:
        return subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"]).returncode
    except OSError:
        say("❌ Δεν βρέθηκε το git.", "git was not found.")
        return 1


def _copy_file(src: Path, dst: Path, secret: bool = False) -> str:
    if src.is_symlink() or not src.is_file():
        return "skip"
    if dst.exists():
        return "exists"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if secret and os.name == "posix":
        os.chmod(dst, 0o600)
    return "copied"


def migrate(old: Path, new: Path) -> dict:
    """Αντιγράφει ρυθμίσεις/δεδομένα από τον παλιό φάκελο στον νέο."""
    report = {"copied": [], "exists": []}

    def note(name: str, result: str) -> None:
        if result in report:
            report[result].append(name)

    for name in SECRET_FILES:
        note(name, _copy_file(old / name, new / name, secret=True))
    for name in DATA_FILES:
        note(name, _copy_file(old / name, new / name))
    corpus = old / "corpus"
    if corpus.is_dir() and not corpus.is_symlink():
        for f in sorted(corpus.iterdir()):
            if f.suffix.lower() in CORPUS_EXTENSIONS:
                note(f"corpus/{f.name}", _copy_file(f, new / "corpus" / f.name))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="old", help="ο ΠΑΛΙΟΣ φάκελος της εφαρμογής")
    args = ap.parse_args()

    if (ROOT / ".git").exists() and not args.old:
        return git_pull()

    raw = args.old
    if not raw:
        say("Σύρε εδώ τον ΠΑΛΙΟ φάκελο της εφαρμογής (ή γράψε τη διαδρομή) και πάτα Enter:",
            "Drag the OLD app folder here (or type its path) and press Enter:")
        try:
            raw = input("> ")
        except EOFError:
            return 1
    old = Path(raw.strip().strip('"').strip("'")).expanduser()
    try:
        old = old.resolve(strict=True)
    except OSError:
        say("❌ Ο φάκελος δεν βρέθηκε.", "Folder not found.")
        return 1
    if old == ROOT:
        say("❌ Αυτός είναι ο ίδιος φάκελος — δώσε τον ΠΑΛΙΟ.", "That is this same folder — give the OLD one.")
        return 1
    if not old.is_dir() or not is_app_folder(old):
        say("❌ Δεν μοιάζει με φάκελο της εφαρμογής (λείπει το ai_detector_server.py).",
            "This does not look like an app folder (ai_detector_server.py is missing).")
        return 1

    report = migrate(old, ROOT)
    for name in report["copied"]:
        print(f"  ✅ {name}")
    for name in report["exists"]:
        print(f"  ↷ {name} — υπάρχει ήδη, δεν άλλαξε (already present, kept)")
    if not report["copied"] and not report["exists"]:
        say("ℹ Δεν βρέθηκαν ρυθμίσεις ή δεδομένα για μεταφορά.", "Nothing to migrate.")
    say("\n✔ Έτοιμο. Ξεκίνα τη νέα έκδοση με το run.bat. Τον παλιό φάκελο μπορείς να τον σβήσεις "
        "όταν βεβαιωθείς ότι όλα δουλεύουν.",
        "Done. Start the new version with run.bat; delete the old folder once everything works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
