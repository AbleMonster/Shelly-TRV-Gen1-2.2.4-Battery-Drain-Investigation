# Beacon RX Counter Analysis

## Scope

This document describes the beacon statistics used by Shelly TRV Gen1 firmware 2.2.4 and how the host firmware derives `real_beacon_skip` from the cumulative WF200 received-beacon counter.

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

The important distinction is:

> `real_beacon_skip` is not a direct WF200 power-save state and is not a direct readback of the currently programmed beacon-skip parameter.

It is a host-derived value calculated from the change of a cumulative WF200 statistic.

This document focuses on:

- the origin of the beacon statistics
- WF200 statistics command `0x66`
- the host-side baseline `P`
- the calculation of `real_beacon_skip`
- measurement-window validity
- C1a/C1b/C2
- cached diagnostic state versus fresh control evidence
- runtime observations
- the boundary between known host behavior and protected WF200 internals
- the current PM52→cmd66 observer
- the relevance of this mechanism to the battery-drain investigation

Detailed arithmetic is also documented in:

[`real-beacon-skip.md`](real-beacon-skip.md)

The complete Recovery control flow is documented in:

[`recovery-mechanism.md`](recovery-mechanism.md)

---

# 1. Summary

Firmware 2.2.4 does not count WLAN beacons directly inside the Shelly application.

Instead, the host periodically requests statistics from the WF200 subsystem using:

```text
command 0x66
```

The returned structure contains, among other fields:

```text
received beacon count
missed beacon count
TBTT difference
```

The known `real_beacon_skip` calculation uses the cumulative received-beacon count.

For clarity:

```text
C = current cumulative received-beacon count
P = previous host-side received-beacon baseline
R = cached real_beacon_skip byte
```

When a usable previous baseline exists and the counter has increased, the host approximately performs:

```text
delta = C - P

R = uint8_t(600 / delta)

P = C
```

The missed-beacon counter and TBTT-difference field are not used to normalize this calculation.

Three independent host-side validity defects were identified:

```text
C1a
signed interpretation of the 8-bit R value

C1b
measurement-window / baseline validity

C2
historical R reused as fresh Recovery evidence
```

These defects do not require the WF200 cumulative statistic itself to be incorrect.

---

# 2. WF200 Statistics Source

The beacon statistics consumed by the Shelly application originate in the WF200 WLAN subsystem.

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

Relevant returned fields include:

```text
received beacon count
missed beacon count
TBTT difference
```

The Shelly application therefore consumes statistics maintained below the host application.

The protected WF200 code responsible for maintaining the counters has not been fully reconstructed.

---

# 3. Received-Beacon Counter

The received-beacon field behaves as a cumulative WF200 statistic.

For example:

```text
P = 12000
C = 12030
```

The host does not use:

```text
12030
```

directly as the Recovery measurement.

Instead:

```text
delta = C - P
      = 30
```

The derived value therefore depends on the difference between two cumulative samples.

Important distinctions are:

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

The exact internal WF200 event that increments the cumulative counter remains unresolved.

That uncertainty does not prevent host-side arithmetic and lifecycle analysis.

---

# 4. Missed-Beacon Counter

Command `0x66` also returns a missed-beacon statistic.

The host stores this value, but the known `real_beacon_skip` calculation does not perform a ratio such as:

```text
received
------------------
received + missed
```

Instead, the identified arithmetic is:

```text
600 / (C - P)
```

The exact treatment of intentionally skipped beacon opportunities by the WF200 missed-beacon statistic remains unresolved.

This is especially relevant under Fast Power Save, because an intentionally skipped beacon opportunity is not automatically equivalent to an RF reception failure.

---

# 5. TBTT Difference

The statistics response also contains a TBTT-related value.

TBTT means:

```text
Target Beacon Transmission Time
```

The field contains timing-related information.

However, the known host calculation does not use it as the timebase for `real_beacon_skip`.

The host does not perform:

```text
received-beacon delta
        /
measured TBTT interval
```

for this estimator.

This matters because the numerator:

```text
600
```

is fixed.

---

# 6. Host-Side Calculation

With:

```text
P != 0
```

and:

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

The complete path is:

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

The original engineering rationale behind interpreting this quotient as an effective beacon-skip measure is not explicitly documented by the firmware.

---

# 7. The Fixed Numerator `600`

