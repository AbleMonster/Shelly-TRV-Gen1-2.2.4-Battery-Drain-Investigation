# Battery Testing

## Scope

This document tracks the long-term battery investigation for Shelly TRV Gen1
devices across different firmware and patch configurations.

The purpose of the test is to determine whether measurable battery behavior
correlates with:

- firmware version;
- the firmware 2.2.4 beacon-recovery mechanism;
- the periodic mDNS restart mechanism;
- experimental suppression of beacon recovery;
- experimental suppression of periodic mDNS restart;
- the combined A+B patch;
- Wi-Fi conditions;
- valve/motor workload;
- device-specific battery characteristics;
- other configuration-specific factors.

The current investigation is a long-term observational comparison.

It is **not** a laboratory-grade electrical power measurement.

> **Important:** Cross-device differences in battery percentage or battery
> voltage must not be interpreted as direct proof of firmware energy
> consumption.

---

# 1. Research Questions

The battery investigation currently addresses several separate questions.

## 1.1 Does stock 2.2.4 repeatedly enter beacon recovery?

Yes.

This has been demonstrated repeatedly at runtime.

Affected stock 2.2.4 devices can enter the identified recovery path at
approximately:

```text
1 event / minute
```

The characteristic log sequence is:

```text
Beacon skip error! Attempt recovery
        ↓
Power save state 1
        ↓
approximately 5 seconds
        ↓
Power save state 3
```

The behavior has also been observed with relatively good RSSI and without valve
movement.

---

## 1.2 Does Patch A suppress beacon recovery?

Yes, under the tested conditions.

Patched 2.2.4 devices continue to calculate beacon statistics and
`real_beacon_skip`, while the targeted recovery transition remains suppressed.

Observed Patch-A devices have shown:

```text
beacon statistics active
real_beacon_skip active
desired_beacon_skip active
beacon recovery/error counter = 0
```

This confirms the intended control-flow effect of Patch A.

---

## 1.3 Does Patch B suppress periodic mDNS restart activity?

Yes, during the monitored runtime test.

Patch B was installed by itself on device `.77`.

A TShark capture filtered for:

```text
UDP port 5353
host 192.168.178.77
```

showed:

```text
0 packets captured
```

during the monitored test window of at least approximately 10 minutes.

This provides strong finite-window evidence that the targeted periodic mDNS
restart was suppressed.

It does **not** prove that all mDNS functionality is disabled.

Other event-driven mDNS paths remain present in the firmware.

---

## 1.4 Does suppressing periodic mDNS also suppress beacon recovery?

No, under the tested conditions.

Device `.77` continued to enter the beacon-recovery path after installation of
Patch B.

The recovery continued approximately once per minute.

This was observed even around:

```text
RSSI:
-58 to -59 dBm

desired beacon skip:
20
```

Therefore:

> The periodic mDNS restart is not required for the observed recurring
> beacon-recovery behavior under the tested conditions.

This does not prove universal independence between the mechanisms under every
possible operating condition.

---

## 1.5 Can Patch A and Patch B operate together?

Yes, under the tested conditions.

The combined A+B firmware was installed on device `.226`.

Runtime testing showed:

```text
periodic mDNS restart:
not observed during monitored capture

recurring beacon recovery:
not observed during multi-hour debug-log observation

normal Wi-Fi:
operational

normal TRV operation:
operational
```

The combined patch therefore appears functionally valid for the two targeted
mechanisms.

---

## 1.6 Does suppressing these mechanisms improve battery life?

This is **not yet proven**.

The current data contain encouraging observations, particularly from the first
runtime period of the combined A+B device.

However, the dataset is not yet sufficient to establish:

```text
Patch A+B
    =
measurably improved long-term battery endurance
```

Longer observation is required.

---

## 1.7 Did battery drain already exist before 2.2.4?

Historical observation indicates that firmware 2.1.8 also appeared to consume
battery relatively quickly.

Therefore the known 2.2.4 beacon-recovery mechanism cannot explain the complete
historical battery-drain problem.

---

## 1.8 Where was the older drain introduced?

This remains unresolved.

Current investigation includes the possibility that an energy-relevant change
may have occurred as early as:

```text
2.1.0 -> 2.1.3
```

Firmware 2.1.3 must therefore not be treated as a known-good battery reference.

---

# 2. Measurement Sources

The battery logger queries each TRV directly.

The primary device-reported battery values are:

```text
bat.value
bat.voltage
```

Where available, additional diagnostic values are collected from `/stats`.

These include values associated with:

- `real_beacon_skip`;
- desired beacon skip;
- beacon receive statistics;
- beacon missed statistics;
- beacon recovery/error counters;
- other firmware-specific diagnostic values.

The logger also records:

- firmware version;
- uptime;
- RSSI;
- device address;
- diagnostic availability.

Runtime debug logs are retained separately where required.

These logs provide additional information including:

