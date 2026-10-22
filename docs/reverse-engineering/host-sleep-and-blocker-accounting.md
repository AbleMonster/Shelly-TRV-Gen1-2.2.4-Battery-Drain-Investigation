````markdown
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
- PA8 as an independent WLAN sleep gate
- the relationship between host sleep and WLAN power management
- cross-version relevance
- the boundary between these findings and the A1 patch

The main firmware target is:

```text
20240619-130912/v2.2.4@ee290818
```

Firmware 2.1.0 is also used for a narrower architectural comparison.

This document does not attempt to estimate electrical current consumption.

It describes when the firmware permits or prevents host low-power entry and identifies a correctness defect in the shared B2 blocker accounting.

---

# 1. Host MCU

The Shelly TRV Gen1 uses an:

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

A host-side sleep restriction does not directly prove that the WF200 is awake.

Likewise, a WF200 power-save state does not directly prove that the EFM32GG11 has entered EM2.

The two layers interact, but they must be analyzed separately.

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

These names describe their role in the reconstructed firmware logic.

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

This means B2 is the stronger restriction.

---

# 4. B2 and B3 Are Reference Counters

B2 and B3 should not be interpreted as simple Boolean flags.

They are aggregate reference counters.

Multiple independent software components can legitimately require the same sleep restriction at the same time.

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

This design is necessary because independent operations can overlap.

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

Replacing B2 with a Boolean would lose this ownership information.

---

# 5. Why Shared Ownership Is Correct

The fact that several tasks modify B2 is not itself a bug.

A shared reference counter is an appropriate design when multiple independent subsystems can require the same restriction.

The required invariant is:

```text
B2 == number of active B2 ownership contributions
```

The problem identified in firmware 2.2.4 is not shared ownership.

The problem is that the read-modify-write operations used to maintain the shared count are not consistently serialized.

This distinction is fundamental:

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

Therefore the normal idle selector does not reach EM3.

---

# 7. The Permanent B3 Contribution Is Intentional

A permanent sleep restriction can initially look suspicious in a battery-powered device.

In this case, however, the restriction has a concrete technical reason.

The stock firmware configures the low-frequency scheduler/RTC timebase using:

```text
LFXO
```

The RTC is used by the tickless scheduler for wake timing and elapsed-time reconstruction.

The EM3 implementation disables the low-frequency oscillators required by the current configuration.

The relevant EM3 path disables:

```text
LFXO
LFRCO
```

while EM2 retains the required clocking.

Therefore:

```text
normal deepest idle = EM2
```

is consistent with the current firmware design.

---

# 8. Why EM3 Cannot Simply Be Enabled

A tempting battery optimization would be:

```text
remove permanent B3
        |
        v
allow EM3
```

That is not a valid correction for the current firmware.

The scheduler currently depends on an RTC/tickless timebase sourced from LFXO.

Entering EM3 with the current implementation would stop that clock.

Re-enabling LFXO after wake does not recreate the RTC ticks that did not occur while the oscillator was stopped.

The problem is therefore not simply:

```text
EM3 disabled
```

but:

```text
current scheduler/timebase architecture
is not designed for normal EM3 residency
```

Using EM3 safely would require a separate redesign of the low-frequency clock and scheduler assumptions.

That would be an optimization project, not a correction of the current battery-drain defects.

---

# 9. Intended Normal Host Sleep

With the permanent B3 contribution present, the intended normal idle condition is:

```text
B2 = 0
B3 != 0
```

which permits:

```text
EM2
```

Therefore the important host-side battery question is not:

> Why does the TRV not enter EM3?

The relevant question is:

> Does the host reliably reach EM2 whenever no legitimate B2 owner requires EM1?

This distinction changed the direction of the host-sleep investigation.

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

Others use the generic blocker helper without protecting the complete read-modify-write operation from task preemption.

This mixture is the basis of the B2 concurrency defect.

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

The actual implementation also contains bounds/assertion behavior.

The important concurrency property is that the generic read-modify-write sequence is not itself globally protected against task switching.

A task can therefore be preempted after reading B2 but before storing the updated value.

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

This means O-to-O operations using this path are serialized against each other.

The problem appears when an unprotected generic B2 operation overlaps with one of these protected operations.

The protected operation is internally atomic.

