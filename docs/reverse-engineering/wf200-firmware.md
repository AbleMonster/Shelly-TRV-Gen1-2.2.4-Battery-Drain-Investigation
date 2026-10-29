# WF200 Firmware and Power-Save Behavior

## Shelly TRV Gen1

## Scope

This document describes the WF200 WLAN firmware used by the Shelly TRV Gen1, its evolution across the investigated Shelly firmware releases, and its relationship to the host-side battery-drain investigation.

The main topics are:

- Shelly FMAC and WF200 firmware versions
- separation between host and radio power management
- WF200 power-save modes used by the TRV
- `PS_MODE_ERROR`
- the historical D3 observer
- the relationship between D3 and Beacon Recovery
- the experimental WF200 3.18.0 integration
- the Silicon Labs 3.18.0 power-save fix
- compatibility with Shelly FMAC 3.7.0
- SEC relocation and qualification
- the current B2.1/B2.1_OBS integration
- the limits of what can currently be established about internal WF200 behavior

The primary Shelly host firmware target is:

```text id="brd3tt"
20240619-130912/v2.2.4@ee290818
```

The stock WLAN components in this release are:

```text id="mfszzh"
FMAC:
3.7.0

WF200 firmware:
3.16.1
```

The project additionally integrates the official:

```text id="3g3gv9"
WF200 3.18.0
```

radio firmware with the unchanged Shelly FMAC 3.7.0 host driver.

The current research position remains conservative:

> WF200 3.18.0 contains an official Silicon Labs fix in a directly relevant power-save area and has been demonstrated to operate on Shelly TRV Gen1 hardware, but it has not been proven to be the historical battery-drain root-cause fix.

---

# 1. Host and Radio Are Separate Firmware Layers

The Shelly TRV Gen1 WLAN subsystem contains two important software layers.

The EFM32GG11 host runs Shelly's application and FMAC-side control logic:

```text id="5b4gpu"
EFM32GG11
    |
    +-- Shelly application
    +-- WLAN policy
    +-- Beacon Recovery
    +-- host sleep control
    +-- FMAC host driver
```

The WF200 runs its own protected firmware:

```text id="mp0mwu"
WF200
    |
    +-- radio operation
    +-- beacon processing
    +-- power-save implementation
    +-- WLAN protocol handling
    +-- lower-level timing
```

Communication between these layers occurs through the WF200 host interface.

This distinction is fundamental to the battery investigation.

A host request for power save does not prove that WF200 physically entered the intended low-power state.

Likewise, a radio-side problem does not automatically imply that the EFM32GG11 host remained awake.

---

# 2. WLAN Firmware Evolution

The investigated Shelly firmware generations use different FMAC and WF200 combinations.

| Shelly firmware | FMAC | WF200 firmware |
|---|---:|---:|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |
| experimental 2.2.4 | 3.7.0 | 3.18.0 |

Therefore WLAN behavior cannot be attributed only to Shelly application changes.

Across releases, both:

```text id="kk2k4d"
host-side FMAC
```

and:

```text id="h5ew4n"
WF200 radio firmware
```

change.

---

# 3. Historical Battery-Drain Relevance

Battery drain has been observed across more than one Shelly firmware generation.

At the same time, the WLAN stack evolved:

```text id="txqhs6"
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

A runtime difference between Shelly releases can therefore involve:

- Shelly application behavior
- FMAC behavior
- WF200 firmware behavior
- interaction between these layers

The project does not currently attribute historical battery drain to one WLAN firmware component alone.

---

# 4. WF200 Power-Save Control

During normal connected operation, the Shelly host configures WF200 power-management behavior.

The normal connected Fast Power Save configuration is commonly associated with Shelly:

```text id="3v3wqf"
PM state 3
```

while Beacon Recovery temporarily moves the WLAN configuration through:

```text id="fl4o86"
PM state 1
```

before restoring connected power saving.

A simplified sequence is:

```text id="hrr2hu"
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

These are host-visible application/control states.

They are not direct physical radio sleep measurements.

---

# 5. Desired Beacon Skip

For firmware 2.2.4, the reconstructed RSSI policy is:

```text id="qvo9pq"
RSSI >= -69 dBm
    desired skip = 20

RSSI -70 .. -79 dBm
    desired skip = 15

RSSI < -79 dBm
    desired skip = 10
```

This is a requested WLAN power-save parameter.

It must not be confused with:

```text id="73o41t"
real_beacon_skip
```

which is calculated by the host from WF200 statistics.

---

