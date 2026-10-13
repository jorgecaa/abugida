"""abugida — a phonological comparator for Pāli words (IAST).

START HERE: `Comparator`. It is the entry point, it validates its input, and
it has the recommended pipeline built in.

    from abugida import Comparator
    cmp = Comparator(words)
    cmp.variants()

Everything else exported below is the layer underneath — the algebra, the
embedding, the metric, the thresholds. It stays public because the theory is
the point of the project, but a variant pipeline should not have to assemble
it by hand.

The product is the distance: an edit metric whose substitution costs come
from the phonological algebra of Pāli. Integration guide in
docs/comparator.md; theoretical foundation in SPEC.md.
"""

# THE ENTRY POINT
from .comparator import RECALL_SETTINGS, Comparator

# The metric underneath
from .distance import (
    algebraic_cost,
    alignment,
    cost,
    distance,
    levenshtein,
    neighbors,
)

# Experimental, not part of the model: the componentwise weighted
# alternative to the angular cost (SPEC §4).
from .distance import L1_MODIFIER_WEIGHT, weighted_cost, weighted_distance

# Recommended pipeline: phonology first, metric second
from .sandhi import CONTRACTIONS, assimilate_word, contract_word, sandhi_join

# Input: normalisation, tokenisation, validation
from .iast import diagnose, normalize, tokenize, transcribe, vectors
from .phonotactics import is_possible, pseudoword

# Candidate generation: legal sequences (above) or formable words (here)
from .morphology import (
    ROOTS,
    Formation,
    Root,
    formations,
    pseudoform,
    pseudoword_morphological,
)

# Integration adapter: search + variant generation over a word list
from .lexicon import ONE_MOVE, Lexicon, edit_tag, phonological_form

# Calibration: read a threshold as an expected precision (SPEC §9.2)
from .channel import Channel, Strata, fit_channel, fit_strata

# Presenting results: Pāli alphabetical order
from .alphabet import ALPHABET, sort_key, sort_words

# Supporting layers (the foundation of the cost)
from .algebra import A, compose, mult

# Experimental, not part of the model: the counterfactuals of SPEC §1.1 —
# the XOR variant (a ring, Z/6Z) and the boolean reading (De Morgan, not
# boolean, so its derived sum is not XOR).
from .algebra import (
    LATTICE_BOTTOM,
    LATTICE_TOP,
    and_,
    compose_xor,
    not_,
    or_,
    sum_,
)
from .embed import DIM, cosine, embed
from .phonology import INVENTORY, PLACES, assimilate, is_voiced, phoneme

__all__ = [
    # the entry point
    "Comparator",
    "RECALL_SETTINGS",
    # comparator
    "distance",
    "levenshtein",
    "cost",
    "algebraic_cost",
    "neighbors",
    "alignment",
    # experimental
    "weighted_cost",
    "weighted_distance",
    "L1_MODIFIER_WEIGHT",
    # pipeline
    "assimilate_word",
    "contract_word",
    "CONTRACTIONS",
    "sandhi_join",
    # input
    "is_possible",
    "pseudoword",
    # generation
    "ROOTS",
    "Root",
    "Formation",
    "formations",
    "pseudoform",
    "pseudoword_morphological",
    "diagnose",
    "normalize",
    "tokenize",
    "transcribe",
    "vectors",
    # adapter
    "Lexicon",
    "edit_tag",
    "ONE_MOVE",
    "phonological_form",
    "Channel",
    "fit_channel",
    "Strata",
    "fit_strata",
    # presentation
    "ALPHABET",
    "sort_key",
    "sort_words",
    # support
    "A",
    "compose",
    "compose_xor",
    "or_",
    "and_",
    "not_",
    "sum_",
    "LATTICE_BOTTOM",
    "LATTICE_TOP",
    "mult",
    "DIM",
    "cosine",
    "embed",
    "INVENTORY",
    "PLACES",
    "assimilate",
    "is_voiced",
    "phoneme",
]
