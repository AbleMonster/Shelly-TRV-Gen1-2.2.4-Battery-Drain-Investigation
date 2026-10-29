# Periodic mDNS Restart

## Scope

This document describes the recurring mDNS restart mechanism found in Shelly TRV Gen1 firmware and how that mechanism evolved across the investigated firmware generations.

The analysis focuses specifically on the connected-maintenance path that periodically restarts the mDNS probing sequence.

It covers:

- firmware chronology
- mDNS responder versus periodic restart
- scheduling differences
- direct restart callers
- probe/announcement traffic
- runtime packet captures
- Patch B
- the long-term `.77` isolation result
- the relationship between mDNS and Beacon Recovery
- the later C-C interpretation
- the current corrected firmware architecture
- relevance to the battery-drain investigation

The central distinction is:

```text
mDNS responder
        !=
periodic restart of mDNS probing
```

Patch B targets only the second mechanism.

---

# 1. Summary

The mDNS responder already exists in firmware 2.1.0.

What changes in later firmware is the addition of a recurring connected-maintenance path that restarts the probing sequence.

The investigated chronology is:

| Firmware | mDNS responder | Recurring connected-maintenance restart | Scheduling |
|---|---|---|---|
| 2.1.0 | present | not identified in examined path | no comparable periodic burst observed |
| 2.1.3 | present | present | ~60 s |
| 2.1.8 | present | present | modulo-3 minute gate |
| 2.2.4 | present | present | ~180 s runtime |

The scheduling change therefore predates firmware 2.2.4.

In 2.2.4 the restart is not driven by a dedicated 180-second timer.

It is reached through minute maintenance and executes every third serviced minute.

A normal successful restart produces approximately:

```text
probe
probe
probe
announcement
```

Patch B changes one conditional branch in the periodic caller:

```text
0x1E0F0

02 D0    BEQ 0x1E0F8
  ↓
02 E0    B   0x1E0F8
```

This bypasses the periodic call while preserving the mDNS responder and the other identified restart paths.

Runtime testing confirmed that:

```text
periodic mDNS bursts disappear
```

while:

```text
normal device operation remains available
```

and:

```text
stock Beacon Recovery continues
```

The strongest historical isolation result came from `.77`.

With:

```text
2.2.4 + Patch B
```

the device accumulated approximately:

```text
12,908 Beacon Recoveries
~9.23 days runtime
~58 Recoveries/hour
```

and reached the end of its discharge test.

Therefore:

> The targeted periodic mDNS restart is not required for the recurring Beacon Recovery behavior observed on firmware 2.2.4.

This does not mean mDNS has zero energy cost.

Its quantitative power cost has not been directly measured.

---

# 2. mDNS Responder vs. Periodic Restart

The mDNS implementation itself must not be confused with the periodic mechanism documented here.

Firmware 2.1.0 already contains normal mDNS responder functionality.

Normal events can therefore generate mDNS traffic without any recurring maintenance restart.

The later behavior adds:

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

Patch B does not disable mDNS globally.

It suppresses one specific recurring caller.

Other event-driven mDNS behavior remains available.

---

# 3. Firmware 2.1.0

Static analysis identifies the mDNS responder in firmware 2.1.0.

The corresponding connected-maintenance path does not contain the recurring restart caller identified in later firmware.

The distinction is:

```text
2.1.0

mDNS responder present
        |
        v
normal event-driven mDNS possible

but

later-style recurring connected-maintenance
restart not identified
```

A historical runtime capture also showed no comparable periodic mDNS burst during the available observation interval.

This does not prove 2.1.0 never sends mDNS.

It only means the recurring mechanism documented here was not identified or observed.

---

# 4. Firmware 2.1.3

Firmware 2.1.3 contains the recurring connected-maintenance restart.

Conceptually:

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

A historical runtime capture showed approximately once-per-minute recurrence.

Representative traffic:

```text
59.699110 s   probe
60.005565 s   probe
60.211304 s   probe
60.519855 s   announcement
```

Observed burst starts included approximately:

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

The dominant interval is approximately:

```text
60 s
```

---

# 5. Firmware 2.1.8

Firmware 2.1.8 provides an important intermediate stage.

The recurring restart remains present, but the scheduler now contains the modulo-3 maintenance gate later retained in 2.2.4.

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

Therefore the change from approximately one minute to approximately three minutes occurred by firmware 2.1.8.