# 6. `real_beacon_skip` Is Not WF200 Sleep Readback

Firmware 2.2.4 obtains cumulative beacon statistics and calculates approximately:

```text id="o06ebv"
delta = current_received_beacons
      - previous_received_beacons

real_beacon_skip = uint8_t(600 / delta)
```

Despite its name, `real_beacon_skip` is not known to be:

- the actual programmed WF200 listen interval
- a direct radio sleep-state readback
- a physical beacon-skip measurement
- a direct measure of WF200 sleep residency

It is a host-derived estimator.

This distinction is important when interpreting `/stats`.

---

# 7. WF200 Statistics Command

The analyzed host path obtains WF200 statistics using:

```text id="0vhxom"
0x66
```

Returned data includes information corresponding to:

- received beacon count
- missed beacon count
- TBTT-related timing information

The known `real_beacon_skip` calculation uses the cumulative received-beacon counter.

The existence of other fields in the response does not imply they participate in the known Recovery calculation.

---

# 8. Beacon Recovery Is Host Logic

The characteristic message:

```text id="gsbo9n"
minutes_tick: Beacon skip error! Attempt recovery
```

originates in Shelly host firmware.

The Recovery decision is based on the host-side estimator and its cached measurement state.

Three demonstrated host-side validity defects are:

```text id="l87qkp"
C1a
signed interpretation

C1b
measurement-window validity

C2
stale control-evidence reuse
```

These are Shelly host defects.

They must not be attributed to WF200 firmware.

---

# 9. Host Recovery Does Not Prove a WF200 Error

The phrase:

```text id="9yom1j"
Beacon skip error
```

can be misread as though WF200 directly reported an error.

The reconstructed control flow does not support that interpretation.

Therefore:

```text id="j7tcs5"
Beacon Recovery
```

does not by itself establish:

```text id="i9yq0j"
WF200 reported a PM error
```

or:

```text id="ujqprx"
WF200 failed to sleep
```

or:

```text id="u8ij3f"
WF200 reported the number of skipped
beacons implied by the diagnostic name
```

The message reflects Shelly's host-side interpretation of beacon statistics.

---

# 10. WF200 `PS_MODE_ERROR`

WF200 exposes a separate indication referred to here as:

```text id="yd1j9w"
PS_MODE_ERROR
```

Firmware 2.2.4 contains host-side handling for this indication.

Four reason values were identified:

```text id="7rt3ur"
0
1
2
3
```

The known interpretation is approximately:

```text id="y32dku"
Reason 0:
PS-Poll timeout
    -> Fast Power Save

Reason 1:
U-APSD timeout
    -> Fast Power Save

Reason 2:
buffered unicast persists across consecutive beacons
    -> Fast Power Save

Reason 3:
unstable beacon timing
    -> beacon-window compensation
```

This is a different path from Shelly's `real_beacon_skip` estimator.

---

# 11. Firmware 2.1.0 and D3

The investigated 2.1.0 host firmware does not expose the same D3 handling behavior found in 2.2.4.

This does not mean the underlying WF200 generation could never produce a corresponding condition.

It means the analyzed host firmware does not expose the same handler path.

Host-visible diagnostics therefore must not be treated as a complete representation of internal radio behavior.

---

# 12. Historical D3 Observer

A dedicated experimental firmware variant was built to observe the D3 / `PS_MODE_ERROR` path without changing normal Beacon Recovery behavior.

The observer recorded categories including:

```text id="1cbn1d"
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

The specific question was:

> Are recurring Shelly Beacon Recovery events accompanied by the known WF200 `PS_MODE_ERROR` indication?

---

# 13. D3 Runtime Result

A long-running hardware observation produced approximately:

```text id="nvqeq7"
uptime:
~63.9 hours

Beacon Recovery:
3835 events

D3_total:
0
```

Therefore thousands of Shelly Beacon Recovery events occurred without an observed D3 `PS_MODE_ERROR`.

The supported conclusion is:

> The known WF200 `PS_MODE_ERROR` indication is not required for the recurring host Beacon Recovery behavior observed in that experiment.

---

# 14. What the D3 Result Does Not Prove

The D3 result does not establish that:

```text id="xo6cb3"
WF200 always entered sleep correctly
```

or:

```text id="98ctkv"
WF200 had no internal PM problem
```

or:

```text id="51yco2"
the radio consumed normal current
```

or:

```text id="gyo2wk"
all possible internal WF200 PM failures
are represented by D3
```

The observer monitored one known host-visible error channel.

Internal behavior that does not generate this indication remains outside its visibility.

---

# 15. D3 and Beacon Recovery Are Independent Evidence

The historical experiment produced:

```text id="2h76c3"
Shelly host:
Beacon Recovery = thousands

