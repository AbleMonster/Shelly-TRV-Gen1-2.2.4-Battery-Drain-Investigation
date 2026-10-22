# Beacon Recovery Mechanism Analysis

## Overview

Shelly TRV Gen1 firmware 2.2.4 contains a host-side Beacon Recovery mechanism
associated with the calculated `real_beacon_skip` value.

When the Recovery condition is satisfied, the firmware logs:

```text
Beacon skip error! Attempt recovery
```

and temporarily changes WLAN power-management behavior.

The normal sequence identified in firmware and confirmed at runtime is
approximately:

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
WF200 Active / Always-On
        |
        v
deeper host sleep restricted
        |
        | approximately 5 seconds
        v
restore application PM state
        |
        v
normally state 3
with current desired_beacon_skip
```

The normal Beacon Recovery path is therefore primarily a temporary
power-management transition.

It does not normally perform:

- WLAN scanning
- AP selection
- disconnect/reconnect
- reassociation
- DHCP negotiation
- complete WLAN-driver initialization
- WF200 firmware reload
- MCU reboot

The main problem in stock 2.2.4 is not simply that this Recovery mechanism
exists.

Three host-side validity problems were identified in the evidence used to
request Recovery:

```text
C1a
signed control-value interpretation

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

C2 can turn one qualifying measurement into a self-sustaining Recovery loop.

Patch C-C corrects these validity problems while deliberately retaining
Recovery for a fresh valid `real_beacon_skip` value of `1` or `2`.

Hardware testing confirms the intended distinction:

- the stock stale-value feedback loop is removed
- the first post-Recovery sample establishes a new baseline
- historical `real_beacon_skip` is not reused as fresh Recovery evidence
- later fresh measurements can still produce `1` or `2`
- those fresh measurements can still trigger Recovery

This leaves an important question:

> Does a fresh low `real_beacon_skip` actually represent a condition that
> requires Recovery?

That has not yet been established.

The detailed `real_beacon_skip` calculation and counter semantics are
documented separately in:

[`real-beacon-skip.md`](real-beacon-skip.md)

and:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

---

# Recovery Trigger

The Recovery decision uses the internally cached:

```text
real_beacon_skip
```

value.

For clarity:

```text
C = current received-beacon counter
P = previous received-beacon baseline
R = cached real_beacon_skip
H = shared PM override / Recovery countdown
```

Firmware 2.2.4 obtains relevant WF200 statistics through command:

```text
0x66
```

The host derives `R` approximately from:

```text
delta = C - P
R = uint8_t(600 / delta)
```

Stock Recovery later interprets the stored byte as signed and approximately
tests:

```text
signed_R != 0
&&
signed_R <= 2
```

Beacon Recovery is therefore triggered by a host-derived estimate.

It is not triggered by a direct readback of the programmed WF200 listen
interval.

It is also not directly triggered by the separate WF200:

```text
PS_MODE_ERROR
```

indication.

This distinction is important when interpreting repeated Recovery events.

---

# What `real_beacon_skip` Actually Represents

The name `real_beacon_skip` can be misleading.

It is not a WF200 register readback and it is not a direct measurement of
physical radio sleep residency.

It is calculated by the Shelly host from received-beacon statistics.

For example:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not mean:

```text
host requested 20
WF200 reported 1
```

It means:

```text
host requested 20

and

the host receive-density estimator calculated 1
```

Those are fundamentally different statements.

A low `real_beacon_skip` value alone does not prove that:

- the WF200 rejected the requested listen interval
- the programmed power-save mode was lost
- the WF200 remained physically awake
- the radio listened to every AP beacon
- a WF200 power-save error occurred

This distinction becomes especially important when considering whether Beacon
Recovery is actually necessary.

---

# C1a — Signed Control Interpretation

The calculated `real_beacon_skip` value is stored as an unsigned byte.

Stock Recovery later interprets that byte as signed.

This creates additional trigger cases.

For example:

```text
delta = 3

600 / 3 = 200
uint8_t = 200
int8_t  = -56
```

and:

```text
delta = 4

600 / 4 = 150
uint8_t = 150
int8_t  = -106
```

Both negative values satisfy the stock comparison:

```text
signed_R <= 2
```

For fresh positive counter deltas, the stock trigger domain therefore includes:

```text
delta = 3
delta = 4
delta = 201..600
```

Patch C-C uses unsigned interpretation for the Recovery decision.

The intended fresh positive trigger condition is therefore limited to:

```text
R = 1
```

or:

```text
R = 2
```

The diagnostic `real_beacon_skip` byte itself remains available.

The full arithmetic and trigger-domain analysis is documented in:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

# C1b — Measurement-Window Validity

The estimator assumes that:

```text
C - P
```

represents the intended measurement interval.

However, `P` has no associated elapsed-time value used by the calculation.

