# Experimental Firmware Patches

## Shelly TRV Gen1 Firmware 2.2.4

## Scope

This directory documents the experimental firmware patches developed during the investigation of battery drain on the Shelly TRV Gen1 (`SHTRV-01`).

The primary host firmware target is:

```text
20240619-130912/v2.2.4@ee290818
```

The work started with small binary isolation patches for two recurring WLAN-related mechanisms:

```text
Patch A
    Beacon Recovery bypass

Patch B
    periodic mDNS restart bypass

Patch A+B
    combined isolation
```

The investigation later progressed from mechanism isolation to corrective firmware work.

The currently documented patch families include:

```text
Historical isolation patches
    |
    +-- Patch A
    +-- Patch B
    +-- Patch A+B

Beacon-Recovery correction
    |
    +-- C-C

Host power-management correction
    |
    +-- A1
    +-- A1R

Host sleep correction
    |
    +-- B2 bounded serialization

Radio integration
    |
    +-- WF200 3.18.0

Integrated research builds
    |
    +-- historical A1 + C-C + WF200 3.18.0
    +-- historical B2 / All-Known build
    +-- B2.1
    +-- B2.1_OBS
    +-- B2.2

Additional qualified corrections
    |
    +-- Calibration Restore Guard
    +-- P01 battery-ADC PA3 cleanup
    +-- P02 I2C timeout retirement
    +-- P03 WLAN GPIO interrupt-mask correction

Diagnostic firmware
    |
    +-- D3 Observer
    +-- PM52 -> cmd66 Observer
```

These variants answer different experimental questions.

An **isolation patch** asks:

> What happens when this mechanism is removed?

A **corrective patch** asks:

> Can a demonstrated firmware defect be corrected while preserving the legitimate surrounding behavior?

An **observer** asks:

> Does the statically reconstructed condition occur on physical hardware, and what state accompanies it?

An **integrated build** asks:

> Can independently qualified corrections coexist without introducing unexplained behavior?

These questions must remain separate.

No firmware documented here should currently be described as a confirmed complete solution to the historical Shelly TRV Gen1 battery-drain problem.

Multiple concrete firmware defects have been demonstrated and corrected experimentally, but their quantitative contribution to historical battery consumption remains under long-term evaluation.

---

# 1. Patch Overview

| Variant | Type | Primary purpose | Current status |
|---|---|---|---|
| Patch A | historical isolation | bypass 2.2.4 Beacon Recovery | hardware tested |
| Patch B | historical isolation | suppress periodic connected mDNS restart | hardware tested |
| Patch A+B | historical isolation | suppress both historical test mechanisms | hardware tested |
| C-C | corrective | correct Beacon Recovery control validity | qualified and hardware tested |
| A1 | historical corrective | correct reconstructed PM lifecycle defects | superseded by A1R |
| A1R | corrective | retain A1 lifecycle corrections while removing the A1 regression | qualified |
| B2 serialization | corrective | serialize shared B2 reference-counter RMW operations | qualified |
| WF200 3.18.0 | radio integration | evaluate newer Silicon Labs power-save firmware | hardware tested |
| Historical A1 + C-C + WF200 3.18.0 | integrated experimental | earlier host/radio correction platform | hardware tested, superseded |
| B2.1 | integrated corrective | A1R + C-C + B2 + MQTT guard + WF200 3.18.0 | qualified |
| B2.1_OBS | integrated diagnostic | B2.1 + PM52→cmd66 observer | current hardware test platform |
| B2.2 | integrated corrective | observer-free All Known Qualified Fixes | offline release-candidate GO; not hardware-qualified |
| D3 Observer | diagnostic | observe WF200 `PS_MODE_ERROR` | historical hardware test |
| PM52→cmd66 Observer | diagnostic | observe native PM52/cmd66 lifecycle without adding WF200 requests | current observer |

Historical variant names must remain historical.

In particular, measurements collected with an A1-based build must not later be renamed as A1R, B2.1 or B2.1_OBS measurements.

---

# 2. Target Firmware

The host patches documented here are based on Shelly TRV Gen1 firmware:

```text
20240619-130912/v2.2.4@ee290818
```

Historical analysis used the original GBL:

```text
SHTRV-01_build.gbl
```

with size:

```text
1,106,384 bytes
```

The canonical application extraction used for the early binary patches begins at:

```text
GBL offset:
0x00006554
```

The corresponding historical application size is:

```text
1,049,548 bytes
```

An earlier extraction beginning at:

```text
0x0000654C
```

was found to be shifted and must not be used as the canonical application image for the historical Patch-A/Patch-B offsets.

All patch tooling must verify the exact input firmware before modifying it.

Offsets documented for firmware 2.2.4 must never be applied blindly to another release.

---

# 3. Firmware-Patch History

The experimental progression is approximately:

```text
Stock 2.2.4
    |
    +-- Patch A
    |     |
    |     +-- bypass Beacon Recovery
    |     +-- isolation experiment
    |
    +-- Patch B
    |     |
    |     +-- bypass periodic mDNS restart
    |     +-- isolation experiment
    |
    +-- Patch A+B
    |     |
    |     +-- combined isolation experiment
    |
    +-- C-C
    |     |
    |     +-- correct C1a
    |     +-- correct C1b
    |     +-- correct C2
    |     +-- retain fresh valid Recovery
    |
    +-- A1
    |     |
    |     +-- PM lifecycle / ownership correction
    |     +-- later found to contain an experimental regression
    |
    +-- A1R
    |     |
    |     +-- retain A1 lifecycle corrections
    |     +-- correct A1 temporary-override regression
    |
    +-- B2 bounded serialization
    |     |
    |     +-- preserve reference-counter semantics
    |     +-- eliminate qualified lost-update race
    |
    +-- B2.1
    |     |
    |     +-- A1R
    |     +-- C-C
    |     +-- B2 serialization
    |     +-- minimal MQTT PUBLISH guard
    |     +-- WF200 3.18.0
    |
    +-- B2.1_OBS
    |     |
    |     +-- B2.1
    |     +-- PM52 -> cmd66 observer
    |     +-- current long-term hardware platform
    |
    +-- B2.2
          |
          +-- observer-free
          +-- additional independently qualified corrections
          +-- offline release-candidate GO
          +-- not yet hardware-qualified
```

