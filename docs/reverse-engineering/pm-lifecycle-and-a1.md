````markdown
# WLAN Power-Management Lifecycle and A1

## Shelly TRV Gen1 Firmware 2.2.4

## Scope

This document describes a group of host-side WLAN power-management defects identified in Shelly TRV Gen1 firmware 2.2.4 and the experimental A1 correction developed from that analysis.

The main firmware target is:

```text
20240619-130912/v2.2.4@ee290818
```

The analysis focuses on the lifecycle of asynchronous WLAN power-management operations rather than on the Beacon Recovery estimator itself.

The relevant defect classes include:

```text
G01  Final-Sleep failure cleanup
G02  Wake failure state handling
G03  timeout versus cancellation
G05  late completion after timeout
G06  requested versus committed PM state
G18  independent inhibit ownership
G19  old PM completion race
```

A1 was designed to correct these problems while preserving the surrounding WLAN behavior.

A1 does not attempt to:

- disable Beacon Recovery
- correct the C1a/C1b/C2 Beacon Recovery defects
- enable EM3
- replace the host sleep architecture
- globally clear B2
- globally serialize all B2 reference-counter operations
- modify the WF200 radio firmware

Those are separate topics.

---

# 1. Two Different Power-Management Problems

The investigation identified two broad host-side problem classes.

The first is the lifecycle of asynchronous WLAN power-management operations:

```text
request
    |
    v
lower-level operation
    |
    +-- success
    |
    +-- failure
    |
    +-- timeout
    |
    +-- late completion
```

The second is the shared host sleep-blocker accounting:

```text
B2
B3
PA8
EM1 / EM2 / EM3
```

A1 primarily addresses the first class.

The later-discovered global B2 read-modify-write race belongs to the second class and remains outside A1.

This distinction is important when interpreting the patch.

---

# 2. Asynchronous WLAN PM Operations

Several WLAN power-management operations are not simple synchronous function calls.

The host requests a transition and lower layers complete it asynchronously.

A simplified lifecycle is:

```text
host wants new PM state
        |
        v
prepare operation
        |
        v
submit lower-level request
        |
        v
wait for completion
        |
        +-- accepted / completed
        |
        +-- rejected / failed
        |
        +-- timeout
```

Correct behavior requires the host to keep several different concepts separate:

```text
desired state
requested state
accepted operation
committed state
completion identity
ownership
timeout state
cancellation state
```

Firmware 2.2.4 does not consistently preserve all of these distinctions.

---

# 3. Requested State Is Not Committed State

One central problem is treating a requested PM transition too much like an already established state.

Conceptually:

```text
desired PM state
        |
        v
request submitted
        |
        v
???
        |
        v
lower layer confirms success
```

The host must not assume the transition is committed before the lower layer has actually accepted and completed the relevant operation.

The correct conceptual model is:

```text
desired
    |
    v
requested
    |
    v
accepted
    |
    v
committed
```

These stages are not interchangeable.

A request can fail or become obsolete before commitment.

---

# 4. G06 — Requested vs. Committed PM State

The 2.2.4 control flow contains paths where software-visible PM state is advanced before lower-level success is sufficiently established.

This creates the possibility that:

```text
host state says:
    transition established
```

while:

```text
lower-level reality says:
    transition failed or never completed
```

Once these states diverge, later logic can make decisions using an incorrect assumption about the current WLAN PM state.

A1 separates intent from accepted/committed state more explicitly.

The corrected model is approximately:

```text
desired state
        |
        v
start transition
        |
        v
transition pending
        |
        +-- success
        |      |
        |      v
        |   commit state
        |
        +-- failure
               |
               v
        preserve/recover previous
        committed state
```

---

# 5. G01 — Final-Sleep Failure Cleanup

One important path occurs during the final transition toward the WLAN sleep configuration.

The normal sequence approximately contains:

```text
acquire wake / sleep-blocking ownership
        |
        v
prepare WLAN PM transition
        |
        v
perform final lower-level sleep operation
        |
        v
release temporary ownership
```

The stock failure path does not always reach the same cleanup/release logic as the successful path.

Conceptually:

```text
acquire
    |
    v
final operation
    |
    +-- success -> cleanup -> release
    |
    +-- failure -> return
                    |
                    X
                 release missed
```

This can retain software ownership that should have been released after the failed transition.

Because that ownership participates in host sleep restrictions, the defect can affect later low-power behavior.

---

# 6. Why G01 Is Not Fixed by Clearing B2

The retained resource contributes to shared blocker accounting.

That does not mean the correct fix is:

```c
B2 = 0;
```

B2 can contain contributions from other legitimate owners.

The correction must release only the ownership associated with the failed operation.

A1 therefore repairs the operation lifecycle rather than overwriting the aggregate blocker state.

This preserves unrelated concurrent ownership.

---

# 7. G02 — Wake Failure State Handling

The inverse direction has a related problem.

During wake handling, software state can be cleared or advanced before the corresponding lower-level wake operation has successfully completed.

Conceptually:

```text
software marks wake ownership/state resolved
        |
        v
hardware / lower-level wake operation
        |
        +-- success
        |
        +-- failure
```

If the lower operation fails after software has already discarded the previous state, the host no longer has a reliable representation of what actually happened.

The corrected rule is:

> Do not discard the previously committed state merely because a new transition was requested.

A1 keeps the transition pending until the relevant result is known.

---

# 8. Failure Must Preserve Recoverable State

A useful general invariant is:

```text
before operation:
    known committed state A

request:
    move toward B
```

If the request fails:

```text
committed state must not silently become B
```

and the information needed to recover or retry must not already have been destroyed.

The lifecycle should therefore behave approximately as:

```text
committed A
    |
    v
request B
    |
    +-- success -> committed B
    |
    +-- failure -> committed A / explicit recovery state
```

rather than:

```text
committed A
    |
    v
request B
    |
    v
immediately publish B
    |
    v
operation fails
    |
    v
software and lower layer disagree
```

---

# 9. G03 — Timeout Is Not Cancellation

Another central defect class is the treatment of timeout.

For an asynchronous operation:

```text
wait_for_completion(timeout)
```

returning because the timeout expired establishes only:

```text
the expected completion was not observed
within the allowed waiting interval
```

It does not automatically establish:

```text
the lower-level operation has been cancelled
```

The operation may still be:

- queued
- executing
- completing
- delivering an event
- visible to another task

This distinction is fundamental to A1.

---

# 10. Why Timeout and Cancellation Must Be Separate

Consider:

```text
host submits operation X
        |
        v
host waits
        |
        v
timeout
```

If the host immediately assumes:

```text
X no longer exists
```

but the lower layer later reports:

```text
X completed
```

the late event can be mistaken for a newer operation or applied to state that has already moved on.

The correct model must account for the possibility:

```text
timeout
    !=
confirmed cancellation
```

A1 therefore treats unresolved timed-out operations as a separate state until ownership of the completion path is settled.

---

# 11. G05 — Late Completion

Once timeout is separated from cancellation, the next problem becomes clear.

An old operation can complete after the host has stopped waiting for it.

For example:

```text
operation A submitted
        |
        v
timeout A
        |
        v
host begins recovery / new operation
        |
        v
late completion A arrives
```

Without sufficient identity or generation tracking, the late completion can affect current state.

This is especially dangerous when the completion format does not itself contain enough information to distinguish:

```text
old A
```

from:

```text
current B
```

at the point where the event is consumed.

---

# 12. Old Completion vs. Current Intent

A robust asynchronous state machine needs to answer:

> Does this completion belong to the operation that currently owns the transition?

The answer cannot safely be inferred only from:

```text
an event occurred
```

or:

```text
the event type looks correct
```

because the event may belong to an older request.

A1 therefore introduces stronger operation identity/generation semantics around the transition lifecycle.

