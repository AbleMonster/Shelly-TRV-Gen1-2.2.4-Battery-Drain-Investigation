# Battery Testing

## Scope

This document tracks the long-term battery investigation for Shelly TRV Gen1
devices across different firmware and experimental patch configurations.

The purpose is to determine whether measurable battery behavior correlates with:

- firmware version
- periodic mDNS activity
- firmware 2.2.4 Beacon Recovery
- experimental firmware modifications
- WLAN conditions
- valve/motor workload
- battery condition
- device-specific characteristics
- other configuration-dependent factors

The investigation combines:

```text
battery percentage
+
battery voltage
+
firmware identity
+
runtime diagnostics
+
WLAN conditions
+
motor workload
+
uptime
```

The current work is primarily a long-term observational comparison.

It is **not** a laboratory-grade electrical power measurement.

> Cross-device differences in battery percentage or battery voltage must not be
> interpreted directly as firmware energy consumption.

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

A technically plausible interpretation consistent with available evidence, but
not directly established.

## UNKNOWN

Available evidence is insufficient to determine the behavior, quantitative
effect, or original developer intent.

Battery trends are described separately from firmware-mechanism proof.

---

# 2. Core Research Questions

The battery investigation currently separates several questions.

## 2.1 Does stock 2.2.4 repeatedly enter Beacon Recovery?

Yes.

Affected stock 2.2.4 operation has shown the characteristic sequence:

```text
Beacon skip error! Attempt recovery
        |
        v
power-save state 1
        |
        v
approximately 5 serviced seconds
        |
        v
normal power-save restoration
```

During persistent operation, approximately:

```text
1 Recovery / minute
```

has been observed.

This is real additional firmware activity.

Its exact electrical cost is not known.

### Classification

Recurring stock 2.2.4 Recovery:

**PROVEN**

Quantitative battery cost per Recovery:

**UNKNOWN**

---

## 2.2 Why can Beacon Recovery repeat?

The current reverse-engineering result is substantially stronger than during
the original battery-test phase.

Three separate problems have been identified.

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

C2 explains the persistent recurrence.

After a qualifying Recovery:

```text
previous_received = 0
```

while the qualifying cached:

```text
real_beacon_skip
```

remains stored.

The next successful baseline-only acquisition can then evaluate that historical
value before a fresh ratio has been calculated.

This can trigger another Recovery and clear the baseline again.

The loop can therefore sustain itself without requiring a new qualifying RF
anomaly on every cycle.

### Classification

C2 stale-state recurrence in identified stock control flow:

**PROVEN**

C1a interpretation as control-validity defect:

**STRONGLY SUPPORTED**

C1b interpretation as measurement-validity defect:

**STRONGLY SUPPORTED**

Exact cause of the first field trigger:

**UNKNOWN**

---

## 2.3 Does periodic mDNS create recurring additional activity?

Yes.

Runtime packet capture established approximately:

```text
2.1.0
no comparable periodic burst observed during ~13 min

2.1.3
~60-second recurring burst

2.2.4 stock
~180-second recurring burst
```

A normal observed sequence contains approximately:

```text
3 probes
+
1 announcement
```

This is real recurring network activity.

Its electrical cost remains unquantified.

### Classification

Periodic mDNS workload:

**PROVEN**

Quantitative battery contribution:

**UNKNOWN**

---

## 2.4 Does Patch B suppress the targeted periodic mDNS restart?

During the monitored Patch-B experiment, yes.

Device `.77` runs:

```text
2.2.4
Patch B active
Beacon Recovery stock
```

A TShark capture filtered for UDP port 5353 from `.77` showed:

```text
0 packets
```

during a window long enough that multiple stock 2.2.4 periodic cycles would
normally have been expected.

This is strong finite-window evidence that the targeted recurring mDNS restart
was suppressed.

Patch B does not intentionally disable all possible mDNS behavior.

### Classification

No targeted periodic packets during monitored Patch-B window:

**PROVEN**

Patch B suppresses targeted recurring restart under tested conditions:

**STRONGLY SUPPORTED**

Patch B disables all mDNS behavior:

**UNKNOWN**

---

## 2.5 Does Patch B also suppress Beacon Recovery?

No under the tested conditions.

`.77` continued entering stock Beacon Recovery after the targeted periodic mDNS
restart had been suppressed.

The current `.77` runtime condition is approximately:

```text
RSSI
-75 ... -77 dBm

desired_beacon_skip
15
```

The earlier:

```text
-58 ... -59 dBm
desired_beacon_skip = 20
```

observation must not be assigned to the current `.77` Patch-B role.

Good-RSSI Recovery observations exist separately in the stock dataset.

The important mechanism result is:

> The targeted periodic mDNS restart is not required for the observed recurring
> Beacon Recovery under the tested conditions.

### Classification

Beacon Recovery remains with Patch B:

**PROVEN**

mDNS restart is required for persistent Recovery:

**UNKNOWN as a hypothetical requirement; the observed Patch-B behavior
demonstrates that it is unnecessary under the tested conditions**

---

## 2.6 Did Patch A suppress Beacon Recovery?

Yes under the tested conditions.

Patch A bypasses the targeted Recovery action while leaving beacon statistics
available.

Patch-A devices showed:

```text
beacon statistics active
real_beacon_skip active
desired_beacon_skip active
Recovery counter = 0
```

This made Patch A useful for mechanism isolation.

