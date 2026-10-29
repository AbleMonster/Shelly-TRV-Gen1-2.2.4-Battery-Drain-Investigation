# Battery Testing

## Overview

This document describes the long-term battery investigation of the Shelly TRV Gen1 across stock firmware, historical experimental builds and the current corrected B2.1_OBS hardware population.

The objective is not to infer laboratory-grade power consumption from battery percentage.

The objective is to determine whether real-world battery behavior changes reproducibly after demonstrated firmware defects are corrected.

The current investigation combines:

```text
battery voltage
+
battery percentage
+
firmware identity
+
runtime
+
PM / Beacon Recovery telemetry
+
WLAN statistics
+
valve workload
+
reboot / reconnect behavior
+
long-term observation
```

No direct current measurement is currently part of the long-term dataset.

Therefore diagnostic values such as:

```text
Recovery events/hour
Recovery wall-clock occupancy
beacon receive rate
sleep_ratio
PM52 activity
cmd66 statistics
```

must not be converted directly into:

```text
mA
mAh/day
battery percentage
battery lifetime
```

without an electrical measurement.

---

# 1. Current Test Objective

The current main question is:

> Does the qualified corrected firmware remain free of the historical rapid battery-drain behavior during long-term real-world operation?

The active corrected hardware stack is:

```text
Shelly TRV 2.2.4
        |
        v
A1R host PM/lifecycle correction
        |
        v
C-C Beacon Recovery correction
        |
        v
B2 bounded serialization
        |
        v
minimal MQTT PUBLISH guard
        |
        v
Shelly FMAC 3.7.0
        |
        v
WF200 3.18.0
        |
        v
PM52 -> cmd66 observer
```

This build is:

```text
B2.1_OBS
```

The active comparison is:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The battery test is also an integration test.

A firmware that appears to improve voltage behavior but causes:

- reconnects
- reboots
- broken thermostat behavior
- incorrect valve behavior
- failed WLAN association
- calibration problems
- PM deadlocks
- incorrect sleep ownership

would not represent a successful correction.

---

# 2. Current Hardware Population

The active long-term devices are:

| Device | Firmware | WF200 | Role |
|---|---|---|---|
| `.77` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.88` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.11` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.71` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.234` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.61` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.97` | stock 2.2.4 | 3.16.1 | stock control |

Historical roles of these physical devices remain valid for their historical experiment periods.

An IP address is not a permanent firmware identity.

---

# 3. Current Decision

The active long-term phase is deliberately conservative:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

During this phase:

- do not flash another firmware variant
- do not deploy B2.2 to the active hardware population
- do not deliberately change AP topology
- do not start a new Recovery-rate experiment
- do not disable fresh Recovery
- do not change the estimator constant
- do not introduce additional WF200 requests
- do not interpret early stability as a final battery result

The current experiment needs time more than additional code changes.

---

# 4. Battery Drain Is Not Treated as a Single-Cause Problem

Battery drain was observed on firmware versions predating 2.2.4.

That is an important boundary condition.

The 2.2.4 Beacon Recovery defects can therefore act as:

```text
additional workload
```

or:

```text
battery-consumption amplifier
```

but cannot by themselves explain the complete historical TRV Gen1 drain problem.

The working model remains:

```text
normal TRV consumption
        |
        +-- host MCU activity
        |
        +-- WF200 WLAN activity
        |
        +-- cloud/controller traffic
        |
        +-- valve motor
        |
        +-- RF conditions
        |
        +-- PM transitions
        |
        +-- Beacon Recovery
        |
        +-- host PM lifecycle defects
        |
        +-- host blocker-accounting defects
        |
        +-- peripheral/resource lifecycle defects
        |
        +-- possible WF200 PM defects
        |
        +-- other unidentified behavior
        |
        v
total battery consumption
```

The corrected firmware removes demonstrated defects without assuming in advance which one dominates battery endurance.

---

# 5. Measurement Sources

The TRV itself remains the primary telemetry source.

Important interfaces include:

```text
/status
/stats
/debug/log
```

depending on firmware generation and build.

The most important battery values are:

```text
bat.value
bat.voltage
```

Additional useful runtime information includes:

```text
uptime

reboot_counter
reconnect_counter

RSSI

valve position
target temperature
measured temperature
steps_counter

sleep_ratio

desired_beacon_skip
real_beacon_skip

beacon_err_counter
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

On B2.1_OBS, the explicit observer readout additionally exposes:

```text
pm52_cmd66
```

for diagnostic correlation.

---

# 6. B2.1_OBS Observer Data

The current observer records already-existing activity around the relevant PM and statistics paths.

It records:

- actual PM52 requests
- PM52 results
- A1R completion decisions
- existing periodic command-0x66 requests
- command-0x66 results
- fresh estimator operands
- connection epochs
- recent-event history
- first-fault freeze state

The observer adds no additional WF200 request.

It adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
```

This makes it suitable for long-term diagnostic use with lower risk of materially changing the system under observation.

Physical timing perturbation from instrumentation can never be excluded absolutely, which is why an observer-free hardware regression remains necessary later.

---

# 7. Sampling Frequency

Frequent diagnostic polling can itself disturb a low-power device.

Long-term testing should therefore use sparse, well-defined sampling.

The preferred long-term pattern is approximately:

```text
one planned measurement per day
```

with additional collection only when required by an abnormal event.

A normal collection should retrieve the minimum telemetry needed for the comparison.

Where `/stats` requires additional WF200 interaction, that interaction must be considered part of the measurement process.

The principle is:

```text
few consistent samples
>
frequent manual polling
```

for battery-life comparison.

---

# 8. Battery Voltage Is the Primary Short-Term Trend

Battery percentage is not a coulomb counter.

It does not represent a continuously integrated measurement of consumed charge.

The firmware derives the displayed percentage from the cached battery voltage using a stateless integer mapping.

Therefore the primary short-term battery trend is:

```text
voltage over time
```

while:

```text
battery percentage
```

is secondary information.

Useful descriptive metrics include:

```text
mV/day
```

and, with more caution:

```text
%/day
```

Percentage has substantially less resolution and physical meaning than direct voltage telemetry.

---

# 9. Battery Percentage Is Stateless

The displayed percentage should not be interpreted as accumulated energy bookkeeping.

Conceptually:

```text
cached battery millivolts
        |
        v
firmware percentage mapping
        |
        v
displayed battery %
```

There is no demonstrated coulomb-counting state that tracks actual consumed charge.

Therefore:

```text
100 %
```

on two physical batteries does not establish identical usable capacity.

Likewise:

```text
50 %
```

on two devices does not establish equal remaining energy.

---

# 10. Low-Voltage Shutdown Threshold

Reverse engineering across:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

shows the same relevant low-voltage threshold:

```text
3000 mV
```

Below approximately:

```text
3.000 V
```

the firmware enters the low-battery shutdown sequence.

The observed host behavior includes an approximately three-serviced-second countdown followed by:

```text
PA0 low
```

and, in 2.2.4, the main task subsequently enters a busy-loop state.

The exact board-level power-rail consequence of PA0 LOW has not been independently established.

The important battery-test implication is:

> A displayed 0% value is not itself the final electrical cutoff criterion; the firmware's low-voltage shutdown logic is tied to approximately 3000 mV.

---

# 11. Voltage Is Not Remaining Capacity

Voltage is more useful than displayed percentage for short-term comparison, but it is still not a direct capacity measurement.

Voltage depends on:

- state of charge
- instantaneous load
- valve movement
- WLAN activity
- battery temperature
- internal resistance
- battery age
- recent charging
- discharge history
- relaxation after load

A short-term change such as:

```text
3.626 V -> 3.609 V
```

must therefore not be extrapolated linearly to a lifetime estimate.

---

# 12. Voltage Rebound

Lithium battery voltage can recover after a temporary load.

For example, historical testing observed values moving from approximately:

```text
3.599 V
```

back toward:

```text
3.609 V
```

without charging.

This is normal load/relaxation behavior.

A single low voltage point therefore does not necessarily represent an irreversible capacity loss of the same magnitude.

---

# 13. API and External Voltage Must Remain Separate

Voltage measurements from different methods must not be merged into one continuous trend.

For example:

```text
external post-charge measurement:
4.020 V
```

and:

```text
later /status measurement:
3.630 V
```

are both useful individually.

They are not equivalent samples.

Every trend should identify the source:

```text
TRV API
```

or:

```text
external meter
```

and avoid calculating a continuous slope across measurement methods.

---

# 14. ADC Measurement Caveat

The battery-voltage sampling path itself has also been reverse engineered.

One identified implementation detail is that the shared millivolt field can transiently contain raw ADC-count data during sampling.

That behavior is tracked separately as a deferred candidate and is not currently treated as a demonstrated cause of the reported long-term voltage trend.

A separate ADC timeout cleanup defect involving PA3 was demonstrated and corrected as:

```text
P01
```

