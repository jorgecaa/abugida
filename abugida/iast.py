"""Representation layer: IAST as the canonical form of Pāli.

`normalize` is Python and stays Python: NFC composition and case folding need
the Unicode character database, and vendoring it to compute a distance would
be a far larger dependency than the metric itself. Everything downstream —
`tokenize`, and therefore `diagnose`, `distance`, `alignment` — runs on the C
core when the extension is present (`abugida.distance.USING_C`), because
tokenisation is on the hot path and longest-match over a byte trie is what C
is for. The public behaviour is identical either way: `tests/test_c_parity.py`
compares the two tokenisers over the whole alphabet and over a sample that
includes every digraph and every opaque character.

See SPEC.md §7. The native scripts of Pāli are abugidas (the unit is the
akṣara: a consonant with an inherent `a`); IAST is the phonemic pivot that
dissolves that complication — a flat representation, one grapheme to one
phoneme, with no inherent vowel.

The one-to-one mapping has two caveats, both absorbed here:

- The aspirated digraphs (kh, gh, …, bh) are two Unicode characters and a
  single phoneme: longest-match tokenisation.
- Unicode: input is normalised to NFC (ṃ composed U+1E43 == m + U+0323
  decomposed) and the ṁ (U+1E41) variant of the niggahīta is accepted.

A note on ḷh (ruḷha, aḷhaka…): the inventory follows the traditional
41-sound alphabet, where ḷh is analysed as the cluster ḷ + h, and it is
tokenised that way. Should it ever be treated as a phoneme of its own (an
aspirated retroflex lateral), it must be added here and to the inventory
together.
"""

from __future__ import annotations

import unicodedata
from typing import List, Tuple

from .embed import Vector, embed
from .phonology import BY_GRAPHEME, Phoneme

try:  # pragma: no cover - the branch taken depends on the build
    from . import _cabugida as _c
except ImportError:  # pragma: no cover
    _c = None

#: Valid graphemes, sorted longest first for longest-match tokenisation.
_GRAPHEMES = sorted(BY_GRAPHEME, key=len, reverse=True)
_MAX_LENGTH = max(len(g) for g in _GRAPHEMES)

#: Accepted orthographic variants → canonical form.
_VARIANTS = {"ṁ": "ṃ"}

#: Editorial marks dropped without complaint: the compound hyphen and the
#: elision apostrophe (evaṁ'me, tass'eva).
_IGNORED = "-'’"

#: IAST diacritics that betray Sanskrit rather than Pāli. They are rejected
#: with their own message: Pāli ḷ is the retroflex lateral, not the Sanskrit
#: vocalic ḷ, and ṛ ṝ ṣ ś do not exist in Pāli.
_NOT_PALI = set("ṛṝṣś")


def normalize(text: str) -> str:
    """NFC + lowercase + canonical variants. Idempotent."""
    text = unicodedata.normalize("NFC", text).lower()
    for variant, canonical in _VARIANTS.items():
        text = text.replace(variant, canonical)
    return text


def tokenize(word: str, lenient: bool = False) -> List[str]:
    """Split an IAST word into graphemes of the inventory.

    The C tokeniser when it is built, the scan below otherwise; identical
    results, checked exactly by `tests/test_c_parity.py`.

    Longest match: in `saṅgha`, what follows ṅ is `gh` (one phoneme), not
    `g` + `h`. There is no converse ambiguity in Pāli: word-internally, a
    stop followed by h is always the aspirate.

    Strict by default: characters outside the Pāli alphabet raise
    `ValueError` — rejecting Sanskrit diacritics and garbage is a guarantee,
    not a limitation. With `lenient=True` (for typo-tolerant search
    frontends) each such character is kept as a single-character OPAQUE
    token instead: the comparator treats it as maximally distant from every
    real grapheme, so the intact remainder of the word still discriminates.
    Use `diagnose` to report what was absorbed.
    """
    word = normalize(word)
    if _c is not None:
        return _c.tokenize(word, lenient)
    tokens: List[str] = []
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in _IGNORED or ch.isspace():
            i += 1
            continue
        if ch in _NOT_PALI:
            if lenient:
                tokens.append(ch)
                i += 1
                continue
            raise ValueError(f"{ch!r} in {word!r} is Sanskrit IAST, not Pāli")
        matched = 0
        for length in range(min(_MAX_LENGTH, len(word) - i), 0, -1):
            candidate = word[i : i + length]
            if candidate in BY_GRAPHEME:
                tokens.append(candidate)
                matched = length
                break
        if matched:
            i += matched
            continue
        if lenient:
            tokens.append(ch)
            i += 1
            continue
        raise ValueError(f"{ch!r} in {word!r} is not a Pāli grapheme")
    return tokens


def diagnose(word: str) -> List[Tuple[int, str, str]]:
    """Report the characters that strict tokenisation would reject.

    Returns a list of (index, character, kind) over the NORMALISED text,
    with kind ∈ {"sanskrit", "unknown"}. Never raises: an empty list means
    the word tokenises strictly. This is the reporting half of typo
    support — `tokenize(..., lenient=True)` is the comparing half.
    """
    word = normalize(word)
    if _c is not None:
        return _c.diagnose(word)
    problems: List[Tuple[int, str, str]] = []
    i = 0
    while i < len(word):
        ch = word[i]
        # The same two predicates `tokenize` skips with, and for the same
        # reason: a character tokenisation silently drops is not one that
        # strict tokenisation "would reject", which is what this reports. The
        # C core's `abugida_diagnose` skips with the identical pair, so the
        # two paths agree by construction rather than by inspection.
        if ch in _IGNORED or ch.isspace():
            i += 1
            continue
        if ch in _NOT_PALI:
            problems.append((i, ch, "sanskrit"))
            i += 1
            continue
        matched = 0
        for length in range(min(_MAX_LENGTH, len(word) - i), 0, -1):
            if word[i : i + length] in BY_GRAPHEME:
                matched = length
                break
        if matched:
            i += matched
        else:
            problems.append((i, ch, "unknown"))
            i += 1
    return problems


def transcribe(word: str) -> Tuple[Phoneme, ...]:
    """IAST word → sequence of phonemes from the inventory."""
    return tuple(BY_GRAPHEME[t] for t in tokenize(word))


def vectors(word: str) -> List[Vector]:
    """IAST word → sequence of embeddings (12 dims per phoneme)."""
    return [embed(p) for p in transcribe(word)]
