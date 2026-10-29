# Firmware Comparison – Shelly TRV Gen1

## Scope

This document compares the WLAN, power-management and battery-relevant behavior of the investigated Shelly TRV Gen1 (`SHTRV-01`) firmware generations.

The primary stock firmware versions are:

| Firmware | Build | Role |
|---|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` | oldest detailed reference |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` | early comparison |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` | later comparison / drain reference |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` | primary reverse-engineering target |

The purpose is not to assign the historical battery-drain problem to one release.

Battery drain has been observed across more than one firmware generation.

The comparison is intended to determine:

- which mechanisms are shared
- which mechanisms were added later
- which defects are version-specific
- which defects belong to the older architecture
- how FMAC and WF200 changed
- which fixes address demonstrated defects
- which mechanisms cannot explain the complete historical problem
- how the experimental firmware evolved from isolation patches to the current qualified builds

The comparison combines:

- ARM Thumb reverse engineering
- cross-version binary comparison
- runtime telemetry
- packet capture
- controlled firmware modifications
- executable behavior qualification
- deterministic binary reconstruction
- long-term physical-device testing

Detailed mechanism analyses are kept in dedicated documents.

This file focuses on chronology and cross-version interpretation.

---

# 1. High-Level Chronology

The investigated releases show incremental evolution rather than a complete redesign.

A simplified chronology is:

```text
2.1.0
 |
 | common WLAN / host-sleep architecture
 | Fast Power Save
 | shared B2/B3 blocker accounting
 | permanent B3 contribution
 | PA8 WLAN sleep gate
 | PM lifecycle / Final-Sleep failure paths
 |
 v
2.1.3
 |
 | recurring connected mDNS restart
 | state-5 / psovrd2
 | PM/event changes
 |
 v
2.1.8
 |
 | mDNS cadence changes to ~180 s
 | post-association PM sequencing changes
 | FMAC / WF200 update
 |
 v
2.2.4
 |
 | expanded WF200 statistics
 | real_beacon_skip
 | Beacon Recovery
 | additional PM retry / ownership behavior
 | FMAC 3.7.0
 | WF200 3.16.1
 |
 v
experimental investigation
 |
 +-- Patch A / Patch B / A+B
 |
 +-- C-C
 |
 +-- D3 observer
 |
 +-- MIN80 experiments
 |
 +-- WF200 3.18.0 integration
 |
 +-- historical A1
 |
 +-- A1R
 |
 +-- B2 bounded serialization
 |
 +-- B2.1
 |
 +-- B2.1_OBS
 |
 +-- B2.2
```

This chronology provides an important constraint:

> A mechanism introduced only in firmware 2.2.4 cannot by itself explain battery drain that also occurred on earlier firmware.

That applies particularly to the 2.2.4 Beacon Recovery mechanism.

Later firmware can still introduce additional energy-consuming behavior or amplify an older problem.

---

# 2. Firmware 2.1.0

Firmware 2.1.0 is the oldest release for which the project has detailed host-side analysis.

It already contains the broad architecture recognizable in later versions:

- mDNS responder
- WF200 WLAN power management
- connected Fast Power Save
- host/WLAN wake-resource coordination
- EFM32GG11 sleep selection
- shared blocker counters
- PA8 WLAN notification/sleep gating
- asynchronous PM request/completion handling
- conditional failure paths around WLAN sleep transitions

Several later recurring mechanisms are absent or have not been identified in the same form.

This makes 2.1.0 important for distinguishing:

```text
old common architecture
```

from:

```text
later firmware additions
```

---

# 3. mDNS in 2.1.0

The mDNS responder exists in firmware 2.1.0.

Therefore:

```text
2.1.0 has no mDNS
```

would be incorrect.

What has not been identified in the analyzed 2.1.0 host firmware is the later recurring connected-maintenance path that repeatedly restarts mDNS probing.

A historical packet capture of approximately 13 minutes also did not show the characteristic recurring bursts observed on later firmware.

The supported statement is:

> mDNS exists in 2.1.0, but the later recurring connected restart mechanism was neither identified statically nor observed during that historical capture.

---

# 4. Common Host-Sleep Architecture

Several host-sleep mechanisms originally investigated in 2.2.4 belong to an older architecture.

The host MCU is an:

```text
EFM32GG11
```

The normal idle path selects between:

```text
EM1
EM2
EM3
```

using shared blocker state.

A simplified selector is:

```text
B2 != 0
    -> maximum EM1

B2 == 0 && B3 != 0
    -> EM2

B2 == 0 && B3 == 0
    -> EM3
```

This broad architecture is present across the investigated firmware generations.

---

# 5. Permanent B3 Contribution

The host installs a B3 contribution during normal startup.

This prevents the normal idle selector from choosing EM3.

Further analysis showed that this is intentional.

The TRV uses the LFXO-backed low-frequency timebase for RTC/tickless operation.

The EM3 path disables the low-frequency clocks required by the existing scheduler/timebase design.

Therefore the normal intended deepest idle state is:

```text
EM2
```

not:

```text
EM3
```

The permanent B3 contribution is not currently classified as a battery-drain defect.

Removing it would require a different clock/timebase design.

---

# 6. Shared B2 Sleep-Blocker Counter

B2 is a shared reference counter.

It represents the number of software owners currently requiring the host to remain at EM1 or shallower.

Conceptually:

```text
B2 = 0
    no EM1 owner
    EM2 may be allowed

B2 = 1
    one owner

B2 = 2
    two owners
```