No equivalent dedicated packet-capture series was performed for the historical 2.1.8 reference.

The ~180-second interpretation is therefore derived from the reconstructed scheduler rather than independently measured in that experiment.

---

# 6. Firmware 2.2.4

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

The mechanism is therefore better described as:

```text
every third serviced minute
```

rather than:

```text
independent 180-second timer
```

Historical runtime burst starts included:

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

A representative burst:

```text
117.554727 s   probe
117.761173 s   probe
117.964812 s   probe
118.272223 s   announcement
```

The physical interval is not required to be exactly 180.000 seconds because the path depends on serviced scheduler boundaries.

---

# 7. Firmware Timeline

The resulting history is:

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
   +-- ~60 s


2.1.8
   |
   +-- recurring restart retained
   |
   +-- modulo-3 minute gate


2.2.4
   |
   +-- modulo-3 scheduling retained
   |
   +-- ~180 s confirmed at runtime
```

This matters because the three-minute scheduling behavior was not introduced together with Beacon Recovery.

The two mechanisms have separate firmware histories.

---

# 8. mDNS Restart Function in 2.2.4

The function identified as the 2.2.4 `mdns_resp_restart()` equivalent is located at:

```text
0x0003D6C8
```

For a registered mDNS interface its behavior is approximately:

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

The initial scheduling includes a randomized component based on modulo 250.

For battery analysis, directly observed network timing is more useful than over-interpreting the internal unit of that randomized value.

---

# 9. Direct Restart Callers in 2.2.4

Five direct callers were identified:

| Caller | Call instruction | Role |
|---|---:|---|
| `0x1D918` | `0x1E0F4` | periodic connected-operation maintenance |
| `0x173B4` | `0x174A4` | conditional button-release path |
| `0x3D2F8` | `0x3D3E2` | successful mDNS network-interface registration |
| `0x3D430` | `0x3D5DC` | successful mDNS service registration |
| `0x63680` | `0x639EE` | successful connection-establishment path |

Patch B targets only:

```text
0x1D918
   |
   v
periodic connected maintenance
   |
   v
0x1E0F4
   |
   v
mdns_resp_restart()
```

The other four identified paths remain unchanged.

Therefore Patch B should be described as:

> suppressing the recurring connected-maintenance mDNS restart

not:

> disabling mDNS.

---

# 10. Probe Sequence

After a restart:

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

Observed traffic uses:

```text
UDP 5353
```

and IPv4 multicast destination:

```text
224.0.0.251
```

A packet capture does not necessarily expose every internal attempt, so an individual burst should not automatically be treated as a complete mDNS state-machine trace.

---

# 11. Retry Behavior

The normal three-probe sequence is not the only possible path.

If a probe cannot complete successfully, the probe counter may not advance.

Possible examples include:

```text
IPv4 unavailable
```

or:

```text
probe construction / transmission failure
```

The callback can then be scheduled again.

No small explicit per-run retry limit was identified in the examined path.

A later periodic restart can also reset the probing sequence again.

Normal successful sequences and failure/retry sequences must therefore remain separate interpretations.

---

# 12. Historical Runtime Comparison

A passive packet capture was performed on 2026-10-11.

Devices:

| Device | Firmware during capture | Purpose |
|---|---|---|
| `.11` | 2.1.0 | old firmware reference |
| `.77` | 2.1.3 | recurring-restart reference |
| `.229` | stock 2.2.4 | stock reference |

The observation interval was approximately 13 minutes.

This was a network-behavior experiment.

It was not an electrical power measurement.

---

# 13. Historical 2.1.0 Runtime Result

No comparable periodic mDNS traffic from the 2.1.0 reference was observed during the available window.

The device remained connected.

This agrees with:

```text
mDNS responder present
```

but:

```text
no recurring connected-maintenance restart
identified in examined path
```

The result does not imply that 2.1.0 never transmits mDNS.

---

# 14. Historical 2.1.3 Runtime Result

Firmware 2.1.3 produced the recurring sequence approximately every 60 seconds.

This confirmed that the static recurring-restart path is active network behavior rather than merely dormant code.

---

# 15. Historical 2.2.4 Runtime Result

Stock 2.2.4 produced the same characteristic probe/announcement pattern approximately every 180 seconds.

The measured timing closely matched the every-third-serviced-minute scheduler.

Summary:

| Firmware | Runtime periodic mDNS behavior |
|---|---|
| 2.1.0 | not observed during available capture |
| 2.1.3 | ~60 s |
| 2.1.8 | modulo-3 scheduling identified statically |
| 2.2.4 | ~180 s |

---

# 16. Patch B Purpose

Patch B was created as a mechanism-isolation experiment.

Its purpose is to remove only the recurring connected-maintenance restart while preserving:

- mDNS responder implementation
- network-interface registration
- service registration
- connection-establishment mDNS behavior
- UDP receive processing
- beacon statistics
- `real_beacon_skip`
- Beacon Recovery
- WLAN PM policy
- RSSI thresholds
- Cloud
- thermostat behavior

This allowed the recurring mDNS workload to be tested independently.

---

# 17. Patch B Location

Firmware 2.2.4:

```text
Virtual address:
0x0001E0F0

