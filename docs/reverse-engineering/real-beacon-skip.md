# `real_beacon_skip` Analysis

## Scope

This document describes the reverse-engineering findings for the
`real_beacon_skip` value exposed by Shelly TRV Gen1 firmware 2.2.4.

The purpose of this analysis is to determine:

- what the value represents
- where its input data originates
- how it is calculated
- how the 8-bit result is interpreted
- how it participates in the beacon-recovery decision
- what runtime observations confirm about the mechanism
- what remains unresolved about the underlying WF200 statistics

This document intentionally contains only the information required to describe
and reproduce the research findings.

It does not contain firmware images, complete disassemblies, complete
decompiled functions or proprietary source code.

---

# Summary

Firmware analysis shows that `real_beacon_skip` is not the configured
beacon-skip value sent to the WLAN subsystem.

Instead, it is an application-side value calculated from the change in the
WF200 cumulative received-beacon counter.

In simplified form, firmware 2.2.4 performs approximately:

```text
delta =
    current_beacon_rx_count
    -
    previous_beacon_rx_count

real_beacon_skip =
    uint8_t(600 / delta)
```

The result is stored in an 8-bit field.

Later, the recovery logic loads that field as a **signed 8-bit value**.

The effective recovery predicate is:

```text
real_beacon_skip != 0
&&
real_beacon_skip <= 2
```

This signed interpretation is important because some unsigned division results
above 127 become negative when interpreted as `int8_t`.

Those negative values also satisfy:

```text
<= 2
```

provided they are non-zero.

The same internal value is exposed through:

```text
/stats
```

as:

```text
real_beacon_skip
```

Runtime experiments further show that:

- recovery can occur with good RSSI
- recovery can occur while the desired beacon skip remains 20
- suppressing the periodic mDNS restart does not suppress beacon recovery
- bypassing the recovery branch suppresses the targeted recovery while normal
  RSSI-dependent beacon-skip behavior continues

The remaining major question is therefore not what the host-side recovery
predicate does.

That part is now understood.

The important unresolved question is:

> Why do the WF200 beacon counter deltas produce values that firmware 2.2.4
> interprets as an invalid `real_beacon_skip`, and is this host-side
> interpretation appropriate for WF200 power-save operation?

---

# `desired_beacon_skip` vs. `real_beacon_skip`

Firmware 2.2.4 maintains two conceptually different beacon-skip values.

They must not be treated as equivalent.

## `desired_beacon_skip`

`desired_beacon_skip` represents the beacon-skip interval that the application
wants the WLAN subsystem to use.

The analyzed firmware selects the desired value according to RSSI.

Observed policy:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

Conceptually:

```text
RSSI
  |
  v
desired_beacon_skip
  |
  v
requested WLAN power-save configuration
```

This is the configured or requested beacon power-saving behavior.

---

## `real_beacon_skip`

`real_beacon_skip` is different.

It is calculated from WF200 beacon reception statistics.

Conceptually:

```text
WF200 beacon statistics
        |
        v
beacon_rx_count
        |
        v
delta from previous sample
        |
        v
600 / delta
        |
        v
8-bit result
        |
        v
real_beacon_skip
```

Therefore a device can report:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

without this meaning that the WLAN subsystem has changed its configured
beacon-skip setting from 20 to 1.

The two values describe different concepts:

```text
desired_beacon_skip
        |
        +-- requested beacon power-saving configuration


real_beacon_skip
        |
        +-- host-side value derived from received-beacon statistics
```

This distinction is essential for interpreting both `/stats` and the recovery
log.

---

# Source of `real_beacon_skip`

Reverse engineering of the `/stats` generation path shows that the value
reported as:

```text
real_beacon_skip
```

is read from the same internal field used by the beacon-monitoring and recovery
logic.

No separate `real_beacon_skip` calculation is performed merely for the HTTP
statistics output.

Therefore:

```text
internal beacon-monitoring value
        |
        +---- recovery logic
        |
        +---- /stats real_beacon_skip
```

The value visible through `/stats` is therefore directly relevant to the
recovery decision.

## Confidence

**PROVEN**

---

# WF200 Statistics Source

Firmware 2.2.4 queries WF200 statistics through command:

```text
0x66
```

The returned statistics include values corresponding to:

