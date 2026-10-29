# Host Sleep and Blocker Accounting

## Shelly TRV Gen1 Firmware 2.2.4

## Scope

This document describes the host-MCU sleep architecture used by the Shelly TRV Gen1 and the shared blocker accounting that determines whether the EFM32GG11 may enter EM1, EM2 or EM3.

The analysis focuses on:

- the native idle/sleep selection path
- the B2 and B3 blocker counters
- the permanent startup B3 contribution
- the RTC/LFXO dependency
- EM1, EM2 and EM3 selection
- the shared B2 reference-counting model
- task-preemption races in B2 accounting
- concrete phantom-B2 and lost-B2 schedules
- the qualified bounded B2 serialization correction
- PA8 as an independent WLAN sleep gate
- the relationship between host sleep and WLAN power management
- cross-version relevance
- the boundary between these findings and A1/A1R
- the current B2.1/B2.1_OBS test architecture

The main firmware target is:

```text
20240619-130912/v2.2.4@ee290818
```

Firmware 2.1.0 is also used for a narrower architectural comparison.

This document does not attempt to estimate electrical current consumption.

It describes when firmware permits or prevents host low-power entry and documents a demonstrated correctness defect in the shared B2 blocker accounting.

The B2 defect has since been corrected experimentally through bounded serialization.

That correction is qualified and incorporated into the current B2.1 and B2.1_OBS firmware.

This does **not** establish that B2 corruption was the historical battery-drain root cause.

---

# 1. Host MCU

The Shelly TRV Gen1 uses a:

```text
Silicon Labs EFM32GG11
```

as its host MCU.

The WF200 WLAN device is a separate component.

This distinction matters because there are two different power-management layers:

```text
EFM32GG11 host
    |
    +-- EM1
    +-- EM2
    +-- EM3
    +-- scheduler / tickless idle
    +-- software sleep blockers
    +-- PA8 WLAN notification gate

WF200
    |
    +-- WLAN power-save modes
    +-- beacon processing
    +-- DTIM / listen behavior
    +-- protected radio firmware
```

A host-side sleep restriction does not prove that WF200 is awake.

Likewise, a WF200 power-save state does not prove that the EFM32GG11 entered EM2.

The two power domains interact but must be analyzed separately.

---

# 2. Native Host Idle Path

The reconstructed native idle chain in firmware 2.2.4 follows approximately:

```text
tickless / idle handling
        |
        v
sleep wrapper
        |
        v
sleep-mode selector
        |
        v
mode dispatch
        |
        +-- EM1
        |
        +-- EM2
        |
        +-- EM3
```

Relevant native areas include approximately:

```text
sleep wrapper:
0x6BBC

sleep-mode selector:
0x6D08

mode dispatch:
0x6D48
```

The sleep selector evaluates shared blocker state before choosing the deepest currently permitted energy mode.

The important counters are referred to in this project as:

```text
B2
B3
```

These names describe their reconstructed firmware roles.

---

# 3. B2 and B3 Selection Semantics

The native selector behaves approximately as:

```text
if B2 != 0:
    deepest allowed mode = EM1

else if B3 != 0:
    deepest allowed mode = EM2

else:
    deepest allowed mode = EM3
```

This can be summarized as:

| B2 | B3 | Deepest permitted mode |
|---:|---:|---|
| non-zero | any | EM1 |
| 0 | non-zero | EM2 |
| 0 | 0 | EM3 |

The counters therefore represent restrictions on deeper sleep.

Conceptually:

```text
B2 owner
    "EM2 and deeper are currently prohibited"

B3 owner
    "EM3 is currently prohibited"
```

B2 is therefore the stronger restriction.

---

# 4. B2 and B3 Are Reference Counters

B2 and B3 must not be interpreted as simple Boolean flags.

They are aggregate reference counters.

Multiple independent software components may legitimately require the same restriction simultaneously.

For B2:

```text
B2 = 0
    no current software owner requires EM1

B2 = 1
    one owner requires EM1

B2 = 2
    two owners require EM1

B2 = 3
    three owners require EM1
```

