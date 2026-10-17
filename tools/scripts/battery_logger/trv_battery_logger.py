#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DB_FILE = BASE_DIR / "trv_logger.sqlite3"
REPORT_DIR = BASE_DIR / "reports"
DEBUG_DIR = BASE_DIR / "debug_logs"


@dataclass
class EndpointResult:
    ok: bool
    status_code: Optional[int]
    text: str
    json_data: Any = None
    error: Optional[str] = None


def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def init_db():

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        "PRAGMA journal_mode=WAL;"
    )

    # -------------------------------------------------
    # Haupttabelle anlegen
    # -------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS samples(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            timestamp_local TEXT NOT NULL,
            device_name TEXT NOT NULL,
            ip TEXT NOT NULL,

            firmware TEXT,
            firmware_full TEXT,

            uptime_seconds REAL,
            battery_percent REAL,
            battery_voltage REAL,
            charger INTEGER,
            rssi INTEGER,

            status_ok INTEGER NOT NULL,
            stats_ok INTEGER,

            status_raw TEXT,
            stats_raw TEXT,

            error_text TEXT
        )
        """
    )

    # -------------------------------------------------
    # Debug-Snapshots
    # -------------------------------------------------

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS debug_snapshots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            timestamp_local TEXT NOT NULL,

            device_name TEXT NOT NULL,
            ip TEXT NOT NULL,

            debug_ok INTEGER NOT NULL,

            file_path TEXT,
            error_text TEXT
        )
        """
    )

    # -------------------------------------------------
    # Bestehende Datenbank automatisch erweitern
    # -------------------------------------------------

    existing_columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(samples)"
        )
    }

    required_columns = {

        "firmware_full":
            "TEXT",

        "rssi":
            "INTEGER",
    }

    for (
        column_name,
        column_type,
    ) in required_columns.items():

        if (
            column_name
            not in existing_columns
        ):

            print(
                f"Datenbank-Migration: "
                f"Spalte "
                f"{column_name} "
                f"wird hinzugefügt."
            )

            conn.execute(
                f"""
                ALTER TABLE samples
                ADD COLUMN
                {column_name}
                {column_type}
                """
            )

    conn.commit()

    return conn


def http_get(ip, path, timeout):
    """
    Gen1-Webserver kann bei persistenten HTTP-Verbindungen problematisch sein.

    Deshalb:
    Connection: close
    """

    req = urllib.request.Request(
        f"http://{ip}{path}",
        headers={
            "User-Agent": "Shelly-TRV-Battery-Logger/2.0",
            "Connection": "close",
            "Accept": "*/*",
        },
    )

    try:

        with urllib.request.urlopen(req, timeout=timeout) as response:

            data = response.read()

            text = data.decode(
                "utf-8",
                errors="replace",
            )

            json_data = None

            stripped = text.lstrip()

            if stripped.startswith("{") or stripped.startswith("["):

                try:
                    json_data = json.loads(text)

                except json.JSONDecodeError:
                    pass

            return EndpointResult(
                ok=True,
                status_code=getattr(response, "status", 200),
                text=text,
                json_data=json_data,
            )

    except urllib.error.HTTPError as exc:

        return EndpointResult(
            ok=False,
            status_code=exc.code,
            text="",
            error=f"HTTP {exc.code}: {exc.reason}",
        )

    except Exception as exc:

        return EndpointResult(
            ok=False,
            status_code=None,
            text="",
            error=f"{type(exc).__name__}: {exc}",
        )


