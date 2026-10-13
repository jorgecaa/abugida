"""The metric against Oberlies' grammar, and both against DPD's variant pairs.

Oberlies, *Pali: A Grammar of the Language of the Theravada Tipitaka*, is the
current reference grammar of Pāli. The case file `oberlies_cases.json`
(local data directory, `eval/_data.py`; not distributed, see `NOTICE`)
carries what was read from its phonology chapter: 740 Sanskrit→Pāli pairs and 134 Pāli doublets
(word pairs only; see the file's `note` for how they were read and what was
left out). It is a ground truth that no distance algorithm produced, unlike
`dpd_headwords.var_phonetic`, which DPD's own rules generate.

What this prints, in order:

1. Separation of real pairs from shuffled ones, for Oberlies and Geiger side
   by side, metric and Levenshtein. Shuffled negatives are RANDOM negatives,
   which `protocol.py` rule 4 says cannot discriminate: read these AUCs as a
   sanity check that the file is not noise, never as evidence for the metric.
2. Where the cost goes for Sanskrit→Pāli: mostly the OIA cluster laws the
   metric does not model (r, ṣ, y, v lost in clusters), as expected of a
   metric built for Pāli against Pāli.
3. The alternations Oberlies documents, priced by the current cost table, in
   multiples of ONE_MOVE.
4. Those alternations counted in DPD's var_phonetic pairs (the 2,310 distinct
   pairs behind `hard_battery.json`, which is a Levenshtein-tie-filtered
   sample, not the whole field) and in Oberlies' own lists.
5. Single~geminate alternations, consonant by consonant, in both sources.
6. Pāli forms the phonotactics rejects.
7. When `oberlies_attested.json` exists (written by
   `oberlies_attested.py --dpd`), the Sanskrit→Pāli pairs whose Sanskrit-side
   form DPD attests as Pāli: a second set of Pāli pairs (western ~ eastern
   reading, `samāja ~ samajja`), measured like the first. Whether the two
   forms mean the same is irrelevant to a metric of sounds.

Needs no DPD database and no rapidfuzz.
"""

import collections
import os
import random
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from abugida import (  # noqa: E402
    ONE_MOVE, alignment, cost, distance, is_possible, levenshtein,
)
from abugida.lexicon import phonological_form as pf  # noqa: E402

import _data  # noqa: E402

SEED = 20260801


load = _data.load

_data.require("oberlies_cases.json", "geiger_cases.json", "hard_battery.json")
O = load("oberlies_cases.json")
G = load("geiger_cases.json")
DPD = sorted({tuple(sorted((b, n))) for b, n, _, _ in load("hard_battery.json")})


def d(a, b):
    return distance(pf(a), pf(b), lenient=True)


def auc(pos, neg):
    s = 0.0
    for p in pos:
        s += sum(1 for n in neg if p < n) + 0.5 * sum(1 for n in neg if p == n)
    return s / (len(pos) * len(neg))


def separation(name, pairs):
    rng = random.Random(SEED)
    pos = [d(a, b) for a, b in pairs]
    shuffled = [b for _, b in pairs]
    rng.shuffle(shuffled)
    neg = [d(a, b) for (a, _), b in zip(pairs, shuffled)]
    lpos = [levenshtein(a, b, lenient=True) for a, b in pairs]
    lneg = [levenshtein(a, b, lenient=True)
            for (a, _), b in zip(pairs, shuffled)]
    within = " ".join(
        f"{k}x:{sum(x <= k * ONE_MOVE + 1e-9 for x in pos) / len(pos):.1%}"
        for k in (1, 2, 3))
    print(f"  {name:9} n={len(pairs):4}  median {st.median(pos):.2f}  "
          f"AUC metric {auc(pos, neg):.3f}  Levenshtein {auc(lpos, lneg):.3f}"
          f"  within ONE_MOVE {within}")


def operations(pairs):
    counts, examples = collections.Counter(), collections.defaultdict(list)
    for a, b in pairs:
        for op, x, y, _ in alignment(pf(a), pf(b), lenient=True):
            if op == "keep":
                continue
            key = (op,) + tuple(sorted((str(x), str(y))))
            counts[key] += 1
            if len(examples[key]) < 3:
                examples[key].append(f"{a}~{b}")
    return counts, examples