The same general reference-counting principle applies to the blocker infrastructure.

This design is required because independent operations can overlap.

For example:

```text
WLAN operation starts
B2 = 1

motor operation starts
B2 = 2

WLAN operation completes
B2 = 1

motor operation completes
B2 = 0
```

Replacing B2 with a Boolean would lose ownership information.

---

# 5. Why Shared Ownership Is Correct

The fact that several tasks modify B2 is not itself a defect.

A shared reference counter is an appropriate design when multiple independent subsystems may require the same sleep restriction.

The required invariant is:

```text
B2 == number of active B2 ownership contributions
```

The problem identified in firmware 2.2.4 is not shared ownership.

The problem is inconsistent serialization of the read-modify-write operations maintaining the shared count.

The distinction is fundamental:

> Multiple simultaneous B2 owners are required. Multiple unsynchronized modifications of B2 are not.

---

# 6. Permanent Startup B3 Contribution

During normal startup, firmware 2.2.4 installs a B3 contribution before normal scheduler operation begins.

The relevant startup path was reconstructed approximately as:

```text
reset
   |
   v
platform initialization
   |
   v
CRT / runtime initialization
   |
   v
product main
   |
   v
sleep-state initialization
   |
   v
board initialization
   |
   v
add B3 contribution
   |
   v
WLAN initialization
   |
   v
main task / scheduler
```

The B3 contribution is installed unconditionally during successful normal startup.

No normal runtime release for this contribution was identified.

The result is:

```text
B3 >= 1
```

during normal operation.

The normal idle selector therefore does not reach EM3.

---

# 7. The Permanent B3 Contribution Is Intentional

A permanent sleep restriction can initially appear suspicious in a battery-powered product.

In this case, however, the restriction has a concrete technical reason.

The stock firmware configures the low-frequency scheduler/RTC timebase using:

```text
LFXO
```

The RTC is used by the tickless scheduler for wake timing and elapsed-time reconstruction.

The EM3 implementation disables:

```text
LFXO
LFRCO
```

while EM2 retains the required low-frequency clocking.

Therefore:

```text
normal deepest idle = EM2
```

is consistent with the current firmware architecture.

The project does not classify the permanent B3 contribution as a battery-drain defect.

---

# 8. Why EM3 Cannot Simply Be Enabled

A tempting battery optimization would be:

```text
remove permanent B3
        |
        v
allow EM3
```

That is not a valid correction for the current firmware architecture.

The scheduler currently depends on an RTC/tickless timebase sourced from LFXO.

Entering EM3 with the current implementation would stop that clock.

Re-enabling LFXO after wake does not recreate the RTC ticks that did not occur while the oscillator was stopped.

The actual constraint is therefore:

```text
current scheduler/timebase architecture
is not designed for normal EM3 residency
```

Using EM3 safely would require a separate clock/timebase redesign.

That would be an optimization project, not a correction of the demonstrated battery-drain-related firmware defects.

---

# 9. Intended Normal Host Sleep

With the permanent B3 contribution present, intended normal idle is:

```text
B2 = 0
B3 != 0
```

which permits:

```text
EM2
```

The important host-side question is therefore not:

> Why does the TRV not enter EM3?

The relevant question is:

> Does the host reliably permit EM2 whenever no legitimate B2 owner requires EM1?

This distinction drove the host-sleep investigation.

---

# 10. B2 Ownership Sources

Several firmware paths can contribute to B2.

The reconstructed 2.2.4 owner classes include:

```text
MOTOR

MANUAL_DTIM

OTA

WLAN / O

initialization-related ownership
```

Different paths use different synchronization behavior.

Some operations are protected by interrupt masking.

Others use a generic blocker helper without protecting the complete read-modify-write operation from task preemption.

This mixture creates the B2 concurrency defect.

---

# 11. Native Blocker Helpers

The generic blocker helper performs the conceptual equivalent of:

```c
value = B2;
value = value + 1;
B2 = value;
```

for an acquire and:

```c
value = B2;
value = value - 1;
B2 = value;
```

for a release.

The actual implementation additionally contains bounds/assertion behavior.

