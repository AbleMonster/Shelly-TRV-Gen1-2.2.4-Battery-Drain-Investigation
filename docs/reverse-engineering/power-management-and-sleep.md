# Power Management and Sleep Analysis

## Overview

The Shelly TRV Gen1 uses several interacting power-management layers.

At minimum, the observed firmware behavior involves:

1. application-level Shelly power-management states
2. host-MCU sleep eligibility
3. WF200 WLAN power-save configuration
4. the WF200 wake/sleep handshake
5. transport and command ownership between the host and WF200

These layers are related, but they are not equivalent.

A request such as:

```text
Power save state 3
Beacon skip 20
```

does not by itself prove that the WF200 is physically sleeping for the expected
amount of time.

Likewise:

```text
WUP LOW
```

means that the host permits the WF200 to sleep.

It is not a direct indication that the WF200 has actually entered a physical
sleep state.

This distinction is central to the battery-drain investigation.

Static analysis of firmware 2.2.4 identified several host-side correctness
problems in the power-management and transport lifecycle.

These include:

- incomplete cleanup on some Final-Sleep failures
- Wake state being committed before hardware wake completion
- ambiguous command ownership after transport timeouts
- ambiguous confirmation/credit ownership
- requested PM policy being treated as selected before lower-layer success
- overlapping logical reasons for keeping the WLAN device awake
- older PM transitions being able to interfere with newer PM intent

These issues are separate from the Beacon Recovery defects documented in:

[`real-beacon-skip.md`](real-beacon-skip.md)

and:

[`recovery-mechanism.md`](recovery-mechanism.md)

The current experimental A1 firmware corrects the identified host-side PM,
ownership and transition problems while Patch C-C corrects the Beacon Recovery
measurement lifecycle.

The integrated test firmware additionally uses Silicon Labs WF200 firmware
3.18.0, which contains a relevant fix for a condition that could prevent the
device from sleeping after a power-save mode change.

The current architecture under test is therefore:

```text
Shelly application PM policy
        |
        v
A1 host PM / lifecycle corrections
        |
        v
Patch C-C Beacon Recovery corrections
        |
        v
Shelly FMAC 3.7.0
        |
        v
WF200 3.18.0
```

This provides a cleaner basis for separating host-side PM defects, radio-side
behavior and the remaining battery-drain question.

---

# Power Management Is Not One State Machine

It is useful to avoid treating "power save" as one single state.

The firmware contains several related state domains.

A simplified model is:

```text
Application PM policy
        |
        v
Shelly PM state
        |
        +----------------------+
        |                      |
        v                      v
WF200 PM request        host sleep eligibility
        |                      |
        v                      v
FMAC / WF200            EM1 / EM2 / EM3
        |
        v
WUP / transport lifecycle
        |
        v
physical radio behavior
```

The host can know what it requested.

It can know whether a command completed successfully.

It can know whether it currently permits the WF200 to sleep.

Those facts do not necessarily tell the host whether the WF200 is physically
sleeping at a particular instant.

That distinction is important throughout this document.

---

# Application Power-Management States

Shelly firmware uses application-level PM states that determine how the WLAN
subsystem and host sleep policy are configured.

The states relevant to this investigation include:

```text
State 1
State 3
State 4
State 5
```

The state numbers are Shelly application concepts.

They should not be confused directly with Silicon Labs WF200 power-save mode
numbers.

---

# State 1 — Active / Recovery State

State 1 is used when the firmware wants the WLAN subsystem available without
the normal beacon-based power-saving configuration.

During Beacon Recovery, firmware enters this state.

The observed sequence is approximately:

```text
Beacon Recovery
        |
        v
Shelly PM state 1
        |
        v
WF200 Active / Always-On request
        |
        v
deeper host sleep restricted
```

This state is temporary during normal Beacon Recovery.

The Recovery mechanism normally restores the previous application policy after
approximately five serviced seconds.

State 1 is therefore relevant to battery behavior because repeated Recovery
temporarily moves the system away from its normal low-power configuration.

---

# State 3 — Connected Beacon Power Save

State 3 is the normal connected beacon-based power-saving state observed during
TRV operation.

Typical runtime logs show transitions such as:

```text
Enter powersave state 3 (skip 20)
```

or:

```text
Enter powersave state 3 (skip 15)
```

The selected skip value is dynamic.

It can change with the normal Shelly signal-strength policy.

For example, runtime testing has shown:

```text
desired_beacon_skip = 20
```

and later:

```text
desired_beacon_skip = 15
```

without loss of WLAN connectivity.

The normal 2.2.4 configuration associated with this state uses WF200 beacon
power save with Fast Power Save strategy.

A common request is equivalent to:

```text
mode            = Beacon Power Save
strategy        = Fast Power Save
listen_interval = 20
```

The exact WF200 command representation is discussed below.

---

# State 4

State 4 participates in the Shelly power-management state machine and related
sleep handling.

It is not the main focus of the current battery-drain mechanism.

The important point for this investigation is that application PM state and
physical WLAN sleep are separate concepts.

A state transition can select a policy and initiate lower-layer work without
that application state itself being proof of the final physical radio state.

---

# State 5

State 5 also participates in the wider Shelly PM logic.

Earlier analysis investigated whether state 5 represented a simple direct
mapping to a specific WF200 sleep state.

The current evidence does not justify such a simple interpretation.

The application states coordinate multiple host and WLAN actions.

For battery analysis, it is therefore safer to reason from the actual
lower-layer operations than from the application state number alone.

---

# WF200 Power-Management Command `0x52`

The Shelly host configures WF200 WLAN power management through command:

```text
0x52
```

The command contains several policy fields.

The relevant fields include:

```text
mode
strategy
listen_interval
idle_timeout
```

The known mode values include:

```text
0 = Active
1 = Beacon Power Save
2 = DTIM Power Save
```

The known strategy values include:

```text
0 = U-APSD
1 = Fast Power Save
```

The listen interval is represented as a little-endian 16-bit value.

A normal Shelly TRV 2.2.4 connected configuration is approximately:

```text
mode            = 1
strategy        = 1
listen_interval = 20
idle_timeout    = 0
```

or conceptually:

```text
Beacon Power Save
Fast Power Save
listen interval 20
default idle timeout
```

The newer command representation contains an idle-timeout field.

A value of:

```text
0
```

uses the default behavior, corresponding to approximately:

```text
20 ms
```

in the relevant Silicon Labs interface.

---

# Requested PM Policy vs. Effective Physical State

One of the most important distinctions in this investigation is:

```text
PM request accepted
```

does not necessarily mean:

```text
radio is physically sleeping now
```

A successful `0x52` transaction tells the host that the command completed with
the returned status.

