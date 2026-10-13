"""Where the evaluation scripts find their third-party case files.

The case files are extractions from works that are not this project's to
license: Oberlies' grammar (De Gruyter), Geiger's grammar (Pali Text Society)
and the Digital Pāḷi Dictionary's `var_phonetic` pairs. They are therefore
not in the repository and not in any distribution (see `NOTICE`). Each user
keeps them locally, in `eval/data/` (ignored by git) or in the directory
named by the environment variable `ABUGIDA_EVAL_DATA`.

A script whose case file is missing says which file and where it looks, and
exits 0 — the same convention the scripts follow when the DPD database is
absent (`eval/_dpd.py`). Files that can be rebuilt are rebuilt by their own
script: `geiger.py --harvest`, `hard_battery.py --harvest --dpd`,
`oberlies_attested.py --dpd`. `oberlies_cases.json` cannot: it was read by
eye from page images of the printed book, so it exists only where it was
transcribed.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("ABUGIDA_EVAL_DATA") or os.path.join(HERE, "data")


def path(name):
    """The local path of a case file, whether or not it exists."""
    return os.path.join(DATA, name)


def exists(name):
    return os.path.exists(path(name))


def require(*names):
    """Exit 0 with a message naming the first missing case file."""
    for name in names:
        if not exists(name):
            print(f"skipped: needs the case file {path(name)}\n"
                  "  It is third-party data and is not distributed with "
                  "abugida (see NOTICE);\n"
                  "  put your local copy there, or set ABUGIDA_EVAL_DATA "
                  "to its directory.")
            sys.exit(0)


def load(name):
    """Load a JSON case file, exiting 0 if it is missing."""
    require(name)
    with open(path(name), encoding="utf-8") as fh:
        return json.load(fh)
