# Beacon RX Counter Analysis

## Scope

This document describes the WLAN beacon statistics used by Shelly TRV Gen1
firmware 2.2.4, with particular focus on the cumulative received-beacon
counter used by the host-side Beacon Recovery logic.

The analysis covers:

- the origin of the beacon statistics
- WF200 statistics command `0x66`
- the host-side current and previous beacon-counter values
- calculation of `real_beacon_skip`
- measurement-window validity
- counter and baseline lifecycle
- the relationship between the counter and Beacon Recovery
- the boundary between proven host-side behavior and unresolved WF200-internal
  counter semantics

This document focuses on the **measurement source and baseline lifecycle**.

The arithmetic interpretation of `real_beacon_skip` is documented separately
in:

[`real-beacon-skip.md`](real-beacon-skip.md)

The resulting recovery control flow is documented in:

[`recovery-mechanism.md`](recovery-mechanism.md)

This document does not contain firmware images, complete disassemblies,
complete decompiled functions, or proprietary source code.

---

# Summary

Firmware 2.2.4 does not maintain its received-beacon count by incrementing a
Shelly application variable for every beacon.

Instead, the application requests statistics from the WF200 WLAN subsystem
using command:

```text
0x66
```

The returned statistics include fields corresponding to:

```text
received beacon count
missed beacon count
TBTT timing difference
```

The host stores the current received-beacon count as:

```text
C
```

and maintains a previous received-beacon baseline:

```text
P
```

When a valid previous baseline exists and the current counter is greater than
the previous counter, the host approximately calculates:

```text
delta = C - P

real_beacon_skip = uint8_t(600 / delta)
```

The resulting byte is cached as:

```text
R
```

The three values relevant to the host-side control flow are therefore:

```text
C = current received-beacon counter
P = previous received-beacon baseline
R = cached real_beacon_skip
```

Several important conclusions are now established independently of the exact
protected-WF200 counter implementation:

1. the calculation uses a fixed numerator of `600`
2. no corresponding elapsed-time value is attached to `P`
3. identified firmware paths can preserve `P` while expected measurement
   opportunities are skipped
4. recovery clears `P` while retaining `R`
5. a baseline-only sample in stock firmware can therefore evaluate historical
   `R` without calculating a fresh ratio
6. the stored quotient is later interpreted as signed by stock recovery logic

These are host-side measurement/control-validity properties.

They do **not** depend on proving that the WF200 statistics themselves are
incorrect.

The exact internal WF200 semantics of the received- and missed-beacon
statistics remain relevant for understanding the original engineering model,
but they are no longer required to establish the identified host-side C1a,
C1b, and C2 defects.

---

# Terminology

For clarity, this document uses:

```text
C = current received-beacon count returned by command 0x66

P = previous received-beacon count retained by the host

R = cached real_beacon_skip byte
```

Conceptually:

```text
WF200
  |
  | command 0x66 statistics
  v
C
  |
  | compare with P
  v
delta = C - P
  |
  v
600 / delta
  |
  v
R
```

`P` is a **host-side baseline**.

Clearing `P` does not imply that the cumulative WF200 counter itself was
cleared.

That distinction is important throughout the analysis.

---

# Origin of the Received-Beacon Counter

Reverse engineering traced the statistics request from the Shelly application
to the WF200 host interface.

The application requests statistics using:

```text
command 0x66
```

The returned structure contains the cumulative received-beacon value used by
the host-side Beacon Recovery logic.

Conceptually:

```text
Shelly application
        |
        | command 0x66
        v
WF200 WLAN subsystem
        |
        | statistics response
        v
current received-beacon count C
```

The Shelly application therefore consumes a statistic maintained by the WLAN
subsystem.

It does not implement the low-level received-beacon counter itself.

### Classification

**PROVEN**

---

# Relevant Statistics Returned by Command `0x66`

The relevant returned fields correspond to:

```text
received beacon count
missed beacon count
TBTT timing difference
```

In the identified host-side statistics storage, these fields are adjacent and
the received-beacon count is the field used by the known
`real_beacon_skip` calculation.

The host does not directly use the missed-beacon or TBTT-difference values in
that calculation.

