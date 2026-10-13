"""Morphologically viable candidates: root + base + ending.

`phonotactics.pseudoword` answers "could this be a Pāli word?" at the level
of SEQUENCES: it knows dharma is impossible and dhamma is not. It does not
ask whether the string could be *formed* — a legal syllable sequence is not
yet a word anyone could inflect. This module adds that second criterion, as
an OPTIONAL alternative generator, not a replacement: `pseudoword` remains
the phonotactic baseline and the evaluations that cite it keep their
numbers.

A form here is built the way the grammarians build one (Kaccāyana's kita and
vibhatti sections; Duroiselle §§ 400ff.; Warder ch. 1-4):

    dhātu (root)  →  aṅga (base)  →  vibhatti (ending)
    pac           →  paca         →  -ti        →  pacati
    pac           →  pacana       →  -assa      →  pacanassa
    kar           →  karo         →  -nti       →  karonti

The bases are DECLARED, not derived. Present-stem formation involves guṇa,
vuddhi and class-specific infixes that no small rule set reproduces
honestly, so `ROOTS` records each root's attested present base alongside its
gaṇa — the same policy `alphabet.py` applies to the avagga order: declare
convention as convention rather than dress it up as a theorem. What IS
derived is everything downstream: the secondary (kita) bases, the junction
rules, and the phonotactic filter every output must pass.

Novelty comes from CROSSING: the generator combines bases and endings that
the canon happens not to combine, so most outputs are unattested yet
formable. That is the intended product — a candidate that a Pāli speaker
could parse, decline and gloss, whether or not any dictionary records it.

    >>> import random
    >>> f = pseudoform(random.Random(0))
    >>> f.word, f.root, f.base, f.ending, f.category  # doctest: +SKIP
    ('taraṇesu', 'tar', 'taraṇa', 'esu', 'loc pl m/n')

Scope, stated plainly: this models word FORMATION, not the history of any
particular word. Junction handles hiatus, the length alternation before
clusters, -hi lengthening and coronal retroflexion; it does not model
consonant loss (kar + ta → kata) or the assimilations that reshaped
inherited clusters. Forms whose junction would fall outside the
phonotactics are dropped rather than repaired, so `is_possible` holds for
every word this module yields.
"""

from __future__ import annotations

from typing import Iterator, List, NamedTuple, Optional, Sequence

from .iast import tokenize
from .phonology import CEREBRAL, DENTAL, BY_GRAPHEME
from .phonotactics import is_possible

_VOWELS = frozenset("aāiīuūeo")

#: Coronal obstruents and nasals block retroflexion (see `_retroflex`). Taken
#: from the inventory's places, not listed by hand: the same tongue-tip class
#: the embedding gives its own CORONAL dimension.
_CORONAL = frozenset(
    g for g, p in BY_GRAPHEME.items()
    if p.places & {CEREBRAL, DENTAL} and g not in _VOWELS and g != "r"
)

_SHORTEN = {"ā": "a", "ī": "i", "ū": "u"}
_LENGTHEN = {"a": "ā", "i": "ī", "u": "ū"}

#: The guṇa base vowels (curādi -e, tanādi -o): they carry the class and
#: survive hiatus, unlike a thematic -a. See `join`.
_GUNA = frozenset({"e", "o"})

#: Endings before which the base vowel lengthens (Duroiselle § 424): the
#: first-person endings and the imperative 2sg -hi. pacati but pacāmi,
#: pacāma, pacāmhe, pacāhi.
_LENGTHENING_ENDINGS = frozenset({"mi", "ma", "mhe", "hi"})


class Root(NamedTuple):
    """A verbal root with its attested present base and class.

    `stem` is the aṅga as the grammars give it (bhū → bhava, gam → gaccha,
    su → suṇā): declared datum, not a derivation.
    """

    root: str
    stem: str
    gana: str
    gloss: str


class Formation(NamedTuple):
    """A generated form and the analysis that produced it — the receipt.

    `distance` has `alignment`; the generator has this: nothing about a
    candidate is unexplained, so a rejected form can always be argued with.
    """

    word: str
    root: str
    base: str
    ending: str
    category: str
    kind: str  # "verb" or "noun"

    def __str__(self) -> str:
        return (f"{self.word} < {self.root} + {self.base} + -{self.ending} "
                f"({self.category})")


# --- The roots (dhātu) -----------------------------------------------------
# Seven traditional gaṇa, each with its own present formation. The sample is
# deliberately ordinary vocabulary: common roots make the crossings legible.