WF200 D3 observer:
PS_MODE_ERROR = zero
```

The two mechanisms must therefore not be treated as synonymous.

This agrees with static host analysis showing that Beacon Recovery is driven by the host-derived beacon estimator.

---

# 16. Limits of WF200 Reverse Engineering

The Shelly host application can be reverse engineered directly because its ARM application firmware is contained in the TRV update image.

WF200 firmware is a different case.

The project can inspect:

- distributed SEC firmware images
- version information
- host commands
- host-visible events
- public interface behavior
- runtime interaction
- release information
- binary placement
- relocation requirements

The project does not currently have a complete internal reverse engineering of WF200 firmware.

Therefore statements such as:

```text id="vyi214"
WF200 remains awake because internal function X fails
```

cannot currently be made from direct radio-firmware control-flow evidence.

---

# 17. Why WF200 Version Still Matters

Lack of complete internal radio reverse engineering does not make WF200 firmware irrelevant.

WF200 firmware implements:

- radio-side PM behavior
- beacon processing
- protocol timing
- low-level sleep transitions
- power-save state handling

A vendor firmware release changing these mechanisms can materially affect battery behavior even if Shelly host code remains unchanged.

This becomes especially relevant when a vendor release documents a fix in the same PM area under investigation.

---

# 18. WF200 3.18.0

Silicon Labs released WF200 firmware:

```text id="i3lob7"
3.18.0
```

with a directly relevant LMAC fix describing a case where the device could fail to sleep after a power-save mode change.

This is technically relevant to the TRV because the product performs repeated WF200 PM transitions.

The correct conclusion is:

> WF200 3.18.0 contains an official Silicon Labs correction for a failure class that could prevent radio sleep after a power-save mode transition.

It is not proof that this was the historical Shelly TRV battery-drain root cause.

---

# 19. Why the 3.18.0 Fix Is Interesting

The TRV performs PM transitions during events such as:

```text id="7ixf66"
association
connected PM setup
Beacon Recovery
temporary Active mode
return to Fast Power Save
manual DTIM behavior
other PM transitions
```

The vendor fix concerns failure to sleep:

```text id="s19phs"
after a power-save mode change
```

That is a strong functional match to the investigation domain.

The possible relationship is:

```text id="wzt7tc"
host changes WF200 PM state
        |
        v
WF200 should enter new PM behavior
        |
        v
older radio firmware may fail
under some condition
```

Without direct reproduction of the vendor defect or internal radio control-flow evidence, this remains a technically relevant candidate mechanism rather than a demonstrated causal match.

---

# 20. Official WF200 3.18.0 SEC Image

The integration uses the official Silicon Labs WF200 3.18.0 SEC image:

```text id="m0fjy8"
wfm_wf200_C0.sec
```

Size:

```text id="r9n8lz"
312,400 bytes
```

SHA-256:

```text id="97f7ga"
886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9
```

The exact image identity is retained for independent verification.

---

# 21. Stock WF200 3.16.1 Placement

In stock Shelly firmware 2.2.4, the protected WF200 firmware is embedded inside the host application image.

The stock radio payload is loaded into WF200 during initialization.

Replacing it is therefore not equivalent to changing a version string.

The embedded payload geometry, references and surrounding host data must remain internally consistent.

---

# 22. Why WF200 3.18.0 Required Relocation

WF200 3.18.0 is larger than the stock embedded 3.16.1 SEC payload.

It therefore cannot overwrite the original source region without affecting subsequent application data.

The experimental integration relocates the embedded SEC image.

Relevant source offsets are approximately:

```text id="y9qlmy"
old SEC offset:
0x4C050

new SEC offset:
0x4C450

shift:
+0x400
```

The corresponding runtime destination remains:

```text id="vpnr28"
[0x1003D0, 0x1007D8)
```

The loader/reset-copy relationship must therefore remain correct even though the embedded source payload moved.

---

# 23. Relocation Fixups

Moving the SEC image required updating every qualified source reference associated with the relocated payload.

The final integration contains:

```text id="xvwk3a"
54 relocation fixups
```

Qualification verified:

- relocated SEC geometry
- all qualified relocation references
- loader boundaries
- reset-copy boundaries
- destination geometry
- surrounding application data
- second PROGRAM preservation
- byte-for-byte SEC identity after extraction

One incorrect pointer or size assumption could otherwise produce a structurally plausible image that fails during WLAN initialization.

---

# 24. Host FMAC Was Not Replaced

The experiment deliberately retains Shelly's stock:

```text id="838tp0"
FMAC 3.7.0
```

while updating only the radio firmware to:

```text id="dtbbpy"
WF200 3.18.0
```

The resulting combination is:

```text id="6xc5yv"
Shelly host firmware 2.2.4
        |
        +-- FMAC 3.7.0
        |
        +-- WF200 3.18.0
