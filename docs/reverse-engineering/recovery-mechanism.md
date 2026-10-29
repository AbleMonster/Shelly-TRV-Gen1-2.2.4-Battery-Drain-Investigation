# Beacon Recovery Mechanism Analysis

## Shelly TRV Gen1 Firmware 2.2.4

## Overview

Shelly TRV Gen1 firmware 2.2.4 contains a host-side Beacon Recovery mechanism associated with the calculated:

```text id="cu4sjf"
real_beacon_skip
```

value.

When the Recovery condition is accepted, firmware logs:

```text id="7mib9j"
Beacon skip error! Attempt recovery
```

and temporarily changes WLAN power-management behavior.

The normal sequence identified in firmware and confirmed at runtime is approximately:

```text id="k6yj2h"
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
        | approximately 5 serviced seconds
        v
restore application PM state
        |
        v
normally state 3
with current desired_beacon_skip
```

The normal Beacon Recovery path is therefore primarily a temporary WLAN power-management transition.

It does not normally perform:

- WLAN scanning
- AP selection
- disconnect/reconnect
- reassociation
- DHCP negotiation
- complete WLAN-driver initialization
- WF200 firmware reload
- MCU reboot

The main problem identified in stock 2.2.4 is not simply that this Recovery mechanism exists.

Three host-side validity defects were found in the evidence used to request Recovery:

```text id="slxj03"
C1a
signed control-value interpretation

C1b
measurement-window validity

C2
post-Recovery evidence freshness
```

C2 can create a **metastable stale-evidence recurrence** in which historical Recovery evidence is reused after the measurement baseline has been reset.

Under commonly observed runtime conditions this can produce the characteristic approximately once-per-minute Recovery pattern.

It must not be interpreted as a mathematically permanent loop that firmware can never leave without reboot.

Patch C-C corrects C1a, C1b and C2 while deliberately retaining Recovery for a **fresh valid** `real_beacon_skip` value of `1` or `2`.

Hardware testing confirmed the intended distinction:

- the demonstrated stale-evidence recurrence is removed
- the first eligible post-Recovery sample establishes a new baseline
- historical `real_beacon_skip` is not treated as fresh Recovery evidence
- later fresh measurements may still produce `1` or `2`
- those fresh measurements may still trigger Recovery

An important unresolved question remains:

> Does a fresh low `real_beacon_skip` actually represent a physical or protocol condition that requires Beacon Recovery?

That has not been established.

The detailed estimator arithmetic and beacon-counter interpretation are documented separately in:

[`real-beacon-skip.md`](real-beacon-skip.md)

and:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

---

# 1. Recovery Trigger

The Recovery decision uses the internally cached:

```text id="p3r6wm"
real_beacon_skip
```

value.

For clarity:

```text id="23rfor"
C = current received-beacon counter
P = previous received-beacon baseline
R = cached real_beacon_skip
H = shared temporary PM / Recovery countdown
```

Firmware 2.2.4 obtains the relevant WF200 statistics through command:

```text id="jq84s5"
0x66
```

The host derives `R` approximately from:

```text id="w0suxv"
delta = C - P
R = uint8_t(600 / delta)
```

Stock Recovery later interprets the stored byte as signed and approximately tests:

```text id="4z84uk"
signed_R != 0
&&
signed_R <= 2
```

Beacon Recovery is therefore triggered by a host-derived estimator.

It is not triggered by direct readback of the programmed WF200 listen interval.

It is also not directly triggered by the separate WF200:

```text id="w1vo87"
D3 PS_MODE_ERROR
```

indication.

---

# 2. What `real_beacon_skip` Represents

The name can be misleading.

`real_beacon_skip` is not:

- a WF200 register readback
- a direct listen-interval readback
- a physical RF-sleep measurement
- a direct indication of WF200 sleep residency

It is calculated by the Shelly host from received-beacon statistics.

For example:

```text id="17fzhg"
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not mean:

```text id="qhczfj"
host requested 20
WF200 reported 1
```

It means:

```text id="9zmlya"
host requested 20

and

the host beacon-density estimator calculated 1
```

A low `real_beacon_skip` therefore does not by itself prove that:

- WF200 rejected the requested listen interval
- the programmed PM mode was lost
- WF200 remained physically awake
- WF200 listened to every AP beacon
- a WF200 power-save error occurred

---

# 3. C1a — Signed Control Interpretation

The calculated `real_beacon_skip` value is stored as an unsigned byte.

Stock Recovery later interprets the byte as signed.

This creates additional qualifying values.

For example:

```text id="v97u8d"
delta = 3

