#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Βαθμονόμηση του σκορ AI στα δικά σου δεδομένα.

Δίνεις εργασίες που ΣΙΓΟΥΡΑ γράφτηκαν από ανθρώπους (π.χ. διπλωματικές πριν
το 2022) από το δικό σου γνωστικό πεδίο. Το εργαλείο μετρά τι σκορ παίρνουν
και από εκεί και πέρα κάθε αποτέλεσμα δείχνει: «στις N ανθρώπινες εργασίες
αναφοράς, το X% είχε σκορ τόσο ή πιο υψηλό» — δηλαδή πόσο συνηθισμένο είναι
αυτό το σκορ για ανθρώπινο κείμενο στο δικό σου πεδίο.

Προσωπικά δεδομένα: το προφίλ κρατά ΜΟΝΟ αριθμούς (σκορ) — όχι κείμενα,
ονόματα αρχείων ή φοιτητών. Αρχείο calibration_profile.json (0600, τοπικό).
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

PROFILE_FILE = Path(os.environ.get("AI_DETECTOR_CALIBRATION",
                                   Path(__file__).resolve().parent / "calibration_profile.json"))
MIN_HUMAN = 10           # λιγότερες δεν δίνουν αξιόπιστη εικόνα
TARGET_FPR = 0.05        # προτεινόμενο όριο: ≤ 5% ανθρώπινων εργασιών πάνω από αυτό
REPORT_THRESHOLDS = (30, 50, 60, 70, 80)
MAX_NAME = 80


def _share_at_or_above(scores: List[float], value: float) -> float:
    return sum(1 for s in scores if s >= value) / len(scores) if scores else 0.0


def build_profile(human_scores: List[float], ai_scores: Optional[List[float]] = None,
                  name: Optional[str] = None) -> Dict:
    human = sorted(round(float(s), 1) for s in human_scores)
    ai = sorted(round(float(s), 1) for s in (ai_scores or []))
    if len(human) < MIN_HUMAN:
        raise ValueError("not_enough_human")
    suggested = next((t for t in range(0, 101) if _share_at_or_above(human, t) <= TARGET_FPR), 100)
    profile = {
        "version": 1,
        "created": int(time.time()),
        "name": ("".join(ch for ch in (name or "") if ch.isprintable()).strip()[:MAX_NAME] or None),
        "n_human": len(human),
        "human_scores": human,
        "n_ai": len(ai),
        "ai_scores": ai,
        "human_median": human[len(human) // 2],
        "false_positive_rate": {str(t): round(100 * _share_at_or_above(human, t), 1)
                                for t in REPORT_THRESHOLDS},
        "suggested_threshold": suggested,
    }
    if ai:
        profile["ai_detection_rate"] = round(100 * _share_at_or_above(ai, suggested), 1)
    return profile


def _valid(profile) -> bool:
    if not isinstance(profile, dict) or profile.get("version") != 1:
        return False
    scores = profile.get("human_scores")
    return (isinstance(scores, list) and len(scores) >= MIN_HUMAN
            and all(isinstance(s, (int, float)) and 0 <= s <= 100 for s in scores))


def load_profile(path: Optional[Path] = None) -> Optional[Dict]:
    try:
        data = json.loads(Path(path or PROFILE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if _valid(data) else None


def save_profile(profile: Dict, path: Optional[Path] = None) -> None:
    path = Path(path or PROFILE_FILE)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def clear_profile(path: Optional[Path] = None) -> bool:
    try:
        Path(path or PROFILE_FILE).unlink()
        return True
    except OSError:
        return False


def summary(profile: Optional[Dict]) -> Optional[Dict]:
    """Ό,τι χρειάζεται η σελίδα (χωρίς τη λίστα με τα σκορ)."""
    if not profile:
        return None
    keys = ("name", "created", "n_human", "n_ai", "human_median", "false_positive_rate",
            "suggested_threshold", "ai_detection_rate")
    return {k: profile.get(k) for k in keys if k in profile}


def position(score: float, profile: Optional[Dict]) -> Optional[Dict]:
    """Πού βρίσκεται ένα σκορ σε σχέση με τις ανθρώπινες εργασίες αναφοράς."""
    if not profile or not isinstance(score, (int, float)):
        return None
    human = profile["human_scores"]
    return {
        "n_human": len(human),
        "name": profile.get("name"),
        "human_share_at_or_above": round(100 * _share_at_or_above(human, score), 1),
        "suggested_threshold": profile.get("suggested_threshold"),
        "above_suggested": score >= profile.get("suggested_threshold", 101),
    }