Conceptually:

```text
command 0x66
        |
        +---- received beacon count ----> Beacon Recovery calculation
        |
        +---- missed beacon count
        |
        +---- TBTT difference
```

### Classification

Existence and host-side mapping of the relevant statistics:

**PROVEN**

Exact protected-WF200 implementation of those counters:

**UNRESOLVED**

---

# Received-Beacon Count

The received-beacon field is a cumulative WF200 statistic associated with
received WLAN beacons.

For example:

```text
P = 12000
C = 12030
```

gives:

```text
delta = 30
```

The absolute counter value:

```text
12030
```

is not the direct quantity used by the known Beacon Recovery calculation.

The relevant host-side quantity is:

```text
C - P
```

The exact internal WF200 event that increments the cumulative counter has not
been independently traced inside the protected WLAN implementation.

### Classification

Cumulative host-visible statistic and its use:

**PROVEN**

Exact internal increment semantics:

**UNRESOLVED**

---

# Missed-Beacon Count

A separate statistic corresponding to missed beacon reception is returned by
the WF200 subsystem.

The host stores this value, but it is not directly used in the identified
`real_beacon_skip` calculation.

The firmware therefore does **not** calculate a ratio such as:

```text
received
------------------
received + missed
```

for Beacon Recovery.

Instead, the identified calculation uses only the change in the cumulative
received-beacon count together with the fixed constant `600`.

The exact treatment of deliberately skipped beacon opportunities by the
WF200 missed-beacon statistic has not been independently established by this
project.

### Classification

Existence and host-side field mapping:

**PROVEN**

Not directly used by the known `real_beacon_skip` calculation:

**PROVEN**

Exact behavior under intentional beacon skipping:

**UNRESOLVED**

---

# TBTT Difference

The statistics also contain a TBTT-related field.

TBTT means:

```text
Target Beacon Transmission Time
```

This value is timing-related information.

It is not another simple received- or missed-beacon count and is not the
direct input to the identified `real_beacon_skip` calculation.

The host-side Beacon Recovery calculation does not normalize its received
counter delta using this TBTT field.

### Classification

Host-side field role:

**PROVEN**

Detailed protected-WF200 timing semantics:

**UNRESOLVED**

---

# Host-Side Calculation

When a previous baseline exists and the current counter has increased, the
firmware approximately performs:

```text
delta = C - P

quotient = 600 / delta

R = uint8_t(quotient)
```

The host then updates:

```text
P = C
```

and the resulting cached byte `R` can be evaluated by the Beacon Recovery
control logic.

Conceptually:

```text
command 0x66
        |
        v
C
        |
        +---- P
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

The arithmetic itself is well established.

The original engineering rationale for interpreting the resulting value as an
effective beacon-skip measurement is not explicitly documented in the
application firmware.

---

# The Constant `600`

The numerator:

```text
600
```

is hard-coded in the host-side calculation.

The surrounding behavior is consistent with an attempt to derive an effective
beacon-skip relationship from the number of received beacons over an assumed
measurement interval.

A likely conceptual model is:

```text
nominal beacon opportunities
            /
received beacons
            =
effective beacon skip
```

However, the firmware does not attach an elapsed-time measurement to `P`.

Therefore the correctness of:

```text
600 / (C - P)
```

depends on the baseline representing the measurement interval assumed by the
constant.

### Classification

Use of the constant `600`:

**PROVEN**

Exact original engineering rationale:

**INFERENCE**

---

# Normal Baseline Lifecycle

In the normal case, a previous sample exists:

```text
P != 0
```

and a later successful statistics acquisition returns:

```text
C > P
```

The host can then calculate a fresh delta:

```text
delta = C - P
```

calculate a new `R`, and update:

```text
P = C
```

This permits consecutive fresh measurements when the measurement epoch remains
valid.

Conceptually:

```text
sample 1
C = 1000
        |
        v
P = 1000
        |
        | valid interval
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

This is the intended measurement progression inferred from the surrounding
control flow.

---

# Baseline Establishment When `P == 0`

If:

```text
P == 0
```

there is no previous counter value from which a valid delta can be calculated.

The stock firmware therefore installs the current counter as the new baseline:

```text
P = C
```

No fresh:

```text
600 / delta
```

calculation is possible on that pass.

This is an important data prerequisite.

A measurement requiring two cumulative counter samples cannot produce fresh
ratio evidence from only the first sample.

### Classification

**PROVEN**

---

# Counter Decrease or Equal Value

The firmware also protects against:

```text
C <= P
```

In that case it does not perform an unsigned subtraction that could produce a
large underflowed delta.

Instead, the relevant cached ratio is cleared and the current counter is used
as the new baseline.

Conceptually:

```text
C <= P
        |
        v
R = 0
P = C
```

This provides protection against counter decrease, reset, or another condition
where the previous baseline can no longer be used as a normal increasing
cumulative-counter reference.

### Classification

**PROVEN**

---

# Statistics Acquisition Failure

If the periodic command `0x66` statistics acquisition fails, stock firmware
clears both the host-side previous baseline and the cached
`real_beacon_skip`.

Conceptually:

```text
0x66 failure
        |
        +---- P = 0
        |
        +---- R = 0
```

This is significant because a statistics failure is one of the identified
stock paths that naturally breaks the cached-state relationship.

A subsequent successful statistics request must establish a new baseline
before a fresh ratio can be calculated.

### Classification

**PROVEN**

---

# C1b – Measurement-Window Validity

The baseline `P` is meaningful only if the interval between `P` and `C`
corresponds to the measurement window assumed by:

```text
600 / (C - P)
```

Stock firmware does not associate an explicit elapsed-time value with `P`.

Identified firmware paths can also suppress or skip expected measurement
opportunities while preserving the old baseline.

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

The resulting counter delta can therefore span a longer logical interval than
the formula assumes.

This is important even if the WF200 counter itself behaves exactly according
to its specification.

The problem is not necessarily:

```text
WF200 returned the wrong count
```

It can instead be:

```text
host compared correct cumulative counts from an invalid measurement window
```

### Classification

Absence of elapsed-time normalization:

**PROVEN**

Existence of identified paths that can preserve `P` across skipped measurement
opportunities:

**PROVEN**

Measurement-validity defect:

**STRONGLY SUPPORTED**

Exact cause of the first observed field recovery:

**UNKNOWN**

---

# Why C1b Does Not Require a Faulty WF200 Counter

Earlier investigation placed substantial emphasis on determining the exact
protected-WF200 counter semantics.

Those semantics remain useful for understanding the intended measurement.

However, the C1b problem exists at a different layer.

Assume that:

```text
WF200 cumulative counter = completely correct
```

If the host compares two valid cumulative values across an interval longer
than the interval assumed by the fixed numerator `600`, the resulting quotient
can still represent the wrong measurement window.

Therefore:

> Proving the exact WF200 counter semantics is not required to establish the
> host-side baseline-age problem.

WF200 semantics remain relevant to the complete engineering interpretation,
but they are no longer a prerequisite for identifying C1b.

---

# C1a – 8-Bit Signed Interpretation

After:

```text
600 / delta
```

the quotient is stored in an 8-bit field.

Stock recovery control subsequently reads that byte as signed.

This creates additional qualifying values unrelated to baseline age.

For example:

```text
delta = 3
600 / 3 = 200
uint8_t = 0xC8
signed 8-bit interpretation = -56
```

and:

```text
delta = 4
600 / 4 = 150
uint8_t = 0x96
signed 8-bit interpretation = -106
```

Because the stock predicate rejects zero and accepts values less than or equal
to `2`, these negative interpretations qualify.

The fresh stock trigger set is therefore:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

The `delta = 3` and `delta = 4` cases are caused by the signed interpretation,
not by the cumulative counter itself.

### Classification

Signed interpretation changes the control decision:

**PROVEN**

Defect classification:

**STRONGLY SUPPORTED**

For the full arithmetic analysis, see:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

# C2 – Baseline and Cached-Control State

The relationship between `P` and `R` becomes particularly important after a
qualifying recovery.

Stock firmware clears:

```text
P
```

but retains:

```text
R
```

Therefore the next successful sample begins conceptually with:

```text
P = 0
R = historical qualifying value
```

