# Battery Reporting and Low-Voltage Shutdown

## Scope

This document describes how the Shelly TRV Gen1 firmware measures, stores, reports and reacts to battery voltage.

The analysis covers:

- battery-voltage acquisition
- the relationship between voltage and displayed percentage
- limitations of the percentage value
- the low-voltage shutdown threshold
- shutdown behavior below the threshold
- cross-version comparison
- ADC sampling behavior
- the demonstrated PA3 timeout cleanup defect
- deferred battery-reporting observations
- implications for long-term battery testing

The investigated firmware generations include:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

The main conclusion is:

> The displayed battery percentage is not a coulomb-counted measure of consumed energy. It is derived from the firmware's cached battery-voltage value, while the actual low-voltage shutdown decision uses an approximately 3000 mV threshold.

---

# 1. Battery Telemetry

The Shelly TRV exposes battery information through its normal runtime status.

Important values include:

```text
bat.value
bat.voltage
```

Conceptually:

```text
battery cells
    |
    v
ADC measurement
    |
    v
battery voltage value
    |
    +----> reported voltage
    |
    +----> percentage mapping
             |
             v
         bat.value
```

These two reported values originate from the same general battery-measurement path but have different interpretation.

---

# 2. Battery Voltage

The reported voltage is the more useful short-term battery diagnostic.

For example:

```text
3.700 V
3.600 V
3.500 V
```

represent measured battery-voltage states rather than integrated energy consumption.

However, voltage is still affected by:

- state of charge
- current load
- valve motor operation
- WLAN activity
- temperature
- internal cell resistance
- cell age
- recent charging
- voltage relaxation after load

Therefore:

```text
voltage
```

is useful for observing trends but is not itself a direct remaining-capacity measurement.

---

# 3. Battery Percentage Is Not Coulomb Counting

No evidence has been found that the TRV maintains a coulomb-counted battery-energy state.

The displayed percentage behaves as a mapping from the currently cached battery-voltage value.

Conceptually:

```text
cached millivolts
       |
       v
integer percentage mapping
       |
       v
displayed battery %
```

This means the percentage is effectively stateless with respect to accumulated energy consumption.

It does not continuously integrate:

```text
current × time
```

and therefore should not be interpreted as a fuel gauge in the coulomb-counting sense.

---

# 4. Consequences of Stateless Percentage Mapping

Because percentage is derived from voltage:

```text
battery = 100 %
```

does not mean that two physical battery packs contain identical usable energy.

Likewise:

```text
battery = 50 %
```

does not establish that half of the original usable capacity remains.

Two physical TRVs can report the same percentage while differing in:

- cell capacity
- internal resistance
- age
- temperature
- load
- discharge history

This is one reason the project uses voltage as the primary short-term trend metric.

---

# 5. Percentage Quantization

A voltage-derived integer percentage naturally changes in discrete steps.

Therefore the reported value can remain unchanged for some time and then change by one or more percentage points.

For example:

```text
74 %
74 %
74 %
73 %
```

does not imply that no energy was consumed during the three earlier samples.

It only means the mapped voltage remained inside the same percentage range.

Percentage is therefore best treated as:

```text
coarse user-facing state information
```

rather than precision battery telemetry.

---

# 6. Voltage Rebound

Battery voltage can rise again after a temporary load is removed.

The project has observed short-term sequences where a lower voltage was later followed by a slightly higher reading without charging.

This can occur after:

- valve movement
- calibration
- WLAN activity
- other transient load

Conceptually:

```text
resting battery
     |
     v
temporary load
     |
     v
voltage sag
     |
     v
load removed
     |
     v
partial voltage recovery
```

Therefore short-term voltage decline must not be extrapolated linearly into expected battery lifetime.

---

# 7. API Voltage vs. External Measurement

Battery measurements from different sources must remain separated.

For example:

```text
external meter immediately after charging
```

and:

```text
TRV API voltage later under operating load
```

are not directly interchangeable.

A valid trend should use one measurement source consistently.

Recommended labels are:

```text
TRV API
```

or:

```text
external meter
```

A continuous battery curve should not be constructed by mixing the two without explicitly accounting for the measurement change.

---

# 8. Battery Pack

The investigated TRV battery pack is identified as:

```text
NCR18650BD
```

with nominal marking:

```text
3.7 V
24.05 Wh
```

From the nominal energy and cell voltage, the pack is consistent with approximately:

```text
~6.5 Ah
```

and a likely:

```text
1S2P
```

cell arrangement.

This capacity value is derived from nominal pack specifications.

It is not an in-device measurement of the remaining usable capacity of any individual test pack.

---

# 9. Low-Voltage Threshold

Across the investigated firmware generations:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

