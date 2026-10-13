# Power Management and Sleep

## Scope

This document describes the power-management and sleep behavior identified in
the analyzed Shelly TRV Gen1 firmware versions:

- 2.1.0
- 2.1.3
- 2.1.8
- 2.2.4

The main purpose is to distinguish between three different layers:

1. application-level WLAN power-management state
2. host-driver wake/sleep and MCU sleep-resource state
3. actual WF200 radio power-save behavior

These layers interact, but they are not equivalent.

This distinction is essential when investigating battery consumption.

For example:

```text
application state = 3
```

does not by itself prove:

```text
WF200 successfully entered the requested power-save mode
```

and it also does not necessarily prove:

```text
the host MCU is free to enter its expected deepest sleep state
```

The document also separates:

- normal power-saving behavior
- externally requested temporary overrides
- inherited conditional sleep-failure paths
- the 2.2.4 beacon-recovery mechanism
- periodic mDNS activity
- experimentally patched behavior

No firmware images, complete proprietary functions or complete disassemblies
are reproduced here.

---

# 1. Power-Management Layers

A simplified model is:

```text
Application PM state
        |
        v
Host / driver state
WUP + MCU sleep resources
        |
        v
WF200 internal power-save state
```

A request from one layer does not automatically prove the final state of the
next layer.

For example, the application may record:

```text
state 3
desired_beacon_skip = 20
```

while the exact internal WF200 behavior remains dependent on:

- successful host-to-WF200 communication
- acceptance of the requested power-save configuration
- internal WF200 behavior
- successful completion of the device-sleep sequence

The application does not continuously verify every aspect of the resulting
internal radio state.

---

# 2. Normal RSSI-Dependent Beacon Skip

The analyzed firmware versions use the same normal desired beacon-skip mapping:

| RSSI | Desired beacon skip |
|---|---:|
| >= -69 dBm | 20 |
| -79 to -70 dBm | 15 |
| < -79 dBm | 10 |

This value is used by the normal connected power-management path.

Conceptually:

```text
RSSI
 |
 v
desired_beacon_skip
 |
 v
state 3
 |
 v
WF200 power-save request
```

The value is a requested configuration.

It must not automatically be interpreted as proof of the exact internal WF200
beacon-listening behavior.

This distinction became particularly important after runtime testing showed
that firmware 2.2.4 can enter beacon recovery even with:

```text
good RSSI
desired_beacon_skip = 20
```

---

# 3. Application Power States

The firmware uses several application-level WLAN power-management states.

The currently understood states are:

| State | Purpose |
|---|---|
| 1 | Active / temporary active WLAN override |
| 2 | Special temporary power-management mode |
| 3 | Normal RSSI-dependent power-save state |
| 4 | Restore saved or deferred power state |
| 5 | Temporary Fast Power Save override with skip 10 |

Not every state exists or is used identically in every analyzed firmware
version.

The most important states for the current battery investigation are:

```text
state 1
state 3
state 5
```

State 4 is important for restoration behavior.

State 2 remains less well characterized and is not currently considered a
primary battery-drain candidate.

---

# 4. State 1 — Active / Temporary Active WLAN

State 1 represents a more active WLAN condition.

The analyzed path requests WLAN power mode:

```text
0
```

which corresponds to:

```text
Active / Always-On
```

in the relevant WF200/fullMAC interface.

Conceptually:

```text
request state 1
        |
        v
wake WLAN device
        |
        v
request Active / Always-On
        |
        v
WUP remains active
        |
        v
WLAN-owned MCU sleep restriction remains active
```

State 1 does not perform the normal final device-sleep transition used by the
normal state-3 path.

Therefore prolonged or repeatedly entered state 1 can be energy relevant.

This does not mean the host CPU necessarily executes continuously.

The important difference is that deeper host sleep states are restricted while
the corresponding WLAN-owned sleep resource remains held.

---

# 5. State 1 Before Firmware 2.2.4

State 1 did not originate with the 2.2.4 beacon-recovery mechanism.

Earlier firmware already contains externally triggered active-override paths.

Firmware 2.1.3 includes a named external override associated with:

```text
psovrd
```

The override temporarily requests the more active WLAN state and later restores
the saved or deferred application state.

No equivalent autonomous approximately once-per-minute state-1 recovery loop
was identified in the focused 2.1.0 -> 2.1.3 comparison.

This distinction is important:

```text
state 1 exists
```

does not mean:

```text
automatic recurring beacon recovery exists
```

The latter is a separate mechanism identified in firmware 2.2.4.

---

# 6. State 3 — Normal Connected Power Saving

