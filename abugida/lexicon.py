"""Integration adapter: search and variant generation over a word list.

Generic over any lexicon. This is the surface an
integrating application needs — no knowledge of the underlying phonological
algebra required, `lenient` handling baked in (no input ever raises), and
the char-level prefilter wired up when rapidfuzz is available (pure-Python
fallback otherwise).

    lex = Lexicon(words)                  # pre-normalises and tokenises once
    lex.search("qamma")                   # → [(distance, word), …] top-k
    lex.variants()                        # → (a, b, distance, edit_tag), …

`variants` yields headword pairs within `theta` of each other — the
generator behind a variant-candidate pipeline (DPD: add-variants-phonetic).
The default theta is ONE_MOVE: the costliest single attested-variation move
the metric knows (0.627 — an epenthetic insertion) — every cheaper move
(vowel length 0.333, one algebra move 0.470, degemination 0.470, the karaṇa
bridges 0.601) falls under it. Not tuned: it is the maximum over the
elementary moves, recomputed from the costs themselves — and DPD's 66
hand-written PHONETIC_RULES have a measured median distance of 0.608,
landing just under the derived anchor (eval/phonetic_rules.py).

`edit_tag` labels a pair with the edits connecting it ("t↔ṭ", "+a", "−h") —
the automatic equivalent of the hand rules' rule:x<->y tags.
"""

from __future__ import annotations

import re

from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

#: `ONE_MOVE` is re-exported from `abugida.distance` (which gets it from the
#: reference implementation, where it is derived as the maximum over the
#: elementary moves). It stays importable from here because that is where
#: every caller and every eval script has always got it.
from .distance import (
    ONE_MOVE,
    USING_C,
    alignment,
    distance,
)

if USING_C:  # the token sequence `distance` can be handed instead of a string
    from ._cabugida import Tokens
else:  # pragma: no cover - exercised only without a built extension
    Tokens = None  # type: ignore[assignment]
from .sandhi import assimilate_word, contract_word
from .iast import normalize, tokenize

try:
    from rapidfuzz import fuzz, process

    _HAVE_RAPIDFUZZ = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAVE_RAPIDFUZZ = False

#: The costliest single attested-variation move (see module docstring).
#:
#: Derived as the MAXIMUM over the elementary moves, not as an alias of any
#: one of them — that is what makes "every cheaper move falls under it" true
#: by construction rather than by coincidence. The moves are: an epenthetic
#: indel (`INDEL_WEIGHT`), one move in the algebra (`k↔kh`, equal to `k↔g` by
#: the balance principle), degemination (`tt↔t`) and vowel length (`a↔ā`).
#:
#: It currently equals `INDEL_WEIGHT`, and was written as an alias of it for
#: that reason — but which move is dearest is a fact about the calibration,
#: not a definition. A trial re-warp of `cost` (concave, since reverted:
#: TODO.md) dropped the epenthetic indel BELOW a single algebra move, and the
#: alias silently stopped covering k↔kh: `variants` returned nothing for
#: kamma. The max is what the docstring always claimed; keeping it costs
#: nothing and the alias is known to be fragile. Do not collapse it back.
#:
#: The value is imported from `abugida.distance`, where it is re-exported
#: from the reference implementation alongside `INDEL_WEIGHT` and `cost` —
#: the same three numbers the C tables are generated from.
ONE_MOVE = ONE_MOVE

_EPS = 1e-9


