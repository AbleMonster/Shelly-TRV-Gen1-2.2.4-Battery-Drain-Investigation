# Battery Testing

## Overview

This document tracks the long-term battery investigation of the Shelly TRV Gen1 across stock firmware, experimental host patches and different WF200 firmware versions.

The goal is not to derive laboratory-grade power consumption from battery percentage.

The goal is to determine whether reproducible battery behavior changes when specific firmware defects or recurring workloads are corrected.

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
Beacon Recovery activity
+
WLAN statistics
+
valve workload
+
reboot / reconnect behavior
+
long-term observation
```

No direct current measurement is currently part of the dataset.

For that reason, values such as:

```text
Recovery events/hour
Recovery wall-clock time
beacon receive rate
sleep_ratio
```

are diagnostic measurements.

They must not be converted directly into:

```text
mA
mAh/day
battery percentage
```

without an electrical measurement.

---

# Test Objective

The main question is:

> Does correcting the identified host-side firmware defects and using the newer
> WF200 firmware produce a reproducible improvement in real-world battery
> endurance?

The current corrected experimental stack is:

```text
Shelly TRV 2.2.4
        |
        v
A1 host PM / lifecycle corrections
        |
        v
Patch C-C Beacon Recovery corrections
        |
        v
Shelly FMAC 3.7.0
        |
        v
WF200 3.18.0
```

The long-term battery test compares this corrected stack with stock and earlier
experimental configurations.

The battery test is also used as an integration test.

A firmware that reduces one visible workload but causes:

- reconnects
- reboots
- broken thermostat operation
- incorrect valve behavior
- failed WLAN association
- PM deadlocks

would not be considered a successful correction.

---

# Battery Drain Is Not Treated as a Single-Cause Problem

Battery drain has been observed on firmware versions predating 2.2.4.

This is an important boundary condition.

The 2.2.4 Beacon Recovery implementation can therefore be an additional drain
mechanism or amplifier, but it cannot by itself explain the complete historical
Shelly TRV Gen1 battery-drain problem.

The current model is:

```text
normal TRV consumption
        |
        +-- host MCU activity
        |
        +-- WF200 WLAN activity
        |
        +-- cloud / controller traffic
        |
        +-- valve motor
        |
        +-- RF conditions / retransmissions
        |
        +-- periodic mDNS
        |
        +-- Beacon Recovery
        |
        +-- host PM / transport defects
        |
        +-- possible WF200 PM defects
        |
        +-- other unidentified behavior
        |
        v
total battery consumption
```

The purpose of the experimental firmware is to remove demonstrated defects
without assuming in advance which one dominates the battery result.

---

# Measurement Method

The TRV itself is the primary telemetry source.

The main endpoints are:

```text
/status
/stats
/debug/log
```

Not every firmware version exposes every endpoint.

The most important battery values are:

```text
bat.value
bat.voltage
```

Additional useful runtime values include:

```text
uptime
reboot_counter
reconnect_counter

RSSI

thermostat position
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

Where available, debug logs are used to correlate these counters with actual
runtime events such as:

```text
Beacon skip error! Attempt recovery
Power save state 1
Power save state 3
valve movement
calibration
WLAN reconnect
```

---

# Sampling Frequency

Frequent diagnostic polling can itself disturb a low-power device.

For long-term battery comparison, unnecessary polling should therefore be
avoided.

The preferred long-term schedule is approximately:

```text
one planned measurement per day
```

A normal sample should obtain:

```text
/status
```

followed, where available, by:

```text
/stats
```

`/stats` causes additional communication with the WF200 and should not be
treated as a completely passive observation.

The long-term test therefore favors fewer well-defined samples over continuous
manual polling.

The automated logger may be used where required, but the measurement frequency
must always be considered when interpreting low-power behavior.

---

# Battery Voltage Is the Primary Trend Metric

Battery percentage is calculated by the device firmware.

It is not a coulomb counter and does not directly measure consumed energy.

It can remain unchanged for long periods and then move in relatively large
steps.

For this reason, the primary battery trend is:

```text
voltage over time
```

with:

```text
battery percentage
```

used as secondary information.

Useful long-term metrics include:

```text
mV/day
```

and:

```text
%/day
```

but percentage should not be treated as having the same precision as voltage.

---

# Voltage Is Still Not an Energy Measurement

Battery voltage is more useful than percentage for observing gradual change,
but it is not a direct measurement of remaining capacity.

Voltage depends on:

- state of charge
- current load
- recent valve movement
- recent WLAN activity
- battery temperature
- internal resistance
- battery age
- time since charging
- relaxation after load

A short-term change such as:

```text
3.626 V -> 3.609 V
```

must therefore not be extrapolated linearly into:

```text
expected battery lifetime
```

without a longer observation period.

---

# API Voltage and External Voltage Must Not Be Mixed

Voltage measurements from different methods must remain separate.

For example, an external measurement immediately after charging and a later
TRV API measurement are not equivalent samples.

A known example is:

```text
external post-charge measurement:
4.020 V
```

versus a later pre-flash API value:

```text
/status:
3.630 V
```

These values are useful individually.