The other task can still have loaded a stale B2 value before the protected operation begins.

---

# 13. Task Preemption Makes the Race Reachable

The affected operations occur in real task contexts.

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

The motor and manual-DTIM B2 operations do not locally mask interrupts or suspend scheduling around the complete generic B2 update.

Equal-priority tasks can be switched by the scheduler following an RTC tick/PendSV sequence.

The race is therefore not based on an impossible theoretical interleaving.

Native task contexts exist that can produce the required preemption.

---

# 14. B2 Concurrency Defect

The shared B2 reference count is vulnerable to a classic lost-update problem.

Consider two operations:

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

Task B's contribution can be lost or an already removed contribution can effectively be recreated.

Both directions have been reconstructed in firmware 2.2.4.

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

The correct result at this point is:

```text
B2 = 1
```

because only Task A's new ownership remains.

Instead:

```text
B2 = 2
```

When Task A later releases its own legitimate ownership:

```text
B2 2 -> 1
```

the final state is:

```text
B2 = 1
```

with:

```text
0 legitimate owners
```

This is a phantom B2 contribution.

---

# 16. Consequence of Phantom B2

The host sleep selector does not know which subsystem owns the count.

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

This can persist until some later operation happens to alter the corrupted aggregate or the system is reinitialized/reset.

The firmware defect is established.

What has not yet been established is how often this schedule occurs on physical TRV devices or how much energy a resulting EM1 period consumes in real operation.

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

Before the motor stores the increment, another WLAN operation acquires ownership through the protected path:

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

When the WLAN operation later releases:

```text
B2 1 -> 0
```

the motor still legitimately requires EM1.

The selector can now permit:

```text
EM2
```

while the motor's B2 ownership has effectively been lost.

---

# 18. Consequence of Lost B2

The B2 defect is therefore not only a battery-consumption issue.

It is a general power-management correctness problem.

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

Because B2 is a shared reference counter, a correction must not simply do:

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

If the WLAN operation finishes:

```text
correct:
B2 = 1
```

Forcing:

```text
B2 = 0
```

would incorrectly discard the motor's ownership.

The same reasoning prevents A1 or another subsystem from treating the entire aggregate as though it belonged to one PM transaction.

---

# 20. Correct Fix Direction

The smallest correction direction is to preserve the reference-counting design while making each complete check/read-modify-write operation atomic with respect to competing task contexts.

Conceptually:

```c
saved = PRIMASK;
disable_interrupts();

validate_counter();
update_counter();

restore_PRIMASK(saved);
```

The exact implementation must preserve:

- existing assertion semantics
- caller ABI
- nested interrupt-mask state
- ownership semantics
- task behavior
- timing constraints

The objective is not to redesign the blocker model.

It is to make the existing shared reference counter safe against the demonstrated preemption race.

No such global B2 correction is part of the current A1 patch.

---

# 21. Relationship to A1

A1 corrects a different set of host power-management problems.

Its scope includes issues such as:

- Final-Sleep failure cleanup
- Wake failure handling
- timeout versus cancellation
- late PM completion
- requested versus committed PM state
- PM generation/settlement
- independent inhibit ownership
- association/handoff correctness

These defects involve PM operation lifecycle and ownership.

The global B2 race occurs in the common blocker accounting used by multiple subsystems.

Conceptually:

```text
A1
    |
    +-- PM lifecycle
    +-- operation ownership
    +-- settlement
    +-- failure handling


B2 race
    |
    +-- shared reference counter
    +-- generic read-modify-write
    +-- task preemption
```

The B2 race is therefore outside A1's current scope.

It is not an A1 regression.

---

# 22. Final-Sleep and B2

A previously identified Final-Sleep failure path can retain a B2 contribution when cleanup/release is not completed correctly.

This can also result in:

```text
B2 != 0
```

without the expected normal lifecycle completing.

That defect and the global B2 concurrency race must not be conflated.

They are two different ways to reach an incorrect blocker state:

```text
Final-Sleep defect
    |
    +-- lifecycle / release failure


B2 concurrency defect
    |
    +-- aggregate reference-count corruption
```

A1 addresses the qualified Final-Sleep lifecycle problem.

It does not globally serialize unrelated B2 modifications.

---

