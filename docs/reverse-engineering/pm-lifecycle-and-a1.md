# WLAN Power-Management Lifecycle, A1 and A1R

## Shelly TRV Gen1 Firmware 2.2.4

## Scope

This document describes a group of host-side WLAN power-management defects identified in Shelly TRV Gen1 firmware 2.2.4, the experimental A1 correction originally developed from that analysis, and the later A1R revision that corrected an A1-specific regression while retaining the qualified lifecycle fixes.

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

A1 was originally designed to correct these problems while preserving the surrounding WLAN behavior.

Later qualification identified an additional issue introduced by A1 itself: some verified temporary `request1` override paths could incorrectly become persistent selected policy.

That experimental regression was corrected by:

```text
A1R
```

A1R therefore represents:

```text
A1 lifecycle corrections
+
correction of the A1 temporary-override regression
```

A1/A1R do not attempt to:

- disable Beacon Recovery
- correct C1a/C1b/C2 Beacon Recovery defects
- enable EM3
- replace the host sleep architecture
- globally clear B2
- alter WLAN AP-selection policy
- replace the WF200 host driver
- modify WF200 radio firmware

The separately demonstrated B2 shared-reference-counter race is corrected independently by bounded B2 serialization.

These mechanisms must remain analytically distinct.

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

The second is shared host sleep-blocker accounting and sleep selection:

```text
B2
B3
PA8
EM1 / EM2 / EM3
```

A1 and A1R primarily address the first class.

The separately demonstrated B2 lost-update race belongs to the second class.

This distinction matters because both can influence host sleep behavior while violating different invariants.

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

Correct behavior requires the host to keep several concepts separate:

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

One central problem is treating a requested PM transition too much like an already-established state.

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

A1 introduced explicit separation of intent from accepted/committed state.

A1R retains that correction.

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

This can retain operation-specific software ownership after the transition failed.

Because that ownership participates in host sleep restriction, the defect can affect later low-power behavior.

---

# 6. Why G01 Is Not Fixed by Clearing B2

The retained ownership ultimately participates in shared blocker accounting.

That does not mean the correct fix is:

```c
B2 = 0;
```

B2 can contain contributions from other legitimate owners.

The correction must release only the ownership associated with the failed operation.

A1 repairs the operation lifecycle rather than overwriting the aggregate blocker state.

A1R retains that behavior.

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

The A1/A1R lifecycle keeps the transition pending until the relevant result is known.

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

and the information required to recover or retry must not already have been destroyed.

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

Another central defect class is timeout handling.

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

This distinction is fundamental to the A1/A1R lifecycle correction.

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

The correct model must account for:

```text
timeout
   !=
confirmed cancellation
```

The corrected lifecycle therefore treats an unresolved timed-out operation as a distinct state until ownership of the completion path is settled.

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

A1 introduced stronger operation identity/generation semantics.

A1R retains them.

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

The host can begin a new PM transition while a previous lower-level operation can still produce a completion.

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

A1 treats the old operation as unresolved until the relevant handoff and settlement conditions are satisfied.

A1R retains that behavior.

---

# 14. Settlement

A useful concept in the corrected lifecycle is **settlement**.

An operation is not settled merely because the caller stopped waiting.

Settlement requires enough evidence that the previous operation can no longer legitimately alter state owned by the next transition.

Depending on the path, this can require confirming properties such as:

```text
expected terminal state reached
no owed completion remains
no cancellation ambiguity remains
handoff identity is valid
```

Only then should ownership move cleanly to the next transition.

---

# 15. G18 — Independent Inhibit Ownership

Power-management restrictions can be requested for more than one reason.

A single Boolean such as:

```text
PM inhibited = true/false
```

is insufficient when independent causes overlap.

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

A1R retains this ownership model.

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

Desired policy can change while an older transition is still unresolved.

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

The old completion must not override newer intent simply because it completed successfully.

The corrected lifecycle therefore keeps desired policy and transition ownership/version separate.

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

When desired state changes:

```text
version N
   ->
version N+1
```

a completion belonging to version N must not silently establish policy for N+1.

This protects against stale asynchronous results.

---

# 18. Association and PM Handoff

Association is a sensitive point because WLAN identity and PM policy become connected.

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
validate no cancellation / owed-event ambiguity
   |
   v
validate handoff topology
   |
   v