```text
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

The value used for the known `real_beacon_skip` calculation is:

```text
beacon_rx_count
```

The application keeps both a current and previous sample.

The known calculation does not directly use:

```text
beacon_rx_missed_count
```

as its denominator or direct recovery input.

Likewise:

```text
beacon_tbtt_diff
```

is not used as the direct input to the known ratio calculation.

The exact low-level semantics of all WF200 beacon counters under power-save
operation remain an important open research question.

In particular, this document does not assume without further evidence exactly
how intentionally skipped beacon opportunities are represented in every WF200
statistics field.

For the detailed statistics investigation, see:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

---

# Calculation

When the required counter conditions are satisfied, firmware 2.2.4 calculates
approximately:

```text
delta =
    current_beacon_rx_count
    -
    previous_beacon_rx_count
```

followed by:

```text
ratio =
    600 / delta
```

The division is unsigned.

The result is then narrowed to an 8-bit value:

```text
real_beacon_skip =
    uint8_t(ratio)
```

Later, the recovery condition reads that stored byte as a signed 8-bit value.

The important type sequence is therefore:

```text
beacon_rx_count delta
        |
        v
unsigned division
        |
        v
600 / delta
        |
        v
low 8 bits stored
        |
        v
uint8_t field
        |
        v
later signed-byte load
        |
        v
int8-style comparison
```

This type conversion is central to understanding the recovery behavior.

## Confidence

**PROVEN**

---

# Interpretation of the Constant `600`

The mathematical use of the constant:

```text
600
```

is proven by the firmware.

The original engineering rationale for choosing that exact constant is not
explicitly documented in the application firmware.

The surrounding logic supports the interpretation that the calculation is
intended to estimate an effective relationship between expected beacon
opportunities and actually received beacons over the relevant measurement
window.

Conceptually:

```text
nominal beacon opportunities
            /
received beacons during interval
            =
estimated effective beacon skip
```

This interpretation is consistent with the variable's use and the surrounding
beacon-monitoring logic.

However, the exact intended model remains an inference.

In particular, without fully establishing the WF200 counter semantics under all
power-save conditions, the calculation should not be described as a direct
measurement of the hardware's actual configured skip interval.

## Confidence

**STRONG INFERENCE**

The mathematical operation is proven.

The original design intent behind the constant `600` is not.

---

# Recovery Condition

After calculation, or when evaluating the cached value, firmware 2.2.4 reads
`real_beacon_skip` as a signed 8-bit value.

The effective recovery condition is:

```text
real_beacon_skip != 0
&&
real_beacon_skip <= 2
```

When this condition evaluates true, the firmware enters the identified
beacon-recovery path.

Runtime logging then produces:

```text
Beacon skip error! Attempt recovery
```

followed by the recovery power-management sequence.

The detailed state transition is documented in:

[`recovery-mechanism.md`](recovery-mechanism.md)

## Confidence

**PROVEN**

---

# Signed 8-Bit Behavior

The combination of:

```text
unsigned division
```

followed by:

```text
8-bit truncation
```

and later:

```text
signed-byte interpretation
```

creates non-obvious edge cases.

Examples:

| Beacon counter delta | `600 / delta` | Stored byte | Signed interpretation | Recovery |
|---:|---:|---:|---:|---|
| 1 | 600 | 88 | 88 | No |
| 2 | 300 | 44 | 44 | No |
| 3 | 200 | 200 | -56 | Yes |
| 4 | 150 | 150 | -106 | Yes |
| 5 | 120 | 120 | 120 | No |
| 200 | 3 | 3 | 3 | No |
| 201-300 | 2 | 2 | 2 | Yes |
| 301-600 | 1 | 1 | 1 | Yes |
| >= 601 | 0 | 0 | 0 | No |

For example:

```text
delta = 3

600 / 3 = 200

uint8_t(200) = 200

int8_t(200) = -56
```

The recovery predicate then evaluates:

```text
-56 != 0
```

and:

```text
-56 <= 2
```

Both conditions are true.

Therefore the recovery path can be entered even though the unsigned calculated
ratio was:

```text
200
```

rather than:

```text
1 or 2
```

This behavior is not hypothetical arithmetic added by the analysis.

It follows directly from the observed storage width and later signed-byte
comparison.

## Confidence

**PROVEN**

---

# Trigger Regions

Because of the 8-bit conversion and signed comparison, the recovery predicate
cannot be understood simply as:

```text
calculated skip is 1 or 2
```

Some much larger unsigned values can also become qualifying negative signed
values.

Conceptually, the host logic behaves like:

```text
ratio = 600 / delta

stored = uint8_t(ratio)

signed_value = int8_t(stored)

if signed_value != 0 and signed_value <= 2:
    recovery
