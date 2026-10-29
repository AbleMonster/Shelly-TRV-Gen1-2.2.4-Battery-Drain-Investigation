# `real_beacon_skip` Analysis

## Overview

Shelly TRV Gen1 firmware 2.2.4 maintains two different beacon-skip values:

- `desired_beacon_skip`
- `real_beacon_skip`

Despite the names, these values do not represent the same thing.

`desired_beacon_skip` is the listen interval selected by the Shelly host application as part of its WLAN power-save policy.

`real_beacon_skip` is calculated by the host from WF200 received-beacon statistics.

It is an estimator derived from the number of received beacons observed between statistics samples.

This distinction is critical when interpreting `/stats` and the firmware log:

```text id="xxnqsd"
Beacon skip error! Attempt recovery
```

That message is not a direct WF200 error indication.

In particular, `real_beacon_skip` is:

- not a readback of the listen interval programmed into WF200
- not a direct indication of physical WF200 sleep
- not a direct count of intentionally skipped beacons
- not a direct measure of radio sleep residency
- not the WF200 `PS_MODE_ERROR` indication

Three host-side validity defects were identified in the way firmware 2.2.4 calculates and uses this value for Beacon Recovery:

```text id="i8811p"
C1a
signed interpretation of an unsigned calculated value

C1b
reuse of a beacon-counter baseline across invalid measurement epochs

C2
reuse of historical real_beacon_skip as fresh Recovery evidence
```

Patch C-C corrects all three while retaining Recovery for a genuinely fresh valid measurement that produces:

```text id="grvx3u"
real_beacon_skip = 1
```

or:

```text id="ln93q5"
real_beacon_skip = 2
```

C2 can create a long-lived stale-evidence recurrence.

That recurrence is best described as **metastable**, not necessarily permanent.

The current long-term research platform is:

```text id="1xkxom"
B2.1_OBS
```

which combines the corrected estimator/Recovery behavior with A1R, bounded B2 serialization, WF200 3.18.0 and a PM52→cmd66 observer.

The purpose of the current test is not to further modify the estimator.

It is to determine whether genuine battery drain still develops after the qualified corrections have been integrated.

---

# 1. `desired_beacon_skip`

`desired_beacon_skip` represents the beacon-listen interval selected by the application.

The RSSI-dependent policy found in firmware 2.2.4 is:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

Conceptually:

```text id="ffzkxo"
RSSI
 |
 v
desired_beacon_skip
 |
 v
requested WLAN power-save configuration
```

This is a configuration value.

It describes host intent.

---

# 2. `real_beacon_skip`

`real_beacon_skip` is calculated differently.

Firmware 2.2.4 periodically obtains WF200 statistics using command:

```text id="7xb8vi"
0x66
```

The returned statistics include fields such as:

```text id="tlpd1k"
beacon_rx_count
beacon_rx_missed_count
beacon_tbtt_diff
```

The known `real_beacon_skip` calculation uses the cumulative:

```text id="tsja0m"
beacon_rx_count
```

and maintains a previous counter baseline.

For the following sections:

```text id="hva1ol"
C = current beacon_rx_count
P = previous beacon_rx_count
R = real_beacon_skip
```

For a valid comparable pair of samples, firmware calculates approximately:

```text id="xhaxrw"
delta = C - P
R = uint8_t(600 / delta)
```

The constant:

```text id="8d59j3"
600
```

is present directly in the firmware.

Its exact original design rationale is not documented.

The surrounding periodic logic is consistent with an estimator based on roughly 600 nominal beacon opportunities during the intended observation interval.

The important point is that `R` is derived from **received-beacon density**.

WF200 is not queried for an "effective beacon skip" value.

Therefore:

```text id="1fub62"
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not mean:

```text id="d4kjx0"
host requested skip 20
WF200 reported effective skip 1
```

The second value is a host-side estimate.

---

# 3. `/stats`

The value exposed as:

```text id="l2gaxr"
real_beacon_skip
```

through `/stats` comes from the same internal byte later used by Beacon Recovery.

There is no separate estimator exclusively for the HTTP endpoint.

Conceptually:

```text id="lxjph1"
WF200 beacon_rx_count
        |
        v