The numerator:

```text
600
```

is hard-coded.

The surrounding design is consistent with an attempt to estimate effective beacon reception across an expected observation interval.

Conceptually:

```text
nominal beacon opportunities
          /
received beacons
          =
effective beacon-density estimate
```

The important implementation detail is that the host does not store a corresponding elapsed-time value together with `P`.

The formula therefore assumes that:

```text
C - P
```

represents the interval for which:

```text
600
```

is appropriate.

If the baseline survives longer than intended, the cumulative counter may remain perfectly correct while the quotient becomes invalid for the intended measurement model.

That is a host-side validity problem.

---

# 8. Normal Baseline Lifecycle

Under normal conditions:

```text
P != 0
```

A later statistics sample returns:

```text
C > P
```

and the host performs:

```text
delta = C - P
R = 600 / delta
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

This produces comparable measurements as long as the baseline remains valid.

---

# 9. Baseline Establishment

When:

```text
P == 0
```

there is no previous cumulative sample.

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

This gives an important invariant:

> A baseline-only sample cannot produce fresh `real_beacon_skip` evidence.

A later comparable sample is required.

---

# 10. Counter Reset or Decrease

The firmware handles:

```text
C <= P
```

without performing an invalid unsigned subtraction.

The relevant state is reset approximately as:

```text
R = 0
P = C
```

This covers cumulative counter reset, decrease or another condition that makes the old baseline incomparable.

---

# 11. Statistics Acquisition Failure

If command `0x66` fails, stock firmware clears approximately:

```text
P = 0
R = 0
```

The next successful request must therefore establish a new baseline before another fresh ratio can be calculated.

This differs from the stock Beacon Recovery path, where `P` is cleared but `R` is retained.

That asymmetry is central to C2.

---

# 12. C1a — Signed Interpretation of `R`

The quotient:

```text
600 / delta
```

is stored in an 8-bit field.

The stock Recovery predicate later interprets that byte as signed.

For example:

```text
delta = 3

600 / 3 = 200

uint8:
0xC8

int8:
-56
```

and:

```text
delta = 4

600 / 4 = 150

uint8:
0x96

int8:
-106
```

The stock predicate rejects zero and accepts values less than or equal to `2`.

The negative signed representations therefore unexpectedly satisfy the predicate.

The fresh stock trigger set includes:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

The `delta = 3` and `delta = 4` cases arise from host-side signed interpretation.

They are not evidence that the WF200 produced negative counters.

C-C changes the control interpretation while preserving the diagnostic byte.

---

# 13. C1b — Measurement-Window Validity

The formula:

```text
600 / (C - P)
```

has the intended meaning only if `P` and `C` delimit the measurement interval assumed by the fixed numerator.

Stock firmware does not attach elapsed-time validity to `P`.

More importantly, paths exist where an expected measurement opportunity can be skipped while the baseline survives.

Conceptually:

```text
P established
     |
     v
expected measurement skipped
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

The later delta can therefore span a longer logical interval than the fixed numerator assumes.

Two correct cumulative counter values can therefore produce an invalid host-derived result:

```text
correct old P
    +
correct later C
    +
invalid assumption about measurement interval
    =
invalid derived value
```

This is C1b.

---

# 14. C2 — Historical `R` Reused as Fresh Evidence

The third defect occurs after Beacon Recovery.

Stock Recovery clears:

```text
P
```

but retains:

```text
R
```

The post-Recovery state can therefore become:

```text
P = 0
R = historical qualifying value
```

At the next successful `0x66` request, firmware can only establish:

```text
P = C
```

No fresh `R` can be calculated.

However, the stock control flow subsequently evaluates the retained historical `R`.

If it still satisfies the Recovery predicate, another Recovery can occur and `P` is cleared again.

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
Recovery can recur
     |
     v
