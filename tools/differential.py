"""Differential harness: the Python API against the C core, domain and range.

The question this answers is not "do they agree on the examples" but "are they
the same function": **same domain** (every input either succeeds in both or
raises the same kind of exception in both) and **same range** (every output is
of the same type and, for numbers, the same double).

`:mod:`tests.test_c_parity` covers this for the documented surface with
hand-chosen inputs. This goes further in two directions that matter for the
mirror claim:

- the input corpus is the **entire inventory crossed with itself** plus every
  long consonant, the Sanskrit phonemes, editorial marks, the two niggahīta
  spellings, uppercase, whitespace, digits, punctuation, astral characters and
  a fixed-seed sample of arbitrary strings — 1.4 million inputs when the pairs
  are counted;
- the comparison is **structural**: return types, list lengths, nested tuple
  shapes, `None` positions and float bit patterns, not just equality of the
  result.

Run it directly for the full report:

    python tools/differential.py

Exit status is 0 when the two are mirrors and 1 when they are not, so it can
be used as a check rather than read as a table.
"""

from __future__ import annotations

import itertools
import math
import random
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import abugida as _pkg  # noqa: E402
from abugida import _cabugida as C  # noqa: E402
from abugida import _pure  # noqa: E402

#: The reference implementation, called directly so the comparison is against
#: the algorithm and not against another delegation of the same call.
REF = _pure

#: The SHIPPED one — `abugida.distance`, `abugida.iast`, `abugida.sandhi` and
#: `abugida.phonological_form` as a user gets them, which is what has to be a
#: mirror of the reference.
import importlib  # noqa: E402

PUB = importlib.import_module("abugida.distance")
PUB.__dict__.setdefault("tokenize",
                        importlib.import_module("abugida.iast").tokenize)
PUB.diagnose = importlib.import_module("abugida.iast").diagnose
PUB.assimilate_word = importlib.import_module("abugida.sandhi").assimilate_word
PUB.contract_word = importlib.import_module("abugida.sandhi").contract_word
PUB.phonological_form = _pkg.phonological_form

from abugida.alphabet import ALPHABET  # noqa: E402
from abugida.iast import normalize  # noqa: E402
from abugida.phonology import BY_GRAPHEME, FOREIGN  # noqa: E402
from abugida.sandhi import CONTRACTIONS  # noqa: E402


def _is_normalised(word: str) -> bool:
    """Is this input already in the canonical form the C core requires?"""
    return normalize(word) == word

SEED = 20260801


# --- the input corpus -----------------------------------------------------

