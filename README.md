# Shelly TRV Gen1 – Firmware Analysis and Battery-Drain Investigation

Reverse engineering, runtime analysis and experimental firmware research for the
Shelly TRV Gen1 (`SHTRV-01`).

The project started with an investigation into unusually high battery drain
observed on Shelly TRV Gen1 devices running firmware 2.2.4.

During the investigation, multiple firmware generations were compared and
several WLAN power-management and recurring network mechanisms were identified.

The current evidence strongly suggests that the observed battery-runtime behavior
should not be reduced to a single bug.

Instead, several independent or potentially interacting mechanisms exist.

---

# Project Status

Research is ongoing.

The following areas have currently been investigated:

- firmware 2.1.0
- firmware 2.1.3
- firmware 2.1.8
- firmware 2.2.4
- WLAN power-management states
- DTIM / beacon skipping
- real beacon-skip calculation
- beacon-recovery behavior
- WF200 communication
- access-point selection and roaming behavior
- WUP / EM2 sleep-resource handling
- periodic mDNS restart behavior
- runtime mDNS packet captures
- isolated beacon-recovery patching
- isolated periodic-mDNS patching
- combined beacon-recovery + mDNS patching
- hardware runtime validation
- long-term battery logging

Two experimental firmware modifications have now been implemented and tested:

```text
Patch A
Beacon-recovery bypass

Patch B
Periodic mDNS restart bypass
```

Both modifications have also been combined into one experimental firmware image.

Runtime testing has confirmed that:

- Patch A suppresses the targeted beacon-recovery entry
- normal beacon-skip calculation remains active with Patch A
- Patch B suppresses the observed periodic mDNS restart traffic
- Patch B alone does not suppress the beacon-recovery cycle
- the combined A+B firmware boots and operates on real SHTRV-01 hardware
- the combined firmware has not shown the targeted periodic mDNS cycle during
  the monitored packet-capture window
- the combined firmware has not shown the recurring beacon-recovery sequence
  during the monitored multi-hour runtime period
- normal Wi-Fi, cloud and thermostat functionality remained available during
  the observed tests

This does **not** yet prove that the historical battery-drain problem has been
solved.

Long-term battery testing remains in progress.

---

# Firmware Versions Investigated

The following firmware versions are currently part of the comparison:

| Firmware | Build |
|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` |

Firmware 2.1.6 and 2.1.7 are known intermediate releases but are not currently
part of the primary four-version comparison.

---

# Historical Battery-Drain Observation

The exact firmware version in which the historical battery-runtime degradation
first appeared is currently unknown.

The available user history is approximately:

```text
older firmware
     ↓
large firmware update
     ↓
2.2.4
     ↓
noticeably shorter battery runtime
     ↓
downgrade to 2.1.8
     ↓
battery drain still observed
     ↓
later downgrade to older firmware
```

This means that firmware 2.2.4 cannot currently be considered the origin of the
entire battery-drain problem.

Firmware 2.1.8 had already shown relatively fast battery drain in practical
use.

Firmware 2.1.3 must also **not** currently be classified as a known
battery-efficient release.

The historical introduction boundary therefore remains unresolved.

Firmware 2.1.0 is currently being used as an older reference firmware because
its observed behavior differs significantly from later versions in several
areas.

---

# WLAN Power Management

The TRV uses several internal WLAN power-management states.

The currently identified application-visible states include:

```text
state 1
state 2
state 3
state 4
state 5
```

The normal connected power-save state is generally state 3.

In this state the firmware configures the WF200 for Fast Power Save with a
desired beacon-skip value derived from RSSI.

Observed RSSI mapping:

```text
RSSI >= -69 dBm       desired skip = 20
RSSI -70 .. -79 dBm   desired skip = 15
RSSI < -79 dBm        desired skip = 10
```

These values describe the requested power-save behavior.

They do not by themselves prove the actual electrical consumption of the radio.

---

# Beacon Skip

Firmware 2.2.4 exposes additional beacon statistics and calculates a value
referred to here as:

```text
real_beacon_skip
```

Static analysis showed that the firmware obtains cumulative beacon statistics
from the WF200 and calculates approximately:

```text
600 / delta(beacon_rx_count)
```

The result is truncated to the low byte and subsequently interpreted as a
signed value.

This creates several edge cases.

The relevant statistics are available through firmware functionality associated
with the WF200 statistics command and are exposed through `/stats` on firmware
2.2.4.

Observed fields include values associated with:

```text
beacon_rx_count
beacon_missed_count
tbtt_diff
real_beacon_skip
desired_beacon_skip
```

The exact lower-level semantics of all WF200 counters are not fully known.

However, the relationship between the cumulative beacon receive counter and the
calculated `real_beacon_skip` value has been established sufficiently to explain
the host-side calculation.

Firmware 2.2.4 then evaluates the calculated value and may enter a recovery path
when the result falls into the qualifying range.

---

# Beacon-Skip Recovery

The characteristic runtime log message is:

```text
minutes_tick: Beacon skip error! Attempt recovery
```

When triggered, the firmware temporarily changes the WLAN power-management
state.

The observed sequence is approximately:

```text
normal power save
     ↓
