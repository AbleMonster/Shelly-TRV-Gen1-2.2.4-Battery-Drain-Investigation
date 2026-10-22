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

Further reverse engineering showed that these mechanisms are only part of the firmware behavior relevant to the investigation.

The project now distinguishes four classes of experimental firmware:

```text
Isolation patches
    |
    +-- Patch A
    +-- Patch B
    +-- Patch A+B

Corrective host patches
    |
    +-- C-C
    +-- A1

Radio integration
    |
    +-- WF200 3.18.0

Diagnostic firmware
    |
    +-- D3 observer
    +-- Stock Host Observer
```

The current work should therefore not be described simply as an "A+B patch" project.

Patch A and Patch B remain useful historical experiments, but later patches target the actual correctness problems identified during reverse engineering.

No experimental firmware in this repository should be described as a confirmed complete battery-drain fix.

Several independent firmware defects have been identified and corrected experimentally, but their quantitative contribution to the historical battery-drain problem remains under investigation.

---

# 1. Patch Overview

| Variant | Type | Primary purpose | Hardware tested |
|---|---|---|---|
| Patch A | isolation | bypass 2.2.4 Beacon Recovery | yes |
| Patch B | isolation | suppress periodic connected mDNS restart | yes |
| Patch A+B | isolation | suppress both historical test mechanisms | yes |
| C-C | corrective | correct Beacon Recovery control validity | yes |
| A1 | corrective | correct identified PM lifecycle / ownership defects | yes, in integrated build |
| WF200 3.18.0 | radio integration | evaluate newer Silicon Labs power-save firmware | yes |
| C-C + WF200 3.18.0 | integrated experimental | corrected Recovery + newer radio | yes |
| A1 + C-C + WF200 3.18.0 | integrated experimental | combined host/radio correction platform | yes |
| D3 Observer | diagnostic | observe WF200 `PS_MODE_ERROR` | yes |
| Stock Host Observer | diagnostic | observe B2 / EM1 / EM2 / PA8 on otherwise stock 2.2.4 | qualification in progress |

The distinction between these variants matters.

An isolation patch answers:

> What happens when this mechanism is removed?

A corrective patch answers:

> Can the demonstrated firmware defect be corrected while preserving legitimate behavior?

An observer answers:

> Does the statically demonstrated condition actually occur on physical hardware?

These are different experimental questions.

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

Offsets documented for firmware 2.2.4 must never be applied blindly to another firmware release.

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
    |     +-- correct PM lifecycle /
    |         ownership / settlement defects
    |
    +-- C-C + WF200 3.18.0
    |
    +-- A1 + C-C + WF200 3.18.0
    |     |
    |     +-- current integrated experimental
    |         correction platform
    |
    +-- Stock Host Observer
          |
          +-- preserve stock behavior
          +-- observe B2 / EM1 / EM2 / PA8
```

The patches were developed incrementally as the understanding of the firmware improved.

Early patches should therefore be interpreted in the context of the questions they were designed to answer rather than as increasingly complete production fixes.

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

Affected stock devices can repeat this sequence approximately once per minute for extended periods.

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

It is not the preferred final correction because legitimate fresh Recovery is also suppressed.

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

More importantly, stock Beacon Recovery continued.

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

The result establishes that the targeted periodic mDNS restart is not required for the recurring Beacon Recovery behavior.

It does not prove that mDNS has zero energy cost, and it does not prove that the remaining Recovery events caused the complete discharge.

Patch B remains useful as an isolation experiment.

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

Patch A+B was useful because it created four experimental states:

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

It is no longer the current corrective architecture.

Patch A+B should now be considered a historical combined isolation experiment.

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

C-C instead corrects the invalid control semantics while retaining Recovery for a fresh valid qualifying measurement.

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

This can produce:

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
Recovery
        |
        v
P cleared again
```

A single qualifying measurement can therefore become a self-sustaining approximately minute-spaced loop.

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
- the known stale-state self-sustaining Recovery behavior is removed
- fresh qualifying Recovery remains possible

This last point is important.

C-C is not equivalent to Patch A.

Fresh Recovery events continue to occur on C-C-based firmware.

