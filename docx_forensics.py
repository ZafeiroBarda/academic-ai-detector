#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ιστορικό επεξεργασίας ενός .docx (μεταδεδομένα & rsid του Word).

Το Word δίνει σε κάθε συνεδρία επεξεργασίας που κλείνει με αποθήκευση έναν
κωδικό (rsid) και «σημαδεύει» με αυτόν το κείμενο που γράφτηκε σε εκείνη τη
συνεδρία. Μια εργασία που γράφτηκε σταδιακά έχει το κείμενό της μοιρασμένο σε
πολλές συνεδρίες· ένα κείμενο που επικολλήθηκε μονομιάς είναι σχεδόν όλο σε
μία. Επιπλέον διαβάζουμε: χρόνο επεξεργασίας (docProps/app.xml → TotalTime),
ημερομηνίες δημιουργίας/τροποποίησης, συγγραφέα, εφαρμογή.

ΠΡΟΣΟΧΗ: είναι βοηθητικές ενδείξεις, ΟΧΙ απόδειξη. Αντιγραφή σε νέο αρχείο,
«Αποθήκευση ως», Google Docs/LibreOffice ή μετατροπή αλλάζουν/σβήνουν αυτά
τα στοιχεία. Δεν επηρεάζουν το σκορ AI. (Βλ. Spennemann & Singh, IJDC.)