Known users include paths associated with:

- WLAN ownership
- motor activity
- manual DTIM handling
- OTA
- initialization
- WLAN management

Reference-count semantics are therefore intentional.

The defect is not the existence of B2.

The defect is inconsistent serialization of its updates.

---

# 7. B2 Read-Modify-Write Race

Relevant stock paths can effectively perform:

```c
old = B2;
new = old + 1;
B2 = new;
```

or the corresponding decrement while RTOS preemption remains possible between load and store.

Other B2 paths use critical sections.

This allows real task schedules to corrupt the aggregate reference count.

---

# 8. Phantom B2 Contribution

One verified 2.2.4 schedule is:

```text
B2 = 1
WLAN owner active

task A:
    loads B2 = 1

        task switch

task B:
    releases WLAN owner
    B2: 1 -> 0

        task switch

task A:
    stores stale 1 + 1
    B2 = 2
```

Correct state:

```text
B2 = 1
```

because only task A remains.

When task A later releases:

```text
B2: 2 -> 1
```

a phantom contribution remains.

The sleep selector then continues to see:

```text
B2 != 0
```

and may incorrectly restrict normal idle to EM1.

The defect and concrete schedule are established.

The frequency of physical occurrence is not established.

---

# 9. Lost B2 Contribution

The opposite corruption is also possible.

Example:

```text
B2 = 0

motor task:
    loads B2 = 0

        task switch

WLAN task:
    acquires contribution
    B2: 0 -> 1

        task switch

motor task:
    stores stale 0 + 1
    B2 = 1
```

Correct value:

```text
B2 = 2
```

If WLAN later releases:

```text
B2: 1 -> 0
```

the host can permit EM2 even though the motor owner remains active.

This is a correctness defect even where it does not increase power consumption.

---

# 10. Cross-Version Relevance of B2

The B2/B3 architecture predates firmware 2.2.4.

Firmware 2.1.0 already contains:

- equivalent shared blocker architecture
- equivalent sleep-selection semantics
- unmasked aggregate helper patterns
- permanent B3 contribution
- related EM2/EM3 dispatch structure

The fully reconstructed concrete task-preemption witnesses were closed in detail for 2.2.4.

The safe cross-version conclusion is:

> The vulnerable blocker-accounting architecture predates 2.2.4, while the strongest concrete task-level proof currently refers to 2.2.4.

---

# 11. B2 Correction

The qualified correction uses bounded serialization of the complete relevant B2 read-modify-write operation.

It preserves:

```text
reference-count semantics
```

It does not:

```text
force B2 = 0
```

and does not convert B2 into a Boolean.

The correction has now progressed beyond design.

It is qualified and included in:

```text
B2.1
B2.1_OBS
B2.2
```

---

# 12. B2 Qualification

Qualification includes:

```text
2060 core cases
102 additional cases
mixed/preemption qualification
```

plus integrated interaction testing.

Therefore statements in older project documentation that the B2 fix still needs to be developed or validated are obsolete.

---

# 13. PA8 WLAN Sleep Gate

PA8 is an independent host-sleep gate associated with the WLAN notification path.

Immediately before WFI, firmware checks PA8.

Conceptually:

```text
normal sleep decision
     |
     v
B2/B3 select allowed mode
     |
     v
check PA8
     |
     +---- LOW  -> continue toward WFI
     |
     +---- HIGH -> skip WFI
```

PA8 therefore differs from B2.

B2 approximately asks:

```text
How many software owners require EM1?
```

PA8 approximately asks:

```text
Is WLAN host-notification work pending?
```

PA8 HIGH is not automatically a defect.

Preventing host sleep while WLAN work is pending is legitimate behavior.

---

# 14. Final-Sleep / PM Lifecycle

The WLAN PM architecture contains asynchronous operations in which:

```text
wake/acquire
   |
   v
PM operation
   |
   v
final sleep
   |
   v
cleanup/release
```

must remain consistent across:

- success
- failure
- timeout
- cancellation
- late completion
- generation changes

Analysis identified several concrete lifecycle defects in 2.2.4.

These became the basis of historical A1.

---

# 15. Historical PMD210 Evidence on 2.1.0

A diagnostic PMD210 experiment on stock 2.1.0 exposed repeated raw ACK-wait failures that are normally hidden by higher-level firmware semantics.

Historical examples included approximately:

```text
7 failures around ~81 s
9 failures around ~1128 s
```

These were not limited to immediate boot behavior.

This establishes that low-level PM failure behavior predates firmware 2.2.4.

It does not prove those failures caused the historical battery drain.

---

# 16. 2.2.4 Final-Sleep / PM52 Control Result

A separate historical stock 2.2.4 + MIN80 control on `.11` observed approximately:

```text
108 Final-Sleep attempts
108 Final-Sleep completions
0 Final-Sleep failures

216 PM52 attempts
0 PM52 failures

107 native Beacon Errors
```

This establishes an important separation:

> Beacon Error activity is not simply equivalent to a raw Final-Sleep or PM52 failure.

---

# 17. Firmware 2.1.0 → 2.1.3

The transition to 2.1.3 retains the older architecture while adding several WLAN behaviors.

Relevant changes include approximately:

```text
2.1.0
 |
 v
2.1.3
 |
 +-- recurring connected mDNS restart
 +-- state-5 / psovrd2
 +-- named temporary PM override
 +-- wake ACK timing changes
 +-- event-handling changes
```

The normal connected Fast Power Save architecture remains recognizable.

---

