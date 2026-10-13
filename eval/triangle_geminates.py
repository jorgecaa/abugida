"""Why the word-level triangle inequality fails, and what each repair costs.

TODO.md ("Open: the triangle inequality across the geminate transitions")
asked which operation makes it fail and whether a narrower repair exists.
This script answers both on the same triples, built from the Pāli forms of
the grammar case files (Oberlies, Geiger; local data, `eval/_data.py`): each of 400 sampled words as the
middle word, with its twelve nearest as the ends.

1. The live metric, and the cause of every violation: the DP decides PER PAIR
   whether a geminate is one long consonant (2:1, 2:2) or two letters (1:1).
   A middle word whose geminate is a unit in one leg and split in the other
   breaks path composition, because a unit change (kk~gg 0.377) is cheaper
   than changing the two halves (k~g 0.470 each).
2. Raising the unit costs to what the triangle demands: every geminate pair
   would need up to 2.0, i.e. the price of two separate substitutions —
   the same as removing the transitions.
3. Closing the transitions under composition (a geminate against any two
   tokens, a whole-geminate deletion): fewer violations, not none, because a
   geminate can be split ACROSS other material (kathita -> katta: th, i
   deleted, t) and no transition of bounded size covers that.
4. One segmentation per word — every geminate always one long token, plain
   edit distance over it, the long token's indel derived as the cheapest
   route through a single token. A metric by the classical theorem; the
   price is geminate-vs-cluster pairs (citta ~ cinta 0.63 -> 1.47).
5. Halves: geminates AND homorganic nasal+stop clusters as one token each,
   a token being (first half, second half, weight) and a cost the max of
   the three. Still a metric by theorem; keeps citta ~ cinta at 0.63 and
   the whole battery. Its price: a one-letter change that breaks a unit
   (a half-geminate, tṭ) costs a broken unit. On variants that are possible
   Pāli it matches the live metric; on the open-vocabulary generator's
   impossible ones it loses.

Needs no DPD.
"""

import functools
import itertools
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from abugida import distance as live_distance, is_possible  # noqa: E402
from abugida._pure import _GEMINATE_BASES, _indel, cost  # noqa: E402
from abugida.alphabet import ALPHABET  # noqa: E402
from abugida.iast import tokenize  # noqa: E402

import _data  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20260801

# --- 3. closure ----------------------------------------------------------
BASES = sorted(set(_GEMINATE_BASES.values()))
UNITS = {b: [g for g, v in _GEMINATE_BASES.items() if v == b] for b in BASES}
@functools.lru_cache(None)
def split(g, c, d):
    """geminate token g against two tokens c d: the cheapest route through any
    middle geminate BB (unit to unit, then split), or splitting g itself."""
    base = _GEMINATE_BASES[g]
    best = cost(g[:len(g) - len(base)], c) + cost(base, d)
    for b in BASES:
        for bb in UNITS[b]:
            first = bb[:len(bb) - len(b)]
            best = min(best, cost(g, bb) + cost(first, c) + cost(b, d))
    return best
@functools.lru_cache(None)
def gdel(g):
    """delete a whole geminate: through any single token it degeminates to."""
    best = _indel(g[:len(g)-len(_GEMINATE_BASES[g])]) + _indel(_GEMINATE_BASES[g])
    for b in BASES:
        best = min(best, cost(g, b) + _indel(b))
    return best
def closure_edit(t1, t2):
    n, m = len(t1), len(t2)
    gem = lambda t, i: (t[i-2] + t[i-1]) if i >= 2 and (t[i-2] + t[i-1]) in _GEMINATE_BASES else None
    INF = float('inf')
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if i == j == 0: continue
            b = INF
            if i: b = min(b, D[i-1][j] + _indel(t1[i-1]))
            if j: b = min(b, D[i][j-1] + _indel(t2[j-1]))
            if i and j: b = min(b, D[i-1][j-1] + cost(t1[i-1], t2[j-1]))
            g1, g2 = gem(t1, i), gem(t2, j)
            if g1 and j: b = min(b, D[i-2][j-1] + cost(g1, t2[j-1]))
            if g2 and i: b = min(b, D[i-1][j-2] + cost(t1[i-1], g2))
            if g1 and g2: b = min(b, D[i-2][j-2] + cost(g1, g2))
            # closure: geminate against two arbitrary tokens, and whole-geminate indels
            if g1 and j >= 2: b = min(b, D[i-2][j-2] + split(g1, t2[j-2], t2[j-1]))
            if g2 and i >= 2: b = min(b, D[i-2][j-2] + split(g2, t1[i-2], t1[i-1]))
            if g1: b = min(b, D[i-2][j] + gdel(g1))
            if g2: b = min(b, D[i][j-2] + gdel(g2))
            D[i][j] = b
    return D[n][m]
def closure_distance(a, b):
    return closure_edit(tokenize(a), tokenize(b))

