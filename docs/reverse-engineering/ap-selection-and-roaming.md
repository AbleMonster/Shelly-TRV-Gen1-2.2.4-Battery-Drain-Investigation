# Access Point Selection and Roaming Analysis

## Scope

This document describes the investigation of access-point selection and roaming
behavior in Shelly TRV Gen1 firmware.

The analysis focuses primarily on firmware 2.2.4, with relevant
version-comparison results from:

- 2.1.0
- 2.1.3
- 2.1.8
- 2.2.4

The purpose is to determine:

- how the TRV selects an access point during connection establishment
- whether the Shelly host application itself selects the strongest access point
- which BSSID and channel are supplied during connection establishment
- whether the TRV can switch to another access point while already connected
- what the `prevent_roaming` parameter controls
- what happens after an actual connection loss
- how RSSI affects normal beacon power saving
- whether AP selection is required for the observed 2.2.4 beacon-recovery loop
- and what relevance these mechanisms may have to battery consumption

This document intentionally separates:

```text
host application behavior
```

from:

```text
protected WF200 behavior
```

because the exact internal AP-selection and roaming policy of the WF200 cannot
be completely reconstructed from the host application image.

No firmware images, complete proprietary functions or complete disassemblies
are reproduced here.

---

# 1. Summary

The Shelly host application does not explicitly select a particular access
point based on strongest RSSI during normal connection establishment.

The WLAN scan can expose multiple BSSIDs and their RSSI values.

However, the subsequent CONNECT request uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

The host therefore does not pass one specific scanned BSSID or channel to the
connection request.

Concrete initial AP selection is delegated to the WLAN/WF200 subsystem.

At the same time, the application sets:

```text
prevent_roaming = 1
```

Public Silicon Labs interface information indicates that this prevents
autonomous firmware-managed roaming after association.

No separate host-side background mechanism was identified that periodically:

```text
scans for stronger AP
        |
        v
selects stronger BSSID
        |
        v
forces reassociation
```

Therefore a weak but still functional AP can potentially remain associated for
an extended period.

After an actual connection loss, the application returns to the normal
scan-and-wildcard-CONNECT path, allowing the WLAN subsystem to select a
compatible AP again.

RSSI affects the normal desired beacon-skip configuration:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

However, later runtime testing established an important constraint:

> The recurring firmware-2.2.4 beacon-recovery mechanism can occur with good
> RSSI and `desired_beacon_skip = 20`.

Therefore poor AP selection or weak RSSI is **not required** for the observed
beacon-recovery loop.

AP selection remains potentially relevant to general WLAN energy consumption,
but it is not currently established as a root cause of the battery-drain
problem.

---

# 2. WLAN Scan

Before establishing a connection, the firmware performs a WLAN scan.

Multiple access points or BSSIDs advertising the configured SSID may appear in
the scan results.

The scan information includes values such as:

```text
SSID
BSSID
Channel
RSSI
```

The host application can therefore observe that multiple BSSIDs exist for the
same SSID.

However, no host-side logic was identified that:

1. collects matching BSSIDs
2. ranks them by RSSI
3. selects the strongest result
4. copies that BSSID into the subsequent CONNECT request

Scan results are retained in arrival order.

No established data-flow path was found equivalent to:

```text
strongest matching scan result
        |
        v
CONNECT BSSID
```

Likewise, no established path was found for:

```text
first matching scan result
        |
        v
CONNECT BSSID
```

## Evidence status

| Finding | Status |
|---|---|
| Scan results contain BSSID, channel and RSSI | **PROVEN** |
| Host explicitly selects strongest matching scan result | **NOT OBSERVED** |
| Host explicitly selects first matching scan result | **NOT OBSERVED** |

---

# 3. Connection Establishment

During connection establishment, the host application supplies the configured
network information to the WLAN subsystem.

The relevant parameters are:

```text
SSID            = configured SSID
BSSID           = FF:FF:FF:FF:FF:FF
Channel         = 0
Security        = configured security mode
prevent_roaming = 1
Password        = configured password
```