the relevant low-voltage shutdown threshold is approximately:

```text
3000 mV
```

or:

```text
3.000 V
```

The consistency of this threshold across the investigated versions is important.

It means the later 2.2.4 battery behavior is not explained by a newly introduced higher low-voltage shutdown threshold.

---

# 10. Shutdown Decision

Conceptually, the relevant firmware decision is:

```text
battery voltage
       |
       v
below ~3000 mV?
       |
   +---+---+
   |       |
  no      yes
   |       |
normal     v
operation low-battery shutdown path
```

The threshold acts on the firmware's measured/cached battery voltage.

The displayed percentage is not the primary shutdown criterion.

---

# 11. Displayed `0 %` Is Not the Shutdown Threshold

A device can report:

```text
0 %
```

while the measured voltage remains above:

```text
3000 mV
```

For example, one historical full-discharge test ended its final available telemetry around:

```text
battery = 0 %
voltage = 3.116 V
```

The percentage display had already reached zero even though the firmware's approximately 3000 mV shutdown boundary had not yet been crossed in that final captured sample.

Therefore:

```text
0 %
```

must not be interpreted as:

```text
firmware shutdown threshold reached
```

---

# 12. Low-Voltage Countdown

Once the low-voltage path is entered, the host does not immediately stop execution.

The reconstructed logic includes a short countdown corresponding to approximately:

```text
3 serviced seconds
```

before the later shutdown action.

Conceptually:

```text
voltage below threshold
       |
       v
low-battery state
       |
       v
~3 serviced-second countdown
       |
       v
PA0 LOW
```

This delay should be understood as firmware execution time based on the relevant serviced periodic path.

It is not a precision real-time shutdown guarantee under every scheduler condition.

---

# 13. PA0 Low

At the end of the low-voltage countdown, firmware drives:

```text
PA0 LOW
```

This is the strongest host-side observable action in the reconstructed shutdown sequence.

The likely purpose is related to board-level power control.

However, the project has not independently verified the complete schematic/electrical consequence of PA0 LOW on the physical TRV power rails.

Therefore the safe statement is:

> The firmware drives PA0 LOW as part of the low-voltage shutdown sequence.

The stronger statement:

```text
PA0 LOW physically disconnects every TRV power rail
```

has not been independently established.

---

# 14. Firmware 2.2.4 Post-Shutdown Host Behavior

In firmware 2.2.4, after the low-voltage shutdown action, the main-task path enters a busy-loop state.

Conceptually:

```text
low-voltage threshold
       |
       v
countdown
       |
       v
PA0 LOW
       |
       v
main-task busy loop
```

This does not necessarily imply that the complete physical device continues consuming normal operating current.

The actual board-level state depends on what PA0 controls electrically.

The firmware behavior and the board-level power consequence must therefore remain separate conclusions.

---

# 15. Host Behavior vs. Board Power State

There are two distinct questions:

```text
What does the MCU firmware execute?
```

and:

```text
What remains electrically powered on the board?
```

Reverse engineering can establish the first from firmware.

The second requires:

- schematic knowledge
- board tracing
- direct electrical measurement
- or equivalent hardware evidence

Therefore the project currently does not claim the complete physical current after the PA0 shutdown action.

---

# 16. Cross-Version Shutdown Comparison

The approximately:

```text
3000 mV
```

low-voltage threshold is present across:

```text
2.1.0
2.1.3
2.1.8
2.2.4
```

This is useful because the historical battery-drain problem occurred across more than one of these generations.

The shutdown threshold itself therefore does not currently provide a convincing explanation for the firmware-dependent drain behavior.

---

# 17. Battery Sampling Path

Battery voltage is obtained through the host ADC path.

The firmware performs a sequence conceptually similar to:

```text
prepare battery measurement
        |
        v
enable required measurement path
        |
        v
start ADC acquisition
        |
        v
wait for result / timeout
        |
        v
process ADC result
        |
        v
store battery value
        |
        v
cleanup measurement resources
```

Correct cleanup is important because battery measurement should be a short-lived operation.

A resource left active after a timeout could create an unintended persistent power cost.

---

# 18. P01 — PA3 Timeout Cleanup Defect

A demonstrated battery-ADC timeout cleanup defect was identified in the host firmware.

It is tracked as:

```text
P01
```

The relevant problem is:

> The ADC timeout path can leave PA3 in the measurement-related state instead of releasing it consistently with the normal completion path.

The defect is a lifecycle asymmetry:

```text
normal completion
    |
    v
resource released

timeout
    |
    v
resource not fully released
```

This violates the expected invariant:

> Temporary battery-measurement resources should be retired on both success and timeout.

---

# 19. P01 Correction

The P01 correction restores the missing PA3 release on the timeout path.

