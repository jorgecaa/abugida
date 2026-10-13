"""The C core and the Python reference must agree.

This is the test that makes a second implementation safe. Every published
figure in the project was measured with the pure-Python metric; the package
now computes with the C core, and the two are required to return the same
answers: the same tokens, the same operations, the same exceptions, and the
same doubles to within `TOLERANCE`.

What is compared, and why each is here:

- **The cost table**, over every ordered pair of tokens, against
  `_pure.cost` evaluated now. The C table is generated from that function,
  so this catches a stale generated file as well as a generator bug.
- **The tokeniser**, over the alphabet, every digraph, every doubled form,
  every pair of graphemes and a sweep of characters outside the inventory.
- **`distance`, `levenshtein` and `alignment`** over a fixed-seed corpus,
  the last operation by operation: two optimal alignments can both be
  correct and only one is the same answer, and `edit_tag` publishes
  whichever comes out.
- **`diagnose`**, against an independent re-implementation here rather than
  against `_pure` — a reporting function that shares code with the thing it
  reports on is not a check.
- **The generated files themselves**: `tools/generate_c_tables.py --check`
  must report them up to date, so the C tables cannot drift from the Python
  definitions by an edit to either side.
- **The constants**: INDEL_WEIGHT and ONE_MOVE as the C core holds them
  against the values the reference derives at import time.

Why a tolerance, and why this one. The C core reads its costs from the
committed tables, so it returns the same doubles on every platform. The
reference recomputes each cost at run time with the platform's `acos` and
`sqrt`, and the C libraries of Linux, macOS and Windows round those
differently in the last bit: measured on the CI runners, up to 3 ulp
(0.746063891461822 against 0.7460638914618217 for bh~a on macOS). On the
platform the tables were generated on (Linux, glibc) the two agree bit for
bit, on every Python version — `embed.cosine` sums with `math.fsum` so that
the interpreter's `sum` (compensated since 3.12) cannot move a bit either.
`TOLERANCE` is the 1e-12 the traceback already uses to compare path costs,
some four orders of magnitude above the libm noise.
"""

import itertools
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from abugida import _pure
from abugida.alphabet import ALPHABET
from abugida.distance import (
    USING_C,
    alignment as _alignment_public,
    cost,
    distance,
    levenshtein,
)
from abugida.iast import diagnose, normalize, tokenize
from abugida.lexicon import phonological_form
from abugida.sandhi import assimilate_word, contract_word

class PUB:
    """The SHIPPED surface — the names a caller reaches through
    `abugida.distance`, `abugida.iast` and `abugida.sandhi`, as opposed to
    `_pure`, which is the reference implementation. The mirror claim is about
    these two facing each other; the bare binding `_c` is a lower layer with a
    narrower documented contract."""

    tokenize = staticmethod(tokenize)
    diagnose = staticmethod(diagnose)
    assimilate_word = staticmethod(assimilate_word)
    contract_word = staticmethod(contract_word)
    phonological_form = staticmethod(phonological_form)
    distance = staticmethod(distance)
    levenshtein = staticmethod(levenshtein)
    alignment = staticmethod(_alignment_public)
    cost = staticmethod(cost)
from abugida.lexicon import ONE_MOVE
from abugida.phonology import BY_GRAPHEME, FOREIGN, INVENTORY
from abugida.sandhi import CONTRACTIONS

ROOT = Path(__file__).resolve().parent.parent

#: The extension is a build artefact: without it this whole file is about a
#: comparison that cannot be made, and saying so is better than 30 failures.
pytestmark = pytest.mark.skipif(
    not USING_C, reason="the C extension is not built (pip install -e .)"
)

if USING_C:  # pragma: no cover - exercised only with the extension built
    from abugida import _cabugida as _c


#: A fixed seed, the project's convention (CLAUDE.md).
SEED = 20260801

#: How far a double from the C core may sit from the reference's (see the
#: module docstring): the traceback's own tie tolerance.
TOLERANCE = 1e-12


