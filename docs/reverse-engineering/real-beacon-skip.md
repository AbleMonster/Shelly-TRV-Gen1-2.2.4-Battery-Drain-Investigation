# `real_beacon_skip` Analysis

## Scope

This document describes the reverse-engineering findings for the
`real_beacon_skip` mechanism in Shelly TRV Gen1 firmware 2.2.4.

The purpose of this analysis is to determine:

- what `real_beacon_skip` represents
- how it differs from `desired_beacon_skip`
- where its input data originates
- how the value is calculated
- how the 8-bit result is stored and interpreted
- how it participates in Beacon Recovery
- which measurement assumptions are made by the host firmware
- how power-management transitions affect measurement validity
- why a qualifying recovery can become self-sustaining
- which parts of the behavior are corrected by the current Patch C-C design
- what remains unresolved

The analysis distinguishes three separate problems:

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-recovery control-evidence freshness
```

These problems are related, but they are not the same defect.

No firmware images, complete proprietary functions, or large raw
disassemblies are reproduced here.

---

# 1. Evidence Classification

This project uses the following evidence levels.

## PROVEN

Directly established from native firmware instructions, deterministic binary
comparison, validated control flow, or sufficiently direct runtime evidence.

## STRONGLY SUPPORTED

Multiple independent findings support the conclusion, but some implementation
detail, runtime dependency, or original design intent remains unresolved.

## INFERENCE

A technically plausible interpretation consistent with the available evidence,
but not directly established.

## UNKNOWN

The available evidence is insufficient to determine the behavior, runtime
frequency, quantitative effect, or original developer intent.

Runtime observations are described explicitly where relevant.

---

# 2. Summary

Firmware 2.2.4 maintains two conceptually different beacon-skip values:

```text
desired_beacon_skip
```

and:

```text
real_beacon_skip
```

They must not be treated as equivalent.

`desired_beacon_skip` is the beacon-skip policy requested by the application.

`real_beacon_skip` is a host-side value derived from WF200 cumulative
received-beacon statistics.

The known calculation is approximately:

```text
C = current_beacon_rx_count
P = previous_beacon_rx_count

delta = C - P

R = uint8_t(600 / delta)
```

where:

```text
R = real_beacon_skip
```

The resulting byte is stored and later used for two different purposes:

```text
R
|
+---- diagnostic output through /stats
|
+---- Beacon Recovery control decision
```

This dual use is important.

The diagnostic value can legitimately represent historical information.

The recovery decision, however, requires fresh and valid measurement evidence.

The stock firmware does not always maintain that distinction.

Three separate host-side validity problems have been identified.

### C1a — Signed control-value validity

The division is unsigned and the result is stored in one byte.

The recovery predicate later loads the byte as signed.

This causes unsigned results such as:

```text
200
150
```

to become:

```text
-56
-106
```

and therefore satisfy the signed:

```text
R <= 2
```

test.

### C1b — Measurement-window validity

The calculation uses the fixed numerator:

```text
600
```

but the previous counter baseline `P` has no corresponding elapsed-time
metadata.

Identified PM and scheduler conditions can cause measurement opportunities to
be skipped while stock firmware preserves `P`.

A later sample can therefore compare counters across an invalid measurement
epoch while still applying the fixed `600` model.

### C2 — Post-recovery freshness failure

After a qualifying Recovery:

```text
P = 0
```

but the qualifying diagnostic value:

```text
R
```

is preserved.

The next successful sample establishes a new baseline but does not calculate a
fresh `R`.

Stock firmware nevertheless evaluates the historical `R`.

If it still qualifies, Recovery occurs again and clears the newly established
baseline.

This creates a self-sustaining control loop.

Therefore the currently established model is:

```text
fresh or invalid qualifying measurement
        |
        v
qualifying R
        |
        v
first Recovery
        |
        v
P cleared
R retained
        |
        v
baseline-only sample
        |
        v
historical R reused
        |
        v
Recovery again
        |
        v
self-sustaining loop
```

The exact cause of the first qualifying event on the observed physical devices
remains unknown.

The subsequent stale-value loop does not.

---

# 3. `desired_beacon_skip` vs. `real_beacon_skip`

Firmware 2.2.4 maintains two conceptually different values.

## `desired_beacon_skip`

`desired_beacon_skip` represents the beacon-skip interval requested by the
application.

The analyzed RSSI policy is:

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

This is a policy/configuration value.

---

## `real_beacon_skip`

`real_beacon_skip` is derived from WF200 beacon reception statistics.

Conceptually:

```text
WF200 beacon statistics
        |
        v
beacon_rx_count
        |
        v
difference from previous sample
        |
        v
600 / delta
        |
        v
8-bit value
        |
        v
real_beacon_skip
```

Therefore a device can have:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

without this meaning that the application changed its requested WLAN
configuration from skip 20 to skip 1.

The two values describe different concepts:

```text
desired_beacon_skip
        |
        +-- requested WLAN power-save policy


real_beacon_skip
        |
        +-- host-derived diagnostic/control value
            based on received-beacon statistics
```

This distinction is essential when interpreting `/stats`, debug logs, and
Beacon Recovery.

---

# 4. Internal Storage and `/stats`

Reverse engineering of the `/stats` generation path shows that the reported:

```text
real_beacon_skip
```

is read from the same internal byte used by the Beacon Recovery logic.

There is no separate calculation performed solely for the HTTP statistics
output.

Conceptually:

```text
internal R byte
    |
    +---- /stats
    |
    +---- Recovery predicate