The patches were developed incrementally as the understanding of the firmware improved.

Early patches must therefore be interpreted in the context of the question they were designed to answer rather than as increasingly complete production fixes.

---

# 4. Background: Beacon Recovery

Firmware 2.2.4 contains host-side processing of WF200 beacon statistics that was not identified in the same form in the analyzed 2.1.x host firmware.

The host queries WF200 statistics and derives the value exposed through `/stats` as:

```text
real_beacon_skip
```

The simplified measurement chain is:

```text
WF200 command 0x66
        |
        v
received-beacon counter C
        |
        v
previous host baseline P
        |
        v
delta = C - P
        |
        v
600 / delta
        |
        v
8-bit real_beacon_skip R
        |
        v
Beacon Recovery decision
```

When the stock recovery decision qualifies, the host temporarily changes WLAN power-management state.

Observed stock behavior is approximately:

```text
normal state 3
        |
        v
Beacon Recovery qualifies
        |
        v
"Beacon skip error! Attempt recovery"
        |
        v
state 1 / active WLAN
        |
        | ~5 serviced seconds
        v
restore state 3
```

Affected stock devices can repeat this sequence at approximately minute-scale cadence for extended periods.

Later reverse engineering showed that the stock decision path contains several separate validity problems.

Those findings changed the patch strategy from a simple Recovery bypass to a corrective implementation.

---

# 5. Patch A — Beacon Recovery Bypass

Patch A was the first isolation patch.

Its purpose was to determine whether the identified Beacon Recovery action could be suppressed while leaving the surrounding beacon-statistics processing operational.

Patch A does not correct the estimator.

It bypasses the Recovery block after the stock decision point.

Conceptually:

```text
calculate real_beacon_skip
        |
        v
stock recovery decision
        |
        v
      bypass
        |
        v
common continuation
```

This made Patch A useful for mechanism isolation.

It is not the preferred corrective solution because legitimate fresh Recovery is also suppressed.

---

## 5.1 Patch-A Native Modification

The relevant Thumb instruction begins at:

```text
0x0001E1C8
```

Original bytes:

```text
31 DC
```

Patch A changes:

```text
31 DC
  ↓
31 E0
```

The modified application byte is:

```text
program offset:
0x0001E1C9

0xDC -> 0xE0
```

Using the canonical historical application start:

```text
0x00006554
```

the corresponding historical GBL offset is:

```text
0x0002471D
```

The patch converts the relevant conditional branch into an unconditional branch to the existing continuation path.

No replacement power-management implementation is introduced.

---

## 5.2 Historical Patch-A Container

For the historical Patch-A GBL:

```text
Original CRC32:
0xDC7BAB58

Patch-A CRC32:
0x432F734F
```

The locally generated Patch-A artifact used during testing had SHA-256:

```text
ac7d85c8e9239bebd3b134c4b93fc838859c613e59f7690650097da984ea7222
```

These values identify a historical locally generated research artifact.

The patched firmware binary is not distributed through this repository.

---

## 5.3 Patch-A Runtime Result

Physical-device testing confirmed that Patch A could suppress the characteristic repeating Recovery sequence while retaining:

- Wi-Fi connectivity
- Shelly Cloud connectivity
- thermostat operation
- valve movement
- valve calibration
- status reporting
- beacon-statistics processing
- `real_beacon_skip` reporting

The experiment established that the Recovery action could be isolated independently from the statistics calculation.

It did not establish that Recovery was the historical battery-drain root cause.

---

# 6. Patch B — Periodic mDNS Restart Bypass

Further analysis identified a separate periodic connected-maintenance path that invokes the equivalent of:

```text
mdns_resp_restart()
```

The recurring restart is distinct from Beacon Recovery.

Patch B suppresses only the targeted periodic caller.

It does not globally disable the mDNS responder.

---

## 6.1 Patch-B Native Modification

The relevant instruction begins at:

```text
0x0001E0F0
```

Original bytes:

```text
02 D0
```

Patch B changes:

```text
02 D0
  ↓
02 E0
```

The changed application byte is:

```text
program offset:
0x0001E0F1

0xD0 -> 0xE0
```

Using the historical application start:

```text
0x00006554
```

the corresponding GBL offset is:

```text
0x00024645
```

The periodic call remains physically present in the firmware but is bypassed by the modified branch.

Other identified mDNS restart paths remain unchanged.

---

## 6.2 Patch-B Runtime Result

Packet capture confirmed that the targeted recurring mDNS sequence disappeared on the Patch-B device.

Normal device connectivity remained available.

Stock Beacon Recovery continued.

The long-term Patch-B device eventually reached approximately:

```text
uptime:
~9.23 days

battery:
0 %

voltage:
3.116 V

beacon_err_counter:
12908
```

This corresponds to approximately:

```text
58.3 Beacon Recovery events/hour
```

over the complete uptime.

The result establishes that the targeted periodic mDNS restart is not required for recurring Beacon Recovery.

It does not prove that mDNS has zero energy cost, and it does not prove that the remaining Recovery events caused the complete discharge.

Patch B remains a historical isolation experiment.

---

# 7. Patch A+B — Historical Combined Isolation

Patch A and Patch B were later combined.

The combined modification was:

```text
Patch B:

program offset 0x0001E0F1
D0 -> E0


Patch A:

program offset 0x0001E1C9
DC -> E0
```

The historical combined GBL had:

```text
Size:
1,106,384 bytes

CRC32:
0xBAEB8265

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61
```

The corresponding patched main PROGRAM payload had SHA-256:

```text
06742a2632a3d45cf697b8be85045914d004f30644dad17b3d0d20012c87c61b
```

Patch A+B created four useful experimental states:

```text
Stock
    Recovery active
    periodic mDNS active

Patch A
    Recovery bypassed
    periodic mDNS active

Patch B
    Recovery active
    periodic mDNS bypassed

Patch A+B
    Recovery bypassed
    periodic mDNS bypassed
```

