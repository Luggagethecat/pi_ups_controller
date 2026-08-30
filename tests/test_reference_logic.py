#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline unit checks. No network, shutdown, VM or UPS command is executed."""

import importlib.machinery
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_extensionless(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


watch = load_extensionless("watch_test", ROOT / "scripts/pi/ups-power-watch")

# Physical-host observation policy.
watch.host_reachable = lambda address, port=22, attempts=3, timeout=1.5: False
watch.nut_client_connected = lambda address: False
assert watch.host_assessment("192.0.2.20")["assessment"] == "SHUTDOWN OBSERVED"

watch.host_reachable = lambda address, port=22, attempts=3, timeout=1.5: True
watch.nut_client_connected = lambda address: True
assert watch.host_assessment("192.0.2.20")["assessment"] == "WARNING - STILL ONLINE"

watch.nut_client_connected = lambda address: False
assert watch.host_assessment("192.0.2.20")["assessment"] == "WARNING - CONFLICTING OBSERVATION"

watch.nut_client_connected = lambda address: None
assert watch.host_assessment("192.0.2.20")["assessment"] == "WARNING - CHECK INCOMPLETE"

# Stale VM report must not be accepted for a later real outage.
with tempfile.TemporaryDirectory() as tmpdir:
    report = Path(tmpdir) / "report.json"
    report.write_text(
        '{"event":"vm_shutdown","received_at":100,"targets":["vm1"],"confirmed":["vm1"],"remaining":[]}'
    )
    original = watch.VM_REPORT_FILE
    watch.VM_REPORT_FILE = report
    assert watch.load_vm_report(outage_start=200) is None
    assert watch.load_vm_report(outage_start=None)["confirmed"] == ["vm1"]
    watch.VM_REPORT_FILE = original

# Controller payload validation.
controller_path = ROOT / "controller/controller-api.py"
spec = importlib.util.spec_from_file_location("controller_test", controller_path)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
controller.EXPECTED_SOURCE = "compute-node"
valid = {
    "event": "vm_shutdown",
    "source": "compute-node",
    "targets": ["vm1"],
    "confirmed": ["vm1"],
    "remaining": [],
}
controller.validate_payload(valid)

try:
    controller.validate_payload({**valid, "confirmed": ["not-a-target"]})
except ValueError:
    pass
else:
    raise AssertionError("controller accepted confirmed VM outside target set")

print("REFERENCE LOGIC TESTS PASSED")