ROOTS = (
    # bhūvādigaṇa: base in -a, with guṇa of the root vowel
    Root("bhū", "bhava", "bhūvādi", "to be"),
    Root("pac", "paca", "bhūvādi", "to cook"),
    Root("gam", "gaccha", "bhūvādi", "to go"),
    Root("car", "cara", "bhūvādi", "to walk"),
    Root("vad", "vada", "bhūvādi", "to say"),
    Root("labh", "labha", "bhūvādi", "to obtain"),
    Root("has", "hasa", "bhūvādi", "to laugh"),
    Root("dhāv", "dhāva", "bhūvādi", "to run"),
    Root("vas", "vasa", "bhūvādi", "to dwell"),
    Root("rakkh", "rakkha", "bhūvādi", "to guard"),
    Root("nam", "nama", "bhūvādi", "to bend"),
    Root("tap", "tapa", "bhūvādi", "to burn"),
    Root("khād", "khāda", "bhūvādi", "to eat"),
    Root("jīv", "jīva", "bhūvādi", "to live"),
    Root("har", "hara", "bhūvādi", "to carry"),
    Root("sar", "sara", "bhūvādi", "to remember"),
    Root("mar", "mara", "bhūvādi", "to die"),
    Root("tar", "tara", "bhūvādi", "to cross"),
    Root("ṭhā", "tiṭṭha", "bhūvādi", "to stand"),
    Root("pā", "piva", "bhūvādi", "to drink"),
    Root("dis", "passa", "bhūvādi", "to see"),
    # rudhādigaṇa: nasal infix before the final consonant
    Root("rudh", "rundha", "rudhādi", "to obstruct"),
    Root("chid", "chinda", "rudhādi", "to cut"),
    Root("bhid", "bhinda", "rudhādi", "to break"),
    Root("muc", "muñca", "rudhādi", "to release"),
    Root("lip", "limpa", "rudhādi", "to smear"),
    # divādigaṇa: suffix -ya, assimilated to the root final
    Root("budh", "bujjha", "divādi", "to awaken"),
    Root("man", "mañña", "divādi", "to think"),
    Root("div", "dibba", "divādi", "to play"),
    Root("muh", "muyha", "divādi", "to be confused"),
    # svādigaṇa: suffix -ṇā / -uṇā
    Root("su", "suṇā", "svādi", "to hear"),
    Root("āp", "pāpuṇā", "svādi", "to attain"),
    # kiyādigaṇa: suffix -nā
    Root("ñā", "jānā", "kiyādi", "to know"),
    Root("ji", "jinā", "kiyādi", "to conquer"),
    Root("kī", "kiṇā", "kiyādi", "to buy"),
    Root("dhu", "dhunā", "kiyādi", "to shake"),
    # tanādigaṇa: suffix -o
    Root("kar", "karo", "tanādi", "to do"),
    Root("tan", "tano", "tanādi", "to stretch"),
    # curādigaṇa: suffix -e (the -aya variant is the same base)
    Root("cur", "core", "curādi", "to steal"),
    Root("cint", "cinte", "curādi", "to think"),
    Root("pūj", "pūje", "curādi", "to honour"),
    Root("kath", "kathe", "curādi", "to relate"),
    Root("dhar", "dhāre", "curādi", "to hold"),
)

# --- Endings (vibhatti) ----------------------------------------------------

#: Person/number, in the grammars' order: 3sg 3pl 2sg 2pl 1sg 1pl.
_PERSONS = ("3sg", "3pl", "2sg", "2pl", "1sg", "1pl")

PRESENT_ACTIVE = ("ti", "nti", "si", "tha", "mi", "ma")
PRESENT_MIDDLE = ("te", "nte", "se", "vhe", "e", "mhe")
IMPERATIVE = ("tu", "antu", "hi", "tha", "mi", "ma")
#: Optative and future attach to the consonantal base, not the present one.
OPTATIVE = ("eyya", "eyyuṃ", "eyyāsi", "eyyātha", "eyyāmi", "eyyāma")
FUTURE_INFIX = "issa"

#: Vowel-initial endings; the base vowel elides before them (see `join`).
A_STEM_CASES = (
    ("o", "nom sg m"), ("aṃ", "acc sg m/n"), ("ena", "instr sg"),
    ("assa", "dat/gen sg"), ("asmā", "abl sg"), ("asmiṃ", "loc sg"),
    ("ā", "nom pl m"), ("e", "acc pl m"), ("ehi", "instr pl"),
    ("ānaṃ", "gen pl"), ("esu", "loc pl"),
)