in B2.2.

P01 is not part of the currently deployed B2.1_OBS hardware population.

---

# 15. Battery Condition

The physical batteries are not guaranteed to have identical:

- age
- usable capacity
- internal resistance
- charge history
- previous discharge depth
- temperature history

This is one of the largest limitations of cross-device comparison.

For example:

```text
TRV A: -5 %
TRV B: -10 %
```

does not establish:

```text
Firmware B uses twice the energy.
```

Repeated trends across several devices are more valuable than ranking individual units.

---

# 16. Charge and T0 Procedure

Where practical, devices beginning a new long-term interval should receive an individually documented starting condition.

Each device should have a:

```text
T0
```

record containing at least:

```text
timestamp
physical device
firmware/build identity
WF200 version
battery percentage
battery voltage
uptime
RSSI
reboot counter
reconnect counter
valve position
target temperature
measured temperature
Beacon Recovery counter
desired_beacon_skip
real_beacon_skip
```

For B2.1_OBS, observer state or research-build identity should also be recorded.

Devices do not need identical starting voltage.

The starting condition needs to be known.

---

# 17. Firmware Identity

A physical TRV does not permanently represent a firmware configuration.

Several devices in this project have run multiple builds.

Therefore:

> Firmware identity must be determined from the actual build and experiment period, not from the device address alone.

Every OTA or reflash creates a new experimental interval.

Data from before and after the transition must not be merged into one continuous firmware result.

---

# 18. Historical Builds Must Keep Their Names

Historical evidence must preserve the firmware that actually produced it.

In particular:

```text
A1
A1R
B2
B2_OBS
B2.1
B2.1_OBS
B2.2
```

are not interchangeable names.

Historical A1 results must not be relabeled A1R.

Historical B2 results must not be relabeled B2.1.

This distinction is necessary for reproducible firmware chronology.

---

# 19. Valve and Motor Workload

The valve motor performs real mechanical work and can represent a significant battery load.

Battery comparisons must therefore consider:

```text
valve movement
calibration
heating demand
target-temperature changes
```

A device performing:

- calibration
- full opening
- full closing
- repeated repositioning

cannot be directly compared over a short interval with a stationary valve.

Useful context includes:

```text
steps_counter
valve position
movement events
```

Motor steps are not currently converted into joules or mAh.

---

# 20. Short-Uptime `steps/hour`

A calculated:

```text
steps/hour
```

value is particularly misleading shortly after boot.

Calibration or large valve movement in the first minutes can produce an extremely high apparent rate.

For long-term comparison:

```text
steps_counter
```

plus the actual elapsed interval is more useful.

---

# 21. WLAN Signal Strength

RSSI is recorded because WLAN conditions can affect:

- desired beacon policy
- retransmission behavior
- receive activity
- reconnects
- cloud traffic
- PM behavior

The reconstructed 2.2.4 desired-skip policy is approximately:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

A lower requested skip does not imply proportional complete-device battery consumption.

RSSI also does not describe the entire RF environment.

Two devices with similar RSSI can differ in:

- access point
- channel
- interference
- retransmissions
- beacon timing
- connection history

---

# 22. `real_beacon_skip`

`real_beacon_skip` is not direct radio-sleep telemetry.

For example:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not prove:

```text
WF200 physically used listen interval 1
```

and does not prove:

```text
WF200 remained continuously awake
```

The value is a host estimator derived from WF200 received-beacon statistics.

It remains relevant because it participates in Shelly's Beacon Recovery decision.

---

# 23. Beacon Recovery as a Battery Variable

Firmware 2.2.4 can enter:

```text
Beacon skip error! Attempt recovery
        |
        v
PM state 1
        |
        v
Active / Always-On WLAN
        |
        | ~5 serviced seconds
        v
restore connected power saving
```

During Recovery:

- a more active WLAN PM policy is requested
- host sleep may be restricted toward EM1
- additional PM control work occurs

This makes Recovery a credible additional workload.

Its electrical energy cost has not been measured directly.

---

# 24. Historical Stock Recovery Occupancy

Several historical stock devices produced approximately:

```text
60 Recoveries/hour
```

for extended periods.

At approximately:

```text
~5 serviced seconds/Recovery
```

this gives:

```text
60 × 5 s
= 300 s/hour
= 5 min/hour
≈ 8.33% wall-clock occupancy
```

This is time.

It is not:

```text
8.33% battery consumption
```

No conversion to energy is justified without current measurement.

---

# 25. Historical `.11` D3 Result

The historical `.11` D3 observer produced approximately:

```text
uptime                 ~63.93 h
Beacon Recoveries      3835
Recovery rate          ~59.99/hour
D3 PS_MODE_ERROR       0
```

At approximately five seconds per Recovery:

```text
3835 × ~5 s
≈ 19175 s
≈ 319.6 min
≈ 5.33 h
```

of explicit Recovery occupancy accumulated.

The central result is:

```text
3835 host Recoveries
0 D3 PM errors
```

The host heuristic and known WF200 PM-error channel are therefore not equivalent.

---

# 26. Historical `.77` Full-Discharge Endpoint

Historical `.77` ran:

```text
2.2.4
+
Patch B
```

with targeted periodic mDNS suppression while stock Beacon Recovery remained active.

Its final observed state was approximately:

```text
uptime              797437 s
                    221.51 h
                    9.23 days

battery             0 %
voltage             3.116 V

reboot_counter      1
reconnect_counter   30

RSSI                -79 dBm

valve position      0 %
target temperature  18.0 °C
temperature         18.7 °C

sleep_ratio         0.014383

desired skip        15
real skip           1

beacon_err          12908
```

Recovery rate:

```text
12908 / 797437 × 3600
≈ 58.27/hour
```

Estimated explicit Recovery occupancy:

```text
12908 × ~5 s
≈ 64540 s
≈ 17.93 h
```

or approximately:

```text
8.09%
```

of total runtime.

Again:

```text
8.09% wall-clock Recovery occupancy
!=
8.09% battery energy
```

The supported conclusion is:

> Targeted periodic mDNS suppression did not prevent the complete observed discharge of this device.

It does not prove Beacon Recovery alone caused the discharge.

---

# 27. Historical `.88` C-C Result

Historical `.88` ran:

```text
2.2.4 + C-C
WF200 3.16.1
```

A long observation around 9.9 days showed approximately:

```text
battery        56 %
voltage        3.570 V
beacon_err     0
desired skip   20
real skip      6
```

This established that C-C could operate for an extended period without fresh qualifying Recovery on that physical device.

It does not by itself prove a battery-life improvement.

---

# 28. Historical `.237` C-C + WF200 3.18.0

Historical `.237` used:

```text
C-C
+
WF200 3.18.0
```

An approximately 15.19-hour interval showed:

```text
battery        72 %
voltage        3.669 V
sleep_ratio    0.020343
desired skip   20
real skip      1
beacon_err     362
```

or approximately:

```text
29.96 Recoveries/hour
```

This showed that fresh qualifying Recovery could still occur after:

- C-C
- WF200 3.18.0

That rate was specific to the observed interval.

---

# 29. Historical `.234` A1 Integration

Historical `.234` tested:

```text
A1
+
C-C
+
WF200 3.18.0
```

The build completed:

```text
OTA
cold reboot
FMAC 3.7.0 initialization
WF200 3.18.0 initialization
scan
association
DHCP
cloud
PM transitions
calibration
thermostat operation
valve movement
```

This was an important historical functional milestone.

It was not the final corrected platform.

A1 was later superseded by A1R.

---

# 30. Historical `.234` Fresh Recovery

Representative historical A1+C-C+WF200 3.18.0 measurements included approximately:

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

The longer intervals corresponded to roughly:

```text
27–28 Recoveries/hour
```

Because C-C was active, this behavior was not the stock C2 stale-evidence recurrence.

Fresh valid estimator measurements were still capable of triggering Recovery.

---

# 31. C2 Interpretation

C2 should not be described as a guaranteed permanent self-trigger loop.

The demonstrated behavior is a:

```text
metastable stale-evidence recurrence
```

that can persist for long periods.

Stock historical approximately once-per-minute behavior remains real.

The mechanism is not necessarily impossible to leave without reboot.

---

# 32. Historical C-C Recovery Occupancy

Some C-C periods showed approximately:

```text
27–30 fresh Recoveries/hour
```

Under those specific conditions:

```text
30 × ~5 s
≈ 150 s/hour
≈ 2.5 min/hour
≈ 4.17% wall-clock occupancy
```

and:

```text
27 × ~5 s
≈ 135 s/hour
≈ 2.25 min/hour
≈ 3.75% wall-clock occupancy
```

These are historical measurements.

They are not universal C-C limits.

---

# 33. Recovery Frequency Is Not Currently Being Optimized

Earlier investigation stages considered further Recovery-rate limiting.

That is not the current active test objective.

The known side remains:

```text
fewer Recoveries
        |
        v
less explicit Recovery occupancy
```

