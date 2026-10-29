# Experimental Device Matrix

This document tracks the Shelly TRV Gen1 devices used during the investigation and the firmware configurations tested on them.

The device address is only an identifier for a physical test unit.

It must not be treated as a permanent firmware label.

Several devices were reflashed repeatedly during the investigation, and at least one physical device changed its DHCP address.

Results must therefore always be associated with:

```text
physical device
+
firmware configuration
+
experiment period
```

rather than with the IP address alone.

---

# 1. Purpose

The investigation uses several physical Shelly TRV Gen1 units to separate different parts of the battery-drain problem.

Historical and current experiment classes include:

- stock firmware references
- mDNS-isolation builds
- Beacon Recovery isolation
- C-C Beacon Recovery correction
- D3 instrumentation
- WF200 firmware experiments
- A1 host-PM lifecycle correction
- A1R lifecycle correction
- B2 host sleep-blocker correction
- PM52→cmd66 instrumentation
- integrated B2.1/B2.1_OBS builds
- stock 2.2.4 long-term control

The device matrix is not a laboratory current-consumption benchmark.

The devices operate under real:

- WLAN conditions
- Shelly Cloud activity
- thermostat demand
- valve movement
- environmental temperature
- battery state
- heating-system operation

Battery percentage and voltage must therefore be interpreted together with firmware identity, uptime, valve activity, network behavior and relevant runtime counters.

---

# 2. Device Identity vs. Firmware Identity

A physical TRV may appear in multiple experiments.

For example:

```text
physical device
    |
    v
stock firmware
    |
    v
patched firmware
    |
    v
instrumented firmware
    |
    v
different corrected firmware
```

An IP address can also change because of DHCP.

Consequently, statements such as:

> ".77 is the mDNS device"

are only correct for a defined experiment period.

Preferred descriptions are:

> "TRV .77 during the historical 2.2.4 + Patch B experiment"

or:

> "TRV .77 currently running B2.1_OBS"

The firmware configuration is part of the experimental identity.

---

# 3. Current Active Long-Term Population

The current active hardware experiment is:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The current devices are:

| Device | Current firmware | Current role |
|---|---|---|
| `.77` | B2.1_OBS | corrected long-term test |
| `.88` | B2.1_OBS | corrected long-term test |
| `.11` | B2.1_OBS | corrected long-term test |
| `.71` | B2.1_OBS | corrected long-term test |
| `.234` | B2.1_OBS | corrected long-term test |
| `.61` | B2.1_OBS | corrected long-term test |
| `.97` | stock 2.2.4 | stock long-term control |

This is the most important current comparison.

Historical configurations of the same devices remain documented below.

---

# 4. Current Experimental Decision

The current project phase is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

During this phase:

- no new firmware variants should be introduced into the active population
- no deliberate AP/network variable should be changed
- B2.2 should not yet be flashed onto the active hardware
- no new Recovery-rate experiment should be started
- no new root-cause hypothesis should replace observation without fresh evidence

The current objective is long-term comparative hardware evidence.

---

# 5. Historical Device Overview

The following table summarizes important historical configurations.

| Device | Historical configurations | Main historical purpose |
|---|---|---|
| `.11` | stock 2.1.0; 2.2.4_D3 | historical drain reference; D3 observer |
| `.77` | stock 2.1.3; later Patch B | mDNS isolation with stock Beacon Recovery |
| `.88` | 2.2.4 + C-C | C-C long-term reference; Cloud experiment |
| `.229` | stock 2.1.8; later stock 2.2.4 | stock firmware reference |
| `.226` | Recovery suppression + mDNS suppression | historical combined isolation |
| `.228` / `.233` | same physical device | C-C development/reference |
| `.234` | C-C+MIN80; WF200 3.18.0; historical A1+C-C+WF200 3.18.0 | radio/integration canary |
| `.235` | insufficiently documented | not used for strong conclusions |
| `.237` | C-C + WF200 3.18.0 | C-C/new-radio comparison |
| `.71` | later B2.1_OBS | current corrected long-term population |
| `.61` | later B2.1_OBS | current corrected long-term population |
| `.97` | stock 2.2.4 | current stock control |

Historical roles and current roles must not be mixed.

