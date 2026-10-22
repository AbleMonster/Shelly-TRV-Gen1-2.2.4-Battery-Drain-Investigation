# Access Point Selection and Roaming Analysis

## Overview

This document describes the access-point selection and roaming behavior identified in the Shelly TRV Gen1 firmware.

The investigation originally started from a simple observation:

> A TRV can sometimes remain connected to an access point with noticeably worse RSSI even though another access point with the same SSID is available.

This raised several questions:

- Does the Shelly host select the strongest AP?
- Does the WF200 select the AP?
- Does the TRV roam after association?
- Can a weak but still functional AP remain associated?
- Can AP selection influence WLAN power consumption?
- Can poor AP selection explain the recurring Beacon Recovery behavior?
- Could AP behavior contribute to the first fresh Recovery trigger?

Static analysis of firmware 2.1.0, 2.1.3, 2.1.8 and 2.2.4 shows that the Shelly host does not explicitly select one particular BSSID during the normal connection request.

Instead, the host uses a wildcard BSSID and channel 0 and delegates the concrete AP selection to the WLAN/WF200 subsystem.

At the same time, the host sets:

```text
prevent_roaming = 1
```

so autonomous roaming after association is disabled.

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

AP behavior can therefore influence normal WLAN efficiency, but it is not required to explain the host-side Beacon Recovery defects identified in firmware 2.2.4.

Runtime observations also show that Beacon Recovery can occur while WLAN signal strength is very good. Weak RSSI is therefore not a necessary condition for the Recovery mechanism to trigger.


---

# WLAN Scan and Connection Establishment

Before connection, the WLAN subsystem provides scan information containing fields such as:

```text
SSID
BSSID
Channel
RSSI
```

The host therefore has access to information about multiple APs advertising the configured SSID.

However, no host-side control flow was identified that:

1. collects all matching BSSIDs,
2. ranks them by RSSI,
3. selects the strongest one,
4. and copies that BSSID into the connection request.

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

The Shelly host therefore does not request one particular access point or one particular WLAN channel.

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

The exact ranking algorithm used inside the WF200 firmware has not been reconstructed.

It is therefore not justified to claim that the WF200 always chooses the strongest AP.

Possible internal selection factors could include RSSI, scan-result ordering, previous connection state, cached information, retry history or other WLAN-firmware heuristics, but these remain implementation details of the protected WLAN subsystem.


---

# Initial AP Selection

The strongest statement supported by the host firmware is:

> The Shelly host submits a wildcard connection request and delegates the concrete AP selection to the WLAN subsystem.

This is different from saying:

```text
Shelly selects strongest AP
```

and also different from saying:

```text
WF200 always selects strongest AP
```

Neither behavior has been established.

The host provides the network credentials and connection parameters but does not constrain the connection to a specific scanned BSSID.


---

# `prevent_roaming`

During connection establishment the host sets:

```text
prevent_roaming = 1
```

This prevents autonomous WLAN-firmware roaming after association.

Changing this to:

```text
prevent_roaming = 0
```

would permit the WLAN subsystem to perform autonomous roaming.

It would not tell us:

- what RSSI threshold is used,
- what hysteresis is used,
- how candidates are ranked,
- when scans occur,
- whether the previous AP is preferred,
- or whether the strongest AP is always selected.

In particular:

```text
prevent_roaming = 0
```

does **not** mean:

```text
always connect to strongest AP
```

It only allows the WLAN firmware to use whatever roaming implementation exists internally.


---

# No Host-Side RSSI Roaming Was Identified

No separate host-side mechanism was found that continuously performs something equivalent to:

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

RSSI is used by the host for power-management decisions, but no equivalent RSSI-driven AP migration path was identified.

This means that after association there are two relevant facts:

```text
host does not appear to perform its own strongest-AP roaming

and

prevent_roaming = 1 disables autonomous WLAN-firmware roaming
```

A weak but still functional AP can therefore potentially remain associated.


---

# Weak-but-Functional AP Retention

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

If AP A remains functional, the identified firmware behavior does not require the TRV to move to AP B.

