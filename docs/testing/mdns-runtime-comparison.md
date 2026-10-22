```markdown
# mDNS Runtime Comparison

## Scope

This document records runtime validation of the periodic mDNS behavior identified during reverse engineering of Shelly TRV Gen1 firmware.

The focus here is deliberately narrow:

- packet-capture behavior of different firmware versions
- observed mDNS cadence
- runtime validation of Patch B
- long-term behavior of the Patch-B device
- separation of periodic mDNS activity from Beacon Recovery
- what these observations do and do not establish about battery drain

The static implementation of the periodic restart, its callers and the exact Patch-B modification are documented separately in:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

This document describes runtime behavior.

It does **not** directly measure electrical current, charge consumption or physical radio sleep residency.

---

# 1. Test Matrix

The relevant runtime configurations are:

| Configuration | Periodic mDNS | Beacon Recovery | Purpose |
|---|---|---|---|
| 2.1.0 stock | no comparable periodic burst observed | 2.2.4 mechanism absent | older firmware reference |
| 2.1.3 stock | observed | 2.2.4 mechanism absent | early periodic-mDNS reference |
| 2.2.4 stock | observed | stock | current stock reference |
| 2.2.4 + Patch B | targeted periodic restart suppressed | stock | mDNS isolation |
| 2.2.4 + C-C | unchanged | validity-corrected | Beacon Recovery comparison |
| 2.2.4 + A1 + C-C | unchanged | validity-corrected | integrated host-PM reference |

The first four configurations are the main subject of this document.

C-C and A1 are included only where later runtime results help interpret the relationship between mDNS and Beacon Recovery.

---

# 2. Original Packet-Capture Setup

The original cross-version experiment observed three physical Shelly TRV Gen1 devices simultaneously on the same local network.

At the time of that capture:

| Device | Firmware | Role |
|---|---|---|
| `.11` | 2.1.0 stock | older firmware reference |
| `.77` | 2.1.3 stock | periodic-mDNS comparison |
| `.229` | 2.2.4 stock | stock 2.2.4 comparison |

Packet capture was performed using TShark on macOS.

The capture filter selected UDP port 5353 traffic from the three devices.

Conceptually:

```text
udp port 5353 and
(
    host <2.1.0 device> or
    host <2.1.3 device> or
    host <2.2.4 device>
)
```

The observation lasted approximately:

```text
13 minutes
```

No active requests were intentionally sent to the TRVs during this observation.

The purpose was to compare naturally occurring mDNS traffic rather than provoke service discovery manually.

Device identifiers in this document describe the firmware state at the time of each experiment. Several devices were reflashed later and must not be treated as permanently associated with one firmware version.

---

# 3. Firmware 2.1.0

Historical device:

```text
.11
```

Firmware:

```text
2.1.0
```

During the approximately 13-minute simultaneous capture, no mDNS packets from this device were observed.

The result is consistent with the static firmware comparison:

```text
mDNS responder exists

but

