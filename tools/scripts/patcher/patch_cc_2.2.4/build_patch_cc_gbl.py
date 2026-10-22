#!/usr/bin/env python3
"""Build only the qualified Shelly TRV 2.2.4 C-C experimental GBL.

Exact report bytes, no assembly. Refuses stock mismatch and existing output.
Does not flash, invoke Ghidra, or modify original firmware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "original/2.2.4/SHTRV-01_build_2.2.4.gbl"
DESIGN = ROOT / "docs/local/rea_report/patch-c-design-2026-10-14.md"
QUALIFICATION = ROOT / "docs/local/rea_report/patch-c-prebuild-qualification-2026-10-14.md"
SOURCE_SHA = "5c4a0b222a313350952f6b1200a855833402f168bd286090c23bd4d018ab918f"
APP_SHA = "4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c"
PROGRAM = 0xFD0303FD
END = 0xFC0404FC
# Verbatim qualified C-C manifest: (application address, preimage, replacement).
SITES = ((123128, '124bdb89', 'e2f0c8f9'),
 (123132, '002b40f09680', '0bb100208fe0'),
 (123154, '234b1b68', 'e2f0c1f9'),
 (123318, '214b93f90030', '3ad0204b1b78'),
 (123330, '93f90030', '93f80030'),
 (123338, '07f11403', 'e2f06ff9'),
 (123432, '044b0022', '08b1044b'),
 (123438, '00bf7437', 'e2f043f9'),
 (123656, '374b1a68354b1b68', 'e2f062f800bf00bf'),
 (127564, 'fb791373', 'e1f0d8f8'),
 (127956, '2837bd46', 'e1f076f8'),
 (360388, '83f82222', 'a8f02cfa'),
 (360736, '83f82222', 'a8f07ef9'),
 (463294, '094b00221a60084b00221a60084b00221a60', '8ff04bf900bf00bf00bf00bf00bf00bf00bf'),
 (469656, '114a7b68', '8df0d2fc'))

# (helper address, exact length, code/literal bytes); never reassemble.
HELPERS = ((1049552, 48, '13b5084b1a68084b1b68934206d33c20b2fbf0f1013141438b4202d903480021016013bd841b0020001a03209cdd0120'),
 (1049600, 32, '33b4eff3108072b6044900240c60fb79137380f3108833bc704700bf9cdd0120'),
 (1049632, 32, '33b4eff3108072b6044900240c6083f8222280f3108833bc704700bf9cdd0120'),
 (1049664, 24, '03b403480021016003bc024a7b6870479cdd0120081a0320'),
 (1049688,
  52,
  '03b4eff3108072b6064900220a60064b1a60064b1a60064b1a6080f3108803bc704700bf9cdd0120081a0320041a0320001a0320'),
 (1049740, 12, '0025014bdb897047bc1a0020'),
 (1049752, 20, 'eff3108472b60125014b1b68704700bf9cdd0120'),
 (1049772, 12, '84f31088002507f114037047'),
 (1049784, 12, '002d01d084f3108874377047'),
 (1049796, 32, '33b4eff3108072b6044900240c6080f3108833bc2837bd46704700bf9cdd0120'))

def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse(data):
    """Parse bounded tag records, rejecting truncation, trailing data and bad END."""
    records = []
    offset = 0
    while offset < len(data):
        require(offset + 8 <= len(data), "Truncated tag header")
        kind, size = struct.unpack_from("<II", data, offset)
        stop = offset + 8 + size
        require(stop <= len(data), "Tag payload extends past EOF")
        payload = data[offset + 8:stop]
        require(kind != PROGRAM or size >= 4, "Short PROGRAM payload")
        records.append((offset, kind, payload))
        if kind == END:
            require(size == 4 and stop == len(data), "END must be final, length four")
        offset = stop
    require(records and records[-1][1] == END, "Missing END tag")
    require(sum(t == END for _, t, _ in records) == 1, "Duplicate END")
    require(zlib.crc32(data[:-4]) == int.from_bytes(data[-4:], "little"), "Bad CRC32")
    return records


def report_manifest():
    """Cross-check hardcoded bytes with both reviewed reports before building."""
    design, qualification = DESIGN.read_text(), QUALIFICATION.read_text()
    section = design.split("### C-C\n", 1)[1].split("### C-D\n", 1)[0]
    sites = []
    for line in section.splitlines():
        c = [v.strip().strip("`") for v in line.strip().strip("|").split("|")]
        if len(c) == 6 and c[0].startswith("0x"):
            sites.append((int(c[0], 16), c[2], c[3]))
    section = design.split("### C-C complete appended bytes\n", 1)[1].split("### C-D appended bytes\n", 1)[0]
    helpers = []
    for line in section.splitlines():
        c = [v.strip().strip("`") for v in line.strip().strip("|").split("|")]
        if len(c) == 4 and c[0].startswith("0x"):
            helpers.append((int(c[0], 16), int(c[1]), c[3]))
    require(tuple(sites) == SITES and tuple(helpers) == HELPERS, "Design/embedded manifest discrepancy; STOP")
    for address, before, after in SITES:
        rows = [l for l in qualification.splitlines() if l.startswith(f"|`{hex(address)}`|")]
        require(len(rows) == 1 and f"`{before}`" in rows[0] and f"`{after}`" in rows[0], "Qualification site discrepancy; STOP")
    for address, size, code in HELPERS:
        require(f"|`0x{address:X}`|{size}|`{code}`|" in qualification, "Qualification helper discrepancy; STOP")


def manifest_bytes():
    require(len(SITES) == 15, "Expected 15 replacement ranges")
    footprint = changed = 0
    last = 0
    for address, before, after in SITES:
        old, new = bytes.fromhex(before), bytes.fromhex(after)
        require(len(old) == len(new) and address >= last, "Overlapping or size-changing patch")
        require(address + len(old) <= 0x1003CC, "Patch outside original application")
        footprint += len(old)
        changed += sum(a != b for a, b in zip(old, new))
        last = address + len(old)
    require((footprint, changed) == (82, 77), "Incorrect footprint/unequal-byte count")
    cursor = 0x1003D0
    fragments = []
    for address, size, code in HELPERS:
        raw = bytes.fromhex(code)
        require(address == cursor and len(raw) == size and address % 2 == 0, "Invalid helper address/length/contiguity")
        cursor += size
        fragments.append(raw)
    appended = b"".join(fragments)
    require(len(HELPERS) == 10 and len(appended) == 276 and cursor == 0x1004E4, "Incorrect helper total/end")
    return appended


def stock_records(source):
    # SHA check precedes parsing or any patching.
    require(digest(source) == SOURCE_SHA, "Original GBL SHA256 mismatch; STOP")
    records = parse(source)
    layout = [(o, t, len(p)) for o, t, p in records]
    require(len(source) == 0x10E1D0 and layout == [
        (0, 0x03A617EB, 8), (0x10, 0xF40A0AF4, 0x1C),
        (0x34, 0xF50909F5, 0x650C), (0x6548, PROGRAM, 0x1003D0),
        (0x106920, PROGRAM, 0x789C), (0x10E1C4, END, 4)
    ], "Unexpected stock container layout; STOP")
    targets = [i for i, (_, t, p) in enumerate(records) if t == PROGRAM and int.from_bytes(p[:4], "little") == 0]
    require(len(targets) == 1, "Expected exactly one address-zero PROGRAM")
    index = targets[0]
    app = records[index][2][4:]
    require(len(app) == 0x1003CC and digest(app) == APP_SHA, "Stock application identity mismatch")
    second = records[index + 1][2]
    require(int.from_bytes(second[:4], "little") == 0x130A98 and len(second[4:]) == 0x7898, "Unexpected second PROGRAM")
    return records, index, app


def construct(source):
    records, index, app = stock_records(source)
    report_manifest()
    helpers = manifest_bytes()
    # Verify every preimage BEFORE performing even in-memory replacement.
    for address, before, _ in SITES:
        require(app[address:address + len(bytes.fromhex(before))].hex() == before, f"Preimage mismatch at {address:#x}; STOP")
    modified = bytearray(app)
    for address, before, after in SITES:
        modified[address:address + len(bytes.fromhex(before))] = bytes.fromhex(after)
    modified += bytes.fromhex("ffffffff") + helpers
    require(len(modified) == 0x1004E4 and len(modified) - len(app) == 0x118, "Incorrect application growth")
    parts = []
    for i, (_, kind, payload) in enumerate(records):
        if i == index:
            payload = payload[:4] + modified
        parts.append(struct.pack("<II", kind, len(payload)) + payload)
    candidate = b"".join(parts)
    candidate = candidate[:-4] + struct.pack("<I", zlib.crc32(candidate[:-4]))
    verify(source, candidate)
    return candidate


def verify(source, candidate):
    old, index, stock_app = stock_records(source)
    new = parse(candidate)  # Fresh complete parse, not cached offsets.
    require(len(new) == len(old), "Tag count changed")
    first, second, end = new[index], new[index + 1], new[-1]
    app = first[2][4:]
    checks = {}
    def check(name, condition):
        require(condition, name)
        checks[name] = "PASS"
    check("unique_address_zero_program", sum(t == PROGRAM and int.from_bytes(p[:4], 'little') == 0 for _, t, p in new) == 1)
    check("first_application_length", len(app) == 0x1004E4)
    check("first_payload_length", len(first[2]) == 0x1004E8)
    check("first_flash_address", first[2][:4] == bytes(4))
    check("second_flash_address", int.from_bytes(second[2][:4], 'little') == 0x130A98)
    check("second_data_length", len(second[2][4:]) == 0x7898)
    check("second_payload_identical", second[1:] == old[index + 1][1:])
    check("second_tag_movement", second[0] == 0x106A38 and second[0] - old[index + 1][0] == 0x118)
    check("end_tag_movement", end[0] == 0x10E2DC and end[0] - old[-1][0] == 0x118)
    check("file_growth", len(candidate) == 0x10E2E8 and len(candidate) - len(source) == 0x118)
    expected_differences = set()
    for address, before, after in SITES:
        raw = bytes.fromhex(after)
        check(f"replacement_{address:06x}", app[address:address + len(raw)] == raw)
        expected_differences.update(address + j for j, (a, b) in enumerate(zip(bytes.fromhex(before), raw)) if a != b)
    actual = {i for i, (a, b) in enumerate(zip(stock_app, app)) if a != b}
    check("only_77_qualified_existing_bytes_changed", actual == expected_differences and len(actual) == 77)
    check("alignment", app[0x1003CC:0x1003D0] == b'\xff' * 4)
    check("all_helper_bytes", app[0x1003D0:] == manifest_bytes())
    for address, size, code in HELPERS:
        check(f"helper_{address:06x}", app[address:address + size].hex() == code)
    check("unrelated_tags_and_payloads_identical", all(new[i][1:] == row[1:] for i, row in enumerate(old) if i not in (index, len(old) - 1)))
    check("tag_order_preserved", [r[1] for r in old] == [r[1] for r in new])
    check("header_before_program_identical", candidate[:old[index][0]] == source[:old[index][0]])
    check("crc32", zlib.crc32(candidate[:-4]) == int.from_bytes(candidate[-4:], 'little') and zlib.crc32(candidate) == 0x2144DF1C)
    return {
        "input_sha256": digest(source), "output_sha256": digest(candidate),
        "output_crc32": f"0x{int.from_bytes(candidate[-4:], 'little'):08X}",
        "application_length": ["0x1003CC", "0x1004E4"],
        "first_program_payload_length": ["0x1003D0", "0x1004E8"],
        "second_program_tag_offset": ["0x106920", hex(second[0])],
        "end_tag_offset": ["0x10E1C4", hex(end[0])],
        "total_file_length": [hex(len(source)), hex(len(candidate))],
        "replacement_ranges": 15, "overwritten_footprint": 82,
        "unequal_existing_bytes": len(actual), "alignment_bytes": "ffffffff",
        "helper_bytes": 276, "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/SHTRV-01_2.2.4_patch_cc_experimental.gbl")
    args = parser.parse_args()
    require(subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == "patch-c-c-experimental", "Wrong branch; STOP")
    output = args.output.resolve()
    require(not output.is_relative_to((ROOT / "original").resolve()), "Output may not be inside original/")
    require(not output.exists(), "Refusing to overwrite existing output")
    summary = output.with_suffix(".verification.json")
    require(not summary.exists(), "Refusing to overwrite existing verification report")
    source = SOURCE.read_bytes()
    candidate = construct(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(candidate)
    # Validate bytes actually read from the output file, not only in-memory data.
    result = verify(source, output.read_bytes())
    require(SOURCE.read_bytes() == source, "Original input changed during build")
    try:
        report_output = str(output.relative_to(ROOT))
    except ValueError:
        report_output = output.name
    result.update(output=report_output, branch="patch-c-c-experimental")
    with summary.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, IndexError) as error:
        raise SystemExit(f"ABORT: {error}")
