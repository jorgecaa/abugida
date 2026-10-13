"""THE entry point. If you are integrating abugida, use this and nothing else.

    from abugida import Comparator

    cmp = Comparator(words)                 # validates as it builds
    cmp.neighbours("dhamma")                # nearest words, ranked
    cmp.variants()                          # every variant pair in the lexicon
    cmp.rejected                            # what was refused, and why

Everything under this — `Lexicon`, `distance`, `phonological_form`, the
thresholds — is the layer below. It stays public because the theory is the
point of the project and because other tasks exist, but a variant pipeline
should not have to assemble it. Assembling it by hand is what produced two
bugs and a 47%-instead-of-96% recipe in one afternoon: the pieces compose in
several plausible ways and only one is right.

WHAT THIS FIXES, concretely. The recommended configuration was five decisions
spread over three call sites — `normalise=True`, `relative=True`, a `theta`
on a different scale from the absolute one, a `pool` whose default
contradicted the published figures, and `constructions=`. Here it is one
object with one named recall setting.

WHAT GOES IN, AND WHERE
=======================

**The lexicon** (the constructor) takes the words you want to FIND: headwords,
lemmas, an index. They are validated strictly and anything unusable is kept
out and reported, because a lexicon that silently indexes junk gives answers
nobody can audit.

**The query** (`neighbours`, `variants(words=…)`) takes what you are looking
WITH. Validated the same way by default, because a typo scored from opaque
tokens returns plausible nonsense — worse than an error. Behind a search box
you do not want that: pass `lenient=True` and get a best effort instead.

**Nothing here takes sentences, phrases or word-splits.** One word per entry.

    Comparator(headwords)                       # the lexicon
    cmp.neighbours(user_input, lenient=True)    # the query, defensively

Measured before choosing the gate: all 75,367 DPD lemmas pass strict
tokenisation, so it refuses nothing legitimate. `is_possible` would be
stricter still and reject 1.1% of real lemmas — considered and not used.

SANSKRITISED PĀLI IS PĀLI
=========================

Pāli carries Sanskritised doublets — `tatra` beside `tattha`, `atra` beside
`attha` — and they are real lemmas in DPD, not errors. They tokenise cleanly
(every grapheme is Pāli) so nothing here rejects them, but be aware of two
limits:

- The METRIC does not price the correspondences cheaply. `tatra ~ tattha` is
  0.831 and lands at ratio 0.166 — just outside `"balanced"` (0.16), inside
  `"exhaustive"`. `sarva ~ sabba` is 1.276 and outside all three. Sanskrit→
  Pāli reflexes are SYSTEMATIC sound change (`tr`→`tth`, `rv`→`bb`:
  correlated edits), and edit distance assumes independent ones. SPEC §9.7 is
  explicit that closing this needs a transducer of the sound laws — another
  machine, buildable on the phonotactics — not a finer metric. Until then:
  use `"exhaustive"` if these matter to you.
- Forms carrying actual Sanskrit graphemes (`ṛ ṣ ś`: `kṣetta`, `kṛṣṇa`) are
  refused by default, because in a Pāli lexicon they are far more often an
  encoding mistake than a decision. If you mean them, say so:
  `accept="pali+sanskrit"`. Those three graphemes carry real phonology in the
  comparison (ṣ↔s costs 0.460, ś↔s 0.667), which is what makes cross-system
  Sanskrit↔Pāli work possible at all.

IF YOU NEED SOMETHING THIS DOES NOT ALLOW
=========================================

This class is deliberately narrow. It is not a wall: `cmp.lexicon` is the
`Lexicon` underneath, unvalidated and fully permissive, and every layer below
it is exported from the package. Reach for them when you have a reason —
a different threshold, a metric-only comparison, your own prefilter — and
read `docs/comparator.md` for what each guarantees. What you lose by going
around is the configuration that produces the published numbers, so measure
what you build.

RECALL SETTINGS are named rather than numeric, because the numbers are not
comparable across modes and copying one from a table is the easy mistake.
Each setting's AGREEMENT WITH DPD, the share of the 5,002 pairs in DPD's
`var_phonetic` (August 2026 build) it also generates — not accuracy: DPD's
own rules compute that field (README, "Agreement with DPD is not
accuracy"):

    setting     agreement   candidates per lemma
    "precise"       86.2%           3.6
    "balanced"      91.4%           9.1      (default)
    "exhaustive"    95.1%          26.6

These three are a product decision, not derived constants like ρ* or
INDEL_WEIGHT — they are measured operating points on a curve, and the
docstring says which. To pick a threshold against a precision budget on your
own corpus instead, see `abugida.channel`.
"""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

from .iast import diagnose, normalize, tokenize
from .lexicon import Lexicon

#: Measured operating points (see the module docstring). Values are relative
#: thresholds: distance divided by the longer word's token count.
RECALL_SETTINGS: Dict[str, float] = {
    "precise": 0.12,
    "balanced": 0.16,
    "exhaustive": 0.22,
}