no comparable recurring connected-maintenance
restart was identified in the examined path
```

The runtime observation should be interpreted narrowly:

> No periodic mDNS burst comparable to the later firmware versions was observed from the 2.1.0 device during this approximately 13-minute capture.

It does not mean that firmware 2.1.0 can never transmit mDNS.

Startup, registration or other event-driven mDNS behavior remains possible.

---

# 4. Firmware 2.1.3

Historical device:

```text
.77
```

Firmware at the time:

```text
2.1.3
```

The device repeatedly produced a characteristic mDNS sequence approximately once per minute.

A normal observed burst consisted of:

```text
probe
probe
probe
announcement
```

One representative sequence was:

```text
59.699 s   probe
60.006 s   probe
60.211 s   probe
60.520 s   announcement
```

Observed burst starts included approximately:

```text
0.0 s
59.7 s
119.8 s
179.8 s
239.6 s
299.7 s
359.6 s
419.7 s
480.2 s
539.8 s
599.6 s
659.8 s
719.8 s
779.9 s
```

The runtime cadence is therefore approximately:

```text
60 seconds
```

This agrees with the connected-maintenance behavior identified in the corresponding firmware.

The important runtime result is simple:

> Firmware 2.1.3 actively restarts the mDNS probing sequence at approximately one-minute intervals under the tested conditions.

---

# 5. Firmware 2.2.4 Stock

Historical reference device:

```text
.229
```

Firmware:

```text
20240619-130912/v2.2.4@ee290818
```

Stock firmware 2.2.4 produced the same general class of mDNS probe/announcement activity as 2.1.3, but at a lower frequency.

Observed burst starts included:

```text
117.555 s
297.779 s
477.492 s
657.413 s
```

The resulting intervals were:

```text
180.225 s
179.713 s
179.921 s
```

The observed cadence is therefore approximately:

```text
180 seconds
```

A normal burst again contained approximately:

```text
3 probes
+
1 announcement
```

The packet capture therefore confirms that the periodic restart remains active in stock firmware 2.2.4.

Its runtime cadence changed from the approximately 60-second behavior observed in 2.1.3 to approximately 180 seconds.

---

# 6. Cross-Version Runtime Comparison

The original capture gives the following direct comparison:

| Firmware | Observed periodic mDNS behavior | Approximate cadence |
|---|---|---:|
| 2.1.0 | no comparable periodic burst observed | none observed in ~13 min |
| 2.1.3 | recurring probe/announcement bursts | ~60 s |
| 2.2.4 | recurring probe/announcement bursts | ~180 s |

Static comparison adds the intermediate firmware 2.1.8.

The resulting firmware history is:

```text
2.1.0
    |
    +-- mDNS responder present
    |
    +-- no comparable recurring maintenance
        burst observed in runtime test


2.1.3
    |
    +-- recurring mDNS restart
    |
    +-- ~60 s


2.1.8
    |
    +-- later modulo-3 scheduling already present


2.2.4
    |
    +-- recurring mDNS restart
    |
    +-- ~180 s confirmed at runtime
```

The approximately 180-second 2.1.8 behavior has not been independently verified with the same dedicated packet-capture experiment.

The important chronology is nevertheless clear:

> Periodic mDNS activity predates firmware 2.2.4.

It was modified over time rather than introduced together with the 2.2.4 Beacon Recovery mechanism.

---

# 7. Patch B

Patch B was created specifically to isolate the recurring mDNS workload.

It suppresses the targeted connected-maintenance restart while leaving the rest of the mDNS implementation and stock Beacon Recovery intact.

Its purpose is therefore:

```text
periodic mDNS variable
        |
        v
remove targeted recurring restart

while

Beacon Recovery
        |
        v
remain stock
```

Patch B does not intentionally modify:

- Beacon Recovery
- `real_beacon_skip`
- `desired_beacon_skip`
- RSSI thresholds
- AP selection
- WLAN power-management policy
- thermostat operation
- valve control

The exact native patch and static qualification are documented in:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

---

# 8. Patch-B Packet-Capture Test

Device:

```text
.77
```

Relevant configuration during this later experiment:

```text
host firmware:
    2.2.4 + Patch B

periodic mDNS restart:
    suppressed

Beacon Recovery:
    stock
```

This is a later configuration than the `.77` 2.1.3 experiment described above.

A TShark capture filtered for UDP port 5353 traffic from the Patch-B device produced:

```text
0 packets captured
```

during an observation window of at least approximately:

```text
10 minutes
```

A stock 2.2.4 device operating at the measured approximately 180-second cadence would normally be expected to produce several targeted periodic bursts during a window of this length.

The result therefore confirms the intended runtime effect:

> The recurring mDNS sequence targeted by Patch B was absent during the monitored Patch-B runtime.

This does not mean that all mDNS functionality has been removed.

Other event-driven responder paths remain present by design.

---

# 9. Connectivity with Patch B

Normal device operation remained available while the targeted periodic restart was suppressed.

The experiment did not identify a loss of ordinary:

```text
Wi-Fi connectivity

local IP access

