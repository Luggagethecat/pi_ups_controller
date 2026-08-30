#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

import html
import json
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPS = "ups@localhost"
DB = "/var/lib/ups-dashboard/ups.db"

LISTEN = os.environ.get("DASHBOARD_LISTEN", "127.0.0.1")
PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))

STATUS_INTERVAL = 10
SAMPLE_INTERVAL = 60
RETENTION_DAYS = 90

lock = threading.Lock()

current = {
    "ok": False,
    "status": "UNKNOWN",
    "battery_charge": None,
    "battery_voltage": None,
    "input_voltage": None,
    "output_voltage": None,
    "load": None,
    "frequency": None,
    "updated": None,
}

previous_status = None
outage_started = None
comm_failed_since = None
comm_failure_reported = False


def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            ts INTEGER PRIMARY KEY,
            status TEXT,
            battery_charge REAL,
            battery_voltage REAL,
            input_voltage REAL,
            output_voltage REAL,
            load REAL,
            frequency REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            event TEXT NOT NULL,
            status TEXT,
            details TEXT
        )
    """)

    conn.commit()
    return conn


def log_event(event, status="", details=""):
    now = int(time.time())

    conn = db()
    conn.execute(
        "INSERT INTO events(ts,event,status,details) VALUES(?,?,?,?)",
        (now, event, status, details)
    )
    conn.commit()
    conn.close()

    print(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        event,
        status,
        details,
        flush=True
    )


def read_ups():
    result = subprocess.run(
        ["/usr/bin/upsc", UPS],
        capture_output=True,
        text=True,
        timeout=5
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "upsc failed")

    values = {}

    for line in result.stdout.splitlines():
        if ": " not in line:
            continue

        key, value = line.split(": ", 1)
        values[key] = value.strip()

    def number(name):
        try:
            return float(values.get(name))
        except (TypeError, ValueError):
            return None

    return {
        "ok": True,
        "status": values.get("ups.status", "UNKNOWN"),
        "battery_charge": number("battery.charge"),
        "battery_voltage": number("battery.voltage"),
        "input_voltage": number("input.voltage"),
        "output_voltage": number("output.voltage"),
        "load": number("ups.load"),
        "frequency": number("output.frequency"),
        "updated": int(time.time()),
    }


def has_flag(status, flag):
    return flag in status.split()


def monitor():
    global current
    global previous_status
    global outage_started
    global comm_failed_since
    global comm_failure_reported

    last_sample = 0
    last_cleanup = 0

    while True:
        now = int(time.time())

        try:
            reading = read_ups()

            with lock:
                current = reading.copy()

            status = reading["status"]

            # Communication restored
            if comm_failed_since is not None:
                duration = now - comm_failed_since

                if comm_failure_reported:
                    log_event(
                        "COMM_RESTORED",
                        status,
                        f"Communication restored after {duration} seconds"
                    )

                comm_failed_since = None
                comm_failure_reported = False

            # Power failure starts
            if has_flag(status, "OB") and not (
                previous_status and has_flag(previous_status, "OB")
            ):
                outage_started = now

                log_event(
                    "POWER_FAILED",
                    status,
                    "UPS switched to battery"
                )

            # Power restored
            if (
                previous_status
                and has_flag(previous_status, "OB")
                and not has_flag(status, "OB")
                and has_flag(status, "OL")
            ):
                duration = 0

                if outage_started:
                    duration = now - outage_started

                log_event(
                    "POWER_RESTORED",
                    status,
                    f"Outage duration {duration} seconds"
                )

                outage_started = None

            # Low battery
            if has_flag(status, "LB") and not (
                previous_status and has_flag(previous_status, "LB")
            ):
                log_event(
                    "LOW_BATTERY",
                    status,
                    "UPS reported low battery"
                )

            previous_status = status

            # Historical sample every minute
            if now - last_sample >= SAMPLE_INTERVAL:
                conn = db()

                conn.execute("""
                    INSERT OR REPLACE INTO samples
                    (
                        ts,
                        status,
                        battery_charge,
                        battery_voltage,
                        input_voltage,
                        output_voltage,
                        load,
                        frequency
                    )
                    VALUES(?,?,?,?,?,?,?,?)
                """, (
                    now,
                    reading["status"],
                    reading["battery_charge"],
                    reading["battery_voltage"],
                    reading["input_voltage"],
                    reading["output_voltage"],
                    reading["load"],
                    reading["frequency"],
                ))

                conn.commit()
                conn.close()

                last_sample = now

            # Delete old minute-by-minute samples once per day.
            if now - last_cleanup >= 86400:
                cutoff = now - (RETENTION_DAYS * 86400)

                conn = db()
                conn.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
                conn.commit()
                conn.close()

                last_cleanup = now

        except Exception as exc:

            with lock:
                current = {
                    "ok": False,
                    "status": "COMMUNICATION ERROR",
                    "battery_charge": None,
                    "battery_voltage": None,
                    "input_voltage": None,
                    "output_voltage": None,
                    "load": None,
                    "frequency": None,
                    "updated": now,
                }

            if comm_failed_since is None:
                comm_failed_since = now

            # Don't alert on a momentary polling failure.
            if (
                not comm_failure_reported
                and now - comm_failed_since >= 30
            ):
                log_event(
                    "COMM_LOST",
                    "",
                    f"Unable to read UPS: {exc}"
                )

                comm_failure_reported = True

        time.sleep(STATUS_INTERVAL)


def format_status(status):
    if status == "COMMUNICATION ERROR":
        return "Offline"

    labels = {
        "OL": "Online",
        "OB": "On Battery",
        "LB": "Low Battery",
        "CAL": "Battery Test",
        "BYPASS": "Bypass",
        "FSD": "Forced Shutdown",
    }

    return " / ".join(
        labels.get(flag, flag)
        for flag in status.split()
    )


def format_value(value, suffix=""):
    if value is None:
        return "—"

    if isinstance(value, float) and value.is_integer():
        value = int(value)

    return f"{value}{suffix}"


def make_svg(rows, field, title, suffix=""):
    points = []

    for row in rows:
        value = row[field]

        if value is not None:
            points.append((row["ts"], value))

    if len(points) < 2:
        return f"<p>No history available yet for {html.escape(title)}.</p>"

    width = 900
    height = 220
    pad = 35

    min_t = min(x[0] for x in points)
    max_t = max(x[0] for x in points)

    values = [x[1] for x in points]
    min_v = min(values)
    max_v = max(values)

    if max_v == min_v:
        max_v += 1
        min_v -= 1

    def sx(t):
        if max_t == min_t:
            return pad

        return pad + (
            (t - min_t) / (max_t - min_t)
        ) * (width - pad * 2)

    def sy(v):
        return (
            height - pad -
            ((v - min_v) / (max_v - min_v))
            * (height - pad * 2)
        )

    line = " ".join(
        f"{sx(t):.1f},{sy(v):.1f}"
        for t, v in points
    )

    return f"""
    <div class="chart">
      <h3>{html.escape(title)}</h3>

      <svg viewBox="0 0 {width} {height}"
           role="img"
           aria-label="{html.escape(title)}">

        <line x1="{pad}" y1="{pad}"
              x2="{pad}" y2="{height-pad}"
              class="axis"/>

        <line x1="{pad}" y1="{height-pad}"
              x2="{width-pad}" y2="{height-pad}"
              class="axis"/>

        <polyline
            points="{line}"
            class="graphline"
            fill="none"/>

        <text x="{pad}" y="20" class="label">
          {min_v:.1f}{html.escape(suffix)}
        </text>

        <text x="{width-pad}" y="20"
              text-anchor="end"
              class="label">
          {max_v:.1f}{html.escape(suffix)}
        </text>
      </svg>
    </div>
    """


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        return

    def do_GET(self):

        if self.path == "/api/current":

            with lock:
                payload = current.copy()

            data = json.dumps(payload).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path != "/":
            self.send_error(404)
            return

        conn = db()
        conn.row_factory = sqlite3.Row

        since = int(time.time()) - 86400

        history = conn.execute("""
            SELECT *
            FROM samples
            WHERE ts >= ?
            ORDER BY ts
        """, (since,)).fetchall()

        events = conn.execute("""
            SELECT *
            FROM events
            ORDER BY ts DESC
            LIMIT 25
        """).fetchall()

        conn.close()

        with lock:
            c = current.copy()

        good = c["ok"] and has_flag(c["status"], "OL") \
               and not has_flag(c["status"], "OB")

        status_class = "good" if good else "bad"

        event_rows = ""

        for event in events:
            stamp = datetime.fromtimestamp(
                event["ts"]
            ).strftime("%Y-%m-%d %H:%M:%S")

            event_rows += f"""
              <tr>
                <td>{html.escape(stamp)}</td>
                <td>{html.escape(event["event"])}</td>
                <td>{html.escape(event["status"] or "")}</td>
                <td>{html.escape(event["details"] or "")}</td>
              </tr>
            """

        if not event_rows:
            event_rows = """
              <tr>
                <td colspan="4">No events recorded yet.</td>
              </tr>
            """

        voltage_chart = make_svg(
            history,
            "battery_voltage",
            "Battery voltage — last 24 hours",
            " V"
        )

        input_chart = make_svg(
            history,
            "input_voltage",
            "Mains input voltage — last 24 hours",
            " V"
        )

        load_chart = make_svg(
            history,
            "load",
            "UPS load — last 24 hours",
            "%"
        )

        page = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UPS Dashboard</title>

<style>
body {{
    font-family: system-ui, sans-serif;
    max-width: 1100px;
    margin: auto;
    padding: 20px;
    background: #11151a;
    color: #e7edf3;
}}

h1, h2, h3 {{
    margin-top: 0;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(170px,1fr));
    gap: 12px;
}}

.card, .chart {{
    background: #1c232b;
    border: 1px solid #36414c;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}}

.value {{
    font-size: 1.8rem;
    font-weight: bold;
}}

.good {{
    color: #6ee787;
}}

.bad {{
    color: #ff7b72;
}}

.small {{
    color: #9da7b1;
    font-size: .9rem;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

td, th {{
    border-bottom: 1px solid #36414c;
    padding: 8px;
    text-align: left;
}}

svg {{
    width: 100%;
    height: auto;
}}

.axis {{
    stroke: #64717d;
    stroke-width: 1;
}}

.graphline {{
    stroke: #9ecbff;
    stroke-width: 2;
}}

.label {{
    fill: #c9d1d9;
    font-size: 14px;
}}
</style>
</head>

<body>

<h1>UPS Dashboard</h1>

<div class="grid">

<div class="card">
<div class="small">UPS Status</div>
<div class="value {status_class}">
{html.escape(format_status(c["status"]))}
</div>
</div>

<div class="card">
<div class="small">Battery</div>
<div class="value">
{format_value(c["battery_charge"], "%")}
</div>
</div>

<div class="card">
<div class="small">Battery Voltage</div>
<div class="value">
{format_value(c["battery_voltage"], " V")}
</div>
</div>

<div class="card">
<div class="small">UPS Load</div>
<div class="value">
{format_value(c["load"], "%")}
</div>
</div>

<div class="card">
<div class="small">Input Voltage</div>
<div class="value">
{format_value(c["input_voltage"], " V")}
</div>
</div>

<div class="card">
<div class="small">Output Voltage</div>
<div class="value">
{format_value(c["output_voltage"], " V")}
</div>
</div>

</div>

<p class="small">
Dashboard refreshes every 10 seconds.
Historical measurements are stored every 60 seconds.
</p>

{voltage_chart}
{input_chart}
{load_chart}

<div class="card">
<h2>Recent UPS Events</h2>

<table>
<thead>
<tr>
<th>Time</th>
<th>Event</th>
<th>Status</th>
<th>Details</th>
</tr>
</thead>

<tbody>
{event_rows}
</tbody>
</table>

</div>

</body>
</html>
"""

        data = page.encode()

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8"
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main():
    db().close()

    worker = threading.Thread(
        target=monitor,
        daemon=True
    )

    worker.start()

    server = ThreadingHTTPServer(
        (LISTEN, PORT),
        Handler
    )

    print(
        f"UPS dashboard listening on "
        f"http://{LISTEN}:{PORT}",
        flush=True
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
