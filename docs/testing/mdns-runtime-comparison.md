# mDNS Runtime Comparison

## Scope

This document records runtime validation of the periodic mDNS behavior identified during reverse engineering of the Shelly TRV Gen1 firmware.

The focus is deliberately narrow:

- packet-capture behavior across firmware generations
- observed mDNS cadence
- Patch B runtime validation
- long-term behavior of the historical Patch-B device
- separation of periodic mDNS from Beacon Recovery
- later C-C observations
- current experimental context
- what these runtime observations do and do not establish about battery drain

The static implementation of the periodic restart, its callers and the exact Patch-B modification are documented in:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

This document focuses on runtime evidence.

It does not directly measure:

```text
electrical current
charge consumption
host sleep residency
WF200 sleep residency
```

Packet capture is network evidence, not an electrical power measurement.

---

# 1. Runtime Test Matrix

The relevant configurations include:

| Configuration | Periodic mDNS | Beacon Recovery | Status / Purpose |
|---|---|---|---|
| 2.1.0 stock | no comparable periodic burst observed | 2.2.4 mechanism absent | historical old-firmware reference |
| 2.1.3 stock | observed | 2.2.4 mechanism absent | historical periodic-mDNS reference |
| 2.2.4 stock | observed | stock | historical/current stock behavior |
| 2.2.4 + Patch B | targeted restart suppressed | stock | historical mDNS isolation |
| 2.2.4 + C-C | unchanged | corrected | historical Recovery comparison |
| C-C + WF200 3.18.0 | unchanged | corrected | historical radio/host comparison |
| A1 + C-C + WF200 3.18.0 | unchanged | corrected | historical integrated canary |
| B2.1 | unchanged | corrected | current observer-free corrected baseline |
| B2.1_OBS | unchanged | corrected | active long-term hardware build |
| B2.2 | unchanged | corrected | offline observer-free candidate |

The first four configurations provide the primary direct mDNS runtime comparison.

Later corrected builds are relevant mainly for interpreting whether periodic mDNS is required for Beacon Recovery or poor battery endurance.

---

# 2. Original Packet-Capture Setup

The original cross-version experiment observed three physical TRVs simultaneously on the same local WLAN.

At that time:

| Device | Firmware | Role |
|---|---|---|
| `.11` | 2.1.0 stock | older firmware reference |
| `.77` | 2.1.3 stock | periodic-mDNS reference |
| `.229` | 2.2.4 stock | stock comparison |

Packet capture was performed using TShark on macOS.

The filter selected UDP port:

```text
5353
```

traffic from the three devices.

Conceptually:

```text
udp port 5353 and
(
    host <2.1.0 device> or
    host <2.1.3 device> or
    host <2.2.4 device>
)
```

The observation lasted approximately:

```text
13 minutes
```

No active service-discovery requests were intentionally generated during this comparison.

The goal was to observe naturally occurring periodic behavior.

Device identifiers in this document always refer to the firmware configuration at the time of the stated experiment.

Several physical devices were reflashed later.

---

# 3. Firmware 2.1.0 Runtime Result

Historical device:

```text
.11
```

Firmware:

```text
2.1.0
```

No mDNS packets from this device were observed during the approximately 13-minute simultaneous capture.

This agrees with the static comparison:

```text
mDNS responder exists
```

but:

```text
no comparable recurring connected-maintenance
restart identified in the examined path
```

The supported runtime statement is:

> No periodic mDNS burst comparable to later firmware was observed from the 2.1.0 device during the approximately 13-minute capture.

This does not mean firmware 2.1.0 can never transmit mDNS.

Startup, registration and other event-driven traffic remain possible.

---

# 4. Firmware 2.1.3 Runtime Result

Historical device:

```text
.77
```

Firmware at the time:

```text
2.1.3
```

The device repeatedly produced the characteristic sequence:

```text
probe
probe
probe
announcement
```

approximately once per minute.

Representative burst:

```text
59.699 s   probe
60.006 s   probe
60.211 s   probe
60.520 s   announcement
```

Observed burst starts included approximately:

```text
0.0 s
59.7 s
119.8 s
179.8 s
239.6 s
299.7 s
359.6 s
419.7 s
480.2 s
539.8 s
599.6 s
659.8 s
719.8 s
779.9 s
```