State 3 is the normal RSSI-dependent connected power-save state.

Conceptually:

```text
RSSI
 |
 v
desired_beacon_skip
 |
 v
state 3
 |
 v
WF200 power-save request
 |
 v
final device-sleep operation
 |
 v
WUP/resource release
```

Typical requested values are:

```text
strong RSSI
skip 20

medium RSSI
skip 15

weak RSSI
skip 10
```

On successful completion of the normal path:

```text
power-save request
        |
        v
device sleep enabled
        |
        v
WUP cleared
        |
        v
WLAN-owned MCU sleep contribution released
        |
        v
deeper host sleep becomes possible
```

Other firmware components can independently hold sleep resources.

Therefore release of the WLAN-owned contribution does not guarantee that the
MCU immediately enters a particular energy mode.

---

# 7. State 4 — Restore Saved / Deferred State

State 4 is associated with restoration of a previously saved or deferred
application power-management state.

Conceptually:

```text
temporary override
        |
        v
saved previous state
        |
        v
state 4
        |
        v
restore previous / deferred state
```

Its importance becomes especially visible in the firmware 2.1.8
post-association sequence.

State 4 must not be interpreted as a separate fixed radio power mode.

Its role is primarily restoration of application power-management state.

---

# 8. State 5 — Temporary Fast Power Save Override

State 5 first appears in the analyzed firmware set in version 2.1.3.

Focused reverse engineering identified external interfaces associated with:

```text
HTTP:
psovrd2

Cloud:
psovrd2
```

State 5 requests:

```text
Fast Power Save
beacon skip = 10
```

and initializes a restoration countdown of:

```text
180
```

The countdown is serviced by firmware seconds maintenance.

Under normal scheduler operation this corresponds to approximately:

```text
3 minutes
```

A typical sequence is:

```text
normal state 3
        |
        | external psovrd2
        v
state 5
        |
        v
Fast Power Save
skip 10
        |
        | approximately 180 serviced seconds
        v
restore saved / deferred state
        |
        v
typically state 3
```

---

# 9. State 5 Does Not Intentionally Hold the Host Awake

State 5 should not be described as:

```text
MCU awake for three minutes
```

The normal state-5 path still performs the final device-sleep operation.

On successful completion:

```text
state 5 request
        |
        v
Fast Power Save
skip 10
        |
        v
device sleep enabled
        |
        v
WUP cleared
        |
        v
WLAN-owned MCU sleep contribution released
```

Therefore state 5 primarily changes the WLAN beacon-listening configuration.

For a device that would normally request:

```text
skip 20
```

state 5 instead requests:

```text
skip 10
```

This creates more nominal beacon-listening opportunities.

It does not by itself establish a particular electrical energy cost.

---

# 10. State 5 Can Be Externally Prolonged

The external `psovrd2` handlers initialize the restoration countdown before
dispatching the state-5 request.

This matters if state 5 is already active.

For example:

```text
state 5
countdown = 60

        |
        | new external psovrd2
        v

countdown = 180

        |
        v

duplicate state request may be rejected
but countdown has already been refreshed
```

Therefore repeated external requests can prolong state 5.

No autonomous periodic firmware mechanism has been identified that repeatedly
generates these `psovrd2` requests during ordinary idle operation.

State 5 is therefore currently classified as:

```text
externally triggered
temporary by design
externally prolongable
```

rather than:

```text
autonomous recurring idle loop
```

---

# 11. WF200 Power-Save Command `0x52`

The host uses WF200 command:

```text
0x52
```

for WLAN power-management configuration.

Across the analyzed firmware versions, the exact payload representation
changes.

The general role remains:

```text
host
 |
 v
command 0x52
 |
 v
requested WF200 power-save configuration
```

Older analyzed versions use the earlier payload representation for the normal
power-save mode and beacon-skip configuration.

Firmware 2.2.4 uses an expanded representation and additional surrounding
locking, retry and error-handling logic.

The existence of a host request does not itself prove that the protected WF200
subsystem remains indefinitely in exactly the requested internal state.

---

# 12. Requested State vs. Confirmed State

A central finding is that application bookkeeping and lower-level hardware
state are not identical.

Conceptually:

```text
application requests state 3
        |
        v
application bookkeeping updated
        |
        v
wake WF200
        |
        v
command 0x52
        |
        v
final device-sleep operation
```

Not every lower-level failure causes the application bookkeeping to be fully
rolled back.

The firmware can therefore conceptually reach a situation such as:

```text
application:
state 3

requested:
skip 20

actual lower-level state:
not completely verified by application bookkeeping alone
```

This is important when interpreting debug logs.