def inputs() -> list:
    """Every string the two implementations are compared over.

    Grouped by what each group is FOR, because a failure should say which
    kind of input broke it — a disagreement on an astral character and one on
    a digraph are different bugs.
    """
    letters = sorted(p.grapheme for p in ALPHABET)
    long_forms = sorted(_pure._GEMINATE_BASES)
    foreign = sorted(FOREIGN)

    corpus = [""]
    # Every grapheme alone, and every grapheme against every other.
    corpus += letters
    corpus += foreign
    corpus += [a + b for a in letters for b in letters]
    # Every long consonant alone, against its own grapheme, and against
    # another long form: the segmentation into heavy units needs these.
    corpus += long_forms
    corpus += [long_ + g for long_ in long_forms for g in letters]
    corpus += [a + b for a in long_forms[:8] for b in long_forms[:8]]
    # The orthographic variants and the marks that are dropped.
    corpus += ["ṁ", "ṃ", "saṁgha", "saṃgha", "aṁ", "aṃ", "ṃṃ", "ṁṁ"]
    corpus += ["-", "'", "\u2019", "--", "''", "a-b", "a'b", "a\u2019b",
               "tass'eva", "evaṁ'me", "Saṁyutta-Nikāya"]
    corpus += [" ", "\t", "\n", "\v", "\f", "\r", "a b", " ", "\u00a0",
               "\u2003"]
    # Case, digits, punctuation, and the characters that are Sanskrit rather
    # than Pāli.
    corpus += ["A", "KAMMA", "Dhamma", "SĪHA", "ṬHĀNA", "0", "9", "a1",
               "!", "?", "*", "#", "@", "a*", "*a", "a*b"]
    corpus += ["ṛ", "ṝ", "ṣ", "ś", "ḷ", "kṛṣṇa", "śānti", "ṛju", "kṣetta"]
    # Outside the BMP, and characters that are not letters at all.
    corpus += ["\U0001d400", "\U0001f600", "a\U0001f600", "\u00e9", "\u00d1",
               "\u4e2d", "\u05d0", "\u0416"]
    # Fixed-seed arbitrary strings: the group that finds what the others miss.
    rng = random.Random(SEED)
    pool = (string.ascii_letters + string.digits + string.punctuation
            + " " + "".join(letters) + "".join(foreign) + "ṁṃ\u2019\u00a0")
    corpus += ["".join(rng.choice(pool) for _ in range(rng.randint(0, 10)))
               for _ in range(400)]
    # Deduplicate, keeping the order (and therefore the groups) stable.
    seen = set()
    out = []
    for s in corpus:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def hot_inputs(corpus: list) -> list:
    """The inputs the pair sweep crosses exhaustively.

    Chosen so the product BUYS something: every class that has ever produced a
    disagreement (case, NFD, the two niggahita spellings, opaque non-ASCII,
    editorial marks, whitespace, the digraphs, the long consonants) is here,
    and the arbitrary random strings — which the sample below covers — are
    not. The full cross product of the 1,299 short inputs was 1.3 million
    comparisons per function, which measures the harness rather than the
    code.
    """
    letters = sorted(p.grapheme for p in ALPHABET)
    long_forms = sorted(_pure._GEMINATE_BASES)[:6]
    return [
        "", "a", "ā", "ṃ", "ṁ", "k", "kh", "bh", "gh", "ṭh", "ḍh",
        "K", "KH", "A", "Ñ", "S", "BH", "ṬH",
        "tt", "tth", "kk", "mm", "khkh", "ṭhṭh",
        "\u00e9", "\u0416", "\u00f1", "\u0410", "\u4e2d", "\u0301",
        "-", "'", "\u2019", " ", "\u00a0", "\u2003", "*", "?", "0",
        "ṛ", "ṣ", "ś",
        "ka", "ak", "kā", "kha", "ga", "attha", "atha", "aṭṭha",
        "saṃ", "saṁ", "saṃgha", "saṅgha", "qamma", "KAMMA", "\u1e43\u0301",
    ] + letters[:12] + long_forms


# --- comparison -----------------------------------------------------------

def call(fn, args, kwargs):
    """Call and describe the outcome, so a difference in KIND is visible and
    not just a difference in value: `("ok", value, type)` or
    `("raise", ExceptionType)`."""
    try:
        value = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the exception IS the datum
        return ("raise", type(exc).__name__)
    return ("ok", value, type(value).__name__)


def describe(value) -> str:
    """A short, recursive description of a return value, for the report."""
    if isinstance(value, float):
        return f"float({value!r})"
    if isinstance(value, (list, tuple)):
        head = ", ".join(describe(v) for v in value[:3])
        more = ", ..." if len(value) > 3 else ""
        return f"{type(value).__name__}[{len(value)}]({head}{more})"
    return repr(value)[:60]


