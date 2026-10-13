from pathlib import Path
import hashlib
import struct

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = PROJECT_ROOT / "original" / "SHTRV-01_build.gbl"

data = FIRMWARE.read_bytes()

sha256 = hashlib.sha256(data).hexdigest().upper()

print("Shelly TRV Firmware Inspector")
print("=" * 70)
print(f"Datei:   {FIRMWARE.name}")
print(f"Größe:   {len(data):,} Bytes")
print(f"SHA-256: {sha256}")
print()

print("GBL-Tags")
print("=" * 70)

offset = 0
tag_number = 1

while offset + 8 <= len(data):

    tag_id, length = struct.unpack_from("<II", data, offset)

    print(
        f"{tag_number:02d}: "
        f"Offset 0x{offset:06X} | "
        f"Tag 0x{tag_id:08X} | "
        f"Länge {length:,} Bytes"
    )

    next_offset = offset + 8 + length

    if next_offset <= offset or next_offset > len(data):
        print()
        print("FEHLER: Ungültige Tag-Länge.")
        break

    offset = next_offset
    tag_number += 1

print()
print(f"Parser-Ende: 0x{offset:06X}")
print(f"Dateiende:   0x{len(data):06X}")

print()
print("Program-Data-Blöcke extrahieren")
print("=" * 70)

PROGRAM_TAG = 0xFD0303FD

offset = 0
block_number = 1

while offset + 8 <= len(data):
    tag_id, length = struct.unpack_from("<II", data, offset)

    payload_start = offset + 8
    payload_end = payload_start + length

    if tag_id == PROGRAM_TAG:
        payload = data[payload_start:payload_end]

        if len(payload) < 4:
            print(f"Block {block_number}: zu kurz")
        else:
            flash_address = struct.unpack_from("<I", payload, 0)[0]
            flash_data = payload[4:]

            output_file = (
                PROJECT_ROOT
                / "extracted"
                / f"program_{block_number}_0x{flash_address:08X}.bin"
            )

            output_file.write_bytes(flash_data)

            print(
                f"Block {block_number}: "
                f"Flash-Adresse 0x{flash_address:08X} | "
                f"{len(flash_data):,} Bytes | "
                f"{output_file.name}"
            )

            block_number += 1

    offset = payload_end

print()
print("Suche nach Beacon-Recovery-String")
print("=" * 70)

search_string = b"Beacon skip error! Attempt recovery"

for bin_file in sorted((PROJECT_ROOT / "extracted").glob("program_*.bin")):
    bin_data = bin_file.read_bytes()
    position = bin_data.find(search_string)

    if position >= 0:
        print(
            f"GEFUNDEN in {bin_file.name}\n"
            f"Datei-Offset: 0x{position:08X}"
        )
    else:
        print(f"Nicht gefunden in {bin_file.name}")