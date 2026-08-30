# Security-Focused Testing

This project was developed with practical security as a design requirement, but it has not undergone a formal independent penetration test or certification.

The public tree includes `tests/public-release-scan.py`, which heuristically checks for:

- private IPv4 addresses;
- MAC addresses;
- non-placeholder email addresses;
- private-key markers;
- non-placeholder NUT password assignments;
- forbidden UPS output/control command strings in executable code.

The development process also exercised privilege boundaries, HMAC authentication/replay behaviour, service-user separation, firewall allow-listing and SELinux-enforcing shutdown paths.

Security testing should include negative cases: malformed request files, wrong ownership/mode/reason, bad HMAC, stale timestamp, replayed nonce, unexpected source address, unavailable dashboard/API/email and loss of one host-observation signal.

Do not equate "passes the scanner" with "secure." The scanner is a guard against obvious publication mistakes and accidental reintroduction of dangerous command strings; it does not understand all shell/Python/systemd/NUT semantics.