This was an appropriate experimental design at that stage of the investigation.

It is not the current corrective architecture.

---

# 8. Why Patch A Was Replaced by C-C

Further analysis of the Beacon Recovery path showed that the problem was more specific than simply:

```text
Recovery exists
```

Three separate control-validity problems were identified:

```text
C1a
    signed interpretation of the cached control byte

C1b
    measurement-window validity

C2
    reuse of historical Recovery evidence
    after the measurement baseline was cleared
```

This made a more precise correction possible.

Patch A suppresses all Recovery.

C-C instead corrects invalid control semantics while retaining Recovery for a fresh, valid qualifying measurement.

Conceptually:

```text
Patch A:

qualifying stock decision
        |
        X
Recovery always bypassed
```

versus:

```text
C-C:

fresh + valid + qualifying evidence
        |
        +---- yes -> Recovery retained
        |
        +---- no  -> no Recovery
```

C-C therefore supersedes Patch A as the preferred Beacon Recovery correction.

Patch A remains useful for documenting the earlier isolation experiment.

---

# 9. C-C — Beacon Recovery Correctness Patch

C-C targets the validity of the host-side Beacon Recovery decision.

It does not disable the beacon-statistics mechanism and does not force a fixed beacon-skip configuration.

Its purpose is to prevent invalid, stale or incorrectly interpreted estimator state from causing Recovery.

---

## 9.1 C1a — Signed Control Interpretation

The stock calculation produces:

```text
R = uint8_t(600 / delta)
```

but the Recovery decision later interprets the byte as signed.

For example:

```text
delta = 3

600 / 3 = 200

uint8_t:
0xC8

int8_t:
-56
```

and:

```text
delta = 4

600 / 4 = 150

uint8_t:
0x96

int8_t:
-106
```

These values can unexpectedly satisfy the stock signed Recovery comparison.

C-C prevents this representation artifact from being treated as legitimate Recovery evidence.

---

## 9.2 C1b — Measurement-Window Validity

The stock calculation assumes a fixed logical measurement interval through the numerator:

```text
600
```

but the previous cumulative beacon baseline does not carry matching elapsed-time metadata.

If a measurement opportunity is skipped while the old baseline survives, the next:

```text
C - P
```

can span a longer interval than the formula assumes.

C-C requires the measurement window used for Recovery to be valid rather than treating every counter delta as equivalent.

---

## 9.3 C2 — Historical Recovery Evidence

Stock Recovery clears the previous beacon baseline while retaining the cached `real_beacon_skip`.

This can create the sequence:

```text
fresh qualifying R
        |
        v
Recovery
        |
        v
P cleared
R retained
        |
        v
next sample establishes P only
        |
        v
old R evaluated again
        |
        v
Recovery may qualify again
```

This creates a metastable recurrence mechanism in which historical Recovery evidence can be reused after the baseline has been invalidated.

On affected runs it can produce approximately minute-spaced repeated Recovery.

The state is not necessarily permanent.

Later state evolution can allow the firmware to leave the loop without rebooting.

C-C prevents a baseline-only sample from treating historical `R` as fresh control evidence.

---

# 10. C-C Runtime Result

C-C has been exercised on physical TRV hardware.

Testing confirmed that:

- firmware boots normally
- WLAN remains operational
- cloud connectivity remains operational
- thermostat operation remains available
- valve operation remains available
- beacon statistics remain available
- the known stale-evidence recurrence is prevented
- fresh qualifying Recovery remains possible

C-C is therefore not equivalent to Patch A.

Fresh Recovery events were observed on earlier C-C-based firmware.

Historical C-C + WF200 3.18.0 configurations showed rates around:

```text
~27–30 events/hour
```

during parts of the earlier tests.

This differed materially from the approximately:

```text
~58–60 events/hour
```

minute-scale stale-recurrence behavior observed on affected stock runs.

These are historical measurements from specific test configurations.

They must not be interpreted as universal event rates.

---

# 11. A1 — Historical PM-Lifecycle Correction

Further reverse engineering identified a second class of host defects outside the Beacon Recovery estimator.

These involve the lifecycle of WLAN power-management operations and host-side ownership of sleep restrictions.

A1 was developed to correct these reconstructed defects while preserving the surrounding PM architecture.

Its scope included defect classes tracked internally as:

```text
G01
G02
G03
G05
G06
G18
G19
```

At a high level, the corrected areas include:

- Final-Sleep failure cleanup
- Wake failure state handling
- timeout versus cancellation
- late-completion ambiguity
- requested versus committed PM state
- stale/old PM completion races
- independent inhibit ownership
- PM settlement and handoff correctness

A1 was a corrective patch rather than an isolation bypass.

However, later qualification discovered that A1 itself introduced a regression in temporary power-management override handling.

A1 is therefore now a **historical experimental correction**.

It has been superseded by A1R.

---

# 12. Final-Sleep Failure Handling

One identified host-side problem occurs when a final WLAN sleep operation fails before the corresponding host-side ownership state has been fully released.

The normal lifecycle is conceptually:

```text
acquire wake / sleep restriction
        |
        v
perform WLAN PM operation
        |
        v
final device sleep
        |
        v
release ownership
```

Some stock error exits can leave host-side ownership inconsistent with the actual operation lifecycle.

The A1/A1R correction addresses the qualified failure lifecycle rather than blindly clearing blockers.

This distinction is important.

A sleep blocker must not be released unless the associated operation no longer legitimately requires it.

---

# 13. Wake Failure Handling

The reverse path contains a complementary problem.

Stock logic can update software state before lower-level wake success has been established.

A lower-layer failure can therefore leave software ownership or state inconsistent with the validated operation state.

The corrective lifecycle changes ensure that software commitment follows the validated operation rather than incorrectly preceding it where required.

---

# 14. Timeout Is Not Cancellation

A timeout does not necessarily mean that a lower-level operation can no longer complete.

Conceptually:

```text
request PM transition
        |
        v
wait
        |
        +---- completion -> normal settlement
        |
        +---- timeout
                |
                v
        operation may still complete later
```

Treating timeout as cancellation can allow a late completion to modify state after the caller has already taken another path.