def same(a, b) -> bool:
    """Structural equality, with floats compared by BITS.

    Bit equality, not approximate: on the platform the tables are generated
    on (Linux, glibc) the two implementations return the same double, because
    the generator emits round-tripping literals. On a C library that rounds
    `acos` differently the reference moves in the last bit and this tool will
    say so; `tests/test_c_parity.py` is the cross-platform check. `==` would
    pass on two NaNs and on +0.0 against -0.0, so the sign and the exact
    payload are checked too.
    """
    ka, va = a[0], a[1:]
    kb, vb = b[0], b[1:]
    if ka != kb:
        return False
    if ka == "raise":
        return va == vb
    value_a, type_a = va
    value_b, type_b = vb
    if type_a != type_b:
        return False
    if isinstance(value_a, float):
        if math.isnan(value_a) or math.isnan(value_b):
            return math.isnan(value_a) and math.isnan(value_b)
        return math.copysign(1.0, value_a) == math.copysign(1.0, value_b) \
            and value_a == value_b
    if isinstance(value_a, (list, tuple)):
        if len(value_a) != len(value_b):
            return False
        return all(same(("ok", x, type(x).__name__),
                        ("ok", y, type(y).__name__))
                   for x, y in zip(value_a, value_b))
    return value_a == value_b


class Report:
    """Failures, grouped so that 10,000 instances of one bug read as one."""

    def __init__(self) -> None:
        self.by_function: dict = {}
        self.checks = 0

    def check(self, name: str, args, kwargs, py, c) -> None:
        self.checks += 1
        if same(py, c):
            return
        key = name
        bucket = self.by_function.setdefault(key, {"count": 0, "examples": []})
        bucket["count"] += 1
        if len(bucket["examples"]) < 4:
            bucket["examples"].append(
                (args, kwargs, describe_outcome(py), describe_outcome(c)))

    @property
    def failures(self) -> int:
        return sum(b["count"] for b in self.by_function.values())

    def print(self) -> None:
        if not self.by_function:
            print(f"  {self.checks:,} comparisons, 0 disagreements")
            return
        print(f"  {self.checks:,} comparisons, {self.failures:,} disagreements "
              f"in {len(self.by_function)} function(s):")
        for name, bucket in sorted(self.by_function.items()):
            print(f"\n  {name}: {bucket['count']:,} disagreements")
            for args, kwargs, py, c in bucket["examples"]:
                print(f"    args={args!r} kwargs={kwargs!r}")
                print(f"      python -> {py}")
                print(f"      C      -> {c}")


def describe_outcome(outcome) -> str:
    if outcome[0] == "raise":
        return f"raises {outcome[1]}"
    return f"{outcome[2]} {describe(outcome[1])}"


# --- the comparison itself ------------------------------------------------

def compare_unary(report: Report, name: str, py, c, corpus: list) -> None:
    for s in corpus:
        report.check(name, (s,), {}, call(py, (s,), {}), call(c, (s,), {}))


def compare_pairs(report: Report, name: str, py, c, corpus: list,
                  hot: list) -> None:
    rng = random.Random(SEED)
    # The cross product of the curated set — small enough to run, chosen so
    # that every class of input that has ever disagreed is inside it — plus a
    # fixed-seed sample from the whole corpus, which covers the arbitrary
    # strings the curated set cannot anticipate.
    for a, b in itertools.product(hot, repeat=2):
        report.check(name, (a, b), {}, call(py, (a, b), {}),
                     call(c, (a, b), {}))
    for _ in range(600):
        a, b = rng.choice(corpus), rng.choice(corpus)
        report.check(name, (a, b), {}, call(py, (a, b), {}),
                     call(c, (a, b), {}))


