# Firmware Comparison – Shelly TRV Gen1

## Scope

This document compares the WLAN and power-management behavior of the
investigated Shelly TRV Gen1 (`SHTRV-01`) firmware generations.

The primary firmware versions are:

| Firmware | Build | Role |
|---|---|---|
| 2.1.0 | `20211223-144805/v2.1.0@d30148ec` | oldest detailed reference |
| 2.1.3 | `20220202-080736/v2.1.3@d255ad74` | early comparison |
| 2.1.8 | `20220811-152343/v2.1.8@5afc928c` | later comparison / drain reference |
| 2.2.4 | `20240619-130912/v2.2.4@ee290818` | primary research target |

The purpose of the comparison is not to select one firmware version and label
it as the origin of the historical battery-drain problem.

Battery drain has been observed on more than one firmware generation.

Instead, the comparison is intended to determine:

- which WLAN and power-management mechanisms are shared between generations
- which mechanisms were added later
- which firmware defects are version-specific
- which defects belong to the older common architecture
- how the FMAC and protected WF200 firmware changed
- which mechanisms can explain version-specific behavior
- which mechanisms cannot explain the complete historical battery-drain problem

The comparison combines native ARM Thumb analysis, binary comparison, runtime
testing, packet captures and controlled experimental firmware.

Detailed analyses are kept in the dedicated reverse-engineering documents.
This file focuses on chronology and cross-version interpretation.

---

# High-Level Chronology

The investigated firmware generations show an incremental evolution rather than
a complete redesign of the WLAN and host power-management architecture.

At a high level:

```text
2.1.0
  |
  | common WLAN / host sleep architecture
  | Fast Power Save
  | shared sleep-blocker accounting
  | permanent B3 contribution
  | PA8 WLAN sleep gate
  | Final-Sleep failure path
  |
  v
2.1.3
  |
  | recurring connected mDNS restart
  | state-5 / psovrd2
  | PM/event changes
  |
  v
2.1.8
  |
  | mDNS cadence changed to ~180 s
  | post-association PM sequencing changed
  | FMAC / WF200 generation updated
  |
  v
2.2.4
  |
  | expanded WF200 statistics
  | real_beacon_skip
  | Beacon Recovery
  | additional PM ownership / retry behavior
  | newer FMAC / WF200 generation
  |
  v
experimental investigation
  |
  +-- C-C
  |     correct Beacon Recovery validity defects
  |
  +-- A1
  |     correct identified PM ownership /
  |     settlement / failure-path defects
  |
  +-- WF200 3.18.0
        newer Silicon Labs radio firmware
```

This chronology provides an important constraint:

> A mechanism introduced only in firmware 2.2.4 cannot by itself explain
> battery drain that also occurs on earlier firmware.

This applies particularly to the 2.2.4 Beacon Recovery mechanism.

At the same time, later firmware can introduce additional drain mechanisms or
amplify a problem already present in the older architecture.

The current evidence therefore supports a multi-mechanism model rather than a
single regression boundary.

---

# Firmware 2.1.0

Firmware 2.1.0 is the oldest firmware for which the current project has a
detailed host-side comparison.

It already contains the basic architecture that remains recognizable in later
versions:

- mDNS responder functionality
- WF200 WLAN power management
- connected Fast Power Save
- host/WLAN wake-resource coordination
- EFM32GG11 sleep-mode selection
- shared sleep-blocker counters
- PA8-based WLAN sleep gating
- conditional failure paths around WLAN sleep transitions

Several later recurring mechanisms are absent or have not been identified in
the same form.

This makes 2.1.0 useful for separating older architectural behavior from later
additions.

---

## mDNS in 2.1.0

The mDNS responder already exists in firmware 2.1.0.

Therefore:

```text
2.1.0 has no mDNS
```

would be incorrect.

The relevant difference is that the later recurring connected maintenance path
that repeatedly restarts mDNS probing has not been identified in the analyzed
2.1.0 host firmware.

A simultaneous runtime packet capture of approximately 13 minutes also did not
show the characteristic periodic mDNS bursts observed on later firmware.

This does not mean that 2.1.0 never transmits mDNS traffic.

It means that the recurring connected restart mechanism found in later
firmware was neither identified statically nor observed during that test.

---

# Common Host Sleep Architecture

Later reverse engineering showed that several parts of the host sleep
architecture previously investigated mainly in 2.2.4 are substantially older.

This is important for the firmware comparison because it changes which findings
can be treated as 2.2.4 regressions.

The host MCU is an EFM32GG11.

The normal idle path ultimately selects between:

```text
EM1
EM2
EM3
```

using shared blocker state.

The relevant simplified policy is:

```text
B2 != 0
    -> EM1 maximum

B2 == 0 && B3 != 0
    -> EM2

B2 == 0 && B3 == 0
    -> EM3
```

This general architecture exists in the investigated older firmware as well as
2.2.4.

---

## Permanent B3 Contribution

The host installs a B3 contribution during normal startup before the scheduler
begins normal operation.

This initially looked interesting because it prevents the normal idle path from
selecting EM3.

Further analysis showed that this behavior is intentional and technically
required by the stock clock configuration.

The TRV configures the RTC/tickless timebase from the LFXO.

The EM3 entry path disables both:

```text
LFXO
LFRCO
```

while EM2 keeps the required low-frequency clock available.

With the unchanged stock clock configuration, allowing normal idle execution to
enter EM3 would therefore stop the clock used for scheduler wake-up and
tickless time reconstruction.

