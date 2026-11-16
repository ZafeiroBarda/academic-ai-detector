#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite / βαθμονόμηση για το detector_engine v2.
Τρέξιμο:  python test_detector.py          (μόνο engine tests)
          python test_detector.py --files  (+ δημιουργία docx/pdf και έλεγχος εξαγωγής)
          python test_detector.py --server (+ end-to-end έλεγχος στον Flask server)
          python test_detector.py --security (+ CSRF/Host/headers, χωρίς server)
          python test_detector.py --binoculars (+ Binoculars με μικρά τοπικά μοντέλα — θέλει torch)
          python test_detector.py --thesis (+ ανάλυση ανά ενότητα μεγάλων κειμένων)
          python test_detector.py --plagiarism (+ corpus & web — χρειάζεται internet)
Το CI (.github/workflows/ci.yml) τρέχει όλα εκτός από --plagiarism.
"""

import os
import sys
import json

# Τα tests δεν πρέπει να διαβάζουν/γράφουν την πραγματική cache του χρήστη·
# όσα ελέγχουν την cache χρησιμοποιούν δικό τους προσωρινό αρχείο.
os.environ["AI_DETECTOR_WEB_CACHE"] = "off"
os.environ["AI_DETECTOR_HISTORY"] = "off"
os.environ["AI_DETECTOR_CALIBRATION"] = os.path.join(
    __import__("tempfile").mkdtemp(prefix="ai_calib_"), "calibration_profile.json")

from detector_engine import analyze_text, detect_language

# ============================================================================
# Δείγματα — ΑΓΓΛΙΚΑ
# ============================================================================

EN_AI = """
In today's rapidly evolving digital landscape, social media plays a crucial role
in shaping how individuals communicate, learn, and interact. Moreover, it serves
as a testament to the transformative power of technology in our daily lives.
It is important to note that social media offers numerous benefits, including
enhanced connectivity, access to information, and opportunities for self-expression.

Furthermore, social media platforms empower users to foster meaningful connections
across geographical boundaries. Additionally, they provide invaluable tools for
businesses seeking to leverage digital marketing strategies. These platforms
facilitate seamless communication, enabling individuals to share ideas, experiences,
and perspectives with a diverse range of audiences.

However, navigating the complexities of social media requires careful consideration.
It's worth noting that excessive use can lead to significant challenges, including
decreased productivity, mental health concerns, and privacy issues. Consequently,
striking a balance between online engagement and real-world interactions is essential
for maintaining overall well-being.

Moreover, the ever-evolving nature of these platforms underscores the need for
digital literacy. Users must develop critical thinking skills to distinguish
credible information from misinformation. Additionally, parents and educators play
a pivotal role in guiding younger generations toward responsible usage.

In conclusion, social media represents a double-edged sword in modern society.
While it offers a plethora of opportunities for connection and growth, it also
presents multifaceted challenges that cannot be overstated. Ultimately, embracing
a holistic approach to digital engagement will pave the way for a healthier
relationship with technology.
"""

EN_HUMAN_CASUAL = """
So I finally got around to deleting Instagram off my phone last month and honestly?
Best decision I've made in ages. I'm not gonna pretend it was easy — the first week
i kept picking up my phone like a zombie, thumb hovering over where the app used to be.
Muscle memory is a hell of a thing.

My friend Katie thinks I'm being dramatic about it. Maybe she's right, I dunno.
But I noticed I was spending like 3 hours a day just scrolling. Three hours!! That's
basically a part-time job where the pay is feeling bad about your own life.

The weird thing is what I miss isn't the app itself,it's the little dopamine hits.
You know that feeling when you post something and the likes start rolling in? Yeah.
Turns out that goes away and you're just left with... your actual life. Which is fine,
by the way. My actual life is fine.

Last week I read two whole books. TWO. I can't remember the last time I did that,
maybe back when I was in college? I also started cooking again, mostly pasta stuff
but still. My mom noticed I seemed happier when I called her on Sunday.

Anyway, I'm not saying everyone should quit social media. That'd be preachy and
annoying. I'm just saying it worked for me, and if you've been thinking about it,
maybe try it for a month and see what happens. Worst case you reinstall and lose
nothing. Best case you get your brain back.
"""

EN_HUMAN_ACADEMIC = """
The relationship between social media use and adolescent mental health remains
contested in the empirical literature. Twenge et al. (2018) reported correlations
between screen time and depressive symptoms among US adolescents, but the effect
sizes were small, and subsequent reanalyses questioned their practical significance
(Orben & Przybylski, 2019). This disagreement reflects a deeper methodological
problem: most studies rely on self-reported usage measures, which correlate only
weakly with logged behaviour (Parry et al., 2021).

Three limitations recur across this body of work. First, cross-sectional designs
dominate, making causal inference impossible. Reverse causation is plausible —
depressed adolescents may seek out social media rather than being harmed by it.
Second, usage is typically measured as total time, ignoring what users actually
do online. Passive scrolling and active messaging likely have different effects
(Verduyn et al., 2017). Third, samples skew heavily toward Western, English-speaking
populations.

The present study addresses these gaps using a longitudinal panel of 2,431 Greek
secondary school students followed over eighteen months. We combine device-logged
usage data with clinical screening instruments administered at three waves. Our
design permits within-person comparisons, which control for stable individual
differences that confound between-person analyses.

We hypothesised that within-person increases in passive use would predict small
increases in depressive symptoms at the subsequent wave (H1), and that this effect
would be moderated by baseline social support (H2). Neither hypothesis specified
effects for active use, which prior work suggests is benign or mildly beneficial.
Results, reported in Section 4, offer partial support for H1 only.
"""

# ============================================================================
# Δείγματα — ΕΛΛΗΝΙΚΑ
# ============================================================================

EL_AI = """
Στη σημερινή εποχή, η τεχνητή νοημοσύνη διαδραματίζει καθοριστικό ρόλο στη
διαμόρφωση της καθημερινότητάς μας. Επιπλέον, αποτελεί αναπόσπαστο κομμάτι της
σύγχρονης κοινωνίας, καθώς προσφέρει πληθώρα δυνατοτήτων σε ποικίλους τομείς.
Είναι σημαντικό να σημειωθεί ότι η ραγδαία εξέλιξη της τεχνολογίας ανοίγει νέους
ορίζοντες τόσο στην εκπαίδευση όσο και στην υγεία.

Επιπροσθέτως, η τεχνητή νοημοσύνη έχει τη δυνατότητα να συμβάλει σημαντικά στην
αντιμετώπιση σημαντικών προκλήσεων. Παράλληλα, καθίσταται σαφές ότι η αξιοποίησή
της απαιτεί προσεκτικό σχεδιασμό και ολιστική προσέγγιση. Ωστόσο, δεν πρέπει να
παραβλέπονται οι κίνδυνοι που ελλοχεύουν, καθώς η τεχνολογία αποτελεί δίκοπο μαχαίρι.

Αξίζει να σημειωθεί ότι οι νέες τεχνολογίες φέρνουν επανάσταση στον τρόπο με τον
οποίο εργαζόμαστε και επικοινωνούμε. Συνεπώς, είναι επιτακτική ανάγκη να
αναπτυχθούν κατάλληλα ρυθμιστικά πλαίσια. Επιπλέον, η εκπαίδευση των πολιτών
διαδραματίζει κομβικό ρόλο στην ομαλή μετάβαση στη νέα ψηφιακή εποχή.

Εν κατακλείδι, η τεχνητή νοημοσύνη προσφέρει πολλαπλά οφέλη, αλλά συγχρόνως
δημιουργεί προκλήσεις και ευκαιρίες που απαιτούν συλλογική αντιμετώπιση.
Συμπερασματικά, η ισορροπημένη αξιοποίηση της τεχνολογίας, σε συνδυασμό με την
κατάλληλη παιδεία, θα ανοίξει τον δρόμο για ένα καλύτερο μέλλον. Αναμφίβολα,
το μέλλον της ανθρωπότητας είναι άρρηκτα συνδεδεμένο με την τεχνολογική πρόοδο.
"""

EL_HUMAN_CASUAL = """
Λοιπόν, να σου πω τι έγινε με το λάπτοπ μου γιατί έχει πλάκα. Πάω προχθές να το
ανοίξω και τίποτα. Μαύρη οθόνη. Πατάω το κουμπί, το ξαναπατάω, τίποτα. Σκέφτομαι
οκ, πάει, κάηκε, δύο χιλιάρικα στον βρόντο.

Παίρνω τον ξάδερφό μου τον Γιώργο που ξέρει απ' αυτά και μου λέει "ρε συ, βγάλε
την μπαταρία και βάλτη ξανά". Του λέω δεν βγαίνει η μπαταρία σ' αυτά τα καινούρια,
ενσωματωμένη είναι. Μου λέει "α, τότε κράτα πατημένο το power για 30 δευτερόλεπτα".
Και καλά, hard reset κάτι τέτοιο.

Το κάνω. Τίποτα. Πάω να το πάω για επισκευή την άλλη μέρα, το βάζω στην τσάντα,
και εκεί που περπατάω ακούω ένα "ντινγκ". Το ανοίγω μες στον δρόμο... δούλευε
κανονικά!! Λες και δεν είχε γίνει τίποτα. Ακόμα δεν έχω καταλάβει τι έφταιγε.

Ο Γιώργος λέει ότι μάλλον είχε κολλήσει κάτι στο firmware και το reset τελικά
έπιασε απλά αργησε να φανεί. Εγώ πάντως έχω αρχίσει και κάνω backup τα πάντα,
δηλαδή ΤΑ ΠΑΝΤΑ, γιατί άμα την επόμενη φορά δεν ξανανοίξει, την πτυχιακή μου
δεν την ξαναγράφω με τίποτα. Μια φορά μου έφτανε.
"""

EL_HUMAN_ACADEMIC = """
Η παρακολούθηση της δικτυακής κίνησης σε περιβάλλοντα SDN παρουσιάζει ιδιαίτερες
δυσκολίες όταν οι επιθέσεις εκδηλώνονται σε χαμηλούς ρυθμούς. Οι Braga κ.ά. (2010)
πρότειναν μέθοδο βασισμένη σε αυτοοργανούμενους χάρτες, η οποία όμως απαιτεί
εκτεταμένη φάση εκπαίδευσης και εμφανίζει υψηλά ποσοστά ψευδών συναγερμών σε
δίκτυα με έντονη μεταβλητότητα φορτίου [3].

Στην παρούσα εργασία επιλέχθηκε ο αλγόριθμος Isolation Forest για δύο λόγους.
Πρώτον, δεν προϋποθέτει επισημασμένα δεδομένα επιθέσεων, κάτι που σπανίζει σε
πραγματικές εγκαταστάσεις. Δεύτερον, το υπολογιστικό του κόστος κλιμακώνεται
γραμμικά με το πλήθος των ροών, επιτρέποντας εκτέλεση σε πραγματικό χρόνο πάνω
στον ελεγκτή χωρίς αισθητή επιβάρυνση.

Τα χαρακτηριστικά που εξάγονται ανά ροή περιλαμβάνουν τον ρυθμό πακέτων, τη
μέση διάρκεια, την εντροπία των θυρών προορισμού και τον λόγο εισερχόμενων προς
εξερχόμενα bytes. Η επιλογή αυτή βασίστηκε σε προκαταρκτικά πειράματα με το
σύνολο δεδομένων CICDDoS2019, όπου η εντροπία θυρών αποδείχθηκε ο ισχυρότερος
διαχωριστικός παράγοντας για επιθέσεις SYN flood.

