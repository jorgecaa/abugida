"""Evaluation: phonological distance vs Levenshtein over real Pāli.

Three ground-truth experiments over the DPD lexicon. Run with the database
available (/dev/shm/dpd.db). Results are recorded in SPEC.md §11.

Scoring per query: the lexicon is ranked by the measure; if the true target
comes strictly first, credit 1; if it ties with k candidates at the best
distance, credit 1/k (the expected value under random tie-breaking);
otherwise 0. The mean rank (expected position of the target) is reported too.
"""

import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402
from abugida.distance import cost  # noqa: E402
from abugida.iast import tokenize  # noqa: E402
from abugida.sandhi import assimilate_word  # noqa: E402

SEED = 20260801

#: Each experiment draws from its OWN generator, seeded independently.
#: With a single shared stream, changing the sample size of one experiment
#: shifts the RNG state for every later one, so their samples change too and
#: their numbers move for no reason connected to the metric. That happened
#: when Exp. 1 grew from 80 to 400 queries (2026-08-02): the sandhi row moved
#: 87.5% → 90.0% purely from redrawing. Independent streams keep an edit to
#: one experiment from silently rewriting the others.
rng1 = random.Random(SEED)      # Exp. 1, scribal corruption
rng2 = random.Random(SEED + 1)  # Exp. 2, sandhi (Exp. 3 is a fixed list)

# --- Lexicon ---------------------------------------------------------------

con = _dpd.connect()
lexicon = set()
for (lemma,) in con.execute("SELECT lemma_1 FROM dpd_headwords"):
    w = re.sub(r"\s+\d+(\.\d+)?$", "", lemma.strip())
    if re.fullmatch(r"[a-zāīūṅñṭḍṇḷṃ]+", w) and 4 <= len(w) <= 10:
        lexicon.add(w)
lexicon = sorted(lexicon)
search_space = set(lexicon)  # the FULL lexicon: the realistic use case

TOKENS = {}


def toks(w):
    if w not in TOKENS:
        TOKENS[w] = tokenize(w)
    return TOKENS[w]


def _edit(t1, t2, sub):
    n, m = len(t1), len(t2)
    row = list(range(m + 1))
    for i in range(1, n + 1):
        prev, row[0] = row[0], i
        for j in range(1, m + 1):
            cur = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1,
                         prev + sub(t1[i - 1], t2[j - 1]))
            prev = cur
    return row[m]


def d_phon(a, b):
    return _edit(toks(a), toks(b), cost)


def d_lev(a, b):
    return _edit(toks(a), toks(b), lambda x, y: 0.0 if x == y else 1.0)


def evaluate(queries, name):
    """queries: list of (query, target). Ranked against the lexicon."""
    res = {}
    for label, measure in [("phonological", d_phon), ("levenshtein", d_lev)]:
        credit, rank_total, ties_total, n = 0.0, 0.0, 0, 0
        for q, target in queries:
            if q == target:
                # the query already IS the target (e.g. after resolving
                # sandhi): a trivial hit at distance 0, not a self-match to
                # skip
                credit += 1.0
                rank_total += 1.0
                ties_total += 1
                n += 1
                continue
            candidates = search_space | {target}
            lt = len(toks(q))
            d_target = None
            dists = []
            for w in candidates:
                if w == q or abs(len(toks(w)) - lt) > 2:
                    continue
                d = measure(q, w)
                dists.append((d, w))
                if w == target:
                    d_target = d
            if d_target is None:
                continue
            best = min(d for d, _ in dists)
            tied = sum(1 for d, _ in dists if abs(d - best) < 1e-9)
            strictly_better = sum(1 for d, _ in dists if d < d_target - 1e-9)
            tied_with_target = sum(
                1 for d, _ in dists if abs(d - d_target) < 1e-9
            )
            if abs(d_target - best) < 1e-9:
                credit += 1.0 / tied
            rank_total += strictly_better + (tied_with_target + 1) / 2.0
            ties_total += tied
            n += 1
        res[label] = (credit / n, rank_total / n, ties_total / n, n)
    print(f"\n== {name} (n={res['phonological'][3]}) ==")
    for label, (acc, rank, ties, _) in res.items():
        print(f"  {label:13} expected top-1: {acc:6.1%}   "
              f"mean rank: {rank:6.2f}   tied at the top: {ties:5.1f}")
    return res


# --- Exp. 1: scribal corruption --------------------------------------------