P = 0
```

The defect is not merely retaining `R`.

Retaining a diagnostic value can be legitimate.

The defect is:

```text
historical diagnostic value
```

being reused as:

```text
fresh control evidence
```

on a pass where no fresh estimator result exists.

---

# 15. C2 Is Metastable

Earlier project documentation often described C2 as:

```text
self-sustaining
```

or effectively:

```text
Recovery forever until reboot
```

That wording is too strong.

The demonstrated behavior is better described as:

```text
metastable stale-evidence recurrence
```

It can produce long-lived, approximately minute-spaced Recovery behavior.

However, it is not proven to be mathematically permanent.

Firmware can leave the recurrence without reboot.

Therefore the correct statement is:

> C2 can repeatedly reuse stale qualifying evidence for extended periods, but the state is not guaranteed to persist forever.

---

# 16. Why the WF200 Counter Does Not Need to Be Faulty

Assume:

```text
WF200 cumulative received-beacon counter
=
completely correct
```

C1a can still occur because the host interprets the derived byte incorrectly.

C1b can still occur because correct cumulative samples can span an invalid measurement epoch.

C2 can still occur because the host reuses a historical derived value after clearing its measurement baseline.

Therefore:

```text
WF200 counter correct
```

does not imply:

```text
host Recovery logic correct
```

These are separate layers.

---

# 17. `desired_beacon_skip` vs. `real_beacon_skip`

The firmware contains two values that are easily confused.

Requested WLAN policy:

```text
desired_beacon_skip
```

Counter-derived estimate:

```text
real_beacon_skip
```

They are not the same quantity.

The normal desired skip is selected from RSSI approximately as:

| RSSI | `desired_beacon_skip` |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

`real_beacon_skip`, by contrast, is derived from:

```text
600 / (C - P)
```

Therefore:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not prove the WF200 was physically waking for every beacon.

Likewise:

```text
desired_beacon_skip = 15
real_beacon_skip    = 12
```

does not mean the radio was simply configured for skip 12.

---

# 18. Stock 2.2.4 Runtime Behavior

Affected stock 2.2.4 devices have shown the characteristic sequence:

```text
Beacon skip error!
Attempt recovery
PS state 1
...
PS state 3
```

with periods close to once per minute.

This has occurred even with relatively good RSSI and:

```text
desired_beacon_skip = 20
```

Poor RSSI is therefore not required for stock recurring Recovery.

---

# 19. Historical Patch B Result

Patch B suppresses the targeted periodic mDNS maintenance behavior while retaining:

```text
command 0x66
beacon statistics
baseline handling
real_beacon_skip
stock Beacon Recovery
```

Long-term testing showed that recurring Recovery continued.

The historical `.77` experiment reached approximately:

```text
~58 Recoveries/hour
```

during the full-discharge run.

Therefore the targeted periodic mDNS mechanism is not required for the observed stock Recovery recurrence.

This does not establish that all network activity is irrelevant.

---

# 20. Historical D3 Observer

Firmware 2.2.4 contains handling for a WF200:

```text
PS_MODE_ERROR
```

indication.

A dedicated D3 observer build counted those events while retaining stock Recovery.

A long historical observation reached approximately:

```text
uptime      ~63.9 h
beacon_err  3835
D3_total    0
```

Thus:

```text
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

were observed.

This separates the Shelly host Recovery heuristic from the known D3 error channel.

It does not prove that no other radio-side PM issue existed.

---

# 21. C-C

C-C corrects:

```text
C1a
C1b
C2
```

while retaining the underlying statistics path.

It preserves:

```text
command 0x66
cumulative beacon statistics
real_beacon_skip diagnostic value
fresh valid Recovery
```

while changing the control logic so that:

- `R` is interpreted correctly
- stale measurement epochs invalidate the baseline
- baseline-only samples cannot reuse historical `R`
- a newly established baseline can survive until another comparable sample
- only fresh valid evidence can produce a new Recovery decision

---

# 22. C-C Progression

The intended corrected progression is:

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
     +---- qualifying ----> Recovery