```

Therefore the accepted set includes:

```text
1
2
```

but can also include:

```text
negative signed values
```

created by the 8-bit conversion.

This considerably broadens the set of counter deltas capable of entering the
recovery path.

---

# Cached-Value Behavior

The calculated value is not necessarily replaced during every later
evaluation.

One relevant control-flow case occurs when the previous beacon counter
reference has been cleared.

Under such a condition, the firmware can skip calculation of a new ratio while
the previously stored `real_beacon_skip` byte remains available to the later
recovery test.

The recovery path clears the previous beacon-counter reference but does not
immediately clear the cached `real_beacon_skip` field.

A possible sequence is therefore:

```text
valid counter pair
        |
        v
calculate qualifying real_beacon_skip
        |
        v
recovery
        |
        v
previous beacon counter cleared
        |
        v
cached real_beacon_skip remains
        |
        v
next evaluation may not calculate a replacement value
        |
        v
old qualifying byte remains available
```

Static analysis establishes that this stale-value situation is possible.

Care is required when extending that result to repeated runtime behavior.

The exact contribution of cached-value reuse to the observed approximately
once-per-minute recovery sequence has not been independently quantified.

## Confidence

**STRONG INFERENCE**

---

# Runtime Observation: Repeating Recovery

On affected stock firmware 2.2.4 devices, the following sequence has been
observed repeatedly:

```text
minutes_tick: Beacon skip error! Attempt recovery
```

followed by:

```text
Enter powersave state 1
```

and approximately five seconds later:

```text
Enter powersave state 3 (skip N)
```

On affected devices, this can recur approximately once per minute.

The recurrence is consistent with the host-side minute-maintenance evaluation.

The approximately 60-second interval therefore does not require a separate
internal WF200 60-second recovery timer to explain it.

The WF200 provides statistics.

The application firmware evaluates those statistics from its host-side
maintenance path.

---

# Runtime Observation: Good RSSI

The recovery mechanism was initially observed under varying Wi-Fi conditions.

Later testing established that poor RSSI is not required.

On the mDNS-only Patch B test device, recovery was observed with RSSI around:

```text
-58 to -59 dBm
```

while the normal RSSI policy selected:

```text
desired_beacon_skip = 20
```

The device nevertheless continued to enter:

```text
Beacon skip error! Attempt recovery
```

This provides an important constraint on the mechanism.

The recovery cannot be explained simply as:

```text
poor RSSI
        |
        v
reduced desired beacon skip
        |
        v
recovery
```

Instead, the recovery predicate can become true while the reported signal
strength is good and the desired skip remains at its highest normal value.

---

# Runtime Observation: mDNS Isolation

A separate experiment tested whether the recurring periodic mDNS restart was
required for the `real_beacon_skip` recovery behavior.

Firmware 2.2.4 was modified with an mDNS-only patch that bypasses the periodic
connected-maintenance `mdns_resp_restart()` call.

The beacon statistics and recovery code were intentionally left unchanged.

Runtime packet capture confirmed that the targeted recurring mDNS bursts were
suppressed during the monitored test window.

Despite that:

```text
Beacon skip error! Attempt recovery
```

continued to occur approximately once per minute.

Therefore:

> The periodic mDNS restart is not required for the observed
> `real_beacon_skip` recovery loop under the tested conditions.

This result helps separate two previously plausible mechanisms:

```text
periodic mDNS activity
```

and:

```text
beacon-statistics-derived recovery
```

A secondary interaction under other network conditions is not categorically
excluded.

However, periodic mDNS cannot currently be treated as a necessary trigger for
the observed recovery loop.

---

# Experimental Beacon-Recovery Patch

The experimental beacon-recovery patch, referred to elsewhere in the project
as Patch A, bypasses the identified recovery branch.

It does not modify:

- the RSSI-based desired beacon-skip calculation
- the desired beacon-skip value
- command `0x66`
- the WF200 beacon statistics
- `beacon_rx_count`
- the `real_beacon_skip` calculation
- the protected WF200 firmware
- the periodic mDNS mechanism

Conceptually:

```text
WF200 statistics
        |
        v
beacon_rx_count
        |
        v
real_beacon_skip calculation
        |
        v
recovery predicate
        |
        X
