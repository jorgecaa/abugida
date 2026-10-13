"""The universal decision rule: hybrid vs char-level, free of population bias.

Any real query stream is a MIX of error types: keyboard typos (phonologically
arbitrary) and phonological confusions (aspiration, length, retroflexion…).
Accuracy over a mix is LINEAR in the mix proportion — each query is one or
the other, so the mix only reweights two fixed per-model accuracies. Two
measures therefore give two lines with a single crossover p*:

    deploy the hybrid  ⇔  typo share p < p*

That rule is universal: it does not depend on whose traffic you have. What
depends on the population is only p, and eval/profile_error_mix.py measures
it from your own logs.

This script measures the four endpoint accuracies on the full DPD lexicon
(tie-aware expected top-1, fixed seed), derives p* in closed form, and
bootstraps a confidence interval. Requires rapidfuzz and /dev/shm/dpd.db.
"""

import os
import random
import re
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

_dpd.check()
from rapidfuzz import fuzz, process  # noqa: E402

from abugida.distance import distance  # noqa: E402
from abugida.iast import tokenize  # noqa: E402

rng = random.Random(20260801)
N_PER_MODEL = 600
POOL = 200

# --- lexicon ---------------------------------------------------------------

con = _dpd.connect()
lexicon = set()
for (lemma,) in con.execute("SELECT lemma_1 FROM dpd_headwords"):
    w = re.sub(r"\s+\d+(\.\d+)?$", "", lemma.strip())
    if re.fullmatch(r"[a-zāīūṅñṭḍṇḷṃ]+", w) and 3 <= len(w) <= 25:
        lexicon.add(w)
lexicon = sorted(lexicon)
lexset = set(lexicon)

# --- error models ----------------------------------------------------------

CONFUSION_PAIRS = [
    ("t", "ṭ"), ("th", "ṭh"), ("d", "ḍ"), ("dh", "ḍh"), ("n", "ṇ"),
    ("l", "ḷ"),
    ("k", "kh"), ("g", "gh"), ("c", "ch"), ("j", "jh"), ("t", "th"),
    ("d", "dh"), ("p", "ph"), ("b", "bh"),
    ("a", "ā"), ("i", "ī"), ("u", "ū"),
    ("k", "g"), ("c", "j"), ("ṭ", "ḍ"), ("t", "d"), ("p", "b"),
    ("ṅ", "ṃ"), ("n", "ṃ"), ("m", "ṃ"),
]
CONFUSABLE = {}
for a, b in CONFUSION_PAIRS:
    CONFUSABLE.setdefault(a, []).append(b)
    CONFUSABLE.setdefault(b, []).append(a)


def scribal(word):
    """One documented phonological confusion, on tokens."""
    t = tokenize(word)
    positions = [i for i, g in enumerate(t) if g in CONFUSABLE]
    if not positions:
        return None
    i = rng.choice(positions)
    t = list(t)
    t[i] = rng.choice(CONFUSABLE[t[i]])
    return "".join(t)


def typo(word):
    """One keyboard edit on the raw string: sub/del/ins/transpose ASCII."""
    kind = rng.choice(["sub", "del", "ins", "swap"])
    i = rng.randrange(len(word))
    letters = string.ascii_lowercase
    if kind == "sub":
        return word[:i] + rng.choice(letters) + word[i + 1:]
    if kind == "del" and len(word) > 3:
        return word[:i] + word[i + 1:]
    if kind == "ins":
        return word[:i] + rng.choice(letters) + word[i:]
    if len(word) > 3 and i < len(word) - 1:
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    return None


def queries(model):
    out = []
    for w in rng.sample(lexicon, len(lexicon)):
        q = model(w)
        if q and q != w and q not in lexset:
            out.append((q, w))
            if len(out) == N_PER_MODEL:
                break
    return out


# --- measures (tie-aware expected top-1) -----------------------------------


def top1_char(q, target):
    ranked = process.extract(q, lexicon, scorer=fuzz.ratio, limit=50)
    best = ranked[0][1]
    tied = [w for w, s, _ in ranked if abs(s - best) < 1e-9]
    return (1.0 / len(tied)) if target in tied else 0.0


def top1_hybrid(q, target):
    pool = [w for w, _, _ in process.extract(q, lexicon,
                                             scorer=fuzz.ratio, limit=POOL)]
    scored = [(distance(q, w, lenient=True), w) for w in pool]
    best = min(d for d, _ in scored)
    tied = [w for d, w in scored if abs(d - best) < 1e-9]
    return (1.0 / len(tied)) if target in tied else 0.0


def run(model):
    qs = queries(model)
    char_scores = [top1_char(q, t) for q, t in qs]
    hyb_scores = [top1_hybrid(q, t) for q, t in qs]
    return char_scores, hyb_scores


print(f"lexicon: {len(lexicon)}  |  n = {N_PER_MODEL} per error model")
char_typo, hyb_typo = run(typo)
char_scrib, hyb_scrib = run(scribal)

mean = lambda xs: sum(xs) / len(xs)
ct, ht = mean(char_typo), mean(hyb_typo)
cs, hs = mean(char_scrib), mean(hyb_scrib)
print("\n              char-level   hybrid")
print(f"typos          {ct:7.1%}   {ht:7.1%}")
print(f"phonological   {cs:7.1%}   {hs:7.1%}")


def crossover(ct, ht, cs, hs):
    # hybrid wins iff p·ht + (1−p)·hs > p·ct + (1−p)·cs  ⇔  p < p*
    num = hs - cs
    den = (ct - ht) + (hs - cs)
    return num / den if den > 0 else (1.0 if num > 0 else 0.0)


p_star = crossover(ct, ht, cs, hs)
print(f"\ncrossover p* = {p_star:.1%}  (deploy the hybrid iff typo share < p*)")

# bootstrap CI over queries
boots = []
n = N_PER_MODEL
for _ in range(2000):
    idx_t = [rng.randrange(n) for _ in range(n)]
    idx_s = [rng.randrange(n) for _ in range(n)]
    boots.append(crossover(
        mean([char_typo[i] for i in idx_t]),
        mean([hyb_typo[i] for i in idx_t]),
        mean([char_scrib[i] for i in idx_s]),
        mean([hyb_scrib[i] for i in idx_s]),
    ))
boots.sort()
lo, hi = boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots))]
print(f"95% CI: [{lo:.1%}, {hi:.1%}]  (bootstrap over queries, 2000 resamples)")
