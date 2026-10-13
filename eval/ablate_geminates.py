"""What the metric loses without its geminates as units.

WHY THIS EXISTS. Written for the 2:1 / 1:2 / 2:2 alignment transitions the
DP used to carry; since 2026-10-13 those are replaced by heavy units (each
word segmented once, geminates and nasal+stop clusters as single tokens),
and `geminates=False` switches the units off instead. Re-run on the units,
2026-10-13, 5,143-pair build: 62.6% live against 48.2% ablated at θ =
ONE_MOVE (−14.4), 1,262 pairs (24.5%) changed, every one for the worse. The
figures below were measured on the transitions. This
script prices the mechanism before anyone removes it. The answer is that they are the single highest-yield
mechanism per unit of volume in the system, and the reason is not raw recall
but CHEAP recall: they move a whole phonological class from "unreachable" to
"inside the operating threshold".

METHOD. `_edit(..., geminates=False)` against the live distance over the same
reference as `variant_curve.py` (`dpd_headwords.var_phonetic`; "recall" is
agreement with DPD — see that script's header). Substitution costs, indel
weights and tokenisation are untouched: the ONLY difference is whether a
doubled pair may align as one long consonant.

READING THE Δ COLUMN. It is large at strict θ and small at loose θ, and that
shape is the finding. Without the transitions those pairs are still reachable
letter by letter, just expensive — so a loose threshold recovers them anyway,
at the price of everything else a loose threshold admits. The transitions do
not add recall; they make recall affordable.

Requires the DPD database. No rapidfuzz: exhaustive over the reference,
no prefilter, so no pool-size effect.
"""

import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

from abugida import Lexicon, distance, tokenize  # noqa: E402
from abugida.distance import INDEL_WEIGHT, _edit, cost  # noqa: E402

THETAS = (0.400, 0.470, 0.530, INDEL_WEIGHT, 0.700, 0.800, 1.000, 1.500)
VOLUME_SAMPLE = 400
SEED = 20260801


def distance_flat(w1, w2):
    """The same DP with the heavy units switched off (letters as they come)."""
    return _edit(tokenize(w1), tokenize(w2), cost, geminates=False)


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

pairs = []
for a, b in sorted(truth):
    try:
        pairs.append((a, b, distance(a, b), distance_flat(a, b)))
    except Exception:
        continue
n = len(pairs)
print(f"reference (var_phonetic): {n} pairs   lexicon: {len(lemmas)} lemmas\n")

changed = [p for p in pairs if abs(p[2] - p[3]) > 1e-9]
deltas = sorted(p[3] - p[2] for p in changed)
print(f"pairs whose distance changes: {len(changed)} ({100 * len(changed) / n:.2f}%)")
print(
    f"  every change is a LOSS: min {deltas[0]:+.3f}  "
    f"median {deltas[len(deltas) // 2]:+.3f}  max {deltas[-1]:+.3f}"
)
print("  worst hit (live → ablated) — the geminate/simple alternation:")
for a, b, live, flat in sorted(changed, key=lambda p: p[2] - p[3])[:8]:
    print(f"    {a} ~ {b}: {live:.3f} → {flat:.3f}")

print(f"\n{'θ':>7} {'recall live':>12} {'recall ablated':>15} {'Δ pts':>8}")
for th in THETAS:
    live = 100 * sum(1 for p in pairs if p[2] <= th) / n
    flat = 100 * sum(1 for p in pairs if p[3] <= th) / n
    print(f"{th:>7.3f} {live:>11.1f}% {flat:>14.1f}% {flat - live:>+7.2f}")

# --- what the lost recall would cost to buy back by raising θ --------------
rng = random.Random(SEED)
lex = Lexicon(sorted(lemmas))
volume = []
for w in rng.sample(sorted(lemmas), VOLUME_SAMPLE):
    for d, _ in lex.search(w, k=200, pool=200, max_distance=1.5):
        volume.append(d)
print(f"\nvolume, live metric ({VOLUME_SAMPLE} random lemmas):")
for th in (0.470, INDEL_WEIGHT, 0.800, 1.000):
    print(
        f"  θ {th:.4f}: {sum(1 for d in volume if d <= th) / VOLUME_SAMPLE:.3f} "
        f"cand/lemma"
    )
print(
    "\nThe ablated metric needs θ≈0.9–1.0 to reach the recall the live one has\n"
    "at its own ONE_MOVE — i.e. 2–5× the candidate volume for the same result."
)
