#!/usr/bin/env python3
"""Independent C-C verifier: no imports from, or calls to, the builder.

Recover expected bytes from the reviewed Markdown, parse both files afresh,
then reverse ONLY qualified edits in memory and compare the full stock image.
Never modifies firmware. Optionally creates a new JSON verification record.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_SOURCE_SHA = '5c4a0b222a313350952f6b1200a855833402f168bd286090c23bd4d018ab918f'
EXPECTED_APP_SHA = '4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c'


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def walk(raw):
    records = []
    cursor = 0
    while cursor != len(raw):
        ensure(len(raw) - cursor >= 8, 'Incomplete tag header')
        identifier = int.from_bytes(raw[cursor:cursor + 4], 'little')
        length = int.from_bytes(raw[cursor + 4:cursor + 8], 'little')
        finish = cursor + 8 + length
        ensure(finish <= len(raw), 'Out-of-bounds tag')
        records.append(dict(offset=cursor, identifier=identifier,
                            length=length, payload=raw[cursor + 8:finish]))
        cursor = finish
    ensure(len(records) == 6, 'Expected six tags')
    ensure([r['identifier'] for r in records] == [0x03A617EB, 0xF40A0AF4, 0xF50909F5,
                                                0xFD0303FD, 0xFD0303FD, 0xFC0404FC], 'Wrong tag order')
    ensure(records[-1]['length'] == 4, 'Invalid END size')
    ensure(int.from_bytes(raw[-4:], 'little') == zlib.crc32(raw[:-4]), 'Invalid stored CRC')
    ensure(zlib.crc32(raw) == 0x2144DF1C, 'Invalid whole-container CRC residue')
    ensure(sum(r['identifier'] == 0xFD0303FD and r['payload'][:4] == bytes(4)
               for r in records) == 1, 'Address-zero PROGRAM must be unique')
    return records


def verify(output):
    source = (ROOT / 'original/2.2.4/SHTRV-01_build_2.2.4.gbl').read_bytes()
    ensure(hashlib.sha256(source).hexdigest() == EXPECTED_SOURCE_SHA, 'Stock GBL hash mismatch')
    candidate = output.read_bytes()
    stock, changed = walk(source), walk(candidate)
    design = (ROOT / 'docs/local/rea_report/patch-c-design-2026-10-14.md').read_text()
    core = re.search(r'^### C-C\n(.*?)^### C-D\n', design, re.M | re.S)
    extra = re.search(r'^### C-C complete appended bytes\n(.*?)^### C-D appended bytes\n', design, re.M | re.S)
    ensure(core is not None and extra is not None, 'Missing report sections')
    edits = [(int(a, 16), bytes.fromhex(before), bytes.fromhex(after)) for a, before, after in
             re.findall(r'^\| `0x([a-fA-F0-9]+)` \| `0x[a-fA-F0-9]+` \| `([a-fA-F0-9]+)` \| `([a-fA-F0-9]+)` \|', core.group(1), re.M)]
    helpers = [(int(a, 16), int(n), bytes.fromhex(code)) for a, n, code in
               re.findall(r'^\| `0x([a-fA-F0-9]+)` \|(\d+)\|[^|]+\| `([a-fA-F0-9]+)` \|', extra.group(1), re.M)]
    ensure(len(edits) == 15 and len(helpers) == 10, 'Wrong report manifest counts')
    checks = {}
    def check(label, condition):
        ensure(condition, label)
        checks[label] = 'PASS'
    app = changed[3]['payload'][4:]
    old_app = stock[3]['payload'][4:]
    check('stock_application_identity', len(old_app) == 0x1003CC and hashlib.sha256(old_app).hexdigest() == EXPECTED_APP_SHA)
    check('file_length_and_growth', len(source) == 0x10E1D0 and len(candidate) == 0x10E2E8 and len(candidate) - len(source) == 0x118)
    check('first_program_offset', stock[3]['offset'] == changed[3]['offset'] == 0x6548)
    check('first_flash_address', changed[3]['payload'][:4] == stock[3]['payload'][:4] == bytes(4))
    check('first_application_lengths', len(app) == 0x1004E4 and len(old_app) == 0x1003CC)
    check('first_payload_lengths', stock[3]['length'] == 0x1003D0 and changed[3]['length'] == 0x1004E8)
    check('second_tag_movement', stock[4]['offset'] == 0x106920 and changed[4]['offset'] == 0x106A38 and changed[4]['offset'] - stock[4]['offset'] == 0x118)
    check('second_flash_address', changed[4]['payload'][:4] == (0x130A98).to_bytes(4, 'little'))
    check('second_data_length', len(changed[4]['payload'][4:]) == 0x7898)
    check('second_complete_tag_identical', source[stock[4]['offset']:stock[5]['offset']] == candidate[changed[4]['offset']:changed[5]['offset']])
    check('end_offsets', stock[5]['offset'] == 0x10E1C4 and changed[5]['offset'] == 0x10E2DC)
    check('all_preceding_tags_identical', source[:stock[3]['offset']] == candidate[:changed[3]['offset']])
    restored = bytearray(app[:0x1003CC])
    footprint = unequal = 0
    previous_end = 0
    for address, before, after in edits:
        check(f'preimage_{address:06x}', old_app[address:address + len(before)] == before)
        check(f'replacement_{address:06x}', app[address:address + len(after)] == after)
        ensure(len(before) == len(after) and address >= previous_end, 'Width/overlap mismatch')
        previous_end = address + len(before)
        restored[address:previous_end] = before
        footprint += len(before)
        unequal += sum(a != b for a, b in zip(before, after))
    check('15_ranges_82_footprint_77_unequal', (len(edits), footprint, unequal) == (15, 82, 77))
    check('no_unqualified_existing_application_changes', bytes(restored) == old_app)
    check('actual_existing_byte_difference_count', sum(a != b for a, b in zip(app, old_app)) == 77)
    check('four_FF_alignment_bytes', app[0x1003CC:0x1003D0] == bytes.fromhex('ffffffff'))
    cursor = 0x1003D0
    for address, length, code in helpers:
        check(f'helper_{address:06x}', address == cursor and length == len(code) and app[address:address + length] == code)
        cursor += length
    check('helper_count_total_and_end', len(helpers) == 10 and cursor == 0x1004E4 and cursor - 0x1003D0 == 276)
    check('complete_append_matches_report', app[0x1003D0:] == b''.join(code for _, _, code in helpers))
    check('only_required_container_metadata_changed', all(
        stock[i]['identifier'] == changed[i]['identifier'] and
        (i in (3, 5) or stock[i]['payload'] == changed[i]['payload']) for i in range(6)))
    check('crc_and_residue', zlib.crc32(candidate[:-4]) == int.from_bytes(candidate[-4:], 'little') and zlib.crc32(candidate) == 0x2144DF1C)
    return dict(verifier='independent report-derived verifier; no builder imports',
                input_sha256=hashlib.sha256(source).hexdigest(),
                output_sha256=hashlib.sha256(candidate).hexdigest(),
                output_crc32=f'0x{int.from_bytes(candidate[-4:], "little"):08X}',
                checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report:
        ensure(not args.report.resolve().is_relative_to((ROOT / 'original').resolve()), 'Report cannot be written in original/')
        ensure(not args.report.exists(), 'Refusing to overwrite verification report')
    result = verify(args.output)
    if args.report:
        with args.report.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, IndexError) as error:
        raise SystemExit(f'FAIL: {error}')