It does not provide a direct measurement of radio sleep residency.

Conceptually:

```text
Host
 |
 | PM52:
 | Beacon PS
 | Fast PS
 | listen interval 20
 v
WF200
 |
 | confirmation
 v
Host
```

The confirmation establishes command completion.

It does not establish:

```text
the WF200 slept for N beacon periods
```

or:

```text
the WF200 is currently in a low-power hardware state
```

This limits what can be inferred from the host logs.

---

# Wake / Sleep Handshake

The WF200 host interface includes a wake/sleep handshake involving the WUP
signal and corresponding host-side state.

Conceptually:

```text
host needs WF200
        |
        v
assert wake request
        |
        v
wait for device availability
        |
        v
perform transport / register work
        |
        v
release final wake requirement
        |
        v
permit WF200 sleep
```

This lifecycle must remain consistent with:

- command ownership
- pending confirmations
- PM transitions
- association state
- transport activity
- host sleep eligibility

The firmware defects identified during the A1 analysis occur in several parts
of this lifecycle.

---

# WUP LOW Does Not Prove Physical Sleep

A particularly important distinction is:

```text
WUP LOW
```

does not mean:

```text
WF200 is definitely sleeping
```

It means that the host is no longer asserting the wake request.

In other words:

```text
WUP LOW
```

permits the WF200 to sleep when its internal state allows it.

The WF200 may still have internal reasons to remain active.

Therefore the following inference is not justified:

```text
WUP LOW
    |
    v
WF200 physically asleep
```

The supported interpretation is:

```text
WUP LOW
    |
    v
host permits WF200 sleep
```

This distinction becomes particularly relevant when evaluating the Silicon
Labs WF200 3.18.0 sleep-related fix.

---

# Final Sleep

The host contains a Final-Sleep path that releases the final host-side
requirement keeping the WF200 awake.

This operation is not simply a software flag change.

It participates in hardware and transport state.

A simplified intended lifecycle is:

```text
host owns wake requirement
        |
        v
complete required WLAN work
        |
        v
Final-Sleep
        |
        v
release hardware / transport state
        |
        v
host no longer requires WF200 awake
```

Static analysis of stock 2.2.4 found failure paths where this lifecycle is not
completed consistently.

This became the first major host-PM correctness issue addressed by A1.

---

# G01 — Final-Sleep Failure Cleanup

Some stock Final-Sleep paths perform register read/modify/write operations while
holding lower-layer state required for the transaction.

If one of these operations fails, the stock error path can return before the
full expected cleanup/release sequence has completed.

The problem is not simply:

```text
a register operation failed
```

The problem is:

```text
operation failed
        |
        v
function returned
        |
        v
ownership / release state may no longer match
the normal completed lifecycle
```

A failure path in low-power coordination must leave the system in a known
ownership state.

Continuing after partial cleanup can otherwise create a host/WF200 state
mismatch.

A1 corrects the affected lifecycle so that failure cannot silently continue
with ambiguous ownership.

---

# G02 — Wake State Committed Too Early

The stock Wake path contains the opposite type of problem.

Software state indicating that Wake has occurred can be updated before all
hardware wake/grant/register operations have successfully completed.

Conceptually, the problematic ordering is:

```text
software says "awake"
        |
        v
perform hardware wake work
        |
        X
failure
```

If the lower operation fails after the software state was already committed,
a later Wake request can observe:

```text
already awake
```

and skip work that was never successfully completed.

This creates a partial-transition problem.

The safer lifecycle is:

```text
wake requested
        |
        v
perform required lower-layer wake work
        |
        v
lower-layer success
        |
        v
commit software state
```

or otherwise enter an explicit failure state that cannot be mistaken for a
completed Wake.

A1 enforces this distinction.

---

# G03 and G05 — Transport and Confirmation Ownership

WF200 communication is asynchronous.

A host timeout does not necessarily mean that the WF200 never received or
executed the command.

A simplified transaction can look like:

```text
Host sends command
        |
        v
WF200 receives command
        |
        v
WF200 processes command
        |
        v
confirmation returns
```

If the host times out before receiving the confirmation:

```text
Host sends command
        |
        v
WF200 may consume command
        |
        v
Host timeout
        |
        v
confirmation may still arrive later
```

The host therefore cannot safely assume:

```text
timeout = command cancelled
```

This is particularly important where transport credits, transaction IDs and
confirmation ownership are reused.

After an ambiguous timeout, the system may no longer know whether:

- the WF200 consumed the request
- a confirmation is still pending
- a transport credit is still owned
- a transaction identifier can safely be reused
- the lower-layer state changed

Blind retry or reuse can turn one timeout into a larger ownership problem.

A1 therefore treats ambiguous command ownership conservatively.

Where the transaction cannot be reconciled safely, the design closes further
admission and enters a controlled non-returning whole-host reset path rather
than replaying or reusing ambiguous state.

This is intentionally fail-stop behavior.

It avoids pretending that a timed-out asynchronous transaction was cancelled.

---

# Why Timeout Is Not Cancellation

This distinction is fundamental enough to state separately:

```text
timeout
```

means:

```text
the host did not receive the expected completion in time
```

It does not necessarily mean:

```text
the WF200 did not receive the request
```

and it does not necessarily mean:

```text
the WF200 did not change state
```

For PM operations this matters because a host can otherwise believe one policy
is active while the WF200 has already accepted another.

Correct power-management behavior therefore depends not only on the PM command
contents but also on transaction ownership and completion semantics.

---

# G06 — Requested Policy vs. Confirmed Policy

Stock firmware can update software policy state before the corresponding
lower-layer operation has successfully completed.

Conceptually:

```text
request new PM policy
        |
        v
software records policy as selected
        |
        v
send lower-layer PM request
        |
        X
failure
```

After failure, software state can then describe what was requested rather than
what was successfully established.

This is a classic desired-state versus confirmed-state problem.

A1 separates these concepts.

The corrected model is approximately:

```text
desired policy
        |
        v
transition in progress
        |
        v
lower-layer PM operation
        |
        +---- success
        |       |
        |       v
        |   confirmed policy
        |
        +---- failure / ambiguity
                |
                v
        explicit failure handling
```

This prevents an unsuccessful PM transition from silently becoming the
software's authoritative state.

---

# G18 — Independent Sleep-Inhibit Ownership

Several independent activities can require the WLAN device to remain awake.

Examples include:

```text
ACTIVE policy
PM transition
JOIN / association lifecycle
```

These are logically separate ownership reasons.

Treating them as one undifferentiated wake state creates a risk that one path
can release a wake requirement still needed by another.

The corrected A1 model therefore treats them as independent logical claims.

Conceptually:

```text
ACTIVE claim --------+
                     |
PM transition claim -+----> sleep inhibited
                     |
JOIN claim ----------+
```

Removing one claim removes only that reason.

For example:

```text
JOIN completes
```

must not implicitly mean:

```text
all other wake requirements are gone
```

Final-Sleep becomes eligible only when the complete ownership state allows it.

This makes the wake/sleep lifecycle substantially easier to reason about.

---

# G19 — PM Transition Generation

Another host-side issue appears when multiple PM requests overlap in time.

For example:

```text
old request:
enter Power Save
```

can still be completing when a newer request says:

```text
remain Active
```

Without transition ownership, the older completion path can continue and
perform actions such as Final-Sleep after the newer policy request has already
changed the desired state.

Conceptually:

```text
generation N
Power Save transition
        |
        | delayed completion
        |
        +--------------------+
                             |
generation N+1               |
Active requested             |
        |                    |
        v                    |
new desired policy           |
                             v
                    old Final-Sleep
```

The older operation must not be allowed to commit or finalize state belonging
to a superseded policy.

A1 therefore associates PM transitions with generation/ownership state.

Before an older operation commits policy or performs final sleep actions, it
must still own the current transition.

If not, it is stale and must not overwrite the newer intent.

---

# A1 Host Power-Management Model

A1 is not a new power-saving algorithm.

Its purpose is to make the existing host/WF200 lifecycle internally
consistent.

The main model is:

```text
desired PM policy
        |
        v
new transition generation
        |
        v
acquire required logical sleep-inhibit claim
        |
        v
perform Wake / transport / PM operation
        |
        +-------------------------+
        |                         |
        v                         v
success                    failure / ambiguity
        |                         |
        v                         v
confirm ownership          do not fake completion
        |                         |
        v                         v
publish confirmed state    controlled failure handling
        |
        v
release only claims
owned by this transition
        |
        v
Final-Sleep only if still
eligible under current generation
```

The key properties are:

- desired policy is not the same as confirmed policy
- timeout is not cancellation
- ambiguous transport ownership is not reused
- independent wake reasons have independent ownership
- stale PM generations cannot commit newer state
- Final-Sleep occurs only when current ownership permits it
- partial Wake cannot masquerade as completed Wake

This is a correctness patch around the existing Shelly PM architecture.

---

# Why A1 Uses Conservative Failure Handling

A tempting response to a failed WLAN command is:

```text
retry it
```

That is not always safe with an asynchronous transport.

If the host cannot determine whether the WF200 consumed the original command,
repeating the same transaction can create:

- duplicate commands
- late confirmations
- transaction-ID confusion
- credit imbalance
- mismatched PM state

A1 therefore does not assume that ambiguous operations can safely be replayed.

When ownership cannot be recovered deterministically, the conservative path is
to stop admitting new work and perform a whole-host reset.

This is intentionally different from trying to perform an unqualified
WF200-only reset.

No sufficiently qualified production path was identified that guarantees a
WF200-only reset can reconstruct all host/FMAC/transport ownership after an
ambiguous transaction.

---

# D3 `PS_MODE_ERROR`

WF200 exposes a host-visible power-save error indication through:

```text
D3 PS_MODE_ERROR
```

Known reason values include:

```text
Reason 0
PS-Poll timeout

Reason 1
U-APSD timeout

Reason 2
buffered unicast not delivered across consecutive beacons

Reason 3
unstable beacon timing / beacon-window compensation
```

This is important because D3 represents a direct WF200-generated PM error
channel.

That makes it fundamentally different from Shelly's:

```text
real_beacon_skip
```

which is calculated by the host from received-beacon statistics.

---

# Firmware Handling of D3

Firmware versions differ in how much visibility they provide for this
indication.

The older 2.1.0 firmware does not expose a dedicated D3 handling path in the
same way.

Firmware 2.2.4 parses and logs the reason information.

However, no dedicated corrective control path was identified that says:

```text
D3 PS_MODE_ERROR
        |
        v
perform Shelly Beacon Recovery
```

The Beacon Recovery mechanism instead operates from the host-derived
`real_beacon_skip` heuristic.

This distinction was later tested directly at runtime.

---

# Long-Term Parallel D3 Observation

A dedicated D3-observer build was created while leaving the normal Shelly
Beacon Recovery and PM behavior active.

This allowed two channels to be observed in parallel:

```text
Shelly host-side path

beacon statistics
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery
```

and:

```text
WF200 path

WF200 PM error
        |
        v
D3 PS_MODE_ERROR
        |
        v
D3 observer
```

At the latest observation point, the device had accumulated approximately:

```text
Runtime:                 230144 s
                         63.93 h
                         2.66 days

Beacon Recovery events: 3835
Recovery rate:           ~59.99/hour

desired_beacon_skip:     20
real_beacon_skip:        1

D3 PS_MODE_ERROR:        0

reboot_counter:          1
reconnect_counter:       1
```

The stock Beacon Recovery rate is effectively one event per minute.

During the same approximately 63.9-hour period:

```text
D3 PS_MODE_ERROR = 0
```

More than 3,800 Shelly Beacon Recoveries therefore occurred without one
observed event on the known direct WF200 `PS_MODE_ERROR` channel.

This is an important experimental result.

It does not prove that the WF200 had no internal issue.

It does not prove that the radio was physically sleeping correctly.

It does establish that the repeated Shelly Beacon Recovery events were not
accompanied by reported D3 `PS_MODE_ERROR` events during this observation.

No observed Beacon Recovery can therefore be tied to a reported D3 PM error in
this test.

Likewise, no D3 error can be shown to have been cleared by Beacon Recovery,
because no D3 error was observed.

---

# Beacon Recovery and PM State

Beacon Recovery temporarily changes the normal PM configuration.

The observed normal sequence is approximately:

```text
State 3
Beacon Power Save
Fast Power Save
desired skip N
        |
        | Recovery
        v
State 1
Active / Always-On
        |
        | approximately 5 s
        v
State 3
Beacon Power Save
Fast Power Save
desired skip N
```

During the Recovery interval:

- WF200 Active / Always-On is requested
- deeper host sleep is restricted
- additional host/WLAN PM work occurs

This makes repeated Recovery relevant to battery consumption.

The detailed trigger and C1a/C1b/C2 analysis is intentionally kept in:

[`recovery-mechanism.md`](recovery-mechanism.md)

and:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

# Stock Recovery Occupancy

The long-running D3 observer provides a useful measurement of the stock
2.2.4 Recovery loop.

Approximately:

```text
3835 Recoveries
```

occurred over:

```text
63.93 hours
```

which is:

```text
~59.99 Recoveries/hour
```

At approximately five seconds per Recovery:

```text
60 × ~5 s
= ~300 s/hour
= ~5 min/hour
≈ 8.33% of wall-clock time
```

Across the complete observation period:

```text
3835 × ~5 s
= ~19175 s
= ~319.6 min
= ~5.33 h
```

of explicit Recovery time accumulated.

These are wall-clock figures.

They are not battery-consumption percentages.

No electrical current measurement was performed.

---

# Patch C-C Recovery Occupancy

Patch C-C prevents historical `real_beacon_skip` from repeatedly acting as
fresh Recovery evidence.

With the currently observed periodic measurement cadence, the first successful
sample after Recovery establishes a new baseline.

A later comparable sample is required before another fresh
`real_beacon_skip` can be calculated.

If every newly calculated value qualifies, the current schedule therefore
allows approximately:

```text
30 fresh-triggered Recoveries/hour
```

rather than the stock stale-loop rate of approximately:

```text
60 Recoveries/hour
```

At approximately five seconds each:

```text
30 × ~5 s
= ~150 s/hour
= ~2.5 min/hour
≈ 4.17% of wall-clock time
```

This is a cadence-dependent theoretical maximum.

It is not a universal C-C limit.

The approximately 30/hour C-C limit is not considered an optimized Recovery
rate. It is a consequence of the current measurement cadence and the
requirement for a fresh post-Recovery baseline. Further rate limiting is under
consideration, but no technically justified minimum Recovery frequency has yet
been established.

During the current integrated A1 + C-C + WF200 3.18.0 test, approximately:

```text
27 fresh-triggered Recoveries/hour
```

were observed over a multi-hour interval.

That corresponds to approximately:

```text
27 × ~5 s
= ~135 s/hour
= ~2.25 min/hour
≈ 3.75% of wall-clock time
```

Again, these values describe Recovery occupancy, not electrical energy.

---

# Recovery Frequency as a Trade-Off

Reducing Recovery frequency is not automatically equivalent to improving
battery life.

There are two competing effects.

The first effect is directly observable:

```text
more Recoveries
        |
        v
more explicit Active / Recovery time
```

The second effect is hypothetical:

```text
if an unknown WF200 condition exists
that leaves the radio awake
        |
        v
less frequent Recovery
        |
        v
that condition could remain active longer
before Recovery corrects it
```

The second case has not been demonstrated.

It is included here because it is important when deciding whether Beacon
Recovery should simply be disabled or heavily rate-limited.

Assume, purely as a working hypothesis, that:

1. an unknown WF200 failure can leave the radio in an undesired awake state,
2. this condition is not reported through D3,
3. the host's periodic Recovery check can detect the condition,
4. and performing Beacon Recovery reliably clears it.

Under those assumptions, Recovery frequency becomes a trade-off between
guaranteed Recovery overhead and the possible lifetime of the hypothetical
fault.

For example:

| Recovery rate | Check / Recovery interval | Explicit Recovery time per hour | Maximum hypothetical undetected fault time | Average hypothetical fault time* |
|---:|---:|---:|---:|---:|
| 60/hour | 1 min | ~300 s = 5 min | ~1 min | ~30 s |
| 30/hour | 2 min | ~150 s = 2.5 min | ~2 min | ~1 min |
| 4/hour | 15 min | ~20 s | ~15 min | ~7.5 min |

\*Assuming the hypothetical fault occurs randomly and uniformly between two
effective detection opportunities.

This table deliberately compares two different quantities.

The Recovery time is based on the observed approximately five-second Active
Recovery interval.

The fault-duration columns are hypothetical.

They are not measurements of the current TRV behavior.

For example, reducing Recovery to only:

```text
4 times/hour
```

would reduce the guaranteed explicit Recovery overhead to approximately:

```text
4 × 5 s
= 20 s/hour
```

That appears attractive when looking only at Recovery occupancy.

However, under the hypothetical failure model above, a fault occurring
immediately after a check could then remain undetected for almost:

```text
15 minutes
```

with an average detection delay of approximately:

```text
7.5 minutes
```

By comparison, with an effective two-minute interval:

```text
maximum delay ≈ 2 minutes
average delay ≈ 1 minute
```

The trade-off can therefore be summarized as:

```text
higher Recovery frequency
        |
        +---- more guaranteed Recovery overhead
        |
        +---- shorter lifetime of a hypothetical
              fault that Recovery can actually correct
```

versus:

```text
lower Recovery frequency
        |
        +---- less guaranteed Recovery overhead
        |
        +---- potentially longer lifetime of a
              hypothetical correctable fault
```

This is one reason Patch C-C currently takes a conservative approach.

It removes the demonstrated stale self-triggering loop but does not arbitrarily
reduce fresh Recovery to a very low rate.

With the currently observed measurement cadence, C-C changes the pathological
stock behavior from approximately:

```text
one Recovery every minute
```

to at most approximately:

```text
one fresh-triggered Recovery every two minutes
```

when every newly calculated measurement continues to qualify.

This approximately halves the guaranteed explicit Recovery occupancy while
still retaining relatively frequent opportunities to correct a real condition
if such a condition exists.

The long-running D3 result is important here:

```text
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

There is currently no evidence that those Recoveries were correcting a known
WF200-reported PM error.

However, D3 is not complete physical sleep telemetry.

The current evidence therefore does not justify either extreme conclusion:

```text
Beacon Recovery is definitely required
```

or:

```text
Beacon Recovery is definitely unnecessary
```

A future controlled experiment with Recovery disabled or deliberately
rate-limited would be useful for testing this hypothesis.

Until then, the C-C approach keeps the fresh Recovery mechanism while removing
the demonstrated invalid/stale behavior.

---

# C-C Does Not Remove Fresh Recovery

Patch C-C deliberately does not disable all Beacon Recovery.

Its corrected lifecycle is:

```text
fresh valid R = 1/2
        |
        v
Recovery
        |
        v
measurement baseline invalidated
        |
        v
next sample establishes baseline
        |
        v
no Recovery from old R
        |
        v
later comparable sample
        |
        v
fresh R
        |
        +---- non-qualifying -> normal operation
        |
        +---- R = 1/2       -> new Recovery