```

This isolates the radio-firmware update while preserving Shelly's existing FMAC generation.

---

# 25. Hardware Compatibility Result

The combination initialized and operated successfully on physical Shelly TRV Gen1 hardware.

Runtime behavior included:

```text id="3gn86s"
FMAC 3.7.0
WF200 3.18.0
```

followed by successful:

- WLAN initialization
- scan
- association
- DHCP
- cloud connectivity
- power-save configuration
- normal thermostat operation

This establishes:

> Shelly FMAC 3.7.0 can operate with the tested official WF200 3.18.0 SEC image under the exercised TRV conditions.

This is practical experimental interoperability.

It is not an official Silicon Labs or Shelly compatibility qualification.

---

# 26. Initial Standalone 3.18.0 Runtime

An early standalone WF200 3.18.0 experiment successfully completed OTA installation and cold reboot.

The device initialized:

```text id="6p8pd1"
FMAC 3.7.0
WF200 3.18.0
```

and retained normal WLAN/cloud operation.

This established basic feasibility before the radio update was combined with the later host corrections.

---

# 27. C-C + WF200 3.18.0

WF200 3.18.0 was later combined with the C-C Beacon Recovery correction.

C-C removes the known host-side stale-evidence recurrence.

Fresh qualifying Recovery events still occurred during some historical periods, in approximately the:

```text id="ls2n12"
~27–30 events/hour
```

range.

This establishes only that:

> WF200 3.18.0 does not automatically eliminate all fresh host-derived Beacon Recovery triggers.

It does not show whether the new radio firmware improved physical radio sleep behavior in other ways.

---

# 28. Historical A1 + C-C + WF200 3.18.0

An earlier integrated experimental platform combined:

```text id="4quh6k"
A1
+
C-C
+
WF200 3.18.0
```

The historical artifact was:

```text id="njhm9m"
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

That platform successfully booted and operated on physical hardware.

It was an important integration milestone.

It is no longer the current corrected platform because A1 was later superseded by A1R and bounded B2 serialization was added.

Historical results from this build remain valid historical evidence and must not be relabeled as A1R or B2.1.

---

# 29. Historical A1+C-C+WF200 Artifact Identity

The historical integrated artifact had:

```text id="ctfizh"
GBL size:
1,123,380 bytes
```

GBL SHA-256:

```text id="sa78x5"
d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379
```

END CRC32:

```text id="i75d9r"
F01262BC
```

Whole-file CRC32 residue:

```text id="djlmfb"
2144DF1C
```

Application size:

```text id="c2s8zd"
1,066,544 bytes
```

Application SHA-256:

```text id="vwx9ad"
0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d
```

The embedded WF200 3.18.0 SEC payload was verified byte-for-byte against the official image.

These identifiers belong to that historical A1-based build only.

---

# 30. Historical Fresh Recovery With WF200 3.18.0

The historical A1+C-C+WF200 3.18.0 test device continued to produce fresh Beacon Recovery events.

Representative historical measurements included approximately:

```text id="nd2q4m"
~17.7 min:
9 Beacon Recovery events

~7.94 h:
217 events

~24 h:
660 events

~32.44 h:
909 events
```

The longer intervals corresponded to roughly:

```text id="t4j4oj"
27–28 events/hour
```

Because C-C had already removed the stale-evidence recurrence, these events required later fresh qualifying host measurements.

They should not be interpreted as proof that WF200 3.18.0 failed to sleep.

---

# 31. Good RSSI Does Not Eliminate Fresh Recovery

Historical fresh Recovery continued even with good WLAN signal.

One representative period showed approximately:

```text id="ps8gc7"
RSSI = -56 dBm
```

while fresh Recovery continued.

Weak RSSI is therefore not required for the observed fresh trigger.

This does not exclude other AP-side timing effects.

---

# 32. Mesh/Band Steering Is Not Required

A historical controlled test disabled FRITZ!Box Mesh/Band Steering while keeping the experimental firmware otherwise unchanged.

Fresh Beacon Recovery continued.

