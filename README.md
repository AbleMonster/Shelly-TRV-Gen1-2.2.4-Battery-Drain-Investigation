# Shelly TRV Gen1 – Battery-Drain Investigation

Reverse engineering, runtime analysis, long-term battery testing, and experimental firmware research for the Shelly TRV Gen1 (`SHTRV-01`).

This project investigates the unusually high battery consumption observed on Shelly TRV Gen1 devices.

The primary reverse-engineering target is:

```text
20240619-130912/v2.2.4@ee290818
```

Older firmware from `2.1.0` through `2.1.8` is used for comparison.

The project does **not** assume that the historical battery-drain problem has a single cause.

Instead, firmware comparison, native ARM analysis, runtime logging, packet capture, controlled firmware modifications, executable qualification and long-term battery tests are used to separate individual mechanisms and determine which ones actually matter.

The investigation has identified several concrete firmware defects, including:

- invalid Beacon Recovery control semantics in 2.2.4
- reuse of stale Beacon Recovery evidence
- invalid beacon-measurement windows
- WLAN power-management lifecycle and settlement defects
- a shared host sleep-blocker reference-counter race
- a regression in the original experimental A1 correction affecting temporary PM overrides
- a calibration restore path capable of immediately re-queuing calibration
- incomplete battery-ADC resource cleanup on timeout
- incomplete I2C display retirement on timeout
- an incorrect WLAN GPIO interrupt-disable mask

Several of these defects now have independently qualified experimental corrections.

The historical battery-drain problem is **not yet considered completely solved**.

---

# Current Status

The project has progressed substantially beyond the original Beacon Recovery and mDNS isolation experiments.

The current evidence supports a multi-layer model rather than a single confirmed root cause.

```text
Historical drain
    |
    +-- exists before 2.2.4
    |
    +-- therefore cannot be explained by one
        2.2.4-only mechanism


2.2.4
    |
    +-- Beacon Recovery
    |     |
    |     +-- C1a signed-value problem
    |     +-- C1b measurement-window problem
    |     +-- C2 stale-evidence recurrence
    |     |
    |     +-- corrected experimentally by C-C
    |
    +-- PM lifecycle / ownership defects
    |     |
    |     +-- originally corrected by A1
    |     +-- A1 temporary-override regression discovered
    |     +-- corrected by A1R
    |
    +-- shared B2 blocker-counter race
    |     |
    |     +-- demonstrated statically
    |     +-- bounded serialization qualified
    |
    +-- additional qualified defects
          |
          +-- calibration restore self-requeue
          +-- battery ADC timeout cleanup
          +-- I2C timeout retirement
          +-- WLAN GPIO interrupt mask


WF200
    |
    +-- stock 2.2.4: 3.16.1
    |
    +-- experimental: 3.18.0
          |
          +-- Silicon Labs sleep-related fix
          +-- interoperable with Shelly FMAC 3.7.0
```

The current hardware-test platform is:

```text
B2.1_OBS
```

It is based on the corrected B2.1 integration and adds passive PM52→cmd66 instrumentation.

The current observer-free next-stage candidate is:

```text
B2.2
```

B2.2 integrates all defects currently considered demonstrated, safely correctable and independently qualified for that build.

B2.2 has passed offline construction and qualification and has the disposition:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

It has **not yet been hardware-qualified** and is **not currently being flashed to the long-term test devices**.

The current priority is long-term observation of B2.1_OBS against a stock 2.2.4 control.

Active root-cause hunting and new firmware experiments are intentionally paused while that dataset develops.

---

# 1. Battery Drain Predates Firmware 2.2.4

Battery-drain behavior has also been observed on firmware older than 2.2.4.

This is important because several mechanisms identified during the investigation are specific to 2.2.4.

Therefore:

> A defect introduced only in firmware 2.2.4 cannot by itself explain the complete historical Shelly TRV Gen1 battery-drain problem.

Firmware chronology is used throughout the project to distinguish:

- shared mechanisms
- later amplifiers
- recovery mechanisms
- version-specific defects
- unrelated recurring workloads

from the underlying historical problem.

---

# 2. Periodic mDNS Restart

The mDNS responder itself already exists in firmware 2.1.0.

Later firmware adds recurring connected maintenance that restarts the mDNS probing sequence.

Runtime packet capture showed approximately:

| Firmware | Periodic mDNS observation |
|---|---|
| 2.1.0 | no comparable periodic burst observed during ~13 min |
| 2.1.3 | ~60 s |
| 2.2.4 | ~180 s |

A typical recurring sequence contains approximately:

```text
probe
probe
probe
announcement
```

Patch B suppresses the targeted periodic restart without globally disabling mDNS.

A long-term Patch-B device continued stock Beacon Recovery at approximately:

```text
58.3 events/hour
```

and ultimately reached:

```text
0 %
3.116 V
~9.23 days uptime
```

