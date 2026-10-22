# Shelly TRV Gen1 – Battery-Drain Investigation

Reverse engineering, runtime analysis, long-term battery testing, and experimental firmware research for the Shelly TRV Gen1 (`SHTRV-01`).

This project investigates the unusually high battery consumption observed on Shelly TRV Gen1 devices.

The primary reverse-engineering target is:

```text
20240619-130912/v2.2.4@ee290818
```

Older firmware from `2.1.0` through `2.1.8` is used for comparison.

The project does **not** assume that the historical battery-drain problem has a single cause.

Instead, firmware comparison, native ARM analysis, runtime logging, packet capture, controlled firmware modifications and long-term battery tests are used to separate individual mechanisms and determine which ones actually matter.

The investigation has now identified several concrete firmware defects, including:

- invalid Beacon Recovery control semantics in 2.2.4
- reuse of stale Beacon Recovery evidence
- invalid beacon-measurement windows
- WLAN power-management lifecycle and settlement defects
- a shared host sleep-blocker reference-counter race

Several of these defects have experimental corrections.

The historical battery-drain problem is **not yet considered completely solved**.

---

# Current Status

The project has progressed beyond the original Beacon Recovery and mDNS isolation experiments.

The current picture is:

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
    |     +-- C2 stale-evidence loop
    |     |
    |     +-- corrected experimentally by C-C
    |
    +-- PM lifecycle / ownership defects
    |     |
    |     +-- corrected experimentally by A1
    |
    +-- shared B2 blocker-counter race
    |     |
    |     +-- demonstrated statically
    |     +-- physical occurrence under investigation
    |
    +-- PA8 WLAN sleep gate
          |
          +-- intentional mechanism
          +-- runtime duty under investigation


WF200
    |
    +-- stock 2.2.4: 3.16.1
    |
    +-- experimental: 3.18.0
          |
          +-- Silicon Labs sleep-related fix
          +-- successfully tested with Shelly FMAC 3.7.0
```

The current integrated experimental platform is:

```text
A1
+
C-C
+
WF200 3.18.0
```

It has passed static qualification and successfully booted and operated on physical TRV hardware.

A separate **Stock Host Observer** is currently being qualified to observe the B2 reference-counter race, actual EM1/EM2 entry and PA8 sleep vetoes without correcting the stock behavior.

---

# Main Findings

## 1. Battery Drain Predates Firmware 2.2.4

Battery-drain behavior has also been observed on firmware older than 2.2.4.

This is important because several mechanisms identified during the investigation are specific to 2.2.4.

Therefore:

> A defect introduced only in firmware 2.2.4 cannot by itself explain the complete historical Shelly TRV Gen1 battery-drain problem.

Firmware chronology is used throughout the project to distinguish:

- shared mechanisms
- later amplifiers
- recovery mechanisms
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

# 7. C2 — Self-Sustaining Recovery

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

This explains how one qualifying result can become an approximately minute-spaced self-sustaining Recovery loop.

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

C-C has now been tested on physical hardware.

Testing confirms that:

- normal WLAN remains operational
- cloud connectivity remains operational
- thermostat and valve operation remain available
- beacon statistics continue operating
- the known stale self-sustaining loop is removed
- fresh qualifying Recovery can still occur

Current C-C-based configurations have shown fresh Recovery rates around:

```text
~27–30 events/hour
```

during parts of the runtime tests.

The remaining fresh trigger is still under investigation.

---

# 9. WF200 `PS_MODE_ERROR` Is Not Required

A separate D3 observer was built to monitor the known WF200:

```text
PS_MODE_ERROR
```

indication.

On one long-term observer run:

```text
uptime:
~63.9 h

Beacon Recovery counter:
3835

