#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binoculars — δεύτερη, ανεξάρτητη μέθοδος ανίχνευσης (ΠΡΟΑΙΡΕΤΙΚΗ).

Hans et al. 2024, «Spotting LLMs With Binoculars» (arXiv:2401.12070). Δύο
συγγενικά γλωσσικά μοντέλα (observer + performer, ίδιος tokenizer) «διαβάζουν»
το κείμενο:
    ppl   = πόσο «αναμενόμενο» είναι το κείμενο για τον performer
    x_ppl = πόσο αναμενόμενες είναι οι προβλέψεις του observer για τον performer
    score = ppl / x_ppl      → χαμηλό score = μοιάζει με AI
Δεν χρειάζεται εκπαίδευση. Οι συγγραφείς αναφέρουν >90% ανίχνευση κειμένων
ChatGPT με 0.01% ψευδώς θετικά (Falcon-7B), καλύτερα στα αγγλικά.

ΕΝΕΡΓΟΠΟΙΗΣΗ (βαριά: θέλει torch + transformers και λήψη μοντέλων):
    pip install -r requirements-binoculars.txt
    AI_DETECTOR_BINOCULARS=qwen2.5-1.5b python ai_detector_server.py
    python tools/calibrate_binoculars.py        # μία φορά, για όριο απόφασης
  ή δικό σου ζεύγος (ίδιος tokenizer):
    AI_DETECTOR_BINOCULARS=custom AI_DETECTOR_BINOCULARS_OBSERVER=… AI_DETECTOR_BINOCULARS_PERFORMER=…