However, Patch A also removes legitimate Recovery behavior.

It therefore does not represent the preferred final correction.

### Classification

Patch A suppresses targeted Recovery under tested conditions:

**PROVEN**

Patch A correctly repairs C1a/C1b/C2 semantics:

**UNKNOWN as a hypothetical property; Patch A bypasses the action rather than
implementing those corrections**

Patch A improves battery endurance:

**UNKNOWN**

---

# 3. Historical Combined A+B Experiment

The combined A+B firmware was tested on `.226`.

Its purpose was to determine whether both identified recurring mechanisms could
be suppressed simultaneously.

During monitored runtime:

```text
targeted periodic mDNS
not observed

recurring Beacon Recovery
not observed

Wi-Fi
operational

local HTTP
operational

cloud
operational after startup

TRV / thermostat
operational
```

This experiment remains important.

It establishes that the two mechanism-isolation modifications can coexist under
the tested conditions.

However:

```text
A+B
```

is no longer the preferred candidate for the final Beacon Recovery correction.

Patch A removes Recovery rather than correcting its evidence semantics.

The current preferred Beacon Recovery research path is Patch C-C.

---

# 4. Patch C-C

Patch C is the research family designed to correct Beacon Recovery validity
while preserving legitimate Recovery behavior.

The current preferred implementation candidate is:

```text
Patch C-C
```

Its behavior-level objectives are:

```text
C1a
prevent signed narrowing from turning large positive values into qualifying
negative control values

C1b
invalidate the received-beacon baseline across measurement epochs where the
fixed 600-based calculation is no longer valid

C2
prevent a baseline-only sample from acting on historical Recovery evidence
```

while preserving:

```text
diagnostic real_beacon_skip
fresh legitimate Recovery
normal PM restoration
```

Patch C-C does not intentionally change:

```text
periodic mDNS
AP selection
prevent_roaming
RSSI thresholds
desired_beacon_skip
normal thermostat behavior
```

Static pre-build qualification has passed.

At the current project stage:

```text
firmware build
hardware flashing
runtime validation
battery validation
```

have not yet established Patch C-C behavior on physical hardware.

### Classification

Patch C-C static pre-build qualification:

**PROVEN as project qualification status**

Patch C-C runtime correctness:

**UNKNOWN; hardware qualification pending**

Patch C-C improves battery life:

**UNKNOWN**

---

# 5. Experimental Patch Roles

The current research distinguishes four patch roles.

| Configuration | Purpose | Current role |
|---|---|---|
| Stock 2.2.4 | control | primary unmodified reference |
| Patch A | bypass Beacon Recovery | historical mechanism-isolation patch |
| Patch B | suppress targeted periodic mDNS restart | active mDNS-isolation patch |
| Patch A+B | suppress both targeted workloads | historical combined isolation experiment |
| Patch C-C | correct C1a/C1b/C2 while retaining legitimate Recovery | current Beacon-Recovery candidate |

The distinction is important.

Patch A and A+B remain scientifically useful.

They should not be presented as the current preferred final fix.

---

# 6. Measurement Sources

The battery logger queries each TRV directly.

Primary battery fields are:

```text
bat.value
bat.voltage
```

Where available, additional `/stats` information is collected.

Relevant values include:

- `real_beacon_skip`
- desired beacon skip
- received-beacon statistics
- missed-beacon statistics
- Beacon Recovery/error counter
- other firmware-specific diagnostics

The logger also records:

- firmware version
- uptime
- RSSI
- device address
- diagnostic availability

Debug logs are retained separately where needed.

These can provide:

- Recovery events
- PM state transitions
- valve movement
- requested motor steps
- executed motor steps

---

# 7. Authoritative Battery Source

For this investigation, battery state reported directly by the TRV is treated
as the primary source.

Home Assistant is not treated as authoritative when its displayed value differs
from current TRV status.

For example:

```text
TRV
100 %

Home Assistant
91 %
```

does not justify replacing the direct TRV measurement with the Home Assistant
value.

Home Assistant may contain a differently timed or stale representation.

---

# 8. Battery Percentage

Battery percentage is calculated by device firmware.

It is not a direct coulomb-counting measurement of consumed energy.

It may depend on:

- firmware estimation logic
- voltage curve
- battery chemistry
- load history
- calibration
- state of charge

A freshly charged battery may remain at:

```text
100 %
```

while its voltage already changes.

Percentage therefore has limited short-term resolution.

---

# 9. Battery Voltage

Voltage provides a higher-resolution observational signal but is also not a
direct energy measurement.

It varies with:

- state of charge
- motor load
- WLAN activity
- temperature
- battery internal resistance
- recovery after load
- battery age
- time since charging

Therefore:

```text
voltage decline
```

cannot automatically be converted into:

```text
energy consumed
```

The preferred interpretation combines:

```text
percentage
+
voltage
+
workload
+
runtime diagnostics
+
time
```

---

# 10. Battery Condition

The physical batteries are not guaranteed to have identical:

- age
- usable capacity
- internal resistance
- charge history
- previous workload
- starting state of charge

This is one of the largest limitations of cross-device comparison.

For example:

```text
TRV A
99 % -> 90 %

TRV B
99 % -> 95 %
```

does not establish that firmware A consumes more energy than firmware B.

Battery condition remains an explicit confounding variable.

---

# 11. Valve Motor Workload

