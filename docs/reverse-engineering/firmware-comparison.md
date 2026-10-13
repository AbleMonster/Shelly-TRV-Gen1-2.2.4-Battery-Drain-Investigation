# Firmware Comparison

## Scope

This document compares energy-relevant host-side and WLAN-related behavior
identified in the following Shelly TRV Gen1 firmware versions:

- 2.1.0
- 2.1.3
- 2.1.8
- 2.2.4

The primary research question is whether firmware changes can explain the
historically observed battery-drain behavior and the additional recurring
beacon-recovery behavior observed in firmware 2.2.4.

The analysis separates:

- proven binary differences
- runtime observations
- experimentally isolated mechanisms
- plausible energy consequences
- unresolved behavior
- actual battery-drain causation

> **Important:** No firmware version is currently proven to be the first
> version affected by the historical battery-drain problem.

Firmware 2.1.3 must not be treated as a known-good battery reference.

The historical observation that firmware 2.1.8 also exhibited relatively fast
battery drain means that the battery problem cannot currently be treated as a
2.2.4-only regression.

---

# 1. Firmware Overview

| Firmware | Build | WF200 runtime | FMAC | Protected WF image | Known 2.2.4-style beacon recovery |
|---|---|---|---|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` | 3.12.2 | 3.3.2 | A | Not identified |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` | 3.12.2* | 3.3.2 | A | Not identified |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` | 3.14.0 | 3.4.1 | B | Not identified |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` | 3.16.1 | 3.7.0 | C | Present |

\* The 2.1.3 WF200 runtime version is inferred from the identical protected
WF200 image shared with 2.1.0.

---

# 2. Protected WF200 Images

The protected WF200 payload is identical between firmware 2.1.0 and 2.1.3.

```text
2.1.0 -> protected WF image A
2.1.3 -> protected WF image A
2.1.8 -> protected WF image B
2.2.4 -> protected WF image C
```

This makes the transition:

```text
2.1.0 -> 2.1.3
```

particularly useful.

Host-side changes can be compared without simultaneously introducing a
different bundled WF200 image or FMAC generation.

This does **not** prove that the WF200 behaves identically in both versions.

Changed host requests, scheduling or network traffic can still alter runtime
behavior even when the protected WF200 image itself is unchanged.

The later transitions are more difficult to isolate because both host firmware
and protected WLAN components change.

---

# 3. Normal RSSI-Dependent Beacon Skip

The analyzed firmware versions retain the same normal RSSI-dependent desired
beacon-skip policy:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

This normal desired skip must be distinguished from the calculated
`real_beacon_skip` value used by firmware 2.2.4.

The desired skip is selected from RSSI.

The `real_beacon_skip` value in 2.2.4 is instead derived from WF200 beacon
statistics.

Runtime testing has also shown that the 2.2.4 beacon-recovery condition can
occur while:

```text
RSSI ≈ -58 to -59 dBm
desired beacon skip = 20
```

Therefore poor RSSI is not required for the observed recovery loop.

---

# 4. Normal Power-Save State 3

The normal state-3 sequence is materially equivalent between firmware 2.1.0
and 2.1.3.

Simplified:

```text
store requested application state
        |
        v
wake WF200
        |
        v
short delay
        |
        v
command 0x52
Fast PS / desired beacon skip
        |
        v
delay
        |
        v
device-sleep enable
```

The dispatcher does not verify the return status of every low-level hardware
operation before retaining the requested application state.

This distinction is important:

```text
application state
        !=
confirmed WF200 state
        !=
confirmed MCU sleep-resource state
```

The normal ordering was not newly introduced in 2.1.3.

---

# 5. WUP / EM2 Retention Path

Earlier investigation identified a conditional path where the application can
record state 3 even though the final device-sleep operation fails.

Focused comparison confirmed that the core path already exists in firmware
2.1.0.

Simplified:

```text
wake WF200
        |
        v
WUP / WLAN sleep resource acquired
        |
        v
application state = 3
        |
        v
command 0x52
        |
        v
final device-sleep operation
        |
        +---- success
        |       |
        |       v
        |   WUP cleared
        |   WLAN EM2 contribution released
        |
        +---- register read/write failure
                |
                v
          release can be skipped
                |
                v
       application may still report state 3
```

## Important conclusion

This conditional failure mechanism is **not new in 2.1.3**.

It exists in:

```text
2.1.0
2.1.3
```

with materially equivalent low-level behavior.

Therefore the existence of this path alone does not establish a:

```text
2.1.0 -> 2.1.3
```

battery-drain boundary.

## Energy relevance

If triggered, a retained WLAN-owned EM2 blocker can prevent the MCU from
entering the expected deeper sleep state.

