# Beacon Recovery Mechanism Analysis

## Scope

This document describes the beacon-recovery mechanism identified in Shelly TRV
Gen1 firmware 2.2.4.

The purpose of this analysis is to determine:

- what triggers the recovery mechanism
- what happens when recovery is entered
- what WLAN power state is requested
- how the host microcontroller's sleep behavior is affected
- how long the recovery state normally lasts
- how normal power-saving operation is restored
- which exceptional failure paths exist
- which runtime experiments isolate the mechanism
- which parts of the mechanism may be relevant to battery consumption

This document intentionally contains only the information required to describe
and reproduce the research findings.

It does not contain firmware images, complete disassemblies, complete
decompiled functions or proprietary source code.

---

# Summary

Firmware 2.2.4 contains a recovery mechanism associated with the calculated
`real_beacon_skip` value.

When the recovery condition is satisfied, the runtime log reports:

```text
Beacon skip error! Attempt recovery
```

The recovery is not merely an internal application-state change.

The analyzed normal recovery path:

1. wakes the WLAN device
2. leaves the normal beacon-based power-saving configuration
3. requests WLAN Active / Always-On mode
4. prevents the host microcontroller from entering deeper EM2 and EM3 sleep
   states
5. maintains the temporary recovery condition for approximately five seconds
6. restores the previously saved or deferred application power state

If the restored state is the normal beacon power-saving state, the current
`desired_beacon_skip` value is applied again.

No explicit WLAN transmit-power increase was identified in the normal recovery
path.

Likewise, the normal recovery path does not itself initiate:

- WLAN scanning
- access-point selection
- disconnect
- reconnect
- DHCP negotiation
- full WLAN driver reinitialization

Runtime experiments have now established several additional facts:

- recovery can occur with good RSSI
- recovery can occur while `desired_beacon_skip = 20`
- suppressing the periodic mDNS restart does not suppress recovery
- bypassing the recovery branch suppresses the targeted recurring recovery
- a combined beacon-recovery + mDNS patch suppresses both targeted recurring
  mechanisms during the monitored test windows

The recovery mechanism is therefore a distinct host-side behavior that can be
experimentally isolated from the periodic mDNS restart.

Its quantitative contribution to battery drain remains unknown.

---

# Recovery Trigger

The recovery decision uses the internally calculated:

```text
real_beacon_skip
```

value.

The relevant condition is equivalent to:

```text
real_beacon_skip != 0
&&
real_beacon_skip <= 2
```

The value is interpreted as a signed 8-bit integer.

If this condition is satisfied, the firmware enters the recovery path and
produces:

```text
Beacon skip error! Attempt recovery
```

The host-side calculation is approximately:

```text
delta =
    current_beacon_rx_count
    -
    previous_beacon_rx_count

real_beacon_skip =
    uint8_t(600 / delta)
```

The stored 8-bit result is later interpreted as signed.

This means the recovery predicate can accept not only:

```text
1
2
```

but also negative values created when unsigned results above 127 are narrowed
to 8 bits and later interpreted as signed.

The detailed calculation is documented separately in:

[`real-beacon-skip.md`](real-beacon-skip.md)

## Confidence

**PROVEN**

---

# Source of the Trigger Data

Firmware 2.2.4 obtains the relevant WLAN statistics through WF200 command:

```text
0x66
```

The returned statistics include values corresponding to:

```text
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

The known `real_beacon_skip` calculation uses the change in:

```text
beacon_rx_count
```

The separate missed-beacon statistic is not the direct known trigger of this
recovery path.

The exact low-level semantics of the WF200 beacon statistics during
power-saving operation remain under investigation.

Therefore the current evidence establishes:

```text
WF200 beacon statistics
        |
        v
beacon_rx_count
        |
        v
host-side delta / ratio calculation
        |
        v
real_beacon_skip
        |
        v
recovery predicate
```

It does not yet establish why the WF200 counter deltas produce qualifying
values under the observed operating conditions.

---

# Recovery Sequence

The normal recovery sequence can be represented as:

```text
qualifying real_beacon_skip
            |
            v