Conceptually:

```text
generation N
    request A

generation N+1
    request B

late completion from N
        |
        v
must not commit state for N+1
```

---

# 13. G19 — Old PM Completion Race

The old-completion problem is not limited to a simple timeout return.

The host can begin a new PM transition while a previous lower-level operation still has the ability to produce a completion.

Without a sufficiently strict settlement boundary:

```text
old operation
        |
        +----------+
                   |
new operation     |
    |              |
    v              v
pending state   late completion
    |              |
    +------?-------+
```

the completion can be attributed to the wrong transition.

A1 treats the old operation as unresolved until the relevant handoff/settlement conditions are satisfied.

This prevents a new policy decision from simply inheriting an ambiguous completion channel.

---

# 14. Settlement

A useful concept in A1 is **settlement**.

An operation is not settled merely because the caller has stopped waiting.

Settlement requires enough evidence that the previous operation can no longer legitimately alter the state owned by the next transition.

Depending on the path, this can require confirming properties such as:

```text
expected terminal state reached
no owed completion remains
no cancellation ambiguity remains
handoff identity is valid
```

Only after these conditions are satisfied should ownership move cleanly to the next transition.

---

# 15. G18 — Independent Inhibit Ownership

Power-management restrictions can be requested by more than one reason.

A single Boolean such as:

```text
PM inhibited = true/false
```

is insufficient when independent causes can overlap.

For example:

```text
reason A acquires inhibit
reason B acquires inhibit

reason A releases
```

The correct result is:

```text
inhibit remains active
```

because reason B still owns it.

The general rule is:

> One owner must not release another owner's power-management restriction.

A1 preserves independent ownership rather than treating all inhibits as one undifferentiated state.

---

# 16. Ownership Is Different From Desired Policy

Another important distinction is between:

```text
what PM policy the host currently wants
```

and:

```text
which operation currently owns the transition
```

The desired policy can change while an older transition is still unresolved.

For example:

```text
desired = sleep
        |
        v
sleep transition begins
        |
        v
desired changes to active
        |
        v
old sleep completion arrives
```

The old completion must not override the newer intent simply because it completed successfully.

A1 therefore keeps desired policy and operation ownership/version separate.

---

# 17. Policy Versioning

A useful conceptual representation is:

```text
desired policy:
    state + version

transition:
    generation / owner

completion:
    accepted only for matching owner/generation
```

When the desired state changes:

```text
version N
    ->
version N+1
```

a completion belonging to version N must not silently establish policy for N+1.

This protects against stale asynchronous results.

---

# 18. Association and PM Handoff

Association is a particularly sensitive point because WLAN identity and PM policy become connected.

The host must not publish PM policy for an association merely because part of the JOIN sequence appears successful.

The transition must correspond to the association identity that currently owns the connection.

A simplified requirement is:

```text
JOIN result
    |
    v
validate association identity
    |
    v
validate accepted terminal state
    |
    v
validate no cancellation / owed event ambiguity
    |
    v
validate handoff topology
    |
    v
publish PM policy
```

Publishing policy before these checks creates the possibility that PM state is attached to a stale or rejected association handoff.

---

# 19. Association Normalization in A1

During A1 qualification, association normalization became an important correctness gate.

The final implementation validates the relevant association/JOIN ownership and handoff conditions before policy publication.

Rejected or stale handoffs return before modifying the new transition state.

The protected rejection boundary prevents changes to items such as:

```text
A / saved association state
desired intent/version
PM generation
transition state
PM setup
additional C-C baseline state
```

when the handoff is not accepted.

This was a necessary correction to an earlier A1 integration candidate.

---

# 20. Why Atomic Publication Matters

It is not sufficient to perform all required checks if policy is published between them.

For example:

```text
check association
        |
        v
publish policy
        |
        v
discover cancellation / stale handoff
```

is still incorrect.

The final A1 integration keeps the relevant validation and publication relationship inside the required bounded atomic section.