with the periodic restart suppressed.

This establishes that the targeted periodic mDNS restart is **not required** for recurring Beacon Recovery and that suppressing it alone did not prevent poor battery endurance on that test device.

Its quantitative energy cost has not been measured.

---

# 3. Beacon Recovery in Firmware 2.2.4

Firmware 2.2.4 contains an additional host-side Beacon Recovery mechanism.

The characteristic runtime message is:

```text
minutes_tick: Beacon skip error! Attempt recovery
```

A typical Recovery sequence approximately performs:

```text
normal connected power save
        |
        v
Beacon Recovery
        |
        v
PM state 1 / active WLAN
        |
        | ~5 serviced seconds
        v
restore connected PM policy
```

Affected stock devices can repeat this sequence approximately once per minute for extended periods.

Good RSSI does not prevent it.

The Recovery mechanism is driven by a host-side value exposed as:

```text
real_beacon_skip
```

Despite its name, this value is **not** a direct readback of the physical beacon-skip state programmed into the WF200.

Recovery is currently treated as:

```text
symptom
+
possible energy amplifier
+
diagnostic window
```

It is not treated as the proven root cause of the historical battery drain.

---

# 4. What `real_beacon_skip` Actually Represents

Firmware 2.2.4 periodically requests WF200 statistics.

The relevant host calculation uses the cumulative received-beacon counter.

For:

```text
P = previous cumulative counter
C = current cumulative counter
```

the host calculates:

```text
delta = C - P
```

followed approximately by:

```text
R = uint8_t(600 / delta)
```

where `R` becomes the cached `real_beacon_skip`.

The same cached value is later used by Beacon Recovery control logic.

Reverse engineering identified three separate validity problems in this chain.

---

# 5. C1a — Signed Control-Value Problem

The calculated quotient is stored as an 8-bit value but later interpreted by the Recovery decision as signed.

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

These negative interpretations can satisfy the stock Recovery comparison.

The resulting stock fresh-trigger set includes:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

This is a control-validity defect in the 2.2.4 host logic.

---

# 6. C1b — Measurement-Window Problem

The host calculation uses the fixed numerator:

```text
600
```

without carrying corresponding elapsed-time information with the previous beacon-counter baseline.

If expected measurement opportunities are skipped while the old baseline survives:

```text
baseline P
    |
    v
measurement skipped
    |
    v
P survives
    |
    v
later C
    |
    v
600 / (C - P)
```

the resulting `delta` can represent a longer interval than the formula assumes.

The value can therefore become invalid as control evidence even though the underlying cumulative beacon counter itself is valid.

---

# 7. C2 — Stale-Evidence Recovery Recurrence

The most important recurring-Recovery defect occurs after a qualifying event.

Two values are relevant:

```text
P = previous beacon-counter baseline
R = cached real_beacon_skip
```

Stock Recovery clears:

```text
P
```

but retains:

```text
R
```

The next successful statistics sample sees:

```text
P = 0
```

and therefore establishes a new baseline without calculating a fresh `R`.

Stock control flow can nevertheless evaluate the old cached `R` again.

The resulting sequence is:

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
next sample establishes new P
        |
        v
no fresh R calculated
        |
        v
old R evaluated again
        |
        v
Recovery
        |
        v
repeat
```

A new beacon anomaly is therefore not required for every subsequent Recovery.

This explains how one qualifying result can become an approximately minute-spaced Recovery loop.

Later stock runtime observations also showed that this state is **metastable rather than necessarily permanent**.

A stock device was observed repeatedly recovering at approximately minute cadence and later leaving that state without a reboot or reconnect.

The most likely control-flow explanation is that a later fresh valid statistics window replaced the problematic cached evidence.

The exact transition was not captured because the relevant earlier debug lines had already left the runtime log buffer.

C2 should therefore not be interpreted as:

```text
once triggered -> Recovery forever until reboot
```

but rather as a mechanism capable of extending a transient qualifying event into a much longer recurring-Recovery episode.

---

# 8. Patch C-C

C-C corrects the identified Beacon Recovery validity problems while retaining Recovery for fresh valid qualifying evidence.

It addresses:

```text
C1a
C1b
C2
```

Unlike the earlier Patch A, C-C does **not** simply disable Beacon Recovery.

Conceptually:

```text
fresh + valid + qualifying measurement
        |
        +---- yes -> Recovery
        |
        +---- no  -> continue normally