The important concurrency property is that the complete generic read-modify-write sequence is not globally protected against task switching.

A task can therefore be preempted after reading B2 but before storing its updated value.

---

# 12. Protected WLAN/O Operations

Another part of the firmware maintains WLAN-related ownership referred to in this project as:

```text
O
```

The relevant O/B2 operations use a saved interrupt-mask sequence equivalent to:

```text
save PRIMASK
disable interrupts

update O
update B2

restore original PRIMASK
```

This serializes operations using that protected path against one another.

The problem occurs when an unprotected generic B2 operation overlaps with one of these protected operations.

The protected operation can itself be atomic while another task still holds a stale B2 value that it loaded before the protected operation began.

---

# 13. Task Preemption Makes the Race Reachable

The affected operations execute in real task contexts.

Relevant examples in firmware 2.2.4 include:

```text
motor path
    main task
    priority 7

manual DTIM path
    HTTP/TCPIP-related task
    priority 7

OTA path
    separate task context

WLAN manager / bus paths
    WLAN-related task contexts
```

The motor and manual-DTIM B2 operations do not locally mask interrupts or suspend scheduling across the complete generic B2 update.

Equal-priority tasks can switch following scheduler activity such as the RTC tick/PendSV path.

The race is therefore not based only on an impossible theoretical interleaving.

Concrete native task contexts exist that can produce the required schedule.

---

# 14. B2 Concurrency Defect

The shared B2 reference count is vulnerable to a classic lost-update race.

Consider:

```text
Task A:
    read B2
    calculate new value
    write B2

Task B:
    read/update/write B2
```

If Task A is preempted after its read:

```text
Task A reads old value
        |
        v
Task B changes B2
        |
        v
Task A resumes
        |
        v
Task A writes result based on stale value
```

Task B's contribution can be lost, or a contribution already removed by Task B can effectively be recreated.

Both directions were reconstructed in firmware 2.2.4.

This is a demonstrated firmware correctness defect.

---

# 15. Phantom B2 Contribution

One concrete schedule can leave B2 larger than the number of legitimate owners.

Start with:

```text
B2 = 1
```

where the contribution belongs to WLAN/O.

A second task begins a B2 acquire:

```text
Task A:
    load B2 = 1
```

Before Task A stores the incremented value, it is preempted.

The WLAN worker performs a protected release:

```text
Task B:
    B2 1 -> 0
```

Task A later resumes with its stale copy:

```text
Task A:
    stale value = 1
    store 1 + 1
    B2 = 2
```

The correct result is:

```text
B2 = 1
```

because only Task A's new ownership remains.

Instead:

```text
B2 = 2
```

When Task A later releases its legitimate ownership:

```text
B2 2 -> 1
```

the final state is:

```text
B2 = 1

0 legitimate owners
```

This is a phantom B2 contribution.

---

# 16. Consequence of Phantom B2

The host sleep selector does not know which subsystem owns each count.

It sees only:

```text
B2 != 0
```

and therefore limits idle to:

```text
EM1
```

The resulting state is:

```text
no legitimate B2 owner
        |
        v
B2 remains non-zero
        |
        v
selector permits only EM1
        |
        v
intended EM2 unavailable
```

The corrupted state can persist until later activity happens to alter the aggregate or the state is reinitialized.

The code defect is established.

Its historical field incidence and quantitative energy impact have not been established.

---

# 17. Lost B2 Contribution

The opposite corruption is also possible.

Start with:

```text
B2 = 0
```

A motor task begins an acquire:

```text
Motor:
    load B2 = 0
```

Before the motor stores the increment, a WLAN operation acquires ownership through the protected path:

```text
WLAN:
    B2 0 -> 1
```

The motor resumes and stores its stale calculation:

```text
Motor:
    stale value = 0
    store 0 + 1
    B2 = 1
```

The correct aggregate should be:

```text
B2 = 2
```

because both owners are active.

Instead:

```text
B2 = 1
```

When WLAN later releases:

```text
B2 1 -> 0
```

the motor may still legitimately require EM1.

The selector can now permit:

```text
EM2
```

while the motor's B2 contribution has effectively been lost.

---

# 18. Consequence of Lost B2

The B2 defect is therefore not only a potential battery-consumption problem.

It is a general power-management correctness defect.

The two directions are:

```text
phantom contribution
    |
    v
B2 too high
    |
    v
EM1 when EM2 should be allowed
```

and:

```text
lost contribution
    |
    v
B2 too low
    |
    v
EM2 while an owner still requires EM1
```

The first can unnecessarily prevent deeper sleep.

The second can permit deeper sleep prematurely.

A correct fix must prevent both.

---

# 19. Why Clearing B2 Is Not a Fix

Because B2 is a shared reference counter, a correction must not simply perform:

```c
B2 = 0;
```

when a suspicious state is detected.

The firmware may legitimately have another active owner.

For example:

```text
motor owns B2
WLAN owns B2

B2 = 2
```

If WLAN completes:

```text
correct:
B2 = 1
```

Forcing:

```text
B2 = 0
```

would incorrectly discard the motor contribution.

The aggregate must retain its reference-count semantics.

---

# 20. Qualified B2 Correction

The minimal correction direction is to preserve the reference-counting architecture while making the complete relevant check/read-modify-write sequence atomic with respect to competing task contexts.

Conceptually:

```c
saved = PRIMASK;
disable_interrupts();

validate_counter();
update_counter();

restore_PRIMASK(saved);
```

The implementation must preserve:

- existing assertion semantics
- caller ABI
- incoming/nested interrupt-mask state
- ownership semantics
- task behavior
- bounded timing behavior

The objective is not to redesign the blocker architecture.

It is to make the existing shared reference counter safe against the demonstrated task-preemption race.

This correction has now been implemented and qualified as:

```text
B2 bounded serialization
```

It is part of:

```text
B2.1
B2.1_OBS
B2.2
```

The B2 correction remains analytically separate from A1/A1R.

---

# 21. B2 Correction Qualification

The B2 correction was qualified against the reconstructed ownership and preemption behavior rather than by merely verifying that the modified instructions decode.

Qualification included thousands of behavior cases together with mixed-owner and preemption schedules.

The current integrated qualification records include:

```text
B2:
2060 + 102

mixed/preemption:
qualified test sets
```

The important properties demonstrated by qualification are:

```text
multiple legitimate owners preserved

phantom-count schedule prevented

lost-count schedule prevented

incoming PRIMASK preserved

reference-counter semantics preserved

no global clear introduced

no Boolean replacement introduced
```

The correction is therefore considered independently qualified for integration.

This is still different from demonstrating its historical battery-life contribution.

---

# 22. Relationship to A1 and A1R

A1/A1R correct a different set of host power-management problems.

Their scope includes:

- Final-Sleep failure cleanup
- Wake failure handling
- timeout versus cancellation
- late PM completion
- requested versus committed PM state
- PM generation/settlement
- independent inhibit ownership
- association/handoff correctness

These defects concern PM operation lifecycle and ownership.

The B2 race concerns the shared aggregate blocker counter.

Conceptually:

```text
A1 / A1R
    |
    +-- PM lifecycle
    +-- operation ownership
    +-- settlement
    +-- failure handling

B2 correction
    |
    +-- shared reference counter
    +-- read-modify-write serialization
    +-- task preemption
```

The original A1 implementation did **not** correct the global B2 race.

The later A1R revision also remains conceptually separate from the B2 correction.

A1R corrects an experimental A1 temporary-override regression while retaining A1's lifecycle corrections.

B2 bounded serialization is independently integrated alongside A1R in B2.1.

---

# 23. Final-Sleep and B2

A previously identified Final-Sleep failure path can retain a B2-related ownership contribution when cleanup/release does not complete correctly.

This can result in:

```text
B2 != 0
```

without the expected normal lifecycle completing.

That defect and the global B2 concurrency race must not be conflated.

They are different ways to reach an incorrect blocker state:

```text
Final-Sleep defect
    |
    +-- lifecycle / release failure

B2 concurrency defect
    |
    +-- aggregate reference-count corruption
```

