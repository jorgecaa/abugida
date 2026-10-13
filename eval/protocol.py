"""The evaluation protocol, as a script rather than as a habit.

WHY THIS EXISTS. Five calibration experiments (the concave warp, the L1 cost,
the residual weights, the dorsal bridge, the geminate ablation) each got
measured a slightly different way, and two of them were nearly mis-called
because of it. This module fixes one definition of "measured better" so that
the answer does not depend on who ran it.

THREE RULES, each of them learnt the hard way:

1. **Report an interval, never a point.** AUC on hard negatives and top-1
   both carry roughly ±2 points at the sample sizes available here. Gains
   smaller than that have been reported as real more than once.

2. **Compare PAIRED, not by overlapping intervals.** Two 95% intervals can
   overlap while the paired difference is decisive, because the same cases
   are scored by both metrics and the case-to-case variation cancels. This
   module reports the paired bootstrap difference and McNemar's exact test;
   the marginal intervals are shown for context only, and must NOT be used
   to decide.

3. **Never compare at equal θ across metrics.** A re-warp moves the whole
   scale, so equal thresholds cost different candidate volumes — this is the
   mistake that made the concave warp look like +3.7 points when it was
   worth nothing. Recall is therefore reported against VOLUME, and
   `iso_volume` interpolates one curve onto the other's volumes.

WHAT IS MEASURED, and why each is here rather than the obvious alternative:

- **Hard battery** — triples where Levenshtein TIES, harvested from
  `var_phonetic` pairs (`eval/hard_battery.py`), and so sharing DPD's
  population: a comparison between two versions of the metric, not a check
  of either against the language. The hand-written battery is
  saturated (29/30, 30/30 since the heavy units) and held that score even under calibrations that make
  `a↔ā` cost 0.073, so it detects regressions only. Difficulty here is
  defined without consulting the phonological metric, so the set is not
  circular.
- **AUC on hard negatives** — real `Lexicon.search` candidates that are not
  true variants. Against RANDOM negatives every candidate scores ≥0.99: that
  comparison cannot discriminate and must not be used.
- **Iso-volume recall** — recall at matched candidates-per-lemma, the only
  fair currency when the scale changes.

Requires the DPD database. `rapidfuzz` strongly recommended (it is what makes
the hard-negative pool realistic).
"""

import bisect
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

from abugida import Lexicon, distance as live_distance  # noqa: E402

SEED = 20260801
BOOTSTRAP = 2000
QUERY_WORDS = 500
POOL = 40
NEGATIVES_PER_QUERY = 20


# --- intervals -------------------------------------------------------------


def wilson(hits: int, n: int, z: float = 1.96):
    """Wilson score interval for a proportion — correct near 0 and 1, where
    the normal approximation is not."""
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def paired_bootstrap(pairs, statistic, rounds: int = BOOTSTRAP, seed: int = SEED):
    """Bootstrap CI for the DIFFERENCE of a statistic between two metrics
    scored on the SAME cases. Resampling cases (not scores) is what makes it
    paired, and it is far more powerful than comparing marginal intervals.

    `pairs` is a list of per-case records; `statistic` maps a resampled list
    to (value_a, value_b).
    """
    rng = random.Random(seed)
    n = len(pairs)
    diffs = []
    for _ in range(rounds):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        a, b = statistic(sample)
        diffs.append(b - a)
    diffs.sort()
    lo = diffs[int(0.025 * rounds)]
    hi = diffs[int(0.975 * rounds) - 1]
    return (lo, hi)


def mcnemar(a_wins: int, b_wins: int):
    """Exact two-sided McNemar p-value on the DISCORDANT cases only.

    Cases both metrics get right (or both wrong) carry no information about
    which is better; only the ones they disagree on do. Under the null,
    discordant cases split 50/50, so this is a binomial sign test.
    """
    n = a_wins + b_wins
    if n == 0:
        return 1.0
    k = min(a_wins, b_wins)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# --- reference -------------------------------------------------------------


def _clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


def load_truth(db="/dev/shm/dpd.db"):
    """(lemmas, {word: {partners}}) from `var_phonetic`, the reference for
    agreement with DPD (not a ground truth: DPD's rules compute it). See
    TODO.md for why not the `variant` field."""
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
    return sorted(lemmas), by


def hard_negative_tasks(lemmas, by, n_queries=QUERY_WORDS):
    """(query, true_variants, hard_negatives) — negatives are real search
    candidates that are not annotated variants."""
    lex = Lexicon(lemmas)
    rng = random.Random(SEED)
    tasks = []
    for w in rng.sample(sorted(by), min(n_queries, len(by))):
        cands = [c for _, c in lex.search(w, k=POOL, pool=POOL,
                                          max_distance=99)]
        pos = [c for c in cands if c in by[w]]
        neg = [c for c in cands if c not in by[w] and c != w]
        if pos and neg:
            tasks.append((w, pos, neg[:NEGATIVES_PER_QUERY]))
    return tasks


