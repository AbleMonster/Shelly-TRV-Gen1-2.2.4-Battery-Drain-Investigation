# Access Point Selection and Roaming Analysis

## Scope

This document describes the investigation of access-point selection, roaming,
reconnection, RSSI handling, and their relationship to WLAN power management
in Shelly TRV Gen1 firmware.

The analysis covers:

- firmware 2.1.0
- firmware 2.1.3
- firmware 2.1.8
- firmware 2.2.4

The main objectives are to determine:

- how the host application establishes a WLAN connection
- whether the host explicitly selects the strongest access point
- which BSSID and channel are supplied during connection
- what `prevent_roaming` controls
- whether an already associated TRV automatically moves to a stronger AP
- what happens after an actual connection loss
- how RSSI influences normal beacon power saving
- whether AP selection is required to explain the 2.2.4 Beacon Recovery behavior
- whether AP behavior may still influence battery consumption
- whether changing roaming behavior is currently justified

This document deliberately separates:

```text
Shelly host application behavior
```

from:

```text
protected WF200 / WLAN firmware behavior
```

The host application exposes important connection parameters and control flow,
but the complete internal AP-selection and roaming policy of the WF200 cannot
be reconstructed from the host image alone.

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

Runtime observations are described explicitly where relevant rather than using
a separate evidence category.

---

# 2. Summary

The Shelly TRV host application does not explicitly select one specific access
point by strongest RSSI during normal connection establishment.

The host performs or receives WLAN scan information containing:

```text
SSID
BSSID
Channel
RSSI
```

but the subsequent CONNECT request uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

The host therefore does not constrain the request to one particular scanned
BSSID or one particular channel.

Concrete initial AP selection is delegated below the Shelly application layer.

At the same time, the connection configuration uses:

```text
prevent_roaming = 1
```

which prevents autonomous WLAN-firmware roaming after association.

No separate host-side mechanism was identified that periodically:

```text
measures RSSI
    |
    v
searches for a stronger AP
    |
    v
selects another BSSID
    |
    v
forces reassociation
```

A weak but still functional AP can therefore potentially remain associated.

After an actual connection loss, the application returns to the normal
connection procedure and again issues a wildcard CONNECT request.

The WLAN subsystem then receives another opportunity to select a compatible
access point.

RSSI directly affects the normal requested beacon-skip policy:

| RSSI | `desired_beacon_skip` |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

AP selection can therefore affect normal WLAN power behavior indirectly through
the resulting RF conditions.

However, the current Beacon Recovery analysis shows that poor AP selection or
weak RSSI is not required to explain the known 2.2.4 Recovery defects.

The host-side problems currently separated as:

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

do not require persistent weak RSSI.

In particular, C2 can sustain recurring Recovery after one qualifying event
without requiring a new RF anomaly on every cycle.

AP behavior therefore remains relevant to:

```text
normal WLAN efficiency
retransmissions
connection stability
beacon-listening policy
possible conditions preceding a first qualifying measurement
```

but is no longer a leading explanation for the persistent 2.2.4 Recovery loop.

Its quantitative contribution to the historical battery-drain problem remains:

**UNKNOWN**

---

# 3. WLAN Scan

Before establishing a connection, the firmware uses WLAN scan information.

Multiple access points or BSSIDs advertising the configured SSID may appear in
the scan results.

Relevant information includes:

```text
SSID
BSSID
Channel
RSSI
```

The host application can therefore observe that multiple BSSIDs exist for the
same SSID.

However, no host-side data flow was identified that:

1. collects all matching BSSIDs
2. ranks them by RSSI
3. selects the strongest result
4. copies that BSSID into the CONNECT request

No established path equivalent to:

```text
strongest matching scan result
        |
        v
CONNECT BSSID
```

was identified.

Likewise, no established path equivalent to:

```text
first matching scan result
        |
        v
CONNECT BSSID
```

was identified.

The existence of scan results therefore does not imply that the Shelly host
application performs AP ranking itself.

### Classification

Scan results contain BSSID, channel and RSSI:

**PROVEN**

Host explicitly selects the strongest scanned BSSID:

**UNKNOWN as a hypothetical behavior; no such host-side path was identified**

Host explicitly selects the first matching BSSID:

**UNKNOWN as a hypothetical behavior; no such host-side path was identified**

---

# 4. Connection Establishment

During connection establishment, the host supplies approximately:

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

means that the host does not request one specific AP.

Likewise:

```text
Channel = 0
```

does not constrain the request to one specific WLAN channel.

The responsibility boundary is therefore:

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

### Classification

Wildcard BSSID in the examined connection path:

**PROVEN**

Channel 0 in the examined connection path:

**PROVEN**

Host does not specify one concrete AP in that CONNECT request:

**PROVEN**

Concrete AP selection occurs below the host application:

**PROVEN**

---

# 5. Initial Access-Point Selection

Because the host does not pass one specific BSSID or channel, the final initial
AP-selection decision occurs below the Shelly application layer.

The exact WF200 ranking strategy remains unknown.

Possible internal factors could include:

- RSSI
- scan-result order
- previously associated AP
- cached scan state
- security compatibility
- channel information
- connection history
- internal firmware heuristics