The corrective design therefore tracks the qualified settlement and ownership relationship instead of assuming that timeout means the lower operation disappeared.

---

# 15. Requested vs. Committed PM State

Stock firmware can treat requested power-management state as though it were already committed before the lower-level operation has successfully completed.

The reconstruction distinguishes:

```text
desired / requested state
```

from:

```text
successfully committed state
```

where required by the PM lifecycle.

This prevents subsequent control decisions from relying on a transition that did not actually settle successfully.

---

# 16. Old PM Completion Race

A later completion belonging to an older PM request can race with a newer request.

Without sufficient generation and ownership tracking, the old completion can incorrectly affect current state.

The corrective lifecycle includes qualified generation and settlement handling so that an obsolete completion is not accepted as the current transition.

---

# 17. Independent Inhibit Ownership

The firmware can have more than one reason for temporarily preventing or altering a PM transition.

The corrective architecture preserves independent ownership instead of collapsing unrelated inhibit conditions into one ambiguous state.

Releasing one reason must not release another still-active reason.

---

# 18. A1 Regression and A1R

Later qualification identified a regression introduced by the experimental A1 implementation.

Five reconstructed native paths use `request1` as a temporary override:

```text
physical button
HTTP /psovrd
Cloud psovrd
SSI settings_sta
OTA launcher
```

The intended behavior is conceptually:

```text
selected policy = 3

temporary request = 1

use 1 temporarily
then restore 3
```

The old A1 implementation could instead cause:

```text
temporary request1
        |
        v
1 becomes persistent selected policy
```

For example:

```text
3 / 3
```

could remain as:

```text
1 / 1
```

after a temporary override.

This was an **experimental A1 regression**.

It is not evidence that the same defect exists in stock Shelly firmware, and it is not evidence that this regression explains historical battery drain.

The corrected implementation is:

```text
A1R
```

A1R retains the qualified A1 PM-lifecycle corrections while distinguishing the verified temporary-return paths from normal persistent `request1` behavior.

Qualification included:

```text
151 / 151 Thumb behavior tests PASS
```

plus retained-state, generation, C-C, B2, MQTT and malformed-input regression tests.

A1R does not attempt to repair an already-running historical `1/1` state in place.

A normal flash/reboot initializes the relevant state normally.

---

# 19. B2 Shared Reference-Counter Correction

The EFM32GG11 host-sleep audit identified a separate concurrency defect outside the original A1 scope.

B2 is a shared reference counter representing active software owners that currently require the host to remain at EM1 instead of entering EM2.

Conceptually:

```text
B2 = 0
    no software owner requires EM1
    EM2 may be allowed

B2 = 1
    one owner requires EM1

B2 = 2
    two simultaneous owners require EM1
```

This reference-count model is legitimate.

The defect is that not all stock B2 read-modify-write operations are serialized consistently.

A task-side sequence can effectively perform:

```c
old = B2;
new = old + 1;
B2 = new;
```

while task preemption remains possible between the load and store.

Other B2 operations are protected.

The mixture allows real schedules to lose updates.

A phantom contribution can leave:

```text
B2 = 1
```

with no legitimate owner and unnecessarily restrict normal idle to EM1.

The opposite race can lose a legitimate contribution and allow B2 to reach zero while an owner still exists.

The correction therefore must not:

```text
force B2 = 0
```

and must not convert the aggregate counter into a Boolean.

The qualified correction uses bounded serialization of the complete relevant B2 reference-counter RMW operation while preserving the original ownership semantics.

B2 bounded serialization is now qualified and forms part of B2.1, B2.1_OBS and B2.2.

---

# 20. B3, EM2 and EM3

The host-sleep audit also resolved the meaning of the permanent B3 contribution.

During normal startup the firmware installs a B3 contribution before normal scheduler operation.

This intentionally prevents normal idle from selecting EM3.

The stock TRV configures its RTC/tickless timebase from the low-frequency clock domain associated with the current design.

The simplified idle selection is:

```text
B2 != 0
    -> max EM1

B2 == 0 && B3 != 0
    -> EM2

B2 == 0 && B3 == 0
    -> EM3
```

Normal deepest intended idle is therefore:

```text
EM2
```

not:

```text
EM3
```

The project does not treat the permanent B3 contribution as a battery-drain defect.

Simply clearing B3 or forcing EM3 would require a separate clock/timebase redesign and is not part of the current correction strategy.

---

# 21. PA8 WLAN Sleep Gate

The host sleep path contains another mechanism independent of B2.

PA8 participates in the WLAN host-notification path.

Immediately before low-power entry, the host checks PA8.

Conceptually:

```text
sleep mode selected
        |
        v
check PA8
        |
        +---- LOW  -> continue to WFI
        |
        +---- HIGH -> no WFI
```

A HIGH level vetoing WFI is not automatically a firmware defect.

Preventing host sleep while the WLAN device has pending work is a legitimate design pattern.

PA8 therefore remains an observed part of the host-sleep architecture rather than something that should simply be removed.

---

# 22. WF200 3.18.0 Integration

The protected WF200 firmware shipped with stock Shelly TRV 2.2.4 is:

```text
WF200 3.16.1
```

Silicon Labs later released:

```text
WF200 3.18.0
```

The investigated official 3.18.0 SEC image has:

```text
Size:
312,400 bytes

SHA-256:
886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9
```

The 3.18.0 changelog contains a power-management fix relevant to the investigated failure class, described in terms of a device not sleeping after a power-save mode change.

This makes the version technically relevant.

It does not prove that the Silicon Labs fix explains historical Shelly TRV battery drain.

---

# 23. FMAC 3.7.0 + WF200 3.18.0 Compatibility

Shelly firmware 2.2.4 uses:

```text
FMAC 3.7.0
```

The project experimentally integrated official WF200 3.18.0 while retaining the Shelly FMAC 3.7.0 host driver.

Physical-device testing demonstrated successful:

```text
FMAC 3.7.0 initialization
        |
        v
WF200 3.18.0 initialization
        |
        v
scan
        |
        v
association
        |
        v
DHCP
        |
        v
cloud connectivity
        |
        v
normal TRV operation
```

