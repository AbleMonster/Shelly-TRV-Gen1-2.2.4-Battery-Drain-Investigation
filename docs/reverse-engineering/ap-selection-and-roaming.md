# Access Point Selection and Roaming Analysis

## Overview

This document describes the access-point selection and roaming behavior identified in the Shelly TRV Gen1 firmware and its possible relevance to WLAN power consumption and the battery-drain investigation.

The investigation originally started from a simple observation:

> A TRV can sometimes remain connected to an access point with noticeably worse RSSI even though another access point with the same SSID is available.

This raised several questions:

- Does the Shelly host select the strongest AP?
- Does the WF200 select the AP?
- Does the TRV roam after association?
- Can a weak but still functional AP remain associated?
- Can AP selection influence WLAN power consumption?
- Can poor AP selection explain Beacon Recovery?
- Could AP behavior contribute to a fresh Recovery trigger?

Static analysis of firmware:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

shows that the Shelly host does not explicitly select one particular BSSID during the normal connection request.

Instead, the host uses approximately:

```text
SSID            = configured SSID
BSSID           = FF:FF:FF:FF:FF:FF
Channel         = 0
prevent_roaming = 1
```

The concrete AP selection is therefore delegated to the WLAN/WF200 subsystem.

After association:

```text
prevent_roaming = 1
```

prevents autonomous WLAN-firmware roaming.

This creates an important distinction:

```text
initial AP selection
        |
        v
handled below the Shelly host
        |
        v
association established
        |
        v
prevent_roaming = 1
        |
        v
existing AP may remain associated
while the connection still works
```

AP behavior can influence normal WLAN efficiency.

However:

> AP selection is not required to explain the demonstrated host-side Beacon Recovery defects in firmware 2.2.4.

Runtime observations also show Beacon Recovery with very good RSSI.

Weak signal is therefore not a necessary condition for Recovery.

---

# 1. WLAN Scan and Connection Establishment

Before connection, the WLAN subsystem provides scan information containing fields such as:

```text
SSID
BSSID
Channel
RSSI
```

The host therefore has visibility into multiple APs advertising the configured SSID.

However, no host-side control flow was identified that:

1. collects every matching BSSID,
2. ranks the candidates by RSSI,
3. selects the strongest AP,
4. copies that BSSID into the connection request.

The examined connection path instead supplies approximately:

```text
SSID            = configured SSID
BSSID           = FF:FF:FF:FF:FF:FF
Channel         = 0
Security        = configured security mode
prevent_roaming = 1
Password        = configured password
```

The important fields are:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

The Shelly host therefore does not request one particular AP or one particular channel.

The responsibility boundary is:

```text
Shelly host
    |
    | configured SSID
    | wildcard BSSID
    | channel 0
    v
WLAN / WF200 subsystem
    |
    v
concrete AP selection
```

The exact ranking algorithm used inside the protected WF200 firmware has not been reconstructed.

It is therefore not justified to claim:

```text
WF200 always selects strongest AP
```

Possible internal selection factors could include:

- RSSI
- scan-result order
- previous connection state
- cached information
- retry history
- internal WLAN heuristics

These remain unresolved implementation details.

---

# 2. Initial AP Selection

The strongest statement supported by the host firmware is:

> The Shelly host submits a wildcard connection request and delegates concrete AP selection to the WLAN subsystem.

This is different from saying:

```text
Shelly selects strongest AP
```

and also different from saying:

```text
WF200 always selects strongest AP
```

Neither behavior has been established.

The host supplies network credentials and connection parameters but does not constrain the connection to one specific scanned BSSID.

---

# 3. `prevent_roaming`

During connection establishment the host sets:

```text
prevent_roaming = 1
```

This disables autonomous WLAN-firmware roaming after association.

Changing this to:

```text
prevent_roaming = 0
```

would permit the WLAN subsystem to use whatever roaming implementation exists internally.

It would not tell us:

- what RSSI threshold is used
- what hysteresis is used
- how candidates are ranked
- when scans occur
- whether a previous AP is preferred
- whether the strongest AP is always selected