These are possible implementation factors only.

They are not established findings.

Therefore:

```text
Shelly host always chooses strongest AP
```

is not supported by the identified host code.

Likewise:

```text
WF200 always chooses strongest AP
```

has not been established.

The strongest supported statement is:

> The host submits a wildcard connection request and delegates the concrete AP
> selection to the WLAN subsystem.

### Classification

Host does not explicitly specify one BSSID:

**PROVEN**

Concrete initial AP selection is delegated below the host:

**PROVEN**

Exact WF200 ranking algorithm:

**UNKNOWN**

WF200 always chooses the strongest AP:

**UNKNOWN**

---

# 6. Previous AP Information

The analysis also examined whether previously associated BSSID or channel
information is reused by the host during later reconnects.

BSSID-related information can exist in host-side state.

However, no identified host-side consumer was found that constrains the next
CONNECT request using that information.

No established path equivalent to:

```text
previous BSSID
        |
        v
next CONNECT BSSID
```

was identified.

Likewise:

```text
previous channel
        |
        v
next CONNECT channel
```

was not identified.

The reconnect request again uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

The protected WF200 subsystem could still retain internal connection history or
scan information.

That behavior cannot be established from the analyzed host application.

### Classification

Host explicitly constrains reconnect to the previous BSSID:

**UNKNOWN as a hypothetical behavior; no such path was identified**

Host explicitly constrains reconnect to the previous channel:

**UNKNOWN as a hypothetical behavior; no such path was identified**

WF200 internally retains or prefers previous AP information:

**UNKNOWN**

---

# 7. `prevent_roaming`

During connection establishment, the host sets:

```text
prevent_roaming = 1
```

The relevant WLAN interface semantics distinguish between:

```text
prevent_roaming = 1
```

and:

```text
prevent_roaming = 0
```

With roaming prevention enabled, autonomous WLAN-firmware roaming after
association is prevented.

Permitting roaming does not imply:

```text
always select strongest AP
```

The parameter does not by itself reveal:

- roaming RSSI threshold
- hysteresis
- candidate ranking
- scan timing
- reassociation timing
- cached-AP preference
- internal retry strategy

Those remain implementation details of the WLAN subsystem.

### Classification

Stock firmware sets `prevent_roaming = 1`:

**PROVEN**

`prevent_roaming = 1` prevents autonomous WLAN-firmware roaming:

**PROVEN**

Allowing roaming permits autonomous roaming behavior:

**PROVEN**

Allowing roaming guarantees strongest-AP selection:

**UNKNOWN**

Exact WF200 roaming thresholds and policy:

**UNKNOWN**

---

# 8. Host-Side Roaming

No separate host-side mechanism was identified that continuously evaluates
signal strength and moves an established connection to a stronger AP.

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

This is distinct from reconnecting after an actual connection loss.

The host therefore normally appears to retain the existing association until
another event changes the connection state.

With:

```text
prevent_roaming = 1
```

autonomous roaming by the WLAN firmware is also intentionally prevented.

### Classification

Host-side RSSI-driven background roaming:

**UNKNOWN as a hypothetical feature; no such mechanism was identified**

Host-side background strongest-BSSID selection:

**UNKNOWN as a hypothetical feature; no such mechanism was identified**

---

# 9. Weak-but-Functional AP Retention

The stock configuration permits a potentially important scenario.

For example:

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

- autonomous roaming is prevented
- no host-side strongest-AP roaming mechanism was identified
- weak RSSI changes the requested beacon-skip configuration
- weak RSSI alone was not found to force host-side reassociation

Continued association with the weaker but still functional AP is therefore
technically plausible.

This does not establish that a particular tested TRV actually remained on a
weaker AP.

That requires direct observation of the associated BSSID.

### Classification

Weak-but-functional AP retention is possible under the identified policy:

**STRONGLY SUPPORTED**

A particular test device remained associated with a weaker AP while a stronger
compatible AP was available:

**UNKNOWN unless the associated BSSID was directly observed**

---

# 10. Behavior After Connection Loss

After an actual WLAN connection loss, the application clears the connected
state and returns to its normal connection procedure.

The next request again uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

No host-side mechanism was identified that explicitly:

- retries the previous BSSID first
- retries the previous channel first
- selects the strongest scan result itself

Conceptually:

```text
existing association
        |
        v
connection loss
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

A reconnect therefore gives the WLAN subsystem another opportunity to choose
an AP.

The selected AP may be the previous AP or another compatible AP.

### Classification

Reconnect returns to wildcard CONNECT:

**PROVEN**

Reconnect creates another AP-selection opportunity:

**PROVEN**

Reconnect necessarily selects a different AP:

**UNKNOWN**

Exact WF200 reconnect-selection criteria:

**UNKNOWN**

---

# 11. Associated BSSID Visibility

The MAC address normally exposed by the TRV through HTTP is the TRV's own MAC
address.

It is not the BSSID of the associated AP.

However, the successful WLAN connection indication contains actual association
information.

The relevant `CONNECT_IND` event contains:

```text
BSSID
Channel
```

The host therefore receives the selected BSSID and channel after successful
association.

This information is not normally exposed through `/status`.

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
host processes connection
```