---

# 6. TRV `.11`

## 6.1 Historical Stock 2.1.0 Reference

TRV `.11` was an important early stock reference running firmware:

```text
2.1.0
```

Battery drain was observable on this older generation.

This is important because the later 2.2.4 Beacon Recovery implementation cannot by itself explain the complete historical TRV battery-drain problem.

The observation supports separating:

1. mechanisms shared across firmware generations
2. 2.2.4-specific amplifiers
3. later Beacon Recovery behavior
4. unrelated normal device activity

It does not identify the root cause by itself.

---

## 6.2 Historical 2.2.4_D3 Observer

The same physical device was later reflashed with the dedicated:

```text
2.2.4_D3
```

observer build.

Purpose:

- preserve normal 2.2.4 Recovery behavior
- observe WF200 `PS_MODE_ERROR`
- classify D3 reason codes
- compare D3 events with host Beacon Recovery

A representative long-running state was approximately:

```text
uptime        ~63.9 h
battery       43 %
voltage       3.481 V
desired skip  20
real skip     1
beacon_err    3835
D3_total      0
```

The strongest result is:

```text
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR events
```

This demonstrates that the observed recurring Shelly Recovery behavior was not simply a direct reaction to the known WF200 D3 error channel.

It does not prove that no other radio-side PM problem existed.

---

## 6.3 Current `.11`

TRV `.11` is now part of the active:

```text
B2.1_OBS
```

long-term test population.

Its historical D3 result remains valid historical evidence.

The current B2.1_OBS period must not be mixed with the old D3-observer period.

---

# 7. TRV `.77`

TRV `.77` has had several important roles.

---

## 7.1 Earlier Stock 2.1.3

During earlier testing, `.77` ran:

```text
2.1.3
```

Example:

```text
battery   99 %
voltage   3.909 V
```

Measurements from that period belong to the old stock comparison.

---

## 7.2 Historical Patch B Experiment

The same physical device later ran:

```text
host firmware      2.2.4
mDNS modification  Patch B
Beacon Recovery    stock behavior retained
```

Patch B suppresses the targeted periodic mDNS behavior but leaves stock Beacon Recovery active.

The device later reached full discharge at approximately:

```text
battery          0 %
voltage          3.116 V
uptime           ~9.23 days
reconnects       30
desired skip     15
real skip        1
beacon_err       12908
recovery rate    ~58.3 / h
```

The supported conclusion is:

> suppressing the targeted periodic mDNS behavior did not prevent the observed drain on this device.

That does not mean mDNS has zero energy cost.

It means the targeted mDNS mechanism was not sufficient to explain this drain episode.

---

## 7.3 Current `.77`

TRV `.77` now runs:

```text
B2.1_OBS
```

as part of the current long-term population.

Therefore `.77` must no longer be described simply as "the Patch B device".

---

# 8. TRV `.88`

## 8.1 Historical C-C Reference

TRV `.88` was an important long-term C-C reference.

Historical configuration:

```text
host firmware   2.2.4 + C-C
WF200           3.16.1
MIN80           absent
D3 observer     absent
```

Representative earlier state:

```text
battery        60 %
voltage        3.594 V
desired skip   20
real skip      4
beacon_err     0
sleep_ratio    0.016871
```

C-C corrects C1a/C1b/C2 while retaining fresh valid Beacon Recovery.

---

## 8.2 Historical Cloud-Off Experiment

`.88` was also used for a Cloud-on/Cloud-off comparison.

A Cloud-on reference included approximately:

```text
RSSI           -54 dBm
cloud          connected
battery        78 %
voltage        3.709 V
uptime         ~1,148,621 s
reboot         1
reconnect      33
sleep_ratio    0.017023
desired skip   20
real skip      7
beacon_err     0
valve          4.6 %
target         16.5 °C
temperature    15.6 °C
```

Cloud was then disabled without reboot.

The purpose was to separate normal Shelly Cloud activity from Beacon Recovery behavior.

Battery voltage alone cannot determine Cloud influence.

---

## 8.3 Current `.88`

TRV `.88` now runs:

```text
B2.1_OBS
```

within the current six-device corrected population.

Its earlier C-C and Cloud experiments remain historical comparisons only.

