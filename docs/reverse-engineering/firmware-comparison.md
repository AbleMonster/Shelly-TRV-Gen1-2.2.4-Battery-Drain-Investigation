# Firmware Comparison – Shelly TRV Gen1

## Scope

This document compares the WLAN, power-management, and recurring network
behavior of the following Shelly TRV Gen1 (`SHTRV-01`) firmware versions:

| Firmware | Build | Role |
|---|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` | older reference |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` | early comparison |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` | later comparison |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` | primary research target |

The purpose of this comparison is not to identify a single firmware version as
the origin of the historical battery-drain problem.

Instead, the objective is to determine:

- which recurring WLAN mechanisms exist in each firmware generation
- when relevant power-management behavior changed
- when periodic mDNS restart behavior appeared
- when Beacon Recovery appeared
- which mechanisms are shared between versions
- which mechanisms are specific to later firmware
- which historical battery-drain explanations can or cannot be supported by
  the firmware chronology

The comparison combines native ARM Thumb analysis, binary comparison, runtime
observations, packet captures, and controlled experiments.

---

# Evidence Classification

This project uses four evidence levels.

## PROVEN

Directly established from native firmware behavior, deterministic binary
comparison, validated control flow, or sufficiently direct runtime evidence.

## STRONGLY SUPPORTED

Multiple independent findings support the conclusion, but some implementation
detail or environmental dependency remains unresolved.

## INFERENCE

A technically plausible interpretation consistent with the available
evidence, but not directly established.

## UNKNOWN

The available evidence is insufficient to determine the behavior or original
developer intent.

The distinction is important because the existence of a firmware mechanism
does not by itself establish its contribution to battery consumption.

---

# High-Level Chronology

The investigated firmware generations show a progressive expansion of WLAN
maintenance and power-management behavior.

At a high level:

```text
2.1.0
  |
  | baseline WLAN / PM implementation
  |
  v
2.1.3
  |
  | recurring connected mDNS restart introduced
  | state-5 / psovrd2 introduced
  | PM/event behavior expanded
  |
  v
2.1.8
  |
  | mDNS cadence changed to approximately 180 s
  | post-association PM restoration changed
  | FMAC / protected WF200 generation updated
  |
  v
2.2.4
  |
  | Beacon statistics expanded
  | real_beacon_skip introduced
  | Beacon Recovery introduced
  | PM retry / locking behavior expanded
  | FMAC / protected WF200 generation updated again
```

This chronology immediately establishes an important constraint:

> The Beacon Recovery mechanism found in firmware 2.2.4 cannot explain the
> entire historical battery-drain problem because battery drain has also been
> observed in practical use on firmware 2.1.8.

The historical problem therefore remains consistent with a multi-mechanism
model.

---

# Firmware 2.1.0

Firmware 2.1.0 is used as the oldest detailed reference in the current
comparison.

It already contains:

- mDNS responder functionality
- WF200 WLAN power management
- normal connected Fast Power Save
- WLAN wake-resource handling
- host sleep / EM2 coordination
- conditional low-level sleep failure paths

However, several recurring mechanisms present in later firmware are absent or
have not been identified in the 2.1.0 host control flow.

---

## mDNS in 2.1.0

The mDNS responder itself already exists.

Therefore:

```text
2.1.0 has no mDNS
```

would be incorrect.

The relevant distinction is that no comparable recurring connected
maintenance caller has been identified that continuously restarts the mDNS
probing sequence during normal connected operation.

A simultaneous runtime packet capture of approximately 13 minutes also did not
observe the later characteristic periodic mDNS bursts from the 2.1.0 reference
device.

This does **not** prove that firmware 2.1.0 never emits mDNS traffic.

It establishes only that the later recurring connected restart behavior was
not observed during that test and has not been identified in the analyzed
2.1.0 host path.

### Classification

mDNS responder exists:

**PROVEN**

Later-style recurring connected restart identified:

**NO**

Comparable periodic runtime burst during the monitored window:

**NOT OBSERVED**

---

# Normal Power Management in 2.1.0

The normal connected power-management path already contains the fundamental
sequence:

```text
wake WLAN subsystem
        ↓
configure WF200 power mode
        ↓
enter device sleep
        ↓
release WLAN-owned wake / sleep resource
```

Normal connected operation uses the earlier form of the state-3 power-save
mechanism.

The fundamental wake-resource and EM2 coordination therefore predates the
later firmware generations.

This is important when evaluating possible low-level sleep-resource retention.

A conditional failure path in which the final device-sleep operation can
prevent the normal release sequence is not unique to firmware 2.2.4.

It already exists in the older architecture.

Therefore:

> The mere existence of the WUP / EM2 retention path cannot identify the
> historical firmware regression boundary.

Its runtime frequency and the effect of later firmware changes remain
unresolved.

---

# Firmware 2.1.0 → 2.1.3

The transition from 2.1.0 to 2.1.3 introduces several relevant host-side
changes.

Conceptually:

```text
2.1.0
  ↓
2.1.3
  ├─ recurring connected mDNS restart
  ├─ state-5 / psovrd2 mechanism
  ├─ named active power-save override
  ├─ wake ACK timing change
  └─ event-handling changes
```

Importantly, this transition does not represent a complete replacement of the
underlying WLAN architecture.

The normal state-3 power-save behavior remains substantially related to the
earlier implementation.

---

# Periodic mDNS Restart in 2.1.3

The most important confirmed new recurring connected workload in this
transition is the periodic mDNS restart.

Firmware 2.1.3 contains a connected maintenance path that periodically invokes
the equivalent of:

```text
mdns_resp_restart()
```

The resulting sequence is approximately:

```text
connected maintenance
        ↓
restart mDNS responder probing
        ↓
reset probing state
        ↓
schedule probes
        ↓
probe
probe
probe
        ↓
announcement
```

Runtime packet capture independently confirmed this recurring behavior.

The observed cadence on the tested 2.1.3 configuration was approximately:

```text
60 seconds
```

The important change is therefore not:

```text
mDNS introduced
```

but:

```text
recurring connected mDNS probing restart introduced
```

### Classification

Recurring connected restart path:

**PROVEN**

Approximately 60-second runtime behavior on the tested configuration:

**PROVEN**

Quantitative battery contribution:

**UNKNOWN**

---

# State 5 / `psovrd2` in 2.1.3

Firmware 2.1.3 also introduces the identified temporary power-management
override associated with state 5.

Known entry mechanisms include:

```text
/psovrd2
```

and the corresponding cloud-side command path.

The mechanism requests approximately:

```text
Fast Power Save
beacon skip = 10
```

for a temporary period.

The associated countdown is initialized to:

```text
180
```

and is serviced by firmware maintenance logic.

This should **not** be interpreted as:

```text
MCU intentionally remains fully awake for 180 seconds
```

State 5 is a temporary WLAN power-management configuration.

The normal low-level sleep mechanism can continue operating while the override
is active.

No autonomous normal-idle caller continuously entering state 5 has been
identified.

Repeated external requests can, however, refresh the countdown.

### Classification

State-5 mechanism exists:

**PROVEN**

Introduced between the investigated 2.1.0 and 2.1.3 images:

**PROVEN**

Autonomous recurring idle entry:

**NOT IDENTIFIED**

Normal three-minute full-MCU-awake hold:

**NOT SUPPORTED**

---

# Wake ACK Timing Change

The investigated transition also changes part of the WLAN wake-acknowledgment
timing.

The earlier implementation uses a shorter bounded wait, while 2.1.3 expands
the corresponding wait to approximately five scheduler ticks.

This represents a real power-management implementation change.

However, no evidence currently establishes that this timing change alone
caused the historical battery-runtime degradation.

### Classification

Implementation change:

**PROVEN**

Battery impact:

**UNKNOWN**

---

# Firmware 2.1.3 → 2.1.8

The transition to firmware 2.1.8 includes more substantial WLAN-stack and
power-management changes.

Relevant differences include:

- changed periodic mDNS cadence
- additional post-association PM sequencing
- updated FMAC generation
- updated protected WF200 firmware
- changes in WLAN state restoration
- additional network behavior changes

This transition is particularly important because practical battery drain has
also been observed on 2.1.8.

---

# mDNS Cadence in 2.1.8

The recurring connected mDNS mechanism remains present in firmware 2.1.8.

However, the scheduling behavior changes from the approximately one-minute
2.1.3 pattern.

Static analysis identifies a modulo-three gate in the relevant connected
maintenance path.

With the underlying minute service, this produces an intended cadence of
approximately:

```text
3 × 60 s = 180 s
```

for the recurring mDNS restart.

Therefore the three-minute mDNS behavior is **not unique to firmware 2.2.4**.

It is already present by the investigated 2.1.8 firmware.

This is an important chronology correction.

### Classification

Recurring mDNS restart retained:

**PROVEN**

Modulo-three gate present in 2.1.8:

**PROVEN**

Intended cadence approximately 180 seconds:

**STRONGLY SUPPORTED**

Equivalent dedicated runtime packet capture for 2.1.8:

**NOT YET AVAILABLE**

---

# Post-Association PM Restoration in 2.1.8

Firmware 2.1.8 changes the sequencing used after association.

The identified path includes an intermediate restoration state before returning
to the normal connected state.

Conceptually:

```text
association
        ↓
intermediate PM restoration state
        ↓
bounded delay
        ↓
normal connected state 3
```

The identified delay is approximately:

```text
100 scheduler ticks
```

before restoration toward the normal state-3 configuration.

This is a real change relative to the earlier firmware generation.

Its net energy effect has not been measured.

### Classification

Sequencing change:

**PROVEN**

Quantitative battery impact:

**UNKNOWN**

---

# WLAN Component Changes in 2.1.8

The transition also updates the underlying WLAN components.

The investigated versions show approximately:

```text
2.1.3
FMAC 3.3.2
WF200 3.12.2

        ↓

2.1.8
FMAC 3.4.1
WF200 3.14.0
```

The protected WF200 image also changes between these firmware generations.

This means that a host-code comparison alone cannot describe every possible
radio-side behavioral change.

The exact internal consequences of the protected WLAN firmware update remain
partially unresolved.

### Classification

Component-version change:

**PROVEN**

Exact radio-internal behavioral consequences:

**UNKNOWN**

---

# Firmware 2.1.8 and Historical Battery Drain

Practical battery drain has been observed after downgrading a device from
firmware 2.2.4 to firmware 2.1.8.

This observation is important because the later 2.2.4 Beacon Recovery
mechanism is not present in the same identified form in 2.1.8.

Therefore:

```text
2.2.4 Beacon Recovery
```

cannot currently explain:

```text
all historical Shelly TRV Gen1 battery drain
```

This does not establish which 2.1.8 mechanism causes the observed drain.

Possible contributors include:

- recurring mDNS activity
- WLAN power-management behavior
- radio-side behavior
- conditional sleep-resource retention
- cloud/network workload
- valve/motor activity
- other unidentified mechanisms

Their quantitative contributions remain unresolved.

---

# Firmware 2.1.8 → 2.2.4

Firmware 2.2.4 further expands the WLAN and power-management implementation.

Relevant changes include:

```text
2.1.8
  ↓
2.2.4
  ├─ expanded WF200 statistics handling
  ├─ received-beacon monitoring
  ├─ real_beacon_skip
  ├─ Beacon Recovery
  ├─ expanded PM retry / locking behavior
  ├─ newer FMAC generation
  └─ newer protected WF200 firmware
```

The most important newly identified recurring mechanism for the current
investigation is Beacon Recovery.

---

# WLAN Component Changes in 2.2.4

The investigated component progression is approximately:

```text
2.1.8
FMAC 3.4.1
WF200 3.14.0

        ↓

2.2.4
FMAC 3.7.0
WF200 3.16.1
```

The protected WLAN firmware image changes again.

As with the 2.1.8 transition, not every radio-internal behavioral difference
can be reconstructed from host code alone.

### Classification

Component-version change:

**PROVEN**

Complete radio-internal behavioral effect:

**UNKNOWN**

---

# Beacon Statistics in 2.2.4

Firmware 2.2.4 contains the identified periodic statistics path using WF200
command:

```text
0x66
```

The returned statistics include values corresponding to:

```text
received beacon count
missed beacon count
TBTT timing difference
```

The host uses the cumulative received-beacon counter for the calculation:

```text
C = current received-beacon count
P = previous received-beacon baseline

delta = C - P

real_beacon_skip = 600 / delta
```

The result is stored in an 8-bit field and later participates in the Beacon
Recovery decision.

This host-side measurement/control chain has not been identified in the same
form in the investigated earlier firmware versions.

For detailed analysis, see:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

and:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

# Beacon Recovery in 2.2.4

When the calculated/cached recovery value qualifies, firmware 2.2.4 can
temporarily reconfigure the WF200 power-management state.

The observed sequence is approximately:

```text
normal state 3 / Fast Power Save
        ↓
Beacon Recovery
        ↓
state 1 / active WLAN
        ↓
approximately 5 serviced seconds
        ↓
restore saved PM state
        ↓
normally state 3 / Fast Power Save
```

The normal recovery sequence therefore performs a real WF200
power-management reconfiguration.

No evidence has been found that the normal recovery path intentionally performs
a complete Wi-Fi reconnect, DHCP renewal, or cloud reconnect.

No explicit transmit-power increase has been identified.

Runtime logs from affected stock 2.2.4 devices have shown the recovery
repeating approximately once per minute for extended periods.

### Classification

Recovery mechanism:

**PROVEN**

Temporary active WLAN configuration:

**PROVEN**

Approximately five-second restoration behavior:

**PROVEN**

Recurring approximately minute-spaced runtime loop:

**PROVEN on observed affected devices**

Quantitative electrical cost:

**UNKNOWN**

---

# C1a – Signed Control-Value Interpretation

Later analysis of the 2.2.4 recovery calculation identified an independent
host-side validity problem.

The quotient:

```text
600 / delta
```

is stored as one byte.

Stock recovery control subsequently reads that byte as signed.

For example:

```text
delta = 3

600 / 3 = 200
uint8_t = 0xC8
signed int8_t = -56
```

and:

```text
delta = 4

600 / 4 = 150
uint8_t = 0x96
signed int8_t = -106
```

Because stock recovery rejects zero and accepts signed values less than or
equal to `2`, these negative interpretations qualify.

The fresh stock trigger set is therefore:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

The `delta = 3` and `delta = 4` cases are created by the signed-byte
interpretation.

### Classification

Control-decision effect:

**PROVEN**

Interpretation as a measurement/control-validity defect:

**STRONGLY SUPPORTED**

---

# C1b – Measurement-Window Validity

The 2.2.4 calculation uses the fixed numerator:

```text
600
```

but the previous cumulative beacon baseline does not carry a corresponding
elapsed-time measurement.

Identified firmware paths can preserve the previous baseline while expected
measurement opportunities are skipped.

The later calculation can therefore become:

```text
old P
        |
        | measurement opportunities skipped
        |
        v
later C
        |
        v
600 / (C - P)
```

where:

```text
C - P
```

represents a longer logical interval than the fixed numerator assumes.

This problem exists even if the WF200 cumulative counter itself is completely
correct.

### Classification

No elapsed-time normalization:

**PROVEN**

Baseline can survive identified skipped measurement opportunities:

**PROVEN**

Measurement-validity defect:

**STRONGLY SUPPORTED**

Exact cause of the first recovery on current physical devices:

**UNKNOWN**

---

# C2 – Self-Sustaining Recovery State

The most important 2.2.4 control-flow defect occurs after a qualifying
recovery.

Let:

```text
P = previous received-beacon baseline
R = cached real_beacon_skip
```

During recovery, stock firmware clears:

```text
P
```

but retains:

```text
R
```

The next successful statistics acquisition therefore begins with:

```text
P = 0
R = historical qualifying value
```

Because `P` is zero, the current counter can only establish a new baseline.

No fresh ratio can be calculated.

However, stock control flow then evaluates the retained historical `R`.

If it qualifies, recovery runs again and clears the newly installed baseline.

Conceptually:

```text
fresh qualifying R
        ↓
Beacon Recovery
        ↓
P = 0
R retained
        ↓
next successful sample
        ↓
new P installed
        ↓
no fresh R calculated
        ↓
old R evaluated
        ↓
Beacon Recovery
        ↓
P = 0
        ↓
repeat
```

This creates a self-sustaining state in which a new radio anomaly is not
required for every subsequent recovery.

### Classification

Self-sustaining stock control-flow state:

**PROVEN**

Requires a new qualifying measurement every minute:

**FALSE**

Broken automatically by normal PM restoration:

**FALSE**

Original developer intent:

**UNKNOWN**

For the complete analysis, see:

[`recovery-mechanism.md`](recovery-mechanism.md)

---

# First Trigger vs. Repeating Recovery

The first qualifying recovery and the subsequent repeating loop must be treated
as separate questions.

A clean startup does not begin in the stale-state loop.

Conceptually:

```text
startup
        ↓
P = 0
R = 0
        ↓
first successful sample
        ↓
establish P
        ↓
later fresh calculation
        ↓
qualifying R
        ↓
first recovery
```

The first recovery therefore requires a qualifying result to be produced
before the stale-state cycle can begin, assuming normal initialized execution
and the identified writers.

After that first recovery, C2 can make the behavior self-sustaining.

Therefore:

```text
cause of first trigger
```

and:

```text
cause of repeated recovery
```

are not necessarily the same mechanism.

The exact cause of the first qualifying field event on the currently affected
physical devices remains:

**UNKNOWN**

---

# Periodic mDNS vs. Beacon Recovery

The chronology shows that periodic mDNS restart behavior predates the
identified 2.2.4 Beacon Recovery mechanism.

Approximately:

```text
2.1.0
no comparable recurring connected restart identified

2.1.3
~60 s recurring mDNS restart

2.1.8
~180 s recurring mDNS restart

2.2.4
~180 s recurring mDNS restart
+
Beacon Recovery
```

Controlled testing with Patch B further demonstrated that Beacon Recovery can
continue after the targeted recurring mDNS restart has been bypassed.

Therefore:

> The periodic mDNS restart is not required for the observed recurring Beacon
> Recovery cycle under the tested conditions.

This does not prove that the two mechanisms can never interact indirectly.

It establishes that the targeted mDNS restart is not a necessary condition for
the observed recovery loop.

---

# WUP / EM2 Across Firmware Generations

A separate low-level power-management path can conditionally retain a
WLAN-owned wake / EM2-blocking resource if a later sleep operation fails before
the normal release path is reached.

This mechanism requires careful chronological interpretation.

The fundamental path already exists in firmware 2.1.0.

Later firmware generations modify surrounding WLAN behavior, timing,
power-management sequencing, and protected WLAN components.

It is therefore possible that the probability or duration of reaching the
condition changes between versions.

However, that has not been demonstrated.

Consequently:

```text
WUP / EM2 retention exists
```

does not imply:

```text
WUP / EM2 retention caused the historical regression
```

and no corrective patch is currently justified that blindly releases the
resource.

### Classification

Conditional path exists:

**PROVEN**

Fundamental path already present in 2.1.0:

**PROVEN**

Runtime frequency:

**UNKNOWN**

Historical battery contribution:

**UNKNOWN**

---

# Cross-Version Summary

| Mechanism | 2.1.0 | 2.1.3 | 2.1.8 | 2.2.4 |
|---|---:|---:|---:|---:|
| mDNS responder | yes | yes | yes | yes |
| recurring connected mDNS restart | not identified | yes | yes | yes |
| observed/intended recurring mDNS cadence | none established | ~60 s | ~180 s static | ~180 s |
| state-5 / `psovrd2` | not identified | yes | yes | yes |
| normal Fast Power Save | yes | yes | yes | yes |
| conditional WUP / EM2 retention path | yes | yes | yes | yes |
| post-association PM restoration changes | earlier form | later form | expanded | expanded further |
| WF200 `0x66` Beacon Recovery statistics chain | not identified | not identified | not identified in current comparison | yes |
| `real_beacon_skip` recovery control | not identified | not identified | not identified | yes |
| Beacon Recovery | not identified | not identified | not identified | yes |
| C1a signed-control issue | n/a | n/a | n/a | yes |
| C1b measurement-window issue | n/a | n/a | n/a | yes |
| C2 stale-control-evidence loop | n/a | n/a | n/a | yes |

`not identified` means that the mechanism has not been found in the
investigated host firmware.

It should not be interpreted as a universal proof that no conceptually similar
behavior can exist elsewhere in protected components.

---

# WLAN Component Evolution

The investigated WLAN component progression is:

| Firmware | FMAC | Protected WF200 firmware |
|---|---|---|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |

This provides another important constraint.

The transition:

```text
2.1.0 → 2.1.3
```

contains significant host-side behavioral changes while retaining the same
investigated FMAC and protected WF200 generations.

The transition:

```text
2.1.3 → 2.1.8
```

changes both host behavior and WLAN components.

The transition:

```text
2.1.8 → 2.2.4
```

again changes both host behavior and WLAN components.

Therefore a battery-runtime difference between firmware versions cannot
automatically be assigned either to:

```text
host application code
```

or:

```text
protected WLAN firmware
```

without additional evidence.

---

# Battery-Drain Interpretation

The firmware chronology currently supports a multi-mechanism model.

Potential contributors include:

```text
normal TRV workload
        +
periodic connected mDNS restart
        +
firmware-specific WLAN power management
        +
protected WF200 behavior
        +
2.2.4 Beacon Recovery
        +
possible conditional sleep-resource retention
        +
cloud/network communication
        +
valve/motor activity
        +
radio environment
```

This is a qualitative model.

It is not a quantitative energy budget.

No direct electrical measurement currently assigns a specific battery-energy
cost to each mechanism.

---

# What the Chronology Establishes

## 1. mDNS itself is not new in 2.1.3

The responder already exists in 2.1.0.

The relevant change is the recurring connected restart.

---

## 2. The recurring mDNS workload changes over time

The investigated progression is:

```text
2.1.0
no comparable recurring connected restart identified

2.1.3
approximately 60-second behavior

2.1.8
approximately 180-second gated behavior

2.2.4
approximately 180-second behavior
```

---

## 3. State 5 is not a three-minute full-awake timer

The 180-second value belongs to a temporary WLAN power-management override.

No normal autonomous periodic state-5 caller has been identified.

---

## 4. WUP / EM2 retention is not unique to the latest firmware

The fundamental conditional path already exists in 2.1.0.

Its existence alone therefore cannot explain a later regression boundary.

---

## 5. Firmware 2.1.8 changes both host and WLAN behavior

Post-association sequencing changes and the FMAC/WF200 generation changes.

Their net battery effect remains unresolved.

---

## 6. Beacon Recovery is a later mechanism

The identified command-`0x66` → counter delta → `real_beacon_skip` → active
recovery chain belongs to the investigated 2.2.4 host control flow.

---

## 7. Beacon Recovery contains independently established host-side problems

The current analysis identifies:

```text
C1a
signed control-value interpretation

C1b
measurement-window / baseline validity

C2
historical control evidence reused after recovery
```

These are distinct issues.

---

## 8. Beacon Recovery cannot explain all historical drain

Battery drain has also been observed on 2.1.8.

Therefore a 2.2.4-specific mechanism cannot be the sole historical cause.

---

# What the Chronology Does NOT Establish

The comparison does **not** currently establish:

- the exact firmware release where the historical battery degradation began
- that firmware 2.1.0 is completely free of battery-drain mechanisms
- that firmware 2.1.3 is battery-drain free
- that firmware 2.1.8 introduced the historical problem
- that periodic mDNS is the sole battery-drain cause
- that Beacon Recovery is the sole battery-drain cause
- that WUP / EM2 retention is the historical cause
- that protected WF200 changes are responsible for the regression
- the quantitative energy cost of any individual mechanism
- the exact first trigger of Beacon Recovery on the affected physical devices
- that Patch A+B restores a specific battery lifetime
- that Patch C-C has demonstrated a battery-life improvement

---

# Patch-Relevant Interpretation

The firmware chronology also changes how the experimental patches should be
interpreted.

## Patch A

Patch A bypasses Beacon Recovery in firmware 2.2.4.

It proved useful for isolating the recurring recovery workload.

However, it also suppresses legitimate recovery after a genuinely qualifying
fresh measurement.

It should therefore not currently be considered the preferred final correction.

---

## Patch B

Patch B bypasses the recurring 2.2.4 mDNS restart call.

It does not intentionally disable the mDNS subsystem itself.

Runtime testing confirmed that the targeted recurring traffic disappears
during the monitored window while normal connectivity remains available.

Beacon Recovery can still occur with Patch B alone.

---

## Patch A+B

The combined experimental firmware suppresses both targeted recurring
mechanisms.

It has operated on real hardware while retaining normal observed TRV
functionality.

This establishes experimental compatibility of the two modifications.

It does **not** establish long-term battery improvement.

---

## Patch C-C

Patch C-C is the current corrective Beacon Recovery candidate.

Unlike Patch A, its objective is not to remove Beacon Recovery.

Its intended behavior is:

```text
preserve statistics
        +
preserve diagnostic history
        +
reject invalid signed interpretation
        +
invalidate unusable measurement baselines
        +
require fresh control evidence
        +
preserve legitimate recovery
```

The C-C design has passed static pre-build qualification.

No known static blocker was identified in the bounded independent review.

The next stage is:

```text
experimental build
        ↓
independent binary / GBL verification
        ↓
controlled hardware A/B test
        ↓
long-term battery observation
```

Patch C-C has **not** yet completed hardware qualification.

---

# Current Research Priorities

The cross-version comparison narrows the remaining work.

## 1. Build and verify Patch C-C

The statically qualified design must be converted into an experimental firmware
artifact using a growth-aware GBL build process.

The resulting binary/container must be independently verified before hardware
flashing.

---

## 2. Hardware-qualify corrected Beacon Recovery

Testing must establish whether Patch C-C:

- boots reliably
- retains normal WLAN connectivity
- retains cloud connectivity
- retains thermostat and valve operation
- preserves legitimate Beacon Recovery
- breaks the stale-state loop
- correctly rejects signed false triggers
- correctly re-baselines after invalid measurement epochs
- remains responsive during the added short critical sections
- remains stable across reconnects, AP restart, clock changes, and PM changes

---

## 3. Capture the first stock recovery event

The exact cause of the first qualifying event remains unknown.

A retained boot-to-first-event trace containing the relevant counter and
baseline state would materially improve the analysis.

---

## 4. Continue long-term battery testing

Long-term comparison remains necessary because:

```text
firmware mechanism corrected
```

does not automatically mean:

```text
historical battery drain solved
```

---

## 5. Keep WUP / EM2 separate

The low-level sleep-resource path remains worth investigating.

However, it should not be modified until its runtime relevance and intended
ownership semantics are better understood.

---

# Current Conclusion

The investigated firmware history does not support a single simple explanation
for Shelly TRV Gen1 battery drain.

Instead, WLAN behavior evolved incrementally:

```text
2.1.0
baseline WLAN / PM behavior
        ↓
2.1.3
new recurring connected mDNS workload
new temporary PM override mechanisms
        ↓
2.1.8
mDNS cadence change
post-association PM changes
new FMAC / WF200 generation
        ↓
2.2.4
expanded PM behavior
new beacon statistics
new real_beacon_skip logic
new Beacon Recovery
```

Firmware 2.2.4 adds a Beacon Recovery mechanism with independently identified
host-side measurement and control-validity problems.

Those problems can explain how a qualifying recovery can become a persistent
approximately minute-spaced recovery cycle.

They cannot explain all historical battery drain because battery drain has also
been observed on firmware 2.1.8.

The strongest current conclusion is therefore:

> Shelly TRV Gen1 battery drain should be treated as a multi-mechanism
> investigation. Firmware 2.2.4 contains a demonstrable Beacon Recovery
> control-flow problem, but the complete historical battery-runtime regression
> remains unresolved.

Patch C-C addresses the identified 2.2.4 Beacon Recovery defects while
attempting to preserve the legitimate recovery mechanism.

Its static pre-build qualification has passed.

Hardware behavior and battery impact remain to be established.

---

# Related Documents

Beacon statistics and baseline handling:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Calculated beacon-skip behavior:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

Periodic mDNS analysis:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Runtime mDNS comparison:

[`../testing/mdns-runtime-comparison.md`](../testing/mdns-runtime-comparison.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Methodology

This comparison is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

Important conclusions are checked against native ARM Thumb instructions,
binary differences, and control flow rather than relying only on decompiler
output.

The comparison deliberately separates:

```text
firmware fact
        ↓
runtime observation
        ↓
technical interpretation
        ↓
battery hypothesis
```

No original or modified Shelly firmware images, complete proprietary
functions, or large raw disassemblies are published in this document.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the tested firmware versions.

No conclusion about the intentions of the original developers is made unless
independently supported by technical evidence.