They must not be combined into one continuous API voltage curve.

Long-term comparisons should therefore identify the measurement source:

```text
TRV API
```

or:

```text
external meter
```

and avoid calculating a trend across different measurement methods.

---

# Battery Percentage

Battery percentage remains useful for identifying large state changes and the
final discharge condition.

However:

```text
100 %
```

does not mean that two physical batteries contain exactly the same usable
energy.

Likewise:

```text
50 %
```

on two different TRVs does not establish equal remaining capacity.

Percentage should therefore always be interpreted together with:

```text
voltage
runtime
battery history
device history
workload
```

---

# Battery Condition

The physical batteries in the test devices are not guaranteed to have
identical:

- age
- usable capacity
- internal resistance
- charge history
- previous discharge depth
- temperature history

This remains one of the largest limitations of cross-device comparison.

A result such as:

```text
TRV A: -5 %
TRV B: -10 %
```

does not establish:

```text
Firmware B consumes twice as much energy.
```

Long-term repeated behavior is more useful than a simple ranking of individual
devices.

---

# Charge and T0 Procedure

Where practical, devices used for a new long-term comparison should be charged
individually.

Each device receives its own test start point:

```text
T0
```

The T0 record should include at least:

```text
timestamp
firmware configuration
WF200 firmware
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

Devices do not need to start at exactly the same voltage to provide useful
observational data.

The starting condition must simply be documented so the resulting trajectory
can be interpreted correctly.

---

# Firmware Identity

A physical TRV does not permanently represent one firmware configuration.

Several devices in this project have run multiple firmware variants.

Therefore:

> Firmware identity must be determined from the actual firmware state and test
> interval, not from the device IP address alone.

Any OTA update or firmware change creates a new experimental interval.

Data before and after that transition must not be combined as if the same
firmware had run continuously.

---

# Valve and Motor Workload

The valve motor performs real mechanical work and can represent a substantial
battery load.

Battery comparison must therefore consider:

```text
valve movement
calibration
heating demand
target-temperature changes
```

A device that performs calibration and multiple full valve movements cannot be
compared directly over a short interval with a device whose valve remains
stationary.

Where available, useful values include:

```text
steps_counter
steps/hour
valve position
movement count
```

The objective is workload context.

Motor steps are not currently converted into joules or mAh.

---

# Short-Uptime `steps/hour` Values

The firmware can expose a calculated:

```text
steps/hour
```

value.

This value requires caution immediately after boot.

For example, calibration or a large valve movement during the first minutes of
runtime can produce an extremely high calculated `steps/hour`.

That does not represent the steady-state motor workload of the device.

For long-term comparison:

```text
steps_counter
```

and the actual observation interval are more useful.

---

# WLAN Signal Strength

RSSI is recorded because WLAN conditions can affect:

- beacon policy
- retransmissions
- receive activity
- reconnect behavior
- cloud traffic
- PM behavior

The observed desired beacon-skip policy includes approximately:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

A lower desired skip means more frequent nominal beacon-listening
opportunities.

It does not mean that complete-device current scales proportionally with the
skip value.

RSSI is also not the complete RF picture.

Two devices with similar RSSI can still differ in:

- associated AP
- channel
- interference
- retransmissions
- connection history
- beacon timing

---

# `real_beacon_skip` Is Not a Physical Sleep Measurement

The name:

```text
real_beacon_skip
```

can be misleading.

It is not a direct WF200 readback of the configured listen interval.

It is calculated by the Shelly host from received-beacon statistics.

Therefore:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not prove:

```text
WF200 actually used listen interval 1
```

and it does not prove:

```text
WF200 remained physically awake
```

The value remains useful because it is the input to Shelly's Beacon Recovery
decision.

It should not be treated as direct radio sleep telemetry.

---

# Beacon Recovery as a Battery Variable

Firmware 2.2.4 can repeatedly enter the sequence:

```text
Beacon skip error! Attempt recovery
        |
        v
Power save state 1
        |
        v
approximately 5 serviced seconds
        |
        v
Power save state 3
```

During the Recovery interval:

- a less power-saving WLAN state is requested
- deeper host sleep is restricted
- additional PM control work occurs

This makes Recovery a plausible battery workload.

Its exact electrical cost has not been measured.

---

# Stock Recovery Occupancy

Several devices have shown approximately one Beacon Recovery per minute.

At:

```text
60 Recoveries/hour
```

and approximately:

```text
5 seconds/Recovery
```

the explicit Recovery interval is:

```text
60 × 5 s
= 300 s/hour
= 5 min/hour
≈ 8.33% of wall-clock time
```

This is a time measurement.

It is not:

```text
8.33% battery consumption
```

No such conversion is justified without current measurement.

---

# Patch C-C Recovery Behavior

Patch C-C corrects the identified stale and invalid Recovery-evidence problems
without completely disabling Recovery.

After a Recovery:

```text
old measurement baseline invalidated
        |
        v
next successful sample establishes new baseline
        |
        v
no Recovery from historical real_beacon_skip
        |
        v
