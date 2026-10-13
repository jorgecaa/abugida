"""Ground truth from Geiger's Pāli Grammar: attested doublets and tadbhava.

Two datasets, both harvested once from Geiger, *A Pāli Grammar* (tr. Ghosh,
rev. Norman, PTS) and since then carried as a case file:

1. DOUBLETS — "X beside Y": variant forms attested side by side in the
   canon (paṭikkūla/paṭikūla, ossajjati/ossajati). Real transmission
   variation with citations — the non-synthetic ground truth the synthetic
   evals lacked.
2. TADBHAVA — "X … = Skt Y": Pāli reflexes with their Sanskrit sources, at
   scale (the previous tadbhava evals had n = 12–18 hand-picked pairs).

THE BOOK IS NOT IN THIS REPOSITORY, AND THAT IS DELIBERATE. Geiger's grammar
is in copyright; a 593 KB OCR of it is not something this project can carry.
What the case file `geiger_cases.json` holds instead is the *extraction*:
pairs of word forms, with none of the book's prose, arrangement or apparatus.
Every Pāli side had to be attested in DPD to survive extraction, so the file
is as much a fact about the dictionary as about the grammar. Even the
extraction is not distributed: it lives in the local data directory
(`eval/_data.py`, `NOTICE`), and each user rebuilds it from their own copy.

REHARVESTING NEEDS YOUR OWN COPY. `--harvest PATH` re-runs the extraction
over an NFC-normalised UTF-8 OCR of the grammar and rewrites the case file;
without `PATH` it looks for `Geiger_Pali_Grammar_OCR.txt` in the local data
directory. The extraction is precision-first: the Pāli side
must be attested in DPD (lookup ∪ lemmas), which filters OCR noise and
English words that happen to be Pāli-legal.

Evaluation is unchanged and still needs the DPD database and rapidfuzz: both
datasets rank the full DPD lexicon, tie-aware expected top-1, hybrid recipe
for speed.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _data  # noqa: E402
import _dpd  # noqa: E402

_dpd.check()
from rapidfuzz import fuzz, process  # noqa: E402

from abugida.distance import alignment, distance  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = _data.path("geiger_cases.json")
BOOK = _data.path("Geiger_Pali_Grammar_OCR.txt")

PALI = r"[a-zāīūṅñṭḍṇḷṃ]{3,}"
SKT = r"[a-zāīūṛṝḹṅñṭḍṇśṣḷṃ]{3,}"

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--harvest", nargs="?", const=BOOK, metavar="OCR_TEXT",
                    help="re-extract from your own OCR of the grammar and "
                         "rewrite the local geiger_cases.json")
args = parser.parse_args()

# --- lexicon (the attestation filter and the search space) -----------------

# Prefer a copy in /dev/shm when present, else the checkout on disk.
_shm = "/dev/shm/dpd.db"
DB = _shm if os.path.exists(_shm) and os.path.getsize(_shm) > 0 else \
    os.path.join(HERE, "..", "..", "dpd-db", "dpd.db")
con = _dpd.connect(DB)
attested = {k for (k,) in con.execute("SELECT lookup_key FROM lookup")}
lemmas = set()
for (lemma,) in con.execute("SELECT lemma_1 FROM dpd_headwords"):
    w = re.sub(r"\s+\d+(\.\d+)?$", "", lemma.strip())
    lemmas.add(w)
attested |= lemmas
search_space = sorted(
    w for w in lemmas if re.fullmatch(PALI, w) and 3 <= len(w) <= 25
)

# --- extraction ------------------------------------------------------------


def last_attested(before):
    """The last DPD-attested Pāli word in a context window."""
    for w in reversed(re.findall(PALI, before)):
        if w in attested:
            return w
    return None


def harvest(path):
    """Re-derive both datasets from an OCR of the grammar."""
    text = unicodedata.normalize("NFC", open(path, encoding="utf-8").read())

    # Adjacency-strict doublets: the X form immediately precedes "(beside",
    # with at most a quoted gloss in between. Window-scanning mis-pairs
    # badly (citation and gloss words get picked up).
    gloss = r"(?:['‘][^'’]{0,40}['’])?"
    doublets = set()
    for m in re.finditer(rf"({PALI})\s*{gloss}\s*\(?\s*beside\s+({PALI})",
                         text):
        x, y = m.group(1), m.group(2)
        # ratio >= 70 (the RIVAL measure as constructor — anti-circular)
        # keeps genuine same-word variants and drops suppletive stems
        # (hoti/bhavati), Prakrit parallels and OCR leaks.
        if x in attested and y in attested and x != y \
                and fuzz.ratio(x, y) >= 70:
            doublets.add((x, y))

    # Tadbhava: nearest preceding attested word, PLUS a relatedness filter
    # using the RIVAL measure (char ratio) — anti-circular by construction:
    # if it biases the dataset, it biases it against the phonological metric.
    tadbhava = set()
    for m in re.finditer(rf"=\s*Skt\.?\s+({SKT})", text):
        skt = m.group(1)
        pali = last_attested(text[max(0, m.start() - 60):m.start()])
        if pali and pali != skt and fuzz.ratio(pali, skt) >= 55:
            tadbhava.add((skt, pali))
    return doublets, tadbhava


if args.harvest:
    if not os.path.exists(args.harvest):
        sys.exit(f"no OCR text at {args.harvest}; the grammar is in "
                 f"copyright and is not shipped — pass your own copy")
    doublets, tadbhava = harvest(args.harvest)
    # One pair per line: the file is meant to be read in a diff.
    def block(pairs):
        return ",\n".join("  " + json.dumps(list(p), ensure_ascii=False)
                          for p in sorted(pairs))
    os.makedirs(os.path.dirname(CASES), exist_ok=True)
    with open(CASES, "w", encoding="utf-8") as fh:
        fh.write('{\n "source": %s,\n "note": %s,\n "doublets": [\n%s\n ],'
                 '\n "tadbhava": [\n%s\n ]\n}\n' % (
                     json.dumps("Geiger, A Pāli Grammar "
                                "(tr. Ghosh, rev. Norman, PTS)",
                                ensure_ascii=False),
                     json.dumps("extracted word pairs only; regenerate with "
                                "eval/geiger.py --harvest PATH"),
                     block(doublets), block(tadbhava)))
    print(f"harvested into {os.path.relpath(CASES)}")
else:
    cases = _data.load("geiger_cases.json")
    doublets = {tuple(p) for p in cases["doublets"]}
    tadbhava = {tuple(p) for p in cases["tadbhava"]}

print(f"extracted: {len(doublets)} doublets, {len(tadbhava)} tadbhava pairs")

# --- evaluation: rank the lexicon, tie-aware expected top-1 ----------------


def rank_char(q):
    ranked = process.extract(q, search_space, scorer=fuzz.ratio, limit=50)
    ranked = [(s, w) for w, s, _ in ranked if w != q]
    best = max(s for s, _ in ranked)
    tied = [w for s, w in ranked if abs(s - best) < 1e-9]
    return len(tied), tied


def rank_hybrid(q):
    pool = [w for w, _, _ in process.extract(
        q, search_space, scorer=fuzz.ratio, limit=200) if w != q]
    scored = [(distance(q, w, lenient=True), w) for w in pool]
    best = min(d for d, _ in scored)
    tied = [w for d, w in scored if abs(d - best) < 1e-9]
    return len(tied), tied


def evaluate(pairs, name):
    pairs = [(q, t) for q, t in pairs if t in set(search_space)]
    if not pairs:
        print(f"{name}: no evaluable pairs")
        return
    scores = {"char-level": 0.0, "hybrid": 0.0}
    for q, t in pairs:
        for label, ranker in [("char-level", rank_char),
                              ("hybrid", rank_hybrid)]:
            tied, hits = ranker(q)
            scores[label] += (1.0 / tied) if t in hits else 0.0
    n = len(pairs)
    print(f"\n== {name} (n={n}, target in lemma space) ==")
    for label, s in scores.items():
        print(f"  {label:11} expected top-1: {s / n:6.1%}")


evaluate(doublets, "Geiger doublets: one attested variant → the other")
evaluate(tadbhava, "Geiger tadbhava: Sanskrit form → Pāli reflex")

# --- audit: which edit types do real doublets embody? ----------------------
# (alignment used descriptively here — to characterise the data, not to
# decide adoption)

edit_types = Counter()
for x, y in doublets:
    try:
        ops = [op for op in alignment(x, y, lenient=True) if op[0] != "keep"]
    except ValueError:
        continue
    if len(ops) == 1:
        op, a, b, _ = ops[0]
        if op == "sub":
            edit_types[f"sub {a}↔{b}"] += 1
        else:
            edit_types[f"{op} {a or b}"] += 1
    else:
        edit_types[f"{len(ops)} edits"] += 1
print("\nedit types in real doublets (top 20):")
for kind, c in edit_types.most_common(20):
    print(f"  {c:3d}  {kind}")
