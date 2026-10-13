# Validating the Oberlies transcription

The case file `oberlies_cases.json` was read by eye from page images. This
directory checks that reading against the book, with a control that lets the
check fail. The sample files are drawn from that case file, so like it they
are third-party data and live in the local data directory, under
`eval/data/validation/` (see `NOTICE`); only the scripts are tracked.

## Files

- `oberlies_sample.tsv` — every pair from 15 randomly drawn pages
  (seed 20261013; pages 59, 70, 74, 100, 112 and 134 were excluded because
  they had already been re-read). **Ten rows carry a deliberately planted
  diacritic error**, indistinguishable from the rest.
- `oberlies_pages.tsv` — the same 15 pages, for the completeness count.
- `oberlies_sample.key.b64` — which rows were planted. **Do not decode it
  before the review is finished**; it is encoded only so it is not read by
  accident.
- `score.py` (tracked) — scores the review against the key.

## The review

For each row of `oberlies_sample.tsv`, find the pair on the printed page
(`printed_page`; `pdf_page` is the page of the scan) and fill in:

- `verdict`: `ok` if both forms match the book letter for letter, diacritics
  included; `wrong` otherwise.
- `correct_form`: for `wrong`, the form as the book prints it.

For each page of `oberlies_pages.tsv`, write in `pairs_printed_but_missing`
the number of pairs the page prints (a Pāli form with its Sanskrit source, or
two Pāli forms given as variants) that the sample does not contain, following
the exclusions in the case file's `note`.

## Reading the result

`python eval/validation/score.py` reports:

- planted errors caught out of ten — if not all ten, the review was not fine
  enough for its clean rows to mean anything;
- errors found in unplanted rows — real transcription errors;
- the error rate on the unplanted rows, with a 95% upper bound;
- the pairs missed per page.