Several firmware events can interrupt the expected measurement progression
while preserving the previous baseline.

A later successful statistics sample can then compare:

```text
old P
```

with:

```text
new C
```

while still using the fixed:

```text
600
```

numerator.

The cumulative WF200 beacon counter itself can be correct while the resulting
host estimate no longer represents the intended measurement window.

Patch C-C invalidates the measurement baseline when identified events break
measurement continuity.

The next successful sample then establishes a new baseline instead of
calculating `real_beacon_skip` from an old one.

---

# C2 — Post-Recovery Freshness Failure

C2 explains the characteristic repeating Recovery loop observed on affected
stock 2.2.4 devices.

Assume a fresh measurement produces:

```text
R = 2
```

and Recovery occurs.

The Recovery path clears:

```text
P = 0
```

but retains:

```text
R = 2
```

Retaining `R` is useful diagnostically.

The problem occurs at the next successful statistics sample.

Because:

```text
P == 0
```

the firmware cannot calculate a fresh ratio.

It therefore establishes:

```text
P = C
```

instead.

This is a baseline-only sample.

Stock firmware nevertheless continues to the Recovery test using the
historical:

```text
R = 2
```

The result is:

```text
fresh qualifying R
        |
        v
Recovery
        |
        +---- P = 0
        |     R retained
        |
        v
next successful sample
        |
        +---- establish P
        |     no fresh R
        |
        v
historical R evaluated
        |
        v
Recovery
        |
        +---- P = 0
        |
        v
repeat
```

A new qualifying beacon measurement is therefore not required for every
Recovery.

Once the loop is established, the cached historical value can repeatedly
request Recovery.

---

# Successful PM Restoration Does Not Break the Stock Loop

The WF200 can successfully return to normal power saving after each Recovery.

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
skip 20
```

can complete normally.

That does not clear the historical qualifying `R`.

Therefore both of the following can be true:

```text
the Recovery transition completed successfully
```

and:

```text
the host Recovery logic remains latched by stale evidence
```

The approximately once-per-minute stock recurrence is therefore not evidence
that the WF200 failed to recover every time.

The host-side C2 logic can sustain that pattern by itself.

---

# Recovery Sequence

Once the Recovery predicate is accepted, the normal sequence is:

```text
qualifying Recovery evidence
        |
        v
log "Beacon skip error! Attempt recovery"
        |
        v
H = 5
        |
        v
request PM state 1
        |
        v
wake/configure WLAN device
        |
        v
request Active / Always-On WLAN mode
        |
        v
restrict deeper host sleep
        |
        | approximately 5 serviced seconds
        v
restore application PM state
```

The Recovery action therefore changes actual power-management behavior.

It is not merely a diagnostic message or counter increment.

---

# Shared Recovery Countdown `H`

Beacon Recovery sets:

```text
H = 5
```

The same field participates in other temporary PM behavior and can also contain
other values such as:

```text
H = 180
```

`H` is therefore not simply a dedicated:

```text
Beacon Recovery active
```

Boolean.

It is a shared temporary PM/recovery countdown.

For Beacon Recovery, `H = 5` normally produces approximately five serviced
seconds of temporary state.

This should not be interpreted as an electrically guaranteed exact five-second
pulse.

Scheduler timing and other state transitions can slightly affect the physical
elapsed time.

Runtime logs nevertheless consistently show a transition back to the normal PM
state approximately five seconds after entering Recovery.

---

# WLAN State During Recovery

During normal Recovery, firmware requests the WLAN power mode corresponding to:

```text
Active / Always-On
```

rather than the normal connected beacon-based power-saving configuration.

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
        | approximately 5 s
        v

restore connected power saving
with current desired beacon skip
```

The Recovery action therefore genuinely changes WF200 power-management policy.

It does not by itself establish what the physical radio sleep state was before
or after that request.

---

# Host Sleep During Recovery

Recovery also affects host-microcontroller sleep availability.

Under normal connected power-saving operation, deeper host energy modes can be
available.

During the identified Recovery interval, the relevant behavior is
approximately:

```text
Normal connected operation

EM1 available
EM2 available
EM3 available
```

versus:

```text
Recovery interval

EM1 available
EM2 blocked
EM3 blocked
```

This does not mean that the host CPU executes continuously for the complete
Recovery interval.

The processor can still idle in EM1.

The important difference is that the deeper EM2 and EM3 states are temporarily
unavailable.

Together with the WLAN Active / Always-On request, this makes repeated Recovery
a credible additional energy workload.

---

# Restoration of Power Saving

When the Recovery countdown expires, firmware restores the application PM
state.

If normal connected beacon power saving is restored, the current:

```text
desired_beacon_skip
```

is used.

For example:

```text
state 3
skip 15
   |
   | Recovery
   v
state 1
Active / Always-On
   |
   | approximately 5 s
   v
state 3
skip 15
```