- beacon-recovery events;
- power-management transitions;
- valve movement;
- requested motor steps;
- executed motor steps.

Motor-step information is planned for direct inclusion in future battery-logger
reports.

---

# 3. Authoritative Battery Source

For this investigation, the battery state reported directly by the TRV is
treated as the primary source.

Values displayed by Home Assistant are not used as the authoritative battery
measurement if they differ from the current TRV status.

For example, a device may report:

```text
TRV status:
100 %

Home Assistant:
91 %
```

For this research, the direct TRV value is retained.

Home Assistant may contain an older or differently updated representation of
the device state.

---

# 4. Battery Percentage vs. Battery Voltage

Both percentage and voltage are recorded.

Neither should be interpreted alone as a direct measurement of consumed energy.

## Battery percentage

Battery percentage is calculated by the device firmware.

It may be affected by:

- firmware estimation logic;
- voltage-curve assumptions;
- load history;
- battery chemistry;
- calibration behavior.

A freshly charged battery can remain at:

```text
100 %
```

while its measured voltage already changes.

For short-term analysis, battery percentage can therefore hide changes that are
visible in the voltage data.

## Battery voltage

Voltage provides an additional signal but is also load-dependent.

It can vary with:

- motor operation;
- radio activity;
- temperature;
- battery internal resistance;
- recovery after load;
- battery age;
- time since charging.

Therefore the preferred interpretation uses:

```text
percentage trend
+
voltage trend
+
workload
+
runtime diagnostics
```

rather than any single reading.

---

# 5. Battery Age and Condition

The batteries used in the different TRVs are not guaranteed to have:

- identical age;
- identical capacity;
- identical internal resistance;
- identical charge history;
- identical previous workload;
- identical starting state of charge.

This remains one of the largest limitations of cross-device comparison.

For example:

```text
TRV A:
99 % -> 90 %

TRV B:
99 % -> 95 %
```

does **not** by itself establish that the firmware running on TRV A consumes
more energy.

Battery age and condition remain explicit confounding variables.

---

# 6. Valve Motor Workload

Valve movement represents a real additional electrical load.

A TRV performing substantially more valve movement can consume more battery even
if its WLAN and MCU behavior is otherwise identical to another device.

Conceptually:

```text
total battery consumption
        |
        +---- baseline electronics
        |
        +---- WLAN activity
        |
        +---- MCU awake time
        |
        +---- valve motor work
```

Motor-step data therefore provide an important additional normalization
variable.

The goal is not currently to convert motor steps into exact electrical energy.

Instead, the value provides a relative indication of mechanical workload.

For example:

```text
Device A:
battery decline = high
motor steps     = very high

Device B:
battery decline = high
motor steps     = very low
```

These observations should not be interpreted in the same way.

Runtime logs from the current test already demonstrate substantial individual
valve movements involving hundreds or more than one thousand motor steps.

Future logger/report versions should therefore include:

- raw motor-step information where available;
- delta motor steps between samples;
- total motor steps during the report interval;
- number of valve movements where practical.

Before using a firmware-exposed motor-step value as a cumulative metric, its
behavior across reboot, reset and possible counter rollover must be verified.

---

# 7. Wi-Fi Signal Strength

RSSI is recorded because Wi-Fi conditions may affect power consumption.

The analyzed firmware uses the following normal desired beacon-skip policy:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

A lower desired skip creates more frequent beacon-listening opportunities.

This does **not** imply that total device power consumption scales directly or
proportionally with the skip value.

Other relevant factors include:

- actual WF200 power state;
- packet traffic;
- retransmissions;
- MCU wake time;
- recovery behavior;
- valve workload.

---

# 8. Good RSSI Does Not Prevent Beacon Recovery

The newer runtime tests provide an important additional result.

The recurring beacon-recovery behavior has been observed at relatively good
signal strength.

The Patch-B-only `.77` device continued entering recovery around:

```text
RSSI:
-58 to -59 dBm

desired beacon skip:
20
```

Stock 2.2.4 `.229` has also shown the recovery mechanism under usable WLAN
conditions.

Therefore:

```text
poor RSSI
```

is not a necessary condition for the observed recurring recovery cycle.

This does not mean that RF conditions are irrelevant to total energy
consumption.

It means only that weak RSSI cannot by itself explain the recovery behavior.

---

# 9. RSSI Is Not the Complete RF Picture

The displayed RSSI alone does not establish which access point or BSSID the
device selected.

Reverse engineering showed that the host connects using:

```text
BSSID: wildcard
channel: 0
prevent_roaming: 1
```

The host does not explicitly select the strongest scanned BSSID itself.

Initial AP selection occurs below the analyzed host logic.

Once connected, autonomous roaming is prevented.

Therefore two devices with similar displayed RSSI values may still have
different RF histories or associations.

Detailed analysis is documented in:

- [`../reverse-engineering/ap-selection-and-roaming.md`](../reverse-engineering/ap-selection-and-roaming.md)