Conceptually:

```text
ADC measurement
   |
   +---- success
   |       |
   |       v
   |    release PA3
   |
   +---- timeout
           |
           v
        release PA3
```

The correction does not change:

- normal ADC conversion
- battery-voltage scaling
- percentage mapping
- low-voltage threshold
- shutdown policy

It corrects cleanup behavior only.

---

# 20. P01 Qualification

P01 has been independently qualified offline.

Qualification included:

```text
128 native cases
+
6 additional focused cases
```

together with composition testing in the B2.2 candidate.

No unexplained application differences were accepted.

P01 is included in:

```text
B2.2
```

It is not included in the currently deployed:

```text
B2.1_OBS
```

long-term population.

Therefore no current hardware battery-runtime claim can yet be attributed to P01.

---

# 21. P11 — Transient Raw ADC Publication

A separate observation exists in the battery sampling path.

During sampling, the shared field later used as the millivolt battery value can transiently contain a raw ADC result before conversion/scaling is complete.

This candidate is tracked as:

```text
P11
```

The important distinction is:

```text
temporary internal representation
```

versus:

```text
stable reported battery value
```

The temporary raw value creates a potential publication/race concern if another path reads the shared field during the narrow conversion interval.

---

# 22. P11 Status

P11 is currently:

```text
DEFERRED
```

It is not part of B2.2.

The project has not demonstrated that this transient state causes the historical battery drain.

It should therefore not be described as:

```text
battery-drain root cause
```

or:

```text
known incorrect long-term voltage reporting
```

The supported statement is narrower:

> A transient raw-ADC representation exists in the shared battery-value path and remains a candidate for later robustness analysis.

---

# 23. Percentage Mapping and P11 Are Different Issues

The percentage mapping is normal firmware behavior:

```text
millivolts
    |
    v
percentage conversion
```

P11 concerns a transient state before the stable millivolt representation is complete.

These issues must not be conflated.

The percentage being stateless is not itself a firmware defect.

It is primarily a telemetry interpretation issue.

---

# 24. Battery Reporting vs. Battery Drain

A device can exhibit:

```text
incorrect or coarse battery reporting
```

without actually consuming excessive power.

Likewise, a device can exhibit:

```text
real excessive battery consumption
```

while still reporting voltage correctly.

Therefore the investigation separates:

```text
battery reporting
```

from:

```text
battery consumption
```

and from:

```text
low-voltage shutdown
```

These are related but distinct firmware domains.

---

# 25. Historical `.77` Endpoint

A useful historical example is TRV `.77` during the Patch-B full-discharge experiment.

Final captured telemetry was approximately:

```text
runtime      ~9.23 days
battery      0 %
voltage      3.116 V
```

The device became unavailable shortly afterward.

This demonstrates two important points.

First:

```text
0 %
```

can be reported before the final approximately:

```text
3000 mV
```

firmware threshold is observed.

Second, the last captured status does not necessarily equal the actual voltage at the instant of final shutdown.

The device may continue operating after the final successful telemetry sample.

---

# 26. Battery Testing Implications

For long-term testing, the preferred comparison is:

```text
voltage trajectory
```

with:

```text
percentage
```

used as secondary context.

A useful battery record should include:

```text
timestamp
firmware/build
physical device
battery voltage
battery percentage
uptime
valve workload
reboot/reconnect state
WLAN context
```

Where relevant, it should also include:

```text
Beacon Recovery activity
observer state
```

---

# 27. Avoid Percentage-Only Conclusions

The following comparison is weak:

```text
Device A:
80 % -> 70 %

Device B:
80 % -> 75 %
```

because it ignores:

- actual voltage
- battery condition
- voltage-to-percentage quantization
- valve workload
- RF conditions
- elapsed runtime
- battery temperature

A stronger comparison uses:

```text
voltage
+
time
+
workload
+
firmware identity
```

---

# 28. Avoid Linear Lifetime Extrapolation

For example:

```text
-20 mV in 12 hours
```

should not automatically become:

```text
-40 mV/day
```

and then:

```text
predicted shutdown date
```

because lithium battery voltage curves are nonlinear and load-dependent.

Short-term voltage is best used to detect:

- gross abnormal drain
- relative direction
- abrupt changes
- long-term trend differences

not precise lifetime from a few hours of data.

---

# 29. Relation to Current B2.1_OBS Testing

The current active long-term population uses:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

B2.1_OBS contains:

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
+
PM52 -> cmd66 observer
```

It does not contain P01.

Therefore the current test primarily answers whether the earlier demonstrated corrected platform avoids the historical rapid-drain phenotype.

It does not test the incremental battery effect of the later P01 ADC cleanup correction.

---

# 30. Relation to B2.2

B2.2 additionally contains:

```text
Calibration Restore Guard
P01 PA3 release
P02 I2C timeout retirement
P03 GPIO interrupt-mask correction
```

alongside the B2.1 correction set.

Its current disposition is:

```text
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

