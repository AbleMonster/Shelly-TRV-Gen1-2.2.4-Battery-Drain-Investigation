# mDNS Runtime Comparison

## Purpose

This test validates the periodic mDNS behavior previously identified during
static firmware analysis of the Shelly TRV Gen1 firmware.

The primary questions were:

1. Is the periodic mDNS restart observed in firmware 2.1.3 at runtime?
2. Is the same behavior present in stock firmware 2.2.4?
3. Is comparable periodic mDNS traffic observable in firmware 2.1.0?

This test measures network behavior only.

It does **not** measure electrical current or battery energy directly.

---

## Test Setup

Three Shelly TRV Gen1 devices were observed simultaneously on the same local
network.

| Device | Firmware | Role |
|---|---|---|
| 192.168.178.11 | 2.1.0 | Old firmware reference |
| 192.168.178.77 | 2.1.3 | First firmware with statically identified periodic mDNS restart |
| 192.168.178.229 | 2.2.4 stock | Current stock firmware comparison |

Packet capture was performed using TShark on macOS.

Capture filter:

```text
udp port 5353 and (host 192.168.178.11 or host 192.168.178.77 or host 192.168.178.229)
```

Capture duration was approximately 13 minutes.

No active requests were intentionally sent to the TRVs during the observation.

---

## Firmware 2.1.0

Device:

```text
192.168.178.11
```

No mDNS packets from this device were observed during the approximately
13-minute capture.

This agrees with the previous static analysis, which found the mDNS responder
itself in 2.1.0 but did not find the later connected-maintenance caller that
periodically restarts probing.

This observation does not prove that firmware 2.1.0 never emits mDNS traffic.

It demonstrates only that no comparable periodic mDNS burst was observed during
this test window.

---

## Firmware 2.1.3

Device:

```text
192.168.178.77
```

Firmware 2.1.3 repeatedly produced an mDNS burst approximately once per minute.

A typical burst consisted of:

1. mDNS probe
2. mDNS probe
3. mDNS probe
4. mDNS announcement

Example:

```text
59.699 s   probe
60.006 s   probe
60.211 s   probe
60.520 s   announcement
```

Further burst starts occurred at approximately:

```text
0 s
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

The observed interval is therefore approximately:

```text
60 seconds
```

This closely matches the behavior predicted by static firmware analysis:

```text
connected maintenance
        ↓
mdns_resp_restart()
        ↓
probing state reset
        ↓
mDNS probes
        ↓
announcement
```

The runtime capture therefore confirms that the statically identified periodic
mDNS restart is active during normal connected operation in firmware 2.1.3.

---

## Firmware 2.2.4 Stock

Device:

```text
192.168.178.229
```

Stock firmware 2.2.4 also produced the same characteristic mDNS
probe/announcement sequence.

Observed burst starts:

```text
117.555 s
297.779 s
477.492 s
657.413 s
```

Intervals:

```text
180.225 s
179.713 s
179.921 s
```

The runtime interval is therefore approximately:

```text
180 seconds
```

A typical burst again consisted of approximately three probes followed by an
announcement.

This confirms that the periodic mDNS restart behavior still exists in stock
firmware 2.2.4.

However, its observed runtime period differs from firmware 2.1.3:

```text
2.1.3   ≈ 60 seconds
2.2.4   ≈ 180 seconds
```

The reason for this period change has not yet been established.

---

## Runtime Comparison

| Firmware | Periodic mDNS burst observed | Approximate interval |
|---|---:|---:|
| 2.1.0 | No | Not observed |
| 2.1.3 | Yes | ~60 s |
| 2.2.4 stock | Yes | ~180 s |

The packet sequence observed in 2.1.3 and 2.2.4 is consistent with the mDNS
probe/re-announcement behavior identified during reverse engineering.

---

## Energy Interpretation

These measurements establish additional network activity.

They do **not** establish the electrical energy cost of that activity.

Compared with a state in which the periodic restart does not occur, the
additional mDNS processing and packet transmission necessarily requires some
additional device activity.

However, this experiment cannot determine:

- the additional current consumed per burst,
- the additional battery capacity consumed per day,
- the resulting reduction in battery lifetime,
- or the fraction of the historical battery-drain problem attributable to
  mDNS.

Therefore the correct conclusion is:

> Periodic mDNS restart activity is a confirmed additional recurring workload,
> but its quantitative contribution to battery drain remains unknown.

---

## Relationship to the 2.2.4 Beacon Recovery

Firmware 2.2.4 contains another independently identified recurring mechanism:
the beacon-skip recovery path.

The current evidence therefore supports the presence of multiple additional
activity sources in later firmware.

For stock 2.2.4 these include at least:

```text
periodic mDNS restart
+
beacon-skip recovery under qualifying conditions
+
normal TRV workload
```

A possible interaction between the mDNS restart and beacon-skip recovery has
not yet been established.

The mechanisms must therefore remain separate hypotheses until tested
independently.

---

## Next Experiment

The next experiment will use firmware 2.2.4 with only the periodic mDNS restart
modified.

The beacon-skip recovery mechanism will remain unchanged.

This provides an isolated test:

```text
Stock 2.2.4
    ↓
remove periodic mDNS restart only
    ↓
observe mDNS traffic
    ↓
observe beacon recovery behavior
```

Expected validation:

### mDNS

The periodic ~180-second probe/announcement bursts should disappear.

### Connectivity

Normal device connectivity must remain functional, including:

- local IP access,
- web interface,
- normal network operation,
- Home Assistant / controller communication where configured.

The mDNS responder itself should not be disabled.

Only the periodic restart mechanism should be modified.

### Beacon recovery

The existing beacon-recovery code must remain unmodified.

If beacon recoveries continue unchanged after the mDNS modification, this
supports the interpretation that the mechanisms are independent.

If beacon recoveries disappear or change substantially, an interaction between
the two mechanisms must be investigated.

---

## Status

Runtime behavior confirmed:

```text
2.1.0        no periodic mDNS burst observed
2.1.3        periodic mDNS burst ≈ 60 s
2.2.4 stock  periodic mDNS burst ≈ 180 s
```

Energy impact:

```text
additional activity confirmed
quantitative energy cost unknown
battery-life contribution unknown
```

Next step:

```text
2.2.4 experimental mDNS-only patch
```