def same(x, y):
    """Equal, with floats compared to within `TOLERANCE` and everything else
    (tokens, operation names, exception kinds, shapes) compared exactly."""
    if isinstance(x, float) or isinstance(y, float):
        return (isinstance(x, (int, float)) and isinstance(y, (int, float))
                and math.isclose(x, y, rel_tol=TOLERANCE, abs_tol=TOLERANCE))
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
        return (type(x) is type(y) and len(x) == len(y)
                and all(same(a, b) for a, b in zip(x, y)))
    return x == y

#: Attested words covering the whole alphabet, both digraph lengths, the
#: heavy units, the epenthetic classes and the sandhi pipeline's own
#: material.
WORDS = [
    "aṭṭha", "upekkhā", "kamma", "citta", "chanda", "jaḷa", "jhāna",
    "ṭhāna", "thūpa", "nibbāna", "paññā", "paṇḍita", "phala", "buddha",
    "bhava", "yoga", "vuḍḍhi", "saṅgha", "saṃsāra", "sīha", "attha",
    "atha", "magga", "makka", "kāma", "gacchati", "gacchanti", "sve",
    "suve", "idāni", "dāni", "uṭṭhita", "vuṭṭhita", "sakiṃ", "saki",
    "dhamma", "dharma", "mettaṃ", "metta", "vikkhambhati", "vikhambhati",
    "abhibhavati", "abhibhoti", "anavakāsa", "anokāsa", "bhāvayitvā",
    "bhāvetvā", "soḷasa", "sola", "ñāṇa", "khanti", "kanti", "ruḷha",
]


def corpus():
    """The attested words plus fixed-seed draws from the inventory, which is
    what reaches the awkward token sequences no word list contains."""
    rng = random.Random(SEED)
    letters = [p.grapheme for p in ALPHABET]
    random_words = [
        "".join(rng.choice(letters) for _ in range(rng.randint(0, 12)))
        for _ in range(120)
    ]
    return WORDS + random_words


# --- the vocabulary and the constants -------------------------------------