later comparable sample produces fresh estimate
```

With the currently observed measurement cadence, this naturally limits fresh
Recovery to approximately:

```text
30 Recoveries/hour
```

if every newly calculated value continues to qualify.

At approximately five seconds each:

```text
30 × 5 s
= 150 s/hour
= 2.5 min/hour
≈ 4.17% wall-clock time
```

This is a cadence-dependent consequence of the current implementation.

It is not considered an optimized Recovery frequency.

No technically justified minimum Recovery frequency has yet been established.

---

# Recovery Frequency Is a Trade-Off

Further Recovery rate limiting is under consideration.

However, reducing Recovery frequency cannot yet be assumed to be universally
beneficial.

The known side is:

```text
fewer Recoveries
        |
        v
less guaranteed explicit Recovery time
```

The unknown side is:

```text
if a real WF200 condition exists
that leaves the radio awake
        |
        v
less frequent Recovery
        |
        v
the condition may remain active longer
```

Assume purely as a working hypothesis that:

1. an unknown WF200 condition can leave the radio in an undesired awake state,
2. D3 does not report this condition,
3. Shelly's host heuristic detects it,
4. Beacon Recovery reliably clears it.

Under those assumptions:

| Recovery rate | Interval | Explicit Recovery time/hour | Maximum hypothetical fault duration | Average hypothetical duration* |
|---:|---:|---:|---:|---:|
| 60/hour | 1 min | ~300 s | ~1 min | ~30 s |
| 30/hour | 2 min | ~150 s | ~2 min | ~1 min |
| 4/hour | 15 min | ~20 s | ~15 min | ~7.5 min |

\*Assuming random occurrence between two effective detection opportunities.

Only the Recovery-time column is based on observed Recovery duration.

The fault-duration columns are hypothetical.

The calculation explains why the current C-C implementation does not
arbitrarily reduce Recovery to a very low frequency.

The demonstrated stale loop is removed.

Fresh Recovery is retained until the physical condition behind the heuristic
is better understood.

---

# D3 Parallel Observation

The WF200 provides a known direct PM error channel:

```text
D3 PS_MODE_ERROR
```

A dedicated observer build on device `.11` records this channel while leaving
normal Shelly Beacon Recovery and PM behavior active.

This allows both mechanisms to be observed in parallel:

```text
Shelly host heuristic
        |
        v
Beacon Recovery
```

and:

```text
WF200
        |
        v
D3 PS_MODE_ERROR
```

At the latest observation:

```text
uptime                 230144 s
                       63.93 h

Beacon Recoveries      3835
Recovery rate          ~59.99/hour

desired_beacon_skip    20
real_beacon_skip       1

D3 PS_MODE_ERROR       0

reboot_counter         1
reconnect_counter      1
```

This is an important result.

During approximately 63.9 hours, the normal Shelly Recovery mechanism executed
3,835 times while the known WF200 D3 PM-error channel reported no error.

No observed Recovery during this period can therefore be directly tied to a
reported D3 `PS_MODE_ERROR`.

Likewise, no Recovery can be shown to have cleared a D3 error, because none was
reported.

This does not prove that the WF200 had no other internal problem.

D3 is not complete physical sleep telemetry.

---

# Device `.11` — D3 Observer

Current relevant configuration:

```text
Host:
2.2.4_D3 observer

Beacon Recovery:
stock behavior

WF200:
3.16.1
```

Latest long-running sample:

```text
uptime              230144 s
                    63.93 h
                    2.66 days

battery             43 %
voltage             3.481 V

reboot_counter      1
reconnect_counter   1

sleep_ratio         0.016867

desired skip        20
real skip           1

beacon_err          3835

D3 PS_MODE_ERROR    0
```

The approximately:

```text
3835 / 230144 × 3600
≈ 59.99 Recoveries/hour
```

rate is essentially one Recovery per minute.

At approximately five seconds each, the device accumulated roughly:

```text
19175 seconds
319.6 minutes
5.33 hours
```

of explicit Recovery intervals during the observation.

Again, this is not an energy measurement.

---

# Device `.77` — Patch-B Full-Discharge Endpoint

Device `.77` is particularly useful because it reached a complete observed
discharge endpoint while the targeted periodic mDNS restart was suppressed and
stock Beacon Recovery remained active.

Relevant configuration:

```text
Host:
2.2.4

Patch B:
active

targeted periodic mDNS:
suppressed under tested conditions

Beacon Recovery:
stock behavior
```

The final snapshot immediately before the device became unavailable showed:

```text
uptime              797437 s
                    221.51 h
                    9.23 days

battery             0 %
voltage             3.116 V

reboot_counter      1
reconnect_counter   30

RSSI                -79 dBm

thermostat position 0 %
target temperature  18.0 °C
measured temperature
                    18.7 °C

sleep_ratio         0.014383

desired skip        15
real skip           1