A1/A1R address the qualified lifecycle problem.

B2 bounded serialization addresses the shared-counter concurrency problem.

Both corrections are present in the B2.1 family.

---

# 24. Initialization and B2

Initialization also contains ownership timing relevant to B2.

The important distinction remains between:

```text
operation-specific ownership lifecycle
```

and:

```text
global aggregate counter correctness
```

A1/A1R correct qualified PM handoff and lifecycle behavior.

The B2 audit demonstrated that even if every individual owner follows a balanced acquire/release lifecycle, the shared aggregate can still be corrupted if concurrent updates are not serialized.

Therefore:

```text
all owners individually balanced
```

does not guarantee:

```text
B2 aggregate remains correct
```

when lost updates are possible.

The current integrated correction addresses both classes separately.

---

# 25. PA8 Is a Separate Sleep Gate

B2/B3 selection is not the final condition before host sleep.

The firmware also samples GPIO PA8.

PA8 was traced to the WLAN host-notification path.

Board initialization configures PA8 as an input with pull-down behavior.

A rising condition maps into the GPIO interrupt path and ultimately into WLAN/bus-worker processing.

The exact schematic net name and external electrical implementation were not recovered from firmware alone.

Functionally, PA8 participates in communication from the WLAN side to the host.

---

# 26. PA8 Sleep Veto

Before executing the low-power instruction, the sleep callback checks PA8.

If PA8 is LOW:

```text
selected sleep path may continue
```

If PA8 is HIGH:

```text
WFI is not executed
```

Conceptually:

```text
select EM1/EM2
        |
        v
check PA8
        |
        +-- LOW
        |     |
        |     v
        |    WFI
        |
        +-- HIGH
              |
              v
         return without WFI
```

PA8 therefore provides a sleep veto independent of B2/B3.

---

# 27. Why PA8 Is Not a Reference Counter

PA8 and B2 represent different forms of state.

B2 answers:

> How many software owners currently require EM1?

PA8 answers approximately:

> Is the WLAN notification line currently asserted?

B2 therefore requires shared ownership accounting.

PA8 is a physical signal level.

A useful conceptual distinction is:

```text
B2:
"How many people are still working in the workshop?"

PA8:
"Is the doorbell currently ringing?"
```

Treating PA8 as another reference-counted software owner would not match its reconstructed role.

---

# 28. PA8 HIGH Is Not Automatically a Bug

A WLAN device asserting a host-notification line while work is pending can be legitimate.

Preventing WFI while that notification remains asserted is therefore reasonable.

A persistent or repeated HIGH state would demonstrate that host low-power entry is being vetoed.

It would not by itself establish why the WLAN side is asserting the signal.

No current correction bypasses PA8 simply to increase sleep time.

---

# 29. Sleep Selection and PA8 Are Separate

A device can have:

```text
B2 = 0
B3 != 0
```

so that the selector chooses:

```text
EM2
```

but still not execute WFI because:

```text
PA8 = HIGH
```

Therefore:

```text
EM2 selected
```

is not equivalent to:

```text
EM2 physically entered
```

This distinction is important for telemetry and battery interpretation.

---

# 30. Sleep Entry Atomicity

The final scheduler admission, blocker selection and low-power entry sequence uses interrupt masking around the critical selection/entry region.

No separate race was demonstrated in which B2 changes after a correct selector read but before WFI in a manner that invalidates the selected mode.

The demonstrated B2 defect occurs earlier:

```text
B2 aggregate already corrupted
        |
        v
selector reads corrupted but stable value
        |
        v
selector makes internally consistent decision
```

The selector can therefore operate correctly while making the wrong effective decision because its input aggregate was previously corrupted.

---

# 31. Deep-Sleep Preparation and Restoration

The EM2/EM3 paths contain state-save and restoration logic around low-power entry.

A potential concern was whether PA8 veto could occur after hardware state had already been destructively modified for deep sleep.

Further analysis showed that the relevant early save operation snapshots/waits but does not perform the destructive hardware transition that would require restoration before a PA8-veto return.

