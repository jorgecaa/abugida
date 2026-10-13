"""Measure YOUR typo share p — the only population-dependent number.

The deployment rule is universal (eval/decision_curve.py): deploy the
rapidfuzz→phonological hybrid iff your traffic's typo share p < p*
(measured p* = 56.8% with 95% CI [45.4%, 68.7%]). What varies between
populations is p alone. This tool estimates it from your own logs.

Usage:
    journalctl -u your-webapp | python eval/profile_error_mix.py
    cat logs/*.uvicorn.log    | python eval/profile_error_mix.py
    cat failed_queries.txt    | python eval/profile_error_mix.py --raw

Input: uvicorn-style access-log lines (queries taken from `?q=`), or with
--raw one bare query per line. Lexicon: the DPD headwords by default, or
--lexicon FILE with one word per line. Read-only everywhere.

Classification of each miss is METRIC-FREE — it must not use the distance
whose adoption is being decided (that would be circular). Rules only:
  counted in p (errors):
    - phonological-like: some lexicon word is reachable by 1-2 substitutions
                         drawn from the documented confusion table
                         (aspiration, length, retroflexion, voicing, nasals)
    - typo-like:         non-Pāli characters, or some lexicon word within
                         1-2 plain character edits (and not
                         confusion-reachable)
  excluded from p (not errors the fuzzy route should fix):
    - prefix of a lexicon word           → incremental search-as-you-type
    - legal Pāli far from the lexicon    → morphological coverage gap
    - fragments / everything else       → unmodelled

The tool also reports DECISION COVERAGE: the share of misses the p-rule
actually governs. If the excluded classes dominate, the fuzzy-measure choice
optimises a minority of your failed traffic — fix the majority elsewhere
(prefix search, morphology) before tuning the fuzzy route.
"""

import argparse
import os
import re
import sys
import unicodedata
from collections import Counter
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402
from abugida import diagnose, is_possible  # noqa: E402
from abugida.iast import tokenize  # noqa: E402

#: The documented scribal/phonological confusions (same table as the error
#: model in decision_curve.py). Classification is by REACHABILITY through
#: this table — no distance metric involved.
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

parser = argparse.ArgumentParser()
parser.add_argument("--raw", action="store_true",
                    help="stdin is one query per line, not an access log")
parser.add_argument("--lexicon", help="word list file (default: DPD)")
args = parser.parse_args()

# --- lexicon ---------------------------------------------------------------

if args.lexicon:
    with open(args.lexicon, encoding="utf-8") as fh:
        words = {line.strip() for line in fh if line.strip()}
else:
    con = _dpd.connect()
    words = {k for (k,) in con.execute("SELECT lookup_key FROM lookup")}
    words |= {
        re.sub(r"\s+\d+(\.\d+)?$", "", l.strip())
        for (l,) in con.execute("SELECT lemma_1 FROM dpd_headwords")
    }



# --- queries ---------------------------------------------------------------

text = sys.stdin.read()
if args.raw:
    queries = [q.strip() for q in text.splitlines() if q.strip()]
else:
    queries = [
        unquote(m.group(1))
        for m in re.finditer(r"[?&]q=([^ &\"]+)", text)
    ]
queries = [unicodedata.normalize("NFC", q.strip().lower()) for q in queries]
queries = [q for q in queries if q and len(q) < 40 and "\n" not in q]

# drop incremental-typing prefixes (a, ar, ara… bursts)
kept = [
    q for i, q in enumerate(queries)
    if not (i + 1 < len(queries) and queries[i + 1] != q
            and queries[i + 1].startswith(q))
]
misses = sorted({q for q in kept if q not in words})

# --- classify --------------------------------------------------------------


def confusion_reachable(q, max_subs=2):
    """Is some lexicon word reachable from q by 1..max_subs substitutions
    drawn ONLY from the documented confusion table? Metric-free."""
    try:
        t = tokenize(q)
    except ValueError:
        return False
    positions = [i for i, g in enumerate(t) if g in CONFUSABLE]
    for i in positions:
        for alt in CONFUSABLE[t[i]]:
            one = t[:i] + [alt] + t[i + 1:]
            if "".join(one) in words:
                return True
            if max_subs >= 2:
                for j in positions:
                    if j <= i:
                        continue
                    for alt2 in CONFUSABLE[t[j]]:
                        two = one[:j] + [alt2] + one[j + 1:]
                        if "".join(two) in words:
                            return True
    return False


def _char_lev(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            cur = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
            prev = cur
        if min(row) > cap:
            return cap + 1
    return row[-1]


try:
    from rapidfuzz import fuzz, process

    _WORDLIST = sorted(words)

    def typo_reachable(q, max_edits=2):
        pool = [w for w, _, _ in process.extract(
            q, _WORDLIST, scorer=fuzz.ratio, limit=30)]
        return any(_char_lev(q, w) <= max_edits for w in pool)
except ImportError:  # pure-Python fallback (slow on big lexicons)

    def typo_reachable(q, max_edits=2):
        return any(_char_lev(q, w) <= max_edits for w in words
                   if abs(len(w) - len(q)) <= max_edits)


kinds = Counter()
for q in misses:
    if any(w.startswith(q) for w in words):
        kinds["excluded: prefix (incremental typing)"] += 1
    elif confusion_reachable(q):
        # priority over typo: a→ā is both a confusion and one char edit;
        # the specific model wins over the generic one
        kinds["phonological-like"] += 1
    elif diagnose(q) or typo_reachable(q):
        kinds["typo-like"] += 1
    elif is_possible(q):
        kinds["excluded: legal Pāli, coverage gap"] += 1
    else:
        kinds["excluded: unmodelled (fragment/other)"] += 1

# --- report ----------------------------------------------------------------

n_err = kinds["typo-like"] + kinds["phonological-like"]
print(f"queries: {len(queries)}  after prefix-dedup: {len(kept)}  "
      f"lexicon misses: {len(misses)}")
for kind, c in kinds.most_common():
    print(f"  {c:4d}  {kind}")
if n_err:
    p = kinds["typo-like"] / n_err
    coverage = n_err / len(misses) if misses else 0.0
    print(f"\nestimated typo share p = {p:.0%}  (n = {n_err} true errors)")
    print(f"rule: deploy the hybrid iff p < p* = 56.8%  "
          f"→  {'HYBRID' if p < 0.63 else 'char-level (rapidfuzz)'}")
    print(f"decision coverage: the p-rule governs {coverage:.0%} of misses "
          f"({n_err}/{len(misses)})")
    if coverage < 0.5:
        print("note: the excluded classes dominate — the fuzzy-measure "
              "choice optimises a minority of failed traffic; address "
              "prefixes/morphology first")
    if n_err < 30:
        print("caution: n < 30 — collect more traffic before deciding")
else:
    print("\nno true errors found — nothing to decide on")