```

This behavior has been observed on hardware.

The continued presence of fresh Recovery is therefore not evidence that C-C
failed.

It means that the host beacon-density estimator still sometimes produces a
fresh value satisfying the retained Recovery condition.

Whether that fresh condition represents a real WF200 PM problem remains open.

---

# Why `real_beacon_skip` Is Not a PM Readback

Shelly exposes:

```text
desired_beacon_skip
```

and:

```text
real_beacon_skip
```

through the statistics path.

The names can suggest:

```text
desired = requested value
real    = actual WF200 value
```

That interpretation is not supported by the implementation.

`real_beacon_skip` is calculated by the host from received-beacon counts.

It is therefore an estimate based on observed beacon density.

It is not a direct readback of:

- WF200 listen interval
- WF200 PM mode
- WF200 internal sleep state
- physical radio sleep residency

For example:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not establish:

```text
WF200 accepted skip 1
```

or:

```text
WF200 remained continuously awake
```

It establishes only that the Shelly estimator derived `1` from the observed
measurement window.

---

# The Estimator Can Also Produce Higher Values

The current integrated hardware test has shown that `real_beacon_skip` is not
permanently stuck at `1`.

Earlier runtime values included:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

while a later observation showed:

```text
desired_beacon_skip = 15
real_beacon_skip    = 13
```

The host estimator is therefore capable of producing a value close to the
currently requested skip.

This is useful evidence against a simplistic interpretation that the estimator
is permanently broken at a fixed low value.

It still does not turn the estimate into a direct physical PM measurement.

---

# WF200 3.18.0

Silicon Labs released WF200 firmware 3.18.0 with a particularly relevant LMAC
fix:

```text
Fixed an error that was preventing the device from sleeping
after a power-save mode change
```

This is directly relevant to the class of behavior under investigation.

The Shelly TRV repeatedly changes WF200 power-save mode during operations such
as Beacon Recovery.

The fix therefore addresses a failure class that could plausibly affect a
battery-powered device performing repeated PM transitions.

It is important not to overstate this result.

The changelog does not establish that this Silicon Labs defect caused the
Shelly TRV Gen1 battery-drain problem.

It also does not establish that every older WF200 PM transition failed.

The correct conclusion is narrower:

> WF200 3.18.0 contains an official Silicon Labs fix for a failure that could
> prevent the device from sleeping after a power-save mode change.

That makes the update technically relevant to this investigation.

---

# WF200 3.18.0 Does Not Fix the Host Stale-Recovery Loop

WF200 3.18.0 was first tested while keeping the stock Shelly 2.2.4 host
Recovery behavior.

The stock approximately once-per-minute Beacon Recovery loop continued.

This is expected.

The C2 stale-evidence loop exists in Shelly host firmware.

Updating the WF200 radio firmware cannot correct host logic that repeatedly
reuses historical Recovery evidence.

This gives a useful separation:

```text
WF200 3.18.0
        |
        +---- can correct radio-side WF200 behavior
        |
        X
        cannot correct Shelly host C2 logic
```

The combined experiment therefore requires both host-side and radio-side
corrections.

---

# Shelly FMAC 3.7.0 and WF200 3.18.0

Shelly firmware 2.2.4 uses FMAC driver:

```text
3.7.0
```

The experimental WF200 3.18.0 integration preserves the Shelly host FMAC
version.

Physical hardware testing has confirmed that this combination reaches normal
operation:

```text
Shelly FMAC 3.7.0
        +
WF200 firmware 3.18.0
        |
        v
WF200 initialization
        |
        v
scan
        |
        v
join
        |
        v
DHCP
        |
        v
cloud
        |
        v
normal PM operation
```

This does not constitute a vendor compatibility guarantee.

It does establish that the combination operates on the tested Shelly TRV Gen1
hardware through the normal WLAN startup and PM path.

---

# Current Integrated Firmware

The current experimental firmware combines:

```text
A1
+
Patch C-C
+
WF200 3.18.0
```

The components address different layers.

A1 addresses host correctness:

```text
Wake
Final-Sleep
transport ownership
confirmation ownership
desired vs confirmed PM state
sleep-inhibit ownership
PM transition generations
```

Patch C-C addresses Beacon Recovery evidence:

```text
signed interpretation
measurement-window validity
stale post-Recovery evidence
```

WF200 3.18.0 addresses the radio firmware layer and includes the Silicon Labs
sleep-after-PM-change fix.

These components should not be treated as three versions of the same patch.

They address different failure domains.

---

# Current Hardware Qualification

The integrated:

```text
A1 + C-C + WF200 3.18.0
```

firmware has been tested on physical Shelly TRV Gen1 hardware.

The device successfully completed:

```text
OTA
 |
 v
cold reboot
 |
 v
host startup
 |
 v
FMAC 3.7.0 initialization
 |
 v
WF200 3.18.0 initialization
 |
 v
scan
 |
 v
join
 |
 v
connected state
 |
 v
PM operation
 |
 v
DHCP
 |
 v
cloud operation
```

Additional application behavior has also been exercised:

- thermostat operation
- valve movement
- manual calibration
- successful calibration completion
- target-temperature changes
- RSSI-dependent beacon-skip selection
- repeated PM state transitions

During the initial approximately eight-hour qualification period:

```text
reboot_counter    = 1
reconnect_counter = 1
```

No additional reboot or WLAN reconnect occurred.

This is an important integration result.

It rules out many gross failure modes such as:

- immediate host crash
- boot loop
- broken WF200 firmware relocation
- basic FMAC/WF200 initialization incompatibility
- basic association failure
- obvious PM deadlock
- obvious valve-control breakage

It does not yet establish long-term battery performance.

---

# Current Integrated PM Behavior

The integrated test still shows fresh Beacon Recovery events.

During the initial multi-hour observation:

```text
~27 Recoveries/hour
```

were measured.

At the same time:

```text
reboot_counter    = 1
reconnect_counter = 1
```

remained unchanged.

The system therefore continued normal WLAN and application operation while
fresh host-estimator Recovery events occurred.

This is useful because it separates several questions.

A1 correctness does not automatically make:

```text
real_beacon_skip
```

stop producing low values.

WF200 3.18.0 also does not automatically make Shelly's host-side beacon
heuristic disappear.

The current result is therefore:

```text
known host PM correctness issues corrected
        +
known C-C Recovery-evidence issues corrected
        +
newer WF200 firmware installed
        |
        v
