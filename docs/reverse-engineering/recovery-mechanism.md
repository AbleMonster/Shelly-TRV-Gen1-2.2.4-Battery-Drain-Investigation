# Beacon Recovery Mechanism Analysis

## Scope

This document describes the Beacon Recovery mechanism identified in Shelly TRV
Gen1 firmware 2.2.4.

The purpose of this analysis is to determine:

- what triggers Beacon Recovery
- how the trigger is derived
- what happens when Recovery is entered
- which WLAN power state is requested
- how host-microcontroller sleep is affected
- how long the temporary Recovery state normally lasts
- how normal power-saving operation is restored
- why Recovery can become self-sustaining
- which parts of the mechanism are legitimate reliability behavior
- which host-side validity defects have been identified
- which experimental patches isolate the mechanism
- how the current Patch C-C design differs from the earlier bypass patch
- which parts of the mechanism may contribute to battery consumption
- what remains unresolved

This document focuses on the Recovery control flow itself.

The detailed `real_beacon_skip` arithmetic and measurement model are documented
separately in:

[`real-beacon-skip.md`](real-beacon-skip.md)

and:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

No firmware images, complete proprietary functions, or large raw disassemblies
are reproduced here.

---

# 1. Evidence Classification

This project uses the following evidence levels.

## PROVEN

Directly established from native firmware instructions, deterministic binary
comparison, validated control flow, or sufficiently direct runtime evidence.

## STRONGLY SUPPORTED

Multiple independent findings support the conclusion, but some implementation
detail, runtime dependency, or original developer intent remains unresolved.

## INFERENCE

A technically plausible interpretation consistent with the available evidence,
but not directly established.

## UNKNOWN

The available evidence is insufficient to determine the behavior, runtime
frequency, quantitative effect, or original developer intent.

Runtime observations are described explicitly where relevant rather than
introducing a separate evidence taxonomy.

---

# 2. Summary

Firmware 2.2.4 contains a host-side Beacon Recovery mechanism associated with
the calculated:

```text
real_beacon_skip
```

value.

When the Recovery predicate is satisfied, the runtime log reports:

```text
Beacon skip error! Attempt recovery
```

The Recovery action is real WLAN power-management behavior.

The normal identified sequence is approximately:

```text
qualifying Recovery evidence
        |
        v
Beacon skip error
        |
        v
H = 5
        |
        v
request PM state 1
        |
        v
wake / configure WF200 Active / Always-On
        |
        v
deeper host sleep restricted
        |
        | approximately 5 serviced seconds
        v
restore application PM state
        |
        v
normally Fast Power Save / state 3
with current desired_beacon_skip
```

No explicit WLAN transmit-power increase, scan, DHCP sequence, ordinary
disconnect/reconnect, or complete WLAN-driver reinitialization has been
identified in the normal Recovery path.

The mechanism therefore appears to have a coherent reliability purpose:

```text
temporarily leave beacon-based power saving
        |
        v
return WF200 to Active operation
        |
        v
reapply normal power-saving configuration
```

The existence of that legitimate action is important.

The defect is not simply:

```text
Recovery exists
```

Instead, three host-side validity problems have been identified around the
evidence used to request Recovery:

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

C2 is particularly important.

After a qualifying Recovery, stock firmware clears the previous beacon-counter
baseline `P` but retains the qualifying cached `real_beacon_skip` value `R`.

The next successful eligible statistics sample can establish a new baseline
without calculating a fresh `R`.

Stock firmware nevertheless evaluates the historical `R`.

If that historical value still qualifies, Recovery occurs again and clears the
new baseline.

The resulting state can therefore repeat indefinitely under successful
eligible statistics acquisitions:

```text
P = 0
R = qualifying historical value
        |
        v
successful sample
        |
        v
P = current counter
        |
        v
no fresh R calculated
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
        +------------------+
                           |
                           v
                         repeat
```

This self-sustaining C2 loop is:

**PROVEN**

The exact cause of the first qualifying event on affected physical devices
remains:

**UNKNOWN**

This distinction is central to the current investigation.

---

# 3. Recovery Trigger

The Recovery decision uses the internally cached:

```text
real_beacon_skip
```

value.

For clarity, this document uses:

```text
C = current received-beacon counter
P = previous received-beacon baseline
R = cached real_beacon_skip
H = shared PM override / Recovery countdown
```

The relevant stock Recovery predicate is approximately:

```text
signed_R != 0
&&
signed_R <= 2
```

The stored byte is read as a signed 8-bit value for this control decision.

When the predicate is accepted, firmware enters the Recovery path and logs:

```text
Beacon skip error! Attempt recovery
```

### Classification

Recovery predicate:

**PROVEN**

Signed interpretation:

**PROVEN**

---

# 4. Source of the Trigger Data

Firmware 2.2.4 obtains the relevant WF200 statistics through command:

```text
0x66
```

The statistics include fields corresponding to:

```text
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

The known `real_beacon_skip` calculation uses the cumulative received-beacon
counter.

Conceptually:

```text
WF200 command 0x66
        |
        v
current beacon_rx_count C
        |
        v
compare with previous baseline P
        |
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
Recovery predicate
```

The separate missed-beacon statistic is not the direct known trigger of this
Recovery path.

The host therefore does not simply perform:

```text
if missed_beacons > threshold:
    recover()
```

It derives its own effective beacon-skip value from received-beacon statistics.

---

# 5. Three Separate Validity Problems

The current analysis separates three defects.

## C1a — Signed control-value validity

The quotient:

```text
600 / delta
```

is unsigned.

The result is narrowed to one byte.

Recovery control later reads that byte as signed.

This creates additional trigger cases through signed wraparound.

---

## C1b — Measurement-window validity

The calculation always uses:

```text
600
```

but the baseline `P` has no elapsed-time metadata used by the calculation.

Identified PM and scheduler conditions can preserve `P` while expected
measurement opportunities are skipped.

A later counter can therefore be compared with an old baseline using the same
fixed numerator.

---

## C2 — Post-Recovery freshness

Recovery clears:

```text
P
```

but preserves:

```text
R
```

The next baseline-only sample does not calculate a fresh `R`, yet stock
firmware still evaluates the historical value.

This can make Recovery self-sustaining.

The detailed arithmetic and proof are documented in:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

# 6. C1a — Signed Recovery Predicate

For a fresh positive measurement, stock firmware approximately performs:

```text
delta = C - P