The desired skip can change over time because the normal RSSI-dependent policy
remains active.

Runtime testing has shown operation with both:

```text
desired_beacon_skip = 20
```

and:

```text
desired_beacon_skip = 15
```

while normal PM restoration continued to operate.

---

# Recovery Is an Indirect Heuristic

A temporary transition from:

```text
Fast Power Save
```

to:

```text
Active / Always-On
```

followed by reapplication of the normal power-save configuration is technically
plausible as a recovery or reconfiguration strategy.

However, the current evidence does not establish that this transition is
required when `real_beacon_skip` becomes `1` or `2`.

No direct evidence has been found that a fresh:

```text
real_beacon_skip = 1
```

or:

```text
real_beacon_skip = 2
```

means that:

- the WF200 failed to enter power save
- the requested listen interval was rejected
- the requested listen interval was lost
- the WF200 remained physically awake
- an Active-to-Power-Save transition is required to restore correct operation

The mechanism therefore appears to use received-beacon density as an indirect
WLAN power-save health heuristic.

That interpretation matches the implementation.

The original design rationale is not known.

---

# Patch A — Recovery Isolation

Patch A was an early isolation experiment.

It bypasses the identified Recovery action while leaving the statistics and
`real_beacon_skip` calculation intact.

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

This was useful because it showed that the recurring Recovery action could be
removed independently of normal RSSI-dependent beacon-skip selection.

However, Patch A also prevents Recovery after a genuinely fresh qualifying
measurement.

It therefore answers:

```text
What happens if this Recovery action is removed?
```

but not:

```text
How should the Recovery mechanism itself be corrected?
```

Patch A remains useful as an isolation experiment, but it is not the preferred
corrective design.

---

# Patch B and mDNS Isolation

Patch B suppresses the targeted periodic connected-state mDNS restart.

It does not intentionally modify:

- WF200 command `0x66`
- beacon statistics
- `real_beacon_skip`
- the Recovery predicate
- the Recovery action
- normal RSSI-dependent desired skip

Runtime testing showed that Beacon Recovery continued while the targeted
periodic mDNS behavior was suppressed.

The targeted periodic mDNS restart is therefore not required for the observed
Beacon Recovery loop under the tested conditions.

This does not mean that arbitrary network activity can never influence WF200
statistics.

It only separates the specific periodic mDNS mechanism from Beacon Recovery.

---

# Patch C-C

Patch C-C corrects the validity semantics around Beacon Recovery rather than
removing Recovery entirely.

Its main requirements are:

1. preserve diagnostic `real_beacon_skip`
2. correct signed control interpretation
3. invalidate unusable measurement baselines
4. distinguish baseline establishment from fresh measurement
5. prevent historical `R` from acting as fresh Recovery evidence
6. preserve Recovery for a fresh valid `R = 1` or `2`
7. preserve unrelated WLAN and PM behavior

Conceptually:

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
normal     Recovery
operation
```

After Recovery:

```text
P = 0
R retained diagnostically
        |
        v
next successful sample
        |
        v
establish new baseline
        |
        v
NO Recovery from historical R
        |
        v
later comparable sample
        |
        v
calculate fresh R
```

This is the central behavioral difference from stock 2.2.4.

---

# Patch C-C Hardware Validation

Patch C-C has been tested on physical hardware.

Its intended post-Recovery behavior has been observed directly.

The relevant runtime pattern is:

```text
fresh qualifying measurement
        |
        v
Recovery
        |
        v
P invalidated
        |
        v
next eligible sample establishes baseline
        |
        v
no stale-R Recovery
        |
        v
later comparable sample
        |
        v
fresh R may qualify again
```

This differs from the stock C2 behavior:

```text
Recovery
   |
   v
baseline-only sample
   |
   v
historical R reused
   |
   v
Recovery again
```

The hardware result confirms the intended distinction between:

```text
historical diagnostic value
```

and:

```text
fresh Recovery evidence
```

Fresh qualifying measurements still occur.

That is expected by design and does not indicate that Patch C-C failed.

---

# Fresh Recovery Still Occurs After C-C

An important runtime result is that Beacon Recovery did not disappear after
C-C removed the stale-value loop.

During current hardware testing, fresh-triggered Recovery has been observed at
approximately:

```text
27 to 30 Recoveries/hour
```

during periods where fresh measurements repeatedly qualify.

The pattern differs from the stock stale-R loop.

Stock behavior can become:

```text
Recovery
        |
        v
baseline-only sample
        |
        v
historical R reused
        |
        v
Recovery
        |
        v
repeat every measurement cycle
```

With C-C the observed behavior is approximately:

```text
Recovery
        |
        v
baseline establishment
        |
        v
no Recovery from old R
        |
        v
later fresh measurement
        |
        v
