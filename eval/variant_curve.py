"""Volume-agreement curve for variant generation, against DPD's var_phonetic.

The threshold θ in `Lexicon.variants` trades coverage for volume, and
picking it requires knowing both curves. This script builds them against
DPD's `var_phonetic`.

REFERENCE, NOT GROUND TRUTH. `dpd_headwords.var_phonetic` is computed by
DPD's own phonetic rules, not curated from the texts, so what this script
calls "recall" is AGREEMENT WITH DPD: how much of what those rules list the
metric also finds (README, "Agreement with DPD is not accuracy"). Every
published figure from it is reported under that name, with its build (5,002
pairs, August 2026; a 2026-10 build has 5,143; this header once counted
5,018, from an earlier build). Its pairs are PHONETIC variation (akaṭa ~
akata, akatūpāsana ~ akatupāsana, a ~ ā), mean length difference 0.57. NOT
the `variant` field, which mixes phonetic
variation with part-whole relations (sumanā ~ vuḍḍhapabbajitasumanā),
compound permutation (sampannavijjācaraṇa ~ vijjācaraṇasampanna), whole
phrases, and outright synonyms (karitvā ~ vihacca) — measuring a
phonological metric against that population understates it and sets targets
no edit distance should hit.

TWO RECALLS, kept apart, because they answer different questions:

  metric  — the pair is within θ. The ceiling: what the distance can reach.
  pipeline — the pair actually comes back from `Lexicon.search` at that
             pool size. What you would really get, prefilter included.

Their gap is what the rapidfuzz prefilter drops.

A related trap, and the likelier explanation for the long-standing puzzle of
why a sweep AT the operating point and a loose sweep FILTERED DOWN to it
disagree (TODO.md): ONE_MOVE is 0.62707…, and a large share of true pairs
sit at exactly one epenthetic indel. Compare against the rounded 0.627 and
every one of them falls outside — 59.9% instead of 63.6%. THETAS therefore
carries the constant itself, never a literal.

PRECISION is a LOWER BOUND and is labelled as such wherever it is printed:
var_phonetic annotates 5,018 pairs, real variation is broader, so a
candidate absent from it is not thereby a false positive.
Recall and volume are the trustworthy columns.

VOLUME is measured on a random sample of lemmas and reported per consulted
lemma; the total for a full sweep halves it, since a full sweep discovers
each unordered pair from both sides while a random sample essentially never
draws both endpoints.

Requires the DPD database; rapidfuzz strongly recommended (without it the
pool is a length window and the pipeline column measures something else).
"""

import os
import random
import re
import sys
from bisect import bisect_right

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402
from abugida import Lexicon, distance  # noqa: E402
from abugida.lexicon import ONE_MOVE, _HAVE_RAPIDFUZZ  # noqa: E402

#: ONE_MOVE enters as the CONSTANT, never as its rounded label. A large share
#: of true pairs sit at exactly one epenthetic indel, so sweeping 0.627 —
#: which is below the actual 0.62707 — silently drops all of them and
#: understates the operating point by 3.7 points.
THETAS = (0.333, 0.400, 0.470, 0.530, ONE_MOVE, 0.700, 0.800, 0.900,
          1.000, 1.150, 1.300, 1.500, 1.750, 2.000)
POOLS = (50, 200)
VOLUME_SAMPLE = 600
SEED = 20260801

con = _dpd.connect()


def clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


lemmas = {clean(l) for (l,) in con.execute("SELECT lemma_1 FROM dpd_headwords")}

truth = set()
for lemma, var in con.execute(
    "SELECT lemma_1, var_phonetic FROM dpd_headwords "
    "WHERE var_phonetic IS NOT NULL AND trim(var_phonetic) != ''"
):
    a = clean(lemma)
    for piece in re.split(r"[;,]", var):
        b = clean(piece)
        if b and a != b and a in lemmas and b in lemmas:
            truth.add(tuple(sorted((a, b))))

print(f"reference: {len(truth)} pairs from DPD's var_phonetic (both sides "
      f"real lemmas; computed by DPD's rules: recall here = agreement)")
print(f"lexicon: {len(lemmas)} lemmas   rapidfuzz: {_HAVE_RAPIDFUZZ}")

lex = Lexicon(sorted(lemmas))
gold = sorted(distance(a, b) for a, b in truth)
n_gold = len(gold)
median = gold[n_gold // 2]
print(f"median distance of a real phonetic variant: {median:.3f}\n")

# --- pipeline recall: does search actually return the pair? ----------------
by_left = {}
for a, b in truth:
    by_left.setdefault(a, set()).add(b)
    by_left.setdefault(b, set()).add(a)

theta_max = max(THETAS)
found = {pool: [] for pool in POOLS}
for pool in POOLS:
    for w, partners in by_left.items():
        hits = {c: d for d, c in lex.search(w, k=pool, pool=pool,
                                            max_distance=theta_max)}
        for p in partners:
            found[pool].append(hits.get(p))  # None = prefilter dropped it

# --- volume and lower-bound precision --------------------------------------
rng = random.Random(SEED)
sample = rng.sample(sorted(lemmas), VOLUME_SAMPLE)
volume = []
for w in sample:
    for d, c in lex.search(w, k=200, pool=200, max_distance=theta_max):
        volume.append(d)
volume.sort()

prec_rows = []
for w, partners in by_left.items():
    for d, c in lex.search(w, k=200, pool=200, max_distance=theta_max):
        prec_rows.append((d, c in partners))
prec_rows.sort()
prec_d = [d for d, _ in prec_rows]
prec_hit = []
running = 0
for _, hit in prec_rows:
    running += hit
    prec_hit.append(running)

print(f"{'θ':>6} {'recall':>8} {'pipe@50':>8} {'pipe@200':>9} "
      f"{'cand/lemma':>11} {'pairs (75k sweep)':>18} {'prec≥':>7} "
      f"{'cost/new pair':>14}")
print("-" * 92)
prev_v = prev_r = 0.0
for th in THETAS:
    recall = bisect_right(gold, th) / n_gold
    pipe = {}
    for pool in POOLS:
        ok = sum(1 for d in found[pool] if d is not None and d <= th + 1e-9)
        pipe[pool] = ok / len(found[pool])
    v = bisect_right(volume, th) / VOLUME_SAMPLE
    total = v * len(lemmas) / 2
    k = bisect_right(prec_d, th)
    precision = (prec_hit[k - 1] / k) if k else 0.0
    marginal = ((v - prev_v) * len(lemmas) / 2 / ((recall - prev_r) * n_gold)
                if recall > prev_r else float("inf"))
    print(f"{th:6.3f} {recall:8.1%} {pipe[50]:8.1%} {pipe[200]:9.1%} "
          f"{v:11.2f} {total:18,.0f} {precision:7.1%} "
          f"{marginal:14,.0f}")
    prev_v, prev_r = v, recall

print("\nrecall   = pair within θ (what the metric can reach)")
print("pipe@N   = pair actually returned by search with pool=N (what you get)")
print("prec≥    = LOWER BOUND: the reference is partial, unannotated "
      "candidates are not thereby wrong")
print("cost/new pair = extra candidates per additional true pair recovered")