publish PM policy
```

Publishing policy before these checks creates the possibility that PM state becomes associated with a stale or rejected connection handoff.

---

# 19. Association Normalization

During A1 qualification, association normalization became an important correctness gate.

The implementation validates the relevant association/JOIN ownership and handoff conditions before policy publication.

Rejected or stale handoffs return before modifying the new transition state.

The protected rejection boundary prevents changes to state such as:

```text
saved association identity/state
desired intent/version
PM generation
transition state
PM setup
related C-C baseline state
```

when the handoff is not accepted.

This was a necessary correction to an earlier A1 integration candidate.

A1R retains this corrected association behavior.

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

The corrected integration keeps the relevant validation/publication relationship inside a bounded protected section.

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

This prevents rejected handoffs from becoming externally visible as accepted PM policy.

---

# 21. A1 State Model

A1 adds explicit state required to distinguish concepts that stock control flow conflates.

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

The important property is separation of lifecycle states.

A1R preserves that architecture.

---

# 22. A1 Does Not Replace the Stock PM Architecture

A1 is intentionally bounded.

It does not replace Shelly's WLAN power-management strategy with a new one.

It preserves:

- existing PM policy architecture
- existing WLAN driver
- existing WF200 command model
- existing Beacon Recovery policy outside C-C
- existing scheduler
- existing B2/B3 sleep selector
- existing PA8 notification gate
- existing motor behavior
- existing OTA behavior

The patch changes lifecycle correctness around identified failure paths.

A1R retains that design philosophy.

---

# 23. Relationship to C-C

C-C and A1/A1R address different layers.

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

A1/A1R correct the WLAN PM transition lifecycle:

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

A later host-sleep audit identified a separate defect in the shared B2 reference counter.

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

This was originally treated as separate future correction work.

That correction has since been implemented and independently qualified as:

```text
bounded B2 serialization
```

The B2 correction preserves the reference-counter semantics rather than replacing B2 with a Boolean or forcing it to zero.

It is part of the current B2.1/B2.1_OBS integrated platform.

---

# 25. Relationship to B3 and EM3

A1/A1R do not remove the permanent B3 contribution.

Host-sleep analysis shows that B3 has a valid purpose.

Stock firmware uses a low-frequency clock configuration required by the RTC/tickless timebase, while the EM3 path disables the relevant low-frequency oscillator domain.

Therefore:

```text
EM2
```

remains the intended normal deepest idle state.

A1/A1R are not EM3 optimization patches.

---

# 26. Relationship to PA8

A1/A1R do not bypass the PA8 WLAN notification gate.

PA8 can independently prevent WFI while the WLAN notification path is asserted.

That behavior is separate from PM lifecycle ownership.

The correction therefore preserves it.

A HIGH PA8 state is not automatically a firmware defect.

---

# 27. Relationship to WF200 Firmware

A1/A1R are host-side corrections.

They do not modify the protected WF200 radio firmware.

This matters because WF200 can have power-management behavior and defects independent of the host lifecycle.

The project separately integrated:

```text
WF200 3.18.0
```

with Shelly's existing:

```text
FMAC 3.7.0
```

That radio update is not part of the A1 mechanism itself.

The integrated research platforms combine the host-side and radio-side changes intentionally.

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

A1R retains the same principle.

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

Battery-powered devices repeatedly traverse low-power transitions, so even relatively rare lifecycle failures can be important.

That does not establish their quantitative battery impact.

---

# 30. Static Qualification Strategy

A1 was not qualified merely by checking that the patched binary booted or that modified instructions decoded.

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

The objective was to find counterexamples to the intended invariants before hardware testing.

This methodology was later extended during A1R qualification.

---

# 31. Historical A1 Canonical Behavior Controls

The final historical A1 integration passed:

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

These controls exercised the final application bytes rather than only a source-level model.

They included corrected association/handoff publication behavior.

These results remain valid historical qualification evidence for A1.

They do not prove that A1 contained no later-discovered regression outside those test dimensions.

---

# 32. Historical Malformed and Corruption Controls

A1 qualification deliberately introduced invalid constructions and corrupted assumptions.

The process included:

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

The purpose was to verify that the build and lifecycle logic failed closed when required assumptions were violated.

---

# 33. Atomic-Guard Qualification

The corrected association/handoff guard was tested in both positive and rejected execution cases.

The historical A1 guard-specific execution set passed:

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

These tests specifically targeted publication-ordering problems identified during A1 integration.

---

# 34. PM Structural Qualification

The PM structural suite retained:

```text
26 checks
```

and the final historical A1 qualification added:

```text
6 critical-precondition mutations
```

These tests passed with the final A1 integration.

The purpose was to ensure that the corrected lifecycle was installed only when the expected stock structure was present.

---

# 35. Historical Hook and Relocation Qualification

The historical integrated A1 application contained:

```text
93 hooks
```

and:

```text
210 relocations
```

relevant to that complete experimental integration.

All were decoded and checked during qualification.

Whole-application reconstruction produced:

```text
zero unexplained changes
```

This result remains useful historical evidence for the A1 build.

Later A1R and B2.1 qualification used their own final-byte and composition checks.

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

The qualification explicitly tested both conditions.

This avoids unconditionally re-enabling interrupts when the caller entered with interrupts already disabled.

A1R preserves this invariant.

---

# 37. Rejected Handoffs Must Be Side-Effect Free

One of the strongest lifecycle invariants is that a rejected association/PM handoff must not partially publish new policy.

For a rejected stale or invalid handoff, the implementation returns before modifying the relevant new-policy state.

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

An earlier A1 integration candidate did not satisfy the publication-ordering requirement.

A control case showed that policy publication could occur before the cancellation/topology guard had fully validated the handoff.

That candidate was correctly classified as:

```text
NO-GO
```

The integration was changed so that validation and publication occur in the correct order.

This remains useful historical evidence that final-state testing alone is insufficient.

---

# 39. Historical A1 Static Verdict

After correcting the association normalization/publication issue, the historical A1 static qualification verdict was:

```text
A1 PRODUCTION INTEGRATION QUALIFIED FOR CONTROLLED DEVICE TEST
```

This wording meant only that the bounded static and executable gates required for controlled hardware testing passed.

It did not mean:

```text
vendor production firmware
```

and did not mean:

```text
battery-drain root cause proven
```

Later analysis subsequently identified the separate A1 temporary-override regression.

Therefore this historical qualification result must not be retroactively described as qualification of A1R.

---

# 40. Historical Integrated A1 Hardware Test

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

This established that the historical A1 integration did not immediately break the normal TRV operating path under the tested conditions.

It did not establish long-term battery improvement.

---

# 41. Historical A1 Integrated Artifact

The controlled-test artifact was:

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

These identities apply to that exact historical integrated build.

The build is superseded because it contains A1 rather than A1R.

Historical measurements collected from it remain valid and must not be relabeled as B2.1 or B2.1_OBS.

---

# 42. Discovery of the A1 Regression

After the historical A1 integration had been qualified and tested, further analysis identified a regression introduced by A1 itself.

Five verified native paths use `request1` as a **temporary override**:

```text
physical button
HTTP /psovrd
Cloud psovrd
SSI settings_sta
OTA launcher
```

The intended stock behavior is approximately:

```text
selected policy = 3

