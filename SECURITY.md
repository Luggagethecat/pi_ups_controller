# Security Policy and Design Notes

## Scope

This repository is a reference implementation for UPS monitoring and graceful shutdown. It is **security-conscious**, but it is not a formally audited or certified product. Treat any change to shutdown, privilege, authentication, networking or UPS command handling as security-sensitive.

## Threat model

The main risks considered are:

- an unprivileged NUT process obtaining arbitrary root command execution;
- an attacker on the LAN submitting false VM-shutdown reports;
- accidental or malicious UPS output control causing abrupt power loss to multiple devices;
- stale/replayed authenticated messages;
- secrets being committed to source control;
- false-positive reporting that claims a host shut down when it did not;
- dashboard/email/controller failure becoming a dependency of the actual shutdown path.

## Practical controls

The reference design uses:

- SELinux enforcing on RHEL;
- no broad `sudo` grant to NUT;
- root-owned systemd `.path`/service privilege boundaries;
- request-file validation: regular file, not symlink, expected UID/GID, `0600`, allow-listed reason;
- atomic rename/write patterns for request and report files;
- report-only HMAC API, source-IP restriction, timestamp skew and nonce replay protection;
- firewall allow-listing for NUT and report API;
- local-only/default-loopback binds for public examples;
- separate service users for dashboard/controller work;
- systemd hardening (`NoNewPrivileges`, `ProtectSystem`, `ProtectHome`, restricted writable paths);
- no direct automated UPS output-off commands;
- no secrets in Git.

## Secrets

Never commit:

- real NUT client or command-user passwords;
- SMTP credentials or Gmail App Passwords;
- HMAC report secret;
- SSH private keys;
- production `site.env` / `mail.env` if they reveal sensitive topology;
- backup archives containing `/etc/nut` or `/etc/postfix`.

Generate strong independent secrets locally. The HMAC secret should be random and readable only by the services that require it.

## HMAC limitation

HMAC authenticates and protects integrity of the VM report. It does **not encrypt** the JSON body. If VM names/status are sensitive on your network, add HTTPS/mTLS or a trusted tunnel. Do not bolt a control endpoint onto the existing report API and assume HMAC alone makes remote shutdown safe.

## Reporting security issues

If publishing this repository publicly, enable private vulnerability reporting in the hosting platform if available. Avoid posting real credentials, network topology or exploit details that expose a live system.

## No warranty / local responsibility

Every deployment is responsible for its own firewalling, account permissions, SELinux policy, UPS compatibility, power budget, shutdown timings, recovery plan and local regulatory requirements. The presence of security controls in this repository is not a guarantee of suitability for any environment.
