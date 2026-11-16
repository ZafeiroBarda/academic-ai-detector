#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ιστορικό αναλύσεων: ξανανοίγεις αποτελέσματα χωρίς νέα ανάλυση.

Προσωπικά δεδομένα (GDPR) — σχεδιασμένο για ελαχιστοποίηση:
  • Μόνο τοπικά, σε αρχείο με δικαιώματα μόνο για τον χρήστη (0600).
  • ΔΕΝ αποθηκεύεται ολόκληρο το κείμενο της εργασίας — μόνο το αποτέλεσμα
    της ανάλυσης (σκορ, δείκτες και τα λίγα αποσπάσματα που σημειώθηκαν).
  • Αυτόματη διαγραφή μετά από RETENTION_DAYS και έως MAX_ENTRIES εγγραφές.
  • Διακόπτης on/off, διαγραφή ανά εγγραφή ή όλων (με VACUUM, για να μη
    μένουν υπολείμματα στο αρχείο).
Ασφάλεια: γράφει μόνο ο server (όχι δεδομένα από τον browser),
αναγνωριστικά 128 bit με αυστηρό έλεγχο μορφής, παραμετροποιημένα SQL,
JSON (όχι pickle), όριο μεγέθους. Χαλασμένο αρχείο → το ιστορικό
απενεργοποιείται, η ανάλυση συνεχίζει κανονικά.