program.bin offset:
0x0001E0F0
```

Original:

```text
BEQ 0x0001E0F8
```

Bytes:

```text
02 D0
```

Patched:

```text
B 0x0001E0F8
```

Bytes:

```text
02 E0
```

Only one byte changes in the main program:

```text
program.bin offset 0x0001E0F1

D0 -> E0
```

Historical GBL changed-byte location:

```text
0x00024645
```

---

# 18. Patch B Control-Flow Effect

Original:

```text
0x1E0F0   BEQ 0x1E0F8
0x1E0F2   load network-interface argument
0x1E0F4   BL 0x3D6C8
0x1E0F8   existing continuation
```

Patch B changes:

```text
0x1E0F0   BEQ 0x1E0F8
```

to:

```text
0x1E0F0   B 0x1E0F8
```

The existing post-call continuation remains unchanged.

The network-interface load and restart call remain physically present in the image but are no longer reached through this periodic path.

The patch does not:

- split an instruction
- alter stack depth
- introduce a new function
- change processor mode
- globally disable mDNS

---

# 19. Verification Window

Original bytes:

```text
02 D0 29 48 1F F0 E8 FA 12 4B
```

Patched:

```text
02 E0 29 48 1F F0 E8 FA 12 4B
```

The existing call:

```text
1F F0 E8 FA
```

remains unchanged.

Only the branch controlling access to it changes.

---

# 20. Why Patch B Does Not Disable mDNS

Patch B bypasses one of five identified direct restart callers.

The following remain intact:

```text
button-related conditional restart

mDNS network-interface registration

mDNS service registration

successful connection-establishment restart
```

Responder receive processing also remains.

Patch B therefore isolates periodic maintenance rather than removing the protocol subsystem.

---

# 21. Patch-B Runtime Validation

A physical TRV was operated with:

```text
2.2.4 + Patch B
```

while retaining stock Beacon Recovery.

A passive packet-capture filter equivalent to:

```text
udp port 5353 and host <patched-device>
```

covered multiple intervals where stock 2.2.4 would normally have executed the recurring restart.

No targeted periodic mDNS packets were observed.

This matches the intended control-flow effect.

It does not prove that no event-driven mDNS packet can ever occur.

---

# 22. Historical `.77` Long-Term Result

The historical `.77` configuration was:

```text
Host:
    2.2.4 + Patch B

Periodic mDNS restart:
    suppressed

Beacon Recovery:
    stock behavior retained
```

Final observed state was approximately:

```text
battery:              0 %
voltage:              3.116 V
uptime:               ~9.23 days
reconnect_counter:    30
desired_beacon_skip:  15
real_beacon_skip:     1
beacon_err_counter:   12908
```

Recovery rate:

```text
12908 / (9.23 × 24)
≈ 58.3 Recoveries/hour
```

The exact event rate varied over time.

The important result is:

```text
periodic mDNS restart suppressed
        while
Beacon Recovery remained frequent
```

Therefore the periodic restart is not required for recurring Recovery.

The full `.77` discharge does not prove that Beacon Recovery alone caused the battery loss.

---

# 23. `.77` Device-History Note

`.77` has represented multiple experiment phases.

Historical packet-capture phase:

```text
.77 = stock 2.1.3
```

Historical Patch-B phase:

```text
.77 = 2.2.4 + Patch B
```

Current phase:

```text
.77 = B2.1_OBS
```

These datasets must remain separated by experiment date/build.

A device identifier alone is never sufficient firmware identity.

---

# 24. Original mDNS-to-Recovery Hypothesis

An early plausible hypothesis was:

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

Patch B tested the strong form of that hypothesis.

Observed:

```text
periodic mDNS restart
        |
        v
suppressed
```

while:

```text
Beacon Recovery
        |
        v
continues
```

Therefore:

> The targeted recurring mDNS restart is not necessary for recurring Beacon Recovery under the tested conditions.

---

# 25. C2 Changed the Recovery Interpretation

Later Beacon Recovery analysis identified multiple host-side validity defects.

The most relevant to the original mDNS hypothesis is C2.

Stock Recovery can clear:

```text
P = beacon baseline
```

while retaining:

```text
R = previously derived real_beacon_skip
```

Conceptually:

```text
fresh qualifying R
        |
        v
Recovery
        |
        v
P cleared
R retained
        |
        v
next sample establishes P only
        |
        v
no fresh R
        |
        v
historical R evaluated
        |
        v
Recovery can recur
```

Therefore a new RF or network anomaly is not required before every recurring stock Recovery.

---

# 26. C2 Is Metastable

Earlier project language sometimes referred to C2 as a:

```text
self-sustaining loop
```

or implied that the state necessarily persists until reboot.

The stronger interpretation is not justified.

The demonstrated behavior is:

```text
metastable stale-evidence recurrence
```

It can persist for long periods and produce roughly minute-spaced Recovery.

However:

> The firmware can leave the recurrence without reboot.

This preserves the observed long-lived behavior without overstating permanence.

---

# 27. Consequence for mDNS

Because C2 can reuse historical evidence, the model:

```text
mDNS must generate a fresh anomaly
every minute
```

is unnecessary.

Patch B provides independent experimental support for this conclusion because recurring Recovery continued after the periodic mDNS restart was removed.

Whether periodic mDNS could influence an initial fresh estimator event under some conditions remains unresolved.

No evidence currently establishes it as a required initial trigger.

---

# 28. C-C

Historical Patch A bypassed Recovery entirely.

C-C instead corrects the demonstrated validity defects while retaining fresh valid Recovery.

C-C addresses:

```text
C1a
signed interpretation

C1b
measurement-window validity

C2
historical control evidence reused as fresh evidence
```

It does not modify mDNS.

---

# 29. Historical C-C Runtime

Historical configurations included:

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

These are historical roles.

C-C removed the demonstrated stale/invalid host evidence behavior but did not eliminate all fresh Recovery.

Historical C-C-based periods showed approximately:

```text
27–30 fresh Recoveries/hour
```

under some conditions.

Those values are specific observations, not universal rates.

---

# 30. Historical A1 + C-C + WF200 3.18.0

The `.234` A1+C-C+WF200 3.18.0 experiment was an important historical integration test.

It showed:

- FMAC 3.7.0 / WF200 3.18.0 interoperability
- functioning WLAN
- DHCP
- Cloud
- thermostat operation
- valve operation
- PM transitions
- fresh Recovery after C-C

A1 was later superseded by A1R.

Historical A1 measurements retain their original identity.

---

# 31. D3 Observation

A separate historical D3 observer retained stock Beacon Recovery while recording the known WF200 `PS_MODE_ERROR` indication.

On `.11`, approximately:

```text
uptime:
63.9 h

beacon_err:
3835

D3_total:
0
```

Therefore thousands of host Recovery events occurred without a recorded D3 event.

This establishes that the known D3 indication is not required for the observed host Recovery mechanism.

It does not prove that the radio was always physically in a correct low-power state.

---

# 32. Patch A+B

Patch A and Patch B were also combined during the early mechanism-isolation phase.

Patch A:

```text
program.bin

0x1E1C8
31 DC -> 31 E0
```

changed byte:

```text
0x1E1C9
DC -> E0
```

Patch B:

```text
program.bin

0x1E0F0
02 D0 -> 02 E0
```

changed byte:

```text
0x1E0F1
D0 -> E0
```

Historical GBL changed-byte locations:

```text
Patch B: 0x00024645
Patch A: 0x0002471D
```

Historical combined GBL:

```text
Size:
1,106,384 bytes

SHA-256:
7adbb31d6b7faa8b9290d7b3436af45d42af9c3602a7195cafab774ded84ac61

CRC32:
0xBAEB8265
```

Historical patched main PROGRAM SHA-256:

```text
06742a2632a3d45cf697b8be85045914d004f30644dad17b3d0d20012c87c61b
```

These values remain historical artifact identities.

Patch A+B is not the current corrective design.

---

# 33. Network Activity

A normal successful recurring restart can generate approximately:

```text
3 probes
+
1 announcement
```

For 2.1.3 this corresponds to roughly four visible mDNS transmissions per minute during successful normal operation.

Later modulo-3 scheduling reduces the average rate.

These counts do not include:

- lower-layer WLAN traffic
- acknowledgements
- retransmissions
- beacon processing
- Cloud traffic
- controller traffic
- other application traffic
- radio-internal activity

Packet count cannot be converted directly into battery consumption.

---

# 34. Power-Management Relevance

Periodic mDNS is unquestionably additional work.

Each cycle can require:

```text
application processing
        |
        v
mDNS state machine
        |
        v
packet construction
        |
        v
network stack
        |
        v
WLAN transmission
```

The network subsystem must be available for that work.

However, the project has not established the periodic restart as:

```text
persistent host sleep lock
```

No direct electrical measurement has established:

- host awake duration per restart
- WF200 active duration per restart
- current per sequence
- energy per restart
- daily battery cost

The correct conclusion remains:

> Periodic mDNS is a real recurring workload with an unmeasured energy cost.

---

# 35. Relationship to Host-Sleep Findings

Later analysis identified independent host PM defects.

These include:

```text
A1/A1R lifecycle defects
B2 reference-counter race
PA8 WLAN sleep gating
```

No direct chain has been demonstrated where:

```text
periodic mDNS restart
        |
        v
B2 corruption
```

must occur.

Likewise, no demonstrated chain requires:

```text
periodic mDNS restart
        |
        v
persistent WF200 no-sleep condition
```

The mechanisms should remain separate.

---

# 36. B2 Correction

The B2 shared blocker counter has a demonstrated preemption/lost-update defect.

Possible outcomes include:

```text
phantom contribution
```

and:

```text
lost contribution
```

The correction uses bounded serialization while preserving reference-count semantics.

The correction is qualified and included in:

```text
B2.1
B2.1_OBS
B2.2
```

This is no longer future work.

---

# 37. A1R

Historical A1 corrected PM lifecycle defects but later introduced an experimental temporary-policy regression.

A1R supersedes A1.

Qualification:

```text
151 / 151
```

native behavior tests passed.

A1R is part of the current corrected platform.

---

# 38. Current Corrected Baseline

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

B2.1 does not include an mDNS suppression patch.

This is intentional.

The Patch-B result showed that periodic mDNS is not required for recurring Beacon Recovery, but no evidence currently justifies removing mDNS from the main corrected platform.

---

# 39. Current Diagnostic Build

The active long-term build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

The observer adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
additional WF200 request
```

It does not modify mDNS behavior.

This keeps mDNS as an unchanged variable during the current hardware test.

---

# 40. Current Hardware Population

The current active experiment is:

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

Historical `.77`, `.88`, `.234` and `.237` roles remain valid only for their historical experiment periods.

---

# 41. Current Experimental Roles

The project configurations should now be interpreted as follows:

| Configuration | Status / Purpose |
|---|---|
| Stock 2.2.4 | stock reference |
| Patch B | historical mDNS isolation |
| Patch A | historical Recovery-action isolation |
| Patch A+B | historical combined isolation |
| C-C | qualified Recovery validity correction component |
| D3 observer | historical WF200 error observation |
| MIN80 | historical experiment |
| C-C + WF200 3.18.0 | historical host/radio comparison |
| A1 + C-C + WF200 3.18.0 | historical integrated canary |
| B2.1 | current observer-free corrected baseline |
| B2.1_OBS | current active long-term hardware build |
| B2.2 | offline observer-free release candidate |

These must not be collapsed into a generic:

```text
patched vs. stock
```

comparison.

---

# 42. B2.2

B2.2 contains exactly nine selected qualified correction components:

```text
1. A1R including A1 lifecycle correction
2. C-C
3. B2 bounded serialization
4. minimal MQTT PUBLISH guard
5. official WF200 3.18.0
6. Calibration Restore Guard
7. P01 PA3 release
8. P02 I2C timeout retirement
9. P03 GPIO interrupt-mask correction
```

Status:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

B2.2 does not include Patch B.

It also does not contain the B2.1_OBS observer.

No B2.2 hardware battery result exists yet.

---

# 43. Why mDNS Is Not Included in B2.2

B2.2 includes demonstrated defects selected under the rule:

```text
demonstrated
+
safely correctable
+
independently qualified
+
composition-qualified
```

The periodic mDNS restart is demonstrated behavior, but it has not been established as a correctness defect requiring removal from the final candidate.

Patch B established a useful causal isolation result.

That is different from proving that suppressing the restart is the correct production behavior.

Therefore mDNS suppression remains excluded from B2.2.

---

# 44. Battery-Drain Interpretation

Periodic mDNS cannot currently explain the complete historical battery-drain behavior.

Reasons include:

1. The recurring mechanism predates 2.2.4.
2. Patch B removes it without eliminating recurring Recovery.
3. `.77` still exhibited poor long-term battery behavior under Patch B.
4. Independent PM lifecycle and blocker-accounting defects exist.
5. WF200 behavior remains a separate layer.
6. Drain also occurred on firmware predating Beacon Recovery.

The current model is therefore:

```text
periodic mDNS
    |
    +-- real recurring network workload
    |
    +-- battery cost not directly measured


Beacon Recovery
    |
    +-- C1a/C1b/C2 host defects
    |
    +-- C2 corrected by C-C
    |
    +-- fresh Recovery still possible


host PM
    |
    +-- A1/A1R lifecycle defects
    |
    +-- B2 ownership race
    |
    +-- PA8 gating


WF200
    |
    +-- independent radio PM behavior
```

No one mechanism is established as the complete historical root cause.

---

# 45. What Patch B Establishes

Patch B establishes that:

1. the periodic caller can be bypassed independently
2. other identified mDNS paths remain intact
3. the characteristic recurring bursts disappear
4. stock Beacon Recovery continues
5. long-term recurring Recovery continues
6. suppressing the periodic restart did not prevent poor battery behavior on `.77`

The strongest supported conclusion is:

> The targeted recurring connected-maintenance mDNS restart is not required for the recurring Beacon Recovery behavior observed on the tested TRV.

Patch B does not establish that:

- mDNS has zero energy cost
- mDNS never influences WLAN timing
- no mDNS packet can ever occur
- mDNS can never affect beacon statistics
- suppressing the restart has zero battery benefit
- all APs behave identically
- all firmware versions behave identically
- Patch B is a final battery fix

---

# 46. Why 2.1.0 Remains Useful

Firmware 2.1.0 separates:

```text
mDNS capability
```

from:

```text
recurring connected-maintenance restart
```

It contains the responder but not the later-style recurring caller in the examined path.

Historical runtime comparison showed:

```text
2.1.0
    no comparable periodic burst observed

2.1.3
    ~60 s periodic burst

2.2.4
    ~180 s periodic burst
```

This supports the narrow conclusion that continually restarting probing is not obviously required for basic IP connectivity.

It does not prove complete service-discovery equivalence.

---

# 47. Why 2.1.8 Remains Useful

Firmware 2.1.8 establishes that the scheduling change occurred before 2.2.4.

The actual examined history is:

```text
2.1.3
    ~60 s
      |
      v
2.1.8
    modulo-3 minute gate
      |
      v
2.2.4
    same general scheduling
```

Therefore the later Beacon Recovery mechanism and the modulo-3 mDNS scheduling change should not be treated as one feature introduced together in 2.2.4.

---

# 48. Battery Testing

For battery comparison:

```text
bat.voltage
```

is more useful for short-term trend analysis than the quantized:

```text
bat.value
```

percentage.

Useful supporting fields include:

- uptime
- exact firmware/build identity
- WF200 version
- RSSI
- desired skip
- real skip
- Recovery count
- reconnects
- motor activity
- Cloud state
- network configuration

For historical mDNS-specific experiments, packet capture remains useful for proving whether the periodic bursts are present.

Packet capture is not an energy measurement.

---

# 49. Current Test Strategy

The current project is no longer planning another mDNS-specific hardware modification.

The active decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

The B2.1_OBS devices should therefore keep native mDNS behavior unchanged during the current long-term experiment.

This preserves comparison integrity.

---

# 50. If B2.1_OBS Drains

If a corrected device develops genuine rapid drain:

```text
abnormal battery trajectory
        |
        v
preserve first-fault observer state
        |
        v
inspect PM52/cmd66 history
        |
        v
correlate WLAN / PM behavior
        |
        v
resume targeted RE
```

mDNS should only become a renewed experimental variable if runtime evidence specifically points back toward it.

---

# 51. If B2.1_OBS Remains Stable

If the corrected population remains stable:

```text
remove observer
        |
        v
requalify observer-free build
        |
        v
hardware regression
        |
        v
evaluate final candidate
```

There is currently no plan to add Patch B automatically to that final candidate.

---

# 52. Remaining Questions

The basic mDNS control flow is now well understood.

Remaining questions are primarily quantitative:

1. How much energy does one normal periodic restart consume?
2. How long do host and WF200 remain in higher-power states because of one cycle?
3. Does the cost differ materially between the ~60 s and ~180 s schedules?
4. Does suppressing the periodic restart measurably improve voltage decay under controlled conditions?
5. Can periodic mDNS influence an initial fresh estimator event under some AP/timing condition?
6. How often are the retained non-periodic restart paths exercised?
7. Does suppression affect long-term mDNS discoverability?
8. Why was the recurring restart introduced in 2.1.3?
9. Why was its cadence reduced by 2.1.8?

The last two questions concern original developer intent and cannot be resolved from host firmware evidence alone.

---

# 53. Current Interpretation

The periodic mDNS restart has a clear chronology:

```text
2.1.0
    responder present
    no later-style recurring caller identified

2.1.3
    recurring restart
    ~60 s

2.1.8
    recurring restart
    modulo-3 minute scheduling

2.2.4
    same general scheduling
    ~180 s runtime cadence
```

In 2.2.4 the periodic caller reaches:

```text
mdns_resp_restart()
0x3D6C8
```

through:

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

and bypasses that periodic call while preserving the responder and other identified restart paths.

Runtime testing confirms the targeted sequence disappears.

The historical `.77` experiment then provides the most important isolation result:

```text
periodic mDNS restart
        |
        v
suppressed

while

Beacon Recovery
        |
        v
continues at high frequency
```

with approximately:

```text
12,908 Recoveries
~9.23 days
~58/hour
```

Later C-C analysis further separated the mechanisms by showing that correcting stale/invalid Recovery evidence still leaves some fresh Recovery.

The current interpretation is therefore:

> The recurring mDNS restart is a confirmed periodic network and processing workload. It necessarily has some non-zero energy cost, but that cost has not been quantified. It is not required for the recurring Beacon Recovery behavior observed on the tested devices and is not established as the historical Shelly TRV Gen1 battery-drain root cause.

The historical Patch-B experiment remains valuable.

Patch B itself is not part of:

```text
B2.1
B2.1_OBS
B2.2
```

and mDNS behavior remains unchanged in the current long-term hardware test.

---

# Related Documents

Firmware comparison:

[`firmware-comparison.md`](firmware-comparison.md)

Beacon-counter model:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

`real_beacon_skip`:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

Power management:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Battery reporting:

[`battery-reporting-and-shutdown.md`](battery-reporting-and-shutdown.md)

Patch overview:

[`../patch/README.md`](../patch/README.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

Runtime mDNS comparison:

[`../testing/mdns-runtime-comparison.md`](../testing/mdns-runtime-comparison.md)

B2.1_OBS qualification:

[`../qualification/b2.1-obs-qualification.md`](../qualification/b2.1-obs-qualification.md)

B2.2 qualification:

[`../qualification/b2.2-offline-release-candidate.md`](../qualification/b2.2-offline-release-candidate.md)

---

# Research Method

This investigation combines:

- cross-version firmware comparison
- native call-site analysis
- connected-maintenance reconstruction
- scheduler analysis
- passive packet capture
- Patch-B isolation testing
- historical Patch-A+B testing
- comparison with Beacon Recovery
- long-term runtime observation

Investigated stock firmware:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

Historical runtime packet captures directly covered:

```text
2.1.0
2.1.3
2.2.4 stock
2.2.4 + Patch B
2.2.4 + Patch A+B
```

The 2.1.8 modulo-3 result derives from static cross-version analysis rather than an equivalent dedicated packet-capture series.

Historical experiment identities are preserved.

Current device identities are not inferred from old device roles.

No complete original or modified Shelly firmware image, proprietary function or large raw disassembly is reproduced here.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The findings describe observed and reverse-engineered behavior of the investigated firmware versions.

Statements about battery-drain causality are intentionally limited to what the available static and runtime evidence supports.