host calculation
        |
        v
        R
       / \
      /   \
     v     v
 /stats   Recovery logic
```

This shared storage matters because:

```text id="w36o0m"
diagnostic history
```

and:

```text id="1lvyjb"
fresh control evidence
```

do not have the same validity requirements.

Keeping the latest calculated value visible through `/stats` is useful.

Using that historical value to trigger another Recovery without a new measurement is not.

---

# 4. C1a — Signed Control Interpretation

The calculation of `R` is unsigned.

The result:

```text id="5ixqhe"
600 / delta
```

is narrowed to one byte:

```text id="q38hmr"
R = uint8_t(600 / delta)
```

Stock Beacon Recovery later reads that byte as signed.

Its effective test is approximately:

```text id="9s140f"
signed_R = int8_t(R)

if signed_R != 0 && signed_R <= 2:
    Recovery
```

This creates trigger values unrelated to the intended positive `R = 1..2` condition.

Examples:

| Delta | `600 / delta` | Stored byte | Signed value | Stock Recovery |
|---:|---:|---:|---:|---|
| 1 | 600 | 88 | 88 | No |
| 2 | 300 | 44 | 44 | No |
| 3 | 200 | 200 | -56 | **Yes** |
| 4 | 150 | 150 | -106 | **Yes** |
| 5 | 120 | 120 | 120 | No |
| 6 | 100 | 100 | 100 | No |
| 200 | 3 | 3 | 3 | No |
| 201–300 | 2 | 2 | 2 | **Yes** |
| 301–600 | 1 | 1 | 1 | **Yes** |
| >600 | 0 | 0 | 0 | No |

For a fresh positive delta, the stock trigger domain therefore includes:

```text id="sdm61h"
delta = 3
delta = 4
delta = 201..600
```

The `delta = 3` and `delta = 4` cases exist only because the unsigned byte is reinterpreted as signed.

Example:

```text id="ef77mm"
delta = 3

600 / 3 = 200

uint8_t(200) = 200
int8_t(200)  = -56

-56 != 0
-56 <= 2
```

Both stock conditions pass.

C-C uses unsigned interpretation for the Recovery decision.

The diagnostic byte itself is preserved.

---

# 5. C1b — Measurement-Window Validity

The calculation:

```text id="kl6ve8"
600 / (C - P)
```

assumes that `C` and `P` represent the intended observation interval.

However, `P` carries no elapsed-time metadata used by the formula.

Several firmware conditions can interrupt normal statistics evaluation or alter PM state while retaining the old baseline.

One important example is the shared temporary PM countdown.

Values such as:

```text id="09ov31"
H = 180
```

and Beacon Recovery's:

```text id="98rd7o"
H = 5
```

can suppress normal periodic estimator progression.

Stock firmware may preserve `P` across such a discontinuity.

The next successful statistics sample can then compare:

```text id="2s9vqz"
old P
  |
  | measurement continuity interrupted
  |
new C

delta = new C - old P
R = 600 / delta
```

The WF200 cumulative counter may be completely correct.

The host estimate may still be invalid because the samples belong to different logical measurement epochs.

A simple:

```text id="mqhc4i"
C > P
```

check is insufficient.

It proves only that the counter increased.

It does not prove temporal comparability.

C-C invalidates `P` when known events break the measurement assumptions.

The next eligible sample establishes a new baseline.

---

# 6. C2 — Stale Recovery Evidence

C2 explains the characteristic repeating Beacon Recovery behavior observed on affected stock 2.2.4 devices.

Assume a valid fresh measurement produces:

```text id="k90jao"
R = 2
```

Stock firmware accepts the value and enters Recovery.

The Recovery path performs approximately:

```text id="1kk6dt"
H = 5
enter power-save state 1
P = 0
```

while preserving:

```text id="jn499h"
R = 2
```

Preserving `R` is not inherently wrong.

The value can remain useful as diagnostic history.

The problem occurs at the next successful statistics evaluation.

Because:

```text id="8x3k2d"
P == 0
```

a new delta cannot yet be calculated.

Firmware therefore establishes:

```text id="n3t5w8"
P = C
```

The resulting logical state is:

```text id="48ll3r"
new baseline available
no fresh R calculated
```

Stock code can nevertheless continue into the Recovery test using the historical cached `R`.

The sequence becomes:

```text id="y32s53"
fresh R = 2
   |
   v