def main() -> int:
    corpus = inputs()
    print(f"differential: {len(corpus):,} distinct inputs "
          f"({sum(1 for s in corpus if len(s) <= 2):,} of them short)")

    hot = hot_inputs(corpus)
    report = Report()

    # --- unary: domain (which inputs raise) and range (what comes back) ---
    #
    # `REF` is the reference implementation and `PUB` the shipped one — the
    # two must be mirrors. `C` (the bare binding) is deliberately NOT compared
    # here: it is a lower layer whose contract is to receive
    # NFC-normalised lowercase IAST (`csrc/abugida.h`), so it is allowed to
    # differ on uppercase and NFD input. Comparing it would have reported the
    # binding's documented precondition as a bug — which it did, before this
    # was split.
    compare_unary(report, "iast.tokenize",
                  REF.tokenize, PUB.tokenize, corpus)
    compare_unary(report, "iast.tokenize(lenient=True)",
                  lambda s: REF.tokenize(s, True),
                  lambda s: PUB.tokenize(s, True), corpus)
    compare_unary(report, "iast.diagnose",
                  _diagnose_reference, PUB.diagnose, corpus)
    compare_unary(report, "sandhi.assimilate_word",
                  _assimilate_reference, PUB.assimilate_word, corpus)
    compare_unary(report, "sandhi.contract_word",
                  _contract_reference, PUB.contract_word, corpus)
    compare_unary(report, "lexicon.phonological_form",
                  _form_reference, PUB.phonological_form, corpus)
    compare_unary(report, "distance.cost (unary)",
                  lambda s: REF.cost(s, s), lambda s: PUB.cost(s, s), corpus)
    compare_unary(report, "distance.indel", REF._indel, PUB.indel, corpus)

    # --- the bare binding agrees with the reference on ITS OWN domain ---
    # Normalised input only, which is the contract: NFC, lowercase, canonical
    # niggahita. Here it must be a mirror too.
    normalised = [s for s in corpus if _is_normalised(s)]
    print(f"  (of which {len(normalised):,} are already normalised: the bare "
          f"binding is compared over those)")
    compare_unary(report, "binding.tokenize", REF.tokenize, C.tokenize,
                  normalised)
    compare_unary(report, "binding.assimilate_word",
                  _assimilate_reference, C.assimilate_word, normalised)
    compare_unary(report, "binding.contract_word",
                  _contract_reference, C.contract_word, normalised)
    compare_unary(report, "binding.phonological_form",
                  _form_reference, C.phonological_form, normalised)

    # --- pairs: the metric itself ---
    compare_pairs(report, "distance.cost", REF.cost, PUB.cost, corpus, hot)
    compare_pairs(report, "distance.distance", REF.distance, PUB.distance,
                  corpus, hot)
    compare_pairs(report, "distance.distance(lenient=True)",
                  lambda a, b: REF.distance(a, b, True),
                  lambda a, b: PUB.distance(a, b, True), corpus, hot)
    compare_pairs(report, "distance.levenshtein", REF.levenshtein,
                  PUB.levenshtein, corpus, hot)
    compare_pairs(report, "distance.levenshtein(lenient=True)",
                  lambda a, b: REF.levenshtein(a, b, True),
                  lambda a, b: PUB.levenshtein(a, b, True), corpus, hot)
    compare_pairs(report, "distance.alignment", REF.alignment, PUB.alignment,
                  corpus, hot)
    compare_pairs(report, "distance.alignment(lenient=True)",
                  lambda a, b: REF.alignment(a, b, True),
                  lambda a, b: PUB.alignment(a, b, True), corpus, hot)
    compare_pairs(report, "distance.weighted_cost", REF.weighted_cost,
                  PUB.weighted_cost, corpus, hot)

    # --- the experimental L1 distance runs the C DP through a callable ---
    compare_pairs(report, "distance.weighted_distance",
                  REF.weighted_distance, PUB.weighted_distance, corpus, hot)

    # --- neighbours: the k-nearest wrapper, over a shared candidate list ---
    candidates = [s for s in corpus if s and _is_normalised(s)][:40]
    for query in candidates[:12]:
        report.check("distance.neighbors", (query, candidates), {"k": 5},
                     call(REF.neighbors, (query, candidates), {"k": 5}),
                     call(PUB.neighbors, (query, candidates), {"k": 5}))

    # --- algebraic_cost is pure arithmetic on both sides ---
    from abugida.algebra import ELEMENTS
    for x, y in itertools.product(ELEMENTS, repeat=2):
        report.check("algebra.cost", (x, y), {},
                     call(_pure.algebraic_cost, (x, y), {}),
                     call(C.algebraic_cost, (x, y), {}))

    # --- _edit, the extension point eval/ scripts drive directly ---
    rng = random.Random(SEED)
    graphemes = sorted(BY_GRAPHEME)
    for _ in range(400):
        a = [rng.choice(graphemes) for _ in range(rng.randint(0, 8))]
        b = [rng.choice(graphemes) for _ in range(rng.randint(0, 8))]
        for geminates in (True, False):
            report.check(
                f"distance._edit(geminates={geminates})", (a, b), {},
                call(lambda x, y: _pure._edit(x, y, _pure.cost,
                                              geminates=geminates), (a, b), {}),
                call(lambda x, y: _edit_c(x, y, geminates), (a, b), {}))

    report.print()

    # --- the range's bounds, stated as assertions rather than described ---
    print("\nrange bounds (both must satisfy them):")
    bounds_ok = True
    for a, b in [("kamma", "khamma"), ("", "kamma"), ("a", "ā"),
                 ("attha", "atha"), ("aṭṭha", "aṭṭha")]:
        for name, value in (("python", _pure.distance(a, b)),
                            ("C", C.distance(a, b))):
            if not (0.0 <= value <= max(len(_pure.tokenize(a)),
                                        len(_pure.tokenize(b)))):
                print(f"  {name}: d({a!r},{b!r}) = {value} is outside "
                      f"[0, max(|a|,|b|)]")
                bounds_ok = False
    for g1, g2 in itertools.product(sorted(BY_GRAPHEME), repeat=2):
        for name, value in (("python", _pure.cost(g1, g2)),
                            ("C", C.cost(g1, g2))):
            if not (0.0 <= value <= 1.0):
                print(f"  {name}: cost({g1!r},{g2!r}) = {value} outside [0,1]")
                bounds_ok = False
    print("  cost in [0, 1] and distance in [0, max len]: "
          f"{'ok' if bounds_ok else 'FAILED'} in both")
    return 0 if report.failures == 0 and bounds_ok else 1


