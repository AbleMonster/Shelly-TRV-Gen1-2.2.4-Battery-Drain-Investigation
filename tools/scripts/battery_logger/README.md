# Shelly TRV Gen1 Battery Logger

## Overview

The Shelly TRV Gen1 Battery Logger is designed for long-term battery drain analysis and firmware comparison.

It polls configured Shelly TRV Gen1 devices at fixed time intervals, stores the collected data in a local SQLite database, and generates a 24-hour PDF report once per day.

The logger is specifically designed to support comparisons between firmware versions where the available HTTP endpoints differ.

## Data Collection

At every regular sampling interval:

- `/status` is queried on all configured Shelly TRV Gen1 devices
- `/stats` is queried only when firmware version `2.2.4` is detected

The `/debug/log` endpoint is intentionally not queried during every sampling cycle.

Instead, it is collected only once per day at the report time.

This is intentional because requesting `/debug/log` itself generates additional network traffic and debug activity on the TRV, which could influence battery drain measurements.

## Default Schedule

By default:

- measurement interval: every 30 minutes
- daily report time: 08:00
- timezone: `Europe/Berlin`

The measurement times are aligned to fixed clock intervals, for example:

```text
08:00
08:30
09:00
09:30
```

This ensures that all configured TRVs are compared at approximately the same points in time.

## Collected Data

The logger currently records values including:

- firmware version
- firmware build string
- battery percentage
- battery voltage
- charger state
- device uptime
- Wi-Fi RSSI
- `/status` response status
- `/stats` response status
- complete raw `/status` response
- complete raw `/stats` response

For firmware `2.2.4`, `/stats` can additionally provide diagnostic values such as:

- `reboot_counter`
- `reconnect_counter`
- `uptime_counter`
- `steps_counter`
- `steps/hour`
- `sleep_ratio`
- `desired_beacon_skip`
- `real_beacon_skip`
- `beacon_err_counter`
- `beacon_rx_count`
- `beacon_rx_missed_count`
- multicast statistics
- unicast statistics

## Installation

Open PowerShell in the logger directory:

```powershell
cd <folder>
```

Install the required Python packages:

```powershell
python -m pip install -r requirements.txt
```

The required packages are:

```text
reportlab>=4.0
tzdata>=2025.1
```

## Configuration

Edit `config.json` and add the desired TRV devices.

Example:

```json
{
  "timezone": "Europe/Berlin",
  "sample_interval_minutes": 30,
  "report_hour": 8,
  "report_minute": 0,
  "http_timeout_seconds": 15,
  "devices": [
    {
      "name": "TRV .228",
      "ip": "192.168.178.228"
    },
    {
      "name": "TRV .229",
      "ip": "192.168.178.88"
    }
  ]
}
```

The device name is only used as a readable identifier in the database and reports.

## Start the Logger

Run:

```powershell
python trv_battery_logger.py
```

A measurement is performed immediately after startup.

After that, measurements continue automatically according to the configured interval.

Example console output:

```text
[2026-10-10T11:06:18+02:00] Messrunde
  TRV .228 (192.168.178.228): FW=2.2.4 Bat=99% V=3.863V Uptime=19979s stats=OK
  TRV .229 (192.168.178.88): FW=2.2.4 Bat=91% V=3.795V Uptime=128391s stats=OK

Nächste Messung: 2026-10-10T11:30:00+02:00
Nächster 24-h-Bericht: 2026-10-11T08:00:00+02:00
```

The logger continues running until it is stopped manually.

To stop it:

```text
Ctrl + C
```

Existing measurement data is retained in the SQLite database and is not lost when the logger is restarted.

## Firmware Detection

The firmware version is read directly from the `/status` response:

```text
fw_info.fw
```

Example:

```text
20240619-130912/v2.2.4@ee290818
```

The logger extracts:

```text
2.2.4
```

from this value.

If firmware `2.2.4` is detected, the logger additionally queries:

```text
/stats
```

For earlier firmware versions, `/stats` is not requested.

This is important because `/stats` is only available on firmware versions where that endpoint is implemented.

## Debug Log Handling

The endpoint:

```text
/debug/log
```

is queried only once per day.

The returned HTML log is stored separately in:

```text
debug_logs/
```

Example:

```text
debug_logs/
2026-10-11_080000_TRV_.228_192-168-178-228.html
```

Reducing the number of `/debug/log` requests helps minimize additional network activity caused by the measurement system itself.

## Database

All measurement data is stored in:

```text
trv_logger.sqlite3
```

The SQLite database contains both extracted values and the original raw responses.

This allows later analysis even if additional fields become relevant during the investigation.

The main measurement table is:

```text
samples
```

A separate table is used for daily debug log snapshots:

```text
debug_snapshots
```

## PDF Reports

A PDF report is generated once every 24 hours.

Reports are stored in:

```text
reports/
```

Example:

```text
reports/
TRV_Battery_Report_2026-10-10_0800_bis_2026-10-11_0800.pdf
```

The report includes the recorded measurements for each TRV during the previous 24-hour period.

For firmware `2.2.4`, selected `/stats` values are also included in the report.

## Measurement Methodology

For battery drain comparisons, the battery percentage alone should not be treated as an exact measure of remaining battery capacity.

The logger therefore stores both:

```text
battery percentage
battery voltage
```

This allows later analysis of:

```text
% loss per day
mV loss per day
battery voltage trend
uptime-normalized statistics
beacon statistics per hour
reconnects per day
missed beacons per hour
```

This is especially important when comparing TRVs with batteries of different age or condition.

## Important

For reliable long-term measurements:

- keep the logger running continuously
- prevent the computer from entering sleep mode
- avoid unnecessary manual requests to the TRVs during the test
- keep the TRVs under comparable network and operating conditions
- use the TRV's own `/status` battery value as the primary battery percentage reference
- evaluate battery voltage together with battery percentage

The logger is intended to provide a reproducible dataset for comparing Shelly TRV Gen1 battery drain behavior across firmware versions and firmware patches.