possible new Recovery
```

With the currently observed periodic measurement cadence, this can result in a
Recovery approximately every second measurement cycle if every newly
calculated measurement again produces `R = 1` or `2`.

This gives an important separation:

> The stock approximately once-per-minute feedback loop is a host-side
> freshness defect.

At the same time:

> Fresh measurements capable of satisfying the remaining Recovery predicate
> still occur.

The cause and significance of those fresh low estimates remain under
investigation.

The approximately 30 Recoveries/hour figure is not a universal Patch C-C
limit.

It follows from the current measurement cadence and the requirement to
establish a new baseline before another fresh estimate can be calculated.

Different scheduling or measurement intervals could produce a different
frequency.

---

# The Estimator Is Not Permanently Stuck at `1`

Runtime testing also shows that `real_beacon_skip` is not simply stuck at a low
value.

For example, the current integrated hardware test has shown:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

during earlier observations, but later also:

```text
desired_beacon_skip = 15
real_beacon_skip    = 13
```

The host estimator can therefore produce values much closer to the requested
skip.

This still does not prove physical WF200 sleep residency.

It also does not contradict fresh Recovery events.

`/stats` shows the current or most recently derived value, while an earlier
measurement window can independently have produced a fresh `1` or `2` and
already triggered Recovery.

---

# Stock vs. Patch C-C Recovery Time

The timing difference between stock 2.2.4 and Patch C-C is significant.

With the stock C2 stale-value loop, Recovery can occur approximately once per
minute even though no new qualifying `real_beacon_skip` measurement was
calculated.

The long-running D3 observer provides a particularly clear example.

Over approximately:

```text
63.9 hours
```

it accumulated:

```text
3835 Beacon Recovery events
```

which corresponds to approximately:

```text
59.99 Recoveries/hour
```

or effectively one Recovery per minute.

At approximately five seconds per Recovery:

```text
Stock 2.2.4 observed worst case

60 Recoveries/hour
× ~5 seconds
= ~300 seconds/hour
= ~5 minutes/hour
≈ 8.33% of wall-clock time
```

Patch C-C breaks the stale-value feedback loop.

After Recovery, the next eligible statistics sample establishes a new baseline
and cannot reuse historical `real_beacon_skip` as fresh Recovery evidence.

With the currently observed periodic measurement cadence, a new fresh Recovery
can therefore normally occur no more often than approximately every second
measurement cycle.

This gives the following theoretical worst case for the current measurement
schedule:

```text
Patch C-C theoretical worst case
for the currently observed measurement cadence

30 fresh-triggered Recoveries/hour
× ~5 seconds
= ~150 seconds/hour
= ~2.5 minutes/hour
≈ 4.17% of wall-clock time
```

In this measurement scenario, correcting C2 therefore reduces the maximum
explicit Recovery time from approximately:

```text
300 seconds/hour
```

to:

```text
150 seconds/hour
```

even if every newly calculated eligible measurement continues to produce:

```text
real_beacon_skip = 1
```

or:

```text
real_beacon_skip = 2
```

Actual Recovery time can be lower because a fresh measurement does not
necessarily qualify.

During the current integrated hardware test, approximately:

```text
27 fresh-triggered Recoveries/hour
```

were observed over a multi-hour interval.

That corresponds to approximately:

```text
27 × ~5 seconds
= ~135 seconds/hour
= ~2.25 minutes/hour
≈ 3.75% of wall-clock time
```

These figures describe time spent in the explicit Recovery interval.

They are not battery-consumption percentages.

The electrical energy difference between normal power-save operation and the
Recovery interval has not been measured.

---

# Long-Term Stock Recovery Example

The D3-observer device provides a useful long-running example of the stock
Recovery behavior.

At the latest observation point:

```text
Runtime:                 ~230144 s
                         ~63.93 h
                         ~2.66 days

Beacon Recovery counter: 3835
Average Recovery rate:   ~59.99/hour

desired_beacon_skip:     20
real_beacon_skip:        1

D3 PS_MODE_ERROR:        0

reboot_counter:          1
reconnect_counter:       1
```

The average Recovery rate is almost exactly one event per minute.

The debug log continues to show the same repeating sequence:

```text
Beacon skip error! Attempt recovery
        |
        v
Enter powersave state 1
        |
        | approximately 5 seconds
        v
Enter powersave state 3 (skip 20)
        |
        | approximately 55 seconds
        v
Beacon skip error! Attempt recovery
```

This is consistent with the stock C2 stale-evidence loop.

Across the complete observation period, the approximate accumulated explicit
Recovery time is:

```text
3835 × ~5 seconds
= ~19175 seconds
= ~319.6 minutes
= ~5.33 hours
```

This means that during approximately 63.9 hours of runtime, the device spent
roughly 5.3 hours in the explicit Recovery interval if the approximately
five-second duration is applied to every event.

Again, this is a wall-clock-time calculation.

It is not a measurement of battery energy consumed.

---

# Relationship to WF200 `PS_MODE_ERROR`

The WF200 interface provides a separate power-save error indication through:

```text
D3 PS_MODE_ERROR
```

Known reason values correspond to conditions including:

```text
0
PS-Poll timeout