Conceptually:

```text
enter protected section

validate owner
validate terminal state
validate cancellation state
validate handoff

if invalid:
    leave without publication

publish policy

leave protected section
```

This prevents a rejected handoff from becoming externally visible as accepted PM policy.

---

# 21. A1 State Model

A1 adds explicit state needed to distinguish concepts that stock control flow conflates.

At a high level, the corrected model tracks concepts equivalent to:

```text
desired PM intent
desired version

current transition
transition generation

accepted / committed PM state

outstanding operation ownership

settlement state

independent inhibit ownership

association handoff identity
```

The exact binary representation is an implementation detail.

The important part is the separation of lifecycle states.

---

# 22. A1 Does Not Replace the Stock PM Architecture

A1 is intentionally bounded.

It does not replace Shelly's WLAN power-management strategy with a new one.

It preserves:

- existing PM policy
- existing WLAN driver
- existing WF200 command model
- existing Beacon Recovery policy outside C-C
- existing scheduler
- existing B2/B3 selector
- existing PA8 behavior
- existing motor behavior
- existing OTA behavior

The patch changes lifecycle correctness around identified failure paths.

This reduces the number of unrelated variables introduced during testing.

---

# 23. Relationship to C-C

C-C and A1 address different layers.

C-C corrects the Beacon Recovery decision chain:

```text
WF200 beacon statistics
        |
        v
host estimator
        |
        v
freshness / validity
        |
        v
Beacon Recovery decision
```

A1 corrects WLAN PM transition lifecycle:

```text
desired PM policy
        |
        v
operation ownership
        |
        v
lower-level request
        |
        v
completion / timeout
        |
        v
settlement
        |
        v
committed state
```

They can therefore be combined without representing the same correction twice.

---

# 24. Relationship to the B2 Concurrency Defect

The later host-sleep audit identified a separate defect in the shared B2 reference counter.

That defect occurs because some B2 read-modify-write operations are not serialized against competing task contexts.

A1 does not globally change those helpers.

Therefore:

```text
A1 installed
```

does not imply:

```text
B2 accounting globally race-free
```

The final A1 helper bytes for unrelated manual/motor/OTA blocker operations remain stock-equivalent.

This separation is intentional.

A future B2 correction must be qualified independently.

---

# 25. Relationship to B3 and EM3

A1 does not remove the permanent B3 contribution.

The host-sleep analysis shows that B3 has a valid purpose.

Stock firmware uses LFXO for the RTC/tickless scheduler timebase, while the EM3 path disables the relevant low-frequency oscillators.

Therefore:

```text
EM2
```

remains the intended normal deepest idle mode.

A1 is not an EM3 optimization patch.

---

# 26. Relationship to PA8

A1 also does not bypass the PA8 WLAN notification gate.

PA8 can independently prevent WFI when the WLAN notification path is asserted.

That behavior is separate from PM lifecycle ownership.

A1 therefore preserves it.

If PA8 prevents host sleep excessively during a real battery-drain episode, that must be investigated separately.

---

# 27. Relationship to WF200 Firmware

A1 is a host-side correction.

It does not modify the protected WF200 radio firmware.

This matters because the WF200 can have its own power-management behavior and defects independent of the host lifecycle.

The project has separately tested:

```text
WF200 3.18.0
```

with Shelly's existing:

```text
FMAC 3.7.0
```

but that radio update is not part of the A1 mechanism itself.

The integrated experimental firmware combines the two intentionally separate changes.

---

# 28. Why A1 Is Not a Blind Recovery Patch

A tempting response to an uncertain PM state would be to force a known state whenever something goes wrong.

For example:

```text
timeout
    |
    v
force active
```

or:

```text
failure
    |
    v
clear all blockers
```

Such approaches can hide the original lifecycle error while introducing new ownership violations.

A1 instead attempts to preserve:

```text
who owns the transition
what state is actually committed
which completion is still valid
which restriction belongs to which owner
```