C-C + WF200 3.18.0 configurations have shown fresh Recovery rates in the approximate range of:

```text
~27–30 events/hour
```

during parts of the current tests.

This is substantially different from the approximately:

```text
~58–60 events/hour
```

stock stale-loop behavior observed on affected devices.

The remaining fresh trigger is still under investigation.

---

# 11. A1 — Power-Management Lifecycle Correction

Further reverse engineering identified a second class of host defects outside the Beacon Recovery estimator.

These involve the lifecycle of WLAN power-management operations and the ownership of host sleep restrictions.

A1 was developed to correct these problems while preserving the surrounding PM architecture.

Its scope includes the defect classes tracked in the project as:

```text
G01
G02
G03
G05
G06
G18
G19
```

The exact defect descriptions are maintained in the project error/correction documentation.

At a high level, A1 addresses:

- Final-Sleep failure cleanup
- Wake failure state handling
- timeout versus cancellation
- late completion ambiguity
- requested versus committed PM state
- stale/old PM completion races
- independent inhibit ownership
- PM settlement and handoff correctness

A1 is a corrective patch, not an isolation bypass.

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

Some stock error exits can leave the host-side restriction retained.

A1 corrects the qualified failure lifecycle rather than blindly clearing the blocker.

This distinction is important.

A sleep blocker must not be released unless the associated operation no longer legitimately requires it.

---

# 13. Wake Failure Handling

The reverse path contains a complementary problem.

Stock logic can update software state before lower-level wake success has been established.

A lower-layer failure can therefore leave software ownership/state inconsistent with the physical or driver state.

A1 changes the qualified sequence so software commitment follows the validated operation rather than preceding it.

---

# 14. Timeout Is Not Cancellation

Another important finding is that a timeout does not necessarily mean the lower-level operation can no longer complete.

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

A1 therefore tracks the qualified settlement/ownership relationship rather than assuming timeout means the lower operation disappeared.

---

# 15. Requested vs. Committed PM State

Stock firmware can treat requested power-management state as though it were already committed before the lower-level operation has successfully completed.

A1 separates:

```text
desired / requested state
```

from:

```text
successfully committed state
```

where required by the reconstructed lifecycle.

This prevents subsequent control decisions from relying on a PM transition that did not actually settle successfully.

---

# 16. Old PM Completion Race

A later completion belonging to an older PM request can race with a newer request.

Without sufficient generation/ownership tracking, the old completion can incorrectly affect current state.

A1 includes qualified generation/settlement handling to prevent an obsolete completion from being accepted as the current transition.

---

# 17. Independent Inhibit Ownership

The firmware can have more than one reason for temporarily preventing or altering a PM transition.

A1 preserves independent ownership rather than collapsing unrelated inhibit conditions into one ambiguous state.

This is necessary because releasing one reason must not release another still-active reason.

---

# 18. A1 Qualification

The final A1 production integration was statically qualified before controlled hardware testing.

The final qualification included:

- corrected association normalization
- validation of the owned JOIN identity
- validation of accepted terminal state
- cancellation/owed-event checks
- handoff topology validation
- policy publication within the same bounded atomic section
- rejected stale/C4 handoff checks
- PM generation checks
- settlement checks
- hook decoding
- relocation validation
- independent reconstruction
- deterministic rebuild comparison

The final behavioral verification covered:

```text
33 / 33 final-byte behavior scenarios
+
3 canonical protected-byte controls
=
36 / 36 canonical PASS
```

Additional malformed and corruption fixtures were also required to reject.

The final integration contained:

```text
93 hooks
210 relocations
```

all of which decoded correctly during qualification.

The final application reconstruction contained no unexplained changes.

---

# 19. What A1 Does Not Fix

A1 does **not** globally serialize every shared B2 blocker-counter operation.

This became important after a later host-sleep audit identified a separate concurrency defect in the common blocker accounting.

The distinction is:

```text
A1
    |
    +-- PM operation ownership
    +-- settlement
    +-- failure lifecycle
    +-- handoff correctness


B2 concurrency defect
    |
    +-- shared aggregate reference-counter RMW
    +-- task-preemption race
```