beacon-skip recovery
     ↓
state 1
     ↓
approximately 5 seconds
     ↓
restore previous / desired state
     ↓
normally state 3
```

Reverse engineering indicates that state 1 places the WLAN subsystem into an
active / always-on configuration and prevents the host from entering its deeper
sleep state while the recovery is active.

No explicit transmit-power increase was identified.

No evidence was found that the normal recovery mechanism intentionally performs
a complete Wi-Fi reconnect, DHCP renewal or cloud reconnect.

The additional activity makes an energy impact technically plausible, but its
electrical cost has not been measured.

---

# Beacon-Recovery Runtime Behavior

On stock firmware 2.2.4, the recovery behavior has repeatedly been observed at
approximately one event per minute under affected conditions.

Long-term logger data provide an additional useful indicator.

On the stock 2.2.4 reference device, the beacon-recovery counter was observed
increasing by approximately:

```text
+30 events per 30 minutes
```

which corresponds closely to:

```text
1 recovery event per minute
```

The same recurring behavior was also observed on the mDNS-only patched device.

Importantly, recovery events have been observed while:

- RSSI was approximately `-58` to `-60 dBm`
- desired beacon skip was 20
- the valve motor was inactive

Poor RSSI and valve movement are therefore not necessary conditions for the
observed recurring recovery behavior.

---

# Patch A – Beacon-Recovery Bypass

An experimental patch for firmware 2.2.4 was developed.

The patch changes only the control flow entering the beacon-recovery block.

Original instruction:

```text
31 DC
```

Patched instruction:

```text
31 E0
```

Program-image instruction address:

```text
0x0001E1C8
```

Changed byte in the extracted program:

```text
0x0001E1C9

DC -> E0
```

Corresponding GBL location:

```text
0x0002471D

DC -> E0
```

The modification bypasses the recovery entry while leaving the surrounding
beacon-statistics calculation intact.

The patch does **not** intentionally modify:

- RSSI thresholds
- desired beacon-skip values
- real beacon-skip calculation
- Wi-Fi transmit power
- cloud communication
- access-point selection
- normal Fast Power Save configuration

Runtime testing has confirmed that patched devices continue calculating beacon
statistics while the targeted recovery counter remains inactive.

Normal device functionality has also remained available during testing.

This proves that the targeted recovery mechanism can be bypassed.

It does **not** prove that bypassing it solves the historical battery-drain
problem.

---

# Periodic mDNS Activity

Static firmware comparison identified another recurring network mechanism that
differs between firmware generations.

The mDNS responder itself already exists in firmware 2.1.0.

The important change in firmware 2.1.3 is the addition of a recurring connected
maintenance caller that invokes the equivalent of:

```text
mdns_resp_restart()
```

The resulting path is approximately:

```text
connected maintenance
       ↓
mdns_resp_restart()
       ↓
reset probing state
       ↓
schedule probe callback
       ↓
mDNS probes
       ↓
mDNS announcement
```

The restart resets the probing state and schedules the mDNS probing sequence
again.

After successful probing, the device sends an mDNS announcement.

This means the relevant firmware difference is **not the introduction of mDNS
itself**.

The difference is the introduction of the recurring restart of the mDNS probing
process.

---

# mDNS Runtime Validation

Passive packet captures performed on real Shelly TRV Gen1 devices confirmed the
behavior.

Three firmware configurations were initially observed simultaneously:

| Device | Firmware | Role |
|---|---|---|
| `.11` | 2.1.0 | old firmware reference |
| `.77` | 2.1.3 | periodic-mDNS reference |
| `.229` | 2.2.4 stock | current stock reference |

The capture was performed using TShark with UDP port 5353 filtered for the
observed devices.

The initial simultaneous observation period was approximately 13 minutes.

---

## Firmware 2.1.0

No mDNS packets from the 2.1.0 reference device were observed during the
approximately 13-minute simultaneous capture.

This is consistent with the static analysis, which found the mDNS responder in
2.1.0 but did not find the later connected-maintenance caller responsible for
periodically restarting the probing process.

This result must not be interpreted as:

```text
2.1.0 never uses mDNS
```

The correct interpretation is:

```text
No comparable recurring mDNS probe / announcement cycle was observed during
this test window.
```

---

## Firmware 2.1.3

Firmware 2.1.3 repeatedly produced a characteristic mDNS sequence.

A complete observed cycle normally consisted of:

```text
probe
probe
probe
announcement
```

Example:

```text
59.699 s   probe
60.006 s   probe
60.211 s   probe
60.520 s   announcement
```

Further burst starts occurred at approximately:

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

The observed period is therefore approximately:

```text
60 seconds
```

This runtime behavior closely matches the mechanism identified during static
analysis.

The periodic mDNS restart in firmware 2.1.3 is therefore no longer only a
static-analysis hypothesis.

It has been confirmed on a running device.

---

## Firmware 2.2.4 Stock

Stock firmware 2.2.4 also produced the characteristic mDNS
probe / announcement sequence.

Observed burst start times included:

```text
117.555 s
297.779 s
477.492 s
657.413 s
```

The intervals were:

```text
180.225 s
179.713 s
179.921 s
```

The observed runtime period is therefore approximately:

```text
180 seconds
```

This establishes that the periodic mDNS behavior is still present in firmware
2.2.4.

However, the period differs significantly from firmware 2.1.3.

Current runtime comparison:

```text
2.1.0        no periodic burst observed during ~13 min
2.1.3        periodic burst ≈ 60 s
2.2.4 stock  periodic burst ≈ 180 s
```

Static analysis of 2.2.4 showed that this approximately 180-second behavior is
not implemented as a dedicated 180-second timer.

Instead, a minute-based maintenance path increments an internal counter and
services the mDNS restart every third invocation when the required connected /
IPv4 conditions are met.

This produces the observed approximately 180-second interval.

---

# Patch B – Periodic mDNS Restart Bypass

After identifying the periodic 2.2.4 mDNS restart path, a second isolated patch
was developed.

The target is the conditional branch immediately before the periodic
`mdns_resp_restart()` call.

Original instruction:

```text
02 D0
```

Patched instruction:

```text
02 E0
```

Program-image instruction address:

```text
0x0001E0F0
```

Changed byte in the extracted program:

```text
0x0001E0F1