This establishes practical interoperability under the tested conditions.

It is not an official Silicon Labs or Shelly compatibility qualification.

---

# 24. WF200 3.18.0 Construction

The experimental 3.18.0 integration required relocation of the protected SEC region while preserving the firmware container and host-side loader relationships.

The qualified relocation moved the SEC region from approximately:

```text
0x4C050
```

to:

```text
0x4C450
```

with:

```text
+0x400
```

displacement.

The destination range was:

```text
[0x1003D0, 0x1007D8)
```

The integration required:

```text
54 relocation fixups
```

while preserving the qualified loader/reset-copy relationships.

The final SEC extracted from the generated GBL was verified byte-for-byte against the intended official WF200 3.18.0 input.

---

# 25. Historical A1 + C-C + WF200 3.18.0 Build

An earlier integrated correction platform combined:

```text
A1
+
C-C
+
WF200 3.18.0
```

The statically qualified controlled-test GBL was:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

GBL:

```text
size:
1,123,380 bytes

SHA-256:
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379

END CRC32:
F01262BC

whole-file CRC32 residue:
2144DF1C
```

Application:

```text
size:
1,066,544 bytes

SHA-256:
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The build successfully booted and operated on physical hardware, including WLAN, cloud, thermostat, valve and calibration functions.

This artifact remains historically valid.

However, it is now superseded because it contains the original A1 implementation rather than A1R.

Historical measurements collected with this build must remain attributed to this build.

---

# 26. Historical B2 / All-Known Build

A later integrated build combined:

```text
A1
+
C-C
+
B2 serialization
+
minimal MQTT PUBLISH guard
+
WF200 3.18.0
```

This historical build predates A1R.

It is therefore superseded because it still contains the A1 temporary-override regression.

Historical runtime results remain valid as measurements of that exact build.

They must not be retroactively renamed as B2.1 or B2.1_OBS results.

---

# 27. B2.1 — Corrected Integrated Baseline

B2.1 replaced the original A1-based integrated build.

It contains:

```text
A1R
+
C-C
+
B2 bounded serialization
+
minimal MQTT PUBLISH guard
+
WF200 3.18.0
```

The MQTT component is documented publicly only at the level required to identify the correction set.

Security-sensitive implementation details are intentionally outside the public battery-drain documentation.

The B2.1 artifact is:

```text
final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.gbl
```

Application:

```text
size:
1,066,776 bytes

SHA-256:
31ddd06a0229fee0b0b58dcbbd28ced1e4fbab0b6dc218c76c9d93673f4961e0

CRC:
24702EBF
```

GBL:

```text
size:
1,123,612 bytes

SHA-256:
5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9

END CRC:
F5429B7F

residue:
2144DF1C
```

B2.1 is the observer-free corrected baseline from which the current diagnostic hardware platform was derived.

---

# 28. PM52 → cmd66 Observer

The earlier proposed Stock Host Observer is no longer the current diagnostic architecture.

The current observer is attached to the B2.1 corrected baseline.

It records the existing PM and beacon-statistics lifecycle, including:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing periodic command-0x66 requests/results
- fresh estimator operands
- connection epochs
- a compact recent-event ring
- first-fault freeze state

The observer deliberately introduces no additional WF200 request.

It adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
policy change
```

Readout occurs only through explicit `/status` access.

Observer RAM is separated from A1 state:

```text
observer:
[0x2007FD80, 0x2007FF80)

A1:
[0x2007FF80, 0x20080000)
```

The observer has been qualified for noninterference at the software level.

As with any instrumentation inserted into firmware, complete absence of physical timing perturbation cannot be mathematically guaranteed.

That limitation must remain explicit.

---

# 29. B2.1_OBS — Current Hardware Test Platform

B2.1_OBS is:

```text
B2.1
+
PM52 -> cmd66 observer
```

During integration, the historical observer placement conflicted with the later A1R classifier.

The observer was therefore relocated while preserving the A1R implementation.

The native Shelly firmware identity remains:

```text
2.2.4
```

and the research build is separately identified as:

```text
research_build: B2.1_OBS
```

The observer readout is exposed as:

```text
pm52_cmd66
```

Qualification included:

```text
A1R:
151 / 151

observer/readout:
356 / 356

B2:
2060 + mixed/preemption qualification

C-C:
qualified regression set

MQTT:
258

decoder regressions:
PASS

unexplained application changes:
0

deterministic construction:
PASS

independent GBL parsing / CRC / geometry / SEC:
PASS
```

Disposition:

```text
B2.1_OBS RELEASE-CANDIDATE GO
```

Artifact:

```text
builds/firmware/B2.1_OBS/
SHTRV-01_2.2.4_B2.1_OBS_EXPERIMENTAL.gbl
```

Application:

```text
size:
1,069,300 bytes

SHA-256:
65e17c4c04bdde23f545ebdb3283d71eef746e8dafba97ed9f6e451b6310c215

CRC:
EEE8DD82
```

GBL:

```text
size:
1,126,136 bytes

SHA-256:
7d7063d81372063dfe0d629d26e614f7dd2ed448b0e65a393e866c79025eac7a

END CRC:
12247888

residue:
2144DF1C
```

B2.1_OBS is the **current physical long-term test firmware**.

That does not mean it has already demonstrated restored battery lifetime.

---

# 30. Calibration Restore Guard

A separate calibration audit demonstrated a concrete self-requeue defect.

A queued successful calibration restore could immediately schedule itself again under the qualified condition.

The corresponding correction is:

```text
Calibration Restore Guard
```

The guard was independently qualified and is included in B2.2.

It is not part of the B2.1_OBS firmware currently running in the long-term test fleet.

---

# 31. Peripheral / Resource-Lifecycle Corrections

A later EFM32 peripheral/resource-lifecycle audit identified additional concrete defects.

## 31.1 P01 — Battery ADC PA3 Cleanup

An ADC timeout can return before PA3 is correctly released.

A later successful cycle may correct the state, so this is not necessarily permanent.

The energy consequence has not been directly measured.

A bounded cleanup correction was qualified.

---