---

# 10. Static IP vs. DHCP

The test group does not use identical network configuration.

Known static-IP devices include:

```text
.11
.77
.88
```

Other devices in the comparison use DHCP.

There is currently no evidence that static IP or DHCP is responsible for the
battery-drain behavior.

The variable is retained because it can potentially affect:

- DHCP traffic;
- reconnect behavior;
- network initialization;
- timing after WLAN association.

No causal conclusion should be drawn without a controlled comparison.

---

# 11. Experimental Device Matrix

The current investigation uses six physical Shelly TRV Gen1 devices.

During the mechanism-isolation phase, the relevant configurations became:

| Device | Relevant configuration | Network | Experimental role |
|---|---|---|---|
| `.11` | 2.1.0 stock | Static IP | older firmware reference |
| `.77` | 2.2.4 + Patch B only | Static IP | isolated mDNS-patch test |
| `.88` | 2.2.4 + Patch A | Static IP | beacon-recovery patch test |
| `.226` | 2.2.4 + Patch A+B | DHCP | combined-patch test |
| `.228` | 2.2.4 + Patch A | DHCP | beacon-recovery patch test |
| `.229` | 2.2.4 stock | DHCP | unmodified control |

These are the relevant recent experimental roles.

Several devices ran different firmware earlier in the investigation.

Therefore:

> Firmware identity must be taken from the actual device status and measurement
> timestamp, not inferred from the device IP address alone.

---

# 12. Device `.11`

## Role

Older firmware reference.

## Firmware

```text
2.1.0
20211223-144805/v2.1.0@d30148ec
```

## Network

```text
Static IP
```

## Relevant observations

Earlier runtime logging demonstrated long uptime on firmware 2.1.0 without the
repeating 2.2.4-style beacon-recovery sequence.

A previous log showed approximately:

```text
uptime:
355568 s

battery:
100 %

voltage:
3.886 V
```

before an intentional reboot.

Historical RSSI around `-83 dBm` was observed in one earlier log.

Later battery-logger measurements showed substantially stronger signal around
approximately `-59 dBm`.

The earlier weak RSSI must therefore not be treated as the permanent RF
condition of this device.

## Interpretation

Firmware 2.1.0 remains a useful older reference.

Its historical endurance appears interesting, but this remains observational.

It must not be classified as a laboratory-proven low-power baseline.

---

# 13. Device `.77`

## Earlier role

Firmware 2.1.3 comparison device.

This device previously contributed runtime data showing the behavior of firmware
2.1.3.

## Current experimental role

Isolated Patch-B test.

## Current firmware configuration

```text
2.2.4
Patch B active
Patch A inactive
```

Patch B suppresses the periodic 2.2.4 mDNS restart path.

The beacon-recovery mechanism remains unmodified.

## Network

```text
Static IP
```

## mDNS result

During the monitored TShark test:

```text
periodic mDNS packets captured:
0
```

This is strong finite-window evidence that the targeted periodic mDNS restart
was suppressed.

## Beacon-recovery result

Despite Patch B, the device continued showing:

```text
Beacon skip error! Attempt recovery
```

approximately once per minute.

This continued even with approximately:

```text
RSSI:
-58 to -59 dBm

desired beacon skip:
20
```

The logger recovery counter also showed the characteristic progression of
approximately:

```text
+30 / 30 minutes
```

## Interpretation

`.77` provides the strongest experimental evidence that suppressing the periodic
mDNS restart does not suppress the observed beacon-recovery cycle.

Patch B therefore does not indirectly solve the beacon-recovery behavior under
the tested conditions.

---

# 14. Device `.88`

## Role

Patch-A test device.

## Firmware configuration

```text
2.2.4
Patch A active
```

## Network

```text
Static IP
```

## Relevant observations

The device continues to calculate:

```text
real_beacon_skip
```

with values varying significantly over time.

Values have occurred that would be relevant to the stock 2.2.4 recovery
decision.

At the same time:

```text
beacon recovery/error counter:
0
```

remained observed under patched operation.

## Interpretation

This is strong runtime evidence that Patch A bypasses the targeted recovery
action while leaving the underlying statistics calculation active.

It is **not** evidence by itself that battery consumption is improved.

---

# 15. Device `.228`

## Role

Second Patch-A test device.

## Firmware configuration

```text
2.2.4
Patch A active
```

## Network

```text
DHCP
```

## Relevant observations

The device has been tested in different physical positions.

Observed RSSI has therefore changed over time.

Examples include:

```text
before relocation:
-57 to -58 dBm

after relocation:
approximately -62 to -65 dBm
```

Later battery-report data have shown values approximately in the range:

```text
RSSI:
-63 to -71 dBm

real_beacon_skip:
frequently low

desired beacon skip:
normally 20 when RSSI permits

beacon recovery/error counter:
0
```

## Battery relevance

