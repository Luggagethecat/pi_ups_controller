#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Heuristic public-release scan for accidental secrets/identifiers and unsafe commands."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TEXT_SUFFIXES = {".md", ".py", ".sh", ".example", ".service", ".path", ".timer", ".conf", ""}

private_ip = re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b")
mac = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
email = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.I)
private_key = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")
password_assignment = re.compile(r"^\s*password\s*=\s*(.+?)\s*$", re.I | re.M)

# These are forbidden in executable/reference code. Documentation may name them to explain why they are excluded.
forbidden_controls = [
    "upsmon -c fsd",
    "upsdrvctl shutdown",
    "load.off",
    "load.on",
    "shutdown.return",
    "shutdown.stayoff",
    "driver.killpower",
]

issues = []
for path in ROOT.rglob("*"):
    if not path.is_file() or path == SELF or ".git" in path.parts or path.name == "LICENSE":
        continue
    if path.suffix not in TEXT_SUFFIXES and path.name not in {"README.md", "SECURITY.md", "AI_CONTEXT.md", "CONTRIBUTING.md"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    rel = path.relative_to(ROOT)

    for match in private_ip.finditer(text):
        issues.append(f"{rel}: private IPv4 address: {match.group(0)}")
    for match in mac.finditer(text):
        issues.append(f"{rel}: MAC address: {match.group(0)}")
    for match in email.finditer(text):
        domain = match.group(1).lower()
        if domain not in {"example.invalid"}:
            issues.append(f"{rel}: non-placeholder email: {match.group(0)}")
    if private_key.search(text):
        issues.append(f"{rel}: private-key material marker")
    if rel.parts[0] == "configs":
        for match in password_assignment.finditer(text):
            value = match.group(1)
            if not any(token in value for token in ("REPLACE_", "EXAMPLE_", "CHANGEME")):
                issues.append(f"{rel}: non-placeholder password assignment")

    if rel.parts[0] in {"scripts", "controller", "dashboard"}:
        lower = text.lower()
        for command in forbidden_controls:
            if command in lower:
                issues.append(f"{rel}: forbidden UPS control string in executable code: {command}")

if issues:
    print("PUBLIC RELEASE SCAN FAILED")
    for issue in issues:
        print(" -", issue)
    sys.exit(1)

print("PUBLIC RELEASE SCAN PASSED")