The B2 problem is outside the current A1 scope.

It is not an A1 regression.

---

# 20. WF200 3.18.0 Integration

The protected WF200 firmware shipped with stock Shelly TRV 2.2.4 is:

```text
WF200 3.16.1
```

Silicon Labs later released WF200 firmware:

```text
3.18.0
```

The investigated official 3.18.0 SEC image has:

```text
Size:
312,400 bytes

SHA-256:
886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9
```

The 3.18.0 changelog contains a particularly relevant power-management fix described as:

```text
device not sleeping after power-save mode change
```

This is relevant to the class of failure being investigated.

It is not proof that the Silicon Labs fix explains the historical Shelly TRV battery drain.

---

# 21. FMAC 3.7.0 + WF200 3.18.0 Compatibility Test

Shelly firmware 2.2.4 uses:

```text
FMAC 3.7.0
```

The project experimentally integrated the official WF200 3.18.0 firmware while retaining the Shelly FMAC 3.7.0 host driver.

Physical-device testing showed successful:

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

It does not represent an official Silicon Labs or Shelly compatibility qualification.

---

# 22. WF200 3.18.0 Construction

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

The final extracted SEC from the generated GBL was verified byte-for-byte against the official WF200 3.18.0 input.

---

# 23. C-C + WF200 3.18.0

C-C was also combined with the newer radio firmware independently of A1.

This configuration is useful because it separates:

```text
Beacon Recovery validity correction
```

from:

```text
A1 PM lifecycle correction
```

while using the newer WF200 firmware.

Physical-device testing confirmed that fresh Recovery events still occur with:

```text
C-C
+
WF200 3.18.0
```

The newer radio firmware therefore does not simply eliminate all fresh host-observed Beacon Recovery conditions.

---

# 24. A1 + C-C + WF200 3.18.0

The current integrated correction platform combines:

```text
A1
+
C-C
+
WF200 3.18.0
```

This configuration addresses three different areas:

```text
C-C
    Beacon Recovery control validity

A1
    host PM lifecycle / ownership correctness

WF200 3.18.0
    newer protected radio PM implementation
```

The components should not be treated as one undifferentiated patch.

Each addresses a different layer.

---

## 24.1 Controlled-Test Artifact

The statically qualified controlled-test GBL is:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

GBL size:

```text
1,123,380 bytes
```

GBL SHA-256:

```text
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379
```

Stored/calculated END CRC32:

```text
F01262BC
```

Whole-file CRC32 residue:

```text
2144DF1C
```

Application size:

```text
1,066,544 bytes
```

Application SHA-256:

```text
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The experimental firmware binary itself is not distributed through the public research repository.

---

## 24.2 Hardware Result

The qualified artifact was installed through the normal Gen1 OTA mechanism on a controlled test device.

The device successfully:

- accepted the OTA
- cold rebooted
- initialized FMAC 3.7.0
- initialized WF200 3.18.0
- scanned for WLAN
- associated
- obtained DHCP configuration
- connected to Shelly Cloud
- operated the thermostat
- operated the valve
- completed later calibration
- entered normal WLAN power-management states
- continued reporting runtime statistics

The initial hardware qualification therefore passed.

Long-term testing continues.

---

## 24.3 Fresh Recovery Remains

The integrated device continued to produce fresh Beacon Recovery events.

Observed rates during the first long-term period were approximately:

```text
27–28 events/hour
```

despite C-C preventing the known stale self-sustaining stock loop.

This is important because it separates:

```text
stock stale recurrence
```

from:

```text
fresh qualifying estimator behavior
```

The remaining fresh trigger is still under investigation.

---

# 25. Remaining B2 Blocker-Accounting Defect

A later EFM32GG11 host-sleep audit identified another host-side correctness defect.

B2 is a shared reference counter.

It represents the number of active software owners that currently require the host to remain at EM1 instead of entering EM2.

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

This is the correct general design.

The defect is that not all B2 read-modify-write operations are serialized.

---

# 26. B2 Lost-Update Race

Some task-side paths effectively perform:

```c
old = B2;
new = old + 1;
B2 = new;
```

or the corresponding decrement while task preemption remains possible between the load and store.

Other B2/O operations are protected by a saved-PRIMASK critical section.

This mixture allows real task schedules to corrupt the aggregate reference count.

---

## 26.1 Phantom B2

A verified 2.2.4 schedule can produce:

```text
B2 = 1