D0 -> E0
```

Corresponding GBL location:

```text
0x00024645

D0 -> E0
```

The patch changes the branch so execution always skips the periodic restart
call and continues at the firmware's existing continuation path.

The periodic caller is bypassed.

The patch does **not** remove the mDNS implementation itself.

Other mDNS entry points remain present, including paths associated with:

- network-interface setup
- service registration
- connection establishment
- other event-driven responder behavior

Patch B should therefore be described as:

```text
periodic mDNS restart bypass
```

and not as:

```text
mDNS disabled
```

---

# Isolated Patch-B Runtime Test

Patch B was installed by itself on the `.77` test device.

The beacon-recovery patch was intentionally **not** included.

This created an important controlled test:

```text
Patch B / periodic mDNS bypass    YES
Patch A / beacon recovery         NO
```

A TShark capture filtered for UDP port 5353 and the test device was then
performed.

During the monitored test window of at least approximately 10 minutes:

```text
0 periodic mDNS packets captured
```

This provides strong finite-window runtime evidence that Patch B suppresses the
targeted periodic mDNS restart behavior.

It does not prove that the device can never emit mDNS traffic because
event-driven mDNS paths remain intact.

Normal device connectivity remained available.

---

# Patch B vs. Beacon Recovery

The isolated Patch-B experiment also answered an important question.

Despite suppression of the periodic mDNS restart, the `.77` device continued
to produce:

```text
Beacon skip error! Attempt recovery
```

at approximately one event per minute.

This continued even with good observed WLAN conditions around:

```text
RSSI ≈ -58 .. -59 dBm
desired beacon skip = 20
```

The recovery sequence continued to include:

```text
state 1
     ↓
approximately 5 seconds
     ↓
state 3 / desired skip
```

This provides strong evidence that, under the tested conditions:

> The periodic mDNS restart is not required for the recurring beacon-recovery
> behavior to occur.

This is more precise than claiming that the two mechanisms are universally or
completely independent.

Other indirect interactions under different conditions have not been ruled out.

---

# mDNS Energy Relevance

The periodic mDNS mechanism generates additional recurring firmware and network
activity.

Each complete observed sequence can include approximately:

```text
3 mDNS probes
+
1 mDNS announcement
```

This requires processing and packet transmission that would not occur at that
moment if the periodic restart were absent.

Therefore the additional mechanism represents a real additional workload.

However, no direct electrical current measurement has been performed.

The current evidence cannot quantify:

- current consumed per mDNS cycle
- battery capacity consumed per cycle
- battery capacity consumed per day
- resulting battery-runtime reduction
- the percentage of the historical battery drain attributable to mDNS

The correct interpretation is therefore:

> Periodic mDNS restart activity is a confirmed additional recurring workload
> and a technically plausible battery-drain contributor, but its quantitative
> contribution to battery drain is currently unknown.

---

# Combined Patch A+B

After the isolated experiments, Patch A and Patch B were combined.

The combined firmware contains:

```text
Patch A
Beacon-recovery bypass

0x0001E1C9
DC -> E0
```

and:

```text
Patch B
Periodic mDNS restart bypass

0x0001E0F1
D0 -> E0
```

No additional firmware-code modifications are intentionally introduced by the
combined patch.

For the specifically supported original firmware image, the validated combined
output has:

```text
Size:
1,106,384 bytes

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61

CRC32:
0xBAEB8265
```

The patched main program SHA-256 is:

```text
06742a2632a3d45cf697b8be85045914d004f30644dad17b3d0d20012c87c61b
```

A complete original-vs-patched GBL comparison produces exactly six changed
bytes:

```text
Firmware modifications:

0x00024645: D0 -> E0
0x0002471D: DC -> E0

Updated GBL CRC32:

0x0010E1CC: 58 -> 65
0x0010E1CD: AB -> 82
0x0010E1CE: 7B -> EB
0x0010E1CF: DC -> BA
```

The first two changes are the two intentional firmware modifications.

The remaining four bytes are the recalculated GBL CRC32.

---

# Combined Patch Runtime Validation

The combined A+B firmware was installed on the `.226` test device.

Before installation, this device was running firmware 2.1.3.

After OTA installation it booted normally as:

```text
20240619-130912/v2.2.4@ee290818
```

The firmware version string remains the normal 2.2.4 identifier because the
patch does not modify version metadata.

The device successfully retained normal observed functionality including:

- firmware boot
- WLAN operation
- local HTTP access
- thermostat operation
- valve operation
- cloud connectivity after startup

A TShark test of the combined firmware did not observe the targeted recurring
mDNS traffic during the monitored capture window.

A subsequent multi-hour debug-log observation also did not show the recurring:

```text
Beacon skip error! Attempt recovery
```

sequence.

During this period:

- RSSI remained in a normal range
- desired beacon skip remained functional
- state 3 remained active during normal connected operation
- no recurring transition to state 1 was observed
- no unexpected reboot was identified in the examined runtime log

This provides hardware runtime evidence that both targeted modifications can
operate together.

It does **not** yet establish long-term battery improvement.

---

# Firmware 2.1.0 → 2.1.3 Changes

The focused firmware comparison found several relevant differences.

Importantly, firmware 2.1.0 and 2.1.3 use the same protected WF200 firmware
payload and the same FMAC generation.

The normal state-3 WLAN power-save configuration is also substantially
equivalent.

Relevant differences include:

```text
2.1.0
  ↓
2.1.3
  ├─ periodic connected mDNS restart
  ├─ new state-5 / psovrd2 mechanism
  ├─ named active power-save override
  ├─ wake ACK wait change
  └─ event dissemination changes
```

Among these changes, the periodic mDNS restart is currently the strongest
confirmed new recurring mechanism during ordinary connected operation.

Runtime packet capture has independently confirmed this behavior.

This does not establish that the mDNS change caused the historical battery
degradation.

---

# State 5 / psovrd2

Firmware 2.1.3 introduced an externally triggered temporary WLAN
power-management state referred to as state 5.

Known entry points include:

```text
/psovrd2
```

and the corresponding cloud command.

The mechanism requests approximately:

```text
Fast Power Save
desired skip = 10
```

for a temporary period.

The countdown is initialized to:

```text
180
```

and is serviced by firmware maintenance logic.

This should not be interpreted as the device intentionally remaining fully
awake for three minutes.

Successful completion of the WLAN sleep transition releases the corresponding
wake / sleep resources.

No autonomous periodic caller continuously entering state 5 has been identified.

However, repeated external requests can refresh the countdown.

State 5 therefore remains a conditional and externally driven mechanism rather
than the strongest candidate for normal idle battery drain.

---

# WUP / EM2 Sleep-Resource Handling

Reverse engineering identified a conditional low-level failure path in the WLAN
power-management implementation.

The normal sleep transition approximately performs:

```text
acquire WLAN wake resource
       ↓
configure WF200 power mode
       ↓
final device-sleep operation
       ↓
release wake / EM2 blocking resource
```

If the final low-level device-sleep control-register operation fails, the
release step may not be reached.

This can leave a WLAN-owned wake / EM2-blocking resource retained.

However, this mechanism requires careful interpretation.

The same fundamental failure path is already present in firmware 2.1.0.

Therefore:

```text
WUP / EM2 retention bug
```

cannot by itself explain a battery-runtime boundary between 2.1.0 and 2.1.3.

Later firmware may theoretically reach or prolong this condition differently,
but this has not yet been demonstrated.

The resource is reference-counted.

A future patch must therefore **not** simply release the resource blindly.

Any modification must first establish ownership and safe cleanup semantics.

---

# Firmware 2.1.3 → 2.1.8

The comparison between firmware 2.1.3 and 2.1.8 found additional WLAN changes.

The most visible host-side change is an additional post-association
power-management sequence.

The sequence approximately performs:

```text
restore state 4
     ↓
delay
     ↓