# 18. Periodic mDNS Restart in 2.1.3

The recurring connected maintenance path periodically invokes behavior equivalent to:

```text
mdns_resp_restart()
```

restarting probing:

```text
connected maintenance
     |
     v
restart probing
     |
     v
probe
probe
probe
     |
     v
announcement
```

Historical packet capture observed a cadence around:

```text
60 s
```

The important change is not:

```text
mDNS introduced
```

but:

```text
recurring connected mDNS probing restart introduced
```

---

# 19. State 5 / `psovrd2`

Firmware 2.1.3 contains a temporary WLAN PM override associated with state 5.

Known control paths include:

```text
/psovrd2
```

and its cloud-side equivalent.

The mechanism requests approximately:

```text
Fast Power Save
beacon skip = 10
```

with a countdown initialized around:

```text
180
```

This does not mean the EFM32 host remains continuously awake for 180 seconds.

It changes WLAN PM policy.

---

# 20. Firmware 2.1.3 → 2.1.8

The transition to 2.1.8 changes both host and WLAN components.

Relevant differences include:

- recurring mDNS cadence
- post-association PM sequencing
- FMAC update
- WF200 update
- additional WLAN state-restoration behavior

Battery drain was also observed on 2.1.8.

That fact remains an important boundary condition.

---

# 21. mDNS Cadence in 2.1.8

The recurring connected mDNS restart remains present.

A modulo-three scheduling gate changes the intended cadence to approximately:

```text
3 × 60 s
=
180 s
```

The roughly three-minute recurring behavior therefore predates firmware 2.2.4.

---

# 22. Post-Association PM Restoration in 2.1.8

Firmware 2.1.8 changes post-association sequencing.

The identified path contains approximately:

```text
association
     |
     v
intermediate PM restoration
     |
     v
bounded delay
     |
     v
normal state 3
```

The delay is approximately:

```text
100 scheduler ticks
```

Its battery impact has not been independently quantified.

---

# 23. WLAN Component Evolution

The investigated progression is:

| Firmware | FMAC | WF200 firmware |
|---|---:|---:|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |
| experimental corrected family | 3.7.0 | 3.18.0 |

This provides useful comparison points.

`2.1.0 -> 2.1.3` changes significant host behavior without changing the investigated FMAC/WF200 generation.

Later transitions change both host and radio components.

Therefore a battery-runtime difference cannot automatically be assigned to either host or radio code.

---

# 24. Firmware 2.1.8 and Historical Drain

Practical drain occurred on firmware 2.1.8.

The later 2.2.4 Beacon Recovery chain has not been identified there in the same form.

Therefore:

```text
2.2.4 Beacon Recovery
```

cannot explain:

```text
all historical Shelly TRV Gen1 battery drain
```

Possible common contributors remain broader:

- host PM lifecycle
- blocker accounting
- WLAN PM behavior
- WF200 behavior
- recurring network work
- radio environment
- cloud activity
- motor workload
- other unidentified mechanisms

---

# 25. Firmware 2.1.8 → 2.2.4

Firmware 2.2.4 expands both diagnostics and PM behavior.

Relevant additions include:

```text
2.1.8
 |
 v
2.2.4
 |
 +-- expanded WF200 statistics
 +-- received-beacon monitoring
 +-- real_beacon_skip
 +-- Beacon Recovery
 +-- expanded PM retry/ownership behavior
 +-- FMAC 3.7.0
 +-- WF200 3.16.1
```

Beacon Recovery became one of the most visible recurring mechanisms in the investigation.

---

# 26. Beacon Statistics in 2.2.4

Firmware 2.2.4 requests WF200 statistics through:

```text
command 0x66
```

The response contains fields including:

```text
received beacon count
missed beacon count
TBTT difference
```

The host derives:

```text
C = current cumulative received count
P = previous baseline

delta = C - P

real_beacon_skip = 600 / delta
```

The result is stored as an 8-bit field and used in Beacon Recovery control.

This chain has not been identified in the same form in the earlier investigated host firmware.

---

# 27. Beacon Recovery

When the cached value qualifies, firmware temporarily changes WLAN PM policy.

Observed sequence:

```text
state 3 / Fast Power Save
     |
     v
Beacon Recovery
     |
     v
state 1 / active WLAN
     |
     v
~5 serviced seconds
     |
     v
restore saved PM state
     |
     v
normally state 3
```

The normal Recovery path does not intentionally perform:

- full WLAN reconnect
- DHCP renewal
- Cloud reconnect
- scan

No explicit transmit-power increase has been identified.

---

# 28. C1a — Signed Interpretation

The estimator result is stored as one byte.

Stock Recovery later interprets that byte as signed.

Example:

```text
delta = 3

600 / 3 = 200

uint8 = 0xC8
int8  = -56
```

and:

```text
delta = 4

600 / 4 = 150

uint8 = 0x96
int8  = -106
```

Because the stock predicate rejects zero but accepts signed values `<= 2`, these negative values unexpectedly qualify.

This is C1a.

---

# 29. C1b — Measurement-Window Validity

The calculation uses:

```text
600 / (C - P)
```

but `P` has no explicit elapsed-time validity attached to it.

If expected measurement opportunities are skipped while the old baseline survives, a later delta can represent a longer logical interval than the fixed numerator assumes.

Correct counters can therefore produce an invalid host-derived estimate.

This is C1b.

---

# 30. C2 — Historical Recovery Evidence

Stock Recovery clears:

```text
P
```

but retains:

```text
R = real_beacon_skip
```