```

The `/stats` formatter reads the byte as a signed value.

Therefore `/stats` can expose negative values when the stored byte is greater
than `127`.

This is separate from the question of whether that same signed interpretation
is appropriate for Recovery control.

### Classification

Shared internal field:

**PROVEN**

`/stats` diagnostic exposure:

**PROVEN**

---

# 5. WF200 Statistics Source

Firmware 2.2.4 queries WF200 statistics through command:

```text
0x66
```

The returned statistics include fields corresponding to:

```text
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

For the known `real_beacon_skip` calculation, the application uses:

```text
beacon_rx_count
```

The host keeps:

```text
C = current beacon_rx_count
P = previous beacon_rx_count
```

The known ratio calculation does not directly use:

```text
beacon_rx_missed_count
```

or:

```text
beacon_tbtt_diff
```

as the denominator or direct Recovery input.

This distinction is important.

Beacon Recovery is not simply:

```text
if missed_beacons > threshold:
    recover()
```

Instead, the host derives its own value from the change in the cumulative
received-beacon counter.

---

# 6. WF200 Counter Semantics

The WF200 statistics interface describes the relevant received-beacon value as
a cumulative per-interface received-beacon count.

The separate missed-beacon field is distinct.

This means that the host calculation is based on:

```text
change in received-beacon count
```

rather than directly on:

```text
number of missed beacons
```

Intentional beacon skipping is particularly important.

A deliberately skipped beacon opportunity is not necessarily equivalent to an
unintentionally missed expected beacon.

Therefore the host-side calculation must be interpreted in the context of the
configured WF200 power-save behavior.

The exact physical relationship between:

```text
received beacons
intentional beacon skipping
DTIM handling
AP timing
WF200 internal behavior
```

remains relevant to the deeper radio analysis.

However, complete resolution of those radio semantics is no longer required
to establish C1a, C1b, or C2.

Those defects are identifiable from the host-side control flow itself.

---

# 7. Counter Variables

For clarity, this document uses:

```text
C = current received-beacon counter
P = previous received-beacon baseline
R = cached real_beacon_skip byte
H = shared PM override / Recovery countdown
```

The relevant internal state is therefore approximately:

```text
C
current cumulative WF200 received-beacon count

P
previous cumulative received-beacon baseline

R
cached calculated real_beacon_skip

H
shared countdown that can suppress the periodic
Beacon Recovery statistics evaluation
```

These values have different lifetimes.

In particular:

```text
P
```

is measurement history.

```text
R
```

is both diagnostic history and control input.

That distinction becomes central after Recovery.

---

# 8. Native Calculation

When the required counter conditions are satisfied, firmware 2.2.4 performs
approximately:

```text
delta = C - P
```

followed by:

```text
ratio = 600 / delta
```

The division is unsigned.

The result is then narrowed to one byte:

```text
R = uint8_t(ratio)
```

The relevant type sequence is:

```text
C - P
  |
  v
unsigned delta
  |
  v
600 / delta
  |
  v
unsigned quotient
  |
  v
low 8 bits stored
  |
  v
R
```

Later, stock Recovery control reads `R` as a signed byte.

Therefore the complete stock control interpretation is approximately:

```text
delta = C - P

ratio = 600 / delta

R = uint8_t(ratio)

signed_R = int8_t(R)

if signed_R != 0 and signed_R <= 2:
    Recovery
```

### Classification

Calculation:

**PROVEN**

8-bit narrowing:

**PROVEN**

Later signed control load:

**PROVEN**

---

# 9. Baseline Preconditions

The calculation is not performed for every successful statistics acquisition.

The previous baseline matters.

Conceptually:

```text
successful command 0x66
        |
        v
P available?
   |          |
  no         yes
   |          |
   v          v
P = C      compare C and P
```

If:

```text
P == 0
```

the current counter becomes the baseline.

There is no valid previous sample from which to calculate a fresh ratio.

If:

```text
P != 0
```

the firmware can evaluate the current counter relative to the previous
baseline.

A further protection handles non-increasing counters.

Conceptually:

```text
C <= P
```

does not proceed as a normal positive-delta measurement.

This protects against obvious invalid/non-progressing counter relationships.

However, it does not protect against an old but numerically valid baseline.

That is the C1b problem.

---

# 10. Interpretation of the Constant `600`

The mathematical use of:

```text
600
```

is directly established by the firmware.

The original engineering rationale is not explicitly documented.

The surrounding logic strongly suggests a model resembling:

```text
nominal beacon opportunities
          /
received beacons during nominal interval
          =
estimated effective beacon skip
```

A plausible interpretation is:

```text
~60 seconds
/
~100 ms beacon interval
≈
600 nominal beacon opportunities
```

This interpretation is consistent with the surrounding minute-maintenance
logic and ordinary WLAN beacon timing.

However, the original design intent is not directly documented.

Therefore:

```text
firmware uses constant 600
```

is:

**PROVEN**

while:

```text
600 specifically means exactly 60 s / 100 ms
```

is:

**INFERENCE**

The more important host-side fact is that `600` is fixed.

The baseline `P` has no associated elapsed-time field used by this calculation.

---

# 11. C1a — Signed Control-Value Validity

The first identified control-validity problem occurs after the unsigned
division result has been stored.

Stock firmware later reads `R` using a signed byte load.

This means that:

```text
0x00 .. 0x7F
```

are interpreted as:

```text
0 .. 127
```

while:

```text
0x80 .. 0xFF
```

are interpreted as:

```text
-128 .. -1
```

The Recovery predicate is effectively:

```text
signed_R != 0
&&
signed_R <= 2
```

Therefore any negative signed value also satisfies:

```text
signed_R <= 2
```

provided it is non-zero.

This is a control interpretation issue.

The stored diagnostic byte itself does not have to be removed or redesigned to
correct it.

---

# 12. Exact Fresh Trigger Domain

For a fresh positive delta, the relevant stock calculation is:

```text
R = uint8_t(600 / delta)
```

followed by signed interpretation.

Important examples are:

| Delta | `600 / delta` | Stored byte | Signed interpretation | Stock Recovery |
|---:|---:|---:|---:|---|
| 1 | 600 | 88 | 88 | No |
| 2 | 300 | 44 | 44 | No |
| 3 | 200 | 200 | -56 | Yes |
| 4 | 150 | 150 | -106 | Yes |
| 5 | 120 | 120 | 120 | No |
| 6 | 100 | 100 | 100 | No |
| 200 | 3 | 3 | 3 | No |
| 201–300 | 2 | 2 | 2 | Yes |
| 301–600 | 1 | 1 | 1 | Yes |
| >600 | 0 | 0 | 0 | No |

Therefore the fresh stock trigger set is:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

For ordinary non-negative interpretation of the quotient, the intended-looking
positive trigger domain would instead be:

```text
delta = 201 .. 600
```

The additional:

```text
delta = 3
delta = 4
```

cases exist solely because of the later signed-byte interpretation.

### Classification

Exact stock trigger domain:

**PROVEN**

Extra delta-3 and delta-4 trigger regions caused by signed interpretation:

**PROVEN**

C1a as a genuine control/measurement-validity defect:

**STRONGLY SUPPORTED**

Original developer intent:

**UNKNOWN**

---

# 13. Why C1a Matters

Consider:

```text
delta = 3
```

The firmware computes:

```text
600 / 3 = 200
```

and stores:

```text
R = 200
```

The control path then interprets:

```text
int8_t(200) = -56
```

The predicate becomes:

```text
-56 != 0
```

and:

```text
-56 <= 2
```

Both are true.

Recovery therefore occurs even though the unsigned calculated value was:

```text
200
```

rather than:

```text
1
```

or:

```text
2
```

This behavior follows directly from the native storage and load semantics.

It is not a hypothetical arithmetic model introduced by the analysis.

---

# 14. C1b — Measurement-Window Validity

C1b is independent of C1a.

Even if `R` is interpreted correctly as unsigned, the input measurement itself
can be invalid.

The formula assumes:

```text
600 / (C - P)
```

but the firmware does not attach an elapsed-time value to `P`.

Therefore the calculation depends on an implicit assumption:

```text
P and C represent the expected nominal measurement window
```

That assumption is not always preserved.

Identified firmware paths can:

```text
retain P
```

while:

```text
one or more normal measurement opportunities are skipped
```

or while the WLAN PM policy changes.

The later sample then uses:

```text
old P
new C
fixed 600
```

even though the logical measurement epoch has changed.

---

# 15. The Shared Countdown `H`

A key example involves the shared countdown:

```text
H
```

State-5 / `psovrd2` behavior can set:

```text
H = 180
```

Beacon Recovery itself uses:

```text
H = 5
```

The periodic Beacon Recovery statistics block is gated by:

```text
H != 0
```

Conceptually:

```text
periodic measurement opportunity
        |
        v
H != 0 ?
   |          |
  yes         no
   |           |
   v           v
skip        command 0x66
evaluation     |
               v
             evaluate
```

In stock firmware, the H-gated path does not necessarily invalidate `P`.

Therefore:

```text
P
```

can survive across a period in which expected intermediate measurement
opportunities did not occur.

### Classification

H gate:

**PROVEN**

Baseline preservation across the identified H-gated path:

**PROVEN**

---

# 16. Example of Baseline Aging

Consider a simplified nominal sequence.

At:

```text
t0
```

the host records:

```text
P = C0
```

Shortly afterwards, a temporary PM override begins:

```text
H = 180
```

The next periodic measurement opportunities can be skipped while `H` remains
non-zero.

After the override expires, a later successful sample obtains:

```text
C1
```

Stock firmware can then calculate:

```text
delta = C1 - C0

R = 600 / delta
```

even though:

```text
C0 -> C1
```

does not represent the nominal measurement interval assumed by the fixed
numerator.

The counter itself can be completely correct.

The host comparison can still be invalid.

This is an important distinction:

```text
correct cumulative counter
+
invalid baseline epoch
=
invalid derived measurement
```

---

# 17. Reachable False-Qualifying Measurement

A simple model demonstrates why baseline age can matter even with an otherwise
correctly operating radio.

Assume a normal desired skip of approximately:

```text
10
```

and a baseline established shortly before a temporary 180-second override.

If the next usable comparison occurs only after the skipped measurement
opportunities, the baseline can span roughly:

```text
240 seconds
```

instead of the nominal interval.

A corresponding received-beacon delta can plausibly be around:

```text
~213
```

under the simplified model.

The host still calculates:

```text
600 / 213 = 2
```

which qualifies for Recovery.

This example demonstrates reachability of a false positive under the host's
fixed-window model.

It is not presented as a captured field trace.

Therefore:

```text
C1b can generate a qualifying result
without a faulty cumulative counter
```

is:

**STRONGLY SUPPORTED**

while:

```text
this exact sequence caused the observed first field Recovery
```

is:

**UNKNOWN**

---

# 18. Other Measurement-Epoch Boundaries

The current analysis identifies several classes of events that can make an old
baseline unsuitable for later comparison.

These include:

- skipped relevant scheduler opportunities
- temporary PM overrides
- PM policy transitions
- PM completion
- association/reassociation
- disconnect/connection changes
- known clock changes or resets
- counter epoch changes

Not every event necessarily produces an invalid measurement on every runtime
path.

The important design principle is:

> A cumulative counter baseline is only valid while the logical measurement
> epoch remains comparable.

Stock firmware does not consistently encode that validity separately.

---

# 19. `C <= P` Protection