The normal intended deep idle state is consequently:

```text
EM2
```

not EM3.

The permanent B3 contribution should therefore not be treated as a battery
drain bug.

Enabling EM3 would require a separate clock/timebase redesign rather than
simply removing B3.

The same broad B3/EM2 policy is already present in the older architecture.

---

# Shared B2 Sleep-Blocker Counter

B2 is not a Boolean flag.

It is a shared reference counter representing the number of software owners
that currently require the host to remain at EM1 rather than entering EM2.

Conceptually:

```text
B2 = 0
    -> no known owner requires EM1
    -> EM2 may be allowed

B2 = 1
    -> one owner requires EM1

B2 = 2
    -> two simultaneous owners require EM1
```

This is necessary because several subsystems can require the restriction at the
same time.

Known users include paths associated with:

- WLAN/O ownership
- motor operation
- manual DTIM handling
- OTA
- initialization and WLAN management

The use of a reference counter is therefore correct in principle.

The problem is how the counter is updated.

---

## B2 Read-Modify-Write Concurrency Defect

Detailed analysis of firmware 2.2.4 identified a separate host-side correctness
problem in the shared B2 accounting.

Not every B2 increment/decrement operation is serialized.

Some paths effectively perform:

```c
old = B2;
new = old + 1;
B2 = new;
```

or the corresponding decrement while task preemption can occur between the
load and store.

Other B2 operations are protected by a saved-PRIMASK critical section.

This combination allows real task schedules to corrupt the aggregate reference
count.

This is not merely a theoretical multi-threading concern.

The relevant callers execute in actual RTOS task contexts where a scheduler
switch can occur between the unprotected load and store.

---

## Phantom B2 Contribution

One verified 2.2.4 execution sequence is:

```text
B2 = 1
WLAN/O owns the existing contribution

task A:
    loads B2 = 1
    intends to add another owner

        ↓ task switch

task B:
    releases WLAN/O
    B2: 1 -> 0

        ↓ task switch back

task A:
    stores stale 1 + 1
    B2 = 2
```

The correct result should be:

```text
B2 = 1
```

because only task A still owns a contribution.

When task A later performs its normal release:

```text
B2: 2 -> 1
```

the counter remains:

```text
B2 = 1
```

despite no remaining legitimate owner.

The sleep selector then continues to see:

```text
B2 != 0
```

and limits idle execution to:

```text
EM1
```

instead of the intended EM2.

This creates a plausible persistent host-power failure state:

```text
lost-update race
      |
      v
phantom B2 contribution
      |
      v
B2 never returns to zero
      |
      v
EM2 blocked
      |
      v
host remains limited to EM1
```

The code defect and the execution schedule are established.

Its occurrence frequency on physical devices and its battery-energy impact are
still being measured.

---

## Lost B2 Contribution

The opposite corruption is also possible.

For example:

```text
B2 = 0

motor task:
    loads B2 = 0

        ↓ task switch

WLAN/O task:
    acquires contribution
    B2: 0 -> 1

        ↓ task switch back

motor task:
    stores stale 0 + 1
    B2 = 1
```

The correct value should now be:

```text
B2 = 2
```

because both owners are active.

If WLAN/O later releases:

```text
B2: 1 -> 0
```

the host can see:

```text
B2 = 0
```

while the motor still owns an EM1 requirement.

The sleep selector can therefore permit EM2 earlier than intended.

This is primarily a correctness problem rather than an obvious battery-drain
mechanism, but it demonstrates that the shared blocker state cannot always be
trusted after concurrent updates.

---

## Cross-Version Relevance of B2

The shared blocker architecture and unprotected aggregate helper pattern are
not unique to firmware 2.2.4.

Firmware 2.1.0 also contains:

- equivalent B2/B3 counter architecture
- equivalent sleep selector semantics
- unmasked aggregate blocker helpers
- the permanent startup B3 contribution
- the same broad EM2/EM3 dispatch structure

This means the underlying concurrency weakness belongs to the older common
architecture rather than being introduced by Beacon Recovery in 2.2.4.

However, the complete concrete task-level execution witness has currently been
closed in detail for 2.2.4.

The corresponding full caller/scheduler proof has not yet been completed for
every earlier firmware generation.

The safe cross-version conclusion is therefore:

> The vulnerable blocker-accounting architecture predates 2.2.4, while the
> fully reconstructed real-task race schedules currently refer to 2.2.4.

This makes B2 particularly interesting for the historical battery-drain
investigation because it is one of the identified host-side mechanisms that
could potentially exist across firmware generations.

Runtime occurrence still needs to be demonstrated.

---

# PA8 WLAN Sleep Gate

The host sleep path contains another mechanism independent of B2.

PA8 is configured as an input with pull-down and participates in the WLAN
interrupt/notification path.

Runtime handling shows that a PA8 event is forwarded into the WLAN bus/RX
worker.

The sleep callback checks PA8 immediately before low-power entry.

If PA8 is HIGH, the firmware vetoes WFI.

Conceptually:

```text
normal sleep decision
      |
      v
B2/B3 select allowed mode
      |
      v
check PA8
      |
      +---- LOW  -> continue toward WFI
      |
      +---- HIGH -> do not execute WFI
```

PA8 therefore represents a different type of sleep restriction from B2.

B2 answers approximately:

```text
How many software owners currently require EM1?
```

PA8 answers approximately:

```text
Is the WLAN host-notification line currently asserted?
```

PA8 is not a reference counter and should not be treated as one.