A later approximately 24-hour observation showed a noticeable decline despite
the recovery counter remaining zero.

Representative endpoints from that interval were approximately:

```text
battery:
74 % -> 65 %

voltage:
3.686 V -> 3.623 V
```

These numbers must be interpreted cautiously because battery condition, motor
workload and other variables are not controlled.

However, the observation is important because it demonstrates:

```text
successful beacon-recovery suppression
```

does not automatically imply:

```text
no observed battery decline
```

## Interpretation

`.228` is currently one of the clearest reasons not to classify Patch A alone
as a proven complete battery-drain fix.

---

# 16. Device `.226`

## Earlier role

Firmware 2.1.3 comparison device.

An earlier approximately 24-hour report included roughly:

```text
battery:
99 % -> 88 %

voltage:
3.847 V -> 3.775 V

RSSI:
approximately -71 to -73 dBm
```

These data remain observational and are affected by multiple confounding
variables.

## Current role

Combined A+B patch test.

## Current firmware configuration

```text
2.2.4
Patch A active
Patch B active
```

## Network

```text
DHCP
```

## Runtime validation

After installation of the combined firmware:

```text
firmware boot:
successful

Wi-Fi:
operational

local HTTP:
operational

cloud:
operational after startup

valve / thermostat:
operational
```

The monitored TShark capture did not show the targeted periodic mDNS cycle.

The subsequent multi-hour debug log did not show the recurring:

```text
Beacon skip error! Attempt recovery
```

sequence.

## Initial battery observation

The report interval containing the firmware transition must be divided into:

```text
before A+B installation
```

and:

```text
after A+B installation
```

because it contains two different firmware configurations.

Before the transition, representative 2.1.3 values included approximately:

```text
08:00:
74 %
3.684 V

19:00:
70 %
3.656 V
```

After installation of the combined patch, the initial overnight voltage was
comparatively stable around approximately:

```text
3.653 to 3.659 V
```

with reported battery around:

```text
69 to 70 %
```

For example, approximately:

```text
19:30:
3.654 V

07:30:
3.653 V
```

was observed in the initial post-patch period.

## Interpretation

This is an encouraging initial observation.

It is **not** sufficient to establish improved battery life because:

- the post-patch observation period is short;
- the report contains a firmware transition;
- voltage can fluctuate naturally;
- motor workload is not yet normalized;
- this is one physical device.

`.226` should therefore be treated as:

```text
promising early A+B battery observation
```

rather than:

```text
proof of battery-drain fix
```

---

# 17. Device `.229`

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

## Firmware-history warning

This device ran firmware 2.1.8 during an earlier phase.

Some older report headings therefore still describe it as 2.1.8.

After the firmware transition, direct status confirmed stock 2.2.4.

Reports spanning that transition must not be interpreted as one continuous
firmware phase.

## Beacon-recovery behavior

Stock 2.2.4 repeatedly produces the known recovery cycle.

The logger counter has shown:

```text
+30 events / 30 minutes
```

for extended periods.

This corresponds closely to:

```text
1 recovery / minute
```

or approximately:

```text
60 recoveries / hour
1440 recoveries / day
```

if the rate continues uninterrupted.

This extrapolation describes event frequency only.

It is **not** a direct energy measurement.

## RSSI relevance

The recovery behavior has occurred with relatively good RSSI.

It has also been observed while the valve was stationary.

Therefore neither:

```text
poor RSSI
```

nor:

```text
motor movement
```

is required for the recurring recovery to occur.

## Initial fully charged observation

During a later approximately 24-hour period, the device remained around:

```text
100 %
```

while voltage changed approximately from:

```text
4.133 V
```

to:

```text
4.111 V
```

or roughly:

```text
-22 mV
```

over the observed interval.

The reported percentage remaining at 100 % illustrates why voltage is retained
alongside percentage.

This voltage change must not be directly compared with another physical device
as a firmware-efficiency ratio.

---

# 18. Mechanism-Isolation Phase

The previous test phase was designed primarily to distinguish firmware
mechanisms.

The resulting experimental matrix was:

```text
Stock 2.2.4 (.229)
        |
        +-- periodic mDNS present
        |
        +-- beacon recovery present


Patch B only (.77)
        |
        +-- targeted periodic mDNS suppressed
        |
        +-- beacon recovery remains


Patch A (.88 / .228)
        |
        +-- beacon statistics remain active
        |
        +-- beacon recovery suppressed


Patch A+B (.226)
        |
        +-- targeted periodic mDNS not observed
        |
        +-- recurring beacon recovery not observed
```

This phase has now provided useful functional evidence for both patches.

The remaining central question is no longer simply:

```text
Do the patches alter the intended firmware paths?
```

That has been demonstrated.

The next question is:

```text
Does suppressing these recurring workloads produce a reproducible improvement
in long-term battery behavior?
```

---

# 19. Beacon-Recovery Counter as a Diagnostic

