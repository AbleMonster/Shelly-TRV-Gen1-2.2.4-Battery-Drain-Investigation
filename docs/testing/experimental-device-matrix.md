# Experimental Device Matrix

This document tracks the Shelly TRV Gen1 devices used during the investigation and the firmware configurations tested on them.

The device address is only an identifier for the physical test unit. It must not be treated as a permanent firmware label.

Several devices were reflashed during the investigation, and one device changed its DHCP address. Results should therefore always be associated with the firmware configuration and experiment period, not with the IP address alone.

---

## 1. Purpose

The investigation uses several physical TRV Gen1 units in parallel to separate different parts of the battery-drain problem.

The main comparison groups are:

- stock firmware references,
- mDNS-isolation builds,
- Beacon Recovery modifications,
- C-C builds,
- D3 instrumentation,
- WF200 firmware experiments,
- A1 host power-management corrections,
- combined experimental builds.

This allows individual mechanisms to be changed while other parts of the firmware remain as close to stock as possible.

The matrix is not a controlled laboratory battery benchmark. The devices operate under real WLAN, valve, cloud and environmental conditions.

Battery percentage and voltage therefore need to be interpreted together with firmware state, uptime, valve activity, WLAN behavior and the relevant runtime counters.

---

# 2. Device identity and firmware identity

A physical TRV may appear in several experiments.

For example:

```text
physical device
    ↓
stock firmware
    ↓
patched firmware
    ↓
different experimental firmware
```

The IP address may also change because of DHCP.

Consequently, statements such as:

> ".77 is the mDNS device"

are only valid for a specific experiment period.

The preferred form is:

> "TRV .77 running 2.2.4 + Patch B"

or:

> "TRV .234 running A1 + C-C + WF200 3.18.0"

where the firmware configuration is explicit.

---

# 3. Device overview

| Device | Important configurations used | Main purpose |
|---|---|---|
| `.11` | stock 2.1.0; later 2.2.4_D3 | historical drain reference and D3 observer |
| `.77` | stock 2.1.3 during earlier testing; later 2.2.4 + Patch B | mDNS isolation with stock Beacon Recovery |
| `.88` | 2.2.4 + C-C | C-C long-term reference |
| `.229` | stock 2.1.8; later stock 2.2.4 | stock firmware reference |
| `.226` | Beacon-Recovery suppression + mDNS suppression | earlier combined host-patch experiment |
| `.228` / `.233` | same physical device under different DHCP addresses | C-C development/reference testing |
| `.234` | C-C + MIN80; WF200 3.18.0 experiment; later A1 + C-C + WF200 3.18.0 | radio and integrated host/radio testing |
| `.235` | configuration not sufficiently documented here | not used for conclusions in this document |
| `.237` | C-C + WF200 3.18.0 | combined C-C/radio reference |

This table summarizes roles only. The sections below contain the experiment-specific context.

---

# 4. TRV `.11`

## 4.1 Earlier stock 2.1.0 reference

TRV `.11` was used as an important early stock reference with host firmware 2.1.0.

Battery drain was already observable on this older firmware generation.

This matters because the later 2.2.4 Beacon Recovery implementation cannot by itself explain the complete historical battery-drain problem.

The observation supports separating:

1. mechanisms shared between older and newer firmware,
2. 2.2.4-specific amplifiers,
3. later recovery logic,
4. unrelated normal activity.

It does not identify the root cause by itself.

---

## 4.2 2.2.4_D3 observer

The device was later reflashed with the 2.2.4_D3 observer build.

Purpose:

- retain the 2.2.4 host behavior,
- observe WF200 `PS_MODE_ERROR` indications,
- classify D3 reason codes,
- compare D3 events with host Beacon Recovery.

The observer records the WF200 D3 reason classes without changing the normal recovery policy.

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

The important result is not the battery percentage itself.

During this observation, thousands of host Beacon Recovery events occurred while the D3 observer recorded no `PS_MODE_ERROR`.

Therefore:

> the observed 2.2.4 Beacon Recovery loop is not simply a direct response to WF200 D3 `PS_MODE_ERROR` events.

This does not prove that no other WF200 internal condition contributes to the drain.

---

# 5. TRV `.77`

TRV `.77` is especially important because its firmware changed during the investigation.

Older captures and measurements must not be mixed with the later Patch B experiment.

---

## 5.1 Earlier 2.1.3 reference

During earlier testing, `.77` ran stock 2.1.3.

