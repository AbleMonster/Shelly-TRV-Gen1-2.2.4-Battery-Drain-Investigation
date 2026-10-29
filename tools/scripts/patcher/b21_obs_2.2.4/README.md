# B2.1_OBS — versioned experimental integration

Current controlled-research constructor: corrected A1R/C-C/B2/MQTT/officialWF2003.18 plus qualified PM52→cmd66 observer and readout-only research_build=B2.1_OBS. Native version unchanged. No devices/network/OTA are used by these scripts.

See `builds/build_b21_obs_2026-10-28/REPORT.md`, `BUILD-IDENTIFICATION.md`, `PIPELINE.md` and qualification results. build.py is source-based application-only; qualify.py opens the pinned package gate; package.py independently checks the container before emitting. Historical All-Known/observer inputs remain unchanged. A release candidate is not hardware-qualified or a battery-drain fix.