Beacon skip error detected
            |
            v
enter recovery
            |
            v
wake WLAN device
            |
            v
request Active / Always-On WLAN mode
            |
            v
block deeper host sleep states
            |
            v
~5-second recovery window
            |
            v
restore saved / deferred application power state
            |
            v
if restoring normal beacon power saving:
apply current desired_beacon_skip
            |
            v
allow deeper host sleep again
```

This sequence matches the approximately five-second transition observed in
runtime logs between:

```text
Enter powersave state 1
```

and:

```text
Enter powersave state 3 (skip N)
```

during normal connected operation.

## Confidence

**PROVEN**

---

# WLAN State During Recovery

During recovery, the firmware requests WLAN power mode:

```text
0
```

Comparison with the documented Silicon Labs WF200/fullMAC interface identifies
this mode as:

```text
Active / Always-On
```

This is distinct from the normal connected beacon-based power-saving
configuration used by the TRV.

The recovery therefore has a real effect on WLAN power management.

It is not merely an application-level state label.

Conceptually:

```text
normal connected operation

Fast Power Save
desired beacon skip 20 / 15 / 10

        |
        | recovery
        v

Active / Always-On

        |
        | ~5 seconds
        v

restore connected power saving
current desired beacon skip
```

## Confidence

**PROVEN**

---

# Host Microcontroller Sleep Behavior

Recovery also affects the energy modes available to the host microcontroller.

The wake path acquires a WLAN-related sleep-blocking resource.

While that resource remains held, deeper host energy modes are restricted.

The relevant effect is:

```text
Normal operation

EM1  available
EM2  available
EM3  available
```

versus:

```text
Recovery window

EM1  available
EM2  blocked
EM3  blocked
```

This does **not** mean that the CPU necessarily executes continuously for the
entire recovery interval.

The processor can still idle in EM1.

The important energy-related difference is that the deeper EM2 and EM3 modes
are unavailable while the corresponding sleep block is active.

## Confidence

**PROVEN**

---

# Recovery Duration

When recovery begins, the firmware initializes a countdown with:

```text
5
```

The countdown is serviced in relation to changes in the firmware's seconds
clock.

Under normal operation this produces a recovery interval of approximately:

```text
5 seconds
```

This corresponds closely to runtime observations.

The duration should therefore be described as:

```text
approximately five seconds
```

rather than as an exact guaranteed five-second electrical pulse.

Scheduling delays, stalls or other state changes can affect the actual elapsed
time.

## Confidence

**PROVEN**

---

# Restoration of Power Saving

When the recovery countdown expires, the firmware requests restoration of the
saved or deferred application power state.

Recovery does not simply force the application into one fixed state after the
timeout.

Conceptually:

```text
recovery entry
        |
        v
save / defer application state
        |
        v
Active / Always-On
        |
        v
~5 seconds
        |
        v
restore saved / deferred state
```

If the restored state is normal beacon power saving, the firmware reads the
current:

```text
desired_beacon_skip
```

and requests the connected power-saving configuration again using that value.

Conceptually:

```text
restore normal connected state
        |
        v
read current desired_beacon_skip
        |
        v
request Fast Power Save
        |
        v
current skip 20 / 15 / 10
        |
        v
release recovery sleep restriction
```

The firmware uses the **current** `desired_beacon_skip` value at restoration
time.

It does not restore a separate saved copy of the skip value captured when the
recovery began.

## Confidence

**PROVEN**

---

# Relationship to `desired_beacon_skip`

The recovery mechanism does not permanently replace:

```text
desired_beacon_skip
```

For example, a TRV can normally operate with:

```text
desired_beacon_skip = 20
```

Recovery temporarily leaves that normal power-saving configuration and
requests:

```text
Active / Always-On
```

After the recovery window, the firmware can restore:

```text
Fast Power Save
skip 20
```

again.

Runtime behavior can therefore look like:

```text
state 3
skip 20
        |
        v