```

C-C therefore corrects the stale-evidence recurrence without globally disabling Recovery.

---

# 23. C-C Runtime Result

Controlled hardware testing confirmed that C-C removes the demonstrated invalid stale-evidence recurrence.

Fresh qualifying Recovery still occurs.

Historical C-C-based configurations produced approximately:

```text
27–30 fresh Recoveries/hour
```

during some periods.

These are specific measurements.

They are not a universal C-C rate or guaranteed maximum.

The important distinction is:

```text
stock stale-evidence recurrence
```

versus:

```text
fresh qualifying Recovery
```

C-C addresses the first.

It deliberately retains the second.

---

# 24. Historical C-C + WF200 3.18.0

Later historical configurations combined:

```text
C-C
+
WF200 3.18.0
```

The newer official WF200 firmware successfully initialized and operated with Shelly FMAC 3.7.0.

Fresh Recovery remained observable.

A historical integrated A1+C-C+WF200 3.18.0 device showed approximately:

```text
27–28 fresh Recoveries/hour
```

during some intervals.

Because C-C was active, those events cannot simply be classified as C2 stale-evidence repetitions.

They resulted from later fresh estimator measurements satisfying the retained Recovery predicate.

---

# 25. Historical A1 Build Identity

The historical integrated build:

```text
A1
+
C-C
+
WF200 3.18.0
```

was an important hardware experiment.

Its measurements remain valid.

However, it is no longer the current corrected baseline.

Historical results from that build must not be relabeled as:

```text
A1R
B2.1
B2.1_OBS
```

The A1 regression discovered later was an experimental patch defect, not a stock Shelly defect.

---

# 26. AP Selection and RSSI

The analyzed connection path uses approximately:

```text
wildcard BSSID
channel = 0
prevent_roaming = 1
```

The host does not implement an identified background strongest-BSSID roaming policy.

Association with a less favorable AP can plausibly affect:

- beacon reception
- WLAN timing
- retransmissions
- power-save behavior

However, current evidence does not establish AP selection as the direct cause of fresh low `real_beacon_skip`.

Fresh Recovery has been observed at good RSSI.

Historical testing with FRITZ! Mesh/Band Steering disabled also did not eliminate fresh Recovery on the historical integrated `.234` experiment.

AP behavior therefore remains environmental context, not a proven counter root cause.

---

# 27. What `real_beacon_skip` Actually Tells Us

The name can suggest that `real_beacon_skip` directly reports radio behavior.

It does not.

The host knows:

```text
previous cumulative count P
current cumulative count C
```

and derives:

```text
R = uint8_t(600 / (C - P))
```

The best supported interpretation is:

> A host-derived value based on received-beacon statistics across an assumed valid measurement interval.

It is not direct telemetry for:

- WF200 sleep residency
- physical radio wake frequency
- programmed beacon skip
- missed RF frames
- DTIM behavior
- current consumption

---

# 28. What the Beacon Counters Do Not Prove

The available statistics do not directly reveal:

- total beacon opportunities generated by the AP
- beacon opportunities intentionally skipped by the radio
- exact RF-loss count
- exact physical time represented by `C - P`
- DTIM interaction
- WF200 sleep residency
- host MCU sleep residency
- PA8 sleep-veto duty
- energy consumed by one Recovery

Therefore:

```text
real_beacon_skip <= 2
```

does not automatically mean:

```text
RF failure
```

The estimator must be interpreted together with its measurement lifecycle.

---

# 29. Battery-Drain Relevance

The received-beacon counter itself is only a statistic.

Its relevance arises from the host reaction:

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
Recovery decision
     |
     v
temporary more-active WLAN PM state
     |
     v
additional PM activity
```

Stock C2 can turn one qualifying measurement into repeated stale-evidence Recovery.

This creates unnecessary PM work.

However, the project has not established that this mechanism alone explains historical TRV battery drain.

---

# 30. Recovery Occupancy Is Not Energy

Historical stock behavior around:

```text
~60 Recoveries/hour
```

with approximately:

```text
~5 serviced seconds/Recovery
```

corresponds to roughly:

```text
~300 s/hour
~5 min/hour
~8.33% wall-clock occupancy
```

Historical C-C intervals around:

```text
27–30/hour
```

correspond to approximately:

```text
~135–150 s/hour
~2.25–2.5 min/hour
```

These are wall-clock figures.

They are not battery-consumption percentages.

No direct synchronized current measurement exists for these events.

---

# 31. Host PM Defects Are Separate

Later reverse engineering demonstrated additional host-side defects independent of the Beacon RX arithmetic.

These include PM lifecycle issues addressed by A1/A1R and the B2 reference-counter race.

The Beacon RX path therefore represents only one part of the battery-drain investigation.

---

# 32. A1R

A1R supersedes historical A1.

A1R retains the lifecycle corrections while fixing the experimental regression affecting verified temporary `request1` override paths.

Qualification:

```text
151 / 151
```

native behavior tests passed.

A1R is part of:

```text
B2.1
B2.1_OBS
B2.2
```

---

# 33. B2 Serialization

The B2 host sleep-blocker reference counter contains a demonstrated preemption/lost-update race.