No separate PA8-veto preparation/restoration defect was established.

---

# 32. `SLEEPDEEP`

EM2 and EM3 use the Cortex-M:

```text
SCR.SLEEPDEEP
```

mechanism before low-power entry.

The deep-sleep path leaves `SLEEPDEEP` set after returning.

The EM1 path explicitly clears it before shallow sleep.

This behavior was examined during the host-sleep audit.

No independent defect was established from this handling.

---

# 33. `/stats sleep_ratio`

Firmware 2.2.4 exposes:

```text
sleep_ratio
```

through `/stats`.

Reverse engineering shows that this value is based on tickless timing/compensation behavior.

It is not a direct measurement of:

```text
EFM32GG11 physical EM1 residency
```

or:

```text
EFM32GG11 physical EM2 residency
```

and it does not directly measure:

```text
WF200 sleep residency
```

A low or high `sleep_ratio` must therefore not be interpreted as a percentage of physical sleep time.

---

# 34. Host Sleep vs. WF200 Power Save

Host and radio can independently have power-state problems.

Examples:

```text
Host problem:

    phantom B2
        |
        v
    EFM32GG11 remains limited to EM1
```

versus:

```text
Radio problem:

    WF200 fails to sleep correctly
        |
        v
    radio remains active despite host policy
```

and:

```text
Interface condition:

    PA8 remains asserted
        |
        v
    host WFI vetoed because WLAN work is pending
```

These mechanisms can interact, but none should be inferred solely from another.

For example:

```text
Beacon Recovery occurred
```

does not prove:

```text
host failed to enter EM2
```

and:

```text
B2 = 0
```

does not prove:

```text
WF200 entered its intended power-save state
```

---

# 35. Relationship to Beacon Recovery

Beacon Recovery changes WLAN power-management behavior and can therefore influence how often host-side ownership transitions occur.

Beacon Recovery and the B2 concurrency defect are nevertheless separate mechanisms.

A useful separation is:

```text
Beacon Recovery
    |
    +-- Why is WLAN PM being changed?

B2 accounting
    |
    +-- Does host software correctly account
        for all active EM1 restrictions?

PA8
    |
    +-- Is the WLAN notification path currently
        preventing WFI?
```

The project does not claim that every historical B2 corruption event, if one occurred, must have originated from Beacon Recovery.

---

# 36. Cross-Version Relevance

A narrower comparison with firmware 2.1.0 found the same broad host-sleep architecture.

Firmware 2.1.0 also contains:

- the B2/B3 blocker architecture
- the permanent startup B3 contribution
- equivalent sleep selection
- the PA8 sleep callback
- EM2/EM3 dispatch
- generic aggregate blocker helpers with the same broad synchronization concern

The architecture relevant to the B2 problem therefore predates firmware 2.2.4.

This matters because historical battery drain also predates 2.2.4.

However, the complete task-level concurrency witness demonstrated for 2.2.4 was not closed to the same depth for 2.1.0.

The supported conclusion remains:

> The vulnerable blocker architecture exists in both analyzed generations, while complete concrete task-preemption schedules were demonstrated for firmware 2.2.4.

Identical runtime incidence across versions must not be assumed.

---

# 37. Why the Cross-Version Result Matters

The B2 finding differs from Beacon Recovery.

The analyzed Beacon Recovery implementation is a later 2.2.4 mechanism.

The shared host blocker architecture is older.

The B2 defect class is therefore structurally compatible with battery-drain reports predating 2.2.4.

That makes it a plausible common host-side contributor.

It does not establish historical causality.

---

# 38. Historical Stock-Observer Plan

Before the B2 correction was implemented, the investigation considered a clean-stock observer intended to measure:

```text
B2
B3
O
PA8
EM1 / EM2 entry
WFI attempts
PA8 vetoes
shadow B2 ownership
```

without serializing the native B2 race.

That was the correct experimental plan at the time because the physical occurrence of the statically demonstrated race had not yet been separated from the effect of a correction.

The observer had strict noninterference requirements:

- no new synchronization across the native B2 race
- no scheduler suspension around the race
- no changed task priorities
- no changed IRQ priorities
- no changed B2/B3 policy
- no PA8 bypass
- no WF200 replacement
- no Beacon Recovery correction

This clean-stock Host Observer is now **historical design work**.

It is no longer the current diagnostic platform.

---

# 39. Why the Observer Architecture Changed

The project subsequently progressed beyond the original stock-observer phase.

The B2 correction was independently reconstructed and qualified through executable preemption and ownership testing.

At the same time, further PM work produced:

```text
A1
    |
    +-- experimental regression discovered
    |
    v
A1R
```

The current need therefore changed.

Instead of asking only:

> Can the stock B2 race occur?

the long-term experiment now asks:

> Does the integrated corrected platform still develop a real battery-drain episode, and if so, what native PM52/cmd66 state appears first?

That is why the current observer is no longer the original Stock Host Observer.

---

# 40. PM52 → cmd66 Observer

The current observer records the already-existing WLAN PM and beacon-statistics lifecycle.

Telemetry includes:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing periodic command-0x66 requests/results
- fresh estimator operands
- connection epochs
- a compact recent-event ring
- first-fault freeze state

The observer deliberately generates no additional WF200 request.

It adds no:

```text
new timer
new task
new queue
automatic network traffic
flash write
policy change
```

Readout occurs only on explicit `/status` access.

The observer is therefore diagnostically different from the earlier proposed stock B2/PA8 observer.

---

# 41. B2.1 Integrated Host-Sleep Correction

The corrected observer-free baseline is:

```text
B2.1
```

It contains:

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

For host-sleep purposes, the relevant pieces are:

```text
A1R
    PM lifecycle / ownership / settlement

B2 bounded serialization
    shared blocker-counter correctness

WF200 3.18.0
    newer radio-side PM implementation
```

These are separate correction layers.

B2.1 does not enable EM3 and does not bypass PA8.

---

# 42. B2.1_OBS

The current hardware diagnostic build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

B2.1_OBS therefore already contains the qualified B2 serialization correction.

It is **not** intended to observe an uncorrected B2 lost-update race.

Its purpose is to observe the corrected integrated system and capture the first relevant PM/radio anomaly if battery drain still occurs.

The observer itself was qualified for software noninterference, while the normal caveat remains that any inserted instrumentation can in principle perturb physical timing slightly.

---

# 43. Current Hardware Experiment

The current controlled population is:

```text
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The current research decision is:

```text
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

No new host-sleep correction is currently being designed.

No EM3 experiment is currently justified.

No B2 architecture change is currently required.

The purpose of the test is to determine whether the corrected platform develops real long-term battery drain.

---

# 44. Current Interpretation of B2 Battery Relevance

The B2 race is a demonstrated firmware defect.

One direction can produce:

```text
unnecessary EM1 restriction
```

which is directly relevant to battery consumption in principle.

The opposite direction can permit EM2 too early, making the defect a correctness problem in both directions.

However, the project still has no direct laboratory measurement that establishes:

```text
historical number of B2 corruption events
×
time spent in resulting state
×
system current delta
```

for affected field devices.

Therefore the strongest supported conclusion is:

> Firmware 2.2.4 contains a demonstrated task-preemption race that can corrupt the shared B2 sleep-blocker reference count. One valid outcome can prevent the EFM32GG11 from reaching its intended EM2 idle state. The defect has been corrected experimentally through qualified bounded serialization, but its quantitative contribution to historical battery drain has not been established.

That is stronger than identifying a code smell.

It remains weaker than proving the historical battery-drain root cause.

---

# 45. What Should Not Be Changed

Current evidence does not support changing the following simply to reduce battery consumption.

### Permanent B3

Do not remove it without redesigning the RTC/tickless clock architecture.

### EM3 policy

Do not enable normal EM3 entry with the current LFXO-dependent scheduler assumptions.

### PA8 veto

Do not bypass it merely because it can prevent WFI.

It represents WLAN-side notification state.

### B2 reference counting

Do not replace the shared reference counter with a Boolean.

### B2 aggregate