def test_generated_tables_are_up_to_date():
    """`--check` re-runs the generator and compares the text exactly and the
    numbers to within its CHECK_TOLERANCE. A cost change in Python that nobody
    regenerated fails here rather than quietly leaving the C core on the old
    scale."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "generate_c_tables.py"),
         "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_constants_agree():
    assert same(_c.INDEL_WEIGHT, _pure.INDEL_WEIGHT)
    assert same(_c.ONE_MOVE, _pure.ONE_MOVE)
    assert same(_c.NEUTRAL_MODIFIER_WEIGHT, _pure.NEUTRAL_MODIFIER_WEIGHT)
    assert ONE_MOVE == _c.ONE_MOVE


def test_token_ids_are_the_reference_order():
    """Token id order is the generator's, and the generator's is the order
    the reference's own tables imply: the inventory by character length, then
    the heavy units, then the Sanskrit phonemes."""
    expected = (
        sorted(BY_GRAPHEME, key=lambda g: (-len(g), g))
        + sorted(_pure._UNITS, key=lambda g: (-len(g), g))
        + sorted(FOREIGN)
    )
    assert [_c.text_of(i) for i in range(len(expected))] == expected
    assert len(INVENTORY) == _c.NPLAIN
    assert len(expected) == _c.NTOKENS


# --- the cost table -------------------------------------------------------

def test_cost_table_matches_the_reference_exactly():
    """Every ordered pair of tokens, against `_pure.cost` computed now.

    This is the strongest statement in the file: the C table IS the Python
    function over its whole domain — including the long consonants, which the
    reference reaches through `_vector` and which no word ever spells
    directly, and the Sanskrit phonemes."""
    tokens = [_c.text_of(i) for i in range(_c.NTOKENS)]
    for a, b in itertools.product(tokens, repeat=2):
        assert same(_c.cost(a, b), _pure.cost(a, b)), (a, b)


def test_the_three_out_of_inventory_classes_price_alike():
    """Opaque typos, the Sanskrit phonemes (real phonology: ṣ↔s is 0.460) and
    the long consonants (consonant length, not deletion)."""
    pairs = [
        ("q", "k"), ("x", "q"), ("*", "a"), ("q", "q"),
        ("ṣ", "s"), ("ś", "s"), ("ṛ", "a"), ("ṣ", "ś"),
        ("ṭṭ", "ṭ"), ("tth", "th"), ("kk", "k"), ("bhbh", "bh"),
    ]
    for a, b in pairs:
        assert same(_c.cost(a, b), _pure.cost(a, b)), (a, b)


def test_indel_weights_match():
    tokens = [_c.text_of(i) for i in range(_c.NTOKENS)]
    for token in tokens:
        assert same(_c.indel(token), _pure._indel(token)), token


# --- the tokeniser --------------------------------------------------------

def test_tokeniser_matches_over_the_alphabet():
    """Every grapheme, every digraph, every grapheme pair and every doubled
    form. The pairs are what catch a longest-match disagreement, which is
    the failure mode a byte-oriented scanner invites."""
    letters = [p.grapheme for p in ALPHABET]
    candidates = list(letters)
    candidates += [a + b for a, b in itertools.product(letters, repeat=2)]
    candidates += sorted(_pure._GEMINATE_BASES)
    for word in candidates:
        assert tokenize(word, lenient=True) == _pure.tokenize(word, True), word
        assert _c.Tokens.from_text(word, True).texts() == \
            _pure.tokenize(word, True), word


def test_tokeniser_matches_on_opaque_characters():
    """Characters outside the alphabet: strict raises in both, lenient
    absorbs in both, and the absorbed token decodes back to the character it
    stands for — which is what a lenient caller sees in an alignment."""
    # ñ is in the inventory and ṭh is a grapheme; these are not. `w` is here
    # because a letter that looks harmless is exactly the case a scanner
    # written for Pāli has to refuse anyway.
    for ch in ["q", "x", "w", "*", "?", "!", "0", "\u2014", "\u2019x"]:
        for word in (ch, "ka" + ch, ch + "mma", "ka" + ch + "ma"):
            with pytest.raises(ValueError):
                tokenize(word)
            with pytest.raises(ValueError):
                _pure.tokenize(word)
            assert tokenize(word, lenient=True) == _pure.tokenize(word, True), word
            assert _c.Tokens.from_text(word, True).texts() == \
                _pure.tokenize(word, True), word


def test_tokeniser_matches_over_the_corpus():
    for word in corpus():
        assert tokenize(word, lenient=True) == _pure.tokenize(word, True), word
        assert _c.token_ids(word) == _c.ids_of(_pure.tokenize(word, True)), word


def test_the_sanskrit_phonemes_are_priced_not_absorbed():
    """The distinction the tokeniser has to make: ṛ ṣ ś carry phonology and
    become tokens in lenient mode, while a genuine typo stays opaque. If the
    core treated Sanskrit as a typo this test would fail on the cost."""
    for word, foreign in [("kṛṣṇa", 2), ("śānti", 1), ("qamma", 0)]:
        ids = _c.token_ids_lenient(word) if hasattr(_c, "token_ids_lenient") \
            else _c.Tokens.from_text(word, True).ids()
        assert sum(1 for i in ids if i >= _c.NPLAIN) == foreign, word
    strict = [w for w in ("kṛṣṇa", "śānti") if not _raises_tokenize(w)]
    assert strict == []


def _raises_tokenize(word):
    try:
        tokenize(word)
    except ValueError:
        return True
    return False


# --- diagnose, against an independent implementation ----------------------

def reference_diagnose(word):
    """`diagnose`, re-derived here from the inventory rather than borrowed
    from either implementation: it walks the normalised text, skips what
    tokenisation skips, and asks whether any grapheme starts at each
    position. A reporting function that shares code with the thing it reports
    on is not a check."""
    text = normalize(word)
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "-'’" or ch.isspace():
            i += 1
            continue
        if ch in "ṛṝṣś":
            out.append((i, ch, "sanskrit"))
            i += 1
            continue
        if any(text[i:i + n] in BY_GRAPHEME for n in (2, 1)):
            # Longest match: consume the whole grapheme.
            i += 2 if text[i:i + 2] in BY_GRAPHEME else 1
            continue
        out.append((i, ch, "unknown"))
        i += 1
    return out


def test_diagnose_matches_an_independent_implementation():
    words = ["dhamma", "qamma", "kṛṣṇa", "Saṁyutta-Nikāya", "śānti",
             "aṭṭha", "ka*qa", "x", "??", "tass'eva", "kamm-a"]
    words += corpus()
    for word in words:
        assert diagnose(word) == reference_diagnose(word), word


def test_diagnose_never_raises_and_is_empty_for_real_pali():
    for word in WORDS:
        assert diagnose(word) == []
        assert _pure.tokenize(word)  # every one of them tokenises strictly


# --- the metric -----------------------------------------------------------

def test_distance_matches_exactly():
    words = corpus()
    rng = random.Random(SEED + 1)
    pairs = [(rng.choice(words), rng.choice(words)) for _ in range(1500)]
    pairs += list(itertools.combinations(WORDS, 2))
    for a, b in pairs:
        assert same(_c.distance(a, b), _pure.distance(a, b)), (a, b)
        assert same(_c.levenshtein(a, b), _pure.levenshtein(a, b)), (a, b)


def test_distance_matches_over_the_geminate_vocabulary():
    """The segmentation into heavy units is the least obvious part of the
    DP and the easiest to get subtly wrong, so it is exercised directly:
    every geminate against its own grapheme and against another."""
    for long_form, base in sorted(_pure._GEMINATE_BASES.items()):
        assert same(_c.cost(long_form, base), _pure.cost(long_form, base))
        assert _c.distance(long_form, long_form) == 0.0
    for a, b in [("attha", "atha"), ("magga", "makka"), ("kamma", "kama"),
                 ("vikkhambhati", "vikhambhati"), ("citta", "cinta"),
                 ("puñña", "puñja"), ("aṭṭha", "aṭha")]:
        assert same(_c.distance(a, b), _pure.distance(a, b)), (a, b)


def test_lenient_distance_matches_exactly():
    for a, b in [("qamma", "kamma"), ("kṛṣṇa", "kanna"),
                 ("axta", "atta"), ("śānti", "santi")]:
        assert same(_c.distance(a, b, True), _pure.distance(a, b, True)), (a, b)
        assert same(_c.levenshtein(a, b, True), _pure.levenshtein(a, b, True)), (a, b)


def test_alignment_matches_operation_for_operation():
    """Not just the total: the same script. The traceback's branch order and
    its 1e-12 tolerance were matched deliberately — two optimal alignments of
    the same pair are both correct, and only one is the same answer."""
    rng = random.Random(SEED + 2)
    words = corpus()
    for _ in range(500):
        a, b = rng.choice(words), rng.choice(words)
        assert same(_c.alignment(a, b), _pure.alignment(a, b)), (a, b)
    for a, b in itertools.combinations(WORDS[:20], 2):
        assert same(_c.alignment(a, b), _pure.alignment(a, b)), (a, b)


def test_alignment_of_lenient_words_reports_the_character():
    for a, b in [("qamma", "kamma"), ("kṛṣṇa", "kanna")]:
        assert same(_c.alignment(a, b, True), _pure.alignment(a, b, True)), (a, b)


def test_the_public_functions_are_the_c_ones():
    """The delegating module must actually delegate: `distance` and
    `levenshtein` in `abugida.distance` are the binding's, not the
    reference's."""
    assert distance("kamma", "khamma") == _c.distance("kamma", "khamma")
    assert levenshtein("kamma", "khamma") == _c.levenshtein("kamma", "khamma")


