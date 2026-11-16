#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Βαθμονόμηση ορίου Binoculars για το ζεύγος μοντέλων που χρησιμοποιείς.

Τα όρια του paper ισχύουν μόνο για Falcon-7B. Για άλλο ζεύγος (π.χ. Qwen)
δώσε φακέλους με ΓΝΩΣΤΑ κείμενα — ιδανικά 20+ ανά κατηγορία, στη γλώσσα και
το είδος των εργασιών σου (.txt, .md, .docx, .pdf):

    AI_DETECTOR_BINOCULARS=qwen2.5-1.5b \\
        python tools/calibrate_binoculars.py --human-dir δείγματα/άνθρωποι --ai-dir δείγματα/ai

Χωρίς φακέλους χρησιμοποιούνται τα λίγα ενσωματωμένα δείγματα του
test_detector.py — αρκούν για δοκιμή, ΟΧΙ για πραγματική χρήση.
Το όριο γράφεται στο binoculars_config.json (δίπλα στον server).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import binoculars_check as bc  # noqa: E402


def _read_dir(path: str):
    from plagiarism_engine import _extract_file_text
    texts = []
    for f in sorted(Path(path).iterdir()):
        if f.suffix.lower() in (".txt", ".md", ".docx", ".pdf"):
            text = _extract_file_text(f)
            if len(text.split()) >= 100:
                texts.append((f.name, text))
    return texts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--human-dir")
    ap.add_argument("--ai-dir")
    ap.add_argument("--dry-run", action="store_true", help="μην γράψεις binoculars_config.json")
    args = ap.parse_args()

    preset = bc.requested_preset()
    if not preset:
        print("Όρισε πρώτα AI_DETECTOR_BINOCULARS (π.χ. qwen2.5-1.5b). Διαθέσιμα:", ", ".join(bc.PRESETS))
        return 2
    settings = bc.resolve_settings(preset)

    if args.human_dir and args.ai_dir:
        human, ai = _read_dir(args.human_dir), _read_dir(args.ai_dir)
    else:
        import test_detector as T
        print("⚠ Χωρίς --human-dir/--ai-dir: ενσωματωμένα δείγματα (πολύ λίγα για πραγματική χρήση)")
        human = [(n, getattr(T, n)) for n in ("EN_HUMAN_CASUAL", "EN_HUMAN_ACADEMIC",
                                              "EL_HUMAN_CASUAL", "EL_HUMAN_ACADEMIC")]
        ai = [(n, getattr(T, n)) for n in ("EN_AI", "EL_AI")]

    print(f"Φόρτωση μοντέλων {settings['observer']} + {settings['performer']} …")
    scorer = bc.load_scorer(settings["observer"], settings["performer"], quantize=settings.get("quantize"))

    def scores(items, label):
        out = []
        for name, text in items:
            r = scorer.score(text)
            if r["scores"]:
                s = sorted(r["scores"])[len(r["scores"]) // 2]
                out.append(s)
                print(f"  {label:6} {s:.4f}  {name}")
        return out

    human_scores = scores(human, "human")
    ai_scores = scores(ai, "AI")
    result = bc.calibrate_threshold(ai_scores, human_scores)
    print(f"\nΌριο: {result['threshold']:.4f} — AI εντοπίστηκαν {result['ai_detected']:.0%}, "
          f"ανθρώπινα σωστά {result['human_correct']:.0%} "
          f"({result['n_ai']} AI / {result['n_human']} ανθρώπινα)")
    if not args.dry_run:
        bc.CONFIG_FILE.write_text(json.dumps({
            "observer": settings["observer"], "performer": settings["performer"],
            "quantize": settings.get("quantize"), "threshold": result["threshold"], "calibration": result,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Γράφτηκε: {bc.CONFIG_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
