"""Build configuration for the Cython extension.

`pyproject.toml` is the package's metadata; this file exists because a Cython
extension needs to be *declared* — what it compiles, where the headers are,
which C standard. Everything else about the build is setuptools' default.

The C core (`csrc/abugida.c` and the generated `csrc/abugida_tables.c`) is
compiled into the extension, so there is no shared library to install and no
runtime dependency: `pip install .` produces a package that links nothing.
The same two files still build standalone with `make -C csrc` for a C
consumer, and `tests/c/test_abugida.c` is that consumer. One source, two ways
in.

Two details here are load-bearing rather than stylistic:

- **The include directory is absolute.** The core files are listed in
  `sources` (that is what makes setuptools compile them) and in `depends`
  (rebuild tracking); `include_dirs` carries `csrc` absolute so the headers
  are found from setuptools' build tree and from an sdist built in a
  temporary directory alike. See the loop below.
- **`-std=c99` is passed explicitly** to GCC and Clang. The core uses declarations after
  statements, and the default standard on older toolchains is C89. `-O3` is
  deliberately NOT passed: setuptools already passes the interpreter's own
  optimisation flags, and overriding them would make this extension's build
  differ from the rest of a wheel.

`cythonize` is imported at the top because the build system declares Cython in
`pyproject.toml`; a machine with the generated `_cabugida.c` but no Cython
does not get this far, which is the correct failure.
"""

import os
import re
import shlex
import subprocess
import sysconfig
import tempfile
from pathlib import Path

from Cython.Build import cythonize
from setuptools import setup
from setuptools.command.build_ext import build_ext

ROOT = Path(__file__).parent
CSRC = ROOT / "csrc"

EXTRA_COMPILE_ARGS = ["-std=c99", "-Wall", "-Wextra"]

#: The C core, compiled into the extension. Order does not matter; all three
#: are self-contained translation units.
CORE = ["abugida.c", "abugida_tables.c"]

#: The bit-parallel Levenshtein kernel is only *used* when this is defined,
#: and the DP remains compiled as the fallback for words longer than one
#: machine word — so a build without it is complete and correct, just slower.
#: That is what makes the kernel optional rather than a new requirement.
DEFINES = [("ABUGIDA_USE_MYERS", "1")]

#: The kernel is compiled once per instruction set, from ONE source, and the
#: dispatcher picks between them at run time. The names are the same ones
#: csrc/Makefile builds, so the C consumer and the Python package have the
#: same set of variants rather than two builds that drift.
KERNEL_VARIANTS = [
    ("_c", None),
    ("_sse2", ["-march=x86-64-v2"]),
    ("_avx2", ["-march=x86-64-v3"]),
]


def _target_arch_flags():
    """The `-arch` flags the extension itself will be compiled with.

    On macOS the python.org interpreters build universal2 extensions —
    `-arch x86_64 -arch arm64` in one compile — and `ARCHFLAGS` can ask for
    the same. A probe without them asks about the build machine alone: on an
    Intel Mac `-march=x86-64-v2` passes the probe, is then applied to the
    arm64 half too, and the whole compile fails (measured on the CI's
    macos-15-intel runner, where the package silently fell back to pure
    Python). Probing with the same `-arch` flags makes that variant fail the
    probe instead, and the universal build keeps the C kernel alone.
    """
    source = os.environ.get("ARCHFLAGS") or sysconfig.get_config_var("CFLAGS") or ""
    words = shlex.split(source)
    flags = []
    for i, word in enumerate(words[:-1]):
        if word == "-arch":
            flags += ["-arch", words[i + 1]]
    return flags


