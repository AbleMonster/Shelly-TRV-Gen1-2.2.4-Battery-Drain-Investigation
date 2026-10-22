# `real_beacon_skip` Analysis

## Overview

Shelly TRV Gen1 firmware 2.2.4 maintains two different beacon-skip values:

- `desired_beacon_skip`
- `real_beacon_skip`

Despite the names, these values do not represent the same thing.

`desired_beacon_skip` is the listen interval requested by the Shelly host
application as part of its WLAN power-save policy.

`real_beacon_skip` is calculated by the host from WF200 received-beacon
statistics. It is an estimate based on the number of beacons received between
two statistics samples.

This distinction is important when interpreting `/stats` and the firmware log:

```text
Beacon skip error! Attempt recovery
```

The message does not represent a direct WF200 error indication.

In particular, `real_beacon_skip` is:

- not a readback of the listen interval programmed into the WF200
- not a direct indication of whether the WF200 is physically sleeping
- not a direct count of intentionally skipped beacons
- not a WF200 `PS_MODE_ERROR`

During reverse engineering of the 2.2.4 implementation, three separate
host-side problems were found in the way this value is calculated and used for
Beacon Recovery:

- **C1a** — signed interpretation of an unsigned calculated value
- **C1b** — reuse of a beacon-counter baseline across invalid measurement epochs
- **C2** — reuse of historical `real_beacon_skip` as fresh Recovery evidence

Patch C-C corrects these three cases while retaining Recovery for a genuinely
fresh measurement that produces `real_beacon_skip = 1` or `2`.

---

## `desired_beacon_skip`

`desired_beacon_skip` represents the beacon-skip interval selected by the
application.

The RSSI-dependent policy found in firmware 2.2.4 is:

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

This is a configuration value. It describes what the host requests from the
WF200 power-management path.

---

## `real_beacon_skip`

`real_beacon_skip` is calculated differently.

Firmware 2.2.4 periodically obtains WF200 statistics using command `0x66`.

The returned statistics include, among other fields:

```text
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

The `real_beacon_skip` calculation uses the cumulative:

```text
beacon_rx_count
```

and maintains a previous counter baseline.

For the following sections:

```text
C = current beacon_rx_count
P = previous beacon_rx_count
R = real_beacon_skip
```

For a valid comparison, the firmware calculates approximately:

```text
delta = C - P
R = uint8_t(600 / delta)
```

The constant `600` is present directly in the firmware.

Its exact original design rationale is not documented, but the surrounding
minute-based logic is consistent with an estimate based on roughly 600 nominal
beacon opportunities per measurement interval.

The important point is that the firmware derives `R` from received-beacon
density.

It does not query the WF200 for an effective beacon-skip value.

Therefore:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does **not** mean that the host requested skip 20 and the WF200 reported that it
was actually configured for skip 1.

The second value is only the result of the host-side estimator.

---

## `/stats`

The `real_beacon_skip` value exposed through `/stats` comes from the same
internal byte that is later used by Beacon Recovery.

There is no separate diagnostic calculation for the HTTP endpoint.

Conceptually:

```text
WF200 beacon_rx_count
        |
        v
host calculation
        |
        v
        R
       / \
      /   \
     v     v
 /stats   Recovery logic
```

This shared use becomes important because diagnostic history and control
evidence have different validity requirements.

Keeping the last calculated value available through `/stats` is useful.

Using that same historical value to trigger a new Recovery without a new
measurement is not.

---

# C1a — Signed Control Interpretation

The calculation of `R` is unsigned.

The result of:

```text
600 / delta
```

is narrowed to one byte:

```text
R = uint8_t(600 / delta)
```

The stock Beacon Recovery code later reads this byte as a **signed** value.

Its effective test is approximately:

```text
signed_R = int8_t(R)

if signed_R != 0 && signed_R <= 2:
    Recovery