600 / 3 = 200
uint8_t = 200
int8_t  = -56
```

and:

```text id="y6f54f"
delta = 4

600 / 4 = 150
uint8_t = 150
int8_t  = -106
```

Both negative signed values satisfy:

```text id="2bifud"
signed_R <= 2
```

For fresh positive counter deltas, the stock trigger domain therefore includes unexpected cases such as:

```text id="y82me1"
delta = 3
delta = 4
delta = 201..600
```

Patch C-C performs the Recovery decision using the intended unsigned interpretation.

The corrected fresh trigger is restricted to:

```text id="1u5at7"
R = 1
```

or:

```text id="167wxb"
R = 2
```

The diagnostic `real_beacon_skip` value itself remains available.

---

# 4. C1b — Measurement-Window Validity

The estimator assumes that:

```text id="vb63zh"
C - P
```

represents the intended measurement interval.

However, `P` has no elapsed-time metadata used by this calculation.

Firmware events can interrupt the normal measurement progression while preserving an older baseline.

A later successful sample can therefore compare:

```text id="3r5bgc"
old P
```

with:

```text id="4wpv7w"
new C
```

while still using the fixed:

```text id="32gg1z"
600
```

numerator.

The cumulative WF200 beacon counter may itself be correct while the resulting host estimate no longer corresponds to the intended observation window.

Patch C-C invalidates the measurement baseline when identified events break measurement continuity.

The next successful eligible sample establishes a new baseline rather than calculating `R` from an obsolete one.

---

# 5. C2 — Post-Recovery Freshness Failure

C2 explains the characteristic repeating Recovery behavior observed on affected stock 2.2.4 devices.

Assume a fresh valid measurement produces:

```text id="khle2r"
R = 2
```

and Recovery occurs.

The Recovery path resets:

```text id="ognt0v"
P = 0
```

while retaining:

```text id="1rgtav"
R = 2
```

Retaining `R` is useful diagnostically.

The defect appears at the next successful statistics sample.

Because:

```text id="e58912"
P == 0
```

firmware cannot calculate a fresh ratio.

It therefore performs:

```text id="wjpvqs"
P = C
```

This is a baseline-establishment sample.

Stock firmware can nevertheless continue into the Recovery decision using the historical cached:

```text id="scwe7b"
R = 2
```

The sequence can therefore become:

```text id="pbxxla"
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
Recovery again
```

A new qualifying beacon measurement is not required for that next Recovery.

---

# 6. C2 Is Metastable, Not Necessarily Permanent

The stale-evidence recurrence must be described carefully.

The demonstrated behavior is:

```text id="l7aaku"
historical qualifying R
        |
        v
baseline reset
        |
        v
baseline-only sample
        |
        v
historical R reused
        |
        v
Recovery recurrence
```

This can repeat for long periods and historically produced approximately one Recovery per minute on affected devices.

However, the firmware can leave this recurrence if other state changes alter the cached evidence, measurement progression or surrounding PM/network state.

Therefore the correct description is:

```text id="vpmtlg"
metastable stale-evidence recurrence
```

rather than:

```text id="1k9gkg"
permanent loop until reboot
```

This distinction matters when correlating logs from devices that show long Recovery bursts followed by periods with fewer events.

---

# 7. Successful PM Restoration Does Not Necessarily Break C2

WF200 can successfully return to normal power saving after a Recovery.

For example:

```text id="2tahtf"
Recovery
   |
   v
state 1
   |
   | ~5 serviced seconds
   v
state 3
skip 20
```

may complete successfully.

That does not itself invalidate the historical cached `R`.

Therefore both can be true:

```text id="cqjkss"
the Recovery transition completed successfully
```

and:

```text id="hejzti"
the host-side freshness defect still permits
historical Recovery evidence to recur
```

The repeated stock pattern is therefore not proof that WF200 failed to recover on every cycle.

---

# 8. Recovery Sequence

Once Recovery is accepted, the normal sequence is approximately:

```text id="z16k8n"
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

Recovery therefore changes real PM policy.

It is not merely a log message or diagnostic counter increment.

---

# 9. Shared Recovery Countdown `H`

Beacon Recovery sets:

```text id="dz2p8p"
H = 5
```