Το πειραματικό περιβάλλον υλοποιήθηκε σε Mininet με ελεγκτή Ryu. Η τοπολογία
περιλαμβάνει οκτώ μεταγωγείς σε διάταξη fat-tree και σαράντα τερματικούς κόμβους.
Η κίνηση υποβάθρου παρήχθη με το εργαλείο D-ITG, ρυθμισμένο ώστε να προσομοιώνει
ρεαλιστικά προφίλ χρήσης γραφείου. Τα αποτελέσματα παρουσιάζονται στο κεφάλαιο 5,
μαζί με συγκριτική αξιολόγηση έναντι των μεθόδων k-means και One-Class SVM.
"""

SAMPLES = [
    ("EN_AI (ChatGPT-style essay)", EN_AI, "english", "ai"),
    ("EN_HUMAN_CASUAL (blog)", EN_HUMAN_CASUAL, "english", "human"),
    ("EN_HUMAN_ACADEMIC (paper)", EN_HUMAN_ACADEMIC, "english", "human"),
    ("EL_AI (ChatGPT-style έκθεση)", EL_AI, "greek", "ai"),
    ("EL_HUMAN_CASUAL (προφορικό)", EL_HUMAN_CASUAL, "greek", "human"),
    ("EL_HUMAN_ACADEMIC (πτυχιακή)", EL_HUMAN_ACADEMIC, "greek", "human"),
]

AI_MIN = 60       # τα AI δείγματα πρέπει να σκοράρουν τουλάχιστον τόσο
HUMAN_MAX = 40    # τα ανθρώπινα το πολύ τόσο
MIN_GAP = 25      # ελάχιστη απόσταση AI-human στην ίδια γλώσσα


def run_engine_tests(verbose: bool = True) -> bool:
    results = {}
    ok = True
    for name, text, expected_lang, kind in SAMPLES:
        lang = detect_language(text)
        analysis = analyze_text(text)
        results[name] = (analysis, kind, lang)

        lang_ok = lang == expected_lang
        if kind == "ai":
            score_ok = analysis["score"] >= AI_MIN
        else:
            score_ok = analysis["score"] <= HUMAN_MAX
        ok = ok and lang_ok and score_ok

        if verbose:
            status = "✅" if (lang_ok and score_ok) else "❌"
            print(f"{status} {name}")
            print(f"   γλώσσα={analysis['language']} σκορ={analysis['score']}% "
                  f"({analysis['confidence']}) → {analysis['verdict']}")
            top = sorted(analysis["features"], key=lambda f: -f["score"] * f["weight"])[:3]
            for f in top:
                print(f"      · {f['label']}: {f['score']}% — {f['detail']}")
            print()

    # Έλεγχος διαχωρισμού ανά γλώσσα
    for lang in ("english", "greek"):
        ai_scores = [r[0]["score"] for r in results.values() if r[1] == "ai" and r[2] == lang]
        hu_scores = [r[0]["score"] for r in results.values() if r[1] == "human" and r[2] == lang]
        if ai_scores and hu_scores:
            gap = min(ai_scores) - max(hu_scores)
            gap_ok = gap >= MIN_GAP
            ok = ok and gap_ok
            print(f"{'✅' if gap_ok else '❌'} Διαχωρισμός {lang}: "
                  f"min(AI)={min(ai_scores)} - max(human)={max(hu_scores)} = {gap:.1f} "
                  f"(ελάχιστο {MIN_GAP})")

    print()
    print("=" * 60)
    print("ENGINE TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


# ============================================================================
# Δοκιμές αρχείων (docx/pdf) — απαιτούν python-docx, reportlab, pdfplumber
# ============================================================================

def run_file_tests(tmpdir: str) -> bool:
    import os
    from docx import Document as DocxDocument
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from ai_detector_server import extract_text

    ok = True
    os.makedirs(tmpdir, exist_ok=True)

    # --- DOCX με αγγλικό AI κείμενο + πίνακα ---
    docx_path = os.path.join(tmpdir, "sample_ai.docx")
    doc = DocxDocument()
    for para in EN_AI.strip().split("\n\n"):
        doc.add_paragraph(para.replace("\n", " "))
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Accuracy"
    table.cell(1, 1).text = "95%"
    doc.save(docx_path)

    text = extract_text(docx_path)
    docx_ok = "rapidly evolving" in text and "Accuracy" in text
    ok = ok and docx_ok
    print(f"{'✅' if docx_ok else '❌'} DOCX: εξαγωγή {len(text)} χαρακτήρων "
          f"(παράγραφοι {'ναι' if 'rapidly evolving' in text else 'ΟΧΙ'}, "
          f"πίνακες {'ναι' if 'Accuracy' in text else 'ΟΧΙ'})")

    analysis = analyze_text(text)
    a_ok = analysis["score"] >= AI_MIN
    ok = ok and a_ok
    print(f"{'✅' if a_ok else '❌'} DOCX AI ανάλυση: σκορ={analysis['score']}%")

    # --- DOCX με ελληνικό κείμενο ---
    docx_el = os.path.join(tmpdir, "sample_el.docx")
    doc = DocxDocument()
    for para in EL_HUMAN_ACADEMIC.strip().split("\n\n"):
        doc.add_paragraph(para.replace("\n", " "))
    doc.save(docx_el)
    text = extract_text(docx_el)
    el_ok = "Isolation Forest" in text and detect_language(text) == "greek"
    analysis = analyze_text(text)
    el_score_ok = analysis["score"] <= HUMAN_MAX
    ok = ok and el_ok and el_score_ok
    print(f"{'✅' if (el_ok and el_score_ok) else '❌'} DOCX ελληνικό: "
          f"γλώσσα={analysis['language']}, σκορ={analysis['score']}%")

    # --- PDF με αγγλικό AI κείμενο ---
    pdf_path = os.path.join(tmpdir, "sample_ai.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    y = 800
    for line in EN_AI.strip().split("\n"):
        if not line.strip():
            y -= 8
            continue
        c.drawString(40, y, line.strip()[:110])
        y -= 14
        if y < 60:
            c.showPage()
            y = 800
    c.save()

    text = extract_text(pdf_path)
    pdf_ok = "rapidly evolving" in text
    analysis = analyze_text(text)
    p_ok = analysis["score"] >= AI_MIN
    ok = ok and pdf_ok and p_ok
    print(f"{'✅' if (pdf_ok and p_ok) else '❌'} PDF: εξαγωγή {len(text)} χαρακτήρων, "
          f"σκορ={analysis['score']}%")

    # --- tools/batch_analyze.py: φάκελος -> CSV (+ ζεύγη, JSON), φάκελος εξόδου που δεν υπάρχει ---
    import csv
    import subprocess
    batch_dir = os.path.join(tmpdir, "batch")
    os.makedirs(batch_dir, exist_ok=True)
    for name, body in (("a.txt", EN_AI), ("b.txt", EN_AI), ("c.txt", EN_HUMAN_CASUAL), ("empty.txt", "hi")):
        with open(os.path.join(batch_dir, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    out_csv = os.path.join(tmpdir, "batch_out", "nested", "res.csv")
    env = {k: v for k, v in os.environ.items() if k != "AI_DETECTOR_BINOCULARS"}
    proc = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        "tools", "batch_analyze.py"),
                           batch_dir, docx_path, "--out", out_csv],
                          capture_output=True, text=True, env=env, timeout=300)
    rows, pairs = [], []
    if proc.returncode == 0:
        with open(out_csv, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        with open(out_csv.replace(".csv", "_pairs.csv"), encoding="utf-8-sig") as fh:
            pairs = list(csv.DictReader(fh))
    by_file = {r["file"]: r for r in rows}
    b_ok = (proc.returncode == 0 and len(rows) == 5
            and by_file.get("empty.txt", {}).get("status") == "error"
            and float(by_file.get("a.txt", {}).get("ai_score") or 0) >= AI_MIN
            and rows[0]["file"] != "c.txt"
            and any({p["a"], p["b"]} == {"a.txt", "b.txt"} for p in pairs)
            and os.path.exists(out_csv.replace(".csv", ".json")))
    ok = ok and b_ok
    print(f"{'✅' if b_ok else '❌'} batch_analyze.py: {len(rows)} γραμμές, {len(pairs)} ζεύγη"
          + ("" if proc.returncode == 0 else f" — exit {proc.returncode}: {proc.stderr[-300:]}"))

    print()
    print("=" * 60)
    print("FILE TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


# ============================================================================
# End-to-end δοκιμή server (πρέπει να τρέχει σε http://localhost:5000)
# ============================================================================

def run_server_tests(base_url: str = "http://localhost:5000") -> bool:
    import urllib.request

    ok = True

    # Health
    with urllib.request.urlopen(f"{base_url}/health", timeout=5) as r:
        health = json.loads(r.read())
    h_ok = health.get("status") == "ok"
    ok = ok and h_ok
    print(f"{'✅' if h_ok else '❌'} GET /health → {health}")

    # UI στη ρίζα
    with urllib.request.urlopen(f"{base_url}/", timeout=5) as r:
        page = r.read().decode("utf-8", errors="replace")
    ui_ok = "AI Content Detector" in page
    ok = ok and ui_ok
    print(f"{'✅' if ui_ok else '❌'} GET / → σερβίρει UI ({len(page)} bytes)")

    # analyze-text EN AI
    req = urllib.request.Request(
        f"{base_url}/analyze-text",
        data=json.dumps({"text": EN_AI, "check_web": False}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    t_ok = data["status"] == "success" and data["analysis"]["score"] >= AI_MIN
    ok = ok and t_ok
    print(f"{'✅' if t_ok else '❌'} POST /analyze-text (EN AI) → "
          f"σκορ={data['analysis']['score']}%")

    # analyze-text EL human
    req = urllib.request.Request(
        f"{base_url}/analyze-text",
        data=json.dumps({"text": EL_HUMAN_CASUAL, "check_web": False}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    t2_ok = data["status"] == "success" and data["analysis"]["score"] <= HUMAN_MAX
    ok = ok and t2_ok
    print(f"{'✅' if t2_ok else '❌'} POST /analyze-text (EL human) → "
          f"σκορ={data['analysis']['score']}%")

    print()
    print("=" * 60)
    print("SERVER TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


# ============================================================================
# Δοκιμές ασφαλείας του server (Flask test client — δεν χρειάζεται server)
# ============================================================================

def run_security_tests() -> bool:
    """Κλειδώνει τις προστασίες: Host allow-list (DNS rebinding), CSRF μέσω
    Origin/Sec-Fetch-Site, security headers, χωρίς CORS, χωρίς διαρροή
    εσωτερικών σφαλμάτων, μηνύματα στη γλώσσα του UI."""
    import ai_detector_server as srv

    client = srv.app.test_client()
    local = {"Host": "localhost:5000"}
    body = {"text": EN_AI, "check_web": False, "check_plagiarism": False}
    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    r = client.get("/", headers=local)
    check("GET / από localhost → 200", r.status_code == 200)
    csp = r.headers.get("Content-Security-Policy", "")
    check("CSP με frame-ancestors 'none' και connect-src 'self'",
          "frame-ancestors 'none'" in csp and "connect-src 'self'" in csp)
    check("X-Frame-Options: DENY", r.headers.get("X-Frame-Options") == "DENY")
    check("X-Content-Type-Options: nosniff",
          r.headers.get("X-Content-Type-Options") == "nosniff")
    check("Χωρίς Access-Control-Allow-Origin (όχι CORS)",
          "Access-Control-Allow-Origin" not in client.get(
              "/health", headers={**local, "Origin": "https://evil.example"}).headers)
    check("Cache-Control: no-store στα API",
          client.get("/health", headers=local).headers.get("Cache-Control") == "no-store")

    for host in ("evil.example", "attacker.example:5000", "127.0.0.1.nip.io:5000"):
        check(f"Ξένο Host {host} → 403",
              client.get("/health", headers={"Host": host}).status_code == 403)
    for host in ("127.0.0.1:5000", "[::1]:5000", "localhost"):
        check(f"Host {host} → 200",
              client.get("/health", headers={"Host": host}).status_code == 200)

    ok_post = client.post("/analyze-text", json=body, headers={
        **local, "Origin": "http://localhost:5000", "Sec-Fetch-Site": "same-origin"})
    check("POST από το ίδιο origin → 200", ok_post.status_code == 200)
    for origin in ("https://evil.example", "null", "http://localhost.evil.example"):
        check(f"POST με Origin {origin} → 403",
              client.post("/analyze-text", json=body,
                          headers={**local, "Origin": origin}).status_code == 403)
    check("POST με Sec-Fetch-Site: cross-site → 403",
          client.post("/config/brave", json={"api_key": "x"},
                      headers={**local, "Sec-Fetch-Site": "cross-site"}).status_code == 403)

    check("JSON λάθος τύπου → 400",
          client.post("/analyze-text", json=[1], headers=local).status_code == 400
          and client.post("/analyze-text", json={"text": 5}, headers=local).status_code == 400
          and client.post("/config/brave", json=[1], headers=local).status_code == 400)

    import logging

    def boom(*_args, **_kwargs):
        raise RuntimeError("SECRET-DETAIL")

    original = srv.engine_analyze
    srv.engine_analyze = boom
    logging.disable(logging.CRITICAL)   # το αναμενόμενο traceback δεν χρειάζεται στο log
    try:
        r500 = client.post("/analyze-text", json=body, headers=local)
    finally:
        srv.engine_analyze = original
        logging.disable(logging.NOTSET)
    check("500 χωρίς διαρροή λεπτομερειών εξαίρεσης",
          r500.status_code == 500 and b"SECRET-DETAIL" not in r500.data)

    msgs = {lang: client.post("/analyze-text", json={"text": "  "},
                              headers={**local, "X-UI-Lang": lang}).get_json()["error"]
            for lang in ("en", "el", "de", "xx")}
    check("Μηνύματα σφάλματος στη γλώσσα του UI (άγνωστη → αγγλικά)",
          msgs["en"] == "The text is empty" and msgs["el"] == "Το κείμενο είναι κενό"
          and msgs["de"] == "Der Text ist leer" and msgs["xx"] == msgs["en"])

    # Νέα πεδία ενδείξεων στην απάντηση (χωρίς δίκτυο: check_refs=False)
    a = ok_post.get_json()["analysis"]
    check("Απάντηση με fairness και references (disabled χωρίς web)",
          "fairness" in a and a.get("references", {}).get("status") == "disabled")
    import io
    from docx import Document as DocxDocument
    buf = io.BytesIO()
    d = DocxDocument()
    d.add_paragraph(EN_AI)
    d.save(buf)
    buf.seek(0)
    up = client.post("/analyze", headers=local, content_type="multipart/form-data",
                     data={"file": (buf, "essay.docx"), "web": "0", "plagiarism": "0"})
    check("Ανέβασμα .docx → docx_history και obfuscation στην απάντηση",
          up.status_code == 200 and {"docx_history", "obfuscation"} <= set(up.get_json()["analysis"]))

    def docx_bytes(text):
        b = io.BytesIO()
        doc = DocxDocument()
        for para in text.strip().split("\n\n"):
            doc.add_paragraph(para)
        doc.save(b)
        b.seek(0)
        return b
    sentences = EN_HUMAN_ACADEMIC.split(".")
    copied = ".".join(sentences[: len(sentences) // 2]) + ". " + EN_HUMAN_CASUAL
    batch = client.post("/analyze-batch", headers=local, content_type="multipart/form-data", data={
        "files": [(docx_bytes(EN_HUMAN_ACADEMIC), "anna.docx"), (docx_bytes(copied), "bob.docx"),
                  (docx_bytes(EN_AI), "chris.docx"), (io.BytesIO(b"x"), "notes.txt")],
        "plagiarism": "0"})
    bj = batch.get_json() or {}
    statuses = {r["filename"]: r["status"] for r in bj.get("results", [])}
    check(f"Μαζικός έλεγχος: 3 αναλύσεις + 1 απορριπτέο, ζεύγος anna–bob ({statuses})",
          batch.status_code == 200
          and statuses == {"anna.docx": "success", "bob.docx": "success",
                           "chris.docx": "success", "notes.txt": "error"}
          and [(p["a"], p["b"]) for p in bj.get("pairs", [])] == [("anna.docx", "bob.docx")])
    too_many = client.post("/analyze-batch", headers=local, content_type="multipart/form-data",
                           data={"files": [(io.BytesIO(b"x"), f"f{i}.docx") for i in range(31)]})
    check("Μαζικός έλεγχος: >30 αρχεία → 400", too_many.status_code == 400)

    # Οι εξωτερικοί έλεγχοι τρέχουν ΤΑΥΤΟΧΡΟΝΑ (ψεύτικοι, 0.5s ο καθένας)
    import time as _time

    def slow(result):
        def fn(*_a, **_k):
            _time.sleep(0.5)
            return result
        return fn
    saved = {n: getattr(srv, n) for n in ("check_wikipedia", "check_scholar", "check_brave",
                                          "check_google", "check_references")}
    try:
        srv.check_wikipedia = slow({"status": "ok", "hits": [], "checked": 1, "total": 1})
        srv.check_scholar = slow({"status": "ok", "hits": [], "checked": 1, "total": 1})
        srv.check_brave = slow({"status": "not_configured", "hits": []})
        srv.check_google = slow({"status": "not_configured", "hits": []})
        srv.check_references = slow({"status": "no_references", "results": [], "counts": {}})
        t0 = _time.time()
        par = client.post("/analyze-text", headers=local, json={
            "text": EN_AI, "check_web": True, "check_refs": True, "check_plagiarism": False})
        elapsed = _time.time() - t0
    finally:
        for n, fn in saved.items():
            setattr(srv, n, fn)
    pa = par.get_json()["analysis"]
    check(f"5 εξωτερικοί έλεγχοι ταυτόχρονα: {elapsed:.2f}s (σειριακά θα ήταν ≥2.5s)",
          elapsed < 1.6 and pa["references"]["status"] == "no_references"
          and pa["plagiarism"]["wikipedia"]["status"] == "ok"
          and pa["plagiarism"]["brave"]["status"] == "not_configured")

    # --- Προοδευτικά αποτελέσματα: σκορ αμέσως, έλεγχοι internet από /jobs/<id> ---
    from background_jobs import JobStore
    try:
        srv.check_wikipedia = slow({"status": "ok", "hits": [], "checked": 1, "total": 1})
        srv.check_scholar = slow({"status": "ok", "hits": [], "checked": 1, "total": 1})
        srv.check_brave = slow({"status": "not_configured", "hits": []})
        srv.check_google = slow({"status": "not_configured", "hits": []})
        srv.check_references = slow({"status": "no_references", "results": [], "counts": {}})
        t0 = _time.time()
        prog = client.post("/analyze-text", headers=local, json={
            "text": EN_AI, "check_web": True, "check_refs": True, "progressive": True})
        fast = _time.time() - t0
        pg = prog.get_json()["analysis"]
        job = pg.get("external_job", "")
        check(f"Προοδευτικά: σκορ σε {fast:.2f}s χωρίς να περιμένει τους ελέγχους internet",
              fast < 0.45 and isinstance(pg["score"], (int, float)) and len(job) == 32
              and pg["plagiarism"].get("pending") is True and "wikipedia" not in pg["plagiarism"]
              and pg["references"]["status"] == "pending")
        first = client.get(f"/jobs/{job}", headers=local)
        check("Προοδευτικά: όσο τρέχει → running", first.status_code == 200
              and first.get_json()["status"] == "running")
        done = None
        for _ in range(40):
            r = client.get(f"/jobs/{job}", headers=local)
            if r.get_json().get("status") == "done":
                done = r.get_json()
                break
            _time.sleep(0.1)
        check("Προοδευτικά: τελικά αποτελέσματα web + αναφορών",
              done is not None and done["plagiarism"]["wikipedia"]["status"] == "ok"
              and done["references"]["status"] == "no_references")
        check("Προοδευτικά: τα αποτελέσματα δίνονται ΜΙΑ φορά (μετά 404)",
              client.get(f"/jobs/{job}", headers=local).status_code == 404)
        bad_ids = ["../../etc/passwd", "a" * 31, "a" * 33, "%00" + "a" * 29,
                   "A" * 32, "<script>alert(1)</script>xxxxxxx"]
        check("Προοδευτικά: άγνωστα/κακόβουλα αναγνωριστικά → 404, χωρίς σφάλμα",
              all(client.get(f"/jobs/{b}", headers=local).status_code in (404, 405)
                  for b in bad_ids))
        check("Προοδευτικά: /jobs από ξένο Host → 403 (DNS rebinding)",
              client.get(f"/jobs/{'a' * 32}", headers={"Host": "evil.example"}).status_code == 403)
        check("Προοδευτικά: /jobs από άλλο site → 403",
              client.get(f"/jobs/{'a' * 32}", headers={**local, "Sec-Fetch-Site": "cross-site"})
              .status_code == 403)
        j2 = client.get(f"/jobs/{'a' * 32}", headers=local)
        check("Προοδευτικά: /jobs χωρίς cache (no-store)", j2.headers.get("Cache-Control") == "no-store")

        saved_store = srv.external_jobs
        srv.external_jobs = JobStore(max_active=0)
        try:
            full = client.post("/analyze-text", headers=local, json={
                "text": EN_AI, "check_web": True, "check_refs": True, "progressive": True})
            fa = full.get_json()["analysis"]
        finally:
            srv.external_jobs = saved_store
        check("Προοδευτικά: στο όριο εργασιών → κανονικός (σύγχρονος) έλεγχος, όχι σφάλμα",
              "external_job" not in fa and fa["plagiarism"]["wikipedia"]["status"] == "ok"
              and not fa["plagiarism"].get("pending"))
        off = client.post("/analyze-text", headers=local, json={
            "text": EN_AI, "check_web": False, "check_refs": False, "progressive": True})
        check("Προοδευτικά: χωρίς ελέγχους internet → χωρίς εργασία παρασκηνίου",
              "external_job" not in off.get_json()["analysis"])
    finally:
        for n, fn in saved.items():
            setattr(srv, n, fn)

    # --- Ρυθμίσεις: κλειδί OpenAlex και cache από τη σελίδα ---
    import plagiarism_engine as _pe
    import urllib.error as _ue3
    st = client.get("/config/search", headers=local).get_json()
    check("Ρυθμίσεις: /config/search δείχνει OpenAlex και cache (όχι το ίδιο το κλειδί)",
          "openalex" in st and isinstance(st["openalex"], bool) and "cache" in st
          and "entries" in st["cache"])
    saved_cfg = (srv.validate_openalex_key, srv.save_openalex_key)
    saved_get = _pe.http_pool.get_json
    stored = []
    try:
        bad = client.post("/config/openalex", headers=local, json={"api_key": "abc def;rm -rf"})
        check("OpenAlex key: λάθος μορφή → 400 χωρίς αίτημα στο internet",
              bad.status_code == 400 and "rm -rf" not in bad.get_data(as_text=True))
        too_long = client.post("/config/openalex", headers=local, json={"api_key": "A" * 500})
        check("OpenAlex key: υπερβολικά μεγάλο → 400", too_long.status_code == 400)

        def deny(url, headers=None, timeout=8.0):
            raise _ue3.HTTPError("https://api.openalex.org/works", 401, "Unauthorized", {}, None)
        _pe.http_pool.get_json = deny
        ok_fmt, msg = _pe.validate_openalex_key("WrongKey12345")
        check("OpenAlex key: απόρριψη από το OpenAlex → μήνυμα, το κλειδί δεν εμφανίζεται",
              not ok_fmt and "WrongKey12345" not in json.dumps(msg, ensure_ascii=False))
        _pe.http_pool.get_json = lambda url, headers=None, timeout=8.0: {"results": []}
        check("OpenAlex key: έγκυρο κλειδί περνά τον ζωντανό έλεγχο",
              _pe.validate_openalex_key("GoodKey12345")[0])
        srv.save_openalex_key = lambda k: stored.append(k)
        good = client.post("/config/openalex", headers=local, json={"api_key": "GoodKey12345"})
        check("OpenAlex key: αποθήκευση μόνο μετά από επιτυχή έλεγχο, χωρίς το κλειδί στην απάντηση",
              good.status_code == 200 and stored == ["GoodKey12345"]
              and "GoodKey12345" not in good.get_data(as_text=True))
        cross = client.post("/config/openalex", headers={**local, "Sec-Fetch-Site": "cross-site"},
                            json={"api_key": "GoodKey12345"})
        check("OpenAlex key: από άλλο site → 403 (CSRF)", cross.status_code == 403 and len(stored) == 1)
    finally:
        srv.validate_openalex_key, srv.save_openalex_key = saved_cfg
        _pe.http_pool.get_json = saved_get
    cc = client.post("/cache/clear", headers=local, json={})
    check("Cache: καθαρισμός από τη σελίδα", cc.status_code == 200 and cc.get_json()["status"] == "success")
    cc_x = client.post("/cache/clear", headers={**local, "Origin": "https://evil.example"}, json={})
    check("Cache: καθαρισμός από άλλο site → 403 (CSRF)", cc_x.status_code == 403)
    cc_get = client.get("/cache/clear", headers=local)
    check("Cache: μόνο POST (όχι GET από link/εικόνα)", cc_get.status_code == 405)

    # --- Corpus από τη σελίδα: ανέβασμα / λίστα / αφαίρεση με ασφάλεια ---
    import tempfile as _tf
    from pathlib import Path as _P
    corpus_tmp = _P(_tf.mkdtemp(prefix="ai_corpus_ui_"))
    outside = corpus_tmp.parent / (corpus_tmp.name + "_outside.txt")
    outside.write_text("μην με σβήσεις", encoding="utf-8")
    saved_corpus = srv.CORPUS_DIR
    srv.CORPUS_DIR = corpus_tmp
    try:
        body = (EN_HUMAN_ACADEMIC * 2).encode("utf-8")

        def up(*files, headers=local):
            return client.post("/corpus/upload", headers=headers, content_type="multipart/form-data",
                               data={"files": [(io.BytesIO(b), n) for n, b in files]})
        r = up(("Εργασία Μαρίας.txt", body), ("../../" + outside.name, body), ("virus.exe", b"MZ" * 50),
               ("empty.txt", b"hi"), ("Εργασία Μαρίας.txt", body), ("README.txt", body))
        res = r.get_json()["results"]
        names = sorted(p.name for p in corpus_tmp.iterdir())
        check(f"Corpus: ανέβασμα με ασφαλή ονόματα ({names})",
              r.status_code == 200 and "Εργασία Μαρίας.txt" in names
              and "Εργασία Μαρίας (2).txt" in names and "_README.txt" in names
              and outside.read_text(encoding="utf-8") == "μην με σβήσεις")
        check("Corpus: «../» δεν γράφει έξω από τον φάκελο",
              all((corpus_tmp / n).resolve().parent == corpus_tmp.resolve() for n in names)
              and not any(n.startswith(".upload-") for n in names))
        check("Corpus: .exe και αρχεία χωρίς κείμενο απορρίπτονται",
              [x["status"] for x in res] == ["saved", "saved", "error", "error", "saved", "saved"]
              and not any(n.endswith(".exe") or n == "empty.txt" for n in names))
        (corpus_tmp / ".hidden.txt").write_text("x", encoding="utf-8")
        try:
            (corpus_tmp / "link.txt").symlink_to(outside)
        except OSError:
            pass
        listed = [f["name"] for f in client.get("/corpus", headers=local).get_json()["files"]]
        check("Corpus: η λίστα δεν δείχνει κρυφά αρχεία ή symlinks",
              ".hidden.txt" not in listed and "link.txt" not in listed and "Εργασία Μαρίας.txt" in listed)
        bad_del = [client.post("/corpus/delete", headers=local, json={"name": n}).status_code
                   for n in ("../" + outside.name, "link.txt", ".hidden.txt", "", "/etc/passwd",
                             str(outside))]
        # το «../../outside.txt» αποθηκεύτηκε ως αντίγραφο ΜΕΣΑ στο corpus — η αφαίρεσή του
        # σβήνει μόνο αυτό, ποτέ το αρχείο έξω από τον φάκελο
        inner = client.post("/corpus/delete", headers=local, json={"name": outside.name}).status_code
        check(f"Corpus: αφαίρεση μόνο αρχείων της λίστας ({bad_del}, εσωτερικό αντίγραφο {inner})",
              all(c == 404 for c in bad_del) and inner == 200 and outside.exists()
              and (corpus_tmp / ".hidden.txt").exists())
        ok_del = client.post("/corpus/delete", headers=local, json={"name": "Εργασία Μαρίας (2).txt"})
        check("Corpus: αφαίρεση αρχείου της λίστας", ok_del.status_code == 200
              and not (corpus_tmp / "Εργασία Μαρίας (2).txt").exists())
        x_up = up(("x.txt", body), headers={**local, "Sec-Fetch-Site": "cross-site"})
        x_del = client.post("/corpus/delete", headers={**local, "Origin": "https://evil.example"},
                            json={"name": "Εργασία Μαρίας.txt"})
        check("Corpus: ανέβασμα/αφαίρεση από άλλο site → 403 (CSRF)",
              x_up.status_code == 403 and x_del.status_code == 403
              and (corpus_tmp / "Εργασία Μαρίας.txt").exists())
    finally:
        srv.CORPUS_DIR = saved_corpus

    # --- Σύγκριση εκδόσεων ---
    from docx import Document as _Doc

    def docx_bytes(text):
        buf = io.BytesIO()
        d = _Doc()
        for para in text.strip().split("\n\n"):
            d.add_paragraph(para.replace("\n", " "))
        d.save(buf)
        return buf.getvalue()
    cmp_ = client.post("/compare-versions", headers=local, content_type="multipart/form-data", data={
        "old": (io.BytesIO(docx_bytes(EN_HUMAN_ACADEMIC)), "v1.docx"),
        "new": (io.BytesIO(docx_bytes(EN_HUMAN_ACADEMIC + "\n\n" + EN_AI)), "v2.docx")})
    cj = cmp_.get_json() or {}
    cc_ = cj.get("comparison", {})
    check("Σύγκριση εκδόσεων: σκορ ανεβαίνει, νέες προτάσεις AI εντοπίζονται",
          cmp_.status_code == 200 and cc_.get("score_delta", 0) > 30
          and cc_["text_change"]["sentences_added"] > 0 and cc_["new_flagged_total"] > 0)
    one = client.post("/compare-versions", headers=local, content_type="multipart/form-data",
                      data={"old": (io.BytesIO(docx_bytes(EN_AI)), "v1.docx")})
    exe = client.post("/compare-versions", headers=local, content_type="multipart/form-data", data={
        "old": (io.BytesIO(b"MZ"), "a.exe"), "new": (io.BytesIO(b"MZ"), "b.exe")})
    check("Σύγκριση εκδόσεων: χωρίς δεύτερο αρχείο → 400, λάθος τύπος → 422",
          one.status_code == 400 and exe.status_code == 422)

    # --- Ιστορικό αναλύσεων: αποθήκευση από τον server, ασφάλεια, GDPR ---
    import tempfile as _tf2
    import analysis_history as ah
    hist_dir = _tf2.mkdtemp(prefix="ai_hist_")
    hs = ah.HistoryStore(os.path.join(hist_dir, "h.sqlite3"))
    ah.set_default_history(hs)
    try:
        r1 = client.post("/analyze-text", headers=local, json={
            "text": EN_HUMAN_ACADEMIC, "check_web": False, "check_refs": False, "check_plagiarism": False})
        hid = r1.get_json()["analysis"].get("history_id", "")
        listed = client.get("/history", headers=local).get_json()
        got = client.get(f"/history/{hid}", headers=local).get_json()
        check("Ιστορικό: η ανάλυση αποθηκεύεται και ξανανοίγει",
              len(hid) == 22 and listed["entries"][0]["id"] == hid
              and got["analysis"]["score"] == r1.get_json()["analysis"]["score"]
              and "history_id" not in got["analysis"])
        if os.name == "posix":
            check("Ιστορικό: αρχείο μόνο για τον χρήστη (0600)",
                  (os.stat(hs.path).st_mode & 0o777) == 0o600)
        from detector_engine import split_sentences as _split
        with open(hs.path, "rb") as fh:
            raw_db = fh.read().decode("utf-8", "replace")
        flagged = {h["text"] for h in got["analysis"].get("highlights", [])}
        unflagged = [x.strip() for x in _split(EN_HUMAN_ACADEMIC, "english")
                     if len(x.split()) > 5 and x.strip() not in flagged]
        check(f"Ιστορικό: δεν κρατά το κείμενο της εργασίας ({len(unflagged)} μη σημειωμένες προτάσεις)",
              len(unflagged) >= 5 and not any(x[:60] in raw_db for x in unflagged))
        bad = [client.get(f"/history/{x}", headers=local).status_code
               for x in ("a" * 22, "x' OR '1'='1", "../../etc/passwd", "a" * 21)]
        check(f"Ιστορικό: άγνωστα/κακόβουλα αναγνωριστικά → 404 ({bad})", all(c in (404, 405) for c in bad))
        check("Ιστορικό: ανάγνωση από άλλο site → 403",
              client.get(f"/history/{hid}", headers={**local, "Sec-Fetch-Site": "cross-site"}).status_code == 403
              and client.get("/history", headers={**local, "Sec-Fetch-Site": "cross-site"}).status_code == 403)
        x_clear = client.post("/history/clear", headers={**local, "Origin": "https://evil.example"}, json={})
        x_set = client.post("/history/settings", headers={**local, "Sec-Fetch-Site": "cross-site"},
                            json={"enabled": False})
        check("Ιστορικό: διαγραφή/ρυθμίσεις από άλλο site → 403 (CSRF)",
              x_clear.status_code == 403 and x_set.status_code == 403 and hs.get(hid) is not None)
        check("Ιστορικό: ρύθμιση μόνο με true/false",
              client.post("/history/settings", headers=local, json={"enabled": "no"}).status_code == 400)

        # Έλεγχοι internet που τελειώνουν μετά την αποθήκευση → συμπληρώνονται στο ιστορικό
        saved_fns = {n: getattr(srv, n) for n in ("check_wikipedia", "check_scholar", "check_brave",
                                                  "check_google", "check_references")}
        try:
            srv.check_wikipedia = slow({"status": "ok", "hits": [], "checked": 3, "total": 3})
            srv.check_scholar = slow({"status": "ok", "hits": [], "checked": 3, "total": 3})
            srv.check_brave = slow({"status": "not_configured", "hits": []})
            srv.check_google = slow({"status": "not_configured", "hits": []})
            srv.check_references = slow({"status": "no_references", "results": [], "counts": {}})
            r2 = client.post("/analyze-text", headers=local, json={
                "text": EN_AI, "check_web": True, "check_refs": True, "progressive": True})
            a2 = r2.get_json()["analysis"]
            for _ in range(40):
                if client.get(f"/jobs/{a2['external_job']}", headers=local).get_json().get("status") == "done":
                    break
                _time.sleep(0.1)
            _time.sleep(0.2)
            h2 = hs.get(a2["history_id"])["analysis"]
        finally:
            for n, fn in saved_fns.items():
                setattr(srv, n, fn)
        check("Ιστορικό: τα αποτελέσματα web/αναφορών συμπληρώνονται όταν τελειώσουν",
              h2["plagiarism"].get("wikipedia", {}).get("status") == "ok"
              and "pending" not in h2["plagiarism"] and h2["references"]["status"] == "no_references"
              and "external_job" not in h2)

        off = client.post("/history/settings", headers=local, json={"enabled": False})
        r3 = client.post("/analyze-text", headers=local, json={"text": EN_AI, "check_web": False})
        check("Ιστορικό: όταν είναι κλειστό, δεν αποθηκεύεται τίποτα",
              off.get_json()["enabled"] is False and "history_id" not in r3.get_json()["analysis"]
              and len(hs.list()) == 2)
        del_ok = client.post("/history/delete", headers=local, json={"id": hid})
        cleared = client.post("/history/clear", headers=local, json={}).get_json()["cleared"]
        check("Ιστορικό: διαγραφή μίας εγγραφής και όλων", del_ok.status_code == 200
              and cleared == 1 and hs.list() == [])
    finally:
        ah.set_default_history(None)

    # Όρια: διάρκεια, πλήθος, χαλασμένο αρχείο
    small = ah.HistoryStore(os.path.join(hist_dir, "small.sqlite3"), max_entries=3)
    ids = []
    for i in range(5):
        ids.append(small.new_id())
        small.save(ids[-1], f"t{i}", {"score": i, "text_stats": {"words": 10}})
        _time.sleep(0.01)
    check("Ιστορικό: κρατά μόνο τις πιο πρόσφατες εγγραφές (όριο πλήθους)",
          [e["name"] for e in small.list()] == ["t4", "t3", "t2"])
    expired = ah.HistoryStore(os.path.join(hist_dir, "exp.sqlite3"), retention_days=-1)
    eid = expired.new_id()
    expired.save(eid, "old", {"score": 1})
    check("Ιστορικό: εγγραφές πέρα από τη διάρκεια διατήρησης σβήνονται",
          expired.get(eid) is None and expired.list() == [])
    late = ah.HistoryStore(os.path.join(hist_dir, "late.sqlite3"))
    lid = late.new_id()
    late.merge_external(lid, {"plagiarism": {"wikipedia": {"status": "ok"}},
                              "references": {"status": "ok", "results": [], "counts": {}}})
    late.save(lid, "x", {"score": 5, "plagiarism": {"enabled": True, "pending": True}})
    check("Ιστορικό: αποτελέσματα που έρχονται πριν την αποθήκευση δεν χάνονται",
          late.get(lid)["analysis"]["plagiarism"].get("wikipedia") == {"status": "ok"})
    bad_path = os.path.join(hist_dir, "bad.sqlite3")
    with open(bad_path, "wb") as fh:
        fh.write(b"not a database" * 100)
    broken = ah.HistoryStore(bad_path)
    check("Ιστορικό: χαλασμένο αρχείο → απενεργοποίηση χωρίς σφάλμα",
          broken.save(broken.new_id(), "x", {"score": 1}) is False and broken.list() == [])

    # --- Μαζικός έλεγχος με ZIP από eClass/Moodle ---
    import zipfile as _zf
    from docx import Document as _Doc2

    def _docx(text):
        b = io.BytesIO()
        d = _Doc2()
        for para in text.strip().split("\n\n"):
            d.add_paragraph(para.replace("\n", " "))
        d.save(b)
        return b.getvalue()
    zbuf = io.BytesIO()
    with _zf.ZipFile(zbuf, "w", _zf.ZIP_DEFLATED) as zf:
        zf.writestr("Άννα Κ_111_assignsubmission_file_/thesis.docx", _docx(EN_AI))
        zf.writestr("Βασίλης Λ_222_assignsubmission_file_/thesis.docx", _docx(EN_HUMAN_ACADEMIC))
        zf.writestr("../../escape.docx", _docx(EN_AI))
        zf.writestr("notes.exe", b"MZ" * 100)
    before = set(os.listdir(srv.UPLOAD_FOLDER))
    bz = client.post("/analyze-batch", headers=local, content_type="multipart/form-data",
                     data={"files": [(io.BytesIO(zbuf.getvalue()), "submissions.zip")]})
    bj = bz.get_json() or {}
    students = sorted(r.get("student", "") for r in bj.get("results", []))
    check(f"Μαζικά: ZIP από Moodle → εργασίες με ονόματα φοιτητών ({students})",
          bz.status_code == 200 and students == ["", "Άννα Κ", "Βασίλης Λ"]
          and all(r["status"] == "success" for r in bj["results"])
          and bj.get("zip_skipped", {}).get("type") == 1)
    check("Μαζικά: ίδιο κείμενο σε δύο εργασίες του ZIP εντοπίζεται",
          any({p_["a"], p_["b"]} == {"Άννα Κ_111_assignsubmission_file_/thesis.docx", "escape.docx"}
              for p_ in bj.get("pairs", [])))
    check("Μαζικά: δεν μένουν προσωρινά αρχεία μετά την ανάλυση",
          set(os.listdir(srv.UPLOAD_FOLDER)) == before)
    badz = client.post("/analyze-batch", headers=local, content_type="multipart/form-data",
                       data={"files": [(io.BytesIO(b"not a zip at all"), "broken.zip")]})
    check("Μαζικά: χαλασμένο ZIP → μήνυμα σφάλματος, όχι κρασάρισμα",
          badz.status_code == 200 and badz.get_json()["results"][0]["status"] == "error")

    # --- Εξαίρεση παραθεμάτων: αναφέρεται στο αποτέλεσμα ---
    qtext = (EN_HUMAN_ACADEMIC + '\n\nAs Smith put it, "the quality of a measurement depends on the '
             'instrument far more than on the analyst" (2019).\n')
    ex_on = client.post("/analyze-text", headers=local, json={
        "text": qtext, "check_web": False, "check_refs": False, "check_plagiarism": True})
    ex_off = client.post("/analyze-text", headers=local, json={
        "text": qtext, "check_web": False, "check_refs": False, "check_plagiarism": True,
        "exclude_quotes": False})
    check("Εξαίρεση: το αποτέλεσμα λέει τι εξαιρέθηκε (και όχι όταν είναι κλειστό)",
          ex_on.get_json()["analysis"]["plagiarism"].get("excluded", {}).get("quotes") == 1
          and "excluded" not in ex_off.get_json()["analysis"]["plagiarism"])

    # --- Βαθμονόμηση από τη σελίδα ---
    import score_calibration as _sc
    saved_pf = _sc.PROFILE_FILE
    _sc.PROFILE_FILE = _P(_tf.mkdtemp(prefix="ai_calib_srv_")) / "calibration_profile.json"
    try:
        none_ = client.get("/calibration", headers=local).get_json()
        few = client.post("/calibration/run", headers=local, content_type="multipart/form-data",
                          data={"human": [(io.BytesIO(EN_HUMAN_ACADEMIC.encode()), "a.txt")]})
        secret_word = "Ξεχωριστόλεξη"
        humans = [(io.BytesIO((f"{secret_word}{i} " + (EN_HUMAN_ACADEMIC if i % 2 else EL_HUMAN_ACADEMIC))
                              .encode()), f"Φοιτητής {i}.txt") for i in range(10)]
        zb = io.BytesIO()
        with _zf.ZipFile(zb, "w") as zf:
            zf.writestr("x/Φοιτήτρια.txt", EN_HUMAN_CASUAL * 3)
        humans.append((io.BytesIO(zb.getvalue()), "more.zip"))
        run = client.post("/calibration/run", headers=local, content_type="multipart/form-data",
                          data={"human": humans, "ai": [(io.BytesIO(EN_AI.encode()), "ai.txt")],
                                "name": "Δοκιμή"})
        prof_ = run.get_json().get("profile", {})
        raw_prof = _sc.PROFILE_FILE.read_text(encoding="utf-8")
        check(f"Βαθμονόμηση: από τη σελίδα με αρχεία και ZIP ({prof_.get('n_human')} ανθρώπινες)",
              none_["profile"] is None and few.status_code == 400 and run.status_code == 200
              and prof_.get("n_human") == 11 and prof_.get("n_ai") == 1)
        check("Βαθμονόμηση: το προφίλ κρατά μόνο σκορ — όχι κείμενα ή ονόματα αρχείων",
              secret_word not in raw_prof and "Φοιτητής" not in raw_prof and "Φοιτήτρια" not in raw_prof)
        an = client.post("/analyze-text", headers=local, json={"text": EN_AI, "check_web": False})
        cal = an.get_json()["analysis"].get("calibration") or {}
        check("Βαθμονόμηση: κάθε ανάλυση δείχνει τη θέση του σκορ στις ανθρώπινες εργασίες",
              cal.get("n_human") == 11 and isinstance(cal.get("human_share_at_or_above"), float))
        x_run = client.post("/calibration/run", headers={**local, "Sec-Fetch-Site": "cross-site"},
                            content_type="multipart/form-data",
                            data={"human": [(io.BytesIO(b"x"), "a.txt")]})
        x_clr = client.post("/calibration/clear", headers={**local, "Origin": "https://evil.example"}, json={})
        check("Βαθμονόμηση: αλλαγή/διαγραφή από άλλο site → 403 (CSRF)",
              x_run.status_code == 403 and x_clr.status_code == 403 and _sc.PROFILE_FILE.exists())
        clr = client.post("/calibration/clear", headers=local, json={})
        check("Βαθμονόμηση: διαγραφή", clr.status_code == 200 and not _sc.PROFILE_FILE.exists()
              and client.get("/calibration", headers=local).get_json()["profile"] is None)
    finally:
        _sc.PROFILE_FILE = saved_pf

    store = JobStore(max_active=1, max_stored=2, ttl=0)
    gate = __import__("threading").Event()
    a = store.submit(lambda: (gate.wait(5), {"x": 1})[1])
    check("JobStore: όριο ταυτόχρονων εργασιών", a and store.submit(lambda: {}) is None)
    gate.set()
    _time.sleep(0.1)
    check("JobStore: ληγμένα αποτελέσματα σβήνονται (TTL)", store.poll(a) is None and store.size() == 0)
    store2 = JobStore()
    err = store2.submit(lambda: 1 / 0)
    _time.sleep(0.1)
    check("JobStore: σφάλμα μέσα στην εργασία → status error, χωρίς λεπτομέρειες",
          store2.poll(err) == {"status": "error"})

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(f"{'✅' if passed else '❌'} {name}")
    print()
    print("=" * 60)
    print("SECURITY TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


# ============================================================================
# Δοκιμές μεγάλων κειμένων (διπλωματικές) — ανάλυση ανά ενότητα
# ============================================================================

def run_thesis_tests() -> bool:
    import time
    ok = True

    # --- Μικτή "διπλωματική": 4 ανθρώπινα + 4 AI + 4 ανθρώπινα κεφάλαια ---
    human_block = EN_HUMAN_ACADEMIC.strip()
    ai_block = EN_AI.strip()
    thesis = "\n\n".join([human_block] * 4 + [ai_block] * 4 + [human_block] * 4)
    n_words = len(thesis.split())

    analysis = analyze_text(thesis)
    sections = analysis.get("sections", [])
    has_sections = len(sections) >= 3
    ok = ok and has_sections
    print(f"{'✅' if has_sections else '❌'} Μικτό έγγραφο {n_words} λέξεων → "
          f"{len(sections)} ενότητες (συνολικό σκορ {analysis['score']}%)")

    if has_sections:
        # Η πρώτη και η τελευταία ενότητα είναι ανθρώπινες — δεν πρέπει να φλεγκάρουν
        first_ok = not sections[0]["is_ai"]
        last_ok = not sections[-1]["is_ai"]
        # Τουλάχιστον μία μεσαία ενότητα (το AI κομμάτι) πρέπει να φλεγκάρει
        middle_ai = any(s["is_ai"] for s in sections[1:-1])
        ok = ok and first_ok and last_ok and middle_ai
        for s in sections:
            mark = "🔴" if s["is_ai"] else "🟢"
            print(f"   {mark} Ενότητα {s['section']} "
                  f"(λέξεις {s['start_word']}-{s['end_word']}): {s['score']}%")
        print(f"{'✅' if first_ok else '❌'} Πρώτη ενότητα (ανθρώπινη) δεν φλεγκάρει")
        print(f"{'✅' if last_ok else '❌'} Τελευταία ενότητα (ανθρώπινη) δεν φλεγκάρει")
        print(f"{'✅' if middle_ai else '❌'} Το AI κομμάτι στη μέση εντοπίστηκε "
              f"({analysis.get('ai_sections', 0)}/{analysis.get('total_sections', 0)} ενότητες AI)")

    # --- Ταχύτητα: κείμενο ~100k λέξεων (200 σελίδες) σε λογικό χρόνο ---
    big = "\n\n".join([human_block, ai_block] * 90)
    t0 = time.time()
    r = analyze_text(big)
    dt = time.time() - t0
    speed_ok = dt < 30
    ok = ok and speed_ok
    print(f"{'✅' if speed_ok else '❌'} Ταχύτητα: {len(big.split())} λέξεις "
          f"σε {dt:.1f}s ({len(r.get('sections', []))} ενότητες)")

    # --- Source hint: σε PDF ο δείκτης παραγράφων παραλείπεται ---
    r_pdf = analyze_text(EN_AI, source="pdf")
    para_feat = next(f for f in r_pdf["features"] if f["name"] == "paragraph_uniformity")
    pdf_ok = para_feat["weight"] == 0
    ok = ok and pdf_ok
    print(f"{'✅' if pdf_ok else '❌'} PDF source hint: δείκτης παραγράφων "
          f"απενεργοποιημένος (βάρος={para_feat['weight']})")

    # --- Μικρά κείμενα δεν αποκτούν sections ---
    r_small = analyze_text(EN_AI)
    small_ok = "sections" not in r_small
    ok = ok and small_ok
    print(f"{'✅' if small_ok else '❌'} Μικρό κείμενο: χωρίς ανάλυση ενοτήτων")

    print()
    print("=" * 60)
    print("THESIS TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


# ============================================================================
# Δοκιμές ελέγχου λογοκλοπής (τύπου Turnitin)
# ============================================================================

def run_plagiarism_tests(tmpdir: str) -> bool:
    import os
    import time as _time
    from docx import Document as DocxDocument
    from plagiarism_engine import CorpusIndex, check_wikipedia

    ok = True
    corpus_dir = os.path.join(tmpdir, "corpus")
    os.makedirs(corpus_dir, exist_ok=True)

    # Corpus: μια "παλιά εργασία" (docx) + ένα κείμενο αναφοράς (txt)
    doc = DocxDocument()
    for p in EL_HUMAN_ACADEMIC.strip().split("\n\n"):
        doc.add_paragraph(p.replace("\n", " "))
    doc.save(os.path.join(corpus_dir, "παλιά_διπλωματική_2023.docx"))
    with open(os.path.join(corpus_dir, "σημειώσεις.txt"), "w", encoding="utf-8") as f:
        f.write(EN_HUMAN_ACADEMIC)

    index = CorpusIndex(corpus_dir)
    index.refresh()
    idx_ok = index.n_files == 2
    ok = ok and idx_ok
    print(f"{'✅' if idx_ok else '❌'} Ευρετήριο corpus: {index.n_files} αρχεία")

    # --- 1. Κείμενο με κλεμμένη παράγραφο από την "παλιά εργασία" ---
    stolen = EL_HUMAN_ACADEMIC.strip().split("\n\n")[2].replace("\n", " ")
    query = EL_AI.strip() + "\n\n" + stolen
    r = index.compare(query)
    found = [s for s in r["sources"] if s["file"] == "παλιά_διπλωματική_2023.docx"]
    detect_ok = bool(found) and found[0]["similarity"] >= 10 and found[0]["passages"]
    ok = ok and detect_ok
    if found:
        print(f"{'✅' if detect_ok else '❌'} Κλεμμένη παράγραφος εντοπίστηκε: "
              f"{found[0]['similarity']}% από «{found[0]['file']}» "
              f"({found[0]['matched_words']} λέξεις, {found[0]['total_passages']} χωρία)")
        print(f"   Χωρίο: «{found[0]['passages'][0]['doc_excerpt'][:90]}…»")
    else:
        print(f"❌ Η κλεμμένη παράγραφος ΔΕΝ εντοπίστηκε: {r}")

    # --- 2. Ανθεκτικότητα σε τόνους/κεφαλαία ---
    import unicodedata
    mangled = unicodedata.normalize("NFD", stolen.upper())
    mangled = "".join(c for c in mangled if not unicodedata.combining(c))
    r2 = index.compare(EL_AI.strip() + "\n\n" + mangled)
    found2 = [s for s in r2["sources"] if s["file"] == "παλιά_διπλωματική_2023.docx"]
    robust_ok = bool(found2) and found2[0]["similarity"] >= 10
    ok = ok and robust_ok
    print(f"{'✅' if robust_ok else '❌'} Ανθεκτικότητα: ΚΕΦΑΛΑΙΑ χωρίς τόνους → "
          f"{found2[0]['similarity'] if found2 else 0}% ομοιότητα")

    # --- 3. Καθαρό κείμενο → μηδενική ομοιότητα ---
    r3 = index.compare(EL_HUMAN_CASUAL)
    clean_ok = r3["similarity"] < 3 and not r3["sources"]
    ok = ok and clean_ok
    print(f"{'✅' if clean_ok else '❌'} Καθαρό κείμενο: {r3['similarity']}% ομοιότητα, "
          f"{len(r3['sources'])} πηγές")

    # --- 4. Ίδιο έγγραφο → επισήμανση, όχι ψευδο-λογοκλοπή ---
    r4 = index.compare(EL_HUMAN_ACADEMIC)
    same_ok = r4.get("same_document_detected") and r4["similarity"] < 10
    ok = ok and same_ok
    print(f"{'✅' if same_ok else '❌'} Ίδιο έγγραφο: εντοπίστηκε ως ταυτόσημο "
          f"(συνολική ομοιότητα από τρίτες πηγές: {r4['similarity']}%)")

    # --- 5. Cache: δεύτερο refresh χωρίς αλλαγές = στιγμιαίο ---
    t0 = _time.time()
    index2 = CorpusIndex(corpus_dir)
    index2.refresh()
    dt = _time.time() - t0
    cache_ok = index2.n_files == 2 and dt < 2
    ok = ok and cache_ok
    print(f"{'✅' if cache_ok else '❌'} Cache: φόρτωση ευρετηρίου σε {dt:.2f}s")

    # --- 6. Wikipedia: πραγματική πρόταση από άρθρο (χρειάζεται internet) ---
    wiki_text = ("Alan Turing was highly influential in the development of "
                 "theoretical computer science, providing a formalisation of "
                 "the concepts of algorithm and computation with the Turing machine. "
                 "This sentence right here is completely original writing of mine. ") * 2
    w = check_wikipedia(wiki_text, max_sentences=6)
    if w["status"] in ("offline", "degraded", "partial"):
        print(f"⚠️  Wikipedia: {w['status']} (rate limit/δίκτυο) — "
              f"ο έλεγχος παραλείφθηκε (δεν μετράει ως αποτυχία)")
    else:
        wiki_ok = w["status"] == "ok" and len(w["hits"]) >= 1
        ok = ok and wiki_ok
        arts = ", ".join(h["article"] for h in w["hits"][:3])
        print(f"{'✅' if wiki_ok else '❌'} Wikipedia: {len(w['hits'])} εύρημα(τα) "
              f"σε {w['checked']} ελέγχους → {arts}")

    # --- 7. OpenAlex (τύπου Google Scholar): πρόταση από γνωστό paper ---
    from plagiarism_engine import check_scholar, check_google
    paper_text = ("The dominant sequence transduction models are based on complex "
                  "recurrent or convolutional neural networks that include an encoder "
                  "and a decoder. This filler sentence exists to give the sampler "
                  "additional material to work with here. ") * 2
    s = check_scholar(paper_text, max_sentences=4)
    if s["status"] in ("offline", "partial"):
        print(f"⚠️  OpenAlex: {s['status']} — παραλείφθηκε (δίκτυο)")
    else:
        sch_ok = s["status"] == "ok" and any("Attention" in h["title"] for h in s["hits"])
        ok = ok and sch_ok
        titles = ", ".join(h["title"][:40] for h in s["hits"][:2])
        print(f"{'✅' if sch_ok else '❌'} OpenAlex: {len(s['hits'])} εύρημα(τα) "
              f"σε {s['checked']} ελέγχους → {titles}")

    # --- 8. OpenAlex αρνητικό: καθαρό προφορικό κείμενο ---
    s2 = check_scholar(EL_HUMAN_CASUAL, max_sentences=4)
    if s2["status"] in ("offline", "partial"):
        print(f"⚠️  OpenAlex αρνητικό: {s2['status']} — παραλείφθηκε")
    else:
        neg_ok = len(s2["hits"]) == 0
        ok = ok and neg_ok
        print(f"{'✅' if neg_ok else '❌'} OpenAlex αρνητικό: {len(s2['hits'])} "
              f"ευρήματα σε καθαρό κείμενο")

    # --- 9. Google χωρίς ρύθμιση → not_configured ---
    g = check_google("some text that will not be checked anyway because no key",
                     config_path="/nonexistent/search_config.json")
    g_ok = g["status"] == "not_configured"
    ok = ok and g_ok
    print(f"{'✅' if g_ok else '❌'} Google χωρίς κλειδί: status={g['status']}")

    # --- 10. Brave χωρίς ρύθμιση → not_configured ---
    from plagiarism_engine import check_brave
    b = check_brave("some text that will not be checked anyway because no key",
                    config_path="/nonexistent/search_config.json")
    b_ok = b["status"] == "not_configured"
    ok = ok and b_ok
    print(f"{'✅' if b_ok else '❌'} Brave χωρίς κλειδί: status={b['status']}")

    # --- 11. Brave: επιλογή αποτελέσματος με επιβεβαίωση φράσης ---
    from plagiarism_engine import _brave_pick_result
    results = [
        {"title": "Άσχετο", "description": "τίποτα κοινό εδώ πέρα απολύτως"},
        {"title": "Σωστό", "description": "Η <strong>τεχνητή νοημοσύνη</strong> "
                                          "αναφέρεται στον τομέα της πληροφορικής"},
    ]
    pick = _brave_pick_result("τεχνητή νοημοσύνη αναφέρεται στον τομέα", results)
    pick_ok = pick is not None and pick["title"] == "Σωστό"
    loose = _brave_pick_result("εντελώς διαφορετική φράση χωρίς καμία σχέση",
                               [results[0]])
    loose_ok = loose is None
    ok = ok and pick_ok and loose_ok
    print(f"{'✅' if pick_ok else '❌'} Brave: διαλέγει το αποτέλεσμα που περιέχει τη φράση")
    print(f"{'✅' if loose_ok else '❌'} Brave: απορρίπτει άσχετο αποτέλεσμα (όχι ψευδοθετικό)")

    print()
    print("=" * 60)
    print("PLAGIARISM TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


def run_model_signature_tests(verbose: bool = True) -> bool:
    from model_signature import detect_model_signature

    ok = True

    # --- 1. EN, φράσεις τύπου ChatGPT (disclaimer, limitations, best practices) ---
    en_chatgpt = (
        "As an AI language model, I appreciate your question. I don't have "
        "access to real-time information, but I can provide some best practices. "
        "It should be noted that this recommended approach might work well. "
        "1. First point. 2. Second point. 3. Third point. "
        "That said, nonetheless, results may vary."
    )
    r1 = detect_model_signature(en_chatgpt)
    ok1 = r1["has_signal"] and r1["primary_model"] == "ChatGPT"
    ok = ok and ok1
    if verbose:
        print(f"{'✅' if ok1 else '❌'} EN ChatGPT-style → primary={r1['primary_model']} "
              f"({r1['primary_score']}%)")

    # --- 2. EL, φράσεις τύπου Claude (αβεβαιότητα, αυτοδιόρθωση) ---
    el_claude = (
        "Οφείλω να σημειώσω ότι δεν είμαι απόλυτα σίγουρος για αυτό το θέμα. "
        "Αυτό είναι περίπλοκο και δεν έχω αρκετές πληροφορίες για οριστική "
        "απάντηση. Για την ακρίβεια, η κατάσταση είναι κάπως ασαφής."
    )
    r2 = detect_model_signature(el_claude)
    ok2 = r2["has_signal"] and r2["primary_model"] == "Claude"
    ok = ok and ok2
    if verbose:
        print(f"{'✅' if ok2 else '❌'} EL Claude-style → primary={r2['primary_model']} "
              f"({r2['primary_score']}%)")

    # --- 3. EN, φράσεις τύπου Gemini (βεβαιότητα, em-dashes, διευκρίνιση) ---
    en_gemini = (
        "So here's the thing — I can help you understand this better. "
        "Absolutely, definitely, certainly this is worth exploring — let me "
        "clarify — I should mention that here's what I found: some key points "
        "worth remembering — interestingly enough, it's fascinating that this "
        "keeps coming up — remember that context matters here."
    )
    r3 = detect_model_signature(en_gemini)
    ok3 = r3["has_signal"] and r3["primary_model"] == "Gemini"
    ok = ok and ok3
    if verbose:
        print(f"{'✅' if ok3 else '❌'} EN Gemini-style → primary={r3['primary_model']} "
              f"({r3['primary_score']}%)")

    # --- 4. Καθαρό δοκίμιο τύπου AI-essay (EN_AI/EL_AI, ήδη στο test suite) ---
    #     ΣΗΜΑΝΤΙΚΟ: αυτά σκοράρουν ΥΨΗΛΑ στο κύριο engine ως AI-generated,
    #     αλλά ΔΕΝ πρέπει να ενεργοποιούν το model_signature — επιβεβαιώνει
    #     τον περιορισμό που περιγράφεται στο module docstring: essay-style
    #     AI κείμενο δεν περιέχει συνομιλιακές "υπογραφές" chatbot.
    r4 = detect_model_signature(EN_AI)
    ok4 = not r4["has_signal"]
    ok = ok and ok4
    if verbose:
        print(f"{'✅' if ok4 else '❌'} EN_AI (δοκίμιο, όχι chat) → has_signal="
              f"{r4['has_signal']} (αναμενόμενο: False)")

    r5 = detect_model_signature(EL_AI)
    ok5 = not r5["has_signal"]
    ok = ok and ok5
    if verbose:
        print(f"{'✅' if ok5 else '❌'} EL_AI (δοκίμιο, όχι chat) → has_signal="
              f"{r5['has_signal']} (αναμενόμενο: False)")

    # --- 5. Κενό κείμενο → καμία κρίσιμη αποτυχία ---
    r6 = detect_model_signature("")
    ok6 = not r6["has_signal"] and r6["primary_model"] is None
    ok = ok and ok6
    if verbose:
        print(f"{'✅' if ok6 else '❌'} Κενό κείμενο: καμία ένδειξη, καμία εξαίρεση")

    print()
    print("=" * 60)
    print("MODEL SIGNATURE TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


def run_revision_guide_tests(verbose: bool = True) -> bool:
    ok = True

    # --- 1. EN, γεμάτο κλισέ weight-3 φράσεις ---
    en_cliche = (
        "In today's rapidly evolving digital landscape, artificial intelligence "
        "plays a crucial role in shaping society. It is important to note that "
        "this technology offers a tapestry of opportunities. Moreover, we must "
        "delve into the complexities involved. Furthermore, the ever-evolving "
        "nature of this field underscores its multifaceted impact. This serves "
        "as a testament to human ingenuity, and it truly cannot be overstated."
    )
    r1 = analyze_text(en_cliche)
    g1 = r1["revision_guide"]
    top_is_phrases1 = bool(g1) and g1[0]["feature"] == "ai_phrases"
    sorted_ok1 = g1 == sorted(g1, key=lambda e: -e["impact_points"])
    has_suggestions1 = bool(g1) and bool(g1[0].get("suggestions"))
    ok1 = top_is_phrases1 and sorted_ok1 and has_suggestions1
    ok = ok and ok1
    if verbose:
        top = g1[0]["label"] if g1 else "-"
        print(f"{'✅' if ok1 else '❌'} EN κλισέ: κορυφαίος δείκτης «{top}», "
              f"{len(g1)} στοιχεία, ταξινομημένα={sorted_ok1}")

    # --- 2. EL, γεμάτο κλισέ weight-3 φράσεις ---
    el_cliche = (
        "Στη σημερινή εποχή, η τεχνητή νοημοσύνη διαδραματίζει καθοριστικό ρόλο "
        "στην εκπαίδευση. Είναι σημαντικό να σημειωθεί ότι αυτό αποτελεί "
        "αναπόσπαστο κομμάτι της εξέλιξης. Επιπροσθέτως, η ολιστική προσέγγιση "
        "προσφέρει πολλαπλά οφέλη. Εν κατακλείδι, δεν είναι υπερβολή να πούμε "
        "ότι αυτό είναι ακρογωνιαίος λίθος του μέλλοντος."
    )
    r2 = analyze_text(el_cliche)
    g2 = r2["revision_guide"]
    top_is_phrases2 = bool(g2) and g2[0]["feature"] == "ai_phrases"
    found_labels = {s["found"] for s in g2[0].get("suggestions", [])} if g2 else set()
    suggestion_ok2 = "διαδραματίζει καθοριστικό ρόλο" in found_labels
    ok2 = top_is_phrases2 and suggestion_ok2
    ok = ok and ok2
    if verbose:
        print(f"{'✅' if ok2 else '❌'} EL κλισέ: κορυφαίος δείκτης «"
              f"{g2[0]['label'] if g2 else '-'}», πρόταση για «διαδραματίζει "
              f"καθοριστικό ρόλο»={suggestion_ok2}")

    # --- 3. Καθαρό ανθρώπινο κείμενο → πολύ μικρός ή κενός οδηγός ---
    r3 = analyze_text(EN_HUMAN_CASUAL)
    g3 = r3["revision_guide"]
    clean_ok3 = len(g3) <= 1
    ok = ok and clean_ok3
    if verbose:
        print(f"{'✅' if clean_ok3 else '❌'} EN_HUMAN_CASUAL: {len(g3)} στοιχεία "
              f"οδηγού (αναμενόμενο: ≤1)")

    # --- 4. Κενό κείμενο → κενή λίστα, καμία εξαίρεση ---
    r4 = analyze_text("")
    ok4 = r4["revision_guide"] == []
    ok = ok and ok4
    if verbose:
        print(f"{'✅' if ok4 else '❌'} Κενό κείμενο: revision_guide=[]")

    print()
    print("=" * 60)
    print("REVISION GUIDE TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


# ============================================================================
# Ενδείξεις πέρα από το σκορ: αναφορές, ιστορικό docx, δικαιοσύνη (χωρίς δίκτυο)
# ============================================================================

NONNATIVE_SIMPLE_EN = (
    "I think that technology is very important for students today. Many students use "
    "technology every day for school. Technology help students to learn more fast and more "
    "easy. For example, students can use internet to find information for homework. Also "
    "students can use computer to write essay and make presentation. But technology also have "
    "some bad things. Some students use phone too much and they do not study. They play games "
    "and use social media all the time. This is not good for their grades. In my opinion, "
    "technology is good for students if they use it in a good way. Teachers and parents should "
    "help students to use technology good. In conclusion, technology is very important and "
    "useful for students, but students must be careful and use technology in a good way for study."
)

SAMPLE_REFERENCES = """Κεφάλαιο 1
Κείμενο της εργασίας.