Ρύθμιση: AI_DETECTOR_HISTORY=off (κλειστό) ή =διαδρομή αρχείου.
"""

import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_FILE = Path(__file__).resolve().parent / ".analysis_history.sqlite3"
RETENTION_DAYS = 30
MAX_ENTRIES = 100
MAX_BYTES = 8 * 1024 * 1024
MAX_NAME = 200
ID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")
_NOT_STORED = ("external_job", "history_id")


def _without_thumbs(images: Dict) -> Dict:
    """Οι μικρογραφίες εικόνων δεν μπαίνουν στο ιστορικό (μέγεθος, προσωπικά δεδομένα)."""
    out = dict(images)
    out["sources"] = [dict(src, matches=[{k: v for k, v in m.items() if not k.endswith("_thumb")}
                                         for m in src.get("matches", []) if isinstance(m, dict)])
                      for src in images.get("sources", []) if isinstance(src, dict)]
    return out


def _clean_name(name) -> Optional[str]:
    if not isinstance(name, str):
        return None
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:MAX_NAME] or None


class HistoryStore:
    def __init__(self, path=None, available: bool = True,
                 max_entries: int = MAX_ENTRIES, retention_days: float = RETENTION_DAYS):
        self.path = Path(path) if path else DEFAULT_FILE
        self.available = available
        self.max_entries = max_entries
        self.retention = retention_days * 86400
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._pending: Dict[str, Dict] = {}     # αποτελέσματα internet που ήρθαν πριν το save

    # --- σύνδεση ---------------------------------------------------------
    def _connect(self) -> Optional[sqlite3.Connection]:
        if not self.available:
            return None
        if self._conn is not None:
            return self._conn
        try:
            if not self.path.exists():
                fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
                os.close(fd)
            else:
                try:
                    os.chmod(self.path, 0o600)
                except OSError:
                    pass
            conn = sqlite3.connect(str(self.path), timeout=2.0, check_same_thread=False)
            conn.execute("CREATE TABLE IF NOT EXISTS history (id TEXT PRIMARY KEY, name TEXT, "
                         "created REAL NOT NULL, summary TEXT NOT NULL, analysis TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            conn.commit()
            self._conn = conn
            return conn
        except (sqlite3.Error, OSError):
            self.available = False
            return None

    def _fail(self) -> None:
        self.available = False
        try:
            if self._conn is not None:
                self._conn.close()
        except sqlite3.Error:
            pass
        self._conn = None

    # --- ρυθμίσεις ---------------------------------------------------------
    def enabled(self) -> bool:
        with self._lock:
            conn = self._connect()
            if conn is None:
                return False
            try:
                row = conn.execute("SELECT v FROM meta WHERE k = 'enabled'").fetchone()
            except sqlite3.Error:
                self._fail()
                return False
        return row is None or row[0] == "1"

    def set_enabled(self, on: bool) -> bool:
        with self._lock:
            conn = self._connect()
            if conn is None:
                return False
            try:
                conn.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('enabled', ?)", ("1" if on else "0",))
                conn.commit()
            except sqlite3.Error:
                self._fail()
                return False
        return True

    # --- εγγραφές ----------------------------------------------------------
    @staticmethod
    def new_id() -> str:
        return secrets.token_urlsafe(16)           # 22 χαρακτήρες, 128 bit

    def save(self, hid: str, name, analysis: Dict) -> bool:
        if not ID_RE.match(hid or "") or not isinstance(analysis, dict) or not self.enabled():
            return False
        data = {k: v for k, v in analysis.items() if k not in _NOT_STORED}
        if isinstance(data.get("images"), dict):
            data["images"] = _without_thumbs(data["images"])
        with self._lock:
            pending = self._pending.pop(hid, None)
            if pending:
                _merge(data, pending)
            try:
                blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return False
            if len(blob.encode("utf-8")) > MAX_BYTES:
                return False
            summary = json.dumps({
                "score": data.get("score"), "verdict": data.get("verdict"),
                "verdict_i18n": data.get("verdict_i18n"), "language": data.get("language"),
                "words": (data.get("text_stats") or {}).get("words"),
            }, ensure_ascii=False)
            conn = self._connect()
            if conn is None:
                return False
            try:
                now = time.time()
                conn.execute("INSERT OR REPLACE INTO history (id, name, created, summary, analysis) "
                             "VALUES (?, ?, ?, ?, ?)", (hid, _clean_name(name), now, summary, blob))
                self._prune(conn, now)
                conn.commit()
            except sqlite3.Error:
                self._fail()
                return False
        return True

    def merge_external(self, hid: str, result: Dict) -> None:
        """Αποτελέσματα web/αναφορών που ολοκληρώθηκαν στο παρασκήνιο."""
        if not ID_RE.match(hid or "") or not isinstance(result, dict):
            return
        with self._lock:
            conn = self._connect()
            if conn is None:
                return
            try:
                row = conn.execute("SELECT analysis FROM history WHERE id = ?", (hid,)).fetchone()
                if row is None:
                    self._pending[hid] = result                # το save δεν έχει γίνει ακόμα
                    if len(self._pending) > 50:                 # να μη μεγαλώνει χωρίς όριο
                        self._pending.pop(next(iter(self._pending)))
                    return
                data = json.loads(row[0])
                _merge(data, result)
                conn.execute("UPDATE history SET analysis = ? WHERE id = ?",
                             (json.dumps(data, ensure_ascii=False, separators=(",", ":")), hid))
                conn.commit()
            except (sqlite3.Error, ValueError):
                self._fail()

    def _prune(self, conn: sqlite3.Connection, now: float) -> None:
        conn.execute("DELETE FROM history WHERE created < ?", (now - self.retention,))
        conn.execute("DELETE FROM history WHERE id IN (SELECT id FROM history "
                     "ORDER BY created DESC LIMIT -1 OFFSET ?)", (self.max_entries,))

    def list(self) -> List[Dict]:
        with self._lock:
            conn = self._connect()
            if conn is None:
                return []
            try:
                self._prune(conn, time.time())
                conn.commit()
                rows = conn.execute("SELECT id, name, created, summary FROM history "
                                    "ORDER BY created DESC").fetchall()
            except sqlite3.Error:
                self._fail()
                return []
        out = []
        for hid, name, created, summary in rows:
            try:
                s = json.loads(summary)
            except ValueError:
                s = {}
            out.append({"id": hid, "name": name, "created": int(created), **{
                k: s.get(k) for k in ("score", "verdict", "verdict_i18n", "language", "words")}})
        return out

    def get(self, hid: str) -> Optional[Dict]:
        if not isinstance(hid, str) or not ID_RE.match(hid):
            return None
        with self._lock:
            conn = self._connect()
            if conn is None:
                return None
            try:
                self._prune(conn, time.time())
                row = conn.execute("SELECT name, created, analysis FROM history WHERE id = ?",
                                   (hid,)).fetchone()
            except sqlite3.Error:
                self._fail()
                return None
        if row is None:
            return None
        try:
            analysis = json.loads(row[2])
        except ValueError:
            return None
        return {"id": hid, "name": row[0], "created": int(row[1]), "analysis": analysis}

    def delete(self, hid: str) -> bool:
        if not isinstance(hid, str) or not ID_RE.match(hid):
            return False
        with self._lock:
            conn = self._connect()
            if conn is None:
                return False
            try:
                n = conn.execute("DELETE FROM history WHERE id = ?", (hid,)).rowcount
                conn.commit()
                conn.execute("VACUUM")
            except sqlite3.Error:
                self._fail()
                return False
        return n > 0

    def clear(self) -> int:
        with self._lock:
            self._pending.clear()
            conn = self._connect()
            if conn is None:
                return 0
            try:
                n = conn.execute("DELETE FROM history").rowcount
                conn.commit()
                conn.execute("VACUUM")
            except sqlite3.Error:
                self._fail()
                return 0
        return n


def _merge(analysis: Dict, result: Dict) -> None:
    plag = analysis.get("plagiarism")
    if not isinstance(plag, dict):
        plag = analysis["plagiarism"] = {}
    for k, v in (result.get("plagiarism") or {}).items():
        if k in ("wikipedia", "scholar", "brave", "google"):
            plag[k] = v
    plag.pop("pending", None)
    if isinstance(result.get("references"), dict):
        analysis["references"] = result["references"]


_default: Optional[HistoryStore] = None
_default_lock = threading.Lock()


def default_history() -> HistoryStore:
    global _default
    with _default_lock:
        if _default is None:
            setting = (os.environ.get("AI_DETECTOR_HISTORY") or "").strip()
            if setting.lower() in ("off", "0", "false", "no"):
                _default = HistoryStore(available=False)
            else:
                _default = HistoryStore(setting or None)
        return _default


def set_default_history(store: Optional[HistoryStore]) -> None:
    global _default
    with _default_lock:
        _default = store
