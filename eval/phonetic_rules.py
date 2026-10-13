"""abugida against DPD's hand-written PHONETIC_RULES.

dpd-db/tools/synonym_variant.py carries ~65 hand-written substitution rules
(PHONETIC_RULES) that generate phonetic variant candidates between
headwords. That is exactly the task this metric claims to model. Measured
here, two levels:

1. RULE level — score every hand rule with `distance` (which subsumes
   cost/indel/gemination uniformly, empty side = pure indel). Compare
   against all non-rule single-grapheme pairs: separation, AUC,
   disagreements in both directions (rules the metric finds expensive;
   non-rule pairs the metric prices below the rule median — candidate
   additions).

2. DATABASE level — apply each rule once at each position over a sample of
   real lemmas (bidirectional, as the tool does), keep productions that hit
   another real lemma: the tool's actual variant-candidate pairs. Measure
   what fraction of them the metric prices under the rule-level threshold
   (recall of the hand system), and count threshold-close DB pairs the
   rules do NOT connect (the metric's additions at scale).

Reads the rules from ../dpd-db at runtime (read-only); requires the DPD db.
"""

import itertools
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _dpd  # noqa: E402

_dpd.check()
from abugida import distance  # noqa: E402
from abugida.alphabet import ALPHABET  # noqa: E402

RULES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "dpd-db",
                          "tools", "synonym_variant.py")

# --- load the hand rules ---------------------------------------------------

src = open(RULES_FILE, encoding="utf-8").read()
block = re.search(r"PHONETIC_RULES[^=]*=\s*\[(.*?)\n\]", src, re.S).group(1)
RULES = [
    (m.group(1), m.group(2))
    for m in re.finditer(r'\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*True\)', block)
]
print(f"hand rules loaded: {len(RULES)}")

# --- level 1: rule scores vs non-rule pairs --------------------------------

scored = sorted((distance(x, y, lenient=True), x or "∅", y or "∅")
                for x, y in RULES)
rule_costs = [d for d, _, _ in scored]
median_rule = rule_costs[len(rule_costs) // 2]
max_rule = rule_costs[-1]

letters = [p.grapheme for p in ALPHABET]
rule_set = {frozenset((x, y)) for x, y in RULES if x and y}
nonrule = sorted(
    (distance(a, b), a, b)
    for a, b in itertools.combinations(letters, 2)
    if frozenset((a, b)) not in rule_set
)
nonrule_costs = [d for d, _, _ in nonrule]

single_rules = [(d, x, y) for d, x, y in scored
                if x in letters and y in letters]
# AUC: P(random rule pair < random non-rule pair), single-grapheme rules only
wins = ties = 0
for d, _, _ in single_rules:
    for dn in nonrule_costs:
        if d < dn - 1e-9:
            wins += 1
        elif abs(d - dn) < 1e-9:
            ties += 1
auc = (wins + ties / 2) / (len(single_rules) * len(nonrule_costs))

print(f"\nrule distances: median {median_rule:.3f}, max {max_rule:.3f}")
print(f"non-rule letter pairs: median {nonrule_costs[len(nonrule_costs)//2]:.3f}")
print(f"AUC (single-grapheme rules vs non-rule pairs): {auc:.3f}")

print("\nmost expensive hand rules (metric disagrees or string rewrite):")
for d, x, y in scored[-8:]:
    print(f"  {d:5.3f}  {x} ↔ {y}")

threshold = median_rule
additions = [(d, a, b) for d, a, b in nonrule if d <= threshold]
print(f"\nnon-rule letter pairs priced ≤ rule median ({threshold:.3f}) — "
      f"the metric's candidate additions ({len(additions)}):")
for d, a, b in additions[:15]:
    print(f"  {d:5.3f}  {a} ↔ {b}")

# --- level 2: real variant pairs in the DB ---------------------------------

con = _dpd.connect()
lemmas = set()
for (lemma,) in con.execute("SELECT lemma_1 FROM dpd_headwords"):
    w = re.sub(r"\s+\d+(\.\d+)?$", "", lemma.strip())
    if re.fullmatch(r"[a-zāīūṅñṭḍṇḷṃ]+", w) and 3 <= len(w) <= 20:
        lemmas.add(w)


def apply_rule(word, x, y):
    if not x:
        return
    start = 0
    while True:
        k = word.find(x, start)
        if k < 0:
            return
        yield word[:k] + y + word[k + len(x):]
        start = k + 1


sample = sorted(lemmas)[::5]  # deterministic 20% sample
pairs = set()
for w in sample:
    for x, y in RULES:
        for a, b in ((x, y), (y, x)):
            for produced in apply_rule(w, a, b):
                if produced != w and produced in lemmas:
                    pairs.add(frozenset((w, produced)))
pairs = [tuple(sorted(p)) for p in pairs]
print(f"\nDB-level: {len(pairs)} real lemma pairs connected by one hand rule"
      f" (20% sample, n={len(sample)})")

theta = max_rule
covered = sum(1 for a, b in pairs if distance(a, b, lenient=True) <= theta + 1e-9)
print(f"metric recall of the hand system at θ = max rule cost ({theta:.3f}): "
      f"{covered / len(pairs):.1%}")
theta2 = median_rule
covered2 = sum(1 for a, b in pairs
               if distance(a, b, lenient=True) <= theta2 + 1e-9)
print(f"at θ = rule median ({theta2:.3f}): {covered2 / len(pairs):.1%}")