Valve movement represents substantial real electrical work.

Conceptually:

```text
total battery consumption
        |
        +-- baseline electronics
        |
        +-- WLAN activity
        |
        +-- MCU activity
        |
        +-- valve motor
```

A device performing significantly more valve movement cannot be compared
directly with a mostly stationary device without accounting for that workload.

Motor-step information should therefore be retained whenever technically
reliable.

Useful fields include:

```text
motor_steps_raw
motor_steps_delta
motor_steps_total_interval
movement_count
```

Before treating a firmware value as cumulative, its behavior across:

```text
reboot
reset
counter rollover
```

must be established.

The goal is initially relative workload normalization, not exact conversion of
steps into joules or mAh.

---

# 12. WLAN Signal Strength

RSSI is recorded because RF conditions can influence normal WLAN behavior.

The identified desired beacon-skip policy is:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

Lower skip values create more nominal beacon-listening opportunities.

This does not mean complete-device current scales proportionally with skip.

Relevant additional variables include:

- WF200 state
- retransmissions
- network traffic
- host awake time
- Recovery behavior
- motor workload

---

# 13. RSSI Does Not Explain Persistent Recovery

Weak RSSI is not required by the host-side C2 recurrence.

Once the firmware reaches:

```text
previous_received = 0
real_beacon_skip = qualifying historical value
```

the next baseline-only acquisition can retrigger Recovery without a fresh ratio.

Therefore persistent Recovery does not require:

```text
new poor RSSI every minute
```

or:

```text
new AP problem every minute
```

Separate stock observations also demonstrate Recovery under usable/good WLAN
conditions.

The current Patch-B `.77` device itself should be described using its actual
current condition:

```text
RSSI approximately -75 ... -77 dBm
desired_beacon_skip = 15
```

not the older unrelated −58/−59 dBm observation.

---

# 14. RSSI Is Not the Complete RF Picture

Displayed RSSI does not establish the associated BSSID.

Host connection establishment uses:

```text
BSSID = wildcard
Channel = 0
prevent_roaming = 1
```

Concrete AP selection occurs below the Shelly host application.

After association, autonomous WLAN-firmware roaming is prevented.

Two devices with similar RSSI can therefore still have different:

- BSSID
- channel
- RF history
- retransmission behavior
- connection history

Detailed analysis is documented in:

[`../reverse-engineering/ap-selection-and-roaming.md`](../reverse-engineering/ap-selection-and-roaming.md)

---

# 15. Static IP vs. DHCP

The current device group contains both static-IP and DHCP configurations.

Examples include:

```text
Static
.11
.77
.88

DHCP
.226
.228
.229
```

No evidence currently establishes static IP or DHCP as the cause of the battery
drain.

The variable is retained because it can influence:

- DHCP traffic
- reconnect behavior
- initialization timing
- post-association network activity

### Classification

Static IP/DHCP materially explains battery drain:

**UNKNOWN**

---

# 16. Device Identity Rule

Device IP addresses describe physical test devices.

They do not permanently identify one firmware configuration.

Several devices have run different firmware during different phases.

Therefore:

> Firmware identity must be determined from the actual device status and
> measurement timestamp, not inferred from the IP address alone.

Reports spanning a firmware transition must be split at the transition.

---

# 17. Current Relevant Device Roles

The recent mechanism-isolation phase uses the following physical devices.

| Device | Relevant recent configuration | Network | Role |
|---|---|---|---|
| `.11` | 2.1.0 stock | Static IP | older firmware reference |
| `.77` | 2.2.4 + Patch B | Static IP | mDNS isolation |
| `.88` | 2.2.4 + Patch A | Static IP | historical Recovery isolation |
| `.226` | 2.2.4 + Patch A+B | DHCP | historical combined isolation |
| `.228` | 2.2.4 + Patch A | DHCP | historical Recovery isolation |
| `.229` | 2.2.4 stock | DHCP | stock control |

These roles describe the recent experimental phase.

Future Patch C-C hardware testing will create a new experimental phase and must
be documented separately.

---

# 18. Device `.11`

## Role

Older firmware reference.

## Relevant firmware

```text
2.1.0
20211223-144805/v2.1.0@d30148ec
```

## Network

```text
Static IP
```

Earlier runtime logging demonstrated long uptime without the repeating
2.2.4-style Beacon Recovery sequence.

One historical observation included approximately:

```text
uptime
355568 s

battery
100 %

voltage
3.886 V
```

before an intentional reboot.

RSSI has varied significantly between historical observations.

Values around:

```text
-83 dBm
```

and later approximately:

```text
-59 dBm
```

have both occurred.

Therefore no single historical RSSI should be treated as the permanent RF
condition of `.11`.

Firmware 2.1.0 remains useful as an older reference.

It is not a laboratory-proven low-power baseline.

---

# 19. Device `.77`

## Historical role

`.77` previously ran firmware 2.1.3 and participated in the original mDNS
runtime comparison.

At that time, recurring mDNS activity was observed approximately every:

```text
60 seconds
```

## Current role

Patch-B mDNS-isolation device.

## Current relevant configuration

```text
2.2.4
Patch B active
Patch A inactive
```

Beacon Recovery remains stock.

## Network

```text
Static IP
```

## mDNS result

During the monitored Patch-B capture:

```text
targeted periodic mDNS packets
0
```

This provides strong finite-window evidence that Patch B suppresses the targeted
periodic restart.