ratio = 600 / delta

R = uint8_t(ratio)

signed_R = int8_t(R)

if signed_R != 0 and signed_R <= 2:
    Recovery
```

This produces the exact fresh stock trigger domain:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

The unexpected:

```text
delta = 3
delta = 4
```

cases result from:

```text
600 / 3 = 200
uint8_t  = 200
int8_t   = -56
```

and:

```text
600 / 4 = 150
uint8_t  = 150
int8_t   = -106
```

Both negative values satisfy:

```text
signed_R <= 2
```

while remaining non-zero.

Therefore the Recovery mechanism can accept values that do not represent an
ordinary positive calculated skip of `1` or `2`.

### Classification

Exact stock trigger domain:

**PROVEN**

Signed-wrap cause of delta-3 and delta-4 cases:

**PROVEN**

C1a as a genuine control-validity defect:

**STRONGLY SUPPORTED**

Original developer intent:

**UNKNOWN**

---

# 7. C1b — Measurement-Window Validity

Even with correct unsigned interpretation, the Recovery input can still be
invalid.

The host calculates:

```text
600 / (C - P)
```

but does not associate an elapsed-time value with `P`.

This assumes that:

```text
P -> C
```

represents the intended nominal measurement window.

That assumption is not always maintained.

Identified firmware paths can suppress normal measurement opportunities while
preserving the old baseline.

A later successful acquisition can then perform:

```text
old P
+
new C
+
fixed 600
```

across a different logical measurement epoch.

The cumulative WF200 counter can be correct while the host-derived ratio is
invalid.

### Classification

Fixed numerator:

**PROVEN**

No elapsed-time value used with `P`:

**PROVEN**

Identified baseline preservation across invalidating conditions:

**PROVEN**

C1b as a measurement-validity defect:

**STRONGLY SUPPORTED**

C1b as the actual cause of the first observed field Recovery:

**UNKNOWN**

---

# 8. Recovery Sequence

Once the Recovery predicate is accepted, the normal identified sequence is:

```text
qualifying Recovery evidence
        |
        v
log Recovery
        |
        v
H = 5
        |
        v
request PM state 1
        |
        v
wake WLAN device
        |
        v
request Active / Always-On WLAN mode
        |
        v
restrict deeper host sleep
        |
        | approximately 5 serviced seconds
        v
restore saved / deferred application PM state
        |
        v
if normal connected PM is restored:
Fast Power Save + current desired_beacon_skip
```

The Recovery action is therefore not merely a log message or internal state
flag.

It changes WLAN and host power-management behavior.

### Classification

Normal Recovery sequence:

**PROVEN**

---

# 9. Shared Recovery Countdown `H`

When Beacon Recovery begins, firmware sets the shared countdown:

```text
H = 5
```

The same countdown field participates in other temporary PM override behavior,
where other paths can use different values such as:

```text
H = 180
```

Therefore `H` should not be interpreted as a dedicated:

```text
Beacon Recovery flag
```

It is a shared temporary PM/recovery countdown.

During the Beacon Recovery case:

```text
H = 5
```

is serviced through the firmware's seconds-related maintenance path.

Under normal operation this results in approximately:

```text
5 seconds
```

of temporary Recovery state.

The duration should not be described as an electrically guaranteed exact
five-second pulse.

Scheduler delays or other state changes can alter the physical elapsed time.

### Classification

Recovery writes `H = 5`:

**PROVEN**

Shared nature of `H`:

**PROVEN**

Approximately five serviced seconds:

**PROVEN**

---

# 10. WLAN State During Recovery

During normal Recovery, the firmware requests the WLAN power mode corresponding
to:

```text
Active / Always-On
```

This is different from normal connected beacon-based power saving.

Conceptually:

```text
normal connected operation

Fast Power Save
desired skip 20 / 15 / 10

        |
        | Recovery
        v

Active / Always-On

        |
        | approximately 5 seconds
        v

restore connected power saving
current desired beacon skip
```

The Recovery action therefore genuinely changes WF200 power management.

### Classification

Active / Always-On request:

**PROVEN**

---

# 11. Host Microcontroller Sleep Behavior

Recovery also affects host-microcontroller sleep availability.

The WLAN wake path acquires or retains a WLAN-related sleep-blocking resource.

During normal connected power saving, deeper host energy modes can normally be
available.

During the Recovery interval, the relevant effect is approximately:

```text
Normal connected operation

EM1  available
EM2  available
EM3  available
```

versus:

```text
Recovery interval

EM1  available
EM2  blocked
EM3  blocked
```

This does not mean that the CPU necessarily executes instructions continuously
for the entire Recovery interval.

The processor can still idle in EM1.

The important energy difference is that deeper EM2 and EM3 sleep are
temporarily unavailable.

### Classification

Recovery-related deeper-sleep restriction:

**PROVEN**

EM1 remaining available:

**PROVEN**

---

# 12. Restoration of Power Saving

When the Recovery countdown expires, firmware restores the application PM
state.

Recovery does not permanently force the device into one fixed state.

Conceptually:

```text
Recovery entry
        |
        v
temporary state 1
        |
        v
Active / Always-On
        |
        | H countdown
        v
restore application PM state
```

If the restored state is normal connected beacon power saving, firmware uses
the current:

```text
desired_beacon_skip
```

value.

Conceptually:

```text
restore normal connected PM
        |
        v
read current desired_beacon_skip
        |
        v
Fast Power Save
        |
        v