# This list is a THEORY of which confusions occur, and the metric is scored
# against it — so an omission here is not neutral, it is a thumb on the scale.
# The tongue-BODY pairs below were missing until 2026-08-02, while the
# tongue-TIP ones were present. That asymmetry is not supported by the data:
# in `var_phonetic`, guttural~palatal is 11.4% of all place substitutions
# between simple consonants, second only to cerebral~dental's 72.7%
# (`eval/karana_bridges.py`). With them absent, a metric that models the
# dorsal bridge could only ever be penalised here, never rewarded — and it
# was, measurably: the bridge "cost" 0.9 points at p=0.0039 on the old list
# and 0.5 points at p=0.23 (not significant) once corrected.
CONFUSION_PAIRS = [
    ("t", "ṭ"), ("th", "ṭh"), ("d", "ḍ"), ("dh", "ḍh"), ("n", "ṇ"),
    ("l", "ḷ"),  # tongue tip: cerebral ↔ dental (72.7% of attested)
    ("k", "c"), ("kh", "ch"), ("g", "j"), ("gh", "jh"), ("ṅ", "ñ"),
    # tongue body: guttural ↔ palatal (11.4% of attested)
    ("k", "kh"), ("g", "gh"), ("c", "ch"), ("j", "jh"), ("t", "th"),
    ("d", "dh"), ("p", "ph"), ("b", "bh"),  # aspiration
    ("a", "ā"), ("i", "ī"), ("u", "ū"),  # vowel length
    ("k", "g"), ("c", "j"), ("ṭ", "ḍ"), ("t", "d"), ("p", "b"),  # voicing
    ("ṅ", "ṃ"), ("n", "ṃ"), ("m", "ṃ"),  # nasals
]
CONFUSABLE = {}
for a, b in CONFUSION_PAIRS:
    CONFUSABLE.setdefault(a, []).append(b)
    CONFUSABLE.setdefault(b, []).append(a)

queries1 = []
for w in rng1.sample(lexicon, 20000):
    t = toks(w)
    positions = [i for i, g in enumerate(t) if g in CONFUSABLE]
    if not positions:
        continue
    i = rng1.choice(positions)
    t2 = list(t)
    t2[i] = rng1.choice(CONFUSABLE[t[i]])
    corrupted = "".join(t2)
    if corrupted in set(lexicon) or corrupted == w:
        continue
    queries1.append((corrupted, w))
    if len(queries1) == 400:
        break
evaluate(queries1, "scribal corruption → recover the original")

# --- Exp. 2: sandhi variants (assimilated ~ unassimilated) -----------------

queries2 = []
nasal_of = {"k": "ṅ", "kh": "ṅ", "g": "ṅ", "gh": "ṅ",
            "c": "ñ", "ch": "ñ", "j": "ñ", "jh": "ñ",
            "ṭ": "ṇ", "ṭh": "ṇ", "ḍ": "ṇ", "ḍh": "ṇ",
            "t": "n", "th": "n", "d": "n", "dh": "n",
            "p": "m", "ph": "m", "b": "m", "bh": "m"}
for w in lexicon:
    t = toks(w)
    for i, g in enumerate(t[:-1]):
        if g == "ṃ" and t[i + 1] in nasal_of:
            t2 = list(t)
            t2[i] = nasal_of[t[i + 1]]
            assimilated = "".join(t2)
            if assimilated in set(lexicon):
                queries2.append((w, assimilated))
            break
rng2.shuffle(queries2)
queries2 = queries2[:40]
evaluate(queries2, "sandhi: ṃC spelling → the attested assimilated form")

# The recommended pipeline (docs/comparator.md): resolve sandhi BEFORE
# comparing. It raises phonological top-1 to 100% — it fixes the failures
# caused by the glut's inflated norm (ṃ→ṅ 0.77 > a final vowel's 0.61).
queries2r = [(assimilate_word(q), target) for q, target in queries2]
evaluate(queries2r, "sandhi, resolved pipeline: assimilate_word + distance")

# --- Exp. 3: tadbhava (Sanskrit → Pāli reflex) -----------------------------

TADBHAVA = [
    ("dharma", "dhamma"), ("karma", "kamma"), ("sūtra", "sutta"),
    ("putra", "putta"), ("mitra", "mitta"), ("indra", "inda"),
    ("candra", "canda"), ("agni", "aggi"), ("mārga", "magga"),
    ("nirvāṇa", "nibbāna"), ("bhadra", "bhadda"), ("tatra", "tattha"),
]
evaluate(TADBHAVA, "tadbhava: Sanskrit → Pāli reflex")