Therefore:

```text
prevent_roaming = 0
```

does not mean:

```text
always connect to strongest AP
```

It only permits the internal WLAN roaming logic to operate.

---

# 4. No Host-Side RSSI Roaming Was Identified

No host-side mechanism was identified that continuously performs:

```text
connected
   |
   v
RSSI becomes weak
   |
   v
scan for stronger AP
   |
   v
select stronger BSSID
   |
   v
reassociate
```

RSSI is used by the host for power-management policy, but no equivalent RSSI-driven AP migration path was found.

Therefore:

```text
host does not appear to perform
its own strongest-AP roaming
```

and:

```text
prevent_roaming = 1
```

disables autonomous firmware roaming.

A weak but still functional AP can therefore potentially remain associated.

---

# 5. Weak-but-Functional AP Retention

Consider:

```text
AP A
RSSI = -80 dBm
currently associated

AP B
RSSI = -55 dBm
same SSID
also available
```

If AP A remains functional, the identified host behavior does not require the TRV to move to AP B.

The host does not perform an identified strongest-BSSID reassociation, while autonomous roaming is disabled.

The TRV may therefore remain connected to the weaker AP until another event changes the connection state.

This is a plausible consequence of the identified policy.

It does not prove that a particular physical TRV has actually done so.

Direct BSSID observation is required.

---

# 6. Behavior After Connection Loss

An actual WLAN connection loss is different from roaming.

After connection loss, the host returns to its normal connection procedure.

The next request again uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

Conceptually:

```text
existing association
        |
        v
connection lost
        |
        v
scan / connection procedure
        |
        v
wildcard CONNECT
        |
        v
WLAN subsystem selects AP
```

The reconnect therefore gives the WLAN subsystem another opportunity to choose an AP.

That AP may be:

```text
the previous AP
```

or:

```text
another compatible AP
```

No host-side path was identified that explicitly constrains the reconnect to the previous BSSID or channel.

---

# 7. Associated BSSID Is Available to the Host

Although the host does not specify one BSSID in the connection request, the successful WLAN connection indication contains the resulting association information.

The relevant `CONNECT_IND` includes:

```text
BSSID
Channel
```

Conceptually:

```text
WLAN subsystem selects AP
        |
        v
association succeeds
        |
        v
CONNECT_IND
        |
        +---- BSSID
        |
        +---- Channel
        |
        v
Shelly host
```

This provides a useful diagnostic observation point.

The normal `/status` response does not expose the associated BSSID.

A diagnostic build could therefore record the BSSID and channel from the connection indication without changing AP-selection behavior.

---

# 8. RSSI Handling

The RSSI used by the host originates from WLAN signal-strength information.

The identified conversion is approximately:

```text
RSSI = ((uint8_t)RCPI >> 1) - 110
```

The RSSI shown through `/status` should not automatically be interpreted as a fresh instantaneous RF measurement.

It represents host-side WLAN state.

Therefore:

```text
scan RSSI
```

and:

```text
/status RSSI
```

do not necessarily represent the same measurement at the same instant.

A sudden RSSI change also does not prove that the TRV changed AP.

For AP-selection experiments, the associated BSSID is the stronger diagnostic signal.

---

# 9. RSSI and `desired_beacon_skip`

RSSI controls the normal requested beacon-skip policy.

The reconstructed thresholds are:

```text
RSSI >= -69 dBm
    desired_beacon_skip = 20

RSSI -70 ... -79 dBm
    desired_beacon_skip = 15

RSSI < -79 dBm
    desired_beacon_skip = 10
```

AP selection can therefore indirectly influence normal WLAN PM behavior.

Conceptually:

```text
AP selection / retention
        |
        v
RF conditions
        |
        v
RSSI
        |
        v
desired_beacon_skip
        |
        v
requested WLAN PM behavior
```

A device associated with a weaker AP can therefore request a lower skip value.

The RSSI thresholds do not directly trigger an AP change.

---

# 10. Nominal Beacon Listening