The available code strongly supports its role as the WLAN host-notification
path, although the exact schematic signal name and electrical implementation
have not been independently recovered.

A HIGH PA8 state preventing WFI is not itself a firmware bug.

It is consistent with preventing the host from sleeping while the WLAN device
has pending work.

The important runtime question is whether PA8 can remain asserted or repeatedly
veto sleep for unexpectedly long periods during a battery-drain episode.

That question requires runtime observation.

---

# Final-Sleep Failure Path

The older WLAN power-management architecture also contains a conditional
failure path around the final device-sleep operation.

Under the normal path:

```text
wake / acquire WLAN resource
      |
      v
perform WLAN PM operation
      |
      v
put device back to sleep
      |
      v
release resource
```

Some failure exits occur before the expected cleanup/release has completed.

This can retain a sleep-blocking contribution.

The fundamental mechanism predates 2.2.4.

It therefore cannot by itself define a 2.2.4 regression boundary.

Later firmware changes can still alter how often such a path is reached.

The A1 experimental correction addresses identified ownership and failure-path
problems of this type in the 2.2.4 implementation.

---

# Firmware 2.1.0 → 2.1.3

The transition from 2.1.0 to 2.1.3 adds several host-side WLAN behaviors while
retaining the older underlying architecture.

Relevant changes include:

```text
2.1.0
  |
  v
2.1.3
  |
  +-- recurring connected mDNS restart
  +-- state-5 / psovrd2 mechanism
  +-- named active power-save override
  +-- wake ACK timing changes
  +-- event-handling changes
```

The normal state-3 Fast Power Save path remains recognizably related to the
earlier implementation.

---

# Periodic mDNS Restart in 2.1.3

The most obvious new recurring connected workload in 2.1.3 is the periodic
mDNS restart.

The connected maintenance path periodically invokes the equivalent of:

```text
mdns_resp_restart()
```

which restarts the probing sequence:

```text
connected maintenance
      |
      v
restart mDNS probing
      |
      v
probe
probe
probe
      |
      v
announcement
```

Packet capture confirmed recurring behavior at approximately:

```text
60 seconds
```

on the tested 2.1.3 configuration.

The important change is therefore not:

```text
mDNS introduced
```

but:

```text
recurring connected mDNS probing restart introduced
```

The quantitative battery cost of this workload has not been isolated.

---

# State 5 / `psovrd2`

Firmware 2.1.3 also contains the identified temporary WLAN power-management
override associated with state 5.

Known entry paths include:

```text
/psovrd2
```

and the corresponding cloud-side command.

The mechanism requests approximately:

```text
Fast Power Save
beacon skip = 10
```

for a temporary period.

The associated countdown is initialized to:

```text
180
```

This should not be interpreted as the host MCU intentionally remaining fully
awake for 180 seconds.

State 5 changes WLAN power-management configuration.

The normal host low-power path can continue operating while the override is
active.

No normal autonomous idle path has been identified that continuously enters
state 5.

---

# Firmware 2.1.3 → 2.1.8

The transition to 2.1.8 changes both host-side behavior and the WLAN
components.

Relevant differences include:

- changed periodic mDNS cadence
- changed post-association PM sequencing
- updated FMAC
- updated protected WF200 firmware
- additional WLAN state-restoration behavior

This transition is particularly relevant because battery drain has also been
observed in practical testing on firmware 2.1.8.

---

# mDNS Cadence in 2.1.8

The recurring connected mDNS restart remains present in 2.1.8.

The scheduling changes from the approximately one-minute behavior seen in
2.1.3.

Static analysis identifies a modulo-three gate in the connected maintenance
path.

With the underlying minute service this produces an intended interval of
approximately:

```text
3 × 60 s = 180 s
```

The three-minute mDNS behavior is therefore not unique to firmware 2.2.4.

It is already present by 2.1.8.

---

# Post-Association PM Restoration in 2.1.8

Firmware 2.1.8 changes the sequencing after association.

The identified path contains an intermediate PM restoration state:

```text
association
      |
      v
intermediate PM restoration
      |
      v
bounded delay
      |
      v
normal connected state 3
```

The identified delay is approximately:

```text
100 scheduler ticks
```

before restoration toward the normal state-3 configuration.

This is a real implementation change.

Its battery-energy effect has not been measured independently.

---

# WLAN Component Evolution

The investigated WLAN component progression is:

| Firmware | FMAC | Protected WF200 firmware |
|---|---:|---:|
| 2.1.0 | 3.3.2 | 3.12.2 |
| 2.1.3 | 3.3.2 | 3.12.2 |
| 2.1.8 | 3.4.1 | 3.14.0 |
| 2.2.4 | 3.7.0 | 3.16.1 |

This provides useful separation points.

The transition:

```text
2.1.0 -> 2.1.3
```

contains substantial host-side changes while retaining the same investigated
FMAC/WF200 generation.

The transition:

```text
2.1.3 -> 2.1.8
```

changes both host behavior and WLAN components.

The transition:

```text
2.1.8 -> 2.2.4
```

again changes both.

A battery-runtime difference between these firmware generations therefore
cannot automatically be assigned either to host code or protected radio
firmware without additional evidence.

---

# Firmware 2.1.8 and Battery Drain

Practical battery drain has been observed on firmware 2.1.8.

This is an important constraint because the later 2.2.4 Beacon Recovery
mechanism has not been identified in the same form in 2.1.8.

Therefore:

```text
2.2.4 Beacon Recovery
```

cannot explain:

```text
all historical Shelly TRV Gen1 battery drain
```