#: Numbers `docs/c-core.md` states, and where they come from. A document that
#: quotes a figure must be checkable; these are the ones the C version added —
#: the vocabulary it generates, and the token-pair domain the cost test above
#: claims to cover exhaustively.
DOC_FIGURES = {"tokens": 126, "graphemes": 41}


def test_the_documents_figures_still_hold():
    """`docs/c-core.md` says "126 tokens, 41 graphemes" and "all 15,876 ordered
    token pairs". Both are checked here, so a vocabulary change fails a test
    instead of leaving a document quietly wrong."""
    import re

    doc = (ROOT / "docs" / "c-core.md").read_text(encoding="utf-8")
    assert f"{DOC_FIGURES['tokens']} tokens" in doc, "the doc's token count"
    assert f"{DOC_FIGURES['graphemes']} graphemes" in doc, "the doc's grapheme count"
    assert _c.NTOKENS == DOC_FIGURES["tokens"]
    assert _c.NPLAIN == DOC_FIGURES["graphemes"]
    # The claimed pair count is the square of the vocabulary, and
    # `test_cost_table_matches_the_reference_exactly` really does iterate it.
    pairs = DOC_FIGURES["tokens"] ** 2
    assert f"{pairs:,}" in doc, f"the doc does not state {pairs:,} pairs"
    # And the generated header agrees with both, so the C consumer sees the
    # same vocabulary the doc describes.
    header = (ROOT / "csrc" / "abugida_tables.h").read_text(encoding="utf-8")
    assert re.search(r"#define ABUGIDA_NTOKENS 126\b", header)
    assert re.search(r"#define ABUGIDA_NPLAIN 41\b", header)