skip 20 / 15 / 10
```

The firmware does not need to restore a separate saved copy of the skip value
captured when Recovery began.

### Classification

PM restoration:

**PROVEN**

Reuse of current desired skip:

**PROVEN**

---

# 13. Recovery Is Potentially Legitimate

The existence of the Recovery mechanism should not itself be treated as a bug.

A temporary transition from:

```text
Fast Power Save
```

to:

```text
Active / Always-On
```

followed by reapplication of normal PM configuration is technically coherent
as a WLAN reliability/reconfiguration strategy.

A genuinely fresh measurement may indicate that the effective beacon behavior
is inconsistent with the expected power-saving operation.

In such a case:

```text
temporarily wake/reconfigure WF200
```

can be a legitimate corrective action.

No independent source comment or explicit developer statement proving the
original intended policy has been identified.

Therefore:

```text
Recovery has a coherent reliability purpose
```

is:

**STRONGLY SUPPORTED**

while the exact original developer intent remains:

**UNKNOWN**

This is why the preferred corrective approach no longer simply removes
Recovery.

---

# 14. C2 — Post-Recovery Freshness Failure

The most important newly established Recovery-control defect is C2.

Consider a fresh qualifying measurement:

```text
P != 0
C > P
```

which produces:

```text
R = 2
```

Recovery occurs.

The Recovery path then clears:

```text
P = 0
```

but retains:

```text
R = 2
```

The resulting state is:

```text
P = 0
R = 2
```

The next successful eligible statistics acquisition obtains a new current
counter:

```text
C = new value
```

Because `P` is zero, no fresh ratio can be calculated.

The firmware establishes:

```text
P = C
```

This sample is therefore only a baseline sample.

Nevertheless, stock firmware then evaluates:

```text
R = 2
```

even though that value was not derived from the newly established baseline.

Recovery occurs again.

The Recovery path clears:

```text
P = 0
```

again.

The system has returned to the same logical state.

---

# 15. Proof of the Self-Sustaining Recovery Loop

Starting from:

```text
P = 0
R = qualifying
```

the stock successful-sample path behaves as follows:

```text
P = 0
R = qualifying historical value
        |
        v
successful command 0x66
        |
        v
fresh current C
        |
        v
P == 0
        |
        v
skip fresh ratio calculation
        |
        v
P = C
        |
        v
historical R still qualifying
        |
        v
Recovery
        |
        v
P = 0
R retained
        |
        +-----------------------+
                                |
                                v
                              repeat
```

A new RF anomaly is not required for every Recovery.

A new qualifying `C-P` measurement is not required for every Recovery.

The cached value itself keeps the control path active.

### Classification

C2 self-sustaining loop:

**PROVEN**

---

# 16. Why Successful PM Restoration Does Not Break C2

The WF200 can genuinely be restored to normal power saving after each
Recovery.

For example:

```text
Recovery
        |
        v
state 1
        |
        | approximately 5 s
        v
state 3
skip 15
```

can complete successfully.

That does not clear the historical qualifying `R`.

Therefore both of the following can simultaneously be true:

```text
WF200 Recovery succeeded
```

and:

```text
host Recovery logic remains latched
```

The approximately once-per-minute recurrence is therefore not evidence that
the radio necessarily failed to recover every time.

It can be generated by the host's stale-control-evidence logic.

---

# 17. No Normal Successful-Sample Escape from C2

Within the identified stock successful measurement path, no ordinary escape
exists once the state is:

```text
P = 0
R = qualifying
```

To replace `R` with a fresh value, firmware needs:

```text
P != 0
```

at the beginning of a later comparable measurement.

But the first successful baseline-only sample evaluates the historical `R`,
enters Recovery, and clears `P` again.

Therefore the sequence never naturally reaches:

```text
baseline sample
        |
        v
second comparable sample
        |
        v
fresh R
```

while the cached qualifying value remains actionable.

### Classification

No normal escape in the identified successful loop:

**PROVEN**

---

# 18. Identified C2 Loop Breakers

C2 does not imply that the device can never leave the state under any possible
event.

Identified state-resetting conditions include:

```text
startup / reset
```

and the periodic statistics failure path, which clears the relevant cached
measurement state.

Therefore the precise statement is:

> No normal escape exists within the identified successful eligible stock
> measurement loop.

This distinction avoids overstating the result.

---

# 19. First Recovery vs. Repeated Recovery

The first Recovery and the repeated Recovery loop must be analyzed separately.

## First Recovery

Starting from clean measurement state:

```text
P = 0
R = 0
```

the first successful acquisition establishes a baseline.

A later comparable acquisition can calculate a fresh `R`.

Possible reasons for a qualifying fresh value include:

- genuine AP/WF200 behavior
- valid low effective beacon reception
- C1a signed interpretation
- C1b baseline-age / measurement-window invalidity
- connection-state effects
- PM-state effects
- radio-internal behavior not visible to the host

The exact cause on the observed physical devices remains:

**UNKNOWN**

---

## Repeated Recovery

Once one qualifying Recovery has occurred:

```text
P = 0
R = qualifying historical value
```

C2 is sufficient to explain subsequent successful approximately once-per-minute
Recovery events.

This phase does not require repeated fresh RF anomalies.

### Classification

First field trigger:

**UNKNOWN**

C2 recurrence after a qualifying trigger:

**PROVEN**

---

# 20. Why Recovery Recurs Approximately Once Per Minute

The Beacon Recovery evaluation is serviced through the host-side
minute-maintenance path.

Therefore the approximately once-per-minute runtime cadence does not require a
separate one-minute timer inside the WF200.

Conceptually:

```text
host minute maintenance
        |
        v
eligible Beacon Recovery evaluation
        |
        v
command 0x66
        |
        v
measurement / cached state
        |
        v
Recovery predicate
        |
        v
possible Recovery
```

Under C2:

```text
historical qualifying R
```

is sufficient to make each eligible successful evaluation retrigger Recovery.

The WF200 provides statistics.

The host application decides whether to enter Recovery.

---

# 21. Counterfactual Healthy Recovery Progression

The intended corrective behavior can be illustrated with a simple
counterfactual.

Assume a Recovery has just occurred:

```text
P = 0
R = historical 2
```

The next successful sample obtains:

```text
C = 1330
```

A healthy progression is:

```text
P = 1330
R = 2 retained diagnostically
no Recovery
```

The next comparable sample obtains:

```text
C = 1360
```

Then:

```text
delta = 30
600 / 30 = 20
```

so:

```text
R = 20
```

and no Recovery occurs.

But if the next comparable sample instead obtains:

```text
C = 1630
```

then:

```text
delta = 300
600 / 300 = 2
```

and a new Recovery is legitimate.

This demonstrates the required distinction:

```text
historical qualifying R
        !=