```

C-C has been tested on physical hardware.

Testing confirms that:

- normal WLAN remains operational
- cloud connectivity remains operational
- thermostat and valve operation remain available
- beacon statistics continue operating
- the known stale-evidence recurrence is removed
- fresh qualifying Recovery can still occur

Earlier C-C-based configurations showed fresh Recovery rates around:

```text
~27–30 events/hour
```

during parts of runtime testing.

This demonstrated that C-C corrected a real defect but did not by itself eliminate every fresh Recovery trigger or the observed battery-drain problem.

---

# 9. WF200 `PS_MODE_ERROR` Is Not Required

A separate D3 observer was built to monitor the known WF200:

```text
PS_MODE_ERROR
```

indication.

A long-term observer run recorded thousands of host Beacon Recovery events while:

```text
D3_total = 0
```

This does not prove that the radio was always physically sleeping correctly.

It does establish that this known WF200 error indication is not required for the observed host Recovery behavior.

The host's `"Beacon skip error!"` terminology must therefore not be assumed to correspond directly to WF200 `PS_MODE_ERROR`.

---

# 10. Host Power-Management Defects

The investigation later expanded beyond Beacon Recovery.

Reverse engineering of the host WLAN power-management lifecycle identified several additional correctness problems involving:

- Final-Sleep failure cleanup
- Wake failure handling
- timeout versus cancellation
- late completions
- requested versus committed PM state
- old PM completion races
- independent inhibit ownership
- PM settlement and handoff

These problems affect the relationship between host software state, lower-level WLAN operations and host sleep restrictions.

They are separate from C1a/C1b/C2.

---

# 11. A1 and the A1R Correction

A1 was the first integrated experimental correction for the qualified PM lifecycle and ownership defects.

It addressed the project defect classes:

```text
G01
G02
G03
G05
G06
G18
G19
```

A1 did not blindly clear sleep blockers.

Instead, it attempted to preserve the reconstructed ownership and settlement model while correcting identified failure paths.

Subsequent reverse engineering identified a regression introduced by A1 itself.

Five native callers use PM state 1 as a **temporary override**, rather than as a persistent new policy:

```text
physical button
HTTP /psovrd
Cloud psovrd
SSI settings_sta
OTA launcher
```

Stock firmware preserves the preceding selected/deferred PM policy for these temporary overrides and restores it when the override expires.

The original A1 implementation could instead publish state 1 as the persistent selected policy.

For example:

```text
previous selected policy: 3

temporary request: 1

expected:
temporary 1 -> restore 3

old A1:
temporary 1 -> selected policy becomes 1
```

This was an **experimental A1 regression**.

It is not evidence that the same defect exists in stock Shelly firmware and is not evidence that it caused the historical battery drain.

The corrected implementation is named:

```text
A1R
```

A1R preserves the original A1 lifecycle corrections while recognizing only the five verified temporary-override return origins.

The normal persistent request-1 path remains persistent.

Recovery behavior remains separately handled.

A1R passed the relevant executable and composition qualification and replaced A1 in the current experimental baseline.

---

# 12. WF200 3.18.0

Stock firmware 2.2.4 uses:

```text
Shelly FMAC:
3.7.0

WF200 firmware:
3.16.1
```

Silicon Labs later released:

```text
WF200 3.18.0
```

The corresponding changelog contains a relevant sleep-related fix described as:

```text
device not sleeping after power-save mode change
```

The official SEC image tested by this project has:

```text
Size:
312,400 bytes

SHA-256:
886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9
```

The newer radio firmware was integrated experimentally without replacing Shelly's FMAC 3.7.0 host driver.

Physical testing confirmed successful:

```text
WF200 initialization
scan
association
DHCP
cloud connectivity
power-save operation
normal TRV operation
```

This establishes practical interoperability under the tested conditions.

It does **not** establish that WF200 3.18.0 alone fixes the historical battery-drain problem.

---

# 13. Historical A1 + C-C + WF200 3.18.0 Platform

An important earlier integrated experimental platform combined:

```text
A1
    host PM lifecycle / ownership correction

C-C
    Beacon Recovery validity correction

WF200 3.18.0
    newer Silicon Labs radio firmware
```

The controlled-test artifact was:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

GBL:

```text
SHA-256:
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379
```

Application:

```text
SHA-256:
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The artifact successfully installed through OTA and operated on physical hardware.

It successfully initialized:

```text
FMAC 3.7.0
+
WF200 3.18.0
```

and continued normal WLAN, cloud, thermostat and valve operation.

This platform is now historical.

It was superseded after discovery of the A1 temporary-override regression and development of A1R.

Historical measurements produced by this build remain valid observations and are not retroactively relabeled as B2.1.

---

# 14. Fresh Recovery and the Remaining Causal Question

Earlier A1/C-C/WF200 and C-C-based devices continued to show fresh qualifying Beacon Recovery events after the known stale-evidence recurrence had been removed.

This established an important distinction:

```text
C2 recurrence
!=
fresh qualifying Recovery
```

The remaining question became:

> Why does the host sometimes obtain a fresh measurement that qualifies for Recovery, and under what conditions does that correlate with actual excessive power consumption?

Current evidence does not justify treating every fresh Recovery as a battery-drain event.

The working model is that network/WLAN conditions may produce a transient abnormal estimator state, after which stock control defects and PM interactions can amplify the event.