```

This creates additional trigger values that are unrelated to the expected
positive `R = 1..2` condition.

Examples:

| Delta | `600 / delta` | Stored byte | Signed value | Stock Recovery |
|---:|---:|---:|---:|---|
| 1 | 600 | 88 | 88 | No |
| 2 | 300 | 44 | 44 | No |
| 3 | 200 | 200 | -56 | **Yes** |
| 4 | 150 | 150 | -106 | **Yes** |
| 5 | 120 | 120 | 120 | No |
| 6 | 100 | 100 | 100 | No |
| 200 | 3 | 3 | 3 | No |
| 201–300 | 2 | 2 | 2 | **Yes** |
| 301–600 | 1 | 1 | 1 | **Yes** |
| >600 | 0 | 0 | 0 | No |

The stock trigger domain for a fresh positive delta is therefore:

```text
delta = 3
delta = 4
delta = 201..600
```

The `delta = 3` and `delta = 4` cases exist only because the calculated
unsigned byte is later interpreted as signed.

For example:

```text
delta = 3

600 / 3 = 200

uint8_t(200) = 200
int8_t(200)  = -56

-56 != 0
-56 <= 2
```

Both Recovery conditions are true.

Patch C-C uses the value as unsigned for the Recovery decision, removing these
false trigger regions without changing the diagnostic byte itself.

---

# C1b — Measurement-Window Validity

The second problem is independent of the signed-value issue.

The calculation:

```text
600 / (C - P)
```

assumes that `C` and `P` describe the intended measurement interval.

However, `P` has no associated elapsed-time value.

Several identified firmware paths can suppress a normal statistics evaluation
or change the WLAN power-management state while preserving the old baseline.

One important example is the shared PM countdown used by the periodic
maintenance logic.

The same countdown can be set to values such as:

```text
H = 180
```

for a longer PM override and:

```text
H = 5
```

during Beacon Recovery.

While this countdown is active, the periodic Beacon Recovery statistics block
can be skipped.

Stock firmware can retain `P` across such a period.

The next successful statistics sample can therefore perform:

```text
old P
  |
  | measurement continuity interrupted
  |
new C

delta = new C - old P

R = 600 / delta
```

The cumulative WF200 counter can be completely correct while the derived value
is still invalid because the host is comparing two samples from different
logical measurement epochs.

A simple `C > P` check does not solve this. It proves only that the counter
increased, not that the two samples are temporally comparable.

Patch C-C invalidates the baseline when known events break the assumptions of
the measurement.

The next successful sample then establishes a new baseline instead of comparing
the current counter with stale history.

---

# C2 — Stale Recovery Evidence

C2 explains the repeating Beacon Recovery loop seen on affected stock 2.2.4
devices.

Assume a valid measurement produces:

```text
R = 2
```

Stock firmware accepts this and enters Beacon Recovery.

The Recovery path performs approximately:

```text
H = 5
enter power-save state 1
P = 0
```

but preserves:

```text
R = 2
```

Preserving `R` is not necessarily wrong. The value is useful as diagnostic
history.

The problem occurs during the next successful statistics evaluation.

Because:

```text
P == 0
```

the host cannot calculate a fresh delta. It therefore establishes a new
baseline:

```text
P = C
```

At this point the logical state is:

```text
new baseline available
no fresh R calculated
```

Stock firmware nevertheless continues to the Recovery test using the old
cached `R`.

The result is:

```text
fresh R = 2
    |
    v
Recovery
    |
    +---- P = 0
    |     R = 2 retained
    |
    v
next statistics sample
    |
    +---- P = C
    |     no fresh R calculated
    |
    v
old R = 2 tested again
    |
    v
Recovery
    |
    +---- P = 0
    |
    v
repeat
```

Once this state is reached, a new anomalous beacon measurement is no longer
required for every Recovery.

This explains how the stock 2.2.4 Recovery sequence can become self-sustaining.

It also explains why successful restoration of the WLAN power-save mode does
not necessarily stop the loop.

The radio can return successfully to normal power saving while the host keeps
reusing the same historical control value.

---

# Beacon Recovery

When the stock Recovery predicate accepts `R`, firmware 2.2.4 logs:

```text
Beacon skip error! Attempt recovery
```

The observed sequence is approximately:

```text
qualifying R
    |
    v
power-save state 1
    |
    v
Active / Always-On WLAN
    |
    | ~5 serviced seconds
    v
restore normal PM
    |
    v
