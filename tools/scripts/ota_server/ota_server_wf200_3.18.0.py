#!/usr/bin/env python3

"""
Local OTA server for Shelly TRV Gen1 2.2.4 + WF200 3.18.0
experimental radio update.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import socket
import struct
import sys
import threading
import time
import zlib

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote


VERSION = "1.0 2.2.4_WF200_3.18.0"
REVISION = "1"

EXPECTED_PATCHED_GBL_SIZE = 1_107_420

EXPECTED_PATCHED_GBL_SHA256 = (
    "96dcf4c3c14c37a28d6fd1c9bf9ee0e3f7590968fefe83df5c51aff967bb6aee"
)

EXPECTED_PATCHED_GBL_CRC32 = 0x9C994D72

DEFAULT_FIRMWARE_NAME = (
    "SHTRV-01_2.2.4_WF200_3.18.0_EXPERIMENTAL.gbl"
)

TARGET_DIRECTORY_NAME = "target"

PREFERRED_PORTS = (80, 8000)

CHUNK_SIZE = 64 * 1024

PROGRESS_BAR_WIDTH = 40


class OTAServerError(Exception):
    """Expected OTA-server error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as firmware_file:
        while True:
            chunk = firmware_file.read(CHUNK_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def read_stored_crc32(path: Path) -> int:
    with path.open("rb") as firmware_file:
        firmware_file.seek(-4, 2)
        crc_bytes = firmware_file.read(4)

    if len(crc_bytes) != 4:
        raise OTAServerError(
            "Could not read the stored CRC32 from the firmware."
        )

    return struct.unpack("<I", crc_bytes)[0]


def calculate_gbl_crc32(path: Path) -> int:
    crc = 0

    remaining = path.stat().st_size - 4

    if remaining <= 0:
        raise OTAServerError(
            "Firmware file is too small."
        )

    with path.open("rb") as firmware_file:
        while remaining > 0:
            chunk = firmware_file.read(
                min(CHUNK_SIZE, remaining)
            )

            if not chunk:
                raise OTAServerError(
                    "Unexpected end of file while calculating CRC32."
                )

            crc = zlib.crc32(chunk, crc)
            remaining -= len(chunk)

    return crc & 0xFFFFFFFF


def validate_patched_firmware(path: Path) -> None:
    if not path.exists():
        raise OTAServerError(
            f"Firmware file does not exist:\n{path}"
        )

    if not path.is_file():
        raise OTAServerError(
            f"Firmware path is not a file:\n{path}"
        )

    size = path.stat().st_size

    if size != EXPECTED_PATCHED_GBL_SIZE:
        raise OTAServerError(
            "Firmware size does not match the expected patched image.\n"
            f"Expected : {EXPECTED_PATCHED_GBL_SIZE:,} bytes\n"
            f"Actual   : {size:,} bytes"
        )

    actual_sha256 = sha256_file(path)

    if actual_sha256.lower() != EXPECTED_PATCHED_GBL_SHA256.lower():
        raise OTAServerError(
            "Firmware SHA-256 does not match the expected patched image.\n"
            f"Expected : {EXPECTED_PATCHED_GBL_SHA256}\n"
            f"Actual   : {actual_sha256}"
        )

    stored_crc32 = read_stored_crc32(path)
    calculated_crc32 = calculate_gbl_crc32(path)

    if stored_crc32 != calculated_crc32:
        raise OTAServerError(
            "Firmware GBL CRC32 is invalid.\n"
            f"Stored     : 0x{stored_crc32:08X}\n"
            f"Calculated : 0x{calculated_crc32:08X}"
        )

    if calculated_crc32 != EXPECTED_PATCHED_GBL_CRC32:
        raise OTAServerError(
            "Firmware CRC32 does not match the expected patched image.\n"
            f"Expected   : 0x{EXPECTED_PATCHED_GBL_CRC32:08X}\n"
            f"Calculated : 0x{calculated_crc32:08X}"
        )


def is_usable_ipv4(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)

    except ValueError:
        return False

    return (
        isinstance(ip, ipaddress.IPv4Address)
        and not ip.is_loopback
        and not ip.is_unspecified
        and not ip.is_multicast
        and not ip.is_link_local
    )


def get_local_ipv4() -> str:
    candidates: list[str] = []

    probe_targets = (
        ("8.8.8.8", 80),
        ("1.1.1.1", 80),
    )

    for target in probe_targets:
        probe = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        try:
            probe.connect(target)

            address = probe.getsockname()[0]

            if is_usable_ipv4(address):
                candidates.append(address)

        except OSError:
            pass

        finally:
            probe.close()

    try:
        hostname = socket.gethostname()

        results = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        for result in results:
            address = result[4][0]

            if is_usable_ipv4(address):
                candidates.append(address)

    except OSError:
        pass

    unique_candidates = list(
        dict.fromkeys(candidates)
    )

    if not unique_candidates:
        raise OTAServerError(
            "Could not determine a usable local IPv4 address automatically."
        )

    for address in unique_candidates:
        if ipaddress.ip_address(address).is_private:
            return address

    return unique_candidates[0]


def port_is_available(
    address: str,
    port: int,
) -> bool:
    test_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    try:
        test_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        test_socket.bind(
            (address, port)
        )

        return True

    except OSError:
        return False

    finally:
        test_socket.close()


def select_port(address: str) -> int:
    for port in PREFERRED_PORTS:
        if port_is_available(address, port):
            return port

    raise OTAServerError(
        "Neither TCP port 80 nor TCP port 8000 is available "
        f"on {address}."
    )


def parse_range_header(
    header_value: str,
    file_size: int,
) -> tuple[int, int] | None:

    if not header_value.startswith("bytes="):
        raise ValueError(
            "Unsupported Range unit."
        )

    range_spec = header_value[6:].strip()

    if "," in range_spec:
        raise ValueError(
            "Multiple byte ranges are not supported."
        )

    if "-" not in range_spec:
        raise ValueError(
            "Invalid byte range."
        )

    start_text, end_text = range_spec.split(
        "-",
        1,
    )

    if not start_text and not end_text:
        raise ValueError(
            "Invalid byte range."
        )

    # Suffix range:
    #
    # Range: bytes=-500
    if not start_text:
        try:
            suffix_length = int(end_text)

        except ValueError as exc:
            raise ValueError(
                "Invalid suffix range."
            ) from exc

        if suffix_length <= 0:
            raise ValueError(
                "Invalid suffix range."
            )

        if suffix_length >= file_size:
            return 0, file_size - 1

        return (
            file_size - suffix_length,
            file_size - 1,
        )

    try:
        start = int(start_text)

    except ValueError as exc:
        raise ValueError(
            "Invalid range start."
        ) from exc

    if start < 0 or start >= file_size:
        return None

    if end_text:
        try:
            end = int(end_text)

        except ValueError as exc:
            raise ValueError(
                "Invalid range end."
            ) from exc

        if end < start:
            raise ValueError(
                "Range end is before range start."
            )

        end = min(
            end,
            file_size - 1,
        )

    else:
        # This is the request form observed during the
        # successful Shelly TRV OTA test:
        #
        # Range: bytes=0-
        end = file_size - 1

    return start, end


def format_bytes(value: float) -> str:
    units = (
        "B",
        "KiB",
        "MiB",
        "GiB",
    )

    size = float(value)

    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{size:.0f} {unit}"

            return f"{size:.1f} {unit}"

        size /= 1024.0

    return f"{size:.1f} GiB"


def format_duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds:.2f} s"

    if seconds < 60.0:
        return f"{seconds:.1f} s"

    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60

    return (
        f"{minutes} min "
        f"{remaining_seconds:.1f} s"
    )


