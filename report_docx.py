#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Επίσημο πρακτικό ελέγχου εργασίας (.docx) για τον φάκελο του φοιτητή.

Περιέχει στοιχεία ιδρύματος / εργασίας / εξεταστή, συνοπτικά ευρήματα (AI,
λογοκλοπή, αναφορές, άλλες ενδείξεις), σημειώσεις εξεταστή, την αποποίηση
ότι το σκορ είναι ένδειξη και όχι απόδειξη, και γραμμή υπογραφής.

Ασφάλεια: τα δεδομένα έρχονται από τη σελίδα, οπότε διαβάζονται ΜΟΝΟ
συγκεκριμένα πεδία, με έλεγχο τύπου, όρια μήκους και αφαίρεση χαρακτήρων
που δεν επιτρέπονται σε XML. Το python-docx κάνει το escaping του XML.
Τίποτα δεν αποθηκεύεται — το αρχείο φτιάχνεται στη μνήμη και επιστρέφεται.
"""

import io
import re
from datetime import datetime
from typing import Dict, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

MAX_FIELD = 300
MAX_NOTES = 5000
MAX_SOURCES = 8
_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
META_FIELDS = ("institution", "department", "course", "student", "title", "examiner", "filename")

L = {
 "el": {"title": "Πρακτικό ελέγχου εργασίας", "institution": "Ίδρυμα", "department": "Τμήμα",
        "course": "Μάθημα / Πρόγραμμα", "student": "Φοιτητής/τρια (ΑΜ)", "work": "Τίτλος εργασίας",
        "file": "Αρχείο", "date": "Ημερομηνία ελέγχου", "examiner": "Εξεταστής/τρια", "tool": "Εργαλείο",
        "s_ai": "1. Ενδείξεις κειμένου γραμμένου από AI", "score": "Σκορ AI", "verdict": "Ετυμηγορία",
        "confidence": "Αξιοπιστία μέτρησης", "words": "Λέξεις", "calib": "Σύγκριση με ανθρώπινες εργασίες αναφοράς",
        "calib_line": "{pct}% των {n} ανθρώπινων εργασιών αναφοράς είχε σκορ ίσο ή υψηλότερο (προτεινόμενο όριο {t}%).",
        "ocr": "Το κείμενο διαβάστηκε με OCR από {pages} σκαναρισμένες σελίδες — τα λάθη αναγνώρισης μειώνουν την αξιοπιστία.",
        "binoculars": "Δεύτερη μέθοδος (Binoculars)", "bino_ai": "μοιάζει με AI", "bino_human": "μοιάζει ανθρώπινο",
        "s_plag": "2. Ομοιότητα / λογοκλοπή", "corpus": "Ομοιότητα με το αρχείο εργασιών (corpus)",
        "sources": "Κυριότερες πηγές", "web": "Ευρήματα στο web", "excluded": "Εξαιρέθηκαν",
        "excluded_line": "{q} παραθέματα ({qw} λέξεις), βιβλιογραφία {bw} λέξεις",
        "web_line": "Wikipedia: {w} · ακαδημαϊκή βιβλιογραφία (OpenAlex): {s} · Brave: {b}",
        "images": "Ίδιες εικόνες/διαγράμματα με το corpus", "images_line": "{n} εικόνες σε {m} αρχεία",
        "not_checked": "δεν ελέγχθηκε",
        "s_refs": "3. Βιβλιογραφικές αναφορές", "refs_line": "Ελέγχθηκαν {checked} από {total} αναφορές",
        "s_other": "4. Άλλες ενδείξεις", "obf": "Κόλπα παράκαμψης ανιχνευτών", "docx": "Ιστορικό επεξεργασίας Word",
        "fair": "Απλό λεξιλόγιο (κίνδυνος ψευδώς θετικού για μη φυσικούς ομιλητές)", "yes": "Ναι",
        "none": "Καμία", "s_notes": "5. Σημειώσεις εξεταστή",
        "disclaimer": "Σημαντικό: τα αποτελέσματα είναι στατιστικές ενδείξεις και ΟΧΙ απόδειξη. Κανένας ανιχνευτής "
                      "AI δεν είναι αλάνθαστος. Η τελική κρίση ανήκει στον/στην εξεταστή/τρια, μετά από συζήτηση με "
                      "τον/τη φοιτητή/τρια.",
        "signature": "Υπογραφή εξεταστή/τριας", "status": {
            "verified": "επιβεβαιωμένες", "partial": "μερική αντιστοιχία", "not_found": "δεν βρέθηκαν",
            "doi_not_found": "ανύπαρκτο DOI", "doi_mismatch": "DOI άλλης δημοσίευσης",
            "skipped_web": "ιστοσελίδες (δεν ελέγχονται)", "unparsed": "δεν αναγνωρίστηκαν"},
        "codes": {"homoglyphs": "ομοιόγλυφα γράμματα", "invisible_chars": "αόρατοι χαρακτήρες",
                  "odd_spaces": "ασυνήθιστα κενά", "tortured_phrases": "«βασανισμένες» φράσεις",
                  "single_session": "γράφτηκε σε μία συνεδρία", "few_sessions": "ελάχιστες συνεδρίες",
                  "low_edit_time": "πολύ μικρός χρόνος επεξεργασίας", "short_span": "πολύ σύντομο χρονικό διάστημα",
                  "author_differs": "διαφορετικός δημιουργός αρχείου"}},
 "en": {"title": "Paper check report", "institution": "Institution", "department": "Department",
        "course": "Course / programme", "student": "Student (ID)", "work": "Paper title",
        "file": "File", "date": "Date of check", "examiner": "Examiner", "tool": "Tool",
        "s_ai": "1. Indicators of AI-written text", "score": "AI score", "verdict": "Verdict",
        "confidence": "Measurement reliability", "words": "Words", "calib": "Comparison with human reference papers",
        "calib_line": "{pct}% of the {n} human reference papers scored as high or higher (suggested threshold {t}%).",
        "ocr": "The text was read with OCR from {pages} scanned pages — recognition errors reduce reliability.",
        "binoculars": "Second method (Binoculars)", "bino_ai": "looks AI-written", "bino_human": "looks human",
        "s_plag": "2. Similarity / plagiarism", "corpus": "Similarity with the paper archive (corpus)",
        "sources": "Main sources", "web": "Web findings", "excluded": "Excluded",
        "excluded_line": "{q} quotations ({qw} words), bibliography {bw} words",
        "web_line": "Wikipedia: {w} · academic literature (OpenAlex): {s} · Brave: {b}",
        "images": "Identical images/diagrams in the corpus", "images_line": "{n} images in {m} files",
        "not_checked": "not checked",
        "s_refs": "3. References", "refs_line": "{checked} of {total} references checked",
        "s_other": "4. Other indicators", "obf": "Detector evasion tricks", "docx": "Word editing history",
        "fair": "Simple vocabulary (false-positive risk for non-native speakers)", "yes": "Yes",
        "none": "None", "s_notes": "5. Examiner's notes",
        "disclaimer": "Important: the results are statistical indicators and NOT proof. No AI detector is "
                      "infallible. The final judgement belongs to the examiner, after discussion with the student.",
        "signature": "Examiner's signature", "status": {
            "verified": "verified", "partial": "partial match", "not_found": "not found",
            "doi_not_found": "non-existent DOI", "doi_mismatch": "DOI of another work",
            "skipped_web": "web pages (not checked)", "unparsed": "not recognised"},
        "codes": {"homoglyphs": "look-alike letters", "invisible_chars": "invisible characters",
                  "odd_spaces": "unusual spaces", "tortured_phrases": "tortured phrases",
                  "single_session": "written in a single session", "few_sessions": "very few sessions",
                  "low_edit_time": "very low editing time", "short_span": "very short time span",
                  "author_differs": "different file author"}},
}
# Γερμανικά/γαλλικά/πορτογαλικά: τίτλοι και αποποίηση μεταφρασμένα, τα υπόλοιπα από τα αγγλικά
for _lang, _tr in {
    "de": {"title": "Prüfprotokoll der Arbeit", "examiner": "Prüfer/in", "signature": "Unterschrift Prüfer/in",
           "disclaimer": "Wichtig: Die Ergebnisse sind statistische Hinweise und KEIN Beweis. Kein KI-Detektor ist "
                         "fehlerfrei. Das abschließende Urteil liegt bei der prüfenden Person, nach einem Gespräch "
                         "mit dem/der Studierenden."},
    "fr": {"title": "Procès-verbal de contrôle du travail", "examiner": "Examinateur·rice",
           "signature": "Signature de l’examinateur·rice",
           "disclaimer": "Important : les résultats sont des indices statistiques et NON une preuve. Aucun détecteur "
                         "d’IA n’est infaillible. Le jugement final appartient à l’examinateur·rice, après discussion "
                         "avec l’étudiant·e."},
    "pt": {"title": "Relatório de verificação do trabalho", "examiner": "Examinador/a",
           "signature": "Assinatura do/a examinador/a",
           "disclaimer": "Importante: os resultados são indícios estatísticos e NÃO prova. Nenhum detetor de IA é "
                         "infalível. O juízo final pertence ao/à examinador/a, após conversa com o/a estudante."},
}.items():
    L[_lang] = dict(L["en"], **_tr)


def _text(v, limit: int = MAX_FIELD) -> str:
    if not isinstance(v, str):
        return ""
    return _BAD_XML.sub("", v).strip()[:limit]


def _num(v) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if -1e9 < v < 1e9 else None


def _pct(v) -> str:
    n = _num(v)
    return f"{n:.1f}%" if n is not None else "—"


def _pick(d, lang: str) -> str:
    if isinstance(d, dict):
        return _text(d.get(lang) or d.get("en") or "")
    return ""


def _dict(v) -> Dict:
    return v if isinstance(v, dict) else {}


def build_report(analysis: Dict, meta: Dict, lang: str = "el", app_version: str = "") -> bytes:
    t = L.get(lang, L["en"])
    a = _dict(analysis)
    notes = _text(_dict(meta).get("notes"), MAX_NOTES)
    meta = {k: _text(_dict(meta).get(k)) for k in META_FIELDS}

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    h = doc.add_heading(t["title"], level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    rows = [(t["institution"], meta["institution"]), (t["department"], meta["department"]),
            (t["course"], meta["course"]), (t["student"], meta["student"]), (t["work"], meta["title"]),
            (t["file"], meta["filename"]), (t["date"], datetime.now().strftime("%d/%m/%Y %H:%M")),
            (t["examiner"], meta["examiner"]), (t["tool"], f"AI Content Detector v{_text(app_version, 20)}")]
    table = doc.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value or "—"

    # 1. AI
    doc.add_heading(t["s_ai"], level=1)
    p = doc.add_paragraph()
    run = p.add_run(f"{t['score']}: {_pct(a.get('score'))}")
    run.bold = True
    run.font.size = Pt(14)
    doc.add_paragraph(f"{t['verdict']}: {_pick(a.get('verdict_i18n'), lang) or _text(a.get('verdict'))}")
    rel = _num(a.get("reliability"))
    if rel is not None:
        doc.add_paragraph(f"{t['confidence']}: {rel:.0f}%")
    words = _num(_dict(a.get("text_stats")).get("words"))
    if words is not None:
        doc.add_paragraph(f"{t['words']}: {int(words):,}".replace(",", "."))
    ocr = _dict(a.get("ocr"))
    if ocr.get("used") is True and _num(ocr.get("pages")):
        doc.add_paragraph(t["ocr"].format(pages=int(_num(ocr["pages"]))))
    cal = _dict(a.get("calibration"))
    if _num(cal.get("human_share_at_or_above")) is not None and _num(cal.get("n_human")) is not None:
        doc.add_paragraph(f"{t['calib']}: " + t["calib_line"].format(
            pct=_num(cal["human_share_at_or_above"]), n=int(_num(cal["n_human"])),
            t=_num(cal.get("suggested_threshold")) if _num(cal.get("suggested_threshold")) is not None else "—"))
    bino = _dict(a.get("binoculars"))
    if _num(bino.get("score")) is not None:
        verdict = {"ai": t["bino_ai"], "human": t["bino_human"]}.get(bino.get("verdict"), "")
        doc.add_paragraph(f"{t['binoculars']}: {_num(bino['score']):.3f} {verdict}".strip())

    # 2. Λογοκλοπή
    doc.add_heading(t["s_plag"], level=1)
    plag = _dict(a.get("plagiarism"))
    corpus = _dict(plag.get("corpus"))
    if _num(corpus.get("similarity")) is not None:
        doc.add_paragraph(f"{t['corpus']}: {_pct(corpus['similarity'])}")
        sources = [s for s in (corpus.get("sources") or []) if isinstance(s, dict)][:MAX_SOURCES]
        if sources:
            doc.add_paragraph(f"{t['sources']}:")
            for s in sources:
                doc.add_paragraph(f"{_text(s.get('file'), 150)} — {_pct(s.get('similarity'))}",
                                  style="List Bullet")
    else:
        doc.add_paragraph(f"{t['corpus']}: {t['not_checked']}")

    def hits(key):
        d = _dict(plag.get(key))
        if not d or d.get("status") in ("not_configured", "disabled", "offline", "pending"):
            return t["not_checked"]
        n = _num(d.get("hit_count"))
        if n is not None:
            return str(max(0, int(n)))
        return str(len([h for h in (d.get("hits") or []) if isinstance(h, dict)]))
    doc.add_paragraph(f"{t['web']}: " + t["web_line"].format(w=hits("wikipedia"), s=hits("scholar"),
                                                            b=hits("brave")))
    imgs = _dict(a.get("images"))
    if _num(imgs.get("checked")) is not None:
        srcs = [x for x in (imgs.get("sources") or []) if isinstance(x, dict)][:MAX_SOURCES]
        n = sum(int(_num(x.get("count")) or 0) for x in srcs)
        doc.add_paragraph(f"{t['images']}: " + (t["images_line"].format(n=n, m=len(srcs)) if srcs else t["none"]))
        for x in srcs:
            doc.add_paragraph(f"{_text(x.get('file'), 150)} — {int(_num(x.get('count')) or 0)}", style="List Bullet")
    ex = _dict(plag.get("excluded"))
    if _num(ex.get("quotes")) or _num(ex.get("bibliography_words")):
        doc.add_paragraph(f"{t['excluded']}: " + t["excluded_line"].format(
            q=int(_num(ex.get("quotes")) or 0), qw=int(_num(ex.get("quoted_words")) or 0),
            bw=int(_num(ex.get("bibliography_words")) or 0)))

    # 3. Αναφορές
    doc.add_heading(t["s_refs"], level=1)
    refs = _dict(a.get("references"))
    counts = _dict(refs.get("counts"))
    if counts:
        doc.add_paragraph(t["refs_line"].format(checked=int(_num(refs.get("checked")) or 0),
                                                total=int(_num(refs.get("total")) or 0)))
        for status, label in t["status"].items():
            n = _num(counts.get(status))
            if n:
                doc.add_paragraph(f"{label}: {int(n)}", style="List Bullet")
    else:
        doc.add_paragraph(t["not_checked"])

    # 4. Άλλες ενδείξεις
    doc.add_heading(t["s_other"], level=1)
    obf = [t["codes"].get(_text(f.get("code"), 40), _text(f.get("code"), 40))
           for f in (_dict(a.get("obfuscation")).get("findings") or []) if isinstance(f, dict)]
    doc.add_paragraph(f"{t['obf']}: {', '.join(obf) if obf else t['none']}")
    hist = [t["codes"].get(_text(f.get("code"), 40), _text(f.get("code"), 40))
            for f in (_dict(a.get("docx_history")).get("findings") or [])
            if isinstance(f, dict) and f.get("level") == "warn"]
    if a.get("docx_history") is not None:
        doc.add_paragraph(f"{t['docx']}: {', '.join(hist) if hist else t['none']}")
    if _dict(a.get("fairness")).get("warning"):
        doc.add_paragraph(f"{t['fair']}: {t['yes']}")

    # 5. Σημειώσεις
    doc.add_heading(t["s_notes"], level=1)
    for line in (notes or "\n\n").split("\n"):
        doc.add_paragraph(line)

    d = doc.add_paragraph()
    r = d.add_run(t["disclaimer"])
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    doc.add_paragraph()
    doc.add_paragraph(f"{t['signature']}: ______________________________")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
