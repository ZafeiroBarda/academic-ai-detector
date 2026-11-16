#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR για σκαναρισμένα PDF (σελίδες-εικόνες χωρίς κείμενο), με Tesseract.

Προαιρετικό: αν δεν είναι εγκατεστημένο το Tesseract, όλα δουλεύουν όπως πριν
και η σελίδα εξηγεί πώς να το εγκαταστήσεις (Windows: εγκαταστάτης UB Mannheim
με «Greek»· Linux: apt install tesseract-ocr tesseract-ocr-ell).

Ασφάλεια / πόροι:
  • Το εκτελέσιμο έρχεται ΜΟΝΟ από το σύστημα (PATH, γνωστές θέσεις ή τη
    μεταβλητή AI_DETECTOR_TESSERACT) — ποτέ από το αίτημα. Καλείται με λίστα
    ορισμάτων (χωρίς shell) και η εικόνα περνά από stdin: κανένα προσωρινό αρχείο.
  • Όρια: σελίδες ανά έγγραφο, μέγιστη διάσταση εικόνας (PDF με τεράστιες
    σελίδες δεν γεμίζουν τη μνήμη), χρόνος ανά σελίδα και συνολικός χρόνος.
  • Ένα έγγραφο κάθε φορά (το OCR είναι βαρύ για τον υπολογιστή).
  • AI_DETECTOR_OCR=off το απενεργοποιεί.
"""

import io
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

MIN_PAGE_CHARS = 40          # σελίδα με λιγότερους χαρακτήρες = πιθανώς εικόνα
SCANNED_SHARE = 0.5          # OCR μόνο αν τουλάχιστον τόσες σελίδες είναι «άδειες»
MAX_PAGES = 80               # σελίδες με OCR ανά έγγραφο
DPI = 300
MAX_SIDE_PX = 4000           # μέγιστη διάσταση εικόνας σελίδας
PAGE_TIMEOUT = 60            # δευτ. ανά σελίδα
TOTAL_TIMEOUT = 600          # δευτ. ανά έγγραφο
WAIT_TIMEOUT = 120           # αναμονή αν τρέχει ήδη άλλο OCR
PREFERRED_LANGS = ("ell", "eng")

_LOCK = threading.Lock()
# Το PDFium (pypdfium2) δεν είναι thread-safe: κάθε κλήση του, από οποιοδήποτε
# module (OCR, εικόνες), περνά από αυτό το κλείδωμα.
PDFIUM_LOCK = threading.RLock()
_info_cache: Dict[str, object] = {}

_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
)


def enabled() -> bool:
    return os.environ.get("AI_DETECTOR_OCR", "").strip().lower() not in ("0", "off", "false", "no")


def _run(args: List[str], data: bytes = b"", timeout: float = 10) -> subprocess.CompletedProcess:
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(args, input=data, capture_output=True, timeout=timeout, check=False, **kwargs)


def find_tesseract() -> Optional[str]:
    candidates = [os.environ.get("AI_DETECTOR_TESSERACT", "").strip(), shutil.which("tesseract") or ""]
    if os.name == "nt":
        candidates.extend(_WINDOWS_PATHS)
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def status(refresh: bool = False) -> Dict:
    """{available, langs[], path?} — τα αποτελέσματα κρατιούνται (το --list-langs κοστίζει)."""
    if not enabled():
        return {"available": False, "disabled": True, "langs": []}
    if _info_cache and not refresh:
        return dict(_info_cache)
    exe = find_tesseract()
    langs: List[str] = []
    if exe:
        try:
            out = _run([exe, "--list-langs"]).stdout.decode("utf-8", "replace")
            langs = sorted({ln.strip() for ln in out.splitlines()[1:]
                            if re.fullmatch(r"[A-Za-z_]{3,20}", ln.strip())})
        except (OSError, subprocess.SubprocessError):
            exe = None
    _info_cache.clear()
    _info_cache.update({"available": bool(exe and langs), "langs": langs, "path": exe})
    return dict(_info_cache)


def available() -> bool:
    return bool(status().get("available"))


def _lang_arg(langs: List[str]) -> str:
    chosen = [lang for lang in PREFERRED_LANGS if lang in langs]
    return "+".join(chosen or langs[:1])


def needs_ocr(page_texts: List[str]) -> List[int]:
    """Οι σελίδες που χρειάζονται OCR — μόνο αν το PDF είναι κυρίως σκαναρισμένο
    (ένα κανονικό PDF με μερικές σελίδες-σχήματα δεν περνά OCR)."""
    if not page_texts:
        return []
    empty = [i for i, t in enumerate(page_texts) if len((t or "").strip()) < MIN_PAGE_CHARS]
    return empty if len(empty) >= SCANNED_SHARE * len(page_texts) else []


def _clean(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # συλλαβισμός στο τέλος γραμμής
    return re.sub(r"[ \t]+", " ", text).strip()


def _render_png(pdf, index: int) -> bytes:
    page = pdf[index]
    try:
        w, h = page.get_size()
        scale = min(DPI / 72.0, MAX_SIDE_PX / max(w, h, 1.0))
        image = page.render(scale=scale, grayscale=True).to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        page.close()


def ocr_pages(pdf_path: str, indexes: List[int]) -> Tuple[Dict[int, str], Dict]:
    """OCR στις σελίδες `indexes`. Επιστρέφει ({σελίδα: κείμενο}, πληροφορίες)."""
    info = {"used": False, "pages": 0, "requested": len(indexes), "truncated": False,
            "timed_out": 0, "langs": None}
    st = status()
    if not st.get("available"):
        info["unavailable"] = True
        return {}, info
    if not _LOCK.acquire(timeout=WAIT_TIMEOUT):
        info["busy"] = True
        return {}, info
    texts: Dict[int, str] = {}
    try:
        import pypdfium2 as pdfium
        langs = _lang_arg(st["langs"])
        info["langs"] = langs
        todo = indexes[:MAX_PAGES]
        info["truncated"] = len(indexes) > MAX_PAGES
        deadline = time.monotonic() + TOTAL_TIMEOUT
        with PDFIUM_LOCK:
            pdf = pdfium.PdfDocument(pdf_path)
        try:
            for i in todo:
                left = deadline - time.monotonic()
                if left <= 1:
                    info["truncated"] = True
                    break
                try:
                    with PDFIUM_LOCK:
                        png = _render_png(pdf, i)
                    res = _run([st["path"], "stdin", "stdout", "-l", langs, "--psm", "3"],
                               data=png, timeout=min(PAGE_TIMEOUT, left))
                except subprocess.TimeoutExpired:
                    info["timed_out"] += 1
                    continue
                if res.returncode == 0:
                    texts[i] = _clean(res.stdout.decode("utf-8", "replace"))
        finally:
            with PDFIUM_LOCK:
                pdf.close()
    except Exception as e:                       # χαλασμένο PDF κ.λπ. — ποτέ δεν ρίχνει την ανάλυση
        info["error"] = type(e).__name__
    finally:
        _LOCK.release()
    info["pages"] = len(texts)
    info["used"] = bool(texts)
    return texts, info