1
U-APSD timeout

2
buffered unicast not delivered across consecutive beacons

3
unstable beacon timing / beacon-window compensation
```

This is a more direct host-visible WF200 power-save error channel than the
Shelly `real_beacon_skip` estimator.

To determine whether Shelly Beacon Recovery correlates with this WF200 error
channel, a dedicated D3-observer firmware was tested while leaving the normal
Shelly Beacon Recovery mechanism active.

This allowed both mechanisms to be observed in parallel:

```text
Shelly host heuristic

received-beacon statistics
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery


WF200 error channel

WF200
        |
        v
D3 PS_MODE_ERROR
        |
        v
D3 observer
```

During approximately:

```text
63.9 hours
```

of continuous runtime, the device accumulated:

```text
Beacon Recovery events: 3835
Average Recovery rate:   ~59.99/hour
```

while the D3 observer recorded:

```text
WF200 D3 PS_MODE_ERROR events: 0
```

The Beacon Recovery rate is effectively one event per minute and matches the
characteristic stock stale-evidence loop.

Across more than 3,800 observed Shelly Beacon Recovery events, no corresponding
WF200 D3 `PS_MODE_ERROR` was reported.

No observed Recovery can therefore be associated with a reported D3
power-save error during this observation period.

There is also no observed case in this test where Beacon Recovery can be shown
to have cleared such an error, because no D3 `PS_MODE_ERROR` was reported in
the first place.

This is an important distinction.

The repeated Shelly Beacon Recovery events were generated by the host-side
`real_beacon_skip` mechanism while the known direct WF200 `PS_MODE_ERROR`
channel remained silent.

The result does not prove that no other internal WF200 condition existed.

It also does not prove that the WF200 was physically sleeping correctly.

The host does not expose every possible internal radio state, and
`PS_MODE_ERROR` cannot be treated as a complete measurement of physical radio
sleep behavior.

What the experiment does establish is narrower:

> During approximately 63.9 hours and more than 3,800 Shelly Beacon Recovery
> events, no corresponding error was observed on the known WF200
> `PS_MODE_ERROR` channel.

The available runtime evidence therefore does not support interpreting the
repeated Shelly Beacon Recovery events as direct reactions to reported WF200
`PS_MODE_ERROR` events.

It also provides no observed example in which Beacon Recovery can be shown to
have corrected such a reported WF200 error.

---

# Why the D3 Result Matters

The D3-observer result does not prove that Beacon Recovery has no purpose.

It does, however, make an important distinction between:

```text
Shelly host-side heuristic
```

and:

```text
WF200-reported power-save error
```

During the long-running observation:

```text
Shelly Beacon Recovery:
3835 events

WF200 D3 PS_MODE_ERROR:
0 events
```

The two mechanisms therefore cannot be treated as equivalent.

The current evidence does not show the following sequence:

```text
WF200 reports PM error
        |
        v
Shelly detects error
        |
        v
Beacon Recovery
        |
        v
WF200 error cleared
```

Instead, the observed sequence is:

```text
host beacon statistics
        |
        v
host real_beacon_skip estimate
        |
        v
Shelly Beacon Recovery
```

while the known WF200 PM-error channel remains silent.

This strengthens the question of what actual failure condition the
`real_beacon_skip` Recovery heuristic was intended to detect.

---

# Relationship to WF200 3.18.0

Silicon Labs WF200 firmware 3.18.0 contains a relevant LMAC fix described as:

```text
Fixed an error that was preventing the device from sleeping
after a power-save mode change
```

This is relevant to the broader investigation because Beacon Recovery itself
repeatedly performs power-save mode changes.

The existence of this Silicon Labs fix does not prove that the fixed issue was
the cause of Shelly TRV Gen1 battery drain.

Runtime testing also showed that WF200 3.18.0 alone does not eliminate the
stock 2.2.4 stale-R Recovery loop.

That is expected because C2 is a Shelly host-side logic defect.

The current integrated firmware therefore combines:

```text
A1
host-side PM / ownership / transition corrections

Patch C-C
Beacon Recovery evidence corrections