TRV operation
```

caused by Patch B.

This is useful because it demonstrates that continuously restarting the mDNS probing sequence is not required for ordinary operation during the tested runtime.

The result should not be generalized into a claim that the periodic restart has no purpose under every possible network condition.

Possible edge cases include:

- hostname changes
- reconnects
- AP restarts
- network topology changes
- long uptime
- unusual multicast conditions

Patch B was designed as an isolation experiment rather than as a complete qualification of all mDNS service-discovery behavior.

---

# 10. Long-Term Patch-B Test

The `.77` Patch-B device was subsequently left running for a long-term discharge experiment.

Configuration:

```text
2.2.4 + Patch B

periodic connected-maintenance mDNS restart:
    suppressed

Beacon Recovery:
    stock
```

At the end of the observed discharge run, the device reported approximately:

```text
battery:              0 %
voltage:              3.116 V
uptime:               ~9.23 days
reconnect_counter:    30
desired_beacon_skip:  15
real_beacon_skip:     1
beacon_err_counter:   12908
```

The Beacon Recovery rate over the complete uptime is approximately:

```text
12908 / (9.23 * 24)

≈ 58.3 recoveries/hour
```

or approximately:

```text
one Recovery every 61.8 seconds
```

on average.

The periodic mDNS restart had been suppressed throughout this experimental configuration.

The long-term result therefore extends the earlier short packet-capture observation:

```text
periodic mDNS restart
        |
        v
suppressed


Beacon Recovery
        |
        v
continues for days
        |
        v
~12908 events
```

This is much stronger than a short observation showing only a few Recoveries after Patch B.

---

# 11. What the `.77` Long-Term Test Establishes

The experiment provides a clear mechanism-separation result.

The following hypothesis is incompatible with the observed runtime behavior:

```text
periodic mDNS restart is required
for recurring Beacon Recovery
```

because recurring Beacon Recovery continued at high frequency after the targeted periodic restart was removed.

The result supports:

> The periodic connected-maintenance mDNS restart is not required for the recurring Beacon Recovery behavior observed on the tested device.

The experiment does **not** establish:

```text
Beacon Recovery caused the complete battery discharge
```

and it does not establish:

```text
mDNS has zero energy cost
```

The device still contained many other possible energy consumers and power-management mechanisms.

No electrical current was measured.

The final battery state therefore demonstrates that Patch B did not prevent poor long-term battery behavior on this device, but it does not identify which remaining mechanism caused that behavior.

---

# 12. Relationship to Beacon Recovery

The mDNS experiment was originally motivated in part by the possibility that the recurring restart could disturb WLAN timing sufficiently to trigger the 2.2.4 Beacon Recovery path.

A simple version of that hypothesis was:

```text
periodic mDNS restart
        |
        v
WLAN activity
        |
        v
beacon timing disturbance
        |
        v
real_beacon_skip anomaly
        |
        v
Beacon Recovery
```

Patch B tests whether the periodic restart is a necessary part of this chain.

Runtime behavior shows:

```text
periodic mDNS restart
        |
        v
removed


Beacon Recovery
        |
        v
still occurs
```

The targeted periodic mDNS activity therefore cannot be treated as a required trigger for recurring Beacon Recovery.

This does not prove that an individual mDNS transmission can never affect beacon timing.

It establishes the narrower and more useful result that the recurring Recovery behavior does not depend on the periodic restart.

---

# 13. Later Beacon Recovery Findings

Subsequent reverse engineering identified three host-side validity problems in the stock Beacon Recovery control chain:

```text
C1a
signed control-value validity

C1b
measurement-window validity

C2
post-Recovery control-evidence freshness
```

C2 is particularly relevant to the earlier mDNS hypothesis.

After a qualifying Recovery, stock firmware can clear the beacon-counter baseline while retaining the previously calculated control value.

The next measurement can therefore establish a new baseline without producing fresh control evidence, while the old value remains available to the Recovery decision.

Conceptually:

```text
fresh qualifying value
        |
        v
Recovery
        |
        v
measurement baseline cleared
        |
        v
old control value retained
        |
        v
next sample establishes baseline
        |
        v
old value evaluated again
        |
        v
