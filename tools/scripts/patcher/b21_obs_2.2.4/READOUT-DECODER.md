# Passive readout and saved-file decoding

`obs_export(oldlen, native_fp, incoming_primask)` is called only by the explicit
status-query suffix wrapper. Its integration contract is the existing qualified
token-7, capacity-4096 native status frame: buffer at `fp+24`, capacity at
`fp+20`, token at `fp+28`, and the same buffer pointer again at `fp+44`.

The wrapper enters masked and saves/restores native registers and APSR. The C
function accepts only incoming PRIMASK zero; a caller originally masked returns
its original length unchanged and restores mask one. Successful readout checks
RAM buffer bounds, trailing NUL/closing JSON brace, observer identity/version/size,
and capacity for the complete suffix **before any output write**. It copies all
128 observer words under that bounded mask, restores incoming PRIMASK, then
formats only the private snapshot. There is no callback, allocation, radio query,
observer-state modification, or native state change except the explicit query's
existing output buffer. No readout occurs unless the endpoint is queried.

The suffix is a locally linked constant, with no hardcoded string address:

```json
"pm52_cmd66":{"v":1,"w":"1024 hexadecimal characters"}
```

Each group of eight characters is one unsigned 32-bit word in increasing RAM
word-address order, printed most-significant hexadecimal digit first. This is
not a byte dump; BSSID words are decoded little-endian to bytes. No data is
resampled after snapshotting. The coherent copy prevents mixing concurrent event
records in one response. Live target tests must independently verify this code
and the suffix wrapper before qualification.

Target compile inspection with the retained clang Cortex-M3 Thumb freestanding
`-Os` configuration gives 24 saved bytes plus 512 private snapshot bytes = 536
bytes. The integrating 32-byte wrapper brings the additional readout path to 568
bytes, below the retained 600-byte envelope. It contains no calls or VFP
instructions. This is a local emitted-frame result, not a replacement for the
parent's complete stack/capacity and emitted-target execution qualification.

Save the complete JSON response manually, then run offline:

```sh
python3 tools/scripts/patcher/pm52_cmd66_observer_2.2.4/decode.py saved-status.json
```

The decoder opens only the named saved file. It has no network library or device
access. Output includes raw words and records in chronological ring order, so a
classification can always be independently reviewed. Preserve the original JSON,
not just the decoded summary.

CASE A requires frozen, clean, non-overrun chronology; a fresh successful cmd66
sample in the currently connected epoch; exact full-width q=1 arithmetic; the
actual expected tuple; matching successful native result; matching accepted A1
first commit and current generation/version/confirmed tuple; and no outstanding
issue. Both the PM52 native result and accepted A1 first commit must precede
the **cmd66 request issue**, not merely its later result/arithmetic. Header word
23 is `query_issue_seq`, recorded only at that existing request. The final fault
record instead matches header word 4 (frozen observer sequence). A successful
PM52 operation interleaved after cmd66 issue cannot establish which policy
preceded the radio snapshot and returns CASE C. The separate physical
`completed_generation` field is **not** required
or interpreted as proof of radio sleep. CASE B requires an explicit matching
native failure or rejected A1 completion in the complete retained chronology.
Missing events, changed epoch, pending/superseded state, unknown flags, or an
unexpected tuple return CASE C, never an inferred success. Rejection is not
automatically described as stale, and a native error is not automatically called
a timeout without native evidence.

The first commit's result is an observed acceptance value, not a claim about
physical effective listen interval. Neither CASE A nor the record decoder proves
the battery-drain root cause. A query itself causes normal status/network work;
minimize explicit queries and retain the first frozen record before reboot.