---

# 9. TRV `.229`

TRV `.229` was used as a stock reference across firmware generations.

---

## 9.1 Stock 2.1.8

Earlier configuration:

```text
2.1.8
```

Example:

```text
battery   100 %
voltage   4.157 V
uptime    65,437 s
```

The older firmware does not expose the richer later `/stats` telemetry.

Missing counters must therefore not be interpreted as zero.

---

## 9.2 Stock 2.2.4

The same physical device later ran stock:

```text
2.2.4
```

Representative state:

```text
uptime         ~62.5 h
desired skip   20
real skip      2
beacon_err     ~3282
sleep_ratio    0.021028
```

This corresponds to approximately:

```text
~52.5 Recoveries/hour
```

during that interval.

This is useful historical stock behavior.

Recovery frequency alone is not a current measurement.

---

# 10. TRV `.226`

TRV `.226` ran an early combined experimental patch that suppressed:

- the targeted Beacon Recovery path
- the targeted mDNS behavior

This predates C-C.

It must not be described as C-C.

The `.226` experiment answers a broad isolation question:

```text
What happens when both targeted mechanisms
are suppressed?
```

C-C answers a different question:

```text
How should Beacon Recovery evidence
be corrected while retaining fresh Recovery?
```

Results from `.226` therefore remain historical isolation data.

---

# 11. TRV `.228` → `.233`

`.228` and `.233` refer to the same physical device.

The DHCP address changed:

```text
old address   192.168.178.228
new address   192.168.178.233
```

Historical screenshots and logs can therefore contain either identifier.

They must not be counted as two independent devices.

This TRV was used during C-C development and reference testing.

The relevant experiment/build identity should be used whenever possible instead of relying solely on the address.

---

# 12. TRV `.234`

TRV `.234` was used for several major development stages.

Its historical configurations must remain separated.

---

## 12.1 Historical C-C + MIN80

An earlier build combined:

```text
C-C
+
MIN80
```

Representative state:

```text
battery       49 %
voltage       3.520 V
desired skip  20
real skip     1
beacon_err    464
```

This must not be interpreted as C-C-only behavior.

MIN80 was a separate experimental modification.

---

## 12.2 Standalone WF200 3.18.0 Experiment

`.234` was then used to test official Silicon Labs:

```text
WF200 3.18.0
```

with Shelly:

```text
FMAC 3.7.0
```

The device successfully completed:

- OTA
- cold reboot
- WF200 initialization
- WLAN
- DHCP
- Cloud
- power-save operation

Representative early state:

```text
battery       77 %
voltage       3.704 V
desired skip  20
real skip     1
beacon_err    2
```

This demonstrated practical interoperability between Shelly FMAC 3.7.0 and WF200 3.18.0.

It did not establish a battery fix.

---

## 12.3 Historical A1 + C-C + WF200 3.18.0

`.234` later became the canary for the historical integrated build:

```text
2.2.4 base
+
A1
+
C-C
+
WF200 3.18.0
```

Artifact:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

GBL SHA-256:

```text
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379
```

Application SHA-256:

```text
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The firmware successfully exercised:

- FMAC 3.7.0
- WF200 3.18.0
- WLAN association
- DHCP
- Cloud
- PM operation
- thermostat function
- valve movement
- calibration

This remains important historical evidence.

It must not be relabeled as A1R or B2.1.

---

## 12.4 Historical Integrated-Build T0

Immediately before the historical A1 integrated flash, `.234` was running stock 2.2.4 host behavior with WF200 3.18.0.

The API reference state was approximately:

```text
RSSI           -66 dBm
cloud          connected
valve          100 %
target         26.0 °C
temperature    22.4 °C

battery        66 %
voltage        3.630 V

uptime         187489 s
ps_mode        0

reboot         1
reconnect      1

desired skip   20
real skip      1
beacon_err     3124
beacon_rx      1649784
missed         16727
sleep_ratio    0.019924