This provides a useful diagnostic observation point.

### Classification

Associated BSSID is present in successful `CONNECT_IND`:

**PROVEN**

Associated channel is present:

**PROVEN**

Associated BSSID is normally exposed through `/status`:

**UNKNOWN as a hypothetical interface feature; it was not identified in the
examined status output**

A direct diagnostic observation point exists:

**PROVEN**

---

# 12. RSSI Representation

The RSSI used by the host originates from WLAN signal-strength information.

The identified conversion is approximately:

```text
RSSI = ((uint8_t)RCPI >> 1) - 110
```

The `/status` interface does not necessarily trigger a new instantaneous radio
measurement for every request.

It reports stored host-side RSSI state.

Therefore:

```text
scan RSSI
```

and:

```text
/status RSSI
```

must not automatically be treated as identical measurements.

They may represent different:

- times
- averaging histories
- packet populations
- connection states
- measurement contexts

This is particularly important when interpreting a sudden RSSI change.

An RSSI jump alone does not prove that the associated BSSID changed.

---

# 13. RSSI and Desired Beacon Skip

RSSI directly controls the normal `desired_beacon_skip` policy.

The identified mapping is:

```text
RSSI >= -69 dBm
desired_beacon_skip = 20


RSSI -70 ... -79 dBm
desired_beacon_skip = 15


RSSI < -79 dBm
desired_beacon_skip = 10
```

These thresholds control the requested normal WLAN beacon power-saving policy.

No corresponding host-side threshold behavior was identified that directly
means:

```text
RSSI < threshold
        |
        v
change AP
```

The established relationship is:

```text
RSSI
 |
 v
desired_beacon_skip
```

not:

```text
RSSI
 |
 v
host AP selection
```

### Classification

RSSI controls `desired_beacon_skip`:

**PROVEN**

These same thresholds directly force host-side AP reassociation:

**UNKNOWN as a hypothetical behavior; no such control path was identified**

---

# 14. Desired Beacon Skip and Nominal Listening

The requested skip values correspond to different nominal beacon-listening
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

Therefore, in nominal opportunity terms:

```text
21 / 11 ~= 1.91
```

so skip 10 represents approximately 1.91 times as many nominal listening
opportunities as skip 20.

Likewise:

```text
21 / 16 ~= 1.31
```

so skip 15 represents approximately 1.31 times as many nominal listening
opportunities as skip 20.

These ratios describe nominal WLAN beacon-listening opportunities.

They do not directly quantify:

- WF200 energy consumption
- host-MCU wake frequency
- RF transmission
- complete-device current
- battery-life reduction

### Classification

Lower skip produces more nominal beacon-listening opportunities:

**PROVEN**

Total-device energy increases in exactly the same proportion:

**UNKNOWN**

---

# 15. Host MCU vs. WF200 Beacon Listening

The identified skip values use the same general host-side sleep-release
architecture.

No separate host-MCU power-state architecture was identified specifically for:

```text
skip 10
skip 15
skip 20
```

The WLAN subsystem can perform radio-side connection maintenance without
requiring the host MCU to execute for every individual beacon event.

Therefore:

```text
more WF200 beacon-listening opportunities
```

does not imply:

```text
the same proportional increase in host-MCU wakeups
```

A lower skip value should be interpreted primarily as increased radio-side
listening opportunity.

The quantitative electrical effect on the complete TRV remains:

**UNKNOWN**

---

# 16. AP Selection and Normal Energy Consumption

AP selection can affect normal WLAN energy behavior through the resulting RF
conditions.

A supported conceptual chain is:

```text
AP selection / AP retention
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
nominal beacon-listening frequency
```

The evidence levels differ along this chain.

```text
AP choice influences RF conditions
        |
        v
INFERENCE in a specific deployment


RSSI -> desired_beacon_skip
        |
        v
PROVEN


desired_beacon_skip -> nominal listening policy
        |
        v
PROVEN
```

Weak RF conditions can also plausibly affect:

```text
retransmissions
```

and:

```text
connection stability
        |
        v
reconnect / scan activity
```

These mechanisms are technically plausible.

Their quantitative contribution to the observed battery drain has not been
measured.

---

# 17. AP Selection and Beacon Recovery

AP selection and Beacon Recovery are separate host control mechanisms.

The WLAN environment can influence both, but they must not be collapsed into
one causal chain.

The relevant high-level model is:

```text
             AP selection / retention
                       |
                       v
                 RF conditions
                       |
             +---------+---------+
             |                   |
             v                   v
            RSSI          beacon reception
             |              statistics
             v                   |
desired_beacon_skip             v
             |           beacon_rx_count
             v                   |
normal requested                v
power-save policy        real_beacon_skip
                                 |
                                 v
                         Recovery predicate
                                 |
                                 v
                         temporary state 1
```

Established relationships include:

- RSSI controls `desired_beacon_skip`
- `desired_beacon_skip` controls normal requested beacon power saving
- WF200 beacon statistics provide the received-beacon counter
- the counter is used in the host-side `real_beacon_skip` calculation
- qualifying control values can trigger Recovery
- Recovery requests temporary state 1 / ACTIVE operation

What is not established is:

```text
poor AP selection
        |
        v
poor RSSI
        |
        v
Beacon Recovery
```

as a required chain.

---

# 18. Updated Beacon-Recovery Findings

The Beacon Recovery investigation has since identified three distinct
host-side validity problems.

## C1a — Signed Control-Value Validity

The stored `real_beacon_skip` byte is read as signed for the Recovery control
predicate.

This creates additional qualifying values through signed narrowing.

For a fresh valid calculation:

```text
delta = 3
600 / 3 = 200
byte = 0xC8
signed = -56
```

and:

```text
delta = 4
600 / 4 = 150
byte = 0x96
signed = -106
```

Both satisfy the stock signed:

```text
<= 2
```

control test.

The resulting stock fresh-trigger domain is:

```text
delta = 3
delta = 4
delta = 201 ... 600
```

This is a host-side control-validity defect.

It does not require weak RSSI.

### Classification

C1a behavior:

**PROVEN**

Interpretation as a genuine control-validity defect:

**STRONGLY SUPPORTED**

---

# 19. C1b — Measurement-Window Validity

The Beacon Recovery calculation uses:

```text
600 / (current_received - previous_received)
```

but the stored previous counter does not carry an elapsed-time measurement.

Certain power-management and maintenance conditions can suppress a scheduled
sample while preserving the old baseline.

The next successful calculation can therefore compare counters spanning more
than the nominal measurement interval while still using the fixed constant:

```text
600
```

For example, shared PM override periods can preserve the previous baseline
across skipped measurement opportunities.

Therefore the counter difference is not guaranteed to represent the interval
assumed by the fixed calculation.

This is a host-side measurement-validity issue.

Again, weak RSSI is not required.

### Classification

Baseline age is not explicitly tracked:

**PROVEN**

Skipped measurement opportunities can preserve the stock baseline:

**PROVEN**

Interpretation as a genuine measurement-validity defect:

**STRONGLY SUPPORTED**

Exact cause of the first observed field trigger:

**UNKNOWN**

---

# 20. C2 — Post-Recovery Freshness Failure

The strongest result for the persistent Recovery loop is C2.

After a qualifying Recovery:

```text
previous_received = 0
```

while the qualifying cached:

```text
real_beacon_skip
```

is retained.

At the next successful measurement:

```text
previous_received == 0
```

causes the current received counter to be installed as the new baseline.

No fresh ratio is calculated.

However, stock control flow then evaluates the previously retained
`real_beacon_skip`.

If that historical value remains qualifying:

```text
Recovery triggers again
```

and:

```text
previous_received
```

is cleared again.

Conceptually:

```text
qualifying Recovery
        |
        v
P = 0
R retained
        |
        v
next successful sample
        |
        v
P = current
no fresh R calculation
        |
        v
historical R tested
        |
        v
Recovery again
        |
        v
P = 0
```

This creates a self-sustaining loop.

No new weak-RSSI event is required.

No AP change is required.

No mDNS event is required.

No failed PM restoration is required.

### Classification

C2 stale-state loop in the identified stock control flow:

**PROVEN**

---

# 21. Consequence for AP-Selection Hypotheses

Before C1a/C1b/C2 were understood, a plausible working hypothesis was:

```text
weak AP retained
        |
        v
weak RSSI
        |
        v
lower desired_beacon_skip
        |
        v
abnormal beacon statistics
        |
        v
Recovery
        |
        v
additional battery consumption
```

That chain is no longer required to explain the known recurring behavior.

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
normal WLAN energy behavior
```

while separately:

```text
WF200 beacon statistics
        |
        v
host measurement
        |
        +---- C1a control validity
        |
        +---- C1b measurement-window validity
        |
        v
qualifying Recovery
        |
        v
C2 stale-state recurrence
```

The paths share the WLAN environment.

They are not the same control path.

---

# 22. First Trigger vs. Persistent Recovery

It is important to separate:

```text
Why did the first qualifying Recovery occur?
```

from:

```text
Why does Recovery then repeat?
```

The second question is substantially answered by C2.

The first remains unresolved in actual field operation.

Possible contributors to the first qualifying measurement can include:

- genuine unusual beacon reception
- measurement-window aging
- connection-state transitions
- PM override timing
- radio-internal behavior
- AP-specific behavior
- RF conditions
- other still-unidentified events

AP selection therefore remains potentially relevant to the first-trigger
environment.

But no evidence currently establishes:

```text
poor AP selection
```

as the actual cause of the first observed trigger.

### Classification

Persistent recurrence requires continued poor AP conditions:

**UNKNOWN as a hypothetical requirement; C2 demonstrates that such a
requirement is unnecessary**

Poor AP selection caused the first field trigger:

**UNKNOWN**

---

# 23. RSSI Is Not a Recovery Predicate

The normal desired-skip thresholds are:

```text
>= -69 dBm      -> 20
-79 .. -70 dBm -> 15
< -79 dBm       -> 10
```

The Beacon Recovery predicate does not directly compare:

```text
RSSI
```

or:

```text
desired_beacon_skip
```

against the calculated real value.

There is no identified predicate equivalent to:

```text
if real_beacon_skip differs from desired_beacon_skip:
    recover
