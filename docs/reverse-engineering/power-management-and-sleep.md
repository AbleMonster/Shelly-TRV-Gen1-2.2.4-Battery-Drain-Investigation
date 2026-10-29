# Power Management and Sleep Analysis

## Shelly TRV Gen1 Firmware 2.2.4

## Overview

The Shelly TRV Gen1 uses several interacting power-management layers.

At minimum, the observed firmware behavior involves:

1. application-level Shelly power-management states
2. host-MCU sleep eligibility
3. shared host sleep-blocker accounting
4. WF200 WLAN power-save configuration
5. the WF200 wake/sleep handshake
6. transport and command ownership between the host and WF200
7. radio-side WF200 firmware behavior

These layers are related, but they are not equivalent.

A request such as:

```text id="mgvrrs"
Power save state 3
Beacon skip 20
```

does not prove that the WF200 is physically sleeping for the expected amount of time.

Likewise:

```text id="g67ce3"
WUP LOW
```

means that the host no longer requires the WF200 to remain awake.

It is not a direct physical-sleep indication.

Similarly:

```text id="7wjkpt"
B2 = 0
```

means that no currently represented software B2 owner requires the host to remain limited to EM1.

It does not prove:

```text id="0n5a8l"
EFM32GG11 is physically in EM2
```

because PA8 and other admission conditions still matter.

These distinctions are central to the battery-drain investigation.

---

# 1. Current Research Position

Static and executable analysis identified several real host-side power-management correctness defects.

These include:

```text id="g4zxo7"
G01  incomplete Final-Sleep failure cleanup
G02  Wake state committed before lower-level completion
G03  timeout treated too much like cancellation
G05  late asynchronous completion ambiguity
G06  requested PM policy vs. committed PM policy
G18  independent sleep-inhibit ownership
G19  stale PM completion / generation race
```

These lifecycle defects were originally corrected by the experimental:

```text id="3yd6fu"
A1
```

implementation.

Subsequent qualification identified a regression introduced by A1 itself in verified temporary `request1` override paths.

The corrected lifecycle implementation is:

```text id="3hf5da"
A1R
```

A1R retains the qualified A1 lifecycle fixes while correcting that experimental regression.

A separate host-sleep audit demonstrated a shared B2 reference-counter race.

That defect is corrected independently by:

```text id="dmpl7b"
bounded B2 serialization
```

Beacon Recovery contains a separate set of validity defects:

```text id="oojq45"
C1a
C1b
C2
```

corrected by:

```text id="pkw2mt"
C-C
```

The current long-term hardware platform additionally uses:

```text id="g66rgt"
WF200 3.18.0
```

which contains an official Silicon Labs power-save fix relevant to this investigation.

The current integrated baseline is therefore conceptually:

```text id="lmv1hc"
Shelly application PM policy
        |
        v
A1R PM lifecycle correction
        |
        v
B2 bounded serialization
        |
        v
C-C Beacon Recovery validity correction
        |
        v
Shelly FMAC 3.7.0
        |
        v
WF200 3.18.0
```

The current diagnostic hardware build adds the PM52→cmd66 observer:

```text id="17mr2k"
B2.1_OBS
```

The current experiment is not attempting to add more PM fixes.

It is attempting to determine whether genuine long-term battery drain still appears after the demonstrated and qualified corrections have been combined.

---

# 2. Power Management Is Not One State Machine

It is useful to avoid treating "power save" as one single state.

The firmware contains several related state domains.

A simplified model is:

```text id="gdatjk"
Application PM policy
        |
        v
Shelly PM state
        |
        +---------------------------+
        |                           |
        v                           v
WF200 PM request            host sleep eligibility
        |                           |
        v                           v
FMAC / WF200                B2 / B3 / PA8
        |                           |
        v                           v
WUP / transport             EM1 / EM2 / EM3
        |
        v
physical radio behavior
```

The host can know what it requested.

It can know whether a lower-level command returned successfully.

It can know whether it currently permits the WF200 to sleep.

It can know which host energy mode is currently permitted by software blockers.

Those facts do not directly reveal physical RF or MCU sleep residency.

---

# 3. Application Power-Management States

Shelly firmware uses application-level PM states that coordinate the WLAN subsystem and host sleep policy.

States relevant to this investigation include:

```text id="abpuv2"
State 1
State 3
State 4
State 5
```

These state numbers are Shelly application concepts.

They must not be interpreted as Silicon Labs WF200 power-save mode numbers.

---

# 4. State 1 — Active / Recovery State

State 1 is used when firmware wants the WLAN subsystem available without the normal beacon-based power-saving configuration.

Beacon Recovery temporarily enters this state.

A simplified sequence is:

```text id="l6elvn"
Beacon Recovery
        |
        v
Shelly PM state 1
        |
        v
WF200 Active / Always-On request
        |
        v
deeper power-saving behavior restricted
```

During normal Recovery behavior, firmware later attempts to restore the previous connected power-saving policy.

Historically, the Recovery interval is approximately five serviced seconds.

State 1 is therefore relevant to battery behavior because repeated Recovery intentionally moves the system away from its normal lower-power configuration.

This does not establish its exact energy cost.

---

# 5. State 3 — Connected Beacon Power Save

State 3 is the normal connected beacon-based power-saving state observed during TRV operation.

Typical logs include:

```text id="v8v6fz"
Enter powersave state 3 (skip 20)
```

or values such as:

```text id="xkrx4y"
Enter powersave state 3 (skip 15)
```

The selected listen interval is dynamic.

It may change according to Shelly's signal-strength or connectivity policy.

Observed examples include:

```text id="sg240g"
desired_beacon_skip = 20
```

and later:

```text id="4hwco4"
desired_beacon_skip = 15
```

without loss of WLAN connectivity.

For firmware 2.2.4, the normal connected request is approximately:

```text id="ykmjke"
mode            = Beacon Power Save
strategy        = Fast Power Save
listen_interval = N
idle_timeout    = 0
```

where `N` is typically the selected beacon-skip value.