WF200 3.18.0
updated radio firmware containing the Silicon Labs
sleep-after-power-save-mode-change fix
```

This gives a cleaner platform for determining whether repeated Beacon Recovery
remains useful after known host-side and radio-side issues have been corrected.

---

# Current Integrated Runtime Result

The current experimental firmware combining:

```text
A1 + Patch C-C + WF200 3.18.0
```

has successfully booted and operated on physical Shelly TRV Gen1 hardware.

Observed normal operation includes:

- successful OTA update
- cold reboot
- FMAC initialization
- WF200 3.18.0 initialization
- WLAN scanning
- association
- DHCP
- cloud connection
- normal PM state transitions
- RSSI-dependent desired beacon-skip selection
- thermostat operation
- valve movement
- successful calibration
- continued operation without additional reboot or reconnect during the
  initial qualification period

Fresh Beacon Recovery events continue to occur.

The important difference is that their runtime pattern follows the corrected
C-C measurement lifecycle rather than the stock stale-R feedback loop.

The integrated runtime test therefore shows that:

```text
removing stale Recovery
```

does not imply:

```text
removing all Recovery
```

and that the corrected firmware can remain operational while fresh Recovery
events continue to occur.

Long-term battery behavior is still under observation.

---

# Energy-Consumption Relevance

Repeated Beacon Recovery creates a credible additional energy workload.

During each Recovery:

- the WLAN device is explicitly woken/configured
- Active / Always-On WLAN mode is requested
- deeper host EM2 and EM3 sleep are restricted
- additional host/WLAN control activity occurs
- the temporary state normally lasts approximately five serviced seconds

For the stock D3-observer device, the long-term Recovery rate is approximately:

```text
60 Recoveries/hour
```

which corresponds to approximately:

```text
300 seconds/hour
```

or:

```text
8.33% of wall-clock time
```

in the explicit Recovery interval.

For Patch C-C under the currently observed measurement cadence, the
theoretical worst case is approximately:

```text
30 Recoveries/hour
```

or:

```text
150 seconds/hour
≈ 4.17% of wall-clock time
```

when every fresh eligible measurement qualifies.

The current integrated test has shown approximately:

```text
27 Recoveries/hour
```

or:

```text
135 seconds/hour
≈ 3.75% of wall-clock time
```

over the observed interval.

The correction therefore reduces the possible Recovery occupancy substantially
under the current measurement schedule even before considering measurement
cycles where `real_beacon_skip` does not qualify.

What remains unmeasured is:

```text
WF200 current during Recovery
incremental host current
energy per Recovery
daily Recovery energy
battery-runtime reduction
```

It would therefore be incorrect to convert:

```text
8.33% Recovery wall-clock time
```

into:

```text
8.33% additional battery consumption
```

The time calculation and the electrical energy calculation are different.

Repeated Recovery can credibly increase energy consumption, but the exact
energy cost has not been measured.

---

# Relationship to Historical Battery Drain

The 2.2.4 Beacon Recovery loop is a credible additional battery-drain
mechanism.

It cannot currently be described as:

```text
the original Shelly TRV Gen1 battery-drain root cause
```

or:

```text
the sole battery-drain mechanism
```

Battery drain was also observed on earlier 2.1.x firmware.

The same 2.2.4 `real_beacon_skip` Recovery implementation has not been
identified there in the same form.

The supported interpretation is therefore:

> Firmware 2.2.4 contains a host-side Beacon Recovery mechanism that can become
> self-sustaining and repeatedly move WLAN and host power management away from
> normal low-power operation.

This can act as a battery-consumption amplifier.

It cannot by itself explain all historical TRV Gen1 battery drain.

---

# Is Beacon Recovery Actually Required?

This is now one of the main open questions.

The implementation clearly shows what Beacon Recovery does.

It does not establish that Recovery is required whenever the host estimator
produces:

```text
R = 1
```

or:

```text
R = 2
```

No direct evidence has been found that such a value proves:

- failed WF200 power-save entry
- loss of the programmed listen interval
- rejection of the requested listen interval
- persistent physical radio wakefulness
- a condition that requires an Active-to-Power-Save transition

The D3-observer experiment strengthens this question.

More than 3,800 Shelly Beacon Recovery events were observed over approximately
63.9 hours while the known WF200:

```text
D3 PS_MODE_ERROR
```

channel remained completely silent.

No observed Recovery could therefore be associated with a reported WF200
power-save error.

No observed D3 error can currently be shown to have been cleared by Beacon
Recovery.

This does not prove that the Recovery mechanism has no purpose.

It means that the current runtime evidence provides no direct WF200
`PS_MODE_ERROR` condition explaining why these repeated Recoveries were
necessary.

The question becomes even more relevant after combining:

- A1 host PM and transition corrections
- Patch C-C measurement and freshness corrections
- WF200 3.18.0 with its relevant sleep-after-PM-change fix

The current experiment deliberately retains fresh Recovery.

This avoids mixing two separate questions:

```text
Are the known host and radio-side defects corrected?
```

and:

```text
Was the Beacon Recovery heuristic necessary in the first place?
```

A future controlled no-Recovery variant could answer the second question
separately.

---

# Why Fresh Recovery Is Still Retained

It would be technically straightforward to remove the Recovery action
completely.

Patch A already demonstrated that this can be done.

That is not the current preferred approach.

Removing Recovery at the same time as correcting the known host and radio-side
issues would make it difficult to determine which change produced a later
behavioral difference.

Patch C-C therefore keeps the mechanism conservative:

```text
invalid / stale evidence
        |
        X
