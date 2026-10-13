"""Which place confusions transmission actually attests, and what the karaṇa
bridges buy.

THE QUESTION. The embedding gives two places a shared half-column when the
tradition assigns them a common karaṇa (active organ): cerebral+dental share
the tongue tip (dim 12), guttural+palatal the tongue body (dim 13). Both are
principled — the same √½/√½ ṭhāna/karaṇa split, no free parameter — but a
principle that no manuscript ever exercises would be decoration. This script
asks DPD's `var_phonetic` which place pairs are really confused, and then ablates
each bridge to price it.

REFERENCE. `dpd_headwords.var_phonetic`, the same population
`variant_curve.py` uses — DPD's rules compute it, so the counts below
describe what DPD lists, and "recall" is agreement with DPD — and and for the same reason (see that script's header,
and TODO.md: the `variant` field mixes in part-whole relations, compound
permutation and synonyms, and understates a phonological metric by ~35
points).

METHOD. For each true pair, take the optimal `alignment` and count the
substitutions between SIMPLE consonants — one place on each side, neither
syllabic — whose places differ. That isolates place confusion from the
vowel, length and modifier axes, which have their own costs. The count is
over alignment operations, not over pairs: a pair may contribute more than
one place substitution, and pairs contributing none are simply silent.

CIRCULARITY, and how it is broken. The alignment that harvests the counts is
computed with the bridges IN PLACE, so a cheap bridged substitution is
likelier to be chosen over an indel than it would be without them — the
count cannot be used, on its own, to justify the bridges. (`--ablate` does
NOT fix this: it re-prices the recall table but `alignment` still uses the
live metric, so the count is identical under every ablation.)

The check that does break the circle is the second table: for the true pairs
of EQUAL token length, compare position by position. That alignment is
forced by the lengths alone and consults no cost at all, so the ranking it
produces is metric-independent evidence. If the tip and the body did not
come out first and second there too, the bridges would be an artefact.

Requires the DPD database. No rapidfuzz: everything here is exhaustive over
the reference, with no prefilter and so no pool-size effect.
"""

import argparse
import collections
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

from abugida import INVENTORY, alignment, distance, phoneme, tokenize  # noqa: E402
from abugida.embed import (  # noqa: E402
    CORONAL,
    DORSAL,
    MODIFIER,
    embed,
)
from abugida.distance import (  # noqa: E402
    EPENTHETIC,
    INDEL_WEIGHT,
    _GEMINATE_BASES,
    _edit,
)
from abugida.embed import LENGTH as LENGTH_DIM  # noqa: E402
from abugida.phonology import FOREIGN, PLACES  # noqa: E402

#: ONE_MOVE enters UNROUNDED and deliberately. A large share of true pairs sit
#: at exactly one epenthetic indel, so sweeping a θ printed as 0.627 — which
#: is below the constant's actual 0.62707 — drops all of them and reports
#: 59.9% where the operating point really yields 63.6%. Any curve quoting the
#: operating point must sweep the constant, not its label.
THETAS = (0.400, 0.470, 0.530, INDEL_WEIGHT, 0.700, 0.800, 1.000, 1.500)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--ablate",
    choices=("none", "coronal", "dorsal", "both"),
    default="none",
    help="zero out one or both karaṇa columns before measuring",
)
args = parser.parse_args()

# --- the ablated metric ----------------------------------------------------
# Zeroing a karaṇa column and renormalising the ṭhāna half back to 1.0 is
# exactly the pre-bridge embedding: the place recovers its whole identity in
# its own column, which is what "no bridge" means.

_ABLATED = {
    "none": (),
    "coronal": (CORONAL,),
    "dorsal": (DORSAL,),
    "both": (CORONAL, DORSAL),
}[args.ablate]


def _vector(g):
    base = _GEMINATE_BASES.get(g)
    grapheme = base if base is not None else g
    p = next((q for q in INVENTORY if q.grapheme == grapheme), None) or FOREIGN.get(
        grapheme
    )
    if p is None:
        return None
    v = list(embed(p))
    for column in _ABLATED:
        if v[column]:
            v[column] = 0.0
            for i, x in enumerate(v[0:5]):  # restore the ṭhāna to full mass
                if x:
                    v[i] = 1.0
    if base is not None:
        v[LENGTH_DIM] = 1.0
    return v


def _rho():
    """ρ* re-derived on whatever layout the ablation leaves (SPEC §4)."""
    k, kh, g = _vector("k"), _vector("kh"), _vector("g")
    lo, hi = 1e-6, 1.0
    for _ in range(60):
        r = (lo + hi) / 2
        if _cos(k, kh, r) > _cos(k, g, r):
            lo = r
        else:
            hi = r
    return (lo + hi) / 2


def _cos(u, w, rho):
    u, w = list(u), list(w)
    u[MODIFIER] = [a * rho for a in u[MODIFIER]]
    w[MODIFIER] = [a * rho for a in w[MODIFIER]]
    dot = sum(a * b for a, b in zip(u, w))
    nu = math.sqrt(sum(a * a for a in u))
    nw = math.sqrt(sum(b * b for b in w))
    return 0.0 if nu == 0 or nw == 0 else dot / (nu * nw)


RHO = _rho()
_cost_cache = {}


def cost_a(g1, g2):
    if g1 == g2:
        return 0.0
    hit = _cost_cache.get((g1, g2))
    if hit is not None:
        return hit
    v1, v2 = _vector(g1), _vector(g2)
    if v1 is None or v2 is None:
        r = 1.0
    else:
        c = _cos(v1, v2, RHO)
        r = min(1.0, math.acos(max(-1.0, min(1.0, c))) / (math.pi / 2))
    _cost_cache[(g1, g2)] = r
    return r


