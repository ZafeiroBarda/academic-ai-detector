#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Content Detection Server v2.0
Ανίχνευση AI-generated κειμένου σε αρχεία .docx και .pdf (Ελληνικά & Αγγλικά).

Τρέξιμο:   python ai_detector_server.py
Μετά άνοιξε στον browser:  http://localhost:5000
(Το UI σερβίρεται πλέον από τον ίδιο τον server — δεν χρειάζεται να ανοίξεις
 ξεχωριστά το HTML αρχείο.)

Endpoints:
  GET  /              → Web UI
  GET  /health        → {"status": "ok", "engine": "2.0"}
  POST /analyze       → multipart file (.docx/.pdf) → ανάλυση
  POST /analyze-text  → JSON {"text": "..."} → ανάλυση
"""

import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from background_jobs import JobStore
import uuid
from pathlib import Path

from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

import pdfplumber
from docx import Document

from detector_engine import analyze_text as engine_analyze
from binoculars_check import check_binoculars
from docx_forensics import analyze_docx
from obfuscation_check import check_obfuscation
from model_signature import detect_model_signature
from plagiarism_engine import (CorpusIndex, _load_brave_config,
                               _load_google_config, check_brave, check_google,
                               check_scholar, check_wikipedia, pairwise_similarity,
                               openalex_api_key, save_brave_config, save_google_config,
                               save_openalex_key, validate_brave_config,
                               validate_google_config, validate_openalex_key)
from web_cache import default_cache
import corpus_manager
from version_compare import compare_versions
from analysis_history import default_history
import score_calibration
from text_exclusions import exclude_for_similarity
from zip_import import ZipImportError, extract_documents
from reference_check import check_references
from report_docx import build_report
import ocr_pdf
import image_reuse
import io
import time

BASE_DIR = Path(__file__).resolve().parent
UI_FILE = "detector_academic.html"

# Φάκελος με παλιές εργασίες για έλεγχο λογοκλοπής (τύπου Turnitin)
CORPUS_DIR = Path(os.environ.get("AI_DETECTOR_CORPUS", BASE_DIR / "corpus"))
CORPUS_DIR.mkdir(parents=True, exist_ok=True)
_corpus_readme = CORPUS_DIR / "README_CORPUS.txt"
if not _corpus_readme.exists():
    _corpus_readme.write_text(
        "Ρίξε σε αυτόν τον φάκελο παλιές εργασίες (.docx, .pdf, .txt, .md).\n"
        "Κάθε νέο κείμενο που αναλύεις θα συγκρίνεται με αυτές για κοινά\n"
        "αποσπάσματα (έλεγχος λογοκλοπής). Το ευρετήριο χτίζεται αυτόματα\n"
        "την πρώτη φορά και ενημερώνεται όταν προσθέτεις/αλλάζεις αρχεία.\n",
        encoding="utf-8")

corpus_index = CorpusIndex(CORPUS_DIR)
image_index = image_reuse.ImageIndex(CORPUS_DIR)
external_jobs = JobStore()


# ---------------------------------------------------------------------------
# Μηνύματα προς το UI — σε όσες γλώσσες έχει η σελίδα. Η σελίδα στέλνει τη
# γλώσσα της στο header X-UI-Lang· όπου λείπει μετάφραση, πέφτουμε στα αγγλικά.
# ---------------------------------------------------------------------------

APP_VERSION = "2.22"

DEFAULT_LANG = "en"

MESSAGES = {
    "no_file": {"el": "Δεν δόθηκε αρχείο", "en": "No file was provided",
        "de": 'Keine Datei übermittelt', "fr": 'Aucun fichier fourni', "pt": 'Nenhum ficheiro enviado'},
    "no_file_selected": {"el": "Δεν επιλέχθηκε αρχείο", "en": "No file was selected",
        "de": 'Keine Datei ausgewählt', "fr": 'Aucun fichier sélectionné', "pt": 'Nenhum ficheiro selecionado'},
    "bad_type": {"el": "Μη επιτρεπτός τύπος. Επιτρέπονται: {allowed}",
                 "en": "File type not allowed. Allowed: {allowed}",
        "de": 'Dateityp nicht erlaubt. Erlaubt: {allowed}', "fr": 'Type de fichier non autorisé. Autorisés : {allowed}', "pt": 'Tipo de ficheiro não permitido. Permitidos: {allowed}'},
    "not_enough_text": {
        "el": "Δεν βρέθηκε επαρκές κείμενο στο αρχείο. "
              "Αν είναι σκαναρισμένο PDF (εικόνες), χρειάζεται OCR.",
        "en": "Not enough text was found in the file. "
              "If it is a scanned PDF (images), it needs OCR first.",
        "de": 'In der Datei wurde nicht genug Text gefunden. Bei einem gescannten PDF (Bilder) ist zuerst OCR nötig.', "fr": "Pas assez de texte trouvé dans le fichier. S'il s'agit d'un PDF scanné (images), il faut d'abord un OCR.", "pt": 'Não foi encontrado texto suficiente no ficheiro. Se for um PDF digitalizado (imagens), precisa primeiro de OCR.'},
    "read_docx": {"el": "Σφάλμα ανάγνωσης DOCX: {detail}", "en": "Could not read the DOCX file: {detail}",
        "de": 'Die DOCX-Datei konnte nicht gelesen werden: {detail}', "fr": 'Impossible de lire le fichier DOCX : {detail}', "pt": 'Não foi possível ler o ficheiro DOCX: {detail}'},
    "read_pdf": {"el": "Σφάλμα ανάγνωσης PDF: {detail}", "en": "Could not read the PDF file: {detail}",
        "de": 'Die PDF-Datei konnte nicht gelesen werden: {detail}', "fr": 'Impossible de lire le fichier PDF : {detail}', "pt": 'Não foi possível ler o ficheiro PDF: {detail}'},
    "unsupported_type": {"el": "Μη υποστηριζόμενος τύπος αρχείου: {detail}",
                         "en": "Unsupported file type: {detail}",
        "de": 'Nicht unterstützter Dateityp: {detail}', "fr": 'Type de fichier non pris en charge : {detail}', "pt": 'Tipo de ficheiro não suportado: {detail}'},
    "internal": {"el": "Εσωτερικό σφάλμα κατά την ανάλυση", "en": "Internal error during analysis",
        "de": 'Interner Fehler bei der Analyse', "fr": "Erreur interne pendant l'analyse", "pt": 'Erro interno durante a análise'},
    "no_text": {"el": "Δεν δόθηκε κείμενο", "en": "No text was provided",
        "de": 'Kein Text übermittelt', "fr": 'Aucun texte fourni', "pt": 'Nenhum texto enviado'},
    "text_not_string": {"el": "Το πεδίο text πρέπει να είναι κείμενο", "en": "The text field must be a string",
        "de": 'Das Feld text muss eine Zeichenkette sein', "fr": 'Le champ text doit être une chaîne de caractères', "pt": 'O campo text tem de ser texto'},
    "empty_text": {"el": "Το κείμενο είναι κενό", "en": "The text is empty",
        "de": 'Der Text ist leer', "fr": 'Le texte est vide', "pt": 'O texto está vazio'},
    "brave_missing": {"el": "Συμπλήρωσε το Brave API key", "en": "Enter the Brave API key",
        "de": 'Gib den Brave-API-Schlüssel ein', "fr": 'Saisissez la clé API Brave', "pt": 'Introduza a chave da API Brave'},
    "google_missing": {"el": "Συμπλήρωσε και τα δύο πεδία (API key και Search Engine ID)",
                       "en": "Fill in both fields (API key and Search Engine ID)",
        "de": 'Fülle beide Felder aus (API-Schlüssel und Search Engine ID)', "fr": 'Remplissez les deux champs (clé API et Search Engine ID)', "pt": 'Preencha os dois campos (chave da API e Search Engine ID)'},
    "forbidden": {"el": "Μη επιτρεπτή προέλευση αιτήματος", "en": "Request origin not allowed",
        "de": 'Herkunft der Anfrage nicht erlaubt', "fr": 'Origine de la requête non autorisée', "pt": 'Origem do pedido não permitida'},
    "too_large": {"el": "Το αρχείο ξεπερνά το όριο των 100MB", "en": "The file exceeds the 100MB limit",
        "de": 'Die Datei überschreitet das Limit von 100 MB', "fr": 'Le fichier dépasse la limite de 100 Mo', "pt": 'O ficheiro excede o limite de 100 MB'},
    "too_many_files": {"el": "Πάρα πολλά αρχεία — μέγιστο {max} ανά μαζικό έλεγχο",
                       "en": "Too many files — at most {max} per batch",
                       "de": "Zu viele Dateien — höchstens {max} pro Stapel",
                       "fr": "Trop de fichiers — {max} au maximum par lot",
                       "pt": "Demasiados ficheiros — no máximo {max} por lote"},
    "bad_type_short": {"el": "Μη επιτρεπτός τύπος αρχείου (μόνο {allowed})",
                       "en": "File type not allowed (only {allowed})",
                       "de": "Dateityp nicht erlaubt (nur {allowed})",
                       "fr": "Type de fichier non autorisé (uniquement {allowed})",
                       "pt": "Tipo de ficheiro não permitido (apenas {allowed})"},
    "compare_need_two": {"el": "Διάλεξε και τα δύο αρχεία (παλιά και νέα έκδοση)",
                         "en": "Choose both files (old and new version)",
                         "de": "Wähle beide Dateien (alte und neue Version)",
                         "fr": "Choisissez les deux fichiers (ancienne et nouvelle version)",
                         "pt": "Escolha os dois ficheiros (versão antiga e nova)"},
    "corpus_bad_name": {"el": "Μη επιτρεπτό όνομα ή τύπος αρχείου (μόνο .docx, .pdf, .txt, .md)",
                        "en": "File name or type not allowed (only .docx, .pdf, .txt, .md)",
                        "de": "Dateiname oder -typ nicht erlaubt (nur .docx, .pdf, .txt, .md)",
                        "fr": "Nom ou type de fichier non autorisé (uniquement .docx, .pdf, .txt, .md)",
                        "pt": "Nome ou tipo de ficheiro não permitido (apenas .docx, .pdf, .txt, .md)"},
    "corpus_unreadable": {"el": "Το αρχείο δεν διαβάζεται (κατεστραμμένο ή λάθος τύπος)",
                          "en": "The file cannot be read (damaged or wrong type)",
                          "de": "Die Datei kann nicht gelesen werden (beschädigt oder falscher Typ)",
                          "fr": "Le fichier est illisible (endommagé ou mauvais type)",
                          "pt": "Não é possível ler o ficheiro (danificado ou tipo errado)"},
    "corpus_not_found": {"el": "Το αρχείο δεν βρέθηκε στο corpus", "en": "The file was not found in the corpus",
                         "de": "Die Datei wurde im Korpus nicht gefunden",
                         "fr": "Le fichier est introuvable dans le corpus",
                         "pt": "O ficheiro não foi encontrado no corpus"},
    "bad_zip": {"el": "Το ZIP δεν είναι έγκυρο ή είναι κατεστραμμένο", "en": "The ZIP file is invalid or damaged",
                "de": "Die ZIP-Datei ist ungültig oder beschädigt", "fr": "Le fichier ZIP est invalide ou endommagé",
                "pt": "O ficheiro ZIP é inválido ou está danificado"},
    "zip_too_many_entries": {"el": "Το ZIP έχει υπερβολικά πολλά αρχεία", "en": "The ZIP contains too many files",
                             "de": "Die ZIP-Datei enthält zu viele Dateien",
                             "fr": "Le ZIP contient trop de fichiers", "pt": "O ZIP contém demasiados ficheiros"},
    "calibration_not_enough": {
        "el": "Χρειάζονται τουλάχιστον {min} αναγνώσιμες εργασίες (100+ λέξεις) — βρέθηκαν {n}",
        "en": "At least {min} readable papers (100+ words) are needed — found {n}",
        "de": "Mindestens {min} lesbare Arbeiten (100+ Wörter) nötig — gefunden: {n}",
        "fr": "Au moins {min} travaux lisibles (100+ mots) sont nécessaires — trouvés : {n}",
        "pt": "São necessários pelo menos {min} trabalhos legíveis (100+ palavras) — encontrados {n}"},
    "scanned_no_ocr": {
        "el": "Το PDF είναι σκαναρισμένο (εικόνες χωρίς κείμενο). Για ανάγνωση χρειάζεται το δωρεάν "
              "Tesseract OCR με ελληνικά — δες Ρυθμίσεις → OCR.",
        "en": "The PDF is scanned (images without text). Reading it needs the free Tesseract OCR "
              "with Greek — see Settings → OCR.",
        "de": "Das PDF ist gescannt (Bilder ohne Text). Zum Lesen wird das kostenlose Tesseract OCR "
              "benötigt — siehe Einstellungen → OCR.",
        "fr": "Le PDF est scanné (images sans texte). Pour le lire, il faut l'OCR gratuit Tesseract "
              "— voir Paramètres → OCR.",
        "pt": "O PDF está digitalizado (imagens sem texto). Para o ler é preciso o OCR gratuito "
              "Tesseract — ver Definições → OCR."},
    "ocr_busy": {"el": "Τρέχει ήδη OCR σε άλλο έγγραφο — δοκίμασε ξανά σε λίγο",
                 "en": "OCR is already running on another document — try again shortly",
                 "de": "OCR läuft bereits für ein anderes Dokument — bitte gleich erneut versuchen",
                 "fr": "Un OCR est déjà en cours sur un autre document — réessayez dans un instant",
                 "pt": "Já está a decorrer OCR noutro documento — tente novamente daqui a pouco"},
    "bad_request": {"el": "Μη έγκυρο αίτημα", "en": "Invalid request", "de": "Ungültige Anfrage",
                    "fr": "Requête invalide", "pt": "Pedido inválido"},
    "history_not_found": {"el": "Η εγγραφή δεν βρέθηκε στο ιστορικό (ίσως διαγράφηκε ή έληξε)",
                          "en": "The entry was not found in the history (it may have been deleted or expired)",
                          "de": "Der Eintrag wurde im Verlauf nicht gefunden (evtl. gelöscht oder abgelaufen)",
                          "fr": "L'entrée est introuvable dans l'historique (supprimée ou expirée)",
                          "pt": "A entrada não foi encontrada no histórico (pode ter sido apagada ou expirado)"},
    "corpus_error": {"el": "Σφάλμα σύγκρισης corpus: {detail}", "en": "Corpus comparison error: {detail}",
        "de": 'Fehler beim Korpus-Vergleich: {detail}', "fr": 'Erreur de comparaison avec le corpus : {detail}', "pt": 'Erro na comparação com o corpus: {detail}'},
}


class ExtractionError(ValueError):
    """Σφάλμα εξαγωγής κειμένου με κλειδί μηνύματος για μετάφραση."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}")
        self.key = key
        self.detail = detail


