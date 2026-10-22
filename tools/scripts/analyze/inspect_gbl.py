from pathlib import Path
import argparse
import hashlib
import struct


PROGRAM_TAG = 0xFD0303FD
BEACON_RECOVERY_STRING = b"Beacon skip error! Attempt recovery"


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a Silicon Labs GBL firmware file, list its tags, "
            "extract PROGRAM data blocks, and search them for the "
            "Shelly TRV Beacon Recovery string."
        )
    )

    parser.add_argument(
        "firmware",
        type=Path,
        help="Path to the GBL firmware file",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("extracted"),
        help="Directory for extracted PROGRAM blocks (default: ./extracted)",
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    firmware = args.firmware.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()

    if not firmware.is_file():
        raise SystemExit(f"ERROR: Firmware file not found: {firmware}")

    data = firmware.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest().upper()

    print("Shelly TRV Firmware Inspector")
    print("=" * 70)
    print(f"File:    {firmware}")
    print(f"Size:    {len(data):,} bytes")
    print(f"SHA-256: {sha256}")
    print()

    print("GBL Tags")
    print("=" * 70)

    offset = 0
    tag_number = 1
    parser_valid = True

    while offset + 8 <= len(data):
        tag_id, length = struct.unpack_from("<II", data, offset)

        print(
            f"{tag_number:02d}: "
            f"Offset 0x{offset:06X} | "
            f"Tag 0x{tag_id:08X} | "
            f"Length {length:,} bytes"
        )

        next_offset = offset + 8 + length

        if next_offset <= offset or next_offset > len(data):
            print()
            print("ERROR: Invalid tag length.")
            parser_valid = False
            break

        offset = next_offset
        tag_number += 1

    print()
    print(f"Parser end: 0x{offset:06X}")
    print(f"File end:   0x{len(data):06X}")

    if offset != len(data):
        parser_valid = False
        print("WARNING: Parser did not end exactly at EOF.")

    if not parser_valid:
        raise SystemExit(1)

    print()
    print("Extract PROGRAM data blocks")
    print("=" * 70)

    output_dir.mkdir(parents=True, exist_ok=True)

    offset = 0
    block_number = 1
    extracted_files = []

    while offset + 8 <= len(data):
        tag_id, length = struct.unpack_from("<II", data, offset)

        payload_start = offset + 8
        payload_end = payload_start + length

        if payload_end > len(data):
            print("ERROR: PROGRAM block exceeds file boundary.")
            raise SystemExit(1)

        if tag_id == PROGRAM_TAG:
            payload = data[payload_start:payload_end]

            if len(payload) < 4:
                print(f"Block {block_number}: too short")
            else:
                flash_address = struct.unpack_from("<I", payload, 0)[0]
                flash_data = payload[4:]

                output_file = (
                    output_dir
                    / f"program_{block_number}_0x{flash_address:08X}.bin"
                )

                output_file.write_bytes(flash_data)
                extracted_files.append(output_file)

                print(
                    f"Block {block_number}: "
                    f"Flash address 0x{flash_address:08X} | "
                    f"{len(flash_data):,} bytes | "
                    f"{output_file.name}"
                )

                block_number += 1

        offset = payload_end

    print()
    print("Search for Beacon Recovery string")
    print("=" * 70)

    if not extracted_files:
        print("No PROGRAM data blocks found.")
        return

    for bin_file in extracted_files:
        bin_data = bin_file.read_bytes()
        position = bin_data.find(BEACON_RECOVERY_STRING)

        if position >= 0:
            print(
                f"FOUND in {bin_file.name}\n"
                f"File offset: 0x{position:08X}"
            )
        else:
            print(f"Not found in {bin_file.name}")


if __name__ == "__main__":
    main()