Because `P == 0`, that sample can only establish:

```text
P = C
```

It cannot calculate a fresh ratio.

However, stock control flow then evaluates the retained historical `R`.

If that value still qualifies, recovery runs again and clears `P` again.

Conceptually:

```text
fresh qualifying R
        |
        v
recovery
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
recovery again
        |
        v
P = 0
```

The newly established baseline therefore does not survive to the next sample.

This creates the identified self-sustaining Beacon Recovery state.

### Classification

Host-side stale-control-evidence loop:

**PROVEN**

Normal successful statistics acquisition breaks the loop:

**FALSE**

Normal PM restoration clears `R`:

**FALSE**

Whether retaining `R` itself was intended for diagnostic history:

**UNKNOWN**

For the complete control-flow analysis, see:

[`recovery-mechanism.md`](recovery-mechanism.md)

---

# Important Distinction: Diagnostic History vs. Measurement Validity

The cached `R` value is also exposed diagnostically.

Therefore retaining the most recently calculated value can have a coherent
diagnostic purpose.

The problem is not necessarily that:

```text
R was retained
```

The demonstrated problem is that:

```text
historical R
```

can be treated as:

```text
fresh control evidence
```

on a pass where no fresh ratio was calculated.

This distinction is central to the corrective Patch C design.

---

# Desired Beacon Skip vs. Counter-Derived Beacon Skip

The firmware separately maintains a requested WLAN power-save parameter:

```text
desired_beacon_skip
```

and the counter-derived diagnostic/control value:

```text
real_beacon_skip
```

They are not the same quantity.

The normal desired skip is selected from RSSI:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

The desired value is passed to the WF200 power-management configuration.

`real_beacon_skip`, by contrast, is derived from:

```text
600 / (C - P)
```

The stock recovery logic does not simply compare:

```text
real_beacon_skip
```

against:

```text
desired_beacon_skip
```

Therefore:

```text
desired skip = 20
```

does not imply:

```text
real_beacon_skip = 20
```

and:

```text
desired skip = 15
```

does not imply:

```text
real_beacon_skip = 15
```

---

# Runtime Evidence Across Different Desired-Skip Regimes

Recurring Beacon Recovery has been observed under more than one normal
RSSI-dependent desired-skip configuration.

On a stock 2.2.4 reference device, recurring recovery was observed with
relatively strong RSSI around:

```text
-58 to -60 dBm
```

corresponding to:

```text
desired_beacon_skip = 20
```

On the mDNS-only Patch-B test device, recurring Beacon Recovery has also been
observed with RSSI approximately:

```text
-75 to -77 dBm
```

corresponding to:

```text
desired_beacon_skip = 15
```

The latter device retains the stock Beacon Recovery mechanism.

This provides an important runtime constraint:

> The recurring recovery loop is not specific to the desired-skip-20 policy
> regime.

It also reinforces the distinction between:

```text
RSSI-dependent requested skip
```

and:

```text
counter-derived recovery evidence
```

These observations do not establish that RSSI or AP behavior is irrelevant.

They establish that the recurring loop cannot be explained solely as a
strong-RSSI/skip-20-specific condition.

---

# Relationship to Periodic mDNS

Patch B bypasses the recurring connected-maintenance mDNS restart while
retaining:

- command `0x66`
- beacon statistics
- received-beacon counter handling
- `real_beacon_skip`
- stock Beacon Recovery

Runtime testing demonstrated that recurring Beacon Recovery can continue on
this configuration.

Therefore:

> The periodic mDNS restart is not required for the observed recurring Beacon
> Recovery behavior under the tested conditions.

This does not prove that unrelated network activity can never influence WLAN
statistics or timing.

It establishes only that the identified periodic mDNS restart is not necessary
for the observed loop.

---

# Relationship to D3 Power-Save Errors

Runtime logs can also contain WF200 power-save error indications.

One identified reason corresponds to the AP indicating buffered unicast data
without delivering it during multiple consecutive beacons.

These events demonstrate that real AP/WF200 power-save timing conditions occur
during field operation.

However, no direct host-side control or data-flow edge has been established
from a D3 power-save error to the Beacon Recovery decision.