unprotected task:
    load B2 = 1

        ↓ task switch

protected O release:
    B2 1 -> 0

        ↓ task switch back

unprotected task:
    store stale 1 + 1
    B2 = 2
```

Only one owner actually remains.

When that owner later releases:

```text
B2 2 -> 1
```

the host is left with:

```text
B2 = 1
```

and no legitimate owner.

The sleep selector then limits normal idle to:

```text
EM1
```

instead of the intended:

```text
EM2
```

until the corrupted state is corrected by some later event or reset.

---

## 26.2 Lost B2 Contribution

The opposite race can also occur.

Two owners can become active while a stale store leaves the aggregate at:

```text
B2 = 1
```

instead of:

```text
B2 = 2
```

When one owner later releases, B2 can reach zero while the other owner is still active.

This can permit EM2 earlier than intended.

The defect therefore affects correctness in both directions.

---

# 27. B2 Is Not a Boolean

The appropriate correction is **not**:

```text
force B2 = 0
```

and it is not:

```text
replace B2 with one subsystem's state
```

Multiple owners can legitimately require EM1 at the same time.

The shared reference-count semantics must be preserved.

The appropriate correction direction is bounded serialization of the complete B2 check/read-modify-write operation while preserving the caller ABI and ownership model.

That correction has not yet been integrated into the current A1 production patch.

---

# 28. B3 and EM3

The same host-sleep audit also resolved the meaning of the permanent B3 contribution.

During normal startup, the firmware installs a B3 contribution before the scheduler begins normal operation.

This prevents normal idle from selecting EM3.

That behavior is intentional.

The stock TRV configures its RTC/tickless timebase from the LFXO.

The EM3 path disables:

```text
LFXO
LFRCO
```

while EM2 retains the required low-frequency clock.

The intended normal deep idle state is therefore:

```text
EM2
```

not:

```text
EM3
```

The project does not treat the permanent B3 contribution as a battery-drain bug.

A future patch must not "fix" battery drain by simply clearing B3 or enabling EM3.

Doing so would require a separate clock/timebase redesign.

---

# 29. PA8 WLAN Sleep Gate

The host sleep path contains another mechanism independent of B2.

PA8 participates in the WLAN host-notification path.

Immediately before low-power entry, the host checks PA8.

If PA8 is HIGH:

```text
WFI is vetoed
```

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

This is not automatically a firmware defect.

Preventing host sleep while the WLAN device has pending work is reasonable.

The open runtime question is whether PA8 remains asserted or repeatedly vetoes WFI for unexpectedly long periods during a battery-drain episode.

---

# 30. Stock Host Observer

The B2 and PA8 findings require runtime evidence before another corrective patch is justified.

For that reason, the next diagnostic firmware is intentionally based on clean stock 2.2.4.

It should retain:

```text
stock Beacon Recovery
stock PM lifecycle
stock B2/B3 accounting
stock Final-Sleep behavior
stock PA8 behavior
stock WF200 3.16.1
```

It should **not** include:

- A1
- C-C
- MIN80
- D3 observer
- WF200 3.18.0
- B2 serialization fix

The objective is to observe the shipped firmware behavior before changing it.

---

# 31. Observer Questions

The Stock Host Observer is intended to answer:

1. Does B2 remain non-zero without a legitimate known owner?

2. Can the demonstrated B2 lost-update race occur on physical hardware?

3. Can B2 become too small relative to active owners?

4. How often does the host actually enter EM1?

5. How often does the host actually enter EM2?

6. How often does PA8 veto WFI?

7. Does PA8 remain asserted unusually long?

8. Does a battery-drain period correlate with:
   - phantom B2
   - lost B2 ownership
   - prolonged EM1 restriction
   - prolonged PA8/WFI veto
   - or none of these?

---

# 32. Observer Noninterference Requirement

The observer must not repair the race it is intended to observe.

In particular, instrumentation must not:

- wrap the stock B2 read-modify-write in a new critical section
- disable interrupts across the stock race window
- suspend scheduling across the stock race window
- move the stock B2 load/store operations
- change task priorities
- change IRQ priorities
- introduce locks around the stock helper
- change the stock sleep policy

Observer-private state may use bounded synchronization only where it does not encompass or serialize the stock B2 operation.

This requirement is more important than collecting every possible statistic.

A less detailed observer that preserves the original race is preferable to a more detailed observer that changes its probability or removes it.

---

# 33. Planned Observer Telemetry

The observer design includes or considers compact RAM-only telemetry such as:

```text
current:
    B2
    B3
    O
    PA8