After Recovery:

```text
P = 0
R = historical qualifying value
```

The next successful statistics sample can only establish a new baseline.

No fresh `R` exists.

Stock control flow can nevertheless evaluate the retained historical `R`.

Conceptually:

```text
fresh qualifying R
     |
     v
Recovery
     |
     v
P = 0
R retained
     |
     v
next sample
     |
     v
new P installed
no fresh R
     |
     v
old R evaluated
     |
     v
Recovery can recur
```

---

# 31. C2 Is Metastable

Earlier documentation often used language such as:

```text
self-sustaining loop
```

or implied:

```text
forever until reboot
```

The stronger permanent interpretation is not justified.

The demonstrated behavior is:

```text
metastable stale-evidence recurrence
```

It can persist for long periods and produce approximately minute-spaced Recoveries.

However:

> The firmware can leave the recurrence without reboot.

Therefore historical once-per-minute behavior remains real, but C2 should not be described as mathematically permanent.

---

# 32. Periodic mDNS vs. Beacon Recovery

The chronology separates the mechanisms:

```text
2.1.0
    no comparable recurring connected mDNS restart identified

2.1.3
    ~60 s recurring mDNS restart

2.1.8
    ~180 s recurring mDNS restart

2.2.4
    ~180 s recurring mDNS restart
    +
    Beacon Recovery
```

Historical Patch B suppressed the recurring mDNS restart while retaining stock Recovery.

Recovery continued at approximately:

```text
~58/hour
```

during the `.77` full-discharge experiment.

Therefore the targeted recurring mDNS mechanism is not required for stock Beacon Recovery.

---

# 33. D3 / `PS_MODE_ERROR`

Firmware 2.2.4 handles the WF200:

```text
PS_MODE_ERROR
```

indication.

A dedicated D3 observer retained normal Beacon Recovery while counting these errors.

Historical result:

```text
~63.93 hours
3835 Beacon Recoveries
D3_total = 0
```

Thus the known D3 error channel is not required for recurring host Recovery.

This does not prove the WF200 was always physically asleep correctly or that no other internal condition existed.

---

# 34. C-C

C-C is the corrective version of Beacon Recovery evidence handling.

It retains:

```text
WF200 statistics
real_beacon_skip diagnostic value
fresh valid Recovery
```

while correcting:

```text
C1a
signed control interpretation

C1b
invalid measurement epoch

C2
historical evidence reused as fresh control evidence
```

C-C does not disable Recovery globally.

---

# 35. C-C Hardware Result

Controlled testing established that C-C:

- boots successfully
- preserves WLAN
- preserves Cloud
- preserves thermostat operation
- preserves valve operation
- removes the demonstrated stale-evidence recurrence
- retains fresh valid Recovery

Historical C-C-based periods still showed fresh Recovery.

Representative measurements were around:

```text
27–30 fresh Recoveries/hour
```

in some intervals.

These are experiment-specific observations, not a universal C-C rate.

---

# 36. MIN80

MIN80 was an experimental minimum-skip modification.

It was useful for isolating behavior but is not part of the current corrected platform.

MIN80 is absent from:

```text
B2.1
B2.1_OBS
B2.2
```

Historical MIN80 results retain their original identity.

---

# 37. Patch A

Historical Patch A bypassed the Beacon Recovery action.

It was useful for mechanism isolation.

Because it also suppresses potentially legitimate fresh Recovery, it is not the current corrective design.

---

# 38. Patch B

Patch B suppresses the targeted recurring mDNS restart while leaving stock Beacon Recovery intact.

It does not disable mDNS entirely.

Patch B remains a historical isolation experiment.

---

# 39. Patch A+B

A+B suppresses both targeted recurring mechanisms.

It demonstrated that:

```text
targeted mDNS recurrence
+
targeted Beacon Recovery
```

could both be suppressed while normal WLAN/Cloud/thermostat operation continued during monitored windows.

It was an isolation experiment, not the current architecture.

---

# 40. Historical A1

Later analysis identified PM lifecycle defects separate from Beacon Recovery.

Historical A1 addressed issues including:

```text
G01
G02
G03
G05
G06
G18
G19
```

The correction scope included:

- Final-Sleep cleanup
- wake-failure handling
- timeout versus cancellation
- late completions
- requested versus committed PM state
- old completion races
- independent inhibit ownership
- settlement/handoff

A1 and C-C addressed different defect classes.

---

# 41. Historical A1 Regression

Later qualification discovered that the experimental A1 patch itself introduced a regression.

Five verified native paths use `request1` as a temporary override:

```text
physical button
HTTP /psovrd
Cloud psovrd
SSI settings_sta
OTA launcher
```

Intended:

```text
selected policy = 3
temporary request = 1
use 1 temporarily
restore 3
```

Old A1 could convert the temporary override into persistent state:

```text
3/3
 |
 v
temporary 1
 |
 v
1/1
```

This was an experimental patch defect.

It is not a demonstrated stock Shelly defect.

---

# 42. A1R

A1R supersedes A1.

It preserves the original lifecycle corrections while correcting the verified temporary-return paths.

Qualification:

```text
151 / 151 Thumb behavior tests PASS
```

A1R is part of:

```text
B2.1
B2.1_OBS
B2.2
```

Historical A1 measurements are not relabeled as A1R.

---

# 43. Historical A1 + C-C + WF200 3.18.0 Platform

An important historical integrated build combined:

```text
stock 2.2.4 host
+
A1
+
C-C
+
WF200 3.18.0
```