WF200          3.18.0
```

The firmware-reported:

```text
3.630 V
```

is the historical experiment T0.

---

## 12.5 Historical A1 Integrated Runtime

Approximately 17.7 minutes after boot:

```text
uptime         1060 s
sleep_ratio    0.019083
desired skip   20
real skip      1
beacon_err     9
```

Approximately 7.94 hours:

```text
battery        62 %
voltage        3.609 V
desired skip   15
real skip      13
beacon_err     217
```

Approximately 24 hours:

```text
battery        52 %
voltage        3.542 V
desired skip   20
real skip      1
beacon_err     660
```

Approximately 32.44 hours:

```text
reboot         1
reconnect      3
uptime         116794 s
sleep_ratio    0.020475
desired skip   15
real skip      12
beacon_err     909
```

Historical fresh Recovery rate remained roughly:

```text
27–28/hour
```

under that configuration.

Because C-C was active, these events did not represent the stock C2 stale-evidence pattern.

---

## 12.6 Historical WLAN Steering Experiment

FRITZ! Mesh/Band Steering was disabled during the historical `.234` experiment.

Fresh Recovery continued.

Therefore the tested Mesh/Band-Steering behavior was not required for those events.

This does not exclude all AP-side effects.

---

## 12.7 Historical Valve-State Observation

During the same experiment, target temperature changed approximately:

```text
25 °C -> 15 °C
```

and valve position approximately:

```text
100 % -> 0 %
```

During a later closed-valve interval:

```text
3.540 V -> 3.537 V
```

over approximately 7 h 52 min while fresh Recovery remained in a similar frequency range.

This is useful evidence that Recovery frequency is not a direct linear battery-current measurement.

---

## 12.8 Current `.234`

TRV `.234` now runs:

```text
B2.1_OBS
```

as part of the six-device long-term corrected population.

Its current role is no longer "A1 integrated canary".

---

# 13. TRV `.237`

TRV `.237` was historically used with:

```text
2.2.4 + C-C
+
WF200 3.18.0
```

This separated:

```text
C-C + new radio
```

from the additional A1 changes present on historical `.234`.

Fresh Recovery remained observable in roughly the same order of magnitude during representative intervals.

The supported conclusion was:

> removing the demonstrated stale host Recovery defect does not automatically eliminate every later fresh Recovery event.

`.237` is not part of the current seven-device active population documented here.

---

# 14. TRV `.71`

TRV `.71` is part of the current corrected hardware population.

Current firmware:

```text
B2.1_OBS
```

Current role:

```text
long-term corrected device
```

No historical experiment described in this matrix should be inferred solely from the address.

---

# 15. TRV `.61`

TRV `.61` is part of the current corrected hardware population.

Current firmware:

```text
B2.1_OBS
```

Current role:

```text
long-term corrected device
```

Its purpose is to increase the number of independently operating corrected devices in the long-term comparison.

---

# 16. TRV `.97`

TRV `.97` is the current active stock control.

Configuration:

```text
stock Shelly 2.2.4
FMAC 3.7.0
WF200 3.16.1
```

Current role:

```text
stock long-term control
```

Early observation showed stock Beacon Recovery behavior with accumulated `beacon_err` values while the initial B2.1_OBS devices remained at zero during the same early phase.

This is preliminary.

It must not be treated as a battery-lifetime result.

---

# 17. Major Firmware Variants

## 17.1 Stock Firmware

Relevant stock generations include:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

Battery drain was observed across more than one generation.

Therefore 2.2.4-specific behavior cannot automatically be treated as the complete historical cause.

---

## 17.2 Patch B

Historical primary device:

```text
.77
```

Purpose:

```text
suppress targeted mDNS activity
retain stock Beacon Recovery
```

The device still discharged.

This demonstrated that the targeted mDNS behavior alone was insufficient to explain the observed drain.

---

## 17.3 Earlier Recovery + mDNS Suppression

Historical primary device:

```text
.226
```

Purpose:

```text
suppress targeted Beacon Recovery
+
suppress targeted mDNS
```

This was a broad isolation experiment.

It predates C-C.

---

## 17.4 C-C

C-C corrects:

```text
C1a signed interpretation
C1b invalid measurement windows
C2 stale Recovery evidence
```

while retaining fresh valid Recovery.

Historical representative devices included:

```text
.88
.233
.237
.234 in selected configurations
```

C2 should be described as a metastable stale-evidence recurrence, not as a guaranteed permanent loop.

---

## 17.5 MIN80

MIN80 was used in some earlier experimental builds.

It is not part of:

```text
B2.1
B2.1_OBS
B2.2
```

Historical C-C+MIN80 data must therefore not be described as C-C-only or current corrected-build data.

---

## 17.6 Historical D3 Observer

Historical primary device:

```text
.11
```

Purpose:

```text
observe WF200 PS_MODE_ERROR
while retaining normal host Beacon Recovery
```

Major result:

```text
3835 Beacon Recoveries
D3_total = 0
```

during the long observation.

---

## 17.7 WF200 3.18.0

WF200 3.18.0 is official Silicon Labs radio firmware experimentally integrated with Shelly FMAC 3.7.0.

Historical devices included:

```text
.234
.237
```

It is also part of all current B2.1-family corrected builds.

The update is technically relevant because Silicon Labs documents a power-save-mode-change sleep fix.

It is not a demonstrated complete battery-drain fix.

---

## 17.8 Historical A1

A1 corrected demonstrated host PM lifecycle defects.

Historical integrated testing used:

```text
A1
+
C-C
+
WF200 3.18.0
```

primarily on `.234`.

A1 was later found to contain an experimental regression in verified temporary PM override paths.

Historical A1 measurements remain valid under the A1 label.

---

## 17.9 A1R

A1R supersedes A1.

It retains the A1 lifecycle corrections while fixing the experimental temporary-override regression.

Qualification included:

```text
151 / 151 Thumb behavior tests PASS
```

A1R is part of:

```text
B2.1
B2.1_OBS
B2.2
```

---

## 17.10 B2 Serialization

A separate host sleep audit demonstrated a shared B2 reference-counter race.

The corrected design uses bounded serialization of complete B2 read-modify-write operations.

It preserves reference-count semantics.

It is included in:

```text
B2.1
B2.1_OBS
B2.2
```

The B2 correction is separate from A1R and from WF200 firmware.

---

# 18. B2.1

B2.1 is the corrected observer-free baseline:

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

B2.1 is the corrected observer-free baseline underlying the current observer build.

---

# 19. PM52→cmd66 Observer

The current observer records already-existing PM/statistics activity.

It records:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing command-0x66 requests/results
- estimator operands
- connection epochs
- compact recent-event history
- first-fault freeze state

It adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
additional WF200 request
```

