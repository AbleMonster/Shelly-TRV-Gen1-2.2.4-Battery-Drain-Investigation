# mDNS Runtime Comparison

## Scope

This document records runtime validation of the periodic mDNS behavior identified
during static reverse engineering of Shelly TRV Gen1 firmware.

The investigation covers:

- firmware 2.1.0
- firmware 2.1.3
- firmware 2.2.4 stock
- firmware 2.2.4 with Patch B

The primary questions are:

1. Is periodic mDNS restart behavior observable at runtime?
2. How does its cadence differ between firmware versions?
3. Does Patch B suppress the targeted periodic restart?
4. Does suppressing the periodic mDNS restart also suppress Beacon Recovery?
5. What can and cannot be concluded about battery consumption?

This document describes network behavior.

It does **not** directly measure electrical current or battery energy.

---

# 1. Evidence Classification

This project uses four evidence levels.

## PROVEN

Directly established from native firmware instructions, deterministic binary
comparison, validated control flow, documented interface semantics, or
sufficiently direct runtime evidence.

## STRONGLY SUPPORTED

Multiple independent findings support the conclusion, but some runtime,
implementation, or environmental detail remains unresolved.

## INFERENCE

A technically plausible interpretation consistent with the available evidence,
but not directly established.

## UNKNOWN

The available evidence is insufficient to determine the behavior, quantitative
effect, or original developer intent.

Runtime observations are described explicitly together with their observation
window.

---

# 2. Static Background

Static firmware analysis identified a recurring connected-maintenance path
capable of restarting mDNS probing.

The relevant high-level behavior is:

```text
connected maintenance
        |
        v
mDNS restart path
        |
        v
probing state restarted
        |
        v
mDNS probes
        |
        v
announcement
```

The chronology differs between firmware generations.

Current reverse-engineering results indicate:

```text
2.1.0
mDNS responder exists
no comparable recurring connected-maintenance caller identified

2.1.3
recurring connected-maintenance restart identified
approximately 60-second cadence

2.1.8
additional gating changes effective cadence
approximately 180 seconds

2.2.4
same general gated periodic behavior
approximately 180 seconds
```

The runtime experiments described below validate important parts of this model.

---

# 3. Original Runtime Test Setup

Three Shelly TRV Gen1 devices were observed simultaneously on the same local
network.

At the time of this original capture, their roles were:

| Device | Firmware at capture time | Role |
|---|---|---|
| `.11` | 2.1.0 | older firmware reference |
| `.77` | 2.1.3 | periodic-mDNS comparison |
| `.229` | 2.2.4 stock | current stock comparison |

Packet capture was performed using TShark on macOS.

The capture filter was equivalent to:

```text
udp port 5353 and
(
    host 192.168.178.11 or
    host 192.168.178.77 or
    host 192.168.178.229
)
```

Capture duration was approximately:

```text
13 minutes
```

No active requests were intentionally sent to the TRVs during the observation.

The device roles listed above describe this historical capture only.

Device IP addresses must not be treated as permanent firmware identities because
several devices were reflashed later in the investigation.

---

# 4. Firmware 2.1.0 Runtime Result

Historical device at capture time:

```text
.11
```

Firmware:

```text
2.1.0
```

No mDNS packets from this device were observed during the approximately
13-minute capture.

This agrees with static analysis:

```text
mDNS responder exists
        |
        v
no comparable recurring connected-maintenance restart caller identified
```

The runtime result must be interpreted narrowly.

It establishes:

> No comparable periodic mDNS burst was observed from the 2.1.0 device during
> this approximately 13-minute observation window.

It does **not** establish:

```text
2.1.0 never transmits mDNS
```

Event-driven or startup-related mDNS behavior remains possible.

### Classification

No comparable periodic burst during this capture:

**PROVEN**

Firmware 2.1.0 can never emit mDNS:

**UNKNOWN**

Comparable recurring connected-maintenance mDNS restart exists in 2.1.0:

**UNKNOWN; no such caller was identified and no such runtime cadence was
observed**

---