targeted recovery action bypassed
```

The patch therefore isolates the recovery action from the underlying
statistics calculation.

Runtime testing showed that normal RSSI-dependent beacon-skip behavior
continues while the recurring targeted recovery is suppressed.

This is important because the patch should **not** be described as:

```text
fixing beacon statistics
```

or:

```text
changing real_beacon_skip
```

The accurate description is:

> Patch A bypasses the identified recovery action triggered by the
> `real_beacon_skip` evaluation.

The underlying reason for the qualifying counter-derived values remains an
open research question.

---

# Relationship to Power-Save State

When the recovery condition is accepted, firmware 2.2.4 temporarily requests:

```text
power-save state 1
```

The analyzed recovery path places the WLAN subsystem into a more active
configuration than the normal connected state 3.

During the temporary recovery interval:

```text
state 1
        |
        +-- active / always-on WLAN configuration
        |
        +-- deeper host sleep blocked
```

After approximately five seconds, the saved or deferred power-save state is
restored.

Under normal connected operation this is typically:

```text
state 3
```

with the current RSSI-dependent desired beacon skip.

No explicit transmit-power increase was identified in this recovery path.

The energy concern is therefore the temporary more-active power-management
state and blocked deeper host sleep, not a demonstrated increase in RF
transmit power.

---

# What `real_beacon_skip` Does Not Prove

A low or qualifying `real_beacon_skip` value does not by itself prove that:

- the WLAN subsystem changed its configured beacon-skip interval
- the access point changed its beacon interval
- the TRV is listening to every beacon
- Wi-Fi transmit power increased
- packets were retransmitted
- the device changed access points
- poor RSSI caused the value
- a specific number of RF beacons was physically lost
- the periodic mDNS restart caused the value
- additional battery consumption occurred

`real_beacon_skip` is an application-side value calculated from WLAN
statistics and used as an input to a host-side recovery decision.

Those other behaviors require separate evidence.

---

# Relationship to `beacon_rx_missed_count`

The WF200 statistics returned to the application also contain a separate
missed-beacon value.

The known `real_beacon_skip` calculation does not directly use that value.

Instead:

```text
real_beacon_skip
        |
        v
derived from delta(beacon_rx_count)
```

This is an important distinction.

It means that the host-side recovery logic is not simply testing:

```text
number of missed beacons
```

and recovering when that number exceeds a threshold.

The exact semantics of the WF200 received- and missed-beacon counters under
intentional beacon skipping, DTIM handling and other power-save behavior
remain part of the deeper WF200 investigation.

Until those semantics are established with sufficient confidence, the
missed-beacon counter should not be used to infer a precise number of
unintentional RF reception failures.

---

# Why the Host-Side Interpretation Is Questionable

The current investigation has established what firmware 2.2.4 does with the
statistics.

It has not yet established that this interpretation is semantically correct
for all WF200 power-save modes.

The host effectively assumes that:

```text
change in received-beacon count
```

can be transformed through:

```text
600 / delta
```

into a useful representation of effective beacon skipping.

The resulting byte is then treated as an error condition when its signed value
is non-zero and `<= 2`.

Several aspects require further investigation:

```text
WF200 beacon counter semantics
        |
        +-- when is beacon_rx_count incremented?
        |
        +-- what happens during intentional beacon skipping?
        |
        +-- how does DTIM behavior affect the counters?
        |
        +-- what exactly is counted as missed?
        |
        +-- how do power-save state transitions affect sampling?
```

The signed-byte behavior adds another concern because values that do not
numerically resemble skip values `1` or `2` can nevertheless satisfy the
predicate after conversion.

The appropriate conclusion is therefore not:

```text
WF200 is faulty
```

but:

> The correctness of the host-side interpretation of the WF200 statistics
> remains unresolved.

---

# Battery-Drain Relevance

`real_beacon_skip` is the calculated value controlling entry into the known
2.2.4 beacon-recovery path.

The calculation itself does not establish battery drain.

The energy-relevant sequence begins when a qualifying value causes:

```text
recovery
        |
        v
state 1
        |
        v
more active WLAN configuration
        |
        v
deeper host sleep blocked
        |
        v
approximately five seconds
        |
        v