This does not identify the mechanism responsible for the 2.1.8 behavior.

Potential common contributors include:

- host sleep-blocker accounting
- WLAN power-management failure paths
- protected WF200 behavior
- recurring network activity
- cloud/network workload
- radio environment
- valve/motor activity
- other unidentified mechanisms

The B2 concurrency finding is especially relevant because the underlying
blocker architecture predates 2.2.4.

Whether that defect actually occurs during a 2.1.x drain episode has not yet
been demonstrated.

---

# Firmware 2.1.8 → 2.2.4

Firmware 2.2.4 expands both WLAN diagnostics and power-management behavior.

Relevant additions include:

```text
2.1.8
  |
  v
2.2.4
  |
  +-- expanded WF200 statistics handling
  +-- received-beacon monitoring
  +-- real_beacon_skip
  +-- Beacon Recovery
  +-- expanded PM retry / ownership behavior
  +-- FMAC 3.7.0
  +-- WF200 3.16.1
```

The most visible new recurring mechanism in the current investigation is Beacon
Recovery.

---

# Beacon Statistics in 2.2.4

Firmware 2.2.4 periodically requests WF200 statistics through command:

```text
0x66
```

The returned statistics include values corresponding to:

```text
received beacon count
missed beacon count
TBTT difference
```

The host uses the cumulative received-beacon count to derive:

```text
C = current received-beacon count
P = previous host-side baseline

delta = C - P

real_beacon_skip = 600 / delta
```

The result is stored in an 8-bit field and later participates in the Beacon
Recovery decision.

This measurement/control chain has not been identified in the same form in the
investigated earlier host firmware.

Detailed analysis is documented in:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

and:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

# Beacon Recovery in 2.2.4

When the cached recovery value qualifies, firmware 2.2.4 temporarily changes
the WF200 power-management state.

The normal observed sequence is approximately:

```text
state 3 / Fast Power Save
      |
      v
Beacon Recovery
      |
      v
state 1 / active WLAN
      |
      v
~5 serviced seconds
      |
      v
restore saved PM state
      |
      v
normally state 3 / Fast Power Save
```

This is a real WLAN power-management transition.

The normal recovery path does not intentionally perform a complete Wi-Fi
reconnect, DHCP renewal or cloud reconnect.

No explicit transmit-power increase has been identified.

Affected stock 2.2.4 devices have shown this sequence repeating approximately
once per minute for extended periods.

Later analysis identified three separate host-side validity problems in this
path.

---

# C1a – Signed Control Interpretation

The derived value:

```text
600 / delta
```

is stored as one byte.

Stock recovery later interprets the byte as signed.

For example:

```text
delta = 3

600 / 3 = 200

uint8_t = 0xC8
int8_t  = -56
```

and:

```text
delta = 4

600 / 4 = 150

uint8_t = 0x96
int8_t  = -106
```

Because stock recovery rejects zero and accepts signed values less than or
equal to `2`, these negative interpretations unexpectedly qualify.

The resulting fresh stock trigger set includes:

```text
delta = 3
delta = 4
delta = 201 .. 600
```

The `delta = 3` and `delta = 4` cases are artifacts of the signed control
interpretation.

---

# C1b – Measurement-Window Validity

The calculation uses the fixed numerator:

```text
600
```

but the previous cumulative beacon baseline does not carry a corresponding
elapsed-time value.

Firmware paths exist where an expected measurement opportunity is skipped
while the old baseline survives.

The next calculation can therefore become:

```text
old P
  |
  | measurement opportunity skipped
  |
  | another interval passes
  |
  v
later C
  |
  v
600 / (C - P)
```

where the counter delta represents a longer logical interval than the fixed
numerator assumes.

This problem can occur even when the WF200 cumulative counter itself is
completely correct.

---

# C2 – Historical Recovery Evidence

The stock recovery path clears:

```text
P
```

but retains:

```text
R = real_beacon_skip
```

After a qualifying recovery:

```text
P = 0
R = old qualifying value
```

The next successful statistics request can only establish a new baseline.

No fresh ratio exists on that pass.

Stock control flow nevertheless evaluates the retained historical `R`.

If it still qualifies, another recovery occurs and the newly installed
baseline is cleared again.

The resulting sequence is:

```text
fresh qualifying R
      |
      v
Beacon Recovery
      |
      v
P = 0
R retained
      |
      v
next statistics sample
      |
      v
new P installed
      |
      | no fresh R
      v
historical R evaluated
      |
      v
Beacon Recovery
      |
      v
P = 0
      |
      v
repeat
```

This explains how a single qualifying measurement can become a
self-sustaining approximately minute-spaced recovery loop.

The first qualifying recovery and the subsequent repeating loop are therefore
separate problems.

A fresh trigger is required to enter the state.

A fresh trigger is not required for every later stock recovery once C2 is
active.

See:

[`recovery-mechanism.md`](recovery-mechanism.md)

---

# Periodic mDNS vs. Beacon Recovery

The firmware chronology separates these mechanisms.

Approximately:

```text
2.1.0
    no comparable recurring connected mDNS restart identified

2.1.3
    ~60 s recurring mDNS restart

2.1.8
    ~180 s recurring mDNS restart

2.2.4
    ~180 s recurring mDNS restart
    +
    Beacon Recovery
```

Patch B later suppressed the identified recurring mDNS restart while leaving
the stock Beacon Recovery path active.

Beacon Recovery continued.

The Patch-B device eventually accumulated approximately:

```text
58 recoveries/hour
```