fresh qualifying R
```

---

# 22. Diagnostic History vs. Recovery Evidence

The same cached `R` field is used for:

```text
/stats real_beacon_skip
```

and:

```text
Recovery control
```

This creates two different semantic roles.

For diagnostics, retaining:

```text
last measured R
```

is useful.

For control, the important question is:

```text
Was this R produced by a fresh,
valid measurement in the current epoch?
```

The stock firmware does not encode that distinction independently.

This leads to the central semantic conclusion:

> `R` can remain valid as diagnostic history while no longer being valid as
> fresh Recovery-control evidence.

This is why simply clearing `R` after every Recovery is not the preferred
solution.

---

# 23. Relationship to `desired_beacon_skip`

Recovery is triggered by:

```text
real_beacon_skip
```

not directly by:

```text
desired_beacon_skip
```

A device can therefore operate normally with:

```text
desired_beacon_skip = 20
```

or:

```text
desired_beacon_skip = 15
```

and still enter Recovery.

Recovery temporarily leaves the normal requested beacon-based PM
configuration.

After the Recovery window, the current desired skip can be applied again.

For example:

```text
state 3
skip 15
        |
        v
state 1
Active / Always-On
        |
        | approximately 5 s
        v
state 3
skip 15
```

without `desired_beacon_skip` itself having changed.

---

# 24. Runtime Evidence Across RSSI Regimes

Runtime evidence shows that the recurring Recovery is not restricted to one
RSSI or desired-skip regime.

A stock 2.2.4 device has shown recurring Recovery at good reported RSSI,
including approximately:

```text
-59 dBm
```

where the normal RSSI policy selects:

```text
desired_beacon_skip = 20
```

The mDNS-only Patch-B `.77` test device has separately shown persistent stock
Beacon Recovery around:

```text
RSSI ≈ -75 .. -77 dBm
```

with:

```text
desired_beacon_skip = 15
```

Therefore:

```text
poor RSSI
```

is not required for the Recovery loop.

Likewise:

```text
desired_beacon_skip = 20
```

is not required.

This does not prove that RF conditions are irrelevant to the first qualifying
measurement.

It establishes that C2 recurrence can persist under multiple normal
RSSI-dependent desired-skip regimes.

---

# 25. Relationship to Periodic mDNS

Firmware comparison identified a separate recurring mechanism:

```text
periodic connected-maintenance mDNS restart
```

The mDNS behavior and Beacon Recovery are distinct host-side mechanisms.

One hypothesis considered during the investigation was:

```text
periodic mDNS
        |
        v
WLAN timing disturbance
        |
        v
qualifying beacon measurement
        |
        v
Recovery
```

This was tested experimentally.

---

# 26. Patch B — mDNS Isolation

Patch B suppresses the targeted periodic connected-maintenance mDNS restart.

It does not intentionally modify:

- WF200 command `0x66`
- beacon statistics
- `beacon_rx_count`
- `real_beacon_skip`
- the Recovery predicate
- the Recovery action
- normal RSSI-dependent desired skip

Passive packet capture confirmed suppression of the targeted recurring mDNS
traffic during the monitored test window.

Beacon Recovery nevertheless continued on the Patch-B test device.

Therefore:

> The targeted periodic mDNS restart is not required for the observed Beacon
> Recovery loop under the tested conditions.

This does not prove that arbitrary network activity can never affect WF200
statistics.

It establishes that the targeted periodic mDNS restart is not a necessary
cause of the observed recurring Recovery.

---

# 27. Patch A — Recovery Isolation Experiment

Patch A was designed to bypass the identified Beacon Recovery action.

The stock conditional branch associated with the Recovery decision is located
at:

```text
0x1E1C8
```

Stock instruction:

```text
BGT 0x1E22E
```

with bytes:

```text
31 DC
```

Patch A changes it to:

```text
B 0x1E22E
```

with bytes:

```text
31 E0
```

Only one program byte changes:

```text
0x1E1C9

DC -> E0
```

The corresponding verified GBL byte is:

```text
0x0002471D

DC -> E0
```

Patch A does not intentionally modify:

- RSSI thresholds
- `desired_beacon_skip`
- command `0x66`
- beacon statistics
- `beacon_rx_count`
- the `real_beacon_skip` calculation
- periodic mDNS behavior
- the protected WF200 image
- WLAN transmit power

Conceptually:

```text
statistics
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

Patch A should therefore be described as:

> a Beacon Recovery isolation patch

rather than:

> a correction of the underlying measurement/control defects.

---

# 28. Runtime Validation of Patch A

Patch A has been tested on physical TRVs running firmware 2.2.4.

During monitored operation, the targeted recurring sequence:

```text
Beacon skip error! Attempt recovery
        |
        v
state 1
        |
        | approximately 5 s
        v
state 3
```

was suppressed.

Normal RSSI-dependent desired-beacon-skip behavior continued.

The device could still use:

```text
20
15
10
```

according to RSSI.

This experimentally isolates the Recovery action from the normal desired-skip
selection mechanism.

However, Patch A also prevents Recovery after a genuinely fresh qualifying
measurement.

It therefore removes potentially legitimate reliability behavior.

For that reason, Patch A is no longer the preferred corrective design.

---

# 29. Combined Patch A+B

Patch A and Patch B were also tested together.

The combined experimental configuration suppresses:

```text
targeted periodic mDNS restart
```

and:

```text
targeted Beacon Recovery action
```

while leaving normal connected firmware operation intact.

During monitored operation:

```text
Beacon skip error! Attempt recovery
```

was not observed.

The targeted recurring state-1 transition was absent.

Normal RSSI-dependent desired-skip operation remained visible.

Cloud connectivity remained operational during the tested interval.

Separate packet capture showed no targeted periodic mDNS sequence during the
monitored mDNS test window.

This demonstrates that the two mechanisms can be experimentally isolated
together.

It does not establish:

- indefinite stability
- long-term battery improvement
- elimination of every possible state-1 entry
- elimination of every possible mDNS transmission
- production suitability

The combined A+B patch remains an experimental isolation configuration.

---