The host does not appear to perform a strongest-BSSID reassociation, while autonomous WLAN roaming is disabled.

The TRV may therefore remain connected to the weaker AP until some other event changes the connection state.

This is a plausible consequence of the identified policy.

It does not prove that a particular TRV has actually done this.

Direct BSSID observation is required for that.


---

# Behavior After Connection Loss

An actual connection loss is different from roaming.

After losing the WLAN connection, the host returns to its normal connection procedure.

The next connection again uses:

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
WF200 selects compatible AP
```

The reconnect therefore gives the WLAN subsystem another opportunity to select an AP.

That AP may be the previous AP or a different compatible AP.

No host-side path was identified that explicitly constrains the reconnect to the previous BSSID or previous channel.


---

# Associated BSSID Is Available to the Host

Although the host does not select one particular BSSID in the connection request, the successful WLAN connection indication contains the actual association information.

The relevant `CONNECT_IND` contains:

```text
BSSID
Channel
```

Conceptually:

```text
WF200 selects AP
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

This is useful because it provides a clean diagnostic observation point.

The normal `/status` response does not expose the associated BSSID.

A diagnostic firmware build could therefore record the BSSID and channel from the successful connection indication without changing the actual AP-selection behavior.


---

# RSSI Handling

The RSSI used by the host originates from WLAN signal-strength information.

The identified conversion is approximately:

```text
RSSI = ((uint8_t)RCPI >> 1) - 110
```

The RSSI shown through `/status` should not automatically be interpreted as a fresh instantaneous radio measurement.

It represents host-side WLAN state.

Therefore:

```text
scan RSSI
```

and:

```text
/status RSSI
```

do not necessarily represent the same measurement at the same point in time.

A sudden RSSI change also does not by itself prove that the TRV changed AP.

For AP-selection experiments, the actual BSSID is the better diagnostic value.


---

# RSSI and `desired_beacon_skip`

RSSI directly controls the normal requested beacon-skip policy.

The identified thresholds are:

```text
RSSI >= -69 dBm
desired_beacon_skip = 20

RSSI -70 ... -79 dBm
desired_beacon_skip = 15

RSSI < -79 dBm
desired_beacon_skip = 10
```

This relationship is important because AP selection can indirectly affect normal WLAN power behavior.

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
requested WLAN power-save behavior
```

A TRV associated with a weaker AP can therefore request a lower beacon-skip value.

However, the RSSI thresholds do not directly trigger an AP change.


---

# Nominal Beacon Listening

The requested skip values correspond approximately to:

```text
desired_beacon_skip = 20
-> approximately every 21st beacon

desired_beacon_skip = 15
-> approximately every 16th beacon

desired_beacon_skip = 10
-> approximately every 11th beacon
```

In nominal listening opportunities:

```text
21 / 16 ~= 1.31
```

so skip 15 represents about 1.31 times as many nominal beacon-listening opportunities as skip 20.

And:

```text
21 / 11 ~= 1.91
```

so skip 10 represents about 1.91 times as many nominal beacon-listening opportunities as skip 20.

These ratios describe nominal radio-side listening opportunities.

They do **not** mean that complete-device power consumption increases by the same factor.

They also do not imply that the host MCU wakes for every individual beacon opportunity.


---

# AP Selection and Normal WLAN Energy Use

AP selection can influence normal WLAN workload through several mechanisms.

A weaker or less suitable AP can potentially result in:

- lower `desired_beacon_skip`,
- more radio listening opportunities,
- additional retransmissions,
- less stable communication,
- reconnects,
- additional scans,
- different beacon reception behavior.

The supported relationship is therefore:

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

Their quantitative contribution to the historical TRV battery drain has not yet been measured.


---

# AP Selection and Beacon Recovery

AP selection and Beacon Recovery must be treated as separate mechanisms.

The WLAN environment can influence both, but there is no identified control path equivalent to:

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
requested WLAN power-save policy
```

The Beacon Recovery path is different:

```text
WF200 beacon statistics
        |
        v
received-beacon counter
        |
        v
host-side estimator
        |
        v
real_beacon_skip
        |
        v
Recovery predicate
```

RSSI itself is not the Recovery predicate.

The firmware does not perform:

```text
if real_beacon_skip != desired_beacon_skip:
    recover
```

Instead, the calculated or cached `real_beacon_skip` is evaluated independently.


---

# Good RSSI Does Not Prevent Beacon Recovery

Poor RF conditions are a plausible contributor to WLAN inefficiency, but the runtime observations do not support weak RSSI as a general explanation for Beacon Recovery.

TRVs have been observed with very good WLAN signal strength while still showing low calculated `real_beacon_skip` values and recurring Beacon Recovery.

In other words, the following relationship does not hold generally:

```text
weak RSSI
    |
    v
low real_beacon_skip
    |
    v
Beacon Recovery
```

A low `real_beacon_skip` and subsequent Recovery can also occur while the device has a strong WLAN signal.

This is consistent with the firmware implementation because RSSI and `real_beacon_skip` come from different inputs.

RSSI controls the requested policy:

```text
RSSI
 |
 v
desired_beacon_skip
```

while `real_beacon_skip` is derived from received-beacon statistics:

```text
beacon receive counter
        |
        v
measurement window
        |
        v
real_beacon_skip
```

Therefore:

```text
good RSSI
```

can result in:

```text
desired_beacon_skip = 20
```

while the host can still calculate:

```text
real_beacon_skip = 1
```

and satisfy the Beacon Recovery predicate.

This has been observed in real TRV runtime data and weakens the hypothesis that recurring Recovery is primarily caused by association with a weak access point.

AP selection can still influence RF conditions, normal WLAN workload and possibly fresh Recovery measurements, but poor RSSI is not a necessary condition for Beacon Recovery.


---

# The Original Stock 2.2.4 Recovery Loop

The investigation of firmware 2.2.4 identified several host-side problems in the Beacon Recovery implementation.

The important point for AP analysis is that the persistent stock Recovery loop does not require persistent weak RF conditions.

After a qualifying Recovery, stock firmware clears the beacon-counter baseline but retains the previously qualifying `real_beacon_skip`.

The next baseline-only measurement can then evaluate that historical value again.

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
old real_beacon_skip evaluated
        |
        v
Recovery again
        |
        v
previous_received = 0
```

This can create the observed approximately once-per-minute Recovery loop.

Once that state exists, the loop does not require:

- a new weak-RSSI event,
- a new AP problem,
- a new mDNS event,
- or a fresh abnormal beacon measurement every minute.

This substantially changed the role of AP selection in the battery-drain investigation.


---

# First Trigger vs. Persistent Recovery

Two questions must be separated:

```text
Why did the first qualifying Recovery occur?
```

and:

```text
Why did Recovery continue repeating afterward?
```

The persistent stock recurrence is explained by the stale-state behavior described above.

The first qualifying measurement remains more interesting.

Possible contributors include:

- unusual beacon reception,
- invalid or aged measurement windows,
- PM transitions,
- connection-state transitions,
- WF200 internal behavior,
- AP-specific behavior,
- RF conditions,
- or another event not yet identified.

However, the observation of fresh Recovery at very good RSSI shows that poor signal strength is not required even for a fresh qualifying event.

AP behavior may therefore still influence the measurement environment, but the first trigger cannot simply be reduced to weak RSSI.


---

# Patch C-C Changes the Interpretation

Patch C-C was developed to correct the host-side validity problems without simply removing Beacon Recovery.

Its relevant behavior is:

- stale Recovery evidence is not reused,
- baseline-only samples do not trigger Recovery from historical evidence,
- invalid/signed control cases are rejected,
- fresh valid measurements can still trigger Recovery.

Patch C-C intentionally does **not** change:

```text
AP selection
prevent_roaming
RSSI thresholds
desired_beacon_skip
mDNS behavior
```

This is important because it allows the Recovery correction to be studied without simultaneously changing the AP-selection policy.


---

# C-C Runtime Behavior

Hardware testing has now confirmed that C-C removes the self-sustaining stale-state Recovery behavior while still allowing fresh Recovery events.

The observed pattern can look approximately like:

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
no Recovery
        |
        v
following fresh measurement
        |
        v
possible new Recovery
```