during its full-discharge test.

The recurring mDNS restart is therefore not required for the observed stock
Beacon Recovery loop.

This does not rule out indirect interaction between network traffic and WLAN
power-management behavior.

---

# D3 / WF200 `PS_MODE_ERROR`

Firmware 2.2.4 contains handling for a WF200 `PS_MODE_ERROR` indication.

A dedicated D3 observer build was used to record these events and their reason
values.

The D3 observer device continued to show recurring Beacon Recovery for days
while:

```text
D3_total = 0
```

At approximately 63.9 hours:

```text
beacon_err ~= 3835
D3_total   = 0
```

The observed recurring Beacon Recovery therefore does not require a host-visible
D3 `PS_MODE_ERROR`.

This does not prove that the protected WF200 firmware is uninvolved.

A radio-internal condition can exist without generating this particular event.

It does show that D3 is not the direct trigger for the recurring recovery
sequence observed in this test.

---

# Patch C-C

Patch C-C was developed as a corrective version of Beacon Recovery rather than
a blanket bypass.

It retains:

```text
WF200 statistics
real_beacon_skip diagnostics
fresh valid Beacon Recovery
```

while correcting the identified control-validity problems:

```text
C1a
signed control interpretation

C1b
invalid measurement window

C2
historical recovery evidence reused without a fresh measurement
```

The corrected logic requires a valid current measurement before recovery can
occur.

A baseline-only pass cannot use historical `real_beacon_skip` as fresh control
evidence.

---

## C-C Hardware Result

C-C has now progressed beyond static qualification.

Controlled hardware testing confirmed that:

- the patched firmware boots
- WLAN remains functional
- cloud connectivity remains functional
- thermostat operation remains functional
- valve operation remains functional
- the known stale-state recovery loop is removed
- fresh qualifying Beacon Recovery remains possible

This last point is important.

C-C does not reduce the system to:

```text
Beacon Recovery disabled
```

Instead it produces:

```text
invalid / stale evidence
    -> no recovery

fresh valid qualifying evidence
    -> recovery retained
```

Later C-C-based test devices continued to show fresh recovery at rates
substantially below the stock stale-loop rate.

This demonstrates that the stock self-sustaining loop and the first/fresh
trigger are separate phenomena.

Long-term battery behavior remains part of the wider investigation.

---

# Patch A and Patch B

Earlier experimental patches were primarily isolation tools.

## Patch A

Patch A bypasses the Beacon Recovery action.

This was useful for determining whether repeated recovery activity could be
removed without disabling the underlying statistics path.

Because it also suppresses legitimate fresh recovery, it is not the preferred
corrective design.

## Patch B

Patch B suppresses the identified recurring connected mDNS restart.

It does not disable the mDNS subsystem itself.

Runtime testing showed that the targeted recurring traffic disappears while
normal connectivity remains available.

Beacon Recovery remains active.

## Patch A+B

The combined experimental firmware suppresses both targeted recurring
mechanisms.

It demonstrated that the modifications could coexist on physical hardware.

It was an isolation experiment, not a final correction architecture.

---

# A1 Power-Management Correction

Later reverse engineering identified several host/WF200 power-management
ownership and failure-path problems separate from Beacon Recovery.

The A1 correction was developed for these issues.

Its scope includes defects involving:

- Final-Sleep failure cleanup
- Wake failure state handling
- timeout versus cancellation
- late PM completion ambiguity
- requested versus committed PM state
- old PM completion races
- independent inhibit ownership

A1 does not replace C-C.

The two patches address different classes of host defect.

Conceptually:

```text
C-C
    -> Beacon Recovery measurement/control validity

A1
    -> PM ownership, settlement and failure-path correctness
```

A1 also does not globally fix the later-discovered B2 reference-counter race.

That defect lies outside the current A1 scope.

---

# A1 + C-C + WF200 3.18.0

A combined experimental firmware was constructed using:

```text
stock 2.2.4 host base
      +
A1
      +
C-C
      +
WF200 3.18.0
```

The integration passed independent static and construction qualification before
controlled device testing.

The controlled-test artifact successfully booted on physical hardware.

Observed functionality includes:

- FMAC 3.7.0 initialization
- WF200 3.18.0 initialization
- WLAN association
- DHCP
- cloud connectivity
- thermostat operation
- valve operation
- power-management transitions
- fresh Beacon Recovery

This demonstrates practical interoperability between the Shelly 2.2.4 FMAC
3.7.0 host environment and the tested official WF200 3.18.0 radio firmware.

It does not prove that every behavior of this unsupported combination is
identical to an officially qualified Silicon Labs/Shelly combination.

---

# WF200 3.18.0

The investigated official WF200 3.18.0 radio firmware was released by Silicon
Labs in October 2026.

Its changelog contains a power-management-related fix described as a condition
where the device could fail to sleep after a power-save mode change.

This is directly relevant to the class of problem being investigated.

It is not proof that this Silicon Labs fix is the historical Shelly TRV battery
drain root cause.

The Shelly TRV combines:

```text
host application behavior
+
FMAC behavior
+
protected WF200 behavior
+
network environment
+
host MCU sleep behavior
```

and several independent host defects have already been demonstrated.

WF200 3.18.0 is therefore being treated as an important experimental radio-side
correction, not as a complete explanation by itself.

---

# Runtime Behavior with A1 + C-C + WF200 3.18.0

The A1+C-C+WF200 3.18.0 canary device successfully passed the initial hardware
qualification and continued running for more than a day.

Fresh Beacon Recovery remained present.