temporary request = 1

use state 1 temporarily

restore selected policy 3
```

The old A1 implementation could instead allow the temporary request to become the persistent selected policy.

For example:

```text
3 / 3
```

could transition through a temporary request and remain as:

```text
1 / 1
```

This was an experimental regression introduced by A1.

It is not evidence of an equivalent stock Shelly firmware defect.

It is also not evidence that the regression caused the historical battery-drain problem.

---

# 43. A1R

The corrected implementation is called:

```text
A1R
```

A1R preserves the qualified A1 lifecycle corrections while distinguishing the five verified temporary-override return paths from normal persistent `request1` behavior.

Conceptually:

```text
request1
   |
   +-- verified temporary caller
   |       |
   |       v
   |   temporary state 1
   |       |
   |       v
   |   restore selected policy
   |
   +-- normal persistent caller
           |
           v
       preserve original
       persistent semantics
```

A1R does not redefine all uses of `request1`.

It changes only the verified temporary-return cases required to remove the A1 regression.

---

# 44. A1R Qualification

A1R qualification included:

```text
151 / 151 Thumb behavior tests PASS
```

with additional qualification covering:

- retained state behavior
- transition generation handling
- C-C interaction
- B2 interaction
- MQTT interaction
- malformed inputs
- deterministic reconstruction
- integration noninterference

A1R also retained the original A1 PM lifecycle correction set.

The important relationship is:

```text
A1R
=
A1 lifecycle correction
+
A1 regression correction
```

not:

```text
A1R
=
a completely different PM architecture
```

---

# 45. A1R State Recovery Boundary

A1R prevents the A1 temporary-override error from being created by the corrected paths.

It does not attempt to repair an already-running historical:

```text
1 / 1
```

state in place.

A firmware flash/reboot initializes the relevant PM state normally.

This distinction matters when interpreting transitions between historical A1 builds and later A1R-based builds.

---

# 46. B2.1 Integration

A1R became part of the corrected integrated baseline:

```text
B2.1
```

B2.1 contains:

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

The artifact is:

```text
SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.gbl
```

Application:

```text
size:
1,066,776 bytes