Stock firmware does contain protection for a non-increasing counter.

Conceptually:

```text
if C <= P:
    R = 0
```

This prevents ordinary positive-delta calculation when:

```text
C <= P
```

Such a condition can occur after:

- counter reset
- counter epoch change
- unusual statistics behavior

This is useful protection.

However, it does not solve C1b.

An old baseline can still satisfy:

```text
C > P
```

while being temporally or logically invalid.

Therefore:

```text
C > P
```

proves numerical progression.

It does not prove measurement-window validity.

---

# 20. Recovery Predicate

After a fresh calculation, or when evaluating the cached value, stock firmware
tests `R`.

The effective predicate is:

```text
signed_R != 0
&&
signed_R <= 2
```

When accepted, firmware logs:

```text
Beacon skip error! Attempt recovery
```

and enters the Beacon Recovery PM sequence.

Conceptually:

```text
R
 |
 v
signed predicate
 |
 +---- false ---> continue normally
 |
 +---- true ----> Beacon Recovery
```

The important phrase is:

```text
after a fresh calculation,
or when evaluating the cached value
```

because those are not semantically equivalent situations.

That distinction leads directly to C2.

---

# 21. Diagnostic State vs. Control Evidence

`R` has two observable roles.

It is:

```text
diagnostic history
```

through:

```text
/stats real_beacon_skip
```

and it is also:

```text
Recovery control input
```

These roles have different freshness requirements.

A diagnostic value can reasonably remain visible after the event that produced
it.

For example:

```text
last measured real_beacon_skip = 2
```

can remain useful diagnostic information.

But that does not imply:

```text
the value 2 is fresh evidence
for another Recovery now
```

This gives the key semantic distinction:

```text
R may remain valid as diagnostic history

while

R is no longer valid as fresh Recovery-control evidence
```

No separate freshness flag for those two roles has been identified in stock
firmware.

---

# 22. C2 — Post-Recovery Freshness Failure

C2 begins after a genuinely qualifying Recovery.

Suppose:

```text
P != 0
```

and a fresh measurement produces:

```text
R = 2
```

The Recovery predicate accepts it.

The Recovery path then:

```text
sets H = 5
requests state 1
clears P
```

but does not clear:

```text
R
```

The resulting state is:

```text
P = 0
R = 2
```

This is not itself necessarily wrong.

Preserving `R` can have diagnostic value.

The problem occurs on the next successful statistics evaluation.

---

# 23. Baseline-Only Sample After Recovery

The next eligible successful command-`0x66` acquisition obtains:

```text
C = new cumulative beacon count
```

Because:

```text
P == 0
```

there is no previous counter baseline.

Therefore the firmware cannot calculate a fresh:

```text
C - P
```

measurement.

It instead establishes:

```text
P = C
```

At this point the correct logical state is:

```text
new baseline available

but

no fresh R exists yet
```

Stock firmware nevertheless continues to the Recovery predicate using the
historical cached `R`.

Therefore:

```text
P = C
R = old 2
```

is interpreted as if:

```text
R = 2
```

were fresh control evidence.

It is not.

---

# 24. Proof of the Self-Sustaining Loop

Starting from:

```text
P = 0
R = qualifying historical value
```

consider one successful eligible statistics evaluation.

### Step 1

Because:

```text
P == 0
```

the fresh ratio calculation is skipped.

### Step 2

The current counter becomes the new baseline:

```text
P = C
```

### Step 3

The historical cached `R` remains unchanged.

For example:

```text
R = 2
```

### Step 4

Stock firmware evaluates that historical `R`.

Because it qualifies:

```text
Recovery
```

occurs.

### Step 5

Recovery clears:

```text
P = 0
```

again.

It does not clear:

```text
R
```

The system has returned to:

```text
P = 0
R = 2
```

Therefore:

```text
(P = 0, qualifying R)
        |
        v
successful sample
        |
        v
P = C
        |
        v
historical R tested
        |
        v
Recovery
        |
        v
P = 0
        |
        +------------------+
                           |
                           v
                         repeat
```

No fresh anomalous beacon measurement is required for the repeated cycles.

### Classification

Self-sustaining C2 loop:

**PROVEN**

---

# 25. Why Normal Recovery Does Not Break C2

The Beacon Recovery PM action itself performs a real reconfiguration.

Conceptually:

```text
state 3
        |
        v
Recovery
        |
        v
state 1 / Active
        |
        | ~5 serviced seconds
        v
restore normal PM
        |
        v
state 3
```

The radio can therefore be successfully returned to normal power saving.

However, PM restoration does not itself clear the historical qualifying `R`.

Therefore:

```text
radio Recovery succeeds
```

and:

```text
host control loop remains latched
```

can both be true.

This is important.

The persistent loop does not prove that the WF200 failed to recover.

It proves that the host can retrigger Recovery without requiring a new
qualifying measurement.

---

# 26. No Normal Escape Within the Identified Successful Loop

Within the identified successful stock control flow, starting from:

```text
P = 0
R = qualifying
```

there is no ordinary successful-sample path that replaces `R` before it is
tested again.

A fresh replacement calculation requires:

```text
P != 0
```

at the beginning of a comparable measurement.

But the baseline-only sample triggers Recovery and clears `P` before the next
comparable sample can occur.

Therefore the system cannot naturally progress to:

```text
baseline sample
        |
        v
second comparable sample
        |
        v
fresh R
```

while the historical `R` continues to qualify.

### Classification

No normal successful-sample escape within the identified loop:

**PROVEN**

---

# 27. Identified Loop Breakers

The loop is not mathematically permanent under every possible firmware event.

Identified events capable of destroying the relevant cached relationship
include:

```text
startup / reset
```

and:

```text
periodic command 0x66 failure
```

where the identified failure path clears both relevant history fields.

Therefore a more precise statement is:

> No normal escape exists within the identified successful eligible stock
> measurement loop.

This does not mean that no external or exceptional event can ever clear the
state.

---

# 28. Counterfactual Healthy Progression

The C2 defect becomes especially clear by considering what should happen if the
first post-Recovery baseline sample is allowed to survive.

Assume:

```text
P = 0
R = historical 2
```

First successful post-Recovery sample:

```text
C = 1330
```

Correct measurement progression would be:

```text
P = 1330
R = 2 retained diagnostically
no Recovery
```

Then a later sample:

```text
C = 1360
```

produces:

```text
delta = 30

600 / 30 = 20

R = 20
```

No Recovery is required.

Alternatively, if the later sample is:

```text
C = 1630
```

then:

```text
delta = 300

600 / 300 = 2

R = 2
```

and Recovery is legitimately triggered again.

This is the behavior the corrective design should preserve:

```text
historical R
does not trigger

fresh qualifying R
does trigger
```

---

# 29. First Trigger vs. Persistent Recovery

The complete behavior must therefore be divided into two phases.

## Phase A — First qualifying event

Starting from clean state:

```text
P = 0
R = 0
```

the first successful sample establishes a baseline.

A later comparable sample can calculate a fresh `R`.

If that fresh `R` qualifies:

```text
first Recovery
```

occurs.

Possible causes include:

- genuine radio/AP behavior
- valid low effective received-beacon ratio
- C1a signed-control error
- C1b invalid measurement window
- other still-unresolved measurement conditions

The exact first field trigger remains:

**UNKNOWN**

---

## Phase B — Persistent loop

After the first Recovery:

```text
P = 0
R = qualifying historical value
```

C2 can repeatedly reuse that historical value.

This phase no longer requires a new anomalous radio measurement on every
cycle.

Therefore:

```text
first trigger
```

and:

```text
persistent recurrence
```

must not be treated as the same root cause.

---

# 30. Why Variable Onset Is Plausible

Observed Recovery onset has not followed one fixed multi-hour timer.

Approximate observed onset has varied across runs.

No fixed:

```text
2-hour
4-hour
6-hour
```

firmware timer has been identified for Beacon Recovery.

A more plausible model is event/state dependent:

```text
device operates normally
        |
        v
some later measurement epoch becomes qualifying
        |
        v
first Recovery
        |
        v
C2 latches recurrence
```

C1b provides one technically plausible route to such delayed onset.

For example, a temporary PM event can occur hours after boot, age the existing
baseline across skipped measurement opportunities, and then produce a
qualifying result.

This fits variable onset qualitatively.

It does not prove that C1b caused the observed first trigger in a particular
field run.

---

# 31. Runtime Observation — Repeating Recovery

On affected firmware 2.2.4 devices, runtime logs show sequences such as:

```text
Beacon skip error! Attempt recovery
```

followed by:

```text
Enter powersave state 1
```

and approximately five serviced seconds later:

```text
Enter powersave state 3 (skip N)
```

On affected devices this can recur approximately once per minute.

The recurrence aligns with the host-side minute-maintenance evaluation.

A separate internal WF200 one-minute Recovery timer is not required to explain
the observed cadence.

The host application already provides the recurring evaluation opportunity.

---

# 32. Runtime Observation — RSSI Does Not Prevent the Loop

Recovery has been observed under different normal desired-skip regimes.

One observed stock 2.2.4 case showed recurring Recovery with approximately:

```text
RSSI ≈ -59 dBm
```

and therefore:

```text
desired_beacon_skip = 20
```

A separate mDNS-only Patch-B test device has shown the stock Beacon Recovery
behavior around:

```text
RSSI ≈ -75 .. -77 dBm
```

with:

```text
desired_beacon_skip = 15
```

Therefore the persistent Recovery behavior is not restricted to one specific:

```text
RSSI
```

or:

```text
desired_beacon_skip
```

regime.

This does not establish that RF conditions are irrelevant to the first
qualifying event.

It establishes that poor RSSI or one particular desired-skip policy is not
required for C2 recurrence.

---

# 33. Relationship to Periodic mDNS

Periodic mDNS and Beacon Recovery are separate mechanisms.

An mDNS-only experimental patch suppresses the targeted recurring connected
`mdns_resp_restart()` call while leaving the Beacon Recovery mechanism intact.

Runtime testing showed that Beacon Recovery continued on the mDNS-only device.

Therefore:

> The targeted periodic mDNS restart is not required for the observed Beacon
> Recovery loop under the tested conditions.

This does not prove that network traffic can never influence WF200 statistics.

It establishes that the specific periodic mDNS restart is not a necessary
cause of the observed repeating Recovery behavior.

---

# 34. Relationship to Power Management

A qualifying `R` causes a real PM action.

The identified Recovery sequence is approximately:

```text
qualifying R
        |
        v
Beacon Recovery
        |
        v
H = 5
        |
        v
state 1
        |
        v
Active / Always-On WLAN
        |
        | ~5 serviced seconds
        v
restore PM
        |
        v
normally state 3
```

During the temporary state-1 interval, the WLAN-owned deeper-sleep restriction
remains active.

Therefore the energy relevance is primarily:

```text
temporary more-active WLAN PM
+
temporary restriction of deeper host sleep
```

No explicit transmit-power increase has been identified in this Recovery path.

---

# 35. Why `R` Should Not Simply Be Cleared

A superficially simple C2 correction would be:

```text
Recovery
        |
        v
P = 0
R = 0
```

This would prevent stale `R` from retriggering.

However, further analysis shows that `R` also has legitimate diagnostic
semantics.

The same cached field is exposed through:

```text
/stats real_beacon_skip
```

Clearing it during Recovery would erase the numeric value that caused the
Recovery.

For diagnostic investigation, retaining:

```text
last measured R
```

is useful.

Therefore the better semantic correction is:

```text
preserve R as diagnostic history

but

do not treat historical R as fresh Recovery evidence
```

This is a central design principle of Patch C-C.

---

# 36. Patch A — Recovery Isolation

Patch A bypasses the identified Beacon Recovery action.

It does not intentionally change:

- `desired_beacon_skip`
- command `0x66`
- WF200 statistics acquisition
- `beacon_rx_count`
- the `real_beacon_skip` calculation
- normal state-3 RSSI policy
- periodic mDNS
- protected WF200 firmware

Conceptually:

```text
WF200 statistics
        |
        v
calculate R
        |
        v
Recovery predicate
        |
        X
Recovery action bypassed
```

Patch A was useful as an isolation experiment.

It demonstrated that the targeted Recovery action could be suppressed while
normal RSSI-dependent desired-skip behavior continued.

However, Patch A also suppresses legitimate Recovery after a genuinely fresh
qualifying measurement.

Therefore Patch A is not the preferred corrective design.

---

# 37. Patch C-C — Corrective Design

Patch C-C is designed to preserve the intended Recovery mechanism while
correcting the identified host-side validity problems.

Its behavioral requirements are:

```text
preserve diagnostic R

preserve legitimate first Recovery

preserve legitimate later Recovery

reject signed-wrap false positives

invalidate unusable measurement baselines

allow baseline-only progression after Recovery

require fresh control evidence for later Recovery

preserve unrelated PM behavior
```

Patch C-C does not attempt to redesign the WF200 power-management system.

---

# 38. Patch C-C and C1a

For Recovery control, Patch C-C changes the relevant load semantics from:

```text
signed byte
```

to:

```text
unsigned byte
```

Conceptually:

```text
stock:
int8_t(R)

Patch C-C:
uint8_t(R)
```

The diagnostic `/stats` formatter remains unchanged.

Therefore values such as:

```text
R = 200
```

remain available diagnostically.

But they no longer become:

```text
-56
```

for Recovery control.

The corrected positive Recovery domain remains:

```text
R = 1
R = 2
```

For fresh positive deltas this corresponds to:

```text
delta = 201 .. 600
```

The erroneous:

```text
delta = 3
delta = 4
```

trigger cases are removed.

---

# 39. Patch C-C and C2

Patch C-C distinguishes baseline establishment from fresh Recovery evidence.

If:

```text
P == 0
```

a successful statistics sample establishes:

```text
P = C
```

but does not evaluate historical `R` as fresh control evidence on that pass.

Conceptually:

```text
P = 0
R = historical 2
        |
        v
successful sample
        |
        v
P = C
        |
        v
baseline-only exit
```

The diagnostic value remains:

```text
R = 2
```

but no Recovery occurs merely because that historical value still exists.

The next comparable sample can then calculate a fresh `R`.

---

# 40. Patch C-C and C1b

Patch C-C also invalidates `P` when identified events break logical measurement
continuity.

The reviewed design covers known classes including:

- H-gated measurement suppression
- missed relevant scheduler boundaries
- relevant PM state/policy commits
- PM completion
- association/reassociation
- disconnect-related state changes
- known clock setter/reset paths
- existing statistics-failure behavior

After invalidation:

```text
P = 0
```

The next successful sample becomes:

```text
baseline only
```

instead of immediately comparing the new counter against an old measurement
epoch.

This preserves the fixed-600 calculation only for measurement histories that
have survived the known validity checks.

---

# 41. Patch C-C Does Not Add a Physical Timestamp

Patch C-C does not add a persistent timestamp associated with every `P`.

Therefore it does not prove:

```text
every future C-P interval is physically exactly 60 seconds
```

The design instead implements logical epoch validity.

Known events that invalidate the assumptions of the measurement also
invalidate the baseline.

Remaining runtime uncertainties include:

- delayed callback execution
- exact physical PM transition duration
- external PM transaction duration
- unusual scheduler latency
- persistent policy churn
- radio-internal timing not visible to the host

These require hardware qualification.

---

# 42. Measurement-State Serialization

Static review identified a race that must be considered when `P` can be
invalidated asynchronously.

Conceptually:

```text
measurement path observes P != 0
        |
        v
asynchronous path invalidates P
        |
        v
measurement path continues using changed state
```

Patch C-C protects the relevant host-side measurement-decision section with a
short interrupt-mask critical section.

The added critical section begins after the WF200 statistics transaction.

It does not intentionally include blocking WF200 communication.

The purpose is:

```text
atomic host-side P / R decision state
```

not:

```text
serialize the entire radio transaction
```

Hardware testing must still verify interrupt latency and runtime behavior.

---

# 43. Static Qualification of Patch C-C

Patch C-C has completed a dedicated static pre-build qualification pass.

The review independently checked:

- existing patch-site preimages
- instruction boundaries
- branch and call targets
- helper-code control flow
- register and flag liveness
- C1a semantics
- C2 baseline-only semantics
- P invalidation paths
- measurement-state serialization
- PM transition interaction
- flash placement
- GBL growth requirements
- scenario-based falsification

No known static blocker was identified.

The decision was:

```text
PASS STATIC PRE-BUILD QUALIFICATION
```

This justifies creation of an experimental firmware build.

It does not establish:

- runtime correctness
- bootloader acceptance
- OTA acceptance
- hardware stability
- interrupt-latency acceptability
- battery-life improvement
- production readiness

Those remain hardware-test questions.

---

# 44. What `real_beacon_skip` Does Not Prove