Therefore the measured runtime cadence is approximately:

```text
60 seconds
```

This confirms that the recurring connected-maintenance path identified statically is active behavior in firmware 2.1.3.

---

# 5. Firmware 2.2.4 Stock Runtime Result

Historical reference device:

```text
.229
```

Firmware:

```text
20240619-130912/v2.2.4@ee290818
```

Stock firmware produced the same general probe/announcement sequence, but at a lower frequency.

Observed burst starts included:

```text
117.555 s
297.779 s
477.492 s
657.413 s
```

Intervals:

```text
180.225 s
179.713 s
179.921 s
```

Measured cadence:

```text
~180 seconds
```

A normal sequence again contained approximately:

```text
3 probes
+
1 announcement
```

This confirms that the recurring restart remains active in 2.2.4.

---

# 6. Cross-Version Runtime Comparison

Direct packet-capture comparison:

| Firmware | Observed periodic mDNS behavior | Approximate cadence |
|---|---|---:|
| 2.1.0 | no comparable burst observed | none in ~13 min |
| 2.1.3 | recurring probe/announcement burst | ~60 s |
| 2.2.4 | recurring probe/announcement burst | ~180 s |

Static analysis adds firmware 2.1.8:

```text
2.1.0
   |
   +-- responder present
   +-- no comparable recurring burst observed


2.1.3
   |
   +-- recurring restart
   +-- ~60 s


2.1.8
   |
   +-- modulo-3 minute scheduling already present


2.2.4
   |
   +-- recurring restart
   +-- ~180 s runtime
```

The approximately 180-second behavior of 2.1.8 was not independently verified using an equivalent dedicated packet capture.

The chronology nevertheless establishes:

> Periodic connected-maintenance mDNS activity predates firmware 2.2.4.

It was modified over time rather than introduced together with Beacon Recovery.

---

# 7. Patch B

Patch B was created specifically to isolate the recurring mDNS workload.

It suppresses the targeted connected-maintenance restart while leaving:

- the mDNS responder
- event-driven mDNS paths
- stock Beacon Recovery
- `real_beacon_skip`
- `desired_beacon_skip`
- RSSI thresholds
- AP-selection behavior
- WLAN PM policy
- thermostat operation
- valve control

unchanged for the purposes of the experiment.

Conceptually:

```text
periodic mDNS restart
        |
        v
suppressed
```

while:

```text
Beacon Recovery
        |
        v
remains stock
```

The exact static patch is documented in:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

---

# 8. Patch-B Packet-Capture Test

Device:

```text
.77
```

Historical configuration:

```text
2.2.4 + Patch B

periodic mDNS restart:
    suppressed

Beacon Recovery:
    stock
```

This is a later `.77` configuration than the original 2.1.3 packet-capture experiment.

A TShark capture filtered for UDP 5353 traffic from the Patch-B device produced:

```text
0 packets captured
```

during an observation window of at least approximately:

```text
10 minutes
```

A stock 2.2.4 device operating at the observed ~180-second cadence would normally be expected to produce several targeted cycles during such a window.

Therefore:

> The recurring mDNS sequence targeted by Patch B was absent during the monitored Patch-B runtime.

This does not mean every possible mDNS packet or event-driven responder path was removed.

---

# 9. Connectivity with Patch B

Normal operation remained available while the targeted periodic restart was suppressed.

The experiment did not identify loss of ordinary:

```text
Wi-Fi connectivity
local IP access
TRV operation
```

caused by Patch B.

This establishes that continuously restarting the probing sequence was not required for ordinary operation during the tested interval.

It does not establish that the restart has no purpose under every possible network condition.

Potential edge cases include:

- reconnects
- AP restarts
- hostname changes
- topology changes
- unusual multicast behavior
- very long uptime

Patch B was an isolation experiment, not complete mDNS functional qualification.

---

# 10. Historical Long-Term Patch-B Test

The `.77` Patch-B device was later left running as a long-term discharge experiment.

Configuration:

```text
2.2.4 + Patch B

periodic connected-maintenance restart:
    suppressed

Beacon Recovery:
    stock
```

Final observed telemetry was approximately:

```text
battery:              0 %
voltage:              3.116 V
uptime:               ~9.23 days
reconnect_counter:    30
desired_beacon_skip:  15
real_beacon_skip:     1
beacon_err_counter:   12908
```

Average Recovery rate:

```text
12908 / (9.23 × 24)
≈ 58.3 Recoveries/hour
```

or approximately:

```text
one Recovery every 61.8 seconds
```

on average.

The periodic mDNS restart remained suppressed by the experimental patch.

---

# 11. Meaning of the `.77` Long-Term Result

The historical `.77` experiment provides a strong mechanism-separation result.

The hypothesis:

```text
periodic mDNS restart
is required
for recurring Beacon Recovery
```

is incompatible with the observed runtime behavior.

Recurring Recovery continued at high frequency after the periodic restart was removed.

Therefore:

> The targeted periodic connected-maintenance mDNS restart is not required for the recurring Beacon Recovery behavior observed on the tested device.

The experiment does not establish:

```text
Beacon Recovery caused the entire discharge
```

and does not establish:

```text
mDNS has zero energy cost
```

No direct electrical current measurement was performed.

The correct battery conclusion is narrower:

> Suppressing the periodic mDNS restart alone did not prevent poor long-term battery endurance on the tested `.77` device.

---

# 12. Relationship to Beacon Recovery

The original mDNS investigation considered a possible chain:

```text
periodic mDNS restart
        |
        v
WLAN activity
        |
        v
beacon timing disturbance
        |
        v
real_beacon_skip anomaly
        |
        v
Beacon Recovery
```

Patch B tests whether periodic mDNS is a necessary component of that chain.

Observed:

```text
periodic mDNS restart
        |
        v
removed
```

while:

```text
Beacon Recovery
        |
        v
still occurs
```

Therefore the targeted periodic activity cannot be treated as a required trigger for recurring Recovery.

This does not prove an individual mDNS transmission can never influence WLAN timing.

---

# 13. C1a / C1b / C2

Later reverse engineering identified three host-side validity defects in the 2.2.4 Beacon Recovery path:

```text
C1a
signed interpretation of cached estimator value

C1b
measurement-window validity

C2
historical Recovery evidence reused as fresh evidence
```

C2 is particularly important to the original mDNS hypothesis.

After Recovery, stock firmware can clear the measurement baseline while retaining the previous qualifying `real_beacon_skip`.

The next sample may establish only a new baseline.

No fresh ratio exists.

Yet the historical value can be evaluated again.

Conceptually:

```text
fresh qualifying R
        |
        v
Recovery
        |
        v
baseline P cleared
R retained
        |
        v
next sample establishes P only
        |
        v
no fresh R
        |
        v
old R evaluated again
        |
        v
Recovery can recur
```

A new external disturbance is therefore not required before every later stock Recovery.

---

# 14. C2 Is Metastable

Earlier documentation sometimes described this state as:

```text
self-sustaining
```

or implied:

```text
Recovery continues until reboot
```

That is stronger than the evidence supports.

The demonstrated behavior is better described as:

```text
metastable stale-evidence recurrence
```

It can continue for extended periods and produce approximately minute-spaced Recovery events.

However:

> The firmware can leave this recurrence without reboot.

This distinction is now used consistently throughout the project documentation.

---

# 15. Effect on the mDNS Hypothesis

Because C2 can reuse historical evidence, the following model is unnecessary:

```text
mDNS must create a fresh beacon anomaly
before every recurring Recovery
```

Patch B independently supports that conclusion.

The cause of the first fresh qualifying measurement remains a separate question.

No current evidence establishes periodic mDNS as that required first trigger.

---

# 16. C-C Runtime Context

C-C was developed to correct C1a/C1b/C2 while preserving Recovery for fresh valid evidence.

Unlike historical Patch A, C-C does not globally bypass Recovery.

Historical physical configurations included:

```text
.88
    2.2.4 + C-C
    WF200 3.16.1

.237
    2.2.4 + C-C
    WF200 3.18.0

.234
    2.2.4 + A1 + C-C
    WF200 3.18.0
```

These are historical device roles.

C-C removed the demonstrated stale/invalid recurrence but did not eliminate all fresh Recovery.

