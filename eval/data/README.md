# Local case files

This directory is ignored by git, except for this file. It holds the
third-party case files the evaluation scripts read (see `../../NOTICE` and
`../_data.py`); they are never committed. Set `ABUGIDA_EVAL_DATA` to keep
them elsewhere.

| file | read by | how to make it |
|---|---|---|
| `oberlies_cases.json` | `oberlies.py`, `oberlies_attested.py`, `triangle_geminates.py`, `validation/` | read by eye from page images of the printed grammar; cannot be regenerated |
| `oberlies_attested.json` | `oberlies.py` (section 7, optional) | `python eval/oberlies_attested.py --dpd` |
| `geiger_cases.json` | `geiger.py`, `oberlies.py`, `triangle_geminates.py` | `python eval/geiger.py --harvest PATH` over your own OCR of the grammar |
| `Geiger_Pali_Grammar_OCR.txt` | `geiger.py --harvest` (default path) | your own OCR, NFC-normalised UTF-8 |
| `hard_battery.json` | `hard_battery.py`, `oberlies.py` | `python eval/hard_battery.py --harvest --dpd` |
| `validation/oberlies_sample.tsv`, `oberlies_pages.tsv`, `oberlies_sample.key.b64` | `validation/score.py` | drawn once from `oberlies_cases.json` (see `../validation/README.md`) |