def _can_compile(flags):
    """Does this toolchain accept these flags for this target?

    A probe rather than a guess from `platform.machine()`: a cross-compiler or
    a stripped `cc` is exactly where the guess is wrong, and the cost of being
    wrong is an extension that does not link. The probe compiles a throwaway
    object with the real flags, and a failure is a fallback rather than an
    error — the C variant is always built and always correct.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cc = os.environ.get("CC") or "cc"
        cmd = cc.split() + _target_arch_flags() + (flags or []) + [
            "-c", str(CSRC / "abugida_myers.c"),
            "-o", os.path.join(tmp, "probe.o"),
            "-I", str(CSRC), "-std=c99",
            "-DABUGIDA_MYERS_SUFFIX=_probe",
        ]
        try:
            return subprocess.run(cmd, capture_output=True, check=False
                                  ).returncode == 0
        except OSError:
            # No `cc` on PATH: a toolchain setuptools can use but this probe
            # cannot name. Build without the extra variants rather than guess.
            return False


#: Which variants this build contains, and the define that tells abugida.c so.
_VARIANTS = [("_c", None)]
HAVE_DEFINES = []
for _suffix, _flags in KERNEL_VARIANTS[1:]:
    if _can_compile(_flags):
        _VARIANTS.append((_suffix, _flags))
        HAVE_DEFINES.append(("ABUGIDA_HAVE" + _suffix.upper(), "1"))
    else:
        print(f"note: building without the {_suffix.lstrip('_')} kernel variant")

DEFINES = DEFINES + HAVE_DEFINES


def _write_variant_sources():
    """One file per kernel variant, so setuptools compiles each of them.

    setuptools de-duplicates `sources`, and it compiles every entry with the
    SAME `extra_compile_args` — there is no per-source hook. So the variants
    cannot be "one file compiled three times with different flags": listing
    one path three times produces one object and a duplicate-symbol link
    error, which is exactly what the first version of this did.

    What works is three files that differ only in the macro that renames their
    symbols. They are generated next to their objects rather than committed:
    the real source is `csrc/abugida_myers.c`, and a checked-in copy of it per
    instruction set would be three files to keep in step by hand.

    Returns the paths, plus the define that belongs to each.
    """
    source = (CSRC / "abugida_myers.c").read_text(encoding="utf-8")
    # The generated file sits in the build tree, so its include of the public
    # header has to be absolute.
    # The generated copy sits in the build tree, so `#include "abugida.h"`
    # would not find the header next to the original — and an absolute path
    # in the INCLUDE LINE is not the fix either, because `sources` and the
    # include resolutions have to survive a build in a temporary directory.
    # `include_dirs` carries `csrc` (absolute, which setuptools allows there;
    # it is `sources` that must be relative), so the header is found by name
    # from anywhere.
    body = re.sub(r'#include "abugida\.h"', '#include "abugida.h"', source)
    made = []
    for suffix, _flags in _VARIANTS:
        path = BUILD / f"abugida_myers{suffix}.c"
        header = (
            f"/* GENERATED by setup.py from csrc/abugida_myers.c — do not edit.\n"
            f" * The {suffix.lstrip('_')} build of the kernel: same source, the\n"
            f" * symbol suffix below, and the instruction-set flags setup.py adds\n"
            f" * to the whole extension. */\n"
            f"#define ABUGIDA_MYERS_SUFFIX {suffix}\n"
        )
        path.write_text(header + body, encoding="utf-8")
        made.append(path)
    return made


#: Where the generated variant sources live. Inside `build/`, so a clean build
#: directory regenerates them and nothing stale is ever compiled.
BUILD = ROOT / "build" / "csrc_variants"
BUILD.mkdir(parents=True, exist_ok=True)
VARIANT_SOURCES = _write_variant_sources()

extensions = cythonize(
    ["abugida/_cabugida.pyx"],
    language_level=3,
    compiler_directives={
        "boundscheck": False,
        "wraparound": False,
        "cdivision": True,
        "language_level": 3,
    },
)

for ext in extensions:
    # The C core is compiled and linked in. It is listed in `sources` because
    # that is what makes setuptools compile it — and the price is that
    # setuptools copies it into its build tree, so the copy needs its header
    # beside it. `include_dirs` would not help there: the copy's own
    # directory is searched first, and an older abugida_tables.h sitting in
    # the build tree would win. Regenerating therefore requires a clean
    # build directory (`rm -rf build/temp*`), which the Makefile-side checks
    # in `tools/generate_c_tables.py --check` and the parity test enforce
    # from the source side. `depends` marks the same files for rebuild
    # tracking, so a change here does not need a full `build_ext --force`.
    ext.sources = list(ext.sources) + [f"csrc/{name}" for name in CORE]
    ext.depends = list(ext.depends) + [f"csrc/{name}" for name in CORE]
    # One compile per variant, from the same source, each with the define that
    # renames its symbols. `extra_compile_args` cannot be per-source in
    # setuptools, so the instruction-set flags are applied to the whole
    # extension: the core is compiled with them too, which is harmless — it is
    # the kernel that is selectable, and the dispatcher only calls a variant
    # the CPU has been shown to support.
    ext.sources = list(ext.sources) + [str(p) for p in VARIANT_SOURCES]
    ext.depends = ext.depends + ["csrc/abugida_myers.c"]
    # The instruction-set flags go on the whole extension, because setuptools
    # has no per-source hook. Harmless for the rest of the core — the kernel
    # is the only thing that is selectable, and the dispatcher calls a variant
    # only after CPUID says this CPU has it.
    _flags = []
    for _suffix, _variant_flags in _VARIANTS:
        _flags.extend(_variant_flags or [])
    ext.extra_compile_args = list(ext.extra_compile_args) + _flags
    # ABSOLUTE here, and that is deliberate: `sources` must be relative to
    # `setup.py` or setuptools refuses them, but `include_dirs` has no such
    # rule, and a relative one resolves against the COMPILER's working
    # directory rather than the project's — which is why the first attempt
    # failed with "csrc/abugida.h: No such file" while building from an sdist
    # in a temp directory.
    ext.include_dirs = list(ext.include_dirs) + [str(CSRC.resolve())]
    ext.extra_compile_args = list(ext.extra_compile_args) + EXTRA_COMPILE_ARGS
    ext.define_macros = list(ext.define_macros or []) + DEFINES
    # libm, for the acos and sqrt of the cost table's calibration.
    ext.libraries = list(ext.libraries) + ["m"]
    # OPTIONAL, so a machine with no C compiler still installs the package:
    # setuptools turns a failed compile of an optional extension into a
    # warning, and `abugida.distance` then answers from the pure-Python
    # reference with the same values. Without this the README's promise was
    # false — measured: `CC=/bin/false pip install abugida-*.tar.gz` failed
    # with "Failed to build installable wheels".
    ext.optional = True

#: Flags only GCC and Clang understand. MSVC warns on unknown options rather
#: than failing, but the warnings bury real ones, and `-march` would select
#: nothing; the C core needs no flag there (MSVC compiles C99 declarations
#: after statements by default, and `__builtin_cpu_supports` is guarded).
GCC_ONLY = set(EXTRA_COMPILE_ARGS)


class BuildExt(build_ext):
    """The declarations above are written for GCC and Clang (Linux, macOS);
    this adapts them to MSVC (Windows), where there is no `libm` to link —
    the maths is in the C runtime — and none of the flags apply. Decided on
    the compiler setuptools actually chose, not on the platform name, so a
    MinGW build on Windows keeps the GCC flags."""

    def build_extensions(self):
        if self.compiler.compiler_type == "msvc":
            for ext in self.extensions:
                ext.extra_compile_args = [
                    a for a in ext.extra_compile_args
                    if a not in GCC_ONLY and not a.startswith("-march")
                ]
                ext.libraries = [lib for lib in ext.libraries if lib != "m"]
        super().build_extensions()


setup(ext_modules=extensions, cmdclass={"build_ext": BuildExt})