primarily on `.234`.

It successfully exercised:

- FMAC 3.7.0
- WF200 3.18.0
- WLAN association
- DHCP
- Cloud
- PM transitions
- thermostat operation
- valve movement
- calibration

This remains valid interoperability evidence.

It is not the current corrected platform.

---

# 44. Historical A1 Artifact

Historical artifact:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

Historical GBL:

```text
size:
1,123,380 bytes

SHA-256:
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379

END CRC:
F01262BC

CRC residue:
2144DF1C
```

Historical application:

```text
size:
1,066,544 bytes

SHA-256:
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

These identities are preserved historically.

---

# 45. Historical A1 Runtime

Representative measurements included approximately:

```text
~17.7 min:
9 Recoveries

~7.94 h:
217 Recoveries

~24 h:
660 Recoveries

~32.44 h:
909 Recoveries
```

The longer intervals correspond to approximately:

```text
27–28 fresh Recoveries/hour
```

Because C-C was active, these events were not simply stock C2 stale-evidence repetitions.

---

# 46. Mesh / Band-Steering Historical Test

FRITZ! Mesh/Band Steering was disabled during a historical `.234` interval.

Fresh Recovery continued.

Therefore the tested steering behavior was not required for those fresh Recovery events.

This does not rule out all AP, RF or timing influences.

---

# 47. WF200 3.18.0

The project integrated official Silicon Labs WF200 3.18.0 into the Shelly 2.2.4/FM​AC 3.7.0 environment.

The official SEC payload is:

```text
wfm_wf200_C0.sec
```

Size:

```text
312,400 bytes
```

SHA-256:

```text
886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9
```

The release contains a relevant power-save correction for a failure class where the radio could fail to sleep after a PM-mode transition.

This is technically relevant.

It is not proof of the historical Shelly root cause.

---

# 48. WF200 3.18.0 Integration

The larger SEC required relocation approximately from:

```text
0x4C050
```

to:

```text
0x4C450
```

for:

```text
+0x400
```

The runtime destination remains:

```text
[0x1003D0, 0x1007D8)
```

The final integration uses:

```text
54 relocation fixups
```

The embedded SEC was verified byte-for-byte against the official image.

---

# 49. Host Sleep vs. WLAN Recovery

Two major diagnostic domains must remain separate.

## WLAN / WF200 Recovery

```text
command 0x66
received-beacon statistics
real_beacon_skip
C1a
C1b
C2
Beacon Recovery
WF200 PM behavior
```

## Host MCU Sleep

```text
A1/A1R lifecycle
B2 ownership
B3 / EM2 policy
PA8 WFI veto
Final-Sleep lifecycle
EM1 / EM2 selection
```

They interact, but they are not the same mechanism.

For example:

```text
Beacon Recovery occurred
```

does not prove:

```text
host remained continuously awake
```

and:

```text
B2 != 0
```

does not prove:

```text
Beacon Recovery caused it
```

---

# 50. B2.1

The current observer-free corrected baseline is:

```text
B2.1
```

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

This is the first current baseline that includes both:

```text
A1R
```

and:

```text
qualified B2 correction
```

rather than the historical A1 implementation.

---

# 51. B2.1 Artifact

Artifact:

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

CRC residue:
2144DF1C
```

---

# 52. PM52→cmd66 Observer

The earlier proposed clean-stock Host Observer was superseded.

The current diagnostic design is the:

```text
PM52 -> cmd66 observer
```

It records:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing command-0x66 requests
- command-0x66 results
- fresh estimator operands
- connection epochs
- 12-record history
- first-fault state

It adds no additional WF200 statistics request.

---

# 53. Observer Noninterference Design

The current observer adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
additional WF200 command
```

Readout occurs only through explicit `/status` access.

Software-level noninterference is qualified.

Absolute physical timing noninterference is not claimed.

---

# 54. B2.1_OBS

The active long-term hardware build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

Research identity:

```text
research_build: B2.1_OBS
```

Readout:

```text
pm52_cmd66
```

The native Shelly version remains 2.2.4.

---

# 55. B2.1_OBS Qualification

Qualification includes:

```text
A1R:
151 / 151

observer/readout:
356 / 356

B2:
2060 + 102
plus mixed/preemption tests

MQTT:
258

plus:
C-C qualification
decoder regressions
deterministic construction
independent GBL verification
zero unexplained changes
```

Disposition:

```text
B2.1_OBS RELEASE-CANDIDATE GO
```

This refers to controlled experimental deployment.

It is not a production-release designation.

---

# 56. B2.1_OBS Artifact

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

CRC residue:
2144DF1C
```

---

# 57. Current Hardware Population

The active hardware population is:

| Device | Current build | Role |
|---|---|---|
| `.77` | B2.1_OBS | corrected long-term |
| `.88` | B2.1_OBS | corrected long-term |
| `.11` | B2.1_OBS | corrected long-term |
| `.71` | B2.1_OBS | corrected long-term |
| `.234` | B2.1_OBS | corrected long-term |
| `.61` | B2.1_OBS | corrected long-term |
| `.97` | stock 2.2.4 | stock control |

Therefore the current comparison is:

```text
6 × B2.1_OBS
1 × stock 2.2.4
```

Historical device roles remain valid only for their historical experiment periods.

---

# 58. Early Current Observation

During the initial B2.1_OBS observation period:

```text
B2.1_OBS devices:
beacon_err = 0
```

during the observed early interval.