# 30. Why Patch A Is Not the Final Fix

The earlier investigation initially treated repeated Recovery primarily as
something to suppress.

The newer control-flow analysis changes that interpretation.

The Recovery action itself can be legitimate.

The defects are in:

```text
what evidence becomes actionable
```

and:

```text
whether that evidence is still fresh and valid
```

Patch A removes both:

```text
invalid Recovery
```

and:

```text
legitimate Recovery
```

Therefore it is too broad as a final corrective strategy.

The preferred design should instead preserve:

```text
fresh valid Recovery
```

while preventing:

```text
invalid or stale Recovery
```

That is the purpose of Patch C-C.

---

# 31. Patch C Research Family

Patch C is the research family intended to correct Beacon Recovery semantics
rather than bypass Recovery entirely.

Its behavioral requirements are:

1. preserve the diagnostic `real_beacon_skip` value
2. preserve legitimate first Recovery
3. preserve legitimate later Recovery
4. correct signed control interpretation
5. prevent invalid measurement epochs from becoming Recovery evidence
6. allow post-Recovery baseline progression
7. prevent historical `R` from acting as fresh control evidence
8. preserve unrelated WLAN and PM behavior

The current preferred implementation candidate is:

```text
Patch C-C
```

---

# 32. Patch C-C and C1a

Patch C-C changes the Recovery-control interpretation of `R` from signed to
unsigned.

Conceptually:

```text
stock control:
int8_t(R)

Patch C-C control:
uint8_t(R)
```

The diagnostic `/stats` representation is not intentionally changed.

Therefore:

```text
R = 200
```

can remain visible diagnostically without becoming:

```text
-56
```

for Recovery control.

Under the corrected control interpretation:

```text
R = 1
R = 2
```

remain qualifying.

For fresh positive deltas this corresponds to:

```text
delta = 201 .. 600
```

The stock signed-wrap trigger cases:

```text
delta = 3
delta = 4
```

are rejected.

---

# 33. Patch C-C and C2

Patch C-C distinguishes:

```text
baseline establishment
```

from:

```text
fresh Recovery evidence
```

After Recovery:

```text
P = 0
R = historical qualifying value
```

The next successful sample can establish:

```text
P = C
```

while preserving:

```text
R
```

for diagnostics.

But that baseline-only sample does not evaluate historical `R` as fresh
Recovery evidence.

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
        |
        v
no Recovery from historical R
```

A later comparable sample can then calculate a fresh `R`.

If that fresh value qualifies, Recovery remains available.

---

# 34. Patch C-C and C1b

Patch C-C also invalidates the measurement baseline when identified events
break logical measurement continuity.

The reviewed design covers known classes including:

- H-gated measurement suppression
- missed relevant scheduler boundaries
- relevant PM state/policy commits
- PM completion
- association/reassociation
- disconnect-related transitions
- known clock setter/reset paths
- existing statistics-failure behavior

The conceptual rule is:

```text
measurement epoch invalidated
        |
        v
P = 0
        |
        v
next successful sample = baseline only
```

This prevents an old cumulative baseline from being interpreted through the
fixed-600 model after known invalidating events.

---

# 35. Patch C-C Measurement-State Serialization

Adding asynchronous baseline invalidation creates a possible race if the
measurement path and an invalidator can access `P` concurrently.

For example:

```text
measurement path sees P != 0
        |
        v
asynchronous path clears P
        |
        v
measurement path continues
```

Patch C-C therefore protects the relevant host-side measurement decision with
a short critical section.

The critical section begins after the WF200 statistics acquisition.

It does not intentionally hold the interrupt mask across the blocking radio
transaction.

The purpose is limited to:

```text
serialize host-side P/R decision state
```

Hardware qualification must still verify:

- interrupt latency
- runtime responsiveness
- unexpected concurrency
- PM timing behavior

---

# 36. Patch C-C Static Pre-Build Qualification

Patch C-C has completed a dedicated static pre-build qualification pass.

The review checked:

- all existing patch-site preimages
- instruction boundaries
- branch targets
- helper-code control flow
- register and APSR dependencies
- C1a behavior
- C2 baseline-only behavior
- baseline invalidation
- PM interaction
- critical-section exits
- flash placement
- program-tag growth requirements
- representative control-flow scenarios

No known static blocker was identified.

The qualification decision was:

```text
PASS STATIC PRE-BUILD QUALIFICATION
```

This means an experimental build for controlled hardware testing is justified.

It does not establish:

- successful boot
- bootloader acceptance
- OTA acceptance
- runtime correctness
- acceptable interrupt latency
- long-term stability
- battery improvement
- production readiness

No Patch C-C hardware result should be claimed until those tests are actually
performed.

---

# 37. No Explicit TX-Power Increase Identified

The normal Recovery path was examined for an explicit WLAN transmit-power
change.

No application-level TX-power-setting operation was identified as part of the
normal Beacon Recovery sequence.

The identified action is a power-management-mode transition, not an explicit
RF transmit-power command.

Therefore the supported statement is:

> No explicit application-level WLAN transmit-power increase was identified in
> the normal Beacon Recovery path.

This does not prove that the protected WF200 implementation can never alter
lower-level RF behavior internally.

That remains:

**UNKNOWN**

---

# 38. No Normal Scan, Reconnect, or DHCP Path Identified

No direct normal Beacon Recovery path has been identified that performs:

- WLAN scanning
- access-point selection
- ordinary disconnect
- ordinary reconnect
- reassociation
- DHCP negotiation
- complete WLAN-driver initialization
- full WLAN subsystem reset

The normal Recovery mechanism is substantially narrower:

```text
wake
 |
 v
Active / Always-On
 |
 v
temporary deeper-sleep restriction
 |
 | approximately 5 s
 v
restore application PM state
```

A scan, reconnect, or DHCP event occurring near a Recovery event must therefore
not automatically be attributed to the normal Beacon Recovery mechanism.

---

# 39. Exceptional Driver-Lock Reset Path

A separate exceptional path exists in the WLAN/PM logic.

If a relevant WLAN driver-lock operation fails, firmware can initialize a
different countdown:

```text
3
```

When that countdown expires, firmware can request a full MCU system reset.

This mechanism is separate from normal Beacon Recovery.

Normal Beacon Recovery:

```text
qualifying Recovery evidence
        |
        v