Therefore the tested Mesh/Band-Steering behavior was not required for those Recovery events.

This does not rule out every AP-side timing, roaming or RF interaction.

---

# 33. Recovery Frequency Is Not Direct Sleep Measurement

Similar Recovery frequency does not necessarily correspond to similar short-term battery-voltage behavior.

This reinforces:

```text id="lhw1ck"
Recovery frequency
    !=
physical WF200 awake time
```

and:

```text id="cld3fc"
Recovery frequency
    !=
battery energy
```

Each Recovery creates known host/radio activity.

Its total energy impact depends on the states before, during and after the transition.

---

# 34. WF200 Sleep Cannot Be Inferred From Host Logs Alone

Host telemetry can show:

```text id="d5o5vy"
PM state 1
PM state 3
desired_beacon_skip
real_beacon_skip
Beacon Recovery
D3
PM52 completion
```

None of these individually provides a complete physical RF sleep trace.

For example:

```text id="06a3s3"
host requests state 3
```

does not prove:

```text id="5vijtn"
WF200 physically slept for the expected duration
```

The existence of the 3.18.0 vendor fix itself illustrates this distinction: a host can successfully request a PM change while an internal radio-side defect interferes with subsequent sleep behavior.

---

# 35. Host Sleep Is Separate

The EFM32GG11 host has its own low-power architecture involving:

```text id="f6pja4"
B2
B3
EM1
EM2
EM3
PA8
WFI
```

A radio-side PM defect and a host-side sleep defect may therefore exist independently.

Examples include:

```text id="h9a95r"
host reaches intended EM2
WF200 remains unexpectedly active
```

or:

```text id="nmn0ti"
WF200 enters intended power save
host remains restricted to EM1
```

or:

```text id="dkjs1g"
PA8 remains asserted
host WFI is vetoed
```

Battery analysis must therefore keep the two processors conceptually separate.

---

# 36. PA8 Connects the Two Layers

PA8 provides an important host/radio interaction.

The EFM32GG11 checks the WLAN notification signal before WFI.

If PA8 is HIGH:

```text id="wm0hrw"
host low-power entry is vetoed
```

Radio-side activity can therefore indirectly prevent host sleep even when B2/B3 selection would otherwise permit EM2.

PA8 HIGH is not automatically a defect.

It can represent legitimate pending WLAN work.

---

# 37. B2 Is Not a WF200 State

B2 represents software ownership of a host sleep restriction.

Conceptually:

```text id="jh61t3"
B2 != 0
    |
    v
host limited to EM1 or shallower
```

It does not directly mean:

```text id="iqyw95"
WF200 awake
```

Likewise:

```text id="rjxnjy"
B2 = 0
```

does not prove:

```text id="6ekcmf"
WF200 asleep
```

The demonstrated B2 race is therefore a host-side correctness defect separate from WF200 firmware.

---

# 38. B2 Serialization

Stock firmware contains a task-preemption race in shared B2 reference-counter updates.

This can produce:

```text id="z0a5mv"
phantom B2 contribution
```

or:

```text id="q7j0a6"
lost B2 contribution
```

The correction uses bounded serialization of the complete relevant B2 read-modify-write operation while preserving reference-count semantics.

This correction is included in the current B2.1 family.

It does not modify WF200 firmware behavior.

---

# 39. Why WF200 3.18.0 Is Not Root-Cause Proof

The vendor description is unusually relevant:

```text id="c6slur"
device not sleeping after a power-save mode change
```

but terminology alone does not establish causality.

A root-cause claim would require stronger evidence such as:

- reproduction of the relevant 3.16.1 radio-side failure
- disappearance of that failure under 3.18.0
- controlled physical current or sleep measurement
- direct correlation with historical drain
- exclusion of independent host-side causes

Those conditions have not been met.

The correct interpretation is:

> WF200 3.18.0 contains a vendor-documented fix in a directly relevant PM area and is therefore an important component of the corrected experimental platform.

---

# 40. Why 3.18.0 Remains in the Corrected Platform

Even without root-cause proof, including 3.18.0 is technically justified.

The project has already demonstrated multiple host-side defects.

Testing those corrected host paths against a newer radio firmware that contains a vendor PM/sleep correction reduces the risk of evaluating the host fixes against an older known radio-side defect class.

The strategy is therefore:

```text id="y69cfm"
correct demonstrated host defects
        +
use newer vendor radio PM implementation
```

without claiming either side alone explains the historical problem.

---

# 41. A1R

The original A1 host PM correction was later found to introduce an experimental regression in verified temporary `request1` override paths.