A hypothetical opposing effect would be:

```text
unknown WF200 fault
        |
        v
Recovery happens to clear it
        |
        v
less frequent Recovery
may allow it to persist longer
```

That second mechanism has not been demonstrated.

Therefore the current corrected firmware conservatively:

```text
rejects invalid/stale Recovery evidence
+
retains fresh valid Recovery
```

and the active long-term experiment does not alter this variable.

---

# 34. WF200 3.18.0

WF200 3.18.0 contains an official Silicon Labs correction in a directly relevant PM area involving failure to sleep after a power-save mode change.

This makes it an important part of the corrected experimental platform.

It does not prove:

```text
WF200 3.16.1 was the historical root cause
```

or:

```text
WF200 3.18.0 fixes all TRV battery drain
```

Physical testing has demonstrated that the tested official WF200 3.18.0 firmware operates with Shelly FMAC 3.7.0 on TRV Gen1 hardware.

---

# 35. A1R

A1R supersedes the historical A1 implementation.

A1R preserves the demonstrated lifecycle corrections while correcting an experimental A1 regression involving temporary `request1` override paths.

Qualification includes:

```text
151 / 151 Thumb behavior tests PASS
```

The historical A1 runtime results remain historical A1 results.

---

# 36. B2 Serialization

The host-sleep investigation demonstrated a task-preemption/lost-update defect in the shared B2 reference counter.

The correction serializes complete relevant B2 read-modify-write operations while preserving reference-count semantics.

It does not:

```text
force B2 = 0
```

and does not:

```text
convert B2 to a Boolean
```

B2 serialization is part of B2.1 and B2.1_OBS.

---

# 37. B2.1

The observer-free corrected baseline is:

```text
B2.1
```

containing:

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

Artifact:

```text
final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.gbl
```

This is the baseline beneath the current observer build.

---

# 38. B2.1_OBS Qualification

The active hardware build is:

```text
B2.1_OBS
```

Qualification includes:

```text
A1R:
151 / 151

observer/readout:
356 / 356

B2:
2060 + additional mixed/preemption qualification

MQTT:
258

plus:
C-C qualification
decoder regressions
deterministic reconstruction
independent GBL verification
zero unexplained changes
```

Disposition:

```text
B2.1_OBS RELEASE-CANDIDATE GO
```

This means suitable for controlled hardware observation.

It is not a battery-life certification.

---

# 39. B2.2

B2.2 is a later observer-free integrated candidate.

It contains nine selected qualified corrections:

```text
1. A1R including A1 lifecycle correction
2. C-C
3. B2 serialization
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

It has not been deployed onto the active long-term hardware population.

Therefore B2.2 currently provides no battery-runtime evidence.

---

# 40. Current Early B2.1_OBS Observation

During the initial corrected-hardware observation period:

```text
B2.1_OBS:
beacon_err = 0
```

on the corrected devices during the observed startup period.

The stock `.97` control accumulated thousands of historical `beacon_err` events and showed periods of approximately minute-scale Recovery recurrence.

Another stock interval showed only a small increase.

Therefore even stock Recovery behavior is not assumed to be temporally constant.

The correct classification is:

```text
early observation
```

not:

```text
battery-life result
```

---

# 41. Stock Control

The active stock control is:

```text
.97
```

running:

```text
stock Shelly 2.2.4
FMAC 3.7.0
WF200 3.16.1
```

The contemporaneous stock control provides reference data for:

```text
battery voltage
battery percentage
Recovery behavior
WLAN behavior
valve workload
reboots
reconnects
```

A single stock TRV does not eliminate hardware or environmental variation.

It is still substantially stronger than comparing only against old historical records.

---

# 42. Normal Heating Operation

The current field test intentionally uses the TRVs in normal heating operation.

Therefore:

```text
valve activity
heating demand
room temperature
```

are not perfectly controlled.

That is intentional.

The final practical question is whether the corrected firmware remains stable and improves real-world endurance under actual TRV use.

The resulting data are observational rather than laboratory-controlled.

---

# 43. Main Long-Term Metrics

The primary short-term battery trend is:

```text
mV/day
```

Secondary battery information includes:

```text
%/day
```

Important mechanism metrics include:

```text
Recovery events/hour
beacon_rx/second
beacon missed rate
desired_beacon_skip
real_beacon_skip
sleep_ratio
reboot count
reconnect count
```

For B2.1_OBS, relevant fault diagnosis also includes:

```text
PM52 result
cmd66 result
connection epoch
observer first-fault state
```

Workload context includes:

```text
motor steps
valve position
target temperature
measured temperature
RSSI
```

No single metric is expected to explain the result.

---

# 44. Recovery Rate Calculation

For cumulative Recovery counters:

```text
delta_recovery = recovery_2 - recovery_1