def construction_key(construction: str) -> Optional[Tuple[str, ...]]:
    """A morphological construction string → its constituents as a sorted
    tuple, or None if there are fewer than two.

    Parses DPD's `construction` shape: constituents joined by `+`, each
    possibly a derivation chain `x > y > z` (the LAST link is the realised
    form), optionally marked as a root (`√gam`), affix (`*ika`) or
    parenthesised. Only the first line is read; DPD puts alternatives below.

        "ati > aty > acc + √i > ay + *a + *ika"  →  ("*a", "*ika", "acc", "ay")

    Sorting is what makes it a MULTISET comparison, so compound permutation
    (`sampannavijjācaraṇa` ~ `vijjācaraṇasampanna`) keys the same as
    identical construction. In DPD the general case dominates: most matches
    are the same formation spelled differently, not reordered compounds.

    Returns None below two constituents, where the key would be too coarse
    to mean anything — a single shared root groups thousands of lemmas
    (measured: 979 candidates per lemma, against 0.082 for the full key).
    """
    if not construction:
        return None
    parts = []
    for piece in re.split(r"\s*\+\s*", construction.split("\n")[0]):
        piece = piece.split(">")[-1].strip().strip("()").lstrip("√").strip()
        if piece:
            parts.append(piece)
    return tuple(sorted(parts)) if len(parts) >= 2 else None


def edit_tag(a: str, b: str) -> str:
    """The edits connecting two words: "t↔ṭ", "+a" (insertion), "−h"
    (deletion), space-separated; "" for identical words."""
    parts: List[str] = []
    for op, x, y, _cost in alignment(a, b, lenient=True):
        if op == "sub":
            parts.append(f"{x}↔{y}")
        elif op == "del":
            parts.append(f"−{x}")
        elif op == "ins":
            parts.append(f"+{y}")
    return " ".join(parts)


def phonological_form(word: str) -> str:
    """The word as the metric should see it: sandhi resolved, then vowel
    contraction. "Phonology first, metric second" in one call.

    `assimilate_word` rewrites saṃgha → saṅgha, so the niggahīta stops being
    compared as the overdetermined object it is; `contract_word` applies the
    two contraction rules that pay (`aya`→`e`, `ava`→`o`, SPEC §6.3). Both
    are NORMALISATIONS, not edit operations, and deliberately so — as
    alignment transitions they break the triangle inequality.

    Input outside the Pāli alphabet is returned UNCHANGED rather than
    raising. `assimilate_word` tokenises strictly, and
    this function is on `Lexicon`'s path, where "no input ever raises" is the
    contract — a lexicon with one Sanskrit headword in it must not fail to
    build. There is no phonology to resolve in a string the inventory does
    not cover, so leaving it alone is also the right answer, not just the
    safe one.

    "Unchanged" is literal, and it is the pre-existing behaviour rather than
    an oversight: a string with a digit or a Cyrillic letter takes the
    exception path, and returns byte for byte what came in — so
    `phonological_form("9Ir")` is "9Ir" while `phonological_form("KAMMA")` is
    "kamma". A string that DOES tokenise is normalised on the way through, as
    the two functions it composes normalise their own input.

    `comparator.Comparator` never relies on the pass-through: it validates
    strictly on the way in and reports what it refused, so a lexicon cannot
    hold a string this function would not touch.
    """
    try:
        return contract_word(assimilate_word(word))
    except ValueError:
        return word


