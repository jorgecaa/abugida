"""The English-only convention, enforced instead of remembered.

CLAUDE.md requires that the files and their names be written in English,
whatever language the conversation that produced them was in. A convention
that lives only in prose is respected by whoever happens to read the prose;
this pins it.

WHAT CAN AND CANNOT BE CHECKED. Detecting a natural language from text is
not something this repository is going to do honestly, so the test splits
the problem in two and is explicit about the strength of each half:

- **The character sweep is exhaustive.** Every non-ASCII codepoint in every
  tracked file must be on the allow-list. That is a proof, not a sample: no
  language written with its own diacritics can hide from it.
- **The word tripwire is a heuristic.** Spanish written in bare ASCII passes
  the sweep, so a list of function words catches the realistic accident —
  a comment typed in the language of the conversation. Absence of a hit is
  evidence, not a guarantee, and the list is meant to grow when something
  slips through.

THE PĀLI ALLOWANCE IS DERIVED, NOT TYPED. Pāli and Sanskrit forms are the
subject matter, so their letters must be allowed; taking them from
`INVENTORY` and `FOREIGN` rather than from a hand-written string means the
allow-list follows the inventory if the inventory changes. Only what the
phonology has no opinion about — mathematical notation and typography — is
listed here by hand, grouped so that an addition has to say what kind of
thing it is.
"""

import re
import subprocess
import unicodedata
from pathlib import Path

import pytest

from abugida.phonology import FOREIGN, INVENTORY

ROOT = Path(__file__).resolve().parent.parent

# Derived: every non-ASCII letter the phonology itself knows about.
PALI = {c for p in INVENTORY for c in p.grapheme if not c.isascii()}
PALI |= {c for c in FOREIGN if not c.isascii()}
PALI |= {c.upper() for c in PALI}

# Indic letters outside the Pāli inventory, used when quoting Sanskrit (the
# visarga ḥ of the Sanskrit forms in the Oberlies case file) or
# the alternative niggahīta transliteration.
INDIC_EXTRA = set("ṝḹṁḥ")

# Greek, used as mathematical variables (ρ*, θ, λ, Σ), never as Greek text.
GREEK = set("ΓΔΣαβεθλπρφ")

# Mathematical and logical notation, including super/subscripts.
MATH = set("¬±×½²³ᵢ₁₂₃₆∂∅∈−√∝∧∨∪≅≈≠≡≤≥⊂⊆⊗⊙⊤⊥⊨°µ")

# Typography: dashes, quotation marks, arrows, section marks, box drawing.
TYPOGRAPHY = set("§«»·–—‘’…№←→↓↔↦⇒⇔─│└✦")

ALLOWED = PALI | INDIC_EXTRA | GREEK | MATH | TYPOGRAPHY

# Spanish function and content words that no English text would contain as
# whole words. Matched against an accent-stripped copy of the line, so the
# list itself stays ASCII — this file is swept by the character test
# like every other — while still catching the accented spellings.
#
# Two obvious candidates are deliberately absent: `para` and `asi` are also
# Pāli words (para "beyond", asi "sword"), and the subject matter wins over
# the tripwire. The collisions with English ("no", "a", "de", "son", "sin",
# "solo") are out for the same reason.
SPANISH = re.compile(
    r"\b(?:que|porque|pero|cuando|donde|aunque|entonces|siempre|nunca|"
    r"tambien|segun|aqui|debe|puede|tiene|hace|hacer|fichero|archivo|"
    r"palabra|cadena|ejemplo|prueba|pruebas|codigo|numero|nombre|linea|"
    r"regla|reglas|cambio|resultado|siguiente|cualquier|mismo|misma|"
    r"estos|estas|todos|todas)\b",
    re.IGNORECASE,
)


def unaccented(line):
    """An accented spelling and a bare one are the same slip."""
    return "".join(c for c in unicodedata.normalize("NFD", line)
                   if not unicodedata.combining(c))


def tracked():
    """The files git is responsible for — the ones the rule governs.

    `-z` is not a detail: without it `ls-files` renders a non-ASCII path as
    a C-quoted ASCII escape, which is exactly the case
    `test_filenames_are_ascii` exists to catch. It would have passed on a
    filename it could no longer see.
    """
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return [ROOT / name for name in out.stdout.split("\0") if name]


def readable():
    for path in tracked():
        try:
            yield path, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def test_every_non_ascii_character_is_pali_or_notation():
    offenders = []
    for path, text in readable():
        for lineno, line in enumerate(text.splitlines(), 1):
            for ch in line:
                if not ch.isascii() and ch not in ALLOWED:
                    rel = path.relative_to(ROOT)
                    offenders.append(f"{rel}:{lineno}: {ch!r} (U+{ord(ch):04X})")
    assert not offenders, (
        "non-ASCII characters outside the Pāli inventory and the notation "
        "allow-list — if this is another language, translate it; if it is "
        "notation, add it to the right group above:\n"
        + "\n".join(sorted(set(offenders))[:20])
    )


def test_no_spanish_slipped_in_from_the_conversation():
    offenders = []
    for path, text in readable():
        if path.name == Path(__file__).name:  # this file lists them on purpose
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if SPANISH.search(unaccented(line)):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:60]}")
    assert not offenders, (
        "Spanish text in files that must be English:\n" + "\n".join(offenders[:20])
    )


def test_filenames_are_ascii():
    offenders = [str(p.relative_to(ROOT)) for p in tracked()
                 if not str(p.relative_to(ROOT)).isascii()]
    assert not offenders, f"non-ASCII filenames: {offenders}"