A log reporting:

```text
Enter powersave state 3 (skip 20)
```

establishes the application request.

It should not automatically be treated as a direct electrical measurement or
complete proof of the final internal WF200 state.

---

# 13. Command `0x52` Failure vs. Final-Sleep Failure

Two failure classes must be distinguished.

A failed power-save command does not automatically imply that WUP or the
WLAN-owned MCU sleep resource remains held.

For example:

```text
command 0x52 fails
        |
        v
final device-sleep operation succeeds
        |
        v
WUP cleared
        |
        v
WLAN-owned sleep contribution released
```

Therefore:

```text
command 0x52 failure
```

does not automatically mean:

```text
persistent MCU sleep blocker
```

The more important resource-retention case is failure of the later
device-sleep operation itself.

---

# 14. WUP and Host Sleep Resources

WUP is part of the host-to-WF200 wake/sleep coordination.

During an explicit WLAN wake sequence:

```text
acquire WLAN sleep resource
        |
        v
assert WUP
        |
        v
communicate with WF200
```

When the operation completes and device sleep is successfully enabled:

```text
device sleep enabled
        |
        v
WUP cleared
        |
        v
WLAN-owned MCU sleep contribution released
```

This lifecycle matters because the WLAN subsystem contributes to host MCU
sleep-resource accounting.

While that contribution remains held, deeper MCU energy modes can be
restricted.

---

# 15. MCU Energy-Mode Restriction

The WLAN subsystem can prevent the host MCU from entering deeper energy modes
while WLAN-related work requires the host to remain available.

Simplified:

```text
WLAN requires host availability
        |
        v
WLAN-owned sleep block held
        |
        v
deeper host sleep restricted
```

When normal cleanup succeeds:

```text
WF200 can sleep
        |
        v
WUP cleared
        |
        v
WLAN-owned contribution released
        |
        v
deeper MCU sleep becomes possible
```

For the known 2.2.4 beacon-recovery path, the relevant practical effect is that
EM2 and EM3 are restricted during the temporary recovery interval.

EM1 remains available.

Therefore:

```text
recovery
```

does not mean:

```text
CPU executes continuously for five seconds
```

It means that the deeper sleep states normally available to the host are
temporarily unavailable because of the WLAN-owned restriction.

---

# 16. Conditional Final-Sleep Failure Path

A separate conditional failure path exists in the lower-level sleep handling.

Simplified:

```text
WLAN wake
        |
        v
WUP / WLAN sleep resource acquired
        |
        v
application PM state recorded
        |
        v
power-save request
        |
        v
final device-sleep operation
        |
        +---- success
        |       |
        |       v
        |   WUP cleared
        |   resource released
        |
        +---- control-register I/O failure
                |
                v
           function returns error
                |
                v
        normal release can be skipped
```

This creates a possible mismatch:

```text
application state = 3
```

while:

```text
WUP / WLAN-owned sleep contribution
may remain active
```

The existence of this control-flow path is established by static analysis.

Its runtime frequency and duration have not been established.

---

# 17. The Final-Sleep Failure Path Is Inherited

Focused comparison showed that the core conditional final-sleep / WUP /
sleep-resource retention path already exists in:

```text
2.1.0
```

and remains present in:

```text
2.1.3
```

Therefore the existence of this path was not introduced by the
2.1.0 -> 2.1.3 transition.

This is important when evaluating historical battery drain.

The inherited path cannot by itself explain a version boundary unless some
other change causes it to be:

- reached more frequently
- retained for longer
- recovered differently
- combined with another mechanism

None of those possibilities has yet been demonstrated at runtime.

---

# 18. Why the Inherited Failure Path Still Matters

Although inherited, the failure path remains potentially energy relevant.

If it occurs:

```text
final sleep operation fails
        |
        v
WUP/resource remains held
        |
        v
deeper host sleep remains restricted
        |
        v
persistent elevated idle consumption becomes possible
```

A persistent retained-resource condition could potentially be more significant
than a short network packet burst.

However, static analysis does not establish:

- whether the failure occurs on real devices during ordinary operation
- how frequently it occurs
- how long the resource remains retained
- whether later WLAN activity repairs the condition
- the resulting electrical current

It must therefore remain classified as a plausible conditional mechanism, not
as an established battery-drain cause.

---

# 19. Transport Automatic Sleep Handling

The lower-level transport contains additional automatic sleep handling.

This behavior depends on internal driver state.

Explicit wake handling changes a driver sleep-enable condition.

If an operation fails before the expected state is restored, automatic cleanup
cannot simply be assumed to repair the condition immediately.

