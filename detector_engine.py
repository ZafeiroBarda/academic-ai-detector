#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Content Detection Engine v2.0
================================
Στατιστικός πυρήνας ανίχνευσης AI-generated κειμένου για Ελληνικά και Αγγλικά.

Αντί για απλά regex patterns (v1), συνδυάζει:
  1. Πυκνότητα χαρακτηριστικών AI φράσεων/λεξιλογίου (curated lists ανά γλώσσα)
  2. Burstiness — διακύμανση μήκους προτάσεων (AI = ομοιόμορφο, άνθρωπος = άνισο)
  3. Πυκνότητα τυπικών συνδέσμων στην αρχή προτάσεων (However/Moreover/Επιπλέον/Ωστόσο)
  4. "Rule of three" — τριάδες "Χ, Υ και Ζ" που λατρεύουν τα LLMs
  5. Em-dashes (—) και άλλα σημάδια στίξης τυπικά των LLMs
  6. Ομοιομορφία μήκους παραγράφων
  7. Επανάληψη ίδιας πρώτης λέξης στις προτάσεις
  8. Υπολείμματα Markdown (** , ###, bullets) από copy-paste chatbot
  9. Ανθρώπινα σημάδια: συντμήσεις, προφορικές λέξεις, τυπογραφικά λάθη,
     προσωπική αφήγηση, βιβλιογραφικές παραπομπές

Κάθε χαρακτηριστικό δίνει σκορ 0..1 (1 = μοιάζει με AI) και συνδυάζονται
με βάρη σε τελικό σκορ 0-100 μέσω λογιστικής συνάρτησης.

Δεν απαιτεί εξωτερικές βιβλιοθήκες — μόνο standard library.
"""

import math
import re
import statistics
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Γλωσσική ανίχνευση
# ---------------------------------------------------------------------------

GREEK_CHARS = re.compile(r'[α-ωάέήίόύώϊϋΐΰςΑ-ΩΆΈΉΊΌΎΏΪΫ]')
LATIN_CHARS = re.compile(r'[a-zA-Z]')


def detect_language(text: str) -> str:
    """Επιστρέφει 'greek' ή 'english' ανάλογα με το ποιοι χαρακτήρες κυριαρχούν."""
    greek = len(GREEK_CHARS.findall(text))
    latin = len(LATIN_CHARS.findall(text))
    return "greek" if greek > latin else "english"


# ---------------------------------------------------------------------------
# Κατακερματισμός κειμένου
# ---------------------------------------------------------------------------

def split_paragraphs(text: str) -> List[str]:
    paras = re.split(r'\n\s*\n|\r\n\s*\r\n', text)
    return [p.strip() for p in paras if p.strip() and len(p.split()) >= 3]


def split_sentences(text: str, language: str) -> List[str]:
    # Στα ελληνικά το ';' είναι ερωτηματικό — χωρίζει πρόταση.
    # Στα αγγλικά το ';' ενώνει προτάσεις — ΔΕΝ χωρίζει.
    if language == "greek":
        parts = re.split(r'(?<=[.!;…])\s+', text)
    else:
        parts = re.split(r'(?<=[.!?…])\s+', text)
    return [s.strip() for s in parts if s.strip() and len(s.split()) >= 2]


WORD_RE = re.compile(r"[\w'''-]+", re.UNICODE)


def tokenize_words(text: str) -> List[str]:
    return WORD_RE.findall(text)


# ---------------------------------------------------------------------------
# AI φράσεις / λεξιλόγιο — ΑΓΓΛΙΚΑ (προτεραιότητα)
# Κάθε entry: (regex, βάρος 1-3, ετικέτα). Βάρος 3 = σχεδόν αποκλειστικά AI.
# ---------------------------------------------------------------------------

AI_PHRASES_EN: List[Tuple[str, int, str]] = [
    # -- Κλασικά LLM κλισέ (βαριά) --
    (r"\bdelve(s|d)? (in|into|deeper)\b", 3, "delve into"),
    (r"\bit is important to note\b", 3, "it is important to note"),
    (r"\bit'?s worth noting\b", 3, "it's worth noting"),
    (r"\bit should be noted\b", 2, "it should be noted"),
    (r"\bin today'?s (fast-paced|rapidly evolving|digital|modern|ever-changing) (world|era|age|landscape|society)\b", 3, "in today's ... world"),
    (r"\bever-evolving\b", 3, "ever-evolving"),
    (r"\bever-changing\b", 2, "ever-changing"),
    (r"\brapidly evolving\b", 2, "rapidly evolving"),
    (r"\bserves? as a testament\b", 3, "serves as a testament"),
    (r"\bstands? as a testament\b", 3, "stands as a testament"),
    (r"\bnavigat\w+ the (complexities|challenges|landscape|intricacies)\b", 3, "navigating the complexities"),
    (r"\bplays? a (crucial|pivotal|vital|significant|key) role\b", 3, "plays a crucial role"),
    (r"\ba tapestry of\b", 3, "a tapestry of"),
    (r"\brich tapestry\b", 3, "rich tapestry"),
    (r"\bunlock\w* the (potential|power|possibilities|secrets)\b", 3, "unlock the potential"),
    (r"\bharness\w* the (power|potential)\b", 3, "harness the power"),
    (r"\bat the forefront of\b", 2, "at the forefront of"),
    (r"\bpav(e|es|ed|ing) the way\b", 2, "paving the way"),
    (r"\ba double-edged sword\b", 2, "a double-edged sword"),
    (r"\bin the realm of\b", 3, "in the realm of"),
    (r"\bthe landscape of\b", 2, "the landscape of"),
    (r"\bunderscor(e|es|ed|ing)\b", 3, "underscore"),
    (r"\bmultifaceted\b", 3, "multifaceted"),
    (r"\bunwavering\b", 2, "unwavering"),
    (r"\bmeticulous(ly)?\b", 2, "meticulous"),
    (r"\bintricac(y|ies)\b", 2, "intricacies"),
    (r"\bintricate\b", 1, "intricate"),
    (r"\bcommendable\b", 2, "commendable"),
    (r"\bnoteworthy\b", 2, "noteworthy"),
    (r"\bgroundbreaking\b", 1, "groundbreaking"),
    (r"\btransformative\b", 2, "transformative"),
    (r"\bparadigm shift\b", 2, "paradigm shift"),
    (r"\bseamless(ly)?\b", 2, "seamless"),
    (r"\bleverag(e|es|ed|ing)\b", 2, "leverage"),
    (r"\bfoster(s|ed|ing)?\b", 1, "foster"),
    (r"\bempower(s|ed|ing|ment)?\b", 1, "empower"),
    (r"\bholistic\b", 2, "holistic"),
    (r"\brobust\b", 1, "robust"),
    (r"\bpivotal\b", 2, "pivotal"),
    (r"\bcrucial\b", 1, "crucial"),
    (r"\bcomprehensive\b", 1, "comprehensive"),
    (r"\binvaluable\b", 1, "invaluable"),
    (r"\bnuanced\b", 1, "nuanced"),
    (r"\bmyriad\b", 2, "myriad"),
    (r"\bplethora\b", 2, "plethora"),
    (r"\bembark\w* on\b", 2, "embark on"),
    (r"\belevate\w* the\b", 1, "elevate the"),
    (r"\bstreamlin(e|es|ed|ing)\b", 1, "streamline"),
    (r"\bcutting-edge\b", 1, "cutting-edge"),
    (r"\bgame-?changer\b", 2, "game-changer"),
    (r"\bactionable insights?\b", 2, "actionable insights"),
    (r"\bvaluable insights?\b", 2, "valuable insights"),
    (r"\bkey takeaways?\b", 2, "key takeaways"),
    (r"\bwhether you'?re .{3,40}, or\b", 2, "whether you're X or Y"),
    (r"\bnot only .{3,60} but also\b", 1, "not only ... but also"),
    (r"\bfrom .{3,30} to .{3,30}, \w+\b", 1, "from X to Y"),
    (r"\bas we (move|look|venture) (forward|ahead|into)\b", 2, "as we move forward"),
    (r"\bin an era (of|where)\b", 2, "in an era of"),
    (r"\bdigital age\b", 1, "digital age"),
    (r"\bshed(s|ding)? light on\b", 2, "shed light on"),
    (r"\bdeep(er)? understanding\b", 1, "deeper understanding"),
    (r"\bbroader implications\b", 2, "broader implications"),
    (r"\bprofound (impact|implications|effect)\b", 2, "profound impact"),
    (r"\blasting (impact|impression|legacy)\b", 1, "lasting impact"),
    (r"\bcornerstone of\b", 2, "cornerstone of"),
    (r"\bbeacon of\b", 3, "beacon of"),
    (r"\bthe advent of\b", 2, "the advent of"),
    (r"\bcritical thinking\b", 1, "critical thinking"),
    (r"\bwell-being\b", 1, "well-being"),
    (r"\bstakeholders\b", 1, "stakeholders"),
    (r"\bsynergy\b", 2, "synergy"),
    (r"\butiliz(e|es|ed|ing|ation)\b", 1, "utilize"),
    (r"\bfacilitat(e|es|ed|ing)\b", 1, "facilitate"),
    (r"\bencompass(es|ed|ing)?\b", 1, "encompass"),
    (r"\boverall,\b", 1, "overall,"),
    (r"\bin conclusion\b", 2, "in conclusion"),
    (r"\bto sum up\b", 1, "to sum up"),
    (r"\bin summary\b", 2, "in summary"),
    (r"\bin essence\b", 2, "in essence"),
    (r"\bultimately\b", 1, "ultimately"),
    (r"\bcannot be overstated\b", 3, "cannot be overstated"),
    (r"\bAs an AI( language model)?\b", 3, "As an AI"),
    (r"\bwhile .{3,60} offers? (numerous|many|several) (benefits|advantages)\b", 3, "while X offers benefits"),
    (r"\bstrik(e|es|ing) a balance\b", 2, "striking a balance"),
    (r"\bcareful consideration\b", 2, "careful consideration"),
    (r"\bwide (range|array|variety) of\b", 1, "wide range of"),
    (r"\bdiverse (range|array|set) of\b", 2, "diverse range of"),
    (r"\bboast(s|ed|ing)?\b", 2, "boasts"),
    (r"\bvibrant\b", 1, "vibrant"),
    (r"\bbustling\b", 2, "bustling"),
    (r"\bnestled\b", 2, "nestled"),
    (r"\bbreathtaking\b", 1, "breathtaking"),
    (r"\bcaptivating\b", 2, "captivating"),
    (r"\bremarkable\b", 1, "remarkable"),
    (r"\benduring\b", 1, "enduring"),
    (r"\baims? to (explore|examine|provide|highlight|shed)\b", 2, "aims to explore"),
    (r"\bthis (essay|article|paper|section) (will|explores|examines|discusses|highlights)\b", 2, "this essay explores"),
]

# Τυπικοί σύνδεσμοι στην ΑΡΧΗ πρότασης — υψηλή πυκνότητα = AI
CONNECTORS_EN = [
    "however", "moreover", "furthermore", "additionally", "in addition",
    "consequently", "therefore", "thus", "hence", "nevertheless",
    "nonetheless", "in conclusion", "in summary", "overall", "ultimately",
    "importantly", "notably", "firstly", "secondly", "thirdly", "finally",
    "similarly", "conversely", "in contrast", "on the other hand",
    "as a result", "for instance", "for example", "in essence",
    "significantly", "subsequently", "meanwhile", "in fact",
]

CONTRACTIONS_EN = re.compile(
    r"\b(i'm|i've|i'll|i'd|you're|you've|you'll|you'd|he's|she's|it's|we're|"
    r"we've|we'll|we'd|they're|they've|they'll|they'd|that's|there's|here's|"
    r"what's|who's|where's|how's|let's|don't|doesn't|didn't|can't|couldn't|"
    r"won't|wouldn't|shouldn't|isn't|aren't|wasn't|weren't|haven't|hasn't|"
    r"hadn't|mustn't|needn't|ain't|gonna|wanna|gotta|kinda|sorta|dunno|"
    r"y'all|c'mon|'cause|could've|would've|should've|might've)\b",
    re.IGNORECASE)

INFORMAL_EN = re.compile(
    r"\b(lol|lmao|omg|btw|tbh|idk|imo|imho|fyi|asap|stuff|guys|cool|awesome|"
    r"yeah|yep|nope|ok(ay)?|hmm+|umm+|uh|huh|damn|crap|freaking|frickin|"
    r"honestly|literally just|like,|you know,|i mean,|anyway,|anyways)\b",
    re.IGNORECASE)

FIRST_PERSON_STORY_EN = re.compile(
    r"\b(i remember|i think|i believe|i feel|i felt|i guess|i noticed|"
    r"my (mom|dad|mother|father|friend|brother|sister|professor|boss|dog|cat)|"
    r"last (year|week|month|summer|night)|when i was|i once|i tried|i had to|"
    r"in my experience|personally,)\b",
    re.IGNORECASE)

# ---------------------------------------------------------------------------
# AI φράσεις / λεξιλόγιο — ΕΛΛΗΝΙΚΑ
# ---------------------------------------------------------------------------

AI_PHRASES_EL: List[Tuple[str, int, str]] = [
    # -- Κλισέ κατακλείδας / εισαγωγής --
    (r"\bεν κατακλείδι\b", 3, "εν κατακλείδι"),
    (r"\bσυμπερασματικά\b", 2, "συμπερασματικά"),
    (r"\bανακεφαλαιώνοντας\b", 2, "ανακεφαλαιώνοντας"),
    (r"\bεν ολίγοις\b", 2, "εν ολίγοις"),
    (r"\bείναι σημαντικό να (σημειωθεί|τονιστεί|αναφερθεί|επισημανθεί)\b", 3, "είναι σημαντικό να σημειωθεί"),
    (r"\bαξίζει να σημειωθεί\b", 3, "αξίζει να σημειωθεί"),
    (r"\bαξίζει να αναφερθεί\b", 2, "αξίζει να αναφερθεί"),
    (r"\bθα πρέπει να σημειωθεί\b", 2, "θα πρέπει να σημειωθεί"),
    (r"\bστη σημερινή εποχή\b", 3, "στη σημερινή εποχή"),
    (r"\bστον σύγχρονο κόσμο\b", 3, "στον σύγχρονο κόσμο"),
    (r"\bστη σύγχρονη εποχή\b", 2, "στη σύγχρονη εποχή"),
    (r"\bσε έναν κόσμο που\b", 2, "σε έναν κόσμο που"),
    (r"\bστο σημερινό ψηφιακό\b", 2, "στο σημερινό ψηφιακό"),
    # -- Ρόλοι και σημασίες --
    (r"\bδιαδραματίζ\w+ (καθοριστικό|σημαντικό|κομβικό|κρίσιμο|ζωτικό|καίριο|πρωταγωνιστικό) ρόλο\b", 3, "διαδραματίζει καθοριστικό ρόλο"),
    (r"\bπαίζει (καθοριστικό|σημαντικό|κομβικό|κρίσιμο|ζωτικό|καίριο) ρόλο\b", 2, "παίζει σημαντικό ρόλο"),
    (r"\bζωτικής σημασίας\b", 2, "ζωτικής σημασίας"),
    (r"\bκαθοριστικής σημασίας\b", 2, "καθοριστικής σημασίας"),
    (r"\bκομβικό ρόλο\b", 2, "κομβικό ρόλο"),
    (r"\bαναπόσπαστο (κομμάτι|μέρος|τμήμα)\b", 3, "αναπόσπαστο κομμάτι"),
    (r"\bαποτελεί (βασικό|σημαντικό|κύριο|θεμελιώδη|θεμέλιο)\b", 2, "αποτελεί βασικό ..."),
    (r"\bακρογωνιαίο λίθο\b", 3, "ακρογωνιαίος λίθος"),
    # -- Λόγιο AI λεξιλόγιο --
    (r"\bκαθίσταται\b", 2, "καθίσταται"),
    (r"\bδύναται\b", 2, "δύναται"),
    (r"\bσυνιστά\b", 2, "συνιστά"),
    (r"\bεπιπροσθέτως\b", 3, "επιπροσθέτως"),
    (r"\bεν συνεχεία\b", 2, "εν συνεχεία"),
    (r"\bεν γένει\b", 2, "εν γένει"),
    (r"\bπρωτίστως\b", 2, "πρωτίστως"),
    (r"\bαδιαμφισβήτητα\b", 3, "αδιαμφισβήτητα"),
    (r"\bαναμφισβήτητα\b", 2, "αναμφισβήτητα"),
    (r"\bαναμφίβολα\b", 2, "αναμφίβολα"),
    (r"\bαδήριτη ανάγκη\b", 3, "αδήριτη ανάγκη"),
    (r"\bπολύπλευρ\w+\b", 2, "πολύπλευρος"),
    (r"\bπολυδιάστατ\w+\b", 2, "πολυδιάστατος"),
    (r"\bολιστικ\w+ προσέγγιση\b", 3, "ολιστική προσέγγιση"),
    (r"\bσφαιρικ\w+ (εικόνα|προσέγγιση|κατανόηση)\b", 2, "σφαιρική εικόνα"),
    (r"\bραγδαί\w+\b", 2, "ραγδαία"),
    (r"\bαλματώδ\w+\b", 2, "αλματώδης"),
    (r"\bολοένα και\b", 2, "ολοένα και"),
    (r"\bδιαρκώς αυξανόμεν\w+\b", 2, "διαρκώς αυξανόμενος"),
    (r"\bσυνεχώς εξελισσόμεν\w+\b", 3, "συνεχώς εξελισσόμενος"),
    (r"\bταχέως (εξελισσόμεν|μεταβαλλόμεν)\w+\b", 3, "ταχέως εξελισσόμενος"),
    # -- Εύρος / πληθώρα --
    (r"\bπληθώρα\b", 2, "πληθώρα"),
    (r"\bευρύ φάσμα\b", 2, "ευρύ φάσμα"),
    (r"\bμεγάλο εύρος\b", 1, "μεγάλο εύρος"),
    (r"\bποικίλ\w+ (τομείς|πτυχές|τρόπους|μορφές)\b", 2, "ποικίλους τομείς"),
    (r"\bπτυχές της (ζωής|καθημερινότητας)\b", 2, "πτυχές της ζωής"),
    (r"\bσε όλους τους τομείς\b", 1, "σε όλους τους τομείς"),
    # -- Οφέλη/προκλήσεις (δομή LLM essay) --
    (r"\bπροσφέρει (πολλαπλά|σημαντικά|αναρίθμητα|πολλά) (οφέλη|πλεονεκτήματα)\b", 3, "προσφέρει πολλαπλά οφέλη"),
    (r"\b(σημαντικές|μεγάλες|νέες) προκλήσεις\b", 2, "σημαντικές προκλήσεις"),
    (r"\bπροκλήσεις και ευκαιρίες\b", 3, "προκλήσεις και ευκαιρίες"),
    (r"\bοφέλη και (κινδύνους|προκλήσεις|μειονεκτήματα)\b", 2, "οφέλη και κινδύνους"),
    (r"\bδίκοπο μαχαίρι\b", 2, "δίκοπο μαχαίρι"),
    (r"\bανοίγει (νέους ορίζοντες|τον δρόμο|νέες προοπτικές)\b", 3, "ανοίγει νέους ορίζοντες"),
    (r"\bφέρνει επανάσταση\b", 2, "φέρνει επανάσταση"),
    (r"\bαλλάζει (ριζικά|δραματικά)\b", 2, "αλλάζει ριζικά"),
    (r"\bέχει τη δυνατότητα να\b", 1, "έχει τη δυνατότητα να"),
    (r"\bμπορεί να συμβάλει (σημαντικά|καθοριστικά|ουσιαστικά)\b", 2, "μπορεί να συμβάλει σημαντικά"),
    (r"\bσυμβάλλει (σημαντικά|καθοριστικά|ουσιαστικά|τα μέγιστα)\b", 2, "συμβάλλει σημαντικά"),
    (r"\bκρίνεται (απαραίτητη|αναγκαία|σκόπιμη|επιτακτική)\b", 2, "κρίνεται απαραίτητη"),
    (r"\bκαθίσταται (σαφές|αναγκαί|επιτακτικ)\w*\b", 3, "καθίσταται σαφές"),
    (r"\bείναι επιτακτική ανάγκη\b", 3, "είναι επιτακτική ανάγκη"),
    (r"\bλαμβάνοντας υπόψη\b", 1, "λαμβάνοντας υπόψη"),
    (r"\bσε συνδυασμό με\b", 1, "σε συνδυασμό με"),
    (r"\bμε γνώμονα\b", 2, "με γνώμονα"),
    (r"\bυπό το πρίσμα\b", 2, "υπό το πρίσμα"),
    (r"\bστο πλαίσιο (της|του|των)\b", 1, "στο πλαίσιο της"),
    (r"\bτόσο σε .{2,30} όσο και\b", 2, "τόσο σε ... όσο και"),
    (r"\bτόσο (η|ο|το|οι|τα) .{2,30} όσο και\b", 2, "τόσο ... όσο και"),
    (r"\bαφενός .{2,60} αφετέρου\b", 2, "αφενός ... αφετέρου"),
    (r"\bγίνεται (ολοένα και )?(εμφανές|σαφές|αντιληπτό|κατανοητό) ότι\b", 3, "γίνεται σαφές ότι"),
    (r"\bδεν είναι υπερβολή να πούμε\b", 3, "δεν είναι υπερβολή να πούμε"),
    (r"\bμε άλλα λόγια\b", 1, "με άλλα λόγια"),
    (r"\bόπως (αναφέρθηκε|προαναφέρθηκε|σημειώθηκε) (παραπάνω|προηγουμένως|ανωτέρω)?\b", 2, "όπως προαναφέρθηκε"),
    (r"\bως εκ τούτου\b", 2, "ως εκ τούτου"),
    (r"\bκατ' επέκταση\b", 2, "κατ' επέκταση"),
    (r"\bεκ των ων ουκ άνευ\b", 3, "εκ των ων ουκ άνευ"),
    (r"\bτεχνητή νοημοσύνη\b", 1, "τεχνητή νοημοσύνη"),
    (r"\bη παρούσα (εργασία|μελέτη|ενότητα) (στοχεύει|εξετάζει|αναλύει|παρουσιάζει)\b", 2, "η παρούσα εργασία στοχεύει"),
]

CONNECTORS_EL = [
    "επιπλέον", "επιπροσθέτως", "επίσης", "ακόμη", "ακόμα", "παράλληλα",
    "ωστόσο", "εντούτοις", "παρόλα αυτά", "παρ' όλα αυτά", "συνεπώς",
    "επομένως", "κατά συνέπεια", "ως εκ τούτου", "εν κατακλείδι",
    "συμπερασματικά", "τέλος", "αρχικά", "πρώτον", "δεύτερον", "τρίτον",
    "αντιθέτως", "αντίθετα", "από την άλλη πλευρά", "από τη μία πλευρά",
    "για παράδειγμα", "παραδείγματος χάριν", "εν συνεχεία", "στη συνέχεια",
    "εν γένει", "γενικότερα", "ειδικότερα", "αναμφίβολα", "αναμφισβήτητα",
    "σαφώς", "προφανώς", "φυσικά", "βεβαίως",
]

# Ελληνικές συντμήσεις/προφορικότητα (απόστροφος = προφορικός λόγος)
CONTRACTIONS_EL = re.compile(
    r"(\bγι'|\bκι\b|\bαπ'|\bσ'\s|\bμ'\s|\bτ'\s|\bν'\s|\bθα 'ναι|\bνα 'ναι|"
    r"\b'ρθει|\bείν'|\bέτσ'|\bόλ'|\bπάν'|\bκάν')",
    re.IGNORECASE)

INFORMAL_EL = re.compile(
    r"\b(ρε|βρε|ε ναι|ελα|έλα|λοιπόν|βασικά|ας πούμε|ξέρω γω|ξερωγω|"
    r"εντάξει|οκ|οκέι|τέλος πάντων|τεσπα|δηλαδή τι|σιγά|χαλαρά|"
    r"φάση|κουλό|τρελό|ωραίος|μπράβο|άντε|οπότε ναι|και καλά|"
    r"πολύ απλά|να σου πω|κοίτα|άκου|αλήθεια|ειλικρινά|χαχα+|χεχε)\b",
    re.IGNORECASE)

FIRST_PERSON_STORY_EL = re.compile(
    r"\b(θυμάμαι|νομίζω|πιστεύω πως|νιώθω|ένιωσα|μου φάνηκε|μου άρεσε|"
    r"η μαμά μου|ο μπαμπάς μου|η μάνα μου|ο πατέρας μου|ο φίλος μου|"
    r"η φίλη μου|ο αδερφός μου|η αδερφή μου|πέρσι|πρόπερσι|χθες|προχθές|"
    r"όταν ήμουν|μια φορά|προσπάθησα|έπρεπε να|κατά τη γνώμη μου|"
    r"προσωπικά|για μένα)\b",
    re.IGNORECASE)

# Βιβλιογραφικές παραπομπές — (Smith, 2019) / [12] / (Παπαδόπουλος, 2020)
CITATIONS_RE = re.compile(
    r"\(\s*[A-ZΑ-Ω][\w''-]+(?:\s+(?:et al\.?|κ\.ά\.|&|and|και)\s*[\w''-]*)?,?\s+(?:19|20)\d{2}[a-z]?\s*\)"
    r"|\[\d{1,3}\]")

# Υπολείμματα Markdown / chatbot μορφοποίησης
MARKDOWN_RE = re.compile(r"(\*\*[^*\n]+\*\*|^#{1,4}\s|^\s*[-•▪]\s+\w|^\s*\d+\.\s+[Α-ΩA-Z])", re.MULTILINE)

# Σημάδια ανθρώπινης "προχειρότητας" (τα LLM δεν κάνουν τέτοια λάθη)
SLOPPINESS_PATTERNS = [
    re.compile(r"  +"),                      # διπλά κενά
    re.compile(r" [,.;:!]"),                  # κενό πριν από σημείο στίξης
    re.compile(r"[a-zα-ωά-ώ],[a-zα-ωά-ώ]"),   # λείπει κενό μετά από κόμμα
    re.compile(r"[!?;]{2,}"),                 # πολλαπλά !!/;;
    re.compile(r"(?<=[.!?;]) [a-zα-ωά-ώ]"),   # πρόταση που ξεκινά με πεζό
    re.compile(r"\bi\b(?= )"),                # αγγλικό "i" πεζό
    re.compile(r"\.\.\.(?!\.)"),              # χειροκίνητα αποσιωπητικά
]

# ---------------------------------------------------------------------------
# Οδηγός διόρθωσης: εναλλακτικές διατυπώσεις για τις πιο "βαριές" (weight 3)
# κλισέ φράσεις — αυτές θεωρούνται σχεδόν αποκλειστικά AI, άρα αξίζουν
# συγκεκριμένη πρόταση αντικατάστασης αντί για γενική συμβουλή.
# ---------------------------------------------------------------------------

REWRITE_SUGGESTIONS_EN: Dict[str, List[str]] = {
    "delve into": ["look at", "examine", "explore"],
    "it is important to note": ["(cut it — just state the fact)"],
    "it's worth noting": ["(cut it — just state the fact)"],
    "in today's ... world": ["(cut it, or name the actual time/context)"],
    "ever-evolving": ["changing", "developing"],
    "serves as a testament": ["shows", "demonstrates"],
    "stands as a testament": ["shows", "demonstrates"],
    "navigating the complexities": ["dealing with", "working through"],
    "plays a crucial role": ["matters for", "affects", "helps determine"],
    "a tapestry of": ["a mix of", "a range of"],
    "rich tapestry": ["a mix of", "a variety of"],
    "unlock the potential": ["enable", "make possible"],
    "harness the power": ["use"],
    "in the realm of": ["in"],
    "underscore": ["show", "highlight"],
    "multifaceted": ["(name the actual aspects instead)"],
    "beacon of": ["example of", "model for"],
    "cannot be overstated": ["(state the actual number/fact instead)"],
    "As an AI": ["(remove — rewrite in your own voice)"],
    "while X offers benefits": ["(state the benefit and drawback as two plain sentences)"],
}

REWRITE_SUGGESTIONS_EL: Dict[str, List[str]] = {
    "εν κατακλείδι": ["(κόψε το — πες κατευθείαν το συμπέρασμα)"],
    "είναι σημαντικό να σημειωθεί": ["(κόψε το — πες την πρόταση απευθείας)"],
    "αξίζει να σημειωθεί": ["(κόψε το — πες την πρόταση απευθείας)"],
    "στη σημερινή εποχή": ["(κόψε το, ή όρισε τη συγκεκριμένη περίοδο)"],
    "στον σύγχρονο κόσμο": ["(κόψε το, ή όρισε το συγκεκριμένο πλαίσιο)"],
    "διαδραματίζει καθοριστικό ρόλο": ["επηρεάζει", "συμβάλλει σε"],
    "αναπόσπαστο κομμάτι": ["μέρος", "στοιχείο"],
    "ακρογωνιαίος λίθος": ["βάση", "θεμέλιο"],
    "επιπροσθέτως": ["επίσης", "ακόμη"],
    "αδιαμφισβήτητα": ["σαφώς", "(ή διέγραψέ το)"],
    "αδήριτη ανάγκη": ["ανάγκη"],
    "ολιστική προσέγγιση": ["ολοκληρωμένη προσέγγιση", "(περίγραψε τι περιλαμβάνει)"],
    "συνεχώς εξελισσόμενος": ["που αλλάζει", "που εξελίσσεται"],
    "ταχέως εξελισσόμενος": ["που αλλάζει γρήγορα"],
    "προσφέρει πολλαπλά οφέλη": ["(ονόμασε τα συγκεκριμένα οφέλη)"],
    "προκλήσεις και ευκαιρίες": ["(περίγραψε τη συγκεκριμένη πρόκληση ή ευκαιρία)"],
    "ανοίγει νέους ορίζοντες": ["επιτρέπει", "κάνει δυνατό"],
    "καθίσταται σαφές": ["φαίνεται", "είναι σαφές"],
    "είναι επιτακτική ανάγκη": ["χρειάζεται"],
    "γίνεται σαφές ότι": ["φαίνεται ότι"],
    "δεν είναι υπερβολή να πούμε": ["(κόψε το — πες την πρόταση απευθείας)"],
    "εκ των ων ουκ άνευ": ["απαραίτητο"],
}

# Γενική συμβουλή ανά κατηγορία δείκτη (χρησιμοποιείται όταν δεν υπάρχει
# συγκεκριμένη πρόταση αντικατάστασης φράσης — π.χ. burstiness, em-dash).
FEATURE_ADVICE: Dict[str, Dict[str, str]] = {
    "ai_phrases": {
        "en": "Replace stock phrases with direct, specific wording. Avoid vague "
              "intensifiers (holistic, multifaceted, seamless) and cliché metaphors "
              "(tapestry, testament, forefront) — just say what you mean plainly.",
        "el": "Αντικατέστησε τις έτοιμες εκφράσεις με άμεση, συγκεκριμένη διατύπωση. "
              "Απόφυγε γενικόλογα επίθετα («ολιστικός», «πολύπλευρος») και μεταφορικά "
              "κλισέ («ανοίγει νέους ορίζοντες», «ακρογωνιαίος λίθος») — πες απευθείας "
              "τι εννοείς.",
        "de": 'Ersetze Standardfloskeln durch direkte, konkrete Formulierungen. Vermeide vage Verstärker (ganzheitlich, vielschichtig, nahtlos) und abgenutzte Metaphern (Mosaik, Zeugnis, Speerspitze) — sag einfach, was du meinst.',
        "fr": 'Remplacez les formules toutes faites par une formulation directe et précise. Évitez les intensifs vagues (holistique, multidimensionnel, fluide) et les métaphores clichés (mosaïque, témoignage, fer de lance) — dites simplement ce que vous voulez dire.',
        "pt": 'Substitua expressões feitas por uma formulação direta e concreta. Evite intensificadores vagos (holístico, multifacetado, fluido) e metáforas gastas (tapeçaria, testemunho, vanguarda) — diga simplesmente o que quer dizer.',
    },
    "connectors": {
        "en": "Cut back on sentence-opening connectors (However/Moreover/Therefore). "
              "Start some sentences directly with the subject instead.",
        "el": "Μείωσε τους συνδέσμους στην αρχή προτάσεων (Ωστόσο/Επιπλέον/Συνεπώς). "
              "Ξεκίνα μερικές προτάσεις κατευθείαν με το υποκείμενο.",
        "de": 'Verwende weniger Konnektoren am Satzanfang (Jedoch/Außerdem/Daher). Beginne einige Sätze direkt mit dem Subjekt.',
        "fr": 'Réduisez les connecteurs en début de phrase (Cependant/De plus/Par conséquent). Commencez certaines phrases directement par le sujet.',
        "pt": 'Reduza os conectores no início das frases (Contudo/Além disso/Portanto). Comece algumas frases diretamente pelo sujeito.',
    },
    "burstiness": {
        "en": "Mix short and long sentences. A blunt 4-5 word sentence between "
              "longer ones breaks the uniform rhythm.",
        "el": "Ανάμειξε μικρές και μεγάλες προτάσεις. Μια κοφτή πρόταση 4-5 λέξεων "
              "ανάμεσα σε μεγαλύτερες σπάει το ομοιόμορφο ρυθμό.",
        "de": 'Mische kurze und lange Sätze. Ein knapper Satz mit 4–5 Wörtern zwischen längeren bricht den gleichförmigen Rhythmus.',
        "fr": 'Alternez phrases courtes et longues. Une phrase sèche de 4–5 mots entre des phrases plus longues casse le rythme uniforme.',
        "pt": 'Alterne frases curtas e longas. Uma frase seca de 4–5 palavras entre frases mais longas quebra o ritmo uniforme.',
    },
    "rule_of_three": {
        "en": "Avoid 'X, Y, and Z' triads — use two items, or expand one of the "
              "three into its own sentence.",
        "el": "Απόφυγε τις τριάδες «Χ, Υ και Ζ» — γράψε δύο στοιχεία, ή ανάπτυξε "
              "ένα από τα τρία σε ξεχωριστή πρόταση.",
        "de": 'Vermeide Dreiergruppen „X, Y und Z“ — nenne zwei Elemente oder führe eines der drei in einem eigenen Satz aus.',
        "fr": "Évitez les triades « X, Y et Z » — citez deux éléments, ou développez l'un des trois dans une phrase à part.",
        "pt": 'Evite tríades «X, Y e Z» — use dois elementos, ou desenvolva um dos três numa frase própria.',
    },
    "em_dash": {
        "en": "Replace some em-dashes with a period, comma, or parentheses.",
        "el": "Αντικατέστησε μερικές παύλες em-dash με τελεία, κόμμα ή παρένθεση.",
        "de": 'Ersetze einige Geviertstriche durch Punkt, Komma oder Klammern.',
        "fr": 'Remplacez certains tirets cadratins par un point, une virgule ou des parenthèses.',
        "pt": 'Substitua alguns travessões por ponto final, vírgula ou parênteses.',
    },
    "paragraph_uniformity": {
        "en": "Vary paragraph length — a short 2-sentence paragraph among longer "
              "ones helps.",
        "el": "Άλλαξε το μήκος των παραγράφων — μια μικρή παράγραφος 2 προτάσεων "
              "ανάμεσα σε μεγαλύτερες βοηθάει.",
        "de": 'Variiere die Absatzlänge — ein kurzer Absatz mit 2 Sätzen zwischen längeren hilft.',
        "fr": 'Variez la longueur des paragraphes — un court paragraphe de 2 phrases entre des plus longs aide.',
        "pt": 'Varie o comprimento dos parágrafos — um parágrafo curto de 2 frases entre outros mais longos ajuda.',
    },
    "opener_repetition": {
        "en": "Don't keep starting sentences with the same word — reorder a few.",
        "el": "Μην ξεκινάς συνέχεια προτάσεις με την ίδια λέξη — άλλαξε τη σειρά "
              "όρων στην αρχή μερικών.",
        "de": 'Beginne Sätze nicht ständig mit demselben Wort — stelle bei einigen die Wortfolge um.',
        "fr": 'Ne commencez pas sans cesse vos phrases par le même mot — réorganisez-en quelques-unes.',
        "pt": 'Não comece as frases sempre com a mesma palavra — reorganize algumas.',
    },
    "markdown_remnants": {
        "en": "Remove leftover markdown formatting (**, ###, bullets) from "
              "copy-pasting.",
        "el": "Αφαίρεσε υπολείμματα μορφοποίησης (**, ###, bullets) που έμειναν "
              "από copy-paste.",
        "de": 'Entferne übrig gebliebene Markdown-Formatierung (**, ###, Aufzählungen) vom Kopieren und Einfügen.',
        "fr": 'Supprimez la mise en forme markdown restante (**, ###, puces) issue du copier-coller.',
        "pt": 'Remova a formatação markdown que sobrou do copiar e colar (**, ###, marcadores).',
    },
}


# ---------------------------------------------------------------------------
# Πολυγλωσσικά κείμενα αποτελεσμάτων
# ---------------------------------------------------------------------------
# Κάθε κείμενο που βλέπει ο χρήστης επιστρέφεται ως {"el": ..., "en": ..., ...}
# (πεδία *_i18n) ώστε το UI να αλλάζει γλώσσα χωρίς νέα ανάλυση. Για νέα
# γλώσσα: πρόσθεσε το κλειδί της στο UI_LANGS και τις μεταφράσεις εδώ, στο
# FEATURE_ADVICE και στο STRINGS του detector_academic.html — όπου λείπει,
# το UI πέφτει στα αγγλικά.

UI_LANGS = ("el", "en", "de", "fr", "pt")


def _tr(el: str, en: str, de: str = "", fr: str = "", pt: str = "") -> Dict[str, str]:
    out = {"el": el, "en": en, "de": de, "fr": fr, "pt": pt}
    return {k: v for k, v in out.items() if v}


def _fmt(templates: Dict[str, str], **params) -> Dict[str, str]:
    """Γεμίζει το ίδιο πρότυπο σε κάθε γλώσσα με τις ίδιες τιμές."""
    return {lang: tpl.format(**params) for lang, tpl in templates.items()}


FEATURE_LABELS: Dict[str, Dict[str, str]] = {
    "ai_phrases": _tr("Χαρακτηριστικές AI φράσεις & λεξιλόγιο",
                      "Characteristic AI phrases & vocabulary",
                      "Typische KI-Formulierungen & Wortschatz",
                      "Formules et vocabulaire typiques de l'IA",
                      "Expressões e vocabulário típicos de IA"),
    "connectors": _tr("Τυπικοί σύνδεσμοι σε αρχή πρότασης",
                      "Stock connectors at sentence start",
                      "Standard-Konnektoren am Satzanfang",
                      "Connecteurs convenus en début de phrase",
                      "Conectores feitos no início da frase"),
    "burstiness": _tr("Ομοιομορφία μήκους προτάσεων (burstiness)",
                      "Uniform sentence length (burstiness)",
                      "Gleichförmige Satzlänge (Burstiness)",
                      "Longueur de phrase uniforme (burstiness)",
                      "Comprimento de frase uniforme (burstiness)"),
    "rule_of_three": _tr("Τριάδες «Χ, Υ και Ζ»", "\"X, Y and Z\" triads",
                         "Dreiergruppen „X, Y und Z“", "Triades « X, Y et Z »",
                         "Tríades «X, Y e Z»"),
    "em_dash": _tr("Παύλες em-dash (—)", "Em-dashes (—)", "Geviertstriche (—)",
                   "Tirets cadratins (—)", "Travessões (—)"),
    "paragraph_uniformity": _tr("Ομοιομορφία μήκους παραγράφων",
                                "Uniform paragraph length",
                                "Gleichförmige Absatzlänge",
                                "Longueur de paragraphe uniforme",
                                "Comprimento de parágrafo uniforme"),
    "opener_repetition": _tr("Επανάληψη ίδιας πρώτης λέξης",
                             "Repeated sentence-opening word",
                             "Wiederholtes erstes Wort im Satz",
                             "Même premier mot de phrase répété",
                             "Mesma primeira palavra repetida"),
    "markdown_remnants": _tr("Μορφοποίηση chatbot (**, ###, bullets)",
                             "Chatbot formatting (**, ###, bullets)",
                             "Chatbot-Formatierung (**, ###, Aufzählungen)",
                             "Mise en forme de chatbot (**, ###, puces)",
                             "Formatação de chatbot (**, ###, marcadores)"),
    "contractions": _tr("Συντμήσεις / προφορικές συντομεύσεις",
                        "Contractions / spoken short forms",
                        "Kontraktionen / gesprochene Kurzformen",
                        "Contractions / formes orales abrégées",
                        "Contrações / formas orais abreviadas"),
    "informal": _tr("Προφορικές / άτυπες εκφράσεις", "Spoken / informal expressions",
                    "Umgangssprachliche / informelle Ausdrücke",
                    "Expressions orales / familières",
                    "Expressões orais / informais"),
    "sloppiness": _tr("Τυπογραφικές ατέλειες (κενά, πεζά, στίξη)",
                      "Typographic slips (spacing, lowercase, punctuation)",
                      "Typografische Unsauberkeiten (Leerzeichen, Kleinschreibung, Zeichensetzung)",
                      "Imperfections typographiques (espaces, minuscules, ponctuation)",
                      "Imperfeições tipográficas (espaços, minúsculas, pontuação)"),
    "personal_story": _tr("Προσωπική αφήγηση / εμπειρίες",
                          "Personal narrative / experiences",
                          "Persönliche Erzählung / Erfahrungen",
                          "Récit personnel / expériences",
                          "Narrativa pessoal / experiências"),
    "citations": _tr("Βιβλιογραφικές παραπομπές", "Bibliographic citations",
                     "Literaturverweise", "Références bibliographiques",
                     "Referências bibliográficas"),
}

VERDICTS: Dict[str, Dict[str, str]] = {
    "empty": _tr("Δεν βρέθηκε κείμενο", "No text found", "Kein Text gefunden",
                 "Aucun texte trouvé", "Nenhum texto encontrado"),
    "ai_likely": _tr("Πιθανώς AI-generated κείμενο", "Likely AI-generated text",
                     "Wahrscheinlich KI-generierter Text",
                     "Texte probablement généré par IA",
                     "Texto provavelmente gerado por IA"),
    "ai_signs": _tr("Ενδείξεις AI-generated κειμένου", "Signs of AI-generated text",
                    "Hinweise auf KI-generierten Text",
                    "Indices de texte généré par IA",
                    "Indícios de texto gerado por IA"),
    "uncertain": _tr("Αβέβαιο / μικτό αποτέλεσμα", "Uncertain / mixed result",
                     "Unsicheres / gemischtes Ergebnis",
                     "Résultat incertain / mitigé",
                     "Resultado incerto / misto"),
    "human_probable": _tr("Μάλλον ανθρώπινο κείμενο", "Probably human-written text",
                          "Eher von Menschen geschriebener Text",
                          "Texte plutôt écrit par un humain",
                          "Texto provavelmente humano"),
    "human_likely": _tr("Πιθανώς ανθρώπινο κείμενο", "Likely human-written text",
                        "Wahrscheinlich von Menschen geschriebener Text",
                        "Texte probablement écrit par un humain",
                        "Texto muito provavelmente humano"),
}

MIXED_VERDICT = _tr(
    "Μικτό κείμενο — ενδείξεις AI σε {n_ai} από {total} ενότητες",
    "Mixed text — signs of AI in {n_ai} of {total} sections",
    "Gemischter Text — KI-Hinweise in {n_ai} von {total} Abschnitten",
    "Texte mixte — indices d'IA dans {n_ai} sections sur {total}",
    "Texto misto — indícios de IA em {n_ai} de {total} secções")

LANGUAGE_NAMES: Dict[str, Dict[str, str]] = {
    "greek": _tr("Ελληνικά", "Greek", "Griechisch", "Grec", "Grego"),
    "english": _tr("Αγγλικά", "English", "Englisch", "Anglais", "Inglês"),
}

CONNECTOR_HIT = _tr("σύνδεσμος «{c}»", "connector \"{c}\"", "Konnektor „{c}“",
                    "connecteur « {c} »", "conector «{c}»")

# Λεπτομέρειες δεικτών: πρότυπα με τις ίδιες παραμέτρους σε κάθε γλώσσα
DETAILS: Dict[str, Dict[str, str]] = {
    "ai_phrases": _tr(
        "{occ} εμφανίσεις, σταθμισμένη πυκνότητα {density:.1f}/1000 λέξεις",
        "{occ} occurrences, weighted density {density:.1f}/1000 words",
        "{occ} Vorkommen, gewichtete Dichte {density:.1f}/1000 Wörter",
        "{occ} occurrences, densité pondérée {density:.1f}/1000 mots",
        "{occ} ocorrências, densidade ponderada {density:.1f}/1000 palavras"),
    "connectors": _tr(
        "{hits}/{total} προτάσεις ({pct:.0f}%) ξεκινούν με σύνδεσμο",
        "{hits}/{total} sentences ({pct:.0f}%) start with a connector",
        "{hits}/{total} Sätze ({pct:.0f}%) beginnen mit einem Konnektor",
        "{hits}/{total} phrases ({pct:.0f} %) commencent par un connecteur",
        "{hits}/{total} frases ({pct:.0f}%) começam com um conector"),
    "burstiness": _tr(
        "CV μήκους προτάσεων = {cv:.2f} (χαμηλό = ομοιόμορφο = AI)",
        "Sentence-length CV = {cv:.2f} (low = uniform = AI)",
        "VK der Satzlänge = {cv:.2f} (niedrig = gleichförmig = KI)",
        "CV de la longueur des phrases = {cv:.2f} (faible = uniforme = IA)",
        "CV do comprimento das frases = {cv:.2f} (baixo = uniforme = IA)"),
    "few_sentences": _tr(
        "Πολύ λίγες προτάσεις για μέτρηση", "Too few sentences to measure",
        "Zu wenige Sätze zum Messen", "Trop peu de phrases pour mesurer",
        "Frases insuficientes para medir"),
    "rule_of_three": _tr(
        "{n} τριάδες σε {total} προτάσεις", "{n} triads in {total} sentences",
        "{n} Dreiergruppen in {total} Sätzen", "{n} triades dans {total} phrases",
        "{n} tríades em {total} frases"),
    "em_dash": _tr(
        "{n} em-dashes ({density:.1f}/1000 λέξεις)",
        "{n} em-dashes ({density:.1f}/1000 words)",
        "{n} Geviertstriche ({density:.1f}/1000 Wörter)",
        "{n} tirets cadratins ({density:.1f}/1000 mots)",
        "{n} travessões ({density:.1f}/1000 palavras)"),
    "pdf_skipped": _tr(
        "Παραλείπεται σε PDF (αναξιόπιστα όρια παραγράφων)",
        "Skipped for PDF (unreliable paragraph boundaries)",
        "Bei PDF übersprungen (unzuverlässige Absatzgrenzen)",
        "Ignoré pour les PDF (limites de paragraphe peu fiables)",
        "Ignorado em PDF (limites de parágrafo pouco fiáveis)"),
    "paragraph_uniformity": _tr(
        "CV μήκους παραγράφων = {cv:.2f} ({n} παράγραφοι)",
        "Paragraph-length CV = {cv:.2f} ({n} paragraphs)",
        "VK der Absatzlänge = {cv:.2f} ({n} Absätze)",
        "CV de la longueur des paragraphes = {cv:.2f} ({n} paragraphes)",
        "CV do comprimento dos parágrafos = {cv:.2f} ({n} parágrafos)"),
    "few_paragraphs": _tr(
        "Λίγες παράγραφοι για μέτρηση", "Too few paragraphs to measure",
        "Zu wenige Absätze zum Messen", "Trop peu de paragraphes pour mesurer",
        "Parágrafos insuficientes para medir"),
    "opener_repetition": _tr(
        "Συχνότερη πρώτη λέξη: «{word}» ({pct:.0f}%)",
        "Most common first word: \"{word}\" ({pct:.0f}%)",
        "Häufigstes erstes Wort: „{word}“ ({pct:.0f}%)",
        "Premier mot le plus fréquent : « {word} » ({pct:.0f} %)",
        "Primeira palavra mais frequente: «{word}» ({pct:.0f}%)"),
    "markdown_remnants": _tr(
        "{n} στοιχεία μορφοποίησης markdown", "{n} markdown formatting elements",
        "{n} Markdown-Formatierungselemente", "{n} éléments de mise en forme markdown",
        "{n} elementos de formatação markdown"),
    "contractions": _tr(
        "{n} συντμήσεις", "{n} contractions", "{n} Kontraktionen",
        "{n} contractions", "{n} contrações"),
    "informal": _tr(
        "{n} άτυπες εκφράσεις", "{n} informal expressions",
        "{n} umgangssprachliche Ausdrücke", "{n} expressions familières",
        "{n} expressões informais"),
    "sloppiness": _tr(
        "{n} μικρο-ατέλειες", "{n} minor slips", "{n} kleine Unsauberkeiten",
        "{n} petites imperfections", "{n} pequenas imperfeições"),
    "personal_story": _tr(
        "{n} προσωπικές αναφορές", "{n} personal references",
        "{n} persönliche Bezüge", "{n} références personnelles",
        "{n} referências pessoais"),
    "citations": _tr(
        "{n} παραπομπές τύπου (Όνομα, έτος) ή [n]",
        "{n} citations like (Name, year) or [n]",
        "{n} Verweise wie (Name, Jahr) oder [n]",
        "{n} références du type (Nom, année) ou [n]",
        "{n} referências do tipo (Nome, ano) ou [n]"),
}


def _detail(key: str, **params) -> Dict[str, str]:
    return _fmt(DETAILS[key], **params)


# ---------------------------------------------------------------------------
# Βοηθητικά
# ---------------------------------------------------------------------------

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _cv(values: List[float]) -> Optional[float]:
    """Συντελεστής διακύμανσης (std/mean)."""
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    if mean == 0:
        return None
    return statistics.stdev(values) / mean


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _score_from_signals(ai_features: List["Feature"], human_features: List["Feature"],
                         reliability: float) -> float:
    """Το ίδιο formula βαθμολόγησης με το _analyze_core, απομονωμένο ώστε να
    μπορεί να ξανατρέχει με μεταβαλλόμενα χαρακτηριστικά (βλ. build_revision_guide)."""
    total_w = sum(f.weight for f in ai_features)
    ai_signal = sum(f.score * f.weight for f in ai_features) / total_w if total_w else 0.0

    total_hw = sum(f.weight for f in human_features)
    human_signal = sum(f.score * f.weight for f in human_features) / total_hw if total_hw else 0.0

    raw = ai_signal - 0.45 * human_signal
    score01 = _logistic((raw - 0.28) * 10)
    score01 = 0.5 + (score01 - 0.5) * (0.4 + 0.6 * reliability)
    return score01 * 100


# ---------------------------------------------------------------------------
# Εξαγωγή χαρακτηριστικών
# ---------------------------------------------------------------------------

class Feature:
    """Ένα χαρακτηριστικό ανίχνευσης: score 0..1 (1 = μοιάζει με AI ή, για
    ανθρώπινα σημάδια, 1 = μοιάζει με άνθρωπο), βάρος, και λεπτομέρειες."""

    def __init__(self, name: str, label: str, score: float, weight: float,
                 detail=None, occurrences: int = 0,
                 examples: Optional[List[str]] = None):
        self.name = name
        self.label = label
        self.label_i18n = FEATURE_LABELS.get(name, {lang: label for lang in UI_LANGS})
        self.score = _clamp(score)
        self.weight = weight
        # detail: απλό κείμενο ή {"el": ..., "en": ...}
        if isinstance(detail, dict):
            self.detail_i18n = detail
            self.detail = detail.get("el", "")
        else:
            self.detail = detail or ""
            self.detail_i18n = {lang: self.detail for lang in UI_LANGS}
        self.occurrences = occurrences
        self.examples = examples or []

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "label": self.label,
            "label_i18n": self.label_i18n,
            "score": round(self.score * 100, 1),
            "weight": self.weight,
            "detail": self.detail,
            "detail_i18n": self.detail_i18n,
            "occurrences": self.occurrences,
            "examples": self.examples[:5],
        }


def _match_phrases(text: str, phrases: List[Tuple[str, int, str]]):
    """Επιστρέφει (σταθμισμένο σύνολο, εμφανίσεις, παραδείγματα, hits/φράση)."""
    weighted = 0
    occurrences = 0
    examples = []
    per_phrase = {}
    for pattern, weight, label in phrases:
        found = re.findall(pattern, text, re.IGNORECASE)
        n = len(found)
        if n:
            weighted += weight * n
            occurrences += n
            per_phrase[label] = n
            if len(examples) < 12:
                examples.append(f"{label} (×{n})")
    return weighted, occurrences, examples, per_phrase


def extract_features(text: str, language: str, source: Optional[str] = None) -> Tuple[List[Feature], List[Feature], Dict]:
    """Επιστρέφει (AI χαρακτηριστικά, ανθρώπινα σημάδια, ενδιάμεσα στοιχεία).

    source: 'pdf' | 'docx' | None — σε PDF οι "παράγραφοι" είναι συνήθως
    σελίδες, οπότε ο δείκτης ομοιομορφίας παραγράφων απενεργοποιείται."""

    sentences = split_sentences(text, language)
    paragraphs = split_paragraphs(text)
    words = tokenize_words(text)
    n_words = max(len(words), 1)
    n_sents = max(len(sentences), 1)

    ai_features: List[Feature] = []
    human_features: List[Feature] = []

    # ---------------- 1. AI φράσεις / λεξιλόγιο ----------------
    phrases = AI_PHRASES_EL if language == "greek" else AI_PHRASES_EN
    weighted, occ, examples, per_phrase = _match_phrases(text, phrases)
    density = weighted / n_words * 1000  # σταθμισμένες εμφανίσεις ανά 1000 λέξεις
    # τυπικό AI essay: 25-60+, ανθρώπινο: 0-10
    score = 1 - math.exp(-density / 16)
    ai_features.append(Feature(
        "ai_phrases", "Χαρακτηριστικές AI φράσεις & λεξιλόγιο",
        score, 0.32,
        _detail("ai_phrases", occ=occ, density=density),
        occ, examples))

    # ---------------- 2. Σύνδεσμοι στην αρχή προτάσεων ----------------
    connectors = CONNECTORS_EL if language == "greek" else CONNECTORS_EN
    conn_hits = 0
    for s in sentences:
        s_clean = s.lstrip('«"\'"()[]- ').lower()
        if any(s_clean.startswith(c + " ") or s_clean.startswith(c + ",") for c in connectors):
            conn_hits += 1
    conn_frac = conn_hits / n_sents
    # άνθρωπος (ακαδημαϊκά): ~3-10% των προτάσεων, AI: 20-45%
    score = _clamp((conn_frac - 0.07) / 0.23)
    ai_features.append(Feature(
        "connectors", "Τυπικοί σύνδεσμοι σε αρχή πρότασης",
        score, 0.14,
        _detail("connectors", hits=conn_hits, total=len(sentences), pct=conn_frac * 100),
        conn_hits))

    # ---------------- 3. Burstiness (διακύμανση μήκους προτάσεων) ----------------
    sent_lengths = [len(tokenize_words(s)) for s in sentences]
    cv = _cv([float(x) for x in sent_lengths]) if len(sent_lengths) >= 5 else None
    if cv is not None:
        # AI: CV 0.25-0.45 (ομοιόμορφο), άνθρωπος: 0.55-0.9+
        score = _clamp((0.55 - cv) / 0.30)
        detail = _detail("burstiness", cv=cv)
        weight = 0.16
    else:
        score, detail, weight = 0.0, _detail("few_sentences"), 0.0
    ai_features.append(Feature(
        "burstiness", "Ομοιομορφία μήκους προτάσεων (burstiness)",
        score, weight, detail))

    # ---------------- 4. Rule of three (τριάδες) ----------------
    if language == "greek":
        triads = re.findall(r"[\wάέήίόύώϊϋΐΰ''-]+,\s+[\wάέήίόύώϊϋΐΰ''-]+\s+και\s+[\wάέήίόύώϊϋΐΰ''-]+", text)
    else:
        triads = re.findall(r"[\w'-]+,\s+[\w'-]+,?\s+and\s+[\w'-]+", text)
    triad_rate = len(triads) / n_sents
    score = _clamp(triad_rate / 0.30)
    ai_features.append(Feature(
        "rule_of_three", "Τριάδες «Χ, Υ και Ζ»",
        score, 0.08,
        _detail("rule_of_three", n=len(triads), total=len(sentences)),
        len(triads), triads[:4]))

    # ---------------- 5. Em-dashes και LLM στίξη ----------------
    em_dashes = len(re.findall(r"—", text)) + len(re.findall(r"\s–\s", text))
    em_density = em_dashes / n_words * 1000
    # Ένα μεμονωμένο em-dash είναι φυσιολογικό — μετράει μόνο η συστηματική χρήση
    score = _clamp((em_density - 0.8) / 4.0) if em_dashes >= 2 else 0.0
    ai_features.append(Feature(
        "em_dash", "Παύλες em-dash (—)",
        score, 0.08,
        _detail("em_dash", n=em_dashes, density=em_density),
        em_dashes))

    # ---------------- 6. Ομοιομορφία παραγράφων ----------------
    para_lengths = [len(tokenize_words(p)) for p in paragraphs]
    pcv = _cv([float(x) for x in para_lengths]) if len(para_lengths) >= 4 else None
    if source == "pdf":
        # Στα PDF η εξαγωγή δεν διατηρεί αξιόπιστα τα όρια παραγράφων
        # (συχνά "παράγραφος" = ολόκληρη σελίδα) — ο δείκτης παραλείπεται.
        score, detail, weight = 0.0, _detail("pdf_skipped"), 0.0
    elif pcv is not None:
        score = _clamp((0.50 - pcv) / 0.35)
        detail = _detail("paragraph_uniformity", cv=pcv, n=len(paragraphs))
        weight = 0.06
    else:
        score, detail, weight = 0.0, _detail("few_paragraphs"), 0.0
    ai_features.append(Feature(
        "paragraph_uniformity", "Ομοιομορφία μήκους παραγράφων",
        score, weight, detail))

    # ---------------- 7. Επανάληψη πρώτης λέξης προτάσεων ----------------
    first_words = []
    for s in sentences:
        toks = tokenize_words(s.lower())
        if toks and toks[0] not in ("i",):
            first_words.append(toks[0])
    top_share = 0.0
    top_word = ""
    if len(first_words) >= 6:
        counts = {}
        for w in first_words:
            counts[w] = counts.get(w, 0) + 1
        top_word, top_n = max(counts.items(), key=lambda kv: kv[1])
        top_share = top_n / len(first_words)
    score = _clamp((top_share - 0.18) / 0.25)
    ai_features.append(Feature(
        "opener_repetition", "Επανάληψη ίδιας πρώτης λέξης",
        score, 0.05,
        _detail("opener_repetition", word=top_word, pct=top_share * 100) if top_word else "—"))

    # ---------------- 8. Υπολείμματα Markdown ----------------
    md_hits = len(MARKDOWN_RE.findall(text))
    md_density = md_hits / max(n_words / 100, 1)
    score = _clamp(md_density / 3.0) if md_hits >= 2 else 0.0
    ai_features.append(Feature(
        "markdown_remnants", "Μορφοποίηση chatbot (**, ###, bullets)",
        score, 0.07 if md_hits >= 2 else 0.0,
        _detail("markdown_remnants", n=md_hits),
        md_hits))

    # ================= Ανθρώπινα σημάδια =================

    # ---------------- Α. Συντμήσεις ----------------
    contractions_re = CONTRACTIONS_EL if language == "greek" else CONTRACTIONS_EN
    contractions = contractions_re.findall(text)
    c_rate = len(contractions) / n_sents
    score = _clamp(c_rate / 0.5)
    human_features.append(Feature(
        "contractions", "Συντμήσεις / προφορικές συντομεύσεις",
        score, 0.30,
        _detail("contractions", n=len(contractions)),
        len(contractions)))

    # ---------------- Β. Προφορικές/άτυπες λέξεις ----------------
    informal_re = INFORMAL_EL if language == "greek" else INFORMAL_EN
    informal = informal_re.findall(text)
    score = _clamp(len(informal) / max(n_sents * 0.25, 2))
    human_features.append(Feature(
        "informal", "Προφορικές / άτυπες εκφράσεις",
        score, 0.25,
        _detail("informal", n=len(informal)),
        len(informal)))

    # ---------------- Γ. Τυπογραφική "προχειρότητα" ----------------
    sloppy = 0
    for pat in SLOPPINESS_PATTERNS:
        sloppy += len(pat.findall(text))
    score = _clamp(sloppy / 4.0)
    human_features.append(Feature(
        "sloppiness", "Τυπογραφικές ατέλειες (κενά, πεζά, στίξη)",
        score, 0.20,
        _detail("sloppiness", n=sloppy),
        sloppy))

    # ---------------- Δ. Προσωπική αφήγηση ----------------
    story_re = FIRST_PERSON_STORY_EL if language == "greek" else FIRST_PERSON_STORY_EN
    story = story_re.findall(text)
    score = _clamp(len(story) / max(n_sents * 0.2, 2))
    human_features.append(Feature(
        "personal_story", "Προσωπική αφήγηση / εμπειρίες",
        score, 0.15,
        _detail("personal_story", n=len(story)),
        len(story)))

    # ---------------- Ε. Βιβλιογραφικές παραπομπές ----------------
    citations = CITATIONS_RE.findall(text)
    score = _clamp(len(citations) / 6.0)
    human_features.append(Feature(
        "citations", "Βιβλιογραφικές παραπομπές",
        score, 0.10,
        _detail("citations", n=len(citations)),
        len(citations)))

    internals = {
        "sentences": sentences,
        "n_words": len(words),
        "n_sentences": len(sentences),
        "n_paragraphs": len(paragraphs),
        "per_phrase": per_phrase,
        "connectors": connectors,
        "phrases": phrases,
    }
    return ai_features, human_features, internals


# ---------------------------------------------------------------------------
# Επισήμανση ύποπτων προτάσεων
# ---------------------------------------------------------------------------

def highlight_sentences(internals: Dict, language: str, limit: int = 12) -> List[Dict]:
    """Βρίσκει τις προτάσεις με τα περισσότερα AI σημάδια για επισήμανση στο UI."""
    highlights = []
    phrases = internals["phrases"]
    connectors = internals["connectors"]
    for s in internals["sentences"]:
        hits = []
        for pattern, weight, label in phrases:
            if weight >= 2 and re.search(pattern, s, re.IGNORECASE):
                hits.append(label)
        hits_i18n = {lang: list(hits) for lang in UI_LANGS}
        s_clean = s.lstrip('«"\'"()[]- ').lower()
        for c in connectors:
            if s_clean.startswith(c + " ") or s_clean.startswith(c + ","):
                for lang, hit in _fmt(CONNECTOR_HIT, c=c).items():
                    hits_i18n[lang].append(hit)
                hits = hits_i18n["el"]
                break
        if hits:
            highlights.append({
                "text": s if len(s) <= 300 else s[:297] + "…",
                "hits": hits[:6],
                "hits_i18n": {lang: h[:6] for lang, h in hits_i18n.items()},
                "count": len(hits),
            })
    highlights.sort(key=lambda h: -h["count"])
    return highlights[:limit]


def build_revision_guide(ai_features: List[Feature], human_features: List[Feature],
                          reliability: float, baseline_score: float, language: str,
                          internals: Dict, limit: int = 6) -> List[Dict]:
    """Ταξινομεί τους δείκτες AI κατά ΠΡΑΓΜΑΤΙΚΗ επίδραση στο σκορ — όχι εκτίμηση:
    ξανατρέχει το ίδιο formula (_score_from_signals) με κάθε δείκτη μηδενισμένο
    και μετράει τη διαφορά. Επειδή ο συνδυασμός είναι μη-γραμμικός (λογιστική
    συνάρτηση), οι επιδράσεις δεν αθροίζονται ακριβώς στο συνολικό χάσμα σκορ."""
    suggestions_table = REWRITE_SUGGESTIONS_EL if language == "greek" else REWRITE_SUGGESTIONS_EN
    per_phrase = internals.get("per_phrase", {})

    entries = []
    for i, f in enumerate(ai_features):
        if f.score <= 0.1 or f.weight <= 0:
            continue
        cleaned = [Feature(g.name, g.label, 0.0 if j == i else g.score, g.weight)
                   for j, g in enumerate(ai_features)]
        counterfactual = _score_from_signals(cleaned, human_features, reliability)
        impact = max(0.0, baseline_score - counterfactual)
        if impact < 0.5:
            continue

        entry = {
            "feature": f.name,
            "label": f.label,
            "label_i18n": f.label_i18n,
            "impact_points": round(impact, 1),
            "examples": f.examples[:5],
            "advice": FEATURE_ADVICE.get(f.name, {}).get(
                "el" if language == "greek" else "en", ""),
            "advice_i18n": FEATURE_ADVICE.get(f.name, {}),
        }
        if f.name == "ai_phrases":
            found = [{"found": label, "try": suggestions_table[label]}
                     for label in per_phrase if label in suggestions_table]
            entry["suggestions"] = found[:6]
        entries.append(entry)

    entries.sort(key=lambda e: -e["impact_points"])
    return entries[:limit]


# ---------------------------------------------------------------------------
# Τελικό σκορ
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Δικαιοσύνη: απλό λεξιλόγιο ≠ AI
# ---------------------------------------------------------------------------
# Οι ανιχνευτές AI χαρακτηρίζουν συχνά λανθασμένα ως «AI» κείμενα με απλό,
# επαναλαμβανόμενο λεξιλόγιο — π.χ. μη φυσικών ομιλητών (Liang et al. 2023,
# Stanford: 61% ψευδώς θετικά σε δοκίμια TOEFL). Μετράμε την ποικιλία
# λεξιλογίου (MATTR) και προειδοποιούμε όταν το σκορ είναι υψηλό αλλά το
# λεξιλόγιο φτωχό: το αποτέλεσμα μπορεί να οφείλεται στο ύφος, όχι σε AI.
# Βαθμονόμηση (παράθυρο 50 λέξεων): ανθρώπινα 0.84-0.96, AI ~0.91,
# απλό δοκίμιο μη φυσικού ομιλητή ~0.70.

MATTR_WINDOW = 50
LOW_DIVERSITY_MATTR = 0.78
FAIRNESS_MIN_WORDS = 100
FAIRNESS_MIN_SCORE = 42      # από «αβέβαιο» και πάνω


def lexical_diversity(text: str, window: int = MATTR_WINDOW) -> Optional[float]:
    """Moving-Average Type-Token Ratio: μέσο ποσοστό διαφορετικών λέξεων σε
    κυλιόμενο παράθυρο — ανεξάρτητο από το μήκος του κειμένου."""
    toks = [t.lower() for t in tokenize_words(text)]
    if len(toks) < window:
        return None
    counts: Dict[str, int] = {}
    for t in toks[:window]:
        counts[t] = counts.get(t, 0) + 1
    total = len(counts)
    for i in range(window, len(toks)):
        old, new = toks[i - window], toks[i]
        counts[old] -= 1
        if not counts[old]:
            del counts[old]
        counts[new] = counts.get(new, 0) + 1
        total += len(counts)
    return total / ((len(toks) - window + 1) * window)


def fairness_check(text: str, score: float, n_words: int) -> Dict:
    mattr = lexical_diversity(text)
    warn = (mattr is not None and n_words >= FAIRNESS_MIN_WORDS
            and score >= FAIRNESS_MIN_SCORE and mattr < LOW_DIVERSITY_MATTR)
    return {
        "lexical_diversity": round(mattr, 3) if mattr is not None else None,
        "threshold": LOW_DIVERSITY_MATTR,
        "warning": "simple_vocabulary" if warn else None,
    }


def _analyze_core(text: str, source: Optional[str] = None,
                  with_highlights: bool = True) -> Dict:
    """Ανάλυση ενός (τμήματος) κειμένου. Επιστρέφει dict συμβατό με το API v1 + νέα πεδία."""

    text = (text or "").strip()
    if not text:
        return {
            "score": 0, "is_likely_ai": False, "confidence": "VERY LOW",
            "language": "-", "language_code": None, "language_i18n": {lang: "-" for lang in UI_LANGS},
            "verdict": VERDICTS["empty"]["el"], "verdict_code": "empty",
            "verdict_i18n": VERDICTS["empty"],
            "patterns_found": [], "features": [], "human_markers_detail": [],
            "highlights": [], "revision_guide": [], "reliability": 0,
            "human_markers": {"contractions_found": 0, "personal_pronouns": 0, "informal_words": 0},
            "text_stats": {"characters": 0, "words": 0, "sentences": 0, "average_sentence_length": 0},
        }

    language = detect_language(text)
    ai_features, human_features, internals = extract_features(text, language, source)

    # Αξιοπιστία: μικρά κείμενα -> σκορ πιο κοντά στο κέντρο
    n_words = internals["n_words"]
    reliability = _clamp(n_words / 200, 0.15, 1.0)

    score = round(_score_from_signals(ai_features, human_features, reliability), 1)

    # Ετυμηγορία και βεβαιότητα
    delta = abs(score - 50)
    if delta > 28 and n_words >= 120:
        confidence = "HIGH"
    elif delta > 17:
        confidence = "MEDIUM"
    elif delta > 8:
        confidence = "LOW"
    else:
        confidence = "VERY LOW"

    is_likely_ai = score >= 55
    if score >= 75:
        verdict_code = "ai_likely"
    elif score >= 55:
        verdict_code = "ai_signs"
    elif score >= 42:
        verdict_code = "uncertain"
    elif score >= 25:
        verdict_code = "human_probable"
    else:
        verdict_code = "human_likely"
    verdict = VERDICTS[verdict_code]["el"]

    # Συμβατότητα με το παλιό API: patterns_found
    patterns_found = []
    for f in ai_features:
        if f.score > 0.15 and f.weight > 0:
            patterns_found.append({
                "pattern": f.name,
                "description": f.label,
                "occurrences": f.occurrences,
                "density": round(f.score, 3),
            })

    # Στατιστικά για το UI (συμβατά ονόματα)
    contractions_found = next((f.occurrences for f in human_features if f.name == "contractions"), 0)
    informal_found = next((f.occurrences for f in human_features if f.name == "informal"), 0)
    if language == "greek":
        pronouns = len(re.findall(r"\b(εγώ|εμείς|εμένα|εσύ|μου|μας)\b", text, re.IGNORECASE))
    else:
        pronouns = len(re.findall(r"\b(I|we|my|our|me|us)\b", text))

    sentences_n = internals["n_sentences"]

    revision_guide = (build_revision_guide(ai_features, human_features, reliability,
                                            score, language, internals)
                       if with_highlights else [])

    return {
        # --- Συμβατά με v1 πεδία ---
        "score": score,
        "is_likely_ai": is_likely_ai,
        "confidence": confidence,
        "language": "Ελληνικά" if language == "greek" else "English",
        "language_code": "el" if language == "greek" else "en",
        "language_i18n": LANGUAGE_NAMES.get(language, {lang: language for lang in UI_LANGS}),
        "patterns_found": patterns_found,
        "human_markers": {
            "contractions_found": contractions_found,
            "personal_pronouns": pronouns,
            "informal_words": informal_found,
        },
        "text_stats": {
            "characters": len(text),
            "words": n_words,
            "sentences": sentences_n,
            "average_sentence_length": round(n_words / max(sentences_n, 1), 1),
            "paragraphs": internals["n_paragraphs"],
        },
        # --- Νέα πεδία v2 ---
        "verdict": verdict,
        "verdict_code": verdict_code,
        "verdict_i18n": VERDICTS[verdict_code],
        "reliability": round(reliability * 100),
        "features": [f.to_dict() for f in ai_features],
        "human_markers_detail": [f.to_dict() for f in human_features],
        "highlights": highlight_sentences(internals, language) if with_highlights else [],
        "revision_guide": revision_guide,
        "fairness": fairness_check(text, score, n_words),
        "engine_version": "2.3",
    }


# ---------------------------------------------------------------------------
# Ανάλυση ανά ενότητα για μεγάλα κείμενα (διπλωματικές 50-200 σελίδων)
# ---------------------------------------------------------------------------

CHUNK_TARGET_WORDS = 1000     # μέγεθος ενότητας
LONG_TEXT_THRESHOLD = 2500    # πάνω από τόσες λέξεις γίνεται και ανάλυση ανά ενότητα
SECTION_AI_THRESHOLD = 60     # ενότητα με σκορ >= τόσο θεωρείται "ύποπτη"


def _split_chunks(text: str) -> List[str]:
    """Σπάει το κείμενο σε ενότητες ~CHUNK_TARGET_WORDS λέξεων,
    σεβόμενο όρια παραγράφων (και προτάσεων για τεράστιες 'παραγράφους' PDF)."""
    raw_paras = [p for p in re.split(r'\n\s*\n', text) if p.strip()]

    # Τεράστιες "παράγραφοι" (π.χ. σελίδες PDF χωρίς κενές γραμμές) → σπάσιμο σε προτάσεις
    paras: List[str] = []
    for p in raw_paras:
        if len(p.split()) > CHUNK_TARGET_WORDS * 1.5:
            lang = detect_language(p)
            piece: List[str] = []
            count = 0
            for s in split_sentences(p, lang) or [p]:
                piece.append(s)
                count += len(s.split())
                if count >= CHUNK_TARGET_WORDS:
                    paras.append(" ".join(piece))
                    piece, count = [], 0
            if piece:
                paras.append(" ".join(piece))
        else:
            paras.append(p)

    chunks: List[str] = []
    cur: List[str] = []
    cur_words = 0
    for p in paras:
        cur.append(p)
        cur_words += len(p.split())
        if cur_words >= CHUNK_TARGET_WORDS:
            chunks.append("\n\n".join(cur))
            cur, cur_words = [], 0
    if cur:
        # Πολύ μικρό υπόλοιπο κολλάει στην τελευταία ενότητα
        if chunks and cur_words < CHUNK_TARGET_WORDS * 0.3:
            chunks[-1] = chunks[-1] + "\n\n" + "\n\n".join(cur)
        else:
            chunks.append("\n\n".join(cur))
    return chunks


def analyze_text(text: str, source: Optional[str] = None) -> Dict:
    """Κύρια συνάρτηση ανάλυσης.

    Για μεγάλα κείμενα (>~2500 λέξεις, π.χ. διπλωματικές) επιστρέφει επιπλέον
    'sections': σκορ ανά ενότητα ~1000 λέξεων, ώστε να εντοπίζεται ΠΟΥ υπάρχουν
    ενδείξεις AI ακόμα κι αν το συνολικό κείμενο είναι κυρίως ανθρώπινο."""

    result = _analyze_core(text, source, with_highlights=True)

    n_words = result["text_stats"]["words"]
    if n_words < LONG_TEXT_THRESHOLD:
        return result

    chunks = _split_chunks(text)
    if len(chunks) < 3:
        return result

    sections = []
    start_word = 1
    for i, chunk in enumerate(chunks):
        r = _analyze_core(chunk, source, with_highlights=False)
        w = r["text_stats"]["words"]
        preview_words = tokenize_words(chunk)[:12]
        sections.append({
            "section": i + 1,
            "start_word": start_word,
            "end_word": start_word + w - 1,
            "words": w,
            "score": r["score"],
            "is_ai": r["score"] >= SECTION_AI_THRESHOLD,
            "preview": " ".join(preview_words) + "…",
        })
        start_word += w

    n_ai = sum(1 for s in sections if s["is_ai"])
    result["sections"] = sections
    result["ai_sections"] = n_ai
    result["total_sections"] = len(sections)

    # Αν το συνολικό σκορ είναι "ανθρώπινο" αλλά υπάρχουν ύποπτες ενότητες,
    # η ετυμηγορία πρέπει να το πει καθαρά — μην κρυφτεί στον μέσο όρο.
    if n_ai > 0 and result["score"] < 55:
        result["verdict_code"] = "mixed"
        result["verdict_i18n"] = _fmt(MIXED_VERDICT, n_ai=n_ai, total=len(sections))
        result["verdict"] = result["verdict_i18n"]["el"]
        if n_ai / len(sections) >= 0.25:
            result["is_likely_ai"] = True
    return result


if __name__ == "__main__":
    import json
    import sys
    data = sys.stdin.read()
    print(json.dumps(analyze_text(data), ensure_ascii=False, indent=2))
