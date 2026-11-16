#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Έλεγχος με τις ΠΡΑΓΜΑΤΙΚΕΣ υπηρεσίες (Crossref, OpenAlex, Wikipedia): τρέχει
κάθε έλεγχο δύο φορές με προσωρινή cache και τυπώνει χρόνους/αιτήματα.
Ενημερωτικό — εξαρτάται από εξωτερικές υπηρεσίες, γι' αυτό στο CI δεν
μπλοκάρει το PR. Στέλνει μόνο τα ενσωματωμένα δείγματα του test_detector.py.

    python tools/live_smoke.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plagiarism_engine as pe  # noqa: E402
import reference_check as rc  # noqa: E402
import test_detector as T  # noqa: E402
from web_cache import WebCache  # noqa: E402


def main() -> int:
    cache = WebCache(os.path.join(tempfile.mkdtemp(prefix="ai_live_"), "cache.sqlite3"))
    ok = True
    first = None
    for run in (1, 2):
        t = time.time()
        r = rc.check_references(T.SAMPLE_REFERENCES, cache=cache)
        statuses = [x["status"] for x in r["results"]]
        print(f"references run {run}: {r['status']} {statuses} {time.time() - t:.2f}s")
        ok = ok and r["status"] == "ok" and (first is None or statuses == first)
        first = first or statuses
    for run in (1, 2):
        t = time.time()
        s = pe.check_scholar(T.EN_HUMAN_ACADEMIC, max_sentences=4, cache=cache)
        print(f"scholar run {run}: {s['status']} checked={s['checked']} {time.time() - t:.2f}s")
        ok = ok and s["status"] == "ok"
    for run in (1, 2):
        t = time.time()
        w = pe.check_wikipedia(T.EN_HUMAN_ACADEMIC, max_sentences=6, cache=cache)
        print(f"wikipedia run {run}: {w['status']} checked={w['checked']} "
              f"requests={w.get('requests')} {time.time() - t:.2f}s")
        ok = ok and w["status"] in ("ok", "degraded")
    print("LIVE SMOKE:", "OK ✅" if ok else "ΠΡΟΒΛΗΜΑ ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