# 5. Firmware 2.1.3 Runtime Result

Historical device at capture time:

```text
.77
```

Firmware at that time:

```text
2.1.3
```

The device repeatedly produced a characteristic mDNS sequence approximately
once per minute.

A typical burst consisted of:

```text
probe
probe
probe
announcement
```

One observed sequence was approximately:

```text
59.699 s   probe
60.006 s   probe
60.211 s   probe
60.520 s   announcement
```

Observed burst starts included approximately:

```text
0 s
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

The observed interval was therefore approximately:

```text
60 seconds
```

This closely matches the connected-maintenance behavior identified statically.

Conceptually:

```text
connected
    |
    v
periodic maintenance
    |
    v
mDNS responder restart
    |
    v
probe sequence
    |
    v
announcement
```

### Classification

Periodic mDNS bursts occur in the tested 2.1.3 runtime:

**PROVEN**

Observed cadence is approximately 60 seconds:

**PROVEN**

The captured packet sequence is consistent with the statically identified
restart path:

**STRONGLY SUPPORTED**

---

# 6. Firmware 2.2.4 Stock Runtime Result

Historical stock device:

```text
.229
```

Firmware:

```text
2.2.4
20240619-130912/v2.2.4@ee290818
```

Stock firmware 2.2.4 produced the same characteristic class of mDNS
probe/announcement activity.

Observed burst starts included:

```text
117.555 s
297.779 s
477.492 s
657.413 s
```

The resulting intervals were approximately:

```text
180.225 s
179.713 s
179.921 s
```

The observed runtime period was therefore approximately:

```text
180 seconds
```

A typical burst again consisted of approximately:

```text
3 probes
+
1 announcement
```

This establishes that the periodic mDNS restart behavior remains present in
stock 2.2.4.

Its cadence differs from the tested 2.1.3 behavior:

```text
2.1.3
~60 s

2.2.4
~180 s
```

Subsequent static comparison identified gating consistent with the longer
2.1.8/2.2.4 cadence.

### Classification

Periodic mDNS bursts occur in tested stock 2.2.4:

**PROVEN**

Observed cadence is approximately 180 seconds:

**PROVEN**

The runtime behavior corresponds to the statically identified periodic restart
mechanism:

**STRONGLY SUPPORTED**

---

# 7. Firmware Chronology

Combining static and runtime evidence gives the following current chronology.

| Firmware | Recurring connected mDNS behavior | Runtime cadence |
|---|---|---:|
| 2.1.0 | comparable recurring caller not identified | not observed in ~13 min |
| 2.1.3 | identified | ~60 s |
| 2.1.8 | identified with later gating | ~180 s expected from static behavior |
| 2.2.4 | identified with later gating | ~180 s observed |

This is important for battery-drain chronology.

The periodic mDNS workload:

```text
did not originate in 2.2.4
```

It was already present in earlier firmware.

The behavior changed over time rather than appearing for the first time in
2.2.4.

---

# 8. Patch B

Patch B is the experimental mDNS-only modification.

Its purpose is narrow:

```text
suppress the targeted recurring connected-maintenance mDNS restart
```

while leaving unrelated mechanisms intact.

Patch B does **not** intentionally modify:

```text
Beacon Recovery
RSSI thresholds
desired_beacon_skip
AP selection
prevent_roaming
normal thermostat behavior
```

The mDNS responder itself is not intended to be globally disabled.

The modification targets the recurring restart path.

---

# 9. Patch-B Runtime Test

Device:

```text
.77
```

Current relevant configuration:

```text
firmware 2.2.4
Patch B active
Beacon Recovery stock
```

This is different from `.77`'s historical role in the original 2.1.3 capture.

A later TShark capture filtered for:

```text
UDP port 5353
host 192.168.178.77
```

showed:

```text
0 packets captured
```

during a monitored window of at least approximately:

```text
10 minutes
```

A stock 2.2.4 device would normally be expected to produce multiple targeted
periodic bursts during such a window because its observed cadence is
approximately:

```text
180 seconds
```

The absence of the targeted traffic therefore provides strong finite-window
runtime evidence that Patch B suppresses the intended recurring restart.

This result does not mean:

```text
all mDNS functionality has been removed
```

Other event-driven mDNS behavior remains part of the firmware.

### Classification

Targeted periodic mDNS traffic absent during the monitored Patch-B window:

**PROVEN**

Patch B suppresses the targeted recurring restart under the tested conditions:

**STRONGLY SUPPORTED**

All possible mDNS activity is disabled:

**UNKNOWN; this is not the design objective and has not been established**

---

# 10. Patch B and Normal Connectivity

During Patch-B testing, normal device operation remained available.

The experiment did not identify a loss of ordinary:

```text
Wi-Fi connectivity
local IP access
TRV operation
```

caused by suppressing the targeted periodic restart.

This is important because the periodic restart is not being treated as
necessary merely because it exists in stock firmware.

However, finite runtime operation cannot establish every possible long-term
network condition.

Potential edge cases include:

- hostname changes
- network topology changes
- reconnects
- AP restarts
- long uptime
- unusual multicast conditions

These remain separate qualification questions.

### Classification

Normal operation during the monitored Patch-B test:

**PROVEN**

Patch B is harmless under every possible network condition:

**UNKNOWN**

---

# 11. Patch B and Beacon Recovery

The Patch-B experiment also provides an important mechanism-separation result.

Beacon Recovery remained stock on `.77`.

After Patch B was installed, the device continued to produce the characteristic
2.2.4 Recovery sequence.

Conceptually:

```text
Patch B
        |
        v
