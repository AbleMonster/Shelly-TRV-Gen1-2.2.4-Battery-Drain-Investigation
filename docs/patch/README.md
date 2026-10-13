# Experimental Firmware Patches
## Shelly TRV Gen1 Firmware 2.2.4

## Scope

This document describes the experimental binary patches developed during the investigation of battery drain on Shelly TRV Gen1 firmware 2.2.4.

The original patch targets the additional beacon-recovery mechanism identified in firmware:

```text
20240619-130912/v2.2.4@ee290818
```

Further reverse engineering identified a separate periodic mDNS-related path involving `mdns_resp_restart()`.

This resulted in three experimentally useful firmware configurations:

```text
Patch A
Beacon-Recovery bypass

Patch B
mDNS restart-path bypass

Patch A+B
Beacon-Recovery bypass + mDNS restart-path bypass
```

The combined **A+B patch** is the current experimental patch used for long-term battery testing.

The current patcher/research release containing the combined configuration is:

```text
v1.0.0-beta.2
```

The purpose of these variants is not to assume that either mechanism is the battery-drain root cause.

Instead, they allow the identified paths to be isolated experimentally and compared against stock firmware.

> **Important:** None of the current patches has yet been proven to fix the historical Shelly TRV Gen1 battery-drain problem. Long-term battery testing is still in progress.

---

## 1. Target Firmware

The patches were developed specifically for Shelly TRV Gen1 firmware 2.2.4:

```text
20240619-130912/v2.2.4@ee290818
```

The analyzed original GBL has:

```text
Filename:
SHTRV-01_build.gbl

Size:
1,106,384 bytes

SHA-256:
5c4a0b...
```

The abbreviated hash is included here only as an identification aid.

The exact source firmware must be verified before applying a binary patch.

A patch offset derived for one firmware build must not be assumed to be valid for another build.

---

## 2. Background

Firmware 2.2.4 introduces host-side beacon-statistics processing not identified in the analyzed 2.1.x firmware versions.

The firmware queries WF200 beacon statistics and derives a value exposed through `/stats` as:

```text
real_beacon_skip
```

This value is used by an additional recovery decision.

Under qualifying conditions, the firmware temporarily changes the WLAN power-management state.

The runtime behavior observed on stock firmware is approximately:

```text
normal state 3
      |
      v
real_beacon_skip qualifies
      |
      v
"Beacon skip error! Attempt recovery"
      |
      v
state 1
      |
      | recovery countdown
      v
state 3
```

On affected devices this sequence can repeat approximately once per minute.

During continued reverse engineering, another independently patchable path involving `mdns_resp_restart()` was identified.

This path is separate from the beacon-recovery decision and therefore provides an additional candidate for unnecessary periodic WLAN activity.

At the current stage of the investigation, neither path is considered a confirmed battery-drain root cause.

Detailed analysis of the beacon-recovery mechanism is documented in:

- [`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)
- [`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)
- [`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

---

## 3. Recovery Decision

The relevant 2.2.4 recovery logic evaluates the stored `real_beacon_skip` byte.

The reverse-engineered logic shows that the byte is interpreted as a signed value for the recovery comparison.

The recovery condition effectively accepts non-zero values less than or equal to the threshold used by the recovery code.

This is important because the value is produced through arithmetic involving the beacon receive counter and reduced to a byte before being interpreted by the recovery logic.

Patch A does not change this calculation.

Instead, it bypasses the recovery block after the decision point.

This allows beacon-statistics processing and `real_beacon_skip` observation to continue while suppressing the targeted recovery action.

---

## 4. Original Control Flow

The relevant control flow can be simplified as:

```text
calculate / load real_beacon_skip
           |
           v
    recovery condition
       /          \
     false        true
      |             |
      |             v
      |       recovery block
      |             |
      |             v
      |          state 1
      |             |
      +-------------+
            |
            v
    common continuation
```

The recovery block includes the transition to the more active temporary power-management state.

Patch A changes the conditional branch so execution bypasses that block.

---

## 5. Patched Control Flow

The Patch-A behavior is conceptually:

```text
calculate / load real_beacon_skip
           |
           v
    recovery decision
           |
           v
     bypass recovery
           |
           v
    common continuation
```

The existing continuation code is retained.

No replacement power-management implementation is introduced.

This is intentionally a minimal modification.

---

## 6. Patch A — Thumb Instruction Patch

The relevant original Thumb instruction is located at virtual address:

```text
0x0001E1C8
```

Original instruction bytes:

```text
31 DC
```

The instruction is a conditional branch.

Patch A changes the second byte:

```text
DC -> E0
```

Patched bytes:

```text
31 E0
```

This converts the relevant conditional branch into an unconditional branch to the existing continuation target.

Only one application-program byte changes:

```text
Original:
DC

Patched:
E0
```

---

## 7. Patch A — Raw Program Image Offset

Within the extracted application/program image, the modified byte is located at:

```text
0x0001E1C9
```

The instruction itself begins at:

```text
0x0001E1C8
```

Therefore:

```text
Original program byte:
offset 0x0001E1C9 = 0xDC

Patched program byte:
offset 0x0001E1C9 = 0xE0
```

---

## 8. Application Image Extraction

The correct application image begins at GBL offset:

```text
0x00006554
```

Decimal:

```text
25940
```

The extracted application size is:

```text
1,049,548 bytes
```

The extraction used during analysis was equivalent to:

```bash
dd if="SHTRV-01_build.gbl" \
  of="SHTRV-01_2.2.4_program.bin" \
  bs=1 \
  skip=25940 \
  count=1049548
```

The extracted application image was analyzed as:

```text
ARM
Little Endian
32-bit
Cortex
Thumb
```

---

## 9. Patch A — GBL Patch Offset

The patched program byte must be mapped back into the GBL container.

The relevant calculation is:

```text
GBL application start:
0x00006554

Program patch offset:
0x0001E1C9

--------------------------------

GBL patch offset:
0x0002471D
```

Therefore the byte changed inside the GBL is:

```text
GBL offset 0x0002471D

DC -> E0
```

This offset is specific to the analyzed 2.2.4 GBL.

It must not be reused blindly for another firmware build.

---

## 10. Why the Earlier Extraction Offset Was Rejected

During the investigation, an earlier extraction beginning at:

```text
0x0000654C
```

was determined to be shifted.

That extraction must not be used as the canonical application image.

The correct application start for the analyzed firmware is:

```text
0x00006554
```

This distinction is important because even a small extraction shift changes:

- binary offsets;
- hashes;
- Ghidra address mapping;
- GBL patch mapping.

All current patch documentation uses the corrected `0x6554` application start.

---

## 11. Patch A — GBL CRC32

Changing the application byte requires the affected GBL integrity information to be updated.

For the analyzed GBL with Patch A:

```text
Original CRC32:
0xDC7BAB58

Patch-A CRC32:
0x432F734F
```

The patched GBL must contain the corrected CRC.

Changing only the application byte without updating the required GBL integrity field does not produce a valid patched firmware container.

---

## 12. Patch A — Patched GBL Verification

The resulting Patch-A GBL has SHA-256:

```text
ac7d85c8e9239bebd3b134c4b93fc838859c613e59f7690650097da984ea7222
```

This hash identifies the locally generated Beacon-Recovery-only artifact used during testing.

The patched firmware binary itself is not intended to be distributed through this research repository.

The project documents the analysis and patch method rather than publishing Shelly firmware.

---

## 13. Patch A Summary

The complete Beacon-Recovery binary modification is:

| Property | Original | Patch A |
|---|---|---|
| Firmware | 2.2.4 | 2.2.4 |
| Instruction address | `0x1E1C8` | `0x1E1C8` |
| Instruction bytes | `31 DC` | `31 E0` |
| Changed program byte | `0xDC` | `0xE0` |
| Program offset | `0x1E1C9` | `0x1E1C9` |
| GBL offset | `0x2471D` | `0x2471D` |
| CRC32 | `0xDC7BAB58` | `0x432F734F` |

Only the targeted branch byte and the required container integrity data are changed.

---

## 14. What Patch A Does

Patch A bypasses the identified 2.2.4 beacon-recovery block.

It prevents the targeted recovery decision from causing the temporary state-1 recovery transition.

The patch leaves the surrounding firmware execution intact.

In particular, it does not intentionally disable the beacon-statistics mechanism itself.

Runtime testing confirms that patched devices can continue reporting beacon-related statistics.

This is important because it allows the underlying calculation to remain observable while preventing the targeted recovery action.

---

## 15. What Patch A Does Not Do

Patch A does **not**:

- force `desired_beacon_skip` to 20;
- disable RSSI-dependent skip selection;
- modify the RSSI thresholds;
- change Wi-Fi transmit power;
- disable Wi-Fi power saving globally;
- modify WF200 firmware;
- change AP selection;
- enable roaming;
- modify thermostat algorithms;
- modify valve calibration;
- modify valve movement;
- directly fix the WUP/EM2 retention path;
- suppress the separately identified mDNS restart path;
- prove lower battery consumption.

It should therefore not be described as a general WLAN or battery optimization.

---

## 16. OTA Installation

The patched GBL was successfully installed on physical Shelly TRV Gen1 devices using the normal Gen1 OTA mechanism with a custom HTTP server.

The TRV requested the firmware through HTTP using a byte-range request.

Observed behavior included a request equivalent to:

```http
Range: bytes=0-
```

The custom OTA server therefore needed to correctly support the request behavior expected by the device.

Successful OTA installation demonstrates that the patched GBL is accepted by the tested device.

It does not independently prove functional correctness of the patch.

---

## 17. Patch-A Runtime Validation

Physical-device testing was performed after installation of the Beacon-Recovery-patched 2.2.4 firmware.

Under the tested conditions, the devices continued to provide:

- Wi-Fi connectivity;
- Shelly Cloud connectivity;
- thermostat operation;
- valve movement;
- valve calibration;
- normal status reporting;
- beacon statistics.

The characteristic repeating recovery sequence was no longer observed on the Patch-A devices during the test periods.

In particular, the patched devices could continue producing `real_beacon_skip` values that would be relevant to the stock recovery decision without entering the targeted state-1 recovery cycle.

This supports the conclusion that Patch A bypasses the recovery action rather than simply disabling the statistics calculation.

---

## 18. Stock 2.2.4 Control

A stock 2.2.4 device was retained as a control.

On the stock device, the characteristic recovery behavior was reproduced:

```text
state 3
   |
   v
beacon recovery condition
   |
   v
state 1
   |
   | approximately 5 seconds
   v
state 3
```

The cycle could repeat approximately once per minute.

The behavior was also observed under relatively good RSSI conditions.

This is important because it demonstrates that the repeating recovery is not limited to an obviously weak-signal environment.

The exact energy cost of each recovery cycle remains unmeasured.

---

## 19. Patch A vs. Stock Behavior

The experimental Beacon-Recovery comparison can be summarized as:

| Behavior | Stock 2.2.4 | Patch A |
|---|---|---|
| Normal desired beacon-skip selection | Yes | Yes |
| Beacon-statistics calculation | Yes | Yes |
| `real_beacon_skip` available | Yes | Yes |
| Targeted recovery decision executed | Yes | Bypassed |
| State-1 recovery observed | Yes | No, under tested conditions |
| Normal thermostat operation | Yes | Yes |
| Valve operation | Yes | Yes |
| Wi-Fi connectivity | Yes | Yes |
| Shelly Cloud connectivity | Yes | Yes |
| mDNS restart path suppressed | No | No |
| Improved battery life proven | No | No |

This comparison established that the Beacon-Recovery path can be selectively suppressed without disabling the surrounding beacon-statistics mechanism.

It did not establish whether the Beacon-Recovery mechanism is the primary cause of battery drain.

---

## 20. Patch Evolution and A/B Test Variants

The original investigation initially focused on the repeating Beacon-Recovery behavior introduced in firmware 2.2.4.

Patch A was developed to isolate that mechanism.

Further analysis identified a separate periodic mDNS-related execution path involving:

```text
mdns_resp_restart()
```

Because this mechanism can be patched independently from the Beacon-Recovery path, a second experimental modification was developed.

The current patch architecture therefore distinguishes:

```text
Patch A
Beacon-Recovery bypass

Patch B
mDNS restart-path bypass

Patch A+B
Beacon-Recovery bypass
+
mDNS restart-path bypass
```

These variants are intended primarily as experimental controls.

The term **A/B patch** in this project refers to the combination of the two independently developed binary modifications.

It does **not** mean that the firmware contains a runtime A/B switch.

### Patch A — Beacon-Recovery bypass

Patch A changes:

```text
Program offset:
0x0001E1C9

Original:
0xDC

Patched:
0xE0
```

This corresponds to:

```text
31 DC -> 31 E0
```

and bypasses the identified Beacon-Recovery block.

### Patch B — mDNS restart-path bypass

Patch B targets the separately identified mDNS-related path.

The relevant application-program modification is:

```text
Program offset:
0x0001E0F1

Original:
0xD0

Patched:
0xE0
```

Using the corrected application start:

```text
0x00006554
```

this maps to GBL offset:

```text
0x00024645
```

Patch B does not modify the Beacon-Recovery branch.

It therefore provides a useful experimental configuration for observing behavior when the mDNS path is suppressed while the Beacon-Recovery mechanism remains otherwise unchanged.

### Patch A+B — current combined experimental patch

The current combined patch applies both modifications to an original 2.2.4 GBL:

```text
Patch B:
Program offset 0x0001E0F1
D0 -> E0

Patch A:
Program offset 0x0001E1C9
DC -> E0
```

The resulting combined GBL has:

```text
CRC32:
0xBAEB8265
```

The locally generated combined artifact used for testing has SHA-256:

```text
7adbb31d...ded84ac61
```

The abbreviated hash is used here as an identification aid.

Including the required GBL integrity updates, the resulting combined container differs from the original GBL at six byte positions.

The combined patch is the current experimental long-term-test candidate.

The corresponding current research/patcher release is:

```text
v1.0.0-beta.2
```

The combined patch must be generated from the verified original 2.2.4 GBL.

It must not be produced by applying offsets intended for 2.2.4 to a different firmware version.

---

## 21. Purpose of the A/B Test Design

The existence of two independently patchable paths allows the investigation to move beyond a simple stock-versus-patched comparison.

The experimental question is no longer only:

```text
Does suppressing Beacon-Recovery improve battery life?
```

The investigation can now distinguish between:

```text
Stock firmware
       |
       +-- Beacon-Recovery active
       |
       +-- mDNS path active


Patch A
       |
       +-- Beacon-Recovery suppressed
       |
       +-- mDNS path active


Patch B
       |
       +-- Beacon-Recovery active
       |
       +-- mDNS path suppressed


Patch A+B
       |
       +-- Beacon-Recovery suppressed
       |
       +-- mDNS path suppressed
```

This provides a more useful experimental framework.

If battery behavior differs between these configurations over sufficiently long observation periods, the comparison may help determine whether:

- Beacon-Recovery contributes materially to battery consumption;
- the mDNS path contributes materially to battery consumption;
- both mechanisms contribute;
- or neither mechanism sufficiently explains the historical drain.

This distinction is important.

A reduction in periodic WLAN activity after applying a patch is not, by itself, proof of meaningful battery-life improvement.

The long-term battery measurements are therefore treated as the primary evidence for evaluating the practical effect.

---

## 22. Current Long-Term Battery Test

Long-term battery testing is currently in progress using multiple physical Shelly TRV Gen1 devices with different firmware and patch configurations.

The test design includes stock and patched devices so that battery behavior can be compared over time.

Current experimental configurations include, among others:

```text
mDNS-only patched device
Beacon-Recovery active
mDNS path suppressed
```

and:

```text
combined A+B patched device
Beacon-Recovery suppressed
mDNS path suppressed
```

A stock 2.2.4 configuration is retained as an important control.

Battery measurements are collected repeatedly rather than relying on occasional readings.

The primary battery parameters used for comparison are obtained from the device `/status` response:

```text
bat.value
bat.voltage
```

Battery voltage is particularly important because the reported percentage is quantized and does not provide sufficient resolution by itself for short-term comparisons.

Measurements are currently logged at 30-minute intervals and stored for later analysis.

Daily reports are generated separately from the raw measurement history.

The objective is to compare trends over sufficiently long periods rather than interpreting individual voltage changes as evidence of a patch effect.

Environmental and operational differences between physical devices remain potential confounding variables.

For that reason, current short-term differences must not be interpreted as final battery-life results.

---

## 23. Why the Current Patches Are Still Experimental

The Beacon-Recovery patch has demonstrated a clear behavioral effect:

> It suppresses the targeted 2.2.4 Beacon-Recovery transition.

The mDNS patch likewise provides a way to suppress the separately identified mDNS restart path.

The combined A+B patch allows both mechanisms to be suppressed simultaneously.

However, none of these observations establishes that either mechanism is the historical root cause of Shelly TRV Gen1 battery drain.

Historical device observations indicate that firmware 2.1.8 could also exhibit relatively rapid battery drain.

The known counter-derived 2.2.4 Beacon-Recovery mechanism is not present in the analyzed 2.1.8 host firmware.

This is strong reason not to equate the 2.2.4 Beacon-Recovery mechanism with the complete historical battery-drain problem.

The newly identified mDNS path provides another concrete mechanism to investigate, but its energy impact has not yet been quantified.

Additional areas that remain relevant include:

- host-side WUP/EM2 sleep-resource retention;
- WF200 power-save fallback;
- differences introduced between 2.1.0 and 2.1.3;
- state-5 behavior introduced in 2.1.3;
- later WF200/FMAC changes.

The current patches should therefore be understood as **experimental isolation patches**.

They selectively suppress identified firmware behavior so that its practical effect can be measured.

They are not yet confirmed root-cause fixes.

---

## 24. Possible Future Root-Cause Patch

If ongoing analysis identifies a specific underlying power-management defect, a future patch may target that mechanism directly.

For example, if a safe correction can be established for:

- device-sleep failure handling;
- WUP/resource cleanup;
- EM2 blocker release;
- WF200 power-save reapplication;

then a root-cause-oriented patch could potentially be developed.

Such a patch would be fundamentally different from the current isolation patches.

Conceptually:

```text
Current Patch A:

abnormal beacon condition
          |
          v
2.2.4 Beacon-Recovery
          |
          X
       bypassed
```

```text
Current Patch B:

mDNS-related restart path
          |
          X
       bypassed
```

```text
Current Patch A+B:

Beacon-Recovery --------X

mDNS restart path ------X
```

A possible future root-cause patch would instead operate conceptually as:

```text
underlying PM failure
          |
          v
safe correction / cleanup
          |
          v
normal power state
          |
          v
secondary recovery activity
may no longer be required
```

No such root-cause patch has currently been established.

---

## 25. Safety of Further Patch Development

A sleep-resource failure must not be patched by blindly forcing resource release.

If the WF200 or host interface still requires the MCU to remain awake, incorrectly releasing the associated sleep blocker could cause:

- lost WLAN communication;
- missed interrupts;
- driver state corruption;
- transport failures;
- unstable firmware behavior.

Any future modification to WUP/EM2 handling therefore requires reconstruction of the complete success and failure lifecycle before a binary patch is attempted.

The current branch patches avoid directly modifying this lower-level mechanism.

This is one reason why the current A/B approach is useful: identified higher-level behaviors can be isolated experimentally without prematurely modifying the lower-level sleep-resource lifecycle.

---

## 26. Distribution Policy

The research repository should document:

- firmware identification;
- reverse-engineering findings;
- patch offsets;
- minimal byte modifications;
- integrity recalculation;
- patch-generation tooling;
- validation results;
- experimental test methodology.

It should not publish:

- original Shelly firmware binaries;
- patched Shelly firmware binaries;
- extracted proprietary application images;
- large raw disassembly exports;
- unreviewed proprietary firmware dumps.

The intended principle is:

> **Publish the results of the analysis and the patch method, not the firmware itself.**

The patches should be reproducible from a legally obtained and verified original firmware image using the documented patching process.

---

## 27. Current Status

### Proven

- Firmware 2.2.4 contains the targeted Beacon-Recovery path.
- The identified Beacon-Recovery branch controls entry into that recovery block.
- Changing `31 DC` to `31 E0` bypasses the targeted Beacon-Recovery block.
- Beacon-Recovery Patch A can be applied to the analyzed 2.2.4 application image.
- The Patch-A GBL can be installed on tested physical TRVs.
- Patch-A devices continue normal thermostat and WLAN operation under the tested conditions.
- Beacon-statistics processing remains active with Patch A.
- The targeted repeating Beacon-Recovery sequence was suppressed during Patch-A testing.
- A separate mDNS-related path involving `mdns_resp_restart()` has been identified and can be patched independently.
- Patch B modifies the mDNS-related path without modifying the Beacon-Recovery branch.
- Patch A and Patch B can be combined in the same 2.2.4 firmware image.
- The combined A+B firmware can be generated from the verified original 2.2.4 GBL.
- The combined A+B patch is suitable for controlled runtime and long-term battery testing.

### Observed / experimentally supported

- Stock 2.2.4 devices can repeatedly enter the Beacon-Recovery sequence approximately once per minute.
- This behavior can occur even under relatively good RSSI conditions.
- Patch A suppresses this sequence while leaving beacon-statistics reporting active.
- The mDNS-related path represents periodic WLAN-related activity independent of the Beacon-Recovery branch.
- Separating Patch A and Patch B provides a practical way to compare the two mechanisms experimentally.
- Patched devices have remained operational during the test periods observed so far.

### Plausible

- Repeated Beacon-Recovery transitions consume additional energy compared with remaining in the normal power-management state.
- Repeated mDNS-related activity may contribute additional energy consumption.
- Suppressing both paths may reduce unnecessary WLAN-related activity.
- Comparing stock, Patch-A, Patch-B and Patch-A+B configurations may help determine the relative contribution of each path.

### Not proven

- The magnitude of the energy consumed by a single Beacon-Recovery cycle.
- The magnitude of the energy consumed by the identified mDNS activity.
- Long-term battery-life improvement from Patch A.
- Long-term battery-life improvement from Patch B.
- Long-term battery-life improvement from Patch A+B.
- That Beacon-Recovery is the original battery-drain root cause.
- That the mDNS path is a battery-drain root cause.
- That Beacon-Recovery and mDNS together fully explain the historical battery drain.
- That the current A+B patch fixes battery-drain mechanisms present in older firmware.
- That the current A+B patch is the optimal final solution.

The long-term battery test is therefore the next major evidence source.

Until sufficient data is available, the current patch should continue to be described as:

> **Experimental A+B isolation patch for Shelly TRV Gen1 firmware 2.2.4.**

and not as:

> **Confirmed battery-drain fix.**

---

## Related Documents

Reverse-engineering details:

- [`Firmware Comparison`](../reverse-engineering/firmware-comparison.md)
- [`Power Management and Sleep`](../reverse-engineering/power-management-and-sleep.md)
- [`Beacon RX Counter`](../reverse-engineering/beacon-rx-counter.md)
- [`Real Beacon Skip`](../reverse-engineering/real-beacon-skip.md)
- [`Recovery Mechanism`](../reverse-engineering/recovery-mechanism.md)
- [`AP Selection and Roaming`](../reverse-engineering/ap-selection-and-roaming.md)

Long-term battery measurements are documented separately in the battery-testing documentation.

The A/B patch variants should be interpreted together with those measurements rather than as independent evidence of improved battery life.