Measurements from that period belong to the older stock-firmware comparison and must not be interpreted as Patch B results.

Example from the earlier period:

```text
firmware  2.1.3
battery   99 %
voltage   3.909 V
```

This configuration was later replaced.

---

## 5.2 2.2.4 + Patch B

The same physical device was later used with:

```text
host firmware     2.2.4
mDNS modification Patch B
Beacon Recovery   stock behavior retained
```

Patch B suppresses the targeted mDNS activity under investigation but does not apply C-C and does not suppress the stock Beacon Recovery mechanism.

This makes `.77` useful for separating mDNS activity from the recurring recovery behavior.

The device eventually reached full discharge with approximately:

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

The result is important:

> suppressing the targeted mDNS behavior did not prevent the battery drain.

At the same time, stock Beacon Recovery remained very frequent.

This does not prove that mDNS has zero energy cost. It shows that the targeted mDNS activity was not sufficient to explain the observed drain on this device.

---

# 6. TRV `.88`

TRV `.88` is the main long-term C-C reference using the stock WF200 generation.

Configuration:

```text
host firmware   2.2.4 + C-C
WF200           3.16.1
MIN80           absent
D3 observer     absent
```

C-C corrects the stale/signed/invalid-window behavior in the host Beacon Recovery decision while retaining recovery for a fresh valid estimator condition.

It does not disable recovery globally.

A representative earlier state was:

```text
battery        60 %
voltage        3.594 V
desired skip   20
real skip      4
beacon_err     0
sleep_ratio    0.016871
```

The absence of `beacon_err` during this period contrasts strongly with stock 2.2.4 devices repeatedly entering the recovery path.

---

## 6.1 Cloud-off experiment

`.88` was also used for a Cloud-on/Cloud-off comparison.

Cloud-on reference:

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

Cloud was then disabled without rebooting the device.

Cloud-off T0:

```text
battery        78 %
voltage        3.709 V
uptime         1,148,754 s
cloud          disabled
```

The purpose of this experiment is to separate normal Shelly Cloud activity from the already corrected Beacon Recovery behavior.

Cloud state should not be inferred from battery voltage alone.

---

# 7. TRV `.229`

TRV `.229` has been used as a stock reference across different host firmware versions.

---

## 7.1 Stock 2.1.8

Earlier configuration:

```text
host firmware   2.1.8
```

Example measurement:

```text
battery   100 %
voltage   4.157 V
uptime    65,437 s
```

The older firmware does not expose all of the `/stats` telemetry available in 2.2.4.

---

## 7.2 Stock 2.2.4

The device was later updated to stock 2.2.4.

A representative state showed:

```text
uptime         ~62.5 h
desired skip   20
real skip      2
beacon_err     ~3282
sleep_ratio    0.021028
```

This corresponds to roughly:

```text
~52.5 recovery events / hour
```

and provides a useful stock comparison against C-C devices.

The high recovery count is an observation, not proof that every recovery event directly causes a fixed amount of battery loss.

---

# 8. TRV `.226`

TRV `.226` was used with an earlier combined experimental patch.

The relevant configuration suppresses:

- the targeted Beacon-Skip/Recovery path,
- the targeted mDNS behavior.

This predates the later C-C approach.

The distinction matters because this build should not be described as C-C.

C-C retains a fresh valid recovery condition and specifically corrects the host estimator/recovery decision. The earlier `.226` experiment was broader suppression intended to isolate behavior.

Results from `.226` are therefore useful as historical isolation data but should not be mixed with later C-C qualification.

---

# 9. TRV `.228` → `.233`

`.228` and `.233` refer to the same physical TRV.

The address changed because of a new DHCP assignment:

```text
old address   192.168.178.228
new address   192.168.178.233
```

Older documents, screenshots and logs may therefore refer to `.228`, while later material refers to `.233`.

They must not be counted as two independent devices.

This device was used during C-C development/reference testing.

Where a result depends on the exact firmware revision, the associated experiment or firmware artifact should be used rather than the IP address alone.

---

# 10. TRV `.234`

TRV `.234` has been used for several of the most important later experiments.

Its configuration changed substantially over time.

---

## 10.1 Earlier C-C + MIN80 configuration

An earlier experimental configuration combined C-C with MIN80.

A representative state before the later WF200 work was:

```text
battery       49 %
voltage       3.520 V
desired skip  20
real skip     1
beacon_err    464
```

This configuration should not be confused with the later radio-only or A1 integration experiments.