The requested values correspond approximately to:

```text
desired_beacon_skip = 20
-> approximately every 21st beacon

desired_beacon_skip = 15
-> approximately every 16th beacon

desired_beacon_skip = 10
-> approximately every 11th beacon
```

Nominal listening-opportunity ratios are therefore approximately:

```text
21 / 16 ~= 1.31
```

and:

```text
21 / 11 ~= 1.91
```

These ratios describe nominal radio-side listening opportunities.

They do not mean complete-device current increases by the same factor.

They also do not imply that the host MCU wakes for every individual beacon opportunity.

---

# 11. AP Selection and Normal WLAN Energy Use

A weaker or less suitable AP can potentially produce:

- lower `desired_beacon_skip`
- more radio listening opportunities
- additional retransmissions
- less stable communication
- reconnects
- additional scans
- different beacon-reception behavior

The supported relationship is:

```text
AP / RF environment
        |
        +---- RSSI
        |       |
        |       v
        |   desired_beacon_skip
        |
        +---- retransmissions
        |
        +---- connection stability
        |
        +---- beacon reception
```

These mechanisms can affect energy consumption.

Their quantitative contribution to historical TRV battery drain has not been measured electrically.

---

# 12. AP Selection and Beacon Recovery

AP selection and Beacon Recovery must be treated as separate mechanisms.

There is no identified control flow equivalent to:

```text
poor AP
   |
   v
poor RSSI
   |
   v
Beacon Recovery
```

The normal RSSI path is:

```text
RSSI
 |
 v
desired_beacon_skip
 |
 v
requested WLAN PM policy
```

The Recovery path is:

```text
WF200 beacon statistics
        |
        v
received-beacon counter
        |
        v
host estimator
        |
        v
real_beacon_skip
        |
        v
Recovery predicate
```

RSSI itself is not the Recovery predicate.

The firmware also does not simply perform:

```text
if real_beacon_skip != desired_beacon_skip:
    recover
```

The calculated or cached `real_beacon_skip` is evaluated by a different condition.

---

# 13. Good RSSI Does Not Prevent Recovery

Runtime observations show low calculated `real_beacon_skip` and Beacon Recovery while signal quality is good.

Therefore the simple model:

```text
weak RSSI
   |
   v
low real_beacon_skip
   |
   v
Recovery
```

does not hold generally.

For example:

```text
good RSSI
```

can produce:

```text
desired_beacon_skip = 20
```

while the host separately calculates:

```text
real_beacon_skip = 1
```

and satisfies the Recovery condition.

This weakens the hypothesis that recurring Recovery is primarily caused by association with a weak AP.

AP behavior can still influence beacon reception and the environment of a fresh estimator calculation.

---

# 14. Stock 2.2.4 Stale-Evidence Recurrence

Firmware 2.2.4 contains a demonstrated host-side validity defect in the Beacon Recovery evidence lifecycle.

After a qualifying Recovery, stock firmware can clear the beacon-counter baseline while retaining the previous qualifying `real_beacon_skip`.

A later baseline-only sample can then evaluate that historical value again.

Conceptually:

```text
qualifying Recovery
        |
        v
previous_received = 0
real_beacon_skip retained
        |
        v
next measurement
        |
        v
new baseline installed
no fresh ratio calculated
        |
        v
historical real_beacon_skip evaluated
        |
        v
Recovery can recur
```

This can create long-lived approximately minute-scale recurrence.

The important qualification is:

> C2 is metastable stale-evidence recurrence, not a mathematical guarantee that Recovery must continue forever until reboot.

The firmware can leave the recurrence without reboot.

---

# 15. First Trigger vs. Later Recurrence

Two different questions must be separated:

```text
Why did a fresh qualifying Recovery occur?
```

and:

```text
Why did Recovery continue recurring afterward?
```

The demonstrated C2 stale-evidence mechanism explains later recurrence.

It does not explain the first fresh qualifying measurement.

Possible contributors to the first event include:

- beacon-reception pattern
- invalid or aged measurement windows
- PM transitions
- connection-state transitions
- WF200 internal behavior
- AP-specific behavior
- RF conditions
- another unidentified event

Good-RSSI observations show that weak signal is not required for the first qualifying event either.

---

# 16. C-C Changes the Interpretation

C-C corrects the known host-side validity defects without disabling legitimate Recovery.

Its behavior includes:

- correct unsigned interpretation
- invalid-window rejection
- stale Recovery evidence not reused as fresh control evidence
- baseline-only samples do not trigger Recovery from historical values
- fresh valid measurements can still trigger Recovery

C-C intentionally does not modify:

```text
AP selection
prevent_roaming
RSSI thresholds
desired_beacon_skip
mDNS behavior
```

This makes it useful for isolating Recovery correctness from AP-selection policy.

---

# 17. C-C Runtime Behavior

Hardware testing demonstrated that C-C removes the demonstrated stale-evidence recurrence while retaining fresh Recovery.

A representative sequence is:

```text
fresh qualifying measurement
        |
        v
Recovery
        |
        v
baseline reset
        |
        v
next measurement establishes baseline
        |
        v
no fresh Recovery evidence yet
        |
        v
later comparable measurement
        |
        v
possible fresh Recovery
```

Under historical measurement cadence, some experiments showed approximately:

```text
27–30 fresh Recoveries/hour
```

These values are specific historical measurements.

They are not a universal C-C property or fixed C-C rate.

---

# 18. Historical Recovery Occupancy

The historical D3 observation provided approximately:

```text
3835 Recoveries
63.93 hours
~59.99 Recoveries/hour
```

At approximately five serviced seconds per Recovery:

```text
~60 × ~5 s
= ~300 s/hour
= ~5 min/hour
≈ 8.33% wall-clock occupancy
```

Some historical C-C periods showed approximately:

```text
27–30 Recoveries/hour
```

which corresponds to roughly:

```text
~2.25–2.5 min/hour
```

of explicit Recovery interval.

These are wall-clock figures.

They are not electrical energy percentages.

No direct current measurement was performed for these comparisons.

---

# 19. Recovery Frequency Is Not the Current Optimization Target

Earlier project stages considered further Recovery-rate limiting.

That is not the current experimental priority.

The current corrected strategy is:

```text
reject stale/invalid Recovery evidence
+
retain fresh valid Recovery
```

The reason is that two effects must remain conceptually separated.

Known:

```text
more Recoveries
        |
        v
more explicit Recovery activity
```

Hypothetical:

```text
unknown radio-side high-power condition
        |
        v
Recovery happens to clear it
```

The second mechanism has not been demonstrated.

Therefore the project is not currently changing Recovery cadence while the B2.1_OBS long-term experiment is running.

---

# 20. D3 Observation

Firmware 2.2.4 exposes the WF200 `PS_MODE_ERROR` indication through the D3 path.

Known reason categories include approximately:

```text
0 -> PS-Poll timeout
1 -> U-APSD timeout
2 -> buffered unicast persists across beacons
3 -> unstable beacon timing / compensation
```

These are more direct radio PM error indications than the host-derived `real_beacon_skip`.

A dedicated D3 observer was therefore used to compare the two mechanisms.

---

# 21. D3 Runtime Result

The historical `.11` D3 observer retained stock Recovery behavior.

After approximately:

```text
230144 s
= 63.93 h
```

it recorded:

```text
beacon_err_counter  = 3835
D3_total            = 0
reboot_counter      = 1
reconnect_counter   = 1
desired_beacon_skip = 20
real_beacon_skip    = 1
```

Recovery rate:

```text
3835 / 230144 × 3600
≈ 59.99/hour
```

Thus:

```text
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

The known D3 error channel is therefore not required for the recurring host Recovery behavior observed in that experiment.

This does not prove the radio had no other internal PM condition.

---

# 22. Consequence for AP Interpretation

AP behavior can matter to WF200 PM.

For example, D3 reason categories themselves show that:

- beacon timing
- delivery behavior
- buffered traffic

can influence radio PM behavior.

However:

```text
AP / RF issue
        |
        v