A low or qualifying `real_beacon_skip` value does not by itself prove that:

- the configured WLAN skip changed
- the AP changed its beacon interval
- the TRV listens to every beacon
- RF transmit power increased
- packets were retransmitted
- the device changed access points
- poor RSSI caused the value
- a specific number of physical RF beacons was lost
- periodic mDNS caused the value
- the WF200 is faulty
- additional battery consumption occurred
- the measurement window was valid
- the value is fresh control evidence

`real_beacon_skip` is a host-side derived value.

Its interpretation depends on both:

```text
how it was calculated
```

and:

```text
whether the measurement/control evidence is still valid
```

---

# 45. Relationship to `beacon_rx_missed_count`

The WF200 statistics include a separate missed-beacon value.

The known `real_beacon_skip` calculation does not directly use it.

Instead:

```text
real_beacon_skip
        |
        v
delta(beacon_rx_count)
```

This means the host Recovery logic is not simply counting missed beacons and
comparing that count to a threshold.

The distinction matters because:

```text
received beacon count
```

and:

```text
missed beacon count
```

do not necessarily encode the same information under intentional power-save
skipping.

The detailed WF200 statistics semantics are documented separately in:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

---

# 46. Why the Host-Side Interpretation Is Problematic

The original analysis focused heavily on whether the WF200 returned statistics
that were semantically unsuitable for:

```text
600 / delta
```

That remains a relevant radio-level question.

However, the current evidence shows that the host implementation itself has
independent validity problems.

The host can:

```text
1. interpret the result with incorrect signed control semantics
2. compare counters across an invalid logical measurement epoch
3. reuse historical diagnostic state as fresh control evidence
```

Therefore a qualifying Recovery does not require a faulty WF200 counter.

The stronger current model is:

```text
WF200 provides cumulative statistics
        |
        v
host selects measurement baseline
        |
        v
host derives R
        |
        v
host interprets R
        |
        v
host decides Recovery
```

Defects exist in the host-side processing chain even if the underlying
cumulative counter is correct.

This does not prove that all WF200/AP behavior is irrelevant.

It means WF200 malfunction is no longer required to explain the identified
host-side defects.

---

# 47. Battery-Drain Relevance

The `real_beacon_skip` calculation itself does not consume the major energy of
interest.

The energy-relevant sequence begins when a qualifying value causes:

```text
Recovery
        |
        v
state 1
        |
        v
Active / Always-On WLAN
        |
        v
deeper host sleep restricted
        |
        | ~5 serviced seconds
        v
restore normal PM
```

One legitimate Recovery may be a reasonable reliability action.

The problem becomes more significant when C2 causes this sequence to recur
approximately once per minute without a new qualifying measurement.

Conceptually:

```text
~5 s more-active interval
every ~60 s
```

is a credible additional energy-consumption mechanism.

However, the following remain unmeasured:

```text
current during state 1
incremental current relative to state 3
energy per Recovery
daily Recovery energy
battery-runtime reduction
```

Therefore:

> The relationship between `real_beacon_skip`, C2, and recurring Recovery is
> established.

But:

> The quantitative contribution of that loop to total historical battery drain
> remains unknown.

This distinction is particularly important because battery drain has also been
observed on firmware 2.1.8.

The 2.2.4 mechanism cannot explain the complete historical problem.

---

# 48. Evidence Summary

| Finding | Status |
|---|---|
| `desired_beacon_skip` and `real_beacon_skip` are different values | **PROVEN** |
| `/stats` exposes the internal cached `R` field | **PROVEN** |
| The same field participates in Recovery control | **PROVEN** |
| Firmware 2.2.4 obtains relevant WF200 statistics through command `0x66` | **PROVEN** |
| `R` is derived from the change in `beacon_rx_count` | **PROVEN** |
| The calculation uses `600 / delta` | **PROVEN** |
| The division is unsigned | **PROVEN** |
| The result is narrowed to 8 bits | **PROVEN** |
| Stock Recovery later reads `R` as signed | **PROVEN** |
| Recovery accepts non-zero signed values `<= 2` | **PROVEN** |
| Fresh stock trigger domain includes delta `3`, `4`, and `201..600` | **PROVEN** |
| Delta `3` and `4` qualify because of signed-byte interpretation | **PROVEN** |
| C1a is a genuine control/measurement-validity defect | **STRONGLY SUPPORTED** |
| `600` is a fixed constant | **PROVEN** |
| `P` has no elapsed-time value used by the calculation | **PROVEN** |
| H-gated measurement opportunities can be skipped | **PROVEN** |
| Stock can preserve `P` across the identified H-gated path | **PROVEN** |
| A numerically increasing counter does not guarantee a valid measurement epoch | **PROVEN** |
| C1b is a host-side measurement-validity defect | **STRONGLY SUPPORTED** |
| Recovery clears `P` | **PROVEN** |
| Recovery preserves cached `R` | **PROVEN** |
| A post-Recovery baseline-only sample does not calculate fresh `R` | **PROVEN** |
| Stock nevertheless evaluates historical `R` on that path | **PROVEN** |
| Historical qualifying `R` can immediately trigger Recovery again | **PROVEN** |
| C2 forms a self-sustaining successful-sample loop | **PROVEN** |
| Every repeated Recovery requires a new RF anomaly | **FALSE** |
| Normal PM restoration automatically breaks C2 | **FALSE** |
| Periodic mDNS is required for the observed Recovery loop | **FALSE under tested conditions** |
| Poor RSSI is required for C2 recurrence | **FALSE** |
| Desired skip 20 is required for C2 recurrence | **FALSE** |
| Patch A changes the `real_beacon_skip` calculation | **FALSE** |
| Patch A preserves legitimate fresh Recovery | **FALSE** |
| Preserving `R` has coherent diagnostic value | **PROVEN** |
| Stock contains a separate freshness distinction between diagnostic `R` and control `R` | **NO SUCH MECHANISM IDENTIFIED** |
| Patch C-C corrects C1a in the reviewed control path | **PROVEN statically** |
| Patch C-C prevents historical `R` from controlling a baseline-only sample | **PROVEN statically** |
| Patch C-C invalidates identified unusable logical baselines | **PROVEN statically** |
| Patch C-C passed static pre-build qualification | **PROVEN** |
| Patch C-C has passed hardware qualification | **NO** |
| Exact first field trigger is known | **UNKNOWN** |
| Original rationale for constant `600` is known | **UNKNOWN** |
| Original intent of the signed control interpretation is known | **UNKNOWN** |
| Exact energy per Recovery is known | **UNKNOWN** |
| Total battery-life improvement from Patch C-C is known | **UNKNOWN** |