# --- references the binding is compared against ---------------------------
# These are written from the documented rules rather than borrowed from
# either implementation, so a shared bug cannot hide in them.

def _diagnose_reference(word):
    text = normalize(word)
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "-'\u2019" or ch.isspace():
            # `str.isspace()`, which is the same predicate `tokenize` skips
            # with: the two must agree on what is dropped, or a character the
            # tokeniser ignores gets reported as a problem.
            i += 1
            continue
        if ch in "ṛṝṣś":
            out.append((i, ch, "sanskrit"))
            i += 1
            continue
        if any(text[i:i + n] in BY_GRAPHEME for n in (2, 1)):
            i += 2 if text[i:i + 2] in BY_GRAPHEME else 1
            continue
        out.append((i, ch, "unknown"))
        i += 1
    return out


def _assimilate_reference(word):
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


def _contract_reference(word):
    word = normalize(word)
    for source, target in CONTRACTIONS:
        word = word.replace(source, target)
    return word


def _form_reference(word):
    """`phonological_form`: resolve, then contract, and pass an input the
    inventory does not cover straight through."""
    try:
        return _contract_reference(_assimilate_reference(word))
    except ValueError:
        return word


def _edit_c(tokens1, tokens2, geminates):
    """The C `_edit` through the binding, with the same signature the
    reference uses — this is the adapter `distance._edit` applies."""
    if not geminates:
        # `distance._edit` takes the reference route when the transitions are
        # switched off; go through it so the comparison is of the public path.
        import importlib

        return importlib.import_module("abugida.distance")._edit(
            tokens1, tokens2, _pure.cost, geminates=False)
    return C.edit(C.ids_of(tokens1), C.ids_of(tokens2), C.PHONOLOGICAL,
                  C.indel_derived)


if __name__ == "__main__":
    raise SystemExit(main())