D3 PS_MODE_ERROR
```

and:

```text
host real_beacon_skip
        |
        v
Beacon Recovery
```

must not be treated as the same mechanism.

The D3 experiment strongly reinforces that distinction.

---

# 23. WF200 3.18.0

The official Silicon Labs WF200 3.18.0 firmware contains a relevant power-save correction involving a condition that could prevent the radio from sleeping after a PM-mode change.

Stock Shelly 2.2.4 uses:

```text
FMAC 3.7.0
WF200 3.16.1
```

The project successfully integrated:

```text
FMAC 3.7.0
WF200 3.18.0
```

and demonstrated on physical TRV hardware:

```text
WF200 initialization
scan
association
DHCP
power-save configuration
Cloud communication
normal thermostat operation
```

This demonstrates practical interoperability under the exercised conditions.

It does not establish that 3.18.0 solves historical battery drain.

---

# 24. WF200 3.18.0 Does Not Eliminate Fresh Recovery

Historical corrected-host experiments with WF200 3.18.0 still produced fresh Beacon Recovery.

That does not prove the radio firmware correction failed.

The mechanisms are different:

```text
WF200 3.18.0
    |
    v
radio-internal PM behavior
```

versus:

```text
Shelly host
    |
    v
beacon statistics
    |
    v
real_beacon_skip
    |
    v
Recovery heuristic
```

Fresh host Recovery can therefore remain even if radio-internal PM behavior changes.

---

# 25. Historical A1 + C-C + WF200 3.18.0 Platform

An important historical integrated platform combined:

```text
A1
+
C-C
+
WF200 3.18.0
```

primarily on TRV `.234`.

This build successfully completed hardware bring-up and normal operation.

Historical runtime included approximately:

```text
~27–28 fresh Recoveries/hour
```

during some intervals.

These data remain valid historical evidence.

They must not be relabeled as:

```text
A1R
B2.1
B2.1_OBS
```

results.

---

# 26. Historical `.234` AP/Steering Experiment

During the historical `.234` integrated experiment, FRITZ! Mesh/Band Steering was disabled.

Fresh Beacon Recovery continued.

Therefore the tested Mesh/Band-Steering behavior was not required for those fresh Recovery events.

This does not rule out:

- all AP-specific effects
- channel effects
- RF interference
- beacon timing
- hidden WLAN heuristics

It only excludes the tested steering behavior as a required condition.

---

# 27. The Estimator Is Not Permanently Stuck at `1`

Historical samples frequently showed:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

but later examples also produced values such as:

```text
desired_beacon_skip = 15
real_beacon_skip    = 13
```

Therefore the estimator is not simply stuck at `1`.

It responds to changing received-beacon statistics.

Those changes can be influenced by the RF/AP environment without directly measuring physical WF200 sleep.

---

# 28. Current Corrected Baseline

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

None of these corrections intentionally changes AP-selection policy.

The connection model remains:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```

---

# 29. Current Diagnostic Hardware Build

The active long-term diagnostic build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

The observer records already-existing PM/statistics activity.

It adds no:

```text
new timer
new task
new queue
automatic network traffic
additional WF200 request
PM policy change
```

It also does not modify:

```text
AP selection
BSSID policy
Channel policy
prevent_roaming
```

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

or:

```text
6 × B2.1_OBS
1 × stock 2.2.4
```

This supersedes the historical `.234` A1 canary as the current experimental platform.

---

# 31. Early Current Observation

During the initial B2.1_OBS observation period, the corrected devices showed:

```text
beacon_err = 0
```

during the first observed interval.

The stock `.97` control retained thousands of accumulated Beacon Recovery events and showed periods of approximately minute-scale recurrence.

These observations are preliminary.

They do not establish long-term battery behavior.

---

# 32. Current Role of AP Selection

The original AP hypothesis was broader:

```text
poor AP selection
        |
        v
weak RSSI
        |
        v
abnormal WLAN behavior
        |
        v
Beacon Recovery
        |
        v
battery drain
```