Χωρίς τη μεταβλητή περιβάλλοντος δεν φορτώνεται τίποτα και η εφαρμογή μένει
ελαφριά. Τα όρια του paper ισχύουν ΜΟΝΟ για το ζεύγος Falcon-7B· για άλλα
ζεύγη το tools/calibrate_binoculars.py υπολογίζει όριο από δείγματα.
"""

import json
import os
import threading
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Sequence

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = Path(os.environ.get("AI_DETECTOR_BINOCULARS_CONFIG",
                                  BASE_DIR / "binoculars_config.json"))

PRESETS: Dict[str, Dict] = {
    # Το ζεύγος του paper — όρια από τον επίσημο κώδικα. ~28 GB, θέλει GPU.
    "falcon-7b": {"observer": "tiiuae/falcon-7b", "performer": "tiiuae/falcon-7b-instruct",
                  "threshold": 0.9015310749276843, "threshold_low_fpr": 0.8536432310785527},
    # Ελαφρύτερο, πολυγλωσσικό (και ελληνικά). ~6 GB RAM σε CPU. Χρειάζεται βαθμονόμηση.
    "qwen2.5-1.5b": {"observer": "Qwen/Qwen2.5-1.5B", "performer": "Qwen/Qwen2.5-1.5B-Instruct",
                     "threshold": None},
    "qwen2.5-0.5b": {"observer": "Qwen/Qwen2.5-0.5B", "performer": "Qwen/Qwen2.5-0.5B-Instruct",
                     "threshold": None},
    # Ελληνικά μοντέλα του ΙΕΛ / «Αθηνά» — εκπαιδευμένα σε μεγάλο ελληνικό σώμα κειμένων,
    # άρα πιο ευαίσθητα στο ελληνικό ύφος. Μεγάλα: θέλουν GPU (σε 4-bit ~6 GB το καθένα,
    # χωράνε μαζί σε δωρεάν T4 16 GB). Χρειάζονται βαθμονόμηση.
    # Krikri (Llama 3.1 8B + ελληνικά): άδεια Llama 3.1 Community License.
    "krikri-8b": {"observer": "ilsp/Llama-Krikri-8B-Base", "performer": "ilsp/Llama-Krikri-8B-Instruct",
                  "threshold": None, "quantize": "4bit"},
    # Meltemi (Mistral 7B + ελληνικά): άδεια Apache-2.0.
    "meltemi-7b": {"observer": "ilsp/Meltemi-7B-v1.5", "performer": "ilsp/Meltemi-7B-Instruct-v1.5",
                   "threshold": None, "quantize": "4bit"},
}
QUANT_MODES = ("4bit", "8bit")

# Δείγμα για τον έλεγχο ότι observer και performer «κόβουν» το κείμενο ίδια
_TOKENIZER_PROBE = ("Η τεχνητή νοημοσύνη αλλάζει τον τρόπο που γράφουμε εργασίες. "
                    "Artificial intelligence changes how theses are written, 2024 (σελ. 12–15).")

MAX_TOKENS = 512         # μήκος κάθε τμήματος
MAX_CHUNKS = 8           # δείγμα τμημάτων για μεγάλα κείμενα (διπλωματικές)
MIN_TOKENS = 64          # κάτω από αυτό το score δεν είναι αξιόπιστο


def requested_quantization(preset_default: Optional[str] = None) -> Optional[str]:
    """AI_DETECTOR_BINOCULARS_QUANT=4bit|8bit|off — αλλιώς ό,τι ορίζει το preset."""
    value = (os.environ.get("AI_DETECTOR_BINOCULARS_QUANT") or "").strip().lower()
    if value in ("off", "none", "0", "no", "false"):
        return None
    if value in QUANT_MODES:
        return value
    return preset_default if preset_default in QUANT_MODES else None


def requested_preset() -> Optional[str]:
    name = (os.environ.get("AI_DETECTOR_BINOCULARS") or "").strip().lower()
    return None if name in ("", "0", "off", "false", "no") else name


def load_config() -> Dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def resolve_settings(preset: str) -> Dict:
    """Μοντέλα + όριο: preset, με υπερισχύ της βαθμονόμησης για το ίδιο ζεύγος.
    «custom»: δικό σου ζεύγος (όνομα Hugging Face ή τοπικός φάκελος) από τις
    AI_DETECTOR_BINOCULARS_OBSERVER / AI_DETECTOR_BINOCULARS_PERFORMER."""
    if preset == "custom":
        observer = os.environ.get("AI_DETECTOR_BINOCULARS_OBSERVER", "").strip()
        performer = os.environ.get("AI_DETECTOR_BINOCULARS_PERFORMER", "").strip()
        if not observer or not performer:
            raise ValueError("Το preset «custom» θέλει AI_DETECTOR_BINOCULARS_OBSERVER "
                             "και AI_DETECTOR_BINOCULARS_PERFORMER")
        base = {"observer": observer, "performer": performer, "threshold": None}
    elif preset in PRESETS:
        base = PRESETS[preset]
    else:
        raise ValueError(f"Άγνωστο preset Binoculars: {preset} "
                         f"(διαθέσιμα: {', '.join(PRESETS)}, custom)")
    settings = dict(base, preset=preset, calibrated=False)
    settings["quantize"] = requested_quantization(base.get("quantize"))
    cfg = load_config()
    # Το 4/8-bit αλλάζει λίγο τα scores: όριο μόνο από βαθμονόμηση με την ίδια ρύθμιση
    if cfg.get("observer") == settings["observer"] and cfg.get("performer") == settings["performer"] \
            and cfg.get("quantize") == settings["quantize"] and isinstance(cfg.get("threshold"), (int, float)):
        settings["threshold"] = float(cfg["threshold"])
        settings["calibrated"] = True
    elif settings["threshold"] is not None:
        settings["calibrated"] = True          # όρια του paper (Falcon)
    return settings


# ---------------------------------------------------------------------------
# Μαθηματικά (ίδια με binoculars/metrics.py του επίσημου κώδικα)
# ---------------------------------------------------------------------------

def binoculars_scores(input_ids, attention_mask, observer_logits, performer_logits):
    """Score ανά ακολουθία (batch). Tensors torch: ids/mask [B,T], logits [B,T,V]."""
    import torch
    import torch.nn.functional as F

    # Ίδιος tokenizer, αλλά τα μοντέλα μπορεί να έχουν διαφορετικό πλήθος γραμμών
    # εξόδου (padding του πίνακα ή επιπλέον special tokens συνομιλίας στο instruct):
    # κρατάμε το κοινό λεξιλόγιο — τα επιπλέον tokens δεν εμφανίζονται σε κείμενο.
    vocab = min(observer_logits.shape[-1], performer_logits.shape[-1])
    observer_logits = observer_logits[..., :vocab]
    performer_logits = performer_logits[..., :vocab]

    # Perplexity του κειμένου υπό τον performer (πρόβλεψη επόμενου token)
    shifted = performer_logits[..., :-1, :].contiguous()
    targets = input_ids[..., 1:].contiguous()
    mask = attention_mask[..., 1:].to(shifted.dtype)
    ce = F.cross_entropy(shifted.transpose(1, 2), targets, reduction="none")
    ppl = (ce * mask).sum(1) / mask.sum(1).clamp(min=1)

    # Cross-perplexity: κατανομή του observer έναντι log-πιθανοτήτων του performer
    p = torch.softmax(observer_logits.float(), dim=-1)
    log_q = torch.log_softmax(performer_logits.float(), dim=-1)
    x = -(p * log_q).sum(-1)
    full_mask = attention_mask.to(x.dtype)
    x_ppl = (x * full_mask).sum(1) / full_mask.sum(1).clamp(min=1)
    return (ppl.float() / x_ppl).tolist()


class BinocularsScorer:
    """Δέχεται ήδη φορτωμένα μοντέλα — έτσι δοκιμάζεται και με μικρά, τοπικά μοντέλα."""

    def __init__(self, observer, performer, tokenizer, device: str = "cpu",
                 max_tokens: int = MAX_TOKENS, max_chunks: int = MAX_CHUNKS):
        self.observer = observer.eval()
        self.performer = performer.eval()
        self.tokenizer = tokenizer
        self.device = device
        self.max_tokens = max_tokens
        self.max_chunks = max_chunks
        self._lock = threading.Lock()   # ο server είναι threaded· ένα inference τη φορά

    def _chunks(self, ids: List[int]) -> List[List[int]]:
        windows = [ids[i:i + self.max_tokens] for i in range(0, len(ids), self.max_tokens)]
        windows = [w for w in windows if len(w) >= MIN_TOKENS] or windows[:1]
        if len(windows) > self.max_chunks:          # ομοιόμορφο δείγμα σε όλο το έγγραφο
            step = len(windows) / self.max_chunks
            windows = [windows[int(i * step)] for i in range(self.max_chunks)]
        return windows

    def score(self, text: str) -> Dict:
        import torch
        ids = self.tokenizer(text, add_special_tokens=False)["input_ids"]
        if len(ids) < MIN_TOKENS:
            return {"tokens": len(ids), "scores": []}
        scores = []
        with self._lock, torch.inference_mode():
            for window in self._chunks(ids):
                input_ids = torch.tensor([window], device=self.device)
                mask = torch.ones_like(input_ids)
                obs = self.observer(input_ids=input_ids, attention_mask=mask).logits
                perf = self.performer(input_ids=input_ids, attention_mask=mask).logits
                scores.extend(binoculars_scores(input_ids, mask, obs, perf))
        return {"tokens": len(ids), "scores": scores}


def tokenizers_compatible(tok_a, tok_b) -> bool:
    """Το Binoculars θέλει ΙΔΙΟ tokenizer. Δεχόμαστε μόνο μία διαφορά: το instruct
    μοντέλο μπορεί να έχει επιπλέον added/special tokens (π.χ. <|im_start|>), με ids
    ΜΕΤΑ το κοινό λεξιλόγιο — κανονικές λέξεις με άλλο id απορρίπτονται."""
    va, vb = tok_a.get_vocab(), tok_b.get_vocab()
    if va != vb:
        small, big, big_tok = (va, vb, tok_b) if len(va) <= len(vb) else (vb, va, tok_a)
        if any(big.get(token) != i for token, i in small.items()):
            return False
        added = {str(t) for t in getattr(big_tok, "added_tokens_decoder", {}).values()}
        added |= set(getattr(big_tok, "all_special_tokens", []))
        limit = max(small.values(), default=-1) + 1
        if not all(i >= limit and token in added for token, i in big.items() if token not in small):
            return False
    probe = lambda tok: tok(_TOKENIZER_PROBE, add_special_tokens=False)["input_ids"]  # noqa: E731
    return probe(tok_a) == probe(tok_b)


def load_scorer(observer_name: str, performer_name: str,
                quantize: Optional[str] = None) -> BinocularsScorer:
    """Φόρτωση μοντέλων από Hugging Face (κατεβαίνουν την πρώτη φορά)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else (
        "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")
    if device == "cuda":
        # bfloat16 μόνο όπου υποστηρίζεται (Ampere+)· π.χ. η δωρεάν T4 του
        # Colab/Kaggle θέλει float16, αλλιώς πέφτει σε αργή εξομοίωση.
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    else:
        dtype = torch.float32
    tok = AutoTokenizer.from_pretrained(observer_name, trust_remote_code=False)
    tok_perf = AutoTokenizer.from_pretrained(performer_name, trust_remote_code=False)
    if not tokenizers_compatible(tok, tok_perf):
        raise ValueError("Το Binoculars θέλει observer και performer με ΙΔΙΟ tokenizer")
    import transformers
    major_minor = tuple(int(x) for x in transformers.__version__.split(".")[:2])
    # Από τη 4.56 η παράμετρος λέγεται «dtype» (το «torch_dtype» αποσύρεται)
    kwargs = {"dtype" if major_minor >= (4, 56) else "torch_dtype": dtype,
              "trust_remote_code": False}
    if quantize and device == "cuda":
        # 4/8-bit (bitsandbytes, μόνο NVIDIA): τα 7-8B μοντέλα χωράνε σε δωρεάν GPU 16 GB
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = (
            BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype)
            if quantize == "4bit" else BitsAndBytesConfig(load_in_8bit=True))
        kwargs["device_map"] = {"": 0}
        observer = AutoModelForCausalLM.from_pretrained(observer_name, **kwargs)
        performer = AutoModelForCausalLM.from_pretrained(performer_name, **kwargs)
    else:
        observer = AutoModelForCausalLM.from_pretrained(observer_name, **kwargs).to(device)
        performer = AutoModelForCausalLM.from_pretrained(performer_name, **kwargs).to(device)
    return BinocularsScorer(observer, performer, tok, device=device)


