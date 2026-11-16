#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Σύγκριση δύο εκδόσεων της ίδιας εργασίας (π.χ. πριν και μετά τις διορθώσεις).

Απαντά σε:
  • Πόσο άλλαξε το σκορ AI και ποιοι δείκτες άλλαξαν περισσότερο;
  • Πόσο από το κείμενο άλλαξε (νέες / αφαιρεμένες / ίδιες προτάσεις);
  • Ποιες ΝΕΕΣ προτάσεις έχουν ενδείξεις AI (π.χ. ο φοιτητής «διόρθωσε»
    ξαναγράφοντας με chatbot);
Μόνο τοπική ανάλυση — καμία αναζήτηση στο internet.
"""

import re
import unicodedata
from typing import Dict, List

from detector_engine import analyze_text, split_sentences

MAX_LISTED = 15          # νέες προτάσεις με ενδείξεις που επιστρέφονται


def _norm_sentence(s: str) -> str:
    """Σύγκριση προτάσεων χωρίς να μετρούν κενά, κεφαλαία, τόνοι, στίξη."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", s).strip()


def _sentences(text: str, language: str) -> List[str]:
    return [s.strip() for s in split_sentences(text, language) if len(s.split()) >= 4]


def compare_versions(old_text: str, new_text: str) -> Dict:
    old_a = analyze_text(old_text)
    new_a = analyze_text(new_text)

    # --- Δείκτες: ποιοι άλλαξαν περισσότερο ---
    old_f = {f["name"]: f for f in old_a["features"]}
    features = []
    for f in new_a["features"]:
        o = old_f.get(f["name"])
        if o is None:
            continue
        delta = round(f["score"] - o["score"], 1)
        features.append({"name": f["name"], "label": f["label"], "label_i18n": f.get("label_i18n", {}),
                         "old": o["score"], "new": f["score"], "delta": delta})
    features.sort(key=lambda x: -abs(x["delta"]))

    # --- Κείμενο: νέες / αφαιρεμένες / ίδιες προτάσεις ---
    old_s = _sentences(old_text, old_a["language"])
    new_s = _sentences(new_text, new_a["language"])
    old_keys = {_norm_sentence(s) for s in old_s}
    new_keys = {_norm_sentence(s) for s in new_s}
    added = [s for s in new_s if _norm_sentence(s) not in old_keys]
    removed = sum(1 for s in old_s if _norm_sentence(s) not in new_keys)
    kept = len(new_s) - len(added)
    new_words = sum(len(s.split()) for s in new_s) or 1
    changed_pct = round(100.0 * sum(len(s.split()) for s in added) / new_words, 1)

    # --- Νέες προτάσεις που ο ανιχνευτής σημειώνει ---
    added_keys = {_norm_sentence(s) for s in added}
    new_flagged = [
        {"text": h["text"], "hits": h["hits"], "hits_i18n": h.get("hits_i18n", {})}
        for h in new_a.get("highlights", [])
        if _norm_sentence(h["text"]) in added_keys
    ][:MAX_LISTED]

    return {
        "old": {"score": old_a["score"], "verdict": old_a["verdict"],
                "verdict_i18n": old_a.get("verdict_i18n", {}), "words": old_a["text_stats"]["words"]},
        "new": {"score": new_a["score"], "verdict": new_a["verdict"],
                "verdict_i18n": new_a.get("verdict_i18n", {}), "words": new_a["text_stats"]["words"]},
        "score_delta": round(new_a["score"] - old_a["score"], 1),
        "features": features,
        "text_change": {"sentences_added": len(added), "sentences_removed": removed,
                        "sentences_kept": kept, "changed_pct": changed_pct},
        "new_flagged": new_flagged,
        "new_flagged_total": sum(1 for h in new_a.get("highlights", [])
                                 if _norm_sentence(h["text"]) in added_keys),
    }