Observed rates during the first day were approximately:

```text
27 - 28 recoveries/hour
```

rather than the approximately:

```text
~60 recoveries/hour
```

characteristic of the stock C2 stale-state loop on affected devices.

The device also produced values such as:

```text
desired_beacon_skip = 20
real_beacon_skip    = 1
```

despite good RSSI.

Because C-C prevents the known stale-`R` self-sustaining mechanism, these
remaining events represent fresh qualifying measurements rather than simple
repetitions of C2.

Their exact radio/environmental trigger remains under investigation.

---

# Mesh / Band-Steering Test

The A1+C-C+WF200 3.18.0 device was also tested with FRITZ! Mesh/Band Steering
disabled.

Fresh Beacon Recovery continued.

This shows that Mesh/Band Steering is not required for the observed fresh
recovery under the tested conditions.

It does not rule out other access-point or RF interactions.

---

# Host Sleep vs. WLAN Recovery

The current investigation now separates two major diagnostic domains.

## WLAN / WF200 Recovery

This includes:

```text
command 0x66
received-beacon statistics
real_beacon_skip
Beacon Recovery
C1a
C1b
C2
WF200 power-save behavior
```

## EFM32GG11 Host Sleep

This includes:

```text
B2 reference counting
B3 / EM2 policy
PA8 WFI veto
Final-Sleep ownership
actual EM1 / EM2 selection
```

These domains interact because WLAN operations can create host sleep-blocking
claims.

They are not the same mechanism.

For example:

```text
Beacon Recovery occurred
```

does not prove:

```text
host remained awake
```

and:

```text
B2 remained nonzero
```

does not prove:

```text
Beacon Recovery caused it
```

The runtime investigation must therefore observe both sides independently.

---

# Stock 2.2.4 Host-Sleep Observer

The next diagnostic firmware is intentionally based on clean stock 2.2.4.

It does not include:

- A1
- C-C
- MIN80
- D3 observer
- WF200 3.18.0
- a B2 fix

The reason is causal isolation.

The goal is to observe the shipped host behavior before correcting the newly
identified B2 accounting defect.

The observer is designed to record, with minimal perturbation:

```text
B2 / B3 state
known B2 owner activity
EM1 entries
EM2 entries
PA8 sleep vetoes
WFI behavior
B2 ownership mismatches
```

The observer must preserve the original B2 load/store race windows.

It must not make the B2 updates atomic merely by instrumenting them.

The most useful possible observations would be states such as:

```text
known active owners = 0
actual B2           = 1

-> phantom B2 contribution
```

or:

```text
known active owners = 1
actual B2           = 0

-> lost B2 contribution
```

The observer is currently being statically and execution-level qualified before
controlled hardware testing.

No runtime conclusion should be drawn from it until that qualification is
complete and the instrumented firmware has been tested on a physical device.

---

# Cross-Version Summary

| Mechanism | 2.1.0 | 2.1.3 | 2.1.8 | 2.2.4 |
|---|---:|---:|---:|---:|
| mDNS responder | yes | yes | yes | yes |
| recurring connected mDNS restart | not identified | yes | yes | yes |
| recurring mDNS cadence | none established | ~60 s observed | ~180 s intended | ~180 s |
| state-5 / `psovrd2` | not identified | yes | yes | yes |
| connected Fast Power Save | yes | yes | yes | yes |
| shared B2/B3 sleep-blocker architecture | yes | yes | yes | yes |
| permanent B3 / normal EM2 policy | yes | yes | yes | yes |
| PA8 WLAN sleep gate | equivalent architecture identified | present | present | confirmed in detail |
| Final-Sleep retention architecture | yes | yes | yes | yes |
| unprotected aggregate blocker helpers | yes | present architecture | present architecture | yes |
| complete concrete B2 task-race witness | not yet closed | not yet closed | not yet closed | yes |
| post-association PM evolution | early form | changed | expanded | expanded further |
| command-`0x66` Beacon Recovery chain | not identified | not identified | not identified in current comparison | yes |
| `real_beacon_skip` recovery control | not identified | not identified | not identified | yes |
| C1a signed-control defect | n/a | n/a | n/a | yes |
| C1b measurement-window defect | n/a | n/a | n/a | yes |
| C2 stale-control-evidence loop | n/a | n/a | n/a | yes |
| D3 `PS_MODE_ERROR` handling used in current investigation | no comparable handler identified | no | no | yes |
| A1 correction target | n/a | n/a | n/a | yes |
| C-C correction target | n/a | n/a | n/a | yes |

`not identified` means that the mechanism has not been found in the
investigated host firmware.

It should not be interpreted as proof that no conceptually related behavior can
exist inside the protected WLAN components.

---

# Experimental Configuration Summary

The experimental firmware used during the investigation should not be confused
with official Shelly releases.

| Configuration | Host basis | Beacon Recovery | WF200 | Purpose |
|---|---|---|---|---|
| Patch A | 2.2.4 | bypassed | 3.16.1 | recovery isolation |
| Patch B | 2.2.4 | stock | 3.16.1 | mDNS isolation |
| C-C | 2.2.4 | corrected | 3.16.1 | Beacon Recovery correction |
| C-C + WF200 3.18 | 2.2.4 | corrected | 3.18.0 | host/radio comparison |
| A1 + C-C + WF200 3.18 | 2.2.4 | corrected | 3.18.0 | combined corrected test platform |
| Stock Host Observer | 2.2.4 | stock | 3.16.1 | B2/PA8/EM1/EM2 observation |