beacon_err          12908
beacon_rx            1986494
beacon_rx_missed     19603
beacon_tbtt_diff     232
```

The complete-runtime Recovery rate is:

```text
12908 / 797437 × 3600
≈ 58.27 Recoveries/hour
```

This is again very close to one Recovery per minute.

At approximately five seconds per event:

```text
12908 × 5 s
= 64540 s
= 17.93 h
```

of explicit Recovery time accumulated.

Relative to the complete runtime:

```text
64540 / 797437
≈ 8.09%
```

of wall-clock time was spent in the explicit Recovery interval.

This closely matches the approximately 8.33% expected for an exact
once-per-minute five-second Recovery pattern.

It does not mean that Recovery consumed 8.09% of the battery.

---

# Interpretation of the `.77` Endpoint

The `.77` result is important for two reasons.

First, it demonstrates that suppressing the targeted periodic mDNS restart did
not prevent a complete discharge during this test.

Second, stock Beacon Recovery remained highly active throughout the observed
runtime.

The result therefore supports:

```text
targeted periodic mDNS suppressed
        +
persistent Beacon Recovery remains
        +
complete discharge still occurs
```

It does not establish:

```text
Beacon Recovery caused the complete discharge
```

and it does not establish:

```text
mDNS has zero battery cost
```

It does show that the targeted periodic mDNS cycle is not sufficient by itself
to explain the observed drain on this device.

A final `/debug/log` was not captured before `.77` became unavailable.

The final `/status` and `/stats` snapshots still preserve the important
cumulative endpoint values.

---

# Device `.88` — C-C Long-Term Reference

Device `.88` provides a useful C-C reference using the older WF200 firmware.

Relevant configuration:

```text
Host:
2.2.4 + Patch C-C

WF200:
3.16.1
```

A long-running observation around 9.9 days showed approximately:

```text
battery             56 %
voltage             3.570 V

beacon_err          0

desired skip        20
real skip           6
```

The important mechanism result is:

```text
C-C active
+
no fresh qualifying Recovery during this interval
```

This is useful for comparison with devices where fresh C-C Recovery continues.

It is not by itself proof that C-C improves battery life.

---

# Device `.237` — C-C + WF200 3.18.0 Reference

Device `.237` combines:

```text
Patch C-C
+
WF200 3.18.0
```

without the complete A1 host integration.

An observed interval of approximately:

```text
15.19 h
```

showed:

```text
battery             72 %
voltage             3.669 V

sleep_ratio         0.020343

desired skip        20
real skip           1

beacon_err          362
```

This corresponds to approximately:

```text
29.96 Recoveries/hour
```

The pattern is consistent with fresh C-C Recovery rather than the old
once-per-minute stale self-trigger loop.

This result is important because similar fresh Recovery is also observed on the
integrated A1 device.

The behavior therefore should not automatically be attributed to A1.

---

# Device `.234` — A1 + C-C + WF200 3.18.0

Device `.234` is the first controlled hardware test of the complete current
integration:

```text
A1
+
Patch C-C
+
WF200 3.18.0
```

Before flashing, `.234` ran stock 2.2.4 host behavior with WF200 3.18.0.

The final pre-flash API status included:

```text
battery             66 %
voltage             3.630 V

uptime              187489 s
                    52.08 h

valve position      100 %
target temperature  26.0 °C

beacon_err          3124

desired skip        20
real skip           1

sleep_ratio         0.019924
```

The stock host still showed the approximately once-per-minute Recovery loop
despite WF200 3.18.0.

This confirms that the C2 stale-Recovery loop is a host-side problem and is not
removed simply by updating the WF200 firmware.

---

# `.234` OTA and Functional Qualification

The integrated firmware was flashed successfully.

The device completed:

```text
OTA
        |
        v
cold reboot
        |
        v
FMAC 3.7.0 initialization
        |
        v
WF200 3.18.0 initialization
        |
        v
scan
        |
        v
join
        |
        v
DHCP
        |
        v
cloud
        |
        v
normal PM operation
```

Manual calibration was also completed successfully.

Thermostat and valve operation continued normally.

This is important because the battery test should only begin after basic
functional qualification has passed.

---

# `.234` Early Runtime

An early sample at approximately:

```text
1060 s
```

showed:

```text
reboot_counter      1
reconnect_counter   1

battery             ~65 %
voltage             ~3.626 V

sleep_ratio         0.019083

desired skip        20
real skip           1

beacon_err          9
```

The short-runtime `steps/hour` value was dominated by calibration and valve
movement and is not representative of steady-state operation.

---

# `.234` Multi-Hour Runtime

After approximately:

```text
28587 s
= 7.94 h
```

the device showed:

```text
battery             62 %
voltage             3.609 V

reboot_counter      1
reconnect_counter   1

valve position      0 %

target temperature  20.6 °C
measured temperature
                    ~20.7 °C

sleep_ratio         0.02081

desired skip        15
real skip           13