Under the currently observed periodic measurement cadence, this produces a practical upper pattern around one fresh-triggered Recovery every two minutes rather than the stock stale-state loop of approximately one Recovery every minute.

This is an important distinction:

> C-C does not eliminate Beacon Recovery. It eliminates the identified invalid recurrence mechanism.

Fresh `real_beacon_skip` values can still satisfy the retained Recovery condition.


---

# Recovery Wall-Clock Occupancy

The difference can also be expressed as wall-clock Recovery time.

The temporary Recovery state lasts approximately five seconds.

For the stock stale-state loop observed on the D3 test device:

```text
~60 Recoveries/hour
× ~5 seconds
= ~300 seconds/hour
= ~5 minutes/hour
= ~8.33% of wall-clock time
```

For C-C, with the currently observed periodic measurement cadence, a fresh Recovery cannot normally occur on the immediately following baseline-only sample.

A theoretical fresh-trigger pattern is therefore approximately:

```text
~30 Recoveries/hour
× ~5 seconds
= ~150 seconds/hour
= ~2.5 minutes/hour
= ~4.17% of wall-clock time
```

The approximately 30/hour C-C limit is not considered an optimized Recovery rate. It is a consequence of the current measurement cadence and the requirement for a fresh post-Recovery baseline.

Further rate limiting is under consideration, but no technically justified minimum Recovery frequency has yet been established.

The current integrated A1 + C-C + WF200 3.18.0 runtime has shown approximately:

```text
~27 Recoveries/hour
× ~5 seconds
= ~135 seconds/hour
= ~2.25 minutes/hour
= ~3.75% of wall-clock time
```

These numbers describe time spent in the explicit Recovery interval.

They are **not battery-consumption percentages**.

They also do not prove how long the WF200 is physically awake outside those intervals.


---

# Why Fresh Recovery Is Still Under Investigation

The remaining fresh Recovery behavior is now more interesting than the old stale-state loop.

The host derives `real_beacon_skip` from received-beacon statistics.

It does not directly read back:

```text
actual physical WF200 sleep residency
```

or:

```text
effective hardware beacon-listen interval
```

Therefore a low `real_beacon_skip` value does not by itself prove that the WF200 failed to enter power save.

This is particularly important when considering AP and RF conditions.

The host estimator may be influenced by the pattern of received beacons without directly describing the internal physical sleep state of the radio.

AP behavior could therefore affect the estimator without necessarily proving a WF200 power-management failure.

The observation that low `real_beacon_skip` values and Recovery can occur even at very good RSSI reinforces this distinction.


---

# Parallel D3 Observation

Firmware 2.2.4 also exposes the WF200 `PS_MODE_ERROR` indication through the D3 event.

Known D3 reasons include conditions corresponding to:

```text
0
PS-Poll timeout

1
U-APSD timeout

2
buffered unicast not delivered across repeated beacons

3
unstable beacon timing / beacon-window compensation
```

These are much closer to explicit WF200 power-save error reporting than the host-derived `real_beacon_skip` estimator.

A dedicated D3 observer build was therefore used to monitor the WF200 error channel in parallel with the normal Shelly Beacon Recovery behavior.


---

# D3 Runtime Result

The D3 observer device `.11` retained the normal Shelly Recovery logic while counting D3 `PS_MODE_ERROR` events.

After approximately:

```text
230144 seconds
= 63.93 hours
= 2.66 days
```

the device reported:

```text
beacon_err_counter  = 3835
D3_total            = 0
reboot_counter      = 1
reconnect_counter   = 1
desired_beacon_skip = 20
real_beacon_skip    = 1
```

The Recovery rate was:

```text
3835 / 230144 × 3600
≈ 59.99 Recoveries/hour
```

which is essentially the stock once-per-minute Recovery loop.