Stock `.97` retained thousands of accumulated Recovery events and showed periods of roughly minute-scale recurrence.

Another stock interval showed only a small increase.

These observations are preliminary.

They are not battery-lifetime evidence.

---

# 59. Calibration Restore Guard

Later analysis identified another concrete defect.

A queued-success calibration restore can immediately self-requeue instead of settling correctly.

A narrow guard was developed and qualified.

This correction is included in:

```text
B2.2
```

but not in the active B2.1_OBS devices.

---

# 60. P01 — Battery ADC PA3 Cleanup

The battery ADC timeout path can return without the normal PA3 release.

This creates a resource-lifecycle asymmetry.

P01 adds the missing timeout cleanup.

Qualification:

```text
128 + 6 cases
```

P01 is included in B2.2.

Its energy impact has not been measured on hardware.

---

# 61. P02 — I2C Timeout Retirement

An I2C timeout path can return with transaction state incompletely retired.

P02 adds bounded retirement.

Qualification:

```text
90 + 480 cases
```

P02 is included in B2.2.

---

# 62. P03 — WLAN GPIO Interrupt Mask

A WLAN GPIO interrupt-disable path passes decimal:

```text
10
```

to a helper expecting a bitmask.

P03 corrects the argument semantics.

Qualification:

```text
128 native cases
```

P03 is included in B2.2.

---

# 63. Deferred P04 and Other Candidates

P04 concerns motor-timeout movement accounting.

Important resources are retired, but movement accounting may remain stale or partial.

Status:

```text
DEFERRED
```

Other deferred candidates include:

```text
P11 raw ADC transient publication
valve_min_percent mixed-unit issue
raw TXDMA candidates
P05
P06
P07
P08
P10
P12
P13
mDNS modification
EM3 modification
diagnostic 500 us FastPS ideas
```

Suspicion alone is not sufficient for inclusion in a final candidate.

---

# 64. B2.2

B2.2 is the observer-free integrated candidate containing exactly nine selected qualified corrections:

```text
1. A1R including A1 lifecycle correction
2. C-C
3. B2 bounded serialization
4. minimal MQTT PUBLISH guard
5. official WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

Current disposition:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

No physical TRV was contacted for B2.2 qualification.

---

# 65. Meaning of “All Known Qualified Fixes”

For B2.2:

```text
All Known Qualified Fixes
```

does not mean:

```text
all possible firmware defects
```

It means all defects selected for the build that satisfied:

```text
demonstrated
+
safely correctable
+
independently qualified
+
composition-qualified
```

Deferred candidates remain excluded.

---

# 66. B2.2 Artifact

GBL:

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

CRC residue:
2144DF1C
```

Application:

```text
final/SHTRV-01_2.2.4_B2.2_EXPERIMENTAL.bin
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

Native firmware identity remains:

```text
20240619-130912/v2.2.4@ee290818
```

B2.2 therefore requires artifact/hash identification.

---

# 67. B2.2 Qualification

Examples from the qualification suite include:

```text
A1R:
151 / 151

C-C:
512 + 10000

B2:
2060 + 102
plus mixed/preemption

MQTT:
258

Calibration Restore Guard:
68 native
66535 scalar
104 queue
30 countdown
plus negative tests

P01:
128 + 6

P02:
90 + 480

P03:
128 native

motor/B2/P01:
10 + 30

sleep/PA8:
48

battery/OTA/boot:
10002 + 2 + 4 + 3

interfaces:
10 interactions