no Recovery


fresh valid R = 1/2
        |
        v
Recovery retained
```

This allows the current long-term experiment to determine whether abnormal
battery behavior remains after the demonstrated host-side defects have been
removed.

A later controlled Recovery-disabled experiment can then answer a separate
question:

> Does fresh Beacon Recovery provide any measurable reliability benefit after
> A1, C-C and WF200 3.18.0?

---

# No Explicit TX-Power Increase Identified

No application-level WLAN transmit-power-setting operation was identified in
the normal Beacon Recovery sequence.

The identified action is a power-management-mode transition.

The supported statement is therefore:

> No explicit application-level WLAN transmit-power increase was identified in
> the normal Beacon Recovery path.

This does not establish that lower-level radio behavior can never change
internally.

---

# No Normal Scan, Reconnect or DHCP Path Identified

No direct normal Beacon Recovery path has been identified that performs:

- WLAN scanning
- AP selection
- ordinary disconnect
- ordinary reconnect
- reassociation
- DHCP negotiation
- complete WLAN-driver initialization
- full WLAN subsystem reset

The normal identified sequence is narrower:

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

A scan, reconnect or DHCP event occurring near a Recovery event should
therefore not automatically be attributed to Beacon Recovery.

---

# Exceptional Driver-Lock Reset Path

A separate exceptional path exists in the WLAN/PM logic.

If a relevant WLAN driver-lock operation fails, firmware can initialize a
different countdown that can eventually request an MCU system reset.

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
separate countdown
        |
        v
MCU system reset
```

The two mechanisms should not be conflated.

---

# Current Patch Roles

| Patch / Firmware | Purpose | Beacon Recovery behavior |
|---|---|---|
| Patch A | Isolation experiment | Recovery action bypassed |
| Patch B | mDNS isolation | Recovery unchanged |
| Patch A+B | Combined isolation | Recovery and targeted mDNS behavior bypassed |
| Patch C family | Corrective research | Fresh valid Recovery retained |
| Patch C-C | Current Beacon Recovery correction | C1a, C1b and C2 corrected |
| A1 + C-C + WF200 3.18.0 | Integrated experimental firmware | Corrected host PM paths and Beacon Recovery with updated WF200 firmware |

Patch A remains useful as an isolation experiment.

Patch C-C is the corrective Beacon Recovery implementation.

A1 + C-C + WF200 3.18.0 is the current integrated firmware under long-term
hardware evaluation.

---

# Open Questions

The Beacon Recovery implementation itself is now substantially understood.

The main unresolved questions are:

1. Why do fresh `real_beacon_skip = 1..2` measurements still occur?

2. Do those fresh measurements correspond to an actual WF200 power-management
   problem?

3. Does the Active-to-Power-Save Recovery correct any measurable condition?

4. Why were more than 3,800 Beacon Recoveries observed while the WF200
   `PS_MODE_ERROR` channel remained at zero?

5. Is Beacon Recovery still required after A1 host corrections and
   WF200 3.18.0?

6. How often do fresh qualifying measurements occur across different APs,
   RSSI conditions and desired-skip values?

7. Does fresh Recovery frequency change over long uninterrupted runtime?

8. What is the electrical energy cost of one Recovery interval?

9. How much battery-runtime improvement results from removing the stock stale-R
   loop?

10. How much of the remaining historical battery drain is caused by mechanisms
    inherited from earlier firmware?

11. Would a controlled no-Recovery variant remain stable after the known host
    and WF200 corrections?

The last question should be tested separately from the current
A1 + C-C + WF200 3.18.0 qualification.

---

# Question for Shelly

One implementation question remains particularly relevant for the original
firmware developers:

> What actual WF200 or WLAN failure condition was a calculated
> `real_beacon_skip = 1` or `2` intended to detect, and why is an
> Active-to-Power-Save transition required to recover from that condition?

This question is especially relevant because the D3-observer experiment
recorded:

```text
~63.9 hours runtime
3835 Shelly Beacon Recovery events
~59.99 Recoveries/hour
0 WF200 D3 PS_MODE_ERROR events
```

The reverse engineering establishes the host-side calculation and Recovery
action, but it does not reveal the original design rationale.

Clarifying this would help distinguish between:

```text
a necessary WLAN reliability mechanism
```

and:

```text
a heuristic workaround for another power-management problem
```

That distinction is important when deciding whether this mechanism should
remain in corrected firmware.

---

# Current Model

The current stock 2.2.4 model is:

```text
WF200 cumulative beacon statistics
        |
        v
host C / P measurement state
        |
        v
derive 8-bit R
        |
        +---- C1a: signed interpretation
        |
        +---- C1b: measurement-window validity
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
WF200 Active / Always-On
        |
        v
EM2 / EM3 restricted
        |
        | ~5 serviced seconds
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

Patch C-C changes the post-Recovery behavior to:

```text
fresh valid R = 1/2
        |
        v
Recovery
        |
        v
P invalidated
R retained diagnostically
        |
        v
next sample establishes baseline
        |
        v
NO Recovery from historical R
        |
        v
later comparable sample
        |
        v
fresh R calculated
        |
        +---- R != 1/2 -> normal operation
        |
        +---- R = 1/2  -> new Recovery
```

This second pattern has now been observed on hardware.

---

# Current Conclusion

Shelly TRV Gen1 firmware 2.2.4 contains a Beacon Recovery mechanism that
temporarily changes both WLAN and host power-management behavior.

The normal action is approximately:

```text
qualifying Recovery evidence
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
        | approximately 5 seconds
        v
restore application PM state
        |
        v
normally state 3
with current desired_beacon_skip
```

Three host-side validity problems were identified around the evidence used to
request this action:

```text
C1a
signed control interpretation

C1b
measurement-window validity

C2
post-Recovery evidence freshness
```

C2 explains how one qualifying event can become the characteristic stock
approximately once-per-minute Recovery loop without requiring a new qualifying
measurement every minute.

The long-running D3-observer test now provides a clear example:

```text
Runtime:                 ~63.93 h
Beacon Recoveries:       3835
Average Recovery rate:   ~59.99/hour
D3 PS_MODE_ERROR:        0
```

At approximately five seconds per event, that stock behavior corresponds to:

```text
~300 seconds/hour
~5 minutes/hour
~8.33% of wall-clock time
```

in the explicit Recovery interval.

Patch C-C corrects the identified validity problems while retaining Recovery
for a fresh valid `R = 1` or `2`.

With the currently observed measurement cadence, the worst case becomes
approximately:

```text
30 fresh Recoveries/hour
× ~5 seconds
= ~150 seconds/hour
≈ 4.17% of wall-clock time
```

and the current integrated hardware test has shown approximately:

```text
27 Recoveries/hour
≈ 135 seconds/hour
≈ 3.75% of wall-clock time
```

during the observed interval.

These values are wall-clock occupancy, not battery-consumption percentages.

The exact electrical energy cost remains unknown.

The D3-observer experiment adds an important second result.

During more than 3,800 Shelly Beacon Recovery events, the known direct WF200
`PS_MODE_ERROR` channel reported zero events.

No observed Recovery can therefore be tied to a reported D3 power-save error,
and no observed D3 error can be shown to have been corrected by Beacon
Recovery.

This does not prove that no other internal WF200 condition existed.

It does mean that the repeated Shelly Recovery loop cannot currently be
explained as a direct response to the known WF200 `PS_MODE_ERROR` channel.

The investigation has therefore reached a more fundamental question:

```text
Does a fresh real_beacon_skip of 1 or 2
actually identify a condition that requires Recovery?
```

Current evidence does not answer that question.

This is particularly relevant now that the integrated experimental firmware
also includes A1 host-side power-management corrections and WF200 3.18.0,
which contains a Silicon Labs fix related to failure to sleep after a
power-save mode change.

For now, fresh Recovery is deliberately retained.

A future controlled no-Recovery experiment can determine whether this heuristic
still provides any measurable reliability benefit after the known host and
radio-side corrections.

Beacon Recovery remains a credible additional energy-consumption mechanism in
firmware 2.2.4, but it is not established as the sole or original Shelly TRV
Gen1 battery-drain cause.

Earlier firmware exhibited battery-drain behavior without this same
2.2.4-specific Recovery implementation.

The broader historical battery problem therefore remains a multi-mechanism
investigation.

---

# Related Documents

Detailed `real_beacon_skip` analysis:

[`real-beacon-skip.md`](real-beacon-skip.md)

WF200 beacon-counter analysis:

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

# Research Notes

This analysis is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

The Recovery path was traced through:

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
- Patch A testing
- Patch B testing
- combined isolation testing
- Patch C-C hardware testing
- parallel D3 `PS_MODE_ERROR` observation
- WF200 3.18.0 hardware testing
- A1 + C-C + WF200 3.18.0 integrated hardware testing
- long-term battery logging

Public Silicon Labs WF200/fullMAC information is used where necessary to
interpret documented host-visible WLAN interface behavior.

No original or modified Shelly firmware image, complete proprietary function,
or large raw disassembly is published in this document.

The project distinguishes between what the host firmware demonstrably does,
what is observed at runtime, and what can actually be concluded about the
physical WF200 radio state.

This is an independent research project and is not affiliated with Shelly
Group or Silicon Labs.