H = 5
        |
        v
temporary Active / Always-On
        |
        v
restore PM
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

The existence of the exceptional reset path is:

**PROVEN**

Its relevance to the ordinary recurring Beacon Recovery observed on the test
devices is:

**UNKNOWN**

The two mechanisms must not be conflated.

---

# 40. Relationship to D3 Power-Save Errors

Firmware 2.2.4 contains separate D3 power-save error reporting.

Identified reasons include conditions corresponding to:

```text
0
AP did not provide buffered unicast after PS-Poll

1
AP did not provide buffered unicast after U-APSD trigger

2
AP indicated buffered unicast but no frame was delivered
across consecutive beacons

3
unstable AP beacon timing / beacon-window adjustment
```

These events demonstrate that the WLAN stack contains other power-save
reliability mechanisms.

However, no direct host-side:

```text
D3 event
        |
        v
Beacon Recovery
```

control or data edge has been established.

Radio-internal effects could still influence the statistics later observed by
the host.

That remains:

**INFERENCE**

Direct D3 causality for Beacon Recovery is:

**UNKNOWN**

---

# 41. Energy-Consumption Relevance

Normal Beacon Recovery contains several energy-relevant state changes.

During each Recovery:

- the WLAN device is explicitly woken/configured
- Active / Always-On WLAN mode is requested
- deeper host EM2 and EM3 sleep are restricted
- additional control/bus activity occurs
- the temporary state normally lasts approximately five seconds

These operations are present in the firmware.

If Recovery occurs approximately once per minute, the device can repeatedly
perform:

```text
normal power saving
        |
        | ~55 s
        v
Recovery
        |
        | ~5 s
        v
normal power saving
        |
        v
repeat
```

This is a credible source of additional energy consumption.

However, the following remain unmeasured:

```text
WF200 current during Recovery
incremental host current
energy per Recovery
daily Recovery energy
battery-runtime reduction
```

Therefore the existence of an additional energy workload is strongly
supported, while its quantitative battery impact remains unknown.

---

# 42. C2 Changes the Energy Interpretation

Before C2 was proven, repeated Recovery could be interpreted as:

```text
new radio problem
        |
        v
Recovery
        |
        v
new radio problem
        |
        v
Recovery
```

The current control-flow evidence supports a different model after the first
qualifying event:

```text
first qualifying event
        |
        v
Recovery
        |
        v
stale control evidence
        |
        v
Recovery
        |
        v
stale control evidence
        |
        v
Recovery
```

This matters for battery analysis.

The radio does not have to generate a fresh fault every minute for the host to
repeatedly incur the Recovery energy cost.

The host-side control loop itself can sustain the workload.

---

# 43. Relationship to the Historical Battery Drain

The 2.2.4 Beacon Recovery loop provides a technically credible additional
source of energy consumption.

However, it cannot currently be described as:

```text
the original Shelly TRV Gen1 battery-drain root cause
```

or:

```text
the sole battery-drain mechanism
```

Battery drain was also observed historically on firmware 2.1.8.

The specific `real_beacon_skip` / Beacon Recovery mechanism documented here
has not been identified in the examined 2.1.x firmware in the same form.

Therefore the supported interpretation is:

> Firmware 2.2.4 contains an additional host-side Beacon Recovery mechanism
> that can become self-sustaining and repeatedly move the WLAN/host system away
> from its normal low-power state.

Its quantitative contribution to battery life remains to be measured.

Older battery-drain behavior requires separate explanation.

---

# 44. Relationship to Periodic mDNS

Periodic mDNS is a separate energy-relevant mechanism.

The examined firmware chronology shows recurring connected-maintenance mDNS
behavior before 2.2.4.

The cadence changed across versions.

Patch B demonstrates that the targeted periodic mDNS restart can be suppressed
without suppressing Beacon Recovery.

Therefore:

```text
periodic mDNS
```

and:

```text
Beacon Recovery
```

must remain separate in the causal model.

They can both contribute to energy use without one being required for the
other.

---

# 45. Relationship to the WUP / EM2 Retention Candidate

A separate low-level WLAN sleep-resource retention/failure path has also been
identified.

Its core behavior already exists in earlier firmware.

It is therefore not the same mechanism as the 2.2.4 Beacon Recovery loop.

The mechanisms should remain separated:

```text
WUP / EM2 retention candidate
        |
        +-- older inherited low-level sleep-resource behavior


periodic mDNS
        |
        +-- recurring network-maintenance behavior


Beacon Recovery
        |
        +-- 2.2.4 counter-derived host Recovery behavior
```

No blind WUP/EM2 patch is currently justified.

Forcing release of a WLAN-owned sleep resource without understanding its
ownership semantics could cause:

- lost WLAN interrupts
- driver-state corruption
- connectivity failure
- race conditions

That investigation remains separate from Patch C-C.

---

# 46. Firmware-Version Context

The specific `real_beacon_skip` Recovery mechanism described here is a 2.2.4
finding.

Earlier examined firmware contains related WLAN PM infrastructure, but the same
host-side `real_beacon_skip` Recovery control flow has not been identified in
the examined 2.1.x versions.

This matters for causal interpretation.

The 2.2.4 mechanism can explain:

```text
an additional 2.2.4-specific recurring energy cost
```

but cannot by itself explain:

```text
all historical battery drain across earlier firmware
```

See:

[`firmware-comparison.md`](firmware-comparison.md)

for the version chronology.

---

# 47. Current Experimental Patch Roles

The current patch roles should be interpreted as follows.

| Patch | Purpose | Recovery semantics |
|---|---|---|
| Patch A | Isolation experiment | Recovery action bypassed |
| Patch B | mDNS isolation | Beacon Recovery unchanged |
| Patch A+B | Combined isolation | Recovery and targeted mDNS both bypassed |
| Patch C family | Corrective research | Preserve legitimate Recovery |
| Patch C-C | Current preferred candidate | Correct C1a/C1b/C2 while retaining Recovery |

Patch A remains scientifically useful.

Patch C-C is the current candidate for semantic correction.