A_STEM_CASES_N = (("aṃ", "nom/acc sg n"), ("āni", "nom/acc pl n"))

AA_STEM_CASES = (
    ("ā", "nom sg f"), ("aṃ", "acc sg f"), ("āya", "instr/dat/gen sg f"),
    ("āyaṃ", "loc sg f"), ("āyo", "nom/acc pl f"), ("āhi", "instr pl f"),
    ("ānaṃ", "gen pl f"), ("āsu", "loc pl f"),
)

#: Primary (kita) suffixes: root → nominal base. Each is regular on the
#: consonantal base, which is why these and not the irregular agent suffix
#: -tar (kar → kattā) or the -ti abstracts (gam → gati), whose formation
#: involves the consonant losses this module does not model.
KITA = (
    ("ana", "action noun", "a"),
    ("aka", "agent noun", "a"),
    ("anta", "present participle", "a"),
    ("ita", "past participle", "a"),
    ("itabba", "gerundive", "a"),
    ("anā", "action noun f", "ā"),
)


# --- Junction --------------------------------------------------------------


def _is_vowel(token: str) -> bool:
    return token in _VOWELS


def consonantal(stem: str) -> str:
    """The base stripped of its final vowel — what optative, future and the
    kita suffixes attach to (paca → pac, karo → kar, jānā → jān)."""
    tokens = tokenize(stem)
    if tokens and _is_vowel(tokens[-1]):
        return "".join(tokens[:-1])
    return stem


def join(base: str, ending: str) -> str:
    """Attach an ending to a base, applying the junction rules.

    Three alternations, all standard and all conditioned by the shape of the
    junction rather than by the identity of the morphemes:

    1. HIATUS — one of the two vowels goes. The base loses its own (paca +
       antu → pacantu, pacana + ena → pacanena), except after the guṇa
       bases in -e and -o, which are what marks their class and so survive
       at the ending's expense: karo + antu → karontu, core + antu →
       corentu.
    2. LENGTHENING — the base vowel lengthens before the first-person
       endings and the imperative 2sg: paca + mi → pacāmi, paca + hi →
       pacāhi, paca + mhe → pacāmhe.
    3. SHORTENING before a cluster — otherwise a long final vowel shortens
       before a consonant cluster, Pāli admitting no long vowel before a
       double consonant: jānā + nti → jānanti.
    """
    tb, te = tokenize(base), tokenize(ending)
    if not tb or not te:
        return base + ending
    last, first = tb[-1], te[0]
    if _is_vowel(last):
        if _is_vowel(first):
            if last in _GUNA and len(te) > 1:
                te = te[1:]
            else:
                # A one-vowel ending (middle 1sg -e) would vanish entirely
                # and leave the bare base, so there the base yields instead:
                # karo + e → kare.
                tb = tb[:-1]
        elif ending in _LENGTHENING_ENDINGS:
            tb = tb[:-1] + [_LENGTHEN.get(last, last)]
        elif len(te) >= 2 and not _is_vowel(te[1]) and last in _SHORTEN:
            tb = tb[:-1] + [_SHORTEN[last]]
    return "".join(tb + te)


def _retroflex(word: str) -> str:
    """Coronal retroflexion (nati): an intervocalic n becomes ṇ after r in
    the same base, unless a coronal intervenes.

    kar + ana → karaṇa, car + ana → caraṇa, sar + ana → saraṇa — while
    rundh + ana stays rundhana, the intervening n and dh blocking it. The
    blocking class is read off the inventory's places, not listed by hand.
    """
    tokens = tokenize(word)
    seen_r = False
    for i, t in enumerate(tokens):
        if t == "r":
            seen_r = True
        elif t in _CORONAL:
            if t == "n" and seen_r and 0 < i < len(tokens) - 1 \
                    and _is_vowel(tokens[i - 1]) and _is_vowel(tokens[i + 1]):
                tokens[i] = "ṇ"
            seen_r = False
    return "".join(tokens)


# --- Generation ------------------------------------------------------------


def _emit(root: Root, base: str, ending: str, category: str, kind: str
          ) -> Optional[Formation]:
    """Build a formation, or None if the junction leaves the phonotactics."""
    word = join(base, ending)
    if not word or not is_possible(word):
        return None
    return Formation(word, root.root, base, ending, category, kind)