Therefore:

```text
D3 event
    ->
Beacon Recovery
```

must not currently be presented as proven causality.

Radio-internal effects on subsequent beacon statistics remain possible, but
that relationship is presently:

**INFERENCE / UNKNOWN**

---

# Relationship to AP Selection and Roaming

Separate firmware analysis shows that the analyzed host connection path uses:

```text
wildcard BSSID
channel = 0
prevent_roaming = 1
```

The host does not implement a normal background policy that continuously
selects a stronger BSSID.

Association with a less favorable AP could plausibly influence:

- beacon reception
- WLAN timing
- retransmissions
- power-save behavior

However, no causal path has been established from AP selection to the
qualifying counter delta that starts Beacon Recovery.

AP selection is therefore relevant environmental context, not a demonstrated
cause.

For details, see:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

---

# Remaining WF200 Semantics Questions

The exact protected-WF200 counter semantics remain incompletely characterized.

Relevant open questions include:

- exactly which received beacon event increments the cumulative counter
- treatment of intentionally skipped beacon opportunities
- exact semantics of the missed-beacon statistic
- DTIM interaction
- behavior during power-state transitions
- behavior across association changes
- counter rollover and reset behavior
- relationship between internal radio fallback and returned statistics

These questions matter for reconstructing the original measurement model.

They do **not**, however, invalidate the host-side findings already
established for C1a, C1b, and C2.

This distinction is important.

---

# What the Counter Does Not Prove

The received-beacon counter alone does not establish:

- how many beacons the access point transmitted
- the exact physical duration represented by a host-side delta
- how many beacon opportunities were deliberately skipped
- how many frames were lost because of RF conditions
- how DTIM affected reception
- that the access point is faulty
- that the WF200 implementation is faulty
- that the associated BSSID is unfavorable
- that transmit power increased
- that a particular counter delta caused measurable battery drain

Likewise:

```text
qualifying counter-derived value
```

does not automatically mean:

```text
genuine RF failure
```

because host-side measurement validity must also be considered.

---

# Patch A and the Counter Path

Patch A bypasses the Beacon Recovery action.

It does not correct or remove:

- command `0x66`
- the received-beacon counter
- the missed-beacon counter
- the TBTT-difference statistic
- baseline sampling
- the `600 / delta` calculation
- `real_beacon_skip`
- normal desired beacon skip

Conceptually:

```text
WF200 statistics
        |
        v
C and P
        |
        v
600 / delta
        |
        v
R
        |
        v
recovery predicate
        |
        X
recovery action bypassed
```

Patch A is therefore an isolation tool.

Successful operation with Patch A does not establish that the underlying
measurement logic is correct.

---

# Patch C-C and Counter Validity

The current Patch C-C candidate is designed to preserve the WF200 statistics
mechanism while correcting the identified host-side validity problems.

At the behavioral level, the candidate is intended to:

- retain command `0x66`
- retain the cumulative WF200 statistics
- retain diagnostic `R`
- preserve legitimate fresh Beacon Recovery
- interpret the control byte as unsigned
- invalidate `P` across identified invalid measurement epochs
- prevent historical `R` from qualifying a baseline-only sample
- allow a newly established baseline to survive until a fresh comparable
  measurement is available

Conceptually:

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
        +---- healthy ----> continue
        |
        +---- qualifying -> legitimate Beacon Recovery
```

The C-C candidate has passed static pre-build qualification.

No known static blocker was identified in the bounded independent review.

This does **not** establish runtime correctness or battery-life improvement.

Experimental build verification and controlled hardware qualification remain
required.

---

# Measurement-Window Qualification in Patch C-C

The current candidate does not add a persistent timestamp to every baseline.

Instead, it invalidates `P` at identified events that make the previous
measurement epoch unsuitable for comparison.

These include, in the reviewed design:

- missed relevant scheduler boundaries
- H-gated measurement periods
- relevant PM state/policy commits
- PM completion
- association/reassociation state changes
- known clock correction/reset paths
- statistics acquisition failure through the existing stock behavior

The design therefore implements a **logical measurement-epoch validity
model**, not a mathematically exact physical elapsed-time normalization.

This distinction remains important.

### Static qualification result

No concrete path retaining `P` across a known invalid long logical interval
was identified in the pre-build falsification review.

### Remaining runtime qualification

The following remain unresolved until hardware testing:

- physical sample age during unusually delayed callback execution
- very long external PM transactions
- exact physical RF completion timing
- measurement availability under persistent policy/connection churn

These are hardware-qualification items rather than demonstrated static defects
in the current candidate.

---

# Battery-Consumption Relevance

The received-beacon counter itself is only a statistic.

Its battery relevance comes from the control decision made from it.

The identified chain is:

```text
WF200 statistics
        |
        v