That model remains a hypothesis rather than a fully demonstrated causal chain.

---

# 15. EFM32GG11 Host Sleep

The Shelly TRV Gen1 host MCU is an:

```text
EFM32GG11
```

A focused host-sleep audit reconstructed the native idle selection.

The relevant policy is approximately:

```text
B2 != 0
    -> maximum EM1

B2 == 0 && B3 != 0
    -> EM2

B2 == 0 && B3 == 0
    -> EM3
```

A permanent B3 contribution is installed during normal startup.

This means the intended deepest normal idle state is:

```text
EM2
```

not EM3.

---

# 16. Why EM3 Is Not the Fix

The permanent B3 contribution initially looked suspicious because it prevents normal idle from reaching EM3.

Further analysis showed that this behavior has a real technical reason.

The stock TRV configures its RTC/tickless scheduler timebase from the:

```text
LFXO
```

The EM3 path disables the relevant low-frequency clocking assumptions while EM2 retains the required timebase.

Simply clearing B3 and allowing EM3 would therefore break assumptions of the current scheduler/tickless implementation.

The project does **not** consider the permanent B3 contribution a demonstrated battery-drain bug.

The intended target is correct EM2 entry.

---

# 17. Shared B2 Reference-Counter Defect

The host uses B2 as a shared reference counter for software components that require EM1.

For example:

```text
B2 = 0
    no owner requires EM1

B2 = 1
    one owner requires EM1

B2 = 2
    two simultaneous owners require EM1
```

This is intentional.

The defect is that not all B2 read-modify-write operations are serialized.

Some task-side paths can be preempted between the load and store while other B2/O operations use a protected critical section.

This creates a real lost-update race.

The defect has been demonstrated statically and through executable qualification.

A bounded serialization correction is now part of B2.1 and B2.2.

---

# 18. Phantom B2 Contribution

One verified schedule can produce:

```text
B2 = 1

Task A:
    load B2 = 1

        ↓ preemption

Task B:
    protected release
    B2 1 -> 0

        ↓ resume

Task A:
    store stale 1 + 1
    B2 = 2
```

Only one real owner remains.

When that owner later releases:

```text
B2 2 -> 1
```

the host is left with:

```text
B2 = 1
```

and no legitimate owner.

The normal sleep selector then limits idle to:

```text
EM1
```

instead of:

```text
EM2
```

A phantom B2 contribution could therefore create persistent excess host power until another event repairs the count or the device resets.

The implementation defect is demonstrated.

Its real-world occurrence rate and quantitative battery impact have not been established.

---

# 19. Lost B2 Contribution

The opposite race is also possible.

Two real owners can be active while the shared counter contains only:

```text
B2 = 1
```

instead of:

```text
B2 = 2
```

When one owner releases, B2 can reach zero while the other owner is still active.

The host may then permit EM2 even though one subsystem still requires EM1.

The defect therefore affects correctness in both directions.

The B2.1/B2.2 correction serializes the relevant counter check/read-modify-write operations while preserving the existing ownership semantics and caller behavior.

---

# 20. PA8 WLAN Sleep Gate

Host sleep contains another mechanism independent of B2.

PA8 belongs to the WLAN host-notification path.

Immediately before low-power entry, the host checks PA8.

If PA8 is HIGH:

```text
WFI is vetoed
```

Conceptually:

```text
sleep selected
     |
     v
PA8?
     |
     +-- LOW  -> WFI
     |
     +-- HIGH -> return without WFI
```

This is not automatically a bug.

The mechanism appears intended to prevent host sleep while the WLAN interface has pending work.

A persistent or high-duty PA8 condition could nevertheless prevent actual low-power entry.

No evidence currently establishes PA8 itself as defective.

---

# 21. PM52→cmd66 Observer

The later diagnostic strategy focused directly on the relationship between host PM requests and the WF200 statistics used by Beacon Recovery.

A passive PM52→cmd66 observer was developed.

It records, without generating additional WF200 requests:

- actual PM52 request payloads
- native PM52 results
- A1R completion decisions
- existing periodic cmd66 issue/results
- fresh estimator operands
- connection epochs
- recent relevant events

The observer uses a bounded in-memory ring and freezes the first relevant full-width fault state.

It does **not** add:

- a new WF200 command
- a new timer
- a new task
- a new queue
- automatic network traffic
- flash writes
- PM policy changes

Readout occurs only through an explicit `/status` request.

The observer is diagnostic instrumentation.

Although it was designed and qualified for noninterference, any added instrumentation can theoretically perturb timing.

Observer results are therefore interpreted with that limitation in mind.

---

# 22. B2.1 and B2.1_OBS

The corrected observer-free integrated baseline is:

```text
B2.1
```