beacon_err          217
```

Between the early and later samples:

```text
beacon_err:
9 -> 217
```

over:

```text
27527 s
```

which corresponds to approximately:

```text
27.2 Recoveries/hour
```

The pattern is consistent with fresh C-C Recovery rather than the stock stale
once-per-minute loop.

No additional reboot or reconnect occurred.

---

# `.234` Battery Interpretation

The clean post-calibration voltage baseline was approximately:

```text
3.626 V
```

and the later value approximately:

```text
3.609 V
```

for a difference of:

```text
-17 mV
```

over roughly 7.5 hours.

This interval is too short for a meaningful battery-life extrapolation.

The device had also recently experienced:

- OTA
- reboot
- calibration
- substantial valve movement
- target-temperature changes

A later log sample around:

```text
3.599 V
```

followed by:

```text
3.609 V
```

also demonstrates short-term voltage rebound.

The correct current conclusion is therefore:

> The integrated firmware has passed the initial functional hardware test.
> Its long-term battery effect is not yet established.

---

# WF200 3.18.0 as a Battery Variable

Silicon Labs WF200 firmware 3.18.0 contains the following relevant fix:

```text
[LMAC] Fixed an error that was preventing the device from sleeping
after a power-save mode change
```

This is directly relevant to a battery-powered device that repeatedly changes
power-save mode.

It is not proof that this Silicon Labs defect caused the historical Shelly TRV
battery drain.

The project therefore treats WF200 3.18.0 as an important experimental
variable rather than a proven root-cause fix.

Physical testing has established that Shelly FMAC 3.7.0 can initialize and
operate the tested WF200 3.18.0 integration on the TRV Gen1.

---

# Historical Patch A

Patch A bypassed the targeted Beacon Recovery action.

It was useful for determining whether the device could continue operating
without the repeated Recovery path.

Patch-A devices retained beacon statistics while the targeted Recovery counter
remained suppressed.

This made Patch A useful as a mechanism-isolation tool.

It is not the preferred correction because it removes legitimate Recovery
rather than correcting the evidence used to trigger it.

Historical Patch-A battery behavior also showed that:

```text
Recovery suppressed
```

does not automatically mean:

```text
no battery decline
```

This is another reason the historical battery problem is not treated as a
single-cause issue.

---

# Historical Patch B

Patch B suppresses the targeted periodic mDNS restart while leaving Beacon
Recovery active.

Device `.77` became the most useful Patch-B long-term example.

Its complete discharge endpoint now shows:

```text
targeted periodic mDNS suppressed
Beacon Recovery ~58.27/hour
runtime ~9.23 days
final battery 0 %
final voltage 3.116 V
```

This strengthens the separation between the periodic mDNS workload and the
Beacon Recovery mechanism.

It does not quantify the energy cost of either one.

---

# Historical Patch A+B

Patch A+B was used as a mechanism-isolation experiment.

During monitored operation:

```text
targeted periodic mDNS
not observed

recurring Beacon Recovery
not observed

Wi-Fi
operational

cloud
operational

thermostat
operational
```

This demonstrated that both targeted recurring workloads could be suppressed
simultaneously without immediately breaking normal operation.

A+B is no longer the preferred final architecture.

The current research uses C-C instead of simply bypassing Recovery and A1 for
the identified host PM/lifecycle defects.

---

# Current Device Matrix

The device roles have changed during the project.

The current relevant roles are approximately:

| Device | Current / relevant configuration | Main role |
|---|---|---|
| `.11` | 2.2.4_D3, stock Recovery, WF200 3.16.1 | D3 / stock-Recovery reference |
| `.77` | 2.2.4 + Patch B, stock Recovery | completed mDNS-isolation discharge |
| `.88` | 2.2.4 + C-C, WF200 3.16.1 | C-C long-term reference |
| `.229` | stock 2.2.4 | stock control |
| `.234` | A1 + C-C + WF200 3.18.0 | integrated canary |
| `.237` | C-C + WF200 3.18.0 | C-C / WF200 3.18 comparison |
| `.226` | historical combined isolation configuration | secondary historical reference |

This table describes experimental roles, not permanent device identities.

Firmware must still be checked from the actual test interval.

---

# Stock Control

At least one stock 2.2.4 device should remain unmodified during the main
long-term corrected-firmware comparison.

The stock device provides a contemporaneous reference for:

```text
battery voltage
battery percentage
Recovery frequency
WLAN behavior
valve workload
reboots
reconnects
```

A stock control does not eliminate environmental differences between physical
TRVs.

It is still substantially more useful than comparing the corrected firmware
only with old historical data.

---

# Normal Heating Operation

The long-term field test is intended to use the TRVs in normal heating
operation.

This means that:

```text
valve activity
heating demand
room temperature
```

will not be perfectly controlled.

That is intentional.

The final question is not only whether the firmware behaves well on a bench.

It is whether the corrected firmware remains stable and shows improved battery
behavior during realistic TRV operation.

The resulting data remain observational rather than laboratory-controlled.

---

# Main Long-Term Metrics

The primary long-term battery metric is:

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

Workload context includes:

```text
motor steps
valve position
target temperature
measured temperature
RSSI
```

No single metric is expected to explain the complete result.

---

# Recovery Rate Calculation

Recovery rate can be calculated from cumulative counter differences.

For example:

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

For a complete uninterrupted runtime from boot:

```text
Recovery/hour
=
beacon_err_counter / uptime × 3600
```

This is appropriate only when the counter semantics and firmware interval are
known.

A firmware transition or counter reset requires a new interval.

---

# Recovery Wall-Clock Calculation

For the observed approximately five-second Recovery interval:

```text
Recovery wall-clock/hour
≈
Recovery/hour × 5 s
```

For example:

```text
60/hour
≈ 300 s/hour
≈ 5 min/hour
≈ 8.33%
```

or:

```text
30/hour
≈ 150 s/hour
≈ 2.5 min/hour
≈ 4.17%
```

This value describes explicit Recovery occupancy.

It must not be reported as an equivalent battery percentage.

---

# Beacon Receive Rate

Where useful:

```text
beacon_rx/second
```

can be calculated from counter differences:

```text
delta_beacon_rx / delta_time
```

This provides a more useful comparison than absolute cumulative counts between
devices with different uptimes.

It still does not directly measure radio power consumption.

---

# Reboots and Reconnects

Battery trends are difficult to interpret if a device repeatedly reboots or
reconnects.

The following should therefore always be retained:

```text
reboot_counter
reconnect_counter
uptime
```

A battery improvement accompanied by frequent reconnects would not represent a
successful production correction.

The initial `.234` integrated test is encouraging in this respect because:

```text
reboot_counter    = 1
reconnect_counter = 1
```

remained unchanged during the initial multi-hour qualification.

---

# `sleep_ratio`

The firmware exposes a:

```text
sleep_ratio
```

value.

This is useful as a comparative diagnostic.

It should not be interpreted as a direct electrical duty-cycle measurement
without establishing its exact implementation and relationship to physical
host/radio sleep.

In particular:

```text
sleep_ratio
```

should not be converted directly into expected battery life.

---

# Major Confounding Variables

The current long-term experiment contains unavoidable confounders.

| Variable | Status | Relevance |
|---|---|---|
| Firmware | controlled per interval | primary variable |
| WF200 firmware | controlled per interval | primary variable |
| Physical TRV | differs | hardware variation |
| Battery age | differs | capacity / resistance |
| Battery history | differs | starting condition |
| Valve workload | recorded where possible | significant load |
| Calibration | documented | significant short-term load |
| RSSI | recorded | WLAN policy / RF |
| Associated AP | not always continuously recorded | RF uncertainty |
| Device location | differs | RF / temperature |
| Heating demand | differs | motor workload |
| Temperature | differs | battery / heating |
| Network traffic | not identical | WLAN activity |
| Reboots | recorded | experimental boundary |
| Reconnects | recorded | WLAN workload |
| Diagnostic polling | minimized | measurement perturbation |

These variables should remain visible when interpreting any battery ranking.

---

# Same-Device Testing

Where practical, same-device A/B testing remains useful.

For example:

```text
same TRV
        |
        +-- stock firmware interval
        |
        +-- corrected firmware interval
