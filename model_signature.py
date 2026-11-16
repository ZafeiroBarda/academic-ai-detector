#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model Signature Detector
=========================
Δευτερεύων, ΠΕΙΡΑΜΑΤΙΚΟΣ έλεγχος: ψάχνει φράσεις-"υπογραφές" τυπικές
συνομιλιακών απαντήσεων ChatGPT / Gemini / Claude (π.χ. "as an AI language
model", "I should note", "Let me clarify") — ΟΧΙ αξιόπιστο forensic
αναγνωριστικό μοντέλου. Προήλθε από το v1 (ai_detector_server_model_specific.py, στο
ιστορικό του git), εδώ ενεργοποιημένο μέσα στο κύριο pipeline και
επεκταμένο με ελληνικά ισοδύναμα (το εργαλείο είναι EN+EL).

ΣΗΜΑΝΤΙΚΟΣ ΠΕΡΙΟΡΙΣΜΟΣ, να είναι ρητός και στο UI: αυτά τα σημάδια είναι
τυπικά ΜΟΝΟ σε ακατέργαστο, αντιγραμμένο chat output (κάποιος επικόλλησε
και τη μετα-σχολιαστική "φωνή" του bot). Ένα καθαρό δοκίμιο/κεφάλαιο που
παρήγαγε AI-generated κείμενο σπάνια θα περιέχει "as an AI, I can't browse
the internet" — άρα χαμηλό/μηδενικό σκορ εδώ ΔΕΝ αποδεικνύει ανθρώπινη
συγγραφή. Το κύριο σκορ AI-vs-άνθρωπος (detector_engine.py) παραμένει η
βασική ένδειξη· αυτό εδώ είναι μόνο ένα συμπληρωματικό, χαμηλής
αξιοπιστίας στοιχείο.
"""

import re
from typing import Dict, List, Optional, Tuple

from detector_engine import detect_language

Signal = Tuple[str, float, float, int, str, str]  # regex, weight, cap, min_n, label, key

SIGNAL_STRENGTH_THRESHOLD = 0.5
HAS_SIGNAL_THRESHOLD = 0.15  # κάτω από αυτό δεν έχει νόημα να προταθεί "πιθανό μοντέλο"

# Αριθμημένες λίστες / em-dash — ίδιο regex και στις δύο γλώσσες.
NUMBERED_LISTS_RE = r"(?:^|\n)\s{0,3}\d+\.\s"
EM_DASH_RE = r"—|\s–\s"


# ---------------------------------------------------------------------------
# ChatGPT — "εξυπηρετικός βοηθός", disclaimers, hedging, δομημένες λίστες
# ---------------------------------------------------------------------------

CHATGPT_SIGNALS: Dict[str, List[Signal]] = {
    "en": [
        (r"\b(As an AI|as an AI language model|As a language model|I'm an AI)\b",
         0.15, 0.15, 1, "AI Language Model Disclaimer", "ai_disclaimer"),
        (r"\b(I appreciate|I'd be happy to|I understand your|I'd like to help)\b",
         0.12, 0.12, 1, "Appreciation/Politeness Pattern", "appreciation"),
        (r"\b(I don't have access to|I cannot see|I can't browse|I don't have the ability)\b",
         0.13, 0.13, 1, "Capability Limitations", "limitation_statements"),
        (NUMBERED_LISTS_RE,
         0.10, 0.10, 3, "Numbered List Format", "numbered_lists"),
        (r"\b(best practices|best approach|recommended approach|best way to)\b",
         0.09, 0.09, 1, "Best Practices Language", "best_practices"),
        (r"\b(might|could|may|tends to|suggests that|appears to)\b",
         0.011, 0.11, 4, "Strong Hedging/Uncertainty", "hedging_language"),
        (r"\b(in fact|it's worth noting that|notably|it should be noted)\b",
         0.10, 0.10, 1, "'In fact' Pattern", "in_fact_pattern"),
        (r"\b(that said|nonetheless|however it's important)\b",
         0.09, 0.09, 1, "'That said' Pattern", "that_said_pattern"),
    ],
    "el": [
        (r"\b(ως τεχνητή νοημοσύνη|ως γλωσσικό μοντέλο|ως μοντέλο (τεχνητής νοημοσύνης|AI)|είμαι ένα μοντέλο AI)\b",
         0.15, 0.15, 1, "Δήλωση AI γλωσσικού μοντέλου", "ai_disclaimer"),
        (r"\b(εκτιμώ (την|το)|θα χαρώ να (βοηθήσω|σε βοηθήσω)|καταλαβαίνω (την ανάγκη|το ερώτημά) σου|θα ήθελα να βοηθήσω)\b",
         0.12, 0.12, 1, "Μοτίβο ευγένειας/εκτίμησης", "appreciation"),
        (r"\b(δεν έχω πρόσβαση σε|δεν μπορώ να περιηγηθώ|δεν έχω τη δυνατότητα να|δεν διαθέτω πρόσβαση σε)\b",
         0.13, 0.13, 1, "Δηλώσεις περιορισμού δυνατοτήτων", "limitation_statements"),
        (NUMBERED_LISTS_RE,
         0.10, 0.10, 3, "Μορφή αριθμημένης λίστας", "numbered_lists"),
        (r"\b(βέλτιστες πρακτικές|βέλτιστη προσέγγιση|συνιστώμενη προσέγγιση|καλύτερος τρόπος για)\b",
         0.09, 0.09, 1, "Γλώσσα «βέλτιστων πρακτικών»", "best_practices"),
        (r"\b(μπορεί να|θα μπορούσε να|τείνει να|υποδεικνύει ότι|φαίνεται να)\b",
         0.011, 0.11, 4, "Έντονη επιφυλακτικότητα διατύπωσης", "hedging_language"),
        (r"\b(στην πραγματικότητα|αξίζει να σημειωθεί ότι|σημειωτέον ότι)\b",
         0.10, 0.10, 1, "Μοτίβο «στην πραγματικότητα»", "in_fact_pattern"),
        (r"\b(τούτου λεχθέντος|παρ' ?όλα αυτά|ωστόσο[,]? είναι σημαντικό να)\b",
         0.09, 0.09, 1, "Μοτίβο «παρ' όλα αυτά»", "that_said_pattern"),
    ],
}

# ---------------------------------------------------------------------------
# Gemini — συνομιλιακά ανοίγματα, βεβαιότητα, em-dashes
# ---------------------------------------------------------------------------

GEMINI_SIGNALS: Dict[str, List[Signal]] = {
    "en": [
        (r"\b(Hey|So here's the thing|Let me explain|So here's|Look)\b",
         0.12, 0.12, 1, "Conversational Opening", "conversational_opener"),
        (r"\b(I can provide|I can help you understand|I can assist|I can explain)\b",
         0.11, 0.11, 1, "'I can help' Pattern", "can_help_pattern"),
        (r"\b(absolutely|definitely|certainly|exactly)\b",
         0.0333, 0.10, 3, "Overuse of 'Absolutely/Definitely'", "absolutely_pattern"),
        (r"\b(It's fascinating that|Interestingly|Interestingly enough|It's interesting)\b",
         0.10, 0.10, 1, "'Fascinating/Interestingly' Pattern", "fascinating_pattern"),
        (r"\b(I should clarify that|I should mention that|I want to clarify|Let me clarify)\b",
         0.12, 0.12, 1, "Clarification Pattern", "clarification"),
        (r"\b(I can't access real-time|real-time data|up-to-date information|current events)\b",
         0.11, 0.11, 1, "Real-time Data Limitation", "realtime_limitation"),
        (r"\b(Here's what I found|Here's what I think|Here's the thing)\b",
         0.10, 0.10, 1, "'Here's what I found' Pattern", "here_is_pattern"),
        (r"\b(Some key points|Here are the main|Key takeaways|Important points)\b",
         0.09, 0.09, 1, "Key Points Pattern", "key_points"),
        (r"\b(Remember that|Keep in mind that|It's worth remembering)\b",
         0.09, 0.09, 1, "'Remember that' Pattern", "remember_pattern"),
        (EM_DASH_RE,
         0.016, 0.08, 4, "High Em-dash Usage", "em_dash_frequency"),
    ],
    "el": [
        (r"\b(για να το εξηγήσω|να το εξηγήσω αναλυτικά|κοίτα να δεις|ας το δούμε αναλυτικά)\b",
         0.12, 0.12, 1, "Συνομιλιακό άνοιγμα", "conversational_opener"),
        (r"\b(μπορώ να (παρέχω|σε βοηθήσω να καταλάβεις|βοηθήσω)|μπορώ να εξηγήσω)\b",
         0.11, 0.11, 1, "Μοτίβο «μπορώ να βοηθήσω»", "can_help_pattern"),
        (r"\b(απολύτως|σίγουρα|ασφαλώς|ακριβώς)\b",
         0.0333, 0.10, 3, "Υπερβολική χρήση «απολύτως/σίγουρα»", "absolutely_pattern"),
        (r"\b(είναι συναρπαστικό (ότι|πως)|αξιοσημείωτο είναι (ότι|πως)|είναι ενδιαφέρον (ότι|πως))\b",
         0.10, 0.10, 1, "Μοτίβο «είναι συναρπαστικό/ενδιαφέρον»", "fascinating_pattern"),
        (r"\b(θα πρέπει να διευκρινίσω ότι|θέλω να διευκρινίσω|ας διευκρινίσω|οφείλω να διευκρινίσω)\b",
         0.12, 0.12, 1, "Μοτίβο διευκρίνισης", "clarification"),
        (r"\b(δεν έχω πρόσβαση σε δεδομένα πραγματικού χρόνου|επίκαιρες πληροφορίες|τρέχουσες εξελίξεις σε πραγματικό χρόνο)\b",
         0.11, 0.11, 1, "Περιορισμός δεδομένων πραγματικού χρόνου", "realtime_limitation"),
        (r"\b(να τι βρήκα|να τι ισχύει|να το θέμα με λίγα λόγια)\b",
         0.10, 0.10, 1, "Μοτίβο «να τι βρήκα»", "here_is_pattern"),
        (r"\b(μερικά βασικά σημεία|τα κύρια σημεία|βασικά συμπεράσματα|σημαντικά σημεία)\b",
         0.09, 0.09, 1, "Μοτίβο βασικών σημείων", "key_points"),
        (r"\b(να θυμάσαι ότι|έχε υπόψη ότι|αξίζει να θυμόμαστε ότι)\b",
         0.09, 0.09, 1, "Μοτίβο «να θυμάσαι ότι»", "remember_pattern"),
        (EM_DASH_RE,
         0.016, 0.08, 4, "Έντονη χρήση em-dash", "em_dash_frequency"),
    ],
}

# ---------------------------------------------------------------------------
# Claude — αυτοδιόρθωση, ειλικρινής αβεβαιότητα, λιγότερες αμυντικές δηλώσεις
# ---------------------------------------------------------------------------

CLAUDE_SIGNALS: Dict[str, List[Signal]] = {
    "en": [
        (r"\b(I should note|I want to be honest|I should clarify|I should acknowledge)\b",
         0.12, 0.12, 1, "'I should note' Pattern", "note_pattern"),
        (r"\b(I don't actually know|I'm not sure|I don't have enough information|uncertain)\b",
         0.11, 0.11, 1, "Honesty/Uncertainty Expression", "transparency"),
        (r"\b(That's a great question|That's an interesting|Good question)\b",
         0.10, 0.10, 1, "'Great question' Pattern", "great_question"),
        (r"\b(Let me think|Let me consider|I'll think through|Let me work through)\b",
         0.09, 0.09, 1, "'Let me think' Pattern", "think_pattern"),
        (r"\b(Actually|Wait, let me|I should correct|I misspoke|That's not quite right)\b",
         0.10, 0.10, 1, "Self-Correction Pattern", "self_correction"),
        (r"\b(I'm not entirely sure|This is tricky|This is complex|somewhat unclear)\b",
         0.09, 0.09, 1, "Natural Uncertainty Expression", "natural_uncertainty"),
    ],
    "el": [
        (r"\b(οφείλω να σημειώσω|θέλω να είμαι ειλικρινής|οφείλω να διευκρινίσω|οφείλω να αναγνωρίσω)\b",
         0.12, 0.12, 1, "Μοτίβο «οφείλω να σημειώσω»", "note_pattern"),
        (r"\b(δεν γνωρίζω με βεβαιότητα|δεν είμαι σίγουρ\w+|δεν έχω αρκετές πληροφορίες)\b",
         0.11, 0.11, 1, "Έκφραση ειλικρίνειας/αβεβαιότητας", "transparency"),
        (r"\b(πολύ καλή ερώτηση|πολύ ενδιαφέρουσα ερώτηση|εύστοχη ερώτηση)\b",
         0.10, 0.10, 1, "Μοτίβο «πολύ καλή ερώτηση»", "great_question"),
        (r"\b(ας το σκεφτώ|να το εξετάσω βήμα.βήμα|ας το εξετάσω αναλυτικά)\b",
         0.09, 0.09, 1, "Μοτίβο «ας το σκεφτώ»", "think_pattern"),
        (r"\b(για την ακρίβεια,|μια στιγμή,|διορθώνομαι[:,]|δεν είναι ακριβώς σωστό αυτό)\b",
         0.10, 0.10, 1, "Μοτίβο αυτοδιόρθωσης", "self_correction"),
        (r"\b(δεν είμαι απόλυτα σίγουρ\w+|αυτό είναι περίπλοκο|κάπως ασαφές|δύσκολο να προσδιοριστεί με ακρίβεια)\b",
         0.09, 0.09, 1, "Φυσική έκφραση αβεβαιότητας", "natural_uncertainty"),
    ],
}

CLAUDE_DEFENSIVE_RE = {
    "en": r"\b(I must point out|I should warn|I need to stress|I must emphasize)\b",
    "el": r"\b(οφείλω να επισημάνω|πρέπει να προειδοποιήσω|πρέπει να τονίσω κατηγορηματικά)\b",
}


# Περιγραφές μοτίβων για γλώσσες UI χωρίς δική τους λίστα σημάτων
# (η ανάλυση υποστηρίζει μόνο el/en κείμενα· το UI έχει περισσότερες γλώσσες)
EXTRA_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "less_defensive": {"de": 'Keine defensiven Vorbehalte', "fr": "Absence d'avertissements défensifs", "pt": 'Ausência de ressalvas defensivas'},
    "ai_disclaimer": {"de": 'Hinweis „KI-Sprachmodell“', "fr": 'Mention « modèle de langage IA »', "pt": 'Declaração de «modelo de linguagem de IA»'},
    "appreciation": {"de": 'Höflichkeits-/Wertschätzungsmuster', "fr": 'Formule de politesse/remerciement', "pt": 'Padrão de cortesia/apreço'},
    "limitation_statements": {"de": 'Hinweise auf eigene Grenzen', "fr": 'Déclarations de limites', "pt": 'Declarações de limitações'},
    "numbered_lists": {"de": 'Nummerierte Listen', "fr": 'Format en liste numérotée', "pt": 'Formato de lista numerada'},
    "best_practices": {"de": '„Best Practices“-Sprache', "fr": 'Langage « bonnes pratiques »', "pt": 'Linguagem de «boas práticas»'},
    "hedging_language": {"de": 'Starke Absicherung/Unsicherheit', "fr": 'Forte prudence/incertitude', "pt": 'Forte hesitação/incerteza'},
    "in_fact_pattern": {"de": 'Muster „tatsächlich“', "fr": 'Formule « en fait »', "pt": 'Padrão «na verdade»'},
    "that_said_pattern": {"de": 'Muster „allerdings“', "fr": 'Formule « cela dit »', "pt": 'Padrão «dito isto»'},
    "conversational_opener": {"de": 'Gesprächseinstieg', "fr": 'Ouverture conversationnelle', "pt": 'Abertura conversacional'},
    "can_help_pattern": {"de": 'Muster „ich kann helfen“', "fr": 'Formule « je peux aider »', "pt": 'Padrão «posso ajudar»'},
    "absolutely_pattern": {"de": 'Übermäßiges „absolut/definitiv“', "fr": 'Abus de « absolument/certainement »', "pt": 'Uso excessivo de «absolutamente/certamente»'},
    "fascinating_pattern": {"de": 'Muster „faszinierend/interessant“', "fr": 'Formule « fascinant/intéressant »', "pt": 'Padrão «fascinante/interessante»'},
    "clarification": {"de": 'Klarstellungsmuster', "fr": 'Formule de clarification', "pt": 'Padrão de esclarecimento'},
    "realtime_limitation": {"de": 'Keine Echtzeitdaten', "fr": 'Limite des données en temps réel', "pt": 'Limitação de dados em tempo real'},
    "here_is_pattern": {"de": 'Muster „Das habe ich gefunden“', "fr": "Formule « voici ce que j'ai trouvé »", "pt": 'Padrão «eis o que encontrei»'},
    "key_points": {"de": 'Muster „Kernpunkte“', "fr": 'Formule « points clés »', "pt": 'Padrão «pontos-chave»'},
    "remember_pattern": {"de": 'Muster „denk daran, dass“', "fr": "Formule « n'oubliez pas que »", "pt": 'Padrão «lembre-se de que»'},
    "em_dash_frequency": {"de": 'Häufige Geviertstriche', "fr": 'Usage fréquent du tiret cadratin', "pt": 'Uso frequente de travessões'},
    "note_pattern": {"de": 'Muster „ich sollte anmerken“', "fr": 'Formule « je dois préciser »', "pt": 'Padrão «devo salientar»'},
    "transparency": {"de": 'Ehrlichkeit/Unsicherheit ausdrücken', "fr": "Expression d'honnêteté/d'incertitude", "pt": 'Expressão de honestidade/incerteza'},
    "great_question": {"de": 'Muster „gute Frage“', "fr": 'Formule « excellente question »', "pt": 'Padrão «ótima pergunta»'},
    "think_pattern": {"de": 'Muster „lass mich überlegen“', "fr": 'Formule « laissez-moi réfléchir »', "pt": 'Padrão «deixe-me pensar»'},
    "self_correction": {"de": 'Selbstkorrektur', "fr": 'Autocorrection', "pt": 'Autocorreção'},
    "natural_uncertainty": {"de": 'Natürlicher Ausdruck von Unsicherheit', "fr": "Expression naturelle d'incertitude", "pt": 'Expressão natural de incerteza'},
}


def _build_descriptions() -> Dict[str, Dict[str, str]]:
    """key → {"el": ..., "en": ...} από τις δύο λίστες κάθε μοντέλου, ώστε το UI
    να δείχνει την περιγραφή στη γλώσσα του, όχι στη γλώσσα του κειμένου."""
    out: Dict[str, Dict[str, str]] = {
        "less_defensive": {"el": "Απουσία αμυντικών δηλώσεων",
                           "en": "Absence of Defensive Disclaimers"},
    }
    for table in (CHATGPT_SIGNALS, GEMINI_SIGNALS, CLAUDE_SIGNALS):
        for lang, signals in table.items():
            for *_, label, key in signals:
                out.setdefault(key, {}).setdefault(lang, label)
    for key, texts in EXTRA_DESCRIPTIONS.items():
        out.setdefault(key, {}).update(texts)
    return out


PATTERN_DESCRIPTIONS = _build_descriptions()


def _lang_key(language: str) -> str:
    return "el" if language == "greek" else "en"


def _score_signals(text: str, signals: List[Signal]) -> Tuple[float, List[Dict]]:
    score = 0.0
    found: List[Dict] = []
    for pattern, weight, cap, min_n, label, key in signals:
        n = len(re.findall(pattern, text, re.IGNORECASE))
        if n >= min_n:
            score += min(weight * n, cap)
            found.append({"pattern": key, "description": label,
                          "description_i18n": PATTERN_DESCRIPTIONS.get(key, {}),
                          "occurrences": n})
    return min(score, 1.0), found


def detect_chatgpt_patterns(text: str, language: str) -> Dict:
    score, patterns = _score_signals(text, CHATGPT_SIGNALS[_lang_key(language)])
    return {"score": score, "patterns": patterns,
            "strength": "STRONG" if score > SIGNAL_STRENGTH_THRESHOLD else "WEAK"}


def detect_gemini_patterns(text: str, language: str) -> Dict:
    score, patterns = _score_signals(text, GEMINI_SIGNALS[_lang_key(language)])
    return {"score": score, "patterns": patterns,
            "strength": "STRONG" if score > SIGNAL_STRENGTH_THRESHOLD else "WEAK"}


def detect_claude_patterns(text: str, language: str) -> Dict:
    lang_key = _lang_key(language)
    score, patterns = _score_signals(text, CLAUDE_SIGNALS[lang_key])
    # Το Claude τείνει να χρησιμοποιεί ΛΙΓΟΤΕΡΕΣ αμυντικές δηλώσεις από τα
    # άλλα δύο — η απουσία τους είναι το ίδιο το σήμα (ίδια λογική με v1).
    defensive_hits = len(re.findall(CLAUDE_DEFENSIVE_RE[lang_key], text, re.IGNORECASE))
    if defensive_hits == 0:
        score = min(score + 0.05, 1.0)
        patterns.append({"pattern": "less_defensive",
                         "description": "Απουσία αμυντικών δηλώσεων" if lang_key == "el"
                                         else "Absence of Defensive Disclaimers",
                         "description_i18n": PATTERN_DESCRIPTIONS["less_defensive"],
                         "occurrences": 0})
    return {"score": score, "patterns": patterns,
            "strength": "STRONG" if score > 0.4 else "WEAK"}


def detect_model_signature(text: str, language: Optional[str] = None) -> Dict:
    """Συνομιλιακές «υπογραφές» ChatGPT/Gemini/Claude — δευτερεύον, πειραματικό
    σήμα. Δες το module docstring για τον περιορισμό αξιοπιστίας σε δοκίμια."""
    text = (text or "").strip()
    if not text:
        return {"has_signal": False, "primary_model": None, "primary_score": 0.0,
                "overall_score": 0.0, "language": "-", "models": {}}

    if language is None:
        language = detect_language(text)

    chatgpt = detect_chatgpt_patterns(text, language)
    gemini = detect_gemini_patterns(text, language)
    claude = detect_claude_patterns(text, language)

    model_results = {"ChatGPT": chatgpt, "Gemini": gemini, "Claude": claude}
    primary_model = max(model_results, key=lambda k: model_results[k]["score"])
    primary_score = model_results[primary_model]["score"]
    overall_score = sum(m["score"] for m in model_results.values()) / 3

    return {
        "has_signal": primary_score >= HAS_SIGNAL_THRESHOLD,
        "primary_model": primary_model if primary_score >= HAS_SIGNAL_THRESHOLD else None,
        "primary_score": round(primary_score * 100, 1),
        "overall_score": round(overall_score * 100, 1),
        "language": "Ελληνικά" if language == "greek" else "English",
        "models": {
            name: {
                "score": round(m["score"] * 100, 1),
                "strength": m["strength"],
                "patterns": m["patterns"],
            }
            for name, m in model_results.items()
        },
    }
