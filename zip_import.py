#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Εισαγωγή ZIP με υποβολές (Open eClass, Moodle «λήψη όλων των υποβολών»).

Ένα ZIP από το internet είναι αναξιόπιστο αρχείο. Άμυνες:
  • Όρια: πλήθος εγγραφών, πλήθος εγγράφων, μέγεθος ανά αρχείο, συνολικό
    αποσυμπιεσμένο μέγεθος και αναλογία συμπίεσης (zip bomb) — τα μεγέθη
    μετρώνται ΠΡΑΓΜΑΤΙΚΑ κατά την αποσυμπίεση, όχι από την κεφαλίδα.
  • Τα ονόματα μέσα στο ZIP δεν χρησιμοποιούνται ποτέ ως διαδρομές στον
    δίσκο (κάθε έγγραφο γράφεται με τυχαίο όνομα) — άρα «../» και απόλυτες
    διαδρομές δεν έχουν καμία επίδραση (zip slip).
  • Παραλείπονται: φάκελοι, symlinks, κρυπτογραφημένα, ZIP μέσα σε ZIP,
    κρυφά/συστήματος (__MACOSX, .DS_Store), τύποι εκτός λίστας.
"""

import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

MAX_ENTRIES = 2000              # εγγραφές που εξετάζονται
MAX_DOCS = 60                   # έγγραφα που αναλύονται
MAX_FILE_BYTES = 60 * 1024 * 1024
MAX_TOTAL_BYTES = 400 * 1024 * 1024
MAX_RATIO = 150                 # αποσυμπιεσμένο / συμπιεσμένο
MAX_LABEL = 200
_CHUNK = 1024 * 1024

# Moodle: "Όνομα Επώνυμο_123456_assignsubmission_file_εργασία.docx" (ή φάκελος)
_MOODLE_RE = re.compile(r"^(.+?)_\d+_assignsubmission_(?:file|onlinetext)_?", re.IGNORECASE)


class ZipImportError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _decode_name(info: zipfile.ZipInfo) -> str:
    """Τα Windows γράφουν ονόματα σε κωδικοσελίδα DOS (ελληνικά: cp737) χωρίς
    σημαία UTF-8· το zipfile τα διαβάζει ως cp437. Τα διορθώνουμε."""
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for enc in ("utf-8", "cp737"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return name


def _clean_label(name: str) -> str:
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    label = "/".join(parts)
    label = "".join(ch for ch in label if ch.isprintable())
    return label[-MAX_LABEL:]


def student_from_label(label: str) -> str:
    """Όνομα φοιτητή από τη δομή του ZIP (Moodle μοτίβο ή πρώτος φάκελος)."""
    parts = label.split("/")
    for part in parts:
        m = _MOODLE_RE.match(part)
        if m:
            return m.group(1).strip()
    if len(parts) > 1:
        return parts[0].strip()
    return ""


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def extract_documents(zip_path, dest_dir, allowed_ext=(".docx", ".pdf"),
                      max_docs: int = MAX_DOCS) -> Tuple[List[Dict], Dict[str, int]]:
    """Επιστρέφει ([{label, student, path, ext}], skipped{λόγος: πλήθος}).
    Σηκώνει ZipImportError("bad_zip") αν δεν είναι έγκυρο ZIP."""
    dest_dir = Path(dest_dir)
    docs: List[Dict] = []
    skipped: Dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise ZipImportError("bad_zip")
    total = 0
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ZipImportError("too_many_entries")
        for info in infos:
            if info.is_dir():
                continue
            label = _clean_label(_decode_name(info))
            base = label.rsplit("/", 1)[-1]
            ext = os.path.splitext(base)[1].lower()
            if not base or base.startswith(".") or "__MACOSX" in label.split("/"):
                skip("system")
                continue
            if _is_symlink(info):
                skip("symlink")
                continue
            if info.flag_bits & 0x1:
                skip("encrypted")
                continue
            if ext not in allowed_ext:
                skip("type")
                continue
            if len(docs) >= max_docs:
                skip("limit")
                continue
            if (info.file_size > MAX_FILE_BYTES
                    or info.file_size > MAX_RATIO * max(info.compress_size, 1)):
                skip("too_large")
                continue
            path = dest_dir / f"{uuid.uuid4().hex}{ext}"
            written = 0
            ok = True
            try:
                with zf.open(info) as src, open(path, "wb") as out:
                    while True:
                        chunk = src.read(_CHUNK)
                        if not chunk:
                            break
                        written += len(chunk)
                        if (written > MAX_FILE_BYTES or total + written > MAX_TOTAL_BYTES
                                or written > MAX_RATIO * max(info.compress_size, 1)):
                            ok = False
                            break
                        out.write(chunk)
            except (zipfile.BadZipFile, OSError, EOFError, RuntimeError, ValueError):
                ok = False
            if not ok:
                try:
                    path.unlink()
                except OSError:
                    pass
                skip("too_large" if written else "unreadable")
                if total + written > MAX_TOTAL_BYTES:
                    break
                continue
            total += written
            docs.append({"label": label, "student": student_from_label(label),
                         "path": str(path), "ext": ext.lstrip(".")})
    return docs, skipped