The same field participates in other temporary PM behavior and may contain values such as:

```text id="usr7gq"
H = 180
```

`H` is therefore not a dedicated Boolean such as:

```text id="rx4r4w"
Beacon Recovery active
```

It is a shared temporary PM/recovery countdown.

For Beacon Recovery, `H = 5` normally corresponds to approximately five serviced seconds.

This is not an electrically guaranteed exact five-second interval.

Scheduler timing and other state changes can affect elapsed wall-clock time slightly.

---

# 10. WLAN State During Recovery

During normal Recovery, firmware requests:

```text id="z8scy7"
Active / Always-On
```

instead of the normal connected beacon-based power-save configuration.

Conceptually:

```text id="adpcgo"
normal connected operation
Fast Power Save
desired skip 20 / 15 / 10
        |
        | Recovery
        v
Active / Always-On
        |
        | approximately 5 serviced seconds
        v
restore connected power saving
with current desired beacon skip
```

Recovery therefore changes WF200 PM policy.

It still does not directly reveal the physical RF state before, during or after that command.

---

# 11. Host Sleep During Recovery

Recovery also affects host-MCU sleep eligibility.

The earlier investigation sometimes described the normal host state too broadly as allowing EM3.

Later host-sleep analysis established that normal firmware intentionally keeps a B3 contribution active because the RTC/tickless architecture depends on the low-frequency clock domain.

Therefore normal deepest intended host idle is:

```text id="c7z5kn"
EM2
```

not EM3.

Conceptually:

```text id="9sl24l"
normal connected idle:

B2 = 0
B3 != 0
    |
    v
EM2 permitted
```

During Recovery, temporary B2-related ownership can instead restrict the host to:

```text id="w52ch4"
EM1
```

Therefore the useful comparison is:

```text id="6a0fra"
normal:
EM2 may be permitted

Recovery:
EM1 may be the deepest permitted host state
```

This does not mean the host CPU runs continuously throughout Recovery.

EM1 can still be entered.

---

# 12. Restoration of Power Saving

When the Recovery countdown expires, firmware restores the application PM policy.

If normal connected beacon power saving is restored, the current:

```text id="5ivcje"
desired_beacon_skip
```

is used.

For example:

```text id="c38cuy"
state 3
skip 15
   |
   | Recovery
   v
state 1
Active / Always-On
   |
   | approximately 5 serviced seconds
   v
state 3
skip 15
```

The desired skip may change independently over time according to the normal policy.

Runtime testing has shown values including:

```text id="yd5i7d"
desired_beacon_skip = 20
```

and:

```text id="9fbqyc"
desired_beacon_skip = 15
```

while Recovery restoration remained functional.

---

# 13. Recovery Is an Indirect Heuristic

A temporary transition:

```text id="3xqaiy"
Fast Power Save
        |
        v
Active / Always-On
        |
        v
Fast Power Save
```

is technically plausible as a recovery/reconfiguration strategy.

What has not been demonstrated is that a fresh:

```text id="g6bg55"
real_beacon_skip = 1
```

or:

```text id="y7o092"
real_beacon_skip = 2
```

proves a condition requiring that transition.

No direct evidence establishes that a fresh low estimator value means:

- WF200 failed to enter power save
- the requested listen interval was rejected
- the requested listen interval was lost
- WF200 remained physically awake
- a PM transition must be reapplied

The implementation therefore behaves like a host-side beacon-density health heuristic.

The original design rationale is unknown.

---

# 14. Historical Patch A — Recovery Isolation

Patch A was an early isolation experiment.

It bypassed the Recovery action while preserving statistics and estimator calculation.

Conceptually:

```text id="8e8bma"
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

This established that the Recovery action could be removed independently of ordinary RSSI-dependent beacon-skip selection.

Patch A also prevents Recovery after a genuinely fresh qualifying measurement.

It therefore answers:

```text id="t5um19"
What happens if Recovery is removed?
```

not:

```text id="1se8tg"
How should Recovery itself be corrected?
```

Patch A remains historically useful but is not the preferred corrective design.

---

# 15. Historical Patch B — mDNS Isolation

Patch B suppresses the targeted periodic connected-state mDNS restart.

It does not intentionally modify:

- WF200 command `0x66`
- beacon statistics
- `real_beacon_skip`
- Recovery predicate
- Recovery action
- RSSI-dependent desired skip

Runtime testing showed that Beacon Recovery continued while the targeted periodic mDNS behavior was suppressed.

Therefore the targeted periodic mDNS restart is not required for the observed Recovery recurrence under those conditions.

This does not mean unrelated network traffic can never affect beacon statistics.

---

# 16. Patch C-C

Patch C-C corrects validity semantics around Beacon Recovery rather than disabling Recovery.

Its requirements are:

1. preserve diagnostic `real_beacon_skip`
2. correct signed control interpretation
3. invalidate unusable measurement baselines
4. distinguish baseline establishment from a fresh measurement
5. prevent historical `R` from acting as fresh Recovery evidence
6. preserve Recovery for fresh valid `R = 1` or `R = 2`
7. preserve unrelated WLAN and PM behavior

Conceptually:

```text id="f6b4mw"
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