# ---------------------------------------------------------------------------
# Βαθμονόμηση ορίου
# ---------------------------------------------------------------------------

def calibrate_threshold(ai_scores: Sequence[float], human_scores: Sequence[float]) -> Dict:
    """Όριο που μεγιστοποιεί τη μέση ακρίβεια (AI κάτω, άνθρωπος πάνω από το όριο).
    Σε ισοπαλία προτιμάται το χαμηλότερο όριο (λιγότερα ψευδώς θετικά)."""
    if not ai_scores or not human_scores:
        raise ValueError("Χρειάζονται δείγματα και AI και ανθρώπινα")
    candidates = sorted(set(ai_scores) | set(human_scores))
    mids = [(a + b) / 2 for a, b in zip(candidates, candidates[1:])] or candidates
    best = None
    for th in mids:
        tpr = sum(s < th for s in ai_scores) / len(ai_scores)
        tnr = sum(s >= th for s in human_scores) / len(human_scores)
        key = ((tpr + tnr) / 2, -th)
        if best is None or key > best[0]:
            best = (key, th, tpr, tnr)
    _, th, tpr, tnr = best
    return {"threshold": th, "ai_detected": round(tpr, 3), "human_correct": round(tnr, 3),
            "n_ai": len(ai_scores), "n_human": len(human_scores)}