enter state 3
```

This is not equivalent to an unconditional persistent awake state.

Depending on the previous state, restoring state 4 may actually terminate a
temporary power-management hold sooner.

No new unconditional host-side sleep-lock leak was identified in 2.1.8.

The protected WF200 firmware image also changed between 2.1.3 and 2.1.8.

Because the internal behavior of that protected image cannot currently be
inspected directly, it remains an important uncertainty.

Firmware 2.1.8 also introduced MQTT failure backoff behavior, which could reduce
network activity under some failure conditions.

Static analysis therefore has not identified one simple new host-side mechanism
that explains the historically observed battery drain on 2.1.8.

---

# Firmware 2.2.4

Firmware 2.2.4 adds several additional mechanisms relevant to this research.

These include:

- expanded WF200 statistics
- beacon receive counters
- calculated `real_beacon_skip`
- beacon-skip recovery
- additional power-management retry / locking behavior
- a newer protected WF200 firmware image

The periodic mDNS behavior introduced in earlier firmware is also still present,
although runtime testing shows an approximately 180-second interval rather than
the approximately 60-second interval observed on firmware 2.1.3.

Firmware 2.2.4 therefore contains at least two independently observable
recurring mechanisms of interest:

```text
periodic mDNS restart
+
beacon-skip recovery under qualifying conditions
```

The isolated Patch-B experiment demonstrates that suppressing the periodic mDNS
restart does not suppress the recurring beacon-recovery behavior under the
tested conditions.

This substantially narrows the possible relationship between the two
mechanisms.

It does not prove that no interaction can occur under any condition.

---

# Access-Point Selection and Roaming

Firmware analysis shows that the host sends the WF200 connection request using:

```text
BSSID   = FF:FF:FF:FF:FF:FF
channel = 0
```

The host therefore does not explicitly select a particular access point from
the scan results.

Initial AP selection is left to the protected WF200 implementation.

The connection configuration also contains:

```text
prevent_roaming = 1
```

This indicates that autonomous roaming is prevented once the connection has
been established.

No host-side background algorithm was identified that continuously searches for
and switches to a stronger BSSID.

This is relevant in multi-AP / Mesh environments because a device may remain
associated with an access point that is not currently the strongest candidate.

However, the exact AP-selection algorithm inside the protected WF200 firmware
remains unknown.

---

# RSSI Interpretation

The `/status` RSSI value should not automatically be interpreted as proof that
the host selected a specific BSSID.

The value is derived from cached connection information.

Scan results and the connected RSSI therefore describe different pieces of
information.

A scan showing a stronger neighboring BSSID does not by itself prove that the
TRV is incorrectly associated.

Direct BSSID observation is required for that conclusion.

The newer runtime tests also establish an important additional point:

```text
good RSSI does not prevent the observed 2.2.4 beacon-recovery cycle
```

The mDNS-only patched `.77` device continued entering the recovery path around
`-58` to `-59 dBm` with desired beacon skip 20.

Stock 2.2.4 also showed the recovery cycle under similarly usable WLAN
conditions.

Poor signal quality alone therefore cannot explain the recurring recovery.

---

# Current Scientific Interpretation

The available evidence increasingly supports a **multi-mechanism model** rather
than a single battery-drain bug.

At least three mechanisms are currently relevant.

## 1. Periodic mDNS restart

The recurring mDNS restart is absent from the identified 2.1.0 connected-minute
path and is present from firmware 2.1.3 onward.

Runtime measurements currently show:

```text
2.1.0        no periodic burst observed during ~13 min
2.1.3        one burst approximately every 60 s
2.2.4 stock  one burst approximately every 180 s
```

This is a confirmed additional recurring workload.

Patch B can suppress the targeted periodic 2.2.4 restart.

Its electrical cost remains unknown.

## 2. Beacon-skip recovery in firmware 2.2.4

Under qualifying conditions, firmware 2.2.4 can repeatedly enter the
beacon-recovery path.

On affected test devices this has been observed approximately once per minute.

The recovery temporarily changes the WLAN power-management state before
returning to the normal power-save state.

Patch A suppresses this specific recovery entry.

Its contribution to total battery drain remains unquantified.

Importantly, some patched devices have continued to show noticeable battery
decline despite the recovery path being suppressed.

The recovery mechanism should therefore not currently be treated as the sole
cause of the historical battery-drain problem.

## 3. Conditional WUP / EM2 retention failure

A low-level failure path can leave a WLAN-owned wake / EM2-blocking resource
retained if the final device-sleep operation fails.

This path already exists in firmware 2.1.0.

It therefore cannot independently establish the historical firmware boundary.

It may still contribute to energy consumption if later firmware reaches the
condition more frequently or retains it longer.

That possibility has not yet been demonstrated.

---

# Cumulative Model

The historical battery-runtime reduction may therefore result from the
accumulation of several effects rather than one catastrophic bug.

A conceptual model is:

```text
normal TRV baseline workload
       +
periodic mDNS activity
       +
firmware-specific WLAN power-management behavior
       +
2.2.4 beacon recovery
       +
conditional sleep-resource retention
       +
normal motor activity
       +
cloud / controller communication
       +
