#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Μαζική ανάλυση φακέλου από τη γραμμή εντολών (χωρίς server/browser).

Χρήσιμο για πολλές εργασίες μαζί και για το notebook Kaggle/Colab
(notebooks/binoculars_gpu.ipynb), όπου το Binoculars τρέχει σε δωρεάν GPU.

    python tools/batch_analyze.py εργασίες/ --out αποτελέσματα.csv
    AI_DETECTOR_BINOCULARS=qwen2.5-1.5b python tools/batch_analyze.py εργασίες/

Γράφει:
  <out>.csv         μία γραμμή ανά εργασία (σκορ, ετυμηγορία, Binoculars, ενδείξεις)
  <out>_pairs.csv   ζεύγη εργασιών με κοινά αποσπάσματα (σύγκριση μεταξύ τους)
  <out>.json        πλήρη αποτελέσματα (για όποιον θέλει λεπτομέρειες)
Χωρίς αναζητήσεις στο internet: τα κείμενα ΔΕΝ στέλνονται πουθενά.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from binoculars_check import check_binoculars, requested_preset  # noqa: E402
from detector_engine import analyze_text  # noqa: E402
from docx_forensics import analyze_docx  # noqa: E402
from obfuscation_check import check_obfuscation  # noqa: E402
from plagiarism_engine import _extract_file_text, pairwise_similarity  # noqa: E402

EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}


def collect(inputs):
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in EXTENSIONS)
        elif p.suffix.lower() in EXTENSIONS:
            files.append(p)
    return files


def analyze_file(path: Path, use_binoculars: bool) -> dict:
    text = _extract_file_text(path)
    if len(text.split()) < 10:
        return {"file": path.name, "status": "error", "error": "not enough text"}
    analysis = analyze_text(text, source=path.suffix.lower().lstrip("."))
    analysis["obfuscation"] = check_obfuscation(text)
    if path.suffix.lower() == ".docx":
        analysis["docx_history"] = analyze_docx(str(path))
    if use_binoculars:
        analysis["binoculars"] = check_binoculars(text)
    return {"file": path.name, "status": "ok", "analysis": analysis, "text": text}


def summary_row(result: dict) -> dict:
    row = {"file": result["file"], "status": result["status"]}
    if result["status"] != "ok":
        row["error"] = result.get("error", "")
        return row
    a = result["analysis"]
    b = a.get("binoculars") or {}
    hist = a.get("docx_history") or {}
    row.update({
        "words": a["text_stats"]["words"],
        "ai_score": a["score"],
        "verdict": (a.get("verdict_i18n") or {}).get("en", a.get("verdict", "")),
        "binoculars_score": b.get("score", ""),
        "binoculars_verdict": b.get("verdict") or (b.get("status") if b else ""),
        "simple_vocabulary": "yes" if (a.get("fairness") or {}).get("warning") else "",
        "evasion_tricks": ", ".join(f["code"] for f in a["obfuscation"]["findings"]),
        "editing_history_warnings": ", ".join(
            f["code"] for f in hist.get("findings", []) if f.get("level") == "warn"),
    })
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="φάκελοι ή αρχεία (.docx/.pdf/.txt/.md)")
    ap.add_argument("--out", default="results.csv", help="αρχείο CSV αποτελεσμάτων")
    args = ap.parse_args()

    files = collect(args.inputs)
    if not files:
        print("Δεν βρέθηκαν αρχεία .docx/.pdf/.txt/.md")
        return 2
    use_binoculars = bool(requested_preset())
    print(f"{len(files)} αρχεία · Binoculars: {requested_preset() or 'off'}", flush=True)

    results = []
    for i, f in enumerate(files, 1):
        t0 = time.time()
        try:
            r = analyze_file(f, use_binoculars)
        except Exception as e:      # ένα χαλασμένο αρχείο δεν σταματά τα υπόλοιπα
            r = {"file": f.name, "status": "error", "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        score = r["analysis"]["score"] if r["status"] == "ok" else "—"
        print(f"[{i}/{len(files)}] {f.name}: {score} ({time.time() - t0:.1f}s)", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [summary_row(r) for r in results]
    fields = ["file", "status", "words", "ai_score", "verdict", "binoculars_score",
              "binoculars_verdict", "simple_vocabulary", "evasion_tricks",
              "editing_history_warnings", "error"]
    with out.open("w", newline="", encoding="utf-8-sig") as fh:   # utf-8-sig: σωστά ελληνικά στο Excel
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: -(r.get("ai_score") or -1)))

    pairs = pairwise_similarity([(r["file"], r["text"]) for r in results if r["status"] == "ok"])
    pairs_path = out.with_name(out.stem + "_pairs.csv")
    with pairs_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["a", "b", "a_pct", "b_pct", "shared_words", "excerpt"])
        w.writeheader()
        w.writerows(pairs)

    json_path = out.with_suffix(".json")
    json_path.write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "text"} for r in results] + [{"pairs": pairs}],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nΑποτελέσματα: {out}\nΚοινά αποσπάσματα: {pairs_path} ({len(pairs)} ζεύγη)\n"
          f"Πλήρη στοιχεία: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