def parse_status(obj):
    """
    Erwartete Shelly-TRV-Struktur:

    bat.value
    bat.voltage
    charger
    uptime
    wifi_sta.rssi
    fw_info.fw
    """

    result = {
        "firmware": None,
        "firmware_full": None,
        "uptime_seconds": None,
        "battery_percent": None,
        "battery_voltage": None,
        "charger": None,
        "rssi": None,
    }

    if not isinstance(obj, dict):
        return result

    # -------------------------------------------------
    # Batterie
    # -------------------------------------------------

    bat = obj.get("bat")

    if isinstance(bat, dict):

        if isinstance(
            bat.get("value"),
            (int, float),
        ):
            result["battery_percent"] = float(
                bat["value"]
            )

        if isinstance(
            bat.get("voltage"),
            (int, float),
        ):
            result["battery_voltage"] = float(
                bat["voltage"]
            )

    # -------------------------------------------------
    # Charger
    # -------------------------------------------------

    charger = obj.get("charger")

    if isinstance(charger, bool):
        result["charger"] = int(charger)

    elif isinstance(
        charger,
        (int, float),
    ):
        result["charger"] = int(
            bool(charger)
        )

    # -------------------------------------------------
    # Uptime
    # -------------------------------------------------

    uptime = obj.get("uptime")

    if isinstance(
        uptime,
        (int, float),
    ):
        result["uptime_seconds"] = float(
            uptime
        )

    # -------------------------------------------------
    # RSSI
    # -------------------------------------------------

    wifi = obj.get("wifi_sta")

    if isinstance(wifi, dict):

        rssi = wifi.get("rssi")

        if isinstance(
            rssi,
            (int, float),
        ):
            result["rssi"] = int(rssi)

    # -------------------------------------------------
    # Firmware
    # -------------------------------------------------

    fw_info = obj.get("fw_info")

    if isinstance(
        fw_info,
        dict,
    ):

        fw = fw_info.get("fw")

        if isinstance(fw, str):

            result["firmware_full"] = fw

            # Beispiel:
            #
            # 20240619-130912/v2.2.4@ee290818

            if "/v" in fw:

                result["firmware"] = (
                    fw
                    .split("/v", 1)[1]
                    .split("@", 1)[0]
                )

            else:
                result["firmware"] = fw

    return result


def poll_device(
    device,
    timeout,
    now_local,
):

    name = device["name"]
    ip = device["ip"]

    # -------------------------------------------------
    # STATUS
    # -------------------------------------------------

    status = http_get(
        ip,
        "/status",
        timeout,
    )

    parsed = parse_status(
        status.json_data
        if status.ok
        else None
    )

    # -------------------------------------------------
    # STATS
    #
    # Nur Firmware 2.2.4
    # -------------------------------------------------

    stats = None

    if parsed["firmware"] == "2.2.4":

        stats = http_get(
            ip,
            "/stats",
            timeout,
        )

    # -------------------------------------------------
    # Fehler sammeln
    # -------------------------------------------------

    errors = []

    if not status.ok:

        errors.append(
            f"/status: {status.error}"
        )

    if (
        stats is not None
        and not stats.ok
    ):

        errors.append(
            f"/stats: {stats.error}"
        )

    # -------------------------------------------------
    # Ergebnis
    # -------------------------------------------------

    return {

        "timestamp_utc":
            now_local
            .astimezone(timezone.utc)
            .isoformat(),

        "timestamp_local":
            now_local.isoformat(),

        "device_name":
            name,

        "ip":
            ip,

        "firmware":
            parsed["firmware"],

        "firmware_full":
            parsed["firmware_full"],

        "uptime_seconds":
            parsed["uptime_seconds"],

        "battery_percent":
            parsed["battery_percent"],

        "battery_voltage":
            parsed["battery_voltage"],

        "charger":
            parsed["charger"],

        "rssi":
            parsed["rssi"],

        "status_ok":
            int(status.ok),

        "stats_ok":
            None
            if stats is None
            else int(stats.ok),

        "status_raw":
            status.text,

        "stats_raw":
            None
            if stats is None
            else stats.text,

        "error_text":
            " | ".join(errors)
            if errors
            else None,
    }