def _ui_lang() -> str:
    lang = (request.headers.get("X-UI-Lang") or "").strip().lower()[:8]
    return lang if lang.isalpha() else DEFAULT_LANG


def _pick(texts: dict) -> str:
    return texts.get(_ui_lang()) or texts.get(DEFAULT_LANG) or next(iter(texts.values()), "")


def _msg(key: str, **params) -> str:
    return _pick(MESSAGES[key]).format(**params)


def _error(key: str, code: int, **params):
    return jsonify({"error": _msg(key, **params), "error_code": key, "status": "error"}), code


def _truthy(value, default=True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


def _safe_web_check(fn, *args, **kwargs) -> dict:
    """Ένας εξωτερικός έλεγχος — ποτέ δεν ρίχνει την κύρια ανάλυση."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"status": "offline", "hits": [], "error": str(e)}


def _web_jobs(text: str, want_web: bool, want_refs: bool, sim_text: str = None) -> dict:
    """Οι έλεγχοι που χρειάζονται internet: {όνομα: (συνάρτηση, args, kwargs)}.
    sim_text: κείμενο για τη λογοκλοπή (χωρίς παραθέματα/βιβλιογραφία)· οι
    αναφορές ελέγχονται πάντα στο πλήρες κείμενο."""
    jobs = {}
    full_text, text = text, (sim_text if sim_text is not None else text)
    if want_web:
        # Περισσότεροι δειγματοληπτικοί έλεγχοι σε μεγαλύτερα έγγραφα
        n_checks = min(30, max(12, len(text.split()) // 1500))
        jobs["wikipedia"] = (check_wikipedia, (text,), {"max_sentences": n_checks})
        # Ακαδημαϊκή βιβλιογραφία (OpenAlex — τύπου Google Scholar)
        jobs["scholar"] = (check_scholar, (text,), {"max_sentences": n_checks})
        # Brave Search (μόνο αν έχει ρυθμιστεί κλειδί) / Google (παλιά projects)
        jobs["brave"] = (check_brave, (text,), {})
        jobs["google"] = (check_google, (text,), {})
    if want_refs:
        jobs["references"] = (run_reference_check, (full_text, True), {})
    return jobs


def _similarity_text(text: str, exclude: bool):
    """(κείμενο για σύγκριση, πληροφορίες εξαίρεσης ή None)."""
    if not exclude:
        return text, None
    try:
        return exclude_for_similarity(text)
    except Exception:
        log.exception("Σφάλμα στην εξαίρεση παραθεμάτων/βιβλιογραφίας")
        return text, None


def _run_web_jobs(jobs: dict) -> dict:
    """Τρέχει τους ελέγχους ΤΑΥΤΟΧΡΟΝΑ: Wikipedia, OpenAlex, Brave, Google και
    Crossref είναι ανεξάρτητες, οπότε ο χρόνος ≈ ο πιο αργός, όχι το άθροισμα.
    Επιστρέφει {"plagiarism": {...web...}, "references": {...}}."""
    results = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {name: pool.submit(_safe_web_check, fn, *args, **kwargs)
                       for name, (fn, args, kwargs) in jobs.items()}
            results = {name: f.result() for name, f in futures.items()}
    references = results.pop("references", None) or run_reference_check("", False)
    return {"plagiarism": results, "references": references}


def _corpus_check(text: str) -> dict:
    # Τοπικό και γρήγορο· στο thread του αιτήματος (το μήνυμα σφάλματος
    # χρειάζεται τη γλώσσα του αιτήματος).
    try:
        return corpus_index.compare(text)
    except Exception as e:
        return {"error": _msg("corpus_error", detail=e)}


def run_external_checks(text: str, want_corpus: bool, want_web: bool,
                        want_refs: bool = False, exclude: bool = False):
    """Λογοκλοπή (corpus + web) και έλεγχος αναφορών, όλα μαζί (σύγχρονα).
    exclude: χωρίς παραθέματα «…» και βιβλιογραφία στη λογοκλοπή.
    Επιστρέφει (plagiarism, references)."""
    plagiarism = {"enabled": want_corpus or want_web}
    sim_text, excluded = _similarity_text(text, exclude and (want_corpus or want_web))
    if excluded is not None:
        plagiarism["excluded"] = excluded
    with ThreadPoolExecutor(max_workers=1) as pool:
        web = pool.submit(_run_web_jobs, _web_jobs(text, want_web, want_refs, sim_text))
        if want_corpus:
            plagiarism["corpus"] = _corpus_check(sim_text)
        web = web.result()
    plagiarism.update(web["plagiarism"])
    return plagiarism, web["references"]


def start_external_checks(text: str, want_corpus: bool, want_web: bool,
                          want_refs: bool = False, on_done=None, exclude: bool = False):
    """Όπως run_external_checks, αλλά οι έλεγχοι internet τρέχουν στο
    παρασκήνιο: επιστρέφει αμέσως (plagiarism, references, job_id) με
    "pending" όπου περιμένουμε αποτέλεσμα. Αν δεν χρειάζεται internet ή
    έχουν φτάσει τα όρια, τρέχει σύγχρονα και job_id = None."""
    sim_text, excluded = _similarity_text(text, exclude and (want_corpus or want_web))
    jobs = _web_jobs(text, want_web, want_refs, sim_text)

    def job():
        result = _run_web_jobs(jobs)
        if on_done:
            try:
                on_done(result)             # π.χ. ενημέρωση ιστορικού — ποτέ δεν ρίχνει τον έλεγχο
            except Exception:
                log.exception("Σφάλμα στο on_done ελέγχων internet")
        return result
    job_id = external_jobs.submit(job) if jobs else None
    if job_id is None:
        plagiarism, references = run_external_checks(text, want_corpus, want_web, want_refs,
                                                      exclude=exclude)
        return plagiarism, references, None
    plagiarism = {"enabled": want_corpus or want_web, "pending": want_web}
    if excluded is not None:
        plagiarism["excluded"] = excluded
    if want_corpus:
        plagiarism["corpus"] = _corpus_check(sim_text)
    references = ({"status": "pending", "results": [], "counts": {}} if want_refs
                  else run_reference_check(text, False))
    return plagiarism, references, job_id


def run_plagiarism_checks(text: str, want_corpus: bool, want_web: bool,
                          exclude: bool = False) -> dict:
    """Μόνο λογοκλοπή (χωρίς αναφορές) — π.χ. για τον μαζικό έλεγχο."""
    return run_external_checks(text, want_corpus, want_web, want_refs=False, exclude=exclude)[0]


def run_calibration_position(score) -> dict:
    """Πού βρίσκεται το σκορ σε σχέση με τις ανθρώπινες εργασίες αναφοράς (αν υπάρχουν)."""
    try:
        return score_calibration.position(score, score_calibration.load_profile())
    except Exception:
        log.exception("Σφάλμα στη βαθμονόμηση")
        return None


def run_image_check(path: str, doc: dict = None, thumbs: bool = True):
    """Ίδιες εικόνες/διαγράμματα με το corpus — ποτέ δεν ρίχνει την ανάλυση."""
    try:
        return image_index.compare(path, doc=doc, thumbs=thumbs)
    except Exception:
        log.exception("Σφάλμα στον έλεγχο εικόνων")
        return None


def run_reference_check(text: str, wanted: bool) -> dict:
    """Ύπαρξη βιβλιογραφικών αναφορών (Crossref/OpenAlex) — ποτέ δεν ρίχνει την ανάλυση."""
    if not wanted:
        return {"status": "disabled", "results": [], "counts": {}}
    try:
        return check_references(text)
    except Exception:
        log.exception("Σφάλμα στον έλεγχο αναφορών")
        return {"status": "offline", "results": [], "counts": {}}


def run_docx_forensics(path: str) -> dict:
    """Ιστορικό επεξεργασίας .docx — ποτέ δεν ρίχνει την ανάλυση."""
    try:
        return analyze_docx(path)
    except Exception:
        log.exception("Σφάλμα στο ιστορικό επεξεργασίας docx")
        return {"available": False, "reason": "unreadable", "findings": []}


def run_obfuscation_check(text: str) -> dict:
    """Κρυφοί χαρακτήρες / ομοιόγλυφα / βασανισμένες φράσεις — ποτέ δεν ρίχνει την ανάλυση."""
    try:
        return check_obfuscation(text)
    except Exception:
        log.exception("Σφάλμα στον έλεγχο απόκρυψης")
        return {"findings": [], "tortured": []}


def run_binoculars(text: str) -> dict:
    """Προαιρετική δεύτερη μέθοδος (Binoculars) — μόνο αν ενεργοποιηθεί, ποτέ δεν ρίχνει την ανάλυση."""
    try:
        return check_binoculars(text)
    except Exception:
        log.exception("Σφάλμα στο Binoculars")
        return {"status": "unavailable"}


def run_model_signature_check(text: str) -> dict:
    """Δευτερεύων, πειραματικός έλεγχος «υπογραφής» ChatGPT/Gemini/Claude.
    Ποτέ δεν ρίχνει την κύρια ανάλυση αν αποτύχει."""
    try:
        return detect_model_signature(text)
    except Exception as e:
        return {"has_signal": False, "primary_model": None, "error": str(e)}

log = logging.getLogger("ai_detector")

app = Flask(__name__)
# Χωρίς CORS: το UI σερβίρεται από τον ίδιο server (same-origin), οπότε καμία
# άλλη ιστοσελίδα που ανοίγει ο χρήστης δεν πρέπει να διαβάζει τις απαντήσεις
# ή να γράφει API keys στο localhost:5000.
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB — διπλωματικές με εικόνες

# Τα μόνα ονόματα host με τα οποία δεχόμαστε αιτήματα — μπλοκάρει DNS rebinding
# (κακόβουλο domain που «δείχνει» στο 127.0.0.1 για να παρακάμψει το same-origin).
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"}

CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    # Το UI είναι ένα αυτόνομο HTML με inline <script>/<style> και onclick
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def _host_allowed(netloc: str) -> bool:
    host = (netloc or "").strip().lower()
    if host.startswith("["):                     # IPv6: [::1]:5000
        host = host.split("]", 1)[0] + "]"
    else:
        host = host.rsplit(":", 1)[0] if ":" in host else host
    return host in ALLOWED_HOSTS


@app.before_request
def _block_foreign_requests():
    if not _host_allowed(request.host):
        abort(403)
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    # CSRF: ένα <form> από οποιοδήποτε site μπορεί να κάνει POST στο localhost
    # (π.χ. να ξοδέψει το όριο του Brave key). Δεχόμαστε μόνο από το δικό μας UI.
    if request.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
        abort(403)
    origin = request.headers.get("Origin")
    if origin is not None:
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or not _host_allowed(parts.netloc):
            abort(403)
    return None


@app.after_request
def _security_headers(resp):
    resp.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.path != "/":
        # Αποτελέσματα αναλύσεων = προσωπικά δεδομένα φοιτητών· όχι στην cache
        resp.headers["Cache-Control"] = "no-store"
    return resp

UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "ai_detector_uploads")
ALLOWED_EXTENSIONS = {"pdf", "docx"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_docx(file_path: str) -> str:
    """Εξαγωγή κειμένου από .docx — παράγραφοι ΚΑΙ πίνακες."""
    try:
        doc = Document(file_path)
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    except Exception as e:
        raise ExtractionError("read_docx", str(e))


def extract_text_from_pdf(file_path: str, ocr_info: dict = None) -> str:
    """Εξαγωγή κειμένου από .pdf (pdfplumber)· OCR για σκαναρισμένα, αν υπάρχει Tesseract.
    ocr_info: αν δοθεί dict, συμπληρώνεται με το τι έγινε στο OCR."""
    try:
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except Exception as e:
        raise ExtractionError("read_pdf", str(e))
    scanned = ocr_pdf.needs_ocr(pages)
    if scanned:
        texts, info = ocr_pdf.ocr_pages(file_path, scanned)
        for i, t in texts.items():
            pages[i] = t
        info["total_pages"] = len(pages)
        if ocr_info is not None:
            ocr_info.update(info)
        if not info["used"] and len(" ".join(pages).split()) < 10:
            raise ExtractionError("ocr_busy" if info.get("busy") else "scanned_no_ocr")
    return "\n".join(pages)


def extract_text(file_path: str, ocr_info: dict = None) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return extract_text_from_docx(file_path)
    if ext == ".pdf":
        return extract_text_from_pdf(file_path, ocr_info)
    raise ExtractionError("unsupported_type", ext)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Σερβίρει το web UI."""
    return send_from_directory(BASE_DIR, UI_FILE)


@app.route("/health", methods=["GET"])
def health():
    corpus_index.refresh()
    return jsonify({"status": "ok", "engine": "2.1", "version": APP_VERSION,
                    "corpus_files": corpus_index.n_files})


@app.route("/analyze", methods=["POST"])
def analyze_file():
    """Ανάλυση ανεβασμένου αρχείου (.docx / .pdf)."""
    saved_path = None
    try:
        if "file" not in request.files:
            return _error("no_file", 400)

        file = request.files["file"]
        if not file.filename:
            return _error("no_file_selected", 400)

        if not allowed_file(file.filename):
            return _error("bad_type", 400, allowed=", ".join(sorted(ALLOWED_EXTENSIONS)))

        # Ασφαλές προσωρινό όνομα — αποφυγή path traversal και συγκρούσεων
        ext = file.filename.rsplit(".", 1)[1].lower()
        safe_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename) or 'upload'}.{ext}"
        saved_path = os.path.join(UPLOAD_FOLDER, safe_name)
        file.save(saved_path)

        ocr_info = {}
        text = extract_text(saved_path, ocr_info)

        if not text or len(text.split()) < 10:
            return _error("not_enough_text", 422)

        analysis = engine_analyze(text, source=ext)
        if ocr_info:
            analysis["ocr"] = ocr_info
        analysis["model_signature"] = run_model_signature_check(text)
        analysis["obfuscation"] = run_obfuscation_check(text)
        analysis["binoculars"] = run_binoculars(text)
        want_web = _truthy(request.form.get("web"))
        history = default_history()
        hid = history.new_id() if history.enabled() else None
        # Οι αναφορές χρειάζονται internet: ακολουθούν το «web» αν δεν ζητηθεί ρητά
        _attach_external(analysis, text,
                         want_corpus=_truthy(request.form.get("plagiarism")),
                         want_web=want_web,
                         want_refs=_truthy(request.form.get("refs"), default=want_web),
                         progressive=_truthy(request.form.get("progressive"), default=False),
                         on_done=(lambda r: history.merge_external(hid, r)) if hid else None,
                         exclude=_truthy(request.form.get("exclude_quotes"), default=True))
        if ext == "docx":
            analysis["docx_history"] = run_docx_forensics(saved_path)
        if _truthy(request.form.get("plagiarism")):
            analysis["images"] = run_image_check(saved_path)
        if hid and history.save(hid, file.filename, analysis):
            analysis["history_id"] = hid

        return jsonify({
            "status": "success",
            "filename": file.filename,
            "analysis": analysis,
        }), 200

    except ExtractionError as e:
        return _error(e.key, 422, detail=e.detail)
    except Exception:
        log.exception("Σφάλμα στο /analyze")
        return _error("internal", 500)
    finally:
        if saved_path and os.path.exists(saved_path):
            try:
                os.remove(saved_path)
            except OSError:
                pass


