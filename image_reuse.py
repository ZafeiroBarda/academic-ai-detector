#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Επαναχρησιμοποίηση εικόνων / διαγραμμάτων: ίδιες εικόνες ανάμεσα στην εργασία
και στο corpus, ή ανάμεσα στις εργασίες του μαζικού ελέγχου.

Κάθε εικόνα (από .docx: word/media/·  από PDF: αντικείμενα εικόνας) παίρνει
ένα «οπτικό αποτύπωμα» (difference hash, 128 bit): ίδιο αποτύπωμα — ή πολύ
κοντινό — σημαίνει ίδια εικόνα, ακόμη κι αν άλλαξε μέγεθος ή συμπίεση.

Ψευδώς θετικά που αποφεύγονται:
  • μικρά εικονίδια/γραμμές (< MIN_SIDE px) και σχεδόν μονόχρωμες εικόνες·
  • «κοινές» εικόνες (λογότυπο ιδρύματος, πρότυπο εξωφύλλου): ό,τι υπάρχει
    σε COMMON_MIN_DOCS ή περισσότερα έγγραφα αγνοείται.

Ασφάλεια (τα αρχεία είναι αναξιόπιστα):
  • μόνο PNG/JPEG/GIF/BMP/TIFF/WEBP — όχι SVG/WMF/EMF·
  • όρια: εικόνες ανά έγγραφο, σελίδες PDF, bytes ανά εικόνα, pixels (κατά
    της «βόμβας αποσυμπίεσης»), αναλογία συμπίεσης στο .docx, χρόνος·
  • οι εικόνες διαβάζονται στη μνήμη· τίποτα δεν γράφεται στον δίσκο εκτός
    από τα αποτυπώματα του corpus (όχι οι ίδιες οι εικόνες).
