# Shelly TRV Gen1 – Battery-Drain Investigation

Reverse engineering, runtime analysis, long-term battery testing, and experimental firmware research for the Shelly TRV Gen1 (`SHTRV-01`).

This project investigates the unusually high battery consumption observed on Shelly TRV Gen1 devices and attempts to identify the firmware mechanisms that contribute to it.

The research currently focuses on firmware generations from `2.1.0` through `2.2.4`, with firmware `2.2.4` as the primary reverse-engineering target.

The project does **not** assume that the historical battery-drain problem has a single cause.

Instead, firmware comparison, runtime observation, packet capture, controlled patching, and long-term battery logging are used to separate individual mechanisms and determine their actual relevance.

---

# Current Status

Research is ongoing.

Several important firmware behaviors have now been identified and independently validated.

The most important current findings are:

- periodic connected mDNS restart activity was introduced after firmware 2.1.0
- firmware 2.2.4 contains an additional Beacon Recovery mechanism
- the Beacon Recovery mechanism contains multiple measurement/control-validity problems
- a qualifying Beacon Recovery result can become self-sustaining because historical control evidence is reused
- the first recovery can also be triggered from an invalid measurement window
- an additional signed-value interpretation problem exists in the recovery decision
- Patch A experimentally suppresses Beacon Recovery
- Patch B experimentally suppresses the periodic 2.2.4 mDNS restart
- Patch A and Patch B can operate together on real hardware
- long-term battery testing is ongoing
- the current Patch C-C candidate has passed static pre-build qualification; experimental build and hardware qualification remain pending

The historical battery-drain problem is **not yet considered solved**.

---

# Firmware Versions Investigated

| Firmware | Build | Role |
|---|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` | older reference |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` | early comparison |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` | later comparison |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` | primary research target |

The exact firmware version in which the historical battery-runtime degradation first appeared remains unknown.

Battery drain was also observed in practical use after downgrading from 2.2.4 to 2.1.8.

Therefore:

> Firmware 2.2.4 cannot currently be considered the origin of the entire historical battery-drain problem.

Firmware 2.1.0 is used as an older reference because several WLAN-related behaviors differ significantly from later firmware.

---

# Research Method

The investigation combines:

- native ARM Thumb firmware analysis
- cross-version firmware comparison
- control-flow reconstruction
- WF200 host-interface analysis
- runtime debug logging
- passive network capture
- controlled firmware modifications
- isolated A/B testing
- long-term battery logging
- battery-voltage comparison
- runtime and reboot tracking
- RSSI monitoring
- Beacon Recovery statistics
- valve/motor activity analysis

Decompiler output is treated as supporting information.

Where possible, important findings are verified against native instructions, control flow, runtime behavior, or independent measurements.

---

# Evidence Classification

The project uses four evidence levels.

### PROVEN

Directly established from native firmware behavior, deterministic static analysis, validated binary changes, or sufficiently direct runtime evidence.

### STRONGLY SUPPORTED

Multiple independent findings support the conclusion, but some implementation detail or environmental dependency remains unresolved.

### INFERENCE

A technically plausible interpretation consistent with the available evidence, but not directly established.

### UNKNOWN

The available evidence is insufficient to determine the behavior or intent.

These classifications are intentionally used to distinguish firmware facts from interpretation.

---

# Key Finding 1 – Periodic mDNS Restart

The mDNS responder itself already exists in firmware 2.1.0.

The important later change is the addition of recurring connected maintenance that restarts the mDNS probing process.

Runtime packet capture confirmed the resulting periodic traffic.

Observed behavior:

| Firmware | Runtime observation |
|---|---|
| 2.1.0 | no comparable periodic burst observed during the monitored ~13-minute window |
| 2.1.3 | approximately one burst every 60 seconds |
| 2.2.4 | approximately one burst every 180 seconds |

A typical burst contains:

```text
probe
probe
probe
announcement
```

In firmware 2.2.4, the approximately 180-second interval is not implemented as a dedicated 180-second timer.