---

# 6. State 4 and State 5

States 4 and 5 participate in the wider Shelly PM state machine.

They must not be interpreted as simple direct descriptions of physical WF200 sleep.

Application-state transitions can initiate multiple lower-layer operations.

For this investigation, actual PM commands, lifecycle ownership and completion behavior are more reliable than inferring physical state solely from the application state number.

---

# 7. WF200 Power-Management Command `0x52`

The Shelly host configures WF200 WLAN power management through command:

```text id="pny9oj"
0x52
```

The relevant fields include:

```text id="qfkcvg"
mode
strategy
listen_interval
idle_timeout
```

Known mode values include:

```text id="rf42xa"
0 = Active
1 = Beacon Power Save
2 = DTIM Power Save
```

Known strategy values include:

```text id="31c8ag"
0 = U-APSD
1 = Fast Power Save
```

The listen interval is represented as a little-endian 16-bit value.

A common Shelly TRV 2.2.4 connected configuration is approximately:

```text id="p6qjk1"
mode            = 1
strategy        = 1
listen_interval = 20
idle_timeout    = 0
```

or conceptually:

```text id="19o7hf"
Beacon Power Save
Fast Power Save
listen interval 20
default idle timeout
```

In the relevant Silicon Labs interface, an idle-timeout value of zero selects default behavior.

---

# 8. Requested PM Policy vs. Effective Physical State

One of the most important distinctions is:

```text id="g85umx"
PM request completed successfully
```

does not mean:

```text id="9am7j4"
radio is physically sleeping now
```

A successful PM52 transaction tells the host that the command was processed with the returned status.

It is not a continuous physical sleep monitor.

Conceptually:

```text id="sz14kj"
Host
 |
 | PM52:
 | Beacon PS
 | Fast PS
 | listen interval N
 v
WF200
 |
 | confirmation
 v
Host
```

The confirmation establishes command completion.

It does not establish:

```text id="opdl3g"
WF200 slept for exactly N beacon periods
```

or:

```text id="yyfmg1"
WF200 is currently in its lowest physical power state
```

---

# 9. Wake / Sleep Handshake

The WF200 host interface uses a wake/sleep handshake involving WUP and corresponding host-side ownership.

Conceptually:

```text id="abuzht"
host needs WF200
        |
        v
assert wake request
        |
        v
wait for device availability
        |
        v
perform transport / register work
        |
        v
release final wake requirement
        |
        v
permit WF200 sleep
```

This lifecycle interacts with:

- command ownership
- pending confirmations
- PM transitions
- association state
- transport activity
- host sleep eligibility

Several A1/A1R defect classes occur in this lifecycle.

---

# 10. WUP LOW Does Not Prove Physical Sleep

The distinction is:

```text id="6r1nwf"
WUP LOW
```

does not mean:

```text id="33ei20"
WF200 definitely asleep
```

It means the host is no longer asserting the wake requirement.

The supported interpretation is:

```text id="9y622g"
WUP LOW
    |
    v
host permits WF200 sleep
```

The WF200 may still have internal reasons to remain active.

This distinction is especially relevant when evaluating radio-side PM defects.

---

# 11. Final Sleep

The host contains a Final-Sleep path that releases the final host-side requirement keeping WF200 awake.

This is not simply a software flag update.

It participates in hardware and transport ownership.

A simplified intended lifecycle is:

```text id="xu0r3l"
host owns wake requirement
        |
        v
complete required WLAN work
        |
        v
Final-Sleep
        |
        v
release hardware / transport ownership
        |
        v
host no longer requires WF200 awake
```

Static analysis found stock 2.2.4 failure paths in which this lifecycle is not completed symmetrically.

That became one of the principal lifecycle defects corrected by A1 and retained by A1R.

---

# 12. G01 — Final-Sleep Failure Cleanup

Some stock Final-Sleep paths perform lower-level register or transport operations while owning state required for the transaction.

If one of these operations fails, the error path can return before the full expected cleanup/release sequence completes.

The problem is not merely:

```text id="klqb34"
register operation failed
```

The relevant problem is:

```text id="q87fg7"
operation failed
        |
        v
function returned
        |
        v
ownership / release state may no longer
match the completed lifecycle
```

A1 corrected this lifecycle asymmetry.

A1R retains that correction.

---

# 13. G02 — Wake State Committed Too Early

The inverse problem exists on Wake.

Software-visible state may be updated before the lower-level wake sequence has successfully completed.

Problematic conceptual ordering:

```text id="t0dy0g"
software says "awake"
        |
        v
perform hardware wake work
        |
        X
failure
```

A later request can then observe an "already awake" state even though the previous lower-level transition was incomplete.

The safer lifecycle is:

```text id="qhmgzu"
wake requested
        |
        v
perform required lower-layer work
        |
        v
lower-layer success
        |
        v
commit software state
```

A1/A1R enforce this distinction.

---

# 14. G03 and G05 — Timeout and Completion Ownership

WF200 communication is asynchronous.

A host timeout does not necessarily mean the WF200 never received or executed the command.

For example:

```text id="3w1ekc"
Host sends command
        |
        v
WF200 receives command
        |
        v
WF200 processes command
        |
        v
confirmation returns
```

If the host times out before seeing the confirmation:

```text id="bbikn3"
Host sends command
        |
        v
WF200 may consume command
        |
        v
Host timeout
        |
        v
confirmation may still arrive later
```

Therefore:

```text id="folmu0"
timeout != cancellation
```

After an ambiguous timeout, the host may no longer know with certainty whether:

- WF200 consumed the request
- a confirmation remains pending
- a transaction identifier remains associated with old work
- lower-layer state changed
- ownership can safely be transferred

A1/A1R treat this ambiguity conservatively rather than pretending the operation was automatically cancelled.

---

# 15. G06 — Requested Policy vs. Confirmed Policy

Stock code contains paths where software policy state can be advanced before lower-level PM success is sufficiently established.

Conceptually:

```text id="j4id5z"
request new PM policy
        |
        v
software publishes requested state
        |
        v
send lower-level request
        |
        X
failure
```

The software state can then represent intent rather than established reality.

A1/A1R separate:

```text id="3elvyv"
desired policy
requested transition
confirmed transition
committed policy
```

The corrected conceptual model is:

```text id="5t4bvo"
desired policy
        |
        v
transition in progress
        |
        v
lower-level PM operation
        |
        +---- success
        |       |
        |       v
        |   commit policy
        |
        +---- failure / ambiguity
                |
                v
        explicit failure handling
```

---

# 16. G18 — Independent Sleep-Inhibit Ownership

Multiple independent activities can require the WLAN device or host PM layer to remain active.

Examples include:

```text id="miwywo"
ACTIVE policy
PM transition
JOIN / association lifecycle
```

These are separate ownership reasons.

Treating them as one undifferentiated flag risks allowing one path to release a restriction still needed by another.

The corrected model treats them as independent logical claims:

```text id="7rfu84"
ACTIVE claim --------+
                     |
PM transition claim -+----> sleep inhibited
                     |
JOIN claim ----------+
```

Removing one claim removes only that owner.

---

# 17. G19 — PM Transition Generation

Multiple PM transitions can overlap in time.

For example, an older request to enter power save may still be completing when a newer request changes desired policy to Active.

Without generation/ownership tracking:

```text id="w1nxvt"
generation N
Power Save transition
        |
        | delayed completion
        |
        +--------------------+
                             |
generation N+1               |
Active requested             |
        |                    |
        v                    |
new desired policy           |
                             v
                     old Final-Sleep
```

The older operation must not finalize state belonging to the newer intent.

A1 introduced transition generation/ownership handling.

A1R retains it.

---

# 18. Historical A1 Model

A1 was a correctness patch around the existing Shelly PM architecture.

Its model was approximately:

```text id="4byu7a"
desired PM policy
        |
        v
new transition generation
        |
        v
acquire required sleep-inhibit ownership
        |
        v
perform Wake / transport / PM operation
        |
        +--------------------------+
        |                          |
        v                          v
success                    failure / ambiguity
        |                          |
        v                          v
validate ownership          preserve ambiguity safely
        |
        v
publish committed state
        |
        v
release only owned claims
        |
        v
Final-Sleep only if current
transition still permits it
```

The key principles were:

- desired policy is not committed policy
- timeout is not cancellation
- late completions require identity
- independent wake reasons require independent ownership
- stale transitions cannot commit newer state
- Final-Sleep requires valid current ownership
- partial Wake cannot masquerade as successful Wake

---

# 19. A1 Regression and A1R

Later qualification identified an experimental regression introduced by A1.

Five verified paths use `request1` as a temporary override:

```text id="sj9daf"
physical button
HTTP /psovrd
Cloud psovrd
SSI settings_sta
OTA launcher
```

The intended behavior is approximately:

```text id="h6remu"
selected policy = 3
temporary request = 1
use 1 temporarily
restore 3
```

Old A1 could allow the temporary `1` to become persistent selected policy.

For example:

```text id="7m79gn"
3 / 3
    |
temporary override
    |
    v
1 / 1
```

where the second state could persist incorrectly.

This was a regression introduced by the experimental A1 implementation.

It is **not** classified as a stock Shelly firmware defect.

The corrected implementation is:

```text id="fbb8gw"
A1R
```

A1R preserves the A1 lifecycle corrections while correcting only the verified temporary-return cases.

A1R passed:

```text id="779taj"
151 / 151 Thumb behavior tests
```

together with retained-state, generation, interaction and malformed-input qualification.

Historical A1 results remain historical A1 results.

They must not be relabeled as A1R.

---

# 20. Shared Host Sleep Blockers

Host MCU sleep eligibility is governed separately from the PM52 lifecycle.

The principal reconstructed shared counters are:

```text id="ceua5m"
B2
B3
```

The selector behaves approximately as:

```text id="m676x8"
if B2 != 0:
    deepest permitted mode = EM1

else if B3 != 0:
    deepest permitted mode = EM2

else:
    deepest permitted mode = EM3
```

B2 and B3 are reference counters, not Boolean flags.

---

# 21. B3 and Normal EM2

Firmware installs a persistent B3 contribution during normal startup.

That makes:

```text id="0l36nq"
B3 != 0
```

the normal condition.

The current RTC/tickless design uses a low-frequency clock configuration that is incompatible with ordinary EM3 residency.

Consequently:

```text id="fho83c"
B2 = 0
B3 != 0
```

selects:

```text id="y2l92j"
EM2
```

as the normal intended deepest idle mode.

Removing B3 simply to force EM3 is not an appropriate battery fix.

---

# 22. B2 Concurrency Defect

B2 counts independent owners requiring EM1.

Conceptually:

```text id="xa126e"
B2 = 0  -> no current owner
B2 = 1  -> one owner
B2 = 2  -> two owners
```

The problem is that not all stock B2 read-modify-write paths are serialized consistently.

A task can load B2, be preempted, allow another context to modify B2, and later store an update derived from the stale value.

This allows both:

```text id="8yte7b"
phantom B2
```

and:

```text id="jlrqhj"
lost B2
```

states.

A phantom contribution can incorrectly keep the host limited to EM1.

A lost contribution can incorrectly permit EM2 while another subsystem still owns an EM1 restriction.

The defect therefore affects correctness in both directions.

---

# 23. Qualified B2 Serialization

The B2 correction preserves reference-counter semantics.

It does not:

```text id="geuu46"
force B2 = 0
replace B2 with Boolean state
remove legitimate concurrent ownership
```

Instead, it serializes the complete relevant B2 read-modify-write operation in a bounded protected section while preserving incoming interrupt-mask state and existing assertion semantics.

The correction has been independently qualified and is part of:

```text id="vsz35s"
B2.1
B2.1_OBS
B2.2
```

This correction is separate from A1R.

Conceptually:

```text id="jfq7r7"
A1R
    PM lifecycle correctness

B2 serialization
    shared blocker accounting correctness
```