# ---------------------------------------------------------------------------
# Κύρια συνάρτηση για τον server
# ---------------------------------------------------------------------------

_scorer: Optional[BinocularsScorer] = None
_settings: Optional[Dict] = None
_load_error: Optional[str] = None
_load_lock = threading.Lock()


def _get_scorer():
    global _scorer, _settings, _load_error
    with _load_lock:
        if _scorer is None and _load_error is None:
            try:
                _settings = resolve_settings(requested_preset())
                _scorer = load_scorer(_settings["observer"], _settings["performer"],
                                      quantize=_settings.get("quantize"))
            except Exception as e:      # λείπει torch, λάθος preset, αποτυχία λήψης…
                _load_error = f"{type(e).__name__}: {e}"
    return _scorer, _settings, _load_error


def check_binoculars(text: str, scorer: Optional[BinocularsScorer] = None,
                     settings: Optional[Dict] = None) -> Dict:
    """status: disabled | unavailable | too_short | ok. Ποτέ δεν ρίχνει εξαίρεση."""
    if scorer is None:
        if not requested_preset():
            return {"status": "disabled"}
        scorer, settings, error = _get_scorer()
        if scorer is None:
            return {"status": "unavailable", "error": error}
    settings = settings or {"preset": "custom", "threshold": None, "calibrated": False}
    result = scorer.score(text or "")
    if not result["scores"]:
        return {"status": "too_short", "tokens": result["tokens"], "preset": settings.get("preset")}
    score = median(result["scores"])
    threshold = settings.get("threshold")
    verdict = None if threshold is None else ("ai" if score < threshold else "human")
    return {
        "status": "ok",
        "score": round(score, 4),
        "threshold": round(threshold, 4) if threshold is not None else None,
        "verdict": verdict,
        "calibrated": bool(settings.get("calibrated")),
        "preset": settings.get("preset"),
        "chunks": len(result["scores"]),
        "chunk_scores": [round(s, 4) for s in result["scores"]],
        "tokens": result["tokens"],
    }
