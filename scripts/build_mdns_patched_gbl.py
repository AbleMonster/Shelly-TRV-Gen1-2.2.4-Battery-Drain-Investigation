from pathlib import Path
import hashlib
import struct
import zlib


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ORIGINAL_GBL = (
    PROJECT_ROOT
    / "original"
    / "2.2.4"
    / "SHTRV-01_build_2.2.4.gbl"
)

PATCHED_BIN = PROJECT_ROOT / "SHTRV-01_2.2.4_mdns_patch.bin"

OUTPUT_GBL = PROJECT_ROOT / "SHTRV-01_build_2.2.4_mdns_patch.gbl"


# ---------------------------------------------------------------------------
# Verified layout of the original Shelly TRV 2.2.4 GBL
# ---------------------------------------------------------------------------

PROGRAM_START = 0x6554
PROGRAM_LENGTH = 1_049_548

EXPECTED_GBL_SIZE = 1_106_384

EXPECTED_ORIGINAL_PROGRAM_SHA256 = (
    "4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c"
)

EXPECTED_PATCHED_PROGRAM_SHA256 = (
    "f5a07e5fbc18daf49860673edc7a41288dc4847889992bee2c82dc8116f17df0"
)


# ---------------------------------------------------------------------------
# Patch definitions
# ---------------------------------------------------------------------------

# Patch B: periodic mDNS restart
MDNS_PATCH_OFFSET = 0x1E0F1
MDNS_ORIGINAL_BYTE = 0xD0
MDNS_PATCHED_BYTE = 0xE0

# Patch A: Beacon-Recovery
# MUST remain stock in this experimental firmware.
BEACON_PATCH_OFFSET = 0x1E1C9
BEACON_STOCK_BYTE = 0xDC


def sha256(data):
    return hashlib.sha256(data).hexdigest()


print("Shelly TRV 2.2.4 mDNS-only GBL builder")
print("=" * 70)

gbl = bytearray(ORIGINAL_GBL.read_bytes())
patched = PATCHED_BIN.read_bytes()

print(f"Original GBL: {len(gbl):,} Bytes")
print(f"Patch Binary: {len(patched):,} Bytes")
print()


# ---------------------------------------------------------------------------
# Basic file checks
# ---------------------------------------------------------------------------

if len(gbl) != EXPECTED_GBL_SIZE:
    raise RuntimeError(
        "Original-GBL hat eine unerwartete Größe:\n"
        f"Erwartet: {EXPECTED_GBL_SIZE:,}\n"
        f"Gefunden: {len(gbl):,}"
    )

if len(patched) != PROGRAM_LENGTH:
    raise RuntimeError(
        "Patch-Binary hat eine unerwartete Größe:\n"
        f"Erwartet: {PROGRAM_LENGTH:,}\n"
        f"Gefunden: {len(patched):,}"
    )


# ---------------------------------------------------------------------------
# Extract and verify original program block
# ---------------------------------------------------------------------------

program_end = PROGRAM_START + PROGRAM_LENGTH

if program_end > len(gbl):
    raise RuntimeError(
        "Der erwartete Program-Block liegt außerhalb des GBL."
    )

original_program = bytes(gbl[PROGRAM_START:program_end])

original_program_sha = sha256(original_program)

print(f"Program-Start:  0x{PROGRAM_START:08X}")
print(f"Program-Ende:   0x{program_end - 1:08X}")
print(f"Program-Länge:  {PROGRAM_LENGTH:,} Bytes")
print()
print(f"Original Program SHA-256:")
print(original_program_sha)
print()

if original_program_sha != EXPECTED_ORIGINAL_PROGRAM_SHA256:
    raise RuntimeError(
        "ABBRUCH: Der Program-Block im Original-GBL entspricht nicht "
        "der analysierten Shelly TRV 2.2.4 Firmware."
    )


# ---------------------------------------------------------------------------
# Verify patched program identity
# ---------------------------------------------------------------------------

patched_program_sha = sha256(patched)

print("mDNS Patch Program SHA-256:")
print(patched_program_sha)
print()

if patched_program_sha != EXPECTED_PATCHED_PROGRAM_SHA256:
    raise RuntimeError(
        "ABBRUCH: SHA-256 des mDNS-Patch-Binaries stimmt nicht."
    )


# ---------------------------------------------------------------------------
# Verify patch positions
# ---------------------------------------------------------------------------

if original_program[MDNS_PATCH_OFFSET] != MDNS_ORIGINAL_BYTE:
    raise RuntimeError(
        "ABBRUCH: Originalbyte an der mDNS-Patchposition ist nicht D0."
    )

if patched[MDNS_PATCH_OFFSET] != MDNS_PATCHED_BYTE:
    raise RuntimeError(
        "ABBRUCH: mDNS-Patchbyte ist nicht E0."
    )

if original_program[BEACON_PATCH_OFFSET] != BEACON_STOCK_BYTE:
    raise RuntimeError(
        "ABBRUCH: Beacon-Recovery-Byte im Original ist unerwartet."
    )

if patched[BEACON_PATCH_OFFSET] != BEACON_STOCK_BYTE:
    raise RuntimeError(
        "ABBRUCH: Das Patch-Binary enthält zusätzlich "
        "den Beacon-Recovery-Patch."
    )


# ---------------------------------------------------------------------------
# Verify that EXACTLY ONE byte differs from stock
# ---------------------------------------------------------------------------

differences = [
    i
    for i, (stock_byte, patch_byte) in enumerate(
        zip(original_program, patched)
    )
    if stock_byte != patch_byte
]

if differences != [MDNS_PATCH_OFFSET]:
    print("Gefundene Unterschiede:")

    for offset in differences[:20]:
        print(
            f"  0x{offset:06X}: "
            f"{original_program[offset]:02X} -> {patched[offset]:02X}"
        )

    raise RuntimeError(
        "ABBRUCH: Patch-Binary unterscheidet sich nicht "
        "ausschließlich an der mDNS-Patchposition."
    )

print(
    f"mDNS-Patch verifiziert: "
    f"0x{MDNS_PATCH_OFFSET:06X}: "
    f"{MDNS_ORIGINAL_BYTE:02X} -> "
    f"{MDNS_PATCHED_BYTE:02X}"
)

print(
    f"Beacon-Recovery unverändert: "
    f"0x{BEACON_PATCH_OFFSET:06X} = "
    f"{BEACON_STOCK_BYTE:02X}"
)

print("Differenz zu Stock: exakt 1 Byte")
print()


# ---------------------------------------------------------------------------
# Replace program block
# ---------------------------------------------------------------------------

gbl[PROGRAM_START:program_end] = patched


# ---------------------------------------------------------------------------
# Recalculate GBL CRC32
# ---------------------------------------------------------------------------

stored_old_crc = struct.unpack_from("<I", gbl, len(gbl) - 4)[0]

new_crc = zlib.crc32(gbl[:-4]) & 0xFFFFFFFF

struct.pack_into("<I", gbl, len(gbl) - 4, new_crc)


# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

OUTPUT_GBL.write_bytes(gbl)

output_sha = sha256(gbl)

print(f"Alte CRC32: 0x{stored_old_crc:08X}")
print(f"Neue CRC32: 0x{new_crc:08X}")
print()

print(f"Ausgabe:")
print(OUTPUT_GBL)

print()
print(f"Größe:   {len(gbl):,} Bytes")
print(f"SHA-256: {output_sha}")
print()

print("mDNS-only GBL erfolgreich erzeugt.")