The recovery/error counter is a useful runtime indicator on firmware 2.2.4.

On affected stock or Patch-B-only configurations:

```text
30 events / 30 minutes
```

is consistent with:

```text
approximately 1 event / minute
```

Patch-A configurations have shown:

```text
beacon statistics active
real_beacon_skip active
recovery/error counter = 0
```

This creates a useful behavioral distinction.

The counter should not be interpreted as a direct energy measurement.

For example:

```text
1440 recoveries/day
```

does not tell us:

```text
X mAh/day
```

without direct electrical measurement.

---

# 20. `real_beacon_skip` and Battery Testing

Firmware 2.2.4 derives `real_beacon_skip` from WF200 beacon receive statistics.

A low or qualifying `real_beacon_skip` value does not itself represent battery
consumption.

Its relevance is indirect:

```text
real_beacon_skip
       |
       v
stock recovery predicate
       |
       v
state 1
       |
       v
temporary additional WLAN activity
       |
       ?
       v
additional energy
```

Patch A modifies the recovery decision without removing the underlying
calculation.

This makes patched devices particularly useful because they allow:

```text
same statistics mechanism
without targeted recovery entry
```

Detailed analysis:

- [`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)
- [`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)
- [`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

---

# 21. Periodic mDNS and Battery Testing

Runtime packet capture established:

```text
2.1.0:
no comparable periodic mDNS burst observed during ~13 min

2.1.3:
approximately one burst every 60 s

2.2.4 stock:
approximately one burst every 180 s
```

Patch B suppresses the targeted periodic 2.2.4 restart during the monitored
runtime test.

Each normal recurring mDNS sequence can involve approximately:

```text
3 probes
+
1 announcement
```

This represents real additional processing and network activity.

However, its electrical cost is unknown.

The current battery test therefore treats periodic mDNS as:

```text
confirmed recurring workload
+
plausible energy contributor
+
unquantified battery effect
```

and not as a proven battery-drain cause.

Detailed analysis:

- [`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

---

# 22. Initial Battery Trend Snapshot

The current dataset allows a preliminary observational snapshot.

These values are **not** a controlled firmware-efficiency benchmark.

| Device | Configuration | Representative interval | Battery | Voltage change | Recovery |
|---|---|---|---:|---:|---|
| `.229` | Stock 2.2.4 | ~24 h, freshly charged region | ~100 % | ~4.133 → 4.111 V | ~1/min |
| `.77` | Patch B only | ~24 h | ~99 % | ~3.897 → 3.872 V | ~1/min |
| `.88` | Patch A | ~23.5 h | ~86 → 83 % | ~3.764 → 3.743 V | suppressed |
| `.228` | Patch A | ~24 h | ~74 → 65 % | ~3.686 → 3.623 V | suppressed |
| `.226` | A+B, initial post-install period | ~12 h | ~69–70 % | approximately stable around 3.65 V | not observed |

The table should be interpreted only as an observational snapshot.

It must **not** be used to calculate statements such as:

```text
Patch X saves Y %
```

or:

```text
Firmware A consumes Z times more energy than firmware B
```

because the physical devices, batteries and workloads differ.

---

# 23. What the Initial Snapshot Tells Us

Despite the limitations, the snapshot provides several useful findings.

## Finding 1 — Stock 2.2.4 has persistent additional activity

`.229` repeatedly enters beacon recovery at approximately one event per minute.

This represents an additional recurring firmware workload that Patch A removes.

## Finding 2 — Patch B alone does not remove that workload

`.77` continues showing approximately the same recovery frequency despite the
targeted periodic mDNS restart being suppressed.

## Finding 3 — Patch A successfully removes the recovery activity

`.88` and `.228` continue producing beacon statistics while their targeted
recovery counter remains zero.

## Finding 4 — Recovery suppression alone has not eliminated all observed battery decline

`.228` showed substantial reported battery and voltage decline despite the
recovery mechanism being suppressed.

This is important evidence against the hypothesis:

```text
Beacon recovery is the only cause of the historical battery drain.
```

## Finding 5 — A+B currently looks promising but remains unproven

`.226` showed comparatively stable voltage during its first post-installation
overnight period.

This is encouraging but statistically and experimentally insufficient for a
battery-life conclusion.

---

# 24. Major Confounding Variables

The current observational comparison contains several important confounding
variables.

| Variable | Controlled? | Relevance |
|---|---|---|
| Firmware | Partially | Primary variable under investigation |
| Physical TRV | No | Hardware variation possible |
| Battery age | No | Potentially large effect |
| Battery capacity | No | Potentially large effect |
| Internal resistance | No | Affects voltage under load |
| Starting state of charge | No | Limits percentage comparison |
| Valve workload | No | Motor is a significant load |
| Motor steps | Partially available | Important normalization variable |
| RSSI | Recorded | Affects RF behavior and desired skip |
| Actual BSSID | Not continuously recorded | RF association uncertainty |
| Device location | Not identical | RF and temperature differences |
| Static IP / DHCP | Mixed | Possible network behavior difference |
| Temperature | Not fully controlled | Battery and heating-load effect |
| Heating demand | Not identical | Changes motor workload |
| Firmware uptime | Recorded | Identifies resets and transitions |
| Firmware transition | Present in some reports | Requires interval separation |

Any firmware conclusion must account for these limitations.

---

# 25. Why Cross-Device Percentage Comparison Is Insufficient

A comparison such as:

```text
Device A:
-3 %

Device B:
-9 %
```

cannot establish firmware efficiency.

The correct interpretation is closer to:

```text
battery trend
    +
voltage trend
    +
motor workload
    +
RSSI
    +
recovery activity
    +
mDNS configuration
    +
uptime
    +
device/battery history
    =
observational evidence
```

Only when several variables align over longer periods can the dataset support a
stronger firmware hypothesis.

---

# 26. Motor Steps as Evidence of Additional Work

Motor-step data should be retained with future battery reports whenever
possible.

The main purpose is not to calculate exact motor energy.

Instead, it provides evidence of relative additional work.

The current debug logs already show individual movements involving values such
as:

```text
68 steps
```

and other movements involving several hundred or more than one thousand steps.

A device that performs a large amount of valve work cannot be directly compared
with a mostly stationary device without considering that workload.

Future reports should therefore include, where technically reliable:

- total motor steps per interval;
- number of valve movements;
- battery voltage change;
- battery percentage change;
- firmware / patch configuration;
- RSSI statistics;
- recovery count;
- uptime.

---

# 27. Uptime and Firmware Transitions

Uptime remains an important diagnostic field.

A sudden reset can indicate:

- reboot;
- firmware installation;
- power interruption;
- device restart.

This was particularly useful for identifying firmware transitions on `.229`
and `.226`.

For example:

```text
old firmware
high uptime
        |
        | OTA / reboot
        v
new firmware
low uptime
```

Reports containing such a boundary must be split before calculating firmware
trends.

A 24-hour report containing:

```text
12 hours firmware A
+
12 hours firmware B
```

must not be treated as a 24-hour measurement of either firmware.

---

# 28. Static IP vs. DHCP

The current fleet contains both network configurations.

Examples include:

```text
Static:
.11
.77
.88

DHCP:
.226
.228
.229
```

This is potentially useful for future investigation.

However, because the devices also differ in battery, location, firmware and
workload, the current fleet does not constitute a controlled static-vs-DHCP
experiment.

Until stronger evidence appears:

> Static IP vs. DHCP remains a recorded variable, not a battery-drain
> explanation.

---

# 29. Current Battery-Drain Model

The current evidence supports a multi-mechanism model.

A simplified representation is:

```text
normal TRV baseline
       |
       +-- MCU / electronics
       |
       +-- normal WLAN power save
       |
       +-- cloud / controller traffic
       |
       +-- valve motor workload
       |
       +-- RF conditions
       |
       +-- periodic mDNS restart
       |
       +-- 2.2.4 beacon recovery
       |
       +-- possible conditional sleep-resource retention
       |
       v
total battery consumption
```

Patch A removes the targeted 2.2.4 beacon-recovery entry.

Patch B removes the targeted periodic 2.2.4 mDNS restart.

The combined patch removes both targeted recurring mechanisms under the tested
conditions.

It does **not** remove:

- normal device workload;
- valve motor consumption;
- normal network communication;
- every possible firmware power-management issue;
- the inherited conditional WUP/EM2 failure path.

Therefore:

```text
A+B removes two identified workloads
```

must not be interpreted as:

```text
A+B necessarily fixes all battery drain
```

---

# 30. Evidence Status

## Proven by runtime observation

- Stock 2.2.4 can repeatedly enter the targeted beacon-recovery path.
- Approximately one recovery event per minute has been observed.
- Recovery can occur with relatively good RSSI.
- Recovery can occur without valve movement.
- Patch-A devices suppress the targeted recovery under tested conditions.
- Patch-A devices continue reporting beacon statistics.
- Firmware 2.1.3 produces recurring mDNS traffic at approximately 60-second
  intervals.
- Stock firmware 2.2.4 produces recurring mDNS traffic at approximately
  180-second intervals.
- Patch B suppresses the targeted periodic mDNS activity during the monitored
  test window.
- Patch B alone does not suppress beacon recovery.
- Patch A+B boots and operates on real hardware.
- The targeted periodic mDNS cycle was not observed during the monitored
  combined-patch capture.
- The recurring beacon-recovery sequence was not observed during the monitored
  multi-hour combined-patch log.

## Observed but confounded

- Different physical devices show different battery trends.
- Firmware 2.1.8 historically appeared to exhibit battery drain.
- Firmware 2.1.0 remains interesting as an older reference.
- Firmware 2.1.3 devices have shown battery decline.
- Patch-A `.228` continued showing noticeable battery decline despite recovery
  suppression.
- Combined A+B `.226` showed encouraging initial voltage stability.

## Not proven

- Firmware 2.1.0 intrinsically consumes less energy.
- Firmware 2.1.3 introduced the historical battery drain.
- Firmware 2.1.8 introduced the historical battery drain.
- Patch A improves long-term battery endurance.
- Patch B improves long-term battery endurance.
- Patch A+B improves long-term battery endurance.
- Recovery suppression alone solves the battery-drain problem.
- Periodic mDNS restart is a major battery-drain contributor.
- Static IP or DHCP materially changes battery consumption.
- RSSI alone explains battery drain.
- The WUP/EM2 retention path occurs frequently on physical devices.
- The historical battery-drain problem has been solved.

---

# 31. Completed Mechanism-Isolation Phase

The current work has progressed beyond the original single-patch comparison.

The following experiments have now been completed:

```text
Stock 2.2.4
    ↓
beacon recovery observed
periodic mDNS observed

Patch A
    ↓
beacon recovery suppressed

Patch B
    ↓
periodic mDNS suppressed
beacon recovery remains

Patch A+B
    ↓
both targeted recurring behaviors suppressed
during monitored runtime
```

This phase provides a useful foundation for the next battery experiment.

---

# 32. Next Long-Term Battery Test

The next phase will focus more directly on battery endurance.

The intended configuration is:

```text
1 × stock 2.2.4
        versus
multiple A+B patched devices
```

The stock 2.2.4 device will remain the control.

The remaining test devices can be standardized on the same combined A+B
firmware.

Before the comparison begins, the batteries should be charged as consistently
as practical.

The intended starting procedure is:

1. fully charge all participating TRVs;
2. leave `.229` on stock 2.2.4;
3. install the same validated A+B firmware on the patched group;
4. return all devices to normal installation positions;
5. start the comparison from a documented common time;
6. avoid firmware changes during the observation period;
7. continue automatic battery logging;
8. record reboots or exceptional events;
9. record motor workload;
10. compare trends over multiple days.

The preferred minimum useful period is approximately:

```text
7 days
```

with:

```text
14 days
```

or longer providing a stronger dataset.

Individual 24-hour periods will remain useful for diagnostics but should not
serve as the primary long-term battery conclusion.

---

# 33. Goals of the Next Test Phase

The next test should answer a more practical question:

> Do multiple A+B patched devices show reproducibly different long-term battery
> behavior from an otherwise normally operating stock 2.2.4 control?

The analysis should focus on:

```text
voltage trend
+
battery percentage trend
+
motor workload
+
RSSI
+
recovery activity
+
uptime / reboots
+
device-specific history
```

A useful positive result would not require every patched device to have an
identical voltage curve.

Instead, stronger evidence would consist of:

- repeatable absence of the targeted recurring mechanisms;
- normal long-term device operation;
- lower or slower battery decline across several patched devices;
- a persistent difference from the stock control;
- no obvious explanation from substantially lower motor workload.

---

# 34. Battery Logger Development

Before or during the next test phase, the battery logger should be extended to
retain motor activity where a reliable source can be identified.

Desired fields include:

```text
motor_steps_raw
motor_steps_delta
motor_steps_total_interval
```

if the underlying device value is cumulative and suitable for this purpose.

Before implementation, the field must be checked for:

- reset behavior;
- reboot behavior;
- firmware differences;
- counter rollover;
- whether it represents requested or executed steps;
- whether opening and closing steps use the same sign or absolute count.

The report generator should then correlate motor workload with:

- battery voltage;
- battery percentage;
- firmware configuration;
- recovery count;
- RSSI;
- uptime.

This will reduce one of the largest remaining interpretation uncertainties.

---

# 35. Preferred Controlled Same-Device Experiment

A same-device A/B comparison remains scientifically stronger than the current
cross-device comparison.

For example:

```text
Phase A:

same TRV
stock 2.2.4
same battery
same location
same network
similar workload

        |
        v

Phase B:

same TRV
A+B 2.2.4
same battery
same location
same network
similar workload
```

However, such a test is difficult to perform perfectly because:

- battery state changes between phases;
- heating demand changes;
- motor workload changes;
- environmental conditions change.

The multi-device long-term test therefore remains useful even though it is not
a laboratory-controlled experiment.

---

# 36. Direct Electrical Measurement

Battery percentage and voltage are useful for long-term observation but weak
for measuring individual short-duration power events.

A direct supply-current experiment could theoretically synchronize:

- supply current;
- WUP;
- debug output;
- WLAN state;
- recovery events;
- motor movement.

This could distinguish:

```text
normal idle
    ↓
low current
```

from:

```text
recovery
    ↓
temporary current increase
```

and potentially:

```text
sleep-resource failure
    ↓
persistent elevated idle current
```

No such laboratory-grade current measurement is currently part of the active
test plan.

The present investigation therefore continues using long-term device telemetry
and runtime behavior.

---

# 37. Data Interpretation Rules

The following rules apply to battery reports.

## Do

- use direct TRV status as the primary battery source;
- record battery percentage and voltage;
- retain uptime;
- record firmware and patch configuration;
- record RSSI;
- retain recovery statistics where available;
- retain mDNS test configuration where relevant;
- include motor workload where possible;
- document firmware changes;
- document device relocation;
- document battery recharge events;
- split reports at firmware-transition boundaries;
- compare long-term trends;
- retain raw data for later re-analysis.

## Do not

- rank firmware solely by battery percentage loss;
- rank firmware solely by short-term voltage loss;
- assume equal battery capacity across devices;
- treat RSSI as proof of AP association;
- treat desired beacon skip as proof of actual WF200 behavior;
- interpret a recovery counter as direct energy consumption;
- assume Patch A fixes all battery drain;
- assume Patch B fixes all battery drain;
- assume A+B improves battery life before long-term evidence exists;
- classify 2.1.3 as known-good without evidence;
- interpret a mixed-firmware report as one continuous firmware measurement.

---

# 38. Current User-Level Interpretation

From the perspective of a normal TRV user, the current evidence can be
summarized as follows.

## Patch A

```text
Functional effect:
confirmed

Beacon-recovery suppression:
confirmed under tested conditions

Battery-life improvement:
not yet proven
```

## Patch B

```text
Functional effect:
confirmed

Periodic mDNS suppression:
confirmed during monitored test window

Beacon-recovery improvement:
no

Battery-life improvement:
not yet proven
```

## Combined A+B

```text
Both targeted mechanisms suppressed:
confirmed during monitored runtime

Normal device operation:
confirmed during monitored runtime

Initial battery behavior:
encouraging

Long-term battery improvement:
not yet proven
```

## Overall battery-drain status

```text
Solved:
not established
```

The current patches remove two confirmed recurring firmware workloads.

Whether those workloads explain enough of the real-world battery drain to
produce a substantial endurance improvement remains the central long-term test
question.

---

# 39. Current Research Priorities

The immediate priorities are:

1. preserve the completed mechanism-isolation dataset;
2. document the current Patch-A, Patch-B and combined A+B results;
3. extend battery logging with motor workload where technically reliable;
4. standardize the next patched test group on A+B;
5. retain one unmodified stock 2.2.4 control;
6. fully charge participating batteries before the new comparison;
7. continue logging over at least several days;
8. monitor voltage as well as percentage;
9. retain uptime and reboot information;
10. correlate motor workload with battery decline;
11. avoid premature cross-device energy conclusions;
12. re-evaluate the battery-drain hypothesis after the new long-term dataset is
    available.

---

# 40. Related Documents

Reverse engineering:

- [`Firmware Comparison`](../reverse-engineering/firmware-comparison.md)
- [`Power Management and Sleep`](../reverse-engineering/power-management-and-sleep.md)
- [`Beacon RX Counter`](../reverse-engineering/beacon-rx-counter.md)
- [`Real Beacon Skip`](../reverse-engineering/real-beacon-skip.md)
- [`Recovery Mechanism`](../reverse-engineering/recovery-mechanism.md)
- [`AP Selection and Roaming`](../reverse-engineering/ap-selection-and-roaming.md)
- [`Periodic mDNS Restart`](../reverse-engineering/mdns-periodic-restart.md)

Patch documentation:

- [`Experimental Beacon-Recovery Patch`](../patch/README.md)

Runtime testing:

- [`mDNS Runtime Comparison`](mdns-runtime-comparison.md)

---

# 41. Current Status — 2026-10-13

The first major mechanism-isolation phase is now sufficiently developed to
support the following conclusions:

```text
Stock 2.2.4:
beacon recovery present
periodic mDNS restart present

Patch A:
targeted beacon recovery suppressed

Patch B:
targeted periodic mDNS restart suppressed
beacon recovery remains

Patch A+B:
both targeted recurring mechanisms suppressed
during monitored runtime
```

The current battery dataset also establishes an important limitation:

> Suppressing the known beacon-recovery mechanism does not automatically
> eliminate all observed battery decline.

At least one Patch-A device continued to show substantial battery decline while
its recovery counter remained at zero.

The combined A+B device has shown encouraging initial battery behavior, but the
post-installation observation period remains too short to establish improved
battery endurance.

The project therefore currently distinguishes between two separate statements:

```text
The patches work against their targeted firmware mechanisms.
```

This is supported by runtime evidence.

and:

```text
The patches fix the Shelly TRV Gen1 battery-drain problem.
```

This is **not yet established**.

The next long-term test phase is intended to determine whether multiple A+B
patched devices show a reproducible battery-behavior improvement relative to a
stock 2.2.4 control.