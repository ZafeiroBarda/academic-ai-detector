#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plagiarism / Similarity Engine v1.0  (λειτουργία τύπου Turnitin)
================================================================
Δύο μηχανισμοί ελέγχου ομοιότητας:

1. **Τοπικό corpus** — σύγκριση με φάκελο παλιών εργασιών (docx/pdf/txt/md).
   Αλγόριθμος: winnowing fingerprints (Schleimer et al. 2003 — ο ίδιος που
   χρησιμοποιεί το MOSS του Stanford). Ανθεκτικός σε αλλαγές κεφαλαίων,
   τόνων και στίξης. Εντοπίζει κοινά αποσπάσματα ≥ ~10 λέξεων και βγάζει
   ποσοστό ομοιότητας ανά πηγή + τα ακριβή χωρία.

2. **Wikipedia (EN + EL)** — δειγματοληπτικός έλεγχος χαρακτηριστικών
   προτάσεων με exact-phrase αναζήτηση στο δωρεάν Wikipedia API.
   Η Wikipedia είναι η συχνότερη πηγή αντιγραφής σε φοιτητικές εργασίες.

ΔΕΝ αντικαθιστά το Turnitin: δεν έχει πρόσβαση στην ιδιωτική βάση του
(συνδρομητικά journals, εργασίες άλλων ιδρυμάτων). Καλύπτει όμως τα δύο
συχνότερα σενάρια: αντιγραφή από παλιότερες εργασίες και από Wikipedia.
"""

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import http_pool
from obfuscation_check import fold_homoglyphs, strip_invisible
from web_cache import WebCache, default_cache

# --- Παράμετροι winnowing ---
K = 7   # μέγεθος shingle σε λέξεις
W = 4   # παράθυρο winnowing → εγγυημένη ανίχνευση κοινών αποσπασμάτων ≥ K+W-1 = 10 λέξεων

CACHE_NAME = ".corpus_index.json"
CACHE_VERSION = 2   # 2: αφαίρεση αόρατων χαρακτήρων / ομοιόγλυφων στο tokenize
CORPUS_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}

# Η Wikimedia ζητά User-Agent με στοιχεία επικοινωνίας — χωρίς αυτό τα αιτήματα
# περιορίζονται/μπλοκάρονται πιο εύκολα.
PROJECT_URL = "https://github.com/ZafeiroBarda/academic-ai-detector"
USER_AGENT = f"ai-detector-edu/1.1 (educational plagiarism checker; {PROJECT_URL})"

_EMAIL_RE = re.compile(r"^[^@\s;()<>,]+@[^@\s;()<>,]+\.[A-Za-z]{2,}$")


def contact_email(config_path: Optional[str] = None) -> Optional[str]:
    """Προαιρετικό email επικοινωνίας για τα «polite pools» OpenAlex/Crossref —
    ανήκει σε όποιον τρέχει το εργαλείο, ΟΧΙ στον κώδικα. Από
    AI_DETECTOR_CONTACT_EMAIL ή search_config.json {"contact_email": "..."}.
    Χωρίς email τα αιτήματα στέλνονται χωρίς mailto (δουλεύουν κανονικά)."""
    email = (os.environ.get("AI_DETECTOR_CONTACT_EMAIL") or "").strip()
    if not email:
        path = Path(config_path) if config_path else Path(__file__).parent / "search_config.json"
        try:
            email = str(json.loads(path.read_text(encoding="utf-8")).get("contact_email") or "").strip()
        except Exception:
            email = ""
    return email if _EMAIL_RE.match(email) else None


def polite_user_agent() -> str:
    """USER_AGENT + (mailto:…) μόνο αν ο χρήστης έχει δώσει email."""
    email = contact_email()
    return f"{USER_AGENT} (mailto:{email})" if email else USER_AGENT
# Wikipedia: αιτήματα πάντα ΣΕΙΡΙΑΚΑ (ένα τη φορά, όπως ζητά η πολιτική της
# Wikimedia). Κανονικά 1 s παύση· μετά από 429 ή αποτυχημένο canary («ύποπτα
# 0 αποτελέσματα») ο ρυθμός πέφτει στα 2 s για 10 λεπτά, σε όλους τους ελέγχους.
REQUEST_DELAY = 1.0
SLOW_DELAY = 2.0
SLOW_MODE_SECONDS = 600
_wiki_slow_until = 0.0


def _wiki_delay() -> float:
    return SLOW_DELAY if time.time() < _wiki_slow_until else REQUEST_DELAY


def _wiki_slow_down() -> None:
    global _wiki_slow_until
    _wiki_slow_until = time.time() + SLOW_MODE_SECONDS


_wiki_lock = threading.Lock()   # ένα αίτημα Wikipedia τη φορά σε ΟΛΟ τον server
_wiki_last = 0.0


def _wiki_paced_search(lang_code: str, srsearch: str) -> Optional[Dict]:
    """_wiki_search με κοινό ρυθμό για όλα τα νήματα: ακόμη κι αν αναλύονται
    δύο εργασίες ταυτόχρονα, η Wikipedia δέχεται ένα αίτημα τη φορά, με παύση
    τουλάχιστον _wiki_delay() ανάμεσα."""
    global _wiki_last
    with _wiki_lock:
        wait = _wiki_last + _wiki_delay() - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            return _wiki_search(lang_code, srsearch)
        finally:
            _wiki_last = time.time()


# ---------------------------------------------------------------------------
# Κανονικοποίηση κειμένου
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[\w''-]+", re.UNICODE)


def _normalize_token(tok: str) -> str:
    """πεζά + αφαίρεση τόνων/διαλυτικών + ς→σ, ώστε η σύγκριση να μην
    επηρεάζεται από τόνους ή κεφαλαία."""
    tok = tok.lower().replace("ς", "σ")
    tok = unicodedata.normalize("NFD", tok)
    return "".join(c for c in tok if not unicodedata.combining(c))


def tokenize(text: str) -> Tuple[List[str], List[str]]:
    """Επιστρέφει (αρχικές λέξεις, κανονικοποιημένες λέξεις) — 1:1 θέσεις.
    Αόρατοι χαρακτήρες αφαιρούνται και ομοιόγλυφα άλλου αλφαβήτου
    «διορθώνονται», ώστε τα κόλπα παράκαμψης να μην κρύβουν την αντιγραφή."""
    orig = _TOKEN_RE.findall(strip_invisible(text))
    norm = [_normalize_token(fold_homoglyphs(t)) for t in orig]
    return orig, norm


# ---------------------------------------------------------------------------
# Winnowing fingerprints
# ---------------------------------------------------------------------------

def _hash_shingle(words: List[str]) -> int:
    h = hashlib.md5(" ".join(words).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def fingerprints(norm_words: List[str]) -> List[Tuple[int, int]]:
    """Winnowing: επιστρέφει [(hash, θέση_λέξης)] — το ελάχιστο hash κάθε
    παραθύρου W διαδοχικών shingles μεγέθους K."""
    n = len(norm_words)
    if n < K:
        return []
    hashes = [_hash_shingle(norm_words[i:i + K]) for i in range(n - K + 1)]
    if len(hashes) <= W:
        m = min(range(len(hashes)), key=lambda i: hashes[i])
        return [(hashes[m], m)]
    fps = []
    last = -1
    for start in range(len(hashes) - W + 1):
        window = range(start, start + W)
        m = min(window, key=lambda i: (hashes[i], i))
        if m != last:
            fps.append((hashes[m], m))
            last = m
    return fps


# ---------------------------------------------------------------------------
# Σύγκριση εργασιών μεταξύ τους (μαζικός έλεγχος)
# ---------------------------------------------------------------------------

def pairwise_similarity(docs: List[Tuple[str, str]], min_pct: float = 5.0,
                        max_pairs: int = 50) -> List[Dict]:
    """Ποιες εργασίες έχουν κοινά αποσπάσματα μεταξύ τους (≥ K+W-1 λέξεις).

    docs: [(όνομα, κείμενο)]. Για κάθε ζεύγος: ποσοστό λέξεων του Α που
    καλύπτεται από κοινά αποσπάσματα με το Β (και αντίστροφα) + ένα απόσπασμα.
    Επιστρέφει μόνο ζεύγη με max(ποσοστό) ≥ min_pct, ταξινομημένα."""
    prepared = []
    index: Dict[int, List[Tuple[int, int]]] = {}
    for i, (name, text) in enumerate(docs):
        orig, norm = tokenize(text or "")
        prepared.append((name, orig))
        for h, pos in fingerprints(norm):
            index.setdefault(h, []).append((i, pos))

    shared: Dict[Tuple[int, int], Tuple[set, set]] = {}
    for postings in index.values():
        if len(postings) < 2:
            continue
        for x in range(len(postings)):
            for y in range(x + 1, len(postings)):
                (a, pa), (b, pb) = postings[x], postings[y]
                if a == b:
                    continue
                if a > b:
                    (a, pa), (b, pb) = (b, pb), (a, pa)
                cov_a, cov_b = shared.setdefault((a, b), (set(), set()))
                cov_a.update(range(pa, pa + K))
                cov_b.update(range(pb, pb + K))

    pairs = []
    for (a, b), (cov_a, cov_b) in shared.items():
        name_a, words_a = prepared[a]
        name_b, words_b = prepared[b]
        cov_a = {p for p in cov_a if p < len(words_a)}
        cov_b = {p for p in cov_b if p < len(words_b)}
        if len(cov_a) < K + W - 1:
            continue                                 # ψίχουλα, όχι κοινό απόσπασμα
        pct_a = len(cov_a) / max(len(words_a), 1) * 100
        pct_b = len(cov_b) / max(len(words_b), 1) * 100
        if max(pct_a, pct_b) < min_pct:
            continue
        start = min(cov_a)
        pairs.append({
            "a": name_a, "b": name_b,
            "a_pct": round(pct_a, 1), "b_pct": round(pct_b, 1),
            "shared_words": len(cov_a),
            "excerpt": _excerpt(words_a, start, start + 40),
        })
    pairs.sort(key=lambda p: -max(p["a_pct"], p["b_pct"]))
    return pairs[:max_pairs]


# ---------------------------------------------------------------------------
# Εξαγωγή κειμένου από αρχεία corpus (αυτόνομη — χωρίς εξάρτηση από τον server)
# ---------------------------------------------------------------------------

def _extract_file_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == ".docx":
        from docx import Document
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.extend(c.text for c in row.cells)
        return "\n".join(parts)
    if ext == ".pdf":
        import pdfplumber
        pages = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)
    raise ValueError(f"Μη υποστηριζόμενος τύπος corpus: {ext}")


# ---------------------------------------------------------------------------
# Ευρετήριο corpus
# ---------------------------------------------------------------------------

class CorpusIndex:
    """Ευρετήριο fingerprints για τον φάκελο παλιών εργασιών.
    Κρατά cache στο corpus/.corpus_index.json — τα αρχεία εξάγονται/γίνονται
    index μία φορά και μετά μόνο όταν αλλάξουν (mtime+size)."""

    def __init__(self, corpus_dir):
        self.dir = Path(corpus_dir)
        self.files: Dict[str, Dict] = {}      # name -> {mtime, size, words, fps}
        self.global_map: Dict[int, List[Tuple[str, int]]] = {}
        self._signature = None

    # -- βοηθητικά --

    def _list_corpus_files(self) -> Dict[str, Tuple[float, int]]:
        out = {}
        if not self.dir.is_dir():
            return out
        for p in sorted(self.dir.iterdir()):
            if not p.is_file() or p.suffix.lower() not in CORPUS_EXTENSIONS:
                continue
            # κρυφά αρχεία και το README του φακέλου δεν είναι "εργασίες"
            if p.name.startswith(".") or p.name.upper().startswith("README"):
                continue
            st = p.stat()
            out[p.name] = (st.st_mtime, st.st_size)
        return out

    def refresh(self) -> None:
        """Φορτώνει/ενημερώνει το ευρετήριο μόνο αν άλλαξε κάτι στον φάκελο."""
        listing = self._list_corpus_files()
        signature = tuple(sorted(listing.items()))
        if signature == self._signature:
            return
        self._load_cache()

        changed = False
        # νέα/αλλαγμένα αρχεία
        for name, (mtime, size) in listing.items():
            entry = self.files.get(name)
            if entry and abs(entry["mtime"] - mtime) < 1 and entry["size"] == size:
                continue
            try:
                text = _extract_file_text(self.dir / name)
            except Exception:
                continue
            orig, norm = tokenize(text)
            fps = fingerprints(norm)
            self.files[name] = {
                "mtime": mtime, "size": size,
                "words": orig,
                "fps": [[h, p] for h, p in fps],
            }
            changed = True
        # διαγραμμένα αρχεία
        for name in list(self.files):
            if name not in listing:
                del self.files[name]
                changed = True

        if changed:
            self._save_cache()
        self._rebuild_global()
        self._signature = signature

    def _rebuild_global(self) -> None:
        self.global_map = {}
        for name, entry in self.files.items():
            for h, pos in entry["fps"]:
                self.global_map.setdefault(h, []).append((name, pos))

    def _cache_path(self) -> Path:
        return self.dir / CACHE_NAME

    def _load_cache(self) -> None:
        if self.files:
            return
        try:
            data = json.loads(self._cache_path().read_text(encoding="utf-8"))
            if data.get("version") == CACHE_VERSION:
                self.files = data["files"]
        except Exception:
            self.files = {}

    def _save_cache(self) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"version": CACHE_VERSION, "files": self.files},
                                 ensure_ascii=False)
            self._cache_path().write_text(payload, encoding="utf-8")
        except Exception:
            pass  # χωρίς cache απλώς θα ξαναγίνει index την επόμενη φορά

    @property
    def n_files(self) -> int:
        return len(self.files)

    # -- σύγκριση --

    def compare(self, text: str, max_sources: int = 8,
                max_passages_per_source: int = 5) -> Dict:
        """Συγκρίνει κείμενο με όλο το corpus.

        Επιστρέφει: {similarity (0-100, κάλυψη λέξεων), sources: [...],
        corpus_files, checked_words}."""
        self.refresh()

        orig, norm = tokenize(text)
        n_words = len(orig)
        result = {
            "similarity": 0.0,
            "sources": [],
            "corpus_files": self.n_files,
            "checked_words": n_words,
        }
        if n_words < K or not self.global_map:
            return result

        # Συλλογή κοινών fingerprints ανά αρχείο-πηγή
        per_file: Dict[str, List[Tuple[int, int]]] = {}
        for h, qpos in fingerprints(norm):
            for name, spos in self.global_map.get(h, ()):
                per_file.setdefault(name, []).append((qpos, spos))

        covered_total = set()
        sources = []
        for name, matches in per_file.items():
            matches.sort()
            # Ομαδοποίηση σε συνεχόμενα χωρία (gaps μέχρι K+W λέξεις)
            passages = []
            cur = [matches[0]]
            for q, s in matches[1:]:
                pq, ps = cur[-1]
                if q - pq <= K + W and abs((s - ps) - (q - pq)) <= K:
                    cur.append((q, s))
                else:
                    passages.append(cur)
                    cur = [(q, s)]
            passages.append(cur)

            # Κάλυψη λέξεων της εξεταζόμενης εργασίας από αυτή την πηγή
            covered = set()
            passage_infos = []
            for run in passages:
                q_start = run[0][0]
                q_end = run[-1][0] + K          # exclusive
                s_start = run[0][1]
                s_end = run[-1][1] + K
                span = range(q_start, min(q_end, n_words))
                if len(span) < 10:              # αγνόησε ψίχουλα < 10 λέξεων
                    continue
                covered.update(span)
                src_words = self.files[name]["words"]
                passage_infos.append({
                    "words": len(span),
                    "doc_excerpt": _excerpt(orig, q_start, q_end),
                    "source_excerpt": _excerpt(src_words, s_start, s_end),
                    "doc_position": f"λέξεις {q_start + 1}–{min(q_end, n_words)}",
                    "doc_start": q_start + 1,
                    "doc_end": min(q_end, n_words),
                })
            if not covered:
                continue

            similarity = len(covered) / n_words * 100
            covered_total.update(covered)
            passage_infos.sort(key=lambda p: -p["words"])
            sources.append({
                "file": name,
                "similarity": round(similarity, 1),
                "matched_words": len(covered),
                "passages": passage_infos[:max_passages_per_source],
                "total_passages": len(passage_infos),
                "likely_same_document": similarity >= 90,
            })

        sources.sort(key=lambda s: -s["similarity"])
        result["sources"] = sources[:max_sources]
        # Συνολική ομοιότητα: κάλυψη από πηγές που ΔΕΝ είναι το ίδιο το έγγραφο
        non_self = set()
        for src in sources:
            if not src["likely_same_document"]:
                for p_ in per_file[src["file"]]:
                    non_self.update(range(p_[0], min(p_[0] + K, n_words)))
        result["similarity"] = round(len(non_self) / n_words * 100, 1)
        result["same_document_detected"] = any(s["likely_same_document"] for s in sources)
        return result


def _excerpt(words: List[str], start: int, end: int, max_words: int = 40) -> str:
    chunk = words[max(0, start):end]
    if len(chunk) > max_words:
        half = max_words // 2
        return " ".join(chunk[:half]) + " […] " + " ".join(chunk[-half:])
    return " ".join(chunk)


# ---------------------------------------------------------------------------
# Έλεγχος Wikipedia (EN + EL)
# ---------------------------------------------------------------------------

def _wiki_api(lang: str, params: Dict, timeout: float = 5.0) -> Dict:
    if lang not in ("el", "en"):
        raise ValueError("unsupported Wikipedia language")
    params = dict(params, format="json")
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return http_pool.get_json(url, headers={"User-Agent": polite_user_agent()}, timeout=timeout)


def _select_check_phrases(text: str, limit: int) -> List[Tuple[str, str]]:
    """Διαλέγει χαρακτηριστικές προτάσεις απλωμένες σε όλο το κείμενο και
    επιστρέφει [(φράση 10 λέξεων για αναζήτηση, ολόκληρη πρόταση)]."""
    from detector_engine import detect_language, split_sentences

    language = detect_language(text)
    sentences = split_sentences(text, language)
    candidates = []
    for s in sentences:
        words = _TOKEN_RE.findall(s)
        if not 12 <= len(words) <= 60:
            continue
        digits = sum(1 for w in words if any(c.isdigit() for c in w))
        if digits > len(words) * 0.15:      # πίνακες/αριθμητικά — άχρηστα για phrase search
            continue
        candidates.append((words, s))
    if not candidates:
        return []
    # Ομοιόμορφη δειγματοληψία σε ΟΛΟ το έγγραφο (πρώτη έως τελευταία πρόταση)
    if len(candidates) <= limit:
        picked = candidates
    else:
        idxs = sorted({round(i * (len(candidates) - 1) / (limit - 1))
                       for i in range(limit)})
        picked = [candidates[i] for i in idxs]
    phrases = []
    for words, s in picked:
        mid = len(words) // 2
        span = words[max(0, mid - 5): mid + 5]     # 10 λέξεις από τη μέση
        phrases.append((" ".join(span), s))
    return phrases


class _RateLimited(Exception):
    pass


def _wiki_search(lang_code: str, srsearch: str) -> Optional[Dict]:
    """Ένα αίτημα αναζήτησης με χειρισμό 429 (Retry-After/backoff).
    Επιστρέφει το JSON, ή σηκώνει _RateLimited / άλλο σφάλμα δικτύου."""
    for attempt in range(3):
        try:
            return _wiki_api(lang_code, {
                "action": "query", "list": "search",
                "srsearch": srsearch, "srlimit": 5,
            })
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _wiki_slow_down()
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    wait = min(float(retry_after), 30.0) if retry_after else 8.0 * (attempt + 1)
                except ValueError:
                    wait = 8.0 * (attempt + 1)
                if attempt < 2:
                    time.sleep(wait)
                    continue
                raise _RateLimited()
            raise
    raise _RateLimited()


def _make_batches(phrases: List[Tuple[str, str]], max_len: int = 280) -> List[List[Tuple[str, str]]]:
    """Ομαδοποιεί φράσεις σε OR-queries ώστε κάθε srsearch < max_len χαρακτήρες.
    Λιγότερα αιτήματα = δεν χτυπάμε το rate limit της Wikipedia."""
    batches: List[List[Tuple[str, str]]] = []
    cur: List[Tuple[str, str]] = []
    cur_len = 0
    for phrase, sentence in phrases:
        extra = len(phrase) + 7   # '"..."' + ' OR '
        if cur and cur_len + extra > max_len:
            batches.append(cur)
            cur, cur_len = [], 0
        cur.append((phrase, sentence))
        cur_len += extra
    if cur:
        batches.append(cur)
    return batches


def _wiki_compact(data: Dict) -> Dict:
    """Κρατά μόνο ό,τι χρειαζόμαστε (για την cache): πλήθος + πρώτος τίτλος."""
    q = data.get("query") if isinstance(data, dict) else None
    q = q if isinstance(q, dict) else {}
    info = q.get("searchinfo") if isinstance(q.get("searchinfo"), dict) else {}
    total = info.get("totalhits", 0)
    results = q.get("search") if isinstance(q.get("search"), list) else []
    found = [{"title": str(r.get("title", ""))} for r in results[:1] if isinstance(r, dict)]
    return {"query": {"searchinfo": {"totalhits": total if isinstance(total, int) else 0},
                      "search": found}}


def check_wikipedia(text: str, max_sentences: int = 12,
                    cache: Optional[WebCache] = None) -> Dict:
    """Ψάχνει δείγμα προτάσεων του κειμένου αυτούσιες στη Wikipedia (EN+EL).

    Στρατηγική δύο σταδίων για σεβασμό του rate limit:
      1. Ομαδικά OR-queries (3-4 φράσεις ανά αίτημα).
      2. Μόνο αν μια ομάδα έχει εύρημα, ατομικά queries για απόδοση
         φράσης → άρθρου.

    Cache: τα ευρήματα αποθηκεύονται αμέσως· τα «0 αποτελέσματα» ΜΟΝΟ αν ο
    έλεγχος canary της ίδιας εκτέλεσης επιβεβαιώσει ότι η Wikipedia απαντά
    κανονικά (αλλιώς θα κρατούσαμε για μέρες ψεύτικα «καθαρά» αποτελέσματα).

    Επιστρέφει {status: 'ok'|'partial'|'offline'|'no_candidates',
                checked, total, hits: [...]}."""
    from detector_engine import detect_language

    language = detect_language(text)
    lang_code = "el" if language == "greek" else "en"

    phrases = _select_check_phrases(text, max_sentences)
    if not phrases:
        return {"status": "no_candidates", "checked": 0, "total": 0, "hits": []}

    cache = cache if cache is not None else default_cache()
    namespace = f"wiki:{lang_code}"
    pending_zero: List[str] = []     # «0 αποτελέσματα» — γράφονται μόνο μετά το canary
    fresh = {"requests": 0}

    def search(query: str) -> Dict:
        cached = cache.get(namespace, query)
        if isinstance(cached, dict):
            return _wiki_compact(cached)     # επανέλεγχος δομής ό,τι κι αν διαβάστηκε
        fresh["requests"] += 1
        data = _wiki_compact(_wiki_paced_search(lang_code, query))
        if data["query"]["searchinfo"]["totalhits"] > 0:
            cache.put(namespace, query, data)
        else:
            pending_zero.append(query)
        return data

    hits = []
    checked = 0
    errors = 0
    rate_limited = False

    batches = _make_batches(phrases)
    for bi, batch in enumerate(batches):
        query = " OR ".join(f'"{p}"' for p, _ in batch)
        try:
            data = search(query)
        except _RateLimited:
            rate_limited = True
            break
        except Exception:
            errors += 1
            if errors >= 3:
                return {"status": "offline", "checked": checked,
                        "total": len(phrases), "hits": hits}
            continue

        total_hits = data.get("query", {}).get("searchinfo", {}).get("totalhits", 0)
        if total_hits == 0:
            checked += len(batch)          # όλη η ομάδα καθαρή με 1 αίτημα
        else:
            # Κάποια φράση της ομάδας υπάρχει — ατομική απόδοση
            for phrase, sentence in batch:
                try:
                    d1 = search(f'"{phrase}"')
                except _RateLimited:
                    rate_limited = True
                    break
                except Exception:
                    errors += 1
                    continue
                checked += 1
                found = d1.get("query", {}).get("search", [])
                if d1.get("query", {}).get("searchinfo", {}).get("totalhits", 0) > 0 and found:
                    title = found[0]["title"]
                    hits.append({
                        "sentence": sentence if len(sentence) <= 300 else sentence[:297] + "…",
                        "phrase": phrase,
                        "article": title,
                        "url": f"https://{lang_code}.wikipedia.org/wiki/" +
                               urllib.parse.quote(title.replace(" ", "_")),
                    })
            if rate_limited:
                break

    if rate_limited and checked < len(phrases):
        status = "partial"
    elif checked == 0 and errors:
        status = "offline"               # κανένα αίτημα δεν πέτυχε — όχι «καθαρό»
    elif not hits and checked > 0 and not pending_zero:
        status = "ok"                    # όλα τα «καθαρά» ήρθαν από επιβεβαιωμένη cache
    elif not hits and checked > 0:
        # Canary: μετά από ριπές η Wikipedia επιστρέφει σιωπηλά 0 αποτελέσματα
        # χωρίς σφάλμα. Ελέγχουμε με ΣΠΑΝΙΑ πολυλεκτική φράση που σίγουρα
        # υπάρχει (ίδιο προφίλ κόστους με τα κανονικά queries) — αν γυρίσει 0,
        # τα «καθαρά» αποτελέσματα είναι αναξιόπιστα.
        canary = ("αναφέρεται στον διεπιστημονικό τομέα με πυρήνα την πληροφορική"
                  if lang_code == "el" else
                  "Turing was highly influential in the development of theoretical computer science")
        try:
            d_c = _wiki_paced_search(lang_code, f'"{canary}"')
            canary_hits = d_c.get("query", {}).get("searchinfo", {}).get("totalhits", 0)
            status = "ok" if canary_hits > 0 else "degraded"
        except Exception:
            status = "degraded"
        if status == "degraded":
            _wiki_slow_down()            # πιθανό σιωπηλό throttling → πιο αργά από εδώ και πέρα
        if status == "ok":
            for query in pending_zero:
                cache.put(namespace, query, {"query": {"searchinfo": {"totalhits": 0},
                                                       "search": []}}, negative=True)
    else:
        status = "ok"
    return {"status": status, "checked": checked, "total": len(phrases), "hits": hits,
            "requests": fresh["requests"]}


# ---------------------------------------------------------------------------
# Έλεγχος ακαδημαϊκής βιβλιογραφίας — OpenAlex (τύπου Google Scholar)
# ---------------------------------------------------------------------------
# Το OpenAlex (openalex.org) είναι η μεγαλύτερη ανοιχτή ακαδημαϊκή βάση
# (250M+ δημοσιεύσεις — ο διάδοχος του Microsoft Academic). Δωρεάν API χωρίς
# κλειδί. Το `search` ψάχνει τίτλους + abstracts + full-text (όπου υπάρχει),
# με exact-phrase όταν η φράση είναι σε εισαγωγικά. Ευρετηριάζει και ελληνικά
# ιδρυματικά αποθετήρια (πτυχιακές/διπλωματικές).

OPENALEX_DELAY = 0.25   # 10 req/s επιτρεπτά στο polite pool — είμαστε συντηρητικοί


_OPENALEX_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def openalex_api_key(config_path: Optional[str] = None) -> Optional[str]:
    """Προαιρετικό δωρεάν κλειδί OpenAlex (από 2/2026 χωρίς κλειδί το ημερήσιο
    όριο είναι πολύ μικρό). Από OPENALEX_API_KEY ή search_config.json
    {"openalex_api_key": "..."} — μένει μόνο τοπικά, όπως τα άλλα κλειδιά."""
    key = (os.environ.get("OPENALEX_API_KEY") or "").strip()
    if not key:
        path = Path(config_path) if config_path else Path(__file__).parent / "search_config.json"
        try:
            key = str(json.loads(path.read_text(encoding="utf-8")).get("openalex_api_key") or "").strip()
        except Exception:
            key = ""
    return key if _OPENALEX_KEY_RE.match(key) else None


def validate_openalex_key(api_key: str) -> Tuple[bool, Dict[str, str]]:
    """Ζωντανή δοκιμή του κλειδιού με ένα φθηνό αίτημα (1 αποτέλεσμα).
    Το κλειδί δεν εμφανίζεται ποτέ σε μήνυμα ή log."""
    key = (api_key or "").strip()
    if not _OPENALEX_KEY_RE.match(key):
        return False, _msg("openalex_bad_format")
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(
        dict(openalex_params({"per-page": 1, "select": "id"}), api_key=key))
    try:
        http_pool.get_json(url, headers={"User-Agent": polite_user_agent()}, timeout=10)
        return True, _msg("openalex_ok")
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            return False, _msg("openalex_bad_key")
        if e.code == 429:                 # αυθεντικοποιήθηκε, απλώς όριο ρυθμού
            return True, _msg("openalex_ok")
        return False, _msg("openalex_unreachable")
    except Exception:
        return False, _msg("openalex_unreachable")


def save_openalex_key(api_key: str, config_path: Optional[str] = None) -> None:
    _update_search_config({"openalex_api_key": api_key.strip()}, config_path)


def openalex_params(params: Dict) -> Dict:
    """Προσθέτει mailto (polite pool, μόνο αν έχει δοθεί email) και, αν υπάρχει, το api_key."""
    params = dict(params)
    email = contact_email()
    if email:
        params["mailto"] = email
    key = openalex_api_key()
    if key:
        params["api_key"] = key
    return params


def _openalex_api(params: Dict, timeout: float = 10.0) -> Dict:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(openalex_params(params))
    return http_pool.get_json(url, headers={
        "User-Agent": polite_user_agent()}, timeout=timeout)


def _openalex_compact(data: Dict) -> Dict:
    """Κρατά μόνο ό,τι χρειάζεται (για την cache): πλήθος + πρώτο αποτέλεσμα."""
    data = data if isinstance(data, dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    count = meta.get("count", 0)
    results = data.get("results") if isinstance(data.get("results"), list) else []

    def text(v):
        return v if isinstance(v, str) else None
    out = []
    for w in results[:1]:
        if not isinstance(w, dict):
            continue
        loc = w.get("primary_location")
        year = w.get("publication_year")
        out.append({
            "title": text(w.get("title")), "publication_year": year if isinstance(year, int) else None,
            "doi": text(w.get("doi")), "id": text(w.get("id")),
            "primary_location": {"landing_page_url": text(loc.get("landing_page_url"))}
            if isinstance(loc, dict) else None,
        })
    return {"meta": {"count": count if isinstance(count, int) else 0}, "results": out}


def check_scholar(text: str, max_sentences: int = 15,
                  cache: Optional[WebCache] = None) -> Dict:
    """Ψάχνει δείγμα προτάσεων αυτούσιες σε ακαδημαϊκές δημοσιεύσεις (OpenAlex).

    Κάθε φράση παίρνει 1 retry πριν μετρηθεί ως αποτυχία — τα σποραδικά
    timeouts/network blips στο OpenAlex είναι συχνά και δεν πρέπει να κόβουν
    όλο το υπόλοιπο δείγμα. Μόνο 3 ΣΥΝΕΧΟΜΕΝΕΣ αποτυχίες (μετά το retry τους)
    θεωρούνται πραγματική διακοπή σύνδεσης και σταματούν νωρίτερα τον έλεγχο·
    μεμονωμένες/σκόρπιες αποτυχίες απλώς παραλείπονται και ο έλεγχος συνεχίζει.

    Επιστρέφει {status: 'ok'|'partial'|'offline'|'no_candidates',
                checked, total, hits: [{sentence, phrase, title, year, url}]}."""
    phrases = _select_check_phrases(text, max_sentences)
    if not phrases:
        return {"status": "no_candidates", "checked": 0, "total": 0, "hits": []}

    cache = cache if cache is not None else default_cache()
    hits = []
    checked = 0
    consecutive_fails = 0
    pause = False
    for i, (phrase, sentence) in enumerate(phrases):
        data = cache.get("openalex_search", phrase)
        if not isinstance(data, dict):
            data = None
        else:
            data = _openalex_compact(data)   # επανέλεγχος δομής ό,τι κι αν διαβάστηκε
            consecutive_fails = 0
        for attempt in ((1, 2) if data is None else ()):
            if pause:
                time.sleep(OPENALEX_DELAY)
            pause = True
            try:
                data = _openalex_api({
                    "search": f'"{phrase}"',
                    "per-page": 3,
                    "select": "title,publication_year,doi,id,primary_location",
                })
                data = _openalex_compact(data)
                cache.put("openalex_search", phrase, data, negative=not data["meta"]["count"])
                break
            except Exception:
                data = None
                if attempt == 1:
                    time.sleep(1.5)
        if data is None:
            consecutive_fails += 1
            if consecutive_fails >= 3:
                status = "offline" if checked == 0 else "partial"
                return {"status": status, "checked": checked,
                        "total": len(phrases), "hits": hits}
            continue

        consecutive_fails = 0
        checked += 1
        results = data.get("results", [])
        if data.get("meta", {}).get("count", 0) > 0 and results:
            w = results[0]
            url = w.get("doi") or ""
            if not url:
                loc = w.get("primary_location") or {}
                url = (loc.get("landing_page_url") or "") if isinstance(loc, dict) else ""
            if not url:
                url = w.get("id", "")
            total_matches = data["meta"]["count"]
            hits.append({
                "sentence": sentence if len(sentence) <= 300 else sentence[:297] + "…",
                "phrase": phrase,
                "title": w.get("title") or "(χωρίς τίτλο)",
                "year": w.get("publication_year"),
                "url": url,
                "total_matches": total_matches,
                # Φράση που εμφανίζεται σε δεκάδες δημοσιεύσεις = κοινότυπη
                # ακαδημαϊκή έκφραση, όχι ένδειξη αντιγραφής συγκεκριμένης πηγής
                "generic": total_matches > 50,
            })

    return {"status": "ok", "checked": checked, "total": len(phrases), "hits": hits}


# ---------------------------------------------------------------------------
# Προαιρετικός έλεγχος Google (Custom Search API — θέλει δωρεάν κλειδί)
# ---------------------------------------------------------------------------
# Δίνει πρόσβαση στο index της Google (άρα και στα ελληνικά ακαδημαϊκά
# αποθετήρια: Πέργαμος, ΙΚΕΕ, Νημερτής κ.ά.). Δωρεάν όριο: 100 αναζητήσεις/μέρα.
# Ρύθμιση: βάλε στο search_config.json (δίπλα στον server):
#   {"google_api_key": "...", "google_cse_id": "..."}
# Κλειδί API: https://developers.google.com/custom-search/v1/overview
# CSE (ολόκληρο το web): https://programmablesearchengine.google.com

GOOGLE_MAX_PHRASES = 8   # φειδώ στο ημερήσιο όριο των 100 αναζητήσεων


def _load_google_config(config_path: Optional[str] = None) -> Optional[Dict]:
    key = os.environ.get("GOOGLE_API_KEY")
    cse = os.environ.get("GOOGLE_CSE_ID")
    if key and cse:
        return {"google_api_key": key, "google_cse_id": cse}
    path = Path(config_path) if config_path else Path(__file__).parent / "search_config.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg.get("google_api_key") and cfg.get("google_cse_id"):
            return cfg
    except Exception:
        pass
    return None


# Μηνύματα επαλήθευσης κλειδιών σε όλες τις γλώσσες του UI — ο server
# διαλέγει τη γλώσσα της σελίδας (X-UI-Lang).
VALIDATION_MESSAGES: Dict[str, Dict[str, str]] = {
    "google_ok": {
        "el": "Τα κλειδιά λειτουργούν — ο έλεγχος Google είναι ενεργός.",
        "en": "The keys work — the Google check is active.",
        "de": "Die Schlüssel funktionieren — die Google-Prüfung ist aktiv.",
        "fr": "Les clés fonctionnent — le contrôle Google est actif.",
        "pt": "As chaves funcionam — a verificação Google está ativa."},
    "google_bad_key": {
        "el": "Το API key δεν είναι έγκυρο. Έλεγξε ότι το αντέγραψες σωστά.",
        "en": "The API key is not valid. Check that you copied it correctly.",
        "de": "Der API-Schlüssel ist ungültig. Prüfe, ob du ihn richtig kopiert hast.",
        "fr": "La clé API n'est pas valide. Vérifiez que vous l'avez copiée correctement.",
        "pt": "A chave da API não é válida. Verifique se a copiou corretamente."},
    "google_bad_cx": {
        "el": "Το Search Engine ID (cx) δεν είναι έγκυρο. Έλεγξέ το στο programmablesearchengine.google.com.",
        "en": "The Search Engine ID (cx) is not valid. Check it at programmablesearchengine.google.com.",
        "de": "Die Search Engine ID (cx) ist ungültig. Prüfe sie unter programmablesearchengine.google.com.",
        "fr": "Le Search Engine ID (cx) n'est pas valide. Vérifiez-le sur programmablesearchengine.google.com.",
        "pt": "O Search Engine ID (cx) não é válido. Verifique-o em programmablesearchengine.google.com."},
    "google_api_disabled": {
        "el": "Το Custom Search API δεν είναι ενεργοποιημένο στο project σου. Ενεργοποίησέ το: {url}",
        "en": "The Custom Search API is not enabled in your project. Enable it: {url}",
        "de": "Die Custom Search API ist in deinem Projekt nicht aktiviert. Aktiviere sie: {url}",
        "fr": "L'API Custom Search n'est pas activée dans votre projet. Activez-la : {url}",
        "pt": "A Custom Search API não está ativada no seu projeto. Ative-a: {url}"},
    "google_refused": {
        "el": "Η Google αρνήθηκε το αίτημα (HTTP {code}): {detail}",
        "en": "Google refused the request (HTTP {code}): {detail}",
        "de": "Google hat die Anfrage abgelehnt (HTTP {code}): {detail}",
        "fr": "Google a refusé la requête (HTTP {code}) : {detail}",
        "pt": "A Google recusou o pedido (HTTP {code}): {detail}"},
    "google_error": {
        "el": "Σφάλμα Google (HTTP {code}): {detail}",
        "en": "Google error (HTTP {code}): {detail}",
        "de": "Google-Fehler (HTTP {code}): {detail}",
        "fr": "Erreur Google (HTTP {code}) : {detail}",
        "pt": "Erro Google (HTTP {code}): {detail}"},
    "google_unreachable": {
        "el": "Δεν ήταν δυνατή η σύνδεση με τη Google: {detail}",
        "en": "Could not connect to Google: {detail}",
        "de": "Keine Verbindung zu Google möglich: {detail}",
        "fr": "Impossible de se connecter à Google : {detail}",
        "pt": "Não foi possível ligar à Google: {detail}"},
    "brave_ok": {
        "el": "Το κλειδί λειτουργεί — ο έλεγχος Brave είναι ενεργός.",
        "en": "The key works — the Brave check is active.",
        "de": "Der Schlüssel funktioniert — die Brave-Prüfung ist aktiv.",
        "fr": "La clé fonctionne — le contrôle Brave est actif.",
        "pt": "A chave funciona — a verificação Brave está ativa."},
    "brave_bad_key": {
        "el": "Το Brave API key δεν είναι έγκυρο. Έλεγξε ότι το αντέγραψες σωστά από το api-dashboard.search.brave.com → API Keys.",
        "en": "The Brave API key is not valid. Check that you copied it correctly from api-dashboard.search.brave.com → API Keys.",
        "de": "Der Brave-API-Schlüssel ist ungültig. Prüfe, ob du ihn richtig von api-dashboard.search.brave.com → API Keys kopiert hast.",
        "fr": "La clé API Brave n'est pas valide. Vérifiez que vous l'avez copiée correctement depuis api-dashboard.search.brave.com → API Keys.",
        "pt": "A chave da API Brave não é válida. Verifique se a copiou corretamente de api-dashboard.search.brave.com → API Keys."},
    "brave_rate_limited_ok": {
        "el": "Το κλειδί λειτουργεί (προσωρινό όριο ρυθμού — ο έλεγχος Brave είναι ενεργός).",
        "en": "The key works (temporary rate limit — the Brave check is active).",
        "de": "Der Schlüssel funktioniert (vorübergehendes Ratenlimit — die Brave-Prüfung ist aktiv).",
        "fr": "La clé fonctionne (limite de débit temporaire — le contrôle Brave est actif).",
        "pt": "A chave funciona (limite de pedidos temporário — a verificação Brave está ativa)."},
    "brave_error": {
        "el": "Σφάλμα Brave (HTTP {code}): {detail}",
        "en": "Brave error (HTTP {code}): {detail}",
        "de": "Brave-Fehler (HTTP {code}): {detail}",
        "fr": "Erreur Brave (HTTP {code}) : {detail}",
        "pt": "Erro Brave (HTTP {code}): {detail}"},
    "openalex_ok": {
        "el": "Το κλειδί OpenAlex λειτουργεί — αποθηκεύτηκε.",
        "en": "The OpenAlex key works — saved.",
        "de": "Der OpenAlex-Schlüssel funktioniert — gespeichert.",
        "fr": "La clé OpenAlex fonctionne — enregistrée.",
        "pt": "A chave OpenAlex funciona — guardada."},
    "openalex_bad_format": {
        "el": "Μη έγκυρη μορφή κλειδιού (μόνο γράμματα, αριθμοί, - και _).",
        "en": "Invalid key format (letters, digits, - and _ only).",
        "de": "Ungültiges Schlüsselformat (nur Buchstaben, Ziffern, - und _).",
        "fr": "Format de clé invalide (lettres, chiffres, - et _ uniquement).",
        "pt": "Formato de chave inválido (apenas letras, números, - e _)."},
    "openalex_bad_key": {
        "el": "Το OpenAlex δεν δέχτηκε το κλειδί. Έλεγξε ότι το αντέγραψες σωστά.",
        "en": "OpenAlex did not accept the key. Check that you copied it correctly.",
        "de": "OpenAlex hat den Schlüssel nicht akzeptiert. Prüfe, ob du ihn richtig kopiert hast.",
        "fr": "OpenAlex n'a pas accepté la clé. Vérifiez que vous l'avez copiée correctement.",
        "pt": "O OpenAlex não aceitou a chave. Verifique se a copiou corretamente."},
    "openalex_unreachable": {
        "el": "Δεν ήταν δυνατή η σύνδεση με το OpenAlex — το κλειδί δεν αποθηκεύτηκε.",
        "en": "Could not connect to OpenAlex — the key was not saved.",
        "de": "Keine Verbindung zu OpenAlex — der Schlüssel wurde nicht gespeichert.",
        "fr": "Impossible de se connecter à OpenAlex — la clé n'a pas été enregistrée.",
        "pt": "Não foi possível ligar ao OpenAlex — a chave não foi guardada."},
    "brave_unreachable": {
        "el": "Δεν ήταν δυνατή η σύνδεση με το Brave: {detail}",
        "en": "Could not connect to Brave: {detail}",
        "de": "Keine Verbindung zu Brave möglich: {detail}",
        "fr": "Impossible de se connecter à Brave : {detail}",
        "pt": "Não foi possível ligar ao Brave: {detail}"},
    "unknown": {"el": "άγνωστο", "en": "unknown", "de": "unbekannt", "fr": "inconnu",
                "pt": "desconhecido"},
    "quota_or_permissions": {
        "el": "πιθανό όριο/δικαιώματα", "en": "possible quota/permissions",
        "de": "mögliches Limit/Berechtigungen", "fr": "quota/permissions probables",
        "pt": "possível limite/permissões"},
}


def _msg(key: str, detail_key: str = "", **params) -> Dict[str, str]:
    """Μήνυμα σε όλες τις γλώσσες. detail_key: λέξη-εναλλακτική όταν η
    απάντηση της υπηρεσίας δεν έδωσε λεπτομέρεια (μεταφράζεται κι αυτή)."""
    out = {}
    for lang, tpl in VALIDATION_MESSAGES[key].items():
        p = dict(params)
        if detail_key and not p.get("detail"):
            p["detail"] = VALIDATION_MESSAGES[detail_key].get(lang, "")
        out[lang] = tpl.format(**p)
    return out


def validate_google_config(api_key: str, cse_id: str) -> Tuple[bool, Dict[str, str]]:
    """Δοκιμάζει τα κλειδιά με ένα ζωντανό αίτημα. Επιστρέφει (ok, μήνυμα {el, en})."""
    params = urllib.parse.urlencode({
        "key": api_key, "cx": cse_id, "q": "test", "num": 1,
    })
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/customsearch/v1?" + params,
            headers={"User-Agent": polite_user_agent()})
        with urllib.request.urlopen(req, timeout=10) as r:
            json.loads(r.read())
        return True, _msg("google_ok")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        if e.code == 400 and "API key not valid" in detail:
            return False, _msg("google_bad_key")
        if e.code == 400 and "invalid argument" in detail.lower():
            return False, _msg("google_bad_cx")
        if e.code == 403 and "not been used" in detail:
            return False, _msg("google_api_disabled",
                               url="https://console.cloud.google.com/apis/library/customsearch.googleapis.com")
        if e.code in (403, 429):
            return False, _msg("google_refused", "quota_or_permissions",
                               code=e.code, detail=detail)
        return False, _msg("google_error", "unknown", code=e.code, detail=detail)
    except Exception as e:
        return False, _msg("google_unreachable", detail=e)


def _update_search_config(updates: Dict, config_path: Optional[str] = None) -> None:
    """Ενημερώνει το search_config.json χωρίς να χαθούν τα υπόλοιπα κλειδιά."""
    path = Path(config_path) if config_path else Path(__file__).parent / "search_config.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}
    cfg.update(updates)
    # Μυστικά: αναγνώσιμο μόνο από τον χρήστη (0600), ατομική αντικατάσταση
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(cfg, ensure_ascii=False, indent=2))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def save_google_config(api_key: str, cse_id: str,
                       config_path: Optional[str] = None) -> None:
    _update_search_config({
        "google_api_key": api_key.strip(),
        "google_cse_id": cse_id.strip(),
    }, config_path)


def check_google(text: str, max_sentences: int = GOOGLE_MAX_PHRASES,
                 config_path: Optional[str] = None) -> Dict:
    """Ψάχνει δείγμα προτάσεων αυτούσιες στο Google (Custom Search API).

    Επιστρέφει {status: 'ok'|'partial'|'quota'|'offline'|'not_configured'|
                'no_candidates', checked, total, hits}."""
    cfg = _load_google_config(config_path)
    if not cfg:
        return {"status": "not_configured", "checked": 0, "total": 0, "hits": []}

    phrases = _select_check_phrases(text, max_sentences)
    if not phrases:
        return {"status": "no_candidates", "checked": 0, "total": 0, "hits": []}

    hits = []
    checked = 0
    errors = 0
    for i, (phrase, sentence) in enumerate(phrases):
        params = urllib.parse.urlencode({
            "key": cfg["google_api_key"], "cx": cfg["google_cse_id"],
            "q": f'"{phrase}"', "num": 3,
        })
        try:
            req = urllib.request.Request(
                "https://www.googleapis.com/customsearch/v1?" + params,
                headers={"User-Agent": polite_user_agent()})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):   # εξαντλήθηκε το ημερήσιο όριο
                return {"status": "quota", "checked": checked,
                        "total": len(phrases), "hits": hits}
            errors += 1
            if errors >= 3:
                return {"status": "offline" if checked == 0 else "partial",
                        "checked": checked, "total": len(phrases), "hits": hits}
            continue
        except Exception:
            errors += 1
            if errors >= 3:
                return {"status": "offline" if checked == 0 else "partial",
                        "checked": checked, "total": len(phrases), "hits": hits}
            continue

        checked += 1
        items = data.get("items", [])
        total = int(data.get("searchInformation", {}).get("totalResults", "0"))
        if total > 0 and items:
            it = items[0]
            hits.append({
                "sentence": sentence if len(sentence) <= 300 else sentence[:297] + "…",
                "phrase": phrase,
                "title": it.get("title", ""),
                "url": it.get("link", ""),
                "total_matches": total,
            })
        if i < len(phrases) - 1:
            time.sleep(0.3)

    return {"status": "ok", "checked": checked, "total": len(phrases), "hits": hits}


# ---------------------------------------------------------------------------
# Έλεγχος Brave Search (θέλει δωρεάν κλειδί — Ο ΣΥΝΙΣΤΩΜΕΝΟΣ έλεγχος web)
# ---------------------------------------------------------------------------
# Η Google έκλεισε το Custom Search JSON API για νέους πελάτες (PERMISSION_DENIED
# ακόμη κι αν φαίνεται Enabled στο Cloud Console). Το Brave Search API έχει δικό
# του ανεξάρτητο index όλου του web (άρα και τα ελληνικά ακαδημαϊκά αποθετήρια)
# και δωρεάν πλάνο 2.000 αναζητήσεων/μήνα με όριο 1 αίτημα/δευτερόλεπτο.
# Ρύθμιση: βάλε στο search_config.json:  {"brave_api_key": "..."}
# Κλειδί: https://api-dashboard.search.brave.com/register → Free plan → API Keys

BRAVE_MAX_PHRASES = 8   # φειδώ στο μηνιαίο όριο των 2.000 αναζητήσεων
BRAVE_DELAY = 1.1       # δωρεάν πλάνο: μέγιστο 1 αίτημα/δευτερόλεπτο
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _load_brave_config(config_path: Optional[str] = None) -> Optional[str]:
    key = os.environ.get("BRAVE_API_KEY")
    if key:
        return key
    path = Path(config_path) if config_path else Path(__file__).parent / "search_config.json"
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        if cfg.get("brave_api_key"):
            return str(cfg["brave_api_key"]).strip()
    except Exception:
        pass
    return None


def _brave_api(api_key: str, query: str, count: int = 3, timeout: float = 10.0) -> Dict:
    params = urllib.parse.urlencode({"q": query, "count": count})
    req = urllib.request.Request(
        BRAVE_ENDPOINT + "?" + params,
        headers={"Accept": "application/json",
                 "X-Subscription-Token": api_key,
                 "User-Agent": polite_user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def validate_brave_config(api_key: str) -> Tuple[bool, Dict[str, str]]:
    """Δοκιμάζει το κλειδί με ένα ζωντανό αίτημα. Επιστρέφει (ok, μήνυμα {el, en})."""
    try:
        _brave_api(api_key, "test", count=1)
        return True, _msg("brave_ok")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("error", {}).get("detail", "")
        except Exception:
            detail = ""
        if e.code in (401, 403, 422):   # SUBSCRIPTION_TOKEN_INVALID → 422
            return False, _msg("brave_bad_key")
        if e.code == 429:
            # Αυθεντικοποιήθηκε αλλά έπεσε σε όριο ρυθμού — το κλειδί δουλεύει.
            return True, _msg("brave_rate_limited_ok")
        return False, _msg("brave_error", "unknown", code=e.code, detail=detail)
    except Exception as e:
        return False, _msg("brave_unreachable", detail=e)


def save_brave_config(api_key: str, config_path: Optional[str] = None) -> None:
    _update_search_config({"brave_api_key": api_key.strip()}, config_path)


def _brave_pick_result(phrase: str, results: List[Dict]) -> Optional[Dict]:
    """Διαλέγει αποτέλεσμα που όντως περιέχει τη φράση (τα quotes του Brave
    είναι λιγότερο αυστηρά από της Google) — αλλιώς δέχεται το πρώτο μόνο αν
    το snippet περιέχει τουλάχιστον το 60% των λέξεων της φράσης."""
    norm_phrase = " ".join(tokenize(phrase)[1])
    for it in results:
        blob = re.sub(r"<[^>]+>", " ", f"{it.get('title', '')} {it.get('description', '')}")
        if norm_phrase and norm_phrase in " ".join(tokenize(blob)[1]):
            return it
    if results:
        toks = set(tokenize(phrase)[1])
        it = results[0]
        blob = re.sub(r"<[^>]+>", " ", f"{it.get('title', '')} {it.get('description', '')}")
        blob_toks = set(tokenize(blob)[1])
        if toks and len(toks & blob_toks) / len(toks) >= 0.6:
            return it
    return None


def check_brave(text: str, max_sentences: int = BRAVE_MAX_PHRASES,
                config_path: Optional[str] = None) -> Dict:
    """Ψάχνει δείγμα προτάσεων αυτούσιες στο Brave Search API.

    Επιστρέφει {status: 'ok'|'partial'|'quota'|'auth'|'offline'|
                'not_configured'|'no_candidates', checked, total, hits}."""
    key = _load_brave_config(config_path)
    if not key:
        return {"status": "not_configured", "checked": 0, "total": 0, "hits": []}

    phrases = _select_check_phrases(text, max_sentences)
    if not phrases:
        return {"status": "no_candidates", "checked": 0, "total": 0, "hits": []}

    hits = []
    checked = 0
    errors = 0
    for i, (phrase, sentence) in enumerate(phrases):
        data = None
        for attempt in (1, 2):
            try:
                data = _brave_api(key, f'"{phrase}"', count=3)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt == 1:
                    retry_after = e.headers.get("Retry-After", "")
                    time.sleep(float(retry_after) if retry_after.isdigit() else 2.0)
                    continue
                if e.code == 429:   # εξαντλήθηκε το μηνιαίο όριο
                    return {"status": "quota", "checked": checked,
                            "total": len(phrases), "hits": hits}
                if e.code in (401, 403, 422):   # το κλειδί δεν ισχύει πια
                    return {"status": "auth", "checked": checked,
                            "total": len(phrases), "hits": hits}
                errors += 1
                break
            except Exception:
                errors += 1
                break
        if data is None:
            if errors >= 3:
                return {"status": "offline" if checked == 0 else "partial",
                        "checked": checked, "total": len(phrases), "hits": hits}
            continue

        checked += 1
        results = (data.get("web") or {}).get("results") or []
        it = _brave_pick_result(phrase, results)
        if it:
            hits.append({
                "sentence": sentence if len(sentence) <= 300 else sentence[:297] + "…",
                "phrase": phrase,
                "title": re.sub(r"<[^>]+>", "", it.get("title", "")),
                "url": it.get("url", ""),
                "total_matches": len(results),
            })
        if i < len(phrases) - 1:
            time.sleep(BRAVE_DELAY)

    return {"status": "ok", "checked": checked, "total": len(phrases), "hits": hits}


if __name__ == "__main__":
    import sys
    corpus = CorpusIndex(sys.argv[1] if len(sys.argv) > 1 else "corpus")
    corpus.refresh()
    print(f"Corpus: {corpus.n_files} αρχεία")
    data = sys.stdin.read()
    print(json.dumps(corpus.compare(data), ensure_ascii=False, indent=2))