# --- domain and range: the shape of the mirror ---------------------------
#
# The tests so far compare VALUES on hand-chosen inputs. These compare the
# two implementations as functions: that they accept and reject the same
# inputs (the DOMAIN) and return the same kind of thing (the RANGE). Three
# real bugs lived in that gap and none of them was visible to a value test,
# because every value test used lowercase input:
#
#  1. `distance`/`levenshtein`/`alignment` did not normalise, so
#     `distance("Bh", "bh")` was 1.34 where the reference says 0.0.
#  2. the C scanner skipped ASCII whitespace only, so a non-breaking space
#     from a pasted page tokenised as mojibake.
#  3. an opaque token stored the character's first BYTE, so one mistyped
#     two-byte letter cost 2.0 instead of 1.0.
#
# `tools/differential.py` is the full sweep (102,000 comparisons, 3,878
# inputs). What stays here is the part that must fail loudly in CI.

#: Inputs that break one of the three, plus the ordinary ones as controls.
MIRROR_INPUTS = [
    "", "a", "A", "KAMMA", "Bh", "BH", "Ñ", "SĪHA", "ṬHĀNA",
    "saṃgha", "saṁgha", "SAṂGHA", "\u1e43\u0301",
    "\u00e9", "\u00c9", "\u0416", "\u00d1", "\u4e2d",
    "a\u00a0b", "a\u2003b", "a\u3000b", "\t", "\n",
    "-", "'", "\u2019", "a-b", "tass'eva",
    "kṛṣṇa", "śānti", "qamma", "attha", "aṭṭha", "kh", "ṭh", "tt", "tth",
    "\U0001f600",
]


def test_the_two_implementations_accept_the_same_inputs():
    """The DOMAIN: for every input, either both raise or neither does, and
    when they raise it is the same exception type.

    A port that is stricter than its reference is as much a bug as one that
    is looser: the first breaks callers that relied on lenient behaviour, the
    second silently returns a number where the reference raised."""
    unary = [
        ("tokenize", _pure.tokenize, PUB.tokenize,
         lambda f, s: f(s)),
        ("tokenize(lenient)", _pure.tokenize, PUB.tokenize,
         lambda f, s: f(s, True)),
        ("diagnose", reference_diagnose, PUB.diagnose,
         lambda f, s: f(s)),
        ("assimilate_word", reference_assimilate, PUB.assimilate_word,
         lambda f, s: f(s)),
        ("contract_word", reference_contract, PUB.contract_word,
         lambda f, s: f(s)),
        ("phonological_form", reference_phonological_form, PUB.phonological_form,
         lambda f, s: f(s)),
    ]
    for name, ref, pub, call in unary:
        for s in MIRROR_INPUTS:
            assert _domain(ref, pub, (s,), call) is None, (name, s)