Representative historical intervals showed approximately:

```text
27–30 fresh Recoveries/hour
```

on some corrected configurations.

These are specific measurements, not a universal C-C rate.

---

# 17. Historical A1 Integrated Runtime

The historical `.234` integrated experiment combined:

```text
A1
+
C-C
+
WF200 3.18.0
```

It showed approximately:

```text
27–28 fresh Recoveries/hour
```

during part of the run.

Because C-C was active, these events were not simple repetitions of C2 stale evidence.

The experiment is important historical evidence but must remain identified as:

```text
A1
```

not:

```text
A1R
B2.1
B2.1_OBS
```

A1 was later superseded by A1R.

---

# 18. D3 Runtime Context

A separate D3 observer monitored the known WF200:

```text
PS_MODE_ERROR
```

indication while retaining stock Beacon Recovery.

Historical `.11` observation:

```text
uptime:       ~63.9 h
beacon_err:   3835
D3_total:     0
```

Thus thousands of host Recovery events occurred without a recorded D3 event.

This does not establish that WF200 was always physically sleeping correctly.

It establishes only:

> The known D3 `PS_MODE_ERROR` indication is not required for the recurring host Beacon Recovery observed in this test.

Combined runtime isolation therefore shows:

```text
periodic mDNS restart
    not required

known D3 PS_MODE_ERROR
    not required

fresh Beacon Recovery
    can still occur
```

---

# 19. Runtime Comparison Summary

| Configuration | Periodic mDNS | Approximate mDNS cadence | Beacon Recovery |
|---|---|---:|---|
| 2.1.0 stock | not observed | none observed in ~13 min | later mechanism absent |
| 2.1.3 stock | observed | ~60 s | later mechanism absent |
| 2.2.4 stock | observed | ~180 s | stock Recovery |
| 2.2.4 + Patch B | targeted cycle absent | suppressed | stock Recovery continues |
| 2.2.4 + C-C | unchanged | stock mDNS | stale/invalid Recovery corrected; fresh events remain |
| C-C + WF200 3.18.0 | unchanged | stock mDNS | fresh Recovery remains |
| historical A1+C-C+3.18 | unchanged | stock mDNS | fresh Recovery remains |
| B2.1/B2.1_OBS | unchanged | native 2.2.4 mDNS behavior | corrected Recovery semantics |

Historical Patch-B long-term result:

```text
periodic mDNS:
suppressed

Beacon Recovery:
~58.3/hour average

runtime:
~9.23 days

final telemetry:
0 %
3.116 V
```

These numbers describe runtime behavior.

They are not an electrical-energy ranking.

---

# 20. Energy Interpretation

A normal successful stock 2.2.4 periodic sequence can include approximately:

```text
3 mDNS probes
+
1 announcement
```

every approximately:

```text
180 seconds
```

This necessarily involves some combination of:

- host execution
- packet construction
- network-stack processing
- WLAN transmission
- WLAN receive work
- radio active time

relative to a state where that sequence does not occur.

Its incremental energy cost is therefore not expected to be exactly zero.

However, the packet capture cannot determine the magnitude.

---

# 21. Why Packet Count Is Not Battery Consumption

A simple count such as:

```text
4 packets / 180 s
```

cannot be converted directly into:

```text
mAh/day
```

without knowledge of physical power states.

Incremental energy depends on:

- whether host was already awake
- whether WF200 was already active
- TX duration
- RX duration
- retransmissions
- RSSI
- WLAN PM mode
- overlap with other scheduled work
- sleep entry afterward

Packet capture therefore measures recurring workload, not electrical energy.

---

# 22. Battery Result of Patch B

The `.77` long-term experiment rules out an overly simple battery hypothesis.

Patch B removed the recurring restart.

Nevertheless:

```text
battery reached 0 %

last captured voltage:
3.116 V

Beacon Recovery:
~58/hour

runtime:
~9.23 days
```

The correct interpretation is:

> Removing the targeted periodic mDNS restart alone did not prevent poor battery endurance on this device.

It would be incorrect to infer:

```text
therefore mDNS has no battery cost
```

or:

```text
therefore Beacon Recovery caused the whole discharge
```

Neither claim is supported by this experiment.

---

# 23. Battery Percentage Caveat