MAX_BATCH_FILES = 30
MAX_BATCH_DOCS = 60          # μαζί με όσα έρχονται από ZIP (eClass/Moodle)


def _batch_items(files):
    """Αποθηκεύει τα ανεβασμένα αρχεία (και τα έγγραφα μέσα σε ZIP) σε
    προσωρινά αρχεία με τυχαία ονόματα. Επιστρέφει (items, προσωρινά αρχεία,
    σφάλματα ανά αρχείο, παραλείψεις ZIP)."""
    items, temps, errors, skipped = [], [], [], {}
    for file in files:
        name = file.filename
        ext = name.rsplit(".", 1)[1].lower() if "." in name else ""
        if ext == "zip":
            zpath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}.zip")
            temps.append(zpath)
            file.save(zpath)
            try:
                docs, sk = extract_documents(zpath, UPLOAD_FOLDER,
                                             max_docs=MAX_BATCH_DOCS - len(items))
            except ZipImportError as e:
                errors.append({"filename": name, "status": "error",
                               "error": _msg("bad_zip" if e.code == "bad_zip" else "zip_too_many_entries")})
                continue
            for k, v in sk.items():
                skipped[k] = skipped.get(k, 0) + v
            for d in docs:
                temps.append(d["path"])
                items.append({"filename": d["label"], "student": d["student"],
                              "path": d["path"], "ext": d["ext"], "source": name})
        elif allowed_file(name):
            if len(items) >= MAX_BATCH_DOCS:
                skipped["limit"] = skipped.get("limit", 0) + 1
                continue
            path = os.path.join(UPLOAD_FOLDER,
                                f"{uuid.uuid4().hex}_{secure_filename(name) or 'upload'}.{ext}")
            temps.append(path)
            file.save(path)
            items.append({"filename": name, "student": "", "path": path, "ext": ext})
        else:
            errors.append({"filename": name, "status": "error",
                           "error": _msg("bad_type_short", allowed="docx, pdf, zip")})
    return items, temps, errors, skipped