---

# 24. PA8 — Independent WLAN Sleep Gate

Host sleep selection does not end with B2/B3.

PA8 is sampled before low-power entry.

PA8 was traced to the WLAN host-notification path.

Conceptually:

```text id="b2chdm"
B2/B3 select permitted mode
        |
        v
check PA8
        |
        +-- LOW  -> WFI may execute
        |
        +-- HIGH -> return without WFI
```

PA8 therefore provides a separate WLAN-side sleep veto.

A HIGH PA8 state is not automatically a defect.

If WLAN work is pending, preventing host sleep can be correct.

---

# 25. Selected Mode Is Not Entered Mode

A host may satisfy:

```text id="ejwd7i"
B2 = 0
B3 != 0
```

causing the selector to choose:

```text id="xw3kyw"
EM2
```

while:

```text id="abh6ow"
PA8 = HIGH
```

prevents WFI.

Therefore:

```text id="xv5msb"
EM2 selected
```

does not prove:

```text id="30mw8a"
EM2 physically entered
```

This is analogous to the radio-side distinction between PM52 success and physical WF200 sleep.

---

# 26. `/stats sleep_ratio`

Firmware 2.2.4 exposes:

```text id="qc7av2"
sleep_ratio
```

through `/stats`.

Reverse engineering indicates that this is derived from tickless timing/compensation behavior.

It is not a direct measurement of:

```text id="h8ih56"
EFM32GG11 EM1 residency
EFM32GG11 EM2 residency
WF200 sleep residency
```

It must therefore not be treated as a physical sleep percentage.

---

# 27. D3 `PS_MODE_ERROR`

WF200 exposes a host-visible power-save error indication:

```text id="vklrja"
D3 PS_MODE_ERROR
```

Known reason classes include:

```text id="l0yseb"
Reason 0
PS-Poll timeout

Reason 1
U-APSD timeout

Reason 2
buffered unicast not delivered across consecutive beacons

Reason 3
unstable beacon timing / beacon-window compensation
```

D3 is fundamentally different from Shelly's:

```text id="vx9wdl"
real_beacon_skip
```

because D3 originates from WF200 PM-error reporting, while `real_beacon_skip` is calculated by the host from received-beacon statistics.

---

# 28. Historical D3 Observation

A dedicated D3 observer was used while normal Shelly Beacon Recovery remained active.

The test separated:

```text id="h6k1cy"
Shelly host path:

beacon statistics
        |
        v
real_beacon_skip
        |
        v
Beacon Recovery
```

from:

```text id="759jhp"
WF200 path:

internal PM error
        |
        v
D3 PS_MODE_ERROR
```

One historical observation reached approximately:

```text id="lyo2la"
runtime:              63.93 h
Beacon Recoveries:    3835
Recovery rate:        ~59.99/hour
desired skip:         20
real skip:            1
D3 PS_MODE_ERROR:     0
```

The important result is:

```text id="nj4s03"
3835 Shelly Beacon Recoveries
0 observed D3 PS_MODE_ERROR events
```

Therefore those Recoveries cannot be described as 3,835 WF200-reported D3 PM failures.

D3 is not a complete physical sleep monitor, so this does not prove that every aspect of WF200 PM behavior was correct.

---

# 29. Beacon Recovery and PM State

Beacon Recovery temporarily changes the PM configuration.

A simplified normal sequence is:

```text id="tvgj25"
State 3
Beacon Power Save
Fast Power Save
desired skip N
        |
        | Recovery
        v
State 1
Active / Always-On
        |
        | approximately 5 serviced seconds
        v
State 3
Beacon Power Save
Fast Power Save
desired skip N
```

During the Recovery interval:

- WF200 Active / Always-On is requested
- host-side deeper sleep restrictions may increase
- additional WLAN control work occurs

Repeated Recovery therefore creates real additional activity.

Its exact electrical cost has not been measured.

---

# 30. Stock Recovery Occupancy

In the historical D3-observer period:

```text id="6vrrho"
3835 Recoveries
over
63.93 hours
```

corresponded to approximately:

```text id="6aoj3a"
59.99 Recoveries/hour
```

At roughly five seconds per Recovery:

```text id="ijfl8a"
60 × 5 s
≈ 300 s/hour
≈ 5 min/hour
≈ 8.33% wall-clock Recovery occupancy
```

Across that complete period:

```text id="p6vmch"
3835 × ~5 s
≈ 19175 s
≈ 319.6 min
≈ 5.33 h
```

of explicit Recovery time accumulated.

These are time figures.

They are not percentages of battery consumption.

---

# 31. C-C and Recovery Validity

C-C corrects three demonstrated host-side validity problems in the Beacon Recovery chain.

These are summarized as:

```text id="er6ktu"
C1a
signed interpretation of cached control data

C1b
measurement-window validity

C2
reuse of historical Recovery evidence after baseline reset
```

C2 must not be described as an unavoidable permanent loop.

The behavior is better characterized as metastable: the firmware can leave the recurrence under some runtime conditions.

C-C invalidates historical Recovery evidence after Recovery and requires a fresh comparable measurement before another Recovery can be triggered.

---

# 32. C-C Does Not Disable Fresh Recovery

The corrected sequence is approximately:

```text id="33e9cy"
fresh valid R = 1/2
        |
        v
Recovery
        |
        v
baseline invalidated
        |
        v
next sample establishes new baseline
        |
        v
old R cannot trigger Recovery
        |
        v
later comparable sample
        |
        v
fresh R
        |
        +-- non-qualifying -> continue
        |
        +-- qualifying     -> fresh Recovery
```

Fresh Recovery therefore remains possible.

The presence of a fresh Recovery event is not evidence that C-C failed.

---

# 33. Historical C-C Recovery Rates

With the observed measurement cadence, C-C can require roughly two measurement opportunities to produce another fresh result.

Historical corrected runs showed approximately:

```text id="42098t"
27–30 fresh Recoveries/hour
```

during specific periods.