The relevant connected maintenance path is serviced on a minute basis and the mDNS restart is reached every third applicable invocation.

### Interpretation

**PROVEN:** The recurring mDNS restart creates additional periodic firmware and network activity.

**UNKNOWN:** Its quantitative contribution to battery drain.

No direct electrical energy measurement per mDNS cycle has yet been performed.

---

# Patch B – Periodic mDNS Restart Bypass

Patch B is an experimental firmware modification that bypasses the recurring 2.2.4 mDNS restart call.

It does **not** remove mDNS itself.

Other event-driven mDNS functionality remains present.

The modification is therefore described as:

```text
Periodic mDNS restart bypass
```

and not:

```text
mDNS disabled
```

Runtime packet capture on the isolated Patch-B test device confirmed that the targeted periodic mDNS traffic disappeared during the monitored test window.

Normal connectivity remained available.

Importantly, Beacon Recovery continued to occur.

This provides strong evidence that:

> The periodic mDNS restart is not required for the observed recurring Beacon Recovery behavior under the tested conditions.

This does not prove that the mechanisms can never interact under other conditions.

---

# Key Finding 2 – Beacon Recovery

Firmware 2.2.4 contains an additional WLAN Beacon Recovery mechanism.

The characteristic runtime message is:

```text
minutes_tick: Beacon skip error! Attempt recovery
```

When triggered, the firmware approximately performs:

```text
normal Fast Power Save
        ↓
Beacon Recovery
        ↓
PM state 1 / active WLAN
        ↓
approximately 5 seconds
        ↓
restore normal PM policy
        ↓
normally state 3 / Fast Power Save
```

State 1 places the WF200 into an active configuration and temporarily prevents the normal deeper host sleep behavior associated with the connected power-save state.

No evidence was found that the normal recovery sequence intentionally performs a complete Wi-Fi reconnect, DHCP renewal, or cloud reconnect.

No explicit transmit-power increase was identified.

On affected stock 2.2.4 devices, the recovery has been observed approximately once per minute for extended periods.

The behavior has also occurred with good RSSI, for example around `-58` to `-60 dBm`.

Poor RSSI is therefore not a necessary condition for the observed recurring recovery loop.

---

# Beacon Measurement

Firmware 2.2.4 periodically requests WF200 statistics.

The relevant host-side measurement uses a cumulative received-beacon counter.

For a previous value `P` and current value `C`, the firmware derives:

```text
delta = C - P
```

and approximately calculates:

```text
real_beacon_skip = 600 / delta
```

The result is stored in an 8-bit field.

The value is also exposed diagnostically through firmware statistics.

The same stored value is later used by the Beacon Recovery control logic.

This creates several important validity problems.

---

# C1a – Signed Beacon-Skip Interpretation

The calculated quotient is stored as one byte.

The recovery decision in stock firmware 2.2.4 subsequently reads that byte as a **signed** value.

This creates unexpected qualifying values.

Examples:

```text
delta = 3

600 / 3 = 200

8-bit value:
0xC8

signed interpretation:
-56
```

and:

```text
delta = 4

600 / 4 = 150

8-bit value:
0x96

signed interpretation:
-106
```

Because the recovery predicate accepts values less than or equal to `2` after rejecting zero, these negative interpretations can incorrectly satisfy the recovery condition.

The fresh-trigger set under the stock signed-byte behavior is therefore:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

Under the intended non-negative quotient interpretation, only the range producing actual values `1` or `2` should satisfy that comparison.

### Classification

**PROVEN:** The signed byte interpretation changes the control decision for valid positive quotient values such as 150 and 200.

**STRONGLY SUPPORTED:** This represents a control/measurement-validity defect rather than an intentional negative error-code mechanism.

No independent negative sentinel or error semantics have been identified for this field.

---

# C1b – Measurement-Window Validity

The firmware uses the fixed numerator:

```text
600
```

but the Beacon Recovery calculation does not contain a corresponding elapsed-time normalization for the stored baseline `P`.