def test_the_two_implementations_accept_the_same_pairs():
    """The same for the two-argument functions, over the cross product: 39
    inputs squared is 1,521 pairs per function, which is cheap and covers
    every combination of the classes above."""
    binary = [
        ("distance", _pure.distance, PUB.distance,
         lambda f, a, b: f(a, b)),
        ("distance(lenient)", _pure.distance, PUB.distance,
         lambda f, a, b: f(a, b, True)),
        ("levenshtein", _pure.levenshtein, PUB.levenshtein,
         lambda f, a, b: f(a, b)),
        ("alignment", _pure.alignment, PUB.alignment,
         lambda f, a, b: f(a, b)),
        ("cost", _pure.cost, PUB.cost, lambda f, a, b: f(a, b)),
    ]
    for name, ref, pub, call in binary:
        for a in MIRROR_INPUTS:
            for b in MIRROR_INPUTS:
                assert _domain(ref, pub, (a, b), call) is None, (name, a, b)


def _domain(ref, pub, args, call):
    """None when both agree about raising, else what each did."""
    def outcome(f):
        try:
            call(f, *args)
            return "ok"
        except Exception as exc:  # noqa: BLE001 - the kind IS the datum
            return type(exc).__name__

    left, right = outcome(ref), outcome(pub)
    return None if left == right else (left, right)


def test_the_two_implementations_raise_the_same_message():
    """The DOMAIN includes what a caller READS when an input is refused.

    Same exception type is not enough: `ValueError("'qa' in 'qamma' is not a
    Pāli grapheme")` names a character the tokeniser never rejected, and a
    user pasting that into a bug report sends the investigation somewhere
    else. The C core reports a BYTE offset, so the binding has to decode the
    character at it using the length its lead byte announces — the first
    version of this guessed by trying 2, then 3, then 4 bytes and split
    `qamma` at `qa`."""
    for word in ["qamma", "kṛṣṇa", "\u1e43\u0301", "\u00e9", "Z",
                 "\U0001f600", "\u0416", "paṭhama*"]:
        ref = _message(_pure.tokenize, word)
        pub = _message(tokenize, word)
        assert ref == pub, (word, ref, pub)


def _message(fn, word):
    """The exception's message, or None when there is no exception."""
    try:
        fn(word)
    except ValueError as exc:
        return str(exc)
    return None


def test_the_two_implementations_return_the_same_values():
    """The RANGE: same type, same shape, and the same double — over the same
    inputs, including the ones that only differ by case or by encoding.

    Doubles to within `TOLERANCE` (module docstring): bit for bit on the
    platform that generated the tables, within libm rounding elsewhere."""
    def outcome(f, args):
        try:
            return ("ok", call_with(f, args))
        except Exception as exc:  # noqa: BLE001
            return ("raise", type(exc).__name__)

    def call_with(f, args):
        value = f(*args) if len(args) == 1 else f(args[0], args[1])
        if isinstance(value, list):
            return tuple(value)
        return value

    unary = [("tokenize", _pure.tokenize, PUB.tokenize),
             ("assimilate_word", reference_assimilate, PUB.assimilate_word),
             ("contract_word", reference_contract, PUB.contract_word),
             ("phonological_form", reference_phonological_form, PUB.phonological_form)]
    for name, ref, pub in unary:
        for s in MIRROR_INPUTS:
            assert outcome(ref, (s,)) == outcome(pub, (s,)), (name, s)

    for name, ref, pub in [("distance", _pure.distance, PUB.distance),
                           ("levenshtein", _pure.levenshtein, PUB.levenshtein),
                           ("alignment", _pure.alignment, PUB.alignment),
                           ("cost", _pure.cost, PUB.cost)]:
        for a in MIRROR_INPUTS:
            for b in MIRROR_INPUTS:
                assert same(outcome(ref, (a, b)), outcome(pub, (a, b))), \
                    (name, a, b)


