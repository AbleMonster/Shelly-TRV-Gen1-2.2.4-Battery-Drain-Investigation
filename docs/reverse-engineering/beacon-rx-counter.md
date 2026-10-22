# Beacon RX Counter Analysis

## Scope

This document describes the beacon statistics used by Shelly TRV Gen1 firmware
2.2.4 and how the host firmware derives `real_beacon_skip` from the cumulative
WF200 received-beacon counter.

The relevant path is:

```text
WF200 statistics
      |
      | command 0x66
      v
received-beacon counter C
      |
      | compare with previous baseline P
      v
delta = C - P
      |
      v
600 / delta
      |
      v
8-bit cached value R
      |
      v
Beacon Recovery decision
```

The important distinction is that `real_beacon_skip` is not a direct WF200
power-save state and is not a direct report of the currently programmed beacon
skip.

It is a host-calculated value derived from the change of a cumulative WF200
statistic.

This document focuses on:

- the origin of the beacon statistics
- WF200 statistics command `0x66`
- the host-side baseline `P`
- the calculation of `real_beacon_skip`
- measurement-window validity
- the relationship between the cached value and Beacon Recovery
- the remaining boundary between known host behavior and protected WF200
  internals

The arithmetic and signed-value problem are also discussed in:

[`real-beacon-skip.md`](real-beacon-skip.md)

The complete recovery path is documented in:

[`recovery-mechanism.md`](recovery-mechanism.md)

---

## Summary

Firmware 2.2.4 does not count received WLAN beacons directly in the Shelly
application.

Instead, the host periodically requests statistics from the WF200 subsystem
using command:

```text
0x66
```

The returned statistics contain, among other fields:

```text
received beacon count
missed beacon count
TBTT difference
```

The host uses the cumulative received-beacon count for the known
`real_beacon_skip` calculation.

For clarity, this document uses:

```text
C = current cumulative received-beacon count
P = previous host-side received-beacon baseline
R = cached real_beacon_skip byte
```

When a usable previous baseline exists and the counter has increased, the host
approximately performs:

```text
delta = C - P

R = uint8_t(600 / delta)

P = C
```

The missed-beacon counter and TBTT-difference field are not used to normalize
this calculation.

Three separate host-side problems were identified around this mechanism:

```text
C1a
signed interpretation of the 8-bit R value

C1b
measurement-window / baseline validity

C2
historical R reused as current recovery evidence
```

These defects exist in the host application and do not require the WF200
statistics themselves to be faulty.

The exact internal meaning of all WF200 beacon statistics remains partly
unknown because the protected WF200 implementation has not been fully reverse
engineered.

---

## WF200 Statistics Source

The beacon statistics consumed by the Shelly application originate in the
WF200 WLAN subsystem.

The host requests them through:

```text
command 0x66
```

Conceptually:

```text
Shelly host application
        |
        | command 0x66
        v
WF200 WLAN subsystem
        |
        | statistics response
        v
host-side statistics structure
```

The relevant returned values include:

```text
received beacon count
missed beacon count
TBTT difference
```

The Shelly application therefore consumes beacon statistics maintained by the
WLAN subsystem rather than incrementing its own application-level counter for
every received beacon.

The exact protected WF200 code responsible for maintaining these statistics is
outside the host application.

---

## Received-Beacon Counter

The received-beacon field is a cumulative WF200 statistic.

For example:

```text
P = 12000
C = 12030
```

The host does not directly use:

```text
12030
```

as the Beacon Recovery measurement.

Instead it calculates:

```text
delta = C - P
      = 30
```

The known recovery measurement therefore depends on the difference between two
cumulative samples.

This distinction is important:

```text
absolute received-beacon count
              !=
real_beacon_skip
```

and:

```text
WF200 received-beacon statistic
              !=
currently programmed beacon skip
```

The exact internal WF200 event that increments the cumulative received-beacon
counter has not been independently reconstructed.