targeted periodic mDNS restart suppressed

while

Beacon Recovery
        |
        v
continues
```

This establishes that the targeted periodic mDNS restart is not required for
the observed recurring Beacon Recovery under the tested conditions.

The current `.77` observations are around approximately:

```text
RSSI
-75 ... -77 dBm

desired_beacon_skip
15
```

Older observations involving approximately:

```text
-58 ... -59 dBm
desired_beacon_skip = 20
```

must not be attributed to the current `.77` Patch-B role.

Good-RSSI Recovery observations exist separately in the research dataset, but
device roles must remain distinct.

### Classification

Beacon Recovery continues on the Patch-B device:

**PROVEN**

Targeted periodic mDNS restart is required for the observed recurring Recovery:

**UNKNOWN as a hypothetical requirement; the Patch-B runtime result demonstrates
that such a requirement is unnecessary under the tested conditions**

Universal independence under every possible state:

**UNKNOWN**

---

# 12. Relationship to C1a, C1b and C2

The later Beacon Recovery investigation identified three separate host-side
validity problems:

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

None of these mechanisms requires the periodic mDNS restart.

In particular, C2 explains how a qualifying cached Recovery value can sustain
the recurring Recovery cycle without requiring a fresh qualifying measurement
on every cycle.

Therefore:

```text
periodic mDNS
```

should not be used as the current explanation for:

```text
persistent Beacon Recovery
```

The mechanisms remain separate experimental variables.

---

# 13. Relationship to Patch A

Patch A is the historical Beacon-Recovery bypass.

Its purpose was to isolate the Recovery workload.

Patch A does not correct the underlying C1a/C1b/C2 semantics.

It suppresses the Recovery action itself.

Patch A was therefore useful for mechanism isolation but is no longer the
preferred candidate for correcting Beacon Recovery.

The historical combined:

```text
Patch A + Patch B
```

experiment demonstrated that both targeted recurring mechanisms could be
suppressed simultaneously while the TRV remained operational during monitored
runtime.

That experiment remains scientifically useful.

It should not be interpreted as the current preferred final fix.

---

# 14. Relationship to Patch C-C

Patch C is the research family intended to correct Beacon Recovery validity
while preserving legitimate Recovery behavior.

The current preferred implementation candidate is:

```text
Patch C-C
```

Patch C-C targets:

```text
C1a
C1b
C2
```

and does not intentionally modify the mDNS mechanism.

The intended experimental separation is therefore:

```text
Patch B
        |
        v