def test_an_opaque_token_is_one_character_not_one_byte():
    """A typo outside ASCII must cost what the reference says.

    The C core encodes an unknown character by its CODEPOINT; encoding its
    first byte instead spent one token per byte of UTF-8, so a single mistyped
    two-byte letter cost 2.0 and an emoji 4.0 — ranking one typo further from
    the truth than two. Checked through `distance`, which is where it shows."""
    # Not Ñ: it normalises to ñ, which IS a Pāli grapheme, so it prices
    # against n (0.437) instead of costing a flat 1.0 — correct, and a
    # different test.
    for typo, word in [("\u00e9", "kamma"), ("\u0416", "kamma"),
                       ("\u00d0", "kamma")]:
        mistyped = typo + "amma"
        assert distance(mistyped, word, lenient=True) == \
            _pure.distance(mistyped, word, True), mistyped
        assert distance(mistyped, word, lenient=True) == \
            distance("qamma", word, lenient=True), mistyped
    # Above U+0800 the token space keeps the low 11 bits, so a character's
    # identity is not preserved — documented, and the same on both sides.
    assert distance("\U0001f600amma", word, lenient=True) == \
        _pure.distance("\U0001f600amma", word, True)


def test_whitespace_beyond_ascii_is_dropped_by_both():
    """`str.isspace()` is the predicate, not the ASCII set: a non-breaking
    space or an em space out of a pasted web page is dropped by tokenisation,
    by the metric and by `diagnose` — and NOT reported as a problem, because
    a character tokenisation silently drops is not one strict tokenisation
    would reject."""
    for space in ["\u00a0", "\u2003", "\u3000", "\u202f", "\u0085"]:
        word = "a" + space + "b"
        assert tokenize(word, lenient=True) == ["a", "b"], word
        assert tokenize(word, lenient=True) == _pure.tokenize(word, True), word
        assert diagnose(word) == [], word
        assert distance(word, "ab", lenient=True) == 0.0, word


# --- the pipeline ---------------------------------------------------------

def reference_assimilate(word):
    """`assimilate_word` written out from `phonology.assimilate` — the rule the
    C table is generated FROM, applied here independently."""
    from abugida.phonology import assimilate as meet

    tokens = _pure.tokenize(word)
    out = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t != "ṃ" or i + 1 == len(tokens):
            out.append(t)
            i += 1
            continue
        following = tokens[i + 1]
        if following == "y":
            out.extend(["ñ", "ñ"])
            i += 2
            continue
        out.append(meet(following).grapheme)
        i += 1
    return "".join(out)


def reference_contract(word):
    """`contract_word` from `sandhi.CONTRACTIONS`, applied independently."""
    word = normalize(word)
    for source, target in CONTRACTIONS:
        word = word.replace(source, target)
    return word


def reference_phonological_form(word):
    """`lexicon.phonological_form`: assimilate then contract, and an input the
    inventory cannot tokenise passes through untouched — the `except
    ValueError: return word` of the shipped function, reproduced here."""
    try:
        return reference_contract(reference_assimilate(word))
    except ValueError:
        return word


def test_pipeline_matches_the_reference_rules():
    """`assimilate_word` and `contract_word`, against the rules written out
    here from `phonology.assimilate` and `sandhi.CONTRACTIONS` — the same
    source the C tables are generated from, applied independently."""
    words = corpus() + ["saṃgha", "saṃyutta", "sakiṃ", "abhibhavati",
                        "anavakāsa", "bhāvayitvā", "kṛṣṇa"]
    for word in words:
        assert _c.contract_word(word) == reference_contract(word), word
        try:
            assert _c.assimilate_word(word) == reference_assimilate(word), word
        except ValueError:
            # Not Pāli: the pipeline is documented to raise here and pass
            # through in `phonological_form`, which the next test covers.
            assert reference_raises(word)
    for word in ["saṃghassa", "kṛṣṇa", "saṃyuttaṃ"]:
        assert _c.phonological_form(word) == (
            word if reference_raises(word) else reference_contract(
                reference_assimilate(word))
        ), word


