# Power Management and Sleep

## Scope

This document describes the power-management and sleep behavior identified in
the analyzed Shelly TRV Gen1 firmware versions:

- 2.1.0
- 2.1.3
- 2.1.8
- 2.2.4

The primary purpose is to distinguish between three different layers:

1. application-level WLAN power-management state
2. host-driver wake/sleep and MCU sleep-resource state
3. actual WF200 radio power-save behavior

These layers interact, but they are not equivalent.

This distinction is essential when investigating battery consumption.

For example:

```text
application state = 3
desired_beacon_skip = 20
```

does not by itself prove:

```text
WF200 successfully entered and remained
in the requested power-save configuration
```

and it also does not necessarily prove:

```text
the host MCU is currently free to enter
its expected deepest sleep state
```

This document also covers:

- normal RSSI-dependent power saving
- temporary power-management overrides
- WUP and host sleep-resource handling
- inherited conditional sleep-failure paths
- power-management evolution across firmware versions
- the 2.2.4 Beacon Recovery mechanism
- interaction between PM state and beacon-measurement validity
- the C1a, C1b, and C2 Beacon Recovery defects
- periodic mDNS as a separate recurring mechanism
- experimental Patch A and Patch B
- the current Patch C-C corrective design
- remaining runtime and energy-consumption unknowns

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

Where useful, runtime observations are explicitly described as runtime
evidence, but they do not replace these evidence classifications.

---

# 2. Power-Management Architecture

A simplified model is:

```text
Application PM state
        |
        v
Host / driver state
WUP + MCU sleep resources
        |
        v
WF200 internal power-save state
```

A request from one layer does not automatically prove the final state of the
next layer.

For example, the application may record:

```text
state 3
desired_beacon_skip = 20
```

while the exact internal WF200 behavior still depends on:

- successful host-to-WF200 communication
- acceptance of the requested power-save configuration
- internal WF200 behavior
- completion of the device-sleep sequence
- subsequent radio-internal events
- later PM reconfiguration

The application does not continuously verify every aspect of the resulting
internal radio state.

This distinction is particularly important when interpreting debug logs.

A log such as:

```text
Enter powersave state 3 (skip 20)
```

establishes the requested host-side transition.

It is not a direct electrical measurement of the WF200 or MCU state.

---

# 3. Normal RSSI-Dependent Beacon Skip

The analyzed firmware versions use the following normal desired beacon-skip
mapping:

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
state 3
 |
 v
WF200 power-save request
```

This value represents the host-requested power-save configuration.

It must not automatically be interpreted as the exact physical number of
beacons between radio wake events.

This distinction becomes especially important in firmware 2.2.4 because the
firmware also maintains a separate counter-derived value:

```text
real_beacon_skip
```

The two values serve different purposes.

```text
desired_beacon_skip
```

is the requested configuration.

```text
real_beacon_skip
```

is a host-derived diagnostic/control value calculated from WF200 statistics.

They must not be treated as equivalent.

---

# 4. Application Power States

The firmware uses several application-level WLAN power-management states.

The currently understood states are:

| State | Current interpretation |
|---|---|
| 1 | Active / temporary Active WLAN |
| 2 | Special temporary PM mode; less completely characterized |
| 3 | Normal RSSI-dependent Fast Power Save |
| 4 | Restore saved or deferred PM state |
| 5 | Temporary Fast Power Save override with beacon skip 10 |

Not every state exists or is used identically in every analyzed firmware
generation.

The most important states for the current battery investigation are:

```text
state 1
state 3
state 5
```

State 4 is important because several temporary mechanisms use it as part of
restoration.

---

# 5. State 3 — Normal Connected Power Saving

State 3 is the normal connected power-management state.

Conceptually:

```text
RSSI
 |
 v
desired_beacon_skip
 |
 v
state 3
 |
 v
WF200 power-save request
 |
 v
final device-sleep operation
 |
 v
WUP/resource release
```

Typical requested configurations are:

```text
strong RSSI
skip 20

medium RSSI
skip 15

weak RSSI
skip 10
```

When the normal path completes successfully:

```text
power-save request
        |
        v
device sleep enabled
        |
        v
WUP cleared
        |
        v
WLAN-owned MCU sleep contribution released
        |
        v
deeper host sleep becomes possible
```

Other firmware components may independently hold their own sleep resources.

Therefore release of the WLAN-owned contribution does not prove that the MCU
immediately enters a specific energy mode.

### Classification

State 3 as normal connected PM state:

**PROVEN**

RSSI-dependent desired-skip mapping:

**PROVEN**

Exact internal WF200 behavior after every successful request:

**UNKNOWN**

---

# 6. State 1 — Active / Temporary Active WLAN

State 1 represents a more active WLAN configuration.

The identified path requests the relevant WF200 mode corresponding to:

```text
Active / Always-On
```

Conceptually:

```text
request state 1
        |
        v
wake WLAN device
        |
        v
request Active / Always-On
        |
        v
WUP remains active
        |
        v
WLAN-owned deeper-sleep restriction remains active
```

State 1 does not perform the normal final device-sleep transition used by the
normal state-3 path.

Therefore prolonged or repeatedly entered state 1 can be energy relevant.

This does **not** mean that the host CPU necessarily executes continuously
during the entire state-1 interval.

The more precise interpretation is:

> The WLAN-owned restriction prevents the host from using the deeper energy
> modes that would otherwise become available after normal WLAN sleep
> completion.

For the known 2.2.4 Beacon Recovery path, EM2 and EM3 are restricted during
the temporary active interval.

EM1 remains available.

---

# 7. State 1 Predates Beacon Recovery

State 1 did not originate with the 2.2.4 Beacon Recovery mechanism.

Earlier firmware already contains externally triggered active-override
behavior.

Firmware 2.1.3 contains an externally accessible override associated with:

```text
psovrd
```

Therefore:

```text
state 1 exists
```

does not imply:

```text
automatic Beacon Recovery exists
```

The approximately minute-spaced automatic state-1 recovery loop investigated
in this project is a separate mechanism identified in firmware 2.2.4.

This distinction is important when comparing firmware generations.

---

# 8. State 4 — Restoration

State 4 is associated with restoration of a saved or deferred application PM
state.

Conceptually:

```text
temporary PM state
        |
        v
saved previous state
        |
        v
state 4
        |
        v
restore previous / deferred PM state
```

State 4 should therefore not be interpreted as one fixed radio power mode.

Its main role is application-level restoration.

It becomes particularly relevant in:

- temporary overrides
- post-association handling
- Beacon Recovery restoration

---

# 9. State 5 — Temporary Fast Power Save Override

State 5 first appears in the analyzed firmware set in version 2.1.3.

Identified external interfaces include:

```text
HTTP:
psovrd2

Cloud:
psovrd2
```

State 5 requests approximately:

```text
Fast Power Save
beacon skip = 10
```

and initializes a shared restoration countdown:

```text
H = 180
```

The countdown is serviced by firmware seconds maintenance.

Under normal scheduler servicing this corresponds to approximately:

```text
180 serviced seconds
≈ 3 minutes
```

A typical sequence is:

```text
normal state 3
        |
        | external psovrd2
        v
state 5
        |
        v
Fast Power Save
skip 10
        |
        | H counts down
        v
restore saved / deferred PM state
        |
        v
typically state 3
```

---

# 10. State 5 Does Not Intentionally Hold the MCU Awake

State 5 must not be described as:

```text
MCU awake for 180 seconds
```

The normal state-5 path still performs the final device-sleep operation.

Conceptually:

```text
state 5 request
        |
        v
Fast Power Save
skip 10
        |
        v
device sleep enabled
        |
        v
WUP cleared
        |
        v
WLAN-owned host sleep contribution released
```

Therefore state 5 primarily changes the WLAN power-save policy.

For example:

```text
normal:
skip 20

state 5:
skip 10
```

This creates more nominal beacon-listening opportunities.

The electrical cost of that difference has not been directly measured.

### Classification

State 5 requests Fast Power Save / skip 10:

**PROVEN**

State 5 intentionally holds the host fully awake for 180 seconds:

**FALSE**

Quantitative energy effect:

**UNKNOWN**

---

# 11. State 5 Can Be Externally Prolonged

The external `psovrd2` paths set the countdown before dispatching the state-5
request.

This matters if the override is already active.

For example:

```text
state 5
H = 60

   |
   | new psovrd2 request
   v

H = 180

   |
   v

duplicate state request may be rejected
but countdown has already been refreshed
```

Repeated external requests can therefore prolong the override.

No autonomous normal-idle firmware mechanism has been identified that
continuously generates `psovrd2` requests.

State 5 is currently best described as:

```text
externally triggered
temporary by design
externally prolongable
```

rather than:

```text
autonomous recurring idle loop
```

---

# 12. WF200 Power-Save Command `0x52`

The host uses WF200 command:

```text
0x52
```

for WLAN power-management configuration.

Conceptually:

```text
host PM state
        |
        v
command 0x52
        |
        v
requested WF200 PM configuration
```

The exact payload representation changes between firmware generations.

Firmware 2.2.4 contains expanded surrounding:

- locking
- retry behavior
- error handling
- PM state management

The existence of a successful host-side request does not prove that the
protected WF200 remains indefinitely in exactly that internal configuration.

---

# 13. Requested State vs. Actual Lower-Level State

Application bookkeeping and lower-level WLAN state are distinct.

Conceptually:

```text
application requests state 3
        |
        v
application bookkeeping
        |
        v
wake WF200
        |
        v
command 0x52
        |
        v
device-sleep sequence
```

Not every lower-level failure necessarily rolls application bookkeeping back
to its previous value.

A state such as:

```text
application:
state 3

requested:
skip 20

lower-level radio / transport:
not completely established from application state alone
```

is therefore conceptually possible.

This is why debug logs must be interpreted as evidence of requested host-side
behavior rather than direct measurement of the final electrical state.

---

# 14. Command `0x52` Failure vs. Device-Sleep Failure

Two failure classes must be distinguished.

A failed command `0x52` does not automatically imply retained WUP or a
persistent MCU sleep restriction.

For example:

```text
command 0x52 fails
        |
        v
final device-sleep operation succeeds
        |
        v
WUP cleared
        |
        v
WLAN-owned host sleep contribution released
```

Therefore:

```text
command 0x52 failure
```

does not automatically mean:

```text
persistent host sleep blocker
```

The more important retained-resource case occurs when the later device-sleep
operation itself fails before normal cleanup.

---

# 15. WUP and Host Sleep Resources

WUP participates in host-to-WF200 wake/sleep coordination.

During explicit WLAN wake:

```text
acquire WLAN sleep resource
        |
        v
assert WUP
        |
        v
communicate with WF200
```

When the operation completes successfully:

```text
device sleep enabled
        |
        v
WUP cleared
        |
        v
WLAN-owned host sleep contribution released
```

This matters because the WLAN subsystem participates in host MCU sleep-resource
accounting.

While the WLAN-owned restriction remains held, deeper host energy modes can be
prevented.

---

# 16. Conditional Final-Sleep Failure

A separate conditional failure path exists in the lower-level sleep handling.

Simplified:

```text
WLAN wake
        |
        v
WUP / WLAN sleep resource acquired
        |
        v
application PM operation
        |
        v
final device-sleep operation
        |
        +---- success
        |       |
        |       v
        |   WUP cleared
        |   resource released
        |
        +---- control-register I/O failure
                |
                v
            error return
                |
                v
        normal release can be skipped
```

This can create a mismatch:

```text
application state = power-save state
```

while:

```text
WUP / WLAN-owned host sleep contribution
may remain active
```

The existence of this control-flow path is established by static analysis.

Its runtime frequency and duration are not established.

### Classification

Conditional retention path:

**PROVEN**

Occurrence during ordinary field operation:

**UNKNOWN**

Battery contribution:

**UNKNOWN**

---

# 17. The WUP Retention Path Is Inherited

Focused comparison shows that the fundamental conditional final-sleep /
resource-retention path already exists in firmware 2.1.0.

It remains present in later firmware generations.

Therefore the existence of this path cannot by itself identify a later
battery-regression boundary.

For it to explain a version-dependent regression, another change would need to
cause it to be:

- reached more frequently
- retained for longer
- recovered differently
- combined with another mechanism

No such runtime relationship has yet been demonstrated.

This is why WUP/EM2 remains a separate research track.

---

# 18. Why Blind WUP Cleanup Would Be Unsafe

A retained-resource path might superficially suggest:

```text
device-sleep operation failed
        |
        v
force WUP low
force sleep-resource release
```

Such a modification is not justified by the current evidence.

If the WF200 transport still legitimately requires host availability, forced
release could cause:

- missed WLAN interrupts
- transport desynchronization
- failed WLAN communication
- driver-state corruption
- unstable PM state
- connectivity loss

A safe correction would require establishing the complete transport and
hardware state after the failure.

An existing vendor cleanup or retry path would be preferable to inventing an
unverified forced-release sequence.

No such WUP/EM2 patch is part of the current Patch C design.

---

# 19. Initialization Sleep-Resource Asymmetry

A related resource-management asymmetry exists during WLAN initialization.

Conceptually:

```text
block deeper host sleep
        |
        v
initialize WLAN transport
        |
        +---- success
        |       |
        |       v
        |   normal lifecycle
        |
        +---- failure
                |
                v
        local matching release
        not guaranteed
```

The relevant behavior exists in older firmware as well.

Therefore it does not independently identify the later battery-regression
boundary.

Whether an in-place reinitialization can leave an earlier resource contribution
retained remains unresolved.

---

# 20. Wake-ACK Timing Change

The WF200 wake-acknowledgement wait changes between firmware 2.1.0 and 2.1.3.

Simplified:

```text
2.1.0:
maximum requested wait = 3 ticks

2.1.3:
maximum requested wait = 5 ticks
+ timeout logging
```

The wait terminates early if acknowledgement arrives before the maximum.

Therefore this does not imply that firmware 2.1.3 always spends two additional
ticks awake on every WLAN wake.

Possible effects include:

- longer wait during slow wake
- greater tolerance for delayed acknowledgement
- fewer premature wake failures
- different timeout behavior

The net energy effect remains unknown.

---

# 21. Firmware Evolution

The PM architecture evolves incrementally across the investigated firmware
versions.

At a high level:

```text
2.1.0
  |
  | baseline PM / WUP architecture
  |
  v
2.1.3
  |
  | state 5 / psovrd2
  | active override handling
  | wake-ACK timing change
  | recurring connected mDNS restart
  |
  v
2.1.8
  |
  | post-association restoration changes
  | mDNS cadence changed to ~180 s
  | newer FMAC / protected WF200
  |
  v
2.2.4
  |
  | expanded PM handling
  | newer FMAC / protected WF200
  | beacon statistics
  | real_beacon_skip
  | Beacon Recovery
```

The details of the firmware chronology are documented separately in:

[`firmware-comparison.md`](firmware-comparison.md)

---

# 22. Firmware 2.1.0 → 2.1.3

Substantially inherited behavior includes:

- normal state-3 ordering
- normal RSSI-dependent desired-skip mapping
- core command-`0x52` behavior
- WUP acquisition/release model
- conditional final-sleep retention path
- initialization sleep-resource asymmetry

Relevant additions or changes include:

- state 5
- `psovrd2`
- named active override
- wake-ACK maximum wait
- timeout logging
- event-handling changes
- recurring connected mDNS restart

The mDNS change is important because it introduces recurring connected network
activity without requiring a normal connection failure.

Its quantitative battery contribution remains unresolved.

---

# 23. Firmware 2.1.8 Post-Association Change

Firmware 2.1.8 changes the post-association PM sequence.

Earlier behavior is approximately:

```text
association
        |
        v
request normal state 3
```

The 2.1.8 generation introduces an additional restoration sequence:

```text
association
        |
        v
state 4 restoration
        |
        v
scheduler delay
        |
        v
state 3
```

The identified delay is represented as:

```text
100 scheduler ticks
```

It must not be described as:

```text
100 ms
```

unless scheduler tick duration is independently established.

No unconditional new steady-state awake loop has been identified from this
sequence.

Its quantitative energy effect remains unknown.

---

# 24. Protected WF200 Firmware Boundary

The protected WF200 image is also relevant to firmware comparison.

Within the investigated set:

```text
2.1.0
2.1.3
```

use the same investigated protected WF200 generation.

The protected image changes in:

```text
2.1.8
```

and changes again in:

```text
2.2.4
```

The investigated WLAN component progression is approximately:

| Firmware | FMAC | Protected WF200 |
|---|---|---|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |

This creates an important analysis boundary.

For:

```text
2.1.0 -> 2.1.3
```

host-side changes can be compared while the investigated protected WLAN
generation remains constant.

For:

```text
2.1.3 -> 2.1.8
```

and:

```text
2.1.8 -> 2.2.4
```

both visible host behavior and protected WLAN components change.

A runtime difference therefore cannot automatically be attributed to either
side without additional evidence.

---

# 25. Firmware 2.2.4 PM Expansion

Firmware 2.2.4 expands several PM-related mechanisms.

Identified changes include:

- expanded command-`0x52` handling
- additional retry behavior
- additional locking/wrappers
- WF200 statistics command `0x66`
- beacon statistics processing
- `real_beacon_skip`
- automatic Beacon Recovery
- temporary state-1 recovery

The new high-level chain is:

```text
WF200 statistics
        |
        v
received beacon count
        |
        v
host measurement
        |
        v
real_beacon_skip
        |
        v
recovery decision
        |
        v
state 1
        |
        v
Active / Always-On
        |
        v
temporary deeper-sleep restriction
        |
        v
restore normal PM state
```

This mechanism is separate from the ordinary state-3 power-save policy.

---

# 26. Beacon Statistics and PM Interaction

Firmware 2.2.4 periodically requests WF200 statistics using:

```text
command 0x66
```

For the relevant host-side calculation:

```text
C = current received-beacon count
P = previous received-beacon baseline
R = cached real_beacon_skip
```

When a usable previous baseline exists:

```text
delta = C - P

R = uint8_t(600 / delta)
```

The important PM-related observation is that `P` is not associated with an
explicit elapsed-time value.

Its validity therefore depends on the PM and scheduler context between the two
samples.

This creates a direct relationship between power-management transitions and
Beacon Recovery measurement validity.

For detailed counter analysis, see:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

---

# 27. Shared Override / Recovery Countdown `H`

The same countdown object participates in temporary PM behavior relevant to
the Beacon Recovery measurement path.

For example:

```text
psovrd2
        |
        v
H = 180
        |
        v
state 5
```

Beacon Recovery uses:

```text
H = 5
```

during its temporary active interval.

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
   |         |
  yes        no
   |         |
   v         v
skip       acquire 0x66
evaluation statistics
```

In stock firmware, an H-gated skipped measurement opportunity does not
necessarily invalidate the previous baseline `P`.

This is central to C1b.

---

# 28. Why PM Overrides Matter to Beacon Measurement

Consider a simplified sequence:

```text
t0
successful statistics sample
P established
        |
        v
temporary PM override
H != 0
        |
        v
one or more periodic measurement opportunities skipped
        |
        v
P retained
        |
        v
override expires
        |
        v
later statistics sample C
        |
        v
600 / (C - P)
```

The calculation still uses:

```text
600
```

even though the baseline may span substantially more than the logical interval
that the constant assumes.

The problem is therefore not necessarily:

```text
WF200 returned an incorrect cumulative counter
```

It can instead be:

```text
host compared correct cumulative values
across an invalid measurement epoch
```

This distinction is fundamental to the current Patch C design.

---

# 29. C1b — Measurement-Window Validity

The fixed-600 calculation has no corresponding elapsed-time measurement.

Stock firmware can preserve `P` across identified conditions in which normal
measurement continuity is broken.

Relevant examples include PM override periods in which:

```text
H != 0
```

causes the periodic Beacon Recovery statistics evaluation to be skipped.

Therefore the later calculation can operate on a baseline whose age no longer
matches the assumed nominal measurement interval.

### Classification

Fixed numerator `600`:

**PROVEN**

No per-baseline elapsed-time normalization:

**PROVEN**

H-gated measurement suppression:

**PROVEN**

Stock baseline can survive identified skipped opportunities:

**PROVEN**

Host-side measurement-validity defect:

**STRONGLY SUPPORTED**

Exact first field trigger on affected devices:

**UNKNOWN**

---

# 30. C1b Is Independent of WF200 Counter Correctness

The exact protected-WF200 beacon-counter semantics remain useful for
reconstructing the original design.

They are not required to establish the host-side measurement-window problem.

Even if:

```text
WF200 cumulative received-beacon counter
is completely correct
```

the host can still perform an invalid comparison if:

```text
P and C
```

represent a longer or otherwise invalid logical measurement epoch while the
formula continues to assume the nominal interval represented by:

```text
600
```

Therefore C1b is fundamentally a host-side data-validity issue.

---

# 31. C1a — Signed Control-Value Interpretation

A separate defect exists after the ratio is calculated.

The quotient is stored in one byte:

```text
R = uint8_t(600 / delta)
```

Stock recovery control subsequently loads the byte as signed.

For example:

```text
delta = 3

600 / 3 = 200
0xC8 as signed int8 = -56
```

and:

```text
delta = 4

600 / 4 = 150
0x96 as signed int8 = -106
```

The stock predicate rejects zero and accepts signed values less than or equal
to `2`.

Therefore the fresh stock trigger domain becomes:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

instead of only the ordinary positive quotient domain:

```text
delta = 201 .. 600
```

### Classification

Signed interpretation:

**PROVEN**

Additional delta-3 / delta-4 triggers:

**PROVEN**

Control/measurement-validity defect:

**STRONGLY SUPPORTED**

---

# 32. Normal Beacon Recovery

When a fresh qualifying value is obtained, firmware 2.2.4 performs a real PM
reconfiguration.

Conceptually:

```text
normal state 3
        |
        v
fresh qualifying R
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
Active / Always-On
        |
        | approximately 5 serviced seconds
        v
restore saved PM state
        |
        v
normally state 3
```

This is not merely a log message.

The recovery path genuinely requests a more active WF200 PM configuration and
later restores the previous/normal configuration.

Therefore a legitimate Beacon Recovery mechanism can have a useful reliability
purpose.

This is an important reason why simply removing the recovery action is not the
preferred final correction.

---

# 33. Energy Relevance of Normal Recovery

During the temporary recovery interval:

1. the WLAN device is explicitly active
2. Active / Always-On mode is requested
3. the WLAN-owned deeper-sleep restriction remains held
4. EM2 and EM3 are unavailable through that WLAN-owned restriction
5. the temporary countdown is serviced
6. the saved/deferred PM state is restored
7. normal power saving can resume

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
        v
EM2 / EM3 restricted
        |
        | ~5 s
        v
restore
        |
        v
state 3
```

This is a technically credible source of additional energy consumption.

Its electrical magnitude has not yet been directly measured.

A single legitimate recovery and a persistent approximately minute-spaced
recovery loop must therefore be distinguished.

---

# 34. C2 — Post-Recovery Freshness Failure

The most important repeating-control defect occurs after a qualifying recovery.

Let:

```text
P = previous received-beacon baseline
R = cached real_beacon_skip
```

Stock recovery clears:

```text
P = 0
```

but preserves:

```text
R
```

The next successful statistics acquisition therefore begins with:

```text
P = 0
R = historical qualifying value
```

Because `P == 0`, that sample cannot calculate a fresh ratio.

It can only establish:

```text
P = C
```

However, stock control flow then evaluates the retained historical `R`.

If it still qualifies:

```text
historical R
        |
        v
Beacon Recovery again
        |
        v
P = 0 again
```

The new baseline is therefore destroyed before a second comparable sample can
be obtained.

Conceptually:

```text
fresh qualifying R
        |
        v
Recovery
        |
        +---- P = 0
        |
        +---- R retained
        |
        v
next successful sample
        |
        v
P = C
        |
        | no fresh R calculation
        v
historical R tested
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

### Classification

Post-recovery stale-control-evidence loop:

**PROVEN**

Fresh radio anomaly required for every repeated recovery:

**FALSE**

Normal PM restoration automatically breaks the loop:

**FALSE**

Original developer intent:

**UNKNOWN**

---

# 35. No Normal Escape Within the Identified Stock Loop

Starting from:

```text
P = 0
R = qualifying historical value
```

each eligible successful statistics acquisition performs:

```text
install P
        |
        v
evaluate unchanged R
        |
        v
Recovery
        |
        v
clear P
```

The two normal paths that calculate or clear `R` require conditions that are
not reached in this repeating baseline-only cycle.

Therefore, within the identified successful stock control flow, no normal
escape exists once this state is established.

Identified events that can break the cached relationship include:

- startup/reset
- a periodic command-`0x66` failure that clears both `P` and `R`
- other explicit state resets where both relevant values are reinitialized

Ordinary successful PM restoration does not clear the stale qualifying `R`.

This is why the approximately minute-spaced loop can continue even after the
underlying recovery action itself successfully restored the WF200 PM state.

---

# 36. First Trigger vs. Persistent Recovery

The first qualifying recovery and the later persistent loop are separate
questions.

A normal clean start begins approximately as:

```text
P = 0
R = 0
```

The first successful statistics acquisition establishes a baseline.

A later comparable sample is required to calculate a fresh `R`.

Therefore:

```text
startup
        |
        v
baseline
        |
        v
fresh measurement
        |
        v
qualifying R
        |
        v
first recovery
```

Only after that first qualifying recovery can C2 create:

```text
P = 0
R = historical qualifying value
```

and make the behavior self-sustaining.

This distinction is critical:

> The mechanism that produces the first qualifying recovery does not have to be
> the mechanism that causes every subsequent approximately minute-spaced
> recovery.

The exact first field trigger remains unknown.

C1a and C1b provide demonstrated host-side mechanisms capable of producing
invalid qualifying evidence.

Genuine RF/WF200 conditions may also produce legitimate qualifying evidence.

The exact contribution on the observed physical devices remains under
investigation.

---

# 37. Runtime Recovery Across Different RSSI Policies

Recurring recovery has been observed under more than one desired-skip regime.

A stock 2.2.4 device showed recurring recovery with approximately:

```text
RSSI ≈ -58 to -60 dBm
desired_beacon_skip = 20
```

The mDNS-only Patch-B test device has also shown the stock Beacon Recovery loop
with approximately:

```text
RSSI ≈ -75 to -77 dBm
desired_beacon_skip = 15
```

Therefore the recurring loop is not specific to:

```text
strong RSSI
+
desired skip 20
```

This does not establish that RSSI or radio conditions are irrelevant.

It establishes that one particular RSSI/desired-skip regime is not required
for the repeating control-flow behavior.

---

# 38. Periodic mDNS Is a Separate Mechanism

Periodic connected mDNS restart behavior is distinct from Beacon Recovery.

The investigated chronology is approximately:

```text
2.1.0
mDNS responder exists
no comparable recurring connected restart identified

2.1.3
~60 s recurring connected restart

2.1.8
modulo-three gate
~180 s intended cadence

2.2.4
~180 s recurring behavior
```

Therefore the approximately three-minute mDNS cadence is not unique to 2.2.4.

It is already present in the investigated 2.1.8 host firmware.

The mDNS mechanism and Beacon Recovery can coexist, but they should not be
conflated.

---

# 39. Patch B — mDNS Isolation

Patch B suppresses the targeted recurring connected-maintenance mDNS restart.

It does not intentionally modify:

- state 1
- state 3
- command `0x52`
- command `0x66`
- beacon statistics
- `real_beacon_skip`
- Beacon Recovery
- WUP handling
- general host sleep-resource handling
- the protected WF200 image

Packet capture confirmed suppression of the targeted recurring mDNS sequence
during the monitored test window.

Other event-driven mDNS behavior remains possible.

Most importantly, Beacon Recovery continues on the Patch-B-only device.

Therefore:

> The periodic connected mDNS restart is not required for the observed
> recurring Beacon Recovery loop under the tested conditions.

---

# 40. Patch A — Beacon Recovery Isolation

Patch A bypasses the 2.2.4 Beacon Recovery action.

It leaves intact:

- normal RSSI-dependent desired skip
- normal state 3
- command `0x52`
- command `0x66`
- beacon statistics
- `real_beacon_skip` calculation
- WUP handling
- periodic mDNS behavior
- protected WF200 firmware

Conceptually:

```text
statistics
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

Patch A was useful as an experimental isolation mechanism.

It demonstrated that the recurring state-1 recovery sequence could be
suppressed without removing normal connected PM behavior.

However, Patch A also suppresses legitimate recovery after a genuinely fresh
qualifying measurement.

For that reason it is no longer considered the preferred corrective design.

---

# 41. Combined Patch A+B

The combined experimental configuration suppresses:

```text
Patch A
Beacon Recovery action
```

and:

```text
Patch B
periodic connected mDNS restart
```

while leaving the broader WLAN PM architecture intact.

The combined patch has operated on physical hardware with:

- normal connected operation
- cloud connectivity
- normal desired beacon-skip selection
- targeted recovery sequence absent during monitored windows
- targeted periodic mDNS sequence absent during its monitored capture window

This establishes experimental compatibility.

It does not establish:

- indefinite stability
- long-term battery improvement
- correction of Beacon Recovery measurement validity
- correction of the WUP/EM2 conditional path
- elimination of all possible WLAN energy issues

Patch A+B remains an experimental isolation configuration rather than the
preferred final correction.

---

# 42. Why Patch A Is No Longer the Preferred Recovery Fix

Further reverse engineering showed that the normal Beacon Recovery action
performs a coherent PM reconfiguration:

```text
problematic beacon measurement
        |
        v
temporarily request Active WLAN
        |
        v
allow recovery interval
        |
        v
restore normal power saving
```

Therefore the existence of the recovery mechanism itself is not sufficient to
classify it as erroneous.

The stronger defect is in the evidence used to trigger and retrigger it:

```text
C1a
signed interpretation

C1b
invalid measurement epoch

C2
historical evidence reused as fresh evidence
```

A better correction should therefore preserve:

```text
legitimate fresh recovery
```

while preventing:

```text
invalid trigger
or
stale retrigger
```

This is the purpose of Patch C-C.

---

# 43. Patch C-C — Corrective PM Design

Patch C-C is the current preferred Beacon Recovery correction candidate.

Its objective is not:

```text
disable Beacon Recovery
```

Instead:

```text
preserve legitimate Beacon Recovery
while correcting measurement/control validity
```

At a behavioral level it is designed to:

1. preserve WF200 statistics acquisition
2. preserve the diagnostic `real_beacon_skip` value
3. preserve legitimate fresh Recovery
4. correct the signed-control interpretation
5. invalidate unusable measurement baselines
6. prevent historical `R` from triggering on a baseline-only sample
7. allow measurement progression after Recovery
8. preserve unrelated PM behavior

---

# 44. Patch C-C and C1a

The control decision is changed so that the cached byte is interpreted as
unsigned for the Recovery predicate.

Conceptually:

```text
stock:
signed 8-bit R

Patch C-C:
unsigned 8-bit R
```

This removes the false qualifying interpretation of values such as:

```text
150 -> -106
200 -> -56
```

while preserving:

```text
R = 1
R = 2
```

as qualifying values.

The diagnostic formatter remains separate.

Therefore the corrective behavior targets the control interpretation rather
than unnecessarily redesigning the diagnostic representation.

---

# 45. Patch C-C and C2

Patch C-C distinguishes:

```text
baseline establishment
```

from:

```text
fresh ratio evaluation
```

If the current pass begins without a previous baseline:

```text
P == 0
```

the successful statistics sample establishes:

```text
P = C
```

but historical `R` is not used as fresh control evidence on that pass.

Conceptually:

```text
post-recovery
P = 0
R = historical 2

        |
        v

next successful sample
P = C
R retained diagnostically

        |
        v

no recovery on baseline-only pass

        |
        v

next comparable sample
fresh delta
fresh R
```

If the fresh later measurement is healthy:

```text
no Recovery
```

If the fresh later measurement genuinely qualifies:

```text
legitimate Recovery
```

This preserves both diagnostic history and control freshness.

---

# 46. Patch C-C and C1b

Patch C-C also invalidates `P` at identified events that make the previous
measurement epoch unsuitable for comparison.

The reviewed design covers known logical invalidation events including:

- H-gated measurement periods
- missed relevant scheduler boundaries
- relevant PM state/policy commits
- PM completion
- association/reassociation transitions
- disconnect-related connection changes
- known clock setter/reset paths
- existing statistics-failure behavior

The next successful sample after such invalidation becomes a baseline-only
sample.

This prevents an old counter baseline from being interpreted using the fixed
nominal `600` model after a known invalid logical epoch.

---

# 47. Patch C-C Does Not Add a Physical Baseline Timestamp

Patch C-C implements a logical measurement-validity model.

It does **not** add a persistent physical timestamp to every `P`.

Therefore it should not be described as mathematically proving that every
future counter interval is exactly the nominal physical duration.

The design instead ensures that identified firmware events known to invalidate
measurement continuity also invalidate the baseline.

Remaining runtime questions include:

- unusually delayed callback execution
- physical RF transition completion
- very long external PM transactions
- persistent policy churn
- exact physical sample age

These require hardware qualification.

---

# 48. PM Completion Matters to C1b

An important refinement in the current Patch C-C design is that invalidation is
not limited to PM entry.

PM completion also invalidates the previous beacon baseline.

This matters because a PM reconfiguration has a duration.

Conceptually:

```text
old measurement epoch
        |
        v
PM transition begins
        |
        v
radio configuration changes
        |
        v
PM transition completes
        |
        v
old P invalidated
        |
        v
next successful sample establishes new baseline
```

Without completion-side invalidation, a baseline collected during a sufficiently
long transition could potentially survive into the new PM regime.

The current design therefore treats PM transitions as measurement-epoch
boundaries rather than only control-state changes.

---

# 49. Measurement Serialization

Patch C-C also addresses a race identified during design review.

The relevant problem is conceptually:

```text
measurement code checks P != 0
        |
        v
asynchronous PM/connection path invalidates P
        |
        v
measurement code reloads or uses changed state
```

This could create inconsistent measurement/control decisions.

The current design therefore serializes the critical measurement-decision
section using a short interrupt-mask critical section.

The critical section begins only after the WF200 statistics acquisition.

No added blocking WF200 operation is intentionally performed while the new
critical section is held.

The goal is to protect:

```text
P / measurement-decision consistency
```

not to hold interrupts across the complete radio transaction.

Runtime interrupt-latency behavior still requires hardware qualification.

---

# 50. Static Qualification of Patch C-C

Patch C-C has completed a dedicated static pre-build qualification pass.

The review included:

- patch-site verification
- instruction-boundary verification
- branch/call verification
- helper liveness
- register/flag behavior
- baseline-state scenarios
- C1a exhaustive byte-domain reasoning
- C2 control-flow verification
- PM invalidation paths
- race analysis
- appended-flash placement
- GBL growth requirements
- falsification scenarios

The result was:

```text
PASS STATIC PRE-BUILD QUALIFICATION
```

No known static blocker was identified.

This means an experimental build is justified.

It does **not** mean:

```text
hardware behavior proven
```

or:

```text
battery improvement proven
```

---

# 51. Patch C-C and the Existing PM Architecture

Patch C-C intentionally avoids redesigning the complete WLAN PM system.

It preserves:

- normal state 3
- RSSI-dependent desired skip
- state 1 Recovery
- state 5
- command `0x52`
- command `0x66`
- protected WF200 firmware
- diagnostic `real_beacon_skip`
- normal restoration logic
- existing WUP lifecycle

Its primary modifications concern:

```text
measurement validity
+
control-evidence freshness
+
short serialization of related host state
```

This is important because the objective is to correct demonstrated defects
without removing legitimate WLAN reliability behavior.

---

# 52. WUP/EM2 Remains Separate from Patch C-C

Patch C-C does not modify the inherited conditional WUP/resource-retention
path.

This is deliberate.

The current evidence supports:

```text
WUP/resource-retention path exists
```

but not:

```text
WUP/resource-retention path occurs frequently in normal field operation
```

and not:

```text
WUP/resource-retention path caused the historical battery drain
```

Changing it without stronger evidence would combine two independent research
questions and could introduce unnecessary WLAN instability.

The WUP/EM2 investigation therefore remains separate.

---

# 53. D3 Power-Save Errors

Firmware 2.2.4 contains diagnostic reasons for WF200 power-save errors.

The identified reasons include conditions corresponding approximately to:

```text
0
AP did not provide buffered unicast after PS-Poll

1
AP did not provide buffered unicast after U-APSD trigger

2
AP indicated buffered unicast but none was delivered
during multiple consecutive beacons

3
unstable AP beacon timing / beacon-window adjustment
```

These diagnostics demonstrate that real AP/WF200 power-save edge conditions
are considered by the firmware.

However, no direct host-side control/data-flow edge has been established from:

```text
D3 power-save error
```

to:

```text
Beacon Recovery
```

Therefore:

```text
D3 causes Beacon Recovery
```

is not established.

Radio-internal behavior could still influence later beacon statistics.

That remains an inference rather than a proven host-side causal chain.

---

# 54. Periodic mDNS and PM

Periodic mDNS creates a separate recurring WLAN workload.

The chronology is:

```text
2.1.0
mDNS exists
no comparable recurring connected caller identified

2.1.3
~60 s recurring restart

2.1.8
~180 s gated restart

2.2.4
~180 s recurring restart
```

mDNS activity may cause normal WLAN communication and wake activity.

However, the Patch-B experiment demonstrates that the stock Beacon Recovery
loop can continue without the targeted periodic mDNS restart.

Therefore the two mechanisms must be analyzed separately.

Their combined quantitative energy contribution remains unknown.

---

# 55. Historical Battery-Drain Interpretation

The current PM evidence does not support a single-cause historical model.

A more appropriate working model is:

```text
baseline device consumption
        +
normal valve/motor activity
        +
normal cloud/network activity
        +
periodic connected mDNS activity
        +
firmware-specific WLAN PM behavior
        +
2.2.4 Beacon Recovery
        +
possible conditional sleep-resource retention
        +
radio/environmental effects
```

This is a qualitative model.

It is not a quantitative energy budget.

Importantly, battery drain has also been observed on firmware 2.1.8.

Therefore the 2.2.4 Beacon Recovery mechanism cannot explain the complete
historical problem.

The strongest supported interpretation is:

> Firmware 2.2.4 contains an additional Beacon Recovery control problem capable
> of creating repeated temporary Active-WLAN intervals, while at least one
> additional explanation is required for battery drain observed on earlier
> firmware.

---

# 56. Current PM / Beacon-Recovery Model

The current combined model is:

```text
                         APPLICATION
                             |
                             v
                      requested PM state
                             |
                 +-----------+-----------+
                 |                       |
                 v                       v
          normal state 3          temporary states
                                  1 / 5 / restore
                 |                       |
                 +-----------+-----------+
                             |
                             v
                       host WF200 driver
                             |
                             v
                       command 0x52
                             |
                             v
                    protected WF200 state
                             |
                             v
                    device-sleep handling
                             |
                 +-----------+-----------+
                 |                       |
              success                  failure
                 |                       |
                 v                       v
           WUP released          possible retained
           resource released     WUP / sleep resource
                 |
                 v
          deeper MCU sleep possible
```

Firmware 2.2.4 adds:

```text
WF200 command 0x66
        |
        v
beacon statistics
        |
        v
C / P measurement
        |
        v
600 / delta
        |
        v
cached R
        |
        v
Recovery decision
        |
        v
temporary state 1
```

Three host-side validity problems are now distinguished:

```text
C1a
signed interpretation of R

C1b
measurement-window / baseline validity

C2
historical R reused as fresh control evidence
```

The separate mDNS path is:

```text
connected maintenance
        |
        v
periodic mDNS restart
        |
        v
network traffic
```

The separate conditional sleep-resource path is:

```text
device-sleep failure
        |
        v
possible retained WUP / host sleep restriction
```

These mechanisms must not be conflated.

---

# 57. Evidence Summary

| Finding | Status |
|---|---|
| Application PM state, host sleep resources, and WF200 internal state are distinct layers | **PROVEN** |
| State 3 is the normal connected RSSI-dependent PM state | **PROVEN** |
| Desired skip mapping is 20 / 15 / 10 for the identified RSSI ranges | **PROVEN** |
| State 1 requests Active / Always-On WLAN | **PROVEN** |
| State 1 restricts deeper host sleep through the WLAN-owned resource | **PROVEN** |
| Beacon Recovery uses temporary state 1 | **PROVEN** |
| State 5 exists by firmware 2.1.3 | **PROVEN** |
| State 5 is associated with `psovrd2` | **PROVEN** |
| State 5 requests Fast Power Save with skip 10 | **PROVEN** |
| State 5 uses a 180-serviced-second restoration countdown | **PROVEN** |
| State 5 intentionally keeps the host fully awake for 180 seconds | **FALSE** |
| Repeated external `psovrd2` can refresh the countdown | **PROVEN** |
| Shared `H` also gates Beacon Recovery measurement processing | **PROVEN** |
| Stock H-gated measurement suppression can preserve old `P` | **PROVEN** |
| Command `0x52` failure alone proves retained WUP | **FALSE** |
| Conditional final-sleep failure can skip normal WUP/resource release | **PROVEN** |
| Fundamental conditional WUP-retention path already exists in 2.1.0 | **PROVEN** |
| WUP-retention path occurs frequently during ordinary field operation | **UNKNOWN** |
| WUP-retention path caused the historical drain | **UNKNOWN** |
| 2.1.8 changes post-association PM sequencing | **PROVEN** |
| Protected WF200 generation changes in 2.1.8 and again in 2.2.4 | **PROVEN** |
| 2.2.4 introduces the identified counter-derived Beacon Recovery chain | **PROVEN** |
| Normal Beacon Recovery genuinely reconfigures WF200 PM | **PROVEN** |
| Normal recovery lasts approximately five serviced seconds | **PROVEN** |
| Recovery can recur approximately once per minute on affected devices | **PROVEN** |
| Recurring recovery requires poor RSSI | **FALSE** |
| Recurring recovery is specific to desired skip 20 | **FALSE** |
| `real_beacon_skip` control uses signed byte interpretation in stock firmware | **PROVEN** |
| Signed interpretation adds delta 3 and 4 to the fresh trigger domain | **PROVEN** |
| Fixed-600 measurement has no corresponding baseline timestamp | **PROVEN** |
| Identified PM/scheduler events can invalidate measurement continuity | **PROVEN** |
| Stock can preserve `P` across identified invalid measurement opportunities | **PROVEN** |
| C1b represents a host-side measurement-validity defect | **STRONGLY SUPPORTED** |
| Recovery clears `P` while preserving qualifying `R` | **PROVEN** |
| Baseline-only post-recovery sample can evaluate historical `R` | **PROVEN** |
| C2 can create a self-sustaining Recovery loop | **PROVEN** |
| Every repeated recovery requires a fresh radio anomaly | **FALSE** |
| Normal PM restoration breaks C2 | **FALSE** |
| Exact first field trigger is known | **UNKNOWN** |
| Periodic mDNS is required for Beacon Recovery | **FALSE under tested conditions** |
| ~180-s mDNS gating already exists in investigated 2.1.8 host firmware | **PROVEN** |
| Patch A suppresses Beacon Recovery action | **PROVEN** |
| Patch A preserves legitimate fresh Recovery | **FALSE** |
| Patch B suppresses the targeted recurring mDNS restart | **PROVEN during monitored test** |
| Patch C-C preserves the intended Recovery mechanism by design | **PROVEN statically** |
| Patch C-C corrects C1a in the reviewed control path | **PROVEN statically** |
| Patch C-C prevents historical `R` from triggering a baseline-only sample | **PROVEN statically** |
| Patch C-C invalidates identified unusable logical measurement epochs | **PROVEN statically** |
| Patch C-C passed static pre-build qualification | **PROVEN** |
| Patch C-C has passed hardware qualification | **NO** |
| Patch C-C improves battery endurance | **UNKNOWN** |
| Beacon Recovery quantitative electrical cost is known | **UNKNOWN** |
| Periodic mDNS quantitative electrical cost is known | **UNKNOWN** |

---

# 58. Current Research Direction

The power-management investigation now separates four main tracks.

## Track A — Patch C-C Build and Hardware Qualification

The next step for Beacon Recovery is no longer additional speculative patch
design.

The current design has passed static pre-build qualification.

The next sequence is:

```text
growth-aware GBL build
        |
        v
independent binary verification
        |
        v
controlled hardware flash
        |
        v
functional qualification
        |
        v
long-term A/B observation
```

Hardware testing should verify:

- boot reliability
- WLAN association
- cloud connectivity
- thermostat operation
- valve/motor operation
- normal state-3 behavior
- RSSI-dependent desired skip
- Beacon Recovery after genuinely fresh qualifying evidence
- elimination of the C2 stale loop
- C1a behavior
- re-baselining after PM overrides
- reassociation/disconnect behavior
- AP restart behavior
- clock-change behavior
- interrupt responsiveness
- long-term stability

---

## Track B — First-Trigger Investigation

C2 explains the persistent loop after the first qualifying recovery.

It does not establish what caused that first recovery on the affected physical
device.

Important future evidence includes a continuous trace from:

```text
boot
```

through:

```text
first baseline
```

to:

```text
first qualifying fresh R
```

and:

```text
first Recovery
```

Relevant state should include:

- current received-beacon counter
- previous baseline
- cached `real_beacon_skip`
- `H`
- PM state
- desired beacon skip
- RSSI
- connection/association state
- relevant D3 diagnostics
- timing of PM overrides

---

## Track C — Long-Term Battery Comparison

Battery voltage remains more useful than short-term percentage changes.

Important observations include:

- battery voltage
- battery percentage
- uptime
- firmware variant
- recovery activity
- beacon statistics
- RSSI
- motor activity where available
- resets/reboots
- major network events

Cross-device comparison must remain cautious because battery cells and devices
introduce confounding factors.

Longer observation windows are required.

---

## Track D — WUP / EM2 Investigation

The conditional resource-retention path remains technically important.

However, before any modification is justified, future work should establish:

1. whether the path occurs during ordinary field operation
2. what event causes it
3. whether the resource remains retained
4. whether later WLAN activity repairs it
5. whether it produces measurable elevated current
6. whether an existing safe cleanup path exists

Until then, WUP/EM2 should remain unpatched.

---

# 59. Current Conclusion

The Shelly TRV Gen1 power-management system consists of multiple interacting
layers:

```text
application PM state
        |
        v
host driver / WUP / MCU sleep resources
        |
        v
protected WF200 power-management state
```

These layers must not be treated as equivalent.

The investigation currently establishes several separate mechanisms.

Normal connected operation uses:

```text
state 3
```

with RSSI-dependent Fast Power Save.

State 5 is:

```text
temporary
externally triggered
Fast Power Save / skip 10
```

and does not intentionally keep the host fully awake for three minutes.

A conditional lower-level WUP/resource-retention path exists, but it is
inherited from older firmware and has not been demonstrated as a normal
runtime battery-drain mechanism.

Firmware 2.2.4 adds a new automatic Beacon Recovery mechanism that temporarily
requests:

```text
state 1
Active / Always-On WLAN
```

for approximately five serviced seconds before restoring normal PM behavior.

The Recovery mechanism itself has a coherent reliability function.

The principal defects identified around it are instead:

```text
C1a
signed control-value interpretation

C1b
invalid measurement-window / baseline handling

C2
historical qualifying evidence reused after Recovery
```

C2 explains why one qualifying recovery can become a persistent approximately
minute-spaced loop without requiring a new radio anomaly on every cycle.

C1a and C1b provide host-side mechanisms capable of producing invalid first
qualifying evidence, although the exact first field trigger on the affected
physical devices remains unknown.

Periodic mDNS is a separate recurring WLAN workload.

Its recurring connected restart exists by firmware 2.1.3, changes to an
approximately 180-second gated cadence by 2.1.8, and remains present in 2.2.4.

Patch B demonstrates that the targeted mDNS restart is not required for the
observed Beacon Recovery loop.

Patch A demonstrated that the Recovery action can be isolated, but it also
removes legitimate Recovery and is therefore no longer the preferred
correction.

Patch C-C instead attempts to preserve the intended PM Recovery mechanism while
correcting:

```text
control interpretation
measurement validity
control-evidence freshness
```

Patch C-C has passed static pre-build qualification.

It has not yet passed hardware qualification.

Finally, none of these findings currently justifies describing one mechanism
as the complete historical Shelly TRV Gen1 battery-drain root cause.

Battery drain has also been observed on firmware 2.1.8.

The current evidence therefore supports a multi-mechanism investigation rather
than a single-cause explanation.

---

# Related Documents

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Periodic mDNS:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Beacon counter and baseline handling:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

`real_beacon_skip` arithmetic:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

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

The analysis includes:

- cross-version firmware comparison
- native ARM Thumb control-flow analysis
- host-side PM state analysis
- WF200 command handling
- WUP lifecycle analysis
- MCU sleep-resource handling
- beacon-statistics processing
- passive network capture
- stock and experimentally patched runtime testing
- independent static falsification of corrective patch designs

Important conclusions are checked against native instructions and control flow
rather than relying only on decompiler output.

Publicly available WF200/fullMAC information is used where necessary to
interpret host-visible WLAN interface behavior.

The protected WF200 implementation is not reproduced.

The project deliberately separates:

```text
PROVEN
STRONGLY SUPPORTED
INFERENCE
UNKNOWN
```

and distinguishes:

```text
firmware behavior
runtime observation
engineering interpretation
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