radio conditions
```

This is currently a qualitative model.

It must not be interpreted as a quantitative energy budget.

The relative contribution of each component is unknown.

---

# Battery Testing

Long-term battery logging is being performed across multiple physical TRVs and
firmware / patch configurations.

Collected values currently include, where available:

- firmware version
- battery percentage
- battery voltage
- uptime
- RSSI
- beacon statistics
- desired beacon skip
- real beacon skip
- beacon-recovery counter

Motor activity is also being extracted from runtime logs and is planned for
direct inclusion in future logger/report output.

This is important because valve movement represents real mechanical work and
must be separated from network- and firmware-related energy consumption when
interpreting battery behavior.

---

# Current Long-Term Test Devices

The current investigation has used several physical SHTRV-01 devices in
different roles.

The relevant experimental configurations have included:

| Device | Configuration | Experimental role |
|---|---|---|
| `.11` | firmware 2.1.0 | older firmware reference |
| `.77` | 2.2.4 + Patch B only | isolated mDNS-patch test |
| `.88` | 2.2.4 + Patch A | beacon-recovery patch test |
| `.228` | 2.2.4 + Patch A | beacon-recovery patch test |
| `.226` | 2.2.4 + Patch A+B | combined-patch test |
| `.229` | stock 2.2.4 | unmodified control/reference |

These roles describe the relevant current or recent experimental configurations.

Devices have changed firmware during the investigation, so reports spanning a
firmware transition must be divided at the transition point before interpreting
battery behavior.

---

# Current Battery Observations

The current long-term dataset is not yet sufficient to establish a quantified
battery-life improvement.

However, several useful observations have already been made.

## Stock 2.2.4 reference

The stock `.229` device continues to show the recurring beacon-recovery
behavior.

Its recovery counter has repeatedly increased at approximately:

```text
30 events / 30 minutes
```

or approximately:

```text
1 event / minute
```

This provides a useful unmodified control for future comparison.

## Patch-B-only device

The `.77` device no longer showed the targeted periodic mDNS traffic during the
monitored packet-capture window.

However, its beacon-recovery counter continued increasing at approximately the
same once-per-minute rate.

Patch B alone therefore does not eliminate the observed beacon-recovery
workload.

## Patch-A devices

Patch-A devices have shown:

```text
beacon-recovery counter = 0
```

while the underlying beacon statistics and `real_beacon_skip` calculation
continue operating.

This confirms the functional effect of Patch A.

Battery behavior, however, has not been uniform across the Patch-A devices.

At least one Patch-A device continued to show a noticeable voltage / reported
battery decline despite the recovery counter remaining zero.

This is important evidence against treating the beacon-recovery cycle as the
only possible battery-drain mechanism.

## Combined A+B device

The `.226` device showed a comparatively stable initial battery-voltage period
after installation of the combined patch.

This is an encouraging observation.

The observation period is currently too short, and the device crossed a
firmware transition during the available report interval.

It therefore cannot yet be treated as evidence that A+B has solved the battery
drain.

---

# Battery-Data Interpretation

Cross-device battery comparisons require caution.

The physical devices differ in:

- battery age
- battery condition
- battery calibration
- initial state of charge
- valve load
- motor workload
- WLAN conditions
- RSSI
- network configuration
- previous operating history

For this reason, battery percentage alone is not treated as a precise energy
measurement.

Battery voltage is retained as an additional indicator, but it is also affected
by:

- load
- battery chemistry
- relaxation after charging
- temperature
- recent motor operation

Therefore a comparison such as:

```text
device A lost X mV
device B lost Y mV
```

cannot by itself establish that one firmware consumes a specific percentage
more or less energy than another.

Longer observation periods and repeated behavior across multiple devices are
required.

---

# Next Long-Term Test Phase

The previous phase was designed primarily to isolate and validate individual
firmware mechanisms.

That phase has now provided:

```text
Stock 2.2.4
    ↓
periodic mDNS present
beacon recovery present

Patch B only
    ↓
periodic mDNS suppressed
beacon recovery remains

Patch A
    ↓
beacon recovery suppressed

Patch A+B
    ↓
periodic mDNS suppressed during capture
beacon recovery not observed during multi-hour test
```

The next phase changes focus from mechanism isolation to battery-runtime
comparison.

The intended test structure is:

```text
1 × stock 2.2.4 control
        versus
multiple A+B patched devices
```

The devices should begin the comparison as close as practical to a common
starting condition:

- batteries fully charged
- fixed firmware configuration
- normal installation positions
- no intentional firmware changes during the observation period
- continuous battery logging
- runtime / reboot monitoring
- RSSI monitoring
- beacon statistics where available
- motor activity tracking

The preferred observation period is multiple days, with at least approximately
one week providing substantially more useful information than individual
24-hour comparisons.

The stock 2.2.4 reference device should remain unmodified during this phase.

---

# Why the Isolated Patch Tests Were Important

The individual patch experiments were intentionally performed before relying on
the combined firmware.

Without the isolated Patch-B test, a successful A+B firmware would only show:

```text
both targeted behaviors disappeared
```

It would not answer whether suppressing periodic mDNS also indirectly changed
beacon recovery.

The isolated experiment established:

```text
Patch B active
        ↓
periodic mDNS restart suppressed
        ↓
beacon recovery continues
```

This substantially improves the interpretation of the combined patch.

Likewise, Patch A demonstrates that the beacon-recovery entry can be suppressed
without disabling the underlying beacon-statistics calculation.

The combined A+B firmware therefore represents the combination of two
individually investigated modifications rather than an unexplained multi-byte
change.

---

# Future Patch Architecture

The currently implemented architecture is:

```text
Patch A
Beacon-recovery bypass