```

This removes some hardware variation.

It does not remove:

- battery aging
- different starting state of charge
- seasonal heating demand
- room temperature changes
- RF changes
- different motor workload

Same-device testing is therefore stronger than simple cross-device ranking but
still not equivalent to direct electrical measurement.

---

# Why Short 24-Hour Rankings Are Weak

A one-day result can be dominated by:

- post-charge relaxation
- calibration
- valve movement
- room-temperature changes
- temporary WLAN behavior
- battery percentage quantization

For this reason:

```text
24 hours
```

is useful for detecting gross problems but weak for battery-life conclusions.

A more useful field interval is:

```text
7 days
```

and:

```text
14 days or longer
```

is preferable where practical.

A complete discharge endpoint such as `.77` is especially useful because it
captures the entire operational trajectory of that particular device and
configuration.

It still remains a single physical-device result.

---

# What `.77` Adds to the Dataset

The `.77` endpoint provides something the earlier short snapshots did not:

```text
documented firmware role
+
documented mDNS isolation
+
cumulative Recovery count
+
full uptime
+
final battery percentage
+
final battery voltage
+
actual device shutdown shortly afterward
```

The final result is:

```text
~9.23 days
12908 Recoveries
~58.27 Recoveries/hour
0 %
3.116 V
```

This is stronger than extrapolating from an early voltage slope.

It still cannot determine the individual energy cost of:

```text
Beacon Recovery
mDNS
WLAN conditions
motor workload
```

without further controls.

---

# What `.11` Adds to the Dataset

The `.11` D3 observer provides a different type of evidence.

It shows that:

```text
~63.93 h
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

can coexist.

This matters for battery interpretation because the approximately once-per-
minute Recovery workload cannot simply be described as the radio reporting a
known PM failure once per minute.

The host heuristic and the known WF200 error channel are separate.

---

# What `.88` and `.237` Add

`.88` and `.237` help separate the remaining fresh C-C behavior.

`.88`:

```text
C-C
WF200 3.16.1
~9.9 days
beacon_err = 0
```

`.237`:

```text
C-C
WF200 3.18.0
~15.2 h
~29.96 Recoveries/hour
```

This difference is interesting but not yet sufficient to assign causality to
the WF200 version.

Other differences between the physical devices and RF environments remain.

Longer observation is required.

---

# What `.234` Adds

`.234` tests the complete corrected integration:

```text
A1
+
C-C
+
WF200 3.18.0
```

The first question was not battery life.

It was:

```text
Does the integrated firmware still work correctly?
```

The answer after the initial hardware qualification is yes.

The next question is:

```text
Does it remain stable over days?
```

and finally:

```text
Does it materially improve battery endurance?
```

Those later questions require more runtime.

---

# Further Recovery Rate Limiting

The current C-C behavior is not intended to define the final optimal Recovery
frequency.

Approximately:

```text
30 Recoveries/hour
```

is a consequence of the current measurement cadence and the requirement for a
fresh post-Recovery baseline.

Further rate limiting is a possible future experiment.

No technically justified minimum Recovery frequency has yet been established.

Possible future experiments could compare different minimum intervals, for
example:

```text
current C-C behavior
        |
        v
moderate rate limit
        |
        v
stronger rate limit
        |
        v
Recovery disabled
```

The actual values should be chosen from runtime evidence rather than selected
arbitrarily.

The main unknown is still:

> What real WF200 condition, if any, does fresh low `real_beacon_skip` actually
> identify?

Until that is better understood, Recovery frequency should not be optimized
from Recovery wall-clock occupancy alone.

---

# Direct Electrical Measurement

Direct current measurement would provide the strongest answer to several
remaining questions.

A synchronized measurement could compare:

```text
normal idle
Recovery
valve movement
WLAN reconnect
PM transition
```

and potentially correlate:

```text
current
+
WUP
+
debug log
+
WF200 state
```

No such measurement is currently part of this project.

The current investigation intentionally focuses on firmware behavior and
long-term battery telemetry.

Therefore no exact values should currently be assigned for:

```text
Recovery current
mAh per Recovery
mAh/day
energy saved by C-C
energy saved by A1
energy saved by WF200 3.18.0
```

---

# Data Interpretation Rules

## Use

- direct TRV battery status as the primary device telemetry source
- voltage as the primary battery trend
- percentage as secondary battery information
- firmware identity for every interval
- WF200 firmware identity where relevant
- uptime to identify test boundaries
- reboot and reconnect counters
- RSSI
- valve and motor workload
- Recovery statistics
- raw cumulative counters
- long observation periods
- one stock control where practical
- separate T0 records for each device
- separate API and external voltage measurements
- explicit documentation of recharge events
- explicit documentation of OTA / firmware transitions

## Do Not

- convert Recovery wall-clock percentage into battery percentage
- convert Recovery count directly into mAh
- treat `real_beacon_skip` as WF200 sleep telemetry
- treat `desired_beacon_skip` as proof of physical radio behavior
- treat `sleep_ratio` as direct electrical duty cycle
- mix external-meter voltage with API voltage in one trend
- compare devices solely by battery percentage
- extrapolate battery lifetime from a few hours of voltage decline
- ignore calibration or valve movement
- combine intervals across firmware changes
- assume equal battery capacity between devices
- claim mDNS is the root cause from the current data
- claim Beacon Recovery is the root cause from the current data
- claim WF200 3.18.0 fixes the complete battery problem
- claim A1 improves battery endurance before long-term data exist
- claim D3=0 proves the WF200 was physically sleeping correctly

---

# Current Findings

The battery investigation currently supports the following statements.

### Stock Beacon Recovery can become persistent

Multiple devices have shown approximately:

```text
~60 Recoveries/hour
```

for extended periods.

---

### The stock stale-Recovery loop is a host-side defect

Patch C-C corrects the stale-evidence lifecycle while preserving fresh
Recovery.

---

### Patch C-C operates on physical hardware

C-C is no longer only a static design.

Hardware testing has demonstrated the corrected behavior.

---

### Fresh Recovery can remain after C-C

This is expected.

Fresh qualifying measurements can still trigger Recovery.

The current measurement cadence can produce approximately:

```text
~30 Recoveries/hour
```

when every fresh estimate continues to qualify.

---

### `.77` reached a complete discharge with mDNS isolation active

The final observed endpoint was approximately:

```text
9.23 days
0 %
3.116 V
12908 Recoveries
~58.27 Recoveries/hour
```

This does not prove Recovery caused the discharge.

It does show that targeted periodic mDNS suppression alone did not prevent the
observed drain on this device.

---

### `.11` produced thousands of Recoveries without D3 PM errors

At approximately:

```text
63.93 h
```

the device showed:

```text
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

The Shelly Recovery heuristic therefore cannot be treated as equivalent to the
known direct WF200 PM-error channel.

---

### WF200 3.18.0 does not remove the stock host stale-Recovery loop

Stock host behavior with WF200 3.18.0 still showed the recurring Recovery loop.

This is expected because C2 is host logic.

---

### A1 + C-C + WF200 3.18.0 boots and operates on real hardware

The integrated `.234` test successfully reached normal WLAN, cloud, thermostat,
valve and PM operation.

No additional reboot or reconnect occurred during the initial approximately
eight-hour qualification interval.

---

### Long-term battery improvement is still open

The integrated firmware has passed its initial functional gate.

Its long-term battery effect has not yet been established.

---

# Current Long-Term Test Plan

The preferred next phase is:

```text
one stock 2.2.4 control
        |
        +
