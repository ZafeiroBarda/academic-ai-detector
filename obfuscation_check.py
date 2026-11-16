#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Κόλπα παράκαμψης ανιχνευτών και ίχνη εργαλείων «humanizer».

Όποιος θέλει να ξεγελάσει έναν ανιχνευτή (AI ή λογοκλοπής) συχνά:
  1. βάζει ΑΟΡΑΤΟΥΣ χαρακτήρες (zero-width space κ.λπ.) μέσα στις λέξεις,
     ώστε να «σπάσει» η σύγκριση κειμένων·
  2. αντικαθιστά γράμματα με ΟΜΟΙΟΓΛΥΦΑ άλλου αλφαβήτου (κυριλλικό «а»
     αντί λατινικό «a», ελληνικό «Ο» αντί λατινικό «O»)·
  3. αλλάζει τα κενά με ΑΣΥΝΗΘΙΣΤΑ κενά Unicode·
  4. περνά το κείμενο από εργαλείο συνωνύμων, που αφήνει «βασανισμένες
     φράσεις» (tortured phrases): «counterfeit consciousness» αντί για
     «artificial intelligence», «profound learning» αντί για «deep learning».
     (Cabanac, Labbé & Magazinov 2021, arXiv:2107.06751 — Problematic Paper
     Screener, >1.000 αποσύρσεις δημοσιεύσεων.)