# --- 4. one segmentation per word -----------------------------------------
SINGLES = [p.grapheme for p in ALPHABET]
def segment(t):
    out, i = [], 0
    while i < len(t):
        if i + 1 < len(t) and t[i] + t[i+1] in _GEMINATE_BASES:
            out.append(t[i] + t[i+1]); i += 2
        else:
            out.append(t[i]); i += 1
    return out
@functools.lru_cache(None)
def unit_indel(g):
    """Deleting a long consonant: the cheapest route through a single token
    (degeminate, then delete) — the extremal value the triangle allows from above."""
    if g not in _GEMINATE_BASES: return _indel(g)
    return min(cost(g, x) + _indel(x) for x in SINGLES)
def unit_edit(a, b):
    n, m = len(a), len(b)
    prev = [0.0] * (m + 1)
    for j in range(1, m + 1): prev[j] = prev[j-1] + unit_indel(b[j-1])
    for i in range(1, n + 1):
        cur = [prev[0] + unit_indel(a[i-1])] + [0.0] * m
        for j in range(1, m + 1):
            cur[j] = min(prev[j] + unit_indel(a[i-1]), cur[j-1] + unit_indel(b[j-1]),
                         prev[j-1] + cost(a[i-1], b[j-1]))
        prev = cur
    return prev[m]
def unit_distance(w1, w2, lenient=False):
    return unit_edit(segment(tokenize(w1, lenient=lenient)), segment(tokenize(w2, lenient=lenient)))
# --- 5. halves: geminates and homorganic nasal+stop clusters as units ----
# Every token is (first half, second half, weight): a single consonant X is
# (X, X, light), a geminate tt (t, t, heavy), tth (t, th, heavy), a homorganic
# nasal+stop cluster nt (n, t, heavy). Cost = the max of the three coordinate
# costs (the sup of metrics on a product is a metric); the weight coordinate
# costs ELL = cost("tt", "t"), the price the live geometry already gives
# consonant length. One segmentation per word, so a metric by theorem — and
# tt~dd = t~d (a geminate counts once), tt~nt = t~n (one half differs),
# nt~nd = t~d (a change inside a cluster at full price), singles untouched.
from abugida.phonology import BY_GRAPHEME  # noqa: E402

base_cost = cost

HALF_SINGLES = [p.grapheme for p in ALPHABET]
NASALS = {"ṅ", "ñ", "ṇ", "n", "m"}
STOPS = {g for g, p in BY_GRAPHEME.items() if p.value is not None and g not in NASALS
         and not p.syllabic and not p.continuant and g not in ('y','r','l','ḷ','v','s','h','ṃ')}
CLUSTERS = {n + s: (n, s) for n in NASALS for s in STOPS
            if BY_GRAPHEME[n].places & BY_GRAPHEME[s].places}
ELL = base_cost("tt", "t")
def halves(g):
    if g in CLUSTERS: return CLUSTERS[g] + (1,)
    if g in _GEMINATE_BASES:
        base = _GEMINATE_BASES[g]
        return (g[:len(g) - len(base)], base, 1)
    return (g, g, 0)
@functools.lru_cache(None)
def half_cost(g1, g2):
    if g1 == g2: return 0.0
    a, b = halves(g1), halves(g2)
    return max(base_cost(a[0], b[0]), base_cost(a[1], b[1]), ELL * abs(a[2] - b[2]))
def half_segment(t):
    out, i = [], 0
    while i < len(t):
        pair = t[i] + t[i+1] if i + 1 < len(t) else None
        if pair and (pair in _GEMINATE_BASES or pair in CLUSTERS):
            out.append(pair); i += 2
        else:
            out.append(t[i]); i += 1
    return out
@functools.lru_cache(None)
def half_indel(g):
    if halves(g)[2] == 0: return _indel(g)
    return min(half_cost(g, x) + _indel(x) for x in HALF_SINGLES)
def half_edit(a, b):
    n, m = len(a), len(b)
    prev = [0.0] * (m + 1)
    for j in range(1, m + 1): prev[j] = prev[j-1] + half_indel(b[j-1])
    for i in range(1, n + 1):
        cur = [prev[0] + half_indel(a[i-1])] + [0.0] * m
        for j in range(1, m + 1):
            cur[j] = min(prev[j] + half_indel(a[i-1]), cur[j-1] + half_indel(b[j-1]),
                         prev[j-1] + half_cost(a[i-1], b[j-1]))
        prev = cur
    return prev[m]
def half_distance(w1, w2, lenient=False):
    return half_edit(half_segment(tokenize(w1, lenient=lenient)),
                     half_segment(tokenize(w2, lenient=lenient)))

# --- the measurement ------------------------------------------------------

def triples():
    words = set()
    for name in ("oberlies_cases.json", "geiger_cases.json"):
        cases = _data.load(name)
        for kind in ("tadbhava", "doublets"):
            for a, b in cases[kind]:
                words |= {a, b}
    words = sorted(w for w in words if is_possible(w) and len(w) <= 9)
    sample = random.Random(SEED).sample(words, min(400, len(words)))
    for y in sample:
        near = sorted(sample, key=lambda w: live_distance(y, w))[1:13]
        for x, z in itertools.combinations(near, 2):
            yield x, y, z