@app.route("/analyze-batch", methods=["POST"])
def analyze_batch():
    """Μαζικός έλεγχος: πολλά .docx/.pdf (ή ZIP από eClass/Moodle) + σύγκριση
    εργασιών μεταξύ τους.

    Χωρίς αναζητήσεις στο web (θα έπαιρνε πολύ χρόνο για δεκάδες αρχεία)·
    προαιρετικά σύγκριση με το τοπικό corpus (form: plagiarism=1)."""
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return _error("no_file", 400)
    if len(files) > MAX_BATCH_FILES:
        return _error("too_many_files", 400, max=MAX_BATCH_FILES)
    want_corpus = _truthy(request.form.get("plagiarism"), default=False)
    exclude = _truthy(request.form.get("exclude_quotes"), default=True)
    profile = score_calibration.load_profile()

    results, texts, temps, img_docs = [], [], [], []
    image_pairs = None
    try:
        items, temps, errors, skipped = _batch_items(files)
        results.extend(errors)
        for item in items:
            entry = {"filename": item["filename"]}
            if item["student"]:
                entry["student"] = item["student"]
            try:
                ocr_info = {}
                text = extract_text(item["path"], ocr_info)
                if not text or len(text.split()) < 10:
                    raise ExtractionError("not_enough_text", "")
                analysis = engine_analyze(text, source=item["ext"])
                if ocr_info:
                    analysis["ocr"] = ocr_info
                analysis["model_signature"] = run_model_signature_check(text)
                analysis["obfuscation"] = run_obfuscation_check(text)
                analysis["plagiarism"] = run_plagiarism_checks(text, want_corpus=want_corpus,
                                                               want_web=False, exclude=exclude)
                analysis["calibration"] = score_calibration.position(analysis["score"], profile)
                if item["ext"] == "docx":
                    analysis["docx_history"] = run_docx_forensics(item["path"])
                images = image_reuse.extract(item["path"])
                img_docs.append((item["filename"], item["path"], images))
                if want_corpus:
                    analysis["images"] = run_image_check(item["path"], doc=images, thumbs=False)
                entry.update(status="success", analysis=analysis)
                texts.append((item["filename"], _similarity_text(text, exclude)[0]))
            except ExtractionError as e:
                entry.update(status="error", error=_msg(e.key, detail=e.detail,
                                                        allowed=", ".join(sorted(ALLOWED_EXTENSIONS))))
            except Exception:
                log.exception("Σφάλμα στο /analyze-batch")
                entry.update(status="error", error=_msg("internal"))
            results.append(entry)
        try:
            # πριν σβηστούν τα προσωρινά αρχεία: οι μικρογραφίες διαβάζονται από αυτά
            image_pairs = image_reuse.batch_pairs(img_docs)
        except Exception:
            log.exception("Σφάλμα στη σύγκριση εικόνων")
    finally:
        for path in temps:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    try:
        pairs = pairwise_similarity(texts)
    except Exception:
        log.exception("Σφάλμα στη σύγκριση εργασιών")
        pairs = []
    return jsonify({"status": "success", "results": results, "pairs": pairs,
                    "image_pairs": image_pairs, "zip_skipped": skipped}), 200