state 1
Active / Always-On
        |
        | ~5 seconds
        v
state 3
skip 20
```

without `desired_beacon_skip` itself having changed.

This distinction is important because the recovery condition is based on:

```text
real_beacon_skip
```

not directly on:

```text
desired_beacon_skip
```

---

# Recovery with Good RSSI

Runtime testing established that poor RSSI is not required for the recurring
recovery.

On the mDNS-only Patch B test device, recurring recovery was observed with
approximately:

```text
RSSI = -58 to -59 dBm
```

while the normal RSSI-dependent policy selected:

```text
desired_beacon_skip = 20
```

The device nevertheless produced:

```text
Beacon skip error! Attempt recovery
```

followed by the normal recovery sequence.

This rules out the simple explanation:

```text
poor RSSI
        |
        v
reduced desired beacon skip
        |
        v
recovery
```

as a necessary causal chain.

The recovery predicate can become true even when reported RSSI is good and the
normal desired skip remains 20.

## Confidence

**RUNTIME CONFIRMED**

---

# Relationship to Periodic mDNS

Firmware comparison identified a separate recurring mechanism:

```text
periodic mDNS responder restart
```

In stock firmware 2.2.4, runtime packet capture observed the corresponding
mDNS probe / announcement sequence approximately every 180 seconds.

One hypothesis considered during the investigation was:

```text
periodic mDNS restart
        |
        v
WLAN activity / beacon timing disturbance
        |
        v
qualifying real_beacon_skip
        |
        v
beacon recovery
```

This was tested experimentally.

---

# mDNS-Only Isolation Experiment

An experimental firmware modification, referred to as Patch B, suppresses only
the periodic connected-maintenance mDNS restart.

It does not modify:

- WF200 command `0x66`
- beacon statistics
- `beacon_rx_count`
- `real_beacon_skip`
- the recovery predicate
- the recovery branch
- normal RSSI-dependent desired beacon skip

Runtime packet capture confirmed that the targeted recurring mDNS traffic was
suppressed during the monitored test window.

However, the device continued to produce:

```text
Beacon skip error! Attempt recovery
```

approximately once per minute.

The normal sequence remained:

```text
state 1
        |
        | ~5 seconds
        v
state 3
```

This continued even during periods of good RSSI.

Therefore:

> The periodic mDNS restart is not required for the recurring beacon-recovery
> behavior under the tested conditions.

This is an important isolation result.

It does not prove that mDNS and beacon statistics can never influence one
another under any network condition.

It does establish that the targeted periodic mDNS mechanism is not necessary
for the observed recurring recovery loop.

## Confidence

**RUNTIME CONFIRMED**

---

# Experimental Patch A

The experimental beacon-recovery modification is referred to as:

```text
Patch A
```

Its purpose is to bypass only the identified recovery action.

The original control flow contains a conditional branch associated with the
recovery decision.

Original instruction:

```text
0x1E1C8

BGT 0x1E22E
31 DC
```

Patched instruction:

```text
B 0x1E22E
31 E0
```

Only one byte in the program payload changes:

```text
0x1E1C9

DC -> E0
```

The corresponding changed byte in the verified GBL container is:

```text
0x0002471D

DC -> E0
```

Patch A does not modify:

- RSSI thresholds
- `desired_beacon_skip`
- WF200 command `0x66`
- `beacon_rx_count`
- the `real_beacon_skip` calculation
- periodic mDNS behavior
- the protected WF200 image
- WLAN transmit power

Conceptually:

```text
WF200 statistics
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        X
recovery action bypassed
```

The patch should therefore be described as:

> bypassing the identified beacon-recovery action

rather than:

> fixing the underlying beacon statistics.

---

# Runtime Validation of Patch A

Patch A has been tested on physical TRVs running firmware 2.2.4.

During monitored operation, the targeted recurring sequence:

```text
Beacon skip error! Attempt recovery
        |
        v
state 1
        |
        v
~5 seconds
        |
        v