def _derived_indel():
    """The extremal epenthetic weight for THIS layout (SPEC §9.3)."""
    letters = [p.grapheme for p in INVENTORY] + sorted(FOREIGN)
    inside = [g for g in letters if g in EPENTHETIC]
    outside = [g for g in letters if g not in EPENTHETIC]
    return max(
        1.0 - min(cost_a(g, c) for g in inside for c in outside),
        max(cost_a(a, b) for a in inside for b in inside) / 2.0,
    )


INDEL_A = _derived_indel()


def indel_a(g):
    return INDEL_A if _GEMINATE_BASES.get(g, g) in EPENTHETIC else 1.0


def distance_a(w1, w2):
    return _edit(tokenize(w1), tokenize(w2), cost_a, indel=indel_a)


# --- reference -------------------------------------------------------------

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

print(f"ablation: {args.ablate}   ρ* = {RHO:.4f}   indel = {INDEL_A:.4f}")
print(f"reference: {len(truth)} pairs from DPD's var_phonetic\n")

# --- which place pairs are confused ---------------------------------------

BRIDGED = {
    frozenset({"cerebral", "dental"}): "tip",
    frozenset({"guttural", "palatal"}): "body",
}

order = {p: i for i, p in enumerate(PLACES)}


def _place_pair(x, y):
    """The unordered place pair of a substitution between simple consonants,
    or None if either side is a vowel, is multi-place, or shares the place."""
    try:
        px, py = phoneme(x), phoneme(y)
    except Exception:
        return None
    if px.syllabic or py.syllabic:
        return None
    if len(px.places) != 1 or len(py.places) != 1 or px.places == py.places:
        return None
    return frozenset(px.places | py.places)


def report(counts, title):
    total = sum(counts.values())
    print(f"\n{title}: {total}")
    print(f"{'pair':<24} {'n':>5} {'share':>7}  {'organ':>6}  {'tract gap':>9}")
    bridged = 0
    for pair, n in counts.most_common():
        p1, p2 = sorted(pair, key=lambda p: order[p])
        organ = BRIDGED.get(pair, "—")
        if organ != "—":
            bridged += n
        print(
            f"{p1 + ' ~ ' + p2:<24} {n:>5} {100 * n / total:>6.1f}%  {organ:>6}  "
            f"{abs(order[p1] - order[p2]):>9}"
        )
    print(
        f"shared organ: {bridged} ({100 * bridged / total:.1f}%)   "
        f"no shared organ: {total - bridged} "
        f"({100 * (total - bridged) / total:.1f}%)"
    )


# (a) from the optimal alignment — richer, but computed with the live metric
counts = collections.Counter()
for a, b in sorted(truth):
    try:
        ops = alignment(a, b)
    except Exception:
        continue
    for op, x, y, _ in ops:
        if op == "sub" and x and y and (pair := _place_pair(x, y)):
            counts[pair] += 1
report(counts, "place substitutions between simple consonants (via alignment)")

# (b) metric-independent: equal-length pairs, compared position by position.
# No cost function is consulted, so this cannot be biased by the bridges.
positional = collections.Counter()
n_equal = 0
for a, b in sorted(truth):
    try:
        t1, t2 = tokenize(a), tokenize(b)
    except Exception:
        continue
    if len(t1) != len(t2):
        continue
    n_equal += 1
    for x, y in zip(t1, t2):
        if x != y and (pair := _place_pair(x, y)):
            positional[pair] += 1
report(
    positional,
    f"the same, positionally, over the {n_equal} equal-length pairs "
    f"(metric-independent)",
)

# --- what the ablation costs ----------------------------------------------

rows = []
for a, b in sorted(truth):
    try:
        rows.append((distance(a, b), distance_a(a, b)))
    except Exception:
        continue
n = len(rows)
if args.ablate != "none":
    changed = sum(1 for live, abl in rows if abs(live - abl) > 1e-9)
    print(f"\npairs whose distance changes: {changed} ({100 * changed / n:.2f}%)")
print(f"\n{'θ':>7} {'recall live':>12} {'recall ablated':>15} {'Δ pts':>8}")
for th in THETAS:
    live = 100 * sum(1 for d, _ in rows if d <= th) / n
    abl = 100 * sum(1 for _, d in rows if d <= th) / n
    print(f"{th:>7.3f} {live:>11.1f}% {abl:>14.1f}% {abl - live:>+7.2f}")

# Comparing at a FIXED θ is unfair once an ablation moves the derived indel
# weight: the cheaper indel of the ablated layout flatters it at any θ above
# its own ONE_MOVE. The honest comparison is each layout at its own operating
# point, which is what a deployment would actually use.
if args.ablate != "none":
    from abugida.distance import INDEL_WEIGHT as LIVE_INDEL

    live_op = 100 * sum(1 for d, _ in rows if d <= LIVE_INDEL) / n
    abl_op = 100 * sum(1 for _, d in rows if d <= INDEL_A) / n
    print(
        f"\nat each layout's own ONE_MOVE:  "
        f"live θ={LIVE_INDEL:.4f} → {live_op:.1f}%   "
        f"ablated θ={INDEL_A:.4f} → {abl_op:.1f}%   "
        f"Δ {abl_op - live_op:+.2f} pts"
    )