Possible consequences include:

```text
phantom B2 contribution
        |
        v
EM2 incorrectly blocked
        |
        v
host restricted to EM1
```

or:

```text
lost B2 contribution
        |
        v
EM2 allowed while owner remains active
```

The correction uses bounded serialization of the relevant complete B2 read-modify-write operations.

It preserves reference-count semantics.

---

# 34. Current Observer-Free Baseline

The current corrected observer-free baseline is:

```text
B2.1
```

containing:

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

This supersedes the historical:

```text
A1 + C-C + WF200 3.18.0
```

platform as the current corrected baseline.

---

# 35. Current PM52→cmd66 Observer

The earlier proposed clean-stock Host Observer is no longer the active diagnostic design.

The current observer is:

```text
PM52 -> cmd66 observer
```

integrated into:

```text
B2.1_OBS
```

It records:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing cmd66 requests
- existing cmd66 results
- fresh estimator operands
- connection epochs
- recent-event history
- first-fault state

This directly connects the host PM request path with the same command-0x66 statistics path documented here.

---

# 36. No Additional Command `0x66`

A critical observer requirement is:

> The observer must not generate an additional WF200 statistics request.

The native firmware already issues command `0x66`.

The observer records those existing transactions.

Therefore:

```text
observer-added cmd66 requests = 0
```

This avoids creating new radio activity simply to observe the counter path.

---

# 37. Observer Noninterference Design

The current observer adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
additional WF200 request
```

Observer data are retrieved only through explicit status access.

Software-level noninterference has been qualified.

Absolute physical timing noninterference is not claimed.

---

# 38. Fresh Estimator Operands

The observer records the operands relevant to fresh `real_beacon_skip` calculation.

This allows a later fault to distinguish:

```text
historical cached R
```

from:

```text
freshly calculated R
```

which is particularly important for C2 analysis.

A future drain event can therefore be correlated with the actual estimator state rather than only the public cached value.

---

# 39. Connection Epochs

Counter/baseline state can become misleading if values from different WLAN connection lifetimes are combined.

The observer therefore tracks:

```text
connection epoch
```

This helps distinguish:

```text
same connection
```

from:

```text
reconnect / new association context
```

when interpreting `P`, `C`, PM52 and cmd66 history.

---

# 40. B2.1_OBS

The active long-term diagnostic build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

Research identity:

```text
research_build: B2.1_OBS
```

Readout identifier:

```text
pm52_cmd66
```

The native Shelly version remains 2.2.4.

---

# 41. B2.1_OBS Qualification

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
decoder regression
deterministic construction
GBL/CRC/geometry verification
zero unexplained changes
```

Disposition:

```text
B2.1_OBS RELEASE-CANDIDATE GO
```

This means qualified for the current controlled long-term hardware experiment.

It does not mean production firmware.

---

# 42. Current Hardware Population

The active hardware population is:

```text
.77  -> B2.1_OBS
.88  -> B2.1_OBS
.11  -> B2.1_OBS
.71  -> B2.1_OBS
.234 -> B2.1_OBS
.61  -> B2.1_OBS

.97  -> stock 2.2.4 control
```

or:

```text
6 × B2.1_OBS
1 × stock 2.2.4
```

The old `.234` A1 integrated canary is therefore historical, not the current test platform.

---

# 43. Early Current Observation

During the initial B2.1_OBS observation period:

```text
beacon_err = 0
```

on the corrected devices during the first observed interval.

The stock `.97` control had accumulated thousands of Beacon Recovery events and showed periods of approximately minute-scale recurrence.

Other stock intervals were quieter.

This is preliminary runtime evidence only.

It is not a battery-lifetime result.

---

# 44. Current Experimental Decision

The current decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

Therefore the project is not currently:

- changing command-0x66 cadence
- changing the estimator formula
- changing C-C
- disabling fresh Recovery
- adding Recovery rate limiting
- changing WF200 firmware
- flashing B2.2 onto the active population

The value of the current experiment depends on continuity.

---

# 45. If a B2.1_OBS Device Drains

If genuine rapid drain develops:

```text
abnormal voltage/runtime behavior
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
inspect C / P / fresh R context
        |
        v
inspect connection epoch
        |
        v
resume targeted RE
```

This is the current reason for retaining the observer.

---