flows:
13 groups
```

Construction qualification also established:

```text
4 clean application constructions identical
2 GBL builds byte-identical
286 builder rejection tests
282 verifier rejection tests
0 unexplained stock -> B2.2 application changes
0 unexplained B2.1 -> B2.2 changes
0 unexplained container changes
observer absent
```

---

# 68. B2.2 Is Not Hardware-Qualified

The status:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

does not mean:

```text
hardware qualified
```

No B2.2 battery-runtime claim exists.

It is intentionally not being deployed while the B2.1_OBS long-term experiment continues.

---

# 69. Battery Reporting Across Versions

The investigated firmware generations:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

use an approximately:

```text
3000 mV
```

low-voltage shutdown threshold.

The displayed battery percentage is derived from cached voltage.

It is not a coulomb counter.

Therefore percentage-only comparisons between firmware generations are weak.

Voltage, runtime, workload and firmware identity should be considered together.

---

# 70. Low-Voltage Shutdown

Below approximately:

```text
3.000 V
```

the firmware enters its low-battery shutdown path.

The reconstructed sequence includes approximately:

```text
~3 serviced seconds
```

before:

```text
PA0 LOW
```

In 2.2.4, the main task subsequently enters a busy-loop state.

The exact board-level power consequence of PA0 LOW has not been independently verified.

---

# 71. Cross-Version Summary

| Mechanism | 2.1.0 | 2.1.3 | 2.1.8 | 2.2.4 |
|---|---:|---:|---:|---:|
| mDNS responder | yes | yes | yes | yes |
| recurring connected mDNS restart | not identified | yes | yes | yes |
| recurring mDNS cadence | none established | ~60 s observed | ~180 s intended | ~180 s |
| state-5 / `psovrd2` | not identified | yes | yes | yes |
| connected Fast Power Save | yes | yes | yes | yes |
| shared B2/B3 architecture | yes | yes | yes | yes |
| permanent B3 / normal EM2 policy | yes | yes | yes | yes |
| PA8 WLAN sleep gate | equivalent architecture | present | present | detailed |
| PM/Final-Sleep lifecycle complexity | yes | yes | yes | yes |
| unprotected blocker-helper architecture | yes | present | present | yes |
| complete concrete B2 task-race witness | not fully closed | not fully closed | not fully closed | yes |
| post-association PM evolution | early | changed | expanded | expanded further |
| command-`0x66` Recovery chain | not identified | not identified | not identified | yes |
| `real_beacon_skip` Recovery control | not identified | not identified | not identified | yes |
| C1a | n/a | n/a | n/a | yes |
| C1b | n/a | n/a | n/a | yes |
| C2 | n/a | n/a | n/a | yes |
| D3 investigation path | no comparable use | no | no | yes |
| low-voltage threshold ~3000 mV | yes | yes | yes | yes |

`not identified` means that the mechanism was not found in the investigated host firmware.

It does not prove that no conceptually related behavior exists inside the protected WLAN components.

---

# 72. Experimental Configuration Summary

| Configuration | Host basis | Recovery | WF200 | Status / purpose |
|---|---|---|---|---|
| Patch A | 2.2.4 | bypassed | 3.16.1 | historical Recovery isolation |
| Patch B | 2.2.4 | stock | 3.16.1 | historical mDNS isolation |
| A+B | 2.2.4 | bypassed | 3.16.1 | historical dual isolation |
| C-C | 2.2.4 | corrected | 3.16.1 | historical/current correction component |
| MIN80 variants | 2.2.4 | modified | 3.16.1 | historical experiment |
| D3 observer | 2.2.4 | stock | 3.16.1 | historical radio-error observation |
| C-C + WF200 3.18 | 2.2.4 | corrected | 3.18.0 | historical host/radio comparison |
| A1 + C-C + WF200 3.18 | 2.2.4 | corrected | 3.18.0 | historical integrated canary |
| B2.1 | 2.2.4 + A1R/B2/etc. | corrected | 3.18.0 | current observer-free baseline |
| B2.1_OBS | B2.1 + observer | corrected | 3.18.0 | active long-term hardware build |
| B2.2 | observer-free integrated candidate | corrected | 3.18.0 | offline release candidate |

The old clean-stock Host Observer is historical design work and is no longer the current diagnostic architecture.

---

# 73. What the Chronology Establishes

## 73.1 The host-sleep architecture is old

B2/B3, B3/EM2 policy and broad sleep selection predate 2.2.4.

Host sleep problems therefore cannot automatically be classified as 2.2.4 regressions.

## 73.2 EM2 is intended normal deep idle

B3 is consistent with the RTC/LFXO design.

EM3 is not a simple battery fix.

## 73.3 B2 contains a real correctness defect

Task-preemption schedules can create phantom or lost contributions.

The correction is now qualified.

## 73.4 PA8 independently gates WFI

This is legitimate when WLAN work is pending.

## 73.5 mDNS predates the recurring restart

The responder exists before the recurring connected maintenance behavior.

## 73.6 mDNS recurrence changed over time

Approximately:

```text
2.1.0: no comparable recurring restart established
2.1.3: ~60 s
2.1.8: ~180 s
2.2.4: ~180 s
```

## 73.7 State 5 is a WLAN policy override

It is not a three-minute host-awake timer.

## 73.8 2.1.8 changes host and radio behavior

Both sides change simultaneously.

## 73.9 Beacon Recovery is a later 2.2.4 mechanism

The `0x66 -> real_beacon_skip -> Recovery` chain belongs to the investigated 2.2.4 host implementation.

## 73.10 Beacon Recovery contains real host defects

C1a/C1b/C2 are demonstrated.

## 73.11 C2 is metastable

It can create long-lived recurrence but is not proven permanent until reboot.

## 73.12 D3 is not required

Thousands of Recoveries occurred with D3_total remaining zero.

## 73.13 WF200 3.18.0 does not eliminate all fresh Recovery

Host estimator behavior and radio-internal PM behavior are distinct.

## 73.14 Historical A1 was not the final correction

A1 was later superseded by A1R after an experimental regression was found.

## 73.15 B2 correction is no longer hypothetical

Bounded serialization has been implemented and qualified.

## 73.16 B2.1_OBS is the current hardware platform

The clean-stock Host Observer is no longer the active design.

## 73.17 B2.2 exists but remains offline

It is qualified offline and not yet hardware-qualified.

---

# 74. What the Chronology Does Not Establish

The comparison does not establish:

- the exact release where historical degradation first appeared
- that 2.1.0 is drain-free
- that 2.1.3 is drain-free
- that 2.1.8 introduced the historical problem
- that recurring mDNS is the root cause
- that Beacon Recovery is the complete root cause
- that WF200 3.16.1 is the complete root cause
- that WF200 3.18.0 solves the problem
- that every physical TRV experiences the B2 race
- that phantom B2 explains a specific historical discharge
- that PA8 remains abnormally asserted during drain
- exact current consumption of each mechanism
- exact physical WF200 sleep residency
- exact EFM32 EM1/EM2 residency during historical drain
- exact cause of every fresh Recovery
- battery-life improvement attributable to one correction
- B2.2 hardware behavior
- a final production fix

---

# 75. Current Battery-Drain Model

The current evidence supports several interacting layers:

```text
normal TRV workload
     +
motor activity
     +
network / cloud activity
     +
periodic mDNS maintenance
     +
WF200 PM behavior
     +
radio / AP environment
     +
host PM lifecycle
     +
B2 blocker accounting
     +
PA8 WLAN sleep gating
     +