B2.1 contains:

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
```

The observer-enabled long-term-test build is:

```text
B2.1_OBS
```

It adds the PM52→cmd66 observer and an explicit research-build identity while retaining native Shelly version identity:

```text
2.2.4
```

The research identity is exposed separately as:

```text
research_build: B2.1_OBS
```

B2.1_OBS passed integration and noninterference qualification before controlled hardware deployment.

The qualified GBL has:

```text
SHA-256:
7d7063d81372063dfe0d629d26e614f7dd2ed448b0e65a393e866c79025eac7a
```

The reconstructed application has:

```text
SHA-256:
65e17c4c04bdde23f545ebdb3283d71eef746e8dafba97ed9f6e451b6310c215
```

B2.1_OBS is currently the primary long-term hardware-test platform.

---

# 23. B2.2 — All Known Qualified Fixes

While the B2.1_OBS long-term experiment continues unchanged, offline analysis has qualified additional independent firmware defects.

These corrections were composed into:

```text
B2.2
```

B2.2 is intentionally observer-free.

Its exact correction set is:

```text
1. A1R including the A1 PM lifecycle correction set
2. C-C
3. B2 serialization
4. minimal MQTT PUBLISH guard
5. official WF200 3.18.0
6. Calibration Restore Guard
7. P01 battery ADC PA3 release
8. P02 I2C timeout retirement
9. P03 WLAN GPIO interrupt-mask correction
```

There is no tenth correction implicitly included in the name.

B2.2 therefore means:

```text
All Known Qualified Fixes
```

not:

```text
every suspicious code path found during research
```

Known findings that remain deferred include, among others:

- P04 motor completion timeout/accounting behavior
- P11 raw ADC transient publication
- calibration `valve_min_percent` mixed-unit issue
- other unqualified or lower-priority candidates
- EM3 redesign
- diagnostic timing modifications

The final B2.2 GBL has:

```text
SHA-256:
912983973a5467241397b9dd967ee0039440c7d77780a2a97ee494b1a507860c
```

The reconstructed application has:

```text
SHA-256:
7ee593265c76abd8cd628a81133d4b1310c1ae24c9ebe2ca3f2c2948acfc64f9
```

The final offline disposition is:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

This means the build passed its defined offline qualification.

It does **not** mean:

```text
battery drain solved
```

and it does **not** mean:

```text
hardware qualified
```

B2.2 is intentionally not being flashed during the current B2.1_OBS long-term experiment.

---

# 24. Firmware Versions Investigated

| Firmware | Build | Role |
|---|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` | older reference |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` | early comparison |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` | later comparison |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` | primary RE target |

Relevant WLAN component evolution:

| Host firmware | FMAC | WF200 |
|---|---:|---:|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |
| experimental 2.2.4 | 3.7.0 | 3.18.0 |

The exact firmware release in which the historical battery-runtime degradation first appeared remains unknown.

---

# 25. Current Device Roles

The physical test devices are reused as the investigation progresses.

The firmware configuration at the time of a dataset is therefore more important than the device suffix itself.

The current long-term experiment uses:

| Device | Configuration | Role |
|---|---|---|
| `.77` | B2.1_OBS | long-term experimental |
| `.88` | B2.1_OBS | long-term experimental |
| `.11` | B2.1_OBS | long-term experimental |
| `.71` | B2.1_OBS | long-term experimental |
| `.234` | B2.1_OBS | long-term experimental / charged reference |
| `.61` | B2.1_OBS | long-term experimental |
| `.97` | stock 2.2.4 | stock control |

Historical device identities and firmware roles are retained in the corresponding datasets and test documentation.

Datasets crossing a firmware transition must be split at that transition.

The stock `.97` control is intentionally left unmodified during the current experiment.

---

# 26. Long-Term Battery Testing

A dedicated logger collects runtime data from multiple physical TRVs.

The normal logging interval is approximately:

```text
30 minutes
```

Collected fields include, where available:

- firmware version
- battery percentage
- battery voltage
- uptime
- reboot counter
- reconnect counter
- RSSI
- desired beacon skip
- real beacon skip
- Beacon Recovery counter
- beacon receive statistics
- missed beacon statistics
- multicast activity
- transmit failures
- sleep-related statistics
- valve/motor state

Daily reports are generated for longer-term comparison.

Battery voltage is generally more useful than reported percentage for short-term trend comparison.

Reverse engineering of the stock battery reporting path showed that the displayed percentage is derived from the measured battery voltage using a stateless integer mapping.

It is not a coulomb counter or direct measurement of remaining energy.

Therefore:

```text
battery %
```

should not be treated as an independent high-resolution energy measurement.

Neither percentage nor voltage is equivalent to direct current or energy measurement.

Valve movement must also be considered because it represents significant real mechanical work.

---

# 27. Important `sleep_ratio` Limitation

Firmware 2.2.4 exposes:

```text
sleep_ratio
```

through `/stats`.

Reverse engineering of the corresponding calculation shows that this value represents tickless timing/compensation behavior.

It is **not** a direct measurement of:

```text
physical EFM32GG11 sleep residency
```

and it is not a direct measurement of:

```text
WF200 sleep residency
```

It must therefore not be interpreted as:

```text
percentage of time physically asleep
```

Observer data and host control-flow reconstruction provide more direct information about low-power decisions, but direct electrical measurement would still be required to establish actual energy consumption.

---

# 28. Current Battery-Drain Model

The available evidence supports a multi-mechanism model.

A current working hypothesis is:

```text
network / WLAN transient
        |
        v