This is not a universal C-C rate.

It is a historical measurement resulting from:

- the test network
- the measurement cadence
- the current estimator behavior
- continued qualifying fresh values

At approximately five seconds per Recovery, 30 events/hour correspond to:

```text id="s5gy0w"
~150 s/hour
~2.5 min/hour
~4.17% wall-clock Recovery occupancy
```

A historical ~27/hour interval corresponds to:

```text id="wi5o5c"
~135 s/hour
~2.25 min/hour
~3.75% wall-clock Recovery occupancy
```

Again, these values describe occupancy, not energy.

---

# 34. Recovery Frequency Is Not a Simple Optimization Variable

Reducing Recovery frequency is not automatically equivalent to improving battery life.

A directly observed effect is:

```text id="vvix4t"
more Recovery
    |
    v
more explicit Active / Recovery time
```

A different possibility remains hypothetical:

```text id="8qgr04"
unknown WF200 condition leaves radio awake
        |
        v
Recovery happens to clear it
        |
        v
less frequent Recovery could allow
the hypothetical fault to persist longer
```

The second mechanism has not been demonstrated.

This is why C-C removes invalid/stale Recovery evidence without arbitrarily eliminating all fresh Recovery.

---

# 35. Historical Recovery-Rate Trade-Off Example

Under a purely hypothetical model in which Recovery reliably detects and clears an otherwise hidden fault:

| Recovery rate | Interval | Explicit Recovery time/hour | Maximum hypothetical delay | Average hypothetical delay |
|---:|---:|---:|---:|---:|
| 60/hour | 1 min | ~300 s | ~1 min | ~30 s |
| 30/hour | 2 min | ~150 s | ~2 min | ~1 min |
| 4/hour | 15 min | ~20 s | ~15 min | ~7.5 min |

The Recovery-time column is based on the approximately five-second observed Recovery duration.

The hypothetical fault-delay columns are not measurements.

They illustrate why Recovery cannot be optimized solely from its visible occupancy until the physical condition behind the heuristic is understood.

---

# 36. `real_beacon_skip` Is Not PM Readback

Shelly exposes:

```text id="fbfu1p"
desired_beacon_skip
```

and:

```text id="azq5vf"
real_beacon_skip
```

The naming can suggest:

```text id="fsr67w"
desired = requested
real    = actual hardware setting
```

That interpretation is not supported by implementation.

`real_beacon_skip` is calculated by the host from received-beacon statistics.

It is not direct readback of:

- WF200 listen interval
- WF200 PM mode
- WF200 hardware sleep state
- physical radio sleep residency

Therefore:

```text id="ho01pd"
desired_beacon_skip = 20
real_beacon_skip    = 1
```

does not prove:

```text id="j5qxya"
WF200 accepted listen interval 1
```

and does not prove:

```text id="cpfn7e"
WF200 stayed continuously awake
```

---

# 37. The Estimator Can Produce Higher Values

Historical integrated testing also showed values such as:

```text id="9u58t5"
desired_beacon_skip = 15
real_beacon_skip    = 13
```

The estimator is therefore not simply fixed at `1`.

It can produce values close to the requested skip.

That does not transform it into physical PM telemetry.

---

# 38. WF200 3.18.0

Silicon Labs WF200 firmware 3.18.0 includes a relevant radio-side fix for an error that could prevent the device from sleeping after a power-save mode change.

This is technically significant because Shelly repeatedly changes WF200 PM configuration during normal operation and Beacon Recovery.

The supported conclusion is narrow:

> WF200 3.18.0 contains an official Silicon Labs fix for a radio-side condition that could prevent the device from sleeping after a power-save mode change.

This does **not** prove:

```text id="gywnkp"
that defect caused historical Shelly TRV battery drain
```

and does not prove:

```text id="bqtcww"
all older WF200 PM transitions failed
```

---

# 39. WF200 3.18.0 Does Not Correct Shelly Host C2

WF200 3.18.0 was tested with otherwise stock Shelly host behavior.

The recurring stock 2.2.4 Beacon Recovery pattern continued.

That is expected because C2 exists in Shelly host logic.

Conceptually:

```text id="k42sjl"
WF200 3.18.0
        |
        +-- can correct radio-side behavior
        |
        X
        cannot correct Shelly host C2 logic
```

Host and radio fixes are therefore separate.

---

# 40. Shelly FMAC 3.7.0 + WF200 3.18.0

Shelly firmware 2.2.4 uses:

```text id="rqn2wc"
FMAC 3.7.0
```

The experimental integration preserves that host driver while replacing the WF200 radio image with official 3.18.0.

Hardware testing demonstrated:

```text id="c8ut3p"
FMAC 3.7.0
+
WF200 3.18.0
    |
    v
WF200 initialization
    |
    v
scan
    |
    v
association
    |
    v
DHCP
    |
    v
cloud
    |
    v
normal TRV operation
```

This establishes practical interoperability on the tested hardware.

It is not an official Shelly or Silicon Labs compatibility qualification.

---

# 41. B2.1

The observer-free corrected integration is:

```text id="a5zl9g"
B2.1
```

B2.1 contains:

```text id="18px6q"
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

For power-management analysis, the important layers are:

```text id="jadum1"
A1R
    host PM lifecycle

C-C
    Beacon Recovery evidence validity

B2 serialization
    host sleep-blocker accounting

WF200 3.18.0
    radio-side PM implementation