power-save state 3
```

This is a real WLAN power-management action.

It is not merely a log message.

However, the name `Beacon skip error` should not be interpreted as a direct
WF200 error report.

The trigger is the host-derived `real_beacon_skip` value described above.

A separate WF200 `PS_MODE_ERROR` indication exists and is handled through a
different firmware path.

---

# Patch C-C

Patch C-C was designed to correct the host-side validity problems without
removing Beacon Recovery completely.

Its intended behavior is:

```text
preserve diagnostic R
preserve fresh R = 1..2 Recovery
reject signed-wrap triggers
invalidate unusable counter baselines
allow post-Recovery baseline establishment
reject historical R as new control evidence
```

For C1a, the Recovery decision uses the stored value as unsigned.

For C1b, known events that break measurement continuity invalidate `P`.

For C2, a baseline-only sample does not evaluate historical `R` as fresh
Recovery evidence.

The important distinction is:

```text
R may remain valid as diagnostic history

but

R is valid as Recovery control evidence only
when it came from a fresh, valid measurement
```

Patch C-C does not change the WF200 statistics command and does not remove the
`real_beacon_skip` calculation.

It also does not force a particular beacon-skip value.

Fresh `R = 1` or `R = 2` measurements can still trigger Recovery.

---

# Runtime Validation

Hardware testing has confirmed the main behavioral distinction Patch C-C was
designed to introduce.

With stock 2.2.4, a qualifying cached `R` can keep the Recovery loop alive by
causing the post-Recovery baseline sample to trigger Recovery again.

With Patch C-C, the post-Recovery sample can establish a new baseline without
reusing the historical value as control evidence.

A later fresh measurement may still produce:

```text
R = 1
```

or:

```text
R = 2
```

and trigger another Recovery.

This behavior has now been observed on hardware.

In recent tests using Patch C-C together with WF200 3.18.0, Recovery events no
longer follow the stock stale-value feedback pattern. A Recovery is followed by
a baseline-establishment interval, and a later fresh measurement can qualify
again.

This is an important result:

> Patch C-C removes the stale-value Recovery loop. It does not hide fresh
> measurements that still satisfy the Recovery condition.

The tests also show that the estimator is not permanently stuck at `1`.

Values much closer to the requested policy have been observed as well, for
example:

```text
desired_beacon_skip = 15
real_beacon_skip    = 13
```

This reinforces the distinction between the estimator itself and the conditions
under which a particular measurement becomes Recovery control evidence.

Fresh `R = 1..2` measurements are still under investigation.

---

# What `real_beacon_skip` Does Not Tell Us

A `real_beacon_skip` value should not be treated as a direct description of the
WF200 power-management state.

In particular, a low value does not by itself prove that:

- the programmed WF200 listen interval changed
- the WF200 rejected the requested power-save configuration
- the WF200 is not physically sleeping
- the TRV is listening to every AP beacon
- the AP changed its beacon interval
- RF transmit power increased
- packets were retransmitted
- the device changed access points
- poor RSSI caused the result
- a specific number of physical RF beacons was lost
- the WF200 generated a power-save error
- additional battery consumption occurred

The value tells us what the **Shelly host estimator calculated from received
beacon statistics**.

That is a much narrower statement.

The firmware's direct WF200 power-save error indication (`PS_MODE_ERROR`) is a
separate mechanism and should not be confused with Beacon Recovery.

---

# Relationship to `beacon_rx_missed_count`

WF200 statistics expose a separate:

```text
beacon_rx_missed_count
```

The known `real_beacon_skip` calculation does not use this field directly.

It uses:

```text
delta(beacon_rx_count)
```

instead.

Beacon Recovery is therefore not equivalent to:

```text
if missed_beacons > threshold:
    recover()
```

This distinction matters because intentionally skipped beacon opportunities
during power saving and unintentionally missed expected beacons do not
necessarily describe the same radio condition.

More details about the counter behavior are documented in
[`beacon-rx-counter.md`](beacon-rx-counter.md).

---

# Relationship to mDNS

Periodic mDNS and Beacon Recovery are separate mechanisms.

Testing with an experimental firmware variant that suppressed the targeted
periodic connected-state mDNS restart while leaving Beacon Recovery unchanged
showed that Beacon Recovery continued.

The targeted periodic mDNS restart is therefore not required for the observed
Recovery loop.

This does not mean that network traffic can never influence WF200 statistics.
It only separates the specific periodic mDNS mechanism from the Recovery defect
described here.

---

# Battery-Drain Relevance

Calculating `real_beacon_skip` itself is not the main energy concern.

The relevant sequence is the action triggered by a qualifying value:

```text
Recovery
   |
   v