sleep:
    EM1 entry count
    EM2 entry count
    WFI attempts
    PA8 veto count

B2:
    add attempts
    remove attempts
    owner-specific activity

shadow ownership:
    MOTOR
    MANUAL_DTIM
    OTA
    WLAN/O
    INIT
    OTHER

diagnostics:
    B2 mismatch
    first-fault snapshot
    compact recent-event ring
```

The observer must not create periodic network traffic or a background timer solely for telemetry.

Readout should occur only on explicit request.

`/stats sleep_ratio` is not treated as physical sleep residency.

---

# 34. Observer Qualification Status

The Stock Host Observer is currently under static and executable qualification.

A working application has been constructed, and initial independent byte checks confirmed that the following stock components remain unchanged:

```text
B2 helpers
sleep selector
permanent B3 contribution
stock radio payload
```

Supplemental bookkeeping tests have also begun passing.

However, the observer is **not yet device-test qualified**.

Remaining qualification includes emitted Thumb wrapper execution, register/interrupt preservation, status serialization, stack safety and final container verification.

It must not be flashed as a qualified observer until the complete gate passes.

The required final verdict is:

```text
STOCK HOST OBSERVER QUALIFIED FOR CONTROLLED DEVICE TEST
```

or:

```text
NO-GO
```

No intermediate build should be represented as device-test qualified.

---

# 35. Current Experimental Architecture

The current research architecture can be summarized as:

```text
                         Stock 2.2.4
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
       Patch A             Patch B          Stock Observer
       isolation           isolation         diagnostic
          |                   |                   |
          +--------+----------+                   |
                   |                              |
                   v                              v
                Patch A+B                    B2 / PA8 /
                historical                   EM1 / EM2
                isolation                    evidence


                         Corrective path
                              |
                 +------------+------------+
                 |                         |
                 v                         v
                C-C                       A1
        Recovery validity          PM lifecycle /
                                  ownership
                 |                         |
                 +------------+------------+
                              |
                              v
                         A1 + C-C
                              |
                              v
                       WF200 3.18.0
                              |
                              v
                  integrated experimental
                       test platform
```

The Stock Host Observer deliberately branches from stock rather than from the corrected platform.

That preserves causal isolation for the newly identified B2 problem.

---

# 36. Why the Current Work Is Still Experimental

Several firmware defects are now demonstrated at code level.

Several corrective patches have also passed substantial static qualification and controlled hardware testing.

That is different from proving that the historical battery-drain problem has been completely solved.

The project still lacks direct electrical current measurements.

Battery behavior is inferred from long-term device runtime, voltage trends and firmware telemetry rather than laboratory power profiling.

Historical drain also occurs on firmware older than 2.2.4.

Therefore:

```text
C-C fixes real 2.2.4 bugs
```

does not imply:

```text
C-C fixes all historical drain
```

Likewise:

```text
A1 fixes real PM lifecycle bugs
```

does not imply:

```text
A1 alone explains historical drain
```

and:

```text
WF200 3.18.0 contains a relevant Silicon Labs sleep fix
```

does not imply:

```text
WF200 3.18.0 alone solves the TRV problem
```

The project intentionally keeps these conclusions separate.

---

# 37. Current Battery-Drain Model

The current working model contains several potentially interacting layers:

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
        +-- PA8 WLAN sleep veto
        |
        +-- WF200 power-save behavior
        |
        +-- RF / AP environment
```