# 46. If B2.1_OBS Remains Stable

If long-term corrected devices remain stable:

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

The observer is instrumentation, not automatically a final production component.

---

# 47. B2.2

B2.2 is a later observer-free candidate containing exactly nine selected qualified corrections:

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

Its status is:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

B2.2 does not contain the PM52→cmd66 observer.

No physical B2.2 hardware qualification has yet been performed.

---

# 48. Why B2.2 Does Not Change This Counter Model

B2.2 retains C-C and the existing command-0x66 statistics architecture.

It does not redefine the underlying WF200 beacon-counter semantics.

Therefore the host model documented here remains relevant to:

```text
B2.1
B2.1_OBS
B2.2
```

with the important distinction that C-C prevents stale/invalid evidence from controlling Recovery.

---

# 49. Historical Patch Relationship

Several historical patches had different purposes.

## Patch A

Patch A bypassed the Beacon Recovery action.

It retained:

```text
command 0x66
beacon statistics
baseline sampling
600 / delta
real_beacon_skip
desired_beacon_skip
```

It was primarily a mechanism-isolation experiment.

Patch A is historical.

---

## Patch B

Patch B suppressed the targeted periodic mDNS behavior while retaining stock Beacon Recovery.

It established that the targeted mDNS mechanism was not required for recurring stock Recovery.

Patch B is historical.

---

## C-C

C-C corrects:

```text
C1a
C1b
C2
```

without suppressing valid fresh Recovery.

C-C remains part of the current corrected platform.

---

## A1 / A1R

Historical A1 addressed separate host PM lifecycle and ownership problems.

A1R supersedes A1 and corrects the later-discovered experimental temporary-override regression.

A1/A1R are not Beacon-counter patches.

---

# 50. Remaining WF200 Questions

The host-side path is sufficiently understood to establish C1a/C1b/C2.

Remaining radio-side questions are narrower.

## Received-Beacon Semantics

What exact internal event increments:

```text
received beacon count
```

under Fast Power Save?

## Intentional Beacon Skipping

How are intentionally skipped beacon opportunities represented in:

```text
received count
missed count
TBTT difference
```

?

## DTIM Interaction

How does DTIM behavior affect these statistics?

## PM Transitions

How are the counters affected by:

- PM mode changes
- Fast Power Save transitions
- temporary Active mode
- reassociation
- internal radio fallback/recovery

?

## Fresh Trigger Meaning

What real RF/WF200 condition, if any, produces a fresh:

```text
real_beacon_skip = 1
```

or:

```text
real_beacon_skip = 2
```

on otherwise healthy connected devices?

---

# 51. Current Model

The current model is:

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
fresh Recovery predicate
```

Stock defects are:

```text
C1a
R is stored as 8-bit but interpreted as signed.

C1b
P can survive a measurement epoch incompatible
with the fixed-600 model.

C2
Recovery clears P but retains R, allowing historical
R to be reused on a baseline-only sample.
```

C-C corrects these validity defects while preserving the underlying statistics path and legitimate fresh Recovery.

---

# 52. Stock vs. Corrected Evidence Lifecycle

Stock:

```text
fresh R qualifies
     |
     v
Recovery
     |
     v
P cleared
R retained
     |
     v
baseline-only sample
     |
     v
old R may be evaluated again
```

Corrected C-C:

```text
fresh R qualifies
     |
     v
Recovery
     |
     v
measurement epoch invalidated
     |
     v
next successful sample
establishes baseline only
     |
     v
later comparable sample
     |
     v
fresh R
     |
     v