B2.2 has not been flashed to the active long-term hardware population.

Therefore:

> No battery-runtime improvement is currently claimed for P01 or B2.2.

---

# 31. Why P01 Belongs in B2.2

P01 satisfies the correction-selection criteria used for B2.2:

```text
demonstrated
+
safely correctable
+
independently qualified
+
composition-qualified
```

A timeout resource-cleanup defect is undesirable even without proof that it dominates battery drain.

Correcting it removes a demonstrated lifecycle asymmetry from the final candidate.

---

# 32. What Has Been Established

The current battery-path reverse engineering establishes the following.

### Battery percentage is voltage-derived

It should not be treated as coulomb counting.

### Percentage is coarse

It is less precise than the underlying voltage trend.

### Voltage is still load-dependent

It is not direct remaining capacity.

### The low-voltage threshold is approximately 3000 mV

This is consistent across the investigated 2.1.x and 2.2.4 releases.

### Displayed `0 %` and shutdown are not identical events

A device can report 0% while remaining above the final low-voltage threshold.

### Low-voltage handling contains a short countdown

The reconstructed host path waits approximately three serviced seconds before PA0 LOW.

### Firmware 2.2.4 then enters a main-task busy loop

The board-level power consequence remains separately unverified.

### The ADC timeout path contains a real cleanup defect

P01 corrects the missing PA3 release.

### P01 is offline-qualified

It is part of B2.2 but not the current B2.1_OBS hardware population.

### A transient raw-ADC publication state exists

P11 remains deferred.

---

# 33. What Has Not Been Established

The project does not currently claim:

- that displayed percentage is a precise capacity gauge
- that voltage alone gives remaining mAh
- that every battery pack has equal capacity
- that 0% means immediate physical shutdown
- that PA0 LOW has been independently proven to disconnect every board rail
- that the post-PA0 busy loop represents actual full-device current
- that P01 caused the historical drain
- that P11 caused the historical drain
- that B2.2 improves battery life
- that the exact current cost of the ADC timeout defect is known
- that the historical battery-drain root cause has been proven

---

# 34. Current Battery Reporting Model

The current model is:

```text
physical battery
       |
       v
battery measurement path
       |
       v
ADC result
       |
       v
scaled/cached millivolts
       |
       +-------------------+
       |                   |
       v                   v
reported voltage     percentage mapping
                           |
                           v
                     reported battery %
```

Low-voltage handling is separate:

```text
cached/measured voltage
       |
       v
< ~3000 mV ?
       |
       +---- no ----> normal operation
       |
       +---- yes
               |
               v
        low-battery path
               |
               v
       ~3 serviced seconds
               |
               v
            PA0 LOW
               |
               v
       2.2.4 main-task
          busy loop
```

ADC timeout cleanup is another distinct path:

```text
ADC measurement
       |
       +---- complete ----> cleanup
       |
       +---- timeout
               |
               v
        stock cleanup defect
               |
               v
          P01 correction
```

---

# 35. Current Research Position

Battery reporting is now sufficiently understood to avoid several common interpretation errors.

The project should use:

```text
voltage
```

as the primary short-term battery telemetry,

```text
percentage
```

as secondary user-facing information,

and:

```text
long-term runtime
```

as the basis for endurance conclusions.

The active hardware question remains:

> Does B2.1_OBS remain stable over long-term real-world operation compared with the stock 2.2.4 control?

If a corrected device drains, the first-fault observer data should be analyzed before changing the test variables.

If the corrected population remains stable, the next stage is observer removal and observer-free hardware regression.

The battery-reporting implementation itself currently provides no evidence sufficient to claim the complete historical battery-drain root cause.

---

# Related Documents

Long-term battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Power-management analysis:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

PM lifecycle:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

Patch overview:

[`../patch/README.md`](../patch/README.md)

---

# Research Method

This analysis is based on:

- static ARM Thumb reverse engineering
- cross-version firmware comparison
- battery ADC control-flow analysis
- shutdown-path reconstruction
- runtime `/status` telemetry
- long-term battery logs
- controlled experimental firmware qualification

Where firmware behavior is known but the corresponding physical board-level effect has not been independently measured, the two are explicitly separated.

Historical runtime measurements are not retroactively reassigned to later firmware builds.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

Battery telemetry and reverse-engineered firmware behavior described here are research observations, not manufacturer specifications.

Experimental firmware modifications should only be used on hardware where recovery or reflashing is possible.