fresh low host beacon estimates still occur
```

The significance of those fresh estimates remains an open question.

---

# What the Available Interfaces Can Tell Us

The host can observe several useful pieces of information.

These include:

```text
requested PM policy
```

```text
PM command completion / status
```

```text
WUP / wake-handshake state
```

```text
received-beacon statistics
```

```text
D3 PS_MODE_ERROR
```

```text
application PM state
```

These are valuable.

They are not equivalent to direct physical sleep measurement.

---

# What the Available Interfaces Do Not Prove

No production interface identified during this investigation provides a direct
continuous measurement of:

```text
WF200 physical sleep residency
```

Therefore the following statements require caution.

A successful PM52 confirmation does not prove:

```text
the WF200 physically slept
```

WUP LOW does not prove:

```text
the WF200 physically slept
```

`real_beacon_skip = 1` does not prove:

```text
the WF200 remained awake
```

`real_beacon_skip = 20` does not prove:

```text
the WF200 slept exactly 20 beacon periods
```

absence of D3 `PS_MODE_ERROR` does not prove:

```text
all internal WF200 PM behavior was correct
```

and presence of a Beacon Recovery does not prove:

```text
the WF200 reported a PM failure
```

These distinctions are necessary to avoid assigning physical meaning to
host-visible values that they do not directly contain.

---

# Why This Matters for Battery Analysis

Battery life depends on the actual time spent in electrical power states.

The host firmware mostly exposes:

- requested policy
- software state
- command completion
- indirect statistics
- error indications

It does not expose direct radio current or physical sleep residency.

A battery-drain investigation therefore cannot rely on one software counter
alone.

The current project instead combines:

```text
static firmware analysis
        +
runtime logs
        +
PM state transitions
        +
WF200 error observation
        +
beacon statistics
        +
battery-voltage trends
        +
controlled firmware variants
```

This allows incorrect host behavior to be demonstrated even where direct
electrical sleep measurement is unavailable.

---

# Battery Voltage and Percentage

Battery percentage is useful as a coarse user-facing indicator.

It is not a precise energy measurement.

Voltage is therefore treated as the primary long-term battery metric in the
current experiments, with percentage used as secondary information.

Even voltage must be interpreted carefully.

It can vary with:

- load
- valve movement
- temperature
- recent charging
- relaxation after charging
- radio activity

For this reason, short-term voltage changes should not be linearly extrapolated
into battery lifetime.

Longer observation periods are required.

---

# Valve Activity Is a Major Confounder

The TRV motor can represent a substantial load compared with normal idle
operation.

Battery comparisons must therefore account for:

- calibration
- valve movement
- target-temperature changes
- heating demand
- mechanical travel

For example, a device that performs calibration and several large valve
movements shortly after charging cannot be compared directly with a stationary
reference using only a short battery-voltage interval.

Long-term field testing is intended to average these effects while retaining a
stock control device for comparison.

---

# Recovery Time Is Not Battery Percentage

The Recovery occupancy calculations are useful but must not be misinterpreted.

For example:

```text
Stock:

60 Recoveries/hour
× ~5 s
= ~300 s/hour
≈ 8.33% wall-clock time
```

does not mean:

```text
8.33% more battery consumption
```

Likewise:

```text
C-C current-cadence worst case:

30 Recoveries/hour
× ~5 s
= ~150 s/hour
≈ 4.17% wall-clock time
```

does not mean:

```text
4.17% more battery consumption
```

The electrical current in each state has not been measured.

What can be said is that Recovery:

- requests a less power-saving WLAN state
- restricts deeper host sleep
- causes additional control activity

and therefore creates a credible additional energy workload.

Its exact energy cost remains unknown.

The opposite side of the equation must also be kept in mind.

If a currently unknown radio condition can leave the WF200 awake and Recovery
actually corrects that condition, reducing Recovery frequency too far could
increase the duration of the real high-power condition even while reducing the
known Recovery overhead.

This remains a hypothesis, not an observed result.

---

# Why the D3 Result Is Important for PM Interpretation

The D3-observer experiment provides a useful negative result.

During approximately:

```text
63.93 h
```

the device generated:

```text
3835 Shelly Beacon Recoveries
```

while:

```text
D3 PS_MODE_ERROR = 0
```

This means that the observed Recovery loop cannot be described as:

```text
3835 WF200-reported PM errors
```

That interpretation would be incorrect.

Instead, the observed data show:

```text
Shelly host beacon heuristic
        |
        v
3835 Recovery events
```

while:

```text
WF200 D3 PM-error channel
        |
        v
0 events
```

This is one of the strongest reasons to keep the Beacon Recovery heuristic
separate from direct WF200 PM error handling.

At the same time, D3 is not a continuous physical sleep monitor.

The absence of D3 errors therefore does not by itself prove that no other
internal WF200 state could benefit from Recovery.

---

# Is Beacon Recovery Required for Correct PM?

This remains unresolved.

The Recovery sequence is now understood.

The host estimator is understood.

The stale-value loop is understood.

What has not been demonstrated is that a fresh:

```text
real_beacon_skip = 1
```

or:

```text
real_beacon_skip = 2
```

represents a WF200 condition that requires:

```text
Active
        |
        v
Power Save
```

to be reapplied.

The long-running D3 observation makes this question more significant.

More than 3,800 Recoveries occurred without a single observed D3
`PS_MODE_ERROR`.

That does not prove the Recovery mechanism is unnecessary.

It means that the currently available evidence does not identify a direct
WF200-reported error that explains those repeated Recoveries.

There is also an important experimental trade-off.

If Recovery is completely disabled and an unknown non-D3 WF200 fault really
does leave the radio awake, that fault could persist indefinitely or until some
other PM transition occurs.

If Recovery is merely made very infrequent, the same hypothetical fault could
remain active for a correspondingly longer time.

For this reason, C-C deliberately retains fresh Recovery while removing only
invalid and stale evidence.

A later controlled no-Recovery or rate-limited experiment can test the
necessity question separately.

---

# Why Recovery Was Not Removed from the Integrated Firmware

The purpose of the current integrated firmware is to remove demonstrated
defects while changing as little unproven behavior as practical.

Completely disabling Beacon Recovery would introduce another experimental
variable.

If battery behavior changed, it would then be harder to separate:

```text
A1 host correctness
```

from:

```text
C-C evidence correction
```

from:

```text
WF200 3.18.0
```

from:

```text
complete Recovery removal
```

There is also a second reason to retain it.

If the Recovery heuristic is indirectly detecting a real WF200 condition that
is not exposed through D3, disabling Recovery could make the resulting
high-power state last longer.

That possibility has not been demonstrated, but it cannot currently be ruled
out.

The current firmware therefore retains Recovery for fresh valid evidence.

This makes the long-term test more conservative.

---

# Historical Firmware Context

Battery drain has been observed on both:

```text
2.1.x
```

and:

```text
2.2.4
```

This is important.

The aggressive 2.2.4 Beacon Recovery implementation cannot by itself explain
the complete historical TRV Gen1 battery-drain problem.

The current working model therefore distinguishes:

```text
common underlying mechanisms
```

from:

```text
2.2.4-specific amplifiers
```

Beacon Recovery can be a 2.2.4-specific amplifier without being the original
root cause.

The host PM and transport correctness findings are especially relevant because
some related architecture is shared across firmware generations.

A detailed firmware comparison is maintained separately in:

[`firmware-comparison.md`](firmware-comparison.md)

---

# Current Power-Management Model

The current high-level model is:

```text
Application requests PM policy
        |
        v