abnormal fresh beacon estimator
        |
        v
Beacon Recovery
        |
        +-- stock C2 stale-evidence recurrence
        |
        +-- additional PM transitions
        |
        v
host / WF200 PM interaction
        |
        +-- host PM lifecycle defects
        |
        +-- B2 blocker-accounting race
        |
        +-- PA8 sleep veto behavior
        |
        +-- WF200 power-save behavior
        |
        v
possible excessive awake/current residency
        |
        v
battery drain
```

This is a **working causal model**, not a proven complete causal chain.

Potentially relevant layers include:

```text
normal thermostat / valve workload
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
        +-- AP / RF / network environment
```

Several of these contain demonstrated firmware defects.

That still does not establish their quantitative energy contribution.

A code defect can exist without being the dominant battery consumer.

Likewise, a high-frequency workload can consume energy without being the original root cause.

The project therefore distinguishes:

```text
defect
!=
trigger
!=
amplifier
!=
root cause
!=
measured energy contribution
```

---

# 29. What Has Been Established

The investigation currently supports the following technical conclusions:

- battery-drain behavior predates firmware 2.2.4
- periodic connected mDNS activity is a real recurring workload in later firmware
- Patch B suppresses the targeted periodic restart
- periodic mDNS is not required for recurring Beacon Recovery
- 2.2.4 contains a real Beacon Recovery mechanism
- good RSSI does not prevent observed recurring Recovery behavior
- `real_beacon_skip` is a host-derived estimator, not direct physical beacon-skip state
- C1a changes valid positive estimator values through signed interpretation
- C1b allows a counter delta to represent a longer window than the fixed formula assumes
- C2 can reuse historical Recovery evidence without a fresh calculation
- C2 can create long recurring Recovery episodes
- the C2 state is metastable and can later clear without reboot
- C-C corrects the identified estimator/control-validity problems while retaining fresh Recovery
- fresh Recovery can still occur after C-C
- known D3 `PS_MODE_ERROR` is not required for host Beacon Recovery
- multiple host PM lifecycle/ownership defects exist
- the original experimental A1 implementation introduced a temporary-override regression
- A1R corrects that experimental regression while preserving the intended A1 correction set
- FMAC 3.7.0 can operate with the tested WF200 3.18.0 integration
- the permanent B3 contribution has a valid RTC/tickless reason
- intended normal deepest host idle is EM2
- shared B2 blocker accounting contains a real task-preemption race
- the B2 race can produce either phantom or lost ownership
- bounded B2 serialization has been independently qualified
- PA8 can independently veto WFI
- the calibration restore path contained a qualified self-requeue defect
- the battery ADC timeout path contains a qualified cleanup defect
- the display I2C timeout path contains a qualified retirement defect
- the WLAN GPIO interrupt-disable path contains a qualified mask defect
- B2.1_OBS passed its defined qualification and is running on physical test devices
- B2.2 composes the currently qualified correction set without observer instrumentation
- B2.2 passed its defined offline qualification
- B2.2 has not yet been hardware-qualified

---

# 30. What Has Not Been Established

The project does **not** currently claim:

- that one single mechanism explains all historical battery drain
- that Beacon Recovery is the sole cause
- that periodic mDNS is the sole cause
- that WF200 3.18.0 alone fixes the problem
- that C-C alone fixes the problem
- that A1R alone fixes the problem
- that B2 corruption is the historical root cause
- that every fresh Beacon Recovery event is erroneous
- that PA8 is defective
- that EM3 should be enabled
- that `/stats sleep_ratio` represents physical sleep residency
- that the exact energy contribution of each mechanism is known
- that B2.1_OBS has already proven restoration of normal battery lifetime
- that B2.2 has been hardware-qualified
- that B2.2 is a final production fix
- that a specific final battery lifetime has been restored

The project currently has no direct electrical current measurements.

---

# 31. Current Research Direction

The current research phase is intentionally conservative.

B2.1_OBS has completed its pre-deployment qualification and is now undergoing long-term hardware observation.

The current strategy is:

```text
B2.1_OBS long-term test
        |
        +-- six experimental devices
        |
        +-- one stock 2.2.4 control
        |
        v