delta_time = uptime_2 - uptime_1
```

then:

```text
Recovery/hour
=
delta_recovery / delta_time × 3600
```

For one uninterrupted firmware interval:

```text
Recovery/hour
=
beacon_err_counter / uptime × 3600
```

This is only valid when:

- counter semantics are known
- uptime has not reset
- firmware has not changed
- the relevant interval is continuous

---

# 45. Recovery Wall-Clock Occupancy

For an approximately five-serviced-second Recovery:

```text
Recovery occupancy/hour
≈
Recovery/hour × ~5 s
```

Examples:

```text
60/hour
≈ 300 s/hour
≈ 5 min/hour
≈ 8.33%
```

and:

```text
30/hour
≈ 150 s/hour
≈ 2.5 min/hour
≈ 4.17%
```

This is explicit Recovery occupancy.

It must not be reported as battery-consumption percentage.

---

# 46. Beacon Receive Rate

When useful:

```text
beacon_rx/second
```

can be calculated as:

```text
delta_beacon_rx / delta_time
```

This is more useful than comparing cumulative counters from different uptimes.

It remains diagnostic telemetry, not radio current.

---

# 47. Reboots and Reconnects

Every long-term record should retain:

```text
reboot_counter
reconnect_counter
uptime
```

Unexpected reboot creates a major experiment boundary.

Frequent reconnects also add WLAN workload and may invalidate a simple battery comparison.

A firmware that saves apparent battery energy by losing connectivity would not be a successful correction.

---

# 48. `sleep_ratio`

The firmware exposes:

```text
sleep_ratio
```

This remains useful comparative telemetry.

It is not direct physical:

```text
EM1 residency
EM2 residency
WF200 sleep residency
```

and must not be converted directly into expected battery lifetime.

---

# 49. Host Sleep Selection

Current reverse engineering establishes:

```text
B2 != 0
    -> deepest permitted host mode EM1

B2 == 0 && B3 != 0
    -> EM2

B2 == 0 && B3 == 0
    -> EM3
```

Normal intended deepest idle includes persistent B3 ownership and is therefore:

```text
EM2
```

not EM3.

This is important because "does not enter EM3" is not itself evidence of a battery defect.

---

# 50. PA8

PA8 is an independent WLAN host-notification / WFI veto.

If PA8 is asserted when the host is about to execute WFI, host low-power entry can be prevented.

PA8 HIGH is not automatically abnormal.

It can indicate legitimate pending WLAN work.

The current telemetry does not directly convert PA8 behavior into an energy value.

---

# 51. Major Confounding Variables

| Variable | Status | Relevance |
|---|---|---|
| Firmware | controlled per interval | primary |
| WF200 firmware | controlled per interval | primary |
| Physical TRV | differs | hardware variation |
| Battery age | differs | capacity/resistance |
| Battery history | differs | starting condition |
| Valve workload | recorded where possible | major load |
| Calibration | documented | major short-term load |
| RSSI | recorded | WLAN policy/RF |
| Associated AP | not always continuously recorded | RF uncertainty |
| Device location | differs | RF/temperature |
| Heating demand | differs | motor workload |
| Temperature | differs | battery/heating |
| Network traffic | not identical | WLAN activity |
| Reboots | recorded | interval boundary |
| Reconnects | recorded | WLAN workload |
| Diagnostic polling | minimized | perturbation |
| Observer build | controlled | instrumentation |

These variables must remain visible when interpreting any apparent battery ranking.

---

# 52. Same-Device Testing

Same-device A/B testing remains useful where practical:

```text
same physical TRV
        |
        +-- stock interval
        |
        +-- corrected interval
```

It reduces some hardware variation.

It does not remove:

- battery aging
- state-of-charge differences
- seasonal heating demand
- room-temperature changes
- RF changes
- valve workload differences

Same-device testing is stronger than simple cross-device ranking but still weaker than direct electrical measurement.

---

# 53. Why Short 24-Hour Rankings Are Weak

A one-day result may be dominated by:

- post-charge relaxation
- calibration
- valve movement
- room-temperature changes
- temporary WLAN behavior
- percentage quantization

Therefore:

```text
24 hours
```

is useful for identifying gross failures but weak for battery-life conclusions.

Longer intervals such as:

```text
7 days
```

and preferably:

```text
14 days or longer
```

are more useful when practical.

Complete discharge trajectories remain valuable historical evidence, but each remains one physical-device result.

---

# 54. Current Long-Term Strategy

The active strategy is no longer a proposed future test.

It is already running:

```text
6 corrected devices
B2.1_OBS
WF200 3.18.0