The objective is consistency rather than forced convergence at any cost.

---

# 29. Failure-Path Symmetry

One recurring theme in the stock code is that successful paths are generally better defined than exceptional paths.

A correct asynchronous PM operation needs lifecycle symmetry:

```text
acquire
    |
    v
start
    |
    v
complete
    |
    v
release
```

and also:

```text
acquire
    |
    v
start
    |
    v
fail / timeout / cancel
    |
    v
settle
    |
    v
release or transfer ownership correctly
```

A1 concentrates heavily on the second sequence.

Battery-powered devices spend most of their life repeating PM transitions, so rare lifecycle failures can matter even if the normal path is correct.

---

# 30. Static Qualification Strategy

A1 was not qualified only by checking that the patched binary boots or that the changed instructions decode.

The qualification process tested behavior and construction at several levels.

Important checks included:

- expected control flow
- success paths
- failure paths
- timeout paths
- stale completion paths
- association handoff rejection
- incoming interrupt-mask states
- state publication ordering
- corruption fixtures
- relocation correctness
- whole-application provenance
- deterministic construction

The goal was to find counterexamples to the intended invariants before hardware testing.

---

# 31. Canonical Behavior Controls

The final A1 production integration passed:

```text
33 / 33
```

actual final-byte behavior scenarios.

In addition:

```text
3
```

canonical protected-byte controls passed.

Combined:

```text
36 / 36 canonical PASS
```

These controls exercise the final application bytes rather than only a source-level model.

They include the corrected association/handoff publication behavior.

---

# 32. Malformed and Corruption Controls

Qualification also deliberately introduced invalid constructions and corrupted assumptions.

The final process included:

```text
36 malformed construction fixtures
```

which were required to reject.

Additional qualification included:

```text
38 supplemental corruption fixtures
```

and:

```text
8 settlement corruption fixtures
```

which also rejected as intended.

The purpose of these tests is to verify that the build and lifecycle logic fail closed when required assumptions are violated.

---

# 33. Atomic-Guard Qualification

The corrected association/handoff guard was tested in both positive and rejected execution cases.

The final guard-specific execution set passed:

```text
4 / 4
```

Host-selection qualification additionally exercised:

```text
198 assertions
```

and independent raw mutation tests rejected:

```text
33 / 33
```

invalid mutations.

These tests specifically target the publication-ordering problem found in the earlier integration candidate.

---

# 34. PM Structural Qualification

The existing PM structural suite retained:

```text
26 checks
```

and the final qualification added:

```text
6 critical-precondition mutations
```

These tests passed with the final A1 integration.

The purpose is to ensure that the corrected lifecycle is installed only when the expected stock structure is present.

---

# 35. Hook and Relocation Qualification

The final integrated application contains:

```text
93 hooks
```

and:

```text
210 relocations
```

relevant to the complete experimental integration.

All were decoded and checked during final qualification.

Whole-application reconstruction produced:

```text
zero unexplained changes
```

This is important because a successful patch is not sufficient if unrelated bytes have changed without explanation.

---

# 36. Interrupt-Mask Preservation

A1 introduces bounded protected sections where required for lifecycle consistency.

These sections must preserve the incoming interrupt-mask state.

The patch must behave correctly when entered with:

```text
PRIMASK = 0
```

and when entered with:

```text
PRIMASK = 1
```

The final qualification explicitly tested both conditions.

This avoids the common patching error of unconditionally re-enabling interrupts on exit from a helper that was entered while interrupts were already disabled.

---

# 37. Rejected Handoffs Must Be Side-Effect Free

One of the strongest A1 invariants is that a rejected association/PM handoff must not partially publish the new policy.

For a rejected stale or invalid handoff, the final implementation returns before modifying the relevant new-policy state.

Conceptually:

```text
invalid handoff
        |
        v
reject
        |
        +-- no new desired publication
        +-- no new generation publication
        +-- no transition publication
        +-- no PM setup
        +-- no unrelated C-C baseline action
```