That can be energy relevant.

However:

- runtime occurrence is not proven
- failure frequency is unknown
- duration is unknown
- electrical current has not been measured
- increased occurrence in later firmware has not been demonstrated

The mechanism remains important, but it is currently an **inherited
conditional defect candidate**, not a demonstrated firmware-regression
boundary.

---

# 6. Additional Initialization Asymmetry

Focused analysis also identified an inherited asymmetry during WLAN driver
initialization.

Initialization directly blocks EM2 before parts of the bus and synchronization
setup are completed.

Some initialization failure paths do not locally perform a corresponding EM2
unblock.

This behavior exists in both 2.1.0 and 2.1.3.

A later successful balanced cleanup or full MCU reset can restore a clean
runtime state.

However, an arbitrary in-place driver reinitialization must not automatically
be assumed to clear a previously retained contribution.

Repeated initialization while an old contribution remained retained could
theoretically create an imbalance.

Whether this occurs on a physical TRV is unresolved.

This mechanism does not currently distinguish 2.1.0 from 2.1.3.

---

# 7. State 5 Introduced in 2.1.3

Firmware 2.1.3 introduces application power-management state 5.

State 5 is associated with the named external commands:

```text
HTTP:
psovrd2

Cloud:
psovrd2
```

The HTTP route is:

```text
/psovrd2
```

The command requests a temporary Fast Power Save configuration with:

```text
mode = 1
strategy = Fast PS
beacon listen interval = 10
```

A shared restoration countdown is set to:

```text
180
```

The countdown is serviced by the firmware's seconds-maintenance routine.

Under normal scheduler operation this corresponds to approximately three
minutes.

---

# 8. State 5 Lifecycle

Typical operation:

```text
normal state 3
desired skip 20 / 15 / 10
        |
        | external psovrd2
        v
state 5
Fast PS
skip 10
        |
        | approximately 180 serviced seconds
        v
restore previous/deferred state
        |
        v
typically state 3
```

State 5 is **not** an unconditional MCU-awake mode.

On a successful device-sleep handshake:

```text
WUP is cleared
WLAN-owned EM2 contribution is released
```

Therefore the MCU can remain eligible for deeper sleep while the application
remains in state 5.

Actual deep sleep still depends on other resource owners.

---

# 9. State 5 Refresh Behavior

The external `psovrd2` handlers write the 180-second countdown before
dispatching the state-5 request.

If another `psovrd2` request arrives while state 5 is already active:

```text
state 5
countdown = 60
        |
        | another psovrd2
        v
countdown = 180
```

The dispatcher can reject re-entering state 5, but the countdown has already
been refreshed.

Therefore repeated external requests can prolong the temporary override.

State 5 is:

```text
event-driven
temporary by design
potentially prolongable by external refresh
```

No autonomous periodic host-side state-5 entry mechanism was identified.

State 5 is therefore not currently considered the strongest explanation for
quiet-idle battery drain.

---

# 10. Named Active Override in 2.1.3

Firmware 2.1.3 also adds named external entry paths to an active override using
state 1.

This is distinct from state 5.

Conceptually:

```text
external psovrd
        |
        v
state 1
        |
        v
active WLAN behavior
WUP held
WLAN EM2 contribution retained
        |
        v
timeout / restoration
```

State 1 is more directly energy relevant than state 5 because it intentionally
uses a more active WLAN configuration and does not perform the normal
sleep-enable operation until restoration.

However, the identified entry paths are externally triggered.

No new autonomous periodic host caller for these override paths was identified.

Their real-world frequency therefore remains unresolved.

---

# 11. Periodic mDNS Restart Introduced by 2.1.3

The most important newly identified ordinary-connected-operation difference
between 2.1.0 and 2.1.3 is a periodic mDNS responder restart.

Firmware 2.1.3 adds a call equivalent to:

```text
mdns_resp_restart()
```

from its connected minute-maintenance path.

The equivalent 2.1.0 minute routine does not perform this call.

Runtime packet capture has now confirmed that this difference produces real
network activity.

Observed behavior:

```text
2.1.0
    no comparable periodic mDNS burst observed
    during approximately 13 minutes

2.1.3
    recurring mDNS probe / announcement burst
    approximately every 60 seconds
```

The periodic mDNS restart is therefore no longer merely a static candidate.

It is:

```text
statically identified
+
runtime confirmed
```

Its electrical cost remains unknown.

---

# 12. mDNS Restart Behavior

The mDNS responder implementation itself already exists in the older firmware.

The significant change is the recurring caller.

Simplified 2.1.3 behavior:

```text
connected TRV
      |
      v
minute maintenance
      |
      v
mdns_resp_restart()
      |
      v
cancel existing probing timer if necessary
      |
      v
probe counter = 0
      |
      v
responder state = probing
      |
      v
schedule probe callback
```

Under normal successful operation:

```text
probe 1
   |
   v
probe 2
   |
   v
probe 3
   |
   v
announcement
```

The resolved code path reaches the lwIP UDP output path.

Observed traffic uses:

```text
UDP port 5353
IPv4 multicast 224.0.0.251
```

This establishes actual packet-generation behavior rather than merely a
function name suggesting mDNS.

---

# 13. mDNS Scheduling in Firmware 2.2.4

Firmware 2.2.4 retains the periodic mDNS restart mechanism, but the observed
period differs from firmware 2.1.3.

Runtime packet capture showed:

```text
2.1.3
    ≈ 60 seconds

2.2.4 stock
    ≈ 180 seconds
```

Static analysis subsequently identified the 2.2.4 scheduling path:

```text
firmware-second dispatcher
        |
        v
seconds % 60 == 0
        |
        v
minute maintenance
        |
        v
increment maintenance counter
        |
        v
counter % 3 == 0
        |
        v
connected / IPv4 predicate
        |
        v
mdns_resp_restart()
```

Therefore the approximately 180-second period is not best described as a
separate 180-second timer.

It is produced by executing the restart on every third serviced minute.

Small deviations from exactly 180 seconds can result from scheduling and
network timing.

---

# 14. mDNS Runtime Comparison

A simultaneous passive capture of three physical TRVs produced the following
result:

| Firmware | Periodic mDNS sequence | Approximate period |
|---|---:|---:|
| 2.1.0 | not observed during ~13-minute capture | — |
| 2.1.3 | confirmed | ~60 s |
| 2.2.4 stock | confirmed | ~180 s |

The 2.1.3 device repeatedly produced approximately:

```text
probe
probe
probe
announcement
```

The 2.2.4 stock device produced the same characteristic sequence at the lower
frequency.

This establishes a real firmware-dependent recurring workload.

It does not establish its electrical magnitude.

---

# 15. mDNS-Only Patch B

A targeted experimental modification was developed for firmware 2.2.4.

Its purpose is to bypass only the periodic connected-maintenance
`mdns_resp_restart()` call.

The responder itself is not disabled.

Five direct callers of the restart-equivalent function were identified in
firmware 2.2.4:

| Caller | Call address | Purpose |
|---|---:|---|
| `0x1D918` | `0x1E0F4` | periodic connected-operation restart |
| `0x173B4` | `0x174A4` | conditional button-release action |
| `0x3D2F8` | `0x3D3E2` | successful mDNS netif registration |
| `0x3D430` | `0x3D5DC` | successful mDNS service registration |
| `0x63680` | `0x639EE` | successful connection-establishment path |

Patch B bypasses only the first path.

The program modification is:

```text
address 0x1E0F0

original:
BEQ 0x1E0F8
02 D0

patched:
B 0x1E0F8
02 E0
```

Only one program byte changes:

```text
0x1E0F1
D0 -> E0
```

The periodic call at `0x1E0F4` is skipped while execution continues through
the existing maintenance path.

Other identified mDNS restart callers remain intact.

---

# 16. Runtime Validation of Patch B

Patch B was tested independently on a physical TRV running firmware 2.2.4.

The beacon-recovery mechanism was intentionally left unchanged.

Passive packet capture over multiple expected stock restart periods observed:

```text
0 periodic mDNS packets
```

during the monitored test window.

Normal IP and cloud connectivity remained operational.

This provides strong finite-window evidence that Patch B suppresses the
targeted recurring mDNS restart.

It does **not** prove that the device can never emit mDNS traffic.

The event-driven mDNS paths intentionally remain present.

---

# 17. mDNS and Beacon-Recovery Isolation

The mDNS-only experiment also tested whether periodic mDNS activity was
required for the recurring 2.2.4 beacon-recovery behavior.

After Patch B:

```text
periodic mDNS bursts
        ↓
suppressed
```

but:

```text
Beacon skip error! Attempt recovery
        ↓
state 1
        ↓
approximately five seconds
        ↓
state 3
```

continued to occur.

The recovery was also observed with good RSSI, including approximately:

```text
-58 to -59 dBm
```

while the normal desired beacon skip remained:

```text
20
```

The supported conclusion is:

> The periodic mDNS restart is not required for the recurring beacon-recovery
> behavior under the tested conditions.

This does not prove that the two mechanisms can never interact.

It does establish that the observed beacon-recovery loop can continue when the
targeted periodic mDNS restart has been suppressed.

---

# 18. Wake ACK Change

The WF200 wake-ACK wait changes between firmware 2.1.0 and 2.1.3.