```text id="18uz9d"
P = 0
R retained diagnostically
        |
        v
next eligible sample
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

# 17. C-C Hardware Validation

C-C was tested on physical hardware.

The expected post-Recovery progression was observed:

```text id="h0pz72"
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

This differs from stock C2:

```text id="y34p0e"
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

Hardware therefore confirmed the distinction between:

```text id="g7aq71"
historical diagnostic value
```

and:

```text id="q34t83"
fresh Recovery evidence
```

---

# 18. Fresh Recovery Still Occurs After C-C

C-C does not make all Recovery disappear.

Historical corrected test periods showed approximately:

```text id="38oy0z"
27–30 fresh Recoveries/hour
```

when fresh measurements repeatedly qualified.

This must not be treated as a universal C-C rate.

It reflects specific historical test conditions and measurement cadence.

The corrected behavior is:

```text id="wv03ur"
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

rather than:

```text id="24w9vq"
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

The cause and significance of fresh low estimator values remain unresolved.

---

# 19. The Estimator Is Not Permanently Stuck at `1`

Runtime testing has produced:

```text id="78afp2"
desired_beacon_skip = 20
real_beacon_skip    = 1
```

but also later:

```text id="izfu8b"
desired_beacon_skip = 15
real_beacon_skip    = 13
```

The estimator is therefore capable of values close to the requested skip.

It is not simply frozen at `1`.

This still does not turn it into physical WF200 PM telemetry.

---

# 20. Historical Stock Recovery Rate

The D3-observer device provided a long-running historical example of stock 2.2.4 behavior.

Approximately:

```text id="0ry19b"
runtime:              63.93 h
Beacon Recoveries:    3835
Recovery rate:        ~59.99/hour
desired skip:         20
real skip:            1
D3 PS_MODE_ERROR:     0
```

were observed.

The average Recovery rate was almost exactly one event per minute.

This is consistent with the characteristic stock stale-evidence recurrence.

At approximately five serviced seconds per Recovery:

```text id="agz3v3"
60 Recoveries/hour
× ~5 s
≈ 300 s/hour
≈ 5 min/hour
≈ 8.33% wall-clock Recovery occupancy
```

Across the complete period:

```text id="qrvm53"
3835 × ~5 s
≈ 19175 s
≈ 319.6 min
≈ 5.33 h
```

of explicit Recovery occupancy accumulated.

These values describe wall-clock time, not battery energy.

---

# 21. Historical C-C Recovery Occupancy

Under the specific historical measurement cadence, one baseline-establishment sample was required before another fresh estimator result could be formed.

If every later fresh result qualified, this produced an approximate historical upper cadence of:

```text id="6fzbvf"
~30 fresh Recoveries/hour
```

At approximately five seconds each:

```text id="0iwt8r"
30 × ~5 s
≈ 150 s/hour
≈ 2.5 min/hour
≈ 4.17% wall-clock occupancy
```

A measured historical period of approximately:

```text id="2u70l3"
27 fresh Recoveries/hour
```

corresponds to:

```text id="a4uwgt"
~135 s/hour
~2.25 min/hour
~3.75% wall-clock occupancy
```

These figures are historical measurements and cadence-dependent calculations.

They are not a protocol limit and not a battery percentage.

---

# 22. Relationship to WF200 `D3 PS_MODE_ERROR`

WF200 provides a separate host-visible PM error channel:

```text id="dibro4"
D3 PS_MODE_ERROR
```

Known reason values include conditions such as:

```text id="5qx8th"
0  PS-Poll timeout
1  U-APSD timeout
2  buffered unicast not delivered across consecutive beacons
3  unstable beacon timing / beacon-window compensation
```

This channel is more direct than Shelly's host-derived `real_beacon_skip` estimator.

A dedicated historical D3 observer monitored both mechanisms in parallel:

```text id="kubng9"
Shelly host heuristic:

beacon statistics
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery
```

and:

```text id="8ghkrw"
WF200 error channel:

WF200
   |
   v
D3 PS_MODE_ERROR
```

During approximately 63.9 hours:

```text id="7tr97s"
Beacon Recovery events: 3835
D3 PS_MODE_ERROR:       0
```

No observed Recovery in that test can therefore be associated with a reported D3 PM error.

No D3 error can be shown to have been cleared by Recovery because no D3 error was observed.

---

# 23. What the D3 Result Establishes

The D3 experiment does **not** prove that Beacon Recovery has no purpose.

It does establish that:

```text id="mcy9xb"
Shelly Beacon Recovery
```

and:

```text id="70ecbe"
WF200 D3 PS_MODE_ERROR
```

are not equivalent mechanisms.

The observed sequence was:

```text id="xdifcf"
host beacon statistics
        |
        v
host real_beacon_skip estimate
        |
        v
Shelly Beacon Recovery
```

while the known WF200 PM-error channel remained silent.

The evidence therefore does not support describing the repeated Recovery pattern as a direct reaction to WF200-reported D3 errors.

D3 is not a complete physical RF-sleep monitor, so other undocumented or unreported WF200 conditions cannot be excluded solely from this result.

---

# 24. Relationship to WF200 3.18.0

Official Silicon Labs WF200 firmware 3.18.0 includes a relevant power-management fix for an error that could prevent the device from sleeping after a power-save mode change.

That fix is directly relevant because Beacon Recovery repeatedly changes PM modes.

However:

```text id="fgqfc3"
WF200 3.18.0
```

does not correct:

```text id="q8vdzr"
Shelly host C1a/C1b/C2
```

Testing with updated WF200 firmware but stock Shelly Recovery logic still showed the host-side Recovery recurrence.

That separation is expected.

---

# 25. Historical A1 + C-C + WF200 3.18.0 Integration

An earlier integrated experimental platform combined:

```text id="mya5yr"
A1
+
C-C
+
WF200 3.18.0
```

This successfully operated on physical TRV hardware through:

- OTA
- reboot
- WF200 initialization
- WLAN scan
- association
- DHCP
- cloud connection
- PM transitions
- thermostat operation
- valve movement
- calibration

Fresh Recovery still occurred because C-C intentionally retained fresh valid Recovery.

This was an important historical integration step.

It is no longer the current corrected platform because A1 was later superseded by A1R and the B2 correction was added.

---

# 26. A1R and Current Integrated Baseline

The current PM lifecycle implementation is:

```text id="u93vke"
A1R
```

not A1.

A1R retains the historical A1 lifecycle corrections while correcting an experimental A1 regression involving verified temporary `request1` override paths.

The current observer-free integrated baseline is:

```text id="5tctjm"
B2.1
```

containing:

```text id="43bybs"
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

For Beacon Recovery, the relevant correction remains C-C.

The other B2.1 components address different defect classes.

---

# 27. B2.1_OBS

The current long-term hardware diagnostic firmware is:

```text id="kkho5b"
B2.1_OBS
```

defined as:

```text id="rp66nu"
B2.1
+
PM52 -> cmd66 observer
```

The observer records already-existing PM52 and command-0x66 activity.

It records:

- PM52 payloads
- native PM52 results
- A1R completion decisions
- existing periodic cmd66 requests/results
- estimator operands
- connection epochs
- a short recent-event ring
- first-fault freeze state

It introduces no additional WF200 request.

It adds no:

```text id="erjn7o"
new timer
new task
new queue
automatic network traffic
flash write
Recovery policy change
```

The current observer therefore measures the corrected integrated system rather than deliberately modifying the Recovery mechanism.

---

# 28. Current Hardware Experiment

The active long-term population is:

```text id="i23la8"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The current research decision is:

```text id="wxc0g8"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

This is important for Recovery interpretation.

The project is **not currently**:

- disabling Recovery
- applying additional Recovery rate limits
- changing AP/network conditions deliberately
- flashing B2.2 onto the test population
- introducing a new Recovery hypothesis

The current objective is long-term comparative evidence.

---

# 29. Early B2.1_OBS Observation

During the initial observed period, the B2.1_OBS devices showed:

```text id="a0k2gv"
beacon_err = 0
```

while the stock 2.2.4 control had already accumulated thousands of historical Beacon Recovery errors.

This is an early observation only.

It does not establish:

```text id="oerjgf"
C-C permanently eliminates all fresh Recovery
```

and does not establish:

```text id="l6ejc2"
B2.1_OBS solves battery drain
```

The test is specifically intended to continue long enough to distinguish short-term behavior from battery-lifetime behavior.

---

# 30. Why Recovery Is Not Being Disabled Now

Recovery removal was historically considered as a separate experiment.

Patch A demonstrated that the action can be bypassed.

However, the current long-term experiment has a different purpose.

It asks:

```text id="vhu2gn"
Does the integrated corrected platform
still develop genuine battery drain?
```

Removing Recovery now would change another variable and reduce causal clarity.

Therefore fresh valid Recovery remains enabled through C-C.

If B2.1_OBS drains, first-fault telemetry should be analyzed before introducing a new no-Recovery experiment.

If B2.1_OBS remains stable long term, the observer should be removed and an observer-free corrected build should first undergo hardware regression.

A no-Recovery test is therefore not the current next step.

---

# 31. Recovery Frequency as a Trade-Off

The visible Recovery overhead is real:

```text id="h79wfm"
more Recoveries
        |
        v
more explicit Active / Recovery time
```

A second possible effect remains hypothetical:

```text id="4nlu65"
unknown WF200 fault exists
        |
        v
Recovery happens to clear it
        |
        v
less frequent Recovery
could allow the fault to persist longer
```

Because the second mechanism has not been demonstrated, Recovery frequency cannot currently be optimized from occupancy calculations alone.

C-C therefore takes a conservative position:

```text id="pp4644"
remove invalid/stale triggers
+
retain fresh valid Recovery
```

---

# 32. Energy-Consumption Relevance

Repeated Beacon Recovery creates a credible additional workload.

During each event:

- WF200 is woken/configured as required
- Active / Always-On PM is requested
- host deep-idle eligibility can be reduced to EM1
- extra host/WLAN control activity occurs
- the temporary state normally lasts about five serviced seconds

The historical stock example reached approximately:

```text id="fkqj99"
~300 s/hour
```

of explicit Recovery occupancy.

Historical corrected C-C periods were closer to:

```text id="bqbx0n"
~135–150 s/hour
```

under the specific observed cadence.

The project has not directly measured:

```text id="arcz1m"
WF200 current during Recovery
host current delta
energy per Recovery
daily Recovery energy
battery-runtime loss caused by Recovery alone
```

Therefore wall-clock Recovery occupancy cannot be converted directly into battery-consumption percentage.

---

# 33. Relationship to Historical Battery Drain

The 2.2.4 Beacon Recovery defects are credible battery-consumption amplifiers.

They cannot currently be described as:

```text id="ngsm4j"
the original Shelly TRV Gen1 battery-drain root cause
```

or:

```text id="td83po"
the only drain mechanism
```

Battery drain was also observed on earlier 2.1.x firmware.

The analyzed 2.2.4 Recovery implementation therefore cannot explain the full historical problem by itself.

A more defensible model is:

```text id="1mh57m"
older shared mechanisms
    |
    +-- PM lifecycle
    +-- blocker accounting
    +-- radio PM behavior
    +-- peripheral/resource lifecycle

2.2.4-specific behavior
    |
    +-- aggressive Beacon Recovery
    +-- C1a/C1b/C2 validity defects
```

Beacon Recovery may amplify consumption without being the original common cause.

---

# 34. No Explicit TX-Power Increase Identified

No application-level WLAN transmit-power increase was identified in the normal Beacon Recovery path.

The demonstrated action is a PM-mode transition.

The supported statement is:

> No explicit application-level WLAN transmit-power increase was identified in the normal Beacon Recovery sequence.

This does not rule out internal lower-level RF behavior changes.

---

# 35. No Normal Scan, Reconnect or DHCP Path Identified

No normal direct Beacon Recovery path has been identified that performs:

- WLAN scan
- AP selection
- ordinary disconnect
- ordinary reconnect
- reassociation
- DHCP negotiation
- complete WLAN-driver initialization
- full WLAN subsystem reset

The normal sequence is much narrower:

```text id="h85pqr"
wake
 |
 v
Active / Always-On
 |
 v
temporary deeper-sleep restriction
 |
 | approximately 5 serviced seconds
 v
restore application PM state
```