received-beacon counter
        |
        v
host-side measurement
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery decision
        |
        v
temporary active WLAN configuration
        |
        v
additional recurring power-management activity
```

Repeated recovery can therefore create additional workload.

However:

```text
counter value
```

is not equivalent to:

```text
energy consumption
```

and:

```text
Beacon Recovery defect
```

is not equivalent to:

```text
complete historical battery-drain explanation
```

The quantitative battery contribution remains under long-term investigation.

Historical battery drain was also observed on firmware older than 2.2.4, so
the 2.2.4 Beacon Recovery mechanism cannot explain the entire historical
problem.

---

# Evidence Classification

| Finding | Status |
|---|---|
| Relevant beacon statistics originate from the WF200 WLAN subsystem | **PROVEN** |
| Firmware 2.2.4 requests them through command `0x66` | **PROVEN** |
| The host does not increment the low-level received-beacon counter itself | **PROVEN** |
| The received-beacon value is cumulative | **PROVEN** |
| Separate missed-beacon and TBTT-difference fields exist | **PROVEN** |
| The received-beacon counter is used for `real_beacon_skip` | **PROVEN** |
| The host uses `C - P` | **PROVEN** |
| The host calculates `600 / (C - P)` when a usable previous baseline exists | **PROVEN** |
| The missed-beacon field is not directly used in that calculation | **PROVEN** |
| The TBTT-difference field is not used to normalize the calculation | **PROVEN** |
| `P == 0` means a fresh ratio cannot be calculated on that sample | **PROVEN** |
| `C <= P` is handled without subtraction underflow | **PROVEN** |
| `0x66` failure clears both `P` and `R` | **PROVEN** |
| Recovery clears `P` while retaining qualifying `R` | **PROVEN** |
| Stock baseline-only processing can evaluate historical `R` | **PROVEN** |
| Stock signed interpretation adds `delta = 3` and `delta = 4` to the qualifying set | **PROVEN** |
| The fixed-600 calculation has no corresponding elapsed-time normalization | **PROVEN** |
| Identified firmware paths can preserve `P` across skipped measurement opportunities | **PROVEN** |
| This creates a host-side measurement-validity problem | **STRONGLY SUPPORTED** |
| Exact internal WF200 received-counter increment semantics are known | **UNRESOLVED** |
| Exact treatment of intentionally skipped beacons is known | **UNRESOLVED** |
| Exact missed-beacon semantics under TRV Fast Power Save are known | **UNRESOLVED** |
| WF200 statistics must be faulty for C1b to exist | **FALSE** |
| Poor RSSI is required for the recurring recovery loop | **NOT SUPPORTED** |
| Periodic mDNS is required for the recurring recovery loop | **NOT SUPPORTED** |
| The recurring loop is specific to desired skip 20 | **NOT SUPPORTED** |
| D3 power-save errors directly cause Beacon Recovery | **NOT PROVEN** |
| Patch C-C has passed static pre-build qualification | **PROVEN** |
| Patch C-C has passed hardware qualification | **NOT YET ESTABLISHED** |
| The counter path proves a quantitative battery penalty | **NOT SUPPORTED** |

---

# Remaining Questions

The remaining questions are now more narrowly defined.

## 1. Exact WF200 counter semantics

What precise internal radio event increments the cumulative received-beacon
counter?

---

## 2. Intentional beacon skipping

How are deliberately skipped beacon opportunities represented in:

```text
received beacon count
missed beacon count
TBTT difference
```

under WF200 Fast Power Save?

---

## 3. DTIM behavior

How do DTIM interval and DTIM reception affect the three statistics?

---

## 4. Physical measurement interval

How closely does the actual physical interval between successful statistics
samples match the logical interval assumed by the host?

Patch C-C addresses identified invalid logical epochs, but does not introduce a
formal per-baseline physical timestamp.

---

## 5. External PM transactions

Can an unusually long externally initiated PM transaction overlap two
successful Beacon Recovery measurement samples before the PM completion path
invalidates the baseline?

Static analysis did not establish such a sequence, but it also could not prove
a strict external transaction duration bound.

This requires hardware qualification.

---

## 6. First field trigger

Which exact event produces the first qualifying fresh measurement on affected
physical devices?

Possible contributors include:

- invalid baseline age
- genuine radio behavior
- AP/WF200 power-save timing
- association changes
- other still-unidentified runtime conditions

The exact field trigger remains:

**UNKNOWN**

---

## 7. Quantitative energy impact

How much battery energy is consumed by:

- periodic Beacon Recovery
- periodic mDNS
- their combination
- other WLAN power-management behavior

This requires long-term comparison and, ideally, direct electrical
measurement.

---

# Current Working Model

The current evidence supports:

```text
Access point / radio environment
        |
        v