This replaces the earlier conceptual "future Stock Host Observer" direction.

The current observer exists, is qualified and is already running on hardware.

---

# 20. B2.1_OBS

B2.1_OBS is:

```text
B2.1
+
PM52->cmd66 observer
```

Research identity:

```text
research_build: B2.1_OBS
```

Status/readout identifier:

```text
pm52_cmd66
```

Qualification includes:

```text
A1R:
151 / 151

observer/readout:
356 / 356

B2:
2060 + 102
plus mixed/preemption qualification

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

This means qualified for controlled long-term hardware testing.

It does not mean:

```text
production firmware
```

or:

```text
battery-drain root cause proven
```

---

# 21. B2.1_OBS Artifact

Artifact:

```text
builds/firmware/B2.1_OBS/SHTRV-01_2.2.4_B2.1_OBS_EXPERIMENTAL.gbl
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

The native Shelly firmware version remains 2.2.4.

Research identity is therefore necessary when comparing test devices.

---

# 22. B2.2

B2.2 is the later observer-free integrated candidate containing nine selected qualified corrections:

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

Disposition:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

No physical TRV was contacted during B2.2 qualification.

Therefore:

```text
offline-qualified
```

does not mean:

```text
hardware-qualified
```

B2.2 is deliberately not part of the current active hardware matrix.

---

# 23. Current Active Comparison

The current useful comparison is now:

| Device | Build | WF200 | Role |
|---|---|---|---|
| `.77` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.88` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.11` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.71` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.234` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.61` | B2.1_OBS | 3.18.0 | corrected long-term |
| `.97` | stock 2.2.4 | 3.16.1 | stock control |

This supersedes the earlier current comparison involving D3, standalone C-C, `.237` and the historical A1 canary.

Those older comparisons remain historically useful but are no longer the active long-term test matrix.

---

# 24. Early Current Observation

During the initial B2.1_OBS observation period:

```text
B2.1_OBS devices:
beacon_err = 0
```

while the stock `.97` control had accumulated thousands of Beacon Recovery errors.

One stock interval also showed approximately minute-scale Recovery recurrence, although another overnight interval showed only a small increase.

This is important because it demonstrates that stock behavior itself is not necessarily constant over every observation interval.

The current evidence is therefore classified as:

```text
early observation
```

not:

```text
lifetime result
```

---

# 25. What the Historical Matrix Has Established

Several historical comparisons remain strong.

## mDNS alone

`.77` drained with the targeted mDNS behavior suppressed.

Therefore the targeted periodic mDNS mechanism was not sufficient to explain that drain episode.

---

## Stock Beacon Recovery

Stock 2.2.4 can produce very frequent Beacon Recovery.

Historical examples include `.229`, `.11` D3 and earlier `.234`.

Recovery frequency alone does not quantify energy consumption.

---

## D3

Historical `.11` demonstrated:

```text
thousands of host Beacon Recoveries
0 D3 PS_MODE_ERROR
```

The host Recovery mechanism is therefore not simply a direct D3 handler.

---

## C-C

C-C corrects demonstrated Recovery-evidence defects.

It retains later fresh valid Recovery.

Historical fresh rates around 27–30/hour are measurements from particular experiments, not universal C-C behavior.

---

## WF200 3.18.0

WF200 3.18.0 operates with Shelly FMAC 3.7.0 on physical TRV hardware.

It does not by itself establish a complete battery-drain fix.

---

## Historical A1

A1 demonstrated successful host PM lifecycle correction integration on physical hardware.

It was later superseded by A1R after an experimental regression was found.

---

## B2

The B2 task-preemption defect is demonstrated and the bounded serialization correction is qualified.

The current active corrected builds include that correction.

---

# 26. What the Current Matrix Is Testing

The current six-versus-one experiment asks a narrower question:

> After integrating the demonstrated and qualified corrections into B2.1_OBS, do corrected devices still develop the historical rapid battery drain under normal real-world operation?

The current design intentionally combines several corrections.

It is therefore not intended to isolate the energy contribution of each individual fix.

Instead it tests the corrected platform as a whole.

---

# 27. If a B2.1_OBS Device Drains

If one of the corrected devices develops genuine drain:

```text
detect abnormal voltage/runtime behavior
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
correlate PM completion behavior
        |
        v
resume deeper reverse engineering
```

This is why the current observer is useful.

A drain event becomes diagnostic evidence rather than merely a voltage graph.

---

# 28. If B2.1_OBS Remains Stable

If the corrected population remains stable over the required long-term period:

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
evaluate final firmware candidate
```

The observer is diagnostic instrumentation.

It should not automatically become part of a final candidate.

---

# 29. What the Matrix Does Not Prove

The device matrix does not establish:

- the complete historical root cause
- electrical current consumption of any individual code path
- physical WF200 sleep residency
- physical EFM32 EM1/EM2 residency
- a fixed energy cost per Beacon Recovery
- that all devices experience the same failure mode
- that good RSSI prevents Recovery
- that WF200 3.18.0 alone fixes battery drain
- that C-C alone fixes battery drain
- that A1R alone fixes battery drain
- that B2 serialization alone fixes battery drain
- that early B2.1_OBS stability proves lifetime success
- that B2.2 is hardware-qualified
- that one stock-control interval represents all stock behavior

Those questions require longer runtime evidence and, for energy attribution, direct electrical measurements.

---

# 30. Battery Percentage vs. Voltage

Displayed battery percentage is not a coulomb counter.

The firmware derives it from cached battery voltage through a stateless integer mapping.

The investigation therefore records both:

```text
battery percentage
battery voltage
```

together with:

- uptime
- reboot count
- reconnect count
- valve activity
- WLAN state
- Beacon Recovery counters
- desired and derived beacon skip
- firmware configuration

For short-term comparison, voltage is generally more informative than percentage.

Voltage itself still varies with:

- load
- valve movement
- temperature
- recent charging
- battery relaxation
- radio activity

Longer intervals are therefore more useful than isolated measurements.

---

# 31. Valve Activity as a Confounder