Current evidence shows that model is too simple.

A better model is:

```text
                  AP selection / retention
                            |
                            v
                      RF environment
                            |
                +-----------+-----------+
                |                       |
                v                       v
               RSSI              beacon reception
                |                       |
                v                       v
     desired_beacon_skip         host estimator
                |                       |
                v                       v
      normal PM policy          fresh Recovery
```

Importantly:

```text
good RSSI
   |
   +----> desired_beacon_skip may be 20
   |
   +----> real_beacon_skip may still be low
   |
   +----> fresh Recovery may still occur
```

Separately, stock C2 stale-evidence recurrence can continue for extended periods after a qualifying event without continued poor AP conditions.

---

# 33. AP Selection Is Still Relevant

AP behavior remains relevant to:

- normal WLAN efficiency
- `desired_beacon_skip`
- retransmissions
- connection stability
- reconnect frequency
- scans
- beacon reception
- environment of fresh estimator measurements
- potentially the first qualifying Recovery event

But the evidence establishes an important boundary:

> Poor RSSI is not required for low `real_beacon_skip` or Beacon Recovery.

AP selection should therefore not be treated as the primary explanation for the known Recovery defect.

---

# 34. Should Roaming Be Enabled?

A controlled future experiment could change:

```text
prevent_roaming = 1
```

to:

```text
prevent_roaming = 0
```

and observe whether the TRV migrates between APs.

Potential questions include:

- Does the device move to stronger APs?
- At what RSSI?
- Does it spend less time at skip 10 or 15?
- Do retransmissions change?
- Does fresh Recovery frequency change?
- Does battery behavior change?
- Does roaming introduce additional scans or instability?

However, enabling roaming introduces a new variable.

For the current main battery experiment:

```text
prevent_roaming
```

should remain unchanged.

---

# 35. BSSID Instrumentation

If AP behavior becomes a priority, observational instrumentation should precede policy changes.

The successful `CONNECT_IND` already provides:

```text
BSSID
Channel
```

A diagnostic build could record:

```text
timestamp
BSSID
channel
RSSI
```

at each successful association.

This would answer directly:

```text
Which AP did the TRV actually associate with?
```

without changing AP-selection behavior.

---

# 36. Suggested Future AP Experiment

AP-specific testing should be separated from the current battery experiment.

A clean sequence would be:

## Phase 1 — Record Associated AP

Record:

```text
timestamp
BSSID
channel
RSSI
```

while keeping:

```text
prevent_roaming = 1
```

unchanged.

## Phase 2 — Weak-but-Functional AP

Create:

```text
AP A
weak but functional
currently associated

AP B
same SSID
substantially stronger
```

Observe:

```text
BSSID
RSSI
desired_beacon_skip
real_beacon_skip
connection state
Recovery events
```

## Phase 3 — Forced Connection Loss

Make AP A unavailable and observe:

```text
old BSSID
   |
   v
connection loss
   |
   v
wildcard reconnect
   |
   v
new BSSID
```

## Phase 4 — Optional Roaming Experiment

Only after baseline behavior is understood, compare:

```text
prevent_roaming = 1
```

with:

```text
prevent_roaming = 0
```

while measuring:

```text
BSSID
channel
RSSI
desired_beacon_skip
real_beacon_skip
Recovery rate
reconnects
battery voltage
```

This should remain a separate experiment.

---

# 37. Recovery Modification Is Not the Current Next Step

Earlier project versions proposed:

```text
current corrected build
        |
        v
long-term baseline
        |
        v
Recovery rate limit / disable
```

That is no longer the immediate experimental plan.

The current priority is:

```text
B2.1_OBS long-term observation
```

If B2.1_OBS develops drain:

```text
capture first fault
        |
        v
correlate PM52/cmd66 telemetry
        |
        v
resume targeted RE
```

If B2.1_OBS remains stable:

```text
remove observer
        |
        v
requalify observer-free build
        |
        v
hardware regression
```

