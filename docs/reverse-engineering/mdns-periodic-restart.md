# Periodic mDNS Restart

## Scope

This document describes the recurring mDNS restart mechanism identified in
Shelly TRV Gen1 firmware and its evolution across the examined firmware
versions.

The purpose of this analysis is to determine:

- when the recurring mDNS restart appeared
- how its scheduling changed between firmware generations
- what the restart function actually does
- which call site creates the periodic behavior
- whether the mechanism is required for normal mDNS operation
- whether it is required for the recurring Beacon Recovery observed in 2.2.4
- what Patch B changes
- what Patch B deliberately leaves unchanged
- what runtime packet capture confirms
- how the mechanism should currently be interpreted in the battery-drain
  investigation
- which questions remain unresolved

The document focuses specifically on the recurring connected-maintenance mDNS
restart.

It does not attempt to describe every mDNS code path in the firmware.

---

# 1. Evidence Classification

This project uses the following evidence levels.

## PROVEN

Directly established from native firmware instructions, deterministic binary
comparison, validated control flow, or sufficiently direct runtime evidence.

## STRONGLY SUPPORTED

Multiple independent findings support the conclusion, but some implementation
detail, runtime dependency, or original developer intent remains unresolved.

## INFERENCE

A technically plausible interpretation consistent with the available evidence,
but not directly established.

## UNKNOWN

The available evidence is insufficient to determine the behavior, runtime
frequency, quantitative effect, or original developer intent.

Runtime observations are described explicitly where relevant rather than
introducing a separate evidence taxonomy.

---

# 2. Summary

The mDNS responder itself is not new to later Shelly TRV Gen1 firmware.

Firmware 2.1.0 already contains mDNS responder functionality.

The important firmware evolution is the addition and later scheduling change
of a recurring connected-maintenance restart of the mDNS probing process.

The current chronology is:

```text
2.1.0
    mDNS responder present
    no recurring connected-minute restart caller identified
    no comparable periodic mDNS burst observed during the available runtime test

2.1.3
    recurring connected-maintenance restart present
    approximately 60-second runtime cadence observed

2.1.8
    recurring restart retained
    modulo-3 minute gate already present
    approximately 180-second scheduling strongly supported statically

2.2.4
    recurring restart retained
    every third serviced minute
    approximately 180-second runtime cadence observed

2.2.4 + Patch B
    targeted periodic restart bypassed
    responder and other identified restart paths retained
    targeted periodic mDNS bursts absent during monitored capture
    Beacon Recovery remains active
```

The approximately 180-second behavior in 2.2.4 is therefore not a new
three-minute mechanism introduced only in 2.2.4.

The relevant scheduling change already exists in 2.1.8.

This is important for firmware chronology and battery-drain interpretation.

Patch B demonstrates that the targeted periodic mDNS restart can be suppressed
without globally disabling mDNS.

It also demonstrates that the targeted periodic mDNS restart is not required
for the recurring 2.2.4 Beacon Recovery loop under the tested conditions.

The periodic mDNS mechanism should therefore currently be treated as:

```text
a separate recurring network / processing workload
```

rather than:

```text
the demonstrated cause of the Beacon Recovery loop
```

Its quantitative contribution to battery consumption remains:

**UNKNOWN**

---

# 3. Important Distinction

This investigation does not show that mDNS itself was introduced in firmware
2.1.3.

The responder implementation already exists in firmware 2.1.0.

The relevant distinction is:

```text
mDNS responder functionality
```

versus:

```text
recurring connected-maintenance restart
of the mDNS probing sequence
```

The second behavior is the mechanism investigated here.

This distinction is important for patch design.

Patch B does not disable mDNS globally.

It suppresses only the identified recurring connected-maintenance restart in
firmware 2.2.4.

Other identified mDNS paths remain available.

---

# 4. Firmware Chronology

## 4.1 Firmware 2.1.0

Static analysis identified the mDNS responder implementation in firmware
2.1.0.

However, the examined connected-maintenance path does not contain the recurring
restart caller found in later firmware.

Conceptually:

```text
mDNS responder available
        |
        v
normal event-driven mDNS operation possible

but

no identified recurring connected-minute restart caller
```

This does not mean:

```text
firmware 2.1.0 never sends mDNS
```

Other events can still cause normal mDNS activity.

The narrower supported statement is:

> The recurring connected-maintenance restart identified in later firmware was
> not found in the corresponding examined 2.1.0 path.

### Classification

mDNS responder present:

**PROVEN**

Recurring later-style connected-maintenance restart identified in 2.1.0:

**UNKNOWN as a firmware-wide universal statement; not identified in the
examined corresponding path**

---

# 5. Firmware 2.1.3

Firmware 2.1.3 contains a recurring connected-maintenance call to the function
identified as equivalent to:

```text
mdns_resp_restart()
```

The resulting behavior is approximately:

```text
connected maintenance
        |
        v
mdns_resp_restart()
        |
        v
reset probing state
        |
        v
schedule probe callback
        |
        v
probe packet construction
        |
        v
UDP / IPv4 output
        |
        v
announcement after successful probing
```

Runtime packet capture showed that this mechanism operates approximately once
per minute under the tested conditions.

### Classification

Recurring restart in the examined 2.1.3 path:

**PROVEN**

Approximately 60-second runtime cadence under the tested conditions:

**PROVEN**

---

# 6. Firmware 2.1.8

Later cross-version analysis established an important chronology correction.

Firmware 2.1.8 already contains the scheduling structure that gates the
recurring mDNS restart through a modulo-3 maintenance condition.

Conceptually:

```text
minute maintenance
        |
        v
maintenance counter
        |
        v
counter % 3
        |
        v
periodic mDNS restart
```

This means the transition from the approximately once-per-minute behavior seen
in 2.1.3 to the later approximately once-every-three-minutes structure occurred
by firmware 2.1.8.

Therefore the 2.2.4 approximately 180-second behavior must not be described as
a new scheduling mechanism introduced in 2.2.4.

The correct chronology is:

```text
2.1.3
    ~60-second recurring restart

        |
        v

2.1.8
    modulo-3 minute gate present

        |
        v

2.2.4
    modulo-3 minute gate retained
    ~180-second runtime cadence confirmed
```

A dedicated packet-capture dataset equivalent to the 2.1.3 and 2.2.4 runtime
captures has not been used to establish the exact physical 2.1.8 cadence.

Therefore:

```text
2.1.8 modulo-3 scheduling
```

is:

**PROVEN**

while:

```text
exact ~180-second physical runtime cadence on the tested 2.1.8 device
```

is:

**STRONGLY SUPPORTED**

rather than independently runtime-confirmed by the capture documented here.

---

# 7. Firmware 2.2.4

Firmware 2.2.4 retains the recurring mDNS restart mechanism.

The relevant path is approximately:

```text
firmware-second dispatcher
        |
        v
changed second value
and
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

The approximately 180-second behavior is therefore best described as:

```text
every third serviced minute
```

rather than:

```text
dedicated 180-second timer
```

This distinction matters.

If a relevant scheduler boundary is not serviced normally, the physical packet
interval does not have to be exactly:

```text
180.000 seconds
```

### Classification

Minute-maintenance scheduling:

**PROVEN**

Modulo-3 gate:

**PROVEN**

Approximately 180-second runtime cadence:

**PROVEN**

---

# 8. Corrected Firmware Timeline

The current mDNS chronology is therefore:

| Firmware | Responder | Recurring connected-maintenance restart | Scheduling |
|---|---|---|---|
| 2.1.0 | present | not identified in examined path | no later-style recurring caller identified |
| 2.1.3 | present | present | approximately every minute |
| 2.1.8 | present | present | modulo-3 minute gate |
| 2.2.4 | present | present | every third serviced minute |

The important transition is:

```text
2.1.0
    responder only in the examined comparison

2.1.3
    recurring connected-maintenance restart added

2.1.8
    recurring restart cadence reduced through modulo-3 gating

2.2.4
    same general modulo-3 scheduling retained
```

This is the current supported firmware history.

---

# 9. Firmware 2.2.4 Restart Function

The firmware 2.2.4 function identified as the
`mdns_resp_restart()` equivalent is located at:

```text
0x0003D6C8
```

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

The initial scheduling delay contains a randomized component based on modulo
250.

The exact real-time interpretation of that internal delay value is less useful
for this investigation than the directly observed packet timing.

### Classification

Restart-function identification:

**PROVEN**

Probe-state reset and callback scheduling:

**PROVEN**

---

# 10. Direct Restart Callers in Firmware 2.2.4

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

Patch B targets only:

```text
0x1D918
    |
    v
periodic connected-operation restart
    |
    v
BL 0x3D6C8 at 0x1E0F4
```

The other identified callers are not modified.

Therefore Patch B must not be described as:

```text
disable mDNS
```

The correct description is:

```text
suppress the recurring connected-maintenance mDNS restart
```

---

# 11. Probe Sequence

The probe callback checks the current probe counter.

While fewer than three successful probes have completed, it attempts to
generate and transmit another probe.

Conceptually:

```text
restart
   |
   v
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

A successful probe advances the probe counter.

After the required probes have completed, the responder transitions into the
announced state and transmits an mDNS announcement.

Observed traffic uses:

```text
UDP port 5353
```

with IPv4 multicast destination:

```text
224.0.0.251
```

Packet captures do not necessarily contain every packet generated by every
burst.

Therefore individual captured bursts should not automatically be interpreted
as complete packet-level traces of the internal state machine.

---

# 12. Conditional Retry Behavior

Static analysis identified additional retry behavior.

If a probe cannot complete successfully, the probe counter may not advance.

Examples include conditions such as:

```text
IPv4 address unavailable
```

or:

```text
probe construction / transmission error
```

Another callback can then be scheduled without reaching the normal
three-successful-probe completion point.

No explicit small per-run retry limit was identified in the examined path.

The next periodic restart can also reset the probing process again.

Therefore two cases must be distinguished:

```text
normal successful probe sequence
```

and:

```text
failure / retry sequence
```

The runtime captures documented below primarily represent the normal successful
sequence.

---

# 13. Runtime Validation — Firmware Comparison

A passive packet capture was performed on 2026-10-11.

Three physical Shelly TRV Gen1 devices were monitored simultaneously.

| Device | Firmware at time of comparison | Purpose |
|---|---|---|
| `.11` | 2.1.0 | old firmware reference |
| `.77` | 2.1.3 | periodic-restart reference |
| `.229` | 2.2.4 stock | stock comparison |

TShark was used on the same local network with UDP port 5353 filtered for the
three devices.

The observation period was approximately 13 minutes.

The purpose of this experiment was:

```text
verify runtime network behavior predicted by static analysis
```

It was not:

```text
measure electrical energy consumption
```

The later use of `.77` with Patch B is a separate test configuration and must
not be conflated with this earlier 2.1.3 capture.

---

# 14. Runtime Result — Firmware 2.1.0

No mDNS packets from the firmware 2.1.0 reference device were observed during
the approximately 13-minute simultaneous capture.

The device remained connected during the observation.

This is consistent with the static comparison:

```text
mDNS responder exists
```

but:

```text
no recurring connected-maintenance restart identified
in the examined path
```

This result must not be generalized to:

```text
firmware 2.1.0 never sends mDNS
```

The supported conclusion is narrower:

> No periodic mDNS probe / announcement behavior comparable to the later
> firmware versions was observed during this test window.

---

# 15. Runtime Result — Firmware 2.1.3

Firmware 2.1.3 showed a strong repeatable periodic pattern.

A normal complete captured burst consisted approximately of:

```text
probe
probe
probe
announcement
```

One example was:

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

The dominant period is therefore approximately:

```text
60 seconds
```

This behavior continued throughout the capture.

Static analysis and runtime observation therefore agree that firmware 2.1.3
contains a recurring mDNS restart mechanism operating approximately once per
minute under the tested conditions.

---

# 16. Runtime Result — Firmware 2.2.4 Stock

Stock firmware 2.2.4 generated the characteristic mDNS probing sequence.

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

This agrees with the statically identified:

```text
every third serviced minute
```

mechanism.

---

# 17. Runtime and Static Comparison

The current combined comparison is:

| Firmware / configuration | Recurring mDNS behavior | Approximate cadence |
|---|---|---:|
| 2.1.0 stock | not observed during available capture | — |
| 2.1.3 stock | runtime confirmed | ~60 s |
| 2.1.8 stock | modulo-3 gate statically identified | ~180 s expected from identified scheduler |
| 2.2.4 stock | runtime confirmed | ~180 s |
| 2.2.4 + Patch B | targeted periodic sequence not observed during monitored capture | — |
| 2.2.4 + Patch A+B | targeted periodic sequence not observed during monitored capture | — |

The evidence level is intentionally not identical for every row.

In particular:

```text
2.1.8 modulo-3 mechanism
```

is statically established, while the exact physical cadence has not been
documented here with an equivalent dedicated packet-capture series.

---

# 18. Experimental Patch B

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
- `real_beacon_skip`
- Beacon Recovery logic
- WLAN power-management state selection
- RSSI thresholds
- cloud handling
- thermostat control

This makes Patch B suitable for isolating the recurring mDNS mechanism from
the separate Beacon Recovery mechanism.

---

# 19. Exact Patch-B Location

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

Only one program byte changes:

```text
program.bin offset 0x0001E0F1

D0 -> E0
```

In the verified GBL container, the corresponding changed byte is:

```text
GBL offset 0x00024645
```

The instruction is a 16-bit Thumb instruction.

---

# 20. Patch-B Control-Flow Effect

The original code around the patch site is:

```text
0x1E0F0   BEQ 0x1E0F8
0x1E0F2   load network-interface argument
0x1E0F4   BL 0x3D6C8
0x1E0F8   existing continuation
```

Original behavior:

```text
condition says skip
        |
        v
0x1E0F8


otherwise
        |
        v
load netif
        |
        v
mdns_resp_restart()
        |
        v
0x1E0F8
```

Patch B changes:

```text
0x1E0F0   BEQ 0x1E0F8
```

to:

```text
0x1E0F0   B 0x1E0F8
```

Result:

```text
periodic maintenance
        |
        v
existing condition / calculation
        |
        v
unconditionally branch to 0x1E0F8
        |
        v
continue normal maintenance
```

The network-interface load at:

```text
0x1E0F2
```

and periodic call at:

```text
0x1E0F4
```

are therefore bypassed.

Execution resumes at the existing continuation.

The patch does not:

- split an instruction
- alter stack depth
- change processor mode
- introduce new executable code
- globally disable the responder

---

# 21. Patch-B Verification Window

Original bytes beginning at `0x1E0F0`:

```text
02 D0 29 48 1F F0 E8 FA 12 4B
```

Patched bytes:

```text
02 E0 29 48 1F F0 E8 FA 12 4B
```

The existing four-byte instruction:

```text
1F F0 E8 FA
```

is the call to the `mdns_resp_restart()` equivalent.

It remains physically present in the firmware image.

Patch B changes only whether the targeted periodic path reaches it.

---

# 22. Why Patch B Does Not Disable mDNS

Five direct restart callers were identified in firmware 2.2.4.

Patch B modifies the control flow of only the periodic caller.

The following identified paths remain unmodified:

```text
button-related conditional restart

mDNS network-interface registration

mDNS service registration

successful connection-establishment restart
```

The responder's receive processing also remains intact.

Therefore:

```text
Patch B disables mDNS
```

is incorrect.

The supported statement is:

> Patch B suppresses the recurring connected-maintenance restart while retaining
> the responder and the other identified restart paths.

---

# 23. Runtime Validation — mDNS-Only Patch B

A physical TRV was later operated with firmware 2.2.4 containing only Patch B.

This is the current `.77` Patch-B test role.

The Beacon Recovery mechanism was deliberately left unchanged.

A passive TShark capture was performed using a filter equivalent to:

```text
udp port 5353 and host <patched-device>
```

During a monitored interval spanning multiple expected stock restart periods:

```text
0 targeted periodic mDNS packets were captured
```

Stock 2.2.4 would normally be expected to produce the targeted recurring
sequence approximately every third serviced minute.

The absence of the sequence across multiple expected periods provides strong
runtime evidence that Patch B suppresses the targeted recurring restart.

This remains a finite observation window.

It does not establish:

```text
this device can never emit any mDNS packet
```

Such a statement would also be inconsistent with Patch B's design because
event-driven responder paths remain available.

---

# 24. Important Device-History Distinction for `.77`

The `.77` device has been used in more than one experimental configuration.

During the earlier firmware-comparison packet capture:

```text
.77 = firmware 2.1.3
```

Later:

```text
.77 = firmware 2.2.4 + Patch B
```

These observations must not be mixed.

The earlier 2.1.3 packet-capture data establishes the approximately 60-second
mDNS cadence.

The later Patch-B data establishes suppression of the targeted 2.2.4 periodic
restart.

Current Patch-B debug observations additionally show stock Beacon Recovery
remaining active at approximately:

```text
RSSI ≈ -75 .. -77 dBm
```

with:

```text
desired_beacon_skip = 15
```

The previously documented association of the Patch-B `.77` runtime with:

```text
-58 .. -59 dBm
desired_beacon_skip = 20
```

should not be used as the current `.77` test-device characterization.

The broader finding that Beacon Recovery can occur under good RSSI conditions
comes from separate stock observations and should not be attributed to the
current `.77` Patch-B log without corresponding evidence.

---

# 25. Beacon-Recovery Isolation Test

Patch B provides an important mechanism-isolation experiment.

The patch suppresses:

```text
targeted recurring mDNS restart
```

while intentionally preserving:

```text
stock 2.2.4 Beacon Recovery
```

After applying Patch B, the device continued to produce the Beacon Recovery
sequence:

```text
Beacon skip error! Attempt recovery
        |
        v
Enter powersave state 1
        |
        | approximately 5 serviced seconds
        v
Enter powersave state 3 (skip N)
```

The sequence continued approximately once per minute during the relevant
observation.

Therefore:

```text
targeted periodic mDNS restart suppressed

        +

Beacon Recovery still recurring
```

establishes an important negative causal result:

> The targeted recurring mDNS restart is not required for the observed
> Beacon Recovery loop under the tested conditions.

### Classification

Patch B suppresses the targeted periodic mDNS sequence:

**PROVEN**

Beacon Recovery remains active on the Patch-B test device:

**PROVEN**

Targeted periodic mDNS is required for the observed recurring Recovery loop:

**UNKNOWN as a universal interaction claim; experimentally not required under
the tested conditions**

---

# 26. Updated Relationship to Beacon Recovery

An earlier plausible hypothesis was:

```text
periodic mDNS restart
        |
        v
WLAN / beacon timing disturbance
        |
        v
real_beacon_skip anomaly
        |
        v
Beacon Recovery
```

Patch B falsifies the strong form of this hypothesis.

Observed result:

```text
periodic mDNS restart
        |
        v
suppressed


Beacon Recovery
        |
        v
continues
```

The current model therefore separates the mechanisms:

```text
periodic mDNS restart
        |
        +---- recurring network / processing workload


beacon measurement
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery
```

Possible secondary interaction between the mechanisms under some network
conditions is not categorically excluded.

But the recurring mDNS restart is not necessary for the observed recurring
Recovery loop.

---

# 27. Why the Beacon-Recovery Interpretation Changed

The Beacon Recovery investigation has advanced substantially since the original
mDNS hypothesis was formulated.

Three host-side validity problems are now separated:

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

Most importantly, C2 establishes that after one qualifying Recovery the host
can enter a self-sustaining Recovery loop without requiring a new qualifying RF
measurement every minute.

Conceptually:

```text
first qualifying Recovery
        |
        v
P cleared
R retained
        |
        v
next baseline-only sample
        |
        v
historical R evaluated
        |
        v
Recovery again
```

Therefore recurring Beacon Recovery no longer requires a hypothesis such as:

```text
mDNS creates a fresh beacon anomaly every minute
```

to explain the observed recurrence.

The exact cause of the first qualifying Beacon Recovery event remains:

**UNKNOWN**

Periodic mDNS is not excluded as one of many possible environmental or timing
influences on an initial measurement.

But no evidence currently establishes it as such a cause.

Detailed analysis belongs in:

```text
beacon-rx-counter.md
real-beacon-skip.md
recovery-mechanism.md
```

---

# 28. Combined Patch A+B

Patch A and Patch B were combined during an earlier isolation phase.

Patch A:

```text
Beacon Recovery action bypass

program.bin:
0x1E1C8   31 DC -> 31 E0

changed byte:
0x1E1C9   DC -> E0
```

Patch B:

```text
periodic mDNS restart bypass

program.bin:
0x1E0F0   02 D0 -> 02 E0

changed byte:
0x1E0F1   D0 -> E0
```

Corresponding GBL changed-byte locations:

```text
Patch B: 0x00024645   D0 -> E0
Patch A: 0x0002471D   DC -> E0
```

The validated combined experimental firmware had:

```text
Size:
1,106,384 bytes

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61

CRC32:
0xBAEB8265
```

The patched main PROGRAM payload had SHA-256:

```text
06742a2632a3d45cf697b8be85045914d004f30644dad17b3d0d20012c87c61b
```

These values document that historical experimental build.

They do not identify the current preferred corrective firmware design.

---

# 29. Combined A+B Runtime Result

A physical TRV was operated with firmware 2.2.4 containing both Patch A and
Patch B.

During the monitored tests:

```text
targeted recurring mDNS sequence
```

was not observed.

Multi-hour debug-log observation also did not show the targeted recurring:

```text
Beacon skip error! Attempt recovery
```

sequence or corresponding Recovery entry into state 1.

Normal RSSI-dependent desired-beacon-skip behavior remained available.

The experiment demonstrated that the two targeted mechanisms could be isolated
simultaneously.

It did not establish:

- long-term battery improvement
- elimination of every mDNS transmission
- elimination of every possible PM state-1 entry
- correction of the underlying Beacon Recovery validity defects
- production suitability

Patch A+B should therefore be regarded as:

```text
historical mechanism-isolation configuration
```

rather than:

```text
current final-fix candidate
```

---

# 30. Why Patch A+B Is No Longer the Main Corrective Direction

Patch A suppresses the Beacon Recovery action itself.

Later reverse engineering established that Recovery has a coherent WLAN
reliability/reconfiguration role.

The underlying problem is more specific:

```text
invalid or stale evidence can become actionable
```

rather than:

```text
Recovery should never exist
```

Patch A therefore removes both:

```text
invalid Recovery
```

and potentially:

```text
legitimate Recovery
```

The current Beacon Recovery research direction is Patch C-C, which attempts to
correct:

```text
C1a
C1b
C2
```

while retaining legitimate fresh Recovery.

Patch B remains useful independently because it isolates a separate recurring
mDNS workload.

The current architecture is therefore:

```text
Patch B
    mDNS-specific isolation / battery-contribution experiment


Patch C-C
    Beacon-Recovery semantic correction candidate
```

rather than:

```text
Patch A+B
    presumed final battery-drain fix
```

---

# 31. Network Activity

A normal successful periodic mDNS restart can produce approximately:

```text
3 probe packets
+
1 announcement packet
```

For firmware 2.1.3 at approximately one cycle per minute, this corresponds
conceptually to approximately:

```text
4 mDNS transmissions / minute
```

during normal successful operation.

For firmware 2.1.8 and 2.2.4 with the modulo-3 gate, the average intended rate
is lower.

These numbers describe only the visible mDNS sequence.

They do not represent total WLAN activity.

They do not include:

- lower-layer WLAN traffic
- acknowledgements
- retransmissions
- beacon reception
- cloud traffic
- controller traffic
- thermostat communication
- unrelated firmware tasks
- radio-internal work

Packet count must therefore not be converted directly into battery consumption.

---

# 32. Relationship to WLAN Power Management

The recurring mDNS restart creates real application and network activity.

Static analysis has not identified a long-lived WUP / EM2 resource acquired
directly and permanently by the mDNS responder as part of the normal periodic
sequence.

The mechanism should therefore currently be classified as:

```text
recurring network / processing activity
```

rather than:

```text
confirmed permanent sleep lock
```

Transmission of the mDNS packets necessarily requires the network subsystem to
perform work.

However, the following have not been electrically measured:

```text
wake duration caused by one restart
WF200 current caused by the sequence
host-MCU current contribution
energy per restart
```

Therefore the mechanism is energy-relevant, but its quantitative cost remains:

**UNKNOWN**

---

# 33. Relationship to WUP / EM2 Retention

A separate WLAN power-management retention/failure candidate has been
identified.

Under specific low-level conditions, a device-sleep operation can fail while a
WLAN-owned sleep-blocking resource remains retained.

That mechanism is distinct from the recurring mDNS restart.

Importantly, the underlying low-level sleep-resource behavior already exists in
earlier firmware, including 2.1.0.

No direct causal path has been established:

```text
periodic mDNS restart
        |
        v
WUP / EM2 retention failure
```

Therefore these mechanisms must remain separate unless future runtime evidence
establishes an interaction.

No blind WUP/EM2 patch is justified from the mDNS findings.

---

# 34. Energy Interpretation

The periodic mDNS restart is a confirmed recurring workload.

Compared with otherwise equivalent operation without the recurring restart, it
causes additional:

```text
application processing
network-stack processing
packet construction
WLAN transmission activity
```

This makes an energy contribution technically unavoidable in principle.

What remains unknown is its magnitude.

No direct electrical measurement currently establishes:

```text
energy per restart

energy per probe

energy per announcement

additional wake time

additional daily consumption

battery-runtime reduction
```

Therefore the supported statement is:

> The recurring mDNS restart is a confirmed additional periodic workload and a
> technically plausible contributor to battery consumption.

The unsupported stronger statement would be:

> The recurring mDNS restart is the cause of the historical Shelly TRV Gen1
> battery-drain problem.

That has not been established.

---

# 35. Why Firmware 2.1.0 Remains Important

Firmware 2.1.0 is useful because it separates:

```text
mDNS capability
```

from:

```text
continuous periodic mDNS restart
```

The responder exists in 2.1.0, but the later recurring connected-maintenance
restart was not identified in the examined path.

During the available runtime comparison:

```text
2.1.0
    no comparable periodic mDNS bursts observed

2.1.3
    bursts approximately every 60 seconds

2.2.4
    bursts approximately every 180 seconds
```

The 2.1.0 device remained reachable during practical operation.

This supports the interpretation that continuously restarting the mDNS probing
sequence is not obviously required for:

```text
basic IP connectivity
```

But:

```text
basic IP connectivity
```

is not equivalent to:

```text
complete mDNS service-discovery behavior
```

This is why Patch B deliberately retains the responder and event-driven mDNS
paths.

---

# 36. Why Firmware 2.1.8 Is Now Important

Firmware 2.1.8 provides the missing chronological link between 2.1.3 and 2.2.4.

Without 2.1.8, the history could be misread as:

```text
2.1.3
~60 s

        |
        v

2.2.4
new ~180 s mechanism
```

The corrected history is:

```text
2.1.3
~60 s recurring restart

        |
        v

2.1.8
modulo-3 minute gating already present

        |
        v

2.2.4
same general ~180 s scheduling retained
```

Therefore the mDNS scheduling change predates the 2.2.4 Beacon Recovery
mechanism.

This weakens any simplistic chronology argument of the form:

```text
2.2.4 introduced both mechanisms
therefore they are one feature
```

They have distinct firmware histories.

---

# 37. Relationship to Historical Battery Drain

The periodic mDNS mechanism cannot currently explain the complete historical
battery-drain problem.

Reasons include:

1. battery-drain behavior was also observed on firmware 2.1.8

2. the mDNS cadence changed across firmware generations

3. the 2.2.4 Beacon Recovery mechanism is a separate later control path

4. inherited low-level WLAN sleep behavior also exists

5. the electrical cost of the mDNS restart has not yet been quantified

The current battery-drain model is therefore multi-mechanism:

```text
periodic mDNS
        |
        +-- recurring network workload


Beacon Recovery
        |
        +-- 2.2.4-specific recurring PM workload
            with identified C1a/C1b/C2 validity defects


WUP / EM2 retention candidate
        |
        +-- inherited low-level sleep-resource behavior


other unidentified contributors
        |
        +-- still possible
```

No one mechanism should currently be declared the sole historical root cause.

---

# 38. Current Experimental Roles

The experimental configurations now have distinct purposes.

| Configuration | Purpose |
|---|---|
| Stock 2.2.4 | control |
| Patch B | isolate periodic mDNS workload |
| Patch A | historical Beacon Recovery isolation |
| Patch A+B | historical combined isolation |
| Patch C family | preserve Recovery while correcting validity semantics |
| Patch C-C | current preferred Beacon Recovery corrective candidate |

Patch B remains valuable because it isolates mDNS independently of the current
Beacon Recovery correction.

Patch A remains valuable as historical experimental evidence.

Patch C-C supersedes Patch A as the preferred direction for correcting Beacon
Recovery semantics.

---

# 39. Current Device Roles

The current long-term research configuration includes devices with different
firmware roles.

Relevant examples include:

```text
.77
2.2.4 with Patch B only
mDNS periodic restart suppressed
Beacon Recovery stock


.226
2.2.4 with historical Patch A+B
mDNS periodic restart suppressed
Beacon Recovery action bypassed


.229
stock 2.2.4 reference
```

These roles must be preserved when interpreting logs.

In particular:

```text
.77
```

must not be treated as a stock 2.2.4 device or as the historical 2.1.3 capture
configuration when analyzing current logs.

Likewise:

```text
.226
```

must not be treated as evidence for Patch C-C.

Patch C-C hardware testing has not yet been performed.

---

# 40. Evidence Summary

| Finding | Evidence |
|---|---|
| mDNS responder exists in firmware 2.1.0 | **PROVEN** |
| Later-style recurring connected-maintenance restart was identified in the examined 2.1.0 path | **UNKNOWN as a firmware-wide universal claim; not identified in the examined path** |
| 2.1.3 contains the recurring connected-maintenance restart | **PROVEN** |
| 2.1.3 runtime cadence is approximately 60 seconds under the tested conditions | **PROVEN** |
| 2.1.8 contains the modulo-3 minute gate | **PROVEN** |
| 2.1.8 exact physical cadence is approximately 180 seconds | **STRONGLY SUPPORTED** |
| 2.2.4 retains the recurring restart | **PROVEN** |
| 2.2.4 uses every-third-serviced-minute gating | **PROVEN** |
| 2.2.4 runtime cadence is approximately 180 seconds | **PROVEN** |
| 2.2.4 uses a dedicated independent 180-second timer for this behavior | **UNKNOWN as a universal timer claim; the identified path instead uses minute maintenance and modulo-3 gating** |
| `mdns_resp_restart()` equivalent is at `0x3D6C8` in 2.2.4 | **PROVEN** |
| Five direct callers were identified in 2.2.4 | **PROVEN** |
| Periodic call is at `0x1E0F4` | **PROVEN** |
| Restart resets probing state and schedules probe processing | **PROVEN** |
| Successful sequence produces probes followed by announcement | **PROVEN** |
| Patch B changes `0x1E0F0: 02 D0 -> 02 E0` | **PROVEN** |
| Patch B bypasses the targeted periodic caller | **PROVEN** |
| Patch B disables the complete mDNS subsystem | **UNKNOWN as a hypothetical claim; contradicted by the identified retained paths** |
| Other identified restart callers remain intact under Patch B | **PROVEN** |
| Targeted recurring mDNS bursts disappear during Patch-B capture | **PROVEN** |
| Beacon Recovery remains active on the Patch-B device | **PROVEN** |
| Targeted periodic mDNS is required for the observed C2 Recovery loop | **UNKNOWN as a universal interaction; not required under tested conditions** |
| Periodic mDNS is the demonstrated first trigger of Beacon Recovery | **UNKNOWN** |
| Periodic mDNS creates recurring network/processing workload | **PROVEN** |
| Periodic mDNS contributes some non-zero processing/network work | **PROVEN** |
| Quantitative electrical cost | **UNKNOWN** |
| Battery-runtime effect | **UNKNOWN** |
| Periodic mDNS is the sole historical battery-drain cause | **UNKNOWN** |
| Patch A+B is the current preferred corrective firmware design | **UNKNOWN as an intent claim; it is no longer the preferred project direction** |
| Patch C-C is the current preferred Beacon Recovery candidate | **PROVEN as current project design status** |
| Patch C-C changes the mDNS mechanism | **UNKNOWN as a hypothetical interaction; it is not intended to modify mDNS** |

---

# 41. What the Patch-B Experiment Establishes

Patch B provides a particularly useful causal isolation result.

Before Patch B, the following model was plausible:

```text
periodic mDNS restart
        |
        v
beacon timing disturbance
        |
        v
bad real_beacon_skip
        |
        v
Beacon Recovery
```

Patch B produced:

```text
periodic mDNS restart
        |
        v
suppressed


Beacon Recovery
        |
        v
continues
```

Therefore the strong hypothesis:

```text
periodic mDNS restart is necessary
for the observed recurring Beacon Recovery
```

does not survive the isolation experiment.

This is one of the most important conclusions of this document.

---

# 42. What Patch B Does Not Establish

Patch B does not establish that:

- mDNS can never influence WLAN timing
- mDNS can never affect beacon statistics
- no mDNS packet can ever be generated
- mDNS has zero energy cost
- suppressing mDNS has zero battery benefit
- the first Beacon Recovery trigger can never correlate with network activity
- all firmware versions behave identically
- the historical battery drain is unrelated to mDNS
- Patch B is production-safe indefinitely
- Patch B materially extends battery life

These questions require separate evidence.

---

# 43. Current Research Direction

The mDNS investigation has largely completed its first mechanistic phase.

The following are now established sufficiently for continued experimentation:

```text
mDNS responder exists before periodic restart

2.1.3 introduces identified recurring connected-maintenance restart

2.1.8 already contains modulo-3 scheduling

2.2.4 retains modulo-3 scheduling

Patch B isolates the targeted periodic restart

Beacon Recovery continues without that restart
```

The next useful question is therefore not:

```text
Does Patch B bypass the targeted periodic restart?
```

That has already been demonstrated.

The next questions are:

```text
How much energy does the periodic mDNS workload actually cost?
```

and:

```text
Does removing only that recurring workload measurably change
long-term battery discharge?
```

At the same time, Beacon Recovery should now be evaluated using Patch C-C
rather than treating Patch A as the final corrective design.

The two experimental questions should remain separate:

```text
Patch B
        |
        v
What is the battery contribution of periodic mDNS?


Patch C-C
        |
        v
Does corrected Beacon Recovery logic eliminate invalid recurrence
while preserving legitimate Recovery?
```

Only after these mechanisms are individually characterized should combined
battery effects be interpreted.

---

# 44. Recommended Long-Term Comparison Strategy

The preferred scientific approach is no longer simply:

```text
stock
vs.
Patch A+B
```

That comparison remains useful historically, but it combines two independent
changes and Patch A removes legitimate Recovery behavior.

A stronger experimental design is:

```text
stock 2.2.4
        |
        +----------------------+
        |                      |
        v                      v
Patch B                  Patch C-C
mDNS isolated            Recovery semantics corrected
        |                      |
        v                      v
measure battery          validate function first
contribution             then measure battery effect
```

If sufficient devices are available, a later combined configuration can test:

```text
Patch B + corrected Patch C behavior
```

but only after Patch C-C has passed hardware qualification.

This preserves causal interpretability.

---

# 45. Battery-Data Interpretation

Long-term battery testing should continue to prioritize:

```text
bat.voltage
```

over the quantized:

```text
bat.value
```

percentage when comparing discharge trends.

Relevant supporting data include:

```text
uptime
RSSI
desired_beacon_skip
real_beacon_skip
Recovery events
motor activity
network availability
firmware identity
```

For mDNS-specific comparison, passive packet capture is useful to verify that:

```text
stock device
    targeted periodic bursts present

Patch-B device
    targeted periodic bursts absent
```

during representative windows.

Packet count alone is not an energy measurement.

---

# 46. Remaining Questions

The main unresolved mDNS questions are:

1. What is the electrical energy cost of one normal mDNS restart sequence?

2. How long does the network subsystem remain in a higher-power condition
   because of one restart?

3. Does the cost differ between the 2.1.3 ~60-second and later ~180-second
   scheduling?

4. What is the exact physical runtime cadence on firmware 2.1.8 under dedicated
   packet capture?

5. Can the periodic mDNS restart influence the first Beacon Recovery
   measurement under particular AP or PM conditions even though it is not
   required for the recurring C2 loop?

6. Does Patch B measurably improve long-term battery voltage decay?

7. Does the mDNS workload interact with the separate WUP / EM2 retention
   candidate?

8. Are there AP-specific differences in the cost of the probing sequence?

9. How frequently are the non-periodic retained mDNS restart paths exercised in
   normal operation?

10. Does suppressing the periodic restart have any measurable long-term effect
    on mDNS discoverability?

11. Why was the recurring restart introduced in 2.1.3?

12. Why was its cadence reduced by 2.1.8?

The last two questions concern developer intent and remain:

**UNKNOWN**

---

# 47. Current Model

The current best-supported mDNS model is:

```text
Firmware 2.1.0
        |
        v
mDNS responder available
        |
        v
event-driven mDNS behavior


Firmware 2.1.3
        |
        v
recurring connected-maintenance restart added
        |
        v
~60-second runtime cadence
        |
        v
probe / probe / probe / announcement


Firmware 2.1.8
        |
        v
recurring restart retained
        |
        v
modulo-3 minute gate
        |
        v
~180-second scheduling strongly supported


Firmware 2.2.4
        |
        v
same general modulo-3 scheduling
        |
        v
~180-second runtime cadence confirmed
        |
        v
recurring network / processing workload
```

Separately:

```text
2.2.4 Beacon measurement
        |
        v
real_beacon_skip
        |
        v
C1a / C1b validity issues
        |
        v
qualifying Recovery
        |
        v
C2 can sustain recurrence
```

Patch B breaks only:

```text
periodic mDNS restart
```

It does not intentionally break:

```text
Beacon Recovery
```

That separation is confirmed experimentally under the tested conditions.

---

# 48. Current Conclusion

The periodic mDNS restart mechanism is now well characterized at the
host-application and network-observation level.

The corrected firmware chronology is:

```text
2.1.0
    mDNS responder present
    later-style recurring connected-maintenance caller not identified
    no comparable periodic burst observed in available runtime capture

2.1.3
    recurring connected-maintenance restart present
    runtime cadence ≈ 60 seconds

2.1.8
    recurring restart retained
    modulo-3 minute gate already present
    ~180-second scheduling strongly supported

2.2.4
    recurring restart retained
    every third serviced minute
    runtime cadence ≈ 180 seconds
```

This establishes that the approximately three-minute scheduling behavior
predates firmware 2.2.4.

Patch B changes one targeted control-flow decision in 2.2.4:

```text
0x1E0F0

02 D0
    |
    v
02 E0
```

which bypasses the recurring connected-maintenance call while preserving the
responder and the other identified restart paths.

Runtime packet capture confirms suppression of the targeted recurring mDNS
bursts during the monitored test window.

Most importantly, Beacon Recovery continues on the Patch-B device.

Therefore:

> The targeted periodic mDNS restart is not required for the recurring Beacon
> Recovery loop observed under the tested conditions.

The later C2 analysis strengthens this separation further.

Once a qualifying Beacon Recovery has occurred, stale host-side control
evidence can sustain the Recovery loop without requiring a new RF anomaly or a
new mDNS-induced disturbance every minute.

The exact cause of the first qualifying Beacon Recovery event remains unknown.

The periodic mDNS mechanism therefore remains scientifically relevant, but its
role is narrower than initially suspected.

It is best described as:

> a confirmed recurring network and processing workload whose quantitative
> battery cost has not yet been measured.

It should not currently be described as:

> the demonstrated cause of Beacon Recovery

or:

> the sole cause of the historical Shelly TRV Gen1 battery drain.

Patch A+B remains useful historical isolation evidence.

The current research direction instead separates the two questions:

```text
Patch B
    quantify the contribution of recurring mDNS activity

Patch C-C
    correct Beacon Recovery validity semantics
    while preserving legitimate Recovery
```

This separation provides a substantially stronger basis for future hardware and
battery testing than treating both mechanisms as one combined defect.

---

# Related Documents

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Beacon-counter measurement model:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

`real_beacon_skip` calculation:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery mechanism:

[`recovery-mechanism.md`](recovery-mechanism.md)

Power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Experimental patch documentation:

[`../patch/README.md`](../patch/README.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Methodology

This investigation is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime observations from personally
owned devices.

The mDNS investigation used:

- cross-version native firmware comparison
- direct-call analysis
- connected-maintenance control-flow reconstruction
- scheduler analysis
- packet capture
- isolated Patch-B testing
- combined Patch-A+B testing
- comparison with Beacon Recovery runtime behavior
- long-term device-role separation

The examined firmware versions include:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

Runtime packet capture directly documented:

```text
2.1.0
2.1.3
2.2.4 stock
2.2.4 + Patch B
2.2.4 + Patch A+B
```

The 2.1.8 modulo-3 scheduling result comes from static cross-version analysis
rather than the same dedicated runtime packet-capture series.

No original or modified Shelly firmware image, complete proprietary function,
or large raw disassembly is reproduced in this document.

The project deliberately distinguishes:

```text
PROVEN
STRONGLY SUPPORTED
INFERENCE
UNKNOWN
```

and separately distinguishes:

```text
static firmware behavior
runtime observation
experimental patch behavior
energy hypothesis
developer intent
```

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the investigated firmware versions.

No conclusion about the intentions of the original developers is made unless
independently supported by technical evidence.