vs.

1 stock control
2.2.4
WF200 3.16.1
```

Devices should remain:

- on unchanged firmware
- under normal heating operation
- sampled consistently
- monitored for reboot/reconnect
- compared primarily by voltage trajectory
- compared secondarily by percentage
- interpreted with valve and RF context

The main requirement now is test continuity.

---

# 55. If B2.1_OBS Drains

If one corrected TRV begins to show genuine rapid drain:

```text
abnormal voltage/runtime trajectory
        |
        v
preserve first-fault observer state
        |
        v
inspect PM52 history
        |
        v
inspect cmd66 history
        |
        v
correlate connection epoch
        |
        v
correlate PM completion behavior
        |
        v
resume deeper reverse engineering
```

The important point is to capture the fault before changing firmware or test conditions.

---

# 56. If B2.1_OBS Remains Stable

If the corrected devices remain stable over a meaningful long-term interval:

```text
remove observer
        |
        v
requalify observer-free corrected build
        |
        v
hardware regression
        |
        v
evaluate final candidate
```

The observer is diagnostic instrumentation.

It should not automatically become part of a final firmware.

---

# 57. Why B2.2 Is Not Being Flashed Now

B2.2 contains additional qualified corrections, but it remains:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

The current B2.1_OBS experiment is already in progress.

Flashing B2.2 now would:

- terminate the current interval
- change several variables
- reduce long-term comparability
- discard the value of continued observer coverage

Therefore B2.2 remains frozen offline while the B2.1_OBS population is observed.

---

# 58. Direct Electrical Measurement

Direct synchronized current measurement would answer several questions more precisely.

Useful comparisons could include:

```text
normal idle
Recovery
valve movement
WLAN reconnect
PM transition
```

and correlate:

```text
current
+
host PM state
+
WUP / PA8
+
debug telemetry
+
WF200 state
```

No such synchronized current measurement is currently part of the active project dataset.

Therefore no exact values are assigned for:

```text
Recovery current
mAh per Recovery
mAh/day caused by Recovery
energy saved by C-C
energy saved by A1R
energy saved by B2 serialization
energy saved by WF200 3.18.0
```

---

# 59. Data Interpretation Rules

## Use

- voltage as the primary short-term battery trend
- percentage as secondary information
- exact firmware/build identity
- WF200 version
- physical device identity
- experiment interval
- uptime
- reboot/reconnect counters
- RSSI
- valve workload
- Recovery statistics
- raw cumulative counters
- long observation periods
- contemporaneous stock control
- explicit T0 records
- explicit recharge events
- explicit OTA boundaries
- separate API/external voltage sources
- B2.1_OBS first-fault telemetry if drain occurs

## Do Not

- convert Recovery occupancy into battery percentage
- convert Recovery counts directly into mAh
- treat `real_beacon_skip` as physical RF sleep telemetry
- treat `desired_beacon_skip` as physical listen-interval proof
- treat `sleep_ratio` as electrical duty cycle
- treat D3=0 as proof WF200 slept correctly
- mix external and API voltage in one curve
- compare devices solely by battery percentage
- extrapolate lifetime from a few hours
- ignore calibration or valve activity
- merge data across firmware changes
- assume equal battery capacity between devices
- claim mDNS is the root cause
- claim Beacon Recovery is the root cause
- claim WF200 3.18.0 fixes the battery problem
- claim A1R alone fixes the battery problem
- claim B2 serialization alone fixes the battery problem
- claim B2.1_OBS has solved drain from early data
- claim B2.2 has been hardware-qualified

---

# 60. Current Findings

The battery investigation currently supports the following conclusions.

### Drain existed before 2.2.4

Therefore the 2.2.4 Beacon Recovery implementation cannot explain the complete historical problem alone.

### Stock 2.2.4 can produce very frequent Beacon Recovery

Historical devices showed approximately:

```text
~60 Recoveries/hour
```

for extended periods.

### C1a/C1b/C2 are real host defects

C-C corrects these Recovery-evidence validity problems.

### C2 is metastable

The stale-evidence recurrence can persist for long periods but should not be described as necessarily permanent until reboot.

### C-C works on hardware

The corrected post-Recovery evidence lifecycle has been demonstrated physically.

### Fresh Recovery can still occur

Historical C-C-based periods produced approximately:

```text
27–30/hour
```

under specific test conditions.

### Patch B did not prevent `.77` discharge

The historical device reached approximately:

```text
9.23 days
0 %
3.116 V
12908 Recoveries
```

with targeted periodic mDNS suppression active.

### D3 does not explain historical recurring Recovery

Historical `.11` showed:

```text
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

