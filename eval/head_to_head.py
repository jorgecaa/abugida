"""Levenshtein vs the phonological metric, on equal terms.

WHY THIS EXISTS. The comparison the project has published for a long time
pits the full phonological metric against a bare Levenshtein — and the
phonological pipeline's two biggest components, `assimilate_word` /
`contract_word` and the length-relative threshold, are not properties of the
metric at all. A flat measure can use both. Withholding them makes the margin
look larger than it is, which is the same class of thumb-on-the-scale as the
`CONFUSION_PAIRS` omission (TODO.md, Phase 3), and it should be held to the
same standard.

So every system here is scored at MATCHED CANDIDATE VOLUME, from the SAME
candidate pool, with each of the four upgrades available to both measures.
Comparing at equal θ would be meaningless: Levenshtein's thresholds are
integers and the two scales are unrelated.

RESULT (agreement with DPD — "recall" over its `var_phonetic` pairs, which
its own rules compute — 500 query lemmas; 2026-10-13, after the heavy units,
5,143-pair build):

    system                    0.5    1.0    2.0    4.0    8.0  cand/lemma
    levenshtein                 -      -      -   74.9   79.4
    lev + normalisation         -      -      -   81.9   85.9
    lev + norm + relative    36.0   55.8   73.3   86.2   91.6
    phonological                -   45.4   67.4   77.6   83.6
    phon + normalisation        -   53.1   78.1   84.4   89.4
    phon + norm + relative   36.4   61.4   80.7   87.2   90.6

(Before the units, on the August build, best against best was +1.4 / +5.0 /
+7.1 / +3.0 / +0.8; the Levenshtein rows moved too, so that shift is the
lexicon as much as the metric.)

Three things follow, and the first is uncomfortable:

1. **The pipeline matters more than the metric.** Levenshtein with
   normalisation and a relative threshold (86.2 at 4 cand/lemma) BEATS the
   bare phonological metric (77.6) by nine points. Most of what was gained
   came from phonology applied before measuring, not from phonology inside
   the cost.
2. **On equal terms the metric's margin is narrow and lives at low volume**:
   +5.6 points at 1 cand/lemma and +7.4 at 2, but +0.4 at 0.5, +1.0 at 4 and
   −1.0 at 8, where dressed Levenshtein is ahead — far from the ~20 points a
   bare-baseline comparison suggests.
3. **Where it matters is at LOW volume.** Bare Levenshtein cannot operate
   below ~4 candidates per lemma at all: its costs are integers, so it
   either admits "one edit" or nothing, with nothing in between. A relative
   threshold gives it fractional cuts and so low volumes too, and there the
   metric's lead is the 5–7 points above. The
   phonological metric runs at 0.5 and 1.0, which is where an integration
   with a precision budget lives. Same property that gives it 167 distinct
   values against Levenshtein's 7 (`tests/test_battery.py`), and the reason
   its margin on top-1 RANKING tasks is much larger than its margin on
   recall.

In one line: the metric buys RESOLUTION, not recall. Recall is bought by the
pipeline, which is metric-agnostic; resolution is what lets you spend that
recall cheaply.

Requires the DPD database and rapidfuzz.
"""

import bisect
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

from abugida import Lexicon, distance, levenshtein, tokenize  # noqa: E402
from abugida.lexicon import phonological_form  # noqa: E402

SEED = 20260801
QUERIES = 500
POOL = 150
VOLUMES = (0.5, 1.0, 2.0, 4.0, 8.0)


def _clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


def _length(word, cache={}):
    if word not in cache:
        try:
            cache[word] = len(tokenize(word, lenient=True))
        except Exception:
            cache[word] = len(word)
    return cache[word]


def main():
    con = _dpd.connect()
    lemmas = sorted({_clean(l) for (l,) in con.execute(
        "SELECT lemma_1 FROM dpd_headwords")})
    known = set(lemmas)
    by = {}
    for lemma, var in con.execute(
        "SELECT lemma_1, var_phonetic FROM dpd_headwords "
        "WHERE var_phonetic IS NOT NULL AND trim(var_phonetic) != ''"
    ):
        a = _clean(lemma)
        for piece in re.split(r"[;,]", var):
            b = _clean(piece)
            if b and a != b and a in known and b in known:
                by.setdefault(a, set()).add(b)
                by.setdefault(b, set()).add(a)

    lex = Lexicon(lemmas)
    rng = random.Random(SEED)
    queries = rng.sample(sorted(by), QUERIES)
    # One generous pool, identical for every system: isolates the MEASURE
    # from the prefilter, which would otherwise confound the comparison.
    pools = {q: [c for _, c in lex.search(q, k=POOL, pool=POOL,
                                          max_distance=99)]
             for q in queries}

    pf = phonological_form
    lev = lambda q, c: float(levenshtein(q, c, lenient=True))  # noqa: E731
    phon = lambda q, c: distance(q, c, lenient=True)  # noqa: E731
    lev_n = lambda q, c: lev(pf(q), pf(c))  # noqa: E731
    phon_n = lambda q, c: phon(pf(q), pf(c))  # noqa: E731

    def relative(score):
        def f(q, c):
            span = max(_length(pf(q)), _length(pf(c)), 1)
            return score(q, c) / span
        return f

    systems = [
        ("levenshtein", lev, [1, 2, 3, 4, 5, 6]),
        ("lev + normalisation", lev_n, [1, 2, 3, 4, 5, 6]),
        ("lev + norm + relative", relative(lev_n),
         [0.06, 0.09, 0.12, 0.16, 0.2, 0.28, 0.4]),
        ("phonological", phon, [0.4, 0.63, 0.9, 1.2, 1.6, 2.2, 3.0]),
        ("phon + normalisation", phon_n, [0.4, 0.63, 0.9, 1.2, 1.6, 2.2, 3.0]),
        ("phon + norm + relative", relative(phon_n),
         [0.03, 0.05, 0.07, 0.09, 0.12, 0.16, 0.22]),
    ]

    def curve(score, thetas):
        points = []
        for theta in thetas:
            hits = truth = volume = 0
            for q in queries:
                got = {c for c in pools[q] if score(q, c) <= theta + 1e-9}
                volume += len(got)
                truth += len(by[q])
                hits += len(got & by[q])
            points.append((volume / len(queries), 100 * hits / truth))
        return sorted(points)

    print(f"recall at matched candidate volume "
          f"({QUERIES} query lemmas, pool={POOL})\n")
    header = "".join(f"{v:>7.1f}" for v in VOLUMES)
    print(f"{'system':<24}{header}  cand/lemma")
    print("-" * (24 + 7 * len(VOLUMES)))
    for name, score, thetas in systems:
        points = curve(score, thetas)
        vs = [v for v, _ in points]
        rs = [r for _, r in points]
        cells = []
        for target in VOLUMES:
            if target < vs[0] or target > vs[-1]:
                cells.append(f"{'-':>7}")
                continue
            i = bisect.bisect_left(vs, target)
            if i == 0:
                cells.append(f"{rs[0]:>7.1f}")
                continue
            f = ((target - vs[i - 1]) / (vs[i] - vs[i - 1])
                 if vs[i] != vs[i - 1] else 0)
            cells.append(f"{rs[i - 1] + f * (rs[i] - rs[i - 1]):>7.1f}")
        print(f"{name:<24}" + "".join(cells))
    print("\nA dash means the system cannot reach that volume: Levenshtein's "
          "costs are\nintegers, so it has no threshold between 'one edit' "
          "and 'none'.")


if __name__ == "__main__":
    main()
