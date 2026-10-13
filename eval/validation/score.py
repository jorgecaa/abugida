"""Score the review of `oberlies_sample.tsv` against the planted-error key.

Planted errors are the control: a review that misses any of them cannot
vouch for the rows it called clean. Errors found in unplanted rows are real
transcription errors in the local `oberlies_cases.json`. The upper bound on the
error rate is the exact one-sided 95% binomial bound (Clopper-Pearson),
computed by bisection so the script needs no dependency.
"""

import base64
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import _data  # noqa: E402

#: The sample, its pages and its key are drawn from the Oberlies case file and
#: live beside it in the local data directory (`eval/_data.py`, `NOTICE`).
FILES = [os.path.join("validation", n) for n in
         ("oberlies_sample.key.b64", "oberlies_sample.tsv", "oberlies_pages.tsv")]


def upper_bound(errors, n, conf=0.95):
    """Smallest p with P(X <= errors | n, p) <= 1 - conf."""
    def cdf(p):
        return sum(math.comb(n, k) * p**k * (1 - p)**(n - k)
                   for k in range(errors + 1))
    lo, hi = errors / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return hi


def main():
    _data.require(*FILES)
    with open(_data.path(FILES[0])) as fh:
        key = json.loads(base64.b64decode(fh.read()).decode("utf-8"))
    planted = {k["row"]: k for k in key}
    with open(_data.path(FILES[1]), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    blank = [r["row"] for r in rows if not r["verdict"].strip()]
    if blank:
        print(f"{len(blank)} rows have no verdict yet (e.g. row {blank[0]}); "
              "finish the review first.")
        return
    caught = [int(r["row"]) for r in rows
              if int(r["row"]) in planted and r["verdict"].strip() == "wrong"]
    missed = sorted(set(planted) - set(caught))
    print(f"planted errors caught: {len(caught)}/{len(planted)}")
    for m in missed:
        k = planted[m]
        print(f"  missed row {m}: {k['side']} form shown as {k['altered']}, "
              f"true reading {k['original']}")
    for c in caught:
        r = next(x for x in rows if int(x["row"]) == c)
        if r["correct_form"].strip() not in ("", planted[c]["original"]):
            print(f"  row {c}: correction given {r['correct_form']!r}, "
                  f"planted original {planted[c]['original']!r}")
    real = [r for r in rows
            if int(r["row"]) not in planted and r["verdict"].strip() == "wrong"]
    n = len(rows) - len(planted)
    print(f"\nreal transcription errors: {len(real)} in {n} unplanted rows "
          f"({len(real) / n:.1%}; 95% upper bound "
          f"{upper_bound(len(real), n):.1%})")
    for r in real:
        print(f"  row {r['row']} (pdf p. {r['pdf_page']}): "
              f"{r['first']} / {r['second']} -> {r['correct_form']}")
    if missed:
        print("\nThe review missed planted errors, so the clean rows above do "
              "not establish the error rate.")
    with open(_data.path(FILES[2]), encoding="utf-8") as fh:
        pages = list(csv.DictReader(fh, delimiter="\t"))
    done = [p for p in pages if p["pairs_printed_but_missing"].strip()]
    if done:
        have = sum(int(p["pairs_in_sample"]) for p in done)
        miss = sum(int(p["pairs_printed_but_missing"]) for p in done)
        print(f"\ncompleteness on {len(done)} pages: {miss} printed pairs "
              f"missing against {have} extracted "
              f"({have / (have + miss):.1%} of what the pages print)")


if __name__ == "__main__":
    main()