### WF200 3.18.0 is technically relevant

It includes an official power-save-related vendor correction.

### FMAC 3.7.0 and WF200 3.18.0 operate together

This has been demonstrated on physical TRV hardware.

### Historical A1 integration worked

A1+C-C+WF200 3.18.0 successfully operated on `.234`.

### A1 was later superseded by A1R

An experimental temporary-policy regression was found and corrected.

### The B2 race is demonstrated

Bounded serialization is qualified and part of B2.1/B2.1_OBS.

### The current observer is qualified and deployed

B2.1_OBS is running on six physical corrected devices.

### B2.2 remains offline

It has not yet produced hardware battery data.

---

# 61. Current Research Questions

The main battery questions are now:

1. Do the six B2.1_OBS devices remain stable over long real-world runtime?

2. How do their voltage trajectories compare with stock `.97`?

3. Does the historical rapid-drain phenotype reappear on any corrected device?

4. If drain appears, what PM52/cmd66 state precedes or accompanies it?

5. Does any observed failure correlate with connection epochs, PM completion or fresh Beacon Recovery?

6. Does the stock control continue to show substantially different long-term voltage behavior?

7. How much of the historical drain remains after the demonstrated host and radio-side corrections?

8. If the corrected population remains stable, does the observer-free build reproduce that stability?

These questions are more valuable now than introducing another Recovery-rate or WF200 variant.

---

# 62. Current Conclusion

The Shelly TRV Gen1 battery investigation has moved beyond simple comparisons of displayed percentage.

Historical work established:

```text
drain before 2.2.4
+
mDNS isolation
+
Beacon Recovery isolation
+
C1a/C1b/C2
+
D3 observation
+
WF200 3.18.0 integration
+
A1 lifecycle corrections
+
A1R correction
+
B2 race correction
```

The active hardware experiment now uses:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The corrected devices combine:

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
+
PM52 -> cmd66 observer
```

The project is deliberately not changing those devices while the long-term test runs.

The current decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

Early corrected-device behavior is encouraging but is not sufficient to establish battery lifetime.

If B2.1_OBS drains, first-fault telemetry becomes the next reverse-engineering input.

If B2.1_OBS remains stable, the next step is:

```text
remove observer
-> requalify observer-free build
-> hardware regression
-> evaluate final candidate
```

B2.2 remains an offline-qualified candidate and is not part of the current hardware experiment.

No claim is currently made that the historical Shelly TRV Gen1 battery-drain root cause has been proven.

---

# Related Documents

Experimental device matrix:

[`experimental-device-matrix.md`](experimental-device-matrix.md)

Power-management analysis:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Host sleep and blocker accounting:

[`../reverse-engineering/host-sleep-and-blocker-accounting.md`](../reverse-engineering/host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

[`../reverse-engineering/pm-lifecycle-and-a1.md`](../reverse-engineering/pm-lifecycle-and-a1.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

`real_beacon_skip`:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon RX counter:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

WF200 firmware:

[`../reverse-engineering/wf200-firmware.md`](../reverse-engineering/wf200-firmware.md)

Firmware comparison:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

Periodic mDNS:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

mDNS runtime comparison:

[`mdns-runtime-comparison.md`](mdns-runtime-comparison.md)

Patch documentation:

[`../patch/README.md`](../patch/README.md)

---

# Methodology Note

The battery investigation uses telemetry and runtime behavior from personally owned Shelly TRV Gen1 devices.

The dataset is observational.

It is not a laboratory-grade electrical characterization.

The project deliberately separates:

```text
observed battery behavior
```

from:

```text
demonstrated firmware behavior
```

and from:

```text
hypotheses about electrical energy consumption
```

Raw observations should be retained so that battery conclusions can be revisited as the firmware model improves.

Firmware identity, device identity, experiment interval and measurement source should always accompany the observation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

All product names and trademarks belong to their respective owners.

Experimental firmware modifications are intended for controlled research on personally owned hardware.

Battery observations do not constitute manufacturer specifications or guaranteed battery-life results.