# 23. Initialization and B2

A separate initialization path also contains ownership timing relevant to B2.

The important distinction is again between:

```text
operation-specific ownership lifecycle
```

and:

```text
global aggregate counter correctness
```

A1 corrects the qualified PM handoff/lifecycle behavior.

The later B2 audit showed that even if every individual owner follows the intended acquire/release lifecycle, the shared aggregate can still become corrupted if concurrent updates are not serialized.

Therefore:

```text
all owners individually balanced
```

does not guarantee:

```text
B2 aggregate remains correct
```

when lost updates are possible.

---

# 24. PA8 Is a Separate Sleep Gate

B2/B3 selection is not the final condition before host sleep.

The firmware also samples GPIO PA8.

PA8 was traced to the WLAN host-notification path.

Board initialization configures PA8 as an input with pull-down behavior.

A rising condition maps into the GPIO interrupt path and ultimately to WLAN/bus-worker processing.

The exact schematic net name and external electrical implementation have not been recovered from the firmware alone.

Functionally, however, PA8 participates in communication from the WLAN side to the host.

---

# 25. PA8 Sleep Veto

Before executing the low-power instruction, the sleep callback checks PA8.

If PA8 is LOW:

```text
selected sleep path may continue
```

If PA8 is HIGH:

```text
WFI is not executed
```

This can be represented as:

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

# 26. Why PA8 Is Not a Reference Counter

PA8 and B2 represent different types of state.

B2 answers:

> How many software owners currently require EM1?

PA8 answers approximately:

> Is the WLAN notification line currently asserted?

B2 therefore needs shared ownership accounting.

PA8 is a physical signal level.

A useful conceptual distinction is:

```text
B2:
"How many people are still working in the workshop?"

PA8:
"Is the doorbell currently ringing?"
```

Treating PA8 as another reference-counted software owner would not match its observed role.

---

# 27. PA8 HIGH Is Not Automatically a Bug

A WLAN device asserting a host-notification signal while work is pending is normal behavior.

Preventing WFI while that notification remains asserted can therefore be intentional.

The important runtime questions are instead:

```text
How often is PA8 HIGH at sleep admission?

How long does it remain HIGH?

Does it repeatedly veto WFI?

Does this correlate with a battery-drain episode?

Does it correlate with WLAN Recovery or another radio state?
```

Static analysis alone cannot answer these questions.

A persistent PA8 HIGH condition would demonstrate that WFI is being prevented.

It would not, by itself, identify why the WLAN side keeps the signal asserted.

---

# 28. Sleep Selection and PA8 Are Separate

A device can have:

```text
B2 = 0
B3 != 0
```

so that the selector chooses:

```text
EM2
```

but still fail to execute WFI because:

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

This distinction is important for runtime telemetry.

A useful observer must distinguish at least:

```text
mode selected
```

from:

```text
WFI reached
```

where instrumentation can do so without changing the behavior being measured.

---

# 29. Sleep Entry Atomicity

The final scheduler admission, blocker selection and low-power entry sequence uses interrupt masking around the critical selection/entry region.

No separate race was demonstrated in which B2 is changed after a correct selector read but before WFI in a way that invalidates the selected mode.

The important B2 defect occurs earlier:

```text
B2 aggregate already corrupted
        |
        v
selector reads corrupted but stable value
        |
        v
selector makes internally consistent decision
```

The selector itself can therefore operate correctly while still choosing the wrong effective restriction because the reference counter was previously corrupted.

---

# 30. Deep-Sleep Preparation and Restoration

The EM2/EM3 paths contain state-save and restoration logic around low-power entry.

A potential concern was whether the PA8 veto could occur after hardware state had already been modified for deep sleep and therefore leave the system partially prepared.

Further analysis showed that the relevant early save operation snapshots/waits but does not perform the destructive hardware transition that would require restoration before the PA8 check returns.

No separate PA8-veto preparation/restoration defect was established.

The returning EM2/EM3 paths contain the expected restoration behavior.

---

# 31. `SLEEPDEEP`

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

# 32. `/stats sleep_ratio`

Firmware 2.2.4 exposes:

```text
sleep_ratio
```

through `/stats`.

Reverse engineering of the corresponding calculation shows that this value is based on tickless timing/compensation behavior.

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