Recovery can repeat
```

A new external disturbance is therefore not required every minute to explain the stock self-sustaining Recovery behavior.

This static result and the Patch-B runtime result agree:

> Periodic mDNS is not needed to explain the recurring stock Recovery loop.

The cause of the initial fresh qualifying measurement remains a separate question.

---

# 14. Patch C-C Runtime Context

Patch C-C was developed to correct the identified Beacon Recovery validity problems while retaining Recovery for fresh qualifying evidence.

Unlike the earlier Patch A, C-C does not simply bypass the Recovery action.

C-C targets:

```text
C1a
C1b
C2
```

while leaving the periodic mDNS mechanism unchanged.

C-C has now been tested on physical TRV hardware.

Relevant configurations include:

```text
.88
    2.2.4 + C-C
    WF200 3.16.1


.237
    2.2.4 + C-C
    WF200 3.18.0


.234
    2.2.4 + A1 + C-C
    WF200 3.18.0
```

These tests show an important distinction.

C-C removes the invalid/stale recurrence mechanism targeted by the patch, but fresh qualifying Recovery events can still occur.

For example, the `.234` A1+C-C+WF200 3.18.0 experiment showed approximately:

```text
27–28 fresh Recovery events/hour
```

during part of the long-term test.

A separate `.237` C-C+WF200 3.18.0 reference showed a similar order of magnitude.

The current runtime model therefore distinguishes:

```text
stock recurring Recovery
        |
        +-- invalid/stale recurrence
        |       |
        |       +-- corrected by C-C
        |
        +-- fresh qualifying measurements
                |
                +-- still observed
```

The remaining fresh Recovery behavior is not explained by the periodic mDNS restart.

---

# 15. D3 Runtime Context

A separate observer experiment monitored the known WF200 `PS_MODE_ERROR` indication while retaining stock Beacon Recovery.

On the `.11` D3 observer device, one long-term state was approximately:

```text
uptime:       63.9 h
beacon_err:   3835
D3_total:     0
```

Thousands of Beacon Recovery events therefore occurred without a recorded D3 `PS_MODE_ERROR`.

This does not establish that the WF200 radio was always physically sleeping correctly.

It does show that the known D3 indication is not required for the host Recovery mechanism.

Together, the runtime isolation results now show:

```text
periodic mDNS restart
        not required


known D3 PS_MODE_ERROR
        not required


fresh Beacon Recovery
        still observed
```

The upstream cause of the remaining fresh qualifying estimator values therefore remains under investigation.

---

# 16. Runtime Comparison Summary

The main runtime observations can be summarized as:

| Configuration | Periodic mDNS | Approximate mDNS cadence | Beacon Recovery |
|---|---|---:|---|
| 2.1.0 stock | not observed in original capture | none observed in ~13 min | 2.2.4 mechanism absent |
| 2.1.3 stock | observed | ~60 s | 2.2.4 mechanism absent |
| 2.2.4 stock | observed | ~180 s | stock Recovery present |
| 2.2.4 + Patch B | targeted cycle not observed | suppressed | stock Recovery continues |
| 2.2.4 + C-C | unchanged | stock mDNS behavior | stale/invalid Recovery corrected; fresh events remain |
| 2.2.4 + A1 + C-C + WF200 3.18 | unchanged | stock mDNS behavior | fresh events remain |

The Patch-B long-term test adds:

```text
periodic mDNS suppressed

Beacon Recovery:
~58.3/hour average

runtime:
~9.23 days

