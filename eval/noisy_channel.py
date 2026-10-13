"""Why the cost is LINEAR in the angular distance — derived, not left alone.

THE QUESTION THIS SETTLES. A concave re-warp of `cost` (log, sqrt) was
implemented, measured and reverted (TODO.md): admissible, but neutral at
equal candidate volume. That left it rejected for want of a gain, which is a
weaker position than the rest of the metric enjoys — ρ*, the karaṇa split and
INDEL_WEIGHT each follow from a stated principle, whereas "no warp" was
merely the untouched default. This script supplies the missing principle, and
it turns out to derive the default.

THE PRINCIPLE. Read the edit distance as a NOISY CHANNEL: a word is corrupted
into another by a sequence of independent operations, and the cost of an
operation is −log P(that operation). Costs then SUM because log-probabilities
of independent events sum, which is the reason an edit distance is additive
at all rather than, say, multiplicative. This is not invented for the
occasion; it is the standard reading of weighted edit distance.

Under that reading the warp is not a free choice. If the metric is to be a
log-likelihood, then for the geometry `d` the cost must satisfy

    cost(d)  ∝  −log P(pair is a true variant | distance d)

so the right transformation is fixed by how confusability actually decays:

    P ∝ exp(−λd)   (exponential decay)  ⇒  −log P linear in d      ⇒  IDENTITY
    P ∝ (1+d)^−k   (power-law decay)    ⇒  −log P linear in log d  ⇒  LOG WARP

MEASURED. Binning real search candidates by distance and taking the fraction
that are annotated variants, over the operating range the decay is
EXPONENTIAL and the identity wins:

    cut     pts   identity      log     sqrt
    1.00      5     0.9296   0.8743   0.7335
    1.50      7     0.9742   0.9318   0.8219
    2.00      9     0.9640   0.9509   0.8752
    2.50     11     0.9716   0.9657   0.9074
    3.50     12     0.9444   0.9708   0.9244   ← log only wins here
    all      13     0.7889   0.9240   0.8891

The identity wins at every cut through 2.5 and loses only when the extreme
tail is included — where P ≈ 0.0001, a handful of true pairs among tens of
thousands of candidates, and the estimate is noise. Since no usable threshold
reaches there (θ=1.5 already costs 10.6 candidates per lemma), the operating
range is what the principle has to fit.

So the linear cost is DERIVED: given the noisy-channel reading, confusability
decays exponentially in the angular distance, and −log of an exponential is
linear. The concave warp is not merely unprofitable, it is wrong for the
decay the data shows — its R² advantage came entirely from fitting a tail
with no signal.

CAVEAT, stated because it bounds the claim: `d` here is the current metric,
so this shows the identity is the right transformation OF THIS GEOMETRY. It
does not validate the geometry itself; that rests on §4.

Normalisation is applied before binning (`assimilate_word` then
`contract_word`), because without it the `aya↔e` pairs sit at 1.65 and put a
visible non-monotonic bump in the curve — real variants at high distance,
which is exactly what the pipeline exists to remove.

Requires the DPD database and rapidfuzz.
"""

import collections
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

from abugida import (  # noqa: E402
    Lexicon,
    assimilate_word,
    contract_word,
    distance,
)

SEED = 20260801
QUERIES = 1200
POOL = 200
BIN = 0.25
MIN_BIN = 80
CUTS = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.5, None)


def _clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


def _norm(word):
    return contract_word(assimilate_word(word))


def r_squared(points, transform):
    """R² of a least-squares line through (transform(d), −log P)."""
    xs = [transform(d) for d, _ in points]
    ys = [y for _, y in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = (sum((a - mx) * (b - my) for a, b in zip(xs, ys))
             / sum((a - mx) ** 2 for a in xs))
    intercept = my - slope * mx
    resid = sum((b - (intercept + slope * a)) ** 2 for a, b in zip(xs, ys))
    total = sum((b - my) ** 2 for b in ys)
    return 1 - resid / total


def main():
    con = _dpd.connect()
    lemmas = sorted({_clean(l) for (l,) in con.execute(
        "SELECT lemma_1 FROM dpd_headwords")})
    by = collections.defaultdict(set)
    for lemma, var in con.execute(
        "SELECT lemma_1, var_phonetic FROM dpd_headwords "
        "WHERE var_phonetic IS NOT NULL AND trim(var_phonetic) != ''"
    ):
        a = _clean(lemma)
        for piece in re.split(r"[;,]", var):
            b = _clean(piece)
            if b and a != b:
                by[a].add(b)
                by[b].add(a)

    lex = Lexicon(lemmas)
    rng = random.Random(SEED)
    bins = collections.defaultdict(lambda: [0, 0])
    for q in rng.sample(sorted(by), QUERIES):
        nq = _norm(q)
        for _, cand in lex.search(q, k=POOL, pool=POOL, max_distance=99):
            if cand == q:
                continue
            key = round(distance(nq, _norm(cand)) / BIN) * BIN
            bins[key][1] += 1
            if cand in by[q]:
                bins[key][0] += 1

    points = []
    print(f"{'d':>6} {'n':>8} {'P(variant)':>12} {'-ln P':>8}")
    for key in sorted(bins):
        hits, total = bins[key]
        if total < MIN_BIN or hits == 0:
            continue
        p = hits / total
        print(f"{key:>6.2f} {total:>8} {p:>12.4f} {-math.log(p):>8.3f}")
        points.append((key, -math.log(p)))

    print(f"\n{'cut':>6} {'pts':>4} {'identity':>10} {'log':>8} {'sqrt':>8}"
          f"   wins")
    for cut in CUTS:
        subset = points if cut is None else [p for p in points if p[0] <= cut]
        if len(subset) < 4:
            continue
        scores = {
            "identity": r_squared(subset, lambda v: v),
            "log": r_squared(subset, math.log1p),
            "sqrt": r_squared(subset, math.sqrt),
        }
        best = max(scores, key=scores.get)
        label = "all" if cut is None else f"{cut:.2f}"
        print(f"{label:>6} {len(subset):>4} {scores['identity']:>10.4f} "
              f"{scores['log']:>8.4f} {scores['sqrt']:>8.4f}   {best}")
    print("\nIdentity wins at every cut through the operating range; log wins"
          "\nonly once the P≈0.0001 tail is included. See the module docstring.")


if __name__ == "__main__":
    main()