This matters because the previous cumulative counter can survive situations in which one or more expected measurement opportunities are skipped.

Conceptually:

```text
baseline P
    ↓
measurement opportunity skipped
    ↓
P survives
    ↓
another opportunity skipped
    ↓
P still survives
    ↓
later current value C
    ↓
600 / (C - P)
```

The resulting `delta` can therefore represent a longer interval than the calculation assumes.

Several WLAN power-management and maintenance paths can affect whether a normal measurement opportunity is available.

### Why this matters

A sufficiently aged baseline can produce a quotient of `1` or `2` even when the underlying beacon reception does not represent the failure condition that the calculation appears intended to detect.

### Classification

**PROVEN:** The fixed-600 calculation contains no corresponding elapsed-time normalization.

**PROVEN:** Identified firmware paths can preserve the previous baseline while measurement opportunities are skipped.

**STRONGLY SUPPORTED:** This creates a genuine measurement-validity problem.

**UNKNOWN:** Whether this is the mechanism responsible for the first Beacon Recovery event observed on the current physical test devices.

Capturing the exact first trigger remains an important runtime objective.

---

# C2 – Self-Sustaining Beacon Recovery

The most important Beacon Recovery control-flow finding concerns what happens **after a qualifying recovery event**.

Two values are relevant:

```text
P = previous cumulative beacon receive counter

R = cached real_beacon_skip
```

During a qualifying recovery, stock firmware clears `P`.

However, the qualifying `R` value is retained.

The next successful measurement therefore begins with:

```text
P = 0
R = previous qualifying value
```

Because `P` is zero, the firmware cannot calculate a fresh delta.

It instead installs the current cumulative counter as the new baseline.

However, stock control flow then continues to evaluate the **old cached R value**.

The sequence becomes:

```text
fresh qualifying R
        ↓
Beacon Recovery
        ↓
P = 0
R retained
        ↓
next successful statistics sample
        ↓
P was zero
        ↓
current counter becomes new P
        ↓
no fresh R was calculated
        ↓
old qualifying R is evaluated anyway
        ↓
Beacon Recovery again
        ↓
P = 0
        ↓
repeat
```

This prevents the newly installed baseline from surviving long enough to obtain the next fresh measurement.

### Important consequence

Once the system enters this state, a new beacon anomaly is **not required for every subsequent recovery**.

The historical qualifying value can repeatedly trigger the recovery path.

### Classification

**PROVEN:** This self-sustaining state exists in the identified stock 2.2.4 control flow.

**PROVEN:** Normal successful post-recovery statistics acquisition does not by itself break the loop.

**PROVEN:** The normal PM restoration does not clear the cached qualifying value.

**UNKNOWN:** Whether preserving the value was originally intended as diagnostic history.

The value is exposed through `/stats`, so retaining the last calculated result has a plausible diagnostic purpose.

The problem is therefore better described as a failure to distinguish:

```text
historical diagnostic value
```

from:

```text
fresh control evidence
```

rather than simply assuming that retaining the value itself was accidental.

---

# Combined Beacon-Recovery Failure Model

The current firmware analysis supports the following possible sequence:

```text
measurement window becomes invalid
        ↓
aged or otherwise invalid baseline
        ↓
qualifying real_beacon_skip result
        ↓
first Beacon Recovery
        ↓
P cleared
R retained
        ↓
historical R reused as fresh control evidence
        ↓
recovery approximately every minute
        ↓
self-sustaining recovery cycle
```

The first-trigger validity problems and the post-recovery loop are separate defects.

A false first trigger is therefore not required for the post-recovery problem to exist.

Likewise, correcting only the first-trigger calculation would not correct the stale-control-evidence loop after a genuinely qualifying recovery.

The exact cause of the first recovery event on the currently affected physical devices remains under investigation.

---

# Patch A – Beacon-Recovery Bypass

Patch A was developed before the complete Beacon Recovery control flow was understood.

It changes the branch entering the recovery block while leaving the surrounding beacon-statistics calculation active.