new Recovery decision
```

This is the core behavioral difference.

---

# 53. Current Battery-Relevance Interpretation

The current evidence supports:

```text
C1a/C1b/C2
=
real host defects
```

and:

```text
C-C
=
corrected host evidence handling
```

It does not establish:

```text
Beacon RX defect
=
complete historical battery root cause
```

Battery drain was observed on firmware predating 2.2.4.

Additional independent host and radio-relevant defects have also been identified.

The counter path is therefore one important mechanism inside a broader low-power system.

---

# 54. What Has Been Established

The project has established that:

- command `0x66` supplies cumulative beacon statistics
- `real_beacon_skip` is host-derived
- `received_beacon_count` is used for the estimator
- missed count is not part of the known formula
- TBTT difference is not the formula timebase
- `P == 0` means baseline establishment only
- C1a is a host signedness defect
- C1b is a host measurement-epoch validity defect
- C2 reuses historical derived evidence
- C2 can produce long-lived stale-evidence recurrence
- C2 is metastable rather than proven permanent
- C-C corrects C1a/C1b/C2
- fresh Recovery remains possible after C-C
- D3 `PS_MODE_ERROR` is not required for recurring host Recovery
- WF200 3.18.0 does not eliminate all fresh host Recovery
- `real_beacon_skip` is not physical sleep telemetry
- the current observer records existing cmd66 activity without adding another WF200 request

---

# 55. What Has Not Been Established

The project has not established:

- exact protected WF200 beacon-counter semantics
- exact treatment of all intentionally skipped beacon opportunities
- exact DTIM influence on command-0x66 counters
- physical WF200 wake frequency from `real_beacon_skip`
- physical radio sleep residency from `real_beacon_skip`
- exact energy cost of one Recovery
- exact energy cost of command `0x66`
- AP selection as the fresh-trigger root cause
- fresh Recovery as necessarily harmful
- fresh Recovery as necessarily beneficial
- Beacon Recovery as the complete historical drain cause
- B2.2 battery behavior
- a final production firmware fix

---

# 56. Current Conclusion

The host-side Beacon RX measurement path in Shelly TRV Gen1 firmware 2.2.4 is now well understood.

The firmware:

1. requests WF200 statistics through command `0x66`
2. receives a cumulative received-beacon counter `C`
3. retains a previous host baseline `P`
4. calculates `C - P`
5. divides `600` by that delta
6. stores the result as the 8-bit cached value `R`
7. uses that value in Beacon Recovery control

Three independent host defects were identified:

```text
C1a
signed interpretation of R

C1b
invalid measurement epoch

C2
historical R reused as fresh evidence
```

C2 explains how stock 2.2.4 can enter long-lived stale-evidence Recovery recurrence after a qualifying measurement.

The state is metastable.

It should not be described as guaranteed to continue forever until reboot.

C-C corrects these validity problems without globally disabling fresh Recovery.

Historical C-C-based experiments still showed fresh Recovery, including the old A1+C-C+WF200 3.18.0 platform.

That platform is now historical.

The current corrected baseline is:

```text
B2.1
```

and the active long-term diagnostic build is:

```text
B2.1_OBS
```

with:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The current PM52→cmd66 observer records the existing command-0x66 activity and fresh estimator context without issuing an additional WF200 statistics request.

The previous proposed Stock Host Observer is no longer the current diagnostic path.

The current project decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

If a corrected device drains, the observer is intended to preserve the first useful PM52/cmd66 context.

If the corrected population remains stable, the next stage is observer removal, requalification and observer-free hardware regression.

The exact internal WF200 meaning of all beacon statistics remains an open question.

It is not required, however, to establish the demonstrated host-side C1a/C1b/C2 defects.

No claim is currently made that the Beacon RX mechanism alone explains the historical Shelly TRV Gen1 battery drain.

---

# Related Documents

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

Host power management:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

Battery reporting:

[`battery-reporting-and-shutdown.md`](battery-reporting-and-shutdown.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

B2.1_OBS qualification:

[`../qualification/b2.1-obs-qualification.md`](../qualification/b2.1-obs-qualification.md)

B2.2 qualification:

[`../qualification/b2.2-offline-release-candidate.md`](../qualification/b2.2-offline-release-candidate.md)

---

# Research Method

This analysis combines:

- static ARM Thumb reverse engineering
- native-instruction control-flow verification
- runtime command-0x66 telemetry
- long-term device observation
- C-C correction testing
- WF200 3.18.0 integration
- PM52→cmd66 observer qualification

The host statistics path was traced through:

```text
WF200 command 0x66
        |
        v
statistics storage
        |
        v
baseline handling
        |
        v
real_beacon_skip calculation
        |
        v
Beacon Recovery
```

The protected WF200 implementation has not been fully reverse engineered.

Where the host/radio boundary matters, unresolved radio-internal behavior is explicitly identified rather than inferred.

Historical build identities are preserved.

No historical A1 data are relabeled A1R or B2.1.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The documented behavior refers to the firmware versions and experimental devices tested in this project.

No proprietary firmware image or large raw disassembly is reproduced here.