Recovery
   |
   +---- P = 0
   |     R = 2 retained
   |
   v
next statistics sample
   |
   +---- P = C
   |     no fresh R calculated
   |
   v
old R = 2 tested again
   |
   v
Recovery
```

A new anomalous beacon measurement is therefore not required for that next Recovery.

---

# 7. C2 Is Metastable

Earlier project documentation described this as a self-sustaining Recovery loop.

That is useful for explaining the common repeating pattern but is too absolute if interpreted literally.

The demonstrated defect is better described as:

```text id="lziz37"
metastable stale-evidence recurrence
```

It can persist for long periods because the same cached evidence repeatedly survives baseline reset and baseline establishment.

Historically this produced approximately one Recovery per minute on some stock devices.

However, unrelated state changes can alter the estimator/control state and allow the firmware to leave the recurrence.

Therefore:

```text id="9p9l83"
long-lived recurring loop
```

is supported.

```text id="0h67e9"
must continue forever until reboot
```

is not.

---

# 8. Successful PM Restoration Does Not Necessarily Clear C2

The radio may successfully return to normal power-saving policy after each Recovery.

For example:

```text id="i6bhia"
Recovery
   |
   v
state 1
   |
   | ~5 serviced seconds
   v
state 3
```

can complete normally.

That does not itself replace or invalidate the historical cached `R`.

Therefore both can be true:

```text id="3nq3nq"
WF200 PM restoration succeeded
```

and:

```text id="1eejk4"
historical R remains eligible under stock
host control flow
```

The recurring stock log pattern is therefore not proof that WF200 failed to recover on every attempt.

---

# 9. Beacon Recovery

When stock Recovery accepts `R`, firmware logs:

```text id="cljl7i"
Beacon skip error! Attempt recovery
```

The observed sequence is approximately:

```text id="559y4c"
qualifying R
   |
   v
power-save state 1
   |
   v
Active / Always-On WLAN
   |
   | ~5 serviced seconds
   v
restore normal PM
   |
   v
power-save state 3
```

This is a real PM action.

It is not merely diagnostic logging.

However, the wording:

```text id="8iv57z"
Beacon skip error
```

must not be interpreted as a direct WF200 error report.

The trigger is the host-derived estimator described here.

WF200 `PS_MODE_ERROR` is separate.

---

# 10. Patch C-C

C-C was designed to correct the validity problems without removing Beacon Recovery.

Its intended behavior is:

```text id="8bhqrc"
preserve diagnostic R
preserve fresh R = 1..2 Recovery

reject signed-wrap triggers

invalidate unusable counter baselines

allow clean post-Recovery baseline establishment

reject historical R as fresh control evidence
```

For C1a:

```text id="ai7rs3"
R is interpreted as unsigned
for the Recovery decision
```

For C1b:

```text id="na55wo"
events that invalidate measurement continuity
also invalidate P
```

For C2:

```text id="24n1tk"
baseline-only sample
does not evaluate historical R
as fresh Recovery evidence
```

The essential distinction is:

```text id="suid28"
R may remain useful as diagnostic history

but

R is valid as Recovery control evidence
only when produced by a fresh valid measurement
```

C-C does not change command `0x66`.

It does not remove estimator calculation.

It does not force a particular desired listen interval.

Fresh valid `R = 1` or `R = 2` can still trigger Recovery.

---

# 11. Runtime Validation of C-C

Hardware testing confirmed the primary behavioral change.

Stock 2.2.4 can follow:

```text id="xr3ibm"
Recovery
   |
   v