Runtime testing confirmed:

- Beacon Recovery is suppressed
- beacon statistics continue to update
- normal Wi-Fi remains available
- cloud connectivity remains available
- thermostat operation remains available

Patch A has therefore been extremely useful as an **experimental isolation tool**.

However, the later reverse engineering changed its interpretation.

Beacon Recovery itself has a legitimate reliability purpose: a fresh and genuinely abnormal beacon measurement can justify reconfiguring the WF200 power-management state.

Patch A suppresses that recovery entirely.

Therefore:

> Patch A should not currently be considered the preferred final correction for the Beacon Recovery defect.

It remains valuable for controlled A/B testing and for measuring the cost of the recovery workload.

---

# Patch C – Corrective Beacon-Recovery Research

The current Patch C research aims to correct the identified Beacon Recovery validity problems **without removing legitimate recovery behavior**.

The behavioral requirements are:

1. preserve diagnostic Beacon Recovery statistics
2. prevent signed-byte interpretation from creating false qualifying control values
3. prevent invalid measurement windows from being treated as nominal samples
4. prevent historical `real_beacon_skip` values from acting as fresh control evidence
5. allow a new baseline to survive long enough to obtain a fresh measurement
6. preserve legitimate recovery when a new valid measurement genuinely qualifies
7. preserve unrelated WLAN power-management behavior
8. preserve normal connectivity and thermostat operation

Conceptually:

```text
invalid measurement window
        ↓
re-establish baseline
        ↓
wait for fresh comparable measurement
        ↓
calculate fresh result
        ↓
healthy result ───────────→ continue normally
        │
        └── genuine fault → Beacon Recovery
```

The current Patch C-C candidate has completed static pre-build qualification.

No known static blocker was identified in the bounded independent review. The modified instruction ranges, control flow, helper code, interrupt-mask handling, baseline invalidation logic, and preservation of legitimate fresh Beacon Recovery were independently checked.

This result justifies the next research phase: creation and independent verification of an experimental firmware build for controlled hardware A/B testing.

It does **not** establish runtime correctness, battery-life improvement, or a production-ready fix. Physical sample timing, external PM transaction behavior, IRQ latency, bootloader/OTA acceptance, and long-term measurement availability under policy or connection churn still require hardware qualification.

Patch C-C therefore remains an experimental research candidate and is not a released or hardware-qualified patch.

---

# WUP / EM2 Sleep-Resource Handling

A separate low-level WLAN power-management path remains under investigation.

The normal sleep transition approximately performs:

```text
acquire WLAN wake resource
        ↓
configure WF200 power mode
        ↓
final device-sleep operation
        ↓
release wake / EM2 blocking resource
```

If the final low-level sleep operation fails, the release path may not be reached.

This can leave a WLAN-owned wake / EM2-blocking resource retained.

However:

- the fundamental path already exists in firmware 2.1.0
- the resource is reference-counted
- later firmware may reach or prolong the condition differently
- its frequency in real operation has not been established

Therefore it cannot currently explain the historical battery-runtime boundary by itself.

No patch is currently justified that blindly releases this resource.

WUP / EM2 handling remains a **separate research topic** and is not the current Patch C.

---

# Desired Beacon Skip

During normal connected operation, firmware 2.2.4 configures WF200 Fast Power Save with a desired beacon-skip value derived from RSSI.

Observed mapping:

```text
RSSI >= -69 dBm       desired skip = 20

RSSI -70 .. -79 dBm   desired skip = 15

RSSI < -79 dBm        desired skip = 10
```

These are requested power-save parameters.

They should not be confused with the calculated diagnostic `real_beacon_skip`.

The current Beacon Recovery logic also does not simply compare:

```text
real_beacon_skip
```

against:

```text
desired_beacon_skip
```

Poor RSSI alone therefore does not explain the observed recurring recovery cycle.

---

# Firmware Evolution

The cross-version comparison shows that WLAN behavior evolved substantially across the investigated firmware generations.