```

Instead, Recovery is based on the cached/calculated `real_beacon_skip` control
value.

This matters because:

```text
good RSSI
```

does not structurally disable the Recovery predicate.

Likewise:

```text
desired_beacon_skip = 20
```

does not structurally prevent Recovery.

The current `.77` Patch-B observations, for example, show recurring stock
Beacon Recovery around:

```text
RSSI approximately -75 ... -77 dBm
desired_beacon_skip = 15
```

These observations are sufficient to demonstrate that the mDNS-only patch does
not remove Beacon Recovery.

They should not be conflated with older device-role observations.

---

# 24. Historical Good-RSSI Observation

Separate stock observations have shown that Beacon Recovery is not restricted
to obviously weak RSSI conditions.

This supports the broader conclusion:

> Weak RSSI is not a necessary structural prerequisite for the 2.2.4 Recovery
> mechanism.

However, device identities and experimental configurations must be kept
separate.

In particular, the current `.77` Patch-B test role should not be described
using an older unrelated:

```text
-58 ... -59 dBm
desired_beacon_skip = 20
```

observation.

The important scientific conclusion does not depend on assigning that older
observation to `.77`.

---

# 25. Version Comparison

The host-side AP-selection behavior was compared across:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

The relevant connection characteristics remain substantially consistent:

```text
wildcard BSSID
Channel = 0
prevent_roaming = 1
```

No version-specific host-side strongest-AP selection mechanism was identified.

Therefore the firmware versions should not be differentiated on the basis of a
host-side AP-ranking algorithm that has not been found.

However, this does not imply identical complete WLAN behavior.

The protected WF200 image changes at later firmware boundaries.

---

# 26. Protected WF200 Boundary

The exact AP-selection and roaming implementation resides partly inside the
protected WLAN subsystem.

Within the analyzed firmware set:

```text
2.1.0
2.1.3
```

use the same identified protected WF200 image generation.

The protected image changes in:

```text
2.1.8
```

and changes again in:

```text
2.2.4
```

The corresponding identified WLAN stack evolution includes:

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

Therefore:

```text
same host CONNECT parameters
```

does not prove:

```text
identical internal AP-selection behavior
```

across all firmware versions.

Internal changes could potentially affect:

- scan-result ranking
- cached-AP preference
- retry strategy
- association timing
- radio power-management behavior
- error handling

No specific protected-firmware AP-ranking change has been established.

### Classification

Protected WLAN implementation changes across later firmware versions:

**PROVEN**

Those changes altered AP ranking in a particular way:

**UNKNOWN**

---

# 27. D3 Power-Save Error Events

Firmware 2.2.4 contains host-visible WLAN power-save error reasons associated
with the protected WLAN subsystem.

Identified reasons include conditions corresponding to:

```text
0
AP did not provide buffered unicast after PS-Poll

1
AP did not provide buffered unicast after U-APSD trigger

2
AP indicated buffered unicast but no frame was delivered
across repeated beacons

3
unstable AP beacon timing / beacon-window adjustment
```

These events demonstrate that AP behavior and beacon timing can influence
radio-side power-save operation.

However, no direct host control-flow edge has been established:

```text
D3 event
    |
    v
Beacon Recovery
```

Therefore D3 events should not currently be treated as the proven cause of
Beacon Recovery.

Radio-internal effects on received-beacon statistics remain possible.

### Classification

D3 power-save error reasons exist:

**PROVEN**

Direct D3-to-Recovery host control edge:

**UNKNOWN; no such direct edge has been established**

Indirect effect on beacon statistics:

**INFERENCE**

---

# 28. Roaming-Patch Feasibility

The host-side `prevent_roaming` setting provides a technically small
experimental modification point.

Stock behavior uses:

```text
prevent_roaming = 1
```

A modification to:

```text
prevent_roaming = 0
```

would permit autonomous WLAN-firmware roaming.

Such a modification would not:

- implement a custom strongest-AP algorithm
- guarantee strongest-AP selection
- reveal WF200 roaming thresholds
- correct C1a
- correct C1b
- correct C2
- suppress periodic mDNS
- guarantee lower power consumption

The technical feasibility of changing the setting must therefore be separated
from the scientific value of doing so.

### Classification

Minimal host-side roaming modification is technically feasible:

**PROVEN**

It would always select the strongest AP:

**UNKNOWN**

It would improve battery life:

**UNKNOWN**

---

# 29. Why a Roaming Patch Is Not a Current Priority

Changing roaming policy introduces another experimental variable.

Conceptually:

```text
different roaming policy
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

This can make battery comparisons harder to interpret.

Meanwhile, the main recurring mechanisms now have cleaner isolated research
paths:

```text
Patch B
        |
        v
periodic mDNS workload


Patch C-C
        |
        v
Beacon Recovery validity semantics
```

AP-selection modification is not required to test either mechanism.

A roaming patch therefore remains technically interesting but secondary.

The preferred order is:

```text
observe AP behavior first
        |
        v
establish whether AP retention is actually occurring
        |
        v
only then consider changing roaming policy
```

---

# 30. Diagnostic BSSID Instrumentation

If AP behavior becomes experimentally important, direct observation is
preferable to inference from RSSI.