That uncertainty matters when trying to reproduce the original engineering
model, but it does not prevent analysis of the host-side arithmetic and
baseline lifecycle.

---

## Missed-Beacon Counter

Command `0x66` also returns a separate missed-beacon statistic.

The host stores this value, but the identified `real_beacon_skip` calculation
does not directly use it.

The firmware does not calculate a ratio such as:

```text
received
------------------
received + missed
```

for the Beacon Recovery decision.

Instead, the known calculation uses:

```text
600 / (C - P)
```

where `C` and `P` are cumulative received-beacon samples.

The exact treatment of deliberately skipped beacon opportunities by the WF200
missed-beacon statistic remains unknown.

This is especially relevant under Fast Power Save because a beacon that the
radio intentionally does not wake for must not automatically be interpreted
as an RF reception failure.

---

## TBTT Difference

The returned statistics also contain a TBTT-related value.

TBTT means:

```text
Target Beacon Transmission Time
```

This field contains timing-related information.

It is not used as the timebase for the identified `real_beacon_skip`
calculation.

In particular, the host does not perform:

```text
received-beacon delta
        /
measured TBTT interval
```

or otherwise normalize `C - P` using the returned TBTT-difference field.

This becomes important when considering the validity of the fixed numerator
`600`.

---

## Host-Side Calculation

With a usable previous baseline:

```text
P != 0
```

and a newer cumulative value:

```text
C > P
```

the host approximately performs:

```text
delta = C - P

quotient = 600 / delta

R = uint8_t(quotient)

P = C
```

The resulting byte `R` is cached and later consumed by the Beacon Recovery
logic.

The complete path is therefore:

```text
command 0x66
      |
      v
current received count C
      |
      +---- previous baseline P
      |
      v
C - P
      |
      v
delta
      |
      v
600 / delta
      |
      v
8-bit R
      |
      v
Beacon Recovery predicate
```

The arithmetic is clear from the host firmware.

What is not explicitly documented by the firmware is the original engineering
reasoning behind treating the resulting quotient as an effective beacon-skip
measurement.

---

## The Fixed Numerator `600`

The numerator:

```text
600
```

is hard-coded.

The surrounding logic is consistent with the firmware trying to infer an
effective beacon-skip relationship from the number of received beacons over an
assumed measurement interval.

A conceptual interpretation is:

```text
nominal beacon opportunities
            /
received beacons
            =
effective beacon skip
```

The important implementation detail is that the host does not store a
corresponding elapsed-time value together with `P`.

The calculation therefore assumes that the interval represented by:

```text
C - P
```

matches the interval represented by the fixed numerator:

```text
600
```

If the baseline survives longer than intended, the cumulative counter can be
perfectly correct while the resulting quotient is no longer representative of
the intended measurement window.

This is a host-side measurement-validity issue.

---

## Normal Baseline Lifecycle

Under normal conditions a previous baseline exists:

```text
P != 0
```

A later statistics request returns:

```text
C > P
```

The host calculates:

```text
delta = C - P
R = 600 / delta
```

and then updates:

```text
P = C
```

Conceptually:

```text
sample 1
C = 1000
      |
      v
P = 1000
      |
      | valid measurement interval
      v
sample 2
C = 1030
      |
      v
delta = 30
      |
      v
fresh R
      |
      v
P = 1030
```

This provides a sequence of comparable measurements as long as the baseline
remains valid.

---

## Baseline Establishment

When:

```text
P == 0
```

there is no previous cumulative sample from which a new delta can be
calculated.

The host therefore installs:

```text
P = C
```

as the new baseline.

No fresh:

```text
600 / delta
```

measurement exists on that pass.

This is fundamental to understanding the later recovery loop:

> A baseline-only sample cannot provide new `real_beacon_skip` evidence.

A valid new measurement requires another later sample.

---

## Counter Reset or Decrease

The firmware also handles:

```text
C <= P
```

without performing an unsigned subtraction that could underflow.

The relevant state is reset approximately as:

```text
R = 0
P = C
```

This handles cases where the cumulative counter has reset, decreased, or
otherwise can no longer be compared normally with the previous baseline.

---

## Statistics Acquisition Failure

If command `0x66` fails, stock firmware clears both:

```text
P = 0
R = 0
```

The next successful statistics request must therefore establish a new baseline
before another fresh ratio can be calculated.

This is different from the Beacon Recovery path discussed below, where `P` is
cleared but `R` is retained.

That difference is important.

---

## C1a — Signed Interpretation of `R`

The quotient:

```text
600 / delta
```

is stored in an 8-bit field.

The stock recovery predicate later interprets this byte as a signed value.

This changes the set of values that qualify for recovery.

For example:

```text
delta = 3

600 / 3 = 200

uint8_t:
0xC8

signed int8:
-56
```

and:

```text
delta = 4

600 / 4 = 150

uint8_t:
0x96

signed int8:
-106
```

The stock predicate rejects zero and accepts values less than or equal to `2`.

As a result, these negative signed interpretations unexpectedly satisfy the
predicate.

The fresh stock trigger set becomes:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

The `delta = 3` and `delta = 4` cases are therefore created by the signed
interpretation of the stored byte.

They are not evidence that the WF200 reported a negative or otherwise invalid
beacon count.

Patch C-C changes the control interpretation to unsigned while preserving the
diagnostic byte.

See [`real-beacon-skip.md`](real-beacon-skip.md) for the complete arithmetic
analysis.

---

## C1b — Measurement-Window Validity

The second problem concerns the age of `P`.

The formula:

```text
600 / (C - P)
```

only has the intended meaning if `P` and `C` delimit the measurement interval
assumed by the constant `600`.

Stock firmware does not attach an elapsed-time value to `P`.

More importantly, firmware paths exist where an expected measurement
opportunity is skipped while the old baseline survives.

Conceptually:

```text
P established
      |
      v
expected measurement opportunity skipped
      |
      v
P retained
      |
      v
another opportunity skipped
      |
      v
P retained
      |
      v
later C
      |
      v
600 / (C - P)
```

The later counter delta can therefore span a longer logical interval than the
fixed numerator assumes.

This does not require the WF200 counter to be wrong.

The failure can occur with two completely correct cumulative counter values:

```text
correct old cumulative value P
              +
correct later cumulative value C
              +
wrong assumption about elapsed measurement window
              =
invalid host-side derived value
```

This is why reconstructing every internal detail of the protected WF200
counter is not required to identify the host-side baseline-validity problem.

---

## C2 — Historical `R` Reused as Current Control Evidence

The third problem occurs after Beacon Recovery.

Stock recovery clears:

```text
P
```

but retains:

```text
R
```

After a qualifying recovery the state can therefore become:

```text
P = 0
R = historical qualifying value
```

At the next successful `0x66` request, the firmware can only establish:

```text
P = C
```

because no previous baseline exists.

No fresh `R` is calculated on that pass.

However, the stock control flow subsequently evaluates the retained historical
`R`.

If it still satisfies the recovery predicate, another recovery occurs and `P`
is cleared again.

Conceptually:

```text
fresh qualifying R
      |
      v
Beacon Recovery
      |
      +---- P = 0
      |
      +---- R retained
      |
      v
next successful 0x66
      |
      v
P == 0
      |
      v
P = C
      |
      | no fresh R calculated
      v
historical R evaluated
      |
      v
Beacon Recovery again
      |
      v
P = 0
```

The newly established baseline never survives long enough to reach the next
comparable sample.

This produces the self-sustaining recovery behavior observed on affected stock
2.2.4 devices.

The important distinction is not simply that `R` is retained.

Retaining the most recent diagnostic value can be perfectly reasonable.

The defect is that:

```text
historical diagnostic value
```

is subsequently treated as:

```text
fresh control evidence
```

on a pass where no fresh measurement was made.

---