# ---------------------------------------------------------------------------
# Βαθμονόμηση στα δικά σου δεδομένα (γνωστές ανθρώπινες εργασίες)
# ---------------------------------------------------------------------------

CALIBRATION_EXTENSIONS = {"docx", "pdf", "txt", "md"}


def _scores_for_uploads(files) -> list:
    """Σκορ AI για ανεβασμένα αρχεία/ZIP — τα κείμενα δεν κρατιούνται πουθενά."""
    scores, temps = [], []
    try:
        for file in files:
            name = file.filename or ""
            ext = name.rsplit(".", 1)[1].lower() if "." in name else ""
            paths = []
            if ext == "zip":
                zpath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}.zip")
                temps.append(zpath)
                file.save(zpath)
                try:
                    docs, _ = extract_documents(zpath, UPLOAD_FOLDER,
                                                allowed_ext=tuple("." + e for e in CALIBRATION_EXTENSIONS),
                                                max_docs=500)
                except ZipImportError:
                    continue
                for d in docs:
                    temps.append(d["path"])
                    paths.append(d["path"])
            elif ext in CALIBRATION_EXTENSIONS:
                path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}.{ext}")
                temps.append(path)
                file.save(path)
                paths.append(path)
            for path in paths:
                try:
                    if path.endswith((".txt", ".md")):
                        with open(path, encoding="utf-8", errors="replace") as fh:
                            text = fh.read()
                    else:
                        text = extract_text(path)
                except Exception:
                    continue
                if text and len(text.split()) >= 100:
                    scores.append(engine_analyze(text)["score"])
    finally:
        for path in temps:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
    return scores