This prevents partial state from surviving a rejected transition.

---

# 38. Earlier A1 Integration Failure

An earlier A1 integration candidate did not satisfy this requirement.

The relevant control case showed that policy publication could occur before the cancellation/topology guard had fully validated the handoff.

That candidate was correctly classified as:

```text
NO-GO
```

The production integration was changed so that validation and publication occur in the correct order.

This historical failure is useful because it demonstrates why the final qualification checks publication ordering rather than only final state.

---

# 39. Final Static Verdict

After correcting the association normalization/publication issue, the final static qualification verdict was:

```text
A1 PRODUCTION INTEGRATION QUALIFIED FOR CONTROLLED DEVICE TEST
```

This verdict means that the bounded static and executable qualification gates required for controlled hardware testing passed.

It does not mean:

```text
production firmware
```

or:

```text
battery-drain root cause proven
```

---

# 40. Integrated Hardware Test

A1 was subsequently combined with:

```text
C-C
+
WF200 3.18.0
```

and installed on a controlled physical TRV.

The integrated firmware successfully completed OTA installation and cold boot.

Runtime initialization showed:

```text
FMAC 3.7.0
WF200 3.18.0
```

and normal operation continued, including:

- WLAN initialization
- scanning
- association
- DHCP
- cloud connectivity
- WLAN power-save operation
- thermostat operation
- valve operation

This provides hardware evidence that the A1 integration does not immediately break the normal TRV operating path under the tested conditions.

Long-term testing remains necessary.

---

# 41. Integrated Artifact

The controlled-test artifact is:

```text
SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl
```

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

These identities apply to the specific integrated experimental build.

They are not identities for a standalone A1-only firmware.

---

# 42. Hardware Runtime Does Not Prove A1 Battery Impact

Successful boot and operation establish important integration properties.

They do not establish:

```text
A1 improves battery lifetime by X
```

or:

```text
A1 fixes the historical drain
```

A1 corrects demonstrated host-side lifecycle defects.

The remaining questions are:

- how frequently those stock defects occur on physical devices
- how long their resulting states persist
- whether they materially increase host or radio power consumption
- how they interact with the separate B2 accounting defect
- how they interact with WF200 behavior

These require runtime evidence.

---

# 43. Why A1 Remains Relevant Without Root-Cause Proof

A firmware correctness defect does not need to be the dominant battery-drain cause to justify correction.

For example:

```text
timeout treated as cancellation
```

is incorrect even if it occurs only rarely.

Likewise:

```text
failed transition leaves ownership unresolved
```

is a lifecycle defect even if another mechanism consumes more energy.

A1 therefore has two separate evaluation questions:

```text
Is the stock behavior incorrect?
```

and:

```text
How much battery impact does that incorrect behavior have?
```

The first has been answered for the qualified A1 defect set.

The second remains a runtime question.

---

# 44. Cross-Version Relevance

Some of the lower-level host PM architecture predates firmware 2.2.4.

In particular, the Final-Sleep retention mechanism and broad host sleep architecture are also present in older firmware such as 2.1.0.

This matters because historical battery drain predates 2.2.4.

However, later firmware changes:

- WLAN PM sequencing
- asynchronous control paths
- FMAC behavior
- WF200 firmware
- Beacon Recovery
- network maintenance

and can alter how often shared mechanisms are exercised.

The existence of a common low-level mechanism does not prove identical runtime incidence across firmware versions.

---

# 45. A1 and the Historical Drain Model

The current investigation does not use the model:

```text
one bug
    |
    v
all battery drain
```

A more realistic model is:

```text
shared host architecture
        |
        +-- PM lifecycle failures
        |
        +-- B2 accounting race
        |
        +-- PA8 sleep gating

later firmware behavior
        |
        +-- Beacon Recovery
        +-- changed PM sequencing
        +-- network maintenance

WF200 behavior
        |
        +-- radio-side power-save implementation
```