Simplified:

```text
2.1.0:
maximum requested wait = 3 ticks

2.1.3:
maximum requested wait = 5 ticks
+ timeout logging
```

The function can return earlier if the acknowledgement arrives.

Therefore this does **not** mean that every wake operation in 2.1.3 remains
awake for two additional ticks.

The change may:

- slightly increase some failed-wake waiting periods
- add logging on timeout
- improve tolerance for a slow acknowledgement

Its net energy effect is unresolved.

---

# 19. Event Notification Changes

Firmware 2.1.3 changes some event dissemination from immediate posting to
deferred/coalesced processing.

Instead of immediately propagating every relevant event, flags can be latched
and processed by the seconds-maintenance routine.

This may reduce repeated event bursts.

No direct new command-0x52, WUP or EM2 acquisition path was identified in this
change.

It is therefore not currently promoted as a battery-drain candidate.

---

# 20. 2.1.0 -> 2.1.3 Summary

| Mechanism | 2.1.0 | 2.1.3 | Energy relevance |
|---|---|---|---|
| Protected WF200 image | A | A | Controlled across boundary |
| FMAC | 3.3.2 | 3.3.2 | Controlled across boundary |
| Normal RSSI skip policy | Same | Same | No identified regression |
| Normal state-3 ordering | Same | Same | Inherited behavior |
| Conditional WUP/EM2 retention | Present | Present | Potentially important but inherited |
| State 5 | Absent | Present | Conditional/external |
| Named active override | No matching new route | Added | Conditional/external |
| Connected-minute mDNS restart | Not identified | Present | **New recurring workload** |
| Runtime periodic mDNS | Not observed in ~13 min | ~60 s | Runtime confirmed |
| Wake ACK maximum wait | 3 | 5 | Net effect unresolved |
| Notification handling | More direct | More coalesced | Could reduce bursts |

## Boundary assessment

The evidence supports the **technical possibility** of an energy-consumption
difference between 2.1.0 and 2.1.3.

The strongest newly identified recurring host-side difference is the periodic
mDNS restart.

It is now confirmed to generate recurring network traffic.

This does **not** prove that firmware 2.1.3 introduced the historical battery
drain.

---

# 21. 2.1.3 -> 2.1.8

The transition from 2.1.3 to 2.1.8 introduces another set of changes.

## Protected firmware

```text
WF200 image:
A -> B

FMAC:
3.3.2 -> 3.4.1

WF200 runtime:
3.12.2 -> 3.14.0
```

## Post-association power sequence

Firmware 2.1.8 changes the post-association C3 power-management sequence.

Simplified:

```text
2.1.3:

request state 3


2.1.8:

restore state 4
      |
      v
delay
      |
      v
request state 3
```

This is a real host-side change.

Its net energy effect is unresolved because, depending on the current state,
the restore operation can also terminate an existing temporary active hold
sooner.

It therefore cannot simply be interpreted as "extra awake time."

## MQTT retry behavior

Firmware 2.1.8 introduces changed MQTT failure backoff behavior.

This can potentially reduce repeated activity under some failure conditions.

It is therefore not automatically a battery-drain candidate.

---

# 22. 2.1.3 -> 2.1.8 Energy Assessment

The strongest candidates from the focused comparison remain:

1. changed protected WF200 / FMAC behavior
2. changed post-association C3 sequencing
3. actual WF200 power-save fallback or rejected command-0x52 behavior
4. conditional inherited sleep-resource retention
5. changed network retry behavior

No new unconditional steady-state host sleep failure was established.

The historical observation that firmware 2.1.8 exhibited relatively fast
battery drain remains important.

Static analysis has not established its cause.

Therefore the historical battery-drain introduction point could be earlier
than 2.1.8.

The current evidence does not justify treating either 2.1.3 or 2.1.8 as the
proven introduction point.

---

# 23. 2.1.8 -> 2.2.4

Firmware 2.2.4 introduces the largest known host-side change directly related
to beacon behavior.

Protected WLAN components also change:

```text
WF200 image:
B -> C

FMAC:
3.4.1 -> 3.7.0

WF200 runtime:
3.14.0 -> 3.16.1
```

Host-side changes include:

- WF200 statistics query command `0x66`
- beacon receive/missed/timing statistics
- calculation of `real_beacon_skip`
- recovery decision based on that value
- temporary state-1 recovery
- additional power-management retry behavior
- device power-save locking/wrappers
- changed command-0x52 payload handling

The periodic mDNS mechanism also remains present, although its observed
frequency is approximately once every three minutes rather than approximately
once per minute as observed on 2.1.3.

---

# 24. 2.2.4 Beacon Statistics