@app.route("/calibration", methods=["GET"])
def calibration_get():
    profile = score_calibration.load_profile()
    return jsonify({"status": "success", "min_human": score_calibration.MIN_HUMAN,
                    "profile": score_calibration.summary(profile)}), 200


@app.route("/calibration/run", methods=["POST"])
def calibration_run():
    human = [f for f in request.files.getlist("human") if f and f.filename]
    ai = [f for f in request.files.getlist("ai") if f and f.filename]
    if not human:
        return _error("no_file", 400)
    if len(human) + len(ai) > 200:
        return _error("too_many_files", 400, max=200)
    human_scores = _scores_for_uploads(human)
    ai_scores = _scores_for_uploads(ai)
    try:
        profile = score_calibration.build_profile(human_scores, ai_scores,
                                                  name=_str_field(dict(request.form), "name", 80))
    except ValueError:
        return _error("calibration_not_enough", 400, n=len(human_scores),
                      min=score_calibration.MIN_HUMAN)
    score_calibration.save_profile(profile)
    return jsonify({"status": "success", "profile": score_calibration.summary(profile)}), 200


@app.route("/calibration/clear", methods=["POST"])
def calibration_clear():
    score_calibration.clear_profile()
    return jsonify({"status": "success"}), 200


@app.route("/analyze-text", methods=["POST"])
def analyze_text_route():
    """Ανάλυση απλού κειμένου (JSON: {"text": "..."})."""
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or "text" not in data:
            return _error("no_text", 400)

        if not isinstance(data["text"], str):
            return _error("text_not_string", 400)
        text = data["text"].strip()
        if not text:
            return _error("empty_text", 400)

        analysis = engine_analyze(text)
        analysis["model_signature"] = run_model_signature_check(text)
        analysis["obfuscation"] = run_obfuscation_check(text)
        analysis["binoculars"] = run_binoculars(text)
        want_web = _truthy(data.get("check_web"))
        history = default_history()
        hid = history.new_id() if history.enabled() else None
        _attach_external(analysis, text,
                         want_corpus=_truthy(data.get("check_plagiarism")),
                         want_web=want_web,
                         want_refs=_truthy(data.get("check_refs"), default=want_web),
                         progressive=_truthy(data.get("progressive"), default=False),
                         on_done=(lambda r: history.merge_external(hid, r)) if hid else None,
                         exclude=_truthy(data.get("exclude_quotes"), default=True))
        if hid and history.save(hid, None, analysis):
            analysis["history_id"] = hid
        return jsonify({"status": "success", "analysis": analysis}), 200

    except Exception:
        log.exception("Σφάλμα στο /analyze-text")
        return _error("internal", 500)


