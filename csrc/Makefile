# The C core: a static library, and its own test suite.
#
#     make -C csrc            # build/libabugida.a
#     make -C csrc check      # build it and run the C tests (needs tests/c/pairs.txt)
#     make -C csrc clean
#
# Three suites run under `check`: `test_abugida.c` checks that the metric is
# RIGHT (the published scale, the metric axioms, the documented examples), and
# `test_edge_cases.c` checks that the library is SOUND (empty words, NULL
# arguments, heap-path words, broken UTF-8, leaks, and the domain in which the
# triangle inequality actually holds).
#
# The Python package does not use this makefile — `pip install .` compiles the
# same sources through the Cython extension — but a C or C++ consumer does,
# and the test suite is what proves the core stands on its own with no Python
# in the process.

CC ?= cc
AR ?= ar
CFLAGS ?= -O2
CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -I.
# The bit-parallel Levenshtein kernel. Defining this is what
# makes `levenshtein` use it; the DP stays compiled as the
# fallback for words longer than one machine word, so removing
# the define is a complete and correct build.
CFLAGS += -DABUGIDA_USE_MYERS
LDLIBS ?= -lm

BUILD ?= ../build/c
LIB = $(BUILD)/libabugida.a
TEST = $(BUILD)/test_abugida
EDGE = $(BUILD)/test_edge_cases
MYERS = $(BUILD)/test_myers
BENCH = $(BUILD)/bench_impl
BOUNDED = $(BUILD)/test_bounded
PAIRS = ../tests/c/pairs.txt

# THE KERNEL IS COMPILED ONCE PER INSTRUCTION SET, from one source, and a
# dispatcher in abugida.c picks between them (abugida_impl_select). The probes
# below decide which ones this toolchain and target can build; the C variant
# always can, and it is the one that answers on a target without the others.
#
#     make -C csrc IMPL=1     # force a single variant, no dispatch
#
PROBE_SSE2 = -march=x86-64-v2
PROBE_AVX2 = -march=x86-64-v3

.PHONY: all check bench clean

all: $(LIB)

$(BUILD):
	mkdir -p $(BUILD)

# Does the toolchain accept these flags FOR THIS TARGET? A probe object, not a
# guess: a cross-compiler or a stripped `cc` is where the guess is wrong, and
# being wrong costs a build that does not link.
# THE PROBES RUN ONCE, at parse time, and their answer is a variable — not a
# marker file whose existence `$(wildcard)` reads before the recipe that would
# create it has run. The marker-file version of this raced with itself: make
# computed OBJECTS from a filesystem that did not yet have the probe results,
# then tried to archive objects nothing had built.
#
# Only an x86-64 target has these instruction sets at all, and a toolchain may
# reject the flags even there, so the probe compiles a throwaway object with
# the real flags.
# Asking `cc -dumpmachine` rather than `uname`: a cross-compiler for ARM on
# an x86 host is exactly the case where the host's answer would be wrong.
IS_X86_64 = $(findstring x86_64,$(shell $(CC) -dumpmachine))

ifeq ($(strip $(IS_X86_64)),)
HAVE_SSE2 =
HAVE_AVX2 =
else
HAVE_SSE2 = $(shell $(CC) $(CFLAGS) -DABUGIDA_MYERS_SUFFIX=_sse2 $(PROBE_SSE2) -c abugida_myers.c -o /dev/null 2>/dev/null && echo 1)
HAVE_AVX2 = $(shell $(CC) $(CFLAGS) -DABUGIDA_MYERS_SUFFIX=_avx2 $(PROBE_AVX2) -c abugida_myers.c -o /dev/null 2>/dev/null && echo 1)
endif

# IMPL=1 builds the C variant alone, so abugida.c must not be told the other
# two exist — it would reference symbols the archive does not contain, and the
# failure would surface as a link error in a consumer's build. The defines and
# the object list come from the SAME condition, which is the only way the two
# translation units cannot disagree.
ifdef IMPL
HAVE_DEFINES =
else
HAVE_DEFINES = $(if $(HAVE_SSE2),-DABUGIDA_HAVE_SSE2)
HAVE_DEFINES += $(if $(HAVE_AVX2),-DABUGIDA_HAVE_AVX2)
endif