The observer intentionally returns to the stock host behavior rather than using
the most corrected experimental build.

That is necessary to determine whether the newly identified host-sleep defect
actually occurs in the original firmware.

---

# What the Firmware Chronology Establishes

## 1. The underlying host sleep architecture is old

The B2/B3 sleep-blocker model, permanent B3 contribution and broad host
sleep architecture predate firmware 2.2.4.

This means that host-sleep problems cannot automatically be classified as
2.2.4 regressions.

---

## 2. EM2 is the intended normal deep idle state

The permanent B3 contribution is consistent with the RTC/LFXO configuration.

Removing it would make the existing EM3 path incompatible with the current
tickless timebase.

The investigation therefore does not treat the absence of normal EM3 residency
as a firmware bug.

---

## 3. B2 accounting contains a real correctness defect

The shared reference counter is conceptually necessary, but its updates are not
globally serialized.

Concrete 2.2.4 task schedules can create:

```text
phantom B2
```

or:

```text
lost B2
```

The first can incorrectly keep the host limited to EM1.

The second can incorrectly permit EM2 while a live owner still requires EM1.

Runtime occurrence is being investigated.

---

## 4. PA8 can independently prevent WFI

PA8 belongs to the WLAN notification path.

When HIGH at the sleep gate, WFI is skipped.

This is intentional behavior unless the signal remains asserted or repeatedly
blocks sleep longer than expected.

Runtime duration and frequency therefore matter more than the existence of the
gate itself.

---

## 5. mDNS itself predates the recurring restart

The mDNS responder exists in 2.1.0.

The important later change is the recurring connected restart.

---

## 6. The recurring mDNS workload changes between releases

The investigated progression is approximately:

```text
2.1.0
    no comparable recurring restart identified

2.1.3
    ~60 s

2.1.8
    ~180 s

2.2.4
    ~180 s
```

Patch-B testing shows that this restart is not required for the stock Beacon
Recovery loop.

---

## 7. State 5 is not a three-minute full-host-awake timer

The 180-second state-5 value belongs to a temporary WLAN power-management
override.

It does not directly mean that the EFM32GG11 remains awake for three minutes.

---

## 8. 2.1.8 changes both host and radio behavior

The transition changes post-association sequencing and updates both FMAC and
WF200 firmware.

Its net battery effect cannot be assigned to one side without additional
evidence.

---

## 9. Beacon Recovery is a later 2.2.4 mechanism

The identified:

```text
0x66 statistics
      ->
received-beacon delta
      ->
real_beacon_skip
      ->
Beacon Recovery
```

chain belongs to the investigated 2.2.4 host implementation.

---

## 10. Beacon Recovery contains multiple host defects

The current analysis separates:

```text
C1a
signed control interpretation

C1b
measurement-window validity

C2
historical control evidence reused without a fresh measurement
```

C-C corrects these problems while retaining fresh recovery.

---

## 11. Stock recurring recovery and fresh recovery are different

Stock C2 can turn one qualifying value into an approximately minute-spaced
self-sustaining loop.

After C-C removes that state, fresh qualifying recovery still occurs.

The cause of:

```text
first / fresh trigger
```

and the cause of:

```text
stock repeated recovery
```

must therefore be investigated separately.

---

## 12. D3 is not required for the observed recovery loop

The D3 observer recorded:

```text
D3_total = 0
```

while thousands of Beacon Recovery events accumulated.

The host-visible `PS_MODE_ERROR` indication is therefore not a required trigger
for the observed recurring recovery.

---

## 13. WF200 3.18.0 does not eliminate every fresh recovery

The newer radio firmware contains a relevant Silicon Labs power-save sleep fix.

Nevertheless, fresh qualifying recovery remains observable with C-C and WF200
3.18.0.

This means the newer radio firmware does not simply make the entire
host-observed beacon phenomenon disappear.

---

## 14. Beacon Recovery cannot explain all historical drain

Drain has also been observed on firmware 2.1.8.

A mechanism specific to 2.2.4 therefore cannot be the sole explanation for the
historical problem.

---

# What the Firmware Chronology Does Not Establish

The current comparison does not establish:

- the exact release where historical battery degradation first appeared
- that firmware 2.1.0 is free of battery-drain mechanisms
- that firmware 2.1.3 is free of battery-drain mechanisms
- that firmware 2.1.8 introduced the historical problem
- that recurring mDNS is the root cause
- that Beacon Recovery is the complete root cause
- that WF200 3.16.1 is the complete root cause
- that WF200 3.18.0 solves the complete problem
- that the B2 race occurs frequently on physical devices
- that a phantom B2 state explains a specific historical discharge
- that PA8 remains asserted abnormally during drain
- the quantitative energy cost of each mechanism
- the exact physical WF200 sleep residency
- the exact EFM32GG11 EM1/EM2 residency during historical drain
- the exact trigger for every fresh C-C Beacon Recovery event
- the exact battery-life improvement produced by C-C or A1
- that the combined experimental firmware represents a final production fix

These questions require runtime evidence rather than additional speculation
from static code alone.

---

# Current Battery-Drain Model

The current evidence supports a model with several independent layers.

```text
normal TRV workload
      +
network / cloud activity
      +
periodic mDNS maintenance
      +
WF200 power-save behavior
      +
radio / AP environment
      +
host PM ownership and failure paths
      +
shared B2 blocker accounting
      +
PA8 WLAN sleep veto
      +
2.2.4 Beacon Recovery
      +
version-specific host/radio changes
```