## Beacon Recovery

Beacon Recovery continued despite Patch B.

Current observations place `.77` around approximately:

```text
RSSI
-75 ... -77 dBm

desired_beacon_skip
15
```

The recurring stock Recovery behavior remains present.

## Interpretation

`.77` provides the cleanest current isolation between:

```text
periodic mDNS
```

and:

```text
Beacon Recovery
```

under the tested conditions.

---

# 20. Device `.88`

## Role

Historical Patch-A Recovery-isolation device.

## Relevant configuration

```text
2.2.4
Patch A active
```

## Network

```text
Static IP
```

The device continued calculating beacon statistics and `real_beacon_skip`
while the targeted Recovery counter remained:

```text
0
```

under observed patched operation.

This validates Patch A as a mechanism-isolation tool.

It does not establish battery improvement.

---

# 21. Device `.228`

## Role

Second historical Patch-A Recovery-isolation device.

## Relevant configuration

```text
2.2.4
Patch A active
```

## Network

```text
DHCP
```

The device was tested in different physical positions, so RSSI changed over
time.

Historical examples include approximately:

```text
-57 ... -58 dBm
```

before relocation and later roughly:

```text
-62 ... -71 dBm
```

depending on the observation interval.

Despite targeted Recovery suppression, one approximately 24-hour observation
showed roughly:

```text
battery
74 % -> 65 %

voltage
3.686 V -> 3.623 V
```

These values are strongly confounded by:

- battery condition
- motor workload
- physical device
- RF conditions
- starting state

They do not quantify Patch-A energy consumption.

They do establish an important caution:

```text
Recovery suppressed
```

does not automatically imply:

```text
no observed battery decline
```

This is one reason Beacon Recovery must not be treated as the sole historical
battery-drain explanation.

---

# 22. Device `.226`

## Historical role

`.226` previously ran other firmware configurations, including 2.1.3.

Those older intervals must not be mixed with its later A+B data.

## Combined-isolation role

Relevant later configuration:

```text
2.2.4
Patch A active
Patch B active
```

## Network

```text
DHCP
```

During monitored runtime:

```text
boot
successful

Wi-Fi
operational

HTTP
operational

cloud
operational after startup

thermostat
operational

targeted periodic mDNS
not observed

recurring Beacon Recovery
not observed
```

An early post-installation overnight period showed comparatively stable voltage
around:

```text
3.65 V
```

with percentage around:

```text
69 ... 70 %
```

This was encouraging but insufficient for a battery-life conclusion.

The A+B experiment should now be treated primarily as a successful historical
mechanism-isolation experiment.

---

# 23. Device `.229`

## Role

Unmodified stock 2.2.4 control.

## Firmware

```text
2.2.4
20240619-130912/v2.2.4@ee290818
```

## Network

```text
DHCP
```

`.229` previously ran 2.1.8.

Reports crossing that transition must therefore be split.

Under stock 2.2.4, `.229` has repeatedly produced the characteristic Recovery
cycle.

Observed counter behavior has included approximately:

```text
+30 events / 30 minutes
```

corresponding to approximately:

```text
1 Recovery / minute
```

If uninterrupted, that event rate would correspond numerically to:

```text
~60 / hour
~1440 / day
```

This is an event-frequency extrapolation only.

It is not an energy measurement.

Stock `.229` debug observations have also shown Recovery under good/usable RSSI
conditions, including observations around approximately:

```text
-59 dBm
```

This supports the conclusion that obviously weak RSSI is not required for
Recovery.

---

# 24. Initial Battery Snapshot

Historical short-term observations remain useful as descriptive data.

They are not a controlled firmware-efficiency benchmark.

Representative earlier observations included:

| Device | Configuration | Representative interval | Battery | Voltage | Recovery |
|---|---|---|---|---|---|
| `.229` | stock 2.2.4 | ~24 h, freshly charged region | ~100 % | ~4.133 -> 4.111 V | ~1/min |
| `.77` | Patch B | ~24 h historical snapshot | ~99 % | ~3.897 -> 3.872 V | present |
| `.88` | Patch A | ~23.5 h | ~86 -> 83 % | ~3.764 -> 3.743 V | suppressed |
| `.228` | Patch A | ~24 h | ~74 -> 65 % | ~3.686 -> 3.623 V | suppressed |
| `.226` | A+B early post-install | ~12 h | ~69-70 % | roughly stable near 3.65 V | not observed |

These values must not be used to calculate:

```text
Patch X saves Y %
```

or:

```text
Firmware A consumes Z times more energy
```

because the devices and batteries are not equivalent.

---

# 25. What the Historical Snapshot Establishes

Several useful conclusions can still be drawn.

## Finding 1

Stock 2.2.4 can produce persistent additional Beacon Recovery activity.

**PROVEN**

## Finding 2

Patch B suppresses targeted periodic mDNS while Beacon Recovery remains.

**PROVEN for the observed runtime behaviors**

## Finding 3

Patch A suppresses targeted Recovery while beacon statistics remain available.

**PROVEN under tested conditions**

## Finding 4

Recovery suppression alone did not eliminate all observed battery decline on
every Patch-A device.

**PROVEN as an observation**

Its causal explanation remains:

**UNKNOWN**

## Finding 5

The early A+B voltage behavior was encouraging but insufficient to establish
improved endurance.

Battery improvement remains:

**UNKNOWN**

