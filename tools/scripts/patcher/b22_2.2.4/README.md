# B2.2 exact composition pipeline

Local/private firmware only. No device interaction. No new defect research.

This version builds the exact nine-component composition documented in `builds/build_b22_2026-10-28/REPORT.md` and `PIPELINE.md`. It accepts only the pinned observer-free B2.1 lineage plus exact stock references and qualified sources. Historical component builders/evidence remain unchanged.

- `build.py --out NEW_DIRECTORY`: verify pinned app/GBL/stock/source/preimages/geometry, independently compile four additions, emit application/object/manifests only. Existing output directory rejected.
- `qualify.py`: version-specific double-build equality and286rejected corruption/control inputs.
- `protected.py --out NEW_JSON`: read-only historical inventory check; output only the requested new JSON.
- `gate.py`: require complete final-byte component/native/interaction/flow/independent app qualification and freeze its pins.
- `package.py`: refuse absent/changed/failed gate; construct two deterministic GBLs. It does not authorize final release by itself.
- `finalize.py`: require independent final container PASS, unchanged frozen pins and protected-artifact PASS before copying experimental BIN/GBL to final/.

The retained native runner copies and independent verifier live under the versioned build's qualification/. Their fixture scopes, actual final-byte binding and modeled endpoints are part of the qualification, not optional details. Future revisions must version their paths/manifests, not weaken parent/source or output pins.

Use PIPELINE.md for exact stage ordering. No GBL is emitted until all application code gates pass. Source copies in the build root are archival snapshots; runnable authoritative scripts remain here. Proprietary blobs must not be committed/distributed. No battery-drain or hardware behavior claim follows from these offline gates.