SHA-256:
31ddd06a0229fee0b0b58dcbbd28ced1e4fbab0b6dc218c76c9d93673f4961e0

CRC:
24702EBF
```

GBL:

```text
size:
1,123,612 bytes

SHA-256:
5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9

END CRC:
F5429B7F

residue:
2144DF1C
```

B2.1 is the corrected observer-free baseline from which the current diagnostic platform was derived.

---

# 47. PM52 → cmd66 Observer and B2.1_OBS

The current diagnostic path no longer uses the earlier proposed clean-stock Host Observer.

Instead, the current observer is integrated on top of B2.1.

It records:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing periodic command-0x66 requests/results
- fresh estimator operands
- connection epochs
- a 12-record recent-event ring
- first-fault freeze state

The observer creates no additional WF200 request.

It introduces no:

```text
new timer
new task
new queue
automatic network traffic
flash write
policy change
```

Readout occurs only on explicit `/status` access.

The current hardware build is:

```text
B2.1_OBS
```

defined as:

```text
B2.1
+
PM52 -> cmd66 observer
```

The observer is intended to reveal the first abnormal PM52/cmd66 transition without deliberately changing the PM policy being tested.

---

# 48. Current Hardware Status

B2.1_OBS passed its qualification gate and is currently the long-term hardware test platform.

The active experimental population is:

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

The objective is no longer to continuously modify the PM lifecycle implementation.

The objective is to determine whether the corrected platform still develops a genuine battery-drain episode.

If it does:

```text
capture first fault
        |
        v
correlate PM52 / cmd66 state
        |
        v
resume deeper reverse engineering
```

If the corrected observer build remains stable over the required long-term period:

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
evaluate final firmware candidate
```

---

# 49. Current Conclusions

The host WLAN PM control flow in firmware 2.2.4 contains multiple real lifecycle defects.

The most important general conclusions are:

### Requested state is not committed state

A lower-level transition must succeed before the corresponding state is treated as established.

### Timeout is not cancellation

An asynchronous operation can remain live after the caller stops waiting.

### Late completions need identity

A completion must belong to the operation that currently owns the transition.

### Ownership must survive failure correctly

Failure paths require the same ownership discipline as success paths.

### Independent restrictions need independent ownership

One PM owner must not release another owner's restriction.

### Association handoff must be validated before publication

A stale or rejected JOIN transition must not publish new PM policy.

### A1 corrected real lifecycle defects

The historical A1 work demonstrated and corrected these PM-lifecycle problems.

### A1 also introduced an experimental regression

Some temporary `request1` override paths could become persistent.

That regression was introduced by the research patch, not demonstrated as a stock Shelly defect.

### A1R supersedes A1

A1R retains the qualified lifecycle correction and removes the verified A1 regression.

### B2 is a separate defect

The shared B2 reference-counter lost-update race is not the same PM-lifecycle defect.

Bounded B2 serialization has now been independently qualified.

### Current hardware uses A1R, not A1

The current B2.1_OBS test platform contains A1R together with C-C, B2 serialization, the minimal MQTT guard, WF200 3.18.0 and the PM52→cmd66 observer.

### Battery impact remains a runtime question

The corrected defects are real.

Their combined quantitative contribution to historical battery drain has not yet been established.

Therefore:

```text
firmware defect demonstrated
!=
battery-drain root cause proven
```

and:

```text
offline qualification passed
!=
long-term hardware battery lifetime proven
```

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

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

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
- composition qualification
- controlled hardware testing
- long-term runtime observation

Decompiler output is used as supporting information.

Important lifecycle conclusions are checked against native instructions, reachable control flow and executable test cases where practical.

No direct electrical current measurement is currently used to infer the battery impact of A1/A1R.

Battery behavior is evaluated through long-term runtime, voltage trends and firmware telemetry.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The analysis applies to the firmware versions and hardware investigated here.

Experimental firmware should only be used on devices where recovery or reflashing is possible.