Patch B
Periodic mDNS restart bypass
```

A possible future area remains:

```text
Patch C
Safe WLAN sleep-resource failure handling
```

Patch C is substantially more sensitive than A or B.

Because the WUP / EM2 resources are reference-counted, no cleanup patch should
be implemented until the complete ownership and failure semantics have been
established for firmware 2.2.4.

There is currently no evidence sufficient to justify blindly releasing the
resource.

Patch C is therefore a research topic, not a planned production modification.

---

# Evidence Classification

The project distinguishes between several evidence levels.

## Proven by static analysis

Examples:

- presence of specific firmware control paths
- RSSI-to-desired-skip mapping
- WF200 command construction
- beacon counter calculation
- periodic mDNS restart caller
- Patch-B branch and bypass target
- WUP / EM2 resource handling
- access-point connection parameters

## Proven by runtime observation

Examples:

- recurring 2.2.4 beacon-recovery logs
- approximately once-per-minute recovery behavior on affected devices
- Patch-A recovery suppression
- continued beacon-statistics calculation after Patch A
- periodic mDNS activity on firmware 2.1.3
- approximately 60-second mDNS interval on firmware 2.1.3
- periodic mDNS activity on stock firmware 2.2.4
- approximately 180-second mDNS interval on stock firmware 2.2.4
- absence of comparable periodic mDNS traffic from the 2.1.0 reference during
  the simultaneous approximately 13-minute capture
- suppression of the targeted periodic mDNS traffic with Patch B during the
  monitored capture window
- continued beacon recovery with Patch B alone
- operation of combined Patch A+B on real hardware
- absence of the targeted periodic mDNS cycle from the combined device during
  the monitored capture window
- absence of recurring beacon recovery from the combined device during the
  monitored multi-hour runtime period

## Strongly supported experimental interpretation

The isolated Patch-B test supports the following statement:

> Periodic mDNS restart activity is not required for the observed recurring
> beacon-recovery cycle under the tested conditions.

This does not establish universal independence under every possible network or
firmware state.

## Plausible but not quantitatively proven

Examples:

- electrical energy cost of beacon recovery
- electrical energy cost of periodic mDNS restart
- battery-life effect of either mechanism
- combined battery-life effect of Patch A+B
- frequency of the conditional WUP / EM2 retention failure in real operation
- possible indirect interactions under conditions not yet tested

## Not established

The project does not currently claim:

- that the complete battery-drain problem has been solved
- that Patch A+B restores a specific battery lifetime
- that one mechanism explains all historical battery drain
- that firmware 2.1.3 is battery-drain free
- that firmware 2.1.8 introduced the original battery-drain problem
- that mDNS is the sole cause of battery drain
- that beacon recovery is the sole cause of battery drain
- that firmware 2.1.0 never emits mDNS traffic
- that Patch A and Patch B are universally independent under every condition
- that battery percentage directly represents precise consumed energy

---

# Documentation

Detailed research notes are maintained under:

```text
docs/

├── patch/
│   └── README.md
│
├── reverse-engineering/
│   ├── ap-selection-and-roaming.md
│   ├── beacon-rx-counter.md
│   ├── firmware-comparison.md
│   ├── mdns-periodic-restart.md
│   ├── power-management-and-sleep.md
│   ├── real-beacon-skip.md
│   └── recovery-mechanism.md
│
└── testing/
    ├── battery-testing.md
    └── mdns-runtime-comparison.md
```

The reverse-engineering documents describe the firmware mechanisms.

The testing documents describe runtime observations and experimental validation.

The documentation will continue to be updated as the long-term battery dataset
grows.

---

# Firmware Patcher

A separate repository contains the local patching tool for the combined
experimental firmware modification.

Repository:

```text
https://github.com/AbleMonster/Shelly-TRV-Gen1-2.2.4-patcher
```

The current experimental release is:

```text
v1.0.0-beta.2
```

The patcher currently applies:

```text
Patch A
Beacon-recovery bypass

+

Patch B
Periodic mDNS restart bypass
```

The tool uses a fail-closed validation model.

It verifies the exact supported original firmware before modification and
checks the expected:

- firmware size
- SHA-256
- GBL CRC32
- GBL tag structure
- program image
- original patch instructions
- resulting program hash
- resulting GBL hash
- resulting GBL CRC32
- final byte differences

The supported original GBL has:

```text
Size:
1,106,384 bytes

SHA-256:
5c4a0b222a313350952f6b1200a855833402f168bd286090c23bd4d018ab918f

CRC32:
0xDC7BAB58
```

The validated combined output has:

```text
Size:
1,106,384 bytes

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61

CRC32:
0xBAEB8265
```

The patcher does **not** distribute Shelly firmware.

Users must provide their own legally obtained supported firmware image.

The patched firmware is generated locally.

No original or modified Shelly firmware image is distributed through the
research or patcher repositories.

---

# Local OTA Testing

The separate patcher project also contains a local OTA HTTP server.

The server:

- validates the expected combined patched firmware
- serves the firmware locally
- supports HTTP/1.1
- supports byte-range requests
- returns `206 Partial Content` for Range requests
- does not download or distribute firmware itself

The complete local workflow has been tested:

```text
original supported GBL
        ↓
local patcher
        ↓
validated A+B GBL
        ↓
local OTA server
        ↓
HTTP transfer
        ↓
SHTRV-01 OTA installation
        ↓