def _save_and_extract(file) -> str:
    """Αποθηκεύει προσωρινά ένα ανεβασμένο .docx/.pdf, βγάζει το κείμενο και
    σβήνει το αρχείο. Σηκώνει ExtractionError με κωδικό μηνύματος."""
    if not file or not file.filename:
        raise ExtractionError("no_file_selected")
    if not allowed_file(file.filename):
        raise ExtractionError("bad_type")
    ext = file.filename.rsplit(".", 1)[1].lower()
    path = os.path.join(UPLOAD_FOLDER,
                        f"{uuid.uuid4().hex}_{secure_filename(file.filename) or 'upload'}.{ext}")
    try:
        file.save(path)
        text = extract_text(path)
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    if not text or len(text.split()) < 10:
        raise ExtractionError("not_enough_text")
    return text


@app.route("/compare-versions", methods=["POST"])
def compare_versions_route():
    """Σύγκριση παλιάς και νέας έκδοσης της ίδιας εργασίας (μόνο τοπικά)."""
    old_file, new_file = request.files.get("old"), request.files.get("new")
    if not old_file or not new_file or not old_file.filename or not new_file.filename:
        return _error("compare_need_two", 400)
    try:
        result = compare_versions(_save_and_extract(old_file), _save_and_extract(new_file))
    except ExtractionError as e:
        return _error(e.key, 422, detail=e.detail, allowed=", ".join(sorted(ALLOWED_EXTENSIONS)))
    except Exception:
        log.exception("Σφάλμα στο /compare-versions")
        return _error("internal", 500)
    return jsonify({"status": "success", "old_filename": old_file.filename,
                    "new_filename": new_file.filename, "comparison": result}), 200


MAX_REPORT_BYTES = 2 * 1024 * 1024     # η σελίδα στέλνει μόνο τα πεδία που χρειάζονται