state 3
```

was suppressed.

Normal RSSI-dependent beacon-skip behavior continued to operate.

The device could still use normal desired skip values such as:

```text
20
15
10
```

according to RSSI.

This provides experimental evidence that the recovery branch can be isolated
from the normal beacon-skip selection mechanism.

It does not establish that the underlying `real_beacon_skip` values are
correct.

It also does not establish a battery-life improvement.

## Confidence

**RUNTIME CONFIRMED**

---

# Combined Patch A+B

The two independently tested experimental modifications were subsequently
combined.

```text
Patch A
    bypass beacon-recovery action

Patch B
    bypass periodic mDNS restart
```

The program modifications are:

```text
Patch B:
0x1E0F1
D0 -> E0

Patch A:
0x1E1C9
DC -> E0
```

The corresponding changed bytes in the verified GBL container are:

```text
0x00024645   D0 -> E0
0x0002471D   DC -> E0
```

The remaining changed GBL bytes belong to the rebuilt CRC32 field.

The combined patch therefore provides an experimental configuration in which:

```text
periodic mDNS restart
        |
        X

beacon recovery
        |
        X
```

while the normal connected firmware continues to operate.

---

# Runtime Validation of Combined Patch

A physical TRV running the combined Patch A+B was monitored for multiple hours.

During the monitored interval:

```text
Beacon skip error! Attempt recovery
```

was not observed.

The recurring transition into:

```text
Enter powersave state 1
```

associated with the targeted beacon recovery was also absent.

Normal RSSI-dependent beacon-skip operation remained visible.

Cloud connectivity remained operational during the tested period.

Separate packet capture also showed no targeted periodic mDNS sequence during
the monitored mDNS test window.

This provides runtime evidence that Patch A and Patch B can coexist and
suppress their respective targeted recurring mechanisms.

The test window is finite.

The result does not establish:

- indefinite stability
- long-term battery improvement
- complete elimination of every possible state-1 entry
- elimination of every possible mDNS transmission
- correction of the underlying WF200 beacon statistics

## Confidence

**RUNTIME CONFIRMED within the monitored test windows**

---

# No Explicit TX-Power Increase Found

A specific objective of this investigation was to determine whether recovery
increases WLAN transmit power.

No explicit TX-power-setting operation was identified in the normal recovery
path.

The WLAN command used to change the power-saving state is separate from the
commands associated with transmit-power control.

Therefore the supported statement is:

> No explicit increase of WLAN transmit power was identified in the normal
> beacon-recovery path.

This is different from proving that the protected WF200 implementation can
never alter lower-level RF behavior internally.

Some behavior remains inside the protected WLAN subsystem and cannot be fully
determined from the application firmware alone.

## Confidence

Explicit TX-power increase by the application recovery path:

**NOT OBSERVED**

Autonomous lower-level WF200 RF behavior:

**UNRESOLVED**

---

# No Normal Scan or Reconnect Found

The normal recovery path was examined for additional WLAN operations.

No direct normal recovery path was identified that performs:

- WLAN scanning
- access-point selection
- disconnect
- reconnect
- reassociation
- DHCP negotiation
- WLAN driver initialization
- full WLAN subsystem reset

The normal recovery mechanism is therefore substantially narrower:

```text
wake
  |
  v
Active / Always-On
  |
  v
temporary host sleep restriction
  |
  v
~5-second timeout
  |
  v
restore previous power state
```

A reconnect, scan or other network event occurring near a recovery event must
not automatically be attributed to the normal recovery mechanism without
additional evidence.

## Confidence

**NOT OBSERVED in the normal recovery path**

---

# Conditional Reset Path

A separate exceptional path was identified during reverse engineering.

If a relevant WLAN driver-lock operation fails, the firmware can initialize a
separate countdown with:

```text
3
```

When that countdown expires, the firmware can request a full MCU system reset.

This is separate from the normal beacon-recovery countdown.

The two mechanisms must not be confused.

Normal recovery:

```text
qualifying real_beacon_skip
        |
        v
countdown = 5
        |
        v
temporary Active / Always-On state
        |
        v