During the same observation period:

```text
D3 PS_MODE_ERROR events = 0
```

This means that the known WF200 power-save error channel was monitored in parallel while thousands of normal Shelly Beacon Recoveries occurred.

At no observed time did a Beacon Recovery coincide with, follow, or visibly clear a known D3 `PS_MODE_ERROR`.

There was also no observed case where Beacon Recovery could be shown to correct a D3-reported error, because no D3 error was reported during the observation period.

This does **not** prove that no other internal WF200 condition existed.

D3 is not complete physical sleep telemetry.

But it strongly separates the Shelly Beacon Recovery heuristic from the known WF200 `PS_MODE_ERROR` indication.


---

# Consequence for AP Interpretation

D3 reason 3 demonstrates that AP beacon timing can matter to WF200 power management.

Reasons 0–2 also show that AP-side delivery behavior can influence power-save operation.

Therefore AP behavior remains relevant to radio power management in general.

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

The long D3 observation makes that distinction particularly important.

Thousands of host Beacon Recoveries occurred without a corresponding known D3 power-save error.

Together with the observation of Recoveries at very good RSSI, this argues against interpreting Beacon Recovery as a simple weak-signal or known-WF200-error detector.


---

# WF200 3.18.0

The official Silicon Labs WF200 3.18.0 firmware includes the change:

```text
[LMAC] Fixed an error that was preventing the device from sleeping after a power-save mode change
```

This is directly relevant to the class of problem being investigated.

The Shelly TRV 2.2.4 host normally uses:

```text
FMAC 3.7.0
WF200 3.16.1
```

The project has successfully integrated the official WF200 3.18.0 image while retaining Shelly FMAC 3.7.0.

Real-device testing confirms that this combination successfully performs:

```text
WF200 initialization
scan
join
association
DHCP
power-save configuration
cloud communication
```

Therefore:

```text
Shelly FMAC 3.7.0 + WF200 3.18.0
```

is operational on the tested TRV Gen1 hardware.


---

# WF200 3.18.0 Does Not Eliminate Fresh Beacon Recovery

An important runtime result is that fresh host Beacon Recovery can still occur with WF200 3.18.0.

This means the Silicon Labs fix does not simply make the Shelly host estimator stop producing qualifying values.

That is not surprising because the two mechanisms are different:

```text
WF200 3.18.0
    |
    v
radio-internal sleep / PM behavior
```

versus:

```text
Shelly host
    |
    v
received-beacon statistics
    |
    v
real_beacon_skip
    |
    v
Recovery heuristic
```

The continued presence of fresh Recovery therefore does not prove that the WF200 3.18.0 sleep fix failed.

Likewise, the presence of Recovery does not prove that the WF200 was physically awake when it should have been asleep.


---

# Current Integrated Firmware

The current integrated experimental firmware combines:

```text
Shelly TRV 2.2.4 host
        |
        +---- A1 host PM / ownership corrections
        |
        +---- Patch C-C Beacon Recovery corrections
        |
        +---- official WF200 3.18.0
```

A1 corrects separate host-side power-management and transaction-ownership issues.

C-C corrects the identified Beacon Recovery validity defects.

WF200 3.18.0 introduces the newer Silicon Labs radio firmware including the LMAC sleep-after-PM-change fix.

None of these changes intentionally modifies the AP-selection policy.