The historical final value:

```text
0 %
```

must not be interpreted as the physical shutdown threshold.

The TRV percentage is voltage-derived rather than coulomb-counted.

The last `.77` telemetry:

```text
3.116 V
```

was still above the approximately:

```text
3.000 V
```

low-voltage shutdown threshold.

The actual final shutdown voltage was not captured in that last successful telemetry sample.

---

# 24. General Battery-Drain Model

The wider investigation contains multiple possible energy-relevant mechanisms:

```text
TRV workload
   |
   +-- thermostat / valve operation
   |
   +-- WLAN traffic
   |
   +-- periodic mDNS
   |
   +-- Beacon Recovery
   |
   +-- host PM lifecycle
   |
   +-- B2 blocker ownership
   |
   +-- PA8 sleep gating
   |
   +-- WF200 PM behavior
   |
   +-- peripheral/resource cleanup
   |
   +-- RF / AP environment
```

Periodic mDNS is now one of the better-isolated variables.

Its status is:

```text
real firmware behavior:
    yes

recurring network workload:
    yes

cadence understood:
    yes

can be selectively suppressed:
    yes

required for recurring Beacon Recovery:
    no

quantitative energy cost:
    not measured

historical battery-drain root cause:
    not established
```

---

# 25. Historical Device Identity

Several device identifiers were reused across phases.

For example:

```text
.77
```

historically represented:

```text
2.1.3 stock
```

then:

```text
2.2.4 + Patch B
```

and currently represents:

```text
B2.1_OBS
```

Similarly, `.11`, `.88`, `.234` and other devices have changed roles over time.

Therefore:

> Device suffix alone must never be used as firmware identity.

Every runtime conclusion must include its experiment/build context.

---

# 26. A1R

Historical A1 corrected PM lifecycle defects but later introduced an experimental temporary-policy regression.

A1R supersedes A1.

Qualification:

```text
151 / 151
```

native Thumb behavior tests passed.

A1R preserves the intended lifecycle corrections while correcting the verified temporary `request1` return paths.

---

# 27. B2 Correction

The shared B2 blocker counter contains a demonstrated task-preemption/lost-update race.

Possible outcomes include:

```text
phantom contribution
```

or:

```text
lost contribution
```

The qualified correction uses bounded serialization of the complete relevant B2 read-modify-write operation.

The correction is included in:

```text
B2.1
B2.1_OBS
B2.2
```

It is no longer a future design proposal.

---

# 28. Current Observer-Free Baseline

The current observer-free corrected baseline is:

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

Importantly:

```text
Patch B is not included
```

Native 2.2.4 mDNS behavior is preserved.

This is intentional.

The project currently has no evidence that mDNS suppression must be part of the corrected platform.

---

# 29. Current Diagnostic Build

The active long-term build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

The observer adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
additional WF200 request
PM policy change
```

It also does not modify mDNS.

This keeps the mDNS variable unchanged during the current long-term test.

---

# 30. Current Hardware Population

The active hardware experiment is:

```text
.77  -> B2.1_OBS
.88  -> B2.1_OBS
.11  -> B2.1_OBS
.71  -> B2.1_OBS
.234 -> B2.1_OBS
.61  -> B2.1_OBS

.97  -> stock 2.2.4 control
```

Therefore:

```text
6 × B2.1_OBS
1 × stock 2.2.4
```

is the current comparison.

Historical `.229`, `.237`, `.88`, `.234` and `.77` configurations remain historical evidence only.

---

# 31. Early Current Observation

During the first observed B2.1_OBS interval:

```text
beacon_err = 0
```

on the corrected devices.

The stock `.97` control retained thousands of accumulated Recovery events and showed periods of approximately minute-scale recurrence.

Other stock intervals were quieter.

This is preliminary runtime evidence only.

It is not a long-term battery conclusion.

---

# 32. B2.2

B2.2 is the later observer-free candidate containing exactly nine selected qualified corrections:

```text
1. A1R including A1 lifecycle correction
2. C-C
3. B2 bounded serialization
4. minimal MQTT PUBLISH guard
5. official WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

Current status:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

B2.2 does not contain:

```text
Patch B
```

and does not contain:

```text
PM52 -> cmd66 observer
```