# (alternation, Oberlies section that documents it)
ALTERNATIONS = [
    ("ḍ", "ḷ", "§13"), ("r", "l", "§14.10"), ("l", "ḷ", "§13 rem."),
    ("n", "ṇ", "§14.7"), ("t", "ṭ", "§14.5"), ("y", "v", "§14.8"),
    ("b", "v", "§13 rem. g"), ("k", "kh", "§14.1"), ("k", "g", "§14.2"),
    ("p", "v", "§14.2 n. 6"), ("y", "l", "§14.12"), ("d", "j", "p. 89 n. 1"),
    ("s", "ch", "§13"), ("s", "h", "§18.4"), ("kh", "ch", "§18.2"),
    ("t", "c", "§16.1"), ("d", "r", "§14.14"), ("m", "v", "§14.14"),
]


def geminations(pairs):
    counts, examples = collections.Counter(), collections.defaultdict(list)
    for a, b in pairs:
        for op, x, y, _ in alignment(pf(a), pf(b), lenient=True):
            if op != "sub" or not x or not y:
                continue
            short, long_ = sorted((x, y), key=len)
            if (len(long_) > len(short) and long_.endswith(short)
                    and long_[:-len(short)] in (short, short[0])):
                counts[short] += 1
                if len(examples[short]) < 2:
                    examples[short].append(f"{a}~{b}")
    return counts, examples


def main():
    print("1. Separation from shuffled pairs (random negatives: a sanity "
          "check only)")
    print(" Sanskrit -> Pali")
    separation("Oberlies", O["tadbhava"])
    separation("Geiger", G["tadbhava"])
    print(" Pali ~ Pali doublets")
    separation("Oberlies", O["doublets"])
    separation("Geiger", G["doublets"])

    print("\n2. Where the cost goes, Sanskrit -> Pali (top 15 by total cost)")
    total = collections.Counter()
    seen = collections.Counter()
    for a, b in O["tadbhava"]:
        for op, x, y, w in alignment(pf(a), pf(b), lenient=True):
            if op != "keep":
                total[(op, x, y)] += w
                seen[(op, x, y)] += 1
    grand = sum(total.values())
    for k, v in total.most_common(15):
        print(f"  {k[0]:3} {str(k[1]):>3} -> {str(k[2]):<4} x{seen[k]:<3} "
              f"cost/op {v / seen[k]:.3f}  share {v / grand:.1%}")

    od, _ = operations(O["doublets"])
    ot, _ = operations(O["tadbhava"])
    dd, _ = operations(DPD)
    print(f"\n3-4. Alternations Oberlies documents: cost, and attestation in "
          f"DPD's {len(DPD)} pairs and Oberlies' lists")
    print("  alternation  cost  xONE_MOVE  DPD  Ob.doublets  Ob.Skt>Pali  "
          "section")
    for x, y, sect in ALTERNATIONS:
        key = ("sub",) + tuple(sorted((x, y)))
        c = cost(x, y)
        print(f"  {x:>2} ~ {y:<4}   {c:.3f}  {c / ONE_MOVE:5.2f}   {dd[key]:4} "
              f"{od[key]:8} {ot[key]:11}   {sect}")

    print("\n5. Single ~ geminate, by consonant")
    gd, ge = geminations(DPD)
    go, gx = geminations(O["doublets"])
    print("  cons  DPD  Ob.doublets  examples")
    for k in sorted(set(gd) | set(go), key=lambda k: (-gd[k], k)):
        print(f"  {k:4} {gd[k]:4} {go[k]:8}     {ge[k] or gx[k]}")

    print("\n6. Pali forms in the Oberlies file the phonotactics rejects")
    pali = {b for _, b in O["tadbhava"]} | {w for p in O["doublets"] for w in p}
    print("  ", sorted(w for w in pali if not is_possible(w)) or "none")

    if not _data.exists("oberlies_attested.json"):
        print("\n7. (skipped: run oberlies_attested.py --dpd to list the "
              "Sanskrit-side forms DPD attests as Pali)")
        return
    att = [(h["first"], h["second"])
           for h in load("oberlies_attested.json")["pairs"]]
    print(f"\n7. Sanskrit-side forms DPD attests as Pali: {len(att)} more Pali "
          "pairs (western ~ eastern reading)")
    separation("attested", att)
    ad, ae = operations(att)
    print("  the alternations of section 3 in these pairs:")
    for x, y, sect in ALTERNATIONS:
        key = ("sub",) + tuple(sorted((x, y)))
        if ad[key]:
            print(f"    {x:>2} ~ {y:<4} {ad[key]:3}  {ae[key]}  ({sect})")


if __name__ == "__main__":
    main()