The successful connection event already provides:

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

when association succeeds.

This would directly answer:

```text
Which AP did the TRV actually associate with?
```

without changing:

- AP selection
- roaming policy
- RSSI thresholds
- beacon-skip policy
- mDNS behavior
- Beacon Recovery

This is scientifically cleaner than inferring AP changes from RSSI alone.

---

# 31. Suggested AP Experiment

If AP behavior is investigated later, the preferred sequence is observational
before interventional.

## Phase 1 — Association instrumentation

Record:

```text
timestamp
BSSID
channel
RSSI
```

for each successful association.

Do not change roaming behavior.

---

## Phase 2 — Weak-but-functional AP retention

Create a controlled environment:

```text
AP A
weak but functional


AP B
same SSID
substantially stronger
```

while the TRV remains associated with AP A.

Observe:

```text
BSSID
RSSI
connection state
```

With:

```text
prevent_roaming = 1
```

the hypothesis is that autonomous WLAN-firmware roaming will not occur.

The experiment should verify the actual BSSID rather than relying on RSSI.

---

## Phase 3 — Forced connection loss

Make the currently associated AP unavailable.

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
selected BSSID
```

This tests whether the reconnect selects another compatible AP.

---

## Phase 4 — Optional roaming experiment

Only if scientifically justified, compare:

```text
prevent_roaming = 1
```

against:

```text
prevent_roaming = 0
```

while recording:

```text
BSSID
channel
RSSI
reconnect events
beacon policy
battery voltage
network availability
```

This separates observation from intervention.

---

# 32. Relationship to Patch B

Patch B suppresses the targeted recurring connected-maintenance mDNS restart.

It does not intentionally modify:

```text
AP selection
prevent_roaming
RSSI thresholds
desired_beacon_skip
Beacon Recovery
```

The Patch-B device therefore remains useful for studying AP behavior without
the targeted recurring mDNS workload.

Importantly, recurring Beacon Recovery continues on the Patch-B device.

This demonstrates that the targeted periodic mDNS restart is not required for
the observed Recovery loop under the tested conditions.

It does not establish that AP or RF conditions have no influence on the first
qualifying measurement.

---

# 33. Relationship to Patch A

Patch A bypasses the Beacon Recovery action.

It was useful as a mechanism-isolation experiment.

However, Patch A suppresses both:

```text
invalid Recovery
```

and potentially:

```text
legitimate Recovery
```

It therefore does not correct the underlying validity semantics.

Patch A should now be treated as:

```text
historical Recovery-isolation patch
```

rather than:

```text
preferred final Recovery correction
```

This distinction also changes the role of AP research.

There is no longer a need to change AP behavior simply to prevent the recurring
Recovery loop.

---

# 34. Relationship to Patch C-C

Patch C is the research family intended to correct the Beacon Recovery
validity problems while preserving legitimate Recovery.

The current preferred implementation candidate is:

```text
Patch C-C
```

Its behavior-level objectives are:

```text
C1a
use unsigned control interpretation for real_beacon_skip

C1b
invalidate the beacon counter baseline across invalid measurement epochs

C2
prevent a baseline-only sample from acting on historical Recovery evidence
```

while preserving:

```text
fresh legitimate Recovery
diagnostic real_beacon_skip state
normal PM restoration
```

Patch C-C does not intentionally change:

```text
AP selection
prevent_roaming
RSSI thresholds
desired_beacon_skip
mDNS
```

Static pre-build qualification has passed.

No Patch C-C firmware has yet been hardware-qualified.

Therefore:

```text
runtime correctness
battery improvement
network availability
OTA / GBL acceptance
```

remain to be established experimentally.

---

# 35. AP Selection and C1a

C1a is caused by the host's signed interpretation of the stored
`real_beacon_skip` byte.

This defect exists independently of AP selection.

For example:

```text
delta = 3
```

or:

```text
delta = 4
```

can become qualifying through signed-byte interpretation.

No particular RSSI or BSSID is required by that arithmetic.

AP conditions could influence the received-beacon counter.

They do not create the signedness defect itself.

---

# 36. AP Selection and C1b

C1b concerns whether:

```text
current_received - previous_received
```

represents the time interval assumed by the fixed:

```text
600
```

calculation.

AP selection does not create the missing elapsed-time information.

However, AP or RF conditions could potentially influence:

- connection stability
- PM transitions
- radio-side behavior
- beacon reception
- reconnects

These may affect the circumstances under which a baseline becomes invalid.

Therefore:

```text
AP selection causes C1b
```

is not supported.

But:

```text
AP / RF conditions may influence the measurement environment
```

remains plausible.

---

# 37. AP Selection and C2

C2 is the clearest separation.

Once stock firmware reaches:

```text
P = 0
R = qualifying historical value
```

the identified host control flow can repeat Recovery without a fresh
qualifying ratio.

Therefore persistent weak RSSI is unnecessary.

Persistent association with a poor AP is unnecessary.

A fresh RF anomaly every minute is unnecessary.

This means AP selection cannot be required to explain the self-sustaining
portion of the Recovery loop.

AP behavior may still matter before the first qualifying event.

It does not explain the host-side stale-state recurrence itself.

---

# 38. Historical Battery Drain

The AP-selection mechanism cannot currently be identified as the sole cause of
the historical Shelly TRV Gen1 battery drain.

Several independent mechanisms are now under investigation:

```text
AP / RF conditions
        |
        +-- normal WLAN efficiency
        +-- retransmissions
        +-- reconnect behavior
        +-- desired beacon-skip policy