final battery:
0 %, 3.116 V
```

These values describe observed firmware and network behavior.

They are not an electrical-energy ranking.

---

# 17. Energy Interpretation

The packet captures establish that the periodic restart creates real recurring work.

A normal successful stock 2.2.4 sequence can include approximately:

```text
3 mDNS probes
+
1 announcement
```

every approximately:

```text
180 seconds
```

That necessarily involves some combination of:

- host processing
- packet construction
- network-stack processing
- WLAN transmission
- WLAN receive activity
- radio wake or active time

compared with a state in which the periodic sequence does not occur.

The additional energy cost is therefore not expected to be exactly zero.

However, packet capture cannot determine its magnitude.

---

# 18. Why Packet Count Is Not Battery Consumption

A calculation such as:

```text
4 packets / 180 s
```

cannot be converted directly into:

```text
mAh/day
```

without measuring or otherwise establishing the corresponding physical power states.

The incremental energy depends on factors including:

- whether the host was already awake
- whether the WF200 was already active
- TX duration
- receive windows
- retransmissions
- RSSI and RF conditions
- WLAN power-save state
- interaction with other scheduled activity
- host sleep admission after the operation

A packet transmitted during an already active interval may cost substantially less incremental energy than a packet sequence that creates an otherwise unnecessary wake period.

The packet captures therefore measure recurring workload and network behavior, not electrical power.

---

# 19. Battery Result of Patch B

The `.77` long-term result is useful because it rules out an overly simple battery hypothesis.

Patch B removed the targeted periodic mDNS restart.

Nevertheless:

```text
battery reached 0 %

voltage reached 3.116 V

Beacon Recovery remained ~58/hour
```

over an uptime of approximately 9.23 days.

The correct interpretation is:

> Removing the periodic mDNS restart alone did not prevent poor battery endurance on the tested device.

It would be incorrect to conclude:

> Therefore mDNS consumes no relevant energy.

The experiment did not contain a simultaneous otherwise-identical electrical A/B pair, and no current measurement was performed.

Likewise, it would be incorrect to conclude:

> The remaining Beacon Recovery events caused the entire discharge.

That causal step has not been demonstrated.

---

# 20. Relationship to the General Battery-Drain Investigation

The current investigation contains several distinct mechanisms with possible energy relevance:

```text
TRV workload
    |
    +-- thermostat / valve operation
    |
    +-- WLAN traffic
    |
    +-- periodic mDNS
    |
    +-- Beacon Recovery
    |
    +-- host power-management ownership
    |
    +-- host sleep blockers
    |
    +-- WF200 power-save behavior
    |
    +-- RF / AP conditions
```

The periodic mDNS restart is now one of the better isolated variables.

Its status is:

```text
real firmware behavior:
    yes

recurring network workload:
    yes

runtime cadence known:
    yes

can be selectively suppressed:
    yes

required for recurring Beacon Recovery:
    no

required for poor battery behavior:
    no evidence

quantitative energy cost:
    not measured

complete battery-drain root cause:
    not established
```

This is a more useful result than simply classifying mDNS as either "the bug" or "irrelevant".

---

# 21. Device-History Note

The `.77` identifier appears in two different parts of this document because the same physical device was reused.

Original cross-version capture:

```text
.77
firmware 2.1.3
```

Later Patch-B experiment:

```text
.77
firmware 2.2.4 + Patch B
```

The earlier dataset establishes the approximately 60-second behavior of firmware 2.1.3.

The later dataset establishes the effect of suppressing the periodic restart in firmware 2.2.4.

The datasets must not be mixed.

The same principle applies to other devices that were reflashed during the investigation.

Firmware identity should always be associated with the date and experimental configuration rather than inferred from the device suffix alone.

---

# 22. Remaining Questions

The basic runtime behavior of the periodic mDNS mechanism is now well characterized.

The remaining useful questions are narrower:

1. What is the electrical energy cost of one periodic restart sequence?

2. How much additional host and WF200 awake time does one restart create?

3. Does the energy cost vary substantially with RSSI, retransmissions or AP behavior?

4. Does suppressing the periodic restart measurably improve battery endurance in a controlled otherwise-identical A/B experiment?

5. How often are the retained event-driven mDNS restart paths exercised during normal long-term operation?

6. Does suppressing the periodic restart have any long-term effect on mDNS discoverability after reconnects, AP restarts or network changes?

7. Does firmware 2.1.8 produce the expected approximately 180-second cadence in a dedicated packet capture?

8. Can periodic mDNS influence the probability of an **initial fresh** Beacon Recovery event even though it is clearly not required for the recurring Recovery behavior?

The last question is substantially narrower than the original hypothesis.

A positive answer would not change the Patch-B result that periodic mDNS is unnecessary for the persistent Recovery loop.

---

# 23. Current Conclusion

Runtime packet capture confirms that periodic mDNS behavior changed across Shelly TRV Gen1 firmware generations.

The observed comparison is:

```text
2.1.0
    no comparable periodic burst observed
    during ~13-minute capture


