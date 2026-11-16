# AI Content Detector v2.22

**English** · [Ελληνικά](README.el.md)

A local, open-source tool that checks **.docx** and **.pdf** documents, written in **Greek or English**,
for signs of **AI-generated text** and for **plagiarism**. It is built for **long documents**
(theses and dissertations of 50–200 pages).

It runs **entirely on your own computer**. Documents are never uploaded anywhere; when web checks are
enabled, only short sample phrases are sent to public search services (OpenAlex, Wikipedia, Crossref,
optionally Brave Search).

> **The score is an indication, not proof.** Read the [Limitations](#limitations) before using it for
> any decision about a student.

## Quick start

**Windows:** double-click `run.bat` · **Linux / macOS / WSL:** `./run.sh`

`launcher.py` (called by both) checks Python, installs the libraries **only when** `requirements.txt`
changes, opens your browser at http://localhost:5000 once the server is ready (or just opens the page
if it is already running) and, on Windows, offers once to create a desktop shortcut
(`python launcher.py --shortcut` to do it again).

The interface is available in **English, Greek, German, French and Portuguese** (buttons at the top
right). A step-by-step guide for everyday use, in Greek, is in [QUICK_START.md](QUICK_START.md).

Manual setup:

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
python ai_detector_server.py
```

**Updating:** from a git clone, run `update.bat` / `./update.sh` (it runs `git pull`). From a ZIP,
unzip the new version into a new folder and run `update.bat` there, pointing it at the old folder:
keys (`search_config.json`), `corpus/`, cache and history are carried over without overwriting
anything (`tools/update.py`).

## Plagiarism check (Turnitin-style)

Enabled by default (checkboxes in the UI):

1. **Local archive of past work (`corpus/`).** Drop old theses (.docx/.pdf/.txt/.md) into `corpus/`,
   or manage them from the **Corpus** tab. Each new document is compared with them using
   **winnowing fingerprints** (the MOSS/Stanford algorithm). It finds shared passages of 10+ words,
   robust to changes in accents and capitalisation, and reports a **similarity percentage per source
   plus the exact passages**, like a Turnitin similarity report. The index is built once and refreshed
   automatically.
2. **Academic literature: OpenAlex** (Google Scholar-like, no key required). A sampled exact-phrase
   check against **250M+ publications** (titles, abstracts, full text where available), including
   ~247,000 Greek-language records. Phrases found in dozens of publications are marked as "common"
   to avoid false alarms.
3. **Wikipedia (EN + EL).** Exact-phrase check that respects the rate limits (batched OR queries,
   backoff on 429, a canary check that detects silently degraded answers).
4. **Brave Search (optional, free key, recommended).** Searches the whole web through Brave's
   independent index, which includes the PDFs in Greek institutional repositories (Pergamos, IKEE,
   Nemertes, etc.) where most Greek theses live. The free tier is 2,000 searches/month (~250 theses).
   Set it up from the UI: **⚙ Settings** has the sign-up link, verifies the key live and saves it
   to `search_config.json`.
5. **Google Custom Search (legacy).** Google has **closed the Custom Search JSON API to new
   customers** (new projects get `PERMISSION_DENIED` even when the API looks enabled). It is kept only
   for old Google Cloud projects that already had access.

**What it does NOT do:** it has no access to Turnitin's private database (subscription journals,
papers submitted only to Turnitin). For Greek theses in particular, **OpenAlex + a Brave key** gives
the best coverage.

**Exclude quotes and bibliography** (on by default): quotations of 5+ words in “ ” « » „ “ " " and the
bibliography section at the end are removed from the **plagiarism** comparison (corpus, web, batch),
like Turnitin's exclude options. It is conservative: never more than 40% of the text, never a
"Bibliography" entry in the table of contents, never appendices. The AI analysis and the reference
check still see the full text (`text_exclusions.py`).

**Reused images and diagrams:** when the corpus comparison is enabled, the images in a document
(.docx/PDF) are compared with the images in the corpus and, in batch mode, with each other. Each
image gets a visual fingerprint (128-bit difference hash), so it is found even after resizing or
recompression, and matches are shown as side-by-side thumbnails. Icons (<100 px), single-colour images
and anything that appears in 3+ documents (university logo, cover template) are ignored. Only
PNG/JPEG/GIF/BMP/TIFF/WEBP, with limits on size, pixels, compression ratio and time; the corpus stores
only fingerprints, never the images (`image_reuse.py`).

**Contact email (optional).** OpenAlex and Crossref give more reliable service (their "polite pool")
when requests include a contact email. The tool contains **no** email address; if you want, put yours
in `search_config.json` (`"contact_email": "..."`) or in the `AI_DETECTOR_CONTACT_EMAIL` environment
variable. Without it, everything still works.

**OpenAlex key (recommended):** since February 2026, OpenAlex without a key has a very small daily
limit (the literature check makes ~12–30 searches per thesis). Get a free key at openalex.org
(account → API key, ~1,000 searches/day) and add it in **⚙ Settings**, in `search_config.json`
(`{"openalex_api_key": "..."}`) or in `OPENALEX_API_KEY`. Keys stay local (the file is in
`.gitignore`) and are never shown again on the page.

## Long documents

- File limit **100 MB**, tested on a 200-page / 107,000-word PDF (**~14 s** in total).
- Texts over ~2,500 words are also analysed **in sections of ~1,000 words**. The UI shows a coloured
  bar per section, so you can see **where** in the document the AI signals are: one AI-written chapter
  does not hide in the average of 200 pages.
- If the overall score is low but some sections are flagged, the verdict becomes "Mixed text: AI
  signals in X of Y sections".

## How the AI detection works

The core (`detector_engine.py`, pure Python, no dependencies) combines weighted **statistical
features**:

### AI writing indicators

| Indicator | Weight | What it measures |
|---|---|---|
| AI phrases & vocabulary | 0.32 | 100+ phrases per language ("delve into", "it is important to note", "ever-evolving" / «εν κατακλείδι», «διαδραματίζει καθοριστικό ρόλο»), weighted by strength |
| Burstiness | 0.16 | Variation in sentence length: LLMs write unusually uniform sentences, people mix short and long ones |
| Sentence-initial connectives | 0.14 | Share of sentences starting with However/Moreover/Furthermore or Επιπλέον/Ωστόσο/Συνεπώς: LLMs reach 20–45%, people 3–10% |
| Rule of three | 0.08 | "X, Y and Z" triplets that LLMs love |
| Em dashes (—) | 0.08 | Systematic em-dash use, typical of 2024+ models |
| Chatbot formatting | 0.07 | Leftover Markdown (`**bold**`, `###`, bullets) from copy-paste |
| Paragraph uniformity | 0.06 | Paragraphs of almost identical length |
| Repeated first word | 0.05 | Sentences that keep starting with the same word |

