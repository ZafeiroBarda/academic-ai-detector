#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Διαχείριση του φακέλου corpus/ (παλιές εργασίες για σύγκριση) από τη σελίδα.

Ασφάλεια — τα ονόματα και τα περιεχόμενα έρχονται από τον browser:
  • Όνομα αρχείου: κρατάμε μόνο το τελευταίο κομμάτι (όχι διαδρομές/«..»),
    μόνο γράμματα (και ελληνικά), αριθμούς, κενά και . - _ ( ) [ ] ,
    όχι κρυφά αρχεία, όχι δεσμευμένα ονόματα των Windows (CON, NUL, …),
    μόνο .docx/.pdf/.txt/.md, μέγιστο μήκος.
  • Ποτέ αντικατάσταση: αν υπάρχει ήδη, παίρνει « (2)», « (3)», …
  • Το αρχείο γράφεται πρώτα προσωρινά (O_EXCL), ελέγχεται ότι διαβάζεται
    και έχει κείμενο, και μόνο τότε μπαίνει στο corpus.
  • Διαγραφή μόνο αρχείου που υπάρχει ΗΔΗ στη λίστα του φακέλου (όχι
    διαδρομές από τον χρήστη), όχι symlinks, και μόνο μέσα στον φάκελο.
"""

import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from plagiarism_engine import _extract_file_text

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}
MAX_NAME_LEN = 120
MIN_WORDS = 10
_ALLOWED_CHARS = re.compile(r"[^\w\s.\-()\[\],]", re.UNICODE)
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                     *(f"lpt{i}" for i in range(1, 10))}


class CorpusError(ValueError):
    """Σφάλμα με κωδικό μηνύματος για μετάφραση στο UI."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def safe_name(filename: str) -> Optional[str]:
    """Ασφαλές όνομα για το corpus ή None αν δεν γίνεται."""
    if not isinstance(filename, str):
        return None
    name = unicodedata.normalize("NFC", filename).replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")   # control chars
    name = _ALLOWED_CHARS.sub("_", name).strip(" .")
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    if ext not in ALLOWED_EXTENSIONS or not stem:
        return None
    if stem.lower() in _WINDOWS_RESERVED or stem.upper().startswith("README"):
        stem = "_" + stem
    stem = stem[:MAX_NAME_LEN]
    return stem + ext


def _entries(corpus_dir: Path):
    if not corpus_dir.is_dir():
        return
    for p in sorted(corpus_dir.iterdir(), key=lambda x: x.name.lower()):
        if (p.is_symlink() or not p.is_file() or p.name.startswith(".")
                or p.suffix.lower() not in ALLOWED_EXTENSIONS or p.name.upper().startswith("README")):
            continue
        yield p


def list_files(corpus_dir) -> List[Dict]:
    out = []
    for p in _entries(Path(corpus_dir)):
        st = p.stat()
        out.append({"name": p.name, "size": st.st_size, "modified": int(st.st_mtime)})
    return out


def _unique_target(corpus_dir: Path, name: str) -> Path:
    stem, ext = os.path.splitext(name)
    target = corpus_dir / name
    n = 2
    while target.exists():
        target = corpus_dir / f"{stem} ({n}){ext}"
        n += 1
    return target


def save_upload(corpus_dir, filename: str, stream) -> str:
    """Αποθηκεύει ένα ανεβασμένο αρχείο. Επιστρέφει το τελικό όνομα ή σηκώνει
    CorpusError("bad_name" | "not_enough_text" | "unreadable")."""
    corpus_dir = Path(corpus_dir)
    name = safe_name(filename)
    if not name:
        raise CorpusError("bad_name")
    corpus_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(name)[1]
    tmp = corpus_dir / f".upload-{uuid.uuid4().hex}{ext}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
        try:
            text = _extract_file_text(tmp)
        except Exception:
            raise CorpusError("unreadable")
        if len(text.split()) < MIN_WORDS:
            raise CorpusError("not_enough_text")
        target = _unique_target(corpus_dir, name)
        os.replace(tmp, target)
        return target.name
    finally:
        if tmp.exists():
            tmp.unlink()


def delete_file(corpus_dir, name: str) -> bool:
    """Διαγράφει ΜΟΝΟ αρχείο που εμφανίζεται στη λίστα του φακέλου."""
    corpus_dir = Path(corpus_dir)
    if not isinstance(name, str):
        return False
    for p in _entries(corpus_dir):
        if p.name == name and p.resolve().parent == corpus_dir.resolve():
            p.unlink()
            return True
    return False