A Recovery-modification experiment remains a possible later research branch only if runtime evidence justifies it.

---

# 38. B2.2

A later observer-free candidate is:

```text
B2.2
```

It contains nine selected qualified corrections:

```text
1. A1R including A1 lifecycle correction
2. C-C
3. B2 serialization
4. minimal MQTT PUBLISH guard
5. official WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

Its status is:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

B2.2 does not alter AP-selection policy.

It has not been hardware-qualified.

It is intentionally not being flashed during the active B2.1_OBS experiment.

---

# 39. Version Comparison

The examined host firmware versions are:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

The relevant connection behavior remains substantially consistent:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```

No host-side strongest-AP selection algorithm was identified.

The WLAN stack changed across releases.

Known combinations include:

```text
2.1.0 / 2.1.3
FMAC 3.3.2
WF200 3.12.2

2.1.8
FMAC 3.4.1
WF200 3.14.0

2.2.4
FMAC 3.7.0
WF200 3.16.1
```

The current corrected B2.1 family uses:

```text
Shelly host 2.2.4
FMAC 3.7.0
WF200 3.18.0
```

No specific AP-ranking change between these radio-firmware versions has been established.

---

# 40. Current Model

The current AP-selection model is:

```text
                        scan
                         |
                         v
                 matching SSID(s)
                         |
                         v
                 host CONNECT request
                         |
                BSSID = wildcard
                Channel = 0
                prevent_roaming = 1
                         |
                         v
                    WLAN / WF200
                         |
                         v
                  selects actual AP
                         |
                         v
                    association
                         |
                         v
                    CONNECT_IND
                  BSSID + channel
                         |
                         v
                  connected state
                         |
             +-----------+-----------+
             |                       |
             v                       v
        RSSI changes           connection loss
             |                       |
             v                       v
 desired_beacon_skip                 scan
             |                       |
             v                       v
 normal requested              wildcard CONNECT
 WLAN power saving                    |
                                      v
                               AP selected again
```

The Beacon Recovery path is separate:

```text
WF200 beacon statistics
        |
        v
received-beacon counter
        |
        v
host estimator
        |
        v
real_beacon_skip
        |
        v
fresh Recovery predicate
        |
        v
temporary Recovery state
```

Stock 2.2.4 additionally contains C2 stale-evidence recurrence.

C-C removes that invalid recurrence while retaining fresh Recovery.

---

# 41. Current Experimental Architecture

The current architecture relevant to this document is:

```text
                    stock 2.2.4 control
                           |
                           | WF200 3.16.1
                           |
                           v
                         .97


B2.1_OBS corrected population
        |
        +-- A1R
        +-- C-C
        +-- B2 serialization
        +-- MQTT guard
        +-- WF200 3.18.0
        +-- PM52->cmd66 observer
        |
        v
6 physical TRVs
```

