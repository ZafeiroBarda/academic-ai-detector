#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Έλεγχος ύπαρξης βιβλιογραφικών αναφορών (Crossref + OpenAlex).

Τα γλωσσικά μοντέλα συχνά «επινοούν» αναφορές: πραγματικοί συγγραφείς,
αληθοφανής τίτλος, ανύπαρκτο άρθρο ή DOI. Εδώ βρίσκουμε την ενότητα
βιβλιογραφίας, χωρίζουμε τις αναφορές, και ψάχνουμε την καθεμία:

  1. Αν έχει DOI → το DOI πρέπει να υπάρχει (όλα τα DOI ρωτιούνται μαζί στο
     OpenAlex με ένα αίτημα· όσα λείπουν από εκεί, στο Crossref) και ο τίτλος
     του να ταιριάζει με τον τίτλο της αναφοράς.
  2. Αλλιώς → αναζήτηση στο Crossref (query.bibliographic) και, αν δεν
     βρεθεί, στο OpenAlex· συγκρίνουμε τίτλο και έτος.

Αποτέλεσμα ανά αναφορά (status):
  verified      βρέθηκε δημοσίευση με τον ίδιο τίτλο (και έτος ±1)
  partial       βρέθηκε κάτι παρόμοιο αλλά όχι ίδιο (π.χ. άλλο έτος/τίτλος)
  doi_mismatch  το DOI υπάρχει αλλά ανήκει σε ΑΛΛΗ δημοσίευση — ύποπτο
  doi_not_found το DOI δεν υπάρχει — ισχυρή ένδειξη επινοημένης αναφοράς
  not_found     δεν βρέθηκε πουθενά — ύποπτο, όχι απόδειξη (βιβλία, ελληνικές
                ή τοπικές εκδόσεις λείπουν συχνά από τις βάσεις)
  skipped_web   ιστοσελίδα/URL χωρίς DOI — δεν ελέγχεται
  unparsed      δεν αναγνωρίστηκε τίτλος

Δεν επηρεάζει το σκορ AI — είναι ξεχωριστή ένδειξη για έλεγχο από άνθρωπο.
Τα αποτελέσματα κρατιούνται στην τοπική cache (web_cache.py), οπότε ο
ξαναέλεγχος της ίδιας βιβλιογραφίας δεν ξαναρωτά το internet.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
import unicodedata
import urllib.error
import urllib.parse
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional, Tuple

import http_pool
from plagiarism_engine import openalex_params, polite_user_agent
from web_cache import WebCache, default_cache

CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"

MAX_REFERENCES = 40       # όριο ελέγχων ανά έγγραφο
REQUEST_DELAY = 0.15      # παύση ανάμεσα σε ομάδες αιτημάτων (ευγένεια προς τα δημόσια APIs)
PARALLEL_REFS = 4         # ταυτόχρονα αιτήματα — Crossref polite pool: έως 5 (από 12/2025)
DOI_BATCH = 50            # DOI ανά αίτημα στο OpenAlex (filter=doi:a|b|…)
RATE_LIMIT_WAIT_MAX = 10.0
VERIFIED_SIMILARITY = 0.85
PARTIAL_SIMILARITY = 0.60