The corrected lifecycle implementation is:

```text id="3tyzmb"
A1R
```

A1R retains the A1 lifecycle corrections while correcting that experimental regression.

It passed:

```text id="7mo58q"
151 / 151 Thumb behavior tests
```

together with broader retained-state and interaction qualification.

This distinction matters because historical A1+WF200 3.18.0 runtime measurements must remain labeled as A1 results.

---

# 42. B2.1

The current observer-free corrected integrated baseline is:

```text id="mc8c2d"
B2.1
```

containing:

```text id="g2c8y7"
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

From the WF200 perspective, the important component is still the same official 3.18.0 SEC image integrated with Shelly FMAC 3.7.0.

---

# 43. B2.1 Artifact Identity

The B2.1 experimental artifact is:

```text id="19wn7j"
final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.gbl
```

Application:

```text id="l6jxy5"
size:
1,066,776 bytes

SHA-256:
31ddd06a0229fee0b0b58dcbbd28ced1e4fbab0b6dc218c76c9d93673f4961e0

CRC:
24702EBF
```

GBL:

```text id="q44ihn"
size:
1,123,612 bytes

SHA-256:
5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9

END CRC:
F5429B7F

CRC residue:
2144DF1C
```

This is the corrected observer-free B2.1 artifact.

---

# 44. PM52→cmd66 Observer

The current diagnostic observer records the relationship between host PM commands and the existing statistics path.

It records:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing periodic cmd66 requests/results
- fresh estimator operands
- connection epochs
- a compact event ring
- first-fault freeze state

It sends no additional WF200 request.

It adds no:

```text id="cp5f9s"
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
```

This is particularly important when investigating radio PM behavior because diagnostic instrumentation must not itself create additional WF200 transactions.

---

# 45. B2.1_OBS

The current long-term hardware diagnostic build is:

```text id="5im0ip"
B2.1_OBS
```

defined as:

```text id="7pxlz1"
B2.1
+
PM52 -> cmd66 observer
```

Its software qualification included:

```text id="43ijbb"
A1R:
151 / 151

observer/readout:
356 / 356

B2:
2060 + mixed/preemption qualification

plus:
C-C qualification
MQTT qualification
decoder regressions
deterministic construction
independent GBL verification
zero unexplained changes
```

The build disposition is:

```text id="jo8nzb"
B2.1_OBS RELEASE-CANDIDATE GO
```

This means qualified for controlled hardware observation.

It does not mean production release or battery-drain root-cause proof.

---

# 46. B2.1_OBS Artifact Identity

Artifact:

```text id="0ip94q"
builds/firmware/B2.1_OBS/SHTRV-01_2.2.4_B2.1_OBS_EXPERIMENTAL.gbl
```

Application:

```text id="lmp59u"
size:
1,069,300 bytes

SHA-256:
65e17c4c04bdde23f545ebdb3283d71eef746e8dafba97ed9f6e451b6310c215

CRC:
EEE8DD82
```

GBL:

```text id="sooplj"
size:
1,126,136 bytes

SHA-256:
7d7063d81372063dfe0d629d26e614f7dd2ed448b0e65a393e866c79025eac7a

END CRC:
12247888

CRC residue:
2144DF1C
```

The native Shelly firmware identity remains 2.2.4.

The research identity is:

```text id="it1gxr"
research_build: B2.1_OBS
```

---

# 47. Current Hardware Population

The active long-term test population is:

```text id="9ncuct"
.77  -> B2.1_OBS
.88  -> B2.1_OBS
.11  -> B2.1_OBS
.71  -> B2.1_OBS
.234 -> B2.1_OBS
.61  -> B2.1_OBS
.97  -> stock 2.2.4 control
```

or:

```text id="rqzeyi"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

Early observation showed no Beacon Recovery errors on the B2.1_OBS devices during the first observed interval, while the stock control retained thousands of accumulated Beacon Recovery events.

These are preliminary observations only.

They are not long-term battery conclusions.

---

# 48. Current Research Decision

The current decision is:

```text id="h9g3xf"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

The project is therefore not currently:

- replacing WF200 firmware again
- changing FMAC
- adding new WF200 instrumentation
- changing AP/network conditions
- rolling B2.2 onto the active devices
- starting a new no-Recovery experiment

The current phase is evidence collection.

---

# 49. If B2.1_OBS Develops Drain

If a corrected device develops genuine rapid drain:

```text id="r6tccd"
capture first fault
        |
        v