mDNS variable


Patch C-C
        |
        v
Beacon Recovery validity variable
```

This provides a cleaner future experimental matrix than using Patch A as the
final Recovery modification.

Patch C-C has passed static pre-build qualification.

Hardware runtime qualification remains pending.

---

# 15. Energy Interpretation

The packet captures establish real additional recurring network activity.

For stock 2.2.4, approximately every 180 seconds the targeted sequence can
include:

```text
3 mDNS probes
+
1 announcement
```

This necessarily involves some combination of:

```text
software processing
packet construction
radio transmission
radio receive activity
```

relative to a state where the periodic restart does not occur.

However, packet capture does not measure electrical energy.

The experiment cannot determine:

- current consumed per burst
- charge consumed per burst
- mAh consumed per day
- percentage of total TRV energy attributable to mDNS
- resulting battery-life reduction

The correct conclusion is:

> The periodic mDNS restart is a confirmed recurring network workload, but its
> quantitative contribution to battery drain remains unknown.

### Classification

Periodic mDNS adds recurring network activity:

**PROVEN**

The activity has non-zero energy cost:

**STRONGLY SUPPORTED**

Its quantitative battery impact:

**UNKNOWN**

Periodic mDNS is a major cause of the historical battery drain:

**UNKNOWN**

---

# 16. Why Packet Count Is Not Battery Consumption

A simple calculation such as:

```text
4 packets / 180 s
```

cannot be converted directly into:

```text
mAh/day
```

because the energy cost depends on factors including:

- radio wake state
- TX duration
- receive windows
- CPU processing
- packet retries
- WLAN power state
- interaction with existing awake periods
- RF conditions

A packet emitted while the radio is already active may have a different
incremental cost from a packet that causes an otherwise unnecessary wake
sequence.

Therefore the runtime packet comparison is a workload measurement, not an
electrical power measurement.

---

# 17. Relationship to Historical Battery Drain

Historical observations indicate that battery drain existed on firmware 2.1.8
as well as 2.2.4.

This is compatible with the mDNS chronology because periodic connected mDNS
behavior already existed before 2.2.4.

However, this does not establish causality.

The current historical model contains several potentially energy-relevant
mechanisms:

```text
normal TRV workload
        |
        +-- normal WLAN power save
        |
        +-- valve motor
        |
        +-- RF conditions
        |
        +-- periodic mDNS
        |
        +-- Beacon Recovery in 2.2.4
        |
        +-- possible inherited WUP/EM2 behavior