Valve motor activity can be a significant battery load.

Comparisons should account for:

- calibration
- large valve travel
- target-temperature changes
- heating demand
- repeated repositioning

A device that recently performed calibration cannot be compared directly with a stationary control using only a short voltage interval.

---

# 32. `/stats` Availability

The richer `/stats` endpoint is available on relevant later 2.2.4 builds.

Older firmware versions do not expose identical telemetry.

Therefore:

```text
counter absent
```

must not be interpreted as:

```text
counter = 0
```

This applies especially to older 2.1.x reference measurements.

---

# 33. `sleep_ratio`

The reported:

```text
sleep_ratio
```

is useful telemetry but is not physical sleep residency.

Reverse engineering indicates that it is associated with tickless timing/compensation behavior.

It does not directly measure:

```text
EFM32 EM1 duration
EFM32 EM2 duration
WF200 radio sleep duration
```

The detailed host sleep model is documented in:

[`../reverse-engineering/host-sleep-and-blocker-accounting.md`](../reverse-engineering/host-sleep-and-blocker-accounting.md)

---

# 34. Experiment Interpretation

When comparing two device records, the preferred sequence is:

1. identify exact firmware/build
2. identify physical device
3. identify experiment period
4. compare relevant host/radio behavior
5. compare uptime and operating conditions
6. account for valve/calibration activity
7. compare voltage over a meaningful interval
8. use battery percentage as secondary information
9. avoid assigning causality from one counter

An IP address alone is not sufficient experiment metadata.

---

# 35. Historical Results Must Retain Their Original Build Names

This is especially important for:

```text
A1
A1R
B2
B2_OBS
B2.1
B2.1_OBS
B2.2
```

Historical A1 measurements must not be renamed to A1R.

Historical B2 measurements must not be renamed to B2.1.

The progression reflects actual firmware evolution and is part of the evidence.

---

# 36. Related Documentation

Host sleep and blocker accounting:

[`../reverse-engineering/host-sleep-and-blocker-accounting.md`](../reverse-engineering/host-sleep-and-blocker-accounting.md)

Host PM lifecycle and A1/A1R:

[`../reverse-engineering/pm-lifecycle-and-a1.md`](../reverse-engineering/pm-lifecycle-and-a1.md)

WF200 firmware:

[`../reverse-engineering/wf200-firmware.md`](../reverse-engineering/wf200-firmware.md)

Beacon estimator:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Recovery behavior:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

Beacon receive counter:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

Firmware comparison:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

mDNS analysis:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

Battery testing:

[`battery-testing.md`](battery-testing.md)

mDNS runtime comparison:

[`mdns-runtime-comparison.md`](mdns-runtime-comparison.md)

Patch overview:

[`../patch/README.md`](../patch/README.md)

---

# 37. Current Conclusion

The physical-device matrix shows that the Shelly TRV Gen1 battery-drain problem cannot be reduced to one counter or one firmware mechanism.

Historical experiments established that:

- drain existed before firmware 2.2.4
- targeted mDNS suppression alone did not prevent drain
- stock 2.2.4 Beacon Recovery can run very frequently
- recurring Beacon Recovery did not require observed D3 `PS_MODE_ERROR`
- C-C corrects real Recovery-evidence defects
- fresh Recovery can still occur after C-C
- WF200 3.18.0 operates successfully with Shelly FMAC 3.7.0
- WF200 3.18.0 does not by itself eliminate all fresh Recovery
- WLAN steering is not required for historical fresh Recovery
- short-term voltage does not map simply to Recovery frequency
- historical A1 integration operated successfully on physical hardware
- A1 was later superseded by A1R
- the B2 reference-counter race is demonstrated and corrected

The current experiment has moved beyond the earlier one-device canary stage.

The active population is now:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The corrected devices contain:

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
PM52->cmd66 observer
```

The stock control remains unmodified 2.2.4 with WF200 3.16.1.

The current decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

Early B2.1_OBS behavior is encouraging but not sufficient for a battery-lifetime claim.

The next meaningful result must come from long-term hardware behavior:

```text
stable corrected population
```

or:

```text
drain episode with first-fault telemetry
```

Until then, the project does not claim that the historical battery-drain root cause has been proven.