## 2.1.0 → 2.1.3

Relevant changes include:

```text
2.1.0
  ↓
2.1.3
  ├─ periodic connected mDNS restart
  ├─ state-5 / psovrd2 mechanism
  ├─ named active power-save override
  ├─ wake ACK timing change
  └─ event-handling changes
```

The periodic mDNS restart is the strongest confirmed new recurring connected workload identified in this transition.

## 2.1.3 → 2.1.8

Relevant changes include:

- additional post-association PM sequencing
- updated FMAC generation
- updated protected WF200 firmware
- additional network behavior changes

No single new unconditional host-side sleep-lock leak was identified.

## 2.1.8 → 2.2.4

Firmware 2.2.4 adds or expands:

- WF200 statistics
- beacon receive counters
- `real_beacon_skip`
- Beacon Recovery
- PM retry/locking behavior
- newer FMAC/WF200 components

The Beacon Recovery mechanism investigated in this repository is specific to the later 2.2.4 control flow and therefore cannot explain all battery drain historically observed on 2.1.8.

---

# Experimental Patch Matrix

| Configuration | Periodic mDNS | Beacon Recovery | Purpose |
|---|---:|---:|---|
| Stock 2.2.4 | active | active when qualifying | control |
| Patch A | active | bypassed | isolate Beacon Recovery |
| Patch B | bypassed | active | isolate periodic mDNS |
| Patch A+B | bypassed | bypassed | combined workload experiment |
| Patch C-C | preserved | corrected behavior intended | static pre-build qualification passed; hardware testing pending |

Patch A and Patch B are experimental research modifications.

Patch C is not yet a hardware-qualified release.

---

# Long-Term Battery Testing

Long-term battery logging is being performed across multiple physical SHTRV-01 devices.

The logger records approximately every 30 minutes.

Collected values include, where available:

- firmware version
- battery percentage
- battery voltage
- uptime
- RSSI
- desired beacon skip
- real beacon skip
- beacon receive statistics
- Beacon Recovery counter

Daily reports are generated for longer-term comparison.

Battery voltage is treated as a stronger short-term indicator than the reported battery percentage, but neither represents a direct electrical energy measurement.

Valve/motor activity must also be considered because motor movement represents real mechanical work and can materially affect battery behavior.

---

# Current Test Roles

The active research setup includes several physical TRVs with different firmware roles.

Important current configurations include:

| Device | Configuration | Role |
|---|---|---|
| `.77` | mDNS-only patched firmware; Beacon Recovery unchanged | isolated mDNS experiment |
| `.226` | Beacon Recovery bypass + mDNS bypass | combined experimental patch |
| `.229` | stock 2.2.4 | unmodified control/reference |

Additional TRVs are used for comparison and experimental firmware testing.

Device roles can change during the investigation.

Any dataset crossing a firmware transition must therefore be divided at the transition before battery behavior is compared.

---

# Battery-Data Interpretation

Cross-device battery comparison requires caution.

Physical devices can differ in:

- battery age
- battery condition
- battery calibration
- initial state of charge
- temperature
- valve load
- motor workload
- WLAN conditions
- RSSI
- previous operating history

Battery percentage is quantized and should not be treated as a precise energy measurement.

Battery voltage is more useful for observing trends, but it is also affected by:

- instantaneous load
- battery chemistry
- relaxation after charging
- temperature
- recent motor activity

Therefore:

```text
Device A lost X mV
Device B lost Y mV
```

does not by itself establish an exact difference in energy consumption.

Longer observation periods, repeated behavior, and controlled comparisons are required.

---

# Current Scientific Interpretation

The available evidence currently supports a multi-mechanism model.

At minimum, the investigation has identified:

```text
normal TRV workload
        +
periodic mDNS workload
        +
firmware-specific WLAN power management
        +
2.2.4 Beacon Recovery behavior
        +
possible conditional sleep-resource retention
        +
normal valve/motor activity
        +
cloud/network communication
        +
radio conditions
```

This remains a qualitative model.