Therefore a low or high `sleep_ratio` value must not be interpreted as a direct percentage of physical sleep time.

This limitation is important when comparing battery behavior between firmware variants.

---

# 33. Host Sleep vs. WF200 Power Save

The host and radio can independently have power-state problems.

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

# 34. Relationship to Beacon Recovery

Beacon Recovery changes WLAN power-management behavior and therefore can affect the conditions under which host-side sleep ownership is acquired and released.

However, Beacon Recovery and the B2 concurrency defect are different mechanisms.

Beacon Recovery is driven by the 2.2.4 beacon-statistics/control path.

The B2 problem exists in the shared host sleep-blocker infrastructure.

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

The project does not currently claim that every B2 corruption event must originate from Beacon Recovery.

---

# 35. Cross-Version Relevance

A narrower comparison with firmware 2.1.0 found the same broad host-sleep architecture.

Firmware 2.1.0 also contains:

- the B2/B3 blocker architecture
- the permanent startup B3 contribution
- equivalent sleep selection
- the PA8 sleep callback
- EM2/EM3 dispatch
- generic unprotected aggregate blocker helpers

This means the architecture relevant to the B2 problem predates firmware 2.2.4.

That is important because historical battery drain also predates 2.2.4.

However, the complete task-level concurrency witness established for 2.2.4 has not been closed to the same depth for 2.1.0.

The supported conclusion is therefore:

> The vulnerable blocker architecture exists in both analyzed generations, while the complete concrete task-preemption schedules have been demonstrated for firmware 2.2.4.

It would be too strong to claim identical runtime incidence in 2.1.0 without the corresponding task-level analysis.

---

# 36. Why the Cross-Version Result Matters

The B2 finding is different from Beacon Recovery.

Beacon Recovery in its analyzed form is a later 2.2.4 mechanism.

The shared host blocker architecture is older.

Therefore the B2 defect class is at least structurally compatible with the fact that battery-drain behavior was also observed on older firmware.

This makes it a more interesting candidate for a common host-side mechanism.

It still does not prove historical battery-drain causality.

To establish that, physical runtime evidence is required.

---

# 37. Runtime Questions

The most important remaining host-sleep questions are:

1. Does B2 become non-zero without a legitimate owner on physical hardware?

2. Does B2 become smaller than the number of legitimate owners?

3. If phantom B2 occurs, how long does it persist?

4. How often does the host actually attempt EM1?

5. How often does the host actually attempt EM2?

6. How often does PA8 veto WFI?

7. Can PA8 remain HIGH for extended periods?

8. Do these conditions correlate with rapid battery-voltage decline?

9. Do they correlate with Beacon Recovery?

10. Do they occur on stock firmware without any experimental corrective patch?

These questions motivate the Stock Host Observer work.

---

# 38. Observer Requirements

A diagnostic observer for this problem must preserve the defect it is intended to measure.

It must not:

- make generic B2 operations atomic
- extend PRIMASK across the native B2 race window
- suspend scheduling around the native race window
- replace the stock B2 helper
- change task priorities
- change IRQ priorities
- change B2/B3 selection
- change PA8 behavior
- change the WF200 firmware
- change Beacon Recovery

Otherwise the measurement could eliminate the condition being investigated.

A passive observer can still have timing overhead and therefore affect race probability.

That limitation must be documented.

---

# 39. Useful Observer Telemetry

Useful low-perturbation telemetry includes:

```text
current:
    B2
    B3
    O
    PA8

sleep:
    EM1 entries
    EM2 entries
    WFI attempts
    PA8 vetoes

B2 ownership:
    acquire attempts
    release attempts
    owner class

shadow accounting:
    expected B2
    actual B2
    mismatch state

diagnostics:
    first qualified mismatch
    recent B2 events
```

A shadow owner model is particularly useful because it can distinguish:

```text
known owners = 0
actual B2    = 1

-> possible phantom contribution
```

from:

```text
known owners = 1
actual B2    = 0

-> possible lost contribution
```

Such a comparison is only valid when the observer has sufficient coverage of the relevant owner classes.

---

# 40. Entry Counts Are Not Residency

Even a correctly implemented observer must distinguish:

```text
EM2 entry count
```

from:

```text
time physically spent in EM2
```