The integrated firmware still uses the normal Shelly connection model:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```


---

# Current Hardware Qualification

The integrated A1 + C-C + WF200 3.18.0 build has successfully booted on real Shelly TRV Gen1 hardware.

Observed operation includes:

- WF200 3.18.0 initialization,
- WLAN scanning,
- successful join,
- association,
- DHCP,
- cloud connection,
- normal PM state transitions,
- thermostat operation,
- valve operation,
- successful recalibration.

After approximately eight hours of early qualification:

```text
reboot_counter    = 1
reconnect_counter = 1
```

No additional reboot or reconnect was observed.

Fresh Beacon Recovery remained present at approximately:

```text
~27 Recoveries/hour
```

while the device otherwise remained operational.

This is relevant to AP analysis because it shows that the remaining fresh Recovery behavior is not dependent on changing the AP-selection policy.


---

# The Estimator Is Not Permanently Stuck at `1`

Early runtime samples frequently showed:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

A later integrated sample showed:

```text
desired_beacon_skip = 15
real_beacon_skip    = 13
```

This is useful because it demonstrates that the estimator can produce values much closer to the requested skip.

It is not simply permanently stuck at `1`.

The host estimator therefore responds to changing beacon-reception conditions.

Those conditions may include RF and AP behavior, but the estimator still must not be interpreted as direct physical WF200 sleep telemetry.


---

# Current Role of AP Selection in the Battery Investigation

The original AP hypothesis was broader.

A possible early model was:

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

The runtime observations now show that this model is too simple.

Beacon Recovery has also been observed with very good WLAN signal strength.

The current model is therefore better represented as:

```text
                    AP selection / retention
                              |
                              v
                        RF conditions
                              |
              +---------------+---------------+
              |                               |
              v                               v
             RSSI                     beacon reception
              |                               |
              v                               v
    desired_beacon_skip                host estimator
              |                               |
              v                               v
 normal WLAN power policy             fresh Recovery
```

Importantly:

```text
good RSSI
    |
    +----> desired_beacon_skip may be 20
    |
    +----> real_beacon_skip can still be low
    |
    +----> Beacon Recovery can still occur
```

Separately, stock firmware contained the stale-state defect that could turn one qualifying Recovery into a self-sustaining loop.

That defect does not require continuing poor AP conditions.


---

# AP Selection Is Still Relevant

The fact that AP selection is not required for the stock Recovery loop does not make AP behavior irrelevant.

It remains relevant to:

- normal WLAN efficiency,
- `desired_beacon_skip`,
- retransmissions,
- connection stability,
- reconnect frequency,
- scan frequency,
- beacon reception,
- the environment of a fresh Recovery calculation,
- and possibly the first qualifying Recovery event.

However, real-device observations already establish an important boundary:

> Poor RSSI is not required for a low `real_beacon_skip` or for Beacon Recovery.

AP selection should therefore not be treated as the primary explanation for the Recovery mechanism.

It may still become important if future testing shows that fresh Recovery frequency correlates with particular APs, BSSIDs, channels or other RF conditions even when RSSI itself is good.


---

# Should Roaming Be Enabled?

A technically simple experiment would change:

```text
prevent_roaming = 1
```

to:

```text
prevent_roaming = 0
```

This would allow the WLAN firmware to use its internal roaming implementation.

Such an experiment could answer useful questions:

- Does the TRV actually move to stronger APs?
- At what RSSI does roaming occur?
- Does roaming reduce time spent at skip 10 or skip 15?
- Does it reduce retransmissions?
- Does it affect fresh Beacon Recovery frequency?
- Does it improve long-term battery voltage decline?
- Does it introduce additional scans or connection instability?

However, enabling roaming would introduce another experimental variable.

It would not correct the known host-side Recovery defects and it would not tell us how the internal WF200 AP-ranking algorithm works.

For the current main battery experiment, roaming should therefore remain unchanged.


---

# Diagnostic BSSID Instrumentation

If AP behavior is investigated further, direct BSSID observation is preferable to inferring AP changes from RSSI.

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

on every successful association.

This would answer directly:

```text
Which AP did the TRV actually associate with?
```

without changing:

- AP selection,
- roaming policy,
- RSSI thresholds,
- beacon-skip policy,
- mDNS behavior,
- Beacon Recovery.

This should be the first AP-specific instrumentation step.


---

# Suggested AP Experiment

If AP behavior becomes a priority, the cleanest experiment is observational first and interventional second.

## Phase 1 — Record the Associated AP

Record:

```text
timestamp
BSSID
channel
RSSI
```

for every successful association.

Keep:

```text
prevent_roaming = 1
```

unchanged.


## Phase 2 — Weak-but-Functional AP

Create a controlled situation:

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

This directly tests whether the TRV remains attached to AP A.


## Phase 3 — Force Connection Loss

Disable or otherwise make the currently associated AP unavailable.

Observe:

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

This tests how the WLAN subsystem behaves when it is forced to select again.


## Phase 4 — Optional Roaming Experiment

Only after the baseline behavior is understood, compare:

```text
prevent_roaming = 1
```

with:

```text
prevent_roaming = 0
```

while recording:

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

This separates AP observation from AP-policy modification.


---

# Possible Future Recovery Experiment

The remaining fresh Beacon Recovery behavior is still under investigation.

One future experiment may therefore be to further restrict or temporarily suppress Recovery after the current integrated firmware has accumulated enough long-term runtime data.

The purpose would not be to assume that Recovery is unnecessary.

The purpose would be to answer:

> Does the retained fresh Beacon Recovery provide a measurable functional benefit, or does it mainly introduce additional ACTIVE time without correcting a demonstrated WF200 error?

This experiment should not be mixed with an AP-roaming change.

Changing both simultaneously would make the result difficult to interpret.

A clean sequence would be:

```text
current A1 + C-C + WF200 3.18.0
        |
        v