desired policy
        |
        v
A1 transition generation
        |
        v
acquire required sleep-inhibit ownership
        |
        v
Wake if required
        |
        v
perform transport operation
        |
        v
WF200 PM52 request
        |
        +------------------------------+
        |                              |
        v                              v
successful completion           failure / ambiguity
        |                              |
        v                              v
publish confirmed state         do not fake completion
        |                              |
        v                              v
release owned claims            controlled failure path
        |
        v
Final-Sleep if current
generation still permits it
        |
        v
WUP can be released
        |
        v
WF200 permitted to sleep
```

This describes host correctness.

It still does not directly measure:

```text
physical WF200 sleep residency
```

The radio remains responsible for its internal power-management behavior after
the host has provided a valid policy and released the wake requirement.

---

# Current Experimental Stack

The current corrected experimental stack is:

```text
Shelly TRV 2.2.4 application
        |
        v
A1
Host PM / transport correctness
        |
        v
Patch C-C
Beacon Recovery evidence correctness
        |
        v
Shelly FMAC 3.7.0
        |
        v
WF200 3.18.0
Silicon Labs radio firmware
```

Each layer has a different purpose.

### A1

Corrects demonstrated host-side lifecycle problems involving:

```text
Wake
Final-Sleep
transport ownership
confirmation ownership
PM policy publication
sleep-inhibit ownership
transition generations
```

### Patch C-C

Corrects:

```text
signed Recovery interpretation
measurement-window validity
stale post-Recovery evidence
```

while retaining fresh valid Recovery.

### WF200 3.18.0

Provides the newer Silicon Labs radio firmware including the fix for:

```text
device not sleeping after a power-save mode change
```

The long-term battery test evaluates this stack as one integrated corrected
candidate.

---

# Current Runtime Result

The current integrated device has shown:

```text
successful boot
successful WF200 3.18.0 initialization
successful WLAN association
successful DHCP
successful cloud connection
successful PM transitions
successful calibration
successful valve operation
```

and during the initial approximately eight-hour qualification period:

```text
reboot_counter    = 1
reconnect_counter = 1
```

Fresh Beacon Recovery continues to occur.

During the initial multi-hour interval, the rate was approximately:

```text
27 Recoveries/hour
```

The latest statistics also showed that the host estimator can produce:

```text
desired_beacon_skip = 15
real_beacon_skip    = 13
```

rather than remaining permanently at `1`.

This combination is useful:

```text
host PM corrections operate
WF200 3.18.0 operates
C-C freshness correction operates
fresh estimator variation remains
```

The remaining fresh Recovery behavior therefore deserves separate study rather
than being automatically classified as failure of the integrated patch.

---

# Long-Term Test Strategy

The current long-term test is intended to compare corrected firmware against a
stock control under normal heating operation.

The planned field configuration keeps at least one stock 2.2.4 device while
other devices can run the integrated corrected firmware.

Devices are charged individually and assigned separate test start points.

Daily sampling is preferred over frequent polling to reduce measurement
perturbation.

Useful daily values include:

```text
battery voltage
battery percentage

uptime
reboot counter
reconnect counter

valve position
target temperature
measured temperature

desired_beacon_skip
real_beacon_skip
beacon_err_counter
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
sleep_ratio

host firmware
WF200 firmware
```

Primary comparisons include:

```text
mV/day
Recovery events/hour
beacon receive rate
reboot/reconnect behavior
```

Battery percentage is retained as secondary information.

---

# Remaining Questions

The main PM questions are now narrower than at the beginning of the
investigation.

## 1. Does the corrected integrated firmware improve long-term battery life?

The initial hardware qualification establishes functionality.

It does not yet establish battery lifetime.

---

## 2. What causes the remaining fresh low `real_beacon_skip` estimates?

C-C removes stale evidence.

Fresh values of `1` or `2` still occur.

The underlying reason remains unresolved.

---

## 3. Do fresh low estimates correspond to actual WF200 wakefulness?

No direct physical sleep-residency measurement is currently available.

The host estimate alone cannot answer this.

---

## 4. Is Beacon Recovery actually necessary?

The mechanism remains enabled conservatively.

A future controlled no-Recovery experiment can test this separately.

---

## 5. Does Recovery correct an unknown non-D3 WF200 state?

This is currently hypothetical.

If such a state exists, Recovery frequency would represent a trade-off between:

```text
known Recovery overhead
```

and:

```text
duration of the unknown fault before correction
```

A controlled rate-limit or no-Recovery experiment would help test this.

---

## 6. What was the original purpose of the Shelly heuristic?

The implementation shows what the code does.

It does not reveal why the original developers considered a low
`real_beacon_skip` sufficient reason to cycle WLAN PM state.

---

## 7. Why are thousands of Recoveries observed without D3 PM errors?

The D3 observer now provides approximately:

```text
63.9 h
3835 Recoveries
0 D3 PS_MODE_ERROR
```

Understanding the intended relationship, if any, would be useful.

---

## 8. Does WF200 3.18.0 materially change battery behavior?

The radio firmware contains a directly relevant PM fix.

Long-term comparison is required to determine its practical effect on the TRV.

---

## 9. Are additional shared host-PM defects still present?

A1 corrects the currently demonstrated high-priority lifecycle problems.

Continued runtime observation remains useful for identifying any remaining
paths.

---

## 10. What is the actual electrical cost of Recovery?

The project does not currently include direct current measurement.

Recovery occupancy can be calculated.

Recovery energy cannot.

---

## 11. What mechanism explains drain on older 2.1.x firmware?

The 2.2.4 Beacon Recovery loop cannot explain the complete historical problem.

Shared host architecture and radio behavior therefore remain relevant.

---

# Question for Shelly

Two implementation questions are particularly important for understanding the
original PM design.

First:

> What actual WF200 or WLAN failure condition was a calculated
> `real_beacon_skip = 1` or `2` intended to detect?

Second:

> What host-visible condition was expected to confirm that the WF200 had
> actually returned to correct low-power operation after the
> Active-to-Power-Save Recovery transition?

These questions matter because the currently identified host interfaces expose:

- requested PM policy
- PM command completion
- wake-handshake state
- beacon statistics
- D3 `PS_MODE_ERROR`

but no direct physical sleep-residency indication has been identified.

The D3-observer experiment additionally recorded:

```text
~63.9 h runtime
3835 Shelly Beacon Recoveries
0 WF200 D3 PS_MODE_ERROR events
```

Clarifying the original design intent would help determine whether Beacon
Recovery is a necessary reliability mechanism or an indirect workaround for a
different PM problem.

A related question is:

> If Beacon Recovery was intended to correct an internal WF200 state that is
> not represented by D3 `PS_MODE_ERROR`, what condition was expected to
> indicate that state to the host?

This distinction matters when considering Recovery rate limiting.

Without knowing the intended failure condition, lowering the Recovery rate can
reduce known Active-mode overhead while potentially allowing an unknown
correctable fault to remain active for longer.

---

# Current Conclusion

Shelly TRV Gen1 power management consists of several interacting layers.

The application selects a PM policy.

The host coordinates Wake, transport ownership, sleep-inhibit ownership and
Final-Sleep.

WF200 command `0x52` configures radio power-save policy.

The WUP handshake determines whether the host currently requires the WF200 to
remain awake.

The WF200 then manages its own internal radio power state.

These layers must not be collapsed into one concept.

In particular:

```text
PM52 success
```

does not prove physical sleep.

```text
WUP LOW
```

does not prove physical sleep.

```text
real_beacon_skip
```

does not directly report physical sleep.

```text
D3 PS_MODE_ERROR = 0
```

does not prove that every internal radio PM transition was perfect.

Static analysis of Shelly firmware 2.2.4 identified several host-side
correctness problems around this architecture.

These include:

```text
G01
incomplete Final-Sleep failure cleanup