observe battery voltage / runtime / PM behavior
        |
        +-- no significant drain
        |       |
        |       v
        |   remove observer
        |       |
        |       v
        |   observer-free regression test
        |       |
        |       v
        |   evaluate final candidate
        |
        +-- drain persists
                |
                v
        preserve first-fault evidence
                |
                v
        resume deeper root-cause analysis
```

During this phase:

- no new network variables are intentionally introduced
- no new firmware is flashed merely to test additional hypotheses
- occasional Beacon Recovery alone is not treated as sufficient reason to restart root-cause analysis
- the stock control remains stock
- B2.1_OBS devices remain on B2.1_OBS
- B2.2 remains offline
- static/offline analysis may continue without disturbing the experiment

If a B2.1_OBS device develops significant drain, the priority is to preserve:

```text
/status
/stats
/debug/log
observer state
```

before rebooting, reflashing or changing network conditions.

The goal is to capture the first useful fault state rather than accidentally repair it before collecting evidence.

---

# 32. Repository Structure

Public documentation is organized under:

```text
docs/
├── patch/
├── reverse-engineering/
└── testing/
```

Important documents include:

### Firmware patches

[`docs/patch/README.md`](docs/patch/README.md)

### Firmware chronology

[`docs/reverse-engineering/firmware-comparison.md`](docs/reverse-engineering/firmware-comparison.md)

### Beacon counter

[`docs/reverse-engineering/beacon-rx-counter.md`](docs/reverse-engineering/beacon-rx-counter.md)

### `real_beacon_skip`

[`docs/reverse-engineering/real-beacon-skip.md`](docs/reverse-engineering/real-beacon-skip.md)

### Beacon Recovery

[`docs/reverse-engineering/recovery-mechanism.md`](docs/reverse-engineering/recovery-mechanism.md)

### Host power management and sleep

[`docs/reverse-engineering/power-management-and-sleep.md`](docs/reverse-engineering/power-management-and-sleep.md)

### Host sleep and blocker accounting

[`docs/reverse-engineering/host-sleep-and-blocker-accounting.md`](docs/reverse-engineering/host-sleep-and-blocker-accounting.md)

### PM lifecycle and A1/A1R

[`docs/reverse-engineering/pm-lifecycle-and-a1.md`](docs/reverse-engineering/pm-lifecycle-and-a1.md)

### WF200 firmware

[`docs/reverse-engineering/wf200-firmware.md`](docs/reverse-engineering/wf200-firmware.md)

### AP selection and roaming

[`docs/reverse-engineering/ap-selection-and-roaming.md`](docs/reverse-engineering/ap-selection-and-roaming.md)

### Periodic mDNS

[`docs/reverse-engineering/mdns-periodic-restart.md`](docs/reverse-engineering/mdns-periodic-restart.md)

### mDNS runtime comparison

[`docs/testing/mdns-runtime-comparison.md`](docs/testing/mdns-runtime-comparison.md)

### Battery testing

[`docs/testing/battery-testing.md`](docs/testing/battery-testing.md)

### Experimental device matrix

[`docs/testing/experimental-device-matrix.md`](docs/testing/experimental-device-matrix.md)

---

# 33. Firmware Patching

Experimental firmware is generated locally from verified stock firmware.

The public project does **not** distribute original or modified Shelly firmware binaries.

Patch/construction tooling uses fail-closed validation and should verify, as appropriate:

- exact supported source firmware
- source hashes
- source size
- expected native bytes
- hook addresses
- container geometry
- radio payload identity
- relocation assumptions
- output CRCs
- reconstructed application
- deterministic output
- absence of unexplained changes

A failed precondition should stop the build.

Patch tooling should never silently adapt offsets to an unknown firmware image.

Composition is also treated as a separate qualification problem.

Two individually correct patches are not automatically assumed to remain correct when combined.

Final integrated builds are therefore re-qualified against the composed binary.

---

# 34. Firmware Patcher Repository

A separate patcher repository is available for the public locally applied patch workflow:

```text
https://github.com/AbleMonster/Shelly-TRV-Gen1-2.2.4-patcher
```

The patcher requires the user to provide their own legitimately obtained supported firmware.

No Shelly firmware is distributed by the project.

The research repository may also contain construction and verification scripts used during development of newer experimental patches.

A research script being public does not mean the corresponding experimental firmware has completed hardware qualification.

Likewise:

```text
offline qualification
!=
hardware qualification
```

Always check the documented status of the specific variant.

---

# 35. OTA Testing

Experimental GBL images have been installed on controlled devices through the normal Gen1 OTA mechanism.

For the local test environment, the HTTP server must be reachable on:

```text
TCP port 80
```

Port 8000 caused OTA retrieval problems in the tested setup.

On macOS, binding a Python HTTP server to port 80 normally requires elevated privileges.

OTA acceptance is not equivalent to firmware qualification.

A build must still pass its relevant:

- static checks
- binary checks
- executable behavior tests
- container checks
- integration checks
- runtime checks
- long-term tests

as applicable to the purpose of that build.

---

# 36. Repository Scope

This repository is intended to contain:

- reviewed reverse-engineering results
- technical documentation
- experimental methodology
- patch descriptions
- independently developed tooling
- construction scripts
- validation tools
- sanitized runtime results
- battery-test methodology
- reproducible findings

It is not intended to redistribute proprietary firmware.

The repository should not contain:

- original Shelly firmware images
- complete modified Shelly firmware images
- proprietary extracted application images
- large raw proprietary disassembly dumps
- credentials
- private network identifiers
- sensitive device information
- private security-research material intended for coordinated disclosure

General principle:

> Publish the analysis, construction method and verification evidence — not Shelly's firmware.

---

# 37. Research Method

The investigation combines:

- native ARM Thumb reverse engineering
- EFM32GG11 host analysis
- cross-version firmware comparison
- control-flow reconstruction
- WF200 host-interface analysis
- executable offline verification
- binary reconstruction
- deterministic patch construction
- GBL parsing
- relocation verification
- runtime debug logging
- passive packet capture
- controlled OTA testing
- isolated firmware variants
- long-term battery logging
- negative testing
- composition testing
- independent verification of critical patch behavior

Decompiler output is used as supporting information.

Important control-flow conclusions are checked against native instructions and, where practical, executable behavior.

Diagnostic firmware and production-oriented corrections are deliberately separated.

A diagnostic timing modification that helps expose a mechanism is not automatically suitable for a final correction.

---

# 38. Research Principle

The project deliberately separates:

```text
observation
    |
    v