def build_progress_bar(
    progress: float,
) -> str:
    progress = max(
        0.0,
        min(1.0, progress),
    )

    completed = int(
        PROGRESS_BAR_WIDTH * progress
    )

    remaining = (
        PROGRESS_BAR_WIDTH - completed
    )

    return (
        "["
        + ("#" * completed)
        + ("-" * remaining)
        + "]"
    )


def print_progress(
    transferred: int,
    request_size: int,
    request_start: int,
    file_size: int,
    started_at: float,
) -> None:

    if request_size <= 0:
        request_progress = 1.0

    else:
        request_progress = (
            transferred / request_size
        )

    request_progress = max(
        0.0,
        min(1.0, request_progress),
    )

    current_file_position = min(
        request_start + transferred,
        file_size,
    )

    firmware_progress = (
        current_file_position / file_size
    )

    elapsed = max(
        time.monotonic() - started_at,
        0.000001,
    )

    transfer_rate = (
        transferred / elapsed
    )

    bar = build_progress_bar(
        request_progress
    )

    line = (
        f"\r[OTA] {bar} "
        f"{request_progress * 100:6.2f}%  "
        f"{transferred:,} / {request_size:,} bytes  "
        f"{format_bytes(transfer_rate)}/s  "
        f"Firmware position: "
        f"{firmware_progress * 100:6.2f}%"
    )

    print(
        line,
        end="",
        flush=True,
    )