baseline establishment
   |
   v
historical R reused
   |
   v
Recovery again
```

C-C follows:

```text id="pwrd55"
Recovery
   |
   v
baseline establishment
   |
   v
historical R rejected as control evidence
   |
   v
later comparable sample
   |
   v
fresh R calculated
```

A later fresh measurement may still produce:

```text id="s9h65f"
R = 1
```

or:

```text id="i2e9l3"
R = 2
```

and produce another Recovery.

That behavior was observed on hardware.

This result is central:

> C-C removes the demonstrated stale-evidence recurrence without hiding later fresh measurements that independently satisfy the Recovery predicate.

---

# 12. The Estimator Is Not Permanently Stuck at `1`

Runtime testing has shown:

```text id="51ehtw"
desired_beacon_skip = 20
real_beacon_skip    = 1
```

during some measurements.

Later observations also produced values such as:

```text id="egmlde"
desired_beacon_skip = 15
real_beacon_skip    = 13
```

The estimator can therefore produce substantially different values.

It is not permanently frozen at `1`.

This does not establish that the estimator accurately measures physical RF sleep.

It only establishes that it is responsive to observed beacon-count changes.

---

# 13. Historical C-C Recovery Frequency

During some historical corrected runs, fresh qualifying measurements produced approximately:

```text id="dg0mhd"
27–30 Recoveries/hour
```

This rate must be interpreted carefully.

It is not:

```text id="ofzpt5"
a fixed C-C rate
```

or:

```text id="k8rx9p"
a protocol-defined maximum
```

It resulted from the specific statistics cadence and runtime conditions.

Because a post-Recovery baseline-establishment sample cannot itself produce a fresh comparable `R`, the observed cadence often required an additional statistics interval before another Recovery became eligible.

---

# 14. Historical Stock Recovery Occupancy

A historical D3-observer device produced approximately:

```text id="prqxx3"
63.93 h runtime
3835 Beacon Recoveries
~59.99 Recoveries/hour
```

At about five serviced seconds per event:

```text id="n8rfne"
60 × ~5 s
≈ 300 s/hour
≈ 5 min/hour
≈ 8.33% wall-clock Recovery occupancy
```

This was effectively one Recovery per minute during that historical interval.

It is consistent with the stock C2 recurrence.

These values describe time spent in explicit Recovery.

They do not measure battery energy.

---

# 15. Historical C-C Recovery Occupancy

Under the historical measurement cadence:

```text id="v7zo3d"
~30 Recoveries/hour
× ~5 s
≈ 150 s/hour
≈ 2.5 min/hour
≈ 4.17% wall-clock occupancy
```

A historical measured interval of approximately:

```text id="uanlwb"
27 Recoveries/hour
```

corresponds to:

```text id="6tv01p"
~135 s/hour
~2.25 min/hour
~3.75% wall-clock occupancy
```

Again:

```text id="ta7eqd"
wall-clock occupancy
!=
battery consumption percentage
```

The current difference between normal PM operation and Recovery has not been directly measured electrically.

---

# 16. Relationship to `beacon_rx_missed_count`

WF200 also exposes:

```text id="2g5ccm"
beacon_rx_missed_count
```

The known `real_beacon_skip` calculation does not directly use this field.

It uses:

```text id="1d9rj9"
delta(beacon_rx_count)
```

instead.

Therefore Beacon Recovery is not equivalent to:

```text id="r8jclm"
if missed_beacons > threshold:
    recover()