## Why the WF200 Counter Does Not Need to Be Faulty

Earlier stages of this investigation placed considerable emphasis on
determining exactly how the protected WF200 firmware counts received and missed
beacons.

That remains useful for understanding the original design.

It is no longer necessary for establishing C1a, C1b or C2.

Assume:

```text
WF200 cumulative received-beacon counter
=
completely correct
```

C1a can still occur because the host interprets the resulting 8-bit quotient
as signed.

C1b can still occur because the host can compare correct cumulative values
across an invalid measurement window.

C2 can still occur because the host can reuse an old derived value after
clearing the baseline from which that value was originally calculated.

These are independent host-side properties.

---

## `desired_beacon_skip` and `real_beacon_skip`

The firmware contains two values that are easy to confuse.

The requested WLAN power-save parameter is:

```text
desired_beacon_skip
```

The counter-derived value is:

```text
real_beacon_skip
```

They do not represent the same thing.

The normal desired skip is selected according to RSSI:

| RSSI | `desired_beacon_skip` |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

This value is passed into the WLAN power-management configuration.

`real_beacon_skip`, by contrast, is derived from:

```text
600 / (C - P)
```

It is therefore an estimate derived by the host from WF200 statistics.

It is not a direct readback of the programmed WF200 beacon-skip setting.

Consequently:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not by itself prove that the WF200 was physically waking for every
beacon.

Likewise:

```text
desired_beacon_skip = 15
real_beacon_skip    = 12
```

does not mean that the radio was simply configured for a skip of 12.

The two values come from different mechanisms.

---

## Runtime Behavior

### Stock 2.2.4

Stock 2.2.4 devices have repeatedly shown the characteristic recovery sequence:

```text
Beacon skip error!
Attempt recovery
PS state 1
...
PS state 3
```

On affected devices this can repeat roughly once per minute.

A stock 2.2.4 reference device has shown recurring recovery even with
relatively good RSSI and:

```text
desired_beacon_skip = 20
```

This demonstrates that poor RSSI is not required for the stock recurring loop.

---

### Runtime Behavior with mDNS Suppressed

Patch B suppresses the identified recurring connected-maintenance mDNS restart
while retaining the stock beacon statistics and Beacon Recovery path.

It retains:

```text
command 0x66
received-beacon statistics
baseline handling
real_beacon_skip
stock Beacon Recovery
```

Long-term testing showed that recurring Beacon Recovery continued on this
configuration.

The Patch-B device eventually reached a recovery rate of approximately:

```text
58 recoveries/hour
```

during its full-discharge run.

This demonstrates that the periodic mDNS restart is not required for the
observed recurring Beacon Recovery behavior.

It does not establish that network traffic in general is irrelevant to WF200
timing or power-save behavior.

---

### D3 Power-Save Errors

Firmware 2.2.4 contains handling for a WF200 `PS_MODE_ERROR` indication.

A dedicated D3 observer build was used to count these indications and record
their reason values.

On the D3 observer device, recurring Beacon Recovery continued for days while:

```text
D3_total = 0
```

At approximately 63.9 hours of uptime the same device had accumulated roughly:

```text
beacon_err = 3835
D3_total   = 0
```

This is important because it separates the known host Beacon Recovery trigger
from the observed WF200 D3 error indication.

The available runtime evidence therefore does not support:

```text
D3 PS_MODE_ERROR
        |
        v
Beacon Recovery
```

as a required trigger relationship.

A radio-internal condition that does not generate D3 could still affect the
beacon statistics, so this result does not establish that WF200 behavior is
irrelevant.

It establishes only that the observed recurring Beacon Recovery does not
require a host-visible D3 event.

---

### Runtime Behavior with Patch C-C

Patch C-C was designed to correct the three host-side validity problems while
preserving legitimate fresh Beacon Recovery.

It keeps:

```text
WF200 command 0x66
cumulative beacon statistics
real_beacon_skip diagnostic value
legitimate fresh recovery
```