D3_total:
0
```

Thousands of host Beacon Recovery events therefore occurred without a recorded D3 `PS_MODE_ERROR`.

This does not prove that the radio was always physically sleeping correctly.

It does establish that this known WF200 error indication is not required for the observed host Recovery behavior.

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

# 11. A1

A1 is the experimental correction for the qualified PM lifecycle and ownership defects.

It addresses the project defect classes:

```text
G01
G02
G03
G05
G06
G18
G19
```

A1 does not blindly clear sleep blockers.

Instead, it preserves the reconstructed ownership and settlement model and corrects the identified failure paths.

The final integration passed extensive static qualification, including:

```text
36 / 36 canonical behavior/control scenarios
```

plus malformed and corruption tests.

The final build contains:

```text
93 hooks
210 relocations
```

with zero unexplained application changes in the final reconstruction.

A1 has also been exercised on physical hardware as part of the integrated A1+C-C+WF200 3.18.0 firmware.

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

The corresponding changelog contains a relevant fix described as:

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

# 13. A1 + C-C + WF200 3.18.0

The current integrated experimental correction platform combines:

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
Size:
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
Size:
1,066,544 bytes

SHA-256:
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The artifact successfully installed through OTA and booted on physical hardware.

The device successfully initialized:

```text
FMAC 3.7.0
+
WF200 3.18.0
```

and continued normal WLAN, cloud, thermostat and valve operation.

Long-term testing is ongoing.

---

# 14. Fresh Recovery Still Exists

The integrated A1+C-C+WF200 3.18.0 device continues to show fresh qualifying Beacon Recovery events.

One representative long-term period produced approximately:

```text
27–28 events/hour
```

This is important because C-C has already removed the known stale-evidence recurrence.

The remaining events therefore represent a different question:

> Why does the host still occasionally obtain a fresh measurement that qualifies for Recovery?

Disabling FRITZ!Box Mesh/Band Steering did not eliminate this behavior in the current test.

The remaining trigger is still being investigated.

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

The EM3 path disables:

```text
LFXO
LFRCO
```

while EM2 retains the required low-frequency clock.

Simply clearing B3 and allowing EM3 would therefore break the assumptions of the current scheduler/tickless implementation.

The project does **not** consider the permanent B3 contribution a battery-drain bug.

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

---

# 18. Phantom B2 Contribution

One verified native schedule can produce:

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

A phantom B2 contribution could therefore create persistent excess host awake power until another event repairs the count or the device resets.

Whether this occurs frequently on physical draining devices is not yet established.

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

This is a demonstrated firmware concurrency defect.

Its field occurrence rate and battery impact remain to be measured.

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

The open question is whether PA8 repeatedly or persistently prevents WFI during a battery-drain episode.

---

# 21. Stock Host Observer

The next diagnostic firmware is intentionally based on clean stock 2.2.4.

It should preserve:

```text
stock Beacon Recovery
stock PM lifecycle
stock B2/B3 accounting
stock Final-Sleep
stock PA8 handling
stock WF200 3.16.1
```

and add only passive instrumentation.

The observer is intended to measure:

- current B2/B3/O state
- B2 acquire/release activity
- owner-specific B2 activity
- shadow ownership
- B2 mismatch
- EM1 entry count
- EM2 entry count
- WFI attempts
- PA8 veto count
- first-fault state
- recent relevant events

The observer must **not** serialize or repair the stock B2 race.

That noninterference requirement is part of its qualification.

---

# 22. Observer Status

A working Stock Host Observer application has been constructed.

Initial independent checks confirmed preservation of:

```text
stock B2 helpers
stock sleep selector
permanent B3 contribution
stock WF200 payload
```

and initial observer bookkeeping tests have passed.

However, the observer is **not yet qualified for device testing**.

Remaining qualification includes:

- emitted Thumb wrapper execution
- register/flags/LR/SP preservation
- PRIMASK behavior
- race-window preservation
- status serialization
- stack/headroom analysis
- RAM lifetime
- final GBL reconstruction
- deterministic construction

The final qualification verdict must be either:

```text
STOCK HOST OBSERVER QUALIFIED FOR CONTROLLED DEVICE TEST
```

or:

```text
NO-GO
```

No intermediate observer build should be treated as qualified firmware.

---

# 23. Experimental Firmware Overview

| Variant | Purpose | Status |
|---|---|---|
| Stock 2.2.4 | reference | hardware |
| Patch A | bypass Beacon Recovery | historical hardware-tested isolation |
| Patch B | suppress periodic mDNS restart | hardware-tested isolation |
| Patch A+B | combined isolation | historical hardware-tested experiment |
| C-C | correct C1a/C1b/C2 | hardware tested |
| D3 Observer | observe WF200 `PS_MODE_ERROR` | hardware tested |
| WF200 3.18.0 | newer radio PM firmware | hardware tested |
| C-C + WF200 3.18.0 | Recovery correction + newer radio | hardware tested |
| A1 | PM lifecycle correction | qualified and hardware tested in integrated build |
| A1 + C-C + WF200 3.18.0 | integrated correction platform | hardware testing ongoing |
| Stock Host Observer | observe B2/PA8/EM1/EM2 | qualification in progress |

Detailed patch information is maintained in:

[`docs/patch/README.md`](docs/patch/README.md)

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

Current or recent important roles include:

| Device | Configuration | Role |
|---|---|---|
| `.11` | 2.2.4 D3 observer / WF200 3.16.1 | D3 comparison |
| `.77` | 2.2.4 + Patch B | completed mDNS-isolation discharge test |
| `.88` | 2.2.4 + C-C / WF200 3.16.1 | C-C long-term reference |
| `.229` | stock 2.2.4 | stock reference |
| `.234` | A1 + C-C + WF200 3.18.0 | integrated correction canary |
| `.237` | C-C + WF200 3.18.0 | combined reference |

Additional devices are used for historical and secondary comparisons.

Datasets crossing a firmware transition must be split at that transition.

---

# 26. Long-Term Battery Testing

A dedicated logger collects runtime data from multiple physical TRVs.

The normal interval is approximately:

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

Battery voltage is generally more useful than reported percentage for short-term trend comparison, but neither is a direct measurement of energy consumption.

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

The Stock Host Observer is intended to provide more direct information about actual host low-power entry decisions.

---

# 28. Current Battery-Drain Model

The available evidence supports a multi-mechanism model.

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
        +-- AP / RF environment
```