@app.route("/report/docx", methods=["POST"])
def report_docx():
    """Πρακτικό ελέγχου (.docx) από ένα αποτέλεσμα που ήδη έχει η σελίδα.
    Φτιάχνεται στη μνήμη· τίποτα δεν αποθηκεύεται στον δίσκο."""
    if request.content_length is None or request.content_length > MAX_REPORT_BYTES:
        return _error("bad_request", 413 if request.content_length else 400)
    try:
        data = _json_object()
    except RecursionError:
        data = {}
    analysis, meta = data.get("analysis"), data.get("meta")
    if not isinstance(analysis, dict) or not isinstance(meta or {}, dict):
        return _error("bad_request", 400)
    try:
        content = build_report(analysis, meta or {}, lang=_ui_lang(), app_version=APP_VERSION)
    except Exception:
        log.exception("Σφάλμα στο /report/docx")
        return _error("internal", 500)
    # Σταθερό ASCII όνομα: τίποτα από τον χρήστη στην κεφαλίδα Content-Disposition
    name = time.strftime("check_report_%Y%m%d_%H%M.docx")
    return send_file(io.BytesIO(content), as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


MAX_CORPUS_UPLOAD = 30


@app.route("/corpus", methods=["GET"])
def corpus_list():
    """Τα αρχεία του corpus (μόνο ονόματα, μέγεθος, ημερομηνία — όχι περιεχόμενο)."""
    return jsonify({"status": "success", "files": corpus_manager.list_files(CORPUS_DIR)}), 200


@app.route("/corpus/upload", methods=["POST"])
def corpus_upload():
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return _error("no_file", 400)
    if len(files) > MAX_CORPUS_UPLOAD:
        return _error("too_many_files", 400, max=MAX_CORPUS_UPLOAD)
    results = []
    for f in files:
        try:
            name = corpus_manager.save_upload(CORPUS_DIR, f.filename, f.stream)
            results.append({"filename": f.filename, "status": "saved", "name": name})
        except corpus_manager.CorpusError as e:
            key = {"bad_name": "corpus_bad_name", "unreadable": "corpus_unreadable",
                   "not_enough_text": "not_enough_text"}.get(e.code, "internal")
            results.append({"filename": f.filename, "status": "error", "error": _msg(key)})
        except Exception:
            log.exception("Σφάλμα στο ανέβασμα corpus")
            results.append({"filename": f.filename, "status": "error", "error": _msg("internal")})
    return jsonify({"status": "success", "results": results,
                    "files": corpus_manager.list_files(CORPUS_DIR)}), 200


@app.route("/corpus/delete", methods=["POST"])
def corpus_delete():
    name = _str_field(_json_object(), "name", max_len=200)
    if not name or not corpus_manager.delete_file(CORPUS_DIR, name):
        return _error("corpus_not_found", 404)
    return jsonify({"status": "success", "files": corpus_manager.list_files(CORPUS_DIR)}), 200


def _attach_external(analysis: dict, text: str, want_corpus: bool, want_web: bool,
                     want_refs: bool, progressive: bool, on_done=None,
                     exclude: bool = True) -> None:
    """progressive=True (το UI): οι έλεγχοι internet συνεχίζουν στο παρασκήνιο
    και το UI παίρνει τα αποτελέσματα από το /jobs/<id>. Αλλιώς (API) όλα μαζί."""
    if progressive:
        plagiarism, references, job_id = start_external_checks(
            text, want_corpus, want_web, want_refs, on_done=on_done, exclude=exclude)
        if job_id:
            analysis["external_job"] = job_id
    else:
        plagiarism, references = run_external_checks(text, want_corpus, want_web, want_refs,
                                                      exclude=exclude)
    analysis["plagiarism"], analysis["references"] = plagiarism, references
    analysis["calibration"] = run_calibration_position(analysis.get("score"))


@app.route("/history", methods=["GET"])
def history_list():
    """Λίστα του ιστορικού (μόνο σύνοψη: όνομα, ημερομηνία, σκορ)."""
    if request.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
        abort(403)
    history = default_history()
    return jsonify({"status": "success", "enabled": history.enabled(), "available": history.available,
                    "retention_days": int(history.retention // 86400),
                    "entries": history.list()}), 200


@app.route("/history/<hid>", methods=["GET"])
def history_get(hid):
    if request.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
        abort(403)
    entry = default_history().get(hid)
    if entry is None:
        return _error("history_not_found", 404)
    return jsonify(dict(entry, status="success")), 200


@app.route("/history/delete", methods=["POST"])
def history_delete():
    hid = _str_field(_json_object(), "id", max_len=64)
    if not default_history().delete(hid):
        return _error("history_not_found", 404)
    return jsonify({"status": "success"}), 200


@app.route("/history/clear", methods=["POST"])
def history_clear():
    return jsonify({"status": "success", "cleared": default_history().clear()}), 200


@app.route("/history/settings", methods=["POST"])
def history_settings():
    value = _json_object().get("enabled")
    if not isinstance(value, bool):
        return _error("bad_request", 400)
    default_history().set_enabled(value)
    return jsonify({"status": "success", "enabled": default_history().enabled()}), 200


@app.route("/jobs/<job_id>", methods=["GET"])
def external_job_status(job_id):
    """Αποτέλεσμα ελέγχων internet που ξεκίνησαν με progressive=1. Δίνεται μία
    φορά (μετά σβήνεται). 404 για άγνωστο/ληγμένο αναγνωριστικό."""
    # Άμυνα σε βάθος: τα αποτελέσματα διαβάζονται μόνο από το δικό μας UI
    if request.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
        abort(403)
    result = external_jobs.poll(job_id)
    if result is None:
        return jsonify({"status": "unknown"}), 404
    return jsonify(result), 200


def _json_object() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _str_field(data: dict, name: str, max_len: int = 256) -> str:
    """Κλειδιά API: μόνο σύντομο κείμενο χωρίς control χαρακτήρες."""
    value = data.get(name)
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if len(value) > max_len or any(ord(ch) < 0x20 for ch in value):
        return ""
    return value


@app.route("/config/search", methods=["GET"])
def search_config_status():
    """Ποιοι πάροχοι web αναζήτησης είναι ρυθμισμένοι;"""
    return jsonify({"brave": _load_brave_config() is not None,
                    "google": _load_google_config() is not None,
                    "openalex": openalex_api_key() is not None,
                    "cache": default_cache().stats(),
                    "ocr": _ocr_status()})


def _ocr_status() -> dict:
    st = ocr_pdf.status()
    return {"available": bool(st.get("available")), "greek": "ell" in st.get("langs", []),
            "disabled": bool(st.get("disabled"))}


@app.route("/config/openalex", methods=["POST"])
def openalex_config_save():
    """Αποθήκευση κλειδιού OpenAlex μετά από ζωντανή επαλήθευση. Το κλειδί
    δεν επιστρέφεται ποτέ πίσω στη σελίδα ούτε γράφεται σε log."""
    api_key = _str_field(_json_object(), "api_key", max_len=128)
    ok, message = validate_openalex_key(api_key)
    if not ok:
        return jsonify({"status": "error", "error": _pick(message)}), 400
    save_openalex_key(api_key)
    return jsonify({"status": "success", "message": _pick(message)}), 200


@app.route("/cache/clear", methods=["POST"])
def cache_clear():
    """Σβήνει την τοπική cache των εξωτερικών ελέγχων (Wikipedia/OpenAlex/Crossref)."""
    cache = default_cache()
    before = cache.stats()["entries"]
    cache.clear()
    return jsonify({"status": "success", "cleared": before}), 200


@app.route("/config/brave", methods=["POST"])
def brave_config_save():
    """Αποθήκευση κλειδιού Brave μετά από ζωντανή επαλήθευση."""
    data = _json_object()
    api_key = _str_field(data, "api_key")
    if not api_key:
        return _error("brave_missing", 400)

    ok, message = validate_brave_config(api_key)
    if not ok:
        return jsonify({"status": "error", "error": _pick(message)}), 400

    save_brave_config(api_key)
    return jsonify({"status": "success", "message": _pick(message)}), 200


@app.route("/config/google", methods=["GET"])
def google_config_status():
    """Είναι ρυθμισμένος ο έλεγχος Google;"""
    return jsonify({"configured": _load_google_config() is not None})


@app.route("/config/google", methods=["POST"])
def google_config_save():
    """Αποθήκευση κλειδιών Google μετά από ζωντανή επαλήθευση."""
    data = _json_object()
    api_key = _str_field(data, "api_key")
    cse_id = _str_field(data, "cse_id")
    if not api_key or not cse_id:
        return _error("google_missing", 400)

    ok, message = validate_google_config(api_key, cse_id)
    if not ok:
        return jsonify({"status": "error", "error": _pick(message)}), 400

    save_google_config(api_key, cse_id)
    return jsonify({"status": "success", "message": _pick(message)}), 200


@app.errorhandler(403)
def forbidden(_):
    return _error("forbidden", 403)


@app.errorhandler(413)
def too_large(_):
    return _error("too_large", 413)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    print()
    print("=" * 60)
    print(f"  AI Content Detector v{APP_VERSION}")
    print("  Άνοιξε στον browser / Open in your browser:  http://localhost:5000")
    print("  Τερματισμός / Stop: Ctrl+C ή κλείσιμο του παραθύρου")
    print("=" * 60)
    print()
    # threaded=True: μεγάλα PDF (200 σελίδες ≈ 10-60s) δεν μπλοκάρουν το UI
    # host=127.0.0.1: το εργαλείο δεν έχει καμία αυθεντικοποίηση (ανέβασμα αρχείων,
    # ρύθμιση API keys) — 0.0.0.0 θα το εξέθετε σε ΟΛΟ το τοπικό δίκτυο.
    app.run(debug=False, host="127.0.0.1", port=5000, threaded=True)


if __name__ == "__main__":
    main()
