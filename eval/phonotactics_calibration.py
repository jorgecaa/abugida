"""How much of the real lexicon `is_possible` accepts, and what it rejects.

SPEC §13 quotes a calibration against DPD (98.93% of 74,438 cleaned lemmas
accepted; of the lemmas with a valid ending, 99.82%) that had no script
behind it. This is that measurement, so it can be re-run when the
phonotactics change — as they did on 2026-10-13, when the aspirated nasals
nh/mh were admitted as word onsets (Oberlies, *Pali* §15.1) and st as a
word-internal cluster (§16 rem. (a)).

DPD is the lexicon here, used as information: a rejected real lemma is a
question about the rule or about the lemma, and the breakdown says which
kind it is. "Cleaned" means: homonym numbers stripped, multi-word lemmas
dropped, duplicates merged. The original cleaning is not on record, so the
counts may differ slightly from SPEC's.

Prints the acceptance rate, the rejections by cause (citation lemmas ending
in a consonant, strings that do not tokenise, the rest), every one of the
rest to read, and the lemmas each 2026-10-13 rule now admits. Needs
`--dpd [PATH]`.
"""

import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import _dpd  # noqa: E402

_dpd.check()
from abugida import is_possible  # noqa: E402
from abugida.iast import tokenize  # noqa: E402

VOWELS = set("aāiīuūeo")


def clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


def cause(word):
    try:
        tokens = tokenize(word)
    except ValueError:
        return "does not tokenise"
    last = tokens[-1] if tokens else ""
    if last not in VOWELS and last != "ṃ":
        return "ends in a consonant (citation lemma)"
    return "other"


def main():
    con = _dpd.connect()
    lemmas = sorted({clean(l) for (l,) in con.execute(
        "SELECT lemma_1 FROM dpd_headwords")} - {""})
    words = [w for w in lemmas if " " not in w]
    accepted = [w for w in words if is_possible(w)]
    rejected = [w for w in words if not is_possible(w)]
    by = collections.defaultdict(list)
    for w in rejected:
        by[cause(w)].append(w)

    n = len(words)
    print(f"lemmas: {len(lemmas):,} distinct, {n:,} single-word")
    print(f"accepted: {len(accepted):,} ({len(accepted) / n:.2%})")
    print(f"rejected: {len(rejected):,} ({len(rejected) / n:.2%})")
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k}: {len(v):,} ({len(v) / n:.2%})")
    valid_end = n - len(by["ends in a consonant (citation lemma)"])
    print(f"of lemmas with a valid ending: "
          f"{(valid_end - len(by['other']) - len(by['does not tokenise'])) / valid_end:.2%} pass")

    rest = by["other"]
    print(f"\nrejected for another reason, all {len(rest)} (read them):")
    for i in range(0, len(rest), 8):
        print("  " + "  ".join(rest[i:i + 8]))

    nhmh = [w for w in accepted if w[:2] in ("nh", "mh")]
    show("lemmas opening with nh/mh, accepted since 2026-10-13", nhmh)
    st = [w for w in accepted if has_st(w)]
    show("lemmas with a word-internal st, accepted since 2026-10-13", st)


def has_st(word):
    """s then t as tokens: a string match would also take s + th."""
    tokens = tokenize(word)
    return any(a == "s" and b == "t" for a, b in zip(tokens, tokens[1:]))


def show(title, words):
    print(f"\n{title}: {len(words)}")
    for i in range(0, len(words), 8):
        print("  " + "  ".join(words[i:i + 8]))


if __name__ == "__main__":
    main()