Firmware 2.2.4 queries WF200 statistics using command:

```text
0x66
```

The returned statistics include values corresponding to:

```text
beacon_rx_count
beacon_missed_count
tbtt_diff
```

The known recovery trigger is derived from `beacon_rx_count`.

The firmware stores a previous sample and computes approximately:

```text
delta =
    current_beacon_rx_count
    -
    previous_beacon_rx_count
```

It then calculates:

```text
real_beacon_skip =
    uint8_t(600 / delta)
```

The resulting 8-bit value is subsequently loaded as a signed byte when the
recovery condition is evaluated.

This signed interpretation is important.

The recovery predicate is effectively:

```text
real_beacon_skip != 0
&&
real_beacon_skip <= 2
```

`beacon_missed_count` is available in the statistics but is not the direct
known trigger of this recovery path.

The exact low-level WF200 semantics of the beacon counters remain an open
question.

---

# 25. 2.2.4 Beacon Recovery

Among the analyzed firmware versions, the known counter-derived
beacon-recovery mechanism is first identified in 2.2.4.

Simplified:

```text
WF200 command 0x66
        |
        v
beacon_rx_count
        |
        v
delta from previous sample
        |
        v
600 / delta
        |
        v
uint8 conversion
        |
        v
signed interpretation
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        v
state 1
        |
        v
approximately five seconds
        |
        v
restore normal/deferred state
        |
        v
typically state 3
```

On affected stock devices this sequence can repeat approximately once per
minute.

The approximately one-minute recurrence is associated with the host-side
`minutes_tick` processing.

It should not be interpreted as evidence of a separate internal WF200
60-second recovery timer.

---

# 26. Power-Save State During 2.2.4 Recovery

The recovery temporarily requests state 1.

Under the analyzed recovery path, state 1 represents a more active WLAN
configuration than the normal connected state 3.

During this temporary state:

```text
state 1
    more active / always-on WLAN configuration
    host deeper sleep blocked
```

After approximately five seconds, the firmware restores the saved or deferred
power-save state, normally:

```text
state 3
    Fast Power Save
    current desired beacon skip
```

No explicit transmit-power increase was identified in the recovery path.

The energy concern is therefore the temporary more-active WLAN and host
power-management state, not a demonstrated increase in RF transmit power.

The electrical cost of each recovery event remains unmeasured.

---

# 27. Experimental Patch A – Beacon Recovery

Patch A bypasses the identified 2.2.4 recovery entry while leaving the
statistics and normal RSSI-dependent beacon-skip logic intact.

Original instruction:

```text
0x1E1C8

BGT 0x1E22E
31 DC
```

Patched instruction:

```text
B 0x1E22E
31 E0
```

Only one program byte changes:

```text
0x1E1C9
DC -> E0
```

Patch A does not modify:

- normal RSSI thresholds
- desired beacon skip
- command-0x66 statistics collection
- `real_beacon_skip` calculation
- WF200 firmware
- periodic mDNS behavior
- normal cloud communication

Runtime testing has shown that the targeted recurring recovery is suppressed
while normal RSSI-dependent beacon-skip behavior remains operational.

This demonstrates control-flow isolation of the recovery mechanism.

It does **not** establish battery-life improvement.

---

# 28. Experimental Patch B – Periodic mDNS

Patch B independently suppresses the recurring connected-maintenance mDNS
restart.

Original instruction:

```text
0x1E0F0

BEQ 0x1E0F8
02 D0
```

Patched instruction:

```text
B 0x1E0F8
02 E0
```

Only one program byte changes:

```text
0x1E0F1
D0 -> E0
```

The modification bypasses:

```text
network-interface argument load
        +
BL mdns_resp_restart()
```

for the periodic maintenance path.

Other identified mDNS restart callers remain intact.

Runtime packet capture confirmed suppression of the targeted periodic mDNS
bursts over multiple expected stock restart periods.

Beacon recovery continued on the Patch B device.

Therefore the periodic mDNS restart is not required for the observed
beacon-recovery loop under the tested conditions.

---

# 29. Combined Patch A+B

Patch A and Patch B were subsequently combined.

The two program changes are:

```text
Patch B:
0x1E0F1
D0 -> E0

Patch A:
0x1E1C9
DC -> E0
```

In the verified GBL container, the corresponding changed bytes are:

```text
0x00024645   D0 -> E0
0x0002471D   DC -> E0
```

The rebuilt GBL also contains four changed CRC bytes.

Verified combined GBL:

```text
Size:
1,106,384 bytes

CRC32:
0xBAEB8265

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61
```

Patched main PROGRAM SHA-256:

```text
06742a2632a3d45cf697b8be85045914d004f30644dad17b3d0d20012c87c61b
```

