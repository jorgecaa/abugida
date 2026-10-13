"""Every Pāli form of `oberlies_cases.json` (local data), looked for on its own page.

The case file was read by eye from page images, because the scan's OCR text
layer lost the diacritics. That same text layer is still a second witness for
the LETTERS: a Pāli form that cannot be found on the page it is filed under
is a candidate transcription slip, whatever the diacritics.

How a form is looked for. The OCR's own misreadings are modelled rather than
tolerated by a fuzzy score: ā is read as a or d, ī as i, l, f or 1, ṃ as m,
rn or n, ṅ before a velar as h or n (vahka for vaṅka), ñ as n or h (fiana for
ñāṇa). The form, turned into that pattern, must match a whole OCR word on its
page or a neighbouring one, allowing a stray letter or two of OCR noise in
front and up to three letters of ending behind (the book cites stems,
sometimes with a parenthesised part: sisa(ka)-, (a)sekha-).

A second test looks for the case file's own mistake of kind: a pair filed as
Sanskrit -> Pāli whose "Sanskrit" form the page writes as "(~ X)", which is
how the book gives a Pāli VARIANT. In italics that is a Pāli doublet, not a
derivation; the scan has to decide, because the OCR keeps no italics.

What it found on 2026-10-13, every flagged form read against the scan. Three
slips, now corrected in the case file: `punapunaṃ` for the book's
puna-p-punaṃ (p. 45); `paricaryā ~ pāricariyā` filed as Sanskrit -> Pāli
where both are italic Pāli, a doublet (p. 54); and `anupādāya ~ anupādā`
filed as Sanskrit -> Pāli where the book gives anupādā (~ anupādāya), both
Pāli and already among the doublets (p. 55, seen in the image while reading
the neighbouring flags). After the corrections: 866 forms, 787 found, and
the 79 not found are, read one by one, the OCR wrecking the word
(w6/zo for ubho, y7v/*d for jivhā) or the book's bracket notation
(sisa(ka)-, (a)sekha-); the two "(~ X)" hits, kāhiti (~ kariṣyati) and
anopama (~ anūpama ← anupama), have the Sanskrit in roman and are right.
With the 37 doublets added later the same day, 939 forms and 89 not found;
the ten new ones are bracket notation again (kāla[ṃ]kata, (Isi)gili ~
°giri, p(h)alasata, k(h)atta) or a wrecked word (rfzyaft' for dīyati).
It checks letters, not completeness: pairs the book has and the file lacks
(vesiyāna, sampāyati on p. 55; the Pāli doublets anodaka ~ anūdaka and
anopama ~ anūpama on p. 85) are not looked for.

The grammar is in copyright and is not shipped; pass your own copy:

    python eval/validation/ocr_crosscheck.py --pdf PATH/TO/oberlies.pdf

Needs `pdftotext` (poppler). No DPD.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import _data  # noqa: E402


#: How the scan's OCR renders each IAST letter, read off the first pass.
OCR = {
    "ā": "[ad]", "ī": "[ilf1]", "ū": "u", "ṃ": "(?:m|rn|n)",
    "ṅ": "[nhm]", "ñ": "(?:n|h|fi)", "ṭ": "t", "ḍ": "d", "ṇ": "n",
    "ḷ": "[l1]", "ś": "s", "ṣ": "s", "ṛ": "r", "ḥ": "h?", "i": "[il1]",
    "a": "[ad]", "m": "(?:m|rn)", "l": "[l1i]",
}


def fold(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def pattern(word):
    word = unicodedata.normalize("NFC", word.lower())
    core = "".join(OCR.get(ch, re.escape(ch)) for ch in word)
    return re.compile(r"[a-z]{0,2}" + core + r"[a-z]{0,3}")


class Pages:
    def __init__(self, pdf, tmp):
        self.pdf, self.tmp, self.text = pdf, tmp, {}

    def __call__(self, page):
        if page not in self.text:
            out = os.path.join(self.tmp, f"p{page}.txt")
            subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l",
                            str(page), self.pdf, out], check=False,
                           capture_output=True)
            raw = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
            self.text[page] = re.sub(r"-\s*\n\s*", "", raw)  # line-end hyphens
        return self.text[page]

    def words(self, page):
        return [fold(w) for w in
                re.split(r"[\s,;:()\[\]'\"\u2018\u2019\u201c\u201d./°*]+", self(page)) if fold(w)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf", required=True, help="your copy of the grammar")
    args = ap.parse_args()
    if not os.path.exists(args.pdf):
        sys.exit(f"no file at {args.pdf}")
    cases = _data.load("oberlies_cases.json")

    with tempfile.TemporaryDirectory() as tmp:
        pages = Pages(args.pdf, tmp)
        missing, seen = [], set()
        for kind, sides in (("tadbhava", (1,)), ("doublets", (0, 1))):
            for pair, page in zip(cases[kind], cases["pdf_pages"][kind]):
                for i in sides:
                    form = pair[i]
                    if (form, page) in seen:
                        continue
                    seen.add((form, page))
                    rx = pattern(form)
                    pool = [w for q in (page - 1, page, page + 1)
                            for w in pages.words(q)]
                    if not any(rx.fullmatch(w) for w in pool):
                        missing.append((page, form, kind, pair))

        print(f"{len(seen)} forms; {len(seen) - len(missing)} found on their "
              f"page (+-1); {len(missing)} not found — read each in the scan:")
        for page, form, kind, pair in missing:
            print(f"  p{page:<4} {form:<18} {kind:<9} {pair[0]} ~ {pair[1]}")

        print("\nSanskrit -> Pali pairs whose Sanskrit side the page writes as "
              "'(~ X)' (a Pali variant if italic — check the scan):")
        for (skt, pali), page in zip(cases["tadbhava"],
                                     cases["pdf_pages"]["tadbhava"]):
            text = pages(page - 1) + pages(page) + pages(page + 1)
            for m in re.finditer(r"\(\s*~\s*([^\s,;)]+)", text):
                if fold(m.group(1)).rstrip("a") == fold(skt).rstrip("a"):
                    print(f"  p{page:<4} {skt} ~ {pali}")
                    break


if __name__ == "__main__":
    main()