A reconnect, DHCP event or scan near a Recovery event should therefore not automatically be attributed to normal Beacon Recovery.

---

# 36. Exceptional Driver-Lock Reset Path

A separate exceptional path exists in the WLAN/PM logic.

If a relevant WLAN driver-lock operation fails, firmware may initialize another countdown that eventually requests a host reset.

This is separate from ordinary Beacon Recovery.

Normal Recovery:

```text id="0opgq9"
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

```text id="vsm5zv"
driver-lock failure
        |
        v
separate countdown
        |
        v
MCU system reset
```

These mechanisms must not be conflated.

---

# 37. Current Patch and Build Roles

| Patch / Build | Purpose | Beacon Recovery behavior |
|---|---|---|
| Patch A | Historical isolation experiment | Recovery action bypassed |
| Patch B | Historical mDNS isolation | Recovery unchanged |
| Patch A+B | Combined historical isolation | Recovery and targeted mDNS behavior bypassed |
| C-C | Current Recovery correction | C1a/C1b/C2 corrected; fresh valid Recovery retained |
| Historical A1 + C-C + WF200 3.18.0 | Earlier integrated platform | C-C Recovery behavior with historical A1 |
| B2.1 | Current corrected observer-free baseline | C-C Recovery behavior with A1R/B2/WF200 3.18 |
| B2.1_OBS | Current long-term hardware diagnostic build | Same Recovery policy as B2.1; observer only |
| B2.2 | Offline observer-free release candidate | C-C retained; additional qualified corrections |

C-C remains the Beacon Recovery correction.

A1R, B2 serialization and other B2.1/B2.2 corrections address different defect domains.

---

# 38. B2.2 and Recovery

B2.2 contains C-C unchanged as its Beacon Recovery correction component.

Its full selected correction set is:

```text id="jkfgnu"
1. A1R including A1 lifecycle correction
2. C-C
3. B2 serialization
4. minimal MQTT PUBLISH guard
5. WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

B2.2 is currently:

```text id="87fpym"
OFFLINE RELEASE-CANDIDATE GO
```

It has not been rolled onto physical hardware in the current phase.

Therefore B2.2 provides no new hardware evidence about Recovery frequency or battery behavior.

---

# 39. Remaining Questions

The Recovery implementation itself is now substantially understood.

The main unresolved questions are:

1. Why do some fresh valid measurements still produce `real_beacon_skip = 1` or `2`?

2. Do those fresh low values correspond to a real WF200 PM problem?

3. Does the Active→Power-Save Recovery transition correct any measurable physical or protocol fault?

4. Why did more than 3,800 historical Beacon Recoveries occur with zero observed D3 `PS_MODE_ERROR` events?

5. Does WF200 3.18.0 materially change the underlying physical condition that the Shelly heuristic attempted to detect?

6. If B2.1_OBS develops drain, does first-fault PM52/cmd66 telemetry reveal an abnormal transition before the voltage decline?

7. If B2.1_OBS remains stable, which subset of the integrated corrections materially contributed?

8. What is the electrical energy cost of one Recovery event?

9. How much of the historical battery drain predates and is independent of 2.2.4 Beacon Recovery?

These questions require runtime evidence rather than further reinterpretation of the same static Recovery code.

---

# 40. Question for Shelly

One original-design question remains particularly important:

> What actual WF200 or WLAN failure condition was a calculated `real_beacon_skip = 1` or `2` intended to detect, and why was an Active-to-Power-Save transition considered the appropriate recovery action?

A related question is:

> What host-visible condition was expected to confirm that the WF200 had returned to correct low-power operation after that Recovery transition?

The reverse engineering establishes the host-side estimator and action.

It does not establish the original design rationale.

The historical D3 observation makes this especially relevant:

```text id="3fix2z"
~63.9 h runtime
3835 Shelly Beacon Recoveries
~59.99 Recoveries/hour
0 WF200 D3 PS_MODE_ERROR events
```

Clarifying the original design intent would help distinguish between:

```text id="mglcf5"
necessary WLAN reliability mechanism
```

and:

```text id="g3rclm"
indirect heuristic workaround for
another PM condition
```

---

# 41. Current Stock 2.2.4 Model

The reconstructed stock path is approximately:

```text id="6d20kv"
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
host restricted toward EM1
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
historical R may be evaluated
        |
        +---- C2 stale-evidence recurrence
```