def reference_raises(word):
    try:
        _pure.tokenize(word)
    except ValueError:
        return True
    return False


# --- the kernel variants (docs/asm-plan.md phase 1) -----------------------

def _variant_pairs(limit=None):
    """Inputs every implementation accepts, in BOTH modes.

    Not `MIRROR_INPUTS`: that list exists to probe the domain, so it is full
    of strings the strict tokeniser is supposed to reject, and a variant test
    that raised on them would be measuring the tokeniser rather than the
    kernels. Everything here is a word or a word-shaped string, and every pair
    is checked in both modes because `levenshtein` has a lenient path and an
    opaque token has a negative id — which used to be exactly where the kernel
    read its pattern table out of bounds."""
    words = corpus() + [
        "a", "ā", "k", "kh", "kamma", "khamma", "dhamma", "dhammā",
        "saṃgha", "saṅgha", "citta", "citra", "buddha", "buddhā",
        "abhidhamma", "abhidhammapiṭaka", "vikkhambhati", "vikhambhati",
        "sīha", "sīhassa", "ṭhāna", "ṭhānāni", "ñāṇa", "ñāṇena",
        "paṭhama", "paṭhamā", "kṛṣṇa", "śānti", "qamma", "\u00e9",
    ]
    pairs = []
    for a in words:
        for b in words:
            pairs.append((a, b))
            if limit and len(pairs) >= limit:
                return pairs
    return pairs


def test_every_kernel_variant_returns_the_same_values():
    """The `levenshtein` kernel is built once per instruction set, and the
    dispatcher picks one. EVERY variant this build contains is compared with
    every other, and each with the pure-Python reference: a variant that is
    wrong only on silicon the author does not own is exactly the failure the
    dispatcher makes possible, and agreeing with each other is not enough —
    three variants built from one wrong source agree perfectly."""
    names = _c.impl_names()
    assert names, "a build with no kernel variant at all is not this test"
    assert "c" in names, (
        "the portable variant must always be built: it is the fallback on any "
        f"target without the others, and this build has {names}"
    )

    pairs = _variant_pairs(limit=4000)
    results = {}
    try:
        for name in names:
            _c.impl_select(name)
            assert _c.impl_name() == name, (name, _c.impl_name())
            results[name] = [_c.levenshtein(a, b, True) for a, b in pairs]
    finally:
        _c.impl_select(None)

    for name in names:
        # Against the reference FIRST, so a bug shared by every variant — one
        # wrong source compiled three times, which is what the variants are —
        # cannot pass by agreeing with itself.
        wrong = [
            (pairs[i], results[name][i], _pure.levenshtein(*pairs[i], True))
            for i in range(len(pairs))
            if results[name][i] != _pure.levenshtein(*pairs[i], True)
        ]
        assert not wrong, (name, wrong[:3])
        # And against the others, so a divergence is reported as one.
        if name != names[0]:
            differ = [
                (pairs[i], results[names[0]][i], results[name][i])
                for i in range(len(pairs))
                if results[names[0]][i] != results[name][i]
            ]
            assert not differ, (names[0], name, differ[:3])


def test_the_variant_can_be_forced_and_the_choice_is_reported():
    """`impl_select` is what makes the variants testable in one process, and
    what a bug report carries: which kernel answered is not answerable from a
    number. An unknown name must RAISE rather than be ignored — a test that
    believes it forced `sse2` while `avx2` answered has verified nothing."""
    names = _c.impl_names()
    try:
        for name in names:
            _c.impl_select(name)
            assert _c.impl_name() == name
        with pytest.raises(ValueError):
            _c.impl_select("no-such-variant")
        # The refusal must not change the choice.
        _c.impl_select(names[0])
        with pytest.raises(ValueError):
            _c.impl_select("no-such-variant")
        assert _c.impl_name() == names[0]
    finally:
        _c.impl_select(None)
    assert _c.impl_name() in names