state 1
   |
   v
more active WLAN state
   |
   | ~5 seconds
   v
restore power saving
```

On affected stock 2.2.4 devices, the C2 feedback loop can repeat this sequence
approximately once per minute.

With the stock stale-value loop, the observed worst-case cadence is therefore
approximately 60 Recovery events per hour.

At roughly five seconds per Recovery, this corresponds to:

```text
60 Recoveries/hour
× 5 seconds
= 300 seconds/hour
= 5 minutes/hour
≈ 8.33% of wall-clock time
```

spent in the explicit Recovery interval.

Patch C-C changes this significantly because a Recovery invalidates the
measurement baseline and the next eligible statistics sample is used only to
establish a new baseline.

With the current periodic measurement cadence, a fresh qualifying measurement
therefore cannot normally trigger Recovery on every measurement cycle.

The corresponding theoretical upper bound is approximately:

```text
30 fresh-triggered Recoveries/hour
× 5 seconds
= 150 seconds/hour
= 2.5 minutes/hour
≈ 4.17% of wall-clock time
```

Actual Recovery activity can be lower because a newly calculated
`real_beacon_skip` does not necessarily equal `1` or `2`.

For example, current hardware testing has shown approximately 27
fresh-triggered Recoveries per hour:

```text
27 × 5 seconds
≈ 135 seconds/hour
≈ 3.75% of wall-clock time
```

These percentages describe **time spent in the explicit Recovery interval**.

They do not mean:

```text
8.33% more battery consumption
4.17% more battery consumption
3.75% more battery consumption
```

The additional energy consumption cannot be calculated from these values alone
because the current difference between the normal power-save state and the
Recovery interval has not been measured.

The Recovery interval is nevertheless relevant because it deliberately moves
the WLAN subsystem into a more active state and temporarily prevents the normal
power-save progression.

One legitimate Recovery may be a reasonable reliability action.

A self-sustaining Recovery loop that repeatedly performs the same transition
without fresh evidence is a different situation.

This makes the stock 2.2.4 C2 loop a credible additional energy-consumption
mechanism.

It is not, by itself, proof that Beacon Recovery explains the complete Shelly
TRV Gen1 battery-drain problem.

Battery drain has also been observed on firmware versions that do not contain
the same 2.2.4 Recovery implementation.

The current interpretation is therefore:

- the 2.2.4 stale-Recovery loop is a real host-firmware defect
- it can create unnecessary repeated WLAN PM transitions
- Patch C-C removes that feedback loop
- fresh qualifying measurements can still occur
- the quantitative battery impact of both mechanisms requires long-term testing
- the historical TRV Gen1 battery-drain root cause may involve additional host
  and/or WF200 power-management behavior

No current measurement establishes the exact energy cost of one Recovery
cycle.

---

# Open Questions

## Why do fresh `R = 1..2` measurements still occur?

Patch C-C separates this question from the stale-value loop.

Fresh qualifying measurements have been observed even after the stale Recovery
feedback path was removed.

Possible contributors still include:

- actual AP/WF200 beacon behavior
- power-management transitions
- connection-state transitions
- timing of the host statistics window
- WF200 internal power-save behavior
- other timing conditions not yet identified

The current data is not sufficient to assign one of these as the cause.

---

## Is the Beacon Recovery heuristic required at all?

This remains an open question.

The analysis establishes how Shelly's `real_beacon_skip` estimator works and
identifies several defects in the way firmware 2.2.4 uses it.

It does not establish that this estimator is required for correct WF200
power-management operation.

No direct evidence has been found that:

- `real_beacon_skip = 1..2` means that the WF200 failed to enter power save
- the programmed listen interval was rejected or lost
- the WF200 is physically remaining awake
- forcing an Active-to-Power-Save transition is required to restore correct
  operation

The Recovery mechanism appears to use received-beacon density as an indirect
health check for WLAN power saving.

The original reason for introducing this heuristic is not known.

This question has become more relevant with the current experimental firmware.

The host-side A1 corrections address several power-management, transition and
ownership problems independently of Beacon Recovery.

WF200 3.18.0 also contains a Silicon Labs fix for an error that could prevent
the device from sleeping after a power-save mode change.

It is therefore not yet known whether the Beacon Recovery heuristic still
protects against a real failure condition after those underlying paths have
been corrected.

For this reason, Patch C-C currently retains Recovery for fresh valid
measurements instead of removing it completely.

A future controlled test with the Recovery action disabled may be useful to
determine whether the mechanism still provides any measurable benefit.

The current A1 + Patch C-C + WF200 3.18.0 long-term test should be completed
before making that change.

---

## What does the WF200 physically do during these windows?

The host-visible statistics do not provide a direct measurement of radio sleep
residency.

A successful power-save command confirms completion of the command path, but it
does not by itself prove how much time the radio subsequently spends asleep.

Likewise, `real_beacon_skip` cannot provide that proof.

This remains an important distinction when evaluating the battery-drain
problem.

---

## Why was the Recovery heuristic implemented this way?

The code shows what the firmware does, but not why the original implementation
chose received-beacon density as the Recovery criterion.

A plausible purpose is to detect a situation where the requested WLAN
power-save behavior does not appear to be effective and then force an
Active-to-Power-Save transition.

That remains an interpretation of the implementation, not confirmed developer
intent.

This is also one of the questions worth clarifying with Shelly:

> What actual WF200 or WLAN failure condition was `real_beacon_skip = 1..2`
> intended to detect, and why is an Active-to-Power-Save transition required
> to recover from that condition?

---

# Current Conclusion

`real_beacon_skip` is best described as a host-side estimate derived from WF200
received-beacon statistics:

```text
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
C - P
        |
        v