The combined modification therefore targets two independently identified
recurring mechanisms:

```text
Patch A
    beacon-recovery entry bypass

Patch B
    periodic mDNS restart bypass
```

---

# 30. Combined Runtime Validation

A physical TRV running the combined Patch A+B has been monitored under normal
connected operation.

During the monitored tests:

```text
periodic mDNS burst
    not observed
```

and:

```text
Beacon skip error! Attempt recovery
    not observed
```

The recurring state-1 recovery sequence was also absent during the multi-hour
debug-log observation.

Normal RSSI-dependent beacon-skip behavior remained active.

Cloud connectivity remained operational during the tested period.

This provides runtime evidence that Patch A and Patch B can coexist and
suppress their respective targeted mechanisms.

The observation window is finite.

It does **not** prove indefinite stability or long-term battery improvement.

---

# 31. Current Multi-Version Model

The current evidence supports a multi-mechanism model rather than a single
simple regression.

Conceptually:

```text
2.1.0
│
├── inherited conditional WUP / EM2 retention path
├── mDNS responder exists
└── no comparable periodic mDNS burst observed during ~13-minute test
│
▼
2.1.3
│
├── recurring connected-maintenance mDNS restart
├── runtime mDNS interval ≈ 60 s
├── state 5 / psovrd2
├── named active override paths
└── wake-ACK timing change
│
▼
2.1.8
│
├── protected WF200 image A -> B
├── FMAC / WF200 runtime update
├── changed post-association C3 sequence
└── historical fast battery drain observed
│
▼
2.2.4
│
├── protected WF200 image B -> C
├── FMAC / WF200 runtime update
├── periodic mDNS retained
│     └── every third serviced minute
│         runtime ≈ 180 s
├── command-0x66 beacon statistics
├── beacon_rx_count delta processing
├── calculated real_beacon_skip
└── recurring beacon-recovery mechanism
      └── temporary state 1
          ≈ 5 s
          restore state 3
```

This model allows several mechanisms to coexist.

The historical battery drain does not have to have the same root cause as the
additional 2.2.4 recovery loop.

Likewise, the mDNS-only A/B experiment shows that the periodic mDNS restart is
not required for the observed beacon-recovery loop.

---

# 32. Current Candidate Assessment

## 2.1.0 -> 2.1.3

### Periodic mDNS restart

Status:

```text
new host-side recurring mechanism
+
static evidence
+
runtime confirmation
```

Energy relevance:

```text
plausible
but quantitatively unknown
```

This remains the strongest newly identified recurring ordinary-connected
host-side difference at this boundary.

### Named active override

Real state-1/WUP behavior exists, but the identified entry is externally
triggered.

No autonomous periodic caller was identified.

### State 5 / psovrd2

The mechanism is real and can be externally prolonged.

No autonomous periodic state-5 entry was identified.

### WUP / EM2 retention

Potentially important if triggered, but already present in 2.1.0.

It therefore does not establish the 2.1.0 -> 2.1.3 boundary.

### Wake ACK change

A real change exists from maximum wait 3 to 5.

Its energy direction remains unresolved.

---

## 2.1.3 -> 2.1.8

Important changes include:

- new protected WF200 image
- new FMAC generation
- new WF200 runtime
- changed post-association C3 sequence
- changed MQTT failure backoff

The historical observation of relatively fast battery drain on 2.1.8 remains
important.

No single host-side mechanism has yet been established as its cause.

---

## 2.1.8 -> 2.2.4

Firmware 2.2.4 adds a clearly identified additional recurring mechanism:

```text
beacon statistics
        ↓
real_beacon_skip
        ↓
qualifying condition
        ↓
temporary state-1 recovery
```

The mechanism is:

```text
statically identified
+
runtime observed
+
experimentally bypassed
```

It is therefore a strong candidate for **additional** energy consumption in
2.2.4.

Its quantitative battery effect remains unknown.

---

# 33. mDNS vs Beacon Recovery

The project initially considered the possibility that periodic mDNS traffic
might disturb beacon timing or counters and thereby cause the recovery loop.

The isolated Patch B experiment tested the strong form of this hypothesis.

Result:

```text
periodic mDNS restart suppressed

but

beacon recovery continues
```

Therefore:

> Periodic mDNS restart is not required for the recurring beacon-recovery loop
> under the tested conditions.

The current model is:

```text
periodic mDNS restart
        |
        +---- recurring network / processing workload
        |
        +---- possible energy contribution


beacon-statistics processing
        |
        v
real_beacon_skip
        |
        v
beacon recovery
        |
        +---- temporary active power-management state
        |
        +---- possible energy contribution
```

A secondary interaction under some network conditions is not categorically
excluded.

