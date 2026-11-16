#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Εξωτερικοί έλεγχοι (web, αναφορές) στο παρασκήνιο, ώστε το σκορ AI να
εμφανίζεται αμέσως και τα υπόλοιπα να συμπληρώνονται όταν τελειώσουν.

Ασφάλεια:
  • Αναγνωριστικό εργασίας: 192 bit από το `secrets` — δεν μαντεύεται, οπότε
    κανείς δεν μπορεί να διαβάσει αποτελέσματα άλλου ελέγχου.
  • Αυστηρός έλεγχος μορφής αναγνωριστικού πριν από οποιαδήποτε αναζήτηση.
  • Όρια: έως MAX_ACTIVE ταυτόχρονοι έλεγχοι και MAX_STORED συνολικά· πέρα
    από αυτά ο καλών τρέχει τον έλεγχο κανονικά (σύγχρονα) — δεν γεμίζει η
    μνήμη ούτε δημιουργούνται άπειρα threads.
  • Τα αποτελέσματα δίνονται ΜΙΑ φορά και μετά σβήνονται· ό,τι δεν
    παραληφθεί σβήνεται μετά από TTL δευτερόλεπτα. Τίποτα στον δίσκο.
"""

import re
import secrets
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Dict, Optional

MAX_ACTIVE = 4
MAX_STORED = 32
TTL = 600            # δευτερόλεπτα που κρατιέται ένα αποτέλεσμα που δεν παραλήφθηκε
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")


class JobStore:
    def __init__(self, max_active: int = MAX_ACTIVE, max_stored: int = MAX_STORED,
                 ttl: float = TTL):
        self.max_active = max_active
        self.max_stored = max_stored
        self.ttl = ttl
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict] = {}
        self._pool = ThreadPoolExecutor(max_workers=max(1, max_active), thread_name_prefix="ext-check")

    def _prune(self, now: float) -> None:
        for job_id, job in list(self._jobs.items()):
            if now - job["created"] > self.ttl and job["future"].done():
                del self._jobs[job_id]

    def submit(self, fn: Callable[[], Dict]) -> Optional[str]:
        """Ξεκινά τον έλεγχο. None αν έχουμε φτάσει τα όρια (ο καλών τον
        τρέχει τότε σύγχρονα)."""
        now = time.time()
        with self._lock:
            self._prune(now)
            active = sum(1 for j in self._jobs.values() if not j["future"].done())
            if active >= self.max_active or len(self._jobs) >= self.max_stored:
                return None
            job_id = secrets.token_urlsafe(24)          # 32 χαρακτήρες, 192 bit
            future: Future = self._pool.submit(fn)
            self._jobs[job_id] = {"future": future, "created": now}
            return job_id

    def poll(self, job_id: str) -> Optional[Dict]:
        """None: άγνωστο/ληγμένο. {"status": "running"} ή {"status": "done", ...}
        (το αποτέλεσμα σβήνεται μόλις παραδοθεί) ή {"status": "error"}."""
        if not isinstance(job_id, str) or not JOB_ID_RE.match(job_id):
            return None
        with self._lock:
            self._prune(time.time())
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if not job["future"].done():
                return {"status": "running"}
            del self._jobs[job_id]
        try:
            result = job["future"].result()
        except Exception:
            return {"status": "error"}
        return dict(result, status="done")

    def size(self) -> int:
        with self._lock:
            return len(self._jobs)
