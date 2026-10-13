from pathlib import Path
import struct
import zlib
import hashlib


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ORIGINAL_GBL = PROJECT_ROOT / "original" / "SHTRV-01_build.gbl"
PATCHED_BIN = PROJECT_ROOT / "SHTRV-01_2.2.4_beacon_patch.bin"
OUTPUT_GBL = PROJECT_ROOT / "SHTRV-01_build_2.2.4_beacon_patch.gbl"

PROGRAM_TAG = 0xFD0303FD
TARGET_FLASH_ADDRESS = 0x00000000


gbl = bytearray(ORIGINAL_GBL.read_bytes())
patched = PATCHED_BIN.read_bytes()

print("Shelly TRV patched GBL builder")
print("=" * 70)
print(f"Original GBL: {len(gbl):,} Bytes")
print(f"Patch Binary: {len(patched):,} Bytes")
print()

offset = 0
found = False

while offset + 8 <= len(gbl):
    tag_id, length = struct.unpack_from("<II", gbl, offset)

    payload_start = offset + 8
    payload_end = payload_start + length

    if payload_end > len(gbl):
        raise RuntimeError(
            f"Ungültige Tag-Länge bei Offset 0x{offset:08X}"
        )

    if tag_id == PROGRAM_TAG:
        if length < 4:
            raise RuntimeError("PROGRAM_TAG ist zu kurz.")

        flash_address = struct.unpack_from("<I", gbl, payload_start)[0]

        program_start = payload_start + 4
        program_end = payload_end
        program_length = program_end - program_start

        print(
            f"PROGRAM_TAG bei 0x{offset:08X}: "
            f"Flash 0x{flash_address:08X}, "
            f"{program_length:,} Bytes"
        )

        if flash_address == TARGET_FLASH_ADDRESS:
            if found:
                raise RuntimeError(
                    "Mehr als ein passender PROGRAM_TAG gefunden."
                )

            if len(patched) != program_length:
                raise RuntimeError(
                    "Patch-Binary hat nicht die erwartete Länge: "
                    f"{len(patched):,} != {program_length:,}"
                )

            # Zusätzliche Sicherheitsprüfung unseres bekannten Patches
            if gbl[program_start + 0x1E1C9] != 0xDC:
                raise RuntimeError(
                    "Originalbyte bei Patchposition ist nicht DC."
                )

            if patched[0x1E1C9] != 0xE0:
                raise RuntimeError(
                    "Patchbyte bei 0x1E1C9 ist nicht E0."
                )

            gbl[program_start:program_end] = patched

            found = True

            print(
                f"Program-Block ersetzt: "
                f"0x{program_start:08X} - "
                f"0x{program_end - 1:08X}"
            )

    offset = payload_end


if not found:
    raise RuntimeError(
        "PROGRAM_TAG für Flash-Adresse 0x00000000 nicht gefunden."
    )


# Der letzte GBL-Tag enthält die CRC32 in den letzten vier Bytes.
stored_old_crc = struct.unpack_from("<I", gbl, len(gbl) - 4)[0]

new_crc = zlib.crc32(gbl[:-4]) & 0xFFFFFFFF
struct.pack_into("<I", gbl, len(gbl) - 4, new_crc)

OUTPUT_GBL.write_bytes(gbl)

sha256 = hashlib.sha256(gbl).hexdigest().upper()

print()
print(f"Alte CRC32: 0x{stored_old_crc:08X}")
print(f"Neue CRC32: 0x{new_crc:08X}")
print()
print(f"Ausgabe: {OUTPUT_GBL.name}")
print(f"Größe:   {len(gbl):,} Bytes")
print(f"SHA-256: {sha256}")
print()
print("GBL erfolgreich erzeugt.")