The wildcard BSSID:

```text
FF:FF:FF:FF:FF:FF
```

means that the host does not request one specific access point.

Likewise:

```text
Channel = 0
```

does not constrain the connection request to one specific WLAN channel.

The division of responsibility is therefore:

```text
Shelly host application
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

## Evidence status

**PROVEN**

---

# 4. Initial Access-Point Selection

Because the host does not pass a specific BSSID or channel, the final initial
AP selection occurs below the Shelly application layer.

The exact internal WF200 selection algorithm remains unresolved.

Possible internal criteria could include:

- signal strength
- scan-result ordering
- previously associated AP
- previously used channel
- internal scan cache
- security or capability matching
- channel preferences
- internal connection history

These are possible implementation factors, not established findings.

No evidence was found that the Shelly host itself performs this ranking.

Therefore:

```text
host chooses strongest AP
```

is not supported.

Likewise:

```text
WF200 always chooses strongest AP
```

has not been established.

## Evidence status

| Finding | Status |
|---|---|
| Host does not explicitly specify one BSSID | **PROVEN** |
| Concrete initial selection is delegated below the host application | **PROVEN** |
| Exact WF200 AP-ranking strategy | **UNRESOLVED** |
| WF200 always selects strongest AP | **NOT PROVEN** |
| WF200 always selects first scan result | **NOT PROVEN** |

---

# 5. Previous AP Information

The analysis also examined whether previously associated BSSID or channel
information is reused during later reconnects.

Old BSSID-related information may remain in host-side state or RAM.

However, no identified host-side consumer uses this retained information to
constrain the next CONNECT request.

No established path was found equivalent to:

```text
previous BSSID
        |
        v
next CONNECT BSSID
```

or:

```text
previous channel
        |
        v
next CONNECT channel
```

The reconnect path again uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

It remains possible that the protected WF200 subsystem internally retains
connection history or scan state.

That behavior cannot be established from the analyzed host application.

## Evidence status

| Finding | Status |
|---|---|
| Host explicitly reuses previous BSSID for reconnect | **NOT OBSERVED** |
| Host explicitly reuses previous channel for reconnect | **NOT OBSERVED** |
| WF200 may internally retain AP-selection state | **UNRESOLVED** |

---

# 6. `prevent_roaming`

During connection establishment, the host sets:

```text
prevent_roaming = 1
```

Public Silicon Labs WLAN interface information establishes the relevant
distinction:

```text
prevent_roaming = 1
```

prevents autonomous firmware-controlled roaming.

By contrast:

```text
prevent_roaming = 0
```

permits autonomous firmware-controlled roaming.

This parameter should not be overinterpreted.

Setting:

```text
prevent_roaming = 0
```

does not establish:

```text
always use strongest AP
```

and does not reveal:

- roaming RSSI threshold
- hysteresis
- candidate ranking
- scan timing
- reassociation policy

Those decisions remain part of the internal WLAN implementation.

## Evidence status

| Finding | Status |
|---|---|
| Stock firmware sets `prevent_roaming = 1` | **PROVEN** |
| `prevent_roaming = 1` prevents autonomous WLAN-firmware roaming | **PROVEN** |
| `prevent_roaming = 0` permits autonomous roaming | **PROVEN** |
| `prevent_roaming = 0` guarantees strongest-AP selection | **NOT PROVEN** |
| Exact WF200 roaming thresholds and policy | **UNRESOLVED** |

---

# 7. Host-Side Roaming

No separate host-side mechanism was identified that periodically scans for a
better access point and forces reassociation based only on RSSI.

No identified control flow corresponds to:

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

This is distinct from the reconnect path after an actual connection loss.

The host therefore appears to rely on:

```text
existing association
```

until either:

- the connection fails
- another subsystem requests a reconnect
- the WLAN subsystem changes association autonomously, if permitted

With stock:

```text
prevent_roaming = 1
```

the last case is intentionally prevented.

## Evidence status

| Finding | Status |
|---|---|
| RSSI-based host roaming | **NOT OBSERVED** |
| Background strongest-BSSID selection by host | **NOT OBSERVED** |

---

# 8. Weak-but-Functional AP Retention

The stock configuration permits a potentially important scenario.

Consider:

```text
AP A
RSSI ~ -80 dBm
currently associated

