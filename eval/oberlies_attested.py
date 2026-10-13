"""Which Sanskrit-side forms of the Oberlies pairs are also attested Pāli.

Many of the "Sanskrit" forms in `oberlies_cases.json` are Pāli words
too: Pāli keeps a western reading beside the eastern one (`samāja` beside
`samajja`, `mīyati` beside `miyyati`), so such a pair is ALSO a Pāli doublet —
the very population the metric is built for. Phonotactics cannot find them:
`is_possible` accepts 322 of the 740 Sanskrit forms, `jīryate` and `ācārya`
among them, which are not Pāli words. Attestation can.

DPD is used here as information, never as the judge: a form counts as attested
when it is a DPD headword (`lemma_1`, homonym number stripped) or an inflected
form in DPD's `lookup` table. Attestation says the form exists in Pāli, not
that it is the western reading — a Sanskritism borrowed into Pāli
(`brāhmaṇa`) is attested too — so the output is a list to read, not a
classification.

Whether the two forms mean the same thing does not matter to the metric,
which measures sounds only, so the pairs are not classified further.

Writes `oberlies_attested.json` into the local data directory (`eval/_data.py`): the attested pairs, and the Pāli forms
of the case file DPD does not attest, with their page, to be checked against
the book (a transcription slip, a rare form, or a stem written without its
ending). `eval/oberlies.py` measures the attested pairs as a second set of
Pāli doublets. Needs `--dpd [PATH]`.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import _dpd  # noqa: E402

import _data  # noqa: E402

OUT = _data.path("oberlies_attested.json")


def clean(lemma):
    return re.sub(r"\s+\d+(\.\d+)?$", "", str(lemma).strip())


def main():
    con = _dpd.connect()
    lemmas = {clean(l) for (l,) in con.execute(
        "SELECT lemma_1 FROM dpd_headwords")}
    forms = {k for (k,) in con.execute("SELECT lookup_key FROM lookup")}
    attested = lemmas | forms

    cases = _data.load("oberlies_cases.json")
    hits = []
    for (skt, pali), page in zip(cases["tadbhava"],
                                 cases["pdf_pages"]["tadbhava"]):
        if skt in attested:
            how = "headword" if skt in lemmas else "inflected form"
            hits.append({"first": skt, "second": pali, "pdf_page": page,
                         "attested_as": how,
                         "second_attested": pali in attested})
    unattested = []
    seen = set()
    for kind, sides in (("tadbhava", (1,)), ("doublets", (0, 1))):
        for pair, page in zip(cases[kind], cases["pdf_pages"][kind]):
            for i in sides:
                w = pair[i]
                if w not in attested and w not in seen:
                    seen.add(w)
                    unattested.append({"form": w, "pdf_page": page,
                                       "pair": pair, "kind": kind})
    out = {
        "note": ("Sanskrit-side forms of oberlies_cases.json that DPD "
                 "attests as Pali (headword or inflected form). Attested is "
                 "not 'western reading': read each pair before using it as a "
                 "Pali doublet."),
        "dpd": {"headwords": len(lemmas), "lookup_forms": len(forms)},
        "pairs": hits,
        "unattested_pali": unattested,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    n = len(cases["tadbhava"])
    print(f"DPD: {len(lemmas):,} headwords, {len(forms):,} lookup forms")
    print(f"Sanskrit-side forms attested as Pali: {len(hits)} of {n} pairs "
          f"({sum(h['attested_as'] == 'headword' for h in hits)} as headwords)")
    for h in hits:
        print(f"  p.{h['pdf_page']:<4} {h['first']} ~ {h['second']}"
              f"   ({h['attested_as']})")
    print(f"\nPali forms of the case file NOT attested in DPD: "
          f"{len(unattested)} (check each against the page)")
    for u in unattested:
        print(f"  p.{u['pdf_page']:<4} {u['form']:<18} in {u['kind']} "
              f"{u['pair'][0]} ~ {u['pair'][1]}")
    print(f"\nwritten {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