periodic mDNS
        |
        +-- recurring network workload


Beacon Recovery
        |
        +-- C1a
        +-- C1b
        +-- C2
        +-- temporary ACTIVE recovery workload


WUP / EM2 candidate
        |
        +-- inherited low-level sleep-resource behavior
```

These mechanisms may contribute differently.

No evidence currently supports collapsing them into one single root cause.

---

# 39. Evidence Summary

| Finding | Classification |
|---|---|
| Scan information contains BSSID, channel and RSSI | **PROVEN** |
| CONNECT uses wildcard BSSID | **PROVEN** |
| CONNECT uses channel 0 | **PROVEN** |
| Host explicitly selects strongest scan result | **UNKNOWN; no such path identified** |
| Concrete initial AP selection occurs below host application | **PROVEN** |
| Exact WF200 AP-ranking algorithm | **UNKNOWN** |
| WF200 always chooses strongest AP | **UNKNOWN** |
| Host constrains reconnect to previous BSSID | **UNKNOWN; no such path identified** |
| Host constrains reconnect to previous channel | **UNKNOWN; no such path identified** |
| WF200 internally prefers previous AP | **UNKNOWN** |
| Stock sets `prevent_roaming = 1` | **PROVEN** |
| `prevent_roaming = 1` prevents autonomous WLAN-firmware roaming | **PROVEN** |
| Allowing roaming guarantees strongest-AP selection | **UNKNOWN** |
| Host performs background strongest-BSSID roaming | **UNKNOWN; no such mechanism identified** |
| Weak-but-functional AP retention is possible | **STRONGLY SUPPORTED** |
| Connection loss returns to wildcard connection procedure | **PROVEN** |
| Reconnect provides another AP-selection opportunity | **PROVEN** |
| Reconnect necessarily chooses another AP | **UNKNOWN** |
| RSSI controls `desired_beacon_skip` | **PROVEN** |
| RSSI thresholds directly force AP change | **UNKNOWN; no such host path identified** |
| Skip 20 corresponds nominally to approximately every 21st beacon | **PROVEN** |
| Skip 15 corresponds nominally to approximately every 16th beacon | **PROVEN** |
| Skip 10 corresponds nominally to approximately every 11th beacon | **PROVEN** |
| Lower skip increases nominal WF200 listening opportunities | **PROVEN** |
| Lower skip proportionally increases complete-device current | **UNKNOWN** |
| Associated BSSID is present in successful `CONNECT_IND` | **PROVEN** |
| Associated channel is present in successful `CONNECT_IND` | **PROVEN** |
| RSSI change alone proves BSSID change | **UNKNOWN** |
| Weak RSSI is structurally required for Beacon Recovery | **UNKNOWN; identified Recovery logic does not require it** |
| Poor AP selection is required for C2 recurrence | **UNKNOWN; C2 provides an AP-independent recurrence mechanism** |
| C1a is a host-side control-validity defect | **STRONGLY SUPPORTED** |
| C1b is a host-side measurement-validity defect | **STRONGLY SUPPORTED** |
| C2 stale-state recurrence exists | **PROVEN** |
| AP behavior caused the first field Recovery trigger | **UNKNOWN** |
| D3 power-save errors directly trigger Recovery | **UNKNOWN; no direct edge established** |
| AP/RF behavior can affect normal WLAN energy cost | **STRONGLY SUPPORTED** |
| Quantitative AP-selection contribution to battery drain | **UNKNOWN** |
| Minimal `prevent_roaming` experiment is technically feasible | **PROVEN** |
| Such a patch would improve battery life | **UNKNOWN** |
| Patch C-C intentionally changes AP selection | **UNKNOWN as a hypothetical interaction; not part of its design** |
| Patch C-C has passed static pre-build qualification | **PROVEN as project qualification status** |
| Patch C-C runtime behavior is validated | **UNKNOWN; hardware qualification pending** |

---

# 40. Remaining Questions

The main unresolved AP-selection questions are:

1. What exact criteria does the WF200 use during wildcard AP selection?

2. Does the WF200 internally prefer a previously associated AP?

3. What thresholds and hysteresis would control autonomous roaming if
   `prevent_roaming = 0`?

4. How often does weak-but-functional AP retention occur in real mesh or
   multi-AP networks?

5. Do observed large RSSI changes correspond to actual BSSID changes?

6. How much additional energy is consumed at skip 10 versus skip 15 or skip 20?

7. How much do retransmissions contribute under poor RF conditions?

8. How much energy is consumed by scan and reconnect events?

9. Did the protected WF200 changes between 2.1.3, 2.1.8 and 2.2.4 alter AP
   ranking or reconnect behavior?

10. Can AP or RF conditions contribute to the first qualifying Beacon Recovery
    measurement?

11. Do D3 power-save events affect the received-beacon counter in a way relevant
    to C1b?

12. Would permitting autonomous roaming measurably improve long-term battery
    consumption?

13. Would permitting roaming introduce new stability or availability problems?

14. How often would autonomous roaming actually occur in a representative
    multi-AP installation?

The most important distinction is:

```text
AP/RF influence on the first trigger
```

remains open.

But:

```text
AP/RF conditions required for persistent C2 recurrence
```

are not needed by the identified host control flow.

---

# 41. Current Research Priority

AP-selection modification is currently secondary.

The primary experimental paths are now separated.

## Periodic mDNS

```text
Patch B
        |
        v