AP-selection policy remains native:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```

across the corrected population.

This preserves AP policy as a controlled variable.

---

# 42. Current Research Decision

The current decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

Therefore the project is not currently:

- enabling roaming
- adding BSSID instrumentation
- changing AP topology deliberately
- changing Recovery cadence
- disabling Recovery
- flashing B2.2
- changing WF200 firmware

The value of the current experiment depends on keeping these variables stable.

---

# 43. Remaining AP Questions

Important unresolved questions include:

1. What exact criteria does the WF200 use during wildcard AP selection?

2. Does it prefer a previously associated AP?

3. What roaming threshold and hysteresis are used when `prevent_roaming = 0`?

4. How often do real TRVs remain on a weak AP while a stronger AP is available?

5. Do large RSSI changes correspond to BSSID changes?

6. How much additional radio energy is consumed at skip 10, 15 and 20?

7. How much do retransmissions contribute under weak RF conditions?

8. How much energy is consumed by scans and reconnects?

9. Did WF200 versions 3.12.2, 3.14.0, 3.16.1 and 3.18.0 change AP selection behavior?

10. Do particular APs, channels or RF conditions correlate with fresh `real_beacon_skip = 1/2`?

11. What causes fresh low estimator values on devices with good RSSI?

12. Can AP behavior influence the first fresh Recovery independently of RSSI?

13. Why does Shelly use the beacon estimator as a Recovery condition instead of a direct WF200 PM-error signal?

14. Does fresh Recovery provide a measurable functional benefit when no D3 error is present?

15. Would autonomous roaming improve long-term energy behavior?

16. Would roaming instead increase scanning, reassociation or other WLAN work?

These questions remain open.

They are not the current active experiment.

---

# 44. Question for Shelly

The host AP behavior raises two useful questions for Shelly firmware developers.

First:

> Why is `prevent_roaming = 1` used on a battery-powered device that may remain installed for months or years in a multi-AP network?

Second:

> When `real_beacon_skip` reaches the Recovery threshold, what specific WF200 or protocol failure was this heuristic intended to detect?

The second question is particularly important because the project has observed:

```text
3835 host Beacon Recoveries
0 D3 PS_MODE_ERROR
```

and fresh Recovery can occur with good WLAN signal strength.

Understanding the intended failure condition would clarify whether fresh Recovery remains necessary and whether a more direct error signal could be used.

---

# 45. Current Conclusion

The Shelly TRV host does not explicitly select the strongest AP during normal connection establishment.

The examined host request uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

and delegates concrete AP selection to the WLAN/WF200 subsystem.

After association:

```text
prevent_roaming = 1
```

prevents autonomous WLAN-firmware roaming.

No separate host-side strongest-AP roaming mechanism was identified.

A weak but still functional AP can therefore potentially remain associated while a stronger compatible AP is available.

This can influence normal WLAN workload through:

```text
RSSI
desired_beacon_skip
retransmissions
beacon reception
connection stability
```

However, runtime observations demonstrate that:

> Weak RSSI is not required for Beacon Recovery.

RSSI and `real_beacon_skip` are derived from different information.

Stock firmware additionally contains a demonstrated metastable stale-evidence Recovery recurrence that does not require continued poor AP conditions.

C-C corrects that recurrence while retaining fresh Recovery.

The historical D3 observer further separates the mechanisms:

```text
~63.93 h
3835 Beacon Recoveries
0 D3 PS_MODE_ERROR
```

The historical A1+C-C+WF200 3.18.0 platform also demonstrated fresh Recovery at good signal strength and while FRITZ! Mesh/Band Steering was disabled.

That platform is now historical.

The active firmware experiment is:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

with the AP-selection policy intentionally unchanged.

The current priority is therefore not AP-policy modification.

It is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

If future evidence makes AP behavior a priority, the first useful AP-specific experiment should be observational BSSID/channel logging rather than immediately enabling roaming.

No claim is currently made that AP selection is the historical battery-drain root cause.

---

# Related Documents

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Power-management behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Beacon receive counter:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

`real_beacon_skip`:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

Periodic mDNS:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

B2.1_OBS qualification:

[`../qualification/b2.1-obs-qualification.md`](../qualification/b2.1-obs-qualification.md)

B2.2 offline qualification:

[`../qualification/b2.2-offline-release-candidate.md`](../qualification/b2.2-offline-release-candidate.md)

Patch documentation:

[`../patch/README.md`](../patch/README.md)

---

# Research Method

This analysis combines:

- static ARM Thumb reverse engineering
- cross-version firmware comparison
- runtime WLAN observations
- Beacon Recovery telemetry
- D3 observation
- WF200 firmware integration
- physical hardware testing
- corrected-firmware long-term observation

The analysis deliberately separates:

```text
what the host requests
what the host can observe
what the WLAN firmware may do internally
what runtime testing demonstrates
what can actually be concluded about physical power state
```

Historical experiments retain their original build identities.

A1-based results are not relabeled as A1R or B2.1 results.

Current test strategy is kept separate from possible later AP-specific experiments.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The findings describe reverse-engineered and observed behavior of the investigated firmware versions.

No claim is made that the undocumented internal AP-selection algorithm of the protected WF200 firmware has been fully reconstructed.