No physical B2.2 runtime or battery result exists yet.

---

# 33. Why Patch B Is Not in B2.2

B2.2 includes selected defects that satisfy:

```text
demonstrated
+
safely correctable
+
independently qualified
+
composition-qualified
```

The periodic mDNS restart is demonstrated behavior.

However, the project has not established that:

```text
periodic mDNS restart
=
incorrect firmware behavior that must be removed
```

Patch B proves that it can be suppressed and that it is not required for recurring Recovery.

That is not equivalent to proving that suppression is the correct final firmware policy.

Therefore Patch B remains an isolation experiment rather than a B2.2 correction.

---

# 34. Current Experimental Decision

The current decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

Therefore the project is not currently:

- suppressing mDNS on B2.1_OBS
- modifying mDNS cadence
- adding Patch B to B2.2
- changing Recovery cadence
- changing AP policy
- changing WF200 firmware
- flashing B2.2

The current long-term experiment depends on stable variables.

---

# 35. If B2.1_OBS Drains

If a corrected device develops genuine rapid drain:

```text
abnormal voltage/runtime trend
        |
        v
preserve first-fault observer state
        |
        v
inspect PM52 / cmd66 history
        |
        v
correlate Recovery and connection state
        |
        v
resume targeted RE
```

mDNS should only become a renewed active variable if runtime evidence specifically points toward it.

---

# 36. If B2.1_OBS Remains Stable

If the corrected population remains stable:

```text
remove observer
        |
        v
requalify observer-free corrected build
        |
        v
hardware regression
        |
        v
evaluate final candidate
```

There is currently no automatic plan to add Patch B to the final candidate.

---

# 37. Remaining Questions

The basic runtime behavior of the periodic mDNS mechanism is sufficiently characterized.

Remaining questions are narrower:

1. What is the electrical energy cost of one periodic restart?
2. How much additional host awake time does one restart create?
3. How much additional WF200 active time does one restart create?
4. How does energy cost vary with RSSI and retransmissions?
5. Would a controlled otherwise-identical A/B test show measurable battery benefit from Patch B?
6. How often are retained event-driven mDNS restart paths exercised?
7. Does Patch B affect long-term discoverability after reconnect or AP restart?
8. Does 2.1.8 produce ~180-second traffic in a dedicated packet capture?
9. Can periodic mDNS influence the probability of a first fresh Recovery event?
10. Why was the recurring restart introduced in 2.1.3?
11. Why was its cadence reduced by 2.1.8?

These are secondary questions relative to the active B2.1_OBS long-term test.

---

# 38. What the Runtime Evidence Establishes

The runtime evidence establishes that:

- 2.1.3 generates recurring mDNS bursts around 60 seconds
- stock 2.2.4 generates recurring bursts around 180 seconds
- no comparable burst was observed from 2.1.0 during the available ~13-minute capture
- Patch B suppresses the targeted recurring 2.2.4 mDNS sequence
- ordinary device connectivity remained available during the Patch-B test
- recurring stock Beacon Recovery continues without the periodic mDNS restart
- `.77` accumulated approximately 12,908 Recovery events while Patch B remained active
- `.77` still exhibited poor long-term battery endurance
- periodic mDNS is therefore not required for recurring Beacon Recovery
- C2 stale-evidence recurrence explains why a fresh external disturbance is not required for every later stock Recovery
- C2 is metastable, not proven permanent
- C-C removes invalid stale recurrence but retains fresh Recovery
- the current corrected platform intentionally leaves native mDNS behavior unchanged

---

# 39. What the Runtime Evidence Does Not Establish

It does not establish:

- exact mDNS energy consumption
- exact host awake duration per mDNS sequence
- exact WF200 active duration per sequence
- that mDNS is energetically irrelevant
- that Patch B provides zero battery benefit
- that Patch B should be part of a final firmware
- that Beacon Recovery alone caused `.77` to discharge
- that periodic mDNS can never influence an initial estimator event
- that all APs/networks behave identically
- that B2.1_OBS has solved the historical drain
- that B2.2 improves battery life
- a complete historical battery-drain root cause

---

# 40. Current Conclusion

Runtime packet capture confirms that periodic mDNS behavior changed across Shelly TRV Gen1 firmware generations.