```

This distinction matters because:

```text id="d3f31e"
intentionally unobserved beacon opportunities
```

and:

```text id="9hva68"
missed expected beacons
```

are not necessarily the same radio condition.

More detail is maintained in:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

---

# 17. Relationship to D3 `PS_MODE_ERROR`

WF200 exposes a separate PM error channel:

```text id="3kshh2"
D3 PS_MODE_ERROR
```

A historical dedicated observer recorded approximately:

```text id="7dh63f"
~63.9 h runtime
3835 Shelly Beacon Recoveries
0 D3 PS_MODE_ERROR events
```

Therefore the repeated Shelly Recoveries in that experiment were not direct reactions to observed D3 errors.

This does not prove WF200 had no internal PM anomaly.

D3 is not a continuous physical-sleep monitor.

It does establish that:

```text id="fmnhde"
real_beacon_skip
```

and:

```text id="es427z"
D3 PS_MODE_ERROR
```

are separate diagnostic/control channels.

---

# 18. Relationship to mDNS

Periodic mDNS and `real_beacon_skip` Recovery are separate mechanisms.

A historical firmware variant suppressed the targeted periodic connected-state mDNS restart while leaving Beacon Recovery intact.

Recovery continued.

Therefore the targeted periodic mDNS restart is not required for the observed Recovery behavior.

This does not imply that all network traffic is irrelevant to beacon statistics.

It only separates the specific mDNS mechanism.

---

# 19. Relationship to WF200 3.18.0

Official WF200 firmware 3.18.0 includes a relevant power-save fix for a condition that could prevent the radio device from sleeping after a PM-mode change.

That makes the update relevant to interpretation of `real_beacon_skip`.

However, replacing WF200 firmware does not correct:

```text id="us7vln"
C1a
C1b
C2
```

because those defects exist in Shelly host code.

Historical testing showed that WF200 3.18.0 alone did not eliminate the stock host Recovery recurrence.

---

# 20. Historical A1 + C-C + WF200 3.18.0

An earlier integrated hardware platform used:

```text id="gv4c3a"
A1
+
C-C
+
WF200 3.18.0
```

Hardware operation was demonstrated through:

- startup
- WF200 initialization
- association
- DHCP
- cloud connectivity
- PM transitions
- thermostat behavior
- valve movement
- calibration

Fresh qualifying Recovery still occurred.

That was expected because C-C intentionally retains fresh valid control evidence.

This build is now historical.

---

# 21. A1R and B2.1

The historical A1 lifecycle implementation was later replaced by:

```text id="6sg1xe"
A1R
```

after an experimental A1 regression was identified in temporary policy-override return paths.

The current corrected observer-free integrated baseline is:

```text id="s6rwc5"
B2.1
```

containing:

```text id="njn2dk"
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

For `real_beacon_skip`, C-C remains the directly relevant correction.

The other components address separate PM, blocker, transport or radio defect classes.

---

# 22. PM52→cmd66 Observer

The current diagnostic observer records both sides of the relevant host PM/statistics relationship.

It records:

```text id="4zjvxt"
PM52 requests
PM52 results
A1R completion decisions

cmd66 requests
cmd66 results

fresh estimator operands
connection epochs
```

plus a compact event history and first-fault freeze state.

The observer introduces no additional WF200 command.

That matters because new command traffic could itself change the system being observed.

The observer therefore allows `real_beacon_skip` to be interpreted in the context of the PM policy that existed around each measurement epoch.

---

# 23. B2.1_OBS

The current long-term hardware build is:

```text id="0rt3xq"
B2.1_OBS
```

defined as:

```text id="xm0yhv"
B2.1
+
PM52 -> cmd66 observer
```

Its purpose is not to change the estimator or Recovery trigger.

Its purpose is to observe the corrected integrated system.

The current test asks:

```text id="4x3i4w"
If genuine battery drain still occurs,
what PM52 / cmd66 / estimator state
appears around the first fault?
```

This is a different question from the earlier isolated C-C validation.

---

# 24. Current Hardware Population

The active experiment currently uses:

```text id="ts9doa"
.77  -> B2.1_OBS
.88  -> B2.1_OBS
.11  -> B2.1_OBS
.71  -> B2.1_OBS
.234 -> B2.1_OBS
.61  -> B2.1_OBS

.97  -> stock 2.2.4 control
```

or:

```text id="gjyl0i"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

Initial observed B2.1_OBS periods showed:

```text id="gyajwi"
beacon_err = 0
```

on the corrected devices.

The stock control retained thousands of accumulated Beacon Recovery errors and showed historical periods with approximately minute-scale recurrence.

These are early observations only.

They are not lifetime results.

---

# 25. Current Research Decision

The current research state is:

```text id="5mr3it"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

The estimator is therefore not currently being modified further.

The project is not currently:

- disabling fresh Recovery
- changing the constant `600`
- forcing a different `desired_beacon_skip`
- altering statistics cadence
- changing AP topology
- applying additional Recovery rate limits

Doing so now would introduce new variables into the long-term comparison.

---

# 26. What `real_beacon_skip` Does Not Tell Us

A low value does not by itself prove that:

- the programmed WF200 listen interval changed
- WF200 rejected the requested PM configuration
- WF200 is not physically sleeping
- the TRV listens to every AP beacon
- the AP changed its beacon interval
- RF transmit power increased
- frames were retransmitted
- the device changed AP
- poor RSSI alone caused the value
- a specific number of RF beacons was lost
- WF200 generated a PM error
- battery consumption increased by a specific amount

The supported statement is narrower:

> `real_beacon_skip` reports what the Shelly host estimator calculated from received-beacon statistics for the relevant measurement state.

---

# 27. Battery-Drain Relevance

Calculating `real_beacon_skip` itself is not the principal energy concern.

The relevant workload is what can follow a qualifying value:

```text id="xf54xb"
fresh qualifying R
        |
        v
Recovery
        |
        v
state 1
        |
        v
Active / Always-On WLAN
        |
        | ~5 serviced seconds
        v
restore power saving
```

Stock C2 can cause unnecessary Recovery without fresh evidence.

That makes it a real firmware correctness defect and a credible additional energy workload.

However:

```text id="93cm36"
real_beacon_skip defect
```

does not equal:

```text id="a98p8p"
historical battery-drain root cause proven
```

Earlier firmware also exhibited battery drain.

The 2.2.4-specific estimator/Recovery defects therefore cannot explain the entire historical problem alone.

---

# 28. B2.2

The later offline integrated candidate:

```text id="bd53of"
B2.2
```

retains C-C as its `real_beacon_skip` / Recovery correction.

Its selected correction set contains:

```text id="uq9nwq"
1. A1R including A1 lifecycle correction
2. C-C
3. B2 bounded serialization
4. minimal MQTT PUBLISH guard
5. WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

B2.2 is currently:

```text id="90xwbp"
OFFLINE RELEASE-CANDIDATE GO
```

It has not been physically deployed in the current long-term phase.

Therefore it provides no additional current hardware evidence regarding `real_beacon_skip`.

---

# 29. Remaining Questions

The principal unresolved questions are now:

## Why do fresh `R = 1..2` values occur?

C-C separates this from stale history.

Possible contributors include:

- actual AP/WF200 beacon behavior
- PM transitions
- connection-state changes
- host statistics-window timing
- WF200 internal PM behavior
- other timing conditions

No one cause is currently established.

## Does fresh `R = 1..2` correspond to a real PM problem?

No direct physical evidence currently proves this.

## Does Beacon Recovery correct anything measurable?

The current long-term experiment deliberately does not change this variable.

## Why did thousands of historical Recoveries occur without D3 errors?

This remains an important clue that the Shelly heuristic and the WF200 PM-error channel are different mechanisms.

## What happens if corrected hardware still drains?

The current PM52→cmd66 observer is intended to make that event diagnosable.

## What happens if corrected hardware remains stable?

The next step is observer removal and observer-free hardware regression before promoting a final candidate.

A Recovery-disabled experiment is not the current immediate next step.

---

# 30. Question for Shelly

The main implementation question for the original developers remains:

> What actual WF200 or WLAN condition was a calculated `real_beacon_skip = 1` or `2` intended to detect?

And directly related:

> Why was an Active-to-Power-Save transition considered the correct recovery action for that condition?

The code shows what the heuristic does.

It does not establish why the heuristic was designed.

A further useful question is:

> If the heuristic was intended to identify an internal WF200 condition not represented by D3 `PS_MODE_ERROR`, what host-visible evidence was expected to distinguish that state from normal beacon-count variation?

---

# 31. Current Model

The stock 2.2.4 estimator/control path is approximately:

```text id="j34xpr"
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
C - P
        |
        v