class Lexicon:
    """A word list prepared for phonological search and variant generation."""

    def __init__(self, words: Iterable[str], normalise: bool = False):
        """`normalise=True` compares words through `phonological_form`.

        MEASURED end-to-end on DPD (600 query lemmas against the full
        75k lexicon): agreement with DPD's `var_phonetic` at θ=ONE_MOVE goes
        from 62.0% to **77.5%** — agreement, not accuracy, since DPD's rules
        compute that field (README, "Agreement with DPD is not accuracy"). It is the largest single improvement
        available anywhere in the package.

        Normalising is not free in volume — it draws non-variants closer too,
        so candidates per lemma rise 1.56 → 1.94 at that θ. The honest
        comparison is therefore at EQUAL volume, and it holds up there:
        interpolating the un-normalised curve onto the same volumes, the gain
        is **+6 to +13 points across the whole range** and +12.7 at the
        operating point. (An earlier draft of this docstring claimed zero
        volume cost. That was wrong: it compared recall over a fixed pair set
        without counting the extra candidates admitted.)

        It is opt-in rather than the default only because it changes the
        numbers a caller already depends on. New integrations should turn it
        on; `docs/comparator.md` says so.

        Normalisation affects MEASUREMENT ONLY. Keys and results are always
        the original words: `contract_word` alone maps 533 distinct lemma
        pairs onto identical strings, so normalising the lexicon itself would
        silently merge entries the caller still needs to tell apart.
        """
        prepared = {}
        for w in words:
            nw = normalize(w)
            if nw and nw not in prepared:
                prepared[nw] = tokenize(nw, lenient=True)
        self._tokens = prepared
        self._words: List[str] = sorted(prepared)
        self._normalise = normalise
        #: Parallel to `_words`: the form each word is COMPARED as.
        self._compare: List[str] = (
            [phonological_form(w) for w in self._words]
            if normalise else list(self._words)
        )
        self._compare_of = dict(zip(self._words, self._compare))
        #: Compared form -> its tokens, and the SAME tokens a caller would get
        #: from `Tokens.from_text(form, lenient=True)`. Built once, on first
        #: use, because it is only needed by a caller who scores.
        #:
        #: `distance` accepts a `Tokens` object, and one of these is exactly
        #: what it would have built for itself from the string — normalised
        #: the same way, lenient the same way. Passing it removes a
        #: normalisation and a tokenisation per candidate per query:
        #: `Tokens.from_text` costs 233 ns for ONE character from Python
        #: against ~11 ns of actual scanning, and `search` scores 200
        #: candidates. Measured on the scoring loop: 0.922 ms -> 0.311 ms.
        #:
        #: Keyed by the compared form and not by the word, because
        #: `normalise=True` compares a form the lexicon does not otherwise
        #: store. Two words with the same compared form share one entry, and
        #: that is correct rather than merely convenient: the distance is a
        #: function of the compared form, so a lookup that collides gives the
        #: same number it would have computed.
        self._tokens_of: Optional[Dict[str, "Tokens"]] = None
        self._tree = None  # lazy BK-tree, only used without rapidfuzz

    def _compared_tokens(self, form: str) -> "Tokens":
        """The tokens of a COMPARED form, cached.

        `Tokens` has no mutating method, so a shared instance cannot be
        changed by a caller and the cache needs no defensive copy. That is
        checked rather than assumed: `tests/test_lexicon.py` fails if the
        binding grows one."""
        cache = self._tokens_of
        if cache is None:
            cache = self._tokens_of = {}
            # `each`, NOT `form`: the loop variable would shadow the
            # parameter, and the lookup below would then be for the LAST
            # compared form in the lexicon rather than for the one asked
            # about. That is a wrong answer for every query, and it reads as
            # a cache that returns other words' tokens.
            # `each`, NOT `form`: the loop variable would shadow the
            # parameter, and the lookup below would then be for the LAST
            # compared form in the lexicon rather than for the one asked
            # about. That is a wrong answer for every query, and it reads as
            # a cache that returns other words' tokens.
            for each in dict.fromkeys(self._compare):
                cache[each] = Tokens.from_text(each, lenient=True)
        got = cache.get(form)
        if got is None:
            # A form outside the lexicon (a query, or a generated variant).
            got = Tokens.from_text(form, lenient=True)
            cache[form] = got
        return got

    def __len__(self) -> int:
        return len(self._words)

    def __contains__(self, word: str) -> bool:
        return normalize(word) in self._tokens

    # -- search --------------------------------------------------------

    def _as_compared(self, word: str) -> str:
        return phonological_form(word) if self._normalise else word

    def _pool(self, query: str, size: int) -> List[str]:
        """Candidate shortlist, prefiltered on the COMPARED forms so the pool
        agrees with what will be scored."""
        if _HAVE_RAPIDFUZZ:
            return [
                self._words[i] for _, _, i in process.extract(
                    self._as_compared(query), self._compare,
                    scorer=fuzz.ratio, limit=size)
            ]
        # No rapidfuzz: a BK-tree over the metric beats scanning a length
        # window by 2.4x (548ms against 1295ms per query over 75k lemmas),
        # and is exact rather than a heuristic band. Built lazily — it costs
        # ~16s for a lexicon that size, which is wasted if never queried.
        # NOTE this is the fallback only. With rapidfuzz available the tree
        # is slower and no more accurate; see `abugida/index.py`.
        if self._tree is None:
            from .index import BKTree

            self._tree = BKTree(self._compare)
            self._by_compared = {}
            for w, c in zip(self._words, self._compare):
                self._by_compared.setdefault(c, []).append(w)
        out = []
        # exclude_query=False: the query's own compared form may belong to
        # another word (saṃgha ~ saṅgha under normalise). The query word
        # itself is dropped by `search`, by word and not by form, exactly as
        # on the rapidfuzz path.
        for _, form in self._tree.nearest(self._as_compared(query), k=size,
                                          exclude_query=False):
            out.extend(self._by_compared.get(form, ()))
        return out[:size]

    def search(self, query: str, k: int = 5, pool: int = 200,
               max_distance: Optional[float] = None,
               ) -> List[Tuple[float, str]]:
        """The k phonologically nearest words. Accepts anything — typos,
        Sanskrit diacritics, garbage — and never raises; empty input gives
        an empty result. `max_distance` drops candidates beyond it, so
        pure-noise queries can return nothing instead of far junk.

        Returned words are always the lexicon's own; `normalise=True` changes
        how far they are, not what they are."""
        q = normalize(query)
        if not q or not tokenize(q, lenient=True):
            return []
        qc = self._as_compared(q)
        candidates = self._pool(q, pool)
        qt = self._compared_tokens(qc)
        # With a threshold, the DP is told about it: a candidate above it is
        # going to be dropped, so the DP does not have to finish. Measured
        # 1.5x to 1.8x on the scoring of a real pool at the operating range,
        # and exact — the verdicts are identical to filtering afterwards,
        # which `tests/test_lexicon_tokens.py` checks over a query corpus.
        # NOTE: the bounded DP (`_distance_bounded`) is deliberately NOT used
        # here, and that is a measurement rather than an omission. It makes
        # the kernel 1.3x-1.6x cheaper — exact, and checked — but at this
        # level the per-candidate Python work (the `Tokens` lookup, the
        # function call, unpacking the verdict) costs more than the kernel
        # saves: measured 0.92x at theta=1.5 and 1.03x at theta=0.627 on a
        # real 75k lexicon, i.e. no better than filtering afterwards.
        # `docs/asm-plan.md` phase 3 has the numbers.
        scored = sorted(
            (distance(qt, self._compared_tokens(self._compare_of[w]),
                      lenient=True), w)
            for w in candidates if w != q
        )
        if max_distance is not None:
            scored = [(d, w) for d, w in scored if d <= max_distance + _EPS]
        return scored[:k]

    # -- variant generation --------------------------------------------

    def median_length(self) -> int:
        """Median compared-form length in tokens. Used to derive the default
        relative threshold from the caller's own lexicon rather than from a
        constant chosen elsewhere."""
        lengths = sorted(len(self._compared_tokens(c)) for c in self._compare)
        return lengths[len(lengths) // 2] if lengths else 1

    def variants(self, theta: Optional[float] = None, pool: int = 50,
                 words: Optional[Iterable[str]] = None,
                 constructions: Optional[Mapping[str, str]] = None,
                 relative: bool = False,
                 ) -> Iterator[Tuple[str, str, float, str]]:
        """Yield (a, b, distance, edit_tag) for word pairs within `theta`.

        Each unordered pair is yielded once (a < b). `words` restricts the
        left side (e.g. to process the lexicon in batches); the right side
        is always the whole lexicon. Cost is roughly `search` per word —
        budget minutes, not seconds, for a full 70k-lemma sweep.

        `constructions` optionally maps word → morphological construction
        string (DPD's `construction` field, or anything of the same shape:
        constituents joined by `+`, with `>` for derivations). Words whose
        constructions agree as a MULTISET are yielded as pairs whatever
        their distance, with edit tag "=construction".

        MEASURED (2026-08-02, DPD): this is the cheapest coverage in the
        system by an order of magnitude. Against the 5,002 `var_phonetic`
        pairs it lifts agreement with DPD from 63.6% to **71.8% (+8.2
        points)** for **+0.082 candidates per lemma**, where buying six points by raising
        θ to 0.800 instead costs +0.28. It reaches pairs the metric cannot:
        `abhikkhaṇaṃ ~ abhiṇhaṃ` (d = 2.37), `agamā ~ agā` (1.63),
        `abbheti ~ avheti` (1.28) — same word, same formation, spellings too
        far apart for any usable threshold.

        Why it is not part of the metric: it is a LEXICAL fact, not a
        phonological one. abugida owns no lexicon and derives nothing from
        one, so the caller supplies the data and this method only groups it.
        Without `constructions` the behaviour is exactly as before.

        `relative=True` compares `distance / max(token length)` against
        `theta` instead of the raw distance, so the budget scales with the
        word. The noisy-channel reading motivates it (SPEC §9.2): if each
        position can be corrupted independently, the negative log-likelihood
        of a whole word grows with its length, so a fixed budget is
        progressively stricter on long words. Pāli, being a language of long
        compounds, feels that acutely — measured on DPD, agreement with its
        `var_phonetic` falls from 84.2% on words of ≤5 tokens to 72.2% on
        those of 13+.

        MEASURED at MATCHED candidate volume: **+2 to +9 points across the
        whole range**, best in the low-volume region (+8.7 at 0.76
        candidates per lemma). `theta` then defaults to
        `ONE_MOVE / median_length()` — derived from the caller's own lexicon,
        not a constant picked here.

        The ratio is NOT a metric: `distance/n` violates the triangle
        inequality (6 cases in 314,432 grapheme-word triples — rare, but
        real). That is why it lives here as a cut-off criterion and not in
        `distance`, which stays metric so BK-trees and vp-trees keep working.
        """
        if theta is None:
            theta = (ONE_MOVE / self.median_length() if relative
                     else ONE_MOVE)
        restricted = words is not None
        left = self._words if not restricted else sorted(
            {normalize(w) for w in words} & set(self._tokens)
        )
        seen = set()
        for w in left:
            nw = len(self._compared_tokens(self._compare_of[w]))
            for d, c in self.search(w, k=pool, pool=pool):
                if relative:
                    span = max(nw,
                               len(self._compared_tokens(self._compare_of[c])), 1)
                    if d / span > theta + _EPS:
                        continue  # ratio is not monotone in d: do not break
                elif d > theta + _EPS:
                    break  # search results are sorted
                # Pairs are yielded once, ordered (a < b). On a full sweep
                # `w < c` suffices and costs no memory, because the pair is
                # reached again from the other side. Under `words=` it does
                # NOT: the partner may be outside `left` and never visited,
                # so half the pairs would silently vanish. Deduplicate
                # instead — the restricted set is small by definition.
                pair = (w, c) if w < c else (c, w)
                if restricted:
                    if pair in seen:
                        continue
                elif w >= c:
                    continue
                seen.add(pair)
                yield (pair[0], pair[1], d, edit_tag(*pair))

        if not constructions:
            return
        by_key = {}
        for word, construction in constructions.items():
            key = construction_key(construction)
            nw = normalize(word)
            if key and nw in self._tokens:
                by_key.setdefault(key, set()).add(nw)
        restrict = set(left)
        for group in by_key.values():
            for a in sorted(group):
                for b in sorted(group):
                    if a < b and (a in restrict or b in restrict) \
                            and (a, b) not in seen:
                        yield (a, b,
                               distance(self._compared_tokens(self._compare_of[a]),
                                        self._compared_tokens(self._compare_of[b]),
                                        lenient=True),
                               "=construction")