```

These are not alternative versions of the same fix.

They correct different defect classes.

---

# 42. PM52→cmd66 Observer

The current observer records already-existing PM and beacon-statistics activity.

It records:

- actual PM52 payloads
- native PM52 results
- A1R completion decisions
- existing periodic command-0x66 requests/results
- fresh estimator operands
- connection epochs
- a 12-record recent-event ring
- first-fault freeze state

It generates no additional WF200 PM request.

It adds no:

```text id="f7d5gw"
new timer
new task
new queue
automatic network traffic
flash write
PM policy change
```

Readout is performed only when `/status` is explicitly queried.

---

# 43. B2.1_OBS

The current long-term hardware build is:

```text id="y53nc2"
B2.1_OBS
```

defined as:

```text id="ry1gja"
B2.1
+
PM52 -> cmd66 observer
```

Its purpose is not to reproduce the known B2 race.

B2.1_OBS already contains the B2 correction.

Its purpose is to observe the corrected integrated platform and capture the first relevant PM/radio fault if rapid drain still develops.

Software noninterference has been qualified.

As with any instrumentation, physical timing perturbation cannot be absolutely excluded.

---

# 44. B2.1_OBS Qualification

Qualification included:

```text id="74dfno"
A1R:
151 / 151

observer/readout:
356 / 356

B2:
2060 + mixed/preemption qualification

MQTT:
258

plus:
C-C qualification
decoder regressions
deterministic reconstruction
container verification
zero unexplained changes
```

The resulting disposition was:

```text id="xw67jp"
B2.1_OBS RELEASE-CANDIDATE GO
```

This means it passed the project's qualification gates for controlled long-term hardware testing.

It does not mean:

```text id="ilqp73"
production firmware
```

or:

```text id="gnp4ce"
battery-drain root cause solved
```

---

# 45. Current Hardware Population

The current test population is:

```text id="t6xngk"
.77  -> B2.1_OBS
.88  -> B2.1_OBS
.11  -> B2.1_OBS
.71  -> B2.1_OBS
.234 -> B2.1_OBS
.61  -> B2.1_OBS
.97  -> stock 2.2.4 control
```

or:

```text id="p1jg6j"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

Initial observations showed no Beacon Recovery errors on the B2.1_OBS devices during the first observed interval, while the stock control showed large historical Beacon Recovery counts.

These observations are preliminary.

They are not battery-lifetime results.

---

# 46. Current Research Decision

The current phase is:

```text id="d4e4dj"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

No additional PM hypothesis should currently be inserted into the hardware experiment without new evidence.

No new firmware should be flashed into the test population.

No deliberate network-variable change should be introduced.

The current objective is longitudinal evidence.

---

# 47. If B2.1_OBS Drains

If a corrected device develops a genuine drain episode, the next sequence is:

```text id="6abvwo"
capture first fault
        |
        v
correlate PM52/cmd66 telemetry
        |
        v
correlate voltage/runtime behavior
        |
        v
resume deeper reverse engineering
```

The first-fault observer exists specifically to make such an event diagnostically useful.

---

# 48. If B2.1_OBS Remains Stable

If B2.1_OBS remains stable over the required long-term period, the next logical path is:

```text id="pwo3ga"
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

Observer removal matters because diagnostic instrumentation should not automatically become part of a final firmware candidate.

---

# 49. B2.2

A later observer-free integration was constructed offline as:

```text id="ah0gkm"
B2.2
```

B2.2 contains nine selected, demonstrated and qualified correction components:

```text id="7r45ft"
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

The current disposition is:

```text id="jqsj0y"
B2.2 OFFLINE RELEASE-CANDIDATE GO
```

No physical TRV was contacted for the B2.2 qualification phase.

Therefore B2.2 is:

```text id="fl7vg3"
offline-qualified
```

but not:

```text id="88x7ep"
hardware-qualified
```

and not:

```text id="gw1l9t"
a proven final battery-drain fix
```

B2.2 is intentionally not being rolled onto the active long-term hardware population while B2.1_OBS testing is underway.

---

# 50. Additional Power-Related Qualified Corrections

Several additional resource-lifecycle defects were discovered after the earlier PM document was written.

They are relevant to the final integrated correction set but are not central to the WLAN PM state machine.

## P01 — Battery ADC PA3 Cleanup

An ADC timeout can return without correctly releasing PA3-related state.

A later successful cycle may repair the state.

The direct energy impact has not been measured.

The correction has been qualified.

## P02 — I2C Timeout Retirement

An I2C timeout can return with unfinished state and interrupt-enable state still active.

A bounded retirement correction has been qualified.

## P03 — WLAN GPIO Interrupt Mask

A disable path passes decimal `10` where the underlying helper expects a bitmask.

This can leave the intended interrupt state incorrect.

The correction has been qualified.

These corrections are included in B2.2.

---

# 51. Deferred Power-Related Candidates

Not every suspicious path has been promoted into B2.2.

Deferred items include:

```text id="qs79xm"
P04 motor movement accounting after timeout
P11 raw ADC transient publication
valve_min_percent mixed-unit issue
raw TXDMA candidates
P05/P06/P07/P08/P10/P12/P13
mDNS
EM3 redesign
diagnostic FastPS experiments
```

A suspicious path is not enough for inclusion.

The project requires:

```text id="ey2jdr"
demonstrated
+
safely correctable
+
independently qualified
+
composition-qualified
```

before promoting a correction into the integrated candidate.

---

# 52. What the Available Interfaces Can Tell Us

The host can observe:

```text id="5mzp3e"
requested PM policy
PM52 payload
PM52 result/status
WUP / wake-handshake state
received-beacon statistics
D3 PS_MODE_ERROR
application PM state
host blocker state
connection epochs
```

These are valuable.

They still do not provide continuous physical RF sleep measurement.

---

# 53. What the Available Interfaces Do Not Prove

A successful PM52 confirmation does not prove:

```text id="3e0ojt"
WF200 physically slept
```

WUP LOW does not prove:

```text id="i1wz38"
WF200 physically slept
```

`real_beacon_skip = 1` does not prove:

```text id="17rnj4"
WF200 remained awake
```

`real_beacon_skip = 20` does not prove:

```text id="se7avg"
WF200 slept exactly twenty beacon periods
```

absence of D3 `PS_MODE_ERROR` does not prove:

```text id="5ohb1e"
all internal WF200 PM behavior was correct
```

B2 = 0 does not prove:

```text id="98l3vd"
host entered EM2
```

and a Beacon Recovery event does not prove:

```text id="cc9q1v"
WF200 reported a PM failure
```

---

# 54. Why This Matters for Battery Analysis

Battery life depends on actual electrical state residency.

Firmware telemetry mostly provides:

- requested policy
- software state
- command completion
- blocker state
- indirect beacon statistics
- error indications

The project therefore combines:

```text id="9haxng"
static firmware analysis
        +