#: What the constructor will admit. "pali" is the Pāli inventory only;
#: "pali+sanskrit" additionally allows ś, ṣ and ṛ, which carry real phonology
#: in the comparison (ṣ↔s 0.460, ś↔s 0.667) and make cross-system work
#: possible. Nothing widens the gate to arbitrary characters.
ACCEPTS = ("pali", "pali+sanskrit")

#: Shortlist width. The `Lexicon` default of 50 loses several points at the
#: looser settings; 150 is where the curve flattens.
POOL = 150


class Comparator:
    """A validated Pāli lexicon with the recommended pipeline built in."""

    def __init__(self, words: Iterable[str], recall: str = "balanced",
                 constructions: Optional[Mapping[str, str]] = None,
                 accept: str = "pali"):
        if recall not in RECALL_SETTINGS:
            raise ValueError(
                f"recall must be one of {sorted(RECALL_SETTINGS)}, "
                f"not {recall!r}"
            )
        if accept not in ACCEPTS:
            raise ValueError(
                f"accept must be one of {sorted(ACCEPTS)}, not {accept!r}"
            )
        self.recall = recall
        self.accept = accept
        self._theta = RECALL_SETTINGS[recall]
        self._constructions = dict(constructions) if constructions else None

        accepted: List[str] = []
        rejected: Dict[str, str] = {}
        for word in words:
            nw = normalize(word)
            if not nw:
                continue
            reason = self._reject_reason(nw)
            if reason:
                rejected[word] = reason
            else:
                accepted.append(nw)
        #: {word: reason} for everything kept out of the index.
        self.rejected: Dict[str, str] = rejected
        #: The `Lexicon` underneath — permissive, unvalidated, and public on
        #: purpose. The documented way out when this class is too narrow.
        self.lexicon = Lexicon(accepted, normalise=True)

    def _reject_reason(self, word: str) -> Optional[str]:
        """None if the word is admissible under `accept`, else why not."""
        try:
            tokenize(word)  # STRICT: the Pāli inventory only
            return None
        except ValueError:
            pass
        if self.accept == "pali+sanskrit":
            # ś ṣ ṛ carry real phonology in the comparison; anything else is
            # still junk, so this widens the gate rather than opening it.
            offenders = [ch for _, ch, kind in diagnose(word)
                         if kind != "sanskrit"]
            if not offenders:
                return None
        return self._explain(word)

    @staticmethod
    def _explain(word: str) -> str:
        parts = [f"{ch!r} ({kind})" for _, ch, kind in diagnose(word)]
        return "not Pāli: " + ", ".join(parts) if parts else "not Pāli"

    def __len__(self) -> int:
        return len(self.lexicon)

    def __contains__(self, word: str) -> bool:
        return word in self.lexicon

    def _check(self, word: str, lenient: bool = False) -> str:
        """Queries are validated too, and loudly: a typo silently scored as
        an opaque token returns plausible nonsense, which is worse than an
        error. `lenient=True` is the escape hatch for a search box, where a
        best effort beats an exception."""
        nw = normalize(word)
        if lenient:
            return nw
        reason = self._reject_reason(nw)
        if reason:
            raise ValueError(
                f"{word!r} is {reason}. Pass lenient=True for a best-effort "
                "match, or use .lexicon directly."
            )
        return nw

    def neighbours(self, word: str, k: int = 5,
                   lenient: bool = False) -> List[Tuple[float, str]]:
        """The k nearest words as (distance, word), nearest first.

        Use this for "what is this word close to". Distances are raw and
        comparable across queries; the recall setting does not apply, since
        nothing is being thresholded.

        `lenient=True` accepts anything without raising — non-Pāli characters
        become opaque tokens costing 1 against everything, so the intact
        remainder of the word still discriminates. That is what you want
        behind a search box and not what you want when curating a lexicon.
        Report what was absorbed with `iast.diagnose`.
        """
        return self.lexicon.search(self._check(word, lenient), k=k, pool=POOL)

    def variants(self, words: Optional[Iterable[str]] = None,
                 recall: Optional[str] = None
                 ) -> Iterator[Tuple[str, str, float, str]]:
        """Yield (a, b, distance, tag) for every variant pair, once each.

        `words` restricts which words are considered, for batching a large
        lexicon; every pair involving them is still returned.

        `recall` overrides the setting for this call. The index does NOT
        depend on it — only a threshold does — so comparing settings needs
        ONE Comparator, not one per setting:

            cmp = Comparator(words)                    # build once
            for setting in ("precise", "balanced"):
                rows = cmp.variants(recall=setting)    # re-thresholds only

        The whole recommended pipeline is applied: normalisation, the
        length-relative budget, and the construction criterion if
        constructions were supplied.
        """
        if recall is not None and recall not in RECALL_SETTINGS:
            raise ValueError(
                f"recall must be one of {sorted(RECALL_SETTINGS)}, "
                f"not {recall!r}"
            )
        theta = self._theta if recall is None else RECALL_SETTINGS[recall]
        checked = None if words is None else [self._check(w) for w in words]
        return self.lexicon.variants(
            theta=theta,
            relative=True,
            pool=POOL,
            words=checked,
            constructions=self._constructions,
        )
