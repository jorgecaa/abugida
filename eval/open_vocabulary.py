"""OPEN-vocabulary evaluation: the metric without a dictionary.

This answers a fair methodological objection to eval/compare_levenshtein.py:
evaluating by retrieval against DPD inherits its closed world — real
misspellings and unrecorded variants fall outside it, and comparisons
between unregistered forms (where a metric has to stand on its own) are
never measured.

There is no lexicon here. The base words come from the phonotactic generator
(phonotactics.pseudoword): legal by construction, and guaranteed to be
outside any dictionary (checked against DPD only to CERTIFY that they are
out-of-vocabulary — the dictionary as a negative control, not an oracle).

With `--morphological` the base words come instead from
`morphology.pseudoform`: forms with a root, a base and an ending, so the
task runs over candidates a reader could actually parse rather than over
merely legal syllable sequences. Its criterion is the RULES — whether a
form is attested is not part of it, and the generator consults no
dictionary at any point. Fidelity is reported with --attestation (47.9% of
everything it can build turns out to be real Pāli, which measures the
junction rules, not the candidates' right to exist).

`--oov-only` additionally discards attested forms. That is a demand of THIS
experiment, whose premise is measuring without a dictionary, not a
criterion of the generator. Both variants are reported separately and
neither is mixed into the default numbers.

Forced-choice task: given a base word w, we generate
  - a SCRIBAL variant (one documented manuscript confusion:
    dental↔retroflex, aspiration, length, voicing, nasals), and
  - an ARBITRARY variant (same number of edits, substituting an unrelated
    grapheme),
and ask each measure which of the two is closer to w. The truth: the scribal
one. A tie scores 0.5.

With ONE edit, Levenshtein assigns 1 to both by construction: it cannot tell
a plausible variant from an arbitrary mutation. That is the point of the
experiment — and the reason no closed-vocabulary evaluation could show it.
"""

import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402
from abugida.distance import distance, levenshtein  # noqa: E402
from abugida.iast import tokenize  # noqa: E402
from abugida.morphology import formations, pseudoform  # noqa: E402
from abugida.phonotactics import pseudoword  # noqa: E402

MORPHOLOGICAL = "--morphological" in sys.argv
ATTESTATION = "--attestation" in sys.argv
OOV_ONLY = "--oov-only" in sys.argv

rng = random.Random(20260801)

# --- documented scribal confusions (same set as compare_levenshtein) -------
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

GRAPHEMES = sorted(
    {g for pair in CONFUSION_PAIRS for g in pair}
    | set("aiukgcjtdpbmnyrlvsh")
)


def scribal_variant(tokens, n_edits):
    t = list(tokens)
    positions = [i for i, g in enumerate(t) if g in CONFUSABLE]
    rng.shuffle(positions)
    done = 0
    for i in positions:
        if done == n_edits:
            break
        t[i] = rng.choice(CONFUSABLE[t[i]])
        done += 1
    return "".join(t) if done == n_edits else None


def arbitrary_variant(tokens, n_edits):
    t = list(tokens)
    positions = list(range(len(t)))
    rng.shuffle(positions)
    for i in positions[:n_edits]:
        options = [
            g for g in GRAPHEMES
            if g != t[i] and g not in CONFUSABLE.get(t[i], [])
        ]
        t[i] = rng.choice(options)
    return "".join(t)


# --- OOV certificate: DPD only as a negative control -----------------------
dpd_lexicon = set()
con = _dpd.connect()
for (lemma,) in con.execute("SELECT lemma_1 FROM dpd_headwords"):
    dpd_lexicon.add(re.sub(r"\s+\d+(\.\d+)?$", "", lemma.strip()))

# The inflected forms too: a morphological candidate that DPD records only
# as an inflection of some headword is attested Pāli, not a pseudo-word.
dpd_attested = set(dpd_lexicon)
for (key,) in con.execute("SELECT lookup_key FROM lookup"):
    dpd_attested.add(key)


def base_word():
    """Draw one base word, phonotactic or morphological.

    Attestation gates nothing unless --oov-only asks for it: the generator's
    criterion is that the form obeys the rules.
    """
    if not MORPHOLOGICAL:
        return pseudoword(rng)
    while True:
        w = pseudoform(rng).word
        if not OOV_ONLY or w not in dpd_attested:
            return w


if ATTESTATION:
    # Fidelity of the morphological generator, measured not asserted: the
    # share of everything it can build that is real Pāli. Nothing about the
    # metric — a check that the junction rules produce the language.
    forms = list(formations())
    for kind in ("verb", "noun"):
        sub = [f for f in forms if f.kind == kind]
        hit = sum(f.word in dpd_attested for f in sub)
        print(f"  {kind:5} attested in DPD: {hit:5}/{len(sub):5} "
              f"= {hit / len(sub):6.1%}")
    hit = sum(f.word in dpd_attested for f in forms)
    print(f"  total attested in DPD: {hit}/{len(forms)} = {hit / len(forms):.1%}")

mode = "morphological" if MORPHOLOGICAL else "phonotactic"
print(f"\nbase words: {mode}{' (attested discarded)' if OOV_ONLY else ''}")

N = 400
for n_edits in (1, 2, 3):
    hits = {"phonological": 0.0, "levenshtein": 0.0}
    n_oov = n_unattested = used = 0
    while used < N:
        w = base_word()
        t = tokenize(w)
        scribal = scribal_variant(t, n_edits)
        if scribal is None or scribal == w:
            continue
        arbitrary = arbitrary_variant(t, n_edits)
        if arbitrary == w or arbitrary == scribal:
            continue
        # Two different questions, kept apart: not a DPD headword, and not
        # recorded at all (a morphological form is typically neither a
        # lemma nor a novelty — it can be an inflection of some headword).
        n_oov += w not in dpd_lexicon
        n_unattested += w not in dpd_attested
        used += 1
        for name, measure in [
            ("phonological", distance),
            ("levenshtein", levenshtein),
        ]:
            d_scribal, d_arbitrary = measure(w, scribal), measure(w, arbitrary)
            if d_scribal < d_arbitrary - 1e-9:
                hits[name] += 1.0
            elif abs(d_scribal - d_arbitrary) < 1e-9:
                hits[name] += 0.5
    print(f"\n== {n_edits} edit(s), n={N}, not a DPD lemma: {n_oov / N:.1%}, "
          f"unattested (lemma or inflection): {n_unattested / N:.1%} ==")
    for name, h in hits.items():
        print(f"  {name:13} tells scribal from arbitrary: {h / N:6.1%}")