These roles should not be conflated.

---

# 48. Evidence Summary

| Finding | Status |
|---|---|
| Firmware 2.2.4 contains the analyzed Beacon Recovery mechanism | **PROVEN** |
| Recovery control uses cached `real_beacon_skip` | **PROVEN** |
| `real_beacon_skip` is derived from received-beacon counter history | **PROVEN** |
| Relevant statistics are obtained through WF200 command `0x66` | **PROVEN** |
| Stock Recovery reads `R` as signed 8 bit | **PROVEN** |
| Fresh stock trigger domain includes delta `3`, `4`, and `201..600` | **PROVEN** |
| Delta `3` and `4` qualify because of signed interpretation | **PROVEN** |
| C1a is a genuine control-validity defect | **STRONGLY SUPPORTED** |
| Fixed `600` is used without elapsed-time metadata attached to `P` | **PROVEN** |
| Identified conditions can preserve `P` across invalid measurement epochs | **PROVEN** |
| C1b is a genuine measurement-validity defect | **STRONGLY SUPPORTED** |
| Exact first field trigger is known | **UNKNOWN** |
| Recovery sets the shared countdown to `5` | **PROVEN** |
| Recovery requests PM state 1 | **PROVEN** |
| Recovery requests WLAN Active / Always-On operation | **PROVEN** |
| Recovery restricts deeper host EM2/EM3 sleep | **PROVEN** |
| EM1 remains available during the identified restriction | **PROVEN** |
| Recovery normally persists for approximately five serviced seconds | **PROVEN** |
| Normal PM state is restored afterwards | **PROVEN** |
| Current `desired_beacon_skip` is reapplied when normal state 3 is restored | **PROVEN** |
| Recovery clears `P` | **PROVEN** |
| Recovery preserves qualifying `R` | **PROVEN** |
| First post-Recovery baseline sample does not calculate fresh `R` | **PROVEN** |
| Stock evaluates historical `R` on that baseline-only path | **PROVEN** |
| C2 forms a self-sustaining successful-sample Recovery loop | **PROVEN** |
| Every repeated Recovery requires a new RF anomaly | **UNKNOWN as a general radio statement; not required by the proven C2 loop** |
| Normal PM restoration clears the C2 state | **UNKNOWN as a universal statement; not observed in the identified stock path** |
| Recovery has a coherent WLAN reliability purpose | **STRONGLY SUPPORTED** |
| Exact original developer intent | **UNKNOWN** |
| Patch B leaves Beacon Recovery behavior intact | **PROVEN for the targeted patch design and observed runtime behavior** |
| Targeted periodic mDNS is required for the observed Recovery loop | **UNKNOWN as a universal network interaction; not required under tested conditions** |
| Patch A suppresses the targeted Recovery action | **PROVEN** |
| Patch A preserves legitimate Recovery | **UNKNOWN as an intent claim; structurally it bypasses the analyzed action** |
| Patch C-C preserves the fresh `R=1/2` Recovery path statically | **PROVEN** |
| Patch C-C prevents historical `R` from controlling a baseline-only sample statically | **PROVEN** |
| Patch C-C passed static pre-build qualification | **PROVEN** |
| Patch C-C hardware behavior | **UNKNOWN** |
| Explicit application-level TX-power increase in normal Recovery | **UNKNOWN as protected-radio behavior; none identified in the application path** |
| Normal Recovery directly performs scan/reconnect/DHCP | **UNKNOWN as lower-level autonomous behavior; none identified in the application control path** |
| Exceptional driver-lock failure can lead to MCU reset | **PROVEN** |
| Exceptional reset path causes ordinary recurring Recovery | **UNKNOWN** |
| D3 directly triggers Beacon Recovery | **UNKNOWN** |
| Repeated Recovery creates additional energy workload | **STRONGLY SUPPORTED** |
| Quantitative battery impact | **UNKNOWN** |
| Beacon Recovery is the sole historical battery-drain cause | **UNKNOWN and not established by current evidence** |

---

# 49. Remaining Questions

The Recovery mechanism itself is now substantially characterized.

The principal remaining questions are no longer simply:

```text
What does Recovery do?
```

or:

```text
Why does it repeat?
```

The main remaining questions are:

1. What causes the first fresh qualifying measurement on affected physical
   devices?

2. How often is C1a relevant on real hardware?

3. How often does C1b produce the first qualifying value?

4. Which PM, AP, DTIM, association, or radio-internal conditions precede the
   first trigger?

5. What are the exact physical measurement intervals under real scheduler and
   PM timing?

6. Does Patch C-C behave correctly across strong, weak, and fluctuating RSSI?

7. Does Patch C-C preserve legitimate Recovery when a fresh qualifying
   measurement genuinely recurs?

8. Does Patch C-C remain stable across reassociation, AP restart, disconnect,
   clock correction, and temporary PM override?

9. Is interrupt latency acceptable with the added short measurement-state
   critical section?

10. Will the expanded GBL be accepted by the device bootloader/update path?

11. What is the electrical energy cost of one Recovery event?

12. How much battery-runtime improvement results when the self-sustaining loop
    is corrected?

13. How much of the remaining historical battery drain is attributable to
    mechanisms inherited from earlier firmware?

---

# 50. Hardware Qualification Plan for Patch C-C

The next phase is controlled hardware qualification.

The minimum useful test matrix should include:

```text
stock 2.2.4
vs.
Patch C-C
```

under comparable AP and device conditions.

Important scenarios include:

- normal strong RSSI
- normal medium RSSI
- weak RSSI
- fluctuating RSSI
- desired skip 20
- desired skip 15
- desired skip 10
- temporary H=180 PM override
- association/reassociation
- AP restart
- disconnect/reconnect
- clock correction/reset
- long uninterrupted connected operation

The test should verify both:

```text
false Recovery suppression
```

and:

```text
legitimate Recovery preservation
```

The second requirement is essential.

A patch that merely eliminates all Recovery would reproduce the broad behavior
of Patch A rather than validate Patch C-C.

---

# 51. Required Runtime Observations

During Patch C-C testing, the following should be observed where available:

```text
battery voltage
battery percentage
uptime
RSSI
desired_beacon_skip
real_beacon_skip
Recovery log events
PM state transitions
cloud connectivity
network availability
```

The most important behavioral sequence after a qualifying Recovery is:

```text
Recovery
        |
        v
P cleared
R retained
        |
        v
next successful sample establishes baseline
        |
        v
NO Recovery from historical R
        |
        v
later comparable sample calculates fresh R
```

A later fresh:

```text
R = 1
```

or:

```text
R = 2
```

must still be able to trigger Recovery.

---

# 52. Battery Testing Must Remain Separate from Functional Validation

Patch C-C hardware qualification should first answer:

```text
Does the corrected control flow behave as designed?
```

Only after that should long-term battery testing answer:

```text
Does this materially improve battery runtime?
```

These are separate questions.

A firmware can be functionally correct while producing little measurable
battery improvement if another mechanism dominates consumption.

Likewise, apparent short-term voltage improvement is not sufficient evidence
of functional correctness.

The preferred evidence source for battery comparison remains:

```text
bat.voltage
```

rather than relying only on the quantized:

```text
bat.value
```

percentage.

---

# 53. Current Recovery Model

The current best-supported model is:

```text
WF200 cumulative statistics
        |
        v
host measurement state C / P
        |
        +------------------------------+
        |                              |
        | invalid epoch                | valid epoch
        |                              |
        v                              v
C1b risk                         delta = C - P
                                       |
                                       v
                                  600 / delta
                                       |
                                       v
                                  8-bit R
                                       |
                                       v
                              stock signed control
                                       |
                                       +---- C1a risk
                                       |
                                       v
                              qualifying Recovery
                                       |
                                       v
                                  H = 5
                                       |
                                       v
                                  PM state 1
                                       |
                                       v
                             Active / Always-On
                                       |
                                       v
                              EM2 / EM3 restricted
                                       |
                                       | ~5 s
                                       v
                              restore normal PM
                                       |
                                       v
                                   P = 0
                               R remains cached
                                       |
                                       v
                           next baseline-only sample
                                       |
                                       v
                           historical R evaluated
                                       |
                                       +---- C2
                                       |
                                       v
                                  Recovery again
```

Patch C-C changes the host-side validity semantics while preserving the
Recovery action:

```text
valid measurement epoch
        |
        v
fresh unsigned R
        |
        v
R = 1 or 2 ?
   |          |
  no         yes
   |          |
   v          v
normal     legitimate
operation  Recovery
```

and after Recovery:

```text
P = 0
R retained diagnostically
        |
        v
baseline-only sample
        |
        v
no Recovery from historical R
        |
        v
later fresh measurement
```

---

# 54. Current Conclusion

The firmware 2.2.4 Beacon Recovery mechanism is now well characterized at the
host-application level.

The normal Recovery action is approximately:

```text
fresh qualifying Recovery evidence
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
WF200 Active / Always-On
        |
        v
host EM2 / EM3 restricted
        |
        | approximately 5 serviced seconds
        v
restore application PM state
        |
        v
normally state 3
with current desired_beacon_skip
```

This action is technically coherent as a temporary WLAN
recovery/reconfiguration mechanism.

The current evidence therefore does not support simply treating the existence
of Recovery as the defect.

Instead, three host-side validity problems have been identified:

```text
C1a
signed control interpretation

C1b
measurement-window validity

C2
post-Recovery evidence freshness
```

C2 explains the persistent approximately once-per-minute Recovery loop after a
qualifying event.

Once the state becomes:

```text
P = 0
R = qualifying historical value
```

the next successful baseline-only sample can retrigger Recovery without a new
qualifying beacon measurement.

That loop is:

**PROVEN**

The exact cause of the first qualifying field measurement remains:

**UNKNOWN**

This changes the central research question.

It is no longer:

```text
Why does the WF200 necessarily produce a new bad measurement every minute?
```

The better questions are:

```text
What caused the first qualifying measurement?
```

and:

```text
Does correcting C1a, C1b, and C2 preserve legitimate Recovery
while eliminating invalid recurrence?
```

Patch A remains valuable as an isolation experiment but removes legitimate
Recovery together with invalid Recovery.

Patch C-C is therefore the current preferred corrective candidate.

Its static pre-build qualification has passed with no known static blocker.

Hardware qualification is still pending.

Finally, the 2.2.4 Beacon Recovery loop is a credible additional source of
energy consumption, but it is not established as the sole or original Shelly
TRV Gen1 battery-drain mechanism.

Earlier firmware exhibited battery-drain behavior without this identified
2.2.4-specific Recovery implementation.

The broader historical battery problem therefore remains a multi-mechanism
investigation.

---

# Related Documents

Detailed `real_beacon_skip` analysis:

[`real-beacon-skip.md`](real-beacon-skip.md)

WF200 beacon-counter and baseline analysis:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

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

This investigation is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

The Recovery control flow was traced through:

- the WF200 statistics interface
- the `real_beacon_skip` calculation
- measurement baseline handling
- application PM-state logic
- WLAN power-management requests
- host sleep-resource handling
- Recovery restoration
- post-Recovery measurement progression

Runtime experiments include:

- stock firmware debug-log observation
- `/stats` observation
- RSSI and desired-skip comparison
- isolated Patch A testing
- isolated Patch B testing
- combined Patch A+B testing
- passive mDNS packet capture
- long-term battery logging

Patch C-C additionally underwent a dedicated static pre-build qualification
covering:

- patch-site preimages
- native instruction boundaries
- branch/call behavior
- register and flag dependencies
- baseline invalidation
- C1a semantics
- C2 semantics
- PM interaction
- measurement-state serialization
- flash placement
- container-growth requirements
- scenario-based falsification

Public Silicon Labs WF200/fullMAC information is used where necessary to
interpret documented host-visible WLAN interface behavior.

The protected WF200 implementation is not reproduced.

No original or modified firmware image, complete proprietary function, or
large raw disassembly is published in this document.

The project deliberately distinguishes:

```text
PROVEN
STRONGLY SUPPORTED
INFERENCE
UNKNOWN
```

and separately distinguishes:

```text
static host implementation
runtime observation
radio-level interpretation
developer intent
battery hypothesis
```

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