correlate PM52 and cmd66 telemetry
        |
        v
check connection epoch / PM completion
        |
        v
compare battery-voltage behavior
        |
        v
resume deeper RE
```

This is the point at which a new WF200-specific hypothesis would become justified.

---

# 50. If B2.1_OBS Remains Stable

If the corrected platform remains stable long term:

```text id="0cqgpd"
remove observer
        |
        v
requalify observer-free corrected build
        |
        v
hardware regression
        |
        v
evaluate final candidate
```

The observer should not automatically become part of a final firmware candidate.

---

# 51. B2.2

A later observer-free integrated build is:

```text id="w1o5jl"
B2.2
```

Its nine selected correction components are:

```text id="xut7nw"
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

Its current disposition is:

```text id="h91mek"
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

No physical TRV was contacted during B2.2 qualification.

Therefore B2.2 is not hardware-qualified.

---

# 52. B2.2 Artifact Identity

Artifact:

```text id="o66hh6"
builds/firmware/B2.2/SHTRV-01_2.2.4_B2.2_EXPERIMENTAL.gbl
```

GBL:

```text id="h5rr0h"
size:
1,126,156 bytes

SHA-256:
912983973a5467241397b9dd967ee0039440c7d77780a2a97ee494b1a507860c

END CRC:
52A97051

CRC residue:
2144DF1C
```

Application:

```text id="rgri2c"
final/SHTRV-01_2.2.4_B2.2_EXPERIMENTAL.bin

size:
1,069,320 bytes

SHA-256:
7ee593265c76abd8cd628a81133d4b1310c1ae24c9ebe2ca3f2c2948acfc64f9

CRC:
42657D97
```

The native version string remains:

```text id="a4zd7v"
20240619-130912/v2.2.4@ee290818
```

The build must therefore be identified by artifact filename/hash rather than native Shelly version reporting.

---

# 53. WF200 3.18.0 Across B2.1 and B2.2

The same official 3.18.0 radio firmware remains part of:

```text id="a91r4a"
B2.1
B2.1_OBS
B2.2
```

This means the project is no longer changing radio firmware between these corrected build generations.

The differences between B2.1 and B2.2 lie elsewhere in the host application.

This helps preserve the radio side as a controlled variable during later comparison.

---

# 54. Current Experimental Model

The current investigation can be represented as:

```text id="i6ejxt"
Shelly host
    |
    +-- Beacon estimator
    |      |
    |      +-- C1a
    |      +-- C1b
    |      +-- C2
    |      |
    |      +-- C-C
    |
    +-- PM lifecycle
    |      |
    |      +-- G01/G02/G03/G05/G06/G18/G19
    |      |
    |      +-- A1R
    |
    +-- host sleep
           |
           +-- B2 race
           +-- B2 serialization
           +-- B3 / EM2 policy
           +-- PA8 veto

WF200
    |
    +-- radio PM implementation
    |
    +-- D3 / PS_MODE_ERROR
    |
    +-- stock 3.16.1
    |
    +-- experimental 3.18.0
           |
           +-- vendor sleep-related correction