restore previous power state
```

Exceptional path:

```text
driver-lock failure
        |
        v
countdown = 3
        |
        v
MCU system reset
```

The existence of the reset path is established by static analysis.

It has not been established that this exceptional condition is responsible for
the normal recurring beacon-recovery events observed on the test devices.

## Confidence

Existence of the reset path:

**PROVEN**

Relevance to the observed normal recurring recovery:

**UNRESOLVED**

---

# Cached `real_beacon_skip` Behavior

Another control-flow characteristic may contribute to repeated recovery.

During recovery, the firmware clears the stored previous beacon-counter
reference.

However, it does not immediately clear the previously calculated:

```text
real_beacon_skip
```

value.

On a later eligible evaluation, a zero previous counter can cause calculation
of a new ratio to be skipped.

The previously stored `real_beacon_skip` value can therefore remain available
to the recovery test.

A possible sequence is:

```text
qualifying real_beacon_skip calculated
            |
            v
recovery triggered
            |
            v
previous beacon counter cleared
            |
            v
real_beacon_skip remains cached
            |
            v
later eligible evaluation
            |
            v
new ratio may not be calculated
            |
            v
cached value remains available
            |
            v
possible additional recovery
```

This behavior follows from the analyzed host-side control flow.

The exact contribution of this cached-value behavior to the real-device
approximately once-per-minute recovery pattern has not been independently
quantified.

It should therefore remain separate from the proven fact that recurring
recovery itself occurs at runtime.

## Confidence

**STRONG INFERENCE**

---

# Why Recovery Can Recur Approximately Once Per Minute

Runtime logs on affected stock firmware 2.2.4 devices show that the recovery
sequence can recur approximately once per minute.

The recovery check is serviced through the host-side minute-maintenance path.

Therefore the observed interval does not require a separate internal WF200
one-minute recovery timer.

Conceptually:

```text
WF200 statistics
        |
        v
host-side cached / calculated values
        |
        v
minute maintenance
        |
        v
recovery predicate
        |
        v
possible recovery
```

This explains why a qualifying condition can appear with a cadence closely
associated with `minutes_tick`.

The WF200 provides the statistics.

The application firmware decides whether to enter recovery.

---

# Energy-Consumption Relevance

The recovery mechanism contains several operations that can plausibly increase
energy consumption.

## Proven energy-relevant state changes

During normal recovery:

- the WLAN device is explicitly woken
- WLAN Active / Always-On mode is requested
- deeper host EM2 and EM3 sleep states are restricted
- additional control and bus activity occurs when entering and leaving the
  recovery state
- the condition normally persists for approximately five seconds

These operations are present in the firmware.

## Plausible consequences

They can plausibly result in:

- longer WF200 active time
- longer receiver-active time
- increased host-system energy use
- repeated additional energy use when recovery occurs frequently

The electrical magnitude has not been measured.

## Not identified in the normal recovery path

The normal recovery path does not show evidence of:

- explicit TX-power increase
- WLAN scanning
- normal disconnect/reconnect
- DHCP activity
- complete WLAN reinitialization

## Unresolved

The following remain unresolved:

- exact WF200 current during Active / Always-On operation in the TRV
- exact receiver-active duration
- lower-level WLAN signaling caused by the power-mode transition
- electrical energy consumed by one recovery event
- daily energy contribution of approximately once-per-minute recovery
- long-term battery-runtime improvement from suppressing recovery

---

# Relation to the Historical Battery Drain

The recovery mechanism provides a technically credible source of additional
energy consumption in firmware 2.2.4.

An affected device can repeatedly perform:

```text
normal power saving
        |
        v
Active / Always-On
        |
        | ~5 seconds
        v
normal power saving
        |
        | ~55 seconds
        v