---

# 49. Remaining Unknowns

The host-side mechanism is now substantially characterized.

The main remaining questions are narrower than in the earlier investigation.

## First-trigger origin

What produced the first fresh qualifying `R` on each affected physical device?

Possible contributors include:

- genuine AP/WF200 behavior
- C1a
- C1b
- connection-state transitions
- PM transitions
- radio-internal fallback
- other still-unidentified timing conditions

The exact field cause remains unknown.

---

## Physical measurement timing

Patch C-C protects known logical measurement epochs but does not add a physical
timestamp to `P`.

The effect of unusually delayed scheduler servicing or long external
transactions still requires runtime validation.

---

## PM transaction completion

The static analysis does not establish a universal strict physical upper bound
for every external PM transaction.

The design includes PM-completion invalidation, but unusual runtime timing must
still be tested.

---

## WF200/AP semantics

The exact interaction among:

```text
beacon_rx_count
beacon_rx_missed_count
TBTT timing
DTIM
intentional beacon skipping
AP behavior
WF200 internal fallback
```

remains useful for understanding the original engineering intent and genuine
Recovery conditions.

---

## Energy impact

The current investigation has not yet measured:

```text
energy per Recovery
average additional current
daily energy contribution
battery-runtime reduction
```

These require hardware measurements or sufficiently long controlled battery
comparison.

---

# 50. Current Conclusion

The firmware 2.2.4 `real_beacon_skip` mechanism is now substantially
characterized.

The host-side path is approximately:

```text
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
C and P
        |
        v
delta = C - P
        |
        v
600 / delta
        |
        v
uint8_t R
        |
        v
Recovery predicate
```

Three separate validity problems have been identified.

## C1a

```text
unsigned calculation
        |
        v
8-bit storage
        |
        v
signed control load
```

This expands the fresh Recovery trigger domain to:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

instead of the ordinary positive quotient domain:

```text
delta = 201 .. 600
```

---

## C1b

```text
P established
        |
        v
measurement continuity interrupted
        |
        v
P retained
        |
        v
later C compared with old P
        |
        v
fixed 600 still used
```

This can create a qualifying derived value even when the cumulative counter
itself is correct.

---

## C2

```text
fresh qualifying R
        |
        v
Recovery
        |
        v
P = 0
R retained
        |
        v
baseline-only sample
        |
        v
historical R evaluated
        |
        v
Recovery
        |
        v
P = 0
        |
        v
repeat
```

C2 explains why the observed Recovery can become self-sustaining after one
qualifying event.

No new RF anomaly is required for each repeated Recovery.

The exact first qualifying event on the physical devices remains unknown.

The most important semantic conclusion is:

```text
R can remain useful as diagnostic history

but

R is only valid as Recovery-control evidence
when derived from a fresh, valid measurement
```

Patch A demonstrated that the Recovery action can be isolated, but it removes
legitimate Recovery as well.

Patch C-C therefore takes a different approach.

It preserves:

```text
diagnostic R
legitimate fresh Recovery
normal WLAN PM behavior
```

while correcting:

```text
C1a
control interpretation

C1b
measurement-epoch validity

C2
control-evidence freshness
```

Patch C-C has passed static pre-build qualification.

It has not yet passed hardware qualification.

Finally, `real_beacon_skip` and the 2.2.4 Recovery loop should not be described
as the sole historical Shelly TRV Gen1 battery-drain root cause.

Battery drain was also observed on earlier firmware.

The 2.2.4 mechanism is best understood as a separately identified,
firmware-specific additional energy-consumption mechanism whose quantitative
battery impact still requires controlled hardware testing.

---

# Related Documents

Detailed WF200 counter analysis:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

Firmware chronology:

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

# Research Methodology

The analysis was performed using static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

The investigation includes:

- native ARM Thumb control-flow analysis
- cross-version firmware comparison
- WF200 statistics analysis
- host-side measurement-state reconstruction
- power-management state analysis
- runtime debug-log observation
- `/stats` observation
- passive network capture
- isolated experimental patches
- scenario-based falsification
- independent static qualification of the Patch C-C design

Important conclusions are checked against native instructions and control flow
rather than relying only on decompiler output.

Public WF200/fullMAC information is used where necessary to interpret
host-visible statistics and WLAN behavior.

The protected WF200 implementation is not reproduced.

The project deliberately distinguishes:

```text
PROVEN
STRONGLY SUPPORTED
INFERENCE
UNKNOWN
```

and separately distinguishes:

```text
host implementation
runtime observation
radio-level interpretation
developer intent
battery hypothesis
```

No original or modified Shelly firmware image, complete proprietary function,
or large raw disassembly is reproduced in this document.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the investigated firmware versions.

No conclusion about the intentions of the original developers is made unless
independently supported by technical evidence.