```

No single branch currently explains all historical battery symptoms.

---

# 55. What Has Been Established

The current evidence supports the following conclusions.

### Shelly changed both FMAC and WF200 firmware across releases

The WLAN stack evolved significantly from 2.1.0 through 2.2.4.

### Beacon Recovery is host logic

The known Recovery decision is based on a host-derived estimator.

### `real_beacon_skip` is not direct WF200 sleep telemetry

It is derived from received-beacon statistics.

### D3 is a separate WF200 error indication

It is not synonymous with Shelly Beacon Recovery.

### D3 is not required for recurring Recovery

Thousands of historical Recovery events were observed with:

```text id="pn63ll"
D3_total = 0
```

### WF200 3.18.0 contains a relevant vendor correction

It addresses a failure class involving sleep after PM-mode changes.

### FMAC 3.7.0 and WF200 3.18.0 operate together on tested hardware

Initialization, association, DHCP, cloud and PM behavior were demonstrated.

### WF200 3.18.0 does not itself remove all fresh host Recovery

Historical C-C-based configurations still produced fresh qualifying triggers.

### B2.1 and B2.1_OBS use WF200 3.18.0

The current corrected hardware experiment therefore already includes the newer radio firmware.

### B2.2 also uses the same radio firmware

B2.2 adds further host-side corrections but has not been hardware tested.

---

# 56. What Has Not Been Established

The project does not currently claim:

- that WF200 3.16.1 is the sole cause of battery drain
- that WF200 3.18.0 fixes the complete battery problem
- that the Silicon Labs 3.18.0 fix is the exact historical TRV failure
- that every Beacon Recovery corresponds to a radio sleep failure
- that every radio sleep failure produces D3
- that D3 covers every internal WF200 PM failure
- that `real_beacon_skip` measures physical radio sleep
- that desired beacon skip equals physical skip behavior
- that FMAC 3.7.0 is universally supported with every later WF200 image
- that internal WF200 3.16.1 or 3.18.0 control flow has been completely reverse engineered
- that host logs provide direct radio sleep residency
- that the quantitative battery improvement from WF200 3.18.0 is known
- that B2.2 has been hardware-qualified
- that the historical battery-drain root cause has been proven

---

# 57. Remaining Questions

Important open WF200 questions include:

1. Does stock WF200 3.16.1 enter a persistent or extended awake condition after particular PM transitions?

2. If such a condition exists, is it visible through D3 or silent?

3. Does WF200 3.18.0 eliminate such a condition?

4. What exactly causes remaining fresh low host beacon-estimator values?

5. Does PA8 remain asserted during any radio-side abnormal condition?

6. How much time does WF200 physically spend in low-power states?

7. What is the electrical cost of a Beacon Recovery sequence?

8. Does the newer radio firmware materially improve long-term battery endurance once demonstrated host defects are corrected?

9. If B2.1_OBS drains, does PM52→cmd66 first-fault telemetry point toward a radio-side transition problem?

These questions require runtime evidence beyond static host analysis.

---

# 58. Current Test Strategy

Earlier development used several configurations to isolate variables:

```text id="9bghcg"
stock host
+
WF200 3.16.1
```

```text id="uvbn5v"
C-C
+
WF200 3.16.1
```

```text id="pp5aqz"
C-C
+
WF200 3.18.0
```

and historically:

```text id="a251b5"
A1
+
C-C
+
WF200 3.18.0
```

Those stages were useful for mechanism isolation.

The current active strategy is different:

```text id="7myn5l"
B2.1_OBS
+
WF200 3.18.0
```

compared against:

```text id="l6qkjx"
stock 2.2.4
+
WF200 3.16.1
```

The project is now waiting for long-term comparative hardware evidence rather than adding more radio-firmware variants.

---

# 59. Current Conclusions

WF200 is an important but separate part of the Shelly TRV Gen1 battery-drain investigation.

The strongest current conclusions are:

### The radio firmware evolved significantly

Investigated Shelly releases use WF200 firmware from 3.12.2 through 3.16.1.

### Shelly Beacon Recovery is not a direct WF200 error report

It is a host-side decision based on processed beacon statistics.

### D3 does not explain the historical recurring Recovery pattern

A hardware D3 observer recorded thousands of Recoveries without a D3 event.

### WF200 3.18.0 is technically relevant

Silicon Labs documents a fix for failure to sleep after a PM-mode change.

### WF200 3.18.0 works with Shelly FMAC 3.7.0 on tested hardware

This has been demonstrated through normal TRV startup and WLAN operation.

### The radio firmware integration is structurally qualified

The official 3.18.0 SEC was relocated, all 54 qualified references were updated, and the resulting payload was verified byte-for-byte.

### Fresh host Recovery can still occur with 3.18.0

Historical C-C-based tests showed fresh qualifying Recovery events.

### Physical radio sleep remains partly opaque

Host-visible commands and diagnostics are not equivalent to direct RF sleep-residency measurement.

### The current corrected hardware platform already includes 3.18.0

The active platform is B2.1_OBS, not the older A1+C-C build.

### B2.2 retains the same radio firmware

Its additional corrections are host-side and it remains offline-qualified only.

The current research decision remains:

```text id="7fb58o"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

The project therefore does not currently need another WF200 firmware experiment.

The most valuable next evidence will come from whether B2.1_OBS remains stable long term or, if drain occurs, what the PM52→cmd66 observer captures around the first failure.

---

# Related Documents

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle and A1/A1R:

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

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

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
- PM52→cmd66 observation
- long-term battery and WLAN observation

Historical builds are kept under their original identities.

A1 measurements are not relabeled as A1R.

B2/B2_OBS measurements are not retroactively described as B2.1/B2.1_OBS.

Where internal WF200 behavior cannot be observed directly, the limitation is stated rather than inferred from host telemetry.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

Shelly and Silicon Labs product names and trademarks are used only to identify the hardware and firmware being studied.

Experimental firmware should only be used on devices where recovery or reflashing is possible.