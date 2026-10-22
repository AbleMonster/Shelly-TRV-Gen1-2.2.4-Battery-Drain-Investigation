# Periodic mDNS Restart

## Scope

This document describes the recurring mDNS restart mechanism found in Shelly TRV Gen1 firmware and how it changed across the examined firmware versions.

The analysis focuses specifically on the connected-maintenance path that periodically restarts the mDNS probing sequence. It covers:

- the firmware versions in which the recurring restart appears
- the scheduling change between firmware generations
- the mDNS restart function and its direct callers
- the resulting probe and announcement traffic
- runtime packet captures
- the targeted Patch B experiment
- the relationship between periodic mDNS activity and Beacon Recovery
- the relevance of the mechanism to the battery-drain investigation

The important distinction throughout this document is between the **mDNS responder itself** and the **periodic restart of its probing sequence**.

Patch B targets only the latter.

---

# 1. Summary

The mDNS responder already exists in firmware 2.1.0.

What changed in later firmware is the addition of a recurring connected-maintenance call that restarts the mDNS probing sequence.

The examined firmware history is:

| Firmware | mDNS responder | Recurring connected-maintenance restart | Observed / identified scheduling |
|---|---|---|---|
| 2.1.0 | present | not identified in the examined corresponding path | no comparable periodic burst observed |
| 2.1.3 | present | present | approximately every 60 s |
| 2.1.8 | present | present | modulo-3 minute gate |
| 2.2.4 | present | present | approximately every 180 s |

The scheduling change therefore predates firmware 2.2.4.

In 2.2.4, the recurring restart is not driven by a dedicated 180-second timer. It is reached through minute maintenance and executes every third serviced minute.

The identified restart function resets the mDNS probing state and schedules the probe sequence again. A normal successful cycle produces approximately:

```text
probe
probe
probe
announcement
```

Patch B changes a single conditional branch in the periodic caller:

```text
0x1E0F0

02 D0    BEQ 0x1E0F8
   ↓
02 E0    B   0x1E0F8
```

This bypasses the periodic call to the mDNS restart function while leaving the responder and the other identified restart paths intact.

Runtime testing confirmed the intended effect: the recurring mDNS bursts disappeared while normal device operation remained available.

More importantly, stock Beacon Recovery continued on the Patch-B device.

The long-term `.77` experiment strengthened this result substantially. With the periodic mDNS restart suppressed but stock Beacon Recovery left intact, the device accumulated approximately 12,908 Beacon Recovery events over about 9.23 days, corresponding to roughly 58 recoveries per hour, and eventually reached the end of the battery discharge test.

This establishes that the targeted periodic mDNS restart is **not required** for the recurring Beacon Recovery behavior observed on firmware 2.2.4.

It does not establish that mDNS has zero energy cost.

The periodic restart remains a real recurring network and processing workload. Its quantitative contribution to battery consumption has not been measured directly.

---

# 2. mDNS Responder vs. Periodic Restart

The mDNS implementation itself must not be confused with the periodic mechanism investigated here.

Firmware 2.1.0 already contains mDNS responder functionality. Normal events can therefore generate mDNS traffic without any recurring maintenance restart.

The later mechanism adds another behavior:

```text
connected maintenance
        |
        v
restart mDNS probing
        |
        v
probe sequence
        |
        v
announcement
```

This distinction is important because Patch B does **not** disable mDNS globally.

It suppresses only one identified periodic caller.

Other mDNS paths remain present.

---

# 3. Firmware Chronology

## 3.1 Firmware 2.1.0

Static analysis identified the mDNS responder implementation in firmware 2.1.0.

The corresponding connected-maintenance path examined during the cross-version comparison does not contain the recurring restart caller found in later firmware.

The relevant distinction is therefore:

```text
2.1.0

mDNS responder present
        |
        v
normal event-driven mDNS operation possible

but

no later-style recurring connected-maintenance
restart identified in the examined path
```

This does not mean that firmware 2.1.0 never sends mDNS packets.

It means that the specific recurring restart mechanism documented here was not identified in the corresponding path.

A runtime packet capture also showed no comparable periodic mDNS burst from the 2.1.0 reference device during the available observation window.

---

## 3.2 Firmware 2.1.3

Firmware 2.1.3 contains the recurring connected-maintenance restart.

The path is approximately:

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
probe sequence
        |
        v
announcement
```

Runtime packet capture showed this sequence recurring approximately once per minute.

A representative burst was:

```text
59.699110 s   probe
60.005565 s   probe
60.211304 s   probe
60.519855 s   announcement
```

Observed burst starts included:

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

The dominant interval is therefore approximately 60 seconds.

---

## 3.3 Firmware 2.1.8

Firmware 2.1.8 provides the important intermediate step between 2.1.3 and 2.2.4.

Static comparison shows that the recurring restart is still present, but the scheduler now contains the modulo-3 maintenance gate later retained in 2.2.4.

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

The change from the approximately once-per-minute behavior of 2.1.3 to the later every-third-minute structure therefore occurred by firmware 2.1.8.

An equivalent dedicated packet-capture series was not performed for the 2.1.8 reference device, so the exact physical ~180-second cadence is derived from the identified scheduling logic rather than independently established by the same runtime experiment.

---

## 3.4 Firmware 2.2.4

Firmware 2.2.4 retains the modulo-3 scheduling.

The relevant path is approximately:

```text
firmware-second dispatcher
        |
        v
changed second value
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
connected / IPv4 condition
        |
        v
mdns_resp_restart()
```

The periodic behavior is therefore better described as:

```text
every third serviced minute
```

rather than:

```text
independent 180-second timer
```

Runtime capture agrees with the static reconstruction.

Observed burst starts were:

```text
117.554727 s
297.779351 s
477.492032 s
657.412999 s
```

giving intervals of:

```text
180.224624 s
179.712681 s
179.920967 s
```

A representative burst was:

```text
117.554727 s   probe
117.761173 s   probe
117.964812 s   probe
118.272223 s   announcement
```

The physical interval does not have to be exactly 180.000 seconds because the mechanism depends on serviced scheduler boundaries rather than a dedicated 180-second timer.

---

# 4. Firmware Timeline

The resulting firmware history is:

```text
2.1.0
    |
    +-- mDNS responder present
    |
    +-- recurring connected-maintenance restart
        not identified in examined path


2.1.3
    |
    +-- recurring restart present
    |
    +-- approximately 60 s


2.1.8
    |
    +-- recurring restart retained
    |
    +-- modulo-3 minute gate present


2.2.4
    |
    +-- modulo-3 scheduling retained
    |
    +-- approximately 180 s confirmed at runtime
```

This chronology matters for the battery-drain investigation.

The three-minute scheduling behavior was not introduced together with the 2.2.4 Beacon Recovery mechanism. It already existed in 2.1.8.

The two mechanisms therefore have distinct firmware histories.

---

# 5. mDNS Restart Function in Firmware 2.2.4

The function identified as the 2.2.4 `mdns_resp_restart()` equivalent is located at:

```text
0x0003D6C8
```

For a registered mDNS network interface, its behavior is approximately:

```text
if already probing:
    cancel existing probe timeout

reset probe counter

set responder state = probing

schedule probe callback
```

The scheduled probe callback is located at:

```text
0x0003D264
```

The initial scheduling delay includes a randomized component based on modulo 250.

For the battery investigation, the exact internal time-unit interpretation of that value is less important than the packet timing observed directly on the network.

---

# 6. Direct Restart Callers in Firmware 2.2.4

Five direct callers of the restart function were identified:

| Caller | Call instruction | Role |
|---|---:|---|
| `0x1D918` | `0x1E0F4` | periodic connected-operation maintenance |
| `0x173B4` | `0x174A4` | conditional button-release path |
| `0x3D2F8` | `0x3D3E2` | successful mDNS network-interface registration |
| `0x3D430` | `0x3D5DC` | successful mDNS service registration |
| `0x63680` | `0x639EE` | successful connection-establishment path |

Patch B targets only the first path:

```text
0x1D918
    |
    v
periodic connected-operation maintenance
    |
    v
0x1E0F4
    |
    v
mdns_resp_restart()
```

The other four identified callers remain unchanged.

This is why Patch B should be described as:

> suppressing the recurring connected-maintenance mDNS restart

and not as:

> disabling mDNS.

---

# 7. Probe Sequence

After a restart, the responder returns to the probing state.

While fewer than three successful probes have completed, the callback attempts another probe.

The normal successful sequence is:

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

Observed traffic uses UDP port:

```text
5353
```

with IPv4 multicast destination:

```text
224.0.0.251
```

A packet capture does not necessarily contain every packet generated internally, so an individual captured burst should not automatically be treated as a complete trace of the responder state machine.

---

# 8. Retry Behavior

The normal three-probe sequence is not the only possible path.

If a probe cannot complete successfully, the probe counter may not advance.

Examples include:

```text
IPv4 address unavailable
```

or:

```text
probe construction / transmission error
```

The callback can then be scheduled again without reaching the normal three-successful-probe completion point.

No small explicit per-run retry limit was identified in the examined path.

A later periodic restart can also reset the probing sequence again.

The normal successful sequence and a failure/retry sequence therefore need to be distinguished when interpreting packet captures.

The runtime captures used for the firmware comparison primarily represent normal successful sequences.

---

# 9. Runtime Firmware Comparison

A passive packet capture was performed on 2026-10-11.

Three physical Shelly TRV Gen1 devices were monitored simultaneously:

| Device | Firmware during capture | Purpose |
|---|---|---|
| `.11` | 2.1.0 | old firmware reference |
| `.77` | 2.1.3 | recurring-restart reference |
| `.229` | stock 2.2.4 | stock reference |

TShark was used on the same local network with UDP port 5353 filtered for the three devices.

The observation period was approximately 13 minutes.

This experiment was intended to verify the runtime network behavior predicted by static analysis.

It was not an electrical energy measurement.

The later use of `.77` with firmware 2.2.4 + Patch B is a separate configuration.

---

## 9.1 Firmware 2.1.0

No mDNS packets from the 2.1.0 reference device were observed during the approximately 13-minute simultaneous capture.

The device remained connected.

This is consistent with the static comparison:

```text
mDNS responder present
```

but:

```text
no recurring connected-maintenance restart
identified in the examined path
```

The result does not imply that 2.1.0 can never transmit mDNS.

It only shows that no periodic probe/announcement behavior comparable to the later firmware versions was observed during this test window.

---

## 9.2 Firmware 2.1.3

Firmware 2.1.3 produced the recurring sequence approximately every 60 seconds.

The runtime result agrees with the corresponding firmware path and establishes the recurring restart as actual network behavior rather than merely dormant code.

---

## 9.3 Firmware 2.2.4

Stock firmware 2.2.4 produced the same characteristic probing sequence but approximately every 180 seconds.

The measured intervals closely match the every-third-serviced-minute scheduler reconstructed from the firmware.

The combined result is:

| Firmware | Runtime periodic mDNS behavior |
|---|---|
| 2.1.0 | not observed during available capture |
| 2.1.3 | ~60 s |
| 2.1.8 | modulo-3 scheduling identified statically |
| 2.2.4 | ~180 s |

---

# 10. Patch B

## 10.1 Purpose

Patch B was created as a mechanism-isolation experiment.

Its purpose is to remove only the recurring connected-maintenance restart while preserving the rest of the mDNS implementation and the unrelated WLAN behavior.

Patch B deliberately does not modify:

- the mDNS responder implementation
- mDNS network-interface registration
- mDNS service registration
- connection-establishment mDNS behavior
- UDP receive processing
- beacon statistics
- `real_beacon_skip`
- Beacon Recovery
- WLAN power-management state selection
- RSSI thresholds
- cloud handling
- thermostat control

This allows the periodic mDNS workload to be tested independently from Beacon Recovery.

---

## 10.2 Exact Patch Location

The relevant instruction in firmware 2.2.4 is:

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

Only one byte in the main program changes:

```text
program.bin offset 0x0001E0F1

D0 -> E0
```

For the validated historical GBL containing this patch, the corresponding changed byte was:

```text
GBL offset 0x00024645
```

The instruction is a 16-bit Thumb branch.

---

## 10.3 Control-Flow Effect

The original code is:

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
        +--------------------> 0x1E0F8

otherwise
        |
        v
load network interface
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

The periodic path therefore always continues at the existing post-call location.

The network-interface load at `0x1E0F2` and call at `0x1E0F4` remain physically present in the firmware image but are no longer reached through this periodic path.

The patch does not:

- split an instruction
- alter stack depth
- introduce a new function
- change processor mode
- globally disable the responder

---

## 10.4 Verification Window

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

is the existing call to the restart function.

It remains unchanged.

Only the branch deciding whether the periodic path reaches it is modified.

---

# 11. Why Patch B Does Not Disable mDNS

Five direct callers of the restart function were identified.

Patch B bypasses one.

The following identified restart paths remain intact:

```text
button-related conditional restart

mDNS network-interface registration

mDNS service registration

successful connection-establishment restart
```

The responder's receive processing also remains intact.

Patch B therefore isolates the periodic maintenance behavior without attempting to remove the mDNS subsystem.

This is useful experimentally because it avoids turning an mDNS-specific test into a general network-stack modification.

---

# 12. Patch-B Runtime Validation

A physical TRV was operated with firmware 2.2.4 containing Patch B while leaving stock Beacon Recovery unchanged.

This became the `.77` Patch-B test device.

A passive packet capture was performed using a filter equivalent to:

```text
udp port 5353 and host <patched-device>
```

The observation covered multiple intervals in which stock 2.2.4 would normally have executed the periodic restart.

No targeted periodic mDNS packets were captured during that monitored interval.

This matches the intended control-flow effect of Patch B.

The result does not mean that the device can never transmit mDNS. The event-driven paths deliberately remain available.

It demonstrates that the targeted recurring sequence is suppressed.

---

# 13. Long-Term `.77` Result

The `.77` device later provided a much longer isolation test.

Its relevant configuration was:

```text
Host firmware:
    2.2.4 + Patch B

Periodic mDNS restart:
    suppressed

Beacon Recovery:
    stock behavior retained
```

The device eventually reached:

```text
battery:              0 %
voltage:              3.116 V
uptime:               ~9.23 days
reconnect_counter:    30
desired_beacon_skip:  15
real_beacon_skip:     1
beacon_err_counter:   12908
```

This corresponds to approximately:

```text
12908 / (9.23 * 24)
≈ 58.3 Beacon Recovery events per hour
```

The exact event rate varies over time, but the long-term result is unambiguous in one important respect:

```text
periodic mDNS restart suppressed

        while

Beacon Recovery continued at high frequency
```

The periodic mDNS restart is therefore not required for the recurring Beacon Recovery behavior.

The full discharge of `.77` must not be interpreted as proof that Beacon Recovery alone caused the discharge. The experiment was not an electrical power measurement and other host, radio and environmental factors remained active.

What the test does provide is a strong negative causal result:

> Removing the targeted periodic mDNS restart did not remove recurring Beacon Recovery and did not prevent the tested device from exhibiting poor long-term battery behavior.

---

# 14. Device-History Note for `.77`

The `.77` device has been used in two different configurations during this investigation.

During the original firmware-comparison packet capture:

```text
.77 = stock firmware 2.1.3
```

Later:

```text
.77 = firmware 2.2.4 + Patch B
```

These datasets serve different purposes.

The earlier configuration establishes the approximately 60-second periodic mDNS behavior of 2.1.3.

The later configuration tests the effect of suppressing the periodic restart in 2.2.4.

Current `.77` logs must therefore not be interpreted as stock 2.1.3 data.

---

# 15. Relationship to Beacon Recovery

The original mDNS investigation considered a plausible chain such as:

```text
periodic mDNS restart
        |
        v
WLAN activity / timing disturbance
        |
        v
beacon measurement anomaly
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery
```

Patch B allowed the strong form of that hypothesis to be tested directly.

The result was:

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

The long-term `.77` experiment strengthens this result because the continued Recovery behavior was not limited to a short observation window.

The correct conclusion is:

> The targeted periodic mDNS restart is not necessary for recurring Beacon Recovery under the tested conditions.

This does not prove that mDNS activity can never influence WLAN timing or beacon statistics.

It only removes the periodic restart as a required cause of the recurring Recovery behavior.

---

# 16. Why the Recovery Interpretation Changed

Later reverse engineering of the Beacon Recovery path identified multiple host-side validity problems in the `real_beacon_skip` control chain.

The most important for the original mDNS hypothesis is the post-Recovery stale-state behavior.

In stock firmware, Recovery can clear the beacon-counter baseline while retaining the previously calculated `real_beacon_skip` value.

The following sample can therefore be baseline-only while the historical control value is evaluated again.

Conceptually:

```text
qualifying Recovery
        |
        v
beacon baseline P cleared
        |
        v
real_beacon_skip R retained
        |
        v
next sample establishes baseline only
        |
        v
historical R evaluated again
        |
        v
Recovery can repeat
```

This means a new RF anomaly is not required every minute to explain the stock recurring loop.

Consequently, a hypothesis such as:

```text
mDNS must create a fresh beacon anomaly every minute
```

is no longer necessary.

Patch B independently confirms this experimentally because the recurring Recovery loop persists after the periodic mDNS restart is removed.

The cause of an initial qualifying Beacon Recovery event is a separate question.

No evidence currently establishes periodic mDNS as that initial trigger.

---

# 17. Patch C-C and the Updated Recovery Model

Patch A was an early isolation patch that bypassed the Beacon Recovery action itself.

It was useful experimentally, but it suppresses both invalid and potentially legitimate Recovery.

The later Patch C-C design instead corrects the identified host-side validity problems while preserving Recovery for a fresh qualifying estimator result.

Patch C-C has now progressed beyond static design work and has been exercised on physical TRV hardware.

Relevant configurations include:

```text
.88
    2.2.4 + C-C
    WF200 3.16.1

.237
    2.2.4 + C-C
    WF200 3.18.0

.234
    2.2.4 + A1 + C-C
    WF200 3.18.0
```

These tests changed the interpretation of Beacon Recovery further.

C-C removes the stale/signed/invalid-window behavior targeted by the patch, but it does not eliminate all Recovery.

For example, the `.234` A1+C-C+WF200 3.18.0 test continued to show approximately 28 fresh qualifying Recovery events per hour during part of the long-term test.

A separate `.237` C-C+WF200 3.18.0 reference showed a similar order of magnitude.

This means there are two distinct questions:

```text
1. Can invalid/stale host evidence create recurring Recovery?
   Yes. C-C addresses this.

2. Can fresh measurements still satisfy the stock Recovery condition?
   Yes. Hardware testing shows that they can.
```

The second question remains under investigation.

It does not restore the periodic-mDNS hypothesis: fresh Recovery has been observed under configurations and conditions where mDNS cannot be treated as its demonstrated cause.

The mDNS and Beacon Recovery mechanisms should therefore remain separate in the current model.

---

# 18. D3 Observation and the mDNS Interpretation

A separate D3 observer firmware was used to count the known WF200 `PS_MODE_ERROR` indication while retaining the stock 2.2.4 Beacon Recovery behavior.

On the `.11` device, a long-term observation reached approximately:

```text
uptime:             63.9 h
beacon_err:         3835
D3_total:           0
```

The device therefore accumulated thousands of host Beacon Recovery events without a recorded D3 `PS_MODE_ERROR`.

This does not prove that the WF200 radio was always in a correct physical power state.

It does show that the known D3 indication is not required for the host Beacon Recovery mechanism.

Together with Patch B, this removes two previously plausible required triggers:

```text
periodic mDNS restart
        not required

known D3 PS_MODE_ERROR
        not required
```

The upstream meaning of the fresh beacon estimator therefore remains a separate problem.

---

# 19. Historical Patch A+B

Patch A and Patch B were combined during an earlier mechanism-isolation phase.

Patch A bypassed the Beacon Recovery action:

```text
program.bin:

0x1E1C8
31 DC -> 31 E0
```

Changed byte:

```text
0x1E1C9
DC -> E0
```

Patch B bypassed the periodic mDNS restart:

```text
program.bin:

0x1E0F0
02 D0 -> 02 E0
```

Changed byte:

```text
0x1E0F1
D0 -> E0
```

Corresponding changed-byte locations in the historical GBL were:

```text
Patch B: 0x00024645   D0 -> E0
Patch A: 0x0002471D   DC -> E0
```

The validated historical combined firmware had:

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

These values document the historical experiment.

Patch A+B is not the current preferred corrective design.

Patch A removes the Recovery action rather than correcting the validity of the evidence that reaches it.

C-C supersedes Patch A for that purpose.

Patch B remains useful independently as an mDNS isolation experiment.

---

# 20. Network Activity

A normal successful periodic mDNS restart can generate approximately:

```text
3 probe packets
+
1 announcement packet
```

For the approximately 60-second schedule in 2.1.3, that corresponds to roughly four visible mDNS transmissions per minute during normal successful operation.

The modulo-3 schedule in 2.1.8 and 2.2.4 reduces the average frequency.

These numbers describe only the visible mDNS sequence.

They do not include:

- lower-layer WLAN traffic
- acknowledgements
- retransmissions
- beacon reception
- cloud traffic
- controller traffic
- other application traffic
- radio-internal processing

Packet count therefore cannot be converted directly into battery consumption.

---

# 21. Power-Management Relevance

The periodic restart is unquestionably additional work.

Each normal cycle requires some combination of:

```text
application processing
        |
        v
mDNS state-machine processing
        |
        v
packet construction
        |
        v
network-stack processing
        |
        v
WLAN transmission
```

The network subsystem must be available to perform that work.

However, the analysis has not established the periodic mDNS restart as a permanent host sleep lock.

No direct electrical measurement has determined:

- host wake duration per restart
- WF200 active duration per restart
- current consumed by the probe sequence
- energy per restart
- additional daily battery consumption

The safe conclusion is therefore:

> The periodic mDNS restart creates a real recurring network and processing workload, but its quantitative energy cost is unknown.

---

# 22. Relationship to Other Sleep Findings

Subsequent host power-management analysis identified additional mechanisms that are independent of periodic mDNS.

These include host-side WLAN sleep-resource lifecycle problems and a separate shared B2 blocker-accounting concurrency defect.

Those findings are documented separately because they concern host sleep admission and ownership accounting rather than mDNS.

No direct causal chain has been demonstrated in which:

```text
periodic mDNS restart
        |
        v
host blocker corruption
```

or:

```text
periodic mDNS restart
        |
        v
WF200 persistent no-sleep condition
```

must occur.

The mechanisms should therefore not be merged simply because all of them can affect energy use.

The mDNS finding is narrower:

```text
periodic recurring workload
```

with an unmeasured energy cost.

---

# 23. Battery-Drain Interpretation

The periodic mDNS restart cannot currently explain the complete historical Shelly TRV Gen1 battery-drain behavior.

Several observations prevent that conclusion.

First, the firmware chronology is not consistent with treating the 2.2.4 mDNS behavior as a new mechanism introduced together with Beacon Recovery:

```text
2.1.3
    recurring restart ~60 s

2.1.8
    modulo-3 scheduling already present

2.2.4
    modulo-3 scheduling retained
```

Second, Patch B removes the targeted recurring mDNS restart without removing recurring Beacon Recovery.

Third, the `.77` Patch-B device still exhibited poor long-term battery behavior and ultimately reached the end of its discharge test.

Fourth, separate host and WF200 power-management behavior exists outside the mDNS mechanism.

The current model is therefore multi-mechanism rather than a single mDNS root-cause model:

```text
periodic mDNS
        |
        +-- recurring network / processing workload
        |
        +-- quantitative battery cost unknown


Beacon Recovery
        |
        +-- host-side estimator / validity defects
        |
        +-- stale recurrence corrected by C-C
        |
        +-- fresh qualifying events still observed


host sleep management
        |
        +-- separate resource-lifecycle and
            blocker-accounting behavior


WF200
        |
        +-- independent radio power-management behavior
            still relevant to the investigation
```

No one of these mechanisms has been demonstrated to explain the complete historical battery-drain problem by itself.

---

# 24. What the Patch-B Experiment Establishes

Patch B provides a useful causal isolation result.

It demonstrates that:

1. the targeted periodic mDNS restart can be bypassed independently
2. the remaining identified mDNS restart paths can remain present
3. the characteristic periodic mDNS bursts disappear during the monitored runtime
4. Beacon Recovery continues without those bursts
5. long-term recurring Beacon Recovery also continues on the Patch-B device

The strongest supported statement is:

> The targeted recurring connected-maintenance mDNS restart is not required for the recurring Beacon Recovery behavior observed on the tested TRV.

Patch B does **not** establish that:

- mDNS has zero energy cost
- mDNS can never influence WLAN timing
- no mDNS packet can ever be generated
- mDNS can never affect beacon statistics
- suppressing the periodic restart has zero battery benefit
- all APs behave identically
- all firmware versions have identical mDNS behavior
- Patch B is a complete battery-drain fix
- the historical drain is unrelated to every form of mDNS activity

Those are different questions.

---

# 25. Why 2.1.0 Remains Useful

Firmware 2.1.0 separates mDNS capability from the later recurring maintenance behavior.

It contains the responder, but the recurring connected-maintenance restart was not identified in the examined corresponding path.

During the available comparison:

```text
2.1.0
    no comparable periodic mDNS burst observed

2.1.3
    periodic burst approximately every 60 s

2.2.4
    periodic burst approximately every 180 s
```

The 2.1.0 device remained reachable during practical operation.

This supports the narrower conclusion that continuously restarting the probing sequence is not obviously required for basic IP connectivity.

Basic connectivity is not equivalent to complete mDNS service-discovery behavior, which is why Patch B retains the responder and its event-driven paths.

---

# 26. Why 2.1.8 Remains Useful

Firmware 2.1.8 establishes that the scheduling change occurred before 2.2.4.

Without it, the history could be misread as:

```text
2.1.3
~60 s
    |
    v
2.2.4
new ~180 s mechanism
```

The actual examined history is:

```text
2.1.3
~60 s recurring restart
    |
    v
2.1.8
modulo-3 minute gate already present
    |
    v
2.2.4
same general scheduling retained
```

This is particularly relevant because Beacon Recovery as currently investigated is a 2.2.4-specific host control path, while the mDNS scheduling change predates it.

The chronology therefore does not support treating the two mechanisms as a single feature introduced in 2.2.4.

---

# 27. Current Experimental Roles

The main experimental configurations have different purposes:

| Configuration | Purpose |
|---|---|
| Stock 2.2.4 | reference behavior |
| Patch B | isolate periodic mDNS workload |
| Patch A | historical Beacon Recovery action isolation |
| Patch A+B | historical combined isolation |
| Patch C-C | correct Beacon Recovery validity semantics while retaining Recovery |
| A1 + C-C | additionally correct identified WLAN PM lifecycle/ownership defects |
| WF200 3.18.0 variants | evaluate newer Silicon Labs radio firmware |

These experiments should not be collapsed into a single “patched vs. stock” comparison.

Each modifies a different part of the system.

---

# 28. Current Device Roles Relevant to This Analysis

Relevant current or historical roles include:

```text
.77
    2.2.4 + Patch B
    periodic mDNS restart suppressed
    stock Beacon Recovery retained
    long-term discharge experiment completed


.88
    2.2.4 + C-C
    WF200 3.16.1
    Beacon Recovery validity-correction reference


.229
    stock 2.2.4
    stock reference


.234
    A1 + C-C
    WF200 3.18.0
    integrated host/radio experimental reference


.237
    C-C
    WF200 3.18.0
    C-C + newer-radio reference
```

Device history matters.

A device identifier alone must not be used to infer its firmware configuration without considering the date and test phase.

---

# 29. Battery Testing

Battery comparisons should prioritize:

```text
bat.voltage
```

over the quantized:

```text
bat.value
```

percentage.

Useful supporting data include:

- uptime
- firmware identity
- WF200 version
- RSSI
- desired beacon skip
- real beacon skip
- Beacon Recovery count
- reconnect count
- motor activity
- cloud state
- network configuration

For an mDNS-specific comparison, passive packet capture remains useful for confirming that the targeted periodic bursts are present on stock firmware and absent on Patch B.

Packet capture is not an energy measurement.

---

# 30. Remaining Questions

The mDNS mechanism itself is now sufficiently understood for the current investigation. The main remaining questions concern its practical cost rather than its basic control flow.

Useful open questions are:

1. How much energy does one normal periodic restart sequence consume?
2. How long does the host and WF200 remain in a higher-power state because of one restart?
3. Does the energy cost differ significantly between the 2.1.3 ~60-second and later ~180-second schedules?
4. Does removing the periodic restart measurably improve long-term battery voltage decay when other variables are controlled?
5. Can the periodic restart influence an initial fresh beacon-estimator event under particular AP or timing conditions even though it is not required for recurring Recovery?
6. How often are the retained non-periodic mDNS restart paths exercised during normal operation?
7. Does suppressing the periodic restart have any measurable long-term effect on mDNS discoverability?
8. Why was the recurring restart introduced in 2.1.3 and then reduced to every third minute by 2.1.8?

The last question concerns original developer intent and cannot be resolved from the current firmware evidence alone.

---

# 31. Current Interpretation

The periodic mDNS restart is a real firmware behavior with a clear evolution:

```text
2.1.0
    responder present
    no later-style recurring caller identified


2.1.3
    recurring connected-maintenance restart
    ~60 s


2.1.8
    recurring restart retained
    modulo-3 minute scheduling


2.2.4
    same general modulo-3 scheduling
    ~180 s runtime cadence
```

In firmware 2.2.4, the periodic caller reaches:

```text
mdns_resp_restart()
0x3D6C8
```

through the call at:

```text
0x1E0F4
```

Patch B changes:

```text
0x1E0F0

02 D0
  ↓
02 E0
```

and therefore bypasses that one periodic call.

The responder and other identified restart paths remain intact.

Runtime packet capture confirms that the targeted recurring mDNS sequence disappears under Patch B.

The long-term `.77` experiment then provides the most important isolation result:

```text
periodic mDNS restart
        |
        v
suppressed


Beacon Recovery
        |
        v
continues at high frequency
```

The device accumulated approximately 12,908 Recovery events over about 9.23 days despite the periodic mDNS restart being suppressed.

Periodic mDNS therefore cannot be treated as a required cause of recurring Beacon Recovery.

Later C-C testing further separates the mechanisms. Correcting stale and invalid host-side Recovery evidence does not eliminate all fresh qualifying Recovery events, showing that the remaining upstream problem must be investigated independently.

The current interpretation is consequently:

> The recurring mDNS restart is a confirmed periodic network and processing workload. It has a non-zero energy cost in principle, but its quantitative contribution to battery drain has not been measured. It is not required for the recurring Beacon Recovery behavior observed on the tested devices and is not established as the root cause of the historical Shelly TRV Gen1 battery-drain problem.

---

# Related Documents

Firmware comparison:

[`firmware-comparison.md`](firmware-comparison.md)

Beacon-counter measurement model:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

`real_beacon_skip` calculation:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery mechanism:

[`recovery-mechanism.md`](recovery-mechanism.md)

Power-management and host sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Experimental patch documentation:

[`../patch/README.md`](../patch/README.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Method

This investigation combines static reverse engineering of locally obtained Shelly TRV Gen1 firmware with runtime observations from personally owned devices.

The mDNS work used:

- cross-version firmware comparison
- native call-site analysis
- connected-maintenance control-flow reconstruction
- scheduler analysis
- passive packet capture
- isolated Patch-B testing
- historical Patch-A+B testing
- comparison with Beacon Recovery behavior
- long-term device testing

The examined firmware versions include:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

Runtime packet captures directly covered:

```text
2.1.0
2.1.3
2.2.4 stock
2.2.4 + Patch B
2.2.4 + Patch A+B
```

The 2.1.8 modulo-3 result comes from static cross-version analysis rather than an equivalent dedicated packet-capture series.

No original or modified Shelly firmware image, complete proprietary function, or large raw disassembly is reproduced here.

Addresses and small instruction sequences are included only where necessary to document the analyzed control flow and experimental patch.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings describe observed and reverse-engineered behavior of the investigated firmware versions. Statements about battery-drain causality are intentionally limited to what the available static and runtime evidence supports.