## 31.2 P02 — I2C Timeout Retirement

An I2C timeout can return with state equivalent to:

```text
unfinished transaction state
interrupt enable still active
no bounded abort / retirement
```

A bounded retirement correction was qualified.

---

## 31.3 P03 — WLAN GPIO Interrupt Mask

A WLAN GPIO disable path supplies:

```text
decimal 10
```

to a helper whose argument semantics are a bitmask.

This can leave the intended interrupt state inconsistent with the requested operation.

A correction using the proper mask semantics was qualified.

---

## 31.4 Deferred P04

The motor-completion timeout path performs substantial cleanup, including resources associated with:

```text
PA3
LDMA
timers
clocks
B2
```

but movement accounting can still remain stale or partial.

This finding is currently:

```text
DEFERRED
```

It is not included in B2.2.

---

# 32. B2.2 — Observer-Free All Known Qualified Fixes

While B2.1_OBS remains unchanged on physical hardware, an observer-free follow-up build was constructed offline.

Its name is:

```text
B2.2
```

with the description:

```text
observer-free All Known Qualified Fixes
```

Its current disposition is:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

No physical TRV has been used to qualify B2.2.

B2.1_OBS was deliberately left unchanged while B2.2 was built and qualified offline.

Artifact:

```text
builds/firmware/B2.2/
SHTRV-01_2.2.4_B2.2_EXPERIMENTAL.gbl
```

GBL:

```text
size:
1,126,156 bytes

SHA-256:
912983973a5467241397b9dd967ee0039440c7d77780a2a97ee494b1a507860c

END CRC:
52A97051

residue:
2144DF1C
```

Application:

```text
size:
1,069,320 bytes

SHA-256:
7ee593265c76abd8cd628a81133d4b1310c1ae24c9ebe2ca3f2c2948acfc64f9

CRC:
42657D97
```

The native firmware identity remains:

```text
20240619-130912/v2.2.4@ee290818
```

B2.2 is identified by its artifact name and hashes rather than by changing the native Shelly firmware identity.

---

# 33. Exact B2.2 Correction Set

B2.2 contains exactly nine correction components:

```text
1. A1R including the A1 lifecycle correction
2. C-C
3. B2 bounded serialization
4. minimal MQTT PUBLISH guard
5. official WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release correction
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

No tenth fix is implied.

The phrase:

```text
All Known Qualified Fixes
```

means:

> all demonstrated, safely correctable and independently qualified corrections selected for this integrated build.

It does **not** mean:

```text
all suspicious code paths ever identified
```

or:

```text
all bugs that may exist in the original firmware
```

Known findings deliberately deferred from B2.2 include:

```text
P04 motor movement-accounting finding
P11 raw ADC transient publication
valve_min_percent mixed-unit issue
raw TXDMA candidates
P05/P06/P07/P08/P10/P12/P13
mDNS removal
EM3 changes
diagnostic 500 us FastPS ideas
```

Deferred findings must remain distinguishable from the qualified correction set.

---

# 34. B2.2 Offline Qualification

B2.2 underwent composition qualification in addition to qualification of its individual components.

Representative qualification totals include:

```text
A1R:
151 / 151

C-C:
512 + 10000

B2:
2060 + 102
mixed 2 / 10

MQTT:
258

Calibration Restore Guard:
68 native
66535 scalar
104 queue
30 countdown
negative tests

P01:
128 + 6

P02:
90 + 480

P03:
128 native

motor / B2 / P01:
10 + 30

sleep / PA8:
48

battery / OTA / boot:
10002 + 2 + 4 + 3

interfaces / flows:
10 interactions
13 flow groups
```

Construction qualification also established:

```text
four clean application constructions:
byte-identical

two complete GBL builds:
byte-identical

builder rejection tests:
286

independent verifier rejection tests:
282

unexplained stock -> B2.2 application differences:
0

unexplained B2.1 -> B2.2 application differences:
0

observer presence:
none

unexplained container differences:
0
```

These results establish the current offline qualification state.

They do **not** establish physical-device behavior.

Therefore:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

does not mean:

```text
B2.2 hardware-qualified
```

and does not mean:

```text
battery lifetime restored
```

---

# 35. Current Experimental Architecture

The current architecture can be summarized as:

```text
                           Stock 2.2.4
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
          Patch A            Patch B              C-C
          isolation          isolation       Recovery validity
             |                  |                  |
             +--------+---------+                  |
                      |                            |
                      v                            |
                  Patch A+B                        |
                  historical                       |
                  isolation                        |
                                                   |
                          PM lifecycle audit ------+
                                |
                                v
                               A1
                                |
                         regression found
                                |
                                v
                              A1R
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
           B2 serialization             WF200 3.18.0
                  |                           |
                  +-------------+-------------+
                                |
                                v
                              B2.1
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
            B2.1_OBS                       B2.2
         current hardware             observer-free
         long-term platform           additional fixes
                                      offline GO only
```

This distinction is important.

The current physical experiment uses B2.1_OBS.

B2.2 is intentionally frozen offline until the B2.1_OBS long-term evidence justifies the next hardware step.

---

# 36. Current Hardware Experiment

The current controlled hardware population is:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The current research decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

The current B2.1_OBS devices have passed initial hardware smoke testing.

The observer-equipped devices have also shown the expected corrected build identity and readout path.

Early runtime observations are not sufficient to claim restored battery endurance.

The stock control continues to provide an independent reference for stock 2.2.4 behavior.

Network conditions and firmware assignments should remain stable during the long-term comparison.

---

# 37. Battery Reporting Interpretation

The displayed TRV battery percentage is not a coulomb counter.

Static analysis shows that it is derived from a cached battery-voltage value through a stateless integer conversion.

Therefore short-term comparisons should give greater weight to:

```text
battery voltage
```

than to:

```text
displayed battery %
```

The percentage remains useful operationally, but it should not be interpreted as a linear measurement of consumed battery capacity.

The analyzed low-voltage shutdown threshold is:

```text
3000 mV
```

for the inspected 2.1.x and 2.2.4 firmware family.

The board-level electrical consequence after the firmware shutdown sequence has not been independently verified.

---

# 38. Current Battery-Drain Model

The current working model is deliberately multi-mechanism.

Potential contributors or interacting layers include:

```text
normal TRV workload
        |
        +-- thermostat / valve activity
        |
        +-- network / cloud traffic
        |
        +-- periodic mDNS
        |
        +-- Beacon Recovery
        |
        +-- host PM lifecycle
        |
        +-- B2 blocker accounting
        |
        +-- PA8 WLAN sleep gate
        |
        +-- WF200 power-save behavior
        |
        +-- peripheral/resource lifecycle
        |
        +-- calibration behavior
        |
        +-- RF / AP environment