---

# 26. Historical Drain Predates 2.2.4

Historical observation indicates that firmware 2.1.8 also exhibited relatively
rapid battery decline.

Therefore:

```text
2.2.4 Beacon Recovery
```

cannot explain the complete historical Shelly TRV Gen1 battery-drain problem.

This is an important boundary condition.

The older drain may involve:

- periodic mDNS
- WLAN-stack changes
- RF behavior
- PM behavior
- WUP/EM2-related behavior
- other unidentified mechanisms

The responsible mechanism or combination remains unresolved.

### Classification

Historical drain was observed before 2.2.4:

**STRONGLY SUPPORTED**

Beacon Recovery explains all historical drain:

**UNKNOWN as a hypothetical explanation; chronology demonstrates that it cannot
be sufficient by itself**

---

# 27. WUP / EM2 Candidate

Separate reverse engineering identified a conditional host-side path where
sleep-resource release may not complete under some conditions.

This behavior predates 2.2.4.

Its static existence is relevant because it could potentially affect deep-sleep
eligibility.

However, current evidence does not establish:

- how often it occurs on physical devices
- how long the condition persists
- whether it materially affects average current
- whether it explains historical battery drain

Blindly forcing resource release would be unsafe because the retained resource
may be required for valid WLAN or interrupt state.

Therefore no WUP/EM2 patch is currently justified solely from the battery data.

### Classification

Identified conditional path:

**PROVEN**

Frequent physical occurrence:

**UNKNOWN**

Quantitative battery contribution:

**UNKNOWN**

---

# 28. Major Confounding Variables

The current battery comparison contains substantial confounding variables.

| Variable | Controlled? | Relevance |
|---|---|---|
| Firmware | partially | primary research variable |
| Physical TRV | no | hardware variation |
| Battery age | no | potentially large |
| Battery capacity | no | potentially large |
| Internal resistance | no | affects voltage under load |
| Starting state of charge | no | affects comparison |
| Valve workload | no | significant electrical load |
| Motor steps | partially available | important normalization variable |
| RSSI | recorded | affects WLAN policy |
| Actual BSSID | not continuously recorded | RF uncertainty |
| Device location | not identical | RF/temperature difference |
| Static IP/DHCP | mixed | possible network difference |
| Temperature | not fully controlled | battery/heating influence |
| Heating demand | not identical | changes motor work |
| Uptime | recorded | detects resets |
| Firmware transitions | present historically | requires interval splitting |

These limitations must remain visible in every battery conclusion.

---

# 29. Why Cross-Device Ranking Is Weak

A result such as:

```text
Device A
-3 %

Device B
-9 %
```

does not establish a firmware efficiency ratio.

A more defensible interpretation is:

```text
battery trend
+
voltage trend
+
motor workload
+
RSSI
+
Recovery activity
+
mDNS configuration
+
uptime
+
battery history
+
device history
=
observational evidence
```

Longer observation and repeated patterns increase confidence.

They do not eliminate uncontrolled variables automatically.

---

# 30. Firmware Transitions

Uptime and firmware identity must be used to detect experimental boundaries.

For example:

```text
firmware A
high uptime
        |
        v
OTA / reboot
        |
        v
firmware B
low uptime
```

A report containing:

```text
12 h firmware A
+
12 h firmware B
```

must not be treated as:

```text
24 h firmware A
```

or:

```text
24 h firmware B
```

All trend calculations must be segmented at firmware transitions.

---

# 31. Current Battery-Drain Model

The current evidence supports a multi-mechanism model.

```text
normal TRV workload
        |
        +-- baseline electronics
        |
        +-- normal WLAN power save
        |
        +-- cloud/controller traffic
        |
        +-- valve motor workload
        |
        +-- RF conditions / retransmissions
        |
        +-- periodic mDNS restart
        |
        +-- 2.2.4 Beacon Recovery
        |
        +-- possible inherited WUP/EM2 behavior
        |
        +-- other unidentified effects
        |
        v
total battery consumption
```

Patch B isolates one recurring network workload.

Patch A historically isolated Recovery by bypassing it.

Patch C-C is designed to correct the known Recovery validity problems without
removing legitimate Recovery.

None of these facts establishes that one mechanism explains all battery drain.

---

# 32. C1a and Battery Relevance

C1a allows certain positive calculated values to qualify because the stored byte
is interpreted as signed by the Recovery predicate.

For example:

```text
delta = 3
600 / 3 = 200
0xC8 interpreted signed = -56

delta = 4
600 / 4 = 150
0x96 interpreted signed = -106
```

The stock fresh-trigger domain therefore includes:

```text
3
4
201 ... 600
```

rather than only the ordinary positive quotient domain expected from an
unsigned interpretation.

C1a can create an invalid Recovery trigger.

The battery relevance is indirect:

```text
invalid trigger
        |
        v
Recovery workload
        |
        ?
        v
additional energy
```

The electrical magnitude remains unknown.

---

# 33. C1b and Battery Relevance

The stock calculation uses:

```text
600 / delta_received
```

without storing elapsed time with the previous counter baseline.

Skipped measurement opportunities can preserve the old baseline.

The next successful measurement can therefore span a longer interval while
still using:

```text
600
```

as though the interval were nominal.

This can produce a qualifying value even when the underlying radio behavior is
not equivalent to the assumed measurement window.