recovery again
```

A device repeatedly leaving its normal low-power configuration can reasonably
be expected to consume more energy than the same device remaining
continuously in that power-saving configuration.

However, the reverse-engineering evidence does not establish the magnitude of
that difference.

More importantly, the historical battery-drain problem cannot currently be
reduced to this mechanism alone.

Battery drain was also observed historically on firmware 2.1.8, where the
specific counter-derived 2.2.4 recovery mechanism has not been identified.

There is also no current evidence establishing firmware 2.1.3 as universally
battery-drain free.

Therefore the supported interpretation is:

> The 2.2.4 beacon-recovery mechanism is a plausible additional source of
> energy consumption.

It is **not** currently established as:

> the original or sole cause of the historical Shelly TRV battery-drain
> problem.

Long-term battery testing is required to quantify its contribution.

---

# Relationship to Other Identified Mechanisms

The project has identified several potentially energy-relevant mechanisms that
must remain analytically separate.

## Periodic mDNS restart

Introduced into the examined connected-maintenance path by firmware 2.1.3 and
retained in later firmware.

Runtime:

```text
2.1.3
~60-second mDNS cycle

2.2.4 stock
~180-second mDNS cycle
```

Patch B suppresses the targeted periodic restart.

Beacon recovery continues.

Therefore periodic mDNS is not required for the observed recovery loop.

## Inherited WUP / EM2 retention path

A separate conditional low-level failure path can leave a WLAN-owned
sleep-blocking contribution retained.

That core path already exists in firmware 2.1.0.

It is therefore not the same mechanism as the 2.2.4 beacon recovery.

## Beacon recovery

Specific known 2.2.4 path:

```text
WF200 statistics
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        v
temporary Active / Always-On
```

These mechanisms can potentially contribute separately to total battery
consumption.

---

# Evidence Classification

| Finding | Status |
|---|---|
| Recovery is triggered by the qualifying `real_beacon_skip` condition | **PROVEN** |
| `real_beacon_skip` is derived from `beacon_rx_count` | **PROVEN** |
| The recovery predicate interprets the stored value as signed 8 bit | **PROVEN** |
| Recovery wakes the WLAN device | **PROVEN** |
| Recovery requests WLAN Active / Always-On mode | **PROVEN** |
| Recovery restricts host EM2/EM3 sleep | **PROVEN** |
| EM1 remains available | **PROVEN** |
| Normal recovery lasts approximately five seconds | **PROVEN** |
| The saved/deferred application power state is restored afterwards | **PROVEN** |
| The current `desired_beacon_skip` is reused when normal beacon power saving is restored | **PROVEN** |
| Recovery can occur with good RSSI and desired skip 20 | **RUNTIME CONFIRMED** |
| Patch A suppresses the targeted recurring recovery | **RUNTIME CONFIRMED** |
| Patch B suppresses periodic mDNS but not beacon recovery | **RUNTIME CONFIRMED** |
| Combined Patch A+B suppresses both targeted recurring mechanisms during monitored tests | **RUNTIME CONFIRMED** |
| Recovery explicitly increases WLAN TX power | **NOT OBSERVED** |
| Normal recovery performs a WLAN scan | **NOT OBSERVED** |
| Normal recovery performs disconnect/reconnect | **NOT OBSERVED** |
| A driver-lock failure can lead to a full MCU reset | **PROVEN, CONDITIONAL** |
| A cached qualifying value can remain available for another recovery evaluation | **STRONG INFERENCE** |
| Poor RSSI is required for recovery | **NOT SUPPORTED** |
| Periodic mDNS restart is required for recovery | **NOT SUPPORTED** |
| Repeated recovery adds some non-zero workload relative to uninterrupted power saving | **STRONGLY SUPPORTED** |
| Quantitative battery impact of recovery | **UNRESOLVED** |
| Recovery is the sole or original cause of the historical battery drain | **NOT PROVEN** |

---

# Open Questions

The host-side recovery control flow is now substantially understood.

The principal remaining questions are:

1. Why do the WF200 `beacon_rx_count` deltas produce values that firmware 2.2.4
   interprets as an invalid `real_beacon_skip`?

2. Is the host-side `600 / delta` interpretation appropriate for WF200
   power-save operation?

3. What are the exact WF200 beacon-counter semantics during intentional beacon
   skipping and DTIM handling?

4. How much electrical energy is consumed by one approximately five-second
   recovery event?

5. What is the quantitative daily energy contribution when recovery occurs
   approximately once per minute?

6. How much long-term battery-life improvement results from suppressing the
   recovery?

7. How often does cached-value reuse contribute to subsequent recovery
   evaluations?

8. Can specific AP behavior, DTIM configuration or other network conditions
   alter the frequency of qualifying counter deltas?

9. How does the additional 2.2.4 recovery contribution compare with older
   energy-relevant mechanisms such as periodic mDNS activity?

The main unresolved problem has therefore moved from:

```text
What does the recovery mechanism do?
```

toward:

```text
Why do the underlying WF200 statistics cause the host to enter it?
```

---

# Related Documents

The calculation controlling recovery is documented in:

[`real-beacon-skip.md`](real-beacon-skip.md)

The WF200 beacon statistic used as input is documented in:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

The periodic mDNS mechanism and its isolated Patch B experiment are documented
in:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

The broader version comparison is documented in:

[`firmware-comparison.md`](firmware-comparison.md)

The experimental recovery patch is documented in:

[`../patch/README.md`](../patch/README.md)

Together, the main beacon-recovery chain is currently understood as:

```text
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
delta
        |
        v