A1 addresses one important part of this system.

It should therefore be evaluated as one correction layer rather than as a claim that all battery problems originate from one state machine.

---

# 46. What A1 Corrects

The current A1 scope can be summarized as:

### Final-Sleep cleanup

Failure must not silently retain operation-specific ownership.

### Wake failure handling

Software state must not be discarded before lower-level success is known.

### Timeout semantics

Timeout must not be treated as proof of cancellation.

### Late completion

Old completions must not be accepted as current operations.

### Requested vs. committed state

Intent must remain distinct from successfully established PM state.

### Settlement

Old operations must be resolved sufficiently before ownership moves to a new transition.

### Independent inhibit ownership

One owner must not release another owner's restriction.

### Association handoff

PM policy must not be published for a stale or rejected association transition.

---

# 47. What A1 Does Not Correct

A1 does not currently correct:

### C1a

Signed interpretation of the Beacon Recovery estimator.

Handled by C-C.

### C1b

Invalid Beacon Recovery measurement windows.

Handled by C-C.

### C2

Reuse of historical Beacon Recovery control evidence.

Handled by C-C.

### Global B2 RMW race

The shared blocker-counter concurrency defect remains outside A1.

### PA8 behavior

The WLAN notification sleep veto remains stock.

### EM3

A1 does not alter the permanent B3/LFXO energy policy.

### WF200 internal behavior

A1 does not modify radio firmware.

### AP selection

A1 does not alter WLAN AP-selection or roaming policy.

---

# 48. Correction Boundaries

The current project therefore separates the corrections approximately as:

```text
C-C
    |
    +-- Beacon estimator/control validity


A1
    |
    +-- PM lifecycle
    +-- ownership
    +-- settlement
    +-- asynchronous completion validity


future B2 correction
    |
    +-- shared blocker RMW serialization


WF200 3.18.0
    |
    +-- newer radio-side PM implementation
```

Keeping these corrections separate during analysis makes A/B testing and failure attribution much easier.

---

# 49. Current Conclusions

The host WLAN PM control flow in firmware 2.2.4 contains several real lifecycle defects.

The most important general lessons are:

### Requested state is not committed state

A lower-level transition must succeed before the corresponding state is treated as established.

### Timeout is not cancellation

An asynchronous operation can remain live after the caller stops waiting.

### Late completions need identity

A completion must belong to the operation that currently owns the transition.

### Ownership must survive failure correctly

Failure paths need the same ownership discipline as successful paths.

### Independent restrictions need independent ownership

One PM owner must not release another owner's restriction.

### Association handoff must be validated before publication

A stale or rejected JOIN transition must not publish new PM policy.

### A1 corrects these issues without replacing the surrounding PM architecture

The patch is deliberately bounded.

### A1 does not fix the global B2 race

That defect was identified separately and requires its own correction and qualification.

### Hardware operation has been demonstrated

The integrated A1+C-C+WF200 3.18.0 firmware boots and operates on a physical TRV.

### Battery impact remains a runtime question

The corrected defects are real, but their quantitative contribution to historical battery drain has not yet been established.

---

# Related Documents

Experimental patch details:

[`../patch/README.md`](../patch/README.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

General WLAN power management:

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

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Method

This analysis combines:

- native ARM Thumb reverse engineering
- asynchronous control-flow reconstruction
- task/context analysis
- failure-path analysis
- ownership and state-machine reconstruction
- executable final-byte testing
- malformed/corruption fixtures
- whole-application reconstruction
- deterministic firmware construction
- controlled hardware testing

Decompiler output is used as supporting information.

Important lifecycle conclusions are checked against native instructions, reachable control flow and executable test cases where practical.

No direct electrical current measurement is used to infer the battery impact of A1.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The analysis applies to the firmware versions and hardware investigated here.

Experimental firmware should only be used on devices where recovery or reflashing is possible.
````