2.2.4 Beacon Recovery
     +
peripheral/resource lifecycle defects
     +
version-specific host/radio behavior
```

Not every mechanism needs to occur on every device.

Several can interact.

---

# 76. Different Failure Chains Must Remain Separate

For example:

```text
WLAN operation
     |
     v
B2 owner activity
     |
     v
B2 race
     |
     v
phantom contribution
     |
     v
EM2 blocked
```

is different from:

```text
beacon statistics
     |
     v
fresh qualifying real_beacon_skip
     |
     v
Beacon Recovery
     |
     v
temporary active WLAN PM state
```

and both differ from:

```text
WF200 notification pending
     |
     v
PA8 HIGH
     |
     v
WFI veto
```

A battery symptom does not identify which chain occurred.

---

# 77. Current Research Phase

The project is no longer in the phase:

```text
build stock Host Observer
-> decide whether to develop B2 fix
```

That plan has been superseded.

The current phase is:

```text
technical RE largely frozen
+
B2.1_OBS long-term hardware observation
+
B2.2 offline candidate frozen
+
documentation / consistency work
```

---

# 78. Current Research Priority

The active decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

This means the project should not currently:

- flash B2.2
- alter C-C
- alter Recovery cadence
- change WF200 firmware
- change AP policy
- replace the observer
- start another broad speculative RE branch

The current experiment needs longitudinal evidence.

---

# 79. If B2.1_OBS Drains

If genuine drain develops:

```text
detect abnormal voltage/runtime trend
        |
        v
preserve first-fault observer state
        |
        v
inspect PM52/cmd66 history
        |
        v
correlate connection epoch
        |
        v
correlate PM completion
        |
        v
resume targeted RE
```

The first fault should be captured before changing firmware or network variables.

---

# 80. If B2.1_OBS Remains Stable

If the corrected population remains stable:

```text
remove observer
        |
        v
requalify observer-free build
        |
        v
hardware regression
        |
        v
evaluate final candidate
```

B2.2 is available as an offline-qualified candidate for that later stage, but it has not yet passed the hardware gate.

---

# 81. Current Conclusion

The firmware history no longer supports a simple model such as:

```text
2.2.4 Beacon Recovery
=
Shelly TRV battery-drain root cause
```

The evidence is more specific.

Firmware 2.2.4 introduced a Beacon Recovery mechanism containing real host-side validity defects:

```text
C1a
C1b
C2
```

C2 can create metastable stale-evidence recurrence after a qualifying measurement.

C-C corrects that behavior while preserving fresh Recovery.

Fresh Recovery continues to exist after C-C and after integration of WF200 3.18.0.

Meanwhile, deeper analysis demonstrated independent host defects:

```text
A1 lifecycle class
B2 reference-counter race
```

and later qualified additional issues:

```text
Calibration Restore Guard defect
P01 battery ADC cleanup
P02 I2C timeout retirement
P03 GPIO interrupt mask
```

Historical A1 was successfully exercised on physical hardware but later found to contain an experimental temporary-policy regression.

A1R supersedes it.

The B2 correction is implemented and qualified.

The current observer-free corrected baseline is:

```text
B2.1
```

The active hardware build is:

```text
B2.1_OBS
```

running on:

```text
6 physical corrected TRVs
```

against:

```text
1 stock 2.2.4 control
```

The later observer-free candidate:

```text
B2.2
```

has reached:

```text
OFFLINE RELEASE-CANDIDATE GO
```

but has not been hardware-qualified.

The current working model is therefore:

```text
historical drain
    !=
one confirmed mechanism

historical drain
    =
possible interaction of common architecture,
version-specific defects,
radio/WLAN behavior,
resource-lifecycle failures,
and potentially multiple independent
sleep-prevention mechanisms
```

The project now has several demonstrated and qualified corrections.

What remains unresolved is which combination materially explains the observed historical battery lifetime.

That question is currently being answered through long-term hardware observation rather than additional speculative firmware changes.

---

# Related Documents

Beacon statistics and baseline handling:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Calculated beacon-skip behavior:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

Periodic mDNS:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Host PM:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Battery reporting:

[`battery-reporting-and-shutdown.md`](battery-reporting-and-shutdown.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

mDNS runtime comparison:

[`../testing/mdns-runtime-comparison.md`](../testing/mdns-runtime-comparison.md)

Patch overview:

[`../patch/README.md`](../patch/README.md)

B2.1_OBS qualification:

[`../qualification/b2.1-obs-qualification.md`](../qualification/b2.1-obs-qualification.md)

B2.2 qualification:

[`../qualification/b2.2-offline-release-candidate.md`](../qualification/b2.2-offline-release-candidate.md)

---

# Research Method

This comparison is based on:

- static reverse engineering of locally obtained firmware
- native ARM Thumb verification
- binary comparison
- runtime testing on personally owned TRVs
- packet captures
- controlled firmware modification
- executable behavior qualification
- deterministic artifact reconstruction
- independent GBL verification

The project deliberately separates:

```text
host behavior
radio behavior
observed runtime behavior
inferred electrical behavior
```

Historical build identities remain unchanged.

Historical A1 results are not relabeled A1R.

Historical B2-era measurements are not relabeled B2.1.

Offline qualification is not presented as hardware qualification.

No original or modified complete Shelly firmware image or large proprietary disassembly is published in this documentation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The documented behavior refers to firmware versions, experimental builds and physical devices investigated in this project.

Experimental firmware is intended only for controlled testing on personally owned hardware.