### Human markers (lower the score)

- **Contractions:** "don't", "it's" / «γι'», «απ'», «κι»
- **Informal expressions:** "honestly", "gonna" / «λοιπόν», «βασικά»
- **Typographic imperfections:** double spaces, lowercase after a full stop, missing spaces after commas
- **Personal narrative:** "I remember", "my mom" / «θυμάμαι», «πέρσι»
- **Citations:** (Smith, 2019), [12]

The final 0–100% score comes from a weighted combination with logistic calibration. Short texts
(<200 words) give a less reliable result and show a warning.

| Score | Meaning |
|---|---|
| **< 30%** (green) | Probably human |
| **30–60%** (orange) | Mixed / uncertain |
| **> 60%** (red) | Probably AI-generated |

The UI also shows **which sentences** carry AI signals and which indicators fired.

### Revision guide

When you check **your own** text, the results answer "what should I change first?". The indicators
that fired are ranked by their **actual effect on the score**: the same scoring formula is re-run
with each indicator set to zero and the difference is shown in points (a calculation on the same
model, not an estimate). For the strongest clichés ("delve into", «διαδραματίζει καθοριστικό ρόλο»)
it suggests **concrete alternative wording**, only for phrases actually found in your text.

### Model signatures (experimental)

`model_signature.py` looks for conversational "signatures" typical of ChatGPT, Gemini or Claude (for
example "as an AI language model"). These appear almost only in **raw, copy-pasted chat output**; an
AI-written essay or thesis chapter normally does not contain them, so a low result here **does not
prove human authorship**. The main score remains the reliable criterion.

## Signals beyond the score

These checks do **not** change the AI score; they give independent evidence for a human to judge.

- **Reference check** (`reference_check.py`). Language models often invent references. The
  bibliography section is found and each reference is looked up in Crossref and OpenAlex, comparing
  title and year. The strongest signal is a **DOI that does not exist** or **belongs to another
  work**. "Not found" is not proof: books and Greek publications are often missing from these
  databases.
- **.docx editing history** (`docx_forensics.py`). Word records editing sessions (rsid) and total
  editing time. Text written almost entirely in one session, or created and saved within minutes, is
  a reason to ask the student about their drafts, **not proof** ("Save as", Google Docs or
  LibreOffice change or remove this information).