This contributes to the plausibility of the retained-resource path.

However, the actual runtime duration of such a condition remains unresolved.

---

# 20. Initialization EM2 Asymmetry

Another inherited resource-management asymmetry exists during WLAN driver
initialization.

Conceptually:

```text
block deeper MCU sleep
        |
        v
initialize WLAN transport
        |
        +---- success
        |       |
        |       v
        |   normal lifecycle
        |
        +---- failure
                |
                v
        local matching release
        not guaranteed
```

This behavior exists in both:

```text
2.1.0
2.1.3
```

It therefore does not by itself explain a 2.1.0 -> 2.1.3 battery-consumption
difference.

Later cleanup or a complete reset may restore a balanced state.

Whether an in-place driver reinitialization can leave an earlier contribution
retained remains unresolved.

---

# 21. Wake-ACK Wait Change

The WF200 wake-acknowledgement wait changes between firmware 2.1.0 and 2.1.3.

Simplified:

```text
2.1.0:
maximum requested wait = 3 ticks

2.1.3:
maximum requested wait = 5 ticks
+ timeout logging
```

The wait terminates early if the acknowledgement arrives before the maximum.

Therefore this does not imply that firmware 2.1.3 always spends two additional
ticks awake on every WLAN wake.

Possible effects include:

- longer wait during slow or failed wake
- greater tolerance for delayed acknowledgement
- fewer premature wake failures
- additional timeout logging

The net energy effect remains unresolved.

---

# 22. Firmware 2.1.0 -> 2.1.3

The focused comparison separates inherited behavior from newly introduced or
changed behavior.

## Inherited

The following are substantially inherited:

- normal state-3 ordering
- normal RSSI-dependent desired-skip mapping
- core command-`0x52` behavior
- WUP acquisition/release model
- conditional final-sleep retention path
- initialization sleep-resource asymmetry

## Added or changed

Firmware 2.1.3 adds or changes:

- state 5
- `psovrd2`
- named active-override handling
- wake-ACK maximum wait
- timeout logging
- some event-coalescing behavior
- periodic connected-state mDNS restart

The periodic mDNS mechanism is particularly important because it creates
recurring network activity during otherwise connected operation.

Runtime testing subsequently confirmed that this mechanism produces periodic
mDNS traffic.

It is documented separately in:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

---

# 23. Firmware 2.1.8 Post-Association Change

Firmware 2.1.8 changes the post-association power-management sequence.

Earlier behavior is approximately:

```text
association event
        |
        v
request state 3
```

Firmware 2.1.8 adds:

```text
association event
        |
        v
restore state 4
        |
        v
scheduler delay
        |
        v
request state 3
```

The delay is represented as:

```text
100 scheduler ticks
```

It should not be described as:

```text
100 milliseconds
```

unless the scheduler tick duration is independently established.

The additional sequence performs more host-side operations.

However, its energy effect depends on the state being restored.

For example, restoration can potentially terminate an active temporary hold
rather than extend it.

Therefore the net energy effect remains unresolved.

No unconditional new steady-state awake loop was identified from this
sequence.

---

# 24. Protected WF200 Firmware Boundary

The protected WF200 firmware image provides an important version boundary.

Within the analyzed firmware set:

```text
2.1.0
2.1.3
```

use the same protected WF200 image.

The image changes in:

```text
2.1.8
```

and changes again in:

```text
2.2.4
```

This matters for version comparison.

For:

```text
2.1.0 -> 2.1.3
```

the protected WLAN firmware is controlled relatively well, allowing visible
host-side changes to be compared while the protected WF200 image remains the
same.

For:

```text
2.1.3 -> 2.1.8
```

both host-side behavior and the protected WF200 image change.

A difference in actual WLAN behavior after 2.1.8 therefore cannot
automatically be attributed to the visible host application.

The same caution applies when interpreting the additional protected-image
change in 2.2.4.

---

# 25. WF200 Power-Save Verification Gap

The host requests a WLAN power-save configuration through:

```text
command 0x52
```

but does not continuously verify every aspect of the resulting internal WF200
behavior.

Therefore:

```text
desired_beacon_skip = 20
```

means:

```text
the host requested the normal skip-20 configuration
```

It does not independently prove:

```text
every internal WF200 beacon-listening event exactly followed the host's
assumed skip-20 model
```

The protected subsystem may contain:

- internal retries
- fallback behavior
- timing compensation
- DTIM handling
- rejected-request behavior
- other radio-side state transitions

These details cannot be completely reconstructed from the host application
alone.

This verification gap is particularly relevant to the 2.2.4
`real_beacon_skip` investigation.