Observed history:

```text
2.1.0
    no comparable recurring burst observed
    during ~13-minute capture


2.1.3
    recurring mDNS burst
    ~60 s


2.2.4 stock
    recurring mDNS burst
    ~180 s


2.2.4 + Patch B
    targeted recurring burst absent
```

The historical Patch-B experiment continued into a long-term test.

At approximately:

```text
9.23 days
```

the device had accumulated approximately:

```text
12908 Beacon Recovery events
```

or:

```text
~58.3/hour
```

while the periodic mDNS restart remained suppressed.

Final captured telemetry was approximately:

```text
0 %
3.116 V
```

This provides strong runtime separation between:

```text
periodic mDNS restart
```

and:

```text
recurring Beacon Recovery
```

Later analysis further established that stock C2 can reuse historical Recovery evidence, so a fresh external disturbance is not required before every later stock Recovery.

C2 is now classified as:

```text
metastable stale-evidence recurrence
```

rather than a guaranteed permanent loop.

C-C corrects C1a/C1b/C2 while retaining fresh Recovery.

Historical C-C and A1+C-C+WF200 3.18.0 experiments still produced fresh Recovery.

Those builds are now historical.

The current observer-free corrected baseline is:

```text
B2.1
```

and the active hardware test uses:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

Native mDNS behavior is intentionally preserved in B2.1/B2.1_OBS.

The later:

```text
B2.2
```

candidate also leaves mDNS unchanged and currently has status:

```text
OFFLINE RELEASE-CANDIDATE GO
```

without hardware qualification.

The current interpretation is therefore:

> The periodic mDNS restart is a confirmed recurring network workload whose cadence changed from approximately 60 seconds in firmware 2.1.3 to approximately 180 seconds in firmware 2.2.4. Patch B successfully suppresses the targeted recurring sequence. Long-term testing demonstrates that recurring Beacon Recovery and poor battery endurance can still occur without it. Periodic mDNS is therefore not required for the observed recurring Recovery and is not established as the historical Shelly TRV Gen1 battery-drain root cause. Its quantitative energy cost remains unmeasured.

---

# Related Documents

Static mDNS analysis:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

Firmware chronology:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

Beacon-counter model:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

`real_beacon_skip`:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

Power management:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Host sleep and blocker accounting:

[`../reverse-engineering/host-sleep-and-blocker-accounting.md`](../reverse-engineering/host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

[`../reverse-engineering/pm-lifecycle-and-a1.md`](../reverse-engineering/pm-lifecycle-and-a1.md)

Battery reporting:

[`../reverse-engineering/battery-reporting-and-shutdown.md`](../reverse-engineering/battery-reporting-and-shutdown.md)

Battery testing:

[`battery-testing.md`](battery-testing.md)

Experimental device matrix:

[`experimental-device-matrix.md`](experimental-device-matrix.md)

Patch documentation:

[`../patch/README.md`](../patch/README.md)

B2.1_OBS qualification:

[`../qualification/b2.1-obs-qualification.md`](../qualification/b2.1-obs-qualification.md)

B2.2 qualification:

[`../qualification/b2.2-offline-release-candidate.md`](../qualification/b2.2-offline-release-candidate.md)

---

# Methodology

The runtime findings come from personally owned Shelly TRV Gen1 devices operated on a local WLAN.

The investigation combines:

- passive UDP/5353 packet capture
- firmware identity
- `/status` telemetry
- `/stats` telemetry where available
- Beacon Recovery counters
- battery-voltage logging
- static firmware analysis
- targeted experimental firmware modifications
- long-term hardware observation

Packet capture establishes network behavior.

Firmware counters establish software behavior.

Battery voltage provides a useful device-level trend metric.

None of these individually constitutes a direct electrical current measurement.

Finite packet-capture windows are explicitly described and are not generalized beyond what they demonstrate.

Firmware identity is tied to the actual experiment/build, not permanently inferred from a device suffix.

Historical A1 data are not relabeled as A1R or B2.1 results.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The findings describe observed and reverse-engineered behavior of the investigated firmware versions and experimental configurations.

Statements about battery-drain causality are intentionally limited to what the available static and runtime evidence supports.