However, the available evidence does not support treating the beacon recovery
as merely a consequence of periodic mDNS.

---

# 34. What Is Proven

## Across 2.1.0 and 2.1.3

- protected WF200 image is identical
- FMAC generation is identical
- normal RSSI mapping is equivalent
- normal state-3 ordering is materially equivalent
- the conditional final-sleep/WUP/EM2 retention path exists in both

## New or changed in 2.1.3

- state 5
- named `psovrd2` entry
- named active override entry paths
- connected-minute mDNS restart
- longer wake-ACK maximum wait and timeout logging
- changed event-coalescing behavior

## Runtime mDNS evidence

- no comparable periodic mDNS traffic from 2.1.0 was observed during the
  approximately 13-minute simultaneous capture
- 2.1.3 generated recurring mDNS probe/announcement bursts at approximately
  60-second intervals
- stock 2.2.4 generated corresponding bursts at approximately 180-second
  intervals
- the 2.2.4 interval is explained by a restart on every third serviced minute
- Patch B suppressed the targeted periodic 2.2.4 mDNS behavior during the
  monitored test window

## 2.2.4 beacon-recovery evidence

- command `0x66` supplies WF200 beacon statistics
- `beacon_rx_count` is used in the known `real_beacon_skip` calculation
- the firmware computes approximately `uint8_t(600 / delta)`
- the result is subsequently interpreted as a signed byte
- the known recovery predicate accepts nonzero values `<= 2`
- recovery temporarily enters state 1
- restoration occurs approximately five seconds later
- normal state 3 is normally restored
- recovery can recur approximately once per minute
- recovery can occur with good RSSI and desired skip 20
- Patch A suppresses the targeted recovery entry
- Patch B does not suppress the recovery
- combined Patch A+B suppresses both targeted behaviors during the monitored
  tests

---

# 35. What Is Not Proven

The following conclusions are **not** currently justified:

```text
2.1.0 has no battery drain.

2.1.3 definitely introduced the battery drain.

2.1.8 introduced the original battery drain.

mDNS causes the historical battery drain.

State 5 causes the historical battery drain.

The WUP / EM2 retention path causes the historical battery drain.

The 2.2.4 beacon recovery is the complete root cause.

Periodic mDNS causes the beacon-recovery loop.

Poor RSSI is required for beacon recovery.

Patch A fixes battery life.

Patch B fixes battery life.

Patch A+B fixes the historical battery-drain problem.
```

The exact semantics of the WF200 beacon counters also remain incompletely
understood.

In particular, further work is required to establish why the
`beacon_rx_count` deltas can produce values that firmware 2.2.4 interprets as
an invalid `real_beacon_skip`.

---

# 36. Evidence Classification

## Proven by static analysis

- 2.1.0 and 2.1.3 share the same protected WF200 image
- their normal state-3 power-management ordering is materially equivalent
- the conditional WUP/EM2 retention path already exists in 2.1.0
- 2.1.3 introduces state 5
- state 5 is associated with external `psovrd2`
- state 5 requests Fast PS with skip 10
- state 5 normally restores after approximately 180 serviced seconds
- repeated external requests can refresh that countdown
- no autonomous periodic state-5 entry was identified
- 2.1.3 introduces a connected-minute mDNS restart caller
- the mDNS path reaches UDP packet generation
- 2.2.4 retains the periodic mDNS mechanism
- 2.2.4 executes the periodic restart every third serviced minute
- 2.2.4 queries WF200 beacon statistics through command `0x66`
- `beacon_rx_count` participates in the known `real_beacon_skip` calculation
- `real_beacon_skip` is narrowed to 8 bits and subsequently interpreted signed
- the known recovery predicate is nonzero and `<= 2`
- the recovery enters state 1
- the recovery later restores the saved/deferred state
- Patch A bypasses the recovery entry
- Patch B bypasses only the periodic mDNS restart call

## Proven by runtime observation

- 2.1.3 produces recurring mDNS bursts at approximately 60-second intervals
- stock 2.2.4 produces recurring mDNS bursts at approximately 180-second
  intervals
- no comparable periodic mDNS traffic from the 2.1.0 reference was observed
  during the approximately 13-minute comparison
- stock 2.2.4 can repeatedly enter beacon recovery approximately once per
  minute
- beacon recovery can occur with good RSSI
- Patch A suppresses the targeted recovery
- Patch B suppresses the targeted periodic mDNS traffic during the monitored
  capture
- Patch B does not suppress the recurring beacon recovery
- combined Patch A+B suppresses both targeted recurring mechanisms during the
  monitored tests

## Strongly supported interpretation

- periodic mDNS is a real additional recurring workload compared with the
  observed 2.1.0 reference behavior