reverse engineering
    |
    v
hypothesis
    |
    v
attempted falsification
    |
    v
controlled modification
    |
    v
static / executable qualification
    |
    v
integration qualification
    |
    v
runtime validation
    |
    v
long-term observation
```

A plausible firmware mechanism is not treated as a battery-drain cause merely because it exists.

Likewise:

```text
Patch changes the intended behavior correctly
```

does not automatically mean:

```text
Battery drain solved
```

and:

```text
Offline release-candidate GO
```

does not automatically mean:

```text
Hardware-qualified final firmware
```

The objective is to understand why a mechanism exists, determine whether its control logic is valid, preserve legitimate functionality and correct only behavior that the available evidence demonstrates is defective.

For a final correction, the project distinguishes:

```text
original defect
violated invariant
correction
noninterference / regression qualification
hardware validation
```

These stages should not be collapsed into a single claim.

---

# 39. Contributing

Contributions are welcome when they:

- improve reproducibility
- challenge an existing interpretation
- provide independent runtime evidence
- identify missed control flow
- reproduce a firmware defect
- improve patch verification
- provide alternative technical explanations
- independently test the qualified correction set

Please read:

[`CONTRIBUTING.md`](CONTRIBUTING.md)

before submitting an issue or pull request.

Contradicting an existing conclusion is welcome when supported by reproducible evidence.

---

# 40. Security

Security-sensitive findings should not be disclosed through a public issue.

See:

[`SECURITY.md`](SECURITY.md)

for the project's reporting policy.

Security findings are deliberately separated from the battery-drain investigation when public disclosure could create unnecessary risk.

This repository is an independent research project and is not an official Shelly security or support channel.

---

# 41. Safety and Experimental Nature

All modified firmware in this project is experimental.

Experimental firmware can potentially:

- make a device unreachable
- cause unexpected WLAN behavior
- affect battery life
- affect thermostat operation
- affect valve operation
- cause unexpected power-management behavior
- require recovery or reflashing

Do not deploy experimental firmware where failure could create an unsafe condition.

Always retain a known-good recovery path.

Testing should only be performed on devices and networks you own or are authorized to use.

B2.1_OBS and B2.2 should not be interpreted as production firmware merely because they passed their respective research qualification gates.

---

# 42. License

Original code, scripts, tooling, documentation and other copyrightable material created specifically for this project are licensed under:

```text
GPL-3.0-only
```

unless otherwise stated.

See:

[`LICENSE`](LICENSE)

for the full license terms.

---

## Third-Party Firmware and Intellectual Property

The project license applies only to material for which the contributors hold the necessary rights.

Shelly firmware, Silicon Labs firmware, firmware components, trademarks, product names and other third-party intellectual property remain the property of their respective owners.

This repository does not distribute original or modified Shelly firmware images.

Reverse-engineering documentation, independently developed tools, patch descriptions, offsets and small technical excerpts are provided for research, interoperability, debugging and reproducibility.

Users are responsible for obtaining required firmware from legitimate sources and complying with applicable licenses and laws.

---

# 43. Project Independence

This is an independent community research project.

It is not affiliated with, sponsored by, or endorsed by Shelly Group or Silicon Labs.

Product names and trademarks are used only to identify the devices and firmware being studied.