```

Some of these contain demonstrated firmware defects.

Others are legitimate mechanisms whose runtime cost may still influence battery life.

The objective is not to suppress every activity that consumes energy.

The objective is to restore correct firmware behavior and determine whether the corrected system achieves normal battery endurance.

---

# 39. What Has Been Established

The project has established several findings independently of the unresolved total battery-life question.

These include:

- the targeted periodic mDNS restart exists
- Patch B can suppress that targeted restart
- mDNS restart is not required for recurring Beacon Recovery
- stock 2.2.4 Beacon Recovery contains C1a/C1b/C2 validity defects
- C-C corrects the qualified Beacon Recovery validity problems
- C2 recurrence is metastable rather than necessarily permanent
- PM lifecycle and ownership defects were reconstructed and corrected experimentally
- the original A1 implementation introduced its own temporary-override regression
- A1R corrects that regression while retaining the A1 lifecycle correction
- B2 contains a real shared reference-counter lost-update race
- bounded B2 serialization has been qualified
- normal deepest intended host idle is EM2, not EM3
- PA8 can legitimately veto WFI
- FMAC 3.7.0 can operate with the tested WF200 3.18.0 integration
- the Calibration Restore Guard correction has been qualified
- P01 battery-ADC PA3 cleanup has been qualified
- P02 bounded I2C timeout retirement has been qualified
- P03 WLAN GPIO interrupt-mask correction has been qualified
- B2.1_OBS has passed its qualification gate and is running on physical test devices
- B2.2 has passed its current offline composition/reconstruction qualification

These findings should not be collapsed into a single battery-drain root-cause claim.

---

# 40. What Is Not Yet Established

The current work does not establish:

- one single historical root cause for every Shelly TRV Gen1 battery-drain report
- the quantitative energy cost of one Beacon Recovery cycle
- the quantitative energy cost of periodic mDNS
- the historical field frequency of every demonstrated PM defect
- physical WF200 sleep residency during historical drain
- complete physical EFM32 EM1/EM2 residency during historical drain
- that WF200 3.18.0 alone solves the problem
- that C-C alone solves the problem
- that A1R alone solves the problem
- that B2 serialization alone solves the problem
- that B2.1_OBS has restored normal battery lifetime
- that B2.2 is hardware-qualified
- that B2.2 is a final production-quality firmware fix
- the final battery-life improvement of an observer-free corrected firmware

The distinction is fundamental:

```text
correct patch behavior
!=
battery drain solved
```

and:

```text
offline qualification
!=
hardware qualification
```

---

# 41. Current Research Direction

Active root-cause hunting is currently paused.

The immediate research activity is:

```text
long-term B2.1_OBS hardware observation
```

The test variables should remain unchanged unless the experiment itself requires termination.

If B2.1_OBS shows a genuine battery-drain episode:

```text
capture the first fault evidence
        |
        v
correlate PM52 / cmd66 / runtime state
        |
        v
resume deeper reverse engineering
```

If B2.1_OBS remains stable over the required long-term period:

```text
remove observer
        |
        v
requalify observer-free corrected build
        |
        v
hardware regression testing
        |
        v