restore normal power-save state
```

If this sequence occurs approximately once per minute, it creates a recurring
additional active interval.

This makes the recovery mechanism a credible additional energy-consumption
candidate.

However, the following remain unmeasured:

```text
current during state 1
additional current relative to state 3
energy per recovery
daily energy contribution
battery-runtime reduction
```

Therefore:

> The relationship between `real_beacon_skip` and recurring recovery is
> established.

But:

> The quantitative contribution of those recovery events to the historical
> battery-drain problem remains unproven.

This distinction is particularly important because battery drain was also
observed historically on firmware older than 2.2.4.

The 2.2.4 recovery mechanism may therefore represent an additional contributor
rather than the original or sole cause.

---

# Evidence Classification

| Finding | Status |
|---|---|
| `/stats` exposes the internal `real_beacon_skip` field | **PROVEN** |
| Firmware 2.2.4 obtains WF200 beacon statistics through command `0x66` | **PROVEN** |
| `real_beacon_skip` is derived from the change in `beacon_rx_count` | **PROVEN** |
| The calculation uses `600 / delta` | **PROVEN** |
| The division result is narrowed to 8 bits | **PROVEN** |
| The stored byte is later interpreted as signed | **PROVEN** |
| Recovery is accepted for non-zero signed values `<= 2` | **PROVEN** |
| Negative wrapped values can satisfy the recovery predicate | **PROVEN** |
| `beacon_rx_missed_count` is not directly used in the known ratio calculation | **PROVEN** |
| `600 / delta` is intended as an effective beacon-skip estimate | **STRONG INFERENCE** |
| A cached qualifying value can remain available after the previous counter reference is cleared | **STRONG INFERENCE** |
| Recovery can occur with good RSSI and desired skip 20 | **RUNTIME CONFIRMED** |
| Periodic mDNS restart is required for beacon recovery | **NOT SUPPORTED** |
| Patch A changes the `real_beacon_skip` calculation | **NOT SUPPORTED** |
| `real_beacon_skip` proves the actual configured WLAN skip | **NOT SUPPORTED** |
| `real_beacon_skip` proves increased TX power | **NOT SUPPORTED** |
| Poor RSSI is required for recovery | **NOT SUPPORTED** |
| The calculation alone proves the historical battery-drain cause | **NOT SUPPORTED** |

---

# Open Questions

The host-side calculation and recovery predicate are now substantially
understood.

The primary unresolved questions have moved deeper into the WF200 statistics
semantics.

Current open questions include:

1. What exactly causes `beacon_rx_count` to increment under each WF200
   power-save configuration?

2. How are intentionally skipped beacon opportunities represented in the
   WF200 statistics?

3. What are the precise semantics of `beacon_rx_missed_count` during Fast
   Power Save operation?

4. How do DTIM reception, multicast/broadcast handling and access-point beacon
   behavior affect the statistics?

5. Why do real devices produce counter deltas that lead firmware 2.2.4 to
   derive qualifying `real_beacon_skip` values?

6. Is the `600 / delta` calculation appropriate for the statistics returned by
   the WF200 under the TRV's configured power-save behavior?

7. Was the signed interpretation of the stored 8-bit result intentional?

8. How much electrical energy is consumed by each resulting recovery event?

9. How much does suppressing the recovery change long-term battery endurance?

These questions should be kept separate from the already resolved question of
what the host-side `real_beacon_skip` field represents.

---

# Current Conclusion

The host-side `real_beacon_skip` mechanism in firmware 2.2.4 is now well
characterized.

The known path is:

```text
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
current - previous
        |
        v
delta
        |
        v
600 / delta
        |
        v
uint8_t
        |
        v
signed-byte interpretation
        |
        v
real_beacon_skip != 0
&&
real_beacon_skip <= 2
        |
        v
beacon recovery
```

The key findings are:

- `real_beacon_skip` is not the requested WLAN beacon-skip configuration
- it is derived from WF200 received-beacon statistics
- the result is narrowed to 8 bits
- it is later interpreted as signed
- negative wrapped values can therefore satisfy the recovery condition
- the recovery can occur even with good RSSI and desired skip 20
- periodic mDNS activity is not required for the observed recovery loop
- Patch A suppresses the recovery action without changing the underlying
  statistics calculation

The principal unresolved issue is now the semantic validity of the
host-side interpretation of the WF200 beacon statistics.

That question belongs to the deeper WF200 counter investigation rather than
the already resolved identification of `real_beacon_skip`.

---

# Research Methodology

The analysis was performed using static reverse engineering of a locally
obtained Shelly TRV Gen1 firmware image together with runtime observations from
personally owned devices.

Public Silicon Labs WF200/fullMAC documentation was used where necessary to
interpret documented WLAN interface structures and behavior.

Runtime experiments included:

- debug-log observation
- `/stats` comparison
- RSSI and desired-skip observation
- an isolated beacon-recovery patch
- an isolated periodic-mDNS patch
- a combined experimental patch

No Shelly firmware image, complete proprietary function or complete
disassembly is reproduced in this document.

The terminology:

```text
PROVEN
STRONG INFERENCE
RUNTIME CONFIRMED
NOT SUPPORTED
UNRESOLVED
```

is used deliberately to distinguish direct binary evidence, runtime evidence
and interpretation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the tested firmware version and should not be interpreted as a statement
about design intent.