"""

import base64
import io
import json
import os
import threading
import time
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from PIL import Image

from ocr_pdf import PDFIUM_LOCK

MIN_SIDE = 100                       # px
MAX_IMAGES = 300                     # ανά έγγραφο
MAX_PDF_PAGES = 600
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_RATIO = 150                      # αποσυμπιεσμένο / συμπιεσμένο (docx)
TIME_BUDGET = 60.0                   # δευτ. ανά έγγραφο
MATCH_DISTANCE = 10                  # από 128 bit
COMMON_MIN_DOCS = 3
MAX_SOURCES = 8
MAX_THUMBS_PER_SOURCE = 4
THUMB_SIDE = 160
ALLOWED_FORMATS = ("PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP")
CACHE_NAME = ".image_index.json"
CACHE_VERSION = 1

_IMAGE_ERRORS = (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError)


# ---------------------------------------------------------------------------
# Αποτύπωμα
# ---------------------------------------------------------------------------

def _on_white(im: Image.Image) -> Image.Image:
    """Διαφανές φόντο → λευκό (τα διαγράμματα PNG έχουν συχνά διαφάνεια)."""
    if im.mode in ("RGBA", "LA", "P", "PA"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return bg
    return im


def dhash(im: Image.Image) -> Optional[str]:
    """128-bit difference hash (οριζόντιο + κάθετο) ή None για «άδεια» εικόνα."""
    gray = _on_white(im).convert("L")
    lo, hi = gray.getextrema()
    if hi - lo < 16:                       # σχεδόν μονόχρωμη: όχι πληροφορία
        return None
    h = list(gray.resize((9, 8), Image.LANCZOS).getdata())
    v = list(gray.resize((8, 9), Image.LANCZOS).getdata())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (h[r * 9 + c] > h[r * 9 + c + 1])
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (v[r * 8 + c] > v[(r + 1) * 8 + c])
    return f"{bits:032x}"


def distance(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def _thumb_uri(im: Image.Image) -> str:
    t = _on_white(im).convert("RGB")
    t.thumbnail((THUMB_SIDE, THUMB_SIDE))
    buf = io.BytesIO()
    t.save(buf, format="JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


WORK_SIDE = 512          # οι εικόνες μικραίνουν αμέσως: λίγη μνήμη, ίδιο αποτύπωμα


def _small(im: Image.Image) -> Image.Image:
    im = im.copy() if im.mode != "P" else im.convert("RGBA")
    im.thumbnail((WORK_SIDE, WORK_SIDE))
    return im


def _open_bytes(data: bytes) -> Optional[Tuple[Image.Image, Tuple[int, int]]]:
    try:
        im = Image.open(io.BytesIO(data), formats=ALLOWED_FORMATS)
        size = im.size
        if min(size) < MIN_SIDE or size[0] * size[1] > MAX_PIXELS:
            return None
        im.draft("RGB", (WORK_SIDE, WORK_SIDE))  # JPEG: γρήγορη μικρή αποκωδικοποίηση
        im.load()
        return _small(im), size
    except _IMAGE_ERRORS:
        return None


# ---------------------------------------------------------------------------
# Εξαγωγή εικόνων
# ---------------------------------------------------------------------------

def _docx_images(path: Path) -> Iterator[Tuple[str, Image.Image, Tuple[int, int]]]:
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.startswith("word/media/"):
                continue
            if info.file_size > MAX_IMAGE_BYTES or info.file_size > MAX_RATIO * max(info.compress_size, 1):
                continue
            if info.flag_bits & 0x1:            # κρυπτογραφημένο
                continue
            with zf.open(info) as fh:
                data = fh.read(MAX_IMAGE_BYTES + 1)
            if len(data) > MAX_IMAGE_BYTES:
                continue
            opened = _open_bytes(data)
            if opened is not None:
                yield (info.filename,) + opened


def _pdf_images(path: Path) -> Iterator[Tuple[str, Image.Image, Tuple[int, int]]]:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c
    # Το PDFium δεν είναι thread-safe: το κλείδωμα κρατιέται όσο διαβάζουμε
    # (μία εικόνα τη φορά — ο καλών μόνο υπολογίζει το αποτύπωμα και συνεχίζει).
    with PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(str(path))
        try:
            count = 0
            for pi in range(min(len(pdf), MAX_PDF_PAGES)):
                page = pdf[pi]
                try:
                    for oi, obj in enumerate(page.get_objects(filter=(pdfium_c.FPDF_PAGEOBJ_IMAGE,),
                                                              max_depth=2)):
                        try:
                            w, h = obj.get_px_size()
                            if w < MIN_SIDE or h < MIN_SIDE or w * h > MAX_PIXELS:
                                continue
                            # αντίγραφο σε μικρό μέγεθος όσο είναι ανοιχτό το PDF
                            im = _small(obj.get_bitmap(render=False).to_pil())
                        except Exception:
                            continue
                        yield f"p{pi}:{oi}", im, (w, h)
                        count += 1
                        if count >= MAX_IMAGES:
                            break
                finally:
                    page.close()
                if count >= MAX_IMAGES:
                    break
        finally:
            pdf.close()


def _iter_images(path: Path) -> Iterator[Tuple[str, Image.Image, Tuple[int, int]]]:
    ext = path.suffix.lower()
    if ext == ".docx":
        yield from _docx_images(path)
    elif ext == ".pdf":
        yield from _pdf_images(path)


def extract(path, budget: float = TIME_BUDGET) -> Dict:
    """{"images": [{ref, hash, w, h}], "truncated": bool} — ποτέ δεν ρίχνει εξαίρεση."""
    path = Path(path)
    out: List[Dict] = []
    truncated = False
    deadline = time.monotonic() + budget
    try:
        with closing(_iter_images(path)) as images:
            for ref, im, (w, h) in images:
                if len(out) >= MAX_IMAGES or time.monotonic() > deadline:
                    truncated = True
                    break
                try:
                    hd = dhash(im)
                except _IMAGE_ERRORS:
                    continue
                if hd:
                    out.append({"ref": ref, "hash": hd, "w": w, "h": h})
    except Exception:                          # χαλασμένο αρχείο κ.λπ.
        pass
    return {"images": out, "truncated": truncated}


def thumbnails(path, refs) -> Dict[str, str]:
    """Μικρογραφίες (data URI) συγκεκριμένων εικόνων του εγγράφου — ένα πέρασμα."""
    wanted, out = set(refs), {}
    if not wanted:
        return out
    try:
        with closing(_iter_images(Path(path))) as images:
            for r, im, _ in images:
                if r in wanted:
                    out[r] = _thumb_uri(im)
                    if len(out) == len(wanted):
                        break
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Σύγκριση
# ---------------------------------------------------------------------------

def _matches(a: List[Dict], b: List[Dict]) -> List[Tuple[int, int, int]]:
    """Ζεύγη (i, j, απόσταση): κάθε εικόνα του a με την πιο κοντινή του b."""
    out = []
    bv = [int(y["hash"], 16) for y in b]
    for i, x in enumerate(a):
        xv = int(x["hash"], 16)
        best = None
        for j, yv in enumerate(bv):
            d = (xv ^ yv).bit_count()
            if d <= MATCH_DISTANCE and (best is None or d < best[1]):
                best = (j, d)
        if best:
            out.append((i, best[0], best[1]))
    return out


class ImageIndex:
    """Αποτυπώματα εικόνων του corpus, με cache (corpus/.image_index.json) — όπως το CorpusIndex."""

    def __init__(self, corpus_dir):
        self.dir = Path(corpus_dir)
        self.files: Dict[str, Dict] = {}
        self._signature = None
        self._lock = threading.Lock()

    def _listing(self) -> Dict[str, Tuple[float, int]]:
        out = {}
        if not self.dir.is_dir():
            return out
        for p in sorted(self.dir.iterdir()):
            if (p.is_file() and not p.is_symlink() and p.suffix.lower() in (".docx", ".pdf")
                    and not p.name.startswith(".")):
                st = p.stat()
                out[p.name] = (st.st_mtime, st.st_size)
        return out

    def _load(self) -> None:
        if self.files:
            return
        try:
            data = json.loads((self.dir / CACHE_NAME).read_text(encoding="utf-8"))
            if data.get("version") == CACHE_VERSION and isinstance(data.get("files"), dict):
                self.files = data["files"]
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        path = self.dir / CACHE_NAME
        tmp = path.with_name(path.name + ".tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"version": CACHE_VERSION, "files": self.files}, fh, separators=(",", ":"))
            os.replace(tmp, path)
        except OSError:
            pass

    def refresh(self) -> None:
        with self._lock:
            listing = self._listing()
            signature = tuple(sorted(listing.items()))
            if signature == self._signature:
                return
            self._load()
            changed = False
            for name, (mtime, size) in listing.items():
                entry = self.files.get(name)
                if entry and abs(entry.get("mtime", 0) - mtime) < 1 and entry.get("size") == size:
                    continue
                self.files[name] = {"mtime": mtime, "size": size,
                                    "images": extract(self.dir / name)["images"]}
                changed = True
            for name in list(self.files):
                if name not in listing:
                    del self.files[name]
                    changed = True
            if changed:
                self._save()
            self._signature = signature

    @property
    def n_images(self) -> int:
        return sum(len(e.get("images", [])) for e in self.files.values())

    def compare(self, doc_path, doc: Optional[Dict] = None, thumbs: bool = True) -> Dict:
        """Ίδιες εικόνες με το corpus. Οι «κοινές» (σε ≥ COMMON_MIN_DOCS αρχεία) αγνοούνται."""
        self.refresh()
        doc = doc or extract(doc_path)
        images = doc["images"]
        per_file: Dict[str, List[Tuple[int, int, int]]] = {}
        for name, entry in self.files.items():
            for m in _matches(images, entry.get("images", [])):
                per_file.setdefault(name, []).append(m)
        hits_per_image: Dict[int, set] = {}
        for name, ms in per_file.items():
            for i, _, _ in ms:
                hits_per_image.setdefault(i, set()).add(name)
        common = {i for i, names in hits_per_image.items() if len(names) >= COMMON_MIN_DOCS}
        sources = []
        for name, ms in per_file.items():
            ms = [m for m in ms if m[0] not in common]
            if ms:
                sources.append((name, ms))
        sources.sort(key=lambda s: -len(s[1]))
        result = {"checked": len(images), "truncated": doc["truncated"], "common": len(common),
                  "corpus_images": self.n_images, "sources": []}
        shown = [(name, ms[:MAX_THUMBS_PER_SOURCE], len(ms)) for name, ms in sources[:MAX_SOURCES]]
        doc_thumbs = thumbnails(doc_path, {images[i]["ref"] for _, ms, _ in shown for i, _, _ in ms}) \
            if thumbs else {}
        for name, ms, count in shown:
            src_images = self.files[name]["images"]
            src_thumbs = thumbnails(self.dir / name, {src_images[j]["ref"] for _, j, _ in ms}) if thumbs else {}
            result["sources"].append({"file": name, "count": count, "matches": [
                {"distance": d, "doc_thumb": doc_thumbs.get(images[i]["ref"]),
                 "source_thumb": src_thumbs.get(src_images[j]["ref"])} for i, j, d in ms]})
        return result


def batch_pairs(docs: List[Tuple[str, str, Dict]], thumbs: bool = True,
                max_pairs: int = 50) -> Dict:
    """docs: [(όνομα, διαδρομή, extract())]. Ζεύγη εργασιών με κοινές εικόνες."""
    n = len(docs)
    common_min = max(COMMON_MIN_DOCS, -(-3 * n // 10))     # ≥3 ή ≥30% των εργασιών
    pair_matches = {}
    for a in range(n):
        for b in range(a + 1, n):
            ms = _matches(docs[a][2]["images"], docs[b][2]["images"])
            if ms:
                pair_matches[(a, b)] = ms
    # «Κοινή» εικόνα: εμφανίζεται σε πολλές εργασίες (λογότυπο, πρότυπο)
    seen_in: Dict[Tuple[int, int], set] = {}
    for (a, b), ms in pair_matches.items():
        for i, j, _ in ms:
            seen_in.setdefault((a, i), {a}).add(b)
            seen_in.setdefault((b, j), {b}).add(a)
    common = {key for key, docs_with in seen_in.items() if len(docs_with) >= common_min}
    pairs = []
    for (a, b), ms in pair_matches.items():
        ms = [m for m in ms if (a, m[0]) not in common and (b, m[1]) not in common]
        if ms:
            pairs.append((a, b, ms))
    pairs.sort(key=lambda p: -len(p[2]))
    pairs = [(a, b, ms[:MAX_THUMBS_PER_SOURCE], len(ms)) for a, b, ms in pairs[:max_pairs]]
    wanted: Dict[int, set] = {}
    for a, b, ms, _ in pairs:
        for i, j, _ in ms:
            wanted.setdefault(a, set()).add(docs[a][2]["images"][i]["ref"])
            wanted.setdefault(b, set()).add(docs[b][2]["images"][j]["ref"])
    thumbs_by_doc = {k: thumbnails(docs[k][1], refs) for k, refs in wanted.items()} if thumbs else {}

    def thumb(k, idx):
        return thumbs_by_doc.get(k, {}).get(docs[k][2]["images"][idx]["ref"])
    out = [{"a": docs[a][0], "b": docs[b][0], "count": count,
            "matches": [{"distance": d, "a_thumb": thumb(a, i), "b_thumb": thumb(b, j)} for i, j, d in ms]}
           for a, b, ms, count in pairs]
    return {"pairs": out, "common": len({k[0] for k in common})}