long-term baseline
        |
        v
controlled Recovery modification
        |
        v
compare stability and battery behavior
        |
        v
separate AP/roaming experiment if needed
```

At present there is not enough evidence to define how far Recovery can safely be reduced.

The existing C-C behavior therefore remains the conservative baseline because it removes the demonstrated stale/invalid recurrence while retaining fresh Recovery.


---

# Version Comparison

The examined host firmware versions are:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

The relevant host connection behavior remains substantially consistent:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```

No version-specific host-side strongest-AP selection algorithm was identified.

However, the protected WLAN firmware changed across these versions.

Known combinations include:

```text
2.1.3
FMAC 3.3.2
WF200 3.12.2

2.1.8
FMAC 3.4.1
WF200 3.14.0

2.2.4
FMAC 3.7.0
WF200 3.16.1
```

The current experimental integration uses:

```text
Shelly host 2.2.4
FMAC 3.7.0
WF200 3.18.0
```

The same host CONNECT parameters do not prove that all WF200 versions use identical internal AP-selection behavior.

No specific AP-ranking change between these WF200 versions has been established.


---

# Current Model

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
                        WF200
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
             +------------+------------+
             |                         |
             v                         v
        RSSI changes              connection loss
             |                         |
             v                         v
 desired_beacon_skip                  scan
             |                         |
             v                         v
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
temporary ACTIVE state
```

In stock 2.2.4 an additional stale-state defect could sustain Recovery after the original fresh evidence was no longer available.

C-C removes that stale recurrence while preserving fresh Recovery.

Good RSSI does not invalidate this model because RSSI controls the requested skip policy while the Recovery estimator is derived from separate beacon-reception statistics.


---

# Remaining Questions

The most important unresolved AP questions are:

1. What exact criteria does the WF200 use during wildcard AP selection?

2. Does the WF200 prefer a previously associated AP?

3. What roaming thresholds and hysteresis are used when `prevent_roaming = 0`?

4. How often do real TRVs remain associated with a weak but functional AP while a substantially stronger AP is available?

5. Do large observed RSSI changes correspond to BSSID changes?

6. How much additional radio energy is consumed at skip 10, 15 and 20?

7. How much do retransmissions contribute under weak RF conditions?

8. How much energy is consumed by scans and reconnects?

9. Did WF200 firmware changes between 3.12.2, 3.14.0, 3.16.1 and 3.18.0 change AP selection or reconnect behavior?

10. Do particular APs, BSSIDs, channels or RF environments correlate with fresh `real_beacon_skip = 1/2` measurements even when RSSI is good?

11. What causes fresh `real_beacon_skip = 1/2` measurements on devices with very good WLAN signal strength?

12. Can AP conditions influence the first fresh Beacon Recovery trigger independently of RSSI?

13. Why does the Shelly host use the beacon-density estimator as a Recovery condition instead of a direct WF200 PM error indication?

14. Does fresh Beacon Recovery provide a measurable benefit when no D3 `PS_MODE_ERROR` is present?

15. Would enabling autonomous roaming improve long-term battery behavior?

16. Would autonomous roaming instead increase scans, reassociations or other WLAN workload?


---

# Question for Shelly

The host-side AP behavior raises two useful implementation questions for Shelly firmware developers:

> Why is `prevent_roaming = 1` used on a battery-powered device that may remain installed for months or years in a multi-AP network?

and:

> When `real_beacon_skip` reaches the Recovery threshold, what specific WF200 or protocol failure was this heuristic intended to detect?

The second question is particularly important because the current runtime evidence shows:

- thousands of host Beacon Recoveries without a corresponding known D3 `PS_MODE_ERROR`, and
- Beacon Recovery on devices with very good WLAN signal strength.

Understanding the intended failure condition would help determine whether the remaining fresh Recovery behavior is still necessary, can be further constrained, or should be replaced by a more direct error signal.


---

# Current Conclusion

The Shelly TRV host does not explicitly select one particular strongest access point during normal connection establishment.

The examined connection path uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

and delegates concrete AP selection to the WLAN/WF200 subsystem.

After association the host sets:

```text
prevent_roaming = 1
```

which prevents autonomous WLAN-firmware roaming.

No separate host-side strongest-AP roaming mechanism was identified.

A weak but still functional AP can therefore potentially remain associated even when a stronger compatible AP is available.

This can influence normal WLAN power behavior because RSSI controls:

```text
desired_beacon_skip = 20 / 15 / 10
```

and poor RF conditions may also affect retransmissions, beacon reception and connection stability.

At the same time, runtime observations show that low `real_beacon_skip` values and Beacon Recovery can also occur with very good WLAN signal strength.

Weak RSSI is therefore **not a necessary condition for Beacon Recovery**.

This is consistent with the implementation because RSSI and `real_beacon_skip` describe different things:

```text
RSSI
 |
 v