- **Fairness note** (`detector_engine.fairness_check`). Detectors often misclassify simple vocabulary
  as AI, for example from non-native speakers (Liang et al. 2023: 61% false positives on TOEFL
  essays). When the score is ≥ 42% and vocabulary variety (MATTR) is < 0.78, a warning is shown.
- **Detector-evasion tricks** (`obfuscation_check.py`). Finds invisible characters (zero-width space
  etc.), look-alike letters from another alphabet (Cyrillic «а» for Latin "a", Latin "o" inside a
  Greek word), unusual Unicode spaces and the "tortured phrases" of paraphrasing tools ("counterfeit
  consciousness" for artificial intelligence; Cabanac et al. 2021). The plagiarism check also
  normalises these characters, so a disguised copy is still found.

## Second method: Binoculars (optional)

`binoculars_check.py` implements Hans et al. 2024 ([arXiv:2401.12070](https://arxiv.org/abs/2401.12070)):
two related language models read the text and its predictability is compared
(score = perplexity / cross-perplexity; low means AI-like). It needs no training. It is shown as a
separate line under the score and does not change the main score.

It is **off by default** (heavy dependencies, model downloads):

```bash
pip install -r requirements-binoculars.txt           # torch + transformers
AI_DETECTOR_BINOCULARS=qwen2.5-1.5b python ai_detector_server.py
```

| Preset | Models | Size | Threshold |
|---|---|---|---|
| `falcon-7b` | Falcon-7B + Falcon-7B-instruct | ~28 GB, GPU | from the paper (0.9015) |
| `qwen2.5-1.5b` | Qwen2.5-1.5B + Instruct | ~6 GB RAM, CPU ok | needs calibration |
| `qwen2.5-0.5b` | Qwen2.5-0.5B + Instruct | ~2 GB RAM | needs calibration |
| `krikri-8b` 🇬🇷 | [Llama-Krikri-8B](https://huggingface.co/ilsp/Llama-Krikri-8B-Base) Base + Instruct (ILSP / Athena RC) | GPU; 4-bit ~12 GB (free T4) | needs calibration |
| `meltemi-7b` 🇬🇷 | [Meltemi-7B v1.5](https://huggingface.co/ilsp/Meltemi-7B-v1.5) + Instruct (ILSP / Athena RC) | GPU; 4-bit ~10 GB | needs calibration |
| `custom` | `AI_DETECTOR_BINOCULARS_OBSERVER` / `_PERFORMER` (same tokenizer) | — | needs calibration |

The Greek models `krikri-8b` and `meltemi-7b` are preferred for Greek theses. On an NVIDIA GPU they
load in 4-bit (`pip install bitsandbytes`; `AI_DETECTOR_BINOCULARS_QUANT=8bit|off` changes it).
Licences: Krikri, Llama 3.1 Community License; Meltemi, Apache-2.0.

The paper's thresholds apply **only** to Falcon. For any other pair, calibrate once with known texts
(ideally 20+ per class, of the same kind as your theses); the threshold is written to
`binoculars_config.json`:

```bash
AI_DETECTOR_BINOCULARS=qwen2.5-1.5b python tools/calibrate_binoculars.py \
    --human-dir samples/human --ai-dir samples/ai
```

**Free GPU: `notebooks/binoculars_gpu.ipynb`.** On a CPU, Binoculars needs ~1–2 minutes per thesis;
on a GPU, a few seconds. The notebook runs on **Kaggle** (GPU T4 x2 or P100, Internet on) or **Google
Colab** (T4 GPU). Upload the notebook, upload the theses, run all cells and download `results.zip`;
the last cell deletes the theses. ⚠ **Privacy:** in the cloud, the documents leave your computer
(GDPR, student data). Anonymise them first, or use only the local app, which sends nothing.

## Batch checking, history and reports

- **Batch tab** (`POST /analyze-batch`, up to 30 files): analyses many theses together, shows a table
  of scores and signals, and **compares the theses with each other** for shared passages. Web checks
  are skipped for speed.
- **ZIP from eClass / Moodle:** drop the "download all submissions" ZIP (up to 60 theses) into the
  Batch tab. Student names are taken from the ZIP structure, and Greek file names from Windows (cp737)
  are read correctly. `zip_import.py` guards against zip bombs, zip slip, symlinks, encrypted entries
  and nested archives.
- **Command line** (no server, no internet):
  `python tools/batch_analyze.py theses/ --out results/results.csv` writes `results.csv`,
  `results_pairs.csv` (pairs with shared passages) and `results.json`.
- **Compare versions:** the **Compare** tab takes the old and new version of the same thesis and shows
  the score change, the indicators that changed most, how much text changed and which **new** sentences
  carry AI signals (`version_compare.py`).
- **Analysis history:** the **History** tab reopens past results without re-analysing. Stored only
  locally in `.analysis_history.sqlite3`, **without** the full text of the theses, deleted after 30 days
  (max 100 entries); turn it off completely with `AI_DETECTOR_HISTORY=off`.
- **Calibrate on your own data:** in the **Corpus** tab, give 10+ theses that were certainly written
  by people (e.g. before 2022) from your field. Each analysis then shows "of your N human reference
  theses, X% scored this high or higher" and a suggested threshold. Only scores are kept
  (`score_calibration.py`).
- **Check report (.docx):** "📄 Check report" in the results fills in institution, department,
  student, title and examiner and downloads a Word report with the findings, an "indication, not
  proof" disclaimer and a signature line. It is built in memory and never stored (`report_docx.py`).
- **Print / PDF:** the 🖨 button gives a clean printable report.
- **OCR for scanned PDFs:** if most pages have no text, they go through the free Tesseract OCR
  (Greek + English), when it is installed. OCR results are marked "📷 OCR" because recognition errors
  reduce reliability. `AI_DETECTOR_OCR=off` disables it (`ocr_pdf.py`).

## Speed and caching

- The AI score appears **immediately** (~1–3 s); the internet checks run in the background and fill
  in when ready.
- Web and reference checks run **in parallel**, so the total time is roughly the slowest check.
- Answers from Wikipedia/OpenAlex/Crossref are cached in `.web_cache.sqlite3` (30 days for hits,
  7 days for "not found"). Only SHA-256 hashes of the queries and public metadata are stored, never
  thesis text. Disable with `AI_DETECTOR_WEB_CACHE=off`.
- Wikipedia requests stay serial (one at a time across the whole server), as Wikimedia's policy
  asks, and slow down automatically after a 429.

## Security and privacy

- The server listens **only on 127.0.0.1**. Other computers on your network cannot reach it.
- Requests from other websites are refused (Host allow-list, cross-site/CSRF checks, security headers).
- All outgoing requests go through `http_pool.py`: HTTPS only, only to an allow-list of services
  (a DOI in a document cannot make the tool contact anywhere else), full certificate checks, response
  size limits, and error messages never contain keys.
- Uploaded files get safe names and are deleted after analysis. `search_config.json`, `corpus/`,
  caches and history are in `.gitignore`.

## API

```bash
# Analyse a file
curl -X POST -F "file=@document.pdf" http://localhost:5000/analyze

# Analyse text
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "Your text here..."}' \
  http://localhost:5000/analyze-text
```

Without `progressive`, the response contains all results at once. With `progressive`
(form `progressive=1` / JSON `"progressive": true`), the score returns immediately together with
`analysis.external_job`; poll `GET /jobs/<external_job>` for `{"status": "running"}` or
`{"status": "done", "plagiarism": {...}, "references": {...}}` (returned once, then 404).

Example response (abridged):

```json
{
  "status": "success",
  "analysis": {
    "score": 87.3,
    "is_likely_ai": true,
    "confidence": "HIGH",
    "language": "English",
    "verdict": "Πιθανώς AI-generated κείμενο",
    "verdict_i18n": {"en": "Likely AI-generated text", "el": "Πιθανώς AI-generated κείμενο"},
    "reliability": 100,
    "features": [ {"name": "ai_phrases", "score": 95.2, "weight": 0.32, "examples": ["delve into (×2)"]} ],
    "highlights": [ {"text": "In today's rapidly evolving...", "hits": ["in today's ... world"], "count": 2} ],
    "revision_guide": [
      {"feature": "ai_phrases", "impact_points": 16.2,
       "suggestions": [{"found": "delve into", "try": ["look at", "examine", "explore"]}]}
    ],
    "text_stats": {"words": 260, "sentences": 15, "average_sentence_length": 17.3},
    "model_signature": {"has_signal": false, "primary_model": null}
  }
}
```

Every human-readable field also comes in all UI languages (`*_i18n` fields), so switching language
does not need a new analysis.

## Adding a UI language

For a new language (e.g. Italian, `it`):

1. `detector_academic.html`: add `it` to `LANGUAGES` and an `it: {...}` block to `STRINGS`.
2. `detector_engine.py`: add `"it"` to `UI_LANGS` and translations to `FEATURE_LABELS`, `VERDICTS`,
   `MIXED_VERDICT`, `LANGUAGE_NAMES`, `CONNECTOR_HIT`, `DETAILS`, `FEATURE_ADVICE`.
3. `model_signature.py` (`EXTRA_DESCRIPTIONS`), `ai_detector_server.py` (`MESSAGES`),
   `plagiarism_engine.py` (`VALIDATION_MESSAGES`).

`python test_detector.py` fails if an engine translation is missing; anything untranslated falls back
to English. Note that the *text analysis* supports Greek and English documents; that is separate from
the interface language.

## Tests

```bash
python test_detector.py               # engine, model signature, revision guide, i18n, signals
python test_detector.py --files       # + builds docx/pdf files and checks extraction (needs reportlab)
python test_detector.py --server      # + end-to-end checks (the server must be running)
python test_detector.py --thesis      # + mixed document with sections, speed on 40k+ words
python test_detector.py --plagiarism  # + corpus winnowing, robustness, Wikipedia (needs internet)
python test_detector.py --security    # + CSRF, Host allow-list, security headers (no server needed)
python test_detector.py --binoculars  # + Binoculars with small local models (needs torch)
node tools/check_ui.js                # UI: JavaScript syntax + translation completeness
```

**CI:** on every push to `main` and every pull request, GitHub Actions (`.github/workflows/ci.yml`)
runs lint (ruff), all tests except `--plagiarism` on Python 3.10 and 3.12, an end-to-end check against
a real server and the UI check. Dependabot opens pull requests for dependency updates.

Current calibration: AI samples score 96–99%, human samples 0–29%; separation of 88 points (EN) and
67 points (EL).

## Files

| File | Role |
|---|---|
| `ai_detector_server.py` | Flask server (endpoints, docx/pdf extraction) |
| `detector_engine.py` | AI detection core, pure Python with no external dependencies |
| `model_signature.py` | Model-specific signatures (ChatGPT/Gemini/Claude), experimental |
| `plagiarism_engine.py` | Plagiarism check: corpus winnowing, Wikipedia, OpenAlex, Brave |
| `reference_check.py` | Whether references exist (Crossref + OpenAlex) |
| `docx_forensics.py` | .docx editing history (rsid, editing time, metadata) |
| `obfuscation_check.py` | Evasion tricks: invisible characters, look-alikes, tortured phrases |
| `binoculars_check.py`, `tools/calibrate_binoculars.py` | Optional Binoculars method + threshold calibration |
| `zip_import.py`, `text_exclusions.py`, `score_calibration.py` | eClass/Moodle ZIP · quote/bibliography exclusion · calibration on your data |
| `report_docx.py` | Word (.docx) check report |
| `ocr_pdf.py` | OCR for scanned PDFs with Tesseract (optional) |
| `image_reuse.py` | Reused images/diagrams across the corpus and between theses |
| `analysis_history.py` | Local analysis history with retention limits |
| `version_compare.py`, `corpus_manager.py` | Version comparison · safe corpus management from the page |
| `background_jobs.py` | Background internet checks (instant score) with limits and TTL |
| `web_cache.py`, `http_pool.py` | Local cache of external checks · safe keep-alive connections |
| `tools/batch_analyze.py` | Batch analysis of a folder from the command line → CSV/JSON |
| `tools/live_smoke.py` | Smoke test against the real services |
| `tools/check_ui.js` | UI check: JavaScript + translation completeness |
| `notebooks/binoculars_gpu.ipynb` | Kaggle/Colab notebook: Binoculars on a free GPU |
| `corpus/` | Put past theses here for comparison |
| `detector_academic.html` | Web UI (served at `/`) |
| `test_detector.py` | Test suite / calibration |
| `run.bat`, `run.sh`, `launcher.py` | One-click start (venv, libraries, browser, shortcut) |
| `update.bat`, `update.sh`, `tools/update.py` | Update without losing settings or data |
| `QUICK_START.md` | Step-by-step user guide (Greek) |
| `docs/` | Changelog, sample texts, research notes on model signatures |

## Limitations

1. **No AI detector is infallible**, commercial ones included (GPTZero, Turnitin). The result is an
   indication, not proof.
2. Carefully edited human text in a formal style (e.g. many "Moreover") can score higher.
3. AI text that a person has rewritten or paraphrased is harder to detect.
4. Scanned PDFs (images) can only be read with OCR (Tesseract, optional); recognition errors affect
   the score.
5. Texts under ~200 words give an uncertain result.
6. Texts by non-native speakers or in a very formulaic academic style are at higher risk of false
   positives.
7. The plagiarism check has **no** access to Turnitin's database; it covers only the local corpus and
   public sources.

**Do not use this tool as the only basis for academic-integrity decisions.**

## Licence

[MIT](LICENSE)