def save_sample(
    conn,
    row,
):

    conn.execute(
        """
        INSERT INTO samples(
            timestamp_utc,
            timestamp_local,
            device_name,
            ip,

            firmware,
            firmware_full,

            uptime_seconds,
            battery_percent,
            battery_voltage,
            charger,
            rssi,

            status_ok,
            stats_ok,

            status_raw,
            stats_raw,

            error_text
        )
        VALUES(
            :timestamp_utc,
            :timestamp_local,
            :device_name,
            :ip,

            :firmware,
            :firmware_full,

            :uptime_seconds,
            :battery_percent,
            :battery_voltage,
            :charger,
            :rssi,

            :status_ok,
            :stats_ok,

            :status_raw,
            :stats_raw,

            :error_text
        )
        """,
        row,
    )

    conn.commit()


def next_aligned_sample(
    now,
    interval,
):
    """
    Erzeugt feste Messzeitpunkte.

    Beispiel 30 Minuten:

    10:00
    10:30
    11:00
    11:30
    """

    midnight = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    elapsed_minutes = int(
        (now - midnight)
        .total_seconds()
        // 60
    )

    next_minute = (
        (
            elapsed_minutes
            // interval
        )
        + 1
    ) * interval

    return midnight + timedelta(
        minutes=next_minute
    )


def next_report_time(
    now,
    hour,
    minute,
):

    report_time = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if report_time <= now:

        report_time += timedelta(
            days=1
        )

    return report_time


def archive_debug_logs(
    config,
    conn,
    tz,
):
    """
    Debug-Log absichtlich nur einmal täglich.

    /debug/log erzeugt selbst Netzwerkverkehr
    und zusätzliche Debug-Einträge.
    """

    timeout = int(
        config.get(
            "http_timeout_seconds",
            15,
        )
    )

    now = datetime.now(
        tz
    ).replace(
        microsecond=0
    )

    DEBUG_DIR.mkdir(
        exist_ok=True
    )

    print(
        f"\n[{now.isoformat()}] "
        f"täglicher Debug-Log-Snapshot"
    )

    for device in config["devices"]:

        name = device["name"]
        ip = device["ip"]

        result = http_get(
            ip,
            "/debug/log",
            timeout,
        )

        file_path = None

        if result.ok:

            safe_name = "".join(
                c
                if c.isalnum()
                or c in "._-"
                else "_"
                for c in name
            )

            filename = (
                f"{now.strftime('%Y-%m-%d_%H%M%S')}_"
                f"{safe_name}_"
                f"{ip.replace('.', '-')}.html"
            )

            path = (
                DEBUG_DIR
                / filename
            )

            path.write_text(
                result.text,
                encoding="utf-8",
            )

            file_path = str(path)

            print(
                f"  {name}: "
                f"Debug-Log gespeichert"
            )

        else:

            print(
                f"  {name}: "
                f"FEHLER "
                f"{result.error}"
            )

        conn.execute(
            """
            INSERT INTO debug_snapshots(
                timestamp_utc,
                timestamp_local,
                device_name,
                ip,
                debug_ok,
                file_path,
                error_text
            )
            VALUES(
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                now
                .astimezone(timezone.utc)
                .isoformat(),

                now.isoformat(),

                name,
                ip,

                int(result.ok),

                file_path,

                result.error,
            ),
        )

        conn.commit()


def fetch_rows(
    conn,
    start,
    end,
):

    conn.row_factory = sqlite3.Row

    return conn.execute(
        """
        SELECT *
        FROM samples

        WHERE
            timestamp_utc >= ?
            AND
            timestamp_utc < ?

        ORDER BY
            device_name,
            timestamp_utc
        """,
        (
            start
            .astimezone(timezone.utc)
            .isoformat(),

            end
            .astimezone(timezone.utc)
            .isoformat(),
        ),
    ).fetchall()


def fmt(
    value,
    digits=2,
    suffix="",
):

    if value is None:
        return "-"

    if isinstance(
        value,
        float,
    ):

        return (
            f"{value:.{digits}f}"
            f"{suffix}"
        )

    return (
        f"{value}"
        f"{suffix}"
    )


def stats_value(
    row,
    key,
):

    raw = row["stats_raw"]

    if not raw:
        return None

    try:

        obj = json.loads(raw)

        return obj.get(key)

    except Exception:

        return None


def generate_pdf(
    conn,
    start,
    end,
    timezone_name,
):

    rows = fetch_rows(
        conn,
        start,
        end,
    )

    if not rows:

        print(
            "Kein PDF: "
            "keine Messwerte."
        )

        return

    REPORT_DIR.mkdir(
        exist_ok=True
    )

    filename = (
        f"TRV_Battery_Report_"
        f"{start.strftime('%Y-%m-%d_%H%M')}"
        f"_bis_"
        f"{end.strftime('%Y-%m-%d_%H%M')}"
        f".pdf"
    )

    path = (
        REPORT_DIR
        / filename
    )

    doc = SimpleDocTemplate(
        str(path),

        pagesize=
        landscape(A4),

        leftMargin=
        8 * mm,

        rightMargin=
        8 * mm,

        topMargin=
        8 * mm,

        bottomMargin=
        8 * mm,
    )

    styles = (
        getSampleStyleSheet()
    )

    story = [

        Paragraph(
            "Shelly TRV Gen1 – "
            "24-h Battery Report",

            styles["Title"],
        ),

        Paragraph(
            f"Zeitraum: "
            f"{start.strftime('%d.%m.%Y %H:%M')} "
            f"bis "
            f"{end.strftime('%d.%m.%Y %H:%M')} "
            f"({timezone_name})",

            styles["Normal"],
        ),

        Spacer(
            1,
            4 * mm,
        ),
    ]

    by_device = {}

    for row in rows:

        by_device.setdefault(
            row["device_name"],
            [],
        ).append(row)

    for (
        device_name,
        device_rows,
    ) in by_device.items():

        first = device_rows[0]

        story.append(
            Paragraph(
                f"{device_name} – "
                f"{first['ip']} – "
                f"Firmware "
                f"{first['firmware'] or '?'}",

                styles["Heading2"],
            )
        )

        detail = [[
            "Zeit",
            "%",
            "V",
            "RSSI",
            "Uptime",

            "real",
            "desired",
            "sleep",

            "b.err",
            "b.rx",
            "missed",

            "Status",
            "Stats",
        ]]

        for row in device_rows:

            local_time = (
                datetime.fromisoformat(
                    row["timestamp_local"]
                )
            )

            if (
                row["uptime_seconds"]
                is None
            ):

                uptime = "-"

            else:

                uptime = str(
                    timedelta(
                        seconds=int(
                            row["uptime_seconds"]
                        )
                    )
                )

            detail.append([

                local_time.strftime(
                    "%d.%m. %H:%M"
                ),

                fmt(
                    row["battery_percent"],
                    0,
                ),

                fmt(
                    row["battery_voltage"],
                    3,
                ),

                (
                    "-"
                    if row["rssi"]
                    is None
                    else str(
                        row["rssi"]
                    )
                ),

                uptime,

                fmt(
                    stats_value(
                        row,
                        "real_beacon_skip",
                    ),
                    0,
                ),

                fmt(
                    stats_value(
                        row,
                        "desired_beacon_skip",
                    ),
                    0,
                ),

                fmt(
                    stats_value(
                        row,
                        "sleep_ratio",
                    ),
                    4,
                ),

                fmt(
                    stats_value(
                        row,
                        "beacon_err_counter",
                    ),
                    0,
                ),

                fmt(
                    stats_value(
                        row,
                        "beacon_rx_count",
                    ),
                    0,
                ),

                fmt(
                    stats_value(
                        row,
                        "beacon_rx_missed_count",
                    ),
                    0,
                ),

                (
                    "OK"
                    if row["status_ok"]
                    else "ERR"
                ),

                (
                    "n/a"
                    if row["stats_ok"]
                    is None
                    else (
                        "OK"
                        if row["stats_ok"]
                        else "ERR"
                    )
                ),
            ])

        table = Table(
            detail,
            repeatRows=1,
        )

        table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey,
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.2,
                    colors.grey,
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    6.2,
                ),
            ])
        )

        story.append(table)

        story.append(
            PageBreak()
        )

    doc.build(story)

    print(
        f"PDF erstellt: "
        f"{path}"
    )


def run_once(
    config,
    conn,
    tz,
):

    timeout = int(
        config.get(
            "http_timeout_seconds",
            15,
        )
    )

    now = datetime.now(
        tz
    ).replace(
        microsecond=0
    )

    print(
        f"\n[{now.isoformat()}] "
        f"Messrunde"
    )

    for device in config["devices"]:

        row = poll_device(
            device,
            timeout,
            now,
        )

        save_sample(
            conn,
            row,
        )

        if row["stats_ok"] is None:

            stats_text = "n/a"

        elif row["stats_ok"]:

            stats_text = "OK"

        else:

            stats_text = "ERR"

        print(
            f"  "
            f"{row['device_name']} "
            f"({row['ip']}): "

            f"FW="
            f"{row['firmware'] or '?'} "

            f"Bat="
            f"{fmt(row['battery_percent'], 0, '%')} "

            f"V="
            f"{fmt(row['battery_voltage'], 3, 'V')} "

            f"Uptime="
            f"{fmt(row['uptime_seconds'], 0, 's')} "

            f"stats="
            f"{stats_text}"
        )

        if row["error_text"]:

            print(
                f"    Fehler: "
                f"{row['error_text']}"
            )


def main():

    config = load_config()

    try:

        tz = ZoneInfo(
            config.get(
                "timezone",
                "Europe/Berlin",
            )
        )

    except Exception as exc:

        raise SystemExit(
            "Zeitzone konnte nicht geladen werden.\n"
            "Installiere:\n"
            "python -m pip install tzdata"
        ) from exc

    interval = int(
        config.get(
            "sample_interval_minutes",
            30,
        )
    )

    report_hour = int(
        config.get(
            "report_hour",
            8,
        )
    )

    report_minute = int(
        config.get(
            "report_minute",
            0,
        )
    )

    conn = init_db()

    # -------------------------------------------------
    # Sofortige Messung beim Start
    # -------------------------------------------------

    run_once(
        config,
        conn,
        tz,
    )

    # -------------------------------------------------
    # Nächste feste Messzeit
    # -------------------------------------------------

    next_sample = (
        next_aligned_sample(
            datetime.now(tz),
            interval,
        )
    )

    # -------------------------------------------------
    # Nächster Report
    # -------------------------------------------------

    next_report = (
        next_report_time(
            datetime.now(tz),
            report_hour,
            report_minute,
        )
    )

    print(
        f"Nächste Messung: "
        f"{next_sample.isoformat()}"
    )

    print(
        f"Nächster 24-h-Bericht: "
        f"{next_report.isoformat()}"
    )

    try:

        while True:

            now = datetime.now(tz)

            # -----------------------------------------
            # Messung
            # -----------------------------------------

            if now >= next_sample:

                run_once(
                    config,
                    conn,
                    tz,
                )

                next_sample = (
                    next_aligned_sample(
                        datetime.now(tz),
                        interval,
                    )
                )

            # -----------------------------------------
            # täglicher Bericht
            # -----------------------------------------

            if now >= next_report:

                # Debug-Logs nur einmal täglich

                archive_debug_logs(
                    config,
                    conn,
                    tz,
                )

                start = (
                    next_report
                    - timedelta(days=1)
                )

                end = next_report

                generate_pdf(
                    conn,
                    start,
                    end,
                    config.get(
                        "timezone",
                        "Europe/Berlin",
                    ),
                )

                next_report += (
                    timedelta(days=1)
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print(
            "\nBeendet."
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()