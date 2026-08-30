#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal report-only HMAC API for compute VM shutdown results.

There are deliberately NO remote-control endpoints in this service.
"""

import hashlib
import hmac
import json
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LISTEN = os.environ.get("CONTROLLER_LISTEN", "127.0.0.1")
PORT = int(os.environ.get("CONTROLLER_PORT", "8081"))
ALLOWED_SOURCE_IP = os.environ.get("COMPUTE_IP", "192.0.2.20")
EXPECTED_SOURCE = os.environ.get("COMPUTE_NAME", "compute-node")

SECRET_FILE = Path("/etc/ups-controller/report-secret")
REPORT_FILE = Path("/var/lib/ups-dashboard/vm-shutdown-report.json")
MAX_BODY = 65536
MAX_SKEW = 120
NONCE_TTL = 300

seen_nonces = {}
nonce_lock = threading.Lock()


def load_secret():
    secret = SECRET_FILE.read_text().strip().encode("utf-8")
    if len(secret) < 32:
        raise RuntimeError("report secret is too short")
    return secret


def clean_nonces(now):
    expired = [nonce for nonce, ts in seen_nonces.items() if now - ts > NONCE_TTL]
    for nonce in expired:
        seen_nonces.pop(nonce, None)


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if payload.get("event") != "vm_shutdown":
        raise ValueError("unsupported event")
    if payload.get("source") != EXPECTED_SOURCE:
        raise ValueError("unexpected source")
    for key in ("targets", "confirmed", "remaining"):
        value = payload.get(key)
        if not isinstance(value, list) or not all(isinstance(x, str) and 0 < len(x) <= 256 for x in value):
            raise ValueError(f"invalid {key}")
        if len(value) > 256:
            raise ValueError(f"too many entries in {key}")
    targets = set(payload["targets"])
    if not set(payload["confirmed"]).issubset(targets):
        raise ValueError("confirmed contains non-target")
    if not set(payload["remaining"]).issubset(targets):
        raise ValueError("remaining contains non-target")


def atomic_store(payload):
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["received_at"] = int(time.time())
    temp = REPORT_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.chmod(temp, 0o600)
    os.replace(temp, REPORT_FILE)


class Handler(BaseHTTPRequestHandler):
    server_version = "ups-controller/1"

    def log_message(self, fmt, *args):
        print("controller-api:", fmt % args, flush=True)

    def reply_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.reply_json(200, {"ok": True, "service": "ups-controller-api"})
        else:
            self.reply_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/api/v1/report/vm-shutdown":
            self.reply_json(404, {"ok": False, "error": "not found"})
            return

        if self.client_address[0] != ALLOWED_SOURCE_IP:
            self.reply_json(403, {"ok": False, "error": "source not allowed"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_BODY:
            self.reply_json(413, {"ok": False, "error": "invalid body length"})
            return

        timestamp_text = self.headers.get("X-UPS-Timestamp", "")
        nonce = self.headers.get("X-UPS-Nonce", "")
        supplied = self.headers.get("X-UPS-Signature", "")

        try:
            timestamp = int(timestamp_text)
        except ValueError:
            self.reply_json(400, {"ok": False, "error": "bad timestamp"})
            return

        now = int(time.time())
        if abs(now - timestamp) > MAX_SKEW:
            self.reply_json(401, {"ok": False, "error": "timestamp outside allowed skew"})
            return
        if not (16 <= len(nonce) <= 128):
            self.reply_json(400, {"ok": False, "error": "bad nonce"})
            return

        body = self.rfile.read(length)
        secret = load_secret()
        signed = timestamp_text.encode() + b"\n" + nonce.encode() + b"\n" + body
        expected = hmac.new(secret, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            self.reply_json(401, {"ok": False, "error": "bad signature"})
            return

        # Check and reserve the nonce only after authentication so an unauthenticated
        # peer cannot fill the replay cache. Locking closes a same-nonce thread race.
        with nonce_lock:
            clean_nonces(now)
            if nonce in seen_nonces:
                self.reply_json(409, {"ok": False, "error": "replayed request"})
                return
            seen_nonces[nonce] = now

        try:
            payload = json.loads(body.decode("utf-8"))
            validate_payload(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self.reply_json(400, {"ok": False, "error": str(exc)})
            return

        atomic_store(payload)
        print(
            f"Accepted VM shutdown report from {payload['source']}: "
            f"{len(payload['confirmed'])}/{len(payload['targets'])} VMs confirmed shut down",
            flush=True,
        )
        self.reply_json(200, {"ok": True})


def main():
    load_secret()  # fail closed at startup
    server = ThreadingHTTPServer((LISTEN, PORT), Handler)
    print(f"UPS controller report API listening on {LISTEN}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