Τα 1-3 δεν εμφανίζονται σχεδόν ποτέ κατά λάθος σε κείμενο γραμμένο σε
επεξεργαστή κειμένου — είναι ισχυρή ένδειξη σκόπιμης απόκρυψης. Δεν
επηρεάζουν το σκορ AI· εμφανίζονται ως ξεχωριστή ένδειξη.
"""

import re
import unicodedata
from typing import Dict, List

# Αόρατοι χαρακτήρες που δεν έχουν θέση σε κανονικό κείμενο εργασίας
INVISIBLE = {
    "​": "ZERO WIDTH SPACE",
    "‌": "ZERO WIDTH NON-JOINER",
    "‍": "ZERO WIDTH JOINER",
    "⁠": "WORD JOINER",
    "⁡": "FUNCTION APPLICATION",
    "⁢": "INVISIBLE TIMES",
    "⁣": "INVISIBLE SEPARATOR",
    "⁤": "INVISIBLE PLUS",
    "᠎": "MONGOLIAN VOWEL SEPARATOR",
    "﻿": "ZERO WIDTH NO-BREAK SPACE",
}
# Ασυνήθιστα κενά (το απλό non-breaking space U+00A0 είναι φυσιολογικό — εξαιρείται)
ODD_SPACES = {chr(c) for c in range(0x2000, 0x200B)} | {" ", " ", "　"}

# Γράμματα που μοιάζουν οπτικά με λατινικά (κυριλλικά & ελληνικά) και ανάποδα
_CYRILLIC_LOOKALIKE = set("аеорсухіјѕһԁԛԝАВЕКМНОРСТХЅІЈ")
_GREEK_LOOKALIKE_OF_LATIN = set("οΟΑΒΕΖΗΙΚΜΝΡΤΥΧνι")
_LATIN_LOOKALIKE_OF_GREEK = set("oOABEZHIKMNPTYXvi")

MIN_INVISIBLE = 3      # λιγότεροι μπορεί να είναι υπόλειμμα copy-paste
MIN_ODD_SPACES = 10    # και ≥ 2% των κενών ανάμεσα σε λέξεις
ODD_SPACE_RATIO = 0.02
MIN_HOMOGLYPH_WORDS = 2

_WORD_RE = re.compile(r"[^\W\d_]+(?:[​-‍⁠﻿][^\W\d_]+)*", re.UNICODE)

# Βασανισμένη φράση → καθιερωμένος όρος (Cabanac et al. 2021 και Problematic Paper Screener)
TORTURED_PHRASES = {
    "counterfeit consciousness": "artificial intelligence",
    "man-made consciousness": "artificial intelligence",
    "fake neural organization": "artificial neural network",
    "fake neural organizations": "artificial neural networks",
    "counterfeit neural organization": "artificial neural network",
    "profound learning": "deep learning",
    "profound neural organization": "deep neural network",
    "convolutional neural organization": "convolutional neural network",
    "repetitive neural organization": "recurrent neural network",
    "colossal information": "big data",
    "huge information": "big data",
    "enormous information": "big data",
    "information stockroom": "data warehouse",
    "information mining": "data mining",
    "irregular woodland": "random forest",
    "arbitrary timberland": "random forest",
    "random backwoods": "random forest",
    "choice tree": "decision tree",
    "innocent bayes": "naive Bayes",
    "credulous bayes": "naive Bayes",
    "bolster vector machine": "support vector machine",
    "straight relapse": "linear regression",
    "strategic relapse": "logistic regression",
    "k-closest neighbor": "k-nearest neighbor",
    "flag to commotion": "signal to noise",
    "mean square blunder": "mean square error",
    "mean squared blunder": "mean squared error",
    "root mean square blunder": "root mean square error",
    "cloud figuring": "cloud computing",
    "haze figuring": "fog computing",
    "web of things": "internet of things",
    "discourse acknowledgment": "speech recognition",
    "picture acknowledgment": "image recognition",
    "face acknowledgment": "face recognition",
    "normal language preparing": "natural language processing",
    "regular language handling": "natural language processing",
    "pc vision": "computer vision",
    "remote sensor organization": "wireless sensor network",
    "hereditary calculation": "genetic algorithm",
    "subterranean insect settlement": "ant colony",
    "molecule swarm enhancement": "particle swarm optimization",
    "bosom malignant growth": "breast cancer",
    "bosom peril": "breast cancer",
    "kidney disappointment": "kidney failure",
    "heart disappointment": "heart failure",
    "lung malignant growth": "lung cancer",
}
_TORTURED_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(TORTURED_PHRASES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE)

FINDING_CODES = ("invisible_chars", "homoglyphs", "odd_spaces", "tortured_phrases")


def _script(ch: str) -> str:
    name = unicodedata.name(ch, "")
    if name.startswith("LATIN"):
        return "latin"
    if name.startswith("CYRILLIC"):
        return "cyrillic"
    if name.startswith("GREEK"):
        return "greek"
    return "other"


def _visible(word: str) -> str:
    """Λέξη με τους «ύποπτους» χαρακτήρες σημαδεμένους, π.χ. p[а]per."""
    return "".join(f"⟦{c}⟧" if c in INVISIBLE else c for c in word)


def _homoglyph_word(word: str):
    """Αν η λέξη ανακατεύει αλφάβητα με ομοιόγλυφα, επιστρέφει τα ξένα γράμματα."""
    letters = [c for c in word if c.isalpha()]
    if len(letters) < 3:
        return None
    scripts: Dict[str, List[str]] = {}
    for c in letters:
        scripts.setdefault(_script(c), []).append(c)
    if len(scripts) < 2:
        return None
    main = max(scripts, key=lambda s: len(scripts[s]))
    foreign = [c for s, cs in scripts.items() if s != main for c in cs]
    lookalike = {"latin": _CYRILLIC_LOOKALIKE | _GREEK_LOOKALIKE_OF_LATIN,
                 "cyrillic": _LATIN_LOOKALIKE_OF_GREEK,
                 "greek": _LATIN_LOOKALIKE_OF_GREEK | _CYRILLIC_LOOKALIKE}.get(main, set())
    # Μόνο αν ΟΛΑ τα ξένα γράμματα μοιάζουν με γράμματα του κύριου αλφαβήτου —
    # αλλιώς είναι κάτι νόμιμο, π.χ. «TNFα», «μm», «Δx».
    if foreign and all(c in lookalike for c in foreign) and len(foreign) < len(scripts[main]):
        return foreign
    return None


# Αντιστοίχιση ομοιόγλυφων στο γράμμα του κύριου αλφαβήτου της λέξης
_TO_LATIN = dict(zip("аеорсухіјѕһԁԛԝАВЕКМНОРСТХЅІЈ" "οΟΑΒΕΖΗΙΚΜΝΡΤΥΧνι",
                     "aeopcyxijshdqwABEKMHOPCTXSIJ" "oOABEZHIKMNPTYXvi"))
_TO_GREEK = dict(zip("oOABEZHIKMNPTYXvi" "аеорсухАВЕКМНОРСТХ",
                     "οΟΑΒΕΖΗΙΚΜΝΡΤΥΧνι" "αεορσυχΑΒΕΚΜΗΟΡΣΤΧ"))
_TO_CYRILLIC = dict(zip("aeopcyxABEKMHOPCTX", "аеорсухАВЕКМНОРСТХ"))
_STRIP_INVISIBLE = {ord(c): None for c in INVISIBLE}


def strip_invisible(text: str) -> str:
    return (text or "").translate(_STRIP_INVISIBLE)


def fold_homoglyphs(word: str) -> str:
    """Αντικαθιστά τα ομοιόγλυφα άλλου αλφαβήτου με τα «κανονικά» γράμματα, ώστε
    π.χ. «pаper» (κυριλλικό а) να ταιριάζει με «paper» στον έλεγχο λογοκλοπής."""
    foreign = _homoglyph_word(word)
    if not foreign:
        return word
    letters = [c for c in word if c.isalpha() and c not in foreign]
    main = _script(letters[0]) if letters else "latin"
    table = {"latin": _TO_LATIN, "greek": _TO_GREEK, "cyrillic": _TO_CYRILLIC}.get(main, {})
    return "".join(table.get(c, c) if c in foreign else c for c in word)


def check_obfuscation(text: str, max_examples: int = 5) -> Dict:
    """{findings: [{code, level, count, examples}], tortured: [{found, expected, count}]}."""
    text = text or ""
    findings: List[Dict] = []

    invisible = [c for c in text.lstrip("﻿") if c in INVISIBLE]
    if len(invisible) >= MIN_INVISIBLE:
        kinds = sorted({f"U+{ord(c):04X} {INVISIBLE[c]}" for c in invisible})
        examples = []
        for m in re.finditer(r"\S*[​-‍⁠-⁤᠎﻿]\S*", text):
            examples.append(_visible(m.group(0))[:60])
            if len(examples) >= max_examples:
                break
        findings.append({"code": "invisible_chars", "level": "warn", "count": len(invisible),
                         "examples": examples, "kinds": kinds})

    homoglyph_words = []
    for m in _WORD_RE.finditer(text):
        foreign = _homoglyph_word(m.group(0))
        if foreign:
            homoglyph_words.append((m.group(0), foreign))
    if len(homoglyph_words) >= MIN_HOMOGLYPH_WORDS:
        examples = []
        for word, foreign in homoglyph_words[:max_examples]:
            marked = "".join(f"[{c}]" if c in foreign else c for c in word)
            names = ", ".join(sorted({f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in foreign}))
            examples.append(f"{marked} ({names})")
        findings.append({"code": "homoglyphs", "level": "warn", "count": len(homoglyph_words),
                         "examples": examples})

    # Μόνο κενά ΑΝΑΜΕΣΑ ΣΕ ΓΡΑΜΜΑΤΑ: τα στενά κενά πριν από «; : ! ?» (γαλλική
    # τυπογραφία) ή μέσα σε αριθμούς («10 000») είναι νόμιμα.
    odd = [m.group(1) for m in re.finditer(r"(?<=[^\W\d_])([\u2000-\u200a\u202f\u205f\u3000])(?=[^\W\d_])", text)]
    word_gaps = len(re.findall(r"(?<=[^\W\d_])[ \u00a0\u2000-\u200a\u202f\u205f\u3000](?=[^\W\d_])", text))
    if len(odd) >= MIN_ODD_SPACES and len(odd) >= ODD_SPACE_RATIO * max(word_gaps, 1):
        kinds = sorted({f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in odd})
        findings.append({"code": "odd_spaces", "level": "warn", "count": len(odd),
                         "examples": kinds[:max_examples]})

    tortured: Dict[str, Dict] = {}
    for m in _TORTURED_RE.finditer(text):
        key = m.group(1).lower()
        entry = tortured.setdefault(key, {"found": m.group(1), "expected": TORTURED_PHRASES[key],
                                          "count": 0})
        entry["count"] += 1
    tortured_list = sorted(tortured.values(), key=lambda e: -e["count"])
    if tortured_list:
        findings.append({"code": "tortured_phrases", "level": "warn",
                         "count": sum(e["count"] for e in tortured_list),
                         "examples": [f"{e['found']} → {e['expected']}" for e in tortured_list[:max_examples]]})

    return {"findings": findings, "tortured": tortured_list}
