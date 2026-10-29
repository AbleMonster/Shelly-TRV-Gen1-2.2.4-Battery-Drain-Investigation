# A1 source revisions

Current correction: `a1r_restore.S`, `restore_policy.py`, `build_restored.py`. The default All-Known pipeline composes this versioned source layer after verifying its exact historical parent, so future default builds contain A1R automatically.

`build_production.py`, original pm.c and frozen objects reconstruct HISTORICAL A1 and remain immutable for provenance. They alone do not contain the H180 temporary-restore correction and are superseded for future device testing. Do not overwrite old identities/results or modify their checksum inventory. Full semantics and reproducibility instructions: `builds/build_a1r_all_known_2026-10-28/REPORT.md` and `PIPELINE.md`.