600 / delta
        |
        v
uint8_t R
        |
        v
host Recovery decision
```

It is not a WF200 listen-interval readback and it is not a direct measurement of
physical sleep.

Three separate host-side problems were identified in firmware 2.2.4:

### C1a

The unsigned calculated byte is interpreted as signed by the Recovery control
path, creating unintended trigger values.

### C1b

The previous beacon-counter baseline can survive events that invalidate the
logical measurement window.

### C2

After Recovery, the previous `real_beacon_skip` can remain valid as diagnostic
history but is incorrectly reused as fresh Recovery evidence during the next
baseline-only sample.

C2 explains the self-sustaining Recovery loop observed on affected stock 2.2.4
devices.

Patch C-C corrects these three cases while retaining Recovery for a genuinely
fresh `R = 1..2` measurement.

Hardware testing confirms that the stale feedback loop is removed while fresh
qualifying Recovery events can still occur.

At the observed periodic measurement cadence, this changes the Recovery
behavior from a stock worst case of approximately:

```text
60 Recoveries/hour
≈ 8.33% explicit Recovery time
```

to a fresh-measurement-limited theoretical maximum of approximately:

```text
30 Recoveries/hour
≈ 4.17% explicit Recovery time
```

with actual activity potentially lower when the fresh estimator does not
produce `R = 1..2`.

These values describe Recovery time, not battery percentage.

The remaining investigation has therefore moved beyond the original stale-value
loop.

The main questions are now:

```text
Why does the host sometimes derive a fresh real_beacon_skip of 1 or 2?

Does that value correspond to an actual WF200 power-save problem?

Does the Active-to-Power-Save Recovery correct anything measurable?

Is this Beacon Recovery heuristic still required after the host PM paths and
WF200 firmware have been corrected?
```

Until those questions are answered, Patch C-C deliberately keeps fresh valid
Recovery intact rather than simply disabling the mechanism.

---

# Related Documents

WF200 beacon-counter analysis:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Firmware comparison:

[`firmware-comparison.md`](firmware-comparison.md)

Periodic mDNS behavior:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Experimental patch documentation:

[`../patch/README.md`](../patch/README.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

## Research Notes

This analysis is based on static reverse engineering of locally obtained Shelly
TRV Gen1 firmware and runtime testing on personally owned devices.

The investigation uses native ARM Thumb control-flow analysis, cross-version
comparison, WF200 statistics analysis, runtime debug logs, `/stats` data and
controlled experimental firmware variants.

No original or modified Shelly firmware image, complete proprietary function,
or large raw disassembly is reproduced here.

This is an independent research project and is not affiliated with or endorsed
by Shelly Group or Silicon Labs.