multiple corrected devices
A1 + C-C + WF200 3.18.0
```

where practical.

Devices should be:

- charged separately
- assigned individual T0 records
- left in normal heating operation
- kept on unchanged firmware during the interval
- sampled approximately once per day
- monitored for reboots and reconnects
- compared using voltage primarily
- compared using percentage secondarily
- normalized qualitatively for valve workload and RF conditions

The corrected firmware should first demonstrate:

```text
days of stable operation
```

and then:

```text
reproducible battery behavior
```

before any battery-life claim is made.

---

# Current Research Questions

The main remaining battery questions are:

1. Does A1 + C-C + WF200 3.18.0 materially reduce long-term voltage decline?

2. Does the result reproduce across more than one physical TRV?

3. How does the corrected stack compare with the contemporaneous stock 2.2.4
   control?

4. Does the approximately 30/hour fresh C-C Recovery behavior persist over
   longer periods?

5. Why does `.88` show no Recovery while `.237` and `.234` show frequent fresh
   Recovery?

6. Does WF200 3.18.0 influence the fresh host beacon-density estimate?

7. Does A1 change battery behavior independently of C-C?

8. What real WF200 condition, if any, is represented by fresh
   `real_beacon_skip = 1/2`?

9. Does Beacon Recovery actually correct that condition?

10. How far can Recovery frequency be reduced without allowing a real
    high-power fault, if one exists, to remain active for too long?

11. How much of the historical drain predating 2.2.4 remains after the known
    host and radio corrections?

---

# Current Conclusion

The battery investigation has moved beyond comparing firmware versions by
percentage decline.

Several concrete firmware behaviors are now understood.

Stock 2.2.4 can enter an approximately once-per-minute Beacon Recovery loop.

The stale-evidence mechanism behind that loop has been identified and corrected
by Patch C-C.

Device `.77` has now provided a complete discharge endpoint with the targeted
periodic mDNS restart suppressed:

```text
runtime             ~9.23 days
battery             0 %
voltage             3.116 V
Beacon Recoveries   12908
Recovery rate       ~58.27/hour
```

The device therefore spent approximately:

```text
17.93 hours
```

or:

```text
8.09% of its runtime
```

inside the explicit approximately five-second Recovery intervals.

This is a wall-clock measurement, not an energy percentage.

The D3 observer provides a second important result:

```text
~63.93 h
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

The repeated Shelly Recovery mechanism therefore does not correspond to a
sequence of known WF200 D3 PM errors in the observed test.

Patch C-C removes the demonstrated stale self-trigger loop while retaining
fresh Recovery.

With the current measurement cadence, fresh Recovery can occur approximately
every two minutes, giving a theoretical current-cadence maximum around:

```text
30/hour
```

or approximately:

```text
2.5 minutes/hour
4.17% wall-clock Recovery occupancy
```

The current integrated `.234` test observed approximately:

```text
27.2/hour
```

during its initial multi-hour interval.

That rate is not considered optimized.

Further Recovery rate limiting is under consideration, but no technically
justified minimum frequency has yet been established.

Reducing Recovery frequency has two possible effects:

```text
fewer Recoveries
        |
        v
less known Recovery overhead
```

but, hypothetically:

```text
less frequent Recovery
        |
        v
longer lifetime of an unknown WF200 fault
if Recovery is actually correcting one
```

The existence of such a non-D3 fault has not been demonstrated.

For that reason, Recovery is currently retained conservatively for fresh valid
measurements.

The latest integrated firmware combines:

```text
A1
+
Patch C-C
+
WF200 3.18.0
```

A1 corrects identified host PM and transport lifecycle defects.

C-C corrects Beacon Recovery evidence handling.

WF200 3.18.0 contains Silicon Labs' fix for an error that could prevent the
device from sleeping after a power-save mode change.

The integrated firmware has successfully completed its initial hardware
qualification on `.234`.

It boots, initializes WF200 3.18.0, associates with WLAN, obtains DHCP, reaches
the cloud, performs PM transitions, calibrates and controls the valve.

No additional reboot or reconnect occurred during the initial approximately
eight-hour qualification period.

The remaining question is now primarily empirical:

> Does correcting these demonstrated host-side defects and using the newer
> WF200 firmware produce a reproducible improvement in real-world battery
> endurance?

That requires the long-term test.

No battery-life improvement is claimed yet.

---

# Related Documents

Power-management analysis:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

`real_beacon_skip`:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon RX counter:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

Firmware comparison:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

AP selection and roaming:

[`../reverse-engineering/ap-selection-and-roaming.md`](../reverse-engineering/ap-selection-and-roaming.md)

Periodic mDNS:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

mDNS runtime comparison:

[`mdns-runtime-comparison.md`](mdns-runtime-comparison.md)

Patch documentation:

[`../patch/README.md`](../patch/README.md)

---

# Methodology Note

The battery investigation uses telemetry and runtime behavior from personally
owned Shelly TRV Gen1 devices.

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

Raw observations should be retained so that battery conclusions can be
re-evaluated as the firmware model improves.

Firmware identity and measurement source should always be recorded with the
corresponding observation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

Experimental firmware modifications are intended for controlled research on
personally owned hardware.

Battery observations do not constitute manufacturer specifications or
guaranteed battery-life results.