# --- the measurements ------------------------------------------------------


def _auc_and_top1(tasks, d):
    rows = []
    for w, pos, neg in tasks:
        dp = [d(w, p) for p in pos]
        dn = sorted(d(w, x) for x in neg)
        wins = 0.0
        for p in dp:
            lo = bisect.bisect_left(dn, p)
            hi = bisect.bisect_right(dn, p)
            wins += (len(dn) - hi) + 0.5 * (hi - lo)
        rows.append((wins, len(dp) * len(dn), min(dp) < dn[0]))
    return rows


def evaluate(d, tasks, label="metric"):
    """AUC and top-1 with intervals. Marginal intervals are CONTEXT — use
    `compare` to decide between two metrics."""
    rows = _auc_and_top1(tasks, d)
    auc = sum(r[0] for r in rows) / sum(r[1] for r in rows)
    top = sum(1 for r in rows if r[2])
    lo, hi = wilson(top, len(rows))
    print(f"{label:<22} AUC {auc:.4f}   "
          f"top-1 {100 * top / len(rows):.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"
          f"   n={len(rows)}")
    return rows


def compare(d_a, d_b, tasks, label_a="A", label_b="B"):
    """The paired comparison. This is what decides."""
    ra = _auc_and_top1(tasks, d_a)
    rb = _auc_and_top1(tasks, d_b)

    def stat(sample):
        a = sum(x[0][0] for x in sample) / sum(x[0][1] for x in sample)
        b = sum(x[1][0] for x in sample) / sum(x[1][1] for x in sample)
        return a, b

    lo, hi = paired_bootstrap(list(zip(ra, rb)), stat)
    only_a = sum(1 for x, y in zip(ra, rb) if x[2] and not y[2])
    only_b = sum(1 for x, y in zip(ra, rb) if y[2] and not x[2])
    p = mcnemar(only_a, only_b)
    print(f"\npaired: {label_b} − {label_a}")
    print(f"  ΔAUC  {(hi + lo) / 2:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]"
          f"   {'DECISIVE' if lo > 0 or hi < 0 else 'not distinguishable'}")
    print(f"  top-1 discordant: {label_a} only {only_a}, {label_b} only "
          f"{only_b}   McNemar p={p:.3f}"
          f"   {'DECISIVE' if p < 0.05 else 'not distinguishable'}")
    return (lo, hi), p


if __name__ == "__main__":
    lemmas, by = load_truth()
    print(f"lexicon {len(lemmas)}   words with variants {len(by)}")
    tasks = hard_negative_tasks(lemmas, by)
    print(f"query words with both a true variant and hard negatives: "
          f"{len(tasks)}\n")
    evaluate(live_distance, tasks, "live metric")
    print("\nTo compare a candidate:  compare(live_distance, candidate, tasks)")


def iso_volume(d_a, d_b, lemmas, sample_size=400, thetas=None):
    """Recall at MATCHED candidate volume — the only fair currency when a
    change moves the whole scale.

    Comparing at equal θ across two metrics is the mistake that made the
    concave warp look like +3.7 recall points when, at equal cost, it was
    worth nothing. This sweeps each metric's own thresholds, records
    (candidates per lemma, recall) for both, and interpolates B onto A's
    volumes so the two columns are directly comparable.
    """
    if thetas is None:
        thetas = [0.1 * i for i in range(1, 21)]
    lemmas, by = lemmas
    rng = random.Random(SEED)
    lex = Lexicon(lemmas)
    sample = rng.sample(lemmas, sample_size)
    truth = sorted({tuple(sorted((a, b))) for a in by for b in by[a]})

    def curve(d):
        vol = sorted(
            d(w, c)
            for w in sample
            for _, c in lex.search(w, k=200, pool=200, max_distance=99)
            if c != w
        )
        gold = sorted(d(a, b) for a, b in truth)
        return [
            (bisect.bisect_right(vol, t) / sample_size,
             bisect.bisect_right(gold, t) / len(gold))
            for t in thetas
        ]

    ca, cb = curve(d_a), curve(d_b)
    vb = [v for v, _ in cb]
    rb = [r for _, r in cb]
    print(f"\n{'cand/lemma':>11} {'recall A':>9} {'recall B':>9} {'Δ':>7}")
    for v, r in ca:
        if v <= 0 or v > vb[-1]:
            continue
        i = bisect.bisect_left(vb, v)
        if i == 0 or i >= len(vb):
            continue
        f = (v - vb[i - 1]) / (vb[i] - vb[i - 1]) if vb[i] != vb[i - 1] else 0
        interp = rb[i - 1] + f * (rb[i] - rb[i - 1])
        print(f"{v:>11.2f} {100 * r:>8.1f}% {100 * interp:>8.1f}% "
              f"{100 * (interp - r):>+6.1f}")