Do not clear B2 globally when one owner completes.

The appropriate principle is:

> Preserve the intended power-management architecture while correcting demonstrated ownership and concurrency defects.

---

# 46. Current Correction Boundaries

The current corrected architecture separates the relevant layers approximately as:

```text
C-C
    |
    +-- Beacon Recovery estimator/control validity

A1R
    |
    +-- PM lifecycle
    +-- operation ownership
    +-- settlement
    +-- asynchronous completion validity
    +-- correction of A1 temporary-override regression

B2 bounded serialization
    |
    +-- shared blocker RMW correctness

WF200 3.18.0
    |
    +-- newer radio-side PM implementation

PA8
    |
    +-- preserved WLAN notification gate

B3
    |
    +-- preserved EM3 restriction
```

Keeping these boundaries explicit remains important for failure attribution and regression testing.

---

# 47. Current Conclusions

The EFM32GG11 host-sleep architecture is now sufficiently understood to separate several mechanisms that were initially easy to conflate.

### EM2 is the intended normal deep idle state

The permanent B3 contribution prevents normal EM3 selection because the stock RTC/tickless architecture depends on LFXO.

This is intentional.

### B2 is a shared reference counter

Multiple simultaneous B2 owners are legitimate and required.

The counter must preserve aggregate ownership.

### B2 accounting contains a demonstrated concurrency defect

Not all stock read-modify-write operations are serialized.

Concrete 2.2.4 schedules can produce both:

```text
phantom B2
```

and:

```text
lost B2
```

### Phantom B2 can incorrectly prevent EM2

A corrupted residual contribution can restrict the host to EM1 with no legitimate owner.

### Lost B2 can permit EM2 too early

A lost contribution can allow deeper sleep while another owner still requires EM1.

### B2 bounded serialization is now qualified

The correction preserves reference-counter semantics while preventing the demonstrated task-preemption lost-update schedules.

It is part of B2.1, B2.1_OBS and B2.2.

### PA8 is an independent WLAN sleep gate

PA8 HIGH can veto WFI even when B2/B3 selection otherwise permits sleep.

This is not automatically a defect.

### A1/A1R and B2 solve different problems

A1/A1R address PM transition lifecycle, ownership and settlement.

B2 serialization addresses shared aggregate-counter concurrency.

### A1 is historical; A1R is current

The original experimental A1 introduced a separate temporary-override regression.

A1R retains the lifecycle corrections while correcting that research regression.

### The original Stock Host Observer is no longer current

The current diagnostic firmware is B2.1_OBS with the PM52→cmd66 observer.

### Physical battery impact remains unresolved

The B2 defect and other corrected defects are real.

Their combined quantitative contribution to historical battery drain has not yet been demonstrated.

### The current activity is observation

The project is currently waiting for long-term B2.1_OBS evidence.

If a genuine drain event occurs, the first-fault telemetry becomes the basis for renewed reverse engineering.

If the corrected platform remains stable long term, the next logical step is observer removal followed by observer-free hardware regression testing.

The governing distinctions remain:

```text
firmware defect demonstrated
!=
battery-drain root cause proven
```

and:

```text
offline qualification
!=
long-term hardware qualification
```

---

# Related Documents

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

Host/WLAN power management:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Experimental patch details:

[`../patch/README.md`](../patch/README.md)

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Beacon counter:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Calculated beacon skip:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Periodic mDNS:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Method

This analysis combines:

- native ARM Thumb reverse engineering
- task/context reconstruction
- scheduler/preemption analysis
- reference-counter ownership analysis
- concrete interleaving reconstruction
- executable race qualification
- host-sleep control-flow analysis
- cross-version comparison
- deterministic patch construction
- composition qualification
- controlled hardware testing
- long-term runtime observation

Decompiler output is supporting evidence.

Important conclusions are checked against native instructions, reachable control flow and executable behavior where practical.

No direct electrical current measurement is currently used to assign quantitative battery impact to the B2 defect.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The analysis applies to the firmware versions and hardware investigated here.

Experimental firmware should only be used on devices where recovery or reflashing is possible.