Several of these now contain demonstrated firmware defects.

That still does not establish their quantitative energy contribution.

A code defect can exist without being the dominant battery consumer.

Likewise, a high-frequency workload can consume energy without being the original root cause.

---

# 29. What Has Been Established

The investigation currently supports the following technical conclusions:

- periodic connected mDNS activity is a real recurring workload in later firmware
- Patch B suppresses the targeted periodic restart
- periodic mDNS is not required for recurring Beacon Recovery
- 2.2.4 contains a real Beacon Recovery mechanism
- good RSSI does not prevent the observed recurring Recovery behavior
- `real_beacon_skip` is a host-derived estimator, not direct physical beacon-skip state
- C1a changes valid positive estimator values through signed interpretation
- C1b allows a counter delta to represent a longer window than the fixed formula assumes
- C2 can reuse historical Recovery evidence without a fresh calculation
- C-C corrects these validity problems while retaining fresh Recovery
- fresh Recovery still occurs after C-C
- known D3 `PS_MODE_ERROR` is not required for host Beacon Recovery
- multiple host PM lifecycle/ownership defects exist
- A1 corrects the qualified PM lifecycle defect set
- FMAC 3.7.0 can operate with the tested WF200 3.18.0 integration
- the permanent B3 contribution has a valid RTC/LFXO reason
- intended normal deepest host idle is EM2
- shared B2 blocker accounting contains a real task-preemption race
- the B2 race can produce either phantom or lost ownership
- PA8 can independently veto WFI
- A1 does not correct the global B2 RMW race
- the integrated A1+C-C+WF200 3.18.0 firmware boots and operates on physical hardware

---

# 30. What Has Not Been Established

The project does **not** currently claim:

- that one single mechanism explains all historical battery drain
- that Beacon Recovery is the sole cause
- that periodic mDNS is the sole cause
- that WF200 3.18.0 alone fixes the problem
- that C-C alone fixes the problem
- that A1 alone fixes the problem
- that the integrated firmware is a final production fix
- that every fresh Beacon Recovery event is erroneous
- that B2 corruption has already been observed on physical hardware
- that PA8 is defective
- that EM3 should be enabled
- that `/stats sleep_ratio` represents physical sleep residency
- that the exact energy contribution of each mechanism is known
- that a specific final battery lifetime has been restored

The project currently has no direct electrical current measurements.

---

# 31. Current Research Direction

The immediate priority is the host-sleep observer.

The sequence is:

```text
Stock 2.2.4
    |
    v
passive Host Observer
    |
    v
measure B2 / PA8 / EM1 / EM2
    |
    +-- no B2 corruption observed
    |       |
    |       +-- continue investigation
    |
    +-- B2 corruption observed
            |
            v
    bounded B2 serialization fix
            |
            v
    observer A/B comparison
            |
            v
    integrate qualified fix into
    A1 + C-C + WF200 3.18.0
```

In parallel:

- continue long-term A1+C-C+WF200 3.18.0 testing
- continue C-C reference testing
- compare cloud-on/cloud-off behavior
- continue WLAN/AP isolation tests
- investigate the remaining fresh Beacon Recovery trigger

The goal is not to remove every source of WLAN activity.

The goal is to correct demonstrated firmware defects while preserving legitimate power-management and reliability behavior.

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

### AP selection and roaming

[`docs/reverse-engineering/ap-selection-and-roaming.md`](docs/reverse-engineering/ap-selection-and-roaming.md)

### Periodic mDNS

[`docs/reverse-engineering/mdns-periodic-restart.md`](docs/reverse-engineering/mdns-periodic-restart.md)

### mDNS runtime comparison

[`docs/testing/mdns-runtime-comparison.md`](docs/testing/mdns-runtime-comparison.md)

### Battery testing

[`docs/testing/battery-testing.md`](docs/testing/battery-testing.md)

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

A failed precondition should stop the build.

It should never silently adapt offsets to an unknown firmware image.

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

Always check the documented status of the specific variant.

---

# 35. OTA Testing

Experimental GBL images have been installed on controlled devices through the normal Gen1 OTA mechanism.

For the local test environment, the HTTP server must be reachable on:

```text
TCP port 80
```

Port 8000 caused OTA retrieval problems.

On macOS, binding a Python HTTP server to port 80 normally requires elevated privileges.

OTA acceptance is not equivalent to firmware qualification.

A build must still pass its relevant static, binary, container and runtime checks.

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

Decompiler output is used as supporting information.

Important control-flow conclusions are checked against native instructions and, where practical, executable behavior.

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
static qualification
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

The objective is to understand why a mechanism exists, determine whether its control logic is valid, preserve legitimate functionality and correct only behavior that the available evidence demonstrates is defective.

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