def verb_forms(root: Root) -> Iterator[Formation]:
    """Every finite form this module builds for a root: present (both
    voices), imperative, optative and future."""
    cons = consonantal(root.stem)
    tables = (
        (root.stem, PRESENT_ACTIVE, "pres act"),
        (root.stem, PRESENT_MIDDLE, "pres mid"),
        (root.stem, IMPERATIVE, "imper"),
        (cons, OPTATIVE, "opt"),
        (cons + FUTURE_INFIX, PRESENT_ACTIVE, "fut"),
    )
    for base, endings, label in tables:
        for person, ending in zip(_PERSONS, endings):
            form = _emit(root, base, ending, f"{label} {person}", "verb")
            if form is not None:
                yield form


def nominal_bases(root: Root) -> Iterator[tuple]:
    """The kita bases of a root: (base, declension, gloss of the suffix)."""
    cons = consonantal(root.stem)
    for suffix, sense, declension in KITA:
        base = _retroflex(join(cons, suffix))
        if is_possible(base):
            yield (base, declension, sense)


def noun_forms(root: Root) -> Iterator[Formation]:
    """Every declined form built from a root's kita bases."""
    for base, declension, sense in nominal_bases(root):
        cases = AA_STEM_CASES if declension == "ā" else (
            A_STEM_CASES + A_STEM_CASES_N)
        for ending, category in cases:
            form = _emit(root, base, ending, f"{sense}, {category}", "noun")
            if form is not None:
                yield form


def formations(roots: Optional[Sequence[Root]] = None) -> Iterator[Formation]:
    """Every form the generator can build, in a deterministic order."""
    for root in (ROOTS if roots is None else roots):
        yield from verb_forms(root)
        yield from noun_forms(root)


_ALL: Optional[List[Formation]] = None


def _all_forms() -> List[Formation]:
    global _ALL
    if _ALL is None:
        _ALL = list(formations())
    return _ALL


def pseudoform(rng, kind: Optional[str] = None) -> Formation:
    """A random morphologically viable form, with its analysis.

    `rng` is a random.Random supplied by the caller (determinism stays under
    their control), as in `phonotactics.pseudoword`. `kind` restricts to
    "verb" or "noun"; the default draws from both.

    Every word returned satisfies `is_possible` — the phonotactics are the
    floor here, not the ceiling: this generator adds formability on top,
    and never trades it away.
    """
    if kind is None:
        pool = _all_forms()
    elif kind in ("verb", "noun"):
        pool = [f for f in _all_forms() if f.kind == kind]
    else:
        raise ValueError(f"kind must be 'verb', 'noun' or None: {kind!r}")
    return rng.choice(pool)


# --- Analysis: the criterion applied to a string it did not build ---------

#: Every ending the generator can attach, longest first so that the analysis
#: prefers the most specific parse (-asmiṃ before -aṃ).
ENDINGS = tuple(sorted(
    {e for e in PRESENT_ACTIVE + PRESENT_MIDDLE + IMPERATIVE + OPTATIVE}
    | {e for e, _ in A_STEM_CASES + A_STEM_CASES_N + AA_STEM_CASES},
    key=len, reverse=True,
))


def analyse(word: str) -> List[tuple]:
    """Every (base, ending) split of a word into an aṅga and a vibhatti.

    The generator's criterion turned around and applied to a string it did
    not build. A split counts when the ending is one the system knows and
    what precedes it is a possible base: non-empty and containing a vowel,
    so that a bare consonant cluster cannot pass as a stem.

    This is a NECESSARY condition for formability, not a sufficient one: it
    certifies that the word ends in a real ending over a syllabic base, not
    that any root would produce that base. Returns an empty list when no
    split works.
    """
    word = "".join(tokenize(word, lenient=True))
    splits = []
    for ending in ENDINGS:
        if not word.endswith(ending) or len(word) == len(ending):
            continue
        base = word[: len(word) - len(ending)]
        tokens = tokenize(base, lenient=True)
        if tokens and any(_is_vowel(t) for t in tokens):
            splits.append((base, ending))
    return splits


def is_formable(word: str) -> bool:
    """Could this string be a Pāli word MORPHOLOGICALLY — a base plus an
    ending — and not merely a legal sequence of syllables?

    The second criterion, standing beside `phonotactics.is_possible`:

        >>> is_possible("kaṭubha"), is_formable("kaṭubha")
        (True, False)
        >>> is_possible("pacati"), is_formable("pacati")
        (True, True)
    """
    return is_possible(word) and bool(analyse(word))


def pseudoword_morphological(rng, kind: Optional[str] = None) -> str:
    """`pseudoform` without the analysis — the drop-in shape of
    `phonotactics.pseudoword`, for callers that only want the string."""
    return pseudoform(rng, kind).word