Some of these contain demonstrated firmware defects.

Others are normal mechanisms whose runtime behavior may still affect battery life.

The objective is not to suppress every activity that consumes energy.

The objective is to restore correct firmware behavior and determine whether the corrected system achieves normal battery endurance.

---

# 38. Current Research Direction

The immediate research sequence is:

```text
1. Complete Stock Host Observer qualification

2. Test observer on physical stock 2.2.4

3. Determine whether:
       phantom B2 occurs
       lost B2 occurs
       EM2 is incorrectly blocked
       PA8 excessively vetoes WFI

4. If field B2 corruption is observed:
       build bounded B2 serialization correction

5. Retain the same observer where practical

6. Compare:
       stock observer
       vs.
       B2-corrected observer

7. If qualified:
       integrate B2 correction into
       A1 + C-C + WF200 3.18.0

8. Continue long-term battery/runtime testing
```

EM3 is not part of this correction plan.

The target remains correct entry into the intended EM2 state whenever no legitimate blocker exists.

---

# 39. Patcher Design

Public patch tooling should generate experimental firmware from a locally obtained verified stock image.

The patcher must fail closed.

It should not attempt to "make the input fit" when validation fails.

Important construction requirements include:

- exact source-firmware identification
- exact expected input size
- exact expected hashes where applicable
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

# 40. Deterministic Construction

For complex patches such as A1 and the WF200 3.18.0 integration, construction reproducibility is part of the qualification.

The same verified inputs and patcher revision should produce byte-identical:

```text
application image
GBL
construction manifest
```

across repeated builds.

Unexplained output differences are treated as a construction failure rather than ignored.

---

# 41. Container Integrity

A valid application patch is not sufficient by itself.

The resulting GBL must also preserve the expected container structure and integrity fields.

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

For WF200 replacement builds, the extracted final radio payload must match the intended input radio firmware byte-for-byte after accounting for the qualified container placement.

---

# 42. OTA Installation

Experimental GBL files have been installed successfully through the normal Shelly Gen1 OTA mechanism using a local HTTP server.

The TRV requests the firmware using HTTP byte-range behavior.

For the current local test setup, the OTA server must be reachable on:

```text
TCP port 80
```

Using port 8000 caused problems with the TRV OTA retrieval path.

On macOS, binding the Python OTA server to port 80 normally requires elevated privileges.

Successful OTA transfer only establishes that the generated GBL was accepted and booted far enough to perform the update.

It does not replace static or runtime qualification.

---

# 43. Safety of Power-Management Patches

Power-management ownership must not be modified by guessing.

For example, a retained sleep blocker must not be "fixed" by simply clearing it.

If the WLAN device or host interface still legitimately requires the MCU to remain awake, premature release can cause:

- lost WLAN communication
- missed interrupts
- transport corruption
- invalid driver state
- premature deep sleep
- unstable firmware behavior

Likewise, a reference counter must not be replaced by a Boolean if multiple owners can legitimately overlap.

Corrective patches therefore require reconstruction of:

```text
acquire
operation
completion
timeout
late completion
failure
release
```

before changing ownership behavior.

This requirement drove the A1 qualification work and also applies to any future B2 correction.

---

# 44. Distribution Policy

The public research repository should contain enough information to reproduce and review the research without distributing Shelly's proprietary firmware.

The repository may publish:

- firmware identification
- reverse-engineering findings
- patch rationale
- patch offsets
- minimal byte modifications
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
- protected firmware dumps obtained from proprietary packages
- large raw proprietary disassemblies
- sensitive device/network data

The guiding principle is:

> **Publish the analysis, construction method and verification evidence — not Shelly's firmware.**

Research and construction scripts may remain public even while experimental.

Generated firmware artifacts and internal build outputs remain private.

---

# 45. Experimental Use

These patches are research firmware.

They are not official Shelly releases.

A user applying them accepts the risks associated with experimental firmware, including:

- failed OTA
- boot failure
- WLAN failure
- incorrect thermostat behavior
- incorrect valve behavior
- increased battery consumption
- loss of cloud connectivity
- need for device recovery