```

Periodic mDNS remains one candidate contributor.

It is not established as the complete explanation.

---

# 18. Runtime Comparison Summary

| Configuration | Targeted periodic mDNS | Approximate behavior | Beacon Recovery |
|---|---|---|---|
| 2.1.0 stock | not observed in original window | no comparable burst in ~13 min | 2.2.4 mechanism absent |
| 2.1.3 stock | observed | ~60 s | 2.2.4 mechanism absent |
| 2.2.4 stock | observed | ~180 s | present under qualifying conditions |
| 2.2.4 + Patch B | not observed in Patch-B capture | targeted cycle suppressed | remains stock |

This table describes the observed/tested configurations.

It does not represent an electrical-energy ranking.

---

# 19. Evidence Summary

| Finding | Classification |
|---|---|
| No comparable periodic mDNS burst was observed from 2.1.0 during the ~13-minute capture | **PROVEN** |
| 2.1.0 can never emit mDNS | **UNKNOWN** |
| 2.1.3 produced periodic mDNS bursts | **PROVEN** |
| 2.1.3 observed cadence was ~60 s | **PROVEN** |
| Stock 2.2.4 produced periodic mDNS bursts | **PROVEN** |
| Stock 2.2.4 observed cadence was ~180 s | **PROVEN** |
| Periodic mDNS behavior predates 2.2.4 | **PROVEN** |
| Patch B capture contained no targeted periodic mDNS traffic | **PROVEN** |
| Patch B suppresses the targeted periodic restart under tested conditions | **STRONGLY SUPPORTED** |
| Patch B disables every mDNS path | **UNKNOWN** |
| Beacon Recovery continues with Patch B | **PROVEN** |
| Periodic mDNS is required for recurring Beacon Recovery | **UNKNOWN; tested behavior demonstrates that it is unnecessary under the observed conditions** |
| Periodic mDNS adds recurring network workload | **PROVEN** |
| Periodic mDNS has non-zero energy cost | **STRONGLY SUPPORTED** |
| Quantitative energy cost of periodic mDNS | **UNKNOWN** |
| Periodic mDNS is a major historical battery-drain cause | **UNKNOWN** |
| Patch B improves long-term battery endurance | **UNKNOWN** |

---

# 20. Remaining Questions

The main unresolved questions are:

1. What is the electrical energy cost of one periodic mDNS restart sequence?

2. Does suppressing the periodic restart measurably improve long-term battery
   endurance?

3. Does the cost depend strongly on RSSI or retransmissions?

4. Does the periodic restart coincide with other awake activity, reducing its
   incremental energy cost?

5. Are there long-term connectivity consequences from suppressing the periodic
   restart?

6. Under which events are the remaining non-periodic mDNS paths activated?

7. Does firmware 2.1.8 produce the expected ~180-second runtime cadence in a
   direct packet capture?

8. Is the transition from ~60 seconds to ~180 seconds purely the result of the
   identified connected-maintenance gating?

9. How much of the historical 2.1.x battery behavior can be attributed to mDNS
   versus other inherited power-management changes?

These questions require either longer controlled observation or direct
electrical measurement.

---

# 21. Current Research Direction

The original planned Patch-B experiment has been completed.

The current research path is therefore:

```text
static mDNS analysis
        |
        v
stock runtime validation
        |
        v
Patch-B isolation
        |
        v
runtime suppression confirmed in finite window
        |
        v
long-term battery comparison
```

In parallel:

```text
Beacon Recovery analysis
        |
        v
C1a / C1b / C2
        |
        v
Patch C-C
        |
        v
static pre-build qualification passed
        |
        v
experimental build
        |
        v
hardware qualification
```

The two mechanisms should remain separate variables whenever practical.

---

# 22. Current Conclusion

Runtime packet capture confirms that recurring mDNS behavior changed across
Shelly TRV Gen1 firmware generations.

The observed chronology is:

```text
2.1.0
no comparable periodic burst observed during ~13 min

2.1.3
~60-second recurring mDNS burst

2.2.4
~180-second recurring mDNS burst
```

Static analysis further indicates that the later ~180-second behavior already
exists in 2.1.8.

Patch B was subsequently tested on firmware 2.2.4.

During the monitored Patch-B capture:

```text
targeted periodic mDNS packets = 0
```

while normal device operation remained available.

At the same time, stock Beacon Recovery continued on the Patch-B device.

Therefore the current evidence supports two separate conclusions:

> Patch B suppresses the targeted recurring mDNS restart under the tested
> conditions.

and:

> The targeted periodic mDNS restart is not required for the observed recurring
> Beacon Recovery behavior.

The mDNS mechanism remains energy-relevant because it creates recurring network
activity.

Its quantitative contribution to the Shelly TRV Gen1 battery-drain problem
remains:

**UNKNOWN**

---

# Related Documents

Static mDNS analysis:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

Firmware chronology:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

Power management:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

Battery testing:

[`battery-testing.md`](battery-testing.md)

Experimental patches:

[`../patch/README.md`](../patch/README.md)

---

# Methodology Note

The runtime findings in this document are based on packet captures from
personally owned Shelly TRV Gen1 devices.

The experiments observe network behavior.

They do not constitute laboratory-grade electrical power measurements.

Finite observation windows are described explicitly and must not be
generalized beyond what they demonstrate.

Firmware identity is determined from the actual experimental state at the time
of each capture rather than inferred permanently from a device IP address.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings describe observed and reverse-engineered behavior of the examined
firmware versions and experimental configurations.