evaluate final firmware candidate
```

B2.2 should not be rolled onto hardware merely because its offline qualification passed.

The current long-term experiment should first be allowed to answer its intended question.

---

# 42. Patcher Design

Public patch tooling should generate experimental firmware from a locally obtained and verified stock image.

The patcher must fail closed.

It must not attempt to make an unexpected input "fit".

Construction requirements include:

- exact source-firmware identification
- exact expected input size
- expected hashes where applicable
- expected hook bytes
- expected instruction addresses
- expected GBL structure
- expected radio payload
- explicit relocation validation
- integrity recalculation
- post-build reconstruction
- deterministic output
- independent verification where practical

A failed precondition must stop construction.

---

# 43. Deterministic Construction and Composition Qualification

For complex integrated patches, reproducibility is part of qualification.

The same verified inputs and patcher revision should produce byte-identical:

```text
application image
GBL
construction manifest
```

across repeated builds.

Unexplained output differences are treated as construction failures rather than ignored.

Integrated firmware also requires **composition qualification**.

Individually correct patches can interact.

For each correction, the project aims to retain evidence of:

```text
original defect
violated invariant
correction
regression / noninterference qualification
hardware validation status
```

A correction should enter an integrated candidate only when it is:

```text
demonstrated
+
safely correctable
+
independently qualified
+
composition-qualified
```

where applicable.

---

# 44. Container Integrity

A valid application patch is not sufficient by itself.

The resulting GBL must also preserve the expected container structure and integrity relationships.

Depending on the experimental build, verification includes:

- GBL record geometry
- PROGRAM payload boundaries
- END record
- CRC32
- whole-file residue
- loader relationships
- reset-copy relationships
- second PROGRAM preservation
- radio SEC extraction
- relocation targets

For WF200 replacement builds, the extracted final radio payload must match the intended input radio firmware byte-for-byte after accounting for qualified container placement.

---

# 45. OTA Installation

Experimental GBL files have been installed successfully through the normal Shelly Gen1 OTA mechanism using a local HTTP server.

The TRV requests firmware using HTTP byte-range behavior.

For the current local test setup, the OTA server must be reachable on:

```text
TCP port 80
```

Using port 8000 caused problems with the tested TRV OTA retrieval path.

On macOS, binding a Python test server to port 80 normally requires elevated privileges.

Successful OTA transfer establishes only that the generated container was accepted sufficiently to perform the update.

It does not replace static qualification, executable qualification or runtime validation.

---

# 46. Safety of Power-Management Patches

Power-management ownership must not be modified by guessing.

A retained sleep blocker must not simply be cleared because it appears inconvenient.

If the WLAN device or host interface still legitimately requires the MCU to remain awake, premature release can cause:

- lost WLAN communication
- missed interrupts
- transport corruption
- invalid driver state
- premature deep sleep
- unstable firmware behavior

Likewise, a shared reference counter must not be replaced by a Boolean when multiple owners can legitimately overlap.

Corrective patches require reconstruction of:

```text
acquire
operation
completion
timeout
late completion
failure
release
```

before ownership behavior is changed.

This principle drove the A1/A1R lifecycle work and the B2 bounded-serialization correction.

---

# 47. Distribution Policy

The public research repository should contain enough information to reproduce and review the research without distributing Shelly proprietary firmware.

The repository may publish:

- firmware identification
- reverse-engineering findings
- patch rationale
- minimal patch offsets and byte modifications where appropriate
- patch-generation tooling
- deterministic construction scripts
- validation tooling
- manifests
- hashes
- CRC values
- memory maps
- hook maps
- qualification results
- test methodology
- sanitized runtime evidence

The repository should not publish:

- original Shelly firmware binaries
- complete patched Shelly firmware binaries
- extracted proprietary application images
- protected proprietary firmware payloads
- large raw proprietary disassemblies
- private LAN information
- MAC addresses or BSSIDs
- security-sensitive implementation details unrelated to the public battery-drain analysis

The guiding principle is:

> **Publish the analysis, construction method and verification evidence — not Shelly's firmware.**

Generated firmware artifacts and internal build outputs remain private.

---

# 48. Experimental Use

These patches are research firmware.

They are not official Shelly releases.

A user applying experimental firmware accepts risks including:

- failed OTA
- boot failure
- WLAN failure
- incorrect thermostat behavior
- incorrect valve behavior
- increased battery consumption
- loss of cloud connectivity
- need for device recovery

A fail-closed patcher can reduce accidental misuse of incompatible inputs.

It cannot turn experimental firmware into a vendor-supported release.

---

# 49. Current Status

The project has progressed substantially beyond the original A+B isolation stage.

## Beacon Recovery

Stock 2.2.4 contains demonstrated host-side Beacon Recovery validity defects.

C-C corrects the qualified C1a/C1b/C2 behavior while preserving fresh valid Recovery.

C2 can produce metastable repeated Recovery but should not be described as a permanently irreversible state.

## Periodic mDNS

The recurring mDNS restart is a real periodic workload.

Patch B suppresses the targeted recurring caller.

Historical testing demonstrated that stock Beacon Recovery can continue without this mDNS path.

## PM Lifecycle

Multiple PM ownership, settlement and failure-path defects were reconstructed.

A1 was the original experimental correction.

A later experimental A1 regression was then identified and corrected by A1R.

The A1 regression must not be represented as a Shelly stock defect.

## Host Sleep

The permanent B3 contribution is intentional under the reconstructed stock clock/timebase design.

A separate B2 reference-counter concurrency defect was demonstrated.

Bounded serialization of the affected B2 RMW operations is now qualified.

## WF200

Official WF200 3.18.0 contains a relevant Silicon Labs power-management fix.

The tested Shelly FMAC 3.7.0 host implementation successfully operated with the experimental 3.18.0 integration.

This does not establish that the radio update alone solves battery drain.

## Additional Corrections

Qualified additional corrections now include:

```text
Calibration Restore Guard
P01 battery-ADC PA3 cleanup
P02 I2C timeout retirement
P03 WLAN GPIO interrupt-mask correction
```

These are included in B2.2 but not retroactively in earlier firmware.

## Current Hardware Platform

The current hardware test platform is:

```text
B2.1_OBS
```

with:

```text
A1R
+
C-C
+
B2 serialization
+
minimal MQTT PUBLISH guard
+
WF200 3.18.0
+
PM52 -> cmd66 observer
```

Six B2.1_OBS devices are currently being compared against one stock 2.2.4 control.

The purpose is long-term runtime and battery observation without changing test variables.

## Current Offline Candidate

The current observer-free offline candidate is:

```text
B2.2
```

Disposition:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

B2.2 has **not** yet been hardware-qualified.

No battery-life claim is made for B2.2.

---

# 50. Related Documents, Research Method and Disclaimer

Firmware chronology:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

PM lifecycle and A1/A1R:

[`../reverse-engineering/pm-lifecycle-and-a1.md`](../reverse-engineering/pm-lifecycle-and-a1.md)

Host sleep and blocker accounting:

[`../reverse-engineering/host-sleep-and-blocker-accounting.md`](../reverse-engineering/host-sleep-and-blocker-accounting.md)

Host power management and sleep:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Beacon counter:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

Calculated beacon skip:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

WF200 firmware:

[`../reverse-engineering/wf200-firmware.md`](../reverse-engineering/wf200-firmware.md)

Periodic mDNS:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

AP selection and roaming:

[`../reverse-engineering/ap-selection-and-roaming.md`](../reverse-engineering/ap-selection-and-roaming.md)

mDNS runtime comparison:

[`../testing/mdns-runtime-comparison.md`](../testing/mdns-runtime-comparison.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

This work combines:

- static ARM Thumb reverse engineering
- cross-version firmware comparison
- binary-difference analysis
- call-site reconstruction
- executable offline verification
- deterministic patch construction
- composition qualification
- GBL parsing and reconstruction
- relocation verification
- physical OTA testing
- packet capture
- long-term runtime logging
- controlled firmware variants

Important control-flow conclusions are checked against native instructions and executable behavior rather than relying only on decompiler output.

Experimental patches are constructed from locally obtained stock firmware.

No direct laboratory current measurement is currently used in the investigation.

Battery behavior is therefore evaluated primarily through long-term runtime, voltage trends and firmware telemetry.

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

All product names and trademarks belong to their respective owners.

The documented patches are experimental research artifacts for the specific firmware versions and devices investigated.

They must not be treated as official firmware updates or vendor-supported fixes.