A reachable model exists in which a multi-minute baseline produces a qualifying
result without requiring a persistent radio failure.

The model demonstrates reachability.

It does not prove that this was the actual first-trigger cause on a particular
physical device.

---

# 34. C2 and Battery Relevance

C2 explains why one qualifying event can become a persistent recurring workload.

Conceptually:

```text
qualifying R
        |
        v
Recovery
        |
        v
P cleared
R retained
        |
        v
next successful baseline acquisition
        |
        v
historical R evaluated
        |
        v
Recovery again
```

Once established, this can produce approximately minute-scale repeated Recovery
without a fresh qualifying anomaly each time.

This makes C2 especially important for battery research because it converts:

```text
one qualifying event
```

into:

```text
potentially long-lived recurring activity
```

The electrical cost of that recurring activity still requires measurement.

---

# 35. Patch C-C Hardware Test Objectives

Once a growth-aware Patch C-C build has been independently verified, hardware
qualification should precede battery conclusions.

The first hardware tests should establish:

1. firmware boots normally
2. WLAN association remains reliable
3. cloud/local connectivity remains available
4. thermostat and valve operation remain normal
5. `/stats` remains coherent
6. diagnostic `real_beacon_skip` remains available
7. C1a invalid signed cases no longer trigger Recovery
8. first post-Recovery baseline-only acquisition does not retrigger from
   historical R
9. a later fresh legitimate qualifying measurement can still trigger Recovery
10. PM restoration remains functional
11. no unexpected reboot or watchdog behavior appears
12. network availability remains acceptable

Battery endurance is a later qualification layer.

A patch that reduces battery drain but damages WLAN reliability would not be an
acceptable correction.

---

# 36. Preferred Future Experimental Matrix

The earlier A+B standardization plan is superseded by the current
mechanism-level understanding.

A cleaner future matrix is:

```text
Stock 2.2.4
        |
        +-- mDNS stock
        +-- Beacon Recovery stock


Patch B
        |
        +-- targeted mDNS suppressed
        +-- Beacon Recovery stock


Patch C-C
        |
        +-- mDNS stock
        +-- Beacon Recovery validity corrected


Patch B + qualified Patch C-C
        |
        +-- targeted mDNS suppressed
        +-- corrected Beacon Recovery semantics
```

The final combined configuration should only be considered after Patch C-C has
passed independent hardware qualification.

Patch A+B remains a historical isolation reference.

---

# 37. Why Patch C-C Should Be Tested Separately First

Combining Patch B and Patch C-C immediately would make causal interpretation
weaker.

If battery behavior improved, it would be difficult to determine how much came
from:

```text
mDNS suppression
```

versus:

```text
Beacon Recovery correction
```

Therefore the preferred order is:

```text
C-C alone
        |
        v
functional qualification
        |
        v
battery observation

Patch B alone
        |
        v
existing mDNS-isolation observation

then, if justified:

Patch B + C-C
```

This preserves experimental interpretability.

---

# 38. Preferred Long-Term Battery Test

After Patch C-C passes functional hardware qualification, a useful long-term
comparison would include at least:

```text
Stock 2.2.4
Patch B
Patch C-C
```

and later, if justified:

```text
Patch B + Patch C-C
```

Where practical:

- batteries should be charged consistently
- firmware should remain unchanged during the test
- devices should remain in stable installation positions
- battery percentage and voltage should be logged
- RSSI should be logged
- Recovery statistics should be retained
- uptime should be retained
- motor workload should be retained
- reboots should be documented
- exceptional network events should be documented

A useful observation period is at least several days.

Approximately:

```text
7 days
```

is substantially more informative than isolated 24-hour snapshots.

Approximately:

```text
14 days
```

or longer is preferable when practical.

---

# 39. Same-Device A/B Testing

A same-device comparison is scientifically valuable because it removes some
hardware variation.

Conceptually:

```text
Phase A

same TRV
stock 2.2.4
same physical location
same network
documented battery
        |
        v
Phase B

same TRV
Patch C-C
same physical location
same network
same battery if practical
```

However, this still cannot perfectly control:

- battery state between phases
- heating demand
- ambient temperature
- motor workload
- RF environment over time

Same-device testing is therefore stronger than simple cross-device comparison,
but not equivalent to laboratory power measurement.

---

# 40. Direct Electrical Measurement

Battery percentage and voltage are weak tools for measuring short-duration
events.

A direct current experiment could synchronize:

```text
supply current
WUP
debug output
WLAN state
Recovery event
motor movement
```

This could distinguish:

```text
normal idle
```

from:

```text
Recovery
```

and potentially from:

```text
persistent sleep-resource retention
```

Such a test would provide much stronger evidence for event-level energy cost.

No laboratory-grade current measurement is currently part of the established
dataset.

Therefore no exact:

```text
mA
mAh/day
battery-life reduction
```

should be assigned to the identified mechanisms.

---

# 41. Battery Logger Priorities

The logger should continue recording:

```text
timestamp
firmware
battery percentage
battery voltage
uptime
RSSI
diagnostic availability
Recovery statistics
```

Where technically reliable, it should additionally retain:

```text
motor_steps_raw
motor_steps_delta
motor_steps_total_interval
movement_count
```

For Patch C-C testing, useful additional fields include:

```text
real_beacon_skip
desired_beacon_skip
received beacon count
Recovery counter
```

The logger should preserve raw data so future interpretation can change without
losing the original observations.