# The C variant, always. `abugida_myers_c.o` and its siblings are built by
# these explicit rules and by NO pattern rule — an earlier version kept a
# generic `$(BUILD)/%.o` rule alongside them, and make then preferred the
# implicit recipe for the suffixed objects, so the archive was linked with
# undefined references to two of the three variants.
$(BUILD)/abugida_myers_c.o: abugida_myers.c abugida.h abugida_tables.h | $(BUILD)
	$(CC) $(CFLAGS) -DABUGIDA_MYERS_SUFFIX=_c -c $< -o $@

$(BUILD)/abugida_myers_sse2.o: abugida_myers.c abugida.h abugida_tables.h | $(BUILD)
	$(CC) $(CFLAGS) -DABUGIDA_MYERS_SUFFIX=_sse2 $(PROBE_SSE2) -c $< -o $@

$(BUILD)/abugida_myers_avx2.o: abugida_myers.c abugida.h abugida_tables.h | $(BUILD)
	$(CC) $(CFLAGS) -DABUGIDA_MYERS_SUFFIX=_avx2 $(PROBE_AVX2) -c $< -o $@

# `abugida.c` must know which variants exist, to declare them and to dispatch.
# The defines come from the same probes, so the two translation units cannot
# disagree about what is in the library. That matters: abugida.c would call a
# symbol the archive does not contain, and the failure would be a link error
# in the consumer's build rather than here.
$(BUILD)/abugida.o: abugida.c abugida.h abugida_tables.h | $(BUILD)
	$(CC) $(CFLAGS) $(HAVE_DEFINES) -c $< -o $@

$(BUILD)/abugida_tables.o: abugida_tables.c abugida.h abugida_tables.h | $(BUILD)
	$(CC) $(CFLAGS) $(HAVE_DEFINES) -c $< -o $@

ifdef IMPL
# IMPL=1 collapses the three into the C variant alone: one kernel, no dispatch.
# It is how the assembler-free build is exercised.
OBJECTS = $(BUILD)/abugida.o $(BUILD)/abugida_tables.o $(BUILD)/abugida_myers_c.o
else
OBJECTS = $(BUILD)/abugida.o $(BUILD)/abugida_tables.o $(BUILD)/abugida_myers_c.o
OBJECTS += $(if $(HAVE_SSE2),$(BUILD)/abugida_myers_sse2.o)
OBJECTS += $(if $(HAVE_AVX2),$(BUILD)/abugida_myers_avx2.o)
endif

$(LIB): $(OBJECTS)
	$(AR) rcs $@ $(OBJECTS)

$(TEST): ../tests/c/test_abugida.c $(LIB)
	$(CC) $(CFLAGS) $< $(LIB) $(LDLIBS) -o $@

$(EDGE): ../tests/c/test_edge_cases.c $(LIB)
	$(CC) $(CFLAGS) $< $(LIB) $(LDLIBS) -o $@

$(BOUNDED): ../tests/c/test_bounded.c $(LIB)
	$(CC) $(CFLAGS) $< $(LIB) $(LDLIBS) -o $@

$(BENCH): ../tests/c/bench_impl.c $(LIB)
	$(CC) $(CFLAGS) $< $(LIB) $(LDLIBS) -o $@

$(MYERS): ../tests/c/test_myers.c $(LIB)
	$(CC) $(CFLAGS) $< $(LIB) $(LDLIBS) -o $@

# `check` needs the generated fixture. It is committed, so this only fails if
# someone deleted it; the generator writes it.
check: $(TEST) $(EDGE) $(MYERS) $(BOUNDED)
	@test -f $(PAIRS) || { \
	  echo "$(PAIRS) is missing: run python tools/generate_c_tables.py"; exit 1; }
	$(TEST) $(PAIRS)
	$(EDGE)
	$(MYERS)
	$(BOUNDED)

# Not part of `check`: a measurement, and a measurement inside a test suite is
# a test that fails on a loaded machine.
bench: $(BENCH)
	@for v in `$(BENCH) --list`; do $(BENCH) $$v; done

clean:
	rm -rf $(BUILD)