# Επικεφαλίδες ενότητας βιβλιογραφίας (μόνες τους σε γραμμή)
_HEADING_RE = re.compile(
    r"^\s*(?:\d+[\.\)]?\s*)?(references|reference list|bibliography|works cited|"
    r"literature cited|sources|βιβλιογραφία|βιβλιογραφικές αναφορές|αναφορές|"
    r"πηγές|ελληνική βιβλιογραφία|ξενόγλωσση βιβλιογραφία|διεθνής βιβλιογραφία|"
    r"literaturverzeichnis|literatur|bibliographie|références|referências|"
    r"referências bibliográficas)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE)
# Ό,τι ακολουθεί μετά τη βιβλιογραφία και δεν είναι αναφορές
_END_RE = re.compile(r"^\s*(appendix|appendices|παράρτημα|παραρτήματα|anhang|annexe|anexo)\b",
                     re.IGNORECASE | re.MULTILINE)

_NUMBERED_START = re.compile(r"^\s*(\[\d{1,3}\]|\d{1,3}[\.\)])\s+")
_AUTHOR_START = re.compile(
    r"^\s*[A-ZÀ-ÖØ-ÞΑ-ΩΆ-Ώ][\w'’\-]+(?:\s[A-ZÀ-ÖØ-ÞΑ-ΩΆ-Ώ][\w'’\-]+)?,\s+"
    r"(?:[A-ZÀ-ÖØ-ÞΑ-ΩΆ-Ώ]\.|[A-ZÀ-ÖØ-ÞΑ-ΩΆ-Ώ][a-zß-ÿα-ωά-ώ]+)", re.UNICODE)
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
_YEAR_PAREN_RE = re.compile(r"\((?:[^()]*?)((?:19|20)\d{2})[a-z]?\)")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})[a-z]?\b")
_QUOTED_TITLE_RE = re.compile(r"[“\"«]([^”\"»]{10,300})[”\"»]")
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_GREEK_RE = re.compile(r"[α-ωά-ώΑ-ΩΆ-Ώ]")

HttpGet = Callable[[str], Optional[Dict]]

# Όλοι οι κωδικοί αποτελέσματος — το UI πρέπει να έχει κείμενο για καθέναν
STATUSES = ("verified", "partial", "doi_mismatch", "doi_not_found", "not_found",
            "skipped_web", "unparsed")


# ---------------------------------------------------------------------------
# Εντοπισμός και ανάλυση αναφορών
# ---------------------------------------------------------------------------

def find_reference_section(text: str) -> str:
    """Το κείμενο μετά την ΤΕΛΕΥΤΑΙΑ επικεφαλίδα βιβλιογραφίας (η πρώτη μπορεί
    να είναι στον πίνακα περιεχομένων), μέχρι τυχόν παράρτημα."""
    headings = list(_HEADING_RE.finditer(text or ""))
    if not headings:
        return ""
    section = text[headings[-1].end():]
    end = _END_RE.search(section)
    return section[:end.start()] if end else section


_TRAILING_LINK_RE = re.compile(r"(https?://\S+|\b10\.\d{4,9}/\S+)$", re.IGNORECASE)


def _closes_entry(line: str) -> bool:
    """Η γραμμή κλείνει αναφορά: τελεία/παρένθεση ή DOI/URL στο τέλος."""
    line = line.rstrip()
    return line.endswith((".", ")")) or bool(_TRAILING_LINK_RE.search(line))


def split_references(section: str) -> List[str]:
    """Χωρίζει την ενότητα σε αναφορές. Νέα αναφορά ξεκινά σε αριθμημένη
    γραμμή ([1], 1.) ή σε γραμμή «Επώνυμο, Α.» όταν η προηγούμενη έκλεισε."""
    lines = [ln.strip() for ln in section.splitlines()]
    entries: List[str] = []
    cur: List[str] = []
    numbered = sum(1 for ln in lines if _NUMBERED_START.match(ln)) >= 2

    def flush():
        if cur:
            entry = re.sub(r"\s+", " ", " ".join(cur)).strip()
            if len(entry) >= 25:
                entries.append(entry)
            cur.clear()

    for ln in lines:
        if not ln:
            flush()
            continue
        if numbered:
            starts_new = bool(_NUMBERED_START.match(ln))
        else:
            looks_like_start = bool(_AUTHOR_START.match(ln) or _YEAR_PAREN_RE.search(ln[:150]))
            starts_new = looks_like_start and (not cur or _closes_entry(cur[-1]))
        if starts_new:
            flush()
        cur.append(ln)
    flush()
    return entries


def _clean_doi(doi: str) -> str:
    return doi.rstrip(".,;)]}>").strip()


