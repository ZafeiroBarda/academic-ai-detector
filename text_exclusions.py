#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Εξαίρεση παραθεμάτων και βιβλιογραφίας από τον έλεγχο ομοιότητας
(όπως το «exclude quotes / exclude bibliography» του Turnitin).

Ένα σωστό παράθεμα «…» με παραπομπή, ή η λίστα αναφορών που είναι ίδια σε
πολλές εργασίες, ΔΕΝ είναι λογοκλοπή — αλλά ανεβάζει το ποσοστό ομοιότητας.
Επηρεάζει ΜΟΝΟ τη λογοκλοπή (corpus, web, σύγκριση εργασιών)· η ανάλυση AI
και ο έλεγχος αναφορών βλέπουν όλο το κείμενο.

Συντηρητικά, ώστε να μην κρύβεται αντιγραφή:
  • παράθεμα = κείμενο ανάμεσα σε “ ”, « », „ “ ή " " με 5+ λέξεις και
    έως ~1.200 χαρακτήρες (όχι ολόκληρες σελίδες σε εισαγωγικά)·
  • βιβλιογραφία = μετά την ΤΕΛΕΥΤΑΙΑ επικεφαλίδα βιβλιογραφίας, μόνο αν
    είναι στο δεύτερο μισό του κειμένου και όχι πάνω από 40% των λέξεων.
"""

import re
from typing import Dict, Tuple

from reference_check import _END_RE, _HEADING_RE

MIN_QUOTE_WORDS = 5
MAX_QUOTE_CHARS = 1200
MAX_BIBLIOGRAPHY_SHARE = 0.40

_QUOTE_RES = [re.compile(p, re.DOTALL) for p in (
    r"“([^“”]{10,%d})”" % MAX_QUOTE_CHARS,
    r"«([^«»]{10,%d})»" % MAX_QUOTE_CHARS,
    r"„([^„“”]{10,%d})[“”]" % MAX_QUOTE_CHARS,
    r'"([^"\n]{10,%d})"' % MAX_QUOTE_CHARS,
)]


def _words(s: str) -> int:
    return len(s.split())


def bibliography_span(text: str):
    """(αρχή, τέλος) της ενότητας βιβλιογραφίας ή None."""
    headings = list(_HEADING_RE.finditer(text or ""))
    if not headings:
        return None
    h = headings[-1]
    if h.start() < len(text) * 0.5:
        return None
    end_m = _END_RE.search(text, h.end())
    end = end_m.start() if end_m else len(text)
    if _words(text[h.start():end]) > MAX_BIBLIOGRAPHY_SHARE * max(_words(text), 1):
        return None
    return h.start(), end


def exclude_for_similarity(text: str) -> Tuple[str, Dict[str, int]]:
    """Επιστρέφει (κείμενο για σύγκριση, {quotes, quoted_words, bibliography_words})."""
    info = {"quotes": 0, "quoted_words": 0, "bibliography_words": 0}
    if not text:
        return text, info
    span = bibliography_span(text)
    if span:
        info["bibliography_words"] = _words(text[span[0]:span[1]])
        text = text[:span[0]] + "\n" + text[span[1]:]

    def drop(m):
        inner = m.group(1)
        if _words(inner) < MIN_QUOTE_WORDS:
            return m.group(0)
        info["quotes"] += 1
        info["quoted_words"] += _words(inner)
        return " \n "                       # σπάει τη συνέχεια: όχι «γέφυρα» πάνω από το παράθεμα
    for rx in _QUOTE_RES:
        text = rx.sub(drop, text)
    return text, info