---

## 10.2 WF200 3.18.0 experiment

`.234` was then used to test the official Silicon Labs WF200 3.18.0 radio firmware while retaining the Shelly 2.2.4 host/FM​​AC generation.

The OTA completed successfully.

The resulting runtime initialized:

```text
FMAC    3.7.0
WF200   3.18.0
```

WLAN, DHCP, Cloud and power-save operation remained functional.

An early post-boot state was approximately:

```text
battery       77 %
voltage       3.704 V
desired skip  20
real skip     1
beacon_err    2
```

This demonstrated practical compatibility between Shelly's FMAC 3.7.0 host stack and WF200 3.18.0 on the TRV hardware.

It did not by itself establish a battery-drain fix.

---

## 10.3 A1 + C-C + WF200 3.18.0

`.234` was later selected as the canary for the integrated experimental firmware:

```text
2.2.4 host base
+ A1
+ C-C
+ WF200 3.18.0
```

The controlled-test artifact was:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

with:

```text
GBL SHA256
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379

Application SHA256
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The firmware booted successfully on the physical device.

Initialization included:

- FMAC 3.7.0,
- WF200 3.18.0,
- WLAN association,
- DHCP,
- Shelly Cloud,
- power-save operation.

---

## 10.4 Integrated-build T0

Immediately before flashing the integrated build, `.234` was running stock 2.2.4 host behavior with WF200 3.18.0.

The API reference state was:

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

The API value of **3.630 V** is the experiment T0.

An external voltage measured during charging is not used as the firmware-test baseline.

---

## 10.5 Integrated-build runtime

Approximately 17.7 minutes after boot:

```text
uptime         1060 s
sleep_ratio    0.019083
desired skip   20
real skip      1
beacon_err     9
```

This corresponds to approximately 30.6 recovery events per hour during the short initial interval.

At approximately 7.94 hours:

```text
battery        62 %
voltage        3.609 V
desired skip   15
real skip      13
beacon_err     217
```

Recovery rate was approximately 27.2 events per hour.

At approximately 24 hours:

```text
battery        52 %
voltage        3.542 V
desired skip   20
real skip      1
beacon_err     660
```

Recovery rate was approximately 27.5 events per hour.

At approximately 32.44 hours:

```text
reboot         1
reconnect      3
uptime         116794 s
sleep_ratio    0.020475
desired skip   15
real skip      12
beacon_err     909
```

The recovery rate remained close to 28 events per hour.

This is substantially below the approximately once-per-minute behavior observed on some stock configurations, but recovery clearly still occurs after C-C.

That is expected because C-C does not globally disable recovery.

---

## 10.6 WLAN steering experiment

FRITZ! Mesh/Band Steering was disabled during the `.234` experiment.

Recovery events continued.

This shows that WLAN steering is not required for the observed fresh recovery condition.

It does not exclude every possible AP-selection or roaming interaction.

---

## 10.7 Valve state and voltage behavior

During the same experiment, the target temperature was changed from approximately:

```text
25 °C → 15 °C
```

and the valve moved from approximately:

```text
100 % → 0 %
```

During a later overnight interval with the valve closed, voltage changed only approximately:

```text
3.540 V → 3.537 V
```

over roughly 7 h 52 min while the recovery rate remained in the same general range.

This is an important caution against treating recovery frequency as a direct linear battery-consumption metric.

The host and radio have multiple possible energy-consuming states, and the current telemetry does not directly measure electrical current or physical sleep residency.

---

# 11. TRV `.237`

TRV `.237` is used as a combined reference with:

```text
host firmware   2.2.4 + C-C
WF200           3.18.0
```

This separates the C-C + new-radio combination from the additional A1 host changes present on `.234`.

Fresh recovery behavior remains observable at roughly the same order of magnitude as the later `.234` experiment, around 30 events per hour during representative observation periods.

This supports the conclusion that:

> correcting the stale host recovery condition does not eliminate every fresh recovery event.

It does not establish whether those remaining events are harmful, necessary, or related to the historical drain mechanism.

---

# 12. Firmware variants used in the experiments

The device matrix is easier to interpret when the major firmware variants are treated separately.

---

## 12.1 Stock firmware

Stock builds provide the baseline behavior.

Relevant host generations include:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

Battery drain has been observed across more than one generation.

Therefore, later 2.2.4-specific mechanisms should not automatically be treated as the complete historical root cause.

---

## 12.2 Patch B

Patch B was used primarily on `.77`.

Purpose:

```text
suppress targeted mDNS activity
retain stock Beacon Recovery
```

The device still discharged while Beacon Recovery remained frequent.

---

## 12.3 Earlier Beacon-Recovery + mDNS suppression

Used on `.226`.

Purpose:

```text
suppress targeted recovery behavior
+
suppress targeted mDNS behavior
```

This was an isolation experiment and predates C-C.

It should not be described as equivalent to C-C.

---

## 12.4 C-C

C-C corrects the host-side recovery decision around the derived `real_beacon_skip` estimator.

It addresses:

- stale estimator reuse,
- signed-value behavior,
- invalid estimator windows.

It retains recovery when a fresh valid estimator condition requests it.

Representative devices:

```text
.88
.233
.237
.234 in some configurations
```

---

## 12.5 MIN80

MIN80 was used in some earlier experimental builds.

It is not part of the final A1 + C-C + WF200 3.18.0 integrated build.

Results from C-C + MIN80 must therefore not be treated as results from C-C alone.

---

## 12.6 D3 observer

The D3 observer was used on `.11`.

It records WF200 `PS_MODE_ERROR` information while leaving the relevant host recovery behavior available for comparison.

The major observed result was:

```text
many host Beacon Recovery events
D3_total = 0
```

during the measured interval.

---

## 12.7 WF200 3.18.0

WF200 3.18.0 is an official Silicon Labs radio firmware used experimentally with Shelly's existing FMAC 3.7.0 host stack.

Representative devices:

```text
.234
.237
```

Its use is documented separately in:

```text
docs/reverse-engineering/wf200-firmware.md
```

---

## 12.8 A1

A1 corrects a set of host-side asynchronous power-management lifecycle defects identified in 2.2.4.

It does not:

- globally replace the B2 blocker implementation,
- enable EM3,
- replace C-C,
- replace WF200 firmware.

The first integrated controlled device test combines:

```text
A1
+
C-C
+
WF200 3.18.0
```

on `.234`.

---

# 13. Current active comparison roles

At the current stage of the investigation, the most useful logical comparison is:

| Device | Host behavior | WF200 | Current role |
|---|---|---|---|
| `.11` | 2.2.4_D3, stock recovery/PM | 3.16.1 | D3 reference |
| `.88` | C-C | 3.16.1 | C-C long-term / Cloud experiment |
| `.229` | stock 2.2.4 | 3.16.1 generation | stock reference |
| `.234` | A1 + C-C | 3.18.0 | integrated canary |
| `.237` | C-C | 3.18.0 | C-C + new-radio reference |

`.77` remains valuable as a completed mDNS-isolation/full-discharge experiment rather than as the primary current live reference.

---

# 14. What the matrix currently tells us

Several comparisons are already useful.

### mDNS alone

`.77` continued to drain with the targeted mDNS behavior suppressed.

Therefore the targeted mDNS activity is not sufficient to explain the observed drain.

---

### Stock Beacon Recovery

Stock 2.2.4 devices can enter the Beacon Recovery path very frequently.

Examples include `.229` and the earlier `.234` host behavior.

However, recovery frequency alone has not been shown to map linearly to battery consumption.

---

### D3

`.11` demonstrated frequent host recovery without corresponding D3 `PS_MODE_ERROR` events during the observed interval.

The host recovery path is therefore not simply a direct D3 handler.

---

### C-C

C-C removes the stale/signed/invalid-window recovery behavior but does not eliminate all fresh recovery.

This is visible particularly when comparing `.88`, `.237` and the integrated `.234` experiment.

---

### WF200 3.18.0

The newer radio firmware operates successfully with Shelly FMAC 3.7.0 on physical TRV hardware.

Fresh recovery can still occur with WF200 3.18.0.

Therefore the radio update should not be described as a complete demonstrated drain fix.

---

### A1

A1 has successfully passed static qualification and has run on physical hardware as part of the integrated `.234` build.

Long-term runtime behavior remains more important than short initial voltage changes.

---

# 15. What the matrix does not prove

The device matrix does not establish:

- the complete historical root cause of the battery drain,
- electrical current consumption of any individual code path,
- physical WF200 sleep residency,
- physical EFM32 EM1/EM2 residency,
- a fixed energy cost per Beacon Recovery event,
- that every device experiences the same failure mode,
- that good RSSI prevents recovery,
- that WF200 3.18.0 alone fixes the drain,
- that C-C alone fixes the drain,
- that A1 alone fixes the drain.

These questions require correlation with the reverse-engineered host behavior and longer runtime observations.

---

# 16. Battery percentage versus voltage

Battery percentage should not be treated as a precise energy measurement.

The investigation records both:

```text
battery percentage
battery voltage
```

together with:

- uptime,
- reboot count,
- reconnect count,
- valve activity,
- WLAN state,
- Beacon Recovery counters,
- desired and derived beacon skip,
- firmware configuration.

Short-term voltage movement can be strongly influenced by load and battery recovery.

For that reason, longer stable intervals are more useful than isolated percentage changes.

No direct current measurements are part of this investigation.

---

# 17. `/stats` availability

The richer `/stats` endpoint is available on the relevant 2.2.4 builds used during later testing.

Older firmware versions do not expose the same telemetry.

This means that a missing counter on an older reference device must not be interpreted as a zero value.

Examples include early 2.1.x measurements where battery, voltage, uptime and logs were available but the later 2.2.4 statistics were not.

---

# 18. `sleep_ratio`

The reported `sleep_ratio` is useful as firmware telemetry but should not be interpreted as direct physical sleep residency.

Reverse engineering shows that it is associated with tickless timing/compensation behavior.

It does not directly answer:

```text
how long the EFM32 remained in EM1
how long the EFM32 remained in EM2
how long the WF200 radio physically slept
```

The host sleep/blocker analysis is documented separately in:

```text
docs/reverse-engineering/host-sleep-and-blocker-accounting.md
```

---

# 19. Future stock host observer

A dedicated Stock Host Observer is being developed to answer questions that the existing `/stats` telemetry cannot resolve.

Its intended measurements include:

- B2/B3 blocker state,
- EM1/EM2 selection,
- PA8 sleep vetoes,
- WFI activity,
- selected B2 ownership transitions.

Until a fully qualified observer artifact exists and has been tested on a physical device, no observer runtime result is included in this matrix.

This keeps the device matrix limited to experiments that have actually reached controlled hardware testing.

---

# 20. Experiment interpretation

When comparing two devices, the preferred order is:

1. identify the exact firmware configuration,
2. identify the experiment period,
3. compare relevant host/radio behavior,
4. compare uptime and operating conditions,
5. compare voltage over a meaningful interval,
6. use battery percentage as supporting information,
7. avoid attributing causality from a single counter.

A device IP alone is not sufficient experimental metadata.

---

# 21. Related documentation

Detailed analysis is split across the repository.

Host sleep and blocker accounting:

```text
docs/reverse-engineering/host-sleep-and-blocker-accounting.md
```

Host PM lifecycle and A1:

```text
docs/reverse-engineering/pm-lifecycle-and-a1.md
```

WF200 firmware:

```text
docs/reverse-engineering/wf200-firmware.md
```

Beacon estimator:

```text
docs/reverse-engineering/real-beacon-skip.md
```

Recovery behavior:

```text
docs/reverse-engineering/recovery-mechanism.md
```

Beacon receive counter:

```text
docs/reverse-engineering/beacon-rx-counter.md
```

Firmware comparison:

```text
docs/reverse-engineering/firmware-comparison.md
```

mDNS analysis:

```text
docs/reverse-engineering/mdns-periodic-restart.md
```

Runtime battery testing:

```text
docs/testing/battery-testing.md
```

mDNS runtime comparison:

```text
docs/testing/mdns-runtime-comparison.md
```

Patch overview:

```text
docs/patch/README.md
```

---

# 22. Current conclusion

The physical-device experiments show that the battery-drain problem cannot be reduced to one obvious counter or one firmware mechanism.

The strongest comparisons currently show:

- drain existed before 2.2.4,
- targeted mDNS suppression alone did not prevent it,
- stock 2.2.4 Beacon Recovery can run very frequently,
- the observed recovery loop did not require D3 `PS_MODE_ERROR`,
- C-C removes a demonstrated host-side recovery defect but retains fresh recovery,
- fresh recovery remains with WF200 3.18.0,
- WLAN steering is not required for that recovery,
- short-term battery voltage does not follow recovery frequency in a simple linear way,
- A1 + C-C + WF200 3.18.0 runs successfully on physical hardware.

The remaining work is therefore focused on actual host sleep behavior, blocker accounting and longer runtime comparisons rather than treating Beacon Recovery frequency alone as a battery-current measurement.