A count tells us how often an entry path was reached.

It does not by itself tell us how long the MCU remained there.

Likewise:

```text
PA8 veto count
```

does not directly provide total PA8-HIGH duration.

Any future residency measurement requires a timebase that remains valid across the relevant low-power states and does not materially perturb them.

The stock tickless RTC cannot simply be assumed to provide a continuous independent physical-residency clock.

---

# 41. Battery-Drain Interpretation

The B2 race is a demonstrated firmware correctness defect.

One direction can create:

```text
unnecessary EM1 restriction
```

which is directly relevant to battery consumption in principle.

However, the project currently has no direct electrical measurement of:

```text
EM1 current
EM2 current
time spent in each state
```

for the complete TRV system under the observed failure condition.

Therefore the strongest supported statement is:

> Firmware 2.2.4 contains a task-preemption race that can corrupt the shared B2 sleep-blocker reference count. One demonstrated outcome can incorrectly prevent the EFM32GG11 from entering its intended EM2 idle state. Physical occurrence rate and battery impact remain to be measured.

This is a stronger result than a hypothetical code smell, but weaker than a demonstrated battery-drain root cause.

---

# 42. Current Correction Strategy

The current host-side strategy is:

```text
first:
    observe stock behavior

then:
    determine whether B2 corruption occurs
    on physical hardware

if confirmed:
    serialize the complete B2 reference-counter
    read-modify-write operations

then:
    compare stock observer
    vs.
    corrected observer

finally:
    integrate the qualified B2 correction
    with the other host/radio corrections
```

The intended integrated correction path would then contain separate fixes for:

```text
C-C
    Beacon Recovery validity

A1
    PM lifecycle / ownership

future B2 correction
    shared blocker-counter concurrency

WF200 3.18.0
    newer radio-side PM implementation
```

Each component addresses a different defect class.

---

# 43. What Should Not Be Changed

The current evidence does not support changing the following simply to reduce battery consumption:

### Permanent B3

Do not remove it without redesigning the RTC/tickless clock source.

### EM3 policy

Do not enable normal EM3 entry with the current LFXO-dependent scheduler configuration.

### PA8 veto

Do not bypass it merely because it can prevent WFI. It represents WLAN-side notification state.

### B2 reference counting

Do not replace it with a Boolean.

### B2 aggregate

Do not clear it globally when one owner completes.

The appropriate goal is:

> Preserve the intended power-management architecture while correcting demonstrated ownership and concurrency defects.

---

# 44. Current Conclusions

The EFM32GG11 host-sleep architecture is now sufficiently understood to separate several previously conflated mechanisms.

### EM2 is the intended normal deep idle state

The permanent B3 contribution prevents EM3 because the stock RTC/tickless implementation depends on LFXO.

This is intentional and technically justified.

### B2 is a shared reference counter

Multiple simultaneous B2 owners are valid and required.

The counter must therefore preserve aggregate ownership.

### B2 accounting contains a real concurrency defect

Not all read-modify-write operations are serialized.

Concrete 2.2.4 task schedules can produce both:

```text
phantom B2
```

and:

```text
lost B2
```

### Phantom B2 can incorrectly prevent EM2

A corrupted residual contribution can leave the host restricted to EM1 with no legitimate owner.

### Lost B2 can permit EM2 too early

A lost contribution can allow EM2 while another subsystem still requires EM1.

### PA8 is an independent WLAN sleep gate

PA8 HIGH can veto WFI even when the blocker selector would otherwise permit sleep.

This is not automatically a defect.

### A1 does not solve the global B2 race

A1 addresses PM lifecycle, ownership and settlement defects.

The shared blocker-counter concurrency problem is a separate issue.

### Physical runtime evidence is still required

The code defect is established.

Its occurrence frequency, persistence and quantitative contribution to battery drain are not yet established.

The next useful step is passive observation of stock firmware without correcting the race being measured.

---

# Related Documents

Host/WLAN power management:

[`power-management-and-sleep.md`](power-management-and-sleep.md)

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Beacon counter:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Calculated beacon skip:

[`real-beacon-skip.md`](real-beacon-skip.md)

Beacon Recovery:

[`recovery-mechanism.md`](recovery-mechanism.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Periodic mDNS:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

Experimental