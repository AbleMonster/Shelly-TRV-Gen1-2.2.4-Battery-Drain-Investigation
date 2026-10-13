# Periodic mDNS Restart

## Overview

Firmware comparison of the Shelly TRV Gen1 identified a recurring mDNS
maintenance mechanism that differs between firmware generations.

The mDNS responder itself is not new.

Firmware 2.1.0 already contains the mDNS responder implementation.

The important change identified in firmware 2.1.3 is an additional recurring
connected-maintenance caller that restarts the mDNS probing process while the
device is connected.

Static analysis and runtime packet capture have now confirmed the mechanism on
real devices.

Observed runtime behavior:

```text
Firmware 2.1.0
    no comparable periodic mDNS burst observed
    during an approximately 13-minute capture

Firmware 2.1.3
    periodic mDNS probe / announcement burst
    approximately every 60 seconds

Firmware 2.2.4 stock
    periodic mDNS probe / announcement burst
    approximately every 180 seconds
```

Further reverse engineering of firmware 2.2.4 established that the
approximately 180-second interval is not implemented as a dedicated
180-second timer.

Instead, the relevant maintenance routine is serviced on minute boundaries and
a counter causes the mDNS restart to execute every third serviced minute.

An experimental mDNS-only patch was subsequently developed and tested.

The patch suppresses only this periodic restart call while leaving the mDNS
responder itself and the other identified restart callers intact.

Runtime testing confirmed that:

- the periodic approximately 180-second mDNS bursts disappeared
- normal IP and cloud connectivity remained operational
- the stock beacon-skip recovery mechanism remained active
- beacon-skip recovery continued to occur approximately once per minute

This last result is important.

Under the tested conditions, the periodic mDNS restart is **not required** for
the recurring beacon-skip recovery observed in firmware 2.2.4.

The electrical energy cost of the periodic mDNS activity and its contribution
to the historical battery-drain problem remain unknown.

---

# Important Distinction

This investigation does **not** show that mDNS was introduced in firmware
2.1.3.

The responder implementation already exists in firmware 2.1.0.

The relevant difference is:

```text
mDNS responder
```

versus:

```text
periodically restarting the mDNS probing sequence
```

The second behavior is the mechanism investigated here.

This distinction is important for patch design.

The experimental patch does **not** disable mDNS globally.

It suppresses only the recurring connected-maintenance restart in firmware
2.2.4.

Other mDNS paths remain intact.

---

# Static Firmware Comparison

## Firmware 2.1.0

Static analysis found the mDNS responder implementation in firmware 2.1.0.

However, the connected maintenance path examined in 2.1.0 does not contain the
later recurring call that restarts mDNS probing.

The relevant behavior is therefore approximately:

```text
mDNS responder available
        ↓
no identified connected-minute restart caller
```

This does not mean that firmware 2.1.0 can never transmit mDNS traffic.

Other events may still cause normal mDNS operation.

The important observation is narrower:

> The recurring connected-maintenance restart identified in later firmware was
> not found in the corresponding 2.1.0 path.

---

## Firmware 2.1.3

Firmware 2.1.3 adds a recurring connected-maintenance call to the function
identified as the equivalent of:

```text
mdns_resp_restart()
```

The reconstructed path is approximately:

```text
connected maintenance
        ↓
mdns_resp_restart()
        ↓
reset probing state
        ↓
schedule probe callback
        ↓
probe packet construction
        ↓
UDP / IPv4 output
        ↓
mDNS announcement after successful probing
```

Runtime testing shows that this mechanism operates approximately once per
minute in firmware 2.1.3.

---

## Firmware 2.2.4

Firmware 2.2.4 retains the recurring restart mechanism, but its scheduling
differs from the approximately 60-second behavior observed in firmware 2.1.3.

Runtime packet capture showed an approximately 180-second interval.

Subsequent static analysis identified the reason.

The relevant path is:

```text
firmware-second dispatcher
        ↓
changed second value
and
seconds % 60 == 0
        ↓
minute maintenance
        ↓
increment maintenance counter
        ↓
counter % 3 == 0
        ↓
connected / IPv4 predicate
        ↓
mdns_resp_restart()
```

Therefore the approximately 180-second behavior is best described as:

```text
every third serviced minute
```

rather than:

```text
dedicated 180-second timer
```

Missed scheduler boundaries or other scheduling effects can therefore cause
small deviations from an exact 180-second interval.

---

# Firmware 2.2.4 Restart Function

The firmware 2.2.4 function identified as the `mdns_resp_restart()` equivalent
is located at:

```text
0x0003D6C8
```

The function identification is supported by its implementation and associated
mDNS assertion string.

For a registered mDNS network interface, the function approximately performs:

```text
if already probing:
    cancel existing probe timeout

reset probe counter

set responder state = probing

schedule probe callback
```

The scheduled callback is located at:

```text
0x0003D264
```

The initial scheduling delay includes a randomized component based on modulo
250.

The exact real-time interpretation of that internal delay value is less useful
than the directly observed packet timing.

---

# Direct Callers in Firmware 2.2.4

Static analysis identified five direct callers of the
`mdns_resp_restart()`-equivalent function.

| Caller | Call instruction | Role |
|---|---:|---|
| `0x1D918` | `0x1E0F4` | periodic connected-operation maintenance |
| `0x173B4` | `0x174A4` | conditional button-release path |
| `0x3D2F8` | `0x3D3E2` | successful mDNS network-interface registration |
| `0x3D430` | `0x3D5DC` | successful mDNS service registration |
| `0x63680` | `0x639EE` | successful connection-establishment path |

This distinction is critical.

The experimental patch targets only:

```text
0x1D918
    ↓
periodic connected-operation restart
    ↓
BL 0x3D6C8 at 0x1E0F4
```

The other identified callers are not modified.

Therefore the patch should not be described as:

```text
disable mDNS
```

The correct description is:

```text
suppress the recurring connected-maintenance mDNS restart
```

---

# Probe Sequence

The probe callback checks the current probe counter.

While fewer than three successful probes have completed, it attempts to
generate and transmit another probe.

Conceptually:

```text
restart
   ↓
probe 1
   ↓
probe 2
   ↓
probe 3
   ↓
announcement
```

A successful probe advances the probe counter.

After the required probes have completed, the responder transitions into the
announced state and transmits an mDNS announcement.

Observed traffic uses:

```text
UDP port 5353
```

with the IPv4 multicast destination:

```text
224.0.0.251
```

Packet captures do not necessarily contain every packet from every burst, so
individual captured bursts should not be assumed to contain exactly the same
number of packets.

---

# Conditional Retry Behavior

Static analysis identified an additional detail.

If a probe cannot be successfully completed, the probe counter may not advance.

Examples include conditions such as:

```text
IPv4 address unavailable
```

or:

```text
probe construction / transmission returns an error
```

In such a situation another callback can be scheduled without reaching the
normal three-probe completion point.

No explicit small per-run retry limit was identified in the examined path.

The next periodic restart can also reset the probing process again.

Therefore the normal successful sequence and a failure/retry sequence must be
distinguished.

The runtime captures described below primarily show the normal successful
sequence.

---

# Runtime Validation – Firmware Comparison

A passive runtime packet capture was performed on 2026-10-11.

Three physical Shelly TRV Gen1 devices were monitored simultaneously.

| Device | Firmware | Purpose |
|---|---|---|
| `.11` | 2.1.0 | old firmware reference |
| `.77` | 2.1.3 at time of comparison | periodic-restart reference |
| `.229` | 2.2.4 stock | stock comparison |

TShark was used on the same local network with UDP port 5353 filtered for the
three devices.

The observation period was approximately 13 minutes.

The purpose of this test was not to measure energy.

It was designed to determine whether the mDNS behavior predicted by static
analysis was observable on real devices.

---

# Runtime Result – Firmware 2.1.0

No mDNS packets from the firmware 2.1.0 reference device were observed during
the approximately 13-minute simultaneous capture.

The device remained connected during the observation.

This result is consistent with the static comparison:

```text
mDNS responder exists
```

but:

```text
no recurring connected-maintenance restart was identified
```

The runtime result must not be generalized to:

```text
Firmware 2.1.0 never sends mDNS.
```

The supported conclusion is narrower:

> No periodic mDNS probe / announcement behavior comparable to the later
> firmware versions was observed during this test window.

---

# Runtime Result – Firmware 2.1.3

Firmware 2.1.3 showed a strong and repeatable periodic pattern.

A normal complete burst consisted approximately of:

```text
probe
probe
probe
announcement
```

One captured example:

```text
59.699110 s   probe
60.005565 s   probe
60.211304 s   probe
60.519855 s   announcement
```

Additional burst starts were observed at approximately:

```text
0.000 s
59.699 s
119.809 s
179.815 s
239.616 s
299.725 s
359.639 s
419.740 s
480.154 s
539.758 s
599.560 s
659.769 s
719.770 s
779.885 s
```

The dominant period is approximately:

```text
60 seconds
```

This behavior continued throughout the capture.

Static analysis and runtime observation therefore agree that firmware 2.1.3
contains a recurring mDNS restart mechanism operating approximately once per
minute under the tested conditions.

---

# Runtime Result – Firmware 2.2.4 Stock

Stock firmware 2.2.4 also generated the characteristic mDNS probing sequence.

A captured sequence included:

```text
117.554727 s   probe
117.761173 s   probe
117.964812 s   probe
118.272223 s   announcement
```

Further burst starts were observed at:

```text
117.554727 s
297.779351 s
477.492032 s
657.412999 s
```

Calculated intervals:

```text
297.779351 - 117.554727 = 180.224624 s

477.492032 - 297.779351 = 179.712681 s

657.412999 - 477.492032 = 179.920967 s
```

The observed period is therefore approximately:

```text
180 seconds
```

The repeatability strongly supports the periodic mechanism identified by
static analysis.

The later firmware analysis further established that this corresponds to every
third serviced minute rather than a dedicated 180-second timer.

---

# Runtime Comparison

Current experimental result:

| Firmware / configuration | Periodic mDNS sequence | Approximate period |
|---|---:|---:|
| 2.1.0 stock | not observed during capture | — |
| 2.1.3 stock | confirmed | ~60 s |
| 2.2.4 stock | confirmed | ~180 s |
| 2.2.4 + mDNS-only Patch B | not observed during monitored capture | — |
| 2.2.4 + combined Patch A+B | not observed during monitored capture | — |

This provides the current firmware and experimental timeline:

```text
2.1.0
│
│ mDNS responder exists
│ no periodic sequence observed during ~13-minute capture
│
▼
2.1.3
│
│ recurring restart active
│ ~60-second runtime period
│
▼
2.2.4 stock
│
│ recurring restart retained
│ every third serviced minute
│ ~180-second runtime period
│
▼
2.2.4 + Patch B
│
│ periodic restart bypassed
│ no periodic mDNS burst observed during monitored capture
│ beacon recovery still active
│
▼
2.2.4 + Patch A+B
│
│ periodic mDNS restart bypassed
│ beacon-recovery entry bypassed
│ both targeted recurring mechanisms suppressed during testing
```

---

# Experimental Patch B

## Objective

Patch B was designed to suppress only the recurring connected-maintenance call
to `mdns_resp_restart()`.

It was intentionally designed not to modify:

- the mDNS responder implementation
- mDNS network-interface registration
- mDNS service registration
- connection-establishment mDNS behavior
- the UDP receive path
- beacon statistics
- beacon-skip calculation
- beacon-recovery logic
- WLAN power-management state selection
- RSSI thresholds
- cloud handling
- thermostat control

This makes it suitable for isolating the periodic mDNS mechanism from the
separate beacon-recovery mechanism.

---

# Exact Patch Location

The relevant firmware 2.2.4 instruction is located at:

```text
Virtual address:          0x0001E0F0
program.bin file offset:  0x0001E0F0
```

Original instruction:

```text
BEQ 0x0001E0F8
```

Original bytes:

```text
02 D0
```

Patched instruction:

```text
B 0x0001E0F8
```

Patched bytes:

```text
02 E0
```

Only one byte changes:

```text
program.bin offset 0x0001E0F1

D0 -> E0
```

In the verified GBL container, the corresponding changed byte is located at:

```text
GBL offset 0x00024645
```

The instruction is a 16-bit Thumb instruction.

---

# Patch Control-Flow Effect

The original code around the patch site is:

```text
0x1E0F0   BEQ 0x1E0F8
0x1E0F2   load network-interface argument
0x1E0F4   BL 0x3D6C8
0x1E0F8   existing continuation
```

The original conditional behavior is therefore approximately:

```text
condition says skip
        ↓
0x1E0F8

otherwise
        ↓
load netif
        ↓
mdns_resp_restart()
        ↓
0x1E0F8
```

Patch B changes the conditional branch into an unconditional branch:

```text
0x1E0F0   B 0x1E0F8
```

Result:

```text
periodic maintenance
        ↓
existing condition/calculation
        ↓
unconditionally branch to 0x1E0F8
        ↓
continue normal maintenance
```

The network-interface load at `0x1E0F2` and the periodic call at `0x1E0F4` are
therefore bypassed.

Execution resumes at the existing continuation.

The patch does not split an instruction, alter stack depth, change processor
mode or redirect execution to newly introduced code.

---

# Patch Verification Window

Original bytes beginning at `0x1E0F0`:

```text
02 D0 29 48 1F F0 E8 FA 12 4B
```

Patched bytes:

```text
02 E0 29 48 1F F0 E8 FA 12 4B
```

The four-byte instruction:

```text
1F F0 E8 FA
```

is the existing call to the `mdns_resp_restart()` equivalent.

It remains physically present in the firmware image.

Patch B only makes the periodic path branch around it.

---

# Why the Responder Is Not Disabled

Five direct restart callers were identified.

Patch B modifies the control flow of only the periodic caller.

The following paths remain unmodified:

```text
button-related conditional restart

mDNS network-interface registration

mDNS service registration

successful connection-establishment restart
```

The responder's receive processing also remains intact.

Therefore the experimental result must not be described as:

```text
mDNS disabled
```

Instead:

> The recurring connected-maintenance restart was suppressed while the mDNS
> responder and the other identified restart paths were retained.

---

# Runtime Validation – mDNS-Only Patch B

A physical TRV was updated from firmware 2.1.3 to firmware 2.2.4 containing
only Patch B.

The beacon-recovery mechanism was deliberately left unchanged.

A passive TShark capture was then performed for the patched device using a
filter equivalent to:

```text
udp port 5353 and host <patched-device>
```

During a monitored interval of at least approximately 10 minutes:

```text
0 mDNS packets captured
```

In stock firmware 2.2.4, the targeted periodic sequence would normally be
expected approximately every 180 seconds.

The absence of the recurring bursts over multiple expected periods therefore
provides strong runtime evidence that Patch B successfully suppresses the
targeted periodic restart mechanism.

This is still a finite observation window.

It does **not** prove that the device can never generate an mDNS packet.

That would be inconsistent with the design of the patch because the responder
and event-driven restart paths intentionally remain available.

---

# Beacon-Recovery Isolation Test

The mDNS-only Patch B test also provided an important mechanism-isolation
experiment.

Patch B removed the targeted periodic mDNS bursts while intentionally leaving
the stock firmware 2.2.4 beacon-recovery code unchanged.

After the patch, the device continued to produce:

```text
minutes_tick: Beacon skip error! Attempt recovery
```

followed by:

```text
Enter powersave state 1
```

and approximately five seconds later a return to:

```text
Enter powersave state 3 (skip N)
```

The sequence continued approximately once per minute.

This was observed even during periods with good RSSI, including approximately:

```text
-58 to -59 dBm
```

with:

```text
current beacon skip = 20
```

Therefore poor RSSI is not required for the observed recovery behavior.

More importantly:

```text
periodic mDNS restart suppressed
        +
beacon recovery still recurring
```

demonstrates that the periodic mDNS restart is **not required** for the
beacon-recovery loop under the tested conditions.

---

# Revised Relationship to Beacon-Skip Recovery

Before the mDNS-only experiment, one plausible hypothesis was:

```text
periodic mDNS restart
        ↓
changes WLAN / beacon timing or counter behavior
        ↓
affects real_beacon_skip
        ↓
triggers beacon recovery
```

The isolated Patch B experiment does not support this as a necessary causal
chain.

The experimental result was:

```text
periodic mDNS bursts disappear

but

beacon recovery continues
```

Therefore the current supported interpretation is:

> The periodic mDNS restart and the beacon-recovery mechanism can operate
> independently under the tested conditions.

More precisely:

> The recurring periodic mDNS restart is not necessary for the recurring
> beacon-recovery behavior observed on the Patch B test device.

This does not prove that the mechanisms can never influence one another under
any network condition.

It does, however, reject the stronger hypothesis that the periodic mDNS
restart is required to trigger the observed recovery loop.

---

# Good RSSI Result

The Patch B experiment also strengthened another finding.

The recurring beacon-recovery sequence was observed with approximately:

```text
RSSI = -58 to -59 dBm
```

At that signal level the normal RSSI-dependent policy selected:

```text
beacon skip = 20
```

The recovery therefore cannot be explained simply as:

```text
poor RSSI
    ↓
low-quality connection
    ↓
recovery
```

A qualifying internal beacon-statistics condition can occur even while the
reported RSSI is good and the desired beacon-skip value remains 20.

This result belongs primarily to the beacon-recovery investigation, but it is
important here because it was obtained during the mDNS-isolation experiment.

---

# Combined Patch A+B

Following the isolated Patch B test, both independently identified recurring
mechanisms were combined into one experimental firmware modification.

The two patches are:

```text
Patch A
Beacon-recovery entry bypass

program.bin:
0x1E1C8   31 DC -> 31 E0

changed byte:
0x1E1C9   DC -> E0
```

and:

```text
Patch B
Periodic mDNS restart bypass

program.bin:
0x1E0F0   02 D0 -> 02 E0

changed byte:
0x1E0F1   D0 -> E0
```

The corresponding GBL changed-byte locations are:

```text
Patch B: 0x00024645   D0 -> E0
Patch A: 0x0002471D   DC -> E0
```

The remaining changed bytes in the GBL are the rebuilt CRC32 field.

The combined firmware has been validated with:

```text
Size:
1,106,384 bytes

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61

CRC32:
0xBAEB8265
```

The patched main PROGRAM payload has SHA-256:

```text
06742a2632a3d45cf697b8be85045914d004f30644dad17b3d0d20012c87c61b
```

---

# Combined Runtime Validation

A physical TRV was updated to firmware 2.2.4 containing both Patch A and
Patch B.

Runtime testing then examined the two targeted recurring mechanisms
independently.

## Periodic mDNS

A passive packet capture did not observe the targeted recurring mDNS sequence
during the monitored test window.

This is consistent with the isolated Patch B result.

## Beacon recovery

Multi-hour debug-log observation did not show:

```text
Beacon skip error! Attempt recovery
```

or the corresponding recurring transition into:

```text
Enter powersave state 1
```

Normal RSSI-dependent beacon-skip operation remained visible, including
operation with:

```text
beacon skip = 20
```

The combined experiment therefore provides runtime evidence that the two
targeted control-flow modifications can coexist.

It does **not** yet establish long-term battery improvement.

---

# Network Activity

A normal successful stock restart can produce approximately:

```text
3 probe packets
+
1 announcement packet
```

For firmware 2.1.3 at approximately one cycle per minute, this corresponds
conceptually to roughly:

```text
4 mDNS transmissions / minute
```

during normal successful operation.

For stock firmware 2.2.4 at approximately one cycle every three minutes, the
average rate is lower.

These values describe only the observed mDNS transmissions.

They do not describe total WLAN activity.

They also do not account for:

- retransmissions
- lower-layer WLAN traffic
- acknowledgements
- beacon reception
- cloud traffic
- controller traffic
- thermostat communication
- other firmware tasks

Packet count must therefore not be converted directly into battery
consumption.

---

# Relationship to WLAN Power Management

The mDNS restart mechanism creates periodic application and network activity.

Static analysis did not identify a long-lived WUP / EM2 resource acquired
directly by the mDNS responder itself.

The mDNS mechanism should therefore currently be classified as:

```text
recurring network / processing activity
```

rather than:

```text
confirmed permanent sleep lock
```

Transmission of mDNS packets necessarily requires the network subsystem to
perform work.

However, the duration of the resulting wake activity and its electrical cost
have not been measured.

---

# Relationship to WUP / EM2 Retention

A separate WLAN power-management failure path has been identified.

Under specific low-level failure conditions, the final device-sleep operation
can fail while a WLAN-owned WUP / EM2-blocking resource remains retained.

That mechanism is distinct from the periodic mDNS restart.

Importantly, the underlying retention failure path already exists in firmware
2.1.0.

No evidence currently demonstrates:

```text
mDNS restart
        ↓
direct WUP / EM2 retention failure
```

The isolated Patch B experiment also did not establish such a connection.

The mechanisms should therefore remain separate unless future runtime evidence
demonstrates an interaction.

---

# Energy Interpretation

Runtime capture establishes that the periodic mDNS mechanism generates real
additional network activity.

Compared with a condition in which the periodic restart does not occur, the
restart causes additional processing and packet transmission.

Its electrical cost has not been measured.

No direct electrical measurement has established:

```text
energy per restart

energy per probe

energy per announcement

wake duration caused by the sequence

battery capacity consumed per day

battery-runtime reduction
```

It is therefore valid to state:

> The periodic mDNS restart is a confirmed additional recurring workload and a
> technically plausible contributor to battery consumption.

It is not currently valid to state:

> The periodic mDNS restart causes the historical Shelly TRV battery-drain
> problem.

The mDNS-only Patch B experiment also establishes that suppressing the
periodic restart does not, by itself, suppress the recurring beacon-recovery
mechanism.

Long-term battery data are required to determine the practical contribution
of each mechanism.

---

# Why Firmware 2.1.0 Is Important

Firmware 2.1.0 remains a useful behavioral reference.

During the simultaneous runtime test:

```text
2.1.0
    no periodic mDNS bursts observed

2.1.3
    bursts approximately every 60 seconds

2.2.4
    bursts approximately every 180 seconds
```

The 2.1.0 device also remained reachable in practical operation.

This supports the view that continuously restarting mDNS probing is not
obviously required for basic IP connectivity.

However:

```text
basic IP reachability
```

is not equivalent to:

```text
mDNS service discovery
```

The experimental patch therefore deliberately preserves the responder and
event-driven mDNS paths rather than disabling mDNS globally.

---

# Evidence Status

## Proven by static analysis

- the mDNS responder already exists in firmware 2.1.0
- firmware 2.1.3 adds a recurring connected-maintenance restart
- firmware 2.2.4 retains the recurring restart mechanism
- the firmware 2.2.4 restart-equivalent function is located at `0x3D6C8`
- five direct callers of that function were identified
- the periodic caller is the call at `0x1E0F4`
- the firmware 2.2.4 periodic path is serviced through minute maintenance
- a counter modulo three gates the periodic restart
- the approximately 180-second behavior therefore corresponds to every third
  serviced minute rather than a dedicated 180-second timer
- the restart resets the probing state
- the restart schedules probe processing
- successful processing leads to probes and an announcement
- unsuccessful probe attempts can be retried
- Patch B bypasses only the identified periodic call site
- the other identified restart callers remain unmodified

## Proven by runtime observation

- firmware 2.1.3 produces recurring mDNS probe / announcement bursts
- the observed 2.1.3 period is approximately 60 seconds
- stock firmware 2.2.4 produces the same characteristic sequence
- the observed stock 2.2.4 period is approximately 180 seconds
- no comparable periodic mDNS traffic from the 2.1.0 reference was observed
  during the approximately 13-minute simultaneous capture
- the mDNS-only Patch B device produced no periodic mDNS traffic during a
  monitored interval spanning multiple expected stock restart periods
- the Patch B device remained connected during testing
- the Patch B device continued to enter the stock beacon-recovery path
- recurring beacon recovery continued even with good RSSI and beacon skip 20
- the combined Patch A+B device showed no targeted periodic mDNS sequence
  during the monitored capture
- the combined Patch A+B device showed no recurring beacon-recovery entry
  during multi-hour debug-log observation

## Strongly supported interpretation

- Patch B suppresses the intended periodic mDNS restart mechanism
- periodic mDNS restart is not required for the observed recurring
  beacon-recovery loop under the tested conditions
- the two mechanisms can therefore be isolated experimentally
- poor RSSI is not required for the observed beacon-recovery loop
- Patch A and Patch B can coexist without immediately breaking the tested
  connected operation

## Not established

- exact electrical energy per mDNS restart
- exact wake duration caused by each restart
- quantitative battery-life impact of the periodic mDNS mechanism
- whether periodic mDNS can influence beacon statistics under some network
  conditions despite not being required for the observed recovery loop
- whether suppressing periodic mDNS materially improves long-term battery life
- whether the combined patch resolves the historical battery-drain problem
- whether firmware 2.1.0 never emits event-driven mDNS traffic

---

# Experimental Interpretation

The investigation initially considered a possible causal chain:

```text
periodic mDNS restart
        ↓
beacon timing / counter disturbance
        ↓
real_beacon_skip anomaly
        ↓
beacon recovery
```

The isolated Patch B experiment provides an important falsification test for
the strong form of that hypothesis.

Observed result:

```text
periodic mDNS restart
        ↓
suppressed

beacon recovery
        ↓
continues
```

Therefore the strong causal model:

```text
periodic mDNS restart is required for beacon recovery
```

is not supported.

The current model is instead:

```text
                 ┌─────────────────────────┐
                 │ periodic mDNS restart   │
                 │ recurring WLAN traffic  │
                 └────────────┬────────────┘
                              │
                              │ possible energy contribution
                              ▼
                       battery workload


                 ┌─────────────────────────┐
                 │ beacon-skip monitoring  │
                 │ / real_beacon_skip      │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ beacon recovery         │
                 │ temporary state 1       │
                 └────────────┬────────────┘
                              │
                              │ possible energy contribution
                              ▼
                       battery workload
```

Possible secondary interaction between the two paths is not categorically
excluded.

However, the available runtime evidence shows that neither mechanism should be
treated as merely a direct consequence of the other.

---

# Current Conclusion

The periodic mDNS restart mechanism is now supported by static analysis,
runtime packet capture and a targeted isolation experiment.

The current firmware timeline is:

```text
2.1.0
    mDNS responder present
    no periodic burst observed during ~13-minute runtime test

2.1.3
    recurring connected-maintenance restart present
    runtime interval ≈ 60 seconds

2.2.4 stock
    recurring restart retained
    gated by every third serviced minute
    runtime interval ≈ 180 seconds

2.2.4 + Patch B
    periodic restart call bypassed
    no recurring mDNS burst observed during monitored capture
    beacon recovery continues

2.2.4 + Patch A+B
    periodic mDNS restart bypassed
    beacon-recovery entry bypassed
    both targeted recurring behaviors absent during their monitored tests
```

The mDNS-only experiment answered one of the main open questions from the
earlier investigation:

> Suppressing the periodic mDNS restart does not suppress the recurring
> beacon-recovery loop under the tested conditions.

The periodic mDNS mechanism is therefore best treated as a separate recurring
workload rather than as the demonstrated trigger of the beacon-recovery loop.

Its contribution to battery consumption remains quantitatively unknown.

The next phase of the investigation is no longer to determine whether Patch B
works.

That has been demonstrated for the targeted periodic behavior.

The next phase is long-term comparison of:

```text
stock firmware 2.2.4
```

against:

```text
firmware 2.2.4 with Patch A + Patch B
```

while tracking battery voltage, battery percentage, runtime, beacon statistics,
recovery counters and motor activity.

The objective is to determine whether suppressing the two known recurring
mechanisms produces a measurable long-term battery-life improvement.

Until that evidence exists, the project does **not** claim that either patch,
individually or in combination, fixes the historical battery-drain problem.