600 / delta
        |
        v
uint8_t R
        |
        +---- C1a:
        |     signed reinterpretation
        |
        +---- C1b:
        |     measurement-epoch validity
        |
        v
Recovery decision
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
        +---- C2:
              historical R can be reused
```

C-C changes this to:

```text id="2zqujg"
WF200 command 0x66
        |
        v
valid comparable beacon counter samples
        |
        v
fresh unsigned R
        |
        v
R == 1 or R == 2 ?
        |
        +---- no  -> normal operation
        |
        +---- yes
                |
                v
             Recovery
                |
                v
          invalidate P
          retain R diagnostically
                |
                v
        next sample establishes baseline
                |
                v
        historical R not used as
        fresh control evidence
                |
                v
        later comparable sample
                |
                v
             fresh R
```

---

# 32. Current Conclusion

`real_beacon_skip` is best described as a host-side estimator derived from WF200 received-beacon statistics:

```text id="qhfb9k"
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
C - P
        |
        v
600 / delta
        |
        v
uint8_t R
        |
        v
host Recovery decision
```

It is not a WF200 listen-interval readback.

It is not physical RF-sleep telemetry.

Three distinct host-side defects were identified:

### C1a

The unsigned calculated byte is interpreted as signed by stock Recovery control logic, creating unintended trigger values.

### C1b

The previous beacon-counter baseline can survive events that invalidate the logical observation epoch.

### C2

After Recovery, the prior `real_beacon_skip` remains useful as diagnostic history but can be incorrectly reused as fresh control evidence during a baseline-only sample.

C2 can create a long-lived metastable stale-evidence recurrence.

It should not be described as necessarily permanent.

C-C corrects all three validity defects while retaining fresh valid `R = 1..2` Recovery.

Historical hardware testing confirmed that stale evidence is rejected while later fresh qualifying values can still occur.

Historical stock operation showed approximately:

```text id="3l996z"
~60 Recoveries/hour
~8.33% explicit Recovery occupancy
```

during one long observation.

Historical C-C periods showed approximately:

```text id="we1hu9"
~27–30 fresh Recoveries/hour
```

under specific test conditions.

Those rates are historical measurements, not universal properties.

The current research platform is:

```text id="t87q87"
B2.1_OBS
```

with:

```text id="hv6svy"
A1R
+
C-C
+
B2 bounded serialization
+
WF200 3.18.0
+
PM52 -> cmd66 observer
```

The active experiment uses:

```text id="m5q13d"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

and the current decision is:

```text id="xxer2y"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

The central unresolved question remains:

```text id="h93p0m"
What physical or protocol condition,
if any, causes a fresh host-derived
real_beacon_skip of 1 or 2?
```

and:

```text id="ccp11q"
Does Beacon Recovery actually correct
that condition?
```

Current evidence does not yet answer either question.

---

# Related Documents

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

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

Firmware comparison:

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

This analysis is based on static reverse engineering of locally obtained Shelly TRV Gen1 firmware and runtime testing on personally owned devices.

The investigation uses:

- native ARM Thumb control-flow analysis
- WF200 statistics analysis
- cross-version comparison
- runtime debug logs
- `/stats`
- controlled experimental firmware
- C-C hardware validation
- D3 observation
- PM52→cmd66 observation
- long-term battery logging

Historical build names remain preserved.

A1 results are not relabeled as A1R.

Historical C-C rates are not presented as universal limits.

No original or modified complete Shelly firmware image, proprietary complete function or large raw disassembly is reproduced here.

This is an independent research project and is not affiliated with or endorsed by Shelly Group or Silicon Labs.