This recurrence can persist for long periods but is metastable rather than necessarily permanent.

---

# 42. Current C-C Model

C-C changes the post-Recovery sequence to:

```text id="l6kktv"
fresh valid unsigned R = 1/2
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
        +---- R = 1/2  -> new fresh Recovery
```

This behavior has been demonstrated on hardware.

---

# 43. Current Conclusion

Shelly TRV Gen1 firmware 2.2.4 contains a host-side Beacon Recovery mechanism that temporarily moves WLAN power management away from the normal connected low-power configuration.

Three demonstrated defects affect the validity of the evidence used to request this action:

```text id="1qbdve"
C1a
signed control interpretation

C1b
measurement-window validity

C2
post-Recovery evidence freshness
```

C2 can produce a long-lived metastable stale-evidence recurrence in which historical qualifying `R` is reused after a baseline-only sample.

Historical stock testing recorded:

```text id="z8d8fd"
~63.93 h runtime
3835 Beacon Recoveries
~59.99 Recoveries/hour
0 D3 PS_MODE_ERROR
```

At approximately five serviced seconds per Recovery, that corresponds to roughly:

```text id="fr1arx"
~300 s/hour
~5 min/hour
~8.33% wall-clock Recovery occupancy
```

This is not an energy percentage.

Patch C-C corrects C1a, C1b and C2 while retaining fresh valid Recovery.

Historical C-C test periods showed approximately:

```text id="ur1135"
27–30 fresh Recoveries/hour
```

under specific runtime conditions.

Those historical values are not a universal limit.

The D3 experiment establishes that the repeated Shelly Recovery pattern cannot simply be described as repeated WF200-reported `PS_MODE_ERROR` handling.

The current corrected platform is no longer the historical:

```text id="eag2cx"
A1 + C-C + WF200 3.18.0
```

stack.

The current hardware diagnostic platform is:

```text id="zqixyq"
B2.1_OBS
```

which contains:

```text id="dd6mmt"
A1R
+
C-C
+
B2 bounded serialization
+
minimal MQTT PUBLISH guard
+
WF200 3.18.0
+
PM52 -> cmd66 observer
```

The current test population is:

```text id="88c4i8"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The present research decision is:

```text id="obm1te"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

Fresh Recovery is therefore deliberately left enabled.

The project is not currently attempting to optimize Recovery frequency or disable the mechanism.

The central unresolved question remains:

```text id="6qq74i"
Does a fresh real_beacon_skip of 1 or 2
actually identify a condition that requires Recovery?
```

Current evidence does not answer that question.

Beacon Recovery remains a credible 2.2.4-specific additional workload and possible drain amplifier.

It is not established as the sole or original Shelly TRV Gen1 battery-drain cause.

---

# Related Documents

Detailed `real_beacon_skip` analysis:

[`real-beacon-skip.md`](real-beacon-skip.md)

WF200 beacon-counter analysis:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Periodic mDNS behavior:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Experimental patch documentation:

[`../patch/README.md`](../patch/README.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Notes

This analysis combines static reverse engineering with runtime experiments on personally owned Shelly TRV Gen1 devices.

The Recovery path was traced through:

- WF200 statistics command `0x66`
- `real_beacon_skip` calculation
- baseline handling
- Recovery predicate
- PM-state logic
- WF200 PM requests
- host sleep restrictions
- Recovery restoration
- post-Recovery measurement progression

Runtime experiments include:

- stock debug-log observation
- `/stats` observation
- RSSI and desired-skip comparison
- Patch A
- Patch B
- combined isolation testing
- C-C hardware testing
- D3 `PS_MODE_ERROR` observation
- WF200 3.18.0 testing
- historical A1+C-C+WF200 3.18.0 testing
- B2.1/B2.1_OBS qualification
- current long-term battery observation

Historical builds remain labeled according to the firmware actually used.

A1 results are not relabeled as A1R.

Historical C-C rates are not presented as universal protocol limits.

No original or modified complete Shelly firmware image, proprietary complete function or large raw disassembly is published in this document.

The project distinguishes between:

```text id="23rdpw"
what host firmware demonstrably does

what runtime telemetry reports

what executable qualification establishes

what can actually be concluded about
physical WF200 and host power state
```

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The analysis applies to the firmware versions and hardware investigated here.

Experimental firmware should only be used on devices where recovery or reflashing is possible.