firmware 2.2.4 boots
```

Both normal HTTP transfer and byte-range behavior have been validated.

Successful HTTP transfer alone should not be interpreted as proof of successful
firmware installation.

Post-installation device status and runtime behavior must be verified
separately.

---

# Repository Scope

This repository is intended to contain:

- analysis results
- technical documentation
- experimental methodology
- small patch descriptions
- tooling written specifically for this research
- sanitized runtime results
- long-term battery-test methodology and conclusions

It is not intended to redistribute proprietary Shelly firmware.

Original firmware binaries, patched firmware binaries, large disassembly dumps
and unreviewed reverse-engineering output should not be committed.

The general rule is:

> Publish the results of the analysis, not the disassembled firmware.

---

# Safety and Experimental Nature

All firmware modifications in this project are experimental.

A modified firmware image can potentially:

- make a device unreachable
- cause unexpected WLAN behavior
- require recovery or reflashing
- affect battery life
- affect normal thermostat operation

Do not deploy experimental firmware to devices where failure could create an
unsafe condition.

Always retain a known-good firmware image and a recovery path.

---

# Current Conclusions

The investigation has established several important facts.

### Firmware 2.2.4 contains a recurring beacon-recovery mechanism

This mechanism can repeatedly place the WLAN subsystem into a temporary
active / always-on state.

On affected test devices it has been observed at approximately one event per
minute.

The mechanism can be bypassed experimentally using Patch A.

### Periodic mDNS restart behavior appeared after firmware 2.1.0

Static analysis identified the recurring caller in firmware 2.1.3.

Runtime packet capture confirmed the resulting network traffic.

### The mDNS period changed in later firmware

Observed runtime behavior:

```text
2.1.0        no periodic burst observed during ~13 min
2.1.3        ~60-second periodic mDNS burst
2.2.4 stock  ~180-second periodic mDNS burst
```

### The periodic 2.2.4 mDNS restart can be bypassed

Patch B suppresses the targeted periodic restart call.

During the isolated Patch-B runtime test, the characteristic periodic mDNS
traffic was not observed during the monitored packet-capture window.

Normal connectivity remained available.

### Suppressing periodic mDNS does not suppress beacon recovery

The Patch-B-only `.77` device continued to enter the recurring beacon-recovery
path at approximately one event per minute.

This occurred even at good RSSI with desired beacon skip 20.

The periodic mDNS restart is therefore not required for the observed
beacon-recovery cycle under the tested conditions.

### Patch A and Patch B can operate together

The combined A+B firmware has been installed and run successfully on real
SHTRV-01 hardware.

During the monitored tests:

```text
periodic mDNS restart   not observed
beacon recovery         not observed
normal connectivity     operational
normal TRV operation    operational
```

Long-term stability testing continues.

### A conditional WLAN sleep-resource retention path exists

However, the fundamental path already exists in firmware 2.1.0 and therefore
cannot by itself explain the later battery-runtime regression.

### The battery-drain problem is not yet proven solved

This remains the most important limitation.

Patch A removes a confirmed recurring WLAN recovery workload.

Patch B removes a confirmed recurring mDNS workload.

The combined patch removes both targeted behaviors during the observed tests.

However:

```text
removing unnecessary recurring activity
```

is not equivalent to:

```text
proving the historical battery-drain problem is solved
```

Current battery observations remain mixed.

Some beacon-patched devices have continued to lose noticeable battery voltage
despite the recovery counter remaining at zero.

The combined A+B device has shown encouraging initial behavior, but the
observation period is still too short for a battery-life conclusion.

The strongest current interpretation therefore remains that several mechanisms
may contribute to total battery consumption.

Their individual electrical contribution remains unknown.

---

# Current Research Direction

The mechanism-isolation phase has now answered several important questions.

The project is moving into a broader long-term battery comparison.

The next experimental phase will use:

```text
stock 2.2.4 control
        versus
multiple A+B patched devices
```

with batteries charged as consistently as practical before the comparison.

The main measurements will include:

- battery voltage
- reported battery percentage
- uptime
- unexpected reboots
- RSSI
- beacon statistics
- beacon-recovery counter
- valve / motor activity
- motor steps
- firmware / patch configuration

The stock reference device should remain unchanged throughout this comparison.

The goal is not merely to determine whether the patches function.

That has already been demonstrated for the targeted mechanisms.

The next question is:

> Does removing the two confirmed recurring workloads produce a reproducible
> improvement in real battery behavior over an extended observation period?

A positive answer requires long-term data.

Until those data exist, the combined A+B firmware remains experimental.

---

# Research Principle

This project intentionally separates:

```text
observation
    ↓
reverse engineering
    ↓
hypothesis
    ↓
controlled modification
    ↓
runtime validation
    ↓
long-term observation
```

A plausible mechanism is not treated as a proven battery-drain cause until the
available evidence supports that conclusion.

Likewise:

```text
Patch works
```

means only that the targeted firmware behavior has been modified as intended.

It does not automatically mean:

```text
Battery drain fixed
```

That distinction will remain central to the project as the long-term testing
continues.