def parse_reference(entry: str) -> Dict:
    """Βγάζει DOI, έτος και τίτλο από μια αναφορά (APA/Harvard/IEEE/Chicago)."""
    body = _NUMBERED_START.sub("", entry, count=1)
    doi_m = _DOI_RE.search(body)
    doi = _clean_doi(doi_m.group(1)) if doi_m else None

    year = None
    year_m = _YEAR_PAREN_RE.search(body) or _YEAR_RE.search(body)
    if year_m:
        year = int(year_m.group(1))

    title = None
    quoted = _QUOTED_TITLE_RE.search(body)
    if quoted:                                   # IEEE / Chicago: «Τίτλος»
        title = quoted.group(1).strip(" ,.")
    elif year_m and _YEAR_PAREN_RE.search(body):  # APA: Συγγραφείς (έτος). Τίτλος. Περιοδικό
        after = body[year_m.end():].lstrip(" .,:")
        title = re.split(r"(?<=[^\s.]{3})\.\s|\?\s|\sIn:\s", after, maxsplit=1)[0].strip(" ,.")
    else:                                        # Harvard χωρίς παρενθέσεις: Συγγραφείς, έτος, Τίτλος, ...
        parts = [p.strip() for p in re.split(r"\.\s|,\s(?=[A-ZΑ-Ω])", body) if p.strip()]
        candidates = [p for p in parts if len(p.split()) >= 3 and not _DOI_RE.search(p)]
        if candidates:
            title = max(candidates[:3], key=len)
    if title and (len(title.split()) < 3 or len(title) > 300):
        title = None

    return {
        "ref": entry if len(entry) <= 300 else entry[:297] + "…",
        "doi": doi,
        "year": year,
        "title": title,
        "is_web": bool(_URL_RE.search(body)) and not doi,
        "greek": bool(_GREEK_RE.search(title or body)),
    }


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", s).strip()


def title_similarity(cited: str, found: str) -> float:
    """1.0 = ίδιος τίτλος. Ο υπότιτλος (μετά από «:») συχνά λείπει από τη μία πλευρά."""
    a, b = _norm(cited), _norm(found)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter.split()) >= 4 and longer.startswith(shorter):
        ratio = max(ratio, 0.95)
    return ratio


# ---------------------------------------------------------------------------
# Αναζήτηση στις βάσεις
# ---------------------------------------------------------------------------

class _NotFound(Exception):
    pass


def _http_get_json(url: str, timeout: float = 8.0) -> Optional[Dict]:
    """GET JSON. None στο 404 (δεν υπάρχει)· εξαίρεση για σφάλματα δικτύου.
    Σε 429 (πολλά αιτήματα) περιμένει όσο ζητά ο server (έως 10 s) και
    ξαναδοκιμάζει μία φορά."""
    headers = {"User-Agent": polite_user_agent()}
    for attempt in (0, 1):
        try:
            return http_pool.get_json(url, headers=headers, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 and attempt == 0:
                retry_after = (e.headers.get("Retry-After") if e.headers else None) or ""
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = 2.0
                time.sleep(min(max(wait, 0.5), RATE_LIMIT_WAIT_MAX))
                continue
            raise
    return None


def _crossref_title(item: Dict) -> str:
    t = item.get("title") or []
    return (t[0] if isinstance(t, list) and t else t) or ""


def _crossref_year(item: Dict) -> Optional[int]:
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _candidate(title: str, year: Optional[int], doi: Optional[str], source: str) -> Dict:
    return {"title": title, "year": year,
            "url": f"https://doi.org/{doi}" if doi else "", "source": source}


def _grade(ref: Dict, cand: Dict) -> Tuple[str, float]:
    sim = title_similarity(ref["title"] or ref["ref"], cand["title"])
    year_ok = not ref["year"] or not cand["year"] or abs(ref["year"] - cand["year"]) <= 1
    if sim >= VERIFIED_SIMILARITY and year_ok:
        return "verified", sim
    if sim >= PARTIAL_SIMILARITY:
        return "partial", sim
    return "not_found", sim


# Σύνταξη DOI που επιτρέπεται στο ομαδικό φίλτρο (χωρίς | , κενά κ.λπ., ώστε
# ένα DOI από το κείμενο να μην μπορεί να αλλάξει το ερώτημα). Τα υπόλοιπα
# ελέγχονται ένα-ένα στο Crossref, με κωδικοποίηση στο URL.
_BATCH_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:a-z0-9]+$")