class FirmwareRequestHandler(
    BaseHTTPRequestHandler
):
    protocol_version = "HTTP/1.1"

    firmware_path: Path
    firmware_url_path: str

    server_version = "ShellyTRVOTA/1.0"
    sys_version = ""

    def log_message(
        self,
        format_string: str,
        *args: object,
    ) -> None:

        message = format_string % args

        print(
            f"[HTTP] "
            f"{self.client_address[0]} - "
            f"{message}",
            flush=True,
        )

    def send_common_headers(self) -> None:
        self.send_header(
            "Content-Type",
            "application/octet-stream",
        )

        self.send_header(
            "Accept-Ranges",
            "bytes",
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.send_header(
            "Connection",
            "close",
        )

    def reject_unknown_path(self) -> None:
        body = (
            b"Firmware file not found.\n"
        )

        self.send_response(404)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Connection",
            "close",
        )

        self.end_headers()

        if self.command != "HEAD":
            self.wfile.write(body)

        self.close_connection = True

    def reject_range(
        self,
        file_size: int,
    ) -> None:

        self.send_response(416)

        self.send_header(
            "Content-Range",
            f"bytes */{file_size}",
        )

        self.send_header(
            "Content-Length",
            "0",
        )

        self.send_header(
            "Accept-Ranges",
            "bytes",
        )

        self.send_header(
            "Connection",
            "close",
        )

        self.end_headers()

        self.close_connection = True

    def serve_firmware(
        self,
        send_body: bool,
    ) -> None:

        request_path = self.path.split(
            "?",
            1,
        )[0]

        if request_path != self.firmware_url_path:
            self.reject_unknown_path()
            return

        file_size = (
            self.firmware_path.stat().st_size
        )

        range_header = self.headers.get(
            "Range"
        )

        start = 0
        end = file_size - 1
        partial = False

        if range_header:
            print()
            print(
                f"[OTA] Client              : "
                f"{self.client_address[0]}"
            )

            print(
                f"[OTA] Range request       : "
                f"{range_header}"
            )

            try:
                parsed_range = (
                    parse_range_header(
                        range_header,
                        file_size,
                    )
                )

            except ValueError as exc:
                print(
                    f"[OTA] Invalid Range       : "
                    f"{exc}"
                )

                self.reject_range(
                    file_size
                )

                return

            if parsed_range is None:
                print(
                    "[OTA] Range outside file."
                )

                self.reject_range(
                    file_size
                )

                return

            start, end = parsed_range
            partial = True

        else:
            print()
            print(
                f"[OTA] Client              : "
                f"{self.client_address[0]}"
            )

            print(
                "[OTA] Range request       : NONE"
            )

        content_length = (
            end - start + 1
        )

        if partial:
            status = 206

            self.send_response(status)

            self.send_common_headers()

            self.send_header(
                "Content-Range",
                f"bytes {start}-{end}/{file_size}",
            )

            self.send_header(
                "Content-Length",
                str(content_length),
            )

        else:
            status = 200

            self.send_response(status)

            self.send_common_headers()

            self.send_header(
                "Content-Length",
                str(file_size),
            )

        self.end_headers()

        print(
            f"[OTA] HTTP response        : "
            f"{status} "
            f"{'Partial Content' if partial else 'OK'}"
        )

        print(
            f"[OTA] Requested bytes      : "
            f"{start:,} - {end:,}"
        )

        print(
            f"[OTA] Transfer size        : "
            f"{content_length:,} bytes"
        )

        print(
            f"[OTA] Firmware size        : "
            f"{file_size:,} bytes"
        )

        if start == 0 and end == file_size - 1:
            print(
                "[OTA] Request covers       : "
                "100% of firmware"
            )

        else:
            start_percent = (
                start / file_size
            ) * 100.0

            end_percent = (
                (end + 1) / file_size
            ) * 100.0

            print(
                "[OTA] Request covers       : "
                f"{start_percent:.2f}% - "
                f"{end_percent:.2f}% "
                "of firmware"
            )

        if not send_body:
            print(
                "[OTA] HEAD request         : "
                "no firmware body transferred"
            )

            self.close_connection = True
            return

        print(
            "[OTA] Status               : "
            "Firmware transfer active"
        )

        print()

        started_at = time.monotonic()

        transferred = 0
        interrupted = False

        last_progress_update = 0.0

        print_progress(
            transferred=0,
            request_size=content_length,
            request_start=start,
            file_size=file_size,
            started_at=started_at,
        )

        with self.firmware_path.open(
            "rb"
        ) as firmware_file:

            firmware_file.seek(start)

            remaining = content_length

            while remaining > 0:
                chunk = firmware_file.read(
                    min(
                        CHUNK_SIZE,
                        remaining,
                    )
                )

                if not chunk:
                    interrupted = True
                    break

                try:
                    self.wfile.write(chunk)

                except (
                    BrokenPipeError,
                    ConnectionResetError,
                    ConnectionAbortedError,
                ):
                    interrupted = True
                    break

                transferred += len(chunk)
                remaining -= len(chunk)

                now = time.monotonic()

                if (
                    now - last_progress_update
                    >= 0.10
                    or remaining == 0
                ):
                    print_progress(
                        transferred=transferred,
                        request_size=content_length,
                        request_start=start,
                        file_size=file_size,
                        started_at=started_at,
                    )

                    last_progress_update = now

        elapsed = max(
            time.monotonic() - started_at,
            0.000001,
        )

        average_rate = (
            transferred / elapsed
        )

        print()
        print()

        if (
            not interrupted
            and transferred == content_length
        ):
            print(
                "[OTA] Status               : "
                "Transfer complete"
            )

            print(
                "[OTA] HTTP transfer        : "
                "SUCCESS"
            )

        else:
            print(
                "[OTA] Status               : "
                "Transfer interrupted"
            )

            print(
                "[OTA] HTTP transfer        : "
                "INCOMPLETE"
            )

        print(
            f"[OTA] Transferred          : "
            f"{transferred:,} / "
            f"{content_length:,} bytes"
        )

        transfer_percent = (
            transferred / content_length
        ) * 100.0

        print(
            f"[OTA] Request progress     : "
            f"{transfer_percent:.2f}%"
        )

        final_file_position = min(
            start + transferred,
            file_size,
        )

        firmware_position = (
            final_file_position / file_size
        ) * 100.0

        print(
            f"[OTA] Firmware position    : "
            f"{firmware_position:.2f}%"
        )

        print(
            f"[OTA] Duration             : "
            f"{format_duration(elapsed)}"
        )

        print(
            f"[OTA] Average rate         : "
            f"{format_bytes(average_rate)}/s"
        )

        print(
            "[OTA] Firmware install     : "
            "UNKNOWN"
        )

        print(
            "[OTA] Note                 : "
            "A completed HTTP transfer does not "
            "prove successful installation."
        )

        print()

        print(
            "[OTA] Waiting for further requests..."
        )

        print()

        self.close_connection = True

    def do_GET(self) -> None:
        self.serve_firmware(
            send_body=True
        )

    def do_HEAD(self) -> None:
        self.serve_firmware(
            send_body=False
        )


class OTAServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Experimental Radio Update WF200 3.18.0."
        )
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION} revision {REVISION}",
    )

    return parser


def print_header() -> None:
    print()
    print("=" * 68)
    print("SHELLY TRV LOCAL OTA SERVER")
    print("=" * 68)
    print()


def main() -> int:
    parser = build_parser()
    parser.parse_args()

    script_directory = Path(__file__).resolve().parent

    firmware_path = (
        script_directory
        / TARGET_DIRECTORY_NAME
        / DEFAULT_FIRMWARE_NAME
    ).resolve()

    print_header()

    print(
        "Validating experimental firmware..."
    )

    print()

    try:
        validate_patched_firmware(
            firmware_path
        )

        local_ip = get_local_ipv4()

        port = select_port(
            local_ip
        )

    except OTAServerError as exc:
        print("ERROR")
        print("-" * 68)
        print(exc)
        print()

        print(
            "OTA server was not started."
        )

        return 1

    firmware_name = (
        DEFAULT_FIRMWARE_NAME
    )

    encoded_name = quote(
        firmware_name,
        safe="._-",
    )

    firmware_url_path = (
        f"/{encoded_name}"
    )

    if port == 80:
        server_base_url = (
            f"http://{local_ip}"
        )

    else:
        server_base_url = (
            f"http://{local_ip}:{port}"
        )

    firmware_url = (
        f"{server_base_url}"
        f"{firmware_url_path}"
    )

    ota_url = (
        "http://<SHELLY-TRV-IP>/ota?url="
        f"{firmware_url}"
    )

    FirmwareRequestHandler.firmware_path = (
        firmware_path
    )

    FirmwareRequestHandler.firmware_url_path = (
        firmware_url_path
    )

    try:
        server = OTAServer(
            (local_ip, port),
            FirmwareRequestHandler,
        )

    except OSError as exc:
        print("ERROR")
        print("-" * 68)

        print(
            f"Could not start HTTP server on "
            f"{local_ip}:{port}."
        )

        print(exc)

        return 1

    actual_sha256 = sha256_file(
        firmware_path
    )

    stored_crc32 = read_stored_crc32(
        firmware_path
    )

    print("Firmware validation")
    print("-" * 68)

    print(
        f"File                : "
        f"{firmware_path}"
    )

    print(
        f"Size                : "
        f"{firmware_path.stat().st_size:,} bytes"
    )

    print(
        f"SHA-256             : "
        f"{actual_sha256}"
    )

    print(
        f"GBL CRC32           : "
        f"0x{stored_crc32:08X}"
    )

    print(
        "Validation          : PASSED"
    )

    print()

    print("Network")
    print("-" * 68)

    print(
        f"Local IPv4          : "
        f"{local_ip}"
    )

    print(
        f"HTTP port           : "
        f"{port}"
    )

    print(
        "HTTP version        : HTTP/1.1"
    )

    print(
        "Range support       : YES"
    )

    print()

    print("Firmware URL")
    print("-" * 68)
    print(firmware_url)
    print()

    print("Browser test")
    print("-" * 68)

    print(
        "Open the firmware URL above in a browser."
    )

    print(
        "The validated firmware file should be "
        "returned by this server."
    )

    print()

    print("Shelly TRV OTA")
    print("-" * 68)

    print(
        "Replace <SHELLY-TRV-IP> with the IP "
        "address of the TRV:"
    )

    print()
    print(ota_url)
    print()

    print("Example")
    print("-" * 68)

    print(
        "If the Shelly TRV has IP "
        "192.168.178.50:"
    )

    print()

    print(
        "http://192.168.178.50/ota?url="
        f"{firmware_url}"
    )

    print()

    print("=" * 68)
    print("OTA SERVER ONLINE")
    print("=" * 68)

    print()

    print(
        "Status              : Waiting for TRV"
    )

    print(
        "Firmware            : VALIDATED"
    )

    print(
        f"Listening           : "
        f"{local_ip}:{port}"
    )

    print()

    print(
        "Waiting for requests..."
    )

    print(
        "Press Ctrl+C to stop the server."
    )

    print()

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print()
        print()

        print(
            "Stopping OTA server..."
        )

    finally:
        server.shutdown()
        server.server_close()

    print(
        "OTA server stopped."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )