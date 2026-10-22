````markdown
# WF200 Firmware and Power-Save Behavior

## Shelly TRV Gen1

## Scope

This document describes the WF200 WLAN firmware used by the Shelly TRV Gen1, its evolution across the investigated Shelly firmware releases, and the relationship between radio-side power management and the host-side battery-drain investigation.

The main topics are:

- Shelly FMAC and WF200 firmware versions
- separation between host and radio power management
- WF200 power-save modes used by the TRV
- `PS_MODE_ERROR`
- the D3 observer
- the relationship between D3 and Beacon Recovery
- the experimental WF200 3.18.0 integration
- the Silicon Labs 3.18.0 power-save fix
- compatibility with Shelly FMAC 3.7.0
- limits of what can currently be established about internal WF200 behavior

The primary Shelly host firmware target is:

```text
20240619-130912/v2.2.4@ee290818
```

The stock WLAN components in this release are:

```text
FMAC:
3.7.0

WF200 firmware:
3.16.1
```

The project has additionally tested:

```text
WF200 3.18.0
```

with the unchanged Shelly FMAC 3.7.0 host driver.

---

# 1. Host and Radio Are Separate Firmware Layers

The Shelly TRV Gen1 WLAN subsystem contains two important software layers.

The EFM32GG11 host runs Shelly's application and FMAC-side control logic:

```text
EFM32GG11
    |
    +-- Shelly application
    +-- WLAN policy
    +-- Beacon Recovery
    +-- host sleep control
    +-- FMAC host driver
```

The WF200 runs its own protected firmware:

```text
WF200
    |
    +-- radio operation
    +-- beacon processing
    +-- power-save implementation
    +-- WLAN protocol handling
    +-- lower-level timing
```

Communication between the two layers occurs through the WF200 host interface.

This distinction is important throughout the battery investigation.

A host command requesting power save does not by itself prove that the WF200 physically entered the intended low-power state.

Likewise, a radio-side problem does not automatically imply that the EFM32GG11 host remained awake.

---

# 2. WLAN Firmware Evolution

The investigated Shelly firmware generations use different combinations of FMAC and WF200 firmware.

| Shelly firmware | FMAC | WF200 firmware |
|---|---:|---:|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |
| experimental 2.2.4 | 3.7.0 | 3.18.0 |

This means WLAN behavior cannot be attributed only to changes in Shelly's application code.

Between firmware generations, both:

```text
host-side FMAC
```

and:

```text
WF200 radio firmware
```

can change.

---

# 3. Why This Matters for Historical Battery Drain

Battery-drain behavior has been observed on more than one Shelly firmware generation.

The relevant WLAN stack also changed over time.

For example:

```text
2.1.0
FMAC 3.3.2
WF200 3.12.2

        ↓

2.1.8
FMAC 3.4.1
WF200 3.14.0

        ↓

2.2.4
FMAC 3.7.0
WF200 3.16.1
```

Therefore a battery-runtime change between Shelly firmware releases can potentially involve:

- Shelly application behavior
- FMAC behavior
- WF200 firmware behavior
- interaction between those layers

The project does not currently attribute the historical drain to one WLAN firmware component alone.

---

# 4. WF200 Power-Save Control

During normal connected operation, the Shelly host configures WF200 power-management behavior.

Firmware logs and native control-flow reconstruction show several host-visible PM states.

The normal connected Fast Power Save configuration is commonly associated with:

```text
PM state 3
```

while Beacon Recovery temporarily moves the WLAN configuration through:

```text
PM state 1
```

before restoring the connected power-save policy.

A simplified Recovery sequence is:

```text
connected Fast Power Save
        |
        v
Beacon Recovery
        |
        v
PM state 1
        |
        | approximately 5 serviced seconds
        v
restore policy
        |
        v
PM state 3
```

These state numbers describe the host-visible policy/control path.

They should not be treated as direct measurements of physical radio sleep residency.

---

# 5. Desired Beacon Skip

The host also configures a desired beacon-skip value according to RSSI.

For firmware 2.2.4, the reconstructed mapping is:

```text
RSSI >= -69 dBm
    desired skip = 20

RSSI -70 .. -79 dBm
    desired skip = 15

RSSI < -79 dBm
    desired skip = 10
```

This is a requested WLAN power-save parameter.

It must not be confused with:

```text
real_beacon_skip
```

which is a host-calculated estimator derived from WF200 beacon statistics.

The two values have different origins and semantics.

---

# 6. `real_beacon_skip` Is Not a WF200 Sleep Readback

Firmware 2.2.4 obtains cumulative WF200 beacon statistics and calculates approximately:

```text
delta = current_received_beacons
      - previous_received_beacons

real_beacon_skip = uint8_t(600 / delta)
```

This value is later used by host Beacon Recovery logic.

Despite the name:

```text
real_beacon_skip
```

is not known to be:

- the actual programmed WF200 skip value
- a direct radio sleep-state readback
- a physical beacon-skip measurement
- a direct measure of WF200 sleep residency

It is a host-derived value based on the received-beacon counter.

This distinction is important when interpreting `/stats`.

---

# 7. WF200 Statistics Command

The analyzed host path requests WF200 statistics using command:

```text
0x66
```

The returned data includes values corresponding to:

- received beacon count
- missed beacon count
- TBTT-related timing information

The known `real_beacon_skip` calculation uses the cumulative received-beacon counter.

The existence of other statistics in the response does not mean they participate in the known Recovery calculation.

---

# 8. Beacon Recovery Is Host Logic

The characteristic runtime message:

```text
minutes_tick: Beacon skip error! Attempt recovery
```

originates from the Shelly host firmware.

The decision is based on the host-side cached estimator and associated control flow.

The known 2.2.4 defects include:

```text
C1a
signed interpretation

C1b
measurement-window validity

C2
stale control-evidence reuse
```

These are host-side defects.

They should not be described as defects inside WF200 firmware.

---

# 9. Host Recovery Does Not Prove a WF200 Error

The phrase:

```text
Beacon skip error
```

can easily be interpreted as though the WF200 explicitly reported a beacon-skip fault.

The reconstructed path does not support that interpretation.

The host derives a value from cumulative beacon statistics and decides whether to enter Recovery.

Therefore:

```text
Beacon Recovery
```

does not by itself establish:

```text
WF200 reported a power-save error
```

or:

```text
WF200 failed to sleep
```

or:

```text
the radio missed the number of beacons implied by
the diagnostic name
```

The message reflects Shelly's interpretation of host-side statistics.

---

# 10. WF200 `PS_MODE_ERROR`

The WF200 interface also contains a separate indication referred to here as:

```text
PS_MODE_ERROR
```

This is distinct from Shelly's Beacon Recovery decision.

Firmware 2.2.4 contains host handling that can log information associated with this indication.

Four reason values were identified:

```text
0
1
2
3
```

The known interpretation is approximately:

```text
Reason 0:
PS-Poll timeout
    -> Fast Power Save

Reason 1:
U-APSD timeout
    -> Fast Power Save

Reason 2:
buffered unicast persists for more than 8 beacons
    -> Fast Power Save

Reason 3:
unstable beacon timing
    -> beacon-window compensation
```

These conditions belong to a different diagnostic/control path than the host `real_beacon_skip` calculation.

---

# 11. Firmware 2.1.0 and D3

The older 2.1.0 host firmware does not contain the same D3 handling path found in 2.2.4.

This does not mean that the underlying WF200 can never produce the corresponding indication.

It means the investigated 2.1.0 host firmware does not expose the same handler behavior.

This is another example of why host-visible diagnostics must not be assumed to represent the complete internal radio state.

---

# 12. D3 Observer

A dedicated experimental firmware variant was built to observe the D3 / `PS_MODE_ERROR` path without changing normal Beacon Recovery behavior.

The observer records:

```text
D3_total

header_only

malformed

reason0
reason1
reason2
reason3

reason_other

unexpected_longer

first snapshots

last snapshots

WF200 version / driver state
```

The purpose was to answer a specific question:

> Are the recurring Shelly Beacon Recovery events accompanied by known WF200 `PS_MODE_ERROR` indications?

---

# 13. D3 Runtime Result

A long-running D3 observer test on physical hardware produced approximately:

```text
uptime:
63.9 hours

Beacon Recovery counter:
3835

D3_total:
0
```

The host therefore executed thousands of Beacon Recovery events without the observer recording a D3 `PS_MODE_ERROR`.

This establishes that:

> The known WF200 `PS_MODE_ERROR` indication is not required for the recurring host Beacon Recovery behavior observed on this device.

---

# 14. What the D3 Result Does Not Prove

The D3 result must not be overinterpreted.

It does not establish that:

```text
WF200 always entered sleep correctly
```

or:

```text
WF200 had no internal power-management problem
```

or:

```text
the radio consumed normal current
```

or:

```text
all possible WF200 error states are represented by D3
```

The observer monitors one known host-visible indication.

Internal radio behavior that does not produce this indication remains outside the observer's visibility.

---

# 15. D3 and Beacon Recovery Are Independent Evidence

The experiment provides a useful separation:

```text
Shelly host:
Beacon Recovery = thousands

WF200 D3 observer:
PS_MODE_ERROR = zero
```

Therefore the two mechanisms should not be treated as synonymous.

The host can enter its Beacon Recovery path without receiving the known D3 error indication.

This is consistent with the reverse engineering of the host Recovery decision, which is driven by the host-derived beacon estimator.

---

# 16. Limits of WF200 Reverse Engineering

The Shelly host application can be analyzed directly because its ARM firmware is available inside the TRV update image.

The protected WF200 firmware is a different problem.

The project can inspect:

- firmware images distributed as WF200 SEC payloads
- version information
- host commands
- host-visible events
- public interface behavior
- runtime interaction
- release information
- binary placement and relocation requirements

The project does not currently have a complete internal reverse engineering of the WF200 firmware itself.

Therefore statements such as:

```text
WF200 remains awake because internal function X fails
```

cannot currently be made from direct internal radio control-flow evidence.

---

# 17. Why the WF200 Version Still Matters

Lack of full internal WF200 reverse engineering does not make radio firmware irrelevant.

The WF200 firmware directly implements radio-side power-save behavior.

A firmware release that changes that implementation can therefore materially change battery behavior even when the Shelly host application remains unchanged.

This is especially relevant when the vendor documents a fix in the same functional area under investigation.

---

# 18. WF200 3.18.0

Silicon Labs released WF200 firmware:

```text
3.18.0
```

on:

```text
2026-10-07
```

The release information contains a particularly relevant fix:

```text
[LMAC] Fixed an error that was preventing the device
from sleeping after a power-save mode change
```

This directly concerns the class of behavior being investigated in the TRV.

It is therefore a strong reason to test the newer radio firmware.

It is not proof that the documented bug is the Shelly TRV Gen1 battery-drain root cause.

---

# 19. Why the 3.18.0 Fix Is Interesting

The Shelly TRV repeatedly changes WLAN power-save configuration.

Examples include:

```text
association
connected PM setup
Beacon Recovery
temporary active state
return to Fast Power Save
manual DTIM behavior
other PM transitions
```

The 3.18.0 release note specifically describes failure to sleep:

```text
after a power-save mode change
```

That makes the fix technically relevant to the TRV workload.

The possible relationship is:

```text
host changes WF200 PM state
        |
        v
radio should enter new sleep behavior
        |
        v
older radio firmware may fail in some condition
```

But without internal radio evidence or a controlled reproduction of the vendor bug, this remains a relevant hypothesis rather than a demonstrated causal match.

---

# 20. Official WF200 3.18.0 SEC Image

The experimental integration uses the official Silicon Labs WF200 3.18.0 SEC image:

```text
wfm_wf200_C0.sec
```

Size:

```text
312,400 bytes
```

SHA-256:

```text
886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9
```

The exact image identity is retained so that the experimental integration can be reproduced and independently verified.

---

# 21. Stock WF200 3.16.1 Placement

In stock Shelly firmware 2.2.4, the protected WF200 firmware is embedded inside the application image.

The stock radio payload belongs to the normal firmware construction and is loaded into the WF200 during initialization.

Replacing it is therefore not equivalent to simply changing a version string.

The embedded payload geometry and surrounding host application data must remain valid.

---

# 22. Why 3.18.0 Required Relocation

The WF200 3.18.0 SEC image is larger than the stock embedded 3.16.1 payload.

It cannot simply overwrite the old region without affecting following application data.

The experimental integration therefore relocates the radio payload.

The relevant relocation is:

```text
old SEC offset:
0x4C050

new SEC offset:
0x4C450

shift:
+0x400
```

The corresponding runtime destination remains:

```text
[0x1003D0, 0x1007D8)
```

The loader/reset-copy relationship must therefore be preserved while the embedded source payload moves inside the application image.

---

# 23. Relocation Fixups

Moving the SEC payload requires updating every qualified reference to the relocated data.

The final 3.18.0 integration contains:

```text
54 relocation fixups
```

associated with the radio payload relocation.

Qualification verified:

- relocated SEC geometry
- all qualified fixups
- loader boundaries
- reset-copy boundaries
- destination geometry
- surrounding application data
- second PROGRAM preservation

This is necessary because one missed pointer or size assumption could create a firmware image that appears structurally valid but fails during radio initialization.

---

# 24. Host FMAC Was Not Replaced

The experiment deliberately retains Shelly's stock:

```text
FMAC 3.7.0
```

Only the protected WF200 firmware is updated to:

```text
3.18.0
```

The resulting combination is therefore:

```text
Shelly host firmware 2.2.4
        |
        +-- FMAC 3.7.0
        |
        +-- WF200 3.18.0
```

This is important because the experiment tests whether the newer radio firmware can operate with the existing Shelly host driver.

---

# 25. Hardware Compatibility Result

The experimental combination successfully initialized on a physical Shelly TRV Gen1.

Runtime logs showed:

```text
FMAC 3.7.0
WF200 3.18.0
```

followed by successful:

- WLAN initialization
- scanning
- association
- DHCP
- cloud connection
- power-save configuration
- normal thermostat operation

This provides physical evidence that:

> Shelly FMAC 3.7.0 can operate with the tested official WF200 3.18.0 image under the exercised TRV conditions.

This is stronger than a purely static compatibility assumption.

---

# 26. Initial 3.18.0 Runtime Behavior

An early standalone WF200 3.18.0 experiment successfully completed OTA installation and cold reboot.

The radio initialized as:

```text
FMAC 3.7.0
WF200 3.18.0
```

and normal WLAN/cloud operation remained available.

Initial runtime statistics showed the expected transition toward connected power-save behavior.

This established the basic feasibility of the radio update before it was incorporated into the later combined firmware.

---

# 27. C-C + WF200 3.18.0

WF200 3.18.0 was later combined with the C-C Beacon Recovery correction.

This is useful because C-C removes the known stale host Recovery loop.

The resulting configuration still shows fresh qualifying Beacon Recovery events.

Observed rates have been in approximately the same order as:

```text
~30 events/hour
```

depending on the test device and period.

This means:

> Updating the WF200 to 3.18.0 does not by itself eliminate every fresh host Beacon Recovery trigger.

That does not establish whether the newer radio firmware improves sleep behavior or battery consumption in other ways.

---

# 28. A1 + C-C + WF200 3.18.0

The current integrated experimental platform combines:

```text
A1
    host PM lifecycle correction

C-C
    Beacon Recovery validity correction

WF200 3.18.0
    newer radio firmware
```

The controlled-test artifact is:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

The combination has successfully booted and operated on physical hardware.

This allows host and radio corrections to be tested together while retaining the original Shelly FMAC generation.

---

# 29. Integrated Artifact Identity

GBL size:

```text
1,123,380 bytes
```

GBL SHA-256:

```text
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379
```

Stored/calculated END CRC32:

```text
F01262BC
```

Whole-file CRC32 residue:

```text
2144DF1C
```

Application size:

```text
1,066,544 bytes
```

Application SHA-256:

```text
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The extracted WF200 payload in the final GBL was verified byte-for-byte against the official 3.18.0 SEC image.

---

# 30. Fresh Recovery With 3.18.0

The integrated A1+C-C+WF200 3.18.0 test device continued to produce fresh Beacon Recovery events.

Representative measurements were approximately:

```text
~17.7 min:
9 Beacon Recovery events

~7.94 h:
217 events

~24 h:
660 events

~32.44 h:
909 events
```

The longer periods correspond to roughly:

```text
27–28 events/hour
```

The known C2 stale-evidence loop has already been removed by C-C.

These remaining events therefore require a fresh qualifying host measurement.

---

# 31. Good RSSI Does Not Eliminate Fresh Recovery

Fresh Recovery continued even during periods of good WLAN signal.

One representative period showed approximately:

```text
RSSI:
-56 dBm
```

while Recovery continued.

Therefore weak RSSI is not a required condition for the remaining fresh trigger.

This matches earlier observations from stock firmware.

---

# 32. Mesh/Band Steering Is Not Required

A controlled test disabled FRITZ!Box Mesh/Band Steering while leaving the experimental firmware otherwise unchanged.

Beacon Recovery continued.

This establishes that the tested Mesh/Band-Steering behavior is not required for the fresh Recovery events seen on that device.

It does not rule out all AP-side timing or roaming influences.

---

# 33. Recovery Frequency Is Not a Direct Sleep Measurement

An important runtime observation is that similar Recovery frequency does not necessarily correspond to similar short-term battery-voltage decline.

During one period with the valve closed, the integrated test device showed only a small voltage change while Recovery continued at roughly the same rate.

This reinforces an important distinction:

```text
Recovery frequency
    !=
direct radio awake time
```

and:

```text
Recovery frequency
    !=
direct battery-energy measurement
```

A Recovery event creates known host/radio activity.

Its total energy impact depends on what the radio and host actually do before, during and after the transition.

---

# 34. WF200 Sleep Cannot Be Inferred From Host Logs Alone

Host logs can show:

```text
PS state 1
PS state 3
desired skip
real_beacon_skip
Beacon Recovery
D3
```

but none of these individually provides a complete physical radio sleep trace.

For example:

```text
host requests state 3
```

does not prove:

```text
WF200 remained asleep for the expected duration
```

The 3.18.0 release note itself demonstrates why this distinction matters: a device can receive a power-save mode change while an internal radio-side defect prevents the expected sleeping behavior.

---

# 35. Host Sleep Is Also Separate

The EFM32GG11 host has its own sleep architecture:

```text
B2
B3
EM1
EM2
EM3
PA8
WFI
```

A radio-side power-save problem and a host-side sleep problem can therefore coexist.

Possible examples include:

```text
host correctly reaches EM2
WF200 remains unexpectedly active
```

or:

```text
WF200 correctly enters power save
host remains restricted to EM1
```

or:

```text
PA8 remains asserted
host does not execute WFI
```

Battery investigation must therefore consider both processors.

---

# 36. PA8 Connects the Two Layers

PA8 provides one important interaction between the WLAN side and host sleep.

The EFM32GG11 checks the WLAN notification signal before executing WFI.

If PA8 is HIGH:

```text
host sleep is vetoed
```

This means radio-side activity can indirectly prevent host low-power entry even when the host blocker selector would otherwise permit EM2.

The exact duration and runtime frequency of this condition are not yet established.

---

# 37. B2 Is Not a WF200 State

The host B2 reference counter must also not be confused with radio state.

B2 represents software ownership of an EFM32 sleep restriction.

Conceptually:

```text
B2 != 0
    host must remain at EM1 or shallower
```

It does not directly mean:

```text
WF200 awake
```

Likewise:

```text
B2 = 0
```

does not prove:

```text
WF200 asleep
```

The later-discovered B2 concurrency defect is therefore a host-side problem separate from WF200 firmware.

---

# 38. Why 3.18.0 Is Not Treated as a Root-Cause Proof

The release note is unusually relevant:

```text
device not sleeping after a power-save mode change
```

but matching terminology is not enough to establish causality.

To claim that the vendor fix is the historical TRV root cause, the project would need stronger evidence such as:

- reproduction of the exact older WF200 failure
- disappearance of that failure under 3.18.0
- controlled physical sleep or current measurements
- a clear relationship to the historical drain
- exclusion of independent host-side causes

Those conditions have not yet been met.

The correct interpretation is:

> WF200 3.18.0 contains a vendor-documented fix in a directly relevant power-save area and is therefore an important experimental variable.

---

# 39. Why 3.18.0 Still Belongs in the Corrected Platform

Even without root-cause proof, there is a practical reason to include the newer radio firmware in the experimental corrected platform.

The project has already identified several host-side defects.

Testing those host corrections against a radio firmware that contains a later vendor sleep fix reduces the chance of evaluating the corrected host against a known older radio-side defect class.

The resulting platform is:

```text
correct known host defects
        +
test newer radio PM implementation
```

rather than assuming either side alone explains the entire problem.

---

# 40. Current Experimental Model

The current WLAN power-management investigation can be represented as:

```text
Shelly host
    |
    +-- Beacon estimator
    |      |
    |      +-- C1a
    |      +-- C1b
    |      +-- C2
    |      |
    |      +-- C-C correction
    |
    +-- PM lifecycle
    |      |
    |      +-- G01/G02/G03/G05/G06/G18/G19
    |      |
    |      +-- A1 correction
    |
    +-- host sleep
           |
           +-- B2 race
           +-- B3 / EM2 policy
           +-- PA8 veto

WF200
    |
    +-- radio PM implementation
    |
    +-- D3 / PS_MODE_ERROR
    |
    +-- firmware 3.16.1
    |
    +-- firmware 3.18.0
           |
           +-- vendor sleep-related fix
```

No one branch currently explains every observed battery symptom.

---

# 41. What Has Been Established

The current evidence supports the following conclusions.

### Shelly changed both FMAC and WF200 firmware across releases

The WLAN stack evolved significantly between 2.1.0 and 2.2.4.

### Beacon Recovery is host logic

The known Recovery decision is based on a host-derived estimator.

### `real_beacon_skip` is not direct WF200 sleep telemetry

It is derived from cumulative received-beacon statistics.

### D3 is a separate WF200 error indication

It is not the same mechanism as Shelly Beacon Recovery.

### D3 is not required for recurring Recovery

Thousands of Recovery events were observed with:

```text
D3_total = 0
```

on the D3 observer device.

### WF200 3.18.0 contains a relevant vendor fix

The release notes describe a failure that could prevent sleep after a power-save mode change.

### FMAC 3.7.0 and WF200 3.18.0 operate together on tested hardware

The combination successfully initialized and maintained normal TRV connectivity and operation.

### WF200 3.18.0 does not eliminate all fresh Beacon Recovery

Fresh host Recovery events remain observable in C-C-based 3.18.0 configurations.

---

# 42. What Has Not Been Established

The project does not currently claim:

- that WF200 3.16.1 is the sole cause of battery drain
- that WF200 3.18.0 fixes the complete battery problem
- that the Silicon Labs 3.18.0 fix is the exact historical TRV failure
- that every Beacon Recovery corresponds to a radio sleep failure
- that every radio sleep failure produces D3
- that D3 covers every internal WF200 PM failure
- that `real_beacon_skip` measures physical radio sleep
- that desired beacon skip equals actual physical skip
- that FMAC 3.7.0 is officially supported by Silicon Labs with every later WF200 firmware solely because the tested combination works
- that the internal WF200 3.16.1 or 3.18.0 control flow has been completely reverse engineered
- that current host logs provide direct radio sleep residency
- that the quantitative battery improvement from WF200 3.18.0 is known

---

# 43. Remaining Questions

Important open WF200 questions include:

1. Does WF200 3.16.1 enter a persistent awake state after specific PM transitions?

2. If so, does that state produce D3 or remain silent?

3. Does WF200 3.18.0 eliminate such a state?

4. What exactly causes the remaining fresh host Beacon Recovery measurements?

5. Does PA8 remain asserted during any radio-side abnormal state?

6. Can host-side B2 corruption and radio-side PM failure occur independently?

7. How much time does the WF200 physically spend in low-power operation?

8. What is the actual energy cost of a Beacon Recovery sequence?

9. Does the newer radio firmware improve long-term battery endurance after host-side defects are corrected?

These questions require runtime evidence beyond static host reverse engineering.

---

# 44. Current Test Strategy

The current strategy separates host and radio variables as much as practical.

Useful configurations include:

```text
Stock host
+
WF200 3.16.1
```

for the original reference,

```text
C-C
+
WF200 3.16.1
```

for host Beacon Recovery correction without changing radio firmware,

```text
C-C
+
WF200 3.18.0
```

for host Recovery correction with the newer radio firmware,

and:

```text
A1
+
C-C
+
WF200 3.18.0
```

for the current integrated corrected platform.

This makes it possible to distinguish changes caused by host corrections from changes associated with the radio firmware update.

---

# 45. Current Conclusions

The WF200 is an important but separate part of the Shelly TRV Gen1 battery-drain investigation.

The strongest current conclusions are:

### The radio firmware changed substantially over the lifetime of the TRV

The investigated Shelly releases use WF200 firmware from 3.12.2 through 3.16.1.

### Shelly's Beacon Recovery is not a direct WF200 error report

It is a host-side decision based on host-processed beacon statistics.

### D3 does not explain the recurring Recovery loop

A physical D3 observer recorded thousands of Recovery events without a D3 event.

### WF200 3.18.0 is technically relevant

Silicon Labs documents a fix for a device failing to sleep after a power-save mode change.

### The newer radio firmware can operate with Shelly FMAC 3.7.0

This has been demonstrated on physical TRV hardware.

### Fresh Recovery remains

WF200 3.18.0 does not eliminate every fresh host Recovery trigger under the tested conditions.

### Radio sleep remains partly opaque

Without direct physical power measurement or complete internal WF200 reverse engineering, host-visible state cannot be treated as proof of actual radio sleep residency.

### The corrected experimental platform therefore addresses both sides

The current A1+C-C+WF200 3.18.0 platform combines demonstrated host corrections with the newer radio-side PM implementation without claiming that either side alone is the complete historical root cause.

---

# Related Documents

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle and A1:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

General WLAN power management:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Beacon counter:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Calculated beacon skip:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Experimental patches:

[`../patch/README.md`](../patch/README.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Method

This analysis combines:

- native host-firmware reverse engineering
- WF200 host-interface reconstruction
- firmware-version comparison
- radio-payload extraction
- binary relocation analysis
- deterministic firmware reconstruction
- D3 runtime observation
- Beacon Recovery runtime statistics
- controlled WF200 firmware replacement
- physical OTA testing
- long-term battery and WLAN observation

The project distinguishes host-visible radio behavior from conclusions about internal WF200 implementation.

Where internal radio behavior cannot be observed directly, the limitation is stated rather than inferred from host logs.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

Shelly and Silicon Labs product names and trademarks are used only to identify the hardware and firmware being studied.

Experimental firmware should only be used on devices where recovery or reflashing is possible.
````