def violations(dist, trip):
    memo = {}

    def d(a, b):
        key = (a, b) if a < b else (b, a)
        if key not in memo:
            memo[key] = dist(a, b)
        return memo[key]

    return [(x, y, z) for x, y, z in trip
            if d(x, z) > d(x, y) + d(y, z) + 1e-9]


def unit_cost_bound():
    """2.: the least 2:2 cost the triangle allows, x=AA, y=BB, z=CD."""
    singles = [p.grapheme for p in ALPHABET]
    rises, top = 0, 0.0
    pairs = [(a, b) for a in BASES for b in BASES
             if a != b and a + a in _GEMINATE_BASES and b + b in _GEMINATE_BASES]
    for a, b in pairs:
        need = max(min(cost(a, c) + cost(a, d), cost(a + a, c) + _indel(d),
                       _indel(c) + cost(a + a, d)) - cost(b, c) - cost(b, d)
                   for c in singles for d in singles)
        rises += need > cost(a + a, b + b) + 1e-9
        top = max(top, need)
    return rises, len(pairs), top


def main():
    _data.require("oberlies_cases.json", "geiger_cases.json")
    trip = list(triples())
    print(f"{len(trip)} triples from the grammar case files\n")
    print("1. live metric:              ", len(violations(live_distance, trip)),
          "violations")
    rises, total, top = unit_cost_bound()
    print(f"2. raising the unit costs:    {rises} of {total} geminate pairs "
          f"would have to rise, up to {top:.3f}")
    print("3. closure under composition:",
          len(violations(closure_distance, trip)), "violations")
    print("4. one segmentation per word:",
          len(violations(unit_distance, trip)), "violations")
    print("5. halves:                   ",
          len(violations(half_distance, trip)), "violations\n")
    sys.path.insert(0, os.path.join(HERE, "..", "tests"))
    import test_battery as tb
    battery = [v for v in vars(tb).values() if isinstance(v, list) and v
               and isinstance(v[0], tuple) and len(v[0]) == 5][0]
    systems = (("live", live_distance),
               ("one segmentation", lambda a, b: unit_distance(a, b, True)),
               ("halves", lambda a, b: half_distance(a, b, True)))
    for name, d in systems:
        lost = [(b, n, f) for _, b, n, f, _ in battery if not tb._wins(d, b, n, f)]
        print(f"battery, {name}: {len(battery) - len(lost)}/{len(battery)}"
              + (f"  lost: {lost}" if lost else ""))
    from abugida import ONE_MOVE
    from abugida.lexicon import phonological_form as pf
    for name_file in ("oberlies_cases.json", "geiger_cases.json"):
        pairs = _data.load(name_file)["doublets"]
        print(f"{name_file[:8]} doublets within one move: " + "   ".join(
            f"{name} {sum(d(pf(a), pf(b)) <= ONE_MOVE + 1e-9 for a, b in pairs) / len(pairs):.1%}"
            for name, d in systems))
    open_vocabulary(systems)


def open_vocabulary(systems, trials=1500):
    """The forced choice of eval/open_vocabulary.py, with its own scribal and
    arbitrary generators, scored for every system; and again on the trials
    where both variants are possible Pāli. The generators change ONE letter,
    so they write half-geminates (tṭ) that one segmentation per word prices
    as a broken unit: that is where the systems differ."""
    from abugida.phonotactics import pseudoword
    src = open(os.path.join(HERE, "open_vocabulary.py"), encoding="utf-8").read()
    ns = {}
    exec(src[src.index("CONFUSION_PAIRS = ["):src.index("# --- OOV certificate")], ns)
    print("\nopen vocabulary: scribal beats arbitrary (all trials | both possible Pali)")
    for k in (1, 2, 3):
        ns["rng"] = random.Random(SEED + k)
        score = {name: [0.0, 0, 0.0, 0] for name, _ in systems}
        done = 0
        while done < trials:
            w = pseudoword(ns["rng"])
            t = tokenize(w)
            s = ns["scribal_variant"](t, k)
            if s is None:
                continue
            a = ns["arbitrary_variant"](t, k)
            done += 1
            legal = is_possible(s) and is_possible(a)
            for name, d in systems:
                ds, da = d(w, s), d(w, a)
                hit = 1.0 if ds < da else 0.5 if ds == da else 0.0
                score[name][0] += hit
                score[name][1] += 1
                if legal:
                    score[name][2] += hit
                    score[name][3] += 1
        print(f"  {k} edit(s): " + "   ".join(
            f"{name} {v[0] / v[1]:.1%} | {v[2] / v[3]:.1%}"
            for name, v in score.items()) + f"   (possible: n={score['live'][3]})")


if __name__ == "__main__":
    main()