desired_beacon_skip
```

while:

```text
received-beacon statistics
        |
        v
real_beacon_skip
        |
        v
Recovery predicate
```

AP selection is therefore not required to explain either the existence of a low `real_beacon_skip` value or the persistent stock 2.2.4 Beacon Recovery loop.

The stale-state Recovery defect can sustain the stock loop after one qualifying event without requiring continued weak RSSI or a new RF anomaly.

Patch C-C removes that recurrence while retaining fresh Recovery.

The D3 observer provides an additional important separation: approximately **3,835 Beacon Recoveries over 63.93 hours occurred while the known WF200 `PS_MODE_ERROR` counter remained at zero**.

The current A1 + C-C + WF200 3.18.0 integration also continues to show fresh Recovery events while remaining operational.

The current interpretation is therefore:

```text
AP selection
    |
    v
important for normal WLAN efficiency,
desired beacon-skip policy,
RF behavior and possibly fresh-trigger conditions

but

weak RSSI is not required for Recovery

and

AP selection is not required for the old
self-sustaining Beacon Recovery loop
```

The next useful AP-specific step is not to change roaming immediately.

It is to observe the actual associated BSSID and channel.

Only after that behavior is understood should `prevent_roaming = 0` be considered as a controlled experiment.

The same applies to further reducing Beacon Recovery: it is a valid future experiment, but the safe extent of that reduction has not yet been established.


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

Periodic mDNS:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Experimental patches:

[`../patch/README.md`](../patch/README.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)


---

# Research Notes

This investigation is based on static reverse engineering of locally obtained Shelly TRV Gen1 firmware and runtime observations from personally owned devices.

The analysis deliberately separates host-visible behavior from protected WF200 internal behavior.

The exact WF200 AP-ranking and roaming algorithms have not been reconstructed.

Where internal WF200 behavior cannot be established from the host firmware or runtime evidence, it remains unresolved.

Complete proprietary firmware images and large raw disassemblies are not reproduced in this repository.


---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior of the investigated firmware versions.