Not every mechanism needs to be active on every affected device.

Several may also interact.

For example:

```text
WLAN operation
      |
      v
host B2 claim
      |
      v
B2 accounting race
      |
      v
phantom contribution
      |
      v
EM2 blocked
```

is a different failure chain from:

```text
beacon statistics
      |
      v
qualifying real_beacon_skip
      |
      v
Beacon Recovery
      |
      v
temporary active WLAN state
```

and both differ from:

```text
WF200 notification pending
      |
      v
PA8 HIGH
      |
      v
WFI veto
```

The current objective is to determine which of these conditions actually occur
during a physical battery-drain episode.

---

# Current Research Priorities

## 1. Qualify the Stock 2.2.4 Host-Sleep Observer

The observer must pass static, execution, memory, noninterference and GBL
qualification before flashing.

The instrumentation must preserve the original B2 race rather than accidentally
fixing it.

---

## 2. Observe B2 on Physical Stock Behavior

The primary runtime question is whether the demonstrated reference-counter race
actually produces:

```text
phantom B2
```

or:

```text
lost B2
```

on a physical TRV.

A persistent phantom contribution would provide a direct software mechanism for
incorrectly preventing EM2.

---

## 3. Observe PA8 Sleep Vetoes

The same experiment should determine whether PA8:

- vetoes WFI occasionally as expected
- repeatedly vetoes WFI during problematic periods
- remains asserted for unexpectedly long periods

The existence of the gate is already understood.

Its runtime behavior is the open question.

---

## 4. Observe Actual EM1 / EM2 Entry Behavior

`/stats sleep_ratio` is not a physical host sleep-residency measurement.

The observer therefore needs direct instrumentation of the host sleep path.

The goal is to determine whether the host reaches the intended EM2 state when
no legitimate blocker exists.

---

## 5. Correct B2 Accounting if Runtime Evidence Supports It

The smallest appropriate correction is not to clear B2 or assign it from one
subsystem.

B2 must remain a shared reference counter.

The correct direction is bounded serialization of the complete B2
check/read-modify-write operations while preserving caller semantics.

Any such correction must be independently qualified before integration.

---

## 6. Integrate the Validated B2 Fix

If the runtime observer confirms the defect on physical hardware, the validated
B2 correction can be integrated into the corrected platform:

```text
A1
+
C-C
+
B2 correction
+
WF200 3.18.0
```

This would address several independently identified host and radio-side
problems without enabling EM3 or suppressing legitimate WLAN recovery.

---

## 7. Continue Long-Term Battery Testing

Correcting a firmware defect does not automatically prove that the historical
battery-drain problem is solved.

Long-term voltage and runtime behavior remain necessary integration tests.

---

# Current Conclusion

The firmware history no longer supports a simple explanation such as:

```text
2.2.4 Beacon Recovery caused the Shelly TRV battery-drain problem
```

The evidence is more specific.

Firmware 2.2.4 introduced a Beacon Recovery mechanism containing several
demonstrable host-side control-validity defects.

Those defects explain how a fresh qualifying measurement can become a
self-sustaining approximately minute-spaced recovery loop.

Patch C-C corrects that behavior while preserving fresh valid recovery, and
hardware testing confirms that fresh recovery still exists after the stale loop
has been removed.

At the same time, deeper host analysis identified an independent correctness
defect in the shared B2 sleep-blocker accounting.

The underlying B2/B3 architecture predates firmware 2.2.4.

Concrete 2.2.4 task schedules can corrupt B2 through unsynchronized
read-modify-write operations, potentially leaving the EFM32GG11 incorrectly
limited to EM1 or allowing EM2 while a legitimate owner is still active.

The permanent B3 contribution is not considered a bug: with the stock
RTC/LFXO configuration, EM2 is the intended normal deep idle state and EM3
would require a separate clock/timebase redesign.

PA8 provides another independent WLAN-controlled sleep gate and can prevent
WFI while asserted.

The next important step is therefore runtime observation rather than another
broad static search.

A clean-stock 2.2.4 host-sleep observer is being built to determine whether
B2 corruption, prolonged PA8 sleep vetoes, abnormal EM1 behavior, or none of
these conditions actually occur during physical battery-drain operation.

The current working model is consequently:

```text
historical drain
      !=
one confirmed mechanism

historical drain
      =
interaction of common architecture,
version-specific defects,
WLAN/radio behavior,
and possibly multiple independent
sleep-prevention mechanisms
```

The project now has several concrete defects that can be corrected
independently.

What remains is to determine which of them materially contribute to the
observed battery lifetime.

---

# Related Documents

Beacon statistics and baseline handling:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Calculated beacon-skip behavior:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery control flow:

[`recovery-mechanism.md`](recovery-mechanism.md)

Periodic mDNS analysis:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Host power-management and sleep behavior:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Runtime mDNS comparison:

[`../testing/mdns-runtime-comparison.md`](../testing/mdns-runtime-comparison.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Method

This comparison is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware together with runtime testing on personally owned
devices.

Important control-flow conclusions are checked against native ARM Thumb
instructions, binary differences and executable behavior rather than relying
only on decompiler output.

Experimental firmware is built from locally obtained stock firmware and is
used only for controlled testing.

The project does not publish original Shelly firmware images, modified complete
firmware images, complete proprietary functions or large raw disassemblies.

Where protected WF200 behavior cannot be reconstructed from the host side, that
boundary is kept explicit.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The documented behavior refers to the firmware versions, experimental builds
and physical devices tested in this project.