2.1.3
    recurring mDNS burst
    ~60 s


2.2.4 stock
    recurring mDNS burst
    ~180 s


2.2.4 + Patch B
    targeted recurring burst absent
    during monitored capture
```

The Patch-B experiment then continued as a long-term test.

At approximately 9.23 days uptime, the device had accumulated:

```text
12908 Beacon Recovery events
```

corresponding to approximately:

```text
58.3 recoveries/hour
```

while the targeted periodic mDNS restart remained suppressed by the firmware modification.

The device ultimately reported:

```text
0 %
3.116 V
```

This provides a strong runtime separation between the two mechanisms:

```text
periodic mDNS restart
        |
        v
not required


for


recurring Beacon Recovery
```

and also shows that suppressing the periodic restart alone did not prevent poor battery endurance on this particular device.

Later C-C hardware testing further separates the problem.

Correcting the known stale/signed/invalid-window Recovery behavior removes the corresponding host-side defects, but fresh qualifying Recovery events remain observable.

The current interpretation is therefore:

> The periodic mDNS restart is a confirmed recurring network workload whose cadence changed from approximately 60 seconds in firmware 2.1.3 to approximately 180 seconds in firmware 2.2.4. Patch B successfully suppresses the targeted recurring sequence. Long-term testing shows that recurring Beacon Recovery continues without it, so periodic mDNS is not required for the Recovery loop. The periodic workload may still have an energy cost, but its quantitative contribution to Shelly TRV Gen1 battery drain has not been measured and it is not established as the root cause.

---

# Related Documents

Static mDNS analysis:

[`../reverse-engineering/mdns-periodic-restart.md`](../reverse-engineering/mdns-periodic-restart.md)

Firmware chronology:

[`../reverse-engineering/firmware-comparison.md`](../reverse-engineering/firmware-comparison.md)

Beacon-counter measurement model:

[`../reverse-engineering/beacon-rx-counter.md`](../reverse-engineering/beacon-rx-counter.md)

`real_beacon_skip` calculation:

[`../reverse-engineering/real-beacon-skip.md`](../reverse-engineering/real-beacon-skip.md)

Beacon Recovery:

[`../reverse-engineering/recovery-mechanism.md`](../reverse-engineering/recovery-mechanism.md)

Power management and host sleep:

[`../reverse-engineering/power-management-and-sleep.md`](../reverse-engineering/power-management-and-sleep.md)

Battery testing:

[`battery-testing.md`](battery-testing.md)

Experimental patches:

[`../patch/README.md`](../patch/README.md)

---

# Methodology

The runtime findings in this document come from personally owned Shelly TRV Gen1 devices operated on a local WLAN.

The mDNS comparison used passive packet capture to observe UDP port 5353 traffic without intentionally generating service-discovery requests during the primary observation windows.

The investigation combines:

- packet capture
- firmware identity
- runtime `/status` data
- runtime `/stats` data where available
- Beacon Recovery counters
- long-term battery-voltage logging
- static firmware analysis
- targeted experimental firmware modifications

Packet capture establishes network behavior.

Firmware counters establish software behavior.

Battery voltage provides a useful long-term device metric.

None of these individually constitutes a direct electrical current measurement.

Finite packet-capture windows are described explicitly and should not be generalized beyond what they demonstrate.

Firmware identity is determined from the actual experimental configuration at the time of each observation rather than permanently inferred from a device IP address.

---

# Disclaimer

This is an independent research project.

It is not affiliated with, endorsed by, or supported by Shelly Group or Silicon Labs.

All product names and trademarks belong to their respective owners.

The findings describe observed and reverse-engineered behavior of the examined firmware versions and experimental configurations.

Statements about battery-drain causality are intentionally limited to what the available static and runtime evidence supports.
```