It is **not** a quantitative energy budget.

The relative contribution of each component remains unknown.

The Beacon Recovery investigation has, however, progressed beyond identifying only an additional workload.

The stock 2.2.4 host control flow now contains identifiable measurement and control-validity problems that can explain how recurring recovery can become self-sustaining after an initial qualifying event.

That does not establish how much of the historical battery drain is caused by this mechanism.

---

# What Has Been Established

### Periodic mDNS is a real recurring workload

Runtime packet capture confirms periodic mDNS probing/announcement behavior in later firmware.

### Beacon Recovery is a real recurring workload

Affected stock 2.2.4 devices can enter recovery approximately once per minute for extended periods.

### Good RSSI does not prevent the observed recovery loop

Recurring recovery has been observed around `-58` to `-60 dBm`.

### Periodic mDNS is not required for the observed recovery loop

The isolated mDNS-patched device continued Beacon Recovery.

### Patch A suppresses Beacon Recovery

The underlying statistics continue operating.

### Patch B suppresses the targeted periodic mDNS restart

Event-driven mDNS behavior is not intentionally removed.

### Patch A+B operates on real hardware

Both targeted recurring mechanisms can be suppressed simultaneously while normal observed TRV functionality remains available.

### Stock Beacon Recovery contains a stale-control-evidence loop

A qualifying cached `real_beacon_skip` value can be reused after recovery without a fresh ratio calculation.

### Stock Beacon Recovery contains a signed-value control problem

Positive calculated values can become negative after 8-bit signed interpretation and incorrectly satisfy the recovery predicate.

### The measurement window is not explicitly normalized

A fixed numerator is used even when the previous counter baseline can survive skipped measurement opportunities.

---

# What Has NOT Been Established

The project does **not** currently claim:

- that the complete historical battery-drain problem has been solved
- that Beacon Recovery is the sole cause
- that periodic mDNS is the sole cause
- that Patch A+B restores a specific battery lifetime
- that firmware 2.1.8 introduced the original problem
- that firmware 2.1.3 is battery-drain free
- that firmware 2.1.0 never emits mDNS
- that the WUP / EM2 path is responsible for the observed historical regression
- that the exact first Beacon Recovery trigger on the affected physical devices has been captured
- that Patch C-C has completed hardware qualification
- that Patch C-C has demonstrated a battery-life improvement on hardware
- that any current patch is production firmware

---

# Current Research Direction

The current work has two parallel goals.

## 1. Long-Term Battery Comparison

Continue controlled logging of stock and experimental firmware configurations.

Primary measurements include:

- battery voltage
- reported battery percentage
- uptime
- RSSI
- Beacon Recovery statistics
- unexpected reboots
- valve/motor activity
- firmware configuration

The objective is to determine whether removing specific recurring workloads produces a reproducible improvement in real battery behavior.

## 2. Correct Beacon Recovery Instead of Disabling It

Patch A demonstrated that Beacon Recovery can be bypassed.

The current objective is more demanding:

> Preserve legitimate Beacon Recovery while correcting the conditions that allow invalid or historical measurements to trigger it.

The current C-C candidate has completed the first two qualification stages:

```text
static reverse engineering                 completed
        ↓
counterexample / falsification review      completed
        ↓
experimental build                         next
        ↓
independent binary / GBL verification
        ↓
controlled hardware A/B test
        ↓
long-term battery test
```

No known static blocker remains in the reviewed C-C design. The next step is therefore to create the experimental firmware artifact using a growth-aware GBL build process, then independently reparse and verify the resulting container before any hardware flashing is considered.

Passing static qualification does **not** establish runtime correctness or battery-life improvement. Those claims require controlled hardware testing and long-term observation.

---

# Documentation

Detailed research documentation is maintained under `docs/`.

Public documentation contains reviewed findings, methodology, and reproducible technical results.

Typical structure:

```text
docs/
├── patch/
├── reverse-engineering/
└── testing/
```