suppress targeted recurring mDNS restart
        |
        v
measure long-term battery contribution
```

## Beacon Recovery

```text
Patch C-C
        |
        v
correct C1a / C1b / C2 semantics
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

## AP Selection

```text
diagnostic BSSID observation
        |
        v
controlled weak-AP experiment
        |
        v
reconnect experiment
        |
        v
optional roaming intervention
```

This order avoids introducing unnecessary variables into the main battery
experiment.

---

# 42. Current Model

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
            +---------+---------+
            |                   |
            v                   v
       RSSI changes       connection loss
            |                   |
            v                   v
 desired_beacon_skip           scan
            |                   |
            v                   v
 normal requested       wildcard CONNECT
 WLAN power saving             |
                                v
                         AP selected again
```

A separate 2.2.4 host mechanism is:

```text
WF200 beacon statistics
        |
        v
received-beacon counter
        |
        v
host measurement
        |
        +---- C1a
        |
        +---- C1b
        |
        v
real_beacon_skip
        |
        v
Recovery predicate
        |
        v
temporary state 1
        |
        v
C2 can sustain recurrence
```

The two mechanisms share the WLAN environment.

They must not be treated as the same control path.

---

# 43. Current Conclusion

The Shelly TRV host application does not explicitly select one particular
strongest AP during normal connection establishment.

Instead, the examined connection path uses:

```text
BSSID   = FF:FF:FF:FF:FF:FF
Channel = 0
```

and delegates concrete AP selection to the WLAN/WF200 subsystem.

The host also sets:

```text
prevent_roaming = 1
```

which prevents autonomous WLAN-firmware roaming after association.

No separate host-side mechanism was identified that periodically moves an
established connection to a stronger AP based only on RSSI.

A weak but still functional AP can therefore potentially remain associated.

Weak RSSI then affects normal WLAN power saving through:

```text
RSSI
 |
 v
desired_beacon_skip
```

and may increase normal radio-side work through lower skip values,
retransmissions, or connection instability.

However, the Beacon Recovery investigation now provides a much clearer
separation between AP behavior and the recurring 2.2.4 Recovery problem.

C1a concerns signed interpretation of the host control value.

C1b concerns validity of the measurement interval.

C2 concerns reuse of historical Recovery evidence after the counter baseline
has been cleared.

None of these defects requires persistent poor AP selection.

Most importantly:

> Once a qualifying Recovery has occurred, the identified C2 control flow can
> sustain recurring Recovery without requiring continued weak RSSI, a new AP
> problem, a new mDNS event, or a fresh qualifying RF anomaly on every cycle.

AP behavior therefore remains relevant to:

```text
normal WLAN energy efficiency
possible first-trigger conditions
connection stability
retransmissions
reconnect behavior
```

but it is no longer a leading explanation for the self-sustaining Recovery
loop.

The actual contribution of AP selection to the historical battery drain
remains:

**UNKNOWN**

Changing `prevent_roaming` is technically feasible, but it would introduce
another experimental variable without correcting C1a, C1b or C2.

The preferred current strategy is therefore:

```text
do not modify roaming yet
        |
        v
observe actual BSSID first
        |
        v
complete Patch C-C hardware qualification
        |
        v
continue Patch-B battery comparison
        |
        v
investigate AP behavior separately if evidence justifies it
```

This preserves causal interpretability and avoids using an AP-selection change
as a workaround for a host-side Beacon Recovery defect.

---

# Related Documents

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Power-management behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Beacon counter:

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

# Research Methodology

This investigation is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

The analysis includes:

- WLAN scan handling
- CONNECT parameter construction
- BSSID and channel handling
- disconnect and reconnect behavior
- RSSI and RCPI processing
- power-management interaction
- successful `CONNECT_IND` processing
- firmware-version comparison
- protected-WLAN-version comparison
- Beacon Recovery control-flow analysis
- runtime WLAN observations

The examined host firmware versions are:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

The analysis deliberately distinguishes:

```text
host-visible behavior
```

from:

```text
protected WF200 internal behavior
```

The exact protected WF200 AP-ranking algorithm has not been reconstructed and
must therefore remain unknown unless established by separate evidence.

Small instruction-level facts, control-flow relationships and interface
parameters are documented where necessary for reproducibility.

Complete proprietary firmware functions, firmware images and large raw
disassemblies are not reproduced.

The project uses:

```text
PROVEN
STRONGLY SUPPORTED
INFERENCE
UNKNOWN
```

to distinguish direct evidence from interpretation and unresolved behavior.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the investigated firmware versions.

No conclusion about the intentions of the original developers is made unless
supported by independent technical evidence.