G02
Wake software state committed before lower-layer success

G03 / G05
ambiguous transport and confirmation ownership

G06
requested PM policy treated as selected before confirmation

G18
independent sleep-inhibit reasons requiring separate ownership

G19
stale PM transitions able to interfere with newer intent
```

A1 corrects these lifecycle problems.

Patch C-C independently corrects the Beacon Recovery measurement and freshness
problems.

WF200 3.18.0 adds an official Silicon Labs fix for an error that could prevent
the device from sleeping after a power-save mode change.

The integrated:

```text
A1 + C-C + WF200 3.18.0
```

firmware has successfully operated on physical Shelly TRV Gen1 hardware through
boot, WF200 initialization, WLAN association, DHCP, cloud operation, PM
transitions, calibration and valve operation.

No additional reboot or reconnect occurred during the initial approximately
eight-hour qualification period.

Fresh Beacon Recovery nevertheless continues to occur.

This is not currently evidence that A1 or C-C failed.

It shows that Shelly's host beacon-density estimator can still produce fresh
values satisfying the retained Recovery condition.

The long-running D3 observer provides an important comparison:

```text
~63.93 h runtime
3835 Beacon Recoveries
~59.99 Recoveries/hour
0 D3 PS_MODE_ERROR
```

The repeated Shelly Recovery loop therefore cannot be treated as a sequence of
WF200-reported PM errors.

At approximately five seconds per Recovery, the stock loop corresponds to:

```text
~300 seconds/hour
~5 minutes/hour
~8.33% wall-clock Recovery occupancy
```

Patch C-C reduces the current-cadence worst case to approximately:

```text
~150 seconds/hour
~2.5 minutes/hour
~4.17% wall-clock Recovery occupancy
```

and the initial integrated test showed approximately:

```text
~135 seconds/hour
~2.25 minutes/hour
~3.75% wall-clock Recovery occupancy
```

at about 27 fresh Recoveries per hour.

These values describe time, not battery energy.

No direct current measurement has been performed.

There is also an unresolved opposite side to this calculation.

If Beacon Recovery corrects an unknown WF200 condition that is not visible
through D3, reducing the Recovery rate too far could allow that condition to
remain active longer.

For example, under a purely hypothetical model where Recovery reliably clears
such a fault:

```text
60 checks/hour
-> maximum ~1 minute until correction
-> average ~30 seconds

30 checks/hour
-> maximum ~2 minutes until correction
-> average ~1 minute

4 checks/hour
-> maximum ~15 minutes until correction
-> average ~7.5 minutes
```

At four Recoveries per hour, the guaranteed explicit Recovery overhead would
fall to only:

```text
4 × 5 s
= 20 seconds/hour
```

but a hypothetical fault occurring just after a check could remain active for
almost 15 minutes.

This does not demonstrate that such a fault exists.

It shows why Recovery frequency cannot be optimized from Recovery occupancy
alone until the physical condition behind the heuristic is understood.

C-C therefore currently represents a conservative compromise:

```text
remove demonstrated stale Recovery
        |
        v
approximately halve worst-case Recovery occupancy
under the current measurement cadence
        |
        v
retain relatively frequent fresh Recovery
in case the heuristic is detecting a real
non-D3 condition
```

The remaining central question is therefore no longer simply:

```text
Why does the firmware enter Beacon Recovery?
```

The implementation of that mechanism is now understood.

The more important question is:

```text
What physical or protocol-level WF200 condition,
if any, does the host-derived Recovery heuristic
actually identify?
```

and, directly related:

```text
If such a condition exists,
does Beacon Recovery actually correct it?
```

Those questions remain open.

Long-term testing of the corrected integrated firmware is now the most useful
next step for determining whether the demonstrated host-side defects and the
updated WF200 firmware materially improve battery behavior.

---

# Related Documents

Detailed Beacon Recovery analysis:

[`recovery-mechanism.md`](recovery-mechanism.md)

Detailed `real_beacon_skip` analysis:

[`real-beacon-skip.md`](real-beacon-skip.md)

WF200 beacon-counter analysis:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

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

# Research Notes

This analysis is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime testing on personally owned
devices.

The PM analysis included:

- Shelly application PM-state transitions
- WF200 command `0x52`
- Wake and Final-Sleep handling
- WUP lifecycle
- transport ownership
- confirmation ownership
- sleep-inhibit ownership
- PM transition generations
- Beacon Recovery interaction
- WF200 D3 `PS_MODE_ERROR`
- WF200 3.18.0 integration
- long-term runtime observation

The A1 correction was separately subjected to static qualification before
controlled hardware testing.

The final integrated firmware was then tested on physical hardware through the
normal WLAN and application startup path.

Runtime testing currently includes:

- stock 2.2.4
- D3-observer firmware
- Patch C-C
- WF200 3.18.0
- C-C + WF200 3.18.0
- A1 + C-C + WF200 3.18.0

No original or modified Shelly firmware image, complete proprietary function,
or large raw disassembly is published in this document.

Public Silicon Labs documentation and release information are used where
necessary to interpret the host-visible WF200 interface.

The project distinguishes between:

```text
what the host requests
what the host can observe
what runtime testing demonstrates
what can actually be concluded about physical radio state
```

Those distinctions are particularly important for low-power firmware, where a
successful software transition is not necessarily a direct measurement of the
resulting electrical state.

This is an independent research project and is not affiliated with Shelly
Group or Silicon Labs.