executable qualification
        +
runtime telemetry
        +
PM state transitions
        +
WF200 error observation
        +
beacon statistics
        +
battery-voltage trends
        +
stock controls
        +
controlled firmware variants
```

No single software value is treated as a direct battery-current measurement.

---

# 55. Battery Percentage Is Not a Coulomb Counter

Static analysis of the TRV battery-reporting path shows that the displayed battery percentage is not derived from a coulomb counter.

It is calculated from cached battery voltage using a stateless integer mapping.

Therefore:

```text id="rq87q3"
battery %
```

is useful as a coarse user-facing indicator but is not a precise energy measurement.

For short-term comparisons, battery voltage is generally more informative.

Even voltage must be interpreted carefully because it depends on:

- instantaneous load
- valve movement
- temperature
- recent charging
- relaxation
- radio activity

Short voltage intervals must not be linearly extrapolated into lifetime.

---

# 56. Battery Shutdown Threshold

For the analyzed firmware generations:

```text id="ipmm4l"
2.1.0
2.1.3
2.1.8
2.2.4
```

the low-voltage shutdown threshold is:

```text id="0wm5cm"
3000 mV
```

Below that threshold, the firmware uses a short serviced-second countdown before driving the relevant shutdown control.

The board-level rail behavior after that control transition has not been independently electrically verified.

This is separate from the PM-drain investigation but important when interpreting terminal battery behavior.

---

# 57. Valve Activity Is a Major Confounder

The TRV motor can represent a significant load compared with idle operation.

Battery comparison must therefore account for:

- calibration
- valve movement
- target-temperature changes
- heating demand
- mechanical travel

A recently calibrated or heavily moving TRV cannot be compared directly with a stationary control over a short interval solely from voltage drop.

Long-term observation is required.

---

# 58. Recovery Time Is Not Battery Percentage

For example:

```text id="4esfkc"
stock historical case:

~60 Recoveries/hour
× ~5 s
≈ ~300 s/hour
≈ 8.33% wall-clock occupancy
```

does not mean:

```text id="r5qf89"
8.33% more battery consumption
```

Likewise:

```text id="x1lckp"
~30 Recoveries/hour
× ~5 s
≈ ~150 s/hour
≈ 4.17% wall-clock occupancy
```

does not imply:

```text id="0xuo4g"
4.17% battery consumption
```

Electrical current differs across states and has not been directly measured in this project.

---

# 59. Historical Firmware Context

Battery drain was observed on:

```text id="ah1mtl"
2.1.x
```

and:

```text id="wx3o48"
2.2.4
```

The aggressive analyzed 2.2.4 Beacon Recovery behavior therefore cannot by itself explain the entire historical problem.

A useful model is:

```text id="eehfhv"
shared underlying architecture
    |
    +-- host PM lifecycle
    +-- blocker accounting
    +-- radio PM behavior
    +-- peripheral/resource lifecycle

2.2.4-specific behavior
    |
    +-- Beacon Recovery implementation
    +-- C1a/C1b/C2
```

Beacon Recovery can therefore be an amplifier without being the original root cause.

---

# 60. Current Power-Management Model

The corrected conceptual path is:

```text id="z1ftuh"
Application requests PM policy
        |
        v
desired policy
        |
        v
A1R transition ownership / generation
        |
        v
acquire required inhibit ownership
        |
        v
Wake if required
        |
        v
perform transport operation
        |
        v
WF200 PM52 request
        |
        +-------------------------------+
        |                               |
        v                               v
successful completion            failure / ambiguity
        |                               |
        v                               v
validate transition             preserve safe failure state
        |
        v
publish committed state
        |
        v
release only owned restrictions
        |
        v
Final-Sleep if still valid
        |
        v
WUP may be released
        |
        v
WF200 permitted to sleep
```

In parallel, host MCU sleep eligibility is governed by:

```text id="90bb97"
B2
B3
PA8
```

These mechanisms are related but distinct.

---

# 61. Current Experimental Stack

The current long-term diagnostic stack is:

```text id="i6yami"
Shelly TRV 2.2.4 application
        |
        v
A1R
host PM lifecycle correctness
        |
        v
B2 bounded serialization
host sleep-blocker correctness
        |
        v
C-C
Beacon Recovery validity
        |
        v
Shelly FMAC 3.7.0
        |
        v
WF200 3.18.0
        |
        v
PM52 -> cmd66 observer
```

This build is:

```text id="3b1thh"
B2.1_OBS
```

The observer is diagnostic.

It is not a production feature.

---

# 62. Current Long-Term Test Strategy

The current test compares six corrected observer devices with one stock 2.2.4 control.

The important metrics include:

```text id="ry8vpr"
battery voltage
battery percentage

uptime
reboot behavior
reconnect behavior

valve position
target temperature
measured temperature

desired_beacon_skip
real_beacon_skip
Beacon Recovery / beacon_err behavior

PM52 -> cmd66 observer state

firmware identity
WF200 version
```

Battery voltage receives more weight than displayed percentage for short-term interpretation.

Long observation windows receive more weight than isolated measurements.

---

# 63. Questions That Remain Open

The remaining questions are narrower than at the beginning of the investigation.

## 1. Does B2.1_OBS remain stable long term?

Initial behavior is not sufficient.

Battery lifetime requires longitudinal evidence.

## 2. If drain returns, what happens first?

The observer is intended to distinguish PM52 failure, completion ambiguity, estimator behavior and connection epoch around the first relevant anomaly.

## 3. What causes fresh low `real_beacon_skip` values?

C-C removes invalid/stale evidence.

Fresh low estimates can still exist.

Their physical interpretation remains unresolved.

## 4. Does a fresh low estimate correspond to radio wakefulness?

No direct physical sleep-residency measurement currently establishes this.

## 5. Is fresh Beacon Recovery actually required?

The current experiment does not change this variable.

## 6. Does WF200 3.18.0 materially improve long-term behavior?

The firmware contains a relevant official fix, but practical battery benefit has not been isolated.

## 7. Which corrected defects materially contributed to historical drain?

Demonstrating a defect and quantifying its battery contribution are different tasks.

## 8. Does B2.2 remain correct on physical hardware?

B2.2 is currently offline-qualified only.

---

# 64. Questions for Shelly / Original Design Intent

Several implementation questions remain useful.

First:

> What actual WF200 or WLAN condition was a calculated `real_beacon_skip = 1` or `2` intended to identify?

Second:

> What host-visible condition was intended to confirm that WF200 had returned to correct low-power operation after an Active-to-Power-Save Recovery cycle?

Third:

> If Beacon Recovery was intended to recover a WF200 condition not represented by D3 `PS_MODE_ERROR`, what host-visible evidence was expected to identify that condition?

These questions matter because the host interfaces expose:

- requested PM policy
- PM command completion
- wake-handshake state
- beacon statistics
- D3 PM-error reporting

but no direct continuous physical RF-sleep telemetry has been identified.

---

# 65. Current Conclusions

Shelly TRV Gen1 power management consists of several interacting but distinct layers.

The application selects policy.

A1R maintains host PM lifecycle and transition ownership.

B2/B3 determine host sleep eligibility.

PA8 independently gates WFI.

PM52 configures WF200 power-save policy.

WUP controls whether the host currently requires WF200 awake.

WF200 then controls its own internal radio state.

The following distinctions remain essential:

```text id="gpnb4s"
PM52 success
!=
physical RF sleep
```

```text id="9snv7a"
WUP LOW
!=
physical RF sleep
```

```text id="kp2gn0"
real_beacon_skip
!=
WF200 PM readback
```

```text id="bb3ox9"
B2 = 0
!=
physical EM2 residency
```

```text id="70dwdq"
D3 PS_MODE_ERROR = 0
!=
all internal WF200 PM behavior proven correct
```

The project has demonstrated several genuine firmware defects.

A1/A1R address host PM lifecycle defects.

C-C addresses Beacon Recovery validity defects.

Bounded B2 serialization addresses a shared host sleep-blocker race.

WF200 3.18.0 introduces a relevant official radio-side power-save correction.

Additional qualified resource-lifecycle corrections exist in B2.2.

The current long-term hardware test uses:

```text id="1tubxf"
6 × B2.1_OBS
1 × stock 2.2.4 control
```

The current research decision is:

```text id="z87mee"
WAIT
OBSERVE
COLLECT VOLTAGE/RUNTIME DATA
DO NOT CHANGE TEST VARIABLES
```

No demonstrated result currently supports the statement:

```text id="h1ij8b"
the historical battery-drain root cause is proven
```

Likewise, the successful offline qualification of B2.2 does not establish:

```text id="2cbzcm"
B2.2 is hardware-qualified
```

The current strongest position is:

> Multiple real host-side and radio-relevant defects have been demonstrated and qualified corrections have been produced. The corrected B2.1_OBS platform is now undergoing long-term hardware observation to determine whether those corrections materially change the historical battery-drain behavior and, if drain still occurs, to capture the first useful PM fault state.

---

# Related Documents

PM lifecycle and A1/A1R:

[`pm-lifecycle-and-a1.md`](pm-lifecycle-and-a1.md)

Host sleep and blocker accounting:

[`host-sleep-and-blocker-accounting.md`](host-sleep-and-blocker-accounting.md)

Detailed Beacon Recovery analysis:

[`recovery-mechanism.md`](recovery-mechanism.md)

Detailed `real_beacon_skip` analysis:

[`real-beacon-skip.md`](real-beacon-skip.md)

WF200 firmware:

[`wf200-firmware.md`](wf200-firmware.md)

WF200 beacon-counter analysis:

[`beacon-rx-counter.md`](beacon-rx-counter.md)

Firmware chronology:

[`firmware-comparison.md`](firmware-comparison.md)

Periodic mDNS behavior:

[`mdns-periodic-restart.md`](mdns-periodic-restart.md)

AP selection and roaming:

[`ap-selection-and-roaming.md`](ap-selection-and-roaming.md)

Experimental patch documentation:

[`../patch/README.md`](../patch/README.md)

Experimental device matrix:

[`../testing/experimental-device-matrix.md`](../testing/experimental-device-matrix.md)

Battery testing:

[`../testing/battery-testing.md`](../testing/battery-testing.md)

---

# Research Notes

This analysis is based on static reverse engineering of locally obtained Shelly TRV Gen1 firmware together with executable qualification and runtime testing on personally owned devices.

The power-management analysis includes:

- Shelly application PM-state transitions
- WF200 command `0x52`
- Wake and Final-Sleep handling
- WUP lifecycle
- transport ownership
- completion ownership
- sleep-inhibit ownership
- PM transition generations
- B2/B3 blocker accounting
- task-preemption analysis
- PA8 sleep admission
- Beacon Recovery interaction
- WF200 D3 `PS_MODE_ERROR`
- WF200 3.18.0 integration
- A1 and A1R qualification
- B2 serialization qualification
- PM52→cmd66 observation
- long-term battery observation

Historical experimental stages remain labeled according to the firmware actually used.

A1 measurements are not retroactively described as A1R.

Older B2 builds are not retroactively described as B2.1.

No original or modified complete Shelly firmware image, proprietary complete function, or large raw disassembly is published in this document.

The project distinguishes between:

```text id="2duuwk"
what the host requests
what the host reports
what executable qualification demonstrates
what hardware observation demonstrates
what can actually be concluded about physical state
```

Those distinctions are particularly important in low-power firmware, where a successful software transition is not itself a measurement of the resulting electrical state.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

The analysis applies only to the firmware versions and hardware investigated here.

Experimental firmware should only be used on devices where recovery or reflashing is possible.