---

# 42. Data Interpretation Rules

## Do

- use direct TRV status as the primary battery source
- record both percentage and voltage
- retain firmware identity
- retain uptime
- record RSSI
- record Recovery statistics where available
- document mDNS patch configuration
- retain motor workload where reliable
- document reboots
- document firmware changes
- document battery recharge events
- document device relocation
- split intervals at firmware transitions
- compare long-term trends
- retain raw data
- distinguish mechanism behavior from energy conclusions

## Do Not

- rank firmware solely by percentage decline
- rank firmware solely by short-term voltage decline
- assume equal battery capacity across physical devices
- treat RSSI as proof of BSSID
- treat desired beacon skip as actual measured radio behavior
- convert Recovery counts directly to mAh
- assume Patch A is the preferred final Recovery fix
- assume Patch B fixes battery drain
- assume A+B is the preferred final patch
- assume Patch C-C improves battery life before hardware data exist
- classify 2.1.0 as proven low-power baseline
- classify 2.1.3 as known-good
- combine mixed-firmware intervals
- attribute the `.77` Patch-B test to the older −58/−59 dBm observation
- claim that the historical battery-drain problem is solved

---

# 43. Evidence Summary

| Finding | Classification |
|---|---|
| Stock 2.2.4 can repeatedly enter Beacon Recovery | **PROVEN** |
| Approximately one Recovery/minute has been observed | **PROVEN** |
| C2 can sustain the recurring Recovery loop | **PROVEN** |
| C1a native signed behavior exists | **PROVEN** |
| C1a is a genuine control-validity defect | **STRONGLY SUPPORTED** |
| Stock baseline can survive invalid measurement intervals | **PROVEN** |
| C1b is a genuine measurement-validity defect | **STRONGLY SUPPORTED** |
| Exact cause of first field Recovery trigger | **UNKNOWN** |
| Periodic mDNS occurs in 2.1.3 at ~60 s | **PROVEN** |
| Periodic mDNS occurs in stock 2.2.4 at ~180 s | **PROVEN** |
| Comparable periodic mDNS was observed in 2.1.0 test window | **UNKNOWN; none was observed during that finite window** |
| Patch B capture suppressed targeted periodic mDNS traffic | **PROVEN** |
| Beacon Recovery remains with Patch B | **PROVEN** |
| Patch A suppresses targeted Recovery | **PROVEN under tested conditions** |
| Patch A correctly repairs C1a/C1b/C2 | **UNKNOWN; it bypasses Recovery instead** |
| A+B suppressed both targeted recurring behaviors during monitored runtime | **PROVEN** |
| A+B improves long-term battery endurance | **UNKNOWN** |
| Patch C-C passed static pre-build qualification | **PROVEN as project qualification status** |
| Patch C-C runtime correctness | **UNKNOWN** |
| Patch C-C battery improvement | **UNKNOWN** |
| Recovery suppression alone eliminates all battery decline | **UNKNOWN; historical observations demonstrate it is insufficient as a general conclusion** |
| Periodic mDNS is a major battery-drain contributor | **UNKNOWN** |
| WUP/EM2 behavior materially contributes to field battery drain | **UNKNOWN** |
| RSSI alone explains battery drain | **UNKNOWN** |
| Static IP/DHCP explains battery drain | **UNKNOWN** |
| Historical battery drain has been solved | **UNKNOWN** |

---

# 44. Current User-Level Interpretation

## Stock 2.2.4

```text
Periodic mDNS:
present

Beacon Recovery:
can become persistent

Battery impact:
not quantitatively isolated
```

## Patch A

```text
Targeted Recovery suppression:
confirmed under tested conditions

Underlying validity semantics:
not corrected

Role:
historical mechanism-isolation patch

Battery improvement:
unknown
```

## Patch B

```text
Targeted periodic mDNS suppression:
strongly supported by runtime capture

Beacon Recovery:
remains stock

Role:
mDNS-isolation patch

Battery improvement:
unknown
```

## Patch A+B

```text
Both targeted recurring mechanisms:
suppressed during monitored runtime

Normal operation:
observed

Role:
historical combined isolation experiment

Long-term battery improvement:
unknown
```

## Patch C-C

```text
Purpose:
correct C1a / C1b / C2 while preserving legitimate Recovery

Static pre-build qualification:
passed

Hardware qualification:
pending

Battery improvement:
unknown
```

---

# 45. Current Research Priorities

The current priorities are:

1. preserve the historical Patch-A/Patch-B/A+B isolation dataset
2. continue the existing long-term battery logging
3. retain motor workload where technically reliable
4. keep `.229` as an unmodified stock 2.2.4 reference where practical
5. build Patch C-C using a growth-aware GBL process
6. independently verify the generated firmware/container before flashing
7. perform controlled Patch C-C hardware qualification
8. verify legitimate Recovery remains possible after a fresh qualifying event
9. verify the C2 stale-state recurrence is removed
10. monitor network availability and PM restoration
11. begin Patch C-C long-term battery observation only after functional
    qualification
12. keep Patch B as the isolated mDNS comparison
13. consider a combined Patch-B + Patch-C-C experiment only after C-C has been
    independently qualified
14. avoid premature battery-life claims
15. continue investigating older inherited drain mechanisms separately

---

# 46. Current Experimental Pipeline

The current project state is:

```text
Static reverse engineering
        |
        v
C1a / C1b / C2 identified
        |
        v
Patch C-C designed
        |
        v
independent static falsification
        |
        v
static pre-build qualification PASSED
        |
        v
growth-aware experimental build
        |
        v
independent binary / GBL verification
        |
        v
controlled hardware qualification
        |
        v
long-term battery comparison
```

In parallel:

```text
Patch B
        |
        v
mDNS isolation
        |
        v
long-term battery observation
```

Historical:

```text
Patch A / A+B
        |
        v
mechanism-isolation evidence
```

---

# 47. Current Scientific Interpretation

The current evidence does not support a single-cause battery-drain model.

Instead, several independently identified mechanisms may contribute.

Periodic mDNS is a real recurring network workload.

Beacon Recovery is a real additional 2.2.4 workload and can become
self-sustaining through C2.

C1a and C1b can create invalid control evidence under reachable conditions.

Historical battery decline before 2.2.4 demonstrates that Beacon Recovery alone
cannot explain the complete problem.

The WUP/EM2 candidate remains unresolved.

Valve workload, battery condition and RF environment remain substantial
confounding variables.

Therefore the strongest current statement is:

> Multiple firmware mechanisms with plausible energy relevance have been
> identified, but their individual and combined quantitative contributions to
> Shelly TRV Gen1 battery drain have not yet been established.

Patch C-C is the current preferred Beacon-Recovery correction candidate because
it attempts to preserve legitimate Recovery rather than simply disabling the
mechanism.

Its static design has passed pre-build qualification.

Its runtime and battery behavior remain to be established on hardware.

---

# 48. What Has Been Established

The project has established that:

- stock 2.2.4 can enter persistent Beacon Recovery
- the persistent C2 recurrence exists in host control flow
- C1a signed-value behavior exists
- baseline-age validity problems exist in the stock measurement design
- periodic mDNS exists before 2.2.4
- 2.1.3 shows approximately 60-second periodic mDNS
- stock 2.2.4 shows approximately 180-second periodic mDNS
- Patch B suppresses the targeted periodic mDNS traffic during the tested window
- Patch B does not remove Beacon Recovery
- Patch A suppresses targeted Recovery
- A+B can suppress both targeted recurring behaviors during monitored runtime
- suppression of Beacon Recovery alone does not guarantee absence of observed
  battery decline
- historical drain existed before the 2.2.4-specific Recovery mechanism
- Patch C-C has passed static pre-build qualification

---

# 49. What Has Not Been Established

The project has not established:

- exact mAh/day consumed by periodic mDNS
- exact mAh/day consumed by Beacon Recovery
- exact battery-life improvement from Patch B
- exact battery-life improvement from Patch A
- exact battery-life improvement from A+B
- Patch C-C runtime correctness
- Patch C-C battery improvement
- exact cause of the first field Recovery trigger
- exact contribution of WUP/EM2 behavior
- that one firmware mechanism explains all historical drain
- that static IP or DHCP materially affects battery endurance
- that RSSI alone explains battery endurance
- that AP selection explains persistent Recovery
- that the historical battery-drain problem has been solved

---

# 50. Current Conclusion

The long-term battery investigation has progressed from simple firmware
comparison to mechanism-level analysis.

The early experiments established two recurring workloads:

```text
periodic mDNS
```

and:

```text
2.2.4 Beacon Recovery
```

Patch B successfully isolates the first under the tested conditions.

Patch A historically isolated the second by bypassing Recovery.

The later reverse engineering changed the interpretation of Beacon Recovery
substantially.

The current model separates:

```text
C1a
control-value validity

C1b
measurement-window validity

C2
post-Recovery freshness
```

C2 explains how recurring Recovery can become self-sustaining.

Patch C-C is designed to correct these semantics while preserving legitimate
Recovery and diagnostic state.

It has passed static pre-build qualification but has not yet completed hardware
qualification.

The battery data must therefore continue to be interpreted conservatively.

Historical observations already show that:

```text
Recovery suppression
```

is not equivalent to:

```text
complete battery-drain solution
```

and that:

```text
2.2.4 Beacon Recovery
```

cannot explain battery drain observed on earlier firmware.

The current research objective is no longer simply:

```text
Can identified workloads be disabled?
```

It is:

```text
Can the identified defects be corrected without damaging legitimate behavior,
and does doing so produce a reproducible improvement in real-world battery
endurance?
```

That question remains open.

---

# Related Documents

Firmware chronology:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

Power management:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Beacon RX counter:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

Real beacon skip:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

AP selection and roaming:

[`../reverse-engineering/ap-selection-and-roaming.md`](../reverse-engineering/ap-selection-and-roaming.md)

Periodic mDNS:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

mDNS runtime comparison:

[`mdns-runtime-comparison.md`](mdns-runtime-comparison.md)

Patch documentation:

[`../patch/README.md`](../patch/README.md)

---

# Methodology Note

The battery investigation uses telemetry and runtime behavior from personally
owned Shelly TRV Gen1 devices.

The dataset is observational and contains uncontrolled variables.

It must not be represented as laboratory-grade power characterization.

Firmware identity is determined from the actual device state at the relevant
timestamp.

Raw observations should be retained so conclusions can be re-evaluated as the
firmware model improves.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

Experimental firmware modifications are intended for controlled research on
personally owned hardware.

Battery observations do not constitute manufacturer specifications or
guaranteed battery-life results.