Ασφάλεια: διαβάζουμε μόνο συγκεκριμένα αρχεία του zip, με όριο μεγέθους
(προστασία από zip bombs), χωρίς να εξάγουμε τίποτα στον δίσκο.
"""

import re
import zipfile
from datetime import datetime
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {
    "w": W_NS,
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
}
_W = "{%s}" % W_NS

MAX_PART_BYTES = 80 * 1024 * 1024    # όριο αποσυμπιεσμένου μεγέθους ανά XML
MIN_SESSION_SHARE = 0.01             # συνεδρία με <1% του κειμένου = μικροδιόρθωση
SINGLE_SESSION_SHARE = 0.80          # ≥80% του κειμένου σε μία συνεδρία
MANY_SESSIONS = 5                    # από τόσες συνεδρίες και πάνω: σταδιακή γραφή
TYPING_WPM = 40                      # μέση ταχύτητα πληκτρολόγησης για εκτίμηση χρόνου


# Όλοι οι κωδικοί ευρημάτων — το UI πρέπει να έχει κείμενο για καθέναν
FINDING_CODES = ("no_history", "single_session", "few_sessions", "some_sessions",
                 "many_sessions", "low_edit_time", "short_span", "author_differs")


class _TooLarge(Exception):
    pass


def _read_part(zf: zipfile.ZipFile, name: str) -> Optional[bytes]:
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_PART_BYTES:
        raise _TooLarge(name)
    with zf.open(info) as f:
        data = f.read(MAX_PART_BYTES + 1)   # μην εμπιστεύεσαι μόνο το header του zip
    if len(data) > MAX_PART_BYTES:
        raise _TooLarge(name)
    return data


def _parse(data: Optional[bytes]) -> Optional[ET.Element]:
    if not data:
        return None
    # Τα έγγραφα Word δεν χρειάζονται DTD/entities· τα απορρίπτουμε για ασφάλεια
    if b"<!DOCTYPE" in data[:2048] or b"<!ENTITY" in data[:4096]:
        return None
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        return None


def _text(root: Optional[ET.Element], path: str) -> Optional[str]:
    if root is None:
        return None
    el = root.find(path, NS)
    return el.text.strip() if el is not None and el.text else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _session_chars(doc: ET.Element) -> Dict[str, int]:
    """Χαρακτήρες κειμένου ανά συνεδρία (rsid εισαγωγής του run, αλλιώς της παραγράφου)."""
    chars: Dict[str, int] = {}
    for p in doc.iter(_W + "p"):
        p_rsid = p.get(_W + "rsidR") or p.get(_W + "rsidRDefault")
        for r in p.iter(_W + "r"):
            n = sum(len(t.text or "") for t in r.iter(_W + "t"))
            if not n:
                continue
            rsid = r.get(_W + "rsidR") or p_rsid or "none"
            chars[rsid] = chars.get(rsid, 0) + n
    return chars


def analyze_docx(path: str) -> Dict:
    """Επιστρέφει {available, metadata, sessions, findings: [{code, level, params}]}.
    level: 'warn' (αξίζει ερώτηση στον φοιτητή) | 'info' (ουδέτερη πληροφορία)."""
    try:
        with zipfile.ZipFile(path) as zf:
            doc = _parse(_read_part(zf, "word/document.xml"))
            settings = _parse(_read_part(zf, "word/settings.xml"))
            core = _parse(_read_part(zf, "docProps/core.xml"))
            app = _parse(_read_part(zf, "docProps/app.xml"))
    except _TooLarge:
        return {"available": False, "reason": "too_large", "findings": []}
    except (zipfile.BadZipFile, OSError):
        return {"available": False, "reason": "unreadable", "findings": []}
    if doc is None:
        return {"available": False, "reason": "unreadable", "findings": []}

    total_time = _text(app, "ep:TotalTime")
    metadata = {
        "application": _text(app, "ep:Application"),
        "app_version": _text(app, "ep:AppVersion"),
        "creator": _text(core, "dc:creator"),
        "last_modified_by": _text(core, "cp:lastModifiedBy"),
        "created": _text(core, "dcterms:created"),
        "modified": _text(core, "dcterms:modified"),
        "revision": _text(core, "cp:revision"),
        "edit_minutes": int(total_time) if total_time and total_time.isdigit() else None,
    }

    chars = _session_chars(doc)
    total_chars = sum(chars.values())
    words = sum(len(re.findall(r"\w+", t.text or "")) for t in doc.iter(_W + "t"))
    has_rsids = any(k != "none" for k in chars)
    settings_rsids = len(settings.findall("w:rsids/w:rsid", NS)) if settings is not None else 0

    sessions: Dict = {"has_rsids": has_rsids, "recorded_sessions": settings_rsids,
                      "text_sessions": 0, "top_session_share": None, "words": words}
    findings: List[Dict] = []

    if not has_rsids:
        findings.append({"code": "no_history", "level": "info",
                         "params": {"app": metadata["application"] or "?"}})
    elif total_chars:
        shares = sorted((c / total_chars for c in chars.values()), reverse=True)
        sessions["text_sessions"] = sum(1 for s in shares if s >= MIN_SESSION_SHARE)
        sessions["top_session_share"] = round(shares[0] * 100, 1)
        if words >= 300 and shares[0] >= SINGLE_SESSION_SHARE:
            findings.append({"code": "single_session", "level": "warn",
                             "params": {"pct": round(shares[0] * 100)}})
        elif words >= 1500 and sessions["text_sessions"] <= 2:
            findings.append({"code": "few_sessions", "level": "warn",
                             "params": {"n": sessions["text_sessions"], "words": words}})
        elif sessions["text_sessions"] >= MANY_SESSIONS:
            findings.append({"code": "many_sessions", "level": "info",
                             "params": {"n": sessions["text_sessions"]}})
        else:   # 2-4 συνεδρίες: ουδέτερο — δεν λέει κάτι ούτε υπέρ ούτε κατά
            findings.append({"code": "some_sessions", "level": "info",
                             "params": {"n": sessions["text_sessions"]}})

    # Χρόνος/ημερομηνίες έχουν νόημα μόνο σε αρχείο που όντως επεξεργάστηκε το Word:
    # χωρίς rsid (Google Docs, LibreOffice, python-docx) είναι τιμές προτύπου.
    minutes = metadata["edit_minutes"] if has_rsids else None
    if minutes is not None and words >= 500:
        expected = words / TYPING_WPM
        if minutes < expected * 0.25:
            findings.append({"code": "low_edit_time", "level": "warn",
                             "params": {"minutes": minutes, "words": words,
                                        "expected": round(expected)}})

    created, modified = _parse_dt(metadata["created"]), _parse_dt(metadata["modified"])
    if has_rsids and created and modified and words >= 1500:
        span_min = (modified - created).total_seconds() / 60
        if 0 <= span_min < 60:
            findings.append({"code": "short_span", "level": "warn",
                             "params": {"minutes": round(span_min), "words": words}})

    if (metadata["creator"] and metadata["last_modified_by"]
            and metadata["creator"].strip().lower() != metadata["last_modified_by"].strip().lower()):
        findings.append({"code": "author_differs", "level": "info",
                         "params": {"creator": metadata["creator"],
                                    "modifier": metadata["last_modified_by"]}})

    return {"available": True, "metadata": metadata, "sessions": sessions,
            "findings": findings}