600 / delta
        |
        v
8-bit storage
        |
        v
signed interpretation
        |
        v
qualifying real_beacon_skip
        |
        v
host-side recovery decision
        |
        v
Active / Always-On WLAN
        |
        v
EM2 / EM3 restricted
        |
        v
~5 seconds
        |
        v
restore connected power saving
```

---

# Current Conclusion

The firmware 2.2.4 beacon-recovery mechanism is now well characterized at the
host-application level.

The evidence establishes that:

```text
qualifying real_beacon_skip
        |
        v
recovery
        |
        v
WLAN Active / Always-On
        |
        v
host EM2 / EM3 restricted
        |
        v
~5 seconds
        |
        v
restore previous / deferred state
```

Runtime testing adds three important constraints:

```text
good RSSI
does not prevent recovery
```

```text
periodic mDNS suppressed
does not prevent recovery
```

and:

```text
recovery branch bypassed
does suppress the targeted recovery
```

The combined Patch A+B experiment further shows that the two identified
recurring mechanisms can be suppressed together during monitored operation.

The remaining central question is therefore no longer whether the host-side
recovery exists or what it does.

The principal unresolved technical question is why the WF200 beacon statistics
produce counter deltas that firmware 2.2.4 interprets as requiring recovery.

The battery question remains separate:

> The recovery mechanism creates a plausible additional energy cost, but its
> quantitative contribution to the historical battery-drain problem has not
> yet been established.

---

# Research Methodology

This investigation is based on static reverse engineering of a locally
obtained Shelly TRV Gen1 firmware image together with runtime observations from
personally owned devices.

The recovery control flow was traced through:

- the WF200 statistics interface
- the `real_beacon_skip` calculation
- the application power-state logic
- the WLAN power-management interface
- the host sleep-resource handling
- the restoration path

Runtime experiments included:

- stock firmware debug-log observation
- `/stats` observation
- RSSI and desired-beacon-skip comparison
- isolated Patch A testing
- isolated Patch B testing
- combined Patch A+B testing
- passive mDNS packet capture

Public Silicon Labs WF200/fullMAC information was used where necessary to
interpret documented WLAN interface behavior.

The internal protected WF200 implementation is not reproduced.

No firmware images, complete proprietary functions or complete disassemblies
are published in this document.

The classifications:

```text
PROVEN
RUNTIME CONFIRMED
STRONG INFERENCE
STRONGLY SUPPORTED
NOT OBSERVED
NOT SUPPORTED
NOT PROVEN
UNRESOLVED
```

are deliberately used to distinguish static evidence, runtime evidence and
interpretation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the tested firmware version.

No conclusions about the intentions of the original developers are inferred
from these technical findings.