#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Τοπική cache απαντήσεων των εξωτερικών ελέγχων (Wikipedia, OpenAlex, Crossref).

Όταν μια εργασία ξαναελέγχεται (π.χ. διορθωμένη έκδοση), οι φράσεις και οι
αναφορές που δεν άλλαξαν δεν ξαναρωτιούνται στο internet.

Ασφάλεια / ιδιωτικότητα:
  • Το κλειδί κάθε εγγραφής είναι SHA-256 της αναζήτησης — ΔΕΝ αποθηκεύεται
    κείμενο της εργασίας. Οι τιμές είναι μόνο ό,τι επέστρεψε η δημόσια βάση
    (τίτλοι, έτη, URL, πλήθος αποτελεσμάτων).
  • JSON (όχι pickle) — ένα πειραγμένο αρχείο δεν μπορεί να εκτελέσει κώδικα.
  • Παραμετροποιημένα SQL ερωτήματα, αρχείο με δικαιώματα μόνο για τον
    χρήστη (0600), όριο μεγέθους ανά τιμή και πλήθους εγγραφών, λήξη.
  • Χαλασμένο/κλειδωμένο αρχείο → η cache απενεργοποιείται σιωπηλά, ο
    έλεγχος συνεχίζει κανονικά από το internet.
  • Σφάλματα δικτύου και «ύποπτα» αποτελέσματα δεν αποθηκεύονται ποτέ (το
    αποφασίζει ο καλών).

Απενεργοποίηση: AI_DETECTOR_WEB_CACHE=off. Άλλη θέση: AI_DETECTOR_WEB_CACHE=/path.
Καθαρισμός: σβήσε το αρχείο .web_cache.sqlite3.
"""

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_FILE = Path(__file__).resolve().parent / ".web_cache.sqlite3"
TTL_POSITIVE = 30 * 86400     # βρέθηκε κάτι: σταθερό αποτέλεσμα
TTL_NEGATIVE = 7 * 86400      # «δεν βρέθηκε»: οι βάσεις ενημερώνονται, ξαναρωτάμε νωρίτερα
MAX_VALUE_BYTES = 64 * 1024
MAX_ROWS = 50_000
_PRUNE_EVERY = 200            # εγγραφές ανάμεσα σε καθαρισμούς


def cache_key(namespace: str, query: str) -> str:
    return hashlib.sha256(f"{namespace}\x00{query}".encode("utf-8")).hexdigest()


class WebCache:
    def __init__(self, path: Optional[os.PathLike] = None, enabled: bool = True):
        self.path = Path(path) if path else DEFAULT_FILE
        self.enabled = enabled
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._writes = 0

    # --- σύνδεση -----------------------------------------------------------
    def _connect(self) -> Optional[sqlite3.Connection]:
        if not self.enabled:
            return None
        if self._conn is not None:
            return self._conn
        try:
            if not self.path.exists():
                # Δημιουργία με δικαιώματα μόνο για τον χρήστη πριν γραφτεί οτιδήποτε
                fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
                os.close(fd)
            else:
                try:
                    os.chmod(self.path, 0o600)
                except OSError:
                    pass
            conn = sqlite3.connect(str(self.path), timeout=2.0, check_same_thread=False)
            conn.execute("CREATE TABLE IF NOT EXISTS cache ("
                         "k TEXT PRIMARY KEY, v TEXT NOT NULL, "
                         "created REAL NOT NULL, expires REAL NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS cache_expires ON cache(expires)")
            conn.commit()
            self._conn = conn
            return conn
        except (sqlite3.Error, OSError):
            self.enabled = False          # χαλασμένο/μη εγγράψιμο → χωρίς cache
            return None

    def _disable(self) -> None:
        self.enabled = False
        try:
            if self._conn is not None:
                self._conn.close()
        except sqlite3.Error:
            pass
        self._conn = None

    # --- API ---------------------------------------------------------------
    def get(self, namespace: str, query: str) -> Optional[Any]:
        with self._lock:
            conn = self._connect()
            if conn is None:
                return None
            try:
                row = conn.execute("SELECT v, expires FROM cache WHERE k = ?",
                                   (cache_key(namespace, query),)).fetchone()
            except sqlite3.Error:
                self._disable()
                return None
        if not row or row[1] < time.time():
            return None
        try:
            return json.loads(row[0])
        except (ValueError, TypeError):
            return None

    def put(self, namespace: str, query: str, value: Any, negative: bool = False) -> None:
        try:
            data = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            return
        if len(data.encode("utf-8")) > MAX_VALUE_BYTES:
            return
        now = time.time()
        ttl = TTL_NEGATIVE if negative else TTL_POSITIVE
        with self._lock:
            conn = self._connect()
            if conn is None:
                return
            try:
                conn.execute("INSERT OR REPLACE INTO cache (k, v, created, expires) "
                             "VALUES (?, ?, ?, ?)",
                             (cache_key(namespace, query), data, now, now + ttl))
                self._writes += 1
                if self._writes % _PRUNE_EVERY == 1:
                    self._prune(conn, now)
                conn.commit()
            except sqlite3.Error:
                self._disable()

    @staticmethod
    def _prune(conn: sqlite3.Connection, now: float) -> None:
        conn.execute("DELETE FROM cache WHERE expires < ?", (now,))
        conn.execute("DELETE FROM cache WHERE k IN (SELECT k FROM cache "
                     "ORDER BY created DESC LIMIT -1 OFFSET ?)", (MAX_ROWS,))

    def stats(self) -> dict:
        """{enabled, entries, bytes} — για την οθόνη ρυθμίσεων."""
        with self._lock:
            conn = self._connect()
            if conn is None:
                return {"enabled": False, "entries": 0, "bytes": 0}
            try:
                entries = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            except sqlite3.Error:
                self._disable()
                return {"enabled": False, "entries": 0, "bytes": 0}
        try:
            size = self.path.stat().st_size
        except OSError:
            size = 0
        return {"enabled": True, "entries": int(entries), "bytes": int(size)}

    def clear(self) -> None:
        with self._lock:
            conn = self._connect()
            if conn is None:
                return
            try:
                conn.execute("DELETE FROM cache")
                conn.commit()
                conn.execute("VACUUM")         # να μικρύνει και το αρχείο στον δίσκο
            except sqlite3.Error:
                self._disable()


class _NullCache(WebCache):
    def __init__(self):
        super().__init__(enabled=False)


_default: Optional[WebCache] = None
_default_lock = threading.Lock()


def default_cache() -> WebCache:
    """Η κοινή cache του server (ρυθμίζεται από AI_DETECTOR_WEB_CACHE)."""
    global _default
    with _default_lock:
        if _default is None:
            setting = (os.environ.get("AI_DETECTOR_WEB_CACHE") or "").strip()
            if setting.lower() in ("off", "0", "false", "no"):
                _default = _NullCache()
            else:
                _default = WebCache(setting or None)
        return _default


def set_default_cache(cache: Optional[WebCache]) -> None:
    """Για tests: αντικατάσταση της κοινής cache (None = ξανά από το env)."""
    global _default
    with _default_lock:
        _default = cache
