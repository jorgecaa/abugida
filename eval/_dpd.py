"""The one place the evaluation scripts open the DPD database.

The library and its tests never touch DPD; only the scripts in this directory
do, as the lexicon and as the reference they measure agreement with
(`var_phonetic`, which DPD's own rules compute: not a ground truth). By default
they do not use it: a script that needs DPD says so and exits cleanly (status
0) instead of failing on a missing database. Pass `--dpd` to use it, with the
database at its usual place (`/dev/shm/dpd.db`, else `../dpd-db/dpd.db`), or
`--dpd PATH` / `--dpd=PATH` to name the file. An explicit PATH wins over any
path a script would have chosen itself.

The flag (and its PATH) is read here, at import, and removed from `sys.argv`
so scripts that parse their arguments never see it. PATH is taken from the
next argument only when it ends in `.db` or names an existing file, so
`--dpd` followed by a script's own positional argument stays unambiguous.
`hard_battery.py` is the one script whose default run needs no DPD (it reads
the committed case file); there `--dpd` is only needed for `--harvest`.
"""

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = "/dev/shm/dpd.db"
FALLBACK = os.path.normpath(os.path.join(HERE, "..", "..", "dpd-db", "dpd.db"))

USE_DPD = False
PATH = None
_rest = [sys.argv[0]]
_args = iter(sys.argv[1:])
for _a in _args:
    if _a == "--dpd":
        USE_DPD = True
        _nxt = next(_args, None)
        if _nxt is not None:
            if not _nxt.startswith("-") and (_nxt.endswith(".db")
                                              or os.path.isfile(_nxt)):
                PATH = _nxt
            else:
                _rest.append(_nxt)
    elif _a.startswith("--dpd="):
        USE_DPD = True
        PATH = _a.split("=", 1)[1]
    else:
        _rest.append(_a)
sys.argv[:] = _rest


def check():
    """Exit 0 unless `--dpd` was given. Call it before any other import or
    read that could fail first (a missing optional package, a file of
    `../dpd-db`)."""
    if not USE_DPD:
        print(f"{sys.argv[0]}: this script needs the DPD database; pass "
              "--dpd [PATH] to use it. Nothing was run.", file=sys.stderr)
        sys.exit(0)


def resolve(path=None):
    """The database file to open: the explicit `--dpd PATH`, else the path
    the caller passed, else `/dev/shm/dpd.db` when it is there and not
    empty, else `../dpd-db/dpd.db`."""
    if PATH:
        return PATH
    if path and path != DEFAULT:
        return path
    if os.path.exists(DEFAULT) and os.path.getsize(DEFAULT) > 0:
        return DEFAULT
    return FALLBACK


def connect(path=None):
    """Open DPD read-only, or exit 0 unless `--dpd` was given. A missing
    file is reported by name instead of SQLite's bare 'unable to open'."""
    check()
    db = resolve(path)
    if not os.path.isfile(db):
        sys.exit(f"{sys.argv[0]}: no DPD database at {db}; "
                 "pass --dpd PATH to name it.")
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)