The patcher should make unsupported input difficult to use accidentally, but it cannot make experimental firmware equivalent to a vendor-supported release.

---

# 46. Current Status

The project has progressed beyond the original A+B isolation stage.

Current conclusions are:

### Beacon Recovery

The 2.2.4 Beacon Recovery path contains demonstrated host-side validity defects.

C-C corrects the identified C1a/C1b/C2 behavior while preserving fresh valid Recovery.

Hardware testing confirms that the stale self-sustaining stock loop can be removed without disabling all Recovery.

### Periodic mDNS

The recurring mDNS restart is a real periodic workload.

Patch B suppresses the targeted recurring caller.

Long-term testing shows that stock Beacon Recovery continues without it.

Periodic mDNS is therefore not required for the recurring Recovery loop.

### PM Lifecycle

Several PM ownership, settlement and failure-path defects were reconstructed in detail.

A1 corrects the qualified defect set.

The integrated A1 build passed extensive static qualification and has booted successfully on physical hardware.

### WF200

Official WF200 3.18.0 contains a relevant Silicon Labs power-save sleep fix.

FMAC 3.7.0 successfully initialized and operated with the tested 3.18.0 integration on physical TRV hardware.

Fresh Beacon Recovery still occurs.

### Host Sleep

The permanent B3 contribution is intentional and keeps normal idle at EM2 because the stock RTC/tickless configuration depends on LFXO.

A separate shared B2 reference-counter concurrency defect has been demonstrated statically in real 2.2.4 task schedules.

A phantom B2 contribution can incorrectly keep the host at EM1.

A lost contribution can incorrectly permit EM2 while a legitimate owner remains active.

Physical occurrence has not yet been established.

### PA8

PA8 belongs to the WLAN host-notification path and can veto WFI while HIGH.

This is not automatically a bug.

Its runtime duty and relationship to drain still need measurement.

### Stock Host Observer

A clean-stock observer is currently being qualified to measure B2 ownership consistency, EM1/EM2 entry and PA8 WFI veto behavior without correcting the stock race.

It is not yet qualified for device testing.

---

# 47. What Is Not Yet Established

The current work does not establish:

- the single historical root cause of all Shelly TRV Gen1 battery drain
- the quantitative energy cost of one Beacon Recovery cycle
- the quantitative energy cost of periodic mDNS
- the field occurrence rate of the B2 lost-update race
- the duration of PA8 HIGH states during historical drain
- physical EFM32GG11 EM1/EM2 residency during historical drain
- physical WF200 sleep residency during historical drain
- that WF200 3.18.0 alone solves the problem
- that A1 alone solves the problem
- that C-C alone solves the problem
- that the integrated A1+C-C+WF200 3.18.0 firmware is a final production fix
- the final battery-life improvement of the complete corrected platform

These questions require continued runtime evidence.

---

# 48. Related Documents

Firmware chronology:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

Beacon counter:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

Calculated beacon skip:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

Periodic mDNS:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

Host power management and sleep:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

AP selection and roaming:

[`../reverse-engineering/ap-selection-and-roaming.md`](../reverse-engineering/ap-selection-and-roaming.md)

mDNS runtime comparison:

[`../testing/mdns-runtime-comparison.md`](../testing/mdns-runtime-comparison.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# 49. Research Method

This work combines:

- static ARM Thumb reverse engineering
- cross-version firmware comparison
- binary-difference analysis
- call-site reconstruction
- executable offline verification
- deterministic patch construction
- GBL parsing and reconstruction
- relocation verification
- physical OTA testing
- packet capture
- long-term runtime logging
- controlled firmware variants

Important control-flow conclusions are checked against native instructions and executable behavior rather than relying only on decompiler output.

Experimental patches are constructed from locally obtained stock firmware.

No direct electrical current measurement is used in the current investigation.

Battery behavior is evaluated primarily through long-term runtime and voltage data.

---

# 50. Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

All product names and trademarks belong to their respective owners.

The documented patches are experimental research artifacts for the specific firmware versions and devices investigated.

They should not be treated as official firmware updates or vendor-supported fixes.