- the periodic mDNS restart is not required for the observed beacon-recovery
  loop under the tested conditions
- the beacon-recovery loop is not simply a poor-RSSI phenomenon
- Patch A and Patch B isolate two distinct host-side mechanisms
- the historical battery-drain problem is likely more complex than the
  2.2.4-specific beacon-recovery mechanism alone

## Plausible but not quantitatively proven

- periodic mDNS activity contributes additional energy consumption
- recurring state-1 beacon recovery contributes additional energy consumption
- retained WUP/EM2 resources can materially increase idle consumption if the
  inherited failure path occurs
- multiple mechanisms may contribute cumulatively to battery drain

## Unresolved

- exact electrical cost of the periodic mDNS sequence
- exact electrical cost of each beacon-recovery event
- exact WF200 `beacon_rx_count` semantics
- treatment of intentionally skipped beacons in the WF200 statistics
- influence of DTIM and multicast/broadcast behavior on the counters
- reason the resulting counter delta is interpreted as an invalid
  `real_beacon_skip`
- runtime frequency of the inherited WUP/EM2 retention failure
- original historical battery-drain introduction point
- quantitative long-term battery improvement from Patch A
- quantitative long-term battery improvement from Patch B
- quantitative long-term battery improvement from combined Patch A+B

---

# 37. Current Runtime Research

The immediate short-term mechanism-isolation experiments have now been
completed.

The project has established:

```text
stock 2.2.4
    periodic mDNS present
    beacon recovery present

Patch A only
    beacon recovery suppressed
    periodic mDNS unchanged

Patch B only
    periodic mDNS suppressed
    beacon recovery remains

Patch A+B
    periodic mDNS suppressed
    beacon recovery suppressed
```

The next phase is long-term battery observation rather than another immediate
control-flow patch.

The preferred comparison is:

```text
stock 2.2.4
        vs.
combined Patch A+B
```

with additional old-firmware references retained where useful.

Relevant measurements include:

- battery percentage
- battery voltage
- uptime
- firmware version
- beacon statistics where available
- recovery counters where available
- RSSI
- desired beacon skip
- motor activity

Cross-device comparisons require caution because individual batteries, voltage
curves, valve mechanics, calibration state and motor activity can differ.

Where possible, longer observation periods and repeated same-device tests are
more informative than short percentage comparisons.

---

# 38. Current Research Direction

The current priorities are:

1. continue long-term battery logging
2. include motor activity in the battery dataset once a reliable counter and
   reset/overflow interpretation are established
3. compare stock 2.2.4 against combined Patch A+B over longer periods
4. retain 2.1.0 as an old-firmware behavioral reference without assuming that
   it is universally battery-drain free
5. investigate the remaining WF200 beacon-counter semantics
6. determine why firmware 2.2.4 can derive qualifying `real_beacon_skip`
   values from `beacon_rx_count`
7. keep the mDNS and beacon-recovery mechanisms analytically separate unless
   new evidence demonstrates an interaction
8. avoid modifying the inherited WUP/EM2 failure path until its complete
   hardware-state semantics are understood

No additional firmware mechanism should be patched merely because it is
theoretically energy relevant.

The current A+B experiment already provides two independently tested
modifications suitable for long-term observation.

---

# 39. Current Scientific Interpretation

The available evidence supports the following conservative model:

```text
historical battery drain
        |
        +---- introduction point unknown
        |
        +---- may predate firmware 2.2.4
        |
        +---- multiple mechanisms possible
                  |
                  +---- recurring mDNS activity from 2.1.3 onward
                  |
                  +---- protected WF200 / FMAC changes
                  |
                  +---- post-association behavior changes
                  |
                  +---- inherited conditional sleep-resource failure
                  |
                  +---- 2.2.4 beacon-recovery mechanism
```

The important distinction is between:

```text
mechanism identified
```

and:

```text
battery causation established
```

The project has identified and experimentally isolated multiple real firmware
mechanisms.

It has **not** yet established their quantitative battery cost.

This distinction should be preserved in all repository documentation,
GitHub issues and public discussion.

---

# 40. Related Documents

- [`Power Management and Sleep`](power-management-and-sleep.md)
- [`Beacon RX Counter`](beacon-rx-counter.md)
- [`Real Beacon Skip`](real-beacon-skip.md)
- [`Recovery Mechanism`](recovery-mechanism.md)
- [`AP Selection and Roaming`](ap-selection-and-roaming.md)
- [`Periodic mDNS Restart`](mdns-periodic-restart.md)
- [`Experimental Beacon-Recovery Patch`](../patch/README.md)
- [`Battery Testing`](../testing/battery-testing.md)