AP B
same SSID
RSSI ~ -55 dBm
also available
```

If AP A remains functional:

- autonomous roaming is prevented by `prevent_roaming = 1`
- no host-side stronger-AP selection mechanism was identified
- weak RSSI changes the requested beacon-skip configuration
- weak RSSI alone was not found to force host-side reassociation

Therefore continued association with a weaker but still functional AP is
technically possible.

This does not prove that a particular tested TRV remained associated with a
weaker AP.

Direct observation of the associated BSSID is required for that conclusion.

## Evidence status

Weak-but-functional AP retention:

**STRONG INFERENCE**

Specific tested TRV proven to remain on weaker AP:

**NOT PROVEN**

---

# 9. Behavior After Connection Loss

After an actual WLAN connection loss, the application clears the connected
state and returns to its normal connection procedure.

The subsequent request again uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

No host-side mechanism was identified that explicitly:

- retries the previous BSSID first
- retries the previous channel first
- chooses the strongest scan result itself

Therefore a reconnect provides the WLAN subsystem with another opportunity to
select a compatible AP.

Conceptually:

```text
existing association
        |
        v
connection loss
        |
        v
scan
        |
        v
wildcard CONNECT
        |
        v
WF200 selects compatible AP
```

An AP change can therefore occur after reconnect even though autonomous roaming
was disabled during the previous established connection.

## Evidence status

| Finding | Status |
|---|---|
| Reconnect returns to wildcard CONNECT | **PROVEN** |
| Reconnect can provide an opportunity for another AP to be selected | **PROVEN** |
| Reconnect necessarily selects another AP | **NOT PROVEN** |
| Exact WF200 reconnect selection criteria | **UNRESOLVED** |

---

# 10. RSSI Representation

The RSSI used by the firmware originates from the WLAN subsystem's signal
strength information.

The relevant host-side conversion is approximately:

```text
RSSI = ((uint8_t)RCPI >> 1) - 110
```

However, `/status` does not request a completely new radio measurement for
every HTTP request.

The status interface reports a previously stored RSSI value.

The underlying WLAN interface describes RCPI as being derived from recently
received packets.

Therefore:

```text
scan RSSI
```

and:

```text
/status RSSI
```

must not automatically be treated as identical measurements.

They can represent:

- different times
- different measurement contexts
- different averaging histories

This is particularly important when attempting to infer an AP change from an
RSSI jump.

---

# 11. RSSI and Desired Beacon Skip

RSSI directly controls the normal `desired_beacon_skip` value.

The mapping is:

```text
RSSI >= -69 dBm
desired_beacon_skip = 20

RSSI -70 ... -79 dBm
desired_beacon_skip = 15

RSSI < -79 dBm
desired_beacon_skip = 10
```

These thresholds control WLAN beacon power-saving configuration.

No evidence was found that the same thresholds directly trigger:

```text
scan
```

or:

```text
AP reassociation
```

Therefore:

```text
weak RSSI
        |
        v
lower desired_beacon_skip
```

is established.

But:

```text
weak RSSI
        |
        v
host changes AP
```

was not observed.

---

# 12. Nominal Beacon-Listening Intervals

The configured skip values correspond to different nominal beacon-listening
opportunities.

The current interpretation is:

```text
desired_beacon_skip = 20
-> approximately every 21st beacon

desired_beacon_skip = 15
-> approximately every 16th beacon