WF200 WLAN subsystem
        |
        | protected internal beacon handling
        | exact low-level semantics partly unresolved
        v
command 0x66 statistics
        |
        +---- current received count C
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
control-value interpretation
        |
        v
Beacon Recovery decision
```

Three distinct host-side validity problems have been identified:

```text
C1a
signed interpretation of R

C1b
measurement-window / baseline validity

C2
historical R reused as fresh control evidence
```

The exact protected-WF200 semantics remain an upstream research question.

They are no longer required to establish those three host-side problems.

---

# Current Conclusion

The role of the WF200 received-beacon counter in firmware 2.2.4 is now
substantially understood at the host side.

The firmware:

1. requests WF200 statistics through command `0x66`
2. receives a cumulative beacon-related counter `C`
3. retains a previous host-side baseline `P`
4. calculates `C - P` when the baseline is usable
5. divides the fixed value `600` by that delta
6. stores the result as the 8-bit cached value `R`
7. uses `R` in the Beacon Recovery decision

The investigation has progressed beyond the earlier question of whether the
WF200 statistics alone explain the observed behavior.

Independent host-side problems are now established:

- signed interpretation can change the recovery decision
- the fixed-600 calculation can operate on an invalid measurement window
- recovery can clear the baseline while retaining qualifying historical
  control evidence
- the retained value can then prevent a new baseline from surviving long
  enough to obtain a fresh measurement

The exact WF200 counter semantics remain relevant for reconstructing the
original design and understanding the first field trigger.

They are **not** required to establish the identified host-side validity
problems.

Patch C-C therefore focuses on correcting host-side measurement and control
validity while preserving the WF200 statistics mechanism and legitimate fresh
Beacon Recovery.

The candidate has passed static pre-build qualification.

The next research stage is experimental build verification followed by
controlled hardware qualification.

---

# Related Documents

Detailed `real_beacon_skip` arithmetic:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

Firmware-version comparison:

[`firmware-comparison.md`](firmware-comparison.md)

AP-selection behavior:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Periodic mDNS behavior:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

---

# Research Methodology

This investigation is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

Important conclusions are checked against native ARM Thumb instructions and
control flow rather than relying only on decompiler output.

The host-side statistics path was traced from:

```text
WF200 command 0x66
```

through:

```text
counter storage
```

and:

```text
baseline handling
```

to:

```text
real_beacon_skip
```

and:

```text
Beacon Recovery
```

The protected WF200 implementation has not been reproduced or fully reverse
engineered.

The project deliberately distinguishes:

```text
PROVEN
STRONGLY SUPPORTED
INFERENCE
UNKNOWN
NOT SUPPORTED
NOT PROVEN
```

to separate direct firmware evidence from interpretation.

No original or modified firmware images, complete proprietary functions, or
large raw disassemblies are published in this document.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the tested firmware versions.

No conclusions about the intentions of the original developers are inferred
unless independently supported by technical evidence.