while changing the control logic so that:

- `R` is interpreted correctly for the recovery decision
- stale measurement epochs invalidate `P`
- a baseline-only sample cannot reuse historical `R` as fresh evidence
- a newly established baseline can survive until another comparable sample is
  available

The intended progression is:

```text
invalid measurement epoch
      |
      v
P invalidated
      |
      v
next successful sample
      |
      v
establish P only
      |
      v
next valid comparable sample
      |
      v
calculate fresh R
      |
      +---- non-qualifying -> continue normally
      |
      +---- qualifying ----> Beacon Recovery
```

Static analysis and controlled hardware testing confirmed that C-C removes the
self-sustaining stale-`R` recovery mechanism without eliminating all Beacon
Recovery.

This distinction became important during later testing.

Devices running C-C can still produce fresh qualifying recovery events.

Observed rates on later C-C-based configurations have been much lower than the
approximately once-per-minute stale loop, but fresh recovery has not
disappeared.

This means there are two different phenomena:

```text
stock stale-state recovery loop
```

and:

```text
fresh qualifying recovery
```

Patch C-C addresses the first.

It deliberately does not suppress the second.

---

### C-C with WF200 3.18.0

Later test configurations combined the corrected C-C host logic with WF200
3.18.0.

WF200 3.18.0 includes a Silicon Labs change concerning a device not sleeping
after a power-save mode change.

The newer radio firmware initializes and operates successfully with the Shelly
2.2.4 FMAC 3.7.0 host environment used in the test builds.

Fresh Beacon Recovery still occurs with C-C and WF200 3.18.0.

On the A1+C-C+WF200 3.18.0 test device, for example, approximately:

```text
27 - 28 fresh recoveries/hour
```

were observed during the first day.

The device also showed states such as:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

despite good RSSI.

Because C-C prevents the known stale-`R` self-sustaining loop, these remaining
events cannot simply be classified as repetitions of C2.

They represent fresh measurements that satisfy the retained recovery
condition.

The exact radio/environmental condition producing those fresh measurements
remains under investigation.

---

## AP Selection and RSSI

The analyzed host connection path uses approximately:

```text
wildcard BSSID
channel = 0
prevent_roaming = 1
```

The host does not implement a normal background policy that continuously
switches to a stronger BSSID.

Association with a less favorable access point can plausibly affect:

- beacon reception
- WLAN timing
- retransmissions
- power-save behavior

However, the current evidence does not establish AP selection as the direct
cause of a qualifying `real_beacon_skip` measurement.

Recurring recovery has been observed under different RSSI conditions and
different requested skip regimes.

Testing with FRITZ! Mesh/Band Steering disabled also did not eliminate fresh
recovery on the A1+C-C+WF200 3.18.0 test device.

AP behavior therefore remains relevant environmental context rather than an
established explanation for the counter behavior.

See:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

---

## What `real_beacon_skip` Actually Tells Us

The name can easily suggest that the value directly reports what the WF200 is
doing.

The implementation does not support that interpretation.

What the host actually knows is:

```text
previous cumulative received count P
current cumulative received count C
```

and from those values it calculates:

```text
R = uint8_t(600 / (C - P))
```

Therefore `R` is best understood as:

> a host-derived value based on the number of received beacons observed by the
> WF200 across an assumed measurement interval.

It is not a direct measurement of:

- WF200 sleep residency
- actual radio wake frequency
- programmed beacon skip
- missed RF frames
- DTIM behavior
- physical current consumption

This distinction is important when interpreting `/stats`.

A value such as:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

is evidence that the host calculation produced `1`.

It does not by itself prove:

```text
WF200 woke for every beacon
```

Additional radio-side evidence would be required for that conclusion.

---

## What the Beacon Counters Do Not Prove

The available statistics do not by themselves tell us:

- how many beacon opportunities the AP generated
- how many beacon opportunities the WF200 deliberately skipped
- how many frames were lost because of RF conditions
- exact physical time represented by `C - P`
- exact DTIM interaction
- actual WF200 sleep residency
- host MCU sleep residency
- whether PA8 prevented host sleep
- whether a particular recovery event caused measurable battery drain

Likewise:

```text
real_beacon_skip <= 2
```

does not automatically mean:

```text
RF failure
```

because the value must first be interpreted in the context of the host-side
measurement lifecycle.

---

## Battery-Drain Relevance

The received-beacon counter itself consumes no meaningful battery simply by
existing as a statistic.

Its relevance comes from what the host does with the derived value:

```text
WF200 statistics
      |
      v
received-beacon counter
      |
      v
host calculation
      |
      v
real_beacon_skip
      |
      v
Beacon Recovery
      |
      v
temporary active WLAN configuration
      |
      v
additional power-management activity
```

Stock 2.2.4 can turn one qualifying measurement into a recurring recovery loop
through the C2 stale-state defect.

That clearly creates unnecessary WLAN power-management activity.

However, the project has not established that this mechanism alone explains
the historical TRV battery-drain problem.

There are several reasons for keeping those questions separate.

First, battery drain also occurred on firmware versions older than 2.2.4.

Second, C-C removes the known self-sustaining recovery loop but does not remove
all fresh recovery.

Third, later host-sleep analysis identified additional independent defects in
the EFM32GG11 power-management path.

In particular, the shared B2 sleep-blocker reference counter contains
unserialized read-modify-write operations. Under real task preemption these can
produce either:

```text
phantom B2 contribution
      |
      v
EM2 incorrectly blocked
      |
      v
host limited to EM1
```

or:

```text
lost B2 contribution
      |
      v
EM2 incorrectly allowed while an owner still requires EM1
```

This is independent of the Beacon RX calculation.

A separate PA8 WLAN host-notification input can also veto WFI completely while
asserted.

These findings are now being investigated with dedicated host-sleep
instrumentation.

The Beacon Recovery mechanism should therefore be treated as one confirmed
firmware problem inside a larger battery-drain investigation, not as the final
root-cause explanation.

See:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

---

## Patch Relationship

The project has used several patches for different experimental purposes.

### Patch A

Patch A bypasses the Beacon Recovery action.

It does not remove:

```text
command 0x66
beacon statistics
baseline sampling
600 / delta
real_beacon_skip
desired_beacon_skip
```

It was primarily useful as an isolation experiment.

### Patch B

Patch B suppresses the identified periodic mDNS maintenance restart while
leaving the Beacon Recovery path intact.

Long-term testing demonstrated that recurring stock Beacon Recovery continued
without that periodic mDNS path.

### Patch C-C

Patch C-C corrects the identified host-side Beacon Recovery validity defects
while retaining fresh recovery.

It addresses:

```text
C1a
signed control interpretation

C1b
invalid measurement epochs

C2
historical R reused as fresh evidence
```

It does not attempt to redefine the internal WF200 beacon counters.

It also does not suppress a genuinely fresh measurement merely because the
result is unusual.

### A1

A1 addresses a separate set of host/WF200 power-management ownership,
settlement and failure-path problems.

A1 is not a Beacon RX counter patch.

The combined experimental firmware:

```text
A1 + C-C + WF200 3.18.0
```

is useful because it combines independently identified host corrections with
the newer radio firmware while retaining fresh Beacon Recovery for diagnostic
purposes.

It should not be interpreted as evidence that all possible battery-drain
mechanisms have been corrected.

---

## Remaining WF200 Questions

The host-side path is now sufficiently understood to identify and correct its
known validity defects.

The remaining WF200 questions are narrower.

### Received-Beacon Semantics

What exact internal WF200 event increments:

```text
received beacon count
```

under Fast Power Save?

### Intentional Beacon Skipping

How are beacon opportunities that the radio intentionally sleeps through
represented in:

```text
received beacon count
missed beacon count
TBTT difference
```

?

### DTIM Interaction

