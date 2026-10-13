"""A discrimination battery that is not saturated, harvested from real data.

THE PROBLEM IT REPLACES. `tests/test_battery.py` is 30 hand-written triples
and the metric scores 29. It has stopped being an instrument: it holds 29/29
across a calibration sweep that takes `a↔ā` all the way down to 0.073, where
long and short vowels are nearly indistinguishable. It can detect a
regression; it cannot detect an improvement, because there is no headroom.

THE DESIGN. Same idea — a triple (base, nearer, farther) where the answer is
fixed independently of the metric — but harvested at scale:

  base    a lemma with an annotated phonetic variant
  nearer  that variant (ground truth: they ARE the same word's variation)
  farther a lemma that is NOT a variant of base, chosen so that
          levenshtein(base, farther) == levenshtein(base, nearer)

DIFFICULTY IS DEFINED WITHOUT THE PHONOLOGICAL METRIC, and that is the whole
point. Harvesting "cases the current metric gets wrong" would produce a set
that scores 0% by construction and that flatters any change, however
arbitrary — the same circularity `eval/karana_bridges.py` had to break. Here
Levenshtein ties by construction, so a flat measure is at chance and every
triple is decidable only by phonology. Nothing about the answer depends on
what `cost` currently does.

The distractor comes from the rapidfuzz pool, so it is a string a search
would really surface, not a random lemma that no one would confuse.

SCORE THE PIPELINE, NOT ONLY THE RAW METRIC. Both columns are printed, and
the gap between them is the point. Raw, the metric scored 50.6% and dropped to
19.9% at three edits — below chance, which looked like a deficit in `cost`.
It is not: those triples are overwhelmingly `aya↔e` alternations
(`gaṇetvā ~ gaṇayitvā`, 1.65), which `contract_word` exists to normalise. Run
through the recommended pipeline the same triples scored 66.7% overall and
**79.5% at three edits** (with the heavy units of 2026-10-13: 50.9% raw,
68.1% and 85.2% through the pipeline). Measuring the metric in isolation misdiagnosed the
project's own recommendation as a hole in the metric.

USE. Run once with `--harvest --dpd` to build `hard_battery.json` in the
local data directory (`eval/_data.py`); after that the file is enough and the
battery runs anywhere, like the hand-written one. The file is derived from
DPD and is not distributed (see `NOTICE`). Report the interval, never the point — see
`eval/protocol.py` for why.
"""

import argparse
import json
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _data  # noqa: E402
import _dpd  # noqa: E402

from abugida import (  # noqa: E402
    Lexicon,
    assimilate_word,
    contract_word,
    distance,
    levenshtein,
)


def _norm(word):
    """The recommended pipeline: phonology first, metric second."""
    return contract_word(assimilate_word(word))

CASES_PATH = _data.path("hard_battery.json")
SEED = 20260801
MAX_LEV = 3
POOL = 60
TARGET = 3000


def _clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


def harvest(db="/dev/shm/dpd.db", target=TARGET):
    con = _dpd.connect(db)
    lemmas = {_clean(l) for (l,) in con.execute(
        "SELECT lemma_1 FROM dpd_headwords")}
    by = {}
    for lemma, var in con.execute(
        "SELECT lemma_1, var_phonetic FROM dpd_headwords "
        "WHERE var_phonetic IS NOT NULL AND trim(var_phonetic) != ''"
    ):
        a = _clean(lemma)
        for piece in re.split(r"[;,]", var):
            b = _clean(piece)
            if b and a != b and a in lemmas and b in lemmas:
                by.setdefault(a, set()).add(b)
                by.setdefault(b, set()).add(a)

    lex = Lexicon(sorted(lemmas))
    rng = random.Random(SEED)
    triples = []
    for base in rng.sample(sorted(by), len(by)):
        for nearer in sorted(by[base]):
            try:
                lev = levenshtein(base, nearer)
            except Exception:
                continue
            if not 0 < lev <= MAX_LEV:
                continue
            for _, cand in lex.search(base, k=POOL, pool=POOL,
                                      max_distance=99):
                if cand == base or cand in by[base]:
                    continue
                try:
                    if levenshtein(base, cand) == lev:
                        triples.append([base, nearer, cand, lev])
                        break
                except Exception:
                    continue
            if len(triples) >= target:
                return triples
    return triples


def load():
    return _data.load("hard_battery.json")


def wilson(hits, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def score(cases, d=distance, label="metric"):
    won = ties = 0
    for base, nearer, farther, _ in cases:
        dn, df = d(base, nearer), d(base, farther)
        won += dn < df
        ties += abs(dn - df) < 1e-9
    lo, hi = wilson(won, len(cases))
    print(f"{label:<22} {won}/{len(cases)} = {100 * won / len(cases):.1f}% "
          f"[{100 * lo:.1f}, {100 * hi:.1f}]   ties {ties}")
    return [d(b, n) < d(b, f) for b, n, f, _ in cases]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--harvest", action="store_true",
                    help="rebuild the case file from DPD")
    args = ap.parse_args()

    if args.harvest:
        cases = harvest()
        os.makedirs(os.path.dirname(CASES_PATH), exist_ok=True)
        with open(CASES_PATH, "w", encoding="utf-8") as fh:
            json.dump(cases, fh, ensure_ascii=False)
        print(f"harvested {len(cases)} triples → {CASES_PATH}")
    else:
        cases = load()

    print(f"hard battery: {len(cases)} triples "
          f"(Levenshtein ties on every one, by construction)\n")

    def piped(a, b):
        return distance(_norm(a), _norm(b))

    score(cases, distance, "phonological, raw")
    score(cases, piped, "phonological, pipeline")
    score(cases, lambda a, b: float(levenshtein(a, b)), "levenshtein")
    by_lev = {}
    for c in cases:
        by_lev.setdefault(c[3], []).append(c)
    print()
    for lev in sorted(by_lev):
        score(by_lev[lev], distance, f"  raw, lev={lev}")
        score(by_lev[lev], piped, f"  pipeline, lev={lev}")