Internal working notes, temporary reverse-engineering reports, unreviewed analysis output, and local development material are intentionally kept outside the public repository history.

The repository is intended to publish **research results**, not every intermediate analysis artifact.

---

# Firmware Patcher

A separate repository contains tooling for locally applying the currently released experimental firmware modifications:

https://github.com/AbleMonster/Shelly-TRV-Gen1-2.2.4-patcher

The current experimental patcher applies the previously developed Patch A + Patch B combination.

The patcher uses fail-closed validation and verifies the supported input before modification.

It does **not** distribute Shelly firmware.

Users must provide their own legitimately obtained supported firmware image.

The patched image is generated locally.

Patch C is not part of the released patcher unless and until its implementation has completed the required qualification process.

---

# Repository Scope

This repository is intended to contain:

- reviewed analysis results
- technical documentation
- experimental methodology
- small patch descriptions
- independently developed research tooling
- sanitized runtime results
- battery-test methodology
- reproducible findings

It is not intended to redistribute proprietary Shelly firmware.

The repository should not contain:

- original Shelly firmware images
- complete modified Shelly firmware images
- proprietary extracted application images
- large raw disassembly dumps
- unreviewed reverse-engineering output
- credentials or private device information

General principle:

> Publish the results of the analysis, not the disassembled firmware.

---

# Contributing

Contributions are welcome when they improve reproducibility, challenge existing conclusions, provide independent runtime evidence, or identify alternative interpretations.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting an issue or pull request.

Research contributions should clearly distinguish:

- PROVEN
- STRONGLY SUPPORTED
- INFERENCE
- UNKNOWN

Contradicting an existing conclusion is explicitly welcome when supported by reproducible evidence.

---

# Security

Security-sensitive findings should not be disclosed through a public issue.

See [SECURITY.md](SECURITY.md) for the project's reporting policy and private contact information.

This project is independent research and is not an official Shelly security or support channel.

---

# Safety and Experimental Nature

All firmware modifications in this project are experimental.

Modified firmware can potentially:

- make a device unreachable
- cause unexpected WLAN behavior
- affect battery life
- affect thermostat operation
- require recovery or reflashing

Do not deploy experimental firmware where failure could create an unsafe condition.

Always retain a known-good recovery path.

Testing should only be performed on devices and networks you own or are authorized to use.

---

# Research Principle

This project intentionally separates:

```text
observation
    ↓
reverse engineering
    ↓
hypothesis
    ↓
falsification
    ↓
controlled modification
    ↓
runtime validation
    ↓
long-term observation
```

A plausible mechanism is not treated as a proven battery-drain cause merely because it exists in the firmware.

Likewise:

```text
Patch works
```

means that the targeted firmware behavior changed as intended.

It does **not** automatically mean:

```text
Battery drain fixed
```

The objective is not simply to remove activity from the firmware.

The objective is to understand why that activity exists, determine whether its control logic is valid, preserve legitimate functionality, and correct only the behavior that the available evidence demonstrates is defective.

---

# License

Original code, scripts, tooling, documentation, and other copyrightable material created specifically for this project are licensed under the GNU General Public License v3.0 only (`GPL-3.0-only`), unless otherwise stated.

See [LICENSE](LICENSE) for the full license terms.

## Third-Party Firmware and Intellectual Property

This license applies only to material for which the contributors to this repository hold the necessary rights.

Shelly firmware, firmware components, trademarks, product names, and other third-party intellectual property remain the property of their respective owners and are not licensed under the GPL by this project.

This repository does not distribute original or modified Shelly firmware images.

Reverse-engineering documentation, independently developed tools, patch descriptions, offsets, and small technical excerpts are provided for research, interoperability, debugging, and reproducibility purposes.

Users are responsible for obtaining any required firmware from legitimate sources and for complying with applicable licenses and laws.

---

# Project Independence

This project is an independent community research effort.

It is not affiliated with, sponsored by, or endorsed by Shelly or Shelly Group.

Product names and trademarks are used only to identify the devices and firmware being studied.