How do DTIM interval and DTIM reception affect those statistics?

### Power-Save Transitions

How are the counters affected by:

- power-save mode changes
- Fast Power Save transitions
- temporary Active mode
- reassociation
- internal radio fallback/recovery

?

### Fresh Recovery Trigger

With the known stale-state host loop removed by C-C, what produces the
remaining fresh qualifying measurements observed on physical devices?

This is currently the most relevant open question for the beacon-counter path.

---

## Current Model

The current understanding is:

```text
Access point / RF environment
      |
      v
WF200 WLAN subsystem
      |
      | internal beacon handling
      | exact details partly unknown
      v
command 0x66 statistics
      |
      +---- received count C
      |
      +---- missed count
      |
      +---- TBTT difference
      |
      v
Shelly host application
      |
      +---- previous baseline P
      |
      v
measurement-window validity
      |
      v
C - P
      |
      v
600 / delta
      |
      v
8-bit cached R
      |
      v
control interpretation
      |
      v
Beacon Recovery
```

The known host-side defects are:

```text
C1a
R is stored as an 8-bit value but interpreted as signed by stock recovery
logic.

C1b
P can survive measurement epochs that no longer match the fixed-600
calculation.

C2
Recovery clears P but retains R, allowing historical R to be reused on a
baseline-only sample.
```

Patch C-C corrects these control-validity problems while preserving the
underlying statistics and legitimate fresh recovery.

The remaining fresh recovery events therefore provide useful evidence rather
than being hidden by a blanket recovery bypass.

---

## Current Conclusion

The host-side Beacon RX measurement path in Shelly TRV Gen1 firmware 2.2.4 is
now well understood.

The firmware:

1. requests WF200 statistics through command `0x66`
2. receives a cumulative received-beacon counter `C`
3. retains a previous host-side baseline `P`
4. calculates `C - P`
5. divides the fixed value `600` by that delta
6. stores the result as the 8-bit cached value `R`
7. uses `R` as input to the Beacon Recovery decision

The investigation identified three independent host-side problems in this
path:

- signed interpretation can change the recovery decision
- the baseline can represent an invalid measurement window
- historical recovery evidence can be reused without a fresh measurement

The third problem explains how stock 2.2.4 can enter a self-sustaining Beacon
Recovery loop after a qualifying value has been produced.

Patch C-C corrects these validity problems without disabling fresh recovery.

Runtime testing confirms that fresh recovery still occurs after the stale-state
loop has been removed. This means the first qualifying measurement and the
later self-sustaining stock loop must be treated as separate problems.

The exact internal WF200 beacon-counter semantics remain useful for explaining
the first fresh trigger, but they are not required to establish the host-side
C1a, C1b and C2 defects.

Finally, neither the Beacon RX counter nor Beacon Recovery should currently be
treated as the complete explanation for the historical battery drain.

The wider investigation has identified additional host power-management
problems, including B2 blocker-accounting races and the PA8 WLAN sleep veto.
A stock 2.2.4 host-sleep observer is being developed to determine whether those
conditions occur during real battery-drain episodes.

---

## Related Documents

Detailed `real_beacon_skip` arithmetic:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

Firmware-version comparison:

[`firmware-comparison.md`](firmware-comparison.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Periodic mDNS behavior:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Host power management and sleep:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

---

## Research Method

This analysis is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware and runtime testing on personally owned devices.

Important control-flow conclusions were checked against native ARM Thumb
instructions rather than relying only on decompiler output.

The host statistics path was traced from:

```text
WF200 command 0x66
```

through:

```text
statistics storage
baseline handling
real_beacon_skip calculation
Beacon Recovery
```

The protected WF200 implementation has not been fully reverse engineered.
Where that boundary matters, it is stated explicitly rather than inferred from
the host-side code.

No original firmware image, modified firmware image, complete proprietary
function, or large raw disassembly is published in this document.

---

## Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The documented behavior refers to the firmware versions and devices tested in
this project.