---

# 26. Firmware 2.2.4 Changes

Firmware 2.2.4 adds substantial power-management-related logic.

Identified changes include:

- expanded command-`0x52` handling
- additional retry behavior
- additional locking/wrappers
- WF200 statistics command `0x66`
- beacon statistics processing
- `real_beacon_skip`
- automatic beacon-recovery logic
- temporary state-1 recovery

The known recovery chain is:

```text
WF200 statistics
        |
        v
beacon_rx_count
        |
        v
real_beacon_skip
        |
        v
qualifying recovery predicate
        |
        v
state 1
        |
        v
Active / Always-On
        |
        v
deeper host sleep restricted
        |
        | approximately 5 seconds
        v
restore saved / deferred state
```

On affected stock 2.2.4 devices, this sequence has been observed to recur
approximately once per minute.

---

# 27. 2.2.4 Beacon-Recovery Energy Path

During the normal recovery path:

1. the WLAN device is explicitly woken
2. Active / Always-On WLAN mode is requested
3. the WLAN-owned host sleep restriction remains active
4. EM2 and EM3 are unavailable to the host while the restriction is held
5. the temporary recovery countdown runs for approximately five seconds
6. the saved or deferred application power state is restored
7. normal beacon power saving can resume

Conceptually:

```text
normal state 3
        |
        v
qualifying real_beacon_skip
        |
        v
state 1
        |
        v
Active / Always-On
        |
        v
EM2 / EM3 restricted
        |
        | ~5 seconds
        v
restore state
        |
        v
normally state 3
```

This is a technically credible source of additional energy consumption.

The electrical magnitude has not been measured.

---

# 28. Recovery Does Not Require Poor RSSI

Runtime testing provided an important constraint.

Recurring recovery was observed while reported RSSI was approximately:

```text
-58 to -59 dBm
```

and the normal RSSI policy selected:

```text
desired_beacon_skip = 20
```

Therefore poor RSSI is not required for the 2.2.4 recovery mechanism to
trigger.

This does not establish that radio conditions have no effect.

It establishes only that weak signal strength is not a necessary condition for
the observed recurring recovery.

## Confidence

**RUNTIME CONFIRMED**

---

# 29. Periodic mDNS Activity

A separate recurring mechanism exists in the connected-state maintenance logic.

Firmware 2.1.3 introduced a periodic call equivalent to:

```text
mdns_resp_restart
```

Runtime packet capture confirmed recurring mDNS activity.

Observed behavior included approximately:

```text
2.1.3:
~60-second recurring mDNS sequence

stock 2.2.4:
~180-second recurring mDNS sequence
```

The 2.2.4 interval results from the connected minute-maintenance logic invoking
the periodic restart on every third relevant cycle.

This is a separate mechanism from beacon recovery.

The two mechanisms can coexist:

```text
periodic mDNS activity
```

and:

```text
beacon recovery
```

but one should not automatically be assumed to cause the other.

---

# 30. mDNS Isolation Experiment — Patch B

Patch B was created to suppress only the periodic connected-maintenance mDNS
restart.

It does not modify:

- state 1
- state 3
- command `0x52`
- command `0x66`
- `beacon_rx_count`
- `real_beacon_skip`
- the beacon-recovery predicate
- WUP handling
- host sleep-resource handling
- the protected WF200 image

Runtime packet capture on the Patch-B device showed:

```text
0 targeted recurring mDNS packets
```

during the monitored test window of at least approximately ten minutes.

This confirms suppression of the targeted periodic mDNS path during that
finite observation window.

It does not mean that all mDNS functionality was globally disabled.

Other event-driven mDNS callers remain intact.

---

# 31. Beacon Recovery Continues with Patch B

The Patch-B device continued to produce:

```text
Beacon skip error! Attempt recovery
```

approximately once per minute.

The normal sequence remained:

```text
state 1
        |
        | ~5 seconds
        v
state 3
```

This continued even with good RSSI and:

```text
desired_beacon_skip = 20
```

Therefore:

> The periodic mDNS restart is not required for the recurring beacon-recovery
> behavior under the tested conditions.

This experimentally separates the two mechanisms.

It does not prove that mDNS activity can never affect WLAN timing under any
condition.

---

# 32. Beacon-Recovery Isolation — Patch A

Patch A bypasses the identified 2.2.4 beacon-recovery action.

It does not modify:

- normal RSSI-dependent desired skip
- normal state 3
- command `0x52`
- WF200 statistics command `0x66`
- `beacon_rx_count`
- the `real_beacon_skip` calculation
- WUP handling
- general MCU sleep-resource handling
- periodic mDNS behavior
- the protected WF200 image

Conceptually:

```text
WF200 statistics
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        X
recovery action bypassed
```

Runtime testing showed that the targeted recurring recovery sequence was
suppressed while normal beacon-skip selection continued to operate.

Patch A therefore isolates the host-side recovery consequence.

It does not correct or explain the underlying WF200 beacon statistics.

---

# 33. Combined Patch A+B

Patch A and Patch B were subsequently combined.

The combined experimental configuration suppresses:

```text
Patch A:
targeted beacon-recovery action

Patch B:
targeted periodic connected-state mDNS restart
```

while leaving the normal WLAN power-management architecture intact.

In particular, the combined patch does not intentionally modify:

- RSSI thresholds
- normal state 3
- desired beacon skip
- command `0x52`
- command `0x66`
- WUP lifecycle
- general host sleep-resource handling
- the protected WF200 image

This is important because it provides a controlled long-term test
configuration without attempting to redesign the entire power-management
system.

---

# 34. Combined Patch Runtime Validation

A physical TRV running the combined Patch A+B was monitored for multiple hours.

During that monitored interval:

```text
Beacon skip error! Attempt recovery
```

was not observed.

The recurring recovery-associated:

```text
Enter powersave state 1
```

was also absent.

Normal connected operation remained functional.

Normal RSSI-dependent beacon-skip behavior remained visible.

Cloud connectivity remained operational during the tested period.

Separate packet capture showed no targeted periodic mDNS sequence during the
monitored mDNS test window.

The correct interpretation is therefore:

> Both targeted recurring mechanisms were suppressed during their respective
> monitored test windows while normal connected operation continued.

The test windows are finite.

This does not establish:

- indefinite stability
- long-term battery improvement
- elimination of every possible state-1 transition
- elimination of all mDNS traffic
- correction of the underlying WF200 beacon statistics
- correction of the inherited conditional final-sleep path

---

# 35. Why the Combined Patch Does Not Address the WUP Failure Path

Patch A+B intentionally leaves the inherited lower-level sleep/resource
handling unchanged.

Therefore the combined patch does not modify the conditional path:

```text
device-sleep failure
        |
        v
possible retained WUP / sleep resource
```

This is deliberate.

The path already exists in firmware 2.1.0 and its runtime relevance has not
been established.

Changing it without understanding the exact hardware and driver state after a
failure could create new instability.

The current patching strategy therefore separates:

```text
confirmed recurring mechanisms
```

from:

```text
unconfirmed conditional failure mechanisms
```

---

# 36. Why a Sleep-Cleanup Patch Requires Care

A retained-resource failure might superficially suggest a simple correction:

```text
sleep operation failed
        |
        v
force WUP low
force sleep-resource release
```

Such a modification would be unsafe without further analysis.

If the WF200 or host transport still legitimately requires the MCU to remain
available, forced release could cause:

- lost WF200 interrupts
- transport desynchronization
- failed WLAN communication
- driver-state corruption
- unstable firmware behavior

A safe correction would require establishing the complete driver and hardware
state after the failure.

An existing firmware cleanup or retry path would be preferable to inventing a
new forced-release sequence.

No such Patch C is currently part of the tested firmware.

---

# 37. Current Experimental Patch Architecture

The experimentally tested patch architecture currently consists of:

```text
Patch A
Beacon-recovery bypass
```

and:

```text
Patch B
Periodic mDNS restart suppression
```

These have been tested both independently and together.

The resulting configurations include:

```text
stock 2.2.4

Patch A only

Patch B only

Patch A+B
```

This modular approach is important because it allows the effects of the two
identified recurring mechanisms to be separated experimentally.

A hypothetical future sleep-cleanup modification should remain a separate
experiment unless its runtime relevance is first established.

---

# 38. Battery-Drain Interpretation

The current power-management evidence does not support a single-cause model.

A more appropriate working model is:

```text
baseline device consumption
        +
normal motor activity
        +
normal cloud / network activity
        +
version-dependent recurring activity
        +
possible conditional failure states
```

Potential version-dependent contributions include:

```text
2.1.3+
periodic mDNS activity
```

and:

```text
2.2.4
beacon-recovery activity
```

A separate inherited conditional mechanism is:

```text
final device-sleep failure
        |
        v
possible retained WUP / host sleep restriction
```

The historical evidence is important here.

Battery drain was also observed historically on firmware 2.1.8.

Therefore the 2.2.4 beacon-recovery mechanism cannot currently be described as
the original or sole cause of the historical battery-drain problem.

Likewise, firmware 2.1.3 has not been established as universally free of the
problem.

The supported interpretation is:

> Firmware 2.2.4 contains an additional recurring recovery mechanism that
> plausibly adds energy consumption on affected devices.

Its quantitative contribution remains to be determined by long-term testing.

---

# 39. Evidence Classification

| Finding | Status |
|---|---|
| Normal RSSI-dependent desired skip policy is equivalent across the analyzed versions | **PROVEN** |
| State 3 is the normal RSSI-dependent power-save state | **PROVEN** |
| State 1 requests a more active WLAN condition | **PROVEN** |
| State 1 can restrict deeper host sleep | **PROVEN** |
| State 5 appears in firmware 2.1.3 | **PROVEN** |
| State 5 is associated with external `psovrd2` | **PROVEN** |
| State 5 requests Fast Power Save with skip 10 | **PROVEN** |
| State 5 uses a restoration countdown of 180 serviced seconds | **PROVEN** |
| Successful state-5 handling can release WUP and the WLAN-owned sleep contribution | **PROVEN** |
| Repeated external `psovrd2` requests can refresh the state-5 countdown | **PROVEN** |
| The core conditional final-sleep/WUP retention path already exists in 2.1.0 | **PROVEN** |
| Command-`0x52` failure alone does not prove retained WUP | **PROVEN** |
| 2.1.8 changes the post-association PM sequence | **PROVEN** |
| 2.2.4 introduces the known counter-derived beacon-recovery mechanism | **PROVEN** |
| Beacon recovery requests Active / Always-On | **PROVEN** |
| Beacon recovery restricts host EM2/EM3 during the recovery window | **PROVEN** |
| Normal recovery lasts approximately five seconds | **PROVEN** |
| Recovery can recur approximately once per minute on affected stock 2.2.4 devices | **RUNTIME CONFIRMED** |
| Recovery can occur with good RSSI and desired skip 20 | **RUNTIME CONFIRMED** |
| Periodic mDNS activity occurs on stock 2.1.3 and 2.2.4 | **RUNTIME CONFIRMED** |
| Patch B suppresses the targeted periodic mDNS path during the monitored test window | **RUNTIME CONFIRMED** |
| Beacon recovery continues with Patch B | **RUNTIME CONFIRMED** |
| Periodic mDNS is required for beacon recovery | **NOT SUPPORTED** |
| Patch A suppresses the targeted recurring beacon-recovery action | **RUNTIME CONFIRMED** |
| Combined Patch A+B suppresses both targeted recurring mechanisms during monitored tests | **RUNTIME CONFIRMED** |
| Combined Patch A+B fixes the historical battery drain | **NOT PROVEN** |
| The inherited WUP/resource-retention path occurs during ordinary runtime | **UNRESOLVED** |
| The inherited WUP/resource-retention path caused the historical battery drain | **NOT PROVEN** |
| State 5 caused the historical battery drain | **NOT PROVEN** |
| Firmware 2.1.3 was the first battery-drain firmware | **NOT PROVEN** |
| 2.2.4 beacon recovery is the sole battery-drain root cause | **NOT PROVEN** |
| Quantitative electrical cost of beacon recovery | **UNRESOLVED** |
| Quantitative electrical cost of periodic mDNS activity | **UNRESOLVED** |
| Long-term battery improvement from Patch A+B | **UNDER TEST** |

---

# 40. Current Research Direction

The power-management investigation now separates three tracks.

## Track A — Long-Term Battery Comparison

The primary practical test is comparison of:

```text
stock 2.2.4
```

against:

```text
patched 2.2.4
```

with the tested patch variants kept clearly identified.

Important observations include:

- battery voltage
- reported battery percentage
- runtime
- beacon statistics
- recovery counters
- firmware variant
- motor activity where available

Cross-device battery comparisons must be interpreted carefully because
different devices and batteries introduce confounding factors.

Longer observation windows are more useful than short percentage changes.

---

## Track B — WF200 Beacon Statistics

The principal unresolved technical question behind the 2.2.4 recovery is:

> Why do the WF200 beacon statistics produce counter deltas that firmware
> 2.2.4 interprets as an invalid `real_beacon_skip`?

This includes determining:

- exact `beacon_rx_count` semantics
- exact `beacon_rx_missed_count` semantics
- intentional beacon-skip behavior
- DTIM interaction
- whether the host-side `600 / delta` interpretation is appropriate

This work is documented in:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

and:

[`real-beacon-skip.md`](real-beacon-skip.md)

---

## Track C — Conditional Sleep Failures

The inherited WUP / host-sleep-resource retention path remains technically
interesting.

However, its runtime relevance has not been demonstrated.

It should therefore remain separate from the experimentally confirmed
recurring mechanisms.

Future work should first determine whether the condition actually occurs on
real devices before attempting a firmware modification.

---

# 41. Current Working Model

The current power-management model is:

```text
                    APPLICATION
                         |
                         v
                 requested PM state
                         |
             +-----------+-----------+
             |                       |
             v                       v
       normal state 3          temporary states
                               1 / 5 / restore
             |                       |
             +-----------+-----------+
                         |
                         v
                  host WF200 driver
                         |
                         v
                   command 0x52
                         |
                         v
               protected WF200 state
                         |
                         v
                device-sleep handling
                         |
             +-----------+-----------+
             |                       |
          success                  failure
             |                       |
             v                       v
       WUP released          possible retained
       sleep resource        WUP / sleep resource
       released
             |
             v
     deeper MCU sleep possible
```

Firmware 2.2.4 adds another recurring input:

```text
WF200 command 0x66
        |
        v
beacon statistics
        |
        v
real_beacon_skip
        |
        v
recovery predicate
        |
        v
temporary state 1
```

Firmware 2.1.3 and later also contain a separate recurring connected-state
mDNS mechanism.

These mechanisms must not be conflated.

---

# 42. Current Conclusion

The Shelly TRV power-management system consists of multiple interacting layers.

The application requests power states.

The host driver coordinates WUP and MCU sleep resources.

The protected WF200 subsystem implements the actual WLAN power-save behavior.

The most important findings are:

```text
normal state 3
```

is not equivalent to a direct measurement of the final electrical state;

```text
state 5
```

is a temporary externally triggered Fast Power Save override, not a
three-minute continuous-awake state;

```text
the conditional WUP/resource-retention path
```

already exists in firmware 2.1.0 and has not been demonstrated as a runtime
battery-drain mechanism;

```text
firmware 2.2.4 beacon recovery
```

is an additional automatic mechanism that temporarily requests Active /
Always-On WLAN operation and restricts deeper host sleep for approximately five
seconds;

and:

```text
periodic mDNS
```

is a separate recurring mechanism that can be experimentally suppressed
without eliminating beacon recovery.

Patch A and Patch B therefore isolate two separate recurring behaviors:

```text
Patch A
        ->
beacon recovery suppressed
```

```text
Patch B
        ->
periodic mDNS restart suppressed
```

and the combined Patch A+B has operated normally during the monitored test
windows with both targeted recurring mechanisms absent.

The remaining questions are now primarily quantitative and lower-level:

1. how much battery energy the recurring mechanisms actually consume
2. why the WF200 beacon statistics cause the 2.2.4 recovery predicate to
   qualify
3. whether the inherited conditional sleep-resource failure occurs during real
   operation
4. whether suppressing the confirmed recurring mechanisms materially improves
   long-term battery endurance

No current evidence justifies describing any one of these mechanisms as the
sole historical battery-drain root cause.

---

# Related Documents

- [`Firmware Comparison`](firmware-comparison.md)
- [`Periodic mDNS Restart`](mdns-periodic-restart.md)
- [`Beacon RX Counter`](beacon-rx-counter.md)
- [`Real Beacon Skip`](real-beacon-skip.md)
- [`Recovery Mechanism`](recovery-mechanism.md)
- [`AP Selection and Roaming`](ap-selection-and-roaming.md)
- [`Experimental Beacon-Recovery Patch`](../patch/README.md)
- [`Battery Testing`](../testing/battery-testing.md)

---

# Research Methodology

This investigation is based on static reverse engineering of locally obtained
Shelly TRV Gen1 firmware images together with runtime observations from
personally owned devices.

The analysis includes:

- comparison of firmware versions
- host-side power-state control flow
- WF200 command handling
- WUP lifecycle
- MCU sleep-resource handling
- beacon-statistics processing
- passive network capture
- stock and experimentally patched runtime testing

Publicly available Silicon Labs WF200/fullMAC information was used where
necessary to interpret host-visible WLAN interface behavior.

The protected WF200 implementation is not reproduced.

No firmware images, complete proprietary functions or complete disassemblies
are published in this document.

The classifications:

```text
PROVEN
RUNTIME CONFIRMED
STRONG INFERENCE
PLAUSIBLE
NOT SUPPORTED
NOT PROVEN
UNRESOLVED
UNDER TEST
```

are deliberately used to distinguish static evidence, runtime evidence and
interpretation.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or
Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings documented here describe observed and reverse-engineered behavior
of the tested firmware versions.

No conclusions about the intentions of the original developers are inferred
from these technical findings.