Βιβλιογραφία
Vaswani, A., Shazeer, N., Parmar, N. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 30, 5998-6008.
Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional
transformers for language understanding. In Proceedings of NAACL-HLT. https://doi.org/10.18653/v1/N19-1423
Smith, J. (2021). Quantum entanglement in medieval agricultural practices. Journal of Imaginary Studies, 12(3), 45-67. https://doi.org/10.9999/fake.2021.123
Lee, K. (2020). Deep learning for protein folding prediction. Nature Methods, 17, 1-9. https://doi.org/10.1038/s41592-020-0001
Johnson, M. (2019). Neural correlates of algorithmic creativity in polar bears. Nature Neuroscience, 22, 101-110.
Παπαδόπουλος, Γ. (2015). Η εκπαίδευση στην Ελλάδα του 21ου αιώνα. Αθήνα: Gutenberg.
World Health Organization. (2020). Coronavirus disease (COVID-19) advice. Retrieved from https://www.who.int/emergencies

Παράρτημα Α
Πίνακες.
"""


def _fake_scholarly_web(url: str):
    """Ψεύτικο Crossref/OpenAlex με τη μορφή των πραγματικών απαντήσεων."""
    def work(title, year, doi):
        return {"DOI": doi, "title": [title], "issued": {"date-parts": [[year]]}}
    if "api.crossref.org/works/10.18653" in url:
        return {"message": work("BERT: Pre-training of Deep Bidirectional Transformers for "
                                "Language Understanding", 2019, "10.18653/v1/N19-1423")}
    if "api.crossref.org/works/10.1038" in url:
        return {"message": work("A completely different paper about soil bacteria", 2020,
                                "10.1038/s41592-020-0001")}
    if "api.crossref.org/works/10.9999" in url:
        return None                                  # 404: το DOI δεν υπάρχει
    if "api.crossref.org/works?" in url and "Vaswani" in url:
        return {"message": {"items": [work("Attention Is All You Need", 2017, "10.5555/3295222")]}}
    if "api.crossref.org/works?" in url:
        return {"message": {"items": [work("Polar ice dynamics", 2018, "10.1/x")]}}
    if "api.openalex.org" in url:
        return {"results": []}
    raise AssertionError("απρόσμενο URL: " + url)


def _craft_docx(path: str, paragraphs, total_time: str, created: str, modified: str):
    """Φτιάχνει .docx με rsid συνεδριών, όπως τα αποθηκεύει το Word."""
    import re
    import zipfile
    from xml.sax.saxutils import escape
    from docx import Document as DocxDocument
    base = path + ".base.docx"
    DocxDocument().save(base)
    with zipfile.ZipFile(base) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "word/document.xml":
                body = "".join(
                    f'<w:p w:rsidR="{r}" w:rsidRDefault="{r}"><w:r w:rsidR="{r}"><w:t>{escape(t)}</w:t></w:r></w:p>'
                    for r, t in paragraphs)
                data = re.sub(rb"<w:body>.*</w:body>", b"<w:body>" + body.encode() + b"</w:body>",
                              data, flags=re.S)
            elif info.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:created[^>]*>)[^<]*", rb"\g<1>" + created.encode(), data)
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>" + modified.encode(), data)
            elif info.filename == "docProps/app.xml":
                data = re.sub(rb"<TotalTime>[^<]*", b"<TotalTime>" + total_time.encode(), data)
            out.writestr(info, data)


def run_evidence_tests(verbose: bool = True) -> bool:
    import os
    import re
    import tempfile
    import docx_forensics
    import reference_check as rc
    from detector_engine import analyze_text as _analyze

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    # --- Αναφορές: εντοπισμός, διαχωρισμός, ανάλυση ---
    entries = rc.split_references(rc.find_reference_section(SAMPLE_REFERENCES))
    check(f"Βρέθηκαν 7 αναφορές (βρέθηκαν {len(entries)}), χωρίς το παράρτημα",
          len(entries) == 7 and not any("Πίνακες" in e for e in entries))
    parsed = [rc.parse_reference(e) for e in entries]
    check("APA τίτλος: «Attention is all you need»", parsed[0]["title"] == "Attention is all you need")
    check("Τίτλος με «in» μέσα δεν κόβεται",
          parsed[2]["title"] == "Quantum entanglement in medieval agricultural practices")
    check("DOI από URL", parsed[1]["doi"] == "10.18653/v1/N19-1423")
    check("Ελληνική αναφορά αναγνωρίζεται", parsed[5]["greek"] and parsed[5]["year"] == 2015)
    check("Ιστοσελίδα χωρίς DOI σημειώνεται", parsed[6]["is_web"])
    ieee = rc.split_references(rc.find_reference_section(
        'REFERENCES\n[1] A. Vaswani et al., "Attention is all you need," in Proc. NeurIPS, 2017.\n'
        '[2] K. He, X. Zhang, S. Ren, and J. Sun, "Deep residual learning for image\n'
        'recognition," in Proc. CVPR, 2016.\n'))
    check("IEEE: 2 αναφορές με τίτλους σε εισαγωγικά",
          [rc.parse_reference(e)["title"] for e in ieee]
          == ["Attention is all you need", "Deep residual learning for image recognition"])

    # --- Αναφορές: έλεγχος με ψεύτικο Crossref/OpenAlex ---
    res = rc.check_references(SAMPLE_REFERENCES, http_get=_fake_scholarly_web, delay=0)
    statuses = [r["status"] for r in res["results"]]
    check(f"Κατάσταση ανά αναφορά: {statuses}", statuses == [
        "verified", "verified", "doi_not_found", "doi_mismatch", "not_found", "not_found",
        "skipped_web"])

    import time as _time

    def slow_web(url):
        _time.sleep(0.2)
        return _fake_scholarly_web(url)
    t0 = _time.time()
    par = rc.check_references(SAMPLE_REFERENCES, http_get=slow_web, delay=0, workers=4)
    par_time = _time.time() - t0
    check(f"Αναφορές παράλληλα, ίδια σειρά/αποτελέσματα ({par_time:.2f}s, σειριακά ≥1.6s)",
          [r["status"] for r in par["results"]] == statuses and par_time < 1.2)

    def broken(_url):
        raise OSError("no network")
    off = rc.check_references(SAMPLE_REFERENCES, http_get=broken, delay=0)
    check("Χωρίς δίκτυο → status offline, χωρίς εξαίρεση", off["status"] == "offline")
    check("Χωρίς βιβλιογραφία → no_references",
          rc.check_references("Μόνο κείμενο χωρίς αναφορές.", http_get=broken)["status"]
          == "no_references")

    # --- Ιστορικό docx ---
    tmp = tempfile.mkdtemp(prefix="ai_docx_hist_")
    block = "λέξη " * 200
    pasted = os.path.join(tmp, "pasted.docx")
    _craft_docx(pasted, [("00A1B2C3", block)] * 9 + [("00D4E5F6", "Εισαγωγή")],
                "3", "2026-05-01T10:00:00Z", "2026-05-01T10:20:00Z")
    gradual = os.path.join(tmp, "gradual.docx")
    _craft_docx(gradual, [(f"00{i:06X}", block) for i in range(12)],
                "900", "2026-05-01T10:00:00Z", "2026-05-20T18:00:00Z")
    h1 = docx_forensics.analyze_docx(pasted)
    h2 = docx_forensics.analyze_docx(gradual)
    codes1 = {f["code"] for f in h1["findings"]}
    codes2 = {f["code"] for f in h2["findings"]}
    check(f"Επικόλληση → single_session, low_edit_time, short_span ({sorted(codes1)})",
          {"single_session", "low_edit_time", "short_span"} <= codes1)
    check(f"Σταδιακή γραφή → καμία προειδοποίηση ({sorted(codes2)})",
          not any(f["level"] == "warn" for f in h2["findings"]))
    two = os.path.join(tmp, "two.docx")
    _craft_docx(two, [("00A1B2C3", block)] * 3 + [("00D4E5F6", block)] * 2,
                "120", "2026-05-01T10:00:00Z", "2026-05-03T10:00:00Z")
    codes_two = [f["code"] for f in docx_forensics.analyze_docx(two)["findings"]]
    check(f"2 συνεδρίες → ουδέτερο some_sessions, όχι «σταδιακή γραφή» ({codes_two})",
          codes_two == ["some_sessions"])
    from docx import Document as DocxDocument
    plain = os.path.join(tmp, "plain.docx")
    d = DocxDocument()
    for _ in range(5):
        d.add_paragraph(block)
    d.save(plain)
    h3 = docx_forensics.analyze_docx(plain)
    check("Χωρίς rsid (π.χ. Google Docs) → μόνο ουδέτερο no_history",
          [f["code"] for f in h3["findings"]] == ["no_history"])
    bad = os.path.join(tmp, "bad.docx")
    with open(bad, "wb") as f:
        f.write(b"not a zip")
    check("Χαλασμένο αρχείο → available=False, χωρίς εξαίρεση",
          docx_forensics.analyze_docx(bad)["available"] is False)

    # --- Δικαιοσύνη ---
    nn = _analyze(NONNATIVE_SIMPLE_EN)
    check(f"Απλό δοκίμιο μη φυσικού ομιλητή → προειδοποίηση (σκορ {nn['score']}%)",
          nn["fairness"]["warning"] == "simple_vocabulary")
    for name, sample in (("EN_AI", EN_AI), ("EN_HUMAN_CASUAL", EN_HUMAN_CASUAL),
                         ("EN_HUMAN_ACADEMIC", EN_HUMAN_ACADEMIC), ("EL_AI", EL_AI),
                         ("EL_HUMAN_ACADEMIC", EL_HUMAN_ACADEMIC)):
        check(f"{name} → χωρίς προειδοποίηση δικαιοσύνης",
              _analyze(sample)["fairness"]["warning"] is None)

    # --- Κόλπα παράκαμψης ανιχνευτών ---
    import obfuscation_check as oc
    for name, sample in (("EN_AI", EN_AI), ("EN_HUMAN_ACADEMIC", EN_HUMAN_ACADEMIC),
                         ("EL_AI", EL_AI), ("EL_HUMAN_CASUAL", EL_HUMAN_CASUAL)):
        check(f"{name} → κανένα κόλπο παράκαμψης", not oc.check_obfuscation(sample)["findings"])
    sci = ("The TNFα and IFNγ levels were 5 μm and 3 μg/mL; ΔG was negative. Ο ασθενής "
           "έλαβε IL-6 και εμβόλιο mRNA. Bonjour\u202f! Le prix est de 10\u202f000 euros\u202f;")
    check("Επιστημονικά σύμβολα / γαλλική τυπογραφία → όχι ψευδώς θετικό",
          not oc.check_obfuscation(sci)["findings"])
    tricked = ("The pаper discusses ethicаl issues in reseаrch. Artificial intel\u200bligence "
               "is impor\u200btant for socie\u200bty. We used counterfeit consciousness and "
               "profound learning with an irregular woodland." + " word\u2009word" * 12)
    codes = {f["code"] for f in oc.check_obfuscation(tricked)["findings"]}
    check(f"Κρυφοί χαρακτήρες, ομοιόγλυφα, κενά, βασανισμένες φράσεις ({sorted(codes)})",
          codes == set(oc.FINDING_CODES))
    gr = oc.check_obfuscation("Η τεχνoλογία είναι σημαντική. Η εκπαίδευση Kαι η ΕΡEΥΝΑ.")
    check("Λατινικά ομοιόγλυφα μέσα σε ελληνικές λέξεις",
          [f["code"] for f in gr["findings"]] == ["homoglyphs"])

    # --- Σύγκριση εργασιών μεταξύ τους ---
    from plagiarism_engine import pairwise_similarity
    sentences = EN_HUMAN_ACADEMIC.split(".")
    copied = ".".join(sentences[: len(sentences) // 2]) + ". " + EN_HUMAN_CASUAL
    pairs = pairwise_similarity([("anna.docx", EN_HUMAN_ACADEMIC), ("bob.docx", copied),
                                 ("chris.docx", EN_AI), ("dora.docx", EL_HUMAN_ACADEMIC)])
    check(f"Μαζικά: βρέθηκε μόνο το ζεύγος anna–bob ({[(p['a'], p['b']) for p in pairs]})",
          [(p["a"], p["b"]) for p in pairs] == [("anna.docx", "bob.docx")]
          and pairs[0]["a_pct"] > 30)

    disguised = EN_AI.replace("a", "\u0430", 40).replace("e", "\u0435", 30).replace("tion", "ti\u200bon")
    dp = pairwise_similarity([("chris", EN_AI), ("dimitra", disguised)])
    check(f"Αντίγραφο με ομοιόγλυφα/αόρατους χαρακτήρες εντοπίζεται (≥90%: {dp[0]['a_pct'] if dp else 0}%)",
          bool(dp) and dp[0]["a_pct"] >= 90)

    # --- Binoculars (χωρίς torch): απενεργοποιημένο, λάθος ρύθμιση, βαθμονόμηση ---
    import binoculars_check as bc
    saved_env = os.environ.pop("AI_DETECTOR_BINOCULARS", None)
    try:
        check("Binoculars χωρίς ενεργοποίηση → disabled (δεν φορτώνεται τίποτα)",
              bc.check_binoculars(EN_AI) == {"status": "disabled"})
        os.environ["AI_DETECTOR_BINOCULARS"] = "δεν-υπάρχει"
        bc._scorer = bc._settings = bc._load_error = None
        bad = bc.check_binoculars(EN_AI)
        check("Binoculars με άγνωστο preset → unavailable, χωρίς εξαίρεση",
              bad["status"] == "unavailable" and "preset" in (bad.get("error") or ""))
    finally:
        os.environ.pop("AI_DETECTOR_BINOCULARS", None)
        if saved_env is not None:
            os.environ["AI_DETECTOR_BINOCULARS"] = saved_env
        bc._scorer = bc._settings = bc._load_error = None
    cal = bc.calibrate_threshold([0.70, 0.74, 0.78, 0.81], [0.88, 0.92, 0.95, 0.99])
    check(f"Βαθμονόμηση: όριο ανάμεσα σε AI και ανθρώπινα ({cal['threshold']:.3f})",
          0.81 < cal["threshold"] < 0.88 and cal["ai_detected"] == cal["human_correct"] == 1.0)
    check("Όρια του paper μόνο για το ζεύγος Falcon",
          bc.resolve_settings("falcon-7b")["threshold"] == 0.9015310749276843
          and bc.resolve_settings("qwen2.5-0.5b")["threshold"] in (None, bc.load_config().get("threshold")))

    # --- Κάθε κωδικός έχει κείμενο σε όλες τις γλώσσες του UI ---
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "detector_academic.html"), encoding="utf-8").read()
    n_langs = len(re.findall(r"^\s{12}[a-z]{2}: \{ button:", html, re.M))
    missing = [k for k in [f"ref_status_{c}" for c in rc.STATUSES]
               + [f"docx_f_{c}" for c in docx_forensics.FINDING_CODES]
               + [f"obf_f_{c}" for c in oc.FINDING_CODES]
               + ["bino_ai", "bino_human", "bino_uncalibrated", "bino_unavailable", "bino_too_short"]
               if len(re.findall(rf"^\s+{k}:", html, re.M)) != n_langs]
    check(f"Κείμενα UI για κάθε κωδικό σε {n_langs} γλώσσες (λείπουν: {missing})", not missing)

    ok = all(passed for _, passed in checks)
    if verbose:
        for name, passed in checks:
            print(f"{'✅' if passed else '❌'} {name}")
        print()
        print("=" * 60)
        print("EVIDENCE TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok


def _tiny_causal_lm_pair(seed_a: int = 1, seed_b: int = 2):
    """Δύο μικροσκοπικά GPT-2 με κοινό tokenizer, φτιαγμένα τοπικά (χωρίς λήψη)."""
    import torch
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast
    words = sorted({w.lower() for w in (EN_AI + EN_HUMAN_ACADEMIC + EN_HUMAN_CASUAL).split()})
    vocab = {"[UNK]": 0, **{w: i + 1 for i, w in enumerate(words)}}
    tk = Tokenizer(models.WordLevel(vocab=vocab, unk_token="[UNK]"))
    tk.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=tk, unk_token="[UNK]")
    cfg = GPT2Config(vocab_size=len(vocab), n_positions=1024, n_embd=32, n_layer=2, n_head=2,
                     bos_token_id=0, eos_token_id=0)
    torch.manual_seed(seed_a)
    observer = GPT2LMHeadModel(cfg)
    torch.manual_seed(seed_b)
    performer = GPT2LMHeadModel(cfg)
    return observer, performer, tokenizer


def PreTrainedTokenizerFast_with_other_vocab(tokenizer):
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast
    vocab = dict(tokenizer.get_vocab())
    vocab["extra-token"] = len(vocab)
    tk = Tokenizer(models.WordLevel(vocab=vocab, unk_token="[UNK]"))
    tk.pre_tokenizer = pre_tokenizers.Whitespace()
    return PreTrainedTokenizerFast(tokenizer_object=tk, unk_token="[UNK]")


def run_binoculars_tests() -> bool:
    """Πλήρης διαδρομή Binoculars με μικροσκοπικά τοπικά μοντέλα (θέλει torch+transformers)."""
    try:
        import torch
        import transformers  # noqa: F401
    except ImportError:
        import os
        required = bool(os.environ.get("BINOCULARS_TESTS_REQUIRED"))
        print(f"{'❌' if required else '⏭ '} BINOCULARS TESTS: παραλείπονται (λείπουν torch/transformers — "
              "pip install -r requirements-binoculars.txt)")
        return not required   # στο CI job του Binoculars η παράλειψη είναι αποτυχία
    import math
    import binoculars_check as bc

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    # Μαθηματικά έναντι απλής υλοποίησης αναφοράς (βρόχος ανά token)
    torch.manual_seed(0)
    T, V = 12, 7
    ids = torch.randint(0, V, (1, T))
    mask = torch.ones_like(ids)
    obs, perf = torch.randn(1, T, V), torch.randn(1, T, V)
    fast = bc.binoculars_scores(ids, mask, obs, perf)[0]
    ce = [-torch.log_softmax(perf[0, t], -1)[ids[0, t + 1]].item() for t in range(T - 1)]
    x = [-(torch.softmax(obs[0, t], -1) * torch.log_softmax(perf[0, t], -1)).sum().item() for t in range(T)]
    ref = (sum(ce) / len(ce)) / (sum(x) / len(x))
    check(f"Score = ppl / x_ppl όπως ο επίσημος κώδικας ({fast:.5f} ≈ {ref:.5f})", math.isclose(fast, ref, rel_tol=1e-5))

    observer, performer, tokenizer = _tiny_causal_lm_pair()
    scorer = bc.BinocularsScorer(observer, performer, tokenizer, max_tokens=64, max_chunks=3)
    long_text = (EN_AI + " " + EN_HUMAN_ACADEMIC) * 3
    r = scorer.score(long_text)
    check(f"Μεγάλο κείμενο → δείγμα έως 3 τμημάτων ({len(r['scores'])})", 1 <= len(r["scores"]) <= 3)
    check("Score θετικός πεπερασμένος αριθμός", all(s > 0 and math.isfinite(s) for s in r["scores"]))

    res = bc.check_binoculars(long_text, scorer=scorer,
                              settings={"preset": "tiny", "threshold": 1e9, "calibrated": True})
    check("Με όριο → ετυμηγορία ai/human", res["status"] == "ok" and res["verdict"] == "ai")
    res2 = bc.check_binoculars(long_text, scorer=scorer,
                               settings={"preset": "tiny", "threshold": None, "calibrated": False})
    check("Χωρίς βαθμονόμηση → score χωρίς ετυμηγορία", res2["status"] == "ok" and res2["verdict"] is None)
    check("Πολύ μικρό κείμενο → too_short",
          bc.check_binoculars("λίγες λέξεις", scorer=scorer)["status"] == "too_short")

    # Φόρτωση από δίσκο με τον ίδιο κώδικα που χρησιμοποιεί ο server
    import tempfile
    tmp = tempfile.mkdtemp(prefix="ai_bino_")
    for name, model in (("obs", observer), ("perf", performer)):
        model.save_pretrained(f"{tmp}/{name}")
        tokenizer.save_pretrained(f"{tmp}/{name}")
    import warnings
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        loaded = bc.load_scorer(f"{tmp}/obs", f"{tmp}/perf")
    check("load_scorer φορτώνει μοντέλα από φάκελο", loaded.score(long_text)["scores"])
    check("Χωρίς προειδοποιήσεις απόσυρσης παραμέτρων",
          not [w for w in caught if "dtype" in str(w.message)])
    other_vocab = PreTrainedTokenizerFast_with_other_vocab(tokenizer)
    other_vocab.save_pretrained(f"{tmp}/perf2")
    performer.save_pretrained(f"{tmp}/perf2")
    try:
        bc.load_scorer(f"{tmp}/obs", f"{tmp}/perf2")
        mismatch_rejected = False
    except ValueError:
        mismatch_rejected = True
    check("Διαφορετικός tokenizer → απόρριψη (το Binoculars θέλει ίδιο)", mismatch_rejected)

    # Instruct μοντέλο με επιπλέον special token συνομιλίας (όπως Meltemi/Krikri Instruct)
    import copy
    chat_tok = copy.deepcopy(tokenizer)
    chat_tok.add_special_tokens({"additional_special_tokens": ["<|im_start|>"]})
    check("Επιπλέον special token στο instruct → συμβατός tokenizer",
          bc.tokenizers_compatible(tokenizer, chat_tok) and bc.tokenizers_compatible(chat_tok, tokenizer))
    check("Επιπλέον ΚΑΝΟΝΙΚΗ λέξη → ασύμβατος",
          not bc.tokenizers_compatible(tokenizer, PreTrainedTokenizerFast_with_other_vocab(tokenizer)))
    perf_chat = copy.deepcopy(performer)
    perf_chat.resize_token_embeddings(len(chat_tok))
    chat_tok.save_pretrained(f"{tmp}/perf_chat")
    perf_chat.save_pretrained(f"{tmp}/perf_chat")
    try:
        chat_scores = bc.load_scorer(f"{tmp}/obs", f"{tmp}/perf_chat").score(long_text)["scores"]
    except Exception as e:
        print("   ", repr(e))
        chat_scores = []
    check("Φόρτωση/score με instruct που έχει μεγαλύτερο λεξιλόγιο",
          chat_scores and all(math.isfinite(x) and x > 0 for x in chat_scores))
    extra = torch.cat([perf, torch.full((1, T, 3), -1e4)], dim=-1)
    check("Κοινό λεξιλόγιο: επιπλέον (αμελητέες) στήλες logits δεν αλλάζουν το score",
          math.isclose(bc.binoculars_scores(ids, mask, obs, extra)[0], fast, rel_tol=1e-5))

    # Ίδιο μοντέλο ως observer και performer: x_ppl = εντροπία του μοντέλου
    same = bc.BinocularsScorer(observer, observer, tokenizer, max_tokens=64, max_chunks=1)
    check("Ίδιο μοντέλο και στους δύο ρόλους λειτουργεί", same.score(EN_AI)["scores"])

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(f"{'✅' if passed else '❌'} {name}")
    print()
    print("=" * 60)
    print("BINOCULARS TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
    print("=" * 60)
    return ok


def run_i18n_tests(verbose: bool = True) -> bool:
    """Κάθε κείμενο αποτελέσματος που βλέπει ο χρήστης πρέπει να υπάρχει σε
    όλες τις γλώσσες του UI (πεδία *_i18n) — αλλιώς η αλλαγή γλώσσας δείχνει
    μισά ελληνικά/μισά αγγλικά."""
    from model_signature import detect_model_signature
    from detector_engine import UI_LANGS as langs

    def complete(d) -> bool:
        return isinstance(d, dict) and all(isinstance(d.get(l), (str, list)) and d.get(l)
                                           for l in langs)

    ok = True
    problems = []
    texts = {
        "EN": ("Moreover, it is important to note that AI plays a crucial role. "
               "However, the tapestry of innovation is multifaceted. Furthermore, "
               "it fosters growth, innovation, and collaboration. In conclusion, "
               "AI is a testament to progress."),
        "EL": ("Στη σημερινή εποχή, η τεχνητή νοημοσύνη διαδραματίζει καθοριστικό ρόλο "
               "στην εκπαίδευση. Είναι σημαντικό να σημειωθεί ότι αυτό αποτελεί "
               "αναπόσπαστο κομμάτι της εξέλιξης. Επιπροσθέτως, η ολιστική προσέγγιση "
               "προσφέρει πολλαπλά οφέλη."),
    }
    for name, text in texts.items():
        r = analyze_text(text)
        for key in ("verdict_i18n", "language_i18n"):
            if not complete(r.get(key)):
                problems.append(f"{name}: {key}")
        for f in r["features"] + r["human_markers_detail"]:
            for key in ("label_i18n", "detail_i18n"):
                if not complete(f.get(key)):
                    problems.append(f"{name}: {f['name']}.{key}")
        for e in r["revision_guide"]:
            for key in ("label_i18n", "advice_i18n"):
                if not complete(e.get(key)):
                    problems.append(f"{name}: guide {e['feature']}.{key}")
        for h in r["highlights"]:
            if not complete(h.get("hits_i18n")):
                problems.append(f"{name}: highlight hits_i18n")
        sig = detect_model_signature(text)
        for model, m in sig["models"].items():
            for pat in m["patterns"]:
                if not complete(pat.get("description_i18n")):
                    problems.append(f"{name}: {model}.{pat['pattern']}.description_i18n")

    ok = not problems
    if verbose:
        for prob in problems:
            print(f"❌ Λείπει μετάφραση: {prob}")
        print()
        print("=" * 60)
        print("I18N TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok

# ============================================================================
# Ταχύτητα & ασφάλεια εξωτερικών ελέγχων: cache, ομαδικά DOI, keep-alive (χωρίς δίκτυο)
# ============================================================================

def run_web_speed_tests(verbose: bool = True) -> bool:
    import http.server
    import tempfile
    import threading
    import http_pool
    import plagiarism_engine as pe
    import reference_check as rc
    from web_cache import WebCache, cache_key

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    tmp = tempfile.mkdtemp(prefix="ai_webcache_")

    # --- WebCache: βασικά + ιδιωτικότητα + ανθεκτικότητα ---
    db = os.path.join(tmp, "c.sqlite3")
    c = WebCache(db)
    secret = "Η μυστική πρόταση της φοιτήτριας για την εργασία"
    c.put("wiki:el", secret, {"query": {"searchinfo": {"totalhits": 2}}})
    check("Cache: ό,τι γράφεται διαβάζεται ξανά",
          c.get("wiki:el", secret) == {"query": {"searchinfo": {"totalhits": 2}}})
    check("Cache: άλλος χώρος ονομάτων δεν μπερδεύεται", c.get("wiki:en", secret) is None)
    with open(db, "rb") as fh:
        raw = fh.read()
    check("Cache: το κείμενο της εργασίας ΔΕΝ αποθηκεύεται (μόνο SHA-256)",
          secret.encode() not in raw and len(cache_key("a", "b")) == 64)
    if os.name == "posix":
        check("Cache: αρχείο μόνο για τον χρήστη (0600)", (os.stat(db).st_mode & 0o777) == 0o600)
    evil = "x'); DROP TABLE cache; --"
    c.put("ref", evil, {"status": "verified"})
    check("Cache: εισαγωγή SQL δεν έχει επίδραση",
          c.get("ref", evil) == {"status": "verified"} and c.get("wiki:el", secret) is not None)
    c.put("ref", "huge", {"x": "a" * 200_000})
    check("Cache: τεράστια τιμή απορρίπτεται", c.get("ref", "huge") is None)
    st = c.stats()
    check(f"Cache: στατιστικά ({st['entries']} εγγραφές, {st['bytes']} bytes)",
          st["enabled"] and st["entries"] >= 2 and st["bytes"] > 0)
    c._conn.execute("UPDATE cache SET expires = 0 WHERE k = ?", (cache_key("ref", evil),))
    check("Cache: ληγμένη εγγραφή αγνοείται", c.get("ref", evil) is None)
    c._conn.execute("UPDATE cache SET v = 'not json{' WHERE k = ?", (cache_key("wiki:el", secret),))
    check("Cache: χαλασμένη τιμή αγνοείται χωρίς εξαίρεση", c.get("wiki:el", secret) is None)
    c2 = WebCache(os.path.join(tmp, "clear.sqlite3"))
    c2.put("a", "b", {"x": 1})
    c2.clear()
    check("Cache: καθαρισμός σβήνει τα πάντα", c2.get("a", "b") is None and c2.stats()["entries"] == 0)
    bad = os.path.join(tmp, "bad.sqlite3")
    with open(bad, "wb") as fh:
        fh.write(b"this is not a database" * 100)
    cb = WebCache(bad)
    cb.put("x", "y", {"a": 1})
    check("Cache: χαλασμένο αρχείο → απενεργοποίηση, χωρίς εξαίρεση",
          cb.get("x", "y") is None and not cb.enabled)

    # --- Αναφορές: ομαδικά DOI στο OpenAlex + cache ---
    calls = []

    def batch_web(url):
        calls.append(url)
        if "api.openalex.org" in url and "filter=doi" in url:
            return {"results": [
                {"doi": "https://doi.org/10.18653/v1/n19-1423", "publication_year": 2019,
                 "title": "BERT: Pre-training of Deep Bidirectional Transformers for "
                          "Language Understanding"},
                {"doi": "https://doi.org/10.1038/s41592-020-0001", "publication_year": 2020,
                 "title": "A completely different paper about soil bacteria"}]}
        return _fake_scholarly_web(url)

    expected = ["verified", "verified", "doi_not_found", "doi_mismatch", "not_found",
                "not_found", "skipped_web"]
    ref_cache = WebCache(os.path.join(tmp, "refs.sqlite3"))
    r1 = rc.check_references(SAMPLE_REFERENCES, http_get=batch_web, delay=0, cache=ref_cache)
    doi_calls = [u for u in calls if "api.crossref.org/works/10." in u]
    filters = [u for u in calls if "filter=doi" in u]
    check(f"Ομαδικά DOI: 1 αίτημα OpenAlex, Crossref μόνο για όσα λείπουν ({len(doi_calls)})",
          len(filters) == 1 and len(doi_calls) == 1 and "10.9999" in doi_calls[0])
    check(f"Ομαδικά DOI: ίδια αποτελέσματα ({[r['status'] for r in r1['results']]})",
          [r["status"] for r in r1["results"]] == expected)
    calls.clear()
    r2 = rc.check_references(SAMPLE_REFERENCES, http_get=batch_web, delay=0, cache=ref_cache)
    check(f"Ξαναέλεγχος ίδιας βιβλιογραφίας: 0 αιτήματα (έγιναν {len(calls)}), ίδια αποτελέσματα",
          not calls and [r["status"] for r in r2["results"]] == expected)
    check("DOI με | ή κενό δεν μπαίνει στο ομαδικό φίλτρο",
          rc.prefetch_dois([{"doi": "10.1234/a|doi:10.5555/b"}], lambda u: calls.append(u)) == {}
          and not calls)

    def broken(_url):
        raise OSError("no network")
    empty_cache = WebCache(os.path.join(tmp, "off.sqlite3"))
    rc.check_references(SAMPLE_REFERENCES, http_get=broken, delay=0, cache=empty_cache)
    check("Σφάλματα δικτύου δεν αποθηκεύονται στην cache",
          empty_cache._conn is None or empty_cache._conn.execute(
              "SELECT COUNT(*) FROM cache").fetchone()[0] == 0)

    # --- Wikipedia: cache «0 αποτελεσμάτων» μόνο μετά από επιτυχές canary ---
    wiki_text = EN_HUMAN_ACADEMIC
    saved_search, saved_delay = pe._wiki_search, pe.REQUEST_DELAY
    saved_slow, saved_until = pe.SLOW_DELAY, pe._wiki_slow_until
    pe.REQUEST_DELAY = pe.SLOW_DELAY = 0
    wiki_calls = []

    def fake_wiki(canary_ok):
        def f(lang, q):
            wiki_calls.append(q)
            if "Turing" in q:
                return {"query": {"searchinfo": {"totalhits": 1 if canary_ok else 0}, "search": []}}
            return {"query": {"searchinfo": {"totalhits": 0}, "search": []}}
        return f
    try:
        wc = WebCache(os.path.join(tmp, "wiki.sqlite3"))
        pe._wiki_search = fake_wiki(canary_ok=False)
        w1 = pe.check_wikipedia(wiki_text, max_sentences=6, cache=wc)
        n1 = len(wiki_calls)
        wiki_calls.clear()
        w2 = pe.check_wikipedia(wiki_text, max_sentences=6, cache=wc)
        check(f"Wikipedia: αποτυχημένο canary → τίποτα στην cache ({w1['status']}, "
              f"ξανά {len(wiki_calls)} αιτήματα)",
              w1["status"] == "degraded" and len(wiki_calls) == n1 and w2["status"] == "degraded")
        pe._wiki_search = fake_wiki(canary_ok=True)
        wiki_calls.clear()
        w3 = pe.check_wikipedia(wiki_text, max_sentences=6, cache=wc)
        wiki_calls.clear()
        w4 = pe.check_wikipedia(wiki_text, max_sentences=6, cache=wc)
        check(f"Wikipedia: επιβεβαιωμένα «καθαρά» από cache → 0 αιτήματα ({len(wiki_calls)})",
              w3["status"] == "ok" and w4["status"] == "ok" and not wiki_calls
              and w4["checked"] == w3["checked"] > 0)
    finally:
        pe._wiki_search, pe.REQUEST_DELAY = saved_search, saved_delay
        pe.SLOW_DELAY, pe._wiki_slow_until = saved_slow, saved_until

    # --- Wikipedia: ρυθμός 1 s, σειριακά σε όλο τον server, πιο αργά μετά από throttling ---
    import time as _t
    import urllib.error as _ue2
    saved = (pe._wiki_search, pe.REQUEST_DELAY, pe.SLOW_DELAY, pe._wiki_slow_until, pe._wiki_last)
    pe.REQUEST_DELAY, pe.SLOW_DELAY, pe._wiki_slow_until, pe._wiki_last = 0.05, 0.15, 0.0, 0.0
    stamps, active, overlap = [], [0], [False]

    def timed(lang, q):
        active[0] += 1
        overlap[0] = overlap[0] or active[0] > 1
        stamps.append(_t.time())
        _t.sleep(0.01)
        active[0] -= 1
        return {"query": {"searchinfo": {"totalhits": 0}, "search": []}}
    try:
        pe._wiki_search = timed
        threads = [threading.Thread(target=lambda: [pe._wiki_paced_search("en", f"q{i}")
                                                    for i in range(3)]) for _ in range(3)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        check(f"Wikipedia: 9 αιτήματα από 3 νήματα, ποτέ ταυτόχρονα, παύση ≥ ρυθμού "
              f"(ελάχ. {min(gaps):.3f}s)",
              len(stamps) == 9 and not overlap[0] and min(gaps) >= 0.05)
        normal = pe._wiki_delay()

        def throttled(lang, q):
            raise _ue2.HTTPError("https://en.wikipedia.org/w/api.php", 429, "Too Many", {"Retry-After": "0"}, None)
        pe._wiki_search = saved[0]
        saved_api = pe._wiki_api
        pe._wiki_api = lambda lang, params, timeout=5.0: throttled(lang, params)
        try:
            pe._wiki_search("en", "x")
        except pe._RateLimited:
            pass
        finally:
            pe._wiki_api = saved_api
        check(f"Wikipedia: μετά από 429 ο ρυθμός πέφτει ({normal}s → {pe._wiki_delay()}s)",
              normal == 0.05 and pe._wiki_delay() == 0.15)
        check("User-Agent με στοιχεία επικοινωνίας (πολιτική Wikimedia: URL project)",
              pe.PROJECT_URL in pe.USER_AGENT and "@" not in pe.USER_AGENT)
        saved_env = os.environ.pop("AI_DETECTOR_CONTACT_EMAIL", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                empty_cfg = os.path.join(td, "none.json")
                check("Χωρίς email: κανένα email στον κώδικα / στα αιτήματα",
                      pe.contact_email(empty_cfg) is None)
                os.environ["AI_DETECTOR_CONTACT_EMAIL"] = "someone@example.org"
                check("Email από AI_DETECTOR_CONTACT_EMAIL → mailto σε UA και OpenAlex",
                      pe.contact_email(empty_cfg) == "someone@example.org"
                      and "mailto:someone@example.org" in pe.polite_user_agent()
                      and pe.openalex_params({}).get("mailto") == "someone@example.org")
                os.environ["AI_DETECTOR_CONTACT_EMAIL"] = "bad value; x@y"
                check("Άκυρο email αγνοείται (όχι injection στο User-Agent)",
                      pe.contact_email(empty_cfg) is None and "mailto" not in pe.polite_user_agent())
                cfg = os.path.join(td, "cfg.json")
                with open(cfg, "w", encoding="utf-8") as fh:
                    json.dump({"contact_email": "me@example.org"}, fh)
                os.environ.pop("AI_DETECTOR_CONTACT_EMAIL", None)
                check("Email από search_config.json (contact_email)",
                      pe.contact_email(cfg) == "me@example.org")
        finally:
            os.environ.pop("AI_DETECTOR_CONTACT_EMAIL", None)
            if saved_env is not None:
                os.environ["AI_DETECTOR_CONTACT_EMAIL"] = saved_env
    finally:
        (pe._wiki_search, pe.REQUEST_DELAY, pe.SLOW_DELAY, pe._wiki_slow_until,
         pe._wiki_last) = saved

    # --- OpenAlex (Semantic Scholar): cache ---
    saved_api, saved_od = pe._openalex_api, pe.OPENALEX_DELAY
    pe.OPENALEX_DELAY = 0
    oa_calls = []

    def fake_oa(params):
        oa_calls.append(params)
        return {"meta": {"count": 1}, "results": [{"title": "Found paper", "publication_year": 2020,
                                                   "doi": "https://doi.org/10.1/x", "id": "W1"}]}
    try:
        pe._openalex_api = fake_oa
        sc = WebCache(os.path.join(tmp, "oa.sqlite3"))
        s1 = pe.check_scholar(EN_HUMAN_ACADEMIC, max_sentences=4, cache=sc)
        n1 = len(oa_calls)
        s2 = pe.check_scholar(EN_HUMAN_ACADEMIC, max_sentences=4, cache=sc)
        check(f"OpenAlex: ξαναέλεγχος από cache ({n1} → {len(oa_calls) - n1} αιτήματα), ίδια ευρήματα",
              n1 > 0 and len(oa_calls) == n1 and s1["hits"] == s2["hits"] and s2["hits"])
    finally:
        pe._openalex_api, pe.OPENALEX_DELAY = saved_api, saved_od

    # --- OpenAlex API key: μόνο έγκυρη μορφή, ποτέ στα μηνύματα ---
    saved_key = os.environ.get("OPENALEX_API_KEY")
    try:
        os.environ["OPENALEX_API_KEY"] = "abc&mailto=evil@x.com"
        check("OpenAlex key με ύποπτους χαρακτήρες αγνοείται",
              "api_key" not in pe.openalex_params({}))
        os.environ["OPENALEX_API_KEY"] = "Abcdef123456"
        check("Έγκυρο OpenAlex key προστίθεται", pe.openalex_params({})["api_key"] == "Abcdef123456")
    finally:
        if saved_key is None:
            os.environ.pop("OPENALEX_API_KEY", None)
        else:
            os.environ["OPENALEX_API_KEY"] = saved_key

    # --- http_pool: λίστα επιτρεπτών διευθύνσεων ---
    blocked = 0
    for url in ("http://api.crossref.org/works", "https://evil.example.com/x",
                "https://user:pw@api.crossref.org/works", "https://api.crossref.org:8443/works",
                "https://api.crossref.org.evil.com/works", "file:///etc/passwd",
                "https://169.254.169.254/latest/meta-data/"):
        try:
            http_pool.get_json(url)
        except ValueError:
            blocked += 1
        except Exception:
            pass
    check(f"http_pool: μπλοκάρονται μη επιτρεπτές διευθύνσεις ({blocked}/7)", blocked == 7)

    # --- http_pool: keep-alive, 404/429 ως HTTPError, όριο μεγέθους (τοπικός server) ---
    connections = []

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            connections.append(1)
            super().setup()

        def do_GET(self):
            if self.path.startswith("/missing"):
                body, code = b'{"error": 1}', 404
            elif self.path.startswith("/huge"):
                body, code = b"[" + b"1," * (http_pool.MAX_RESPONSE_BYTES // 2) + b"1]", 200
            else:
                body, code = b'{"ok": true}', 200
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    saved_conn, saved_proxy = http_pool._connection, http_pool._uses_proxy
    import http.client as _hc
    local_pool = {}

    def local_connection(host, timeout):
        conn = local_pool.get(host)
        if conn is None:
            conn = local_pool[host] = _hc.HTTPConnection("127.0.0.1", port, timeout=timeout)
        return conn

    def local_drop(host):
        conn = local_pool.pop(host, None)
        if conn:
            conn.close()
    saved_drop = http_pool._drop
    http_pool._connection, http_pool._drop = local_connection, local_drop
    http_pool._uses_proxy = lambda host: False
    try:
        results = [http_pool.get_json("https://api.crossref.org/works?q=1") for _ in range(5)]
        check(f"http_pool: 5 αιτήματα από 1 σύνδεση (keep-alive: {len(connections)})",
              results == [{"ok": True}] * 5 and len(connections) == 1)
        import urllib.error as _ue
        try:
            http_pool.get_json("https://api.crossref.org/missing?api_key=SECRET123")
            got404 = None
        except _ue.HTTPError as e:
            got404 = e
        check("http_pool: 404 → HTTPError χωρίς το API key στο μήνυμα",
              got404 is not None and got404.code == 404 and "SECRET123" not in str(got404)
              and "SECRET123" not in (got404.filename or ""))
        try:
            http_pool.get_json("https://api.crossref.org/huge")
            too_big = False
        except http_pool.ResponseTooLarge:
            too_big = True
        check("http_pool: τεράστια απάντηση απορρίπτεται (όριο μνήμης)", too_big)
        check("http_pool: συνεχίζει κανονικά μετά από σφάλμα",
              http_pool.get_json("https://api.crossref.org/works?q=2") == {"ok": True})
    finally:
        http_pool._connection, http_pool._drop, http_pool._uses_proxy = saved_conn, saved_drop, saved_proxy
        for conn in local_pool.values():
            conn.close()
        srv.shutdown()
        srv.server_close()

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("ΤΑΧΥΤΗΤΑ & ΑΣΦΑΛΕΙΑ ΕΞΩΤΕΡΙΚΩΝ ΕΛΕΓΧΩΝ")
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("WEB SPEED TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok

# ============================================================================
# Εκκίνηση (launcher.py) και ενημέρωση (tools/update.py) — χωρίς δίκτυο
# ============================================================================

def run_tooling_tests(verbose: bool = True) -> bool:
    import http.server
    import subprocess
    import tempfile
    import threading
    from pathlib import Path
    import launcher
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
    import update

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    tmp = Path(tempfile.mkdtemp(prefix="ai_tooling_"))

    # --- Βιβλιοθήκες: εγκατάσταση μόνο όταν αλλάζει το requirements.txt ---
    calls = []
    saved = (launcher.MARKER, launcher.subprocess.run)
    try:
        launcher.MARKER = tmp / "marker"

        def fake_run(cmd, *a, **k):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)
        launcher.subprocess.run = fake_run
        first = launcher.ensure_requirements()
        second = launcher.ensure_requirements()
        check(f"Launcher: pip μόνο την 1η φορά ({len(calls)} κλήση), όχι σε κάθε εκκίνηση",
              first and second and len(calls) == 1 and "-r" in calls[0])
        launcher.MARKER.write_text("παλιό", encoding="utf-8")
        launcher.ensure_requirements()
        check("Launcher: νέα εγκατάσταση όταν αλλάξει το requirements.txt", len(calls) == 2)
        launcher.MARKER.unlink()
        launcher.subprocess.run = lambda cmd, *a, **k: subprocess.CompletedProcess(cmd, 1)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out:     # το αναμενόμενο μήνυμα σφάλματος
            failed = not launcher.ensure_requirements()
        check("Launcher: αποτυχία pip → μήνυμα, χωρίς marker (ξαναδοκιμάζει την επόμενη φορά)",
              failed and not launcher.MARKER.exists() and "internet" in out.getvalue())
    finally:
        launcher.MARKER, launcher.subprocess.run = saved

    # --- «Τρέχει ήδη;»: ours / other / free ---
    class Handler(http.server.BaseHTTPRequestHandler):
        body = b'{"status": "ok"}'

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.body)))
            self.end_headers()
            self.wfile.write(self.body)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    saved_health = launcher.HEALTH
    try:
        launcher.HEALTH = f"http://127.0.0.1:{srv.server_address[1]}/health"
        ours = launcher.server_status()
        Handler.body = b"<html>other app</html>"
        other = launcher.server_status()
        srv.shutdown()
        srv.server_close()
        free = launcher.server_status()
        check(f"Launcher: αναγνωρίζει detector / άλλο πρόγραμμα / ελεύθερη θύρα ({ours}/{other}/{free})",
              (ours, other, free) == ("ours", "other", "free"))
    finally:
        launcher.HEALTH = saved_health

    # --- Ενημέρωση: μεταφορά ρυθμίσεων/δεδομένων ---
    old, new = tmp / "old", tmp / "new"
    for d in (old, new):
        (d / "corpus").mkdir(parents=True)
        (d / "ai_detector_server.py").write_text("#", encoding="utf-8")
        (d / "detector_engine.py").write_text("#", encoding="utf-8")
    (old / "search_config.json").write_text('{"openalex_api_key": "Abcdef123456"}', encoding="utf-8")
    (old / ".web_cache.sqlite3").write_bytes(b"cache")
    (old / "corpus" / "thesis.docx").write_bytes(b"docx")
    (old / "corpus" / "evil.exe").write_bytes(b"MZ")
    (old / "corpus" / "notes.txt").write_text("παλιό", encoding="utf-8")
    (new / "corpus" / "notes.txt").write_text("νέο", encoding="utf-8")
    secret_target = tmp / "secret_outside.txt"
    secret_target.write_text("μυστικό", encoding="utf-8")
    try:
        (old / "corpus" / "link.txt").symlink_to(secret_target)
        made_link = True
    except OSError:
        made_link = False
    report = update.migrate(old, new)
    check("Ενημέρωση: μεταφέρονται κλειδιά, cache και εργασίες corpus",
          (new / "search_config.json").read_text(encoding="utf-8").startswith('{"openalex')
          and (new / ".web_cache.sqlite3").exists() and (new / "corpus" / "thesis.docx").exists())
    check("Ενημέρωση: δεν αντικαθίσταται αρχείο που υπάρχει ήδη",
          (new / "corpus" / "notes.txt").read_text(encoding="utf-8") == "νέο"
          and "corpus/notes.txt" in report["exists"])
    check("Ενημέρωση: μόνο αρχεία εργασιών στο corpus (όχι .exe)",
          not (new / "corpus" / "evil.exe").exists())
    if made_link:
        check("Ενημέρωση: συντομεύσεις/symlinks αγνοούνται (δεν διαρρέουν αρχεία εκτός φακέλου)",
              not (new / "corpus" / "link.txt").exists())
    if os.name == "posix":
        check("Ενημέρωση: το αρχείο κλειδιών παίρνει δικαιώματα μόνο για τον χρήστη (0600)",
              (os.stat(new / "search_config.json").st_mode & 0o777) == 0o600)
    check("Ενημέρωση: απορρίπτεται φάκελος που δεν είναι της εφαρμογής",
          not update.is_app_folder(tmp) and update.is_app_folder(old))

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("ΕΚΚΙΝΗΣΗ & ΕΝΗΜΕΡΩΣΗ")
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("TOOLING TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok

# ============================================================================
# ZIP από eClass/Moodle, εξαίρεση παραθεμάτων/βιβλιογραφίας, βαθμονόμηση
# ============================================================================

def run_import_calibration_tests(verbose: bool = True) -> bool:
    import io
    import tempfile
    import zipfile
    from pathlib import Path
    import score_calibration as sc
    import text_exclusions as te
    import zip_import as zi
    from plagiarism_engine import CorpusIndex

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    tmp = Path(tempfile.mkdtemp(prefix="ai_zip_"))
    out = tmp / "out"
    out.mkdir()

    def make_zip(entries):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in entries:
                if isinstance(item, zipfile.ZipInfo):
                    zf.writestr(item, b"x" * 100)
                else:
                    zf.writestr(item[0], item[1])
        path = tmp / f"z{len(list(tmp.glob('*.zip')))}.zip"
        path.write_bytes(buf.getvalue())
        return path

    # --- ZIP ---
    link = zipfile.ZipInfo("Νίκος_2_assignsubmission_file_/link.docx")
    link.external_attr = (0o120777 << 16)
    def set_encrypted(path, name):
        """Το zipfile μηδενίζει τη σημαία «κρυπτογραφημένο» στην εγγραφή — τη
        βάζουμε απευθείας στα bytes (τοπική κεφαλίδα + κεντρικός κατάλογος)."""
        raw = bytearray(path.read_bytes())
        nb = name.encode("utf-8")
        for sig, flag_off, name_off in ((b"PK\x03\x04", 6, 30), (b"PK\x01\x02", 8, 46)):
            i = raw.find(sig)
            while i != -1:
                if raw[i + name_off:i + name_off + len(nb)] == nb:
                    raw[i + flag_off] |= 0x1
                i = raw.find(sig, i + 1)
        path.write_bytes(bytes(raw))
    z = make_zip([
        ("Γιάννης Παπαδόπουλος_123456_assignsubmission_file_/εργασία.docx", b"doc1" * 100),
        ("Ελένη Κ_654321_assignsubmission_file_thesis.pdf", b"pdf" * 100),
        ("../../../evil.docx", b"evil" * 100),
        ("__MACOSX/._εργασία.docx", b"meta"),
        ("folder/virus.exe", b"MZ" * 100),
        ("inner.zip", b"PK" * 100),
        ("bomb.docx", b"\0" * (5 * 1024 * 1024)),
        link, ("Μαρία_3_assignsubmission_file_/secret.docx", b"secret" * 100),
    ])
    set_encrypted(z, "Μαρία_3_assignsubmission_file_/secret.docx")
    docs, skipped = zi.extract_documents(z, out)
    labels = {d["label"]: d for d in docs}
    check(f"ZIP: έγγραφα και ονόματα φοιτητών (Moodle) ({sorted(d['student'] for d in docs)})",
          labels["Γιάννης Παπαδόπουλος_123456_assignsubmission_file_/εργασία.docx"]["student"]
          == "Γιάννης Παπαδόπουλος"
          and labels["Ελένη Κ_654321_assignsubmission_file_thesis.pdf"]["student"] == "Ελένη Κ")
    check("ZIP: «../» δεν γράφει εκτός φακέλου (zip slip) — τυχαία ονόματα στον δίσκο",
          "evil.docx" in labels and not (tmp.parent / "evil.docx").exists()
          and all(Path(d["path"]).parent == out for d in docs)
          and not any("evil" in p.name for p in out.iterdir()))
    check(f"ZIP: παραλείπονται symlink, κρυπτογραφημένα, .exe, ZIP σε ZIP, __MACOSX ({skipped})",
          skipped.get("symlink") == 1 and skipped.get("encrypted") == 1 and skipped.get("type") == 2
          and skipped.get("system") == 1 and len(docs) == 3)
    check("ZIP: zip bomb (υπερβολική συμπίεση) παραλείπεται",
          skipped.get("too_large") == 1 and "bomb.docx" not in labels)
    many = make_zip([(f"f{i}.docx", b"d" * 50) for i in range(10)])
    docs2, sk2 = zi.extract_documents(many, out, max_docs=4)
    check("ZIP: όριο πλήθους εγγράφων", len(docs2) == 4 and sk2.get("limit") == 6)
    try:
        zi.extract_documents(make_zip([(f"e{i}.txt", b"") for i in range(zi.MAX_ENTRIES + 1)]), out)
        too_many = False
    except zi.ZipImportError as e:
        too_many = e.code == "too_many_entries"
    check("ZIP: υπερβολικά πολλές εγγραφές → σφάλμα", too_many)
    notzip = tmp / "not.zip"
    notzip.write_bytes(b"this is not a zip")
    try:
        zi.extract_documents(notzip, out)
        bad = False
    except zi.ZipImportError as e:
        bad = e.code == "bad_zip"
    check("ZIP: μη έγκυρο αρχείο → σφάλμα, χωρίς εξαίρεση Python", bad)
    info = zipfile.ZipInfo("x")
    info.filename = "Εργασία Μαρίας.docx".encode("cp737").decode("cp437")
    info.flag_bits = 0
    check("ZIP: ελληνικά ονόματα από τα Windows (cp737) διαβάζονται σωστά",
          zi._decode_name(info) == "Εργασία Μαρίας.docx")

    # --- Εξαίρεση παραθεμάτων / βιβλιογραφίας ---
    body = "Η ανάλυση των δεδομένων έδειξε σημαντικές διαφορές μεταξύ των ομάδων. " * 60
    quote_ = "η τεχνητή νοημοσύνη αλλάζει ριζικά τον τρόπο με τον οποίο μαθαίνουμε σήμερα"
    bib = ("\nΒιβλιογραφία\nVaswani, A. (2017). Attention is all you need. NeurIPS.\n"
           "Devlin, J. (2019). BERT: Pre-training of deep bidirectional transformers. NAACL.\n"
           "\nΠαράρτημα Α\nΠίνακες αποτελεσμάτων του πειράματος με όλες τις μετρήσεις.\n")
    doc = body + f"\nΌπως γράφει ο Παπαδόπουλος, «{quote_}» (2020). Κράτα «δύο λέξεις» εδώ.\n" + body + bib
    clean, info2 = te.exclude_for_similarity(doc)
    check(f"Εξαίρεση: παράθεμα 5+ λέξεων και βιβλιογραφία αφαιρούνται ({info2})",
          quote_ not in clean and "Vaswani" not in clean and info2["quotes"] == 1
          and info2["bibliography_words"] > 10)
    check("Εξαίρεση: σύντομα εισαγωγικά και παράρτημα μένουν",
          "«δύο λέξεις»" in clean and "Πίνακες αποτελεσμάτων" in clean)
    toc = "Περιεχόμενα\nΒιβλιογραφία\n" + body * 2
    check("Εξαίρεση: «Βιβλιογραφία» στον πίνακα περιεχομένων δεν σβήνει το κείμενο",
          te.exclude_for_similarity(toc)[1]["bibliography_words"] == 0)
    huge = "Λίγο κείμενο εδώ στην αρχή της εργασίας.\n" * 30 + "\nΒιβλιογραφία\n" + body * 3
    check("Εξαίρεση: ύποπτα μεγάλη «βιβλιογραφία» (>40%) δεν εξαιρείται",
          te.exclude_for_similarity(huge)[1]["bibliography_words"] == 0)
    cdir = tmp / "corpus"
    cdir.mkdir()
    other = ("Εντελώς διαφορετικό κείμενο για άλλο θέμα της πληροφορικής και των δικτύων. " * 40
             + f"\nΚατά τον συγγραφέα, «{quote_}».\n" + bib)
    (cdir / "old.txt").write_text(other, encoding="utf-8")
    idx = CorpusIndex(cdir)
    with_ = idx.compare(doc)["similarity"]
    without = idx.compare(clean)["similarity"]
    check(f"Εξαίρεση: κοινό παράθεμα + βιβλιογραφία δεν μετράνε ως ομοιότητα ({with_}% → {without}%)",
          with_ > 0 and without == 0)

    # --- Βαθμονόμηση ---
    try:
        sc.build_profile([10, 20])
        few = False
    except ValueError:
        few = True
    check("Βαθμονόμηση: χρειάζονται τουλάχιστον 10 ανθρώπινες εργασίες", few)
    human = [5, 8, 10, 12, 15, 18, 20, 22, 25, 30, 35, 40, 45, 50, 55, 60, 62, 65, 70, 90]
    prof = sc.build_profile(human, ai_scores=[80, 95, 99, 40], name="Νομική <b>x</b>\x07")
    check(f"Βαθμονόμηση: προτεινόμενο όριο με ≤5% ανθρώπινων πάνω ({prof['suggested_threshold']})",
          sum(1 for x in human if x >= prof["suggested_threshold"]) / len(human) <= 0.05
          and sum(1 for x in human if x >= prof["suggested_threshold"] - 1) / len(human) > 0.05
          and prof["ai_detection_rate"] == 75.0 and "\x07" not in prof["name"])
    pos = sc.position(62, prof)
    check(f"Βαθμονόμηση: θέση σκορ στις ανθρώπινες εργασίες ({pos['human_share_at_or_above']}%)",
          pos["human_share_at_or_above"] == 20.0 and pos["above_suggested"] is False)
    ppath = tmp / "calib.json"
    sc.save_profile(prof, ppath)
    check("Βαθμονόμηση: αποθήκευση/φόρτωση, αρχείο 0600, όχι λίστα σκορ στη σύνοψη",
          sc.load_profile(ppath)["n_human"] == 20
          and (os.name != "posix" or (os.stat(ppath).st_mode & 0o777) == 0o600)
          and "human_scores" not in sc.summary(prof))
    ppath.write_text('{"version": 1, "human_scores": ["<script>"]}', encoding="utf-8")
    check("Βαθμονόμηση: πειραγμένο αρχείο αγνοείται", sc.load_profile(ppath) is None)

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("ZIP · ΕΞΑΙΡΕΣΕΙΣ · ΒΑΘΜΟΝΟΜΗΣΗ")
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("IMPORT/CALIBRATION TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok


def run_report_tests(verbose: bool = True) -> bool:
    """Πρακτικό ελέγχου .docx: περιεχόμενο, ακραία/κακόβουλα δεδομένα, endpoint."""
    import io
    from docx import Document
    from report_docx import MAX_FIELD, MAX_NOTES, build_report
    import ai_detector_server as srv

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    def doc_text(data):
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.extend(c.text for c in row.cells)
        return "\n".join(parts)

    analysis = {
        "score": 72.4, "verdict": "Πιθανώς AI", "verdict_i18n": {"el": "Πιθανώς AI", "en": "Likely AI"},
        "reliability": 80, "text_stats": {"words": 12345},
        "calibration": {"n_human": 20, "human_share_at_or_above": 5.0, "suggested_threshold": 70},
        "binoculars": {"score": 0.81, "verdict": "ai"},
        "plagiarism": {"corpus": {"similarity": 18.5, "sources": [{"file": "old_thesis.docx", "similarity": 12.0}]},
                       "wikipedia": {"status": "ok", "hit_count": 2},
                       "brave": {"status": "not_configured", "hits": []},
                       "excluded": {"quotes": 3, "quoted_words": 60, "bibliography_words": 900}},
        "references": {"checked": 10, "total": 12, "counts": {"verified": 8, "not_found": 2}},
        "obfuscation": {"findings": [{"code": "homoglyphs"}]},
        "docx_history": {"findings": [{"code": "single_session", "level": "warn"},
                                      {"code": "many_sessions", "level": "info"}]},
        "fairness": {"warning": "simple_vocabulary"},
    }
    meta = {"institution": "Πανεπιστήμιο Πειραιώς", "student": "Μαρία Π. (ΑΜ 123)", "examiner": "Δρ. Χ",
            "notes": "Γραμμή 1\nΓραμμή 2"}
    text = doc_text(build_report(analysis, meta, lang="el", app_version="2.19"))
    check("Πρακτικό: στοιχεία, σκορ, ετυμηγορία, πηγή corpus, αναφορές",
          all(x in text for x in ("Πανεπιστήμιο Πειραιώς", "Μαρία Π. (ΑΜ 123)", "72.4%", "Πιθανώς AI",
                                  "old_thesis.docx", "επιβεβαιωμένες: 8", "δεν βρέθηκαν: 2", "v2.19")))
    check("Πρακτικό: σημειώσεις εξεταστή περνούν (και σε γραμμές)", "Γραμμή 1" in text and "Γραμμή 2" in text)
    check("Πρακτικό: βαθμονόμηση, εξαιρέσεις, Binoculars, μη ρυθμισμένο Brave = «δεν ελέγχθηκε»",
          "5.0% των 20" in text and "3 παραθέματα" in text and "μοιάζει με AI" in text
          and "Brave: δεν ελέγχθηκε" in text and "Wikipedia: 2" in text)
    check("Πρακτικό: μόνο προειδοποιήσεις Word (όχι info), κόλπα, αποποίηση, υπογραφή",
          "γράφτηκε σε μία συνεδρία" in text and "many_sessions" not in text
          and "ομοιόγλυφα" in text and "ΟΧΙ απόδειξη" in text and "Υπογραφή" in text)
    en = doc_text(build_report(analysis, meta, lang="en"))
    check("Πρακτικό: αγγλικά", "Paper check report" in en and "Likely AI" in en and "NOT proof" in en)
    de = doc_text(build_report(analysis, meta, lang="de"))
    check("Πρακτικό: γερμανικά (τίτλος/αποποίηση) και άγνωστη γλώσσα → αγγλικά",
          "Prüfprotokoll" in de and "Paper check report" in doc_text(build_report(analysis, meta, lang="xx")))

    evil = "\x00\x01<w:t>&amp;\x0b\ufffe" + "Α" * 5000
    try:
        data = build_report({"score": "<x>", "plagiarism": [], "references": None,
                             "obfuscation": {"findings": ["x", None, {"code": evil}]},
                             "binoculars": {"score": float("nan")}, "text_stats": {"words": True}},
                            {"institution": evil, "notes": evil * 3, "student": ["λίστα"]}, lang=None)
        bad = doc_text(data)
        ok_evil = ("\x00" not in bad and "<w:t>&amp;" in bad
                   and max(len(line) for line in bad.split("\n")) <= MAX_NOTES)
        long_field = max(len(c.text) for t in Document(io.BytesIO(data)).tables
                         for row in t.rows for c in row.cells)
        ok_evil = ok_evil and long_field <= MAX_FIELD
    except Exception as e:
        print("   ", repr(e))
        ok_evil = False
    check("Πρακτικό: κακόβουλα/λάθος τύπου δεδομένα δεν το ρίχνουν, XML-escape, όρια μήκους", ok_evil)
    try:
        doc_text(build_report(None, None))
        ok_empty = True
    except Exception:
        ok_empty = False
    check("Πρακτικό: κενά δεδομένα → έγκυρο αρχείο", ok_empty)

    client = srv.app.test_client()
    local = {"Host": "localhost:5000", "X-UI-Lang": "en"}
    r = client.post("/report/docx", json={"analysis": analysis, "meta": meta}, headers=local)
    cd = r.headers.get("Content-Disposition", "")
    check("POST /report/docx → .docx συνημμένο, σταθερό ASCII όνομα, no-store",
          r.status_code == 200 and r.data[:2] == b"PK" and "attachment" in cd
          and "check_report_" in cd and r.headers.get("Cache-Control") == "no-store"
          and "Paper check report" in doc_text(r.data))
    meta_evil = dict(meta, filename='x"\r\nSet-Cookie: a=b.docx')
    r = client.post("/report/docx", json={"analysis": analysis, "meta": meta_evil}, headers=local)
    check("POST /report/docx: όνομα αρχείου χρήστη δεν μπαίνει σε κεφαλίδες",
          r.status_code == 200 and "Set-Cookie" not in r.headers and "Set-Cookie" not in r.headers.get(
              "Content-Disposition", ""))
    check("POST /report/docx: cross-site → 403",
          client.post("/report/docx", json={"analysis": analysis},
                      headers={**local, "Sec-Fetch-Site": "cross-site"}).status_code == 403
          and client.post("/report/docx", json={"analysis": analysis},
                          headers={**local, "Origin": "https://evil.example"}).status_code == 403)
    check("POST /report/docx: ξένο Host → 403",
          client.post("/report/docx", json={"analysis": analysis},
                      headers={"Host": "evil.example"}).status_code == 403)
    check("POST /report/docx: λάθος σώμα → 400 (όχι 500)",
          client.post("/report/docx", data="not json", headers=local,
                      content_type="application/json").status_code == 400
          and client.post("/report/docx", json={"analysis": [1]}, headers=local).status_code == 400
          and client.post("/report/docx", json={"analysis": {}, "meta": "x"}, headers=local).status_code == 400)
    deep = "[" * 100000 + "]" * 100000
    r = client.post("/report/docx", data='{"analysis": ' + deep + "}", headers=local,
                    content_type="application/json")
    check("POST /report/docx: πολύ βαθύ JSON → 400", r.status_code == 400)
    big = '{"analysis": {"x": "' + "a" * (srv.MAX_REPORT_BYTES + 10) + '"}}'
    r = client.post("/report/docx", data=big, headers=local, content_type="application/json")
    check("POST /report/docx: πάνω από το όριο μεγέθους → 413", r.status_code == 413)

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("ΠΡΑΚΤΙΚΟ ΕΛΕΓΧΟΥ (.docx)")
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("REPORT TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok


def run_ocr_tests(verbose: bool = True) -> bool:
    """OCR σκαναρισμένων PDF: πότε τρέχει, όρια, ασφάλεια, χωρίς/με Tesseract."""
    import io
    import tempfile
    import threading
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    import ocr_pdf
    import ai_detector_server as srv

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    tmp = Path(tempfile.mkdtemp(prefix="ai_ocr_"))
    font = None
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(path):
            font = ImageFont.truetype(path, 40)
            break
    greek = font is not None
    lines = (["Η τεχνητή νοημοσύνη αλλάζει την εκπαίδευση", "στα ελληνικά πανεπιστήμια σήμερα"] if greek
             else ["Artificial intelligence is changing education", "in Greek universities today"])
    lines += ["Students write theses with new digital tools", "and examiners need reliable evidence."]

    def page_image():
        img = Image.new("L", (1700, 2200), 255)
        draw = ImageDraw.Draw(img)
        for n, line in enumerate(lines):
            draw.text((120, 200 + n * 90), line, fill=0, font=font or ImageFont.load_default(size=40))
        return img

    scanned = tmp / "scanned.pdf"
    page_image().save(scanned, "PDF", resolution=200, save_all=True, append_images=[page_image()])

    check("OCR: μόνο αν το PDF είναι κυρίως σκαναρισμένο",
          ocr_pdf.needs_ocr(["", "", "x" * 100]) == [0, 1]
          and ocr_pdf.needs_ocr(["x" * 100, "x" * 100, "", "x" * 100]) == []
          and ocr_pdf.needs_ocr([]) == [])
    check("OCR: ένωση συλλαβισμού, αφαίρεση form feed",
          ocr_pdf._clean("εκπαί-\nδευση\x0c  test") == "εκπαίδευση\n test")

    # Τεράστια σελίδα PDF → η εικόνα δεν ξεπερνά το όριο (προστασία μνήμης)
    huge = tmp / "huge.pdf"
    Image.new("L", (200, 200), 255).save(huge, "PDF", resolution=1)   # ~14.400 pt πλευρά
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(huge))
    try:
        png = ocr_pdf._render_png(pdf, 0)
    finally:
        pdf.close()
    check("OCR: γιγάντια σελίδα → εικόνα έως MAX_SIDE_PX",
          max(Image.open(io.BytesIO(png)).size) <= ocr_pdf.MAX_SIDE_PX)

    old_env = {k: os.environ.get(k) for k in ("AI_DETECTOR_OCR", "AI_DETECTOR_TESSERACT")}
    try:
        os.environ["AI_DETECTOR_OCR"] = "off"
        st_off = ocr_pdf.status(refresh=True)
        try:
            srv.extract_text_from_pdf(str(scanned))
            off_err = None
        except srv.ExtractionError as e:
            off_err = e.key
        check("OCR: AI_DETECTOR_OCR=off → απενεργοποιημένο, καθαρό μήνυμα σκαναρισμένου",
              st_off == {"available": False, "disabled": True, "langs": []} and off_err == "scanned_no_ocr")
        os.environ.pop("AI_DETECTOR_OCR")
        os.environ["AI_DETECTOR_TESSERACT"] = str(tmp / "nope.exe")
        check("OCR: ανύπαρκτο AI_DETECTOR_TESSERACT αγνοείται",
              ocr_pdf.find_tesseract() != str(tmp / "nope.exe"))
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        ocr_pdf.status(refresh=True)

    bad = tmp / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 garbage")
    texts, info = ocr_pdf.ocr_pages(str(bad), [0])
    check("OCR: χαλασμένο PDF δεν ρίχνει εξαίρεση", texts == {} and not info["used"])

    client = srv.app.test_client()
    local = {"Host": "localhost:5000", "X-UI-Lang": "en"}
    cfg = client.get("/config/search", headers=local).get_json()
    check("/config/search: κατάσταση OCR χωρίς διαδρομή εκτελέσιμου",
          set(cfg.get("ocr", {})) == {"available", "greek", "disabled"} and "path" not in str(cfg))

    def analyze_pdf(path):
        with open(path, "rb") as fh:
            return client.post("/analyze", headers=local, data={
                "file": (io.BytesIO(fh.read()), "scan.pdf"), "web": "0", "plagiarism": "0", "refs": "0"},
                content_type="multipart/form-data")

    if ocr_pdf.available():
        info = {}
        text = srv.extract_text_from_pdf(str(scanned), info)
        words = ("τεχνητή", "εκπαίδευση") if greek else ("intelligence", "education")
        check("OCR (Tesseract): σκαναρισμένο PDF διαβάζεται, και ελληνικά",
              all(w in text for w in words) and "examiners" in text
              and info.get("used") and info.get("pages") == 2 and "ell" in (info.get("langs") or ""))
        r = analyze_pdf(scanned)
        a = (r.get_json() or {}).get("analysis") or {}
        check("POST /analyze: σκαναρισμένο PDF → 200 με analysis.ocr",
              r.status_code == 200 and a.get("ocr", {}).get("used") and a["ocr"]["pages"] == 2)
        old_max = ocr_pdf.MAX_PAGES
        ocr_pdf.MAX_PAGES = 1
        try:
            texts, info = ocr_pdf.ocr_pages(str(scanned), [0, 1])
        finally:
            ocr_pdf.MAX_PAGES = old_max
        check("OCR: όριο σελίδων → truncated", list(texts) == [0] and info["truncated"])
        old_wait = ocr_pdf.WAIT_TIMEOUT
        ocr_pdf.WAIT_TIMEOUT = 0.1
        ocr_pdf._LOCK.acquire()
        try:
            try:
                srv.extract_text_from_pdf(str(scanned))
                busy = None
            except srv.ExtractionError as e:
                busy = e.key
        finally:
            ocr_pdf._LOCK.release()
            ocr_pdf.WAIT_TIMEOUT = old_wait
        check("OCR: ένα έγγραφο κάθε φορά (busy → καθαρό μήνυμα)", busy == "ocr_busy")
        th = threading.Thread(target=lambda: ocr_pdf.ocr_pages(str(scanned), [0]))
        th.start()
        th.join(120)
        check("OCR: το κλείδωμα απελευθερώνεται", ocr_pdf._LOCK.acquire(timeout=1) and (ocr_pdf._LOCK.release() or True))
    else:
        r = analyze_pdf(scanned)
        check("POST /analyze χωρίς Tesseract: σκαναρισμένο → 422 scanned_no_ocr",
              r.status_code == 422 and (r.get_json() or {}).get("error_code") == "scanned_no_ocr")

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("OCR ΣΚΑΝΑΡΙΣΜΕΝΩΝ PDF" + ("" if ocr_pdf.available() else " (χωρίς Tesseract)"))
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("OCR TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok


def run_binoculars_config_tests(verbose: bool = True) -> bool:
    """Presets Binoculars (και ελληνικά), κβαντισμός, όριο μόνο από ίδια ρύθμιση — χωρίς torch."""
    import json
    import tempfile
    from pathlib import Path
    import binoculars_check as bc

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    saved = {k: os.environ.get(k) for k in ("AI_DETECTOR_BINOCULARS_QUANT",)}
    old_cfg = bc.CONFIG_FILE
    bc.CONFIG_FILE = Path(tempfile.mkdtemp(prefix="ai_bcfg_")) / "binoculars_config.json"
    try:
        os.environ.pop("AI_DETECTOR_BINOCULARS_QUANT", None)
        k = bc.resolve_settings("krikri-8b")
        m = bc.resolve_settings("meltemi-7b")
        check("Ελληνικά presets: Krikri/Meltemi (ΙΕΛ), 4-bit, χωρίς όριο πριν τη βαθμονόμηση",
              k["observer"] == "ilsp/Llama-Krikri-8B-Base" and k["performer"] == "ilsp/Llama-Krikri-8B-Instruct"
              and m["observer"] == "ilsp/Meltemi-7B-v1.5" and m["performer"] == "ilsp/Meltemi-7B-Instruct-v1.5"
              and k["quantize"] == m["quantize"] == "4bit"
              and k["threshold"] is None and not k["calibrated"])
        check("Qwen χωρίς κβαντισμό από προεπιλογή", bc.resolve_settings("qwen2.5-1.5b")["quantize"] is None)
        os.environ["AI_DETECTOR_BINOCULARS_QUANT"] = "off"
        off = bc.resolve_settings("krikri-8b")["quantize"]
        os.environ["AI_DETECTOR_BINOCULARS_QUANT"] = "8bit"
        eight = bc.resolve_settings("qwen2.5-1.5b")["quantize"]
        os.environ["AI_DETECTOR_BINOCULARS_QUANT"] = "rm -rf /"
        junk = bc.resolve_settings("krikri-8b")["quantize"]
        check("AI_DETECTOR_BINOCULARS_QUANT: off / 8bit / άκυρη τιμή → προεπιλογή",
              off is None and eight == "8bit" and junk == "4bit")
        os.environ.pop("AI_DETECTOR_BINOCULARS_QUANT")
        bc.CONFIG_FILE.write_text(json.dumps({"observer": k["observer"], "performer": k["performer"],
                                              "quantize": "4bit", "threshold": 0.88}), encoding="utf-8")
        cal = bc.resolve_settings("krikri-8b")
        os.environ["AI_DETECTOR_BINOCULARS_QUANT"] = "off"
        other = bc.resolve_settings("krikri-8b")
        check("Όριο βαθμονόμησης μόνο με την ίδια ρύθμιση κβαντισμού",
              cal["threshold"] == 0.88 and cal["calibrated"] and other["threshold"] is None)
        os.environ.pop("AI_DETECTOR_BINOCULARS_QUANT")
        bc.CONFIG_FILE.write_text(json.dumps({"observer": "Qwen/Qwen2.5-1.5B", "performer": "Qwen/Qwen2.5-1.5B-Instruct",
                                              "threshold": 0.9}), encoding="utf-8")
        check("Παλιό binoculars_config.json (χωρίς quantize) ισχύει ακόμη για Qwen",
              bc.resolve_settings("qwen2.5-1.5b")["threshold"] == 0.9)
    finally:
        bc.CONFIG_FILE = old_cfg
        for key, v in saved.items():
            if v is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = v

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("BINOCULARS: PRESETS & ΡΥΘΜΙΣΕΙΣ")
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("BINOCULARS CONFIG TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok


def _diagram(seed: int, size=(800, 600)):
    """Τυχαίο «διάγραμμα» (κουτιά και γραμμές) για τα τεστ εικόνων."""
    import random
    from PIL import Image, ImageDraw
    r = random.Random(seed)
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    for _ in range(12):
        x0, y0 = r.randint(0, size[0] - 100), r.randint(0, size[1] - 100)
        d.rectangle([x0, y0, x0 + r.randint(40, 200), y0 + r.randint(40, 150)], outline=(r.randint(0, 200),) * 3,
                    width=4, fill=(r.randint(100, 255), r.randint(100, 255), r.randint(100, 255)))
        d.line([r.randint(0, size[0]), r.randint(0, size[1]), r.randint(0, size[0]), r.randint(0, size[1])],
               fill="black", width=3)
    return im


def run_image_tests(verbose: bool = True) -> bool:
    """Ίδιες εικόνες/διαγράμματα: αποτύπωμα, εξαγωγή, άμυνες, corpus, μαζικός έλεγχος, server."""
    import io
    import tempfile
    import zipfile
    from pathlib import Path
    from PIL import Image
    from docx import Document
    from docx.shared import Inches
    import image_reuse as ir
    import analysis_history
    import ai_detector_server as srv
    from report_docx import build_report

    checks = []

    def check(name, cond):
        checks.append((name, bool(cond)))

    tmp = Path(tempfile.mkdtemp(prefix="ai_img_"))

    def buf(im, fmt="PNG", **kw):
        b = io.BytesIO()
        im.save(b, fmt, **kw)
        b.seek(0)
        return b

    A, B, C, LOGO = _diagram(1), _diagram(2), _diagram(3), _diagram(99, (300, 300))
    a_small = Image.open(buf(A.resize((500, 375)), "JPEG", quality=40))
    check("Αποτύπωμα: ίδια εικόνα σε άλλο μέγεθος/JPEG → κοντά, διαφορετική → μακριά",
          ir.distance(ir.dhash(A), ir.dhash(a_small)) <= ir.MATCH_DISTANCE
          and ir.distance(ir.dhash(A), ir.dhash(B)) > 3 * ir.MATCH_DISTANCE)
    check("Αποτύπωμα: σχεδόν μονόχρωμη εικόνα → αγνοείται", ir.dhash(Image.new("RGB", (400, 400), "white")) is None)

    words = "Η εργασία αυτή εξετάζει την επίδραση της τεχνητής νοημοσύνης στην εκπαίδευση με παραδείγματα. " * 3

    def make_docx(name, images, extra_media=None):
        doc = Document()
        doc.add_paragraph(words)
        for im in images:
            doc.add_picture(buf(im), width=Inches(3))
        path = tmp / name
        doc.save(path)
        if extra_media:
            with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as zf:
                for member, data in extra_media.items():
                    zf.writestr(member, data)
        return path

    bomb = Image.new("1", (10000, 5000))                     # 50 Mpixel > όριο, λίγα KB ως PNG
    hostile = make_docx("hostile.docx", [A, Image.new("RGB", (50, 50), "red")], {
        "word/media/zeros.png": b"\0" * (30 * 1024 * 1024),   # zip bomb (τεράστια αναλογία)
        "word/media/broken.png": b"\x89PNG\r\n\x1a\nnot really",
        "word/media/vector.emf": b"\x01\x00\x00\x00" * 100,
        "word/media/huge.png": buf(bomb).getvalue(),
    })
    import time as _t
    t0 = _t.monotonic()
    got = ir.extract(hostile)
    check(f"Εξαγωγή .docx: μόνο η κανονική εικόνα — όχι εικονίδιο, zip bomb, χαλασμένη, EMF, 50 Mpixel "
          f"({len(got['images'])}, {_t.monotonic() - t0:.1f}s)",
          len(got["images"]) == 1 and got["images"][0]["w"] == 800 and _t.monotonic() - t0 < 10)
    (tmp / "bad.pdf").write_bytes(b"%PDF-1.4 garbage")
    (tmp / "bad.docx").write_bytes(b"PK not a zip")
    check("Χαλασμένο PDF/.docx → καμία εικόνα, χωρίς εξαίρεση",
          ir.extract(tmp / "bad.pdf")["images"] == [] and ir.extract(tmp / "bad.docx")["images"] == [])

    pdf_path = tmp / "b.pdf"                                 # μόνο με PIL (όχι reportlab — δεν είναι σε όλα τα CI jobs)
    a_small.convert("RGB").save(pdf_path, "PDF", save_all=True, append_images=[C])
    pdf_imgs = ir.extract(pdf_path)
    check("Εξαγωγή PDF: εικόνες με αρχικές διαστάσεις", [i["w"] for i in pdf_imgs["images"]] == [500, 800])
    thumbs = ir.thumbnails(pdf_path, {"p0:0"})
    check("Μικρογραφία: data URI JPEG έως THUMB_SIDE",
          thumbs.get("p0:0", "").startswith("data:image/jpeg;base64,")
          and max(Image.open(io.BytesIO(__import__("base64").b64decode(thumbs["p0:0"].split(",", 1)[1]))).size)
          <= ir.THUMB_SIDE)

    # Corpus: η «πηγή» έχει το A· το λογότυπο υπάρχει σε 3 εργασίες του corpus
    corpus = tmp / "corpus"
    corpus.mkdir()
    make_docx("old1.docx", [A, LOGO]).rename(corpus / "old1.docx")
    make_docx("old2.docx", [B, LOGO]).rename(corpus / "old2.docx")
    make_docx("old3.docx", [LOGO]).rename(corpus / "old3.docx")
    index = ir.ImageIndex(corpus)
    res = index.compare(pdf_path)
    check("Corpus: βρίσκει το ίδιο διάγραμμα στη σωστή πηγή, με μικρογραφίες",
          [(x["file"], x["count"]) for x in res["sources"]] == [("old1.docx", 1)]
          and res["sources"][0]["matches"][0]["doc_thumb"] and res["sources"][0]["matches"][0]["source_thumb"])
    student = make_docx("student.docx", [LOGO, C])
    res2 = index.compare(student)
    check("Corpus: λογότυπο σε ≥3 εργασίες → «κοινή» εικόνα, όχι εύρημα",
          res2["sources"] == [] and res2["common"] == 1)
    cache = corpus / ir.CACHE_NAME
    raw = cache.read_text(encoding="utf-8")
    check("Corpus cache: μόνο αποτυπώματα (όχι εικόνες), αρχείο 0600",
          "base64" not in raw and len(raw) < 5000
          and (os.name != "posix" or (os.stat(cache).st_mode & 0o777) == 0o600))
    (corpus / "old1.docx").unlink()
    check("Corpus: διαγραμμένο αρχείο φεύγει από το ευρετήριο",
          index.compare(pdf_path, thumbs=False)["sources"] == [])
    (corpus / "evil.docx").symlink_to(pdf_path) if os.name == "posix" else None
    index.refresh()
    check("Corpus: symlinks αγνοούνται", "evil.docx" not in index.files)

    # Μαζικός έλεγχος: 4 εργασίες, το λογότυπο σε 3 → κοινό· το A μόνο σε δύο → ζεύγος
    d1, d2 = make_docx("s1.docx", [A, LOGO]), make_docx("s2.docx", [B, LOGO])
    d3, d4 = make_docx("s3.docx", [LOGO]), make_docx("s4.docx", [C])
    docs = [(p.name, str(p), ir.extract(p)) for p in (d1, d2, d3, d4)] + [("b.pdf", str(pdf_path), pdf_imgs)]
    pairs = ir.batch_pairs(docs)
    check("Μαζικά: ζεύγη με κοινό διάγραμμα (όχι λόγω λογοτύπου)",
          sorted((p["a"], p["b"]) for p in pairs["pairs"]) == [("s1.docx", "b.pdf"), ("s4.docx", "b.pdf")]
          and pairs["common"] >= 1 and all(m["a_thumb"] and m["b_thumb"] for p in pairs["pairs"]
                                           for m in p["matches"]))

    # Ιστορικό: χωρίς μικρογραφίες
    stripped = analysis_history._without_thumbs(res)
    check("Ιστορικό: οι μικρογραφίες δεν αποθηκεύονται",
          "base64" not in str(stripped) and stripped["sources"][0]["count"] == 1)
    rep_text = "\n".join(p.text for p in Document(io.BytesIO(build_report(
        {"score": 10, "images": stripped}, {}, lang="el"))).paragraphs)
    check("Πρακτικό: γραμμή για ίδιες εικόνες", "Ίδιες εικόνες/διαγράμματα με το corpus: 1 εικόνες σε 1 αρχεία"
          in rep_text)

    # Server: /analyze (με corpus) και /analyze-batch
    old_index = srv.image_index
    srv.image_index = ir.ImageIndex(corpus)
    make_docx("old1.docx", [A]).rename(corpus / "old1.docx")
    client = srv.app.test_client()
    local = {"Host": "localhost:5000", "X-UI-Lang": "en"}
    try:
        with open(make_docx("s5.docx", [A, C]), "rb") as fh:
            r = client.post("/analyze", headers=local, content_type="multipart/form-data", data={
                "file": (io.BytesIO(fh.read()), "s5.docx"), "web": "0", "plagiarism": "1", "refs": "0"})
        imgs = ((r.get_json() or {}).get("analysis") or {}).get("images") or {}
        check("POST /analyze: analysis.images με την πηγή από το corpus",
              r.status_code == 200 and [x["file"] for x in imgs.get("sources", [])] == ["old1.docx"])
        with open(d1, "rb") as fh:
            r = client.post("/analyze", headers=local, content_type="multipart/form-data", data={
                "file": (io.BytesIO(fh.read()), "s1.docx"), "web": "0", "plagiarism": "0", "refs": "0"})
        check("POST /analyze χωρίς corpus → χωρίς έλεγχο εικόνων",
              r.status_code == 200 and "images" not in r.get_json()["analysis"])
        before = set(os.listdir(srv.UPLOAD_FOLDER))
        # .docx (όχι το PDF-εικόνα: θα έπαιρνε OCR) με τις ίδιες δύο εικόνες με το b.pdf
        d6 = make_docx("s6.docx", [a_small.convert("RGB"), C])
        files = [(io.BytesIO(open(p, "rb").read()), p.name) for p in (d1, d4, d6)]
        r = client.post("/analyze-batch", headers=local, content_type="multipart/form-data",
                        data={"files": files, "plagiarism": "1"})
        data = r.get_json() or {}
        ip = (data.get("image_pairs") or {}).get("pairs", [])
        check("POST /analyze-batch: κοινές εικόνες μεταξύ εργασιών, με μικρογραφίες",
              r.status_code == 200 and len(ip) == 2 and all(m.get("a_thumb") for p in ip for m in p["matches"]))
        check("POST /analyze-batch: τα προσωρινά αρχεία σβήνονται", set(os.listdir(srv.UPLOAD_FOLDER)) <= before)
    finally:
        srv.image_index = old_index

    ok = all(c for _, c in checks)
    if verbose:
        print("\n" + "=" * 60)
        print("ΙΔΙΕΣ ΕΙΚΟΝΕΣ / ΔΙΑΓΡΑΜΜΑΤΑ")
        print("=" * 60)
        for name, c in checks:
            print(f"{'✅' if c else '❌'} {name}")
        print("\n" + "=" * 60)
        print("IMAGE TESTS:", "ΟΛΑ ΠΕΡΑΣΑΝ ✅" if ok else "ΑΠΟΤΥΧΙΕΣ ❌")
        print("=" * 60)
    return ok


if __name__ == "__main__":
    ok = run_engine_tests()
    ok = run_model_signature_tests() and ok
    ok = run_revision_guide_tests() and ok
    ok = run_i18n_tests() and ok
    ok = run_evidence_tests() and ok
    ok = run_web_speed_tests() and ok
    ok = run_tooling_tests() and ok
    ok = run_import_calibration_tests() and ok
    ok = run_report_tests() and ok
    ok = run_ocr_tests() and ok
    ok = run_binoculars_config_tests() and ok
    ok = run_image_tests() and ok
    if "--files" in sys.argv:
        import tempfile
        ok = run_file_tests(tempfile.mkdtemp(prefix="ai_detector_test_")) and ok
    if "--server" in sys.argv:
        ok = run_server_tests() and ok
    if "--security" in sys.argv:
        ok = run_security_tests() and ok
    if "--binoculars" in sys.argv:
        ok = run_binoculars_tests() and ok
    if "--thesis" in sys.argv:
        ok = run_thesis_tests() and ok
    if "--plagiarism" in sys.argv:
        import tempfile
        ok = run_plagiarism_tests(tempfile.mkdtemp(prefix="ai_plag_test_")) and ok
    sys.exit(0 if ok else 1)
