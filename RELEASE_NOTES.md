# Public Reference Release Notes

This package is a sanitized, GitHub-ready reference reconstructed from an iteratively developed and real-hardware-tested NUT deployment.

Compared with the first documentation draft, this public package incorporates later development work:

- staged libvirt VM shutdown before compute-host poweroff;
- QEMU Guest Agent / ACPI fallback behaviour;
- HMAC-authenticated report-only controller API with replay protection;
- conservative dual-signal physical-host observation;
- one consolidated prolonged-outage report instead of separate threshold spam;
- safe warm-test scripts for temporarily dropping one NUT client connection without shutting anything down;
- documentation of the RHEL `nut.target` boot gotcha;
- documentation of restricted NUT PATH exit 127;
- confirmation that the request-file/systemd local physical shutdown path was exercised end-to-end during development;
- GPL-3.0-or-later licensing and a public-release PII/secret/forbidden-command scanner.

The public genericized tree received syntax/static/offline logic checks after sanitization, but **was not reinstalled end-to-end on the original production hardware after its addresses/names were replaced with public examples**. Treat this as a reference and repeat the test ladder locally.