desired_beacon_skip = 10
-> approximately every 11th beacon
```

Therefore:

```text
21 / 11 ~= 1.91
```

Skip 10 represents approximately 1.91 times as many nominal listening
opportunities as skip 20.

Likewise:

```text
21 / 16 ~= 1.31
```

Skip 15 represents approximately 1.31 times as many nominal listening
opportunities as skip 20.

These ratios describe nominal WLAN beacon-listening opportunities only.

They do not directly describe:

- total WLAN energy consumption
- total device energy consumption
- host-MCU wake frequency
- RF transmit activity
- battery-life reduction

---

# 13. Host MCU vs. WF200 Beacon Listening

The examined skip values use the same host-side sleep-release architecture.

No separate host-MCU power-state path was identified for:

```text
skip 10
skip 15
skip 20
```

Connection-maintenance activity can also be handled internally by the WLAN
subsystem without requiring a host-MCU wake for every radio event.

Therefore:

```text
more WF200 beacon-listening opportunities
```

does not imply:

```text
the same proportional increase in host-MCU wakeups
```

A lower skip value is expected to increase radio-side listening opportunities.

The exact electrical effect on the complete TRV has not been measured.

## Evidence status

| Finding | Status |
|---|---|
| Same host sleep-release architecture for skip 10/15/20 | **PROVEN** |
| Every additional beacon listen wakes host MCU | **NOT SUPPORTED** |
| Lower skip increases nominal WF200 listening opportunities | **PROVEN** |
| Proportional increase in total-device power | **NOT PROVEN** |

---

# 14. Associated BSSID Visibility

The MAC address normally exposed by the TRV through HTTP is the TRV's own MAC
address.

It is not the BSSID of the currently associated access point.

However, the successful WLAN connection indication contains the actual
association information.

The relevant `CONNECT_IND` event contains:

```text
BSSID
Channel
```

The host receives this information after successful association.

The event structure is later released and the BSSID is not normally exposed
through `/status`.

Therefore `CONNECT_IND` provides a suitable diagnostic observation point.

Conceptually:

```text
WF200 selects AP
        |
        v
successful CONNECT_IND
        |
        +---- BSSID
        |
        +---- Channel
        |
        v
host processes event
```

A diagnostic modification could capture this information without modifying AP
selection itself.

## Evidence status

| Finding | Status |
|---|---|
| Actual associated BSSID is present in successful `CONNECT_IND` | **PROVEN** |
| Associated channel is present in successful `CONNECT_IND` | **PROVEN** |
| Associated BSSID is exposed through `/status` | **NO** |
| Diagnostic observation point exists | **PROVEN** |

---

# 15. Real-Device RSSI Observations

Real-device testing has shown substantial RSSI changes around connection or
re-establishment events.

Such changes are compatible with a different AP being selected.

However:

```text
RSSI change
```

does not prove:

```text
BSSID change
```

because RSSI can also vary because of:

- device orientation
- propagation changes
- environmental conditions
- measurement timing
- RCPI averaging
- RF interference

The firmware nevertheless provides a plausible mechanism for an AP change
after reconnect:

```text
connection loss / restart
        |
        v
new scan
        |
        v
wildcard CONNECT
        |
        v
WF200 selects compatible AP
```

Direct BSSID observation remains necessary to prove that a particular RSSI
jump corresponds to a different AP.

---

# 16. AP Selection and Energy Consumption

AP selection is potentially relevant to battery consumption because radio
conditions influence the normal power-save configuration.

A supported chain is:

```text
AP selection / retention
        |
        v
actual RF conditions
        |
        v
RSSI
        |
        v
desired_beacon_skip
        |
        v
nominal beacon-listening frequency
```

The links can be classified as:

```text
AP selection -> resulting RF conditions / RSSI
STRONG INFERENCE

RSSI -> desired_beacon_skip
PROVEN

desired_beacon_skip -> nominal listening opportunities
PROVEN

lower skip -> more nominal WF200 listening opportunities
PROVEN

additional WLAN activity -> additional electrical energy
PLAUSIBLE

additional energy -> observed long-term battery drain
UNRESOLVED
```

Other possible weak-signal costs include:

```text
weak RF conditions
        |
        v
packet retransmissions
```

and:

```text
weak RF conditions
        |
        v
connection instability
        |
        v
scan / reconnect
```

These mechanisms are technically plausible, but their contribution to the
observed long-term battery drain has not been quantified.

---

# 17. AP Selection and Beacon Recovery

AP selection and the 2.2.4 beacon-recovery mechanism are separate mechanisms.

The possible interaction is:

```text
AP selection / retention
        |
        v
actual WLAN conditions
        |
        +-------------------------+
        |                         |
        v                         v
       RSSI                beacon reception
        |                    statistics
        v                         |
desired_beacon_skip              v
        |                  beacon_rx_count
        v                         |
normal listening                 v
configuration              real_beacon_skip
                                  |
                                  v
                           recovery predicate
                                  |
                                  v
                            temporary state 1
```

The following relationships are established:

- RSSI controls `desired_beacon_skip`
- `desired_beacon_skip` controls the requested normal beacon-listening policy
- `beacon_rx_count` is used in the `real_beacon_skip` calculation
- qualifying `real_beacon_skip` values can trigger recovery
- recovery requests temporary Active / Always-On WLAN operation
- recovery temporarily restricts deeper host sleep states

However, the complete chain:

```text
poor AP selection
        |
        v
poor RSSI
        |
        v
beacon recovery
```

is not required by the observed runtime behavior.

---

# 18. Recovery at Good RSSI

Later runtime testing provided a particularly important result.

A firmware-2.2.4 device running the isolated periodic-mDNS patch continued to
show recurring:

```text
Beacon skip error! Attempt recovery
```

while reported RSSI was approximately:

```text
-58 to -59 dBm
```

At this signal strength, the normal policy selected:

```text
desired_beacon_skip = 20
```

The recovery sequence still occurred approximately once per minute.

This establishes:

> Weak RSSI is not a necessary condition for the observed 2.2.4
> beacon-recovery loop.

It also weakens the hypothesis that the recurring recovery is primarily a
consequence of a TRV being trapped on a weak access point.

This does not establish that RF conditions are completely irrelevant to beacon
statistics.

It establishes only that the known recurring recovery can occur without weak
RSSI.

## Evidence status

**RUNTIME CONFIRMED**

---

# 19. Consequence for the Battery-Drain Investigation

Before the good-RSSI runtime result, a plausible working hypothesis was:

```text
weak AP retained
        |
        v
weak RSSI
        |
        v
lower desired beacon skip
        |
        v
abnormal beacon statistics
        |
        v
recovery
        |
        v
additional battery consumption
```

The later runtime result requires this model to be revised.

The better-supported model is:

```text
                AP selection
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
        normal WLAN energy cost
```

while the 2.2.4 recovery mechanism has a separate input:

```text
WF200 beacon statistics
        |
        v
beacon_rx_count delta
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        v
state 1 recovery
```

The two paths may interact through the underlying WLAN environment, but poor
RSSI is not required for the second path.

Therefore AP selection is no longer a leading explanation for the recurring
2.2.4 recovery loop.

---

# 20. Version Comparison

The relevant host-side AP-selection behavior was compared across the analyzed
firmware versions.

The important connection characteristics remain substantially consistent:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```

No version-specific host-side strongest-AP selection mechanism was identified.

Therefore the current analysis does not provide evidence that a new
host-controlled AP-selection policy was introduced at the known firmware
boundaries associated with the battery investigation.

This is important because:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

should not be differentiated on the basis of a host-side strongest-AP
algorithm that has not been found.

The protected WF200 image does change at later version boundaries, so internal
WLAN behavior cannot be assumed to be identical across every version.

---

# 21. Protected WF200 Boundary

The exact AP-selection and roaming implementation resides partly inside the
protected WLAN subsystem.

Within the analyzed firmware set:

```text
2.1.0
2.1.3
```

use the same protected WF200 image.

The protected image changes in:

```text
2.1.8
```

and changes again in:

```text
2.2.4
```

Therefore:

```text
same host CONNECT parameters
```

does not necessarily prove:

```text
identical internal AP-selection behavior
```

across all four versions.

For example, the protected firmware could theoretically change:

- scan-result ranking
- cached-AP preference
- retry strategy
- roaming implementation
- association timing

without changing the visible host CONNECT parameters.

No such specific protected-firmware AP-selection change has currently been
established.

---

# 22. Roaming-Patch Feasibility

Static analysis identified the application-side `prevent_roaming` assignment
as a technically minimal experimental modification.

Stock behavior supplies:

```text
prevent_roaming = 1
```

A modification to:

```text
prevent_roaming = 0
```

would permit autonomous WF200 roaming.

The identified host-side modification is compatible with a minimal
single-immediate change.

However, such a patch would not:

- implement a custom strongest-AP algorithm
- guarantee selection of the strongest AP
- reveal the WF200 roaming threshold
- guarantee lower power consumption
- correct the 2.2.4 beacon-statistics interpretation
- suppress the known beacon-recovery mechanism

Therefore the technical feasibility of the modification should be separated
from its research priority.

## Evidence status

Minimal host-side roaming modification feasible:

**PROVEN**

Result would always select strongest AP:

**NOT PROVEN**

Battery improvement:

**UNRESOLVED**

---

# 23. Why a Roaming Patch Is Not Currently a Priority

The later battery-drain investigation changed the experimental priority.

The recurring 2.2.4 recovery mechanism has now been observed with:

```text
good RSSI
desired_beacon_skip = 20
```

and the recovery can be directly suppressed using the isolated beacon-recovery
Patch A.

Periodic mDNS activity can independently be suppressed using Patch B.

This provides cleaner experimental isolation than changing AP behavior.

A roaming patch would introduce another variable:

```text
different association policy
        |
        v
possibly different AP
        |
        v
different RF conditions
        |
        v
different WLAN workload
```

That could make battery comparisons harder to interpret.

Therefore a roaming patch remains technically interesting, but is not
currently required for the main battery-drain experiment.

---

# 24. Diagnostic BSSID Instrumentation

If AP-selection behavior becomes relevant again, diagnostic instrumentation is
preferable to immediately changing roaming policy.

The successful connection event already contains:

```text
BSSID
Channel
```

A diagnostic build could capture:

```text
timestamp
BSSID
channel
RSSI
```

when association succeeds.

This would directly answer:

```text
Which AP did the TRV actually associate with?
```

without modifying:

- AP selection
- roaming policy
- RSSI thresholds
- beacon-skip policy
- beacon recovery

This is a cleaner experiment than inferring AP changes from RSSI alone.

---

# 25. Suggested Future AP Experiment

AP-specific testing is not currently required for the main Patch A+B battery
comparison.

If AP behavior is investigated later, the clean sequence would be:

## Phase 1 — Diagnostic observation

Record the actual associated:

```text
BSSID
Channel
RSSI
```

without changing connection behavior.

## Phase 2 — Weak-AP retention test

Create:

```text
AP A
weak but functional

AP B
same SSID
substantially stronger
```

while the TRV remains associated.

Observe whether the BSSID changes.

With stock:

```text
prevent_roaming = 1
```

no autonomous WF200 roaming is expected.

## Phase 3 — Reconnect test

Make the current AP unavailable and observe:

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

## Phase 4 — Optional roaming experiment

Only if needed, compare:

```text
prevent_roaming = 1
```

against:

```text
prevent_roaming = 0
```

while recording the same WLAN and battery-related metrics.

This sequence separates observation from intervention.

---

# 26. Evidence Classification

| Finding | Status |
|---|---|
| TRV scan can observe multiple BSSIDs advertising the same SSID | **PROVEN** |
| Scan results contain BSSID, channel and RSSI | **PROVEN** |
| Host explicitly selects strongest scan result | **NOT OBSERVED** |
| Host explicitly selects first scan result | **NOT OBSERVED** |
| CONNECT uses wildcard BSSID | **PROVEN** |
| CONNECT uses channel 0 | **PROVEN** |
| Concrete initial AP selection is delegated below the host application | **PROVEN** |
| Exact internal WF200 AP-ranking algorithm is known | **UNRESOLVED** |
| Host reuses previous BSSID to constrain reconnect | **NOT OBSERVED** |
| Host reuses previous channel to constrain reconnect | **NOT OBSERVED** |
| WF200 may internally retain AP-selection state | **UNRESOLVED** |
| Stock firmware sets `prevent_roaming = 1` | **PROVEN** |
| `prevent_roaming = 1` prevents autonomous WLAN-firmware roaming | **PROVEN** |
| `prevent_roaming = 0` permits autonomous roaming | **PROVEN** |
| `prevent_roaming = 0` guarantees strongest-AP selection | **NOT PROVEN** |
| Host performs background strongest-BSSID roaming | **NOT OBSERVED** |
| Weak-but-functional AP retention is technically possible | **STRONG INFERENCE** |
| Connection loss returns to scan + wildcard CONNECT | **PROVEN** |
| Reconnect provides another opportunity for AP selection | **PROVEN** |
| RSSI controls `desired_beacon_skip` | **PROVEN** |
| RSSI thresholds directly trigger AP change | **NOT OBSERVED** |
| Skip 20 corresponds nominally to approximately every 21st beacon | **PROVEN** |
| Skip 15 corresponds nominally to approximately every 16th beacon | **PROVEN** |
| Skip 10 corresponds nominally to approximately every 11th beacon | **PROVEN** |
| Skip 10 provides approximately 1.91x the nominal listening opportunities of skip 20 | **PROVEN** |
| Lower skip necessarily wakes host MCU proportionally more often | **NOT SUPPORTED** |
| Lower skip increases nominal WF200 listening opportunities | **PROVEN** |
| Lower skip causes proportional total-device power increase | **NOT PROVEN** |
| Associated BSSID is present in successful `CONNECT_IND` | **PROVEN** |
| Associated BSSID is exposed through `/status` | **NO** |
| Recurring 2.2.4 beacon recovery can occur with good RSSI | **RUNTIME CONFIRMED** |
| Weak RSSI is required for recurring beacon recovery | **DISPROVEN FOR TESTED CONDITIONS** |
| Poor AP selection is required for recurring beacon recovery | **NOT SUPPORTED** |
| Minimal `prevent_roaming` modification is technically feasible | **PROVEN** |
| Roaming modification would improve battery life | **UNRESOLVED** |
| AP-selection policy causes the historical battery drain | **NOT PROVEN** |

---

# 27. Remaining Open Questions

The main unresolved AP-selection questions are now:

1. What exact criteria does the WF200 use during wildcard AP selection?
2. Does the WF200 internally prefer a previously associated AP?
3. What thresholds and hysteresis would control autonomous roaming if
   `prevent_roaming = 0`?
4. Do large observed RSSI changes on real devices correspond to actual BSSID
   changes?
5. How frequently does weak-AP retention occur in real multi-AP or mesh
   environments?
6. What is the quantitative electrical cost of operating at skip 10 versus
   skip 15 or skip 20?
7. How much do retransmissions and reconnects contribute under poor RF
   conditions?
8. Does internal AP-selection behavior differ between the protected WF200
   images used by 2.1.3, 2.1.8 and 2.2.4?
9. Would permitting autonomous roaming materially change long-term battery
   consumption?
10. Do RF conditions affect the WF200 beacon statistics involved in
    `real_beacon_skip`, even though weak RSSI is not required for recovery?

The last question is particularly important.

The good-RSSI result shows that:

```text
weak RSSI
```

is not necessary for recovery.

It does not prove that:

```text
RF conditions
```

have no influence on the underlying beacon statistics.

---

# 28. Current Research Priority

For the main battery-drain investigation, AP-selection modification is
currently secondary.

The higher-priority comparison is:

```text
stock 2.2.4
```

against controlled experimental variants:

```text
Patch A
beacon-recovery suppression

Patch B
periodic mDNS restart suppression

Patch A+B
both targeted recurring mechanisms suppressed
```

This provides cleaner causal isolation than changing roaming behavior.

AP-selection research remains useful for:

- understanding WLAN behavior
- explaining RSSI variation
- evaluating weak-signal energy costs
- investigating mesh behavior
- interpreting reconnect events

but should currently remain separate from the primary patch validation.

---

# 29. Current Model

The current WLAN model is:

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
          +----------+----------+
          |                     |
          v                     v
     RSSI changes        connection loss
          |                     |
          v                     v
 desired_beacon_skip          scan
          |                     |
          v                     v
 normal WLAN             wildcard CONNECT
 power saving                  |
                                v
                        AP selected again
```

A separate 2.2.4 mechanism is:

```text
WF200 beacon statistics
        |
        v
beacon_rx_count
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        v
temporary state 1
```

The two mechanisms share the WLAN environment but must not be treated as the
same control path.

---

# 30. Current Conclusion

The Shelly TRV host application does not explicitly select the strongest access
point during normal connection establishment.

Instead it uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

and delegates concrete AP selection to the WLAN/WF200 subsystem.

The stock firmware also sets:

```text
prevent_roaming = 1
```

which prevents autonomous firmware-controlled roaming after association.

No separate host-side mechanism was identified that periodically moves an
established connection to a stronger AP.

Consequently, retention of a weak but functional AP is technically possible.

Weak RSSI then affects normal WLAN power saving by reducing
`desired_beacon_skip`.

However, later runtime testing established that the recurring 2.2.4
beacon-recovery loop also occurs with good RSSI and:

```text
desired_beacon_skip = 20
```

Therefore:

> Weak RSSI and poor AP selection are not necessary conditions for the known
> recurring beacon-recovery behavior.

This substantially reduces the likelihood that AP retention alone explains the
2.2.4 recovery loop.

AP selection can still affect WLAN energy consumption through normal radio
conditions, beacon-listening frequency, retransmissions and reconnects.

Its quantitative contribution to the historical battery-drain problem remains
unresolved.

For the current research phase, direct comparison of stock firmware with the
isolated and combined recurring-activity patches provides a cleaner experiment
than modifying roaming behavior.

---

# Related Documents

- [`Firmware Comparison`](firmware-comparison.md)
- [`Power Management and Sleep`](power-management-and-sleep.md)
- [`Beacon RX Counter`](beacon-rx-counter.md)
- [`Real Beacon Skip`](real-beacon-skip.md)
- [`Recovery Mechanism`](recovery-mechanism.md)
- [`Periodic mDNS Restart`](mdns-periodic-restart.md)
- [`Experimental Beacon-Recovery Patch`](../patch/README.md)
- [`Battery Testing`](../testing/battery-testing.md)

---

# Research Methodology

This investigation is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware images together with runtime observations from
personally owned devices.

The analysis includes:

- WLAN scan handling
- CONNECT parameter construction
- disconnect and reconnect handling
- RSSI and RCPI processing
- power-management interaction
- successful `CONNECT_IND` handling
- firmware-version comparison
- runtime observation of RSSI and beacon recovery

Publicly available Silicon Labs WF200/fullMAC information was used where
necessary to interpret host-visible WLAN interface parameters.

The internal protected WF200 AP-ranking and roaming implementation is not
reproduced and cannot be completely determined from the host application.

No firmware images, complete proprietary functions or complete disassemblies
are published in this document.

The classifications:

```text
PROVEN
RUNTIME CONFIRMED
STRONG INFERENCE
PLAUSIBLE
NOT OBSERVED
NOT SUPPORTED
NOT PROVEN
UNRESOLVED
```

are deliberately used to distinguish direct static evidence, runtime evidence
and interpretation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the tested firmware versions.

No conclusions about the intentions of the original developers are inferred
from these technical findings.