def prefetch_dois(refs: List[Dict], http_get: HttpGet = _http_get_json) -> Dict[str, Dict]:
    """Όλα τα DOI με ελάχιστα αιτήματα στο OpenAlex: {doi (πεζά): υποψήφιο}.
    Όσα δεν βρεθούν (ή αν αποτύχει το αίτημα) ελέγχονται κανονικά στο Crossref."""
    dois = []
    for r in refs:
        d = (r.get("doi") or "").lower()
        if d and _BATCH_DOI_RE.match(d) and d not in dois:
            dois.append(d)
    found: Dict[str, Dict] = {}
    for start in range(0, len(dois), DOI_BATCH):
        chunk = dois[start:start + DOI_BATCH]
        params = openalex_params({"filter": "doi:" + "|".join(chunk), "per-page": DOI_BATCH,
                                  "select": "doi,title,publication_year"})
        try:
            data = http_get(f"{OPENALEX_API}?{urllib.parse.urlencode(params)}") or {}
        except Exception:
            continue                       # fallback: Crossref ανά DOI
        for w in data.get("results") or []:
            if not isinstance(w, dict):
                continue
            doi = (w.get("doi") or "").lower().replace("https://doi.org/", "")
            if doi in chunk and w.get("title"):
                found[doi] = _candidate(str(w["title"]), w.get("publication_year"), doi, "openalex")
    return found


def _grade_doi(ref: Dict, out: Dict, cand: Dict) -> Dict:
    if not ref["title"]:
        out.update(status="verified", match=cand, similarity=1.0)
        return out
    status, sim = _grade(ref, cand)
    out.update(status="verified" if status == "verified" else "doi_mismatch",
               match=cand, similarity=round(sim, 2))
    return out


def check_one(ref: Dict, http_get: HttpGet = _http_get_json,
              prefetched: Optional[Dict[str, Dict]] = None) -> Dict:
    """Ελέγχει μία αναφορά. Ρίχνει εξαίρεση μόνο σε σφάλμα δικτύου."""
    out = dict(ref)
    if ref["doi"]:
        cand = (prefetched or {}).get(ref["doi"].lower())
        if cand:
            return _grade_doi(ref, out, cand)
        data = http_get(f"{CROSSREF_API}/{urllib.parse.quote(ref['doi'], safe='/')}")
        if data is None:
            out.update(status="doi_not_found", match=None, similarity=0.0)
            return out
        item = data.get("message") or {}
        cand = _candidate(_crossref_title(item), _crossref_year(item), ref["doi"], "crossref")
        return _grade_doi(ref, out, cand)

    if ref["is_web"]:
        out.update(status="skipped_web", match=None, similarity=0.0)
        return out
    if not ref["title"]:
        out.update(status="unparsed", match=None, similarity=0.0)
        return out

    best: Tuple[str, float, Optional[Dict]] = ("not_found", 0.0, None)
    q = urllib.parse.urlencode({"query.bibliographic": ref["ref"][:300], "rows": 3,
                                "select": "DOI,title,issued,published-print,published-online"})
    data = http_get(f"{CROSSREF_API}?{q}") or {}
    for item in (data.get("message") or {}).get("items", []):
        cand = _candidate(_crossref_title(item), _crossref_year(item), item.get("DOI"), "crossref")
        status, sim = _grade(ref, cand)
        if sim > best[1]:
            best = (status, sim, cand)

    if best[0] != "verified":
        q = urllib.parse.urlencode(openalex_params({"search": ref["title"][:200], "per-page": 3,
                                                    "select": "title,publication_year,doi"}))
        data = http_get(f"{OPENALEX_API}?{q}") or {}
        for w in data.get("results", []):
            doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
            cand = _candidate(w.get("title") or "", w.get("publication_year"), doi, "openalex")
            status, sim = _grade(ref, cand)
            if sim > best[1]:
                best = (status, sim, cand)

    status, sim, cand = best
    out.update(status=status, match=cand if status != "not_found" else None,
               similarity=round(sim, 2))
    return out


def _try_check(ref: Dict, http_get: HttpGet, prefetched: Optional[Dict[str, Dict]] = None):
    try:
        return check_one(ref, http_get, prefetched)
    except Exception:
        return None          # σφάλμα δικτύου για αυτή την αναφορά


_STATUSES = {"verified", "partial", "doi_mismatch", "doi_not_found", "not_found",
             "skipped_web", "unparsed"}
_NEGATIVE = {"not_found", "doi_not_found"}


def _cache_query(ref: Dict) -> str:
    return " ".join(ref["ref"].split())


def _from_cache(ref: Dict, value) -> Optional[Dict]:
    """Επικυρώνει ό,τι διαβάστηκε από την cache πριν χρησιμοποιηθεί."""
    if not isinstance(value, dict) or value.get("status") not in _STATUSES:
        return None
    match = value.get("match")
    sim = value.get("similarity")
    if match is not None and not isinstance(match, dict):
        return None
    if not isinstance(sim, (int, float)):
        return None
    out = dict(ref)
    out.update(status=value["status"], match=match, similarity=float(sim), cached=True)
    return out


def check_references(text: str, http_get: HttpGet = _http_get_json,
                     max_refs: int = MAX_REFERENCES, delay: float = REQUEST_DELAY,
                     workers: int = PARALLEL_REFS, cache: Optional[WebCache] = None) -> Dict:
    """Κύρια συνάρτηση. status: ok | partial | offline | no_references.

    1. Όσες αναφορές ελέγχθηκαν πρόσφατα έρχονται από την τοπική cache.
    2. Τα DOI των υπόλοιπων ρωτιούνται μαζί στο OpenAlex (prefetch_dois).
    3. Οι υπόλοιπες ελέγχονται σε ομάδες των `workers` ταυτόχρονα.
    Η σειρά των αποτελεσμάτων διατηρείται. 3 συνεχόμενες αποτυχίες δικτύου, με
    τη σειρά της βιβλιογραφίας, σταματούν τον έλεγχο."""
    entries = split_references(find_reference_section(text))
    if not entries:
        return {"status": "no_references", "total": 0, "checked": 0,
                "counts": {}, "results": []}

    cache = cache if cache is not None else default_cache()
    refs = [parse_reference(e) for e in entries[:max_refs]]
    outcomes: List[Optional[Dict]] = [None] * len(refs)
    for i, ref in enumerate(refs):
        outcomes[i] = _from_cache(ref, cache.get("ref", _cache_query(ref)))
    todo = [i for i, o in enumerate(outcomes) if o is None]

    prefetched = prefetch_dois([refs[i] for i in todo], http_get) if any(
        refs[i]["doi"] for i in todo) else {}

    consecutive_fails = 0
    stopped = False
    workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for start in range(0, len(todo), workers):
            group = todo[start:start + workers]
            for i, outcome in zip(group, pool.map(
                    lambda j: _try_check(refs[j], http_get, prefetched), group)):
                if outcome is None:
                    consecutive_fails += 1
                    if consecutive_fails >= 3:
                        stopped = True
                        break
                else:
                    outcomes[i] = outcome
                    consecutive_fails = 0
                    if outcome["status"] not in ("skipped_web", "unparsed"):
                        cache.put("ref", _cache_query(refs[i]),
                                  {"status": outcome["status"], "match": outcome.get("match"),
                                   "similarity": outcome.get("similarity", 0.0)},
                                  negative=outcome["status"] in _NEGATIVE)
            if stopped:
                break
            if delay and start + workers < len(todo):
                time.sleep(delay)

    results = [o for o in outcomes if o is not None]
    status = "ok"
    if stopped:
        status = "offline" if not results else "partial"

    counts: Dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "status": status,
        "total": len(entries),
        "checked": len(results),
        "truncated": len(entries) > max_refs,
        "counts": counts,
        "results": results,
    }
