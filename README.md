# Pi NUT Monitoring & Staged Shutdown Reference Guide

A security-conscious reference design for using **Network UPS Tools (NUT)** with a small Linux controller such as a Raspberry Pi, multiple Linux Windows clients, optional libvirt/KVM virtual machines, email alerts, a lightweight dashboard, and staged graceful shutdown.

The project (Pi Nut) deliberately separates **UPS observation** from **host shutdown**. The central controller reads UPS state and coordinates reporting; each protected Linux or Windows host shuts **itself** down through a tightly constrained local systemd path. The controller does not use UPS output-off commands as part of automated outage handling.

> **Vibe-coded, then tested on real hardware:** this project was developed iteratively with an AI coding assistant. Generated code was not treated as correct merely because it looked plausible: the design was exercised on real hardware, failures were investigated, and the architecture was changed when testing exposed unsafe or unreliable assumptions. This is still a community reference project, not a formally audited safety product.

<img width="1440" height="1256" alt="image" src="https://github.com/user-attachments/assets/00278495-98ea-4bc7-a9c2-15cac382bcba" />

## Read this first

This software can participate in shutting down computers. **There is no warranty. You must test it in your own environment before relying on it.** Hardware, firmware, NUT drivers, SELinux policy, systemd packaging, networking and UPS behaviour differ between installations.

The repository is intentionally sanitized. It contains no real hostnames, personal IP addresses, MAC addresses, email addresses, passwords, NUT credentials, SMTP App Passwords, SSH keys or HMAC secrets. Example addresses use the documentation-only `192.0.2.0/24` range.

For an AI assistant or a new maintainer, start with **[AI_CONTEXT.md](AI_CONTEXT.md)**. It describes the intended architecture, invariants, safety rules, event sequence, known failure modes and what should not be casually rewritten.

## What this design does

```text
                         USB
                    ┌──────────┐
                    │   UPS    │
                    └────┬─────┘
                         │
              ┌──────────▼──────────┐
              │ Linux controller    │
              │ NUT driver + upsd   │
              │ dashboard           │
              │ email queue         │
              │ report-only API     │
              │ NO local upsmon     │
              └───────┬───────┬─────┘
                      │3493   │3493
               ┌──────▼───┐ ┌─▼──────────┐
               │ compute  │ │ storage    │
               │ NUT      │ │ NUT        │
               │ 3m VMs   │ │ 5m host    │
               │ 4m host  │ │ shutdown   │
               └──────────┘ └────────────┘
```

Reference outage sequence:

- **0:00** — controller observes `OB` and sends one immediate power-failure alert.
- **3:00** — compute host snapshots all currently-running libvirt VMs and requests graceful VM shutdown (guest-agent first, ACPI fallback).
- **4:00** — compute host requests its own local graceful poweroff.
- **5:00** — storage host requests its own local graceful poweroff.
- **6:30** — if the UPS is still `OB`, the controller sends one consolidated shutdown report.
- **mains return** — controller sends a restoration report. This reference design does not automatically wake hosts back up.

The 6:30 report is deliberately conservative. A physical host is reported as **shutdown observed** only when two controller-side signals agree: its SSH/TCP stack is no longer reachable and its persistent NUT client connection is gone. VM shutdown can be reported as **confirmed** from an authenticated libvirt result produced by the compute host.

## Tested development profile

The design evolved through real testing on:

- Red Hat Enterprise Linux **9** family client(s);
- Red Hat Enterprise Linux **10** client(s);
- Raspberry Pi / Debian-family Linux used as the central USB NUT controller;
- Dynamix **UPSD1200 Defender** 1200 VA / 720 W UPS;
- USB device observed as `0665:5161` with NUT `nutdrv_qx` / Voltronic-QS-compatible behaviour;
- libvirt / QEMU / KVM Linux and Windows guests;
- Windows QEMU Guest Agent for agent-assisted graceful shutdown.

This is a compatibility record, **not** a claim that every release, UPS firmware or similarly named model will behave identically.

## Why the automation does not issue UPS shutdown/output commands

NUT exposes powerful commands that can affect the UPS itself. This project intentionally does **not** automate commands such as:

```text
upsmon -c fsd
upsdrvctl shutdown
load.off
load.on
shutdown.return
shutdown.stayoff
driver.killpower
```

A UPS output action is not equivalent to shutting down one operating system: it can remove power from every device connected to that UPS. During early development an experimental shutdown/control path produced unexpected shutdown/power behaviour with a much larger blast radius than intended. The surviving project notes do not reliably attribute that incident to one specific UPS command, so this repository does not pretend otherwise. The lesson was clear enough: **keep host shutdown local and keep automated UPS control out of the outage path.**

The one intentionally supported UPS instant command is the narrowly-scoped quick internal battery self-test:

```text
test.battery.start.quick
```

Even that is guarded by preconditions, a dedicated NUT identity allowed only that command, and observation of the UPS returning to `OL`. If your UPS reports different states during self-test, do not enable unattended tests until you have verified its behaviour.

## Security model

The practical security goals are least privilege, narrow trust boundaries and failure isolation:

- the controller's `nut-monitor`/`upsmon` service is **masked**, not merely disabled;
- NUT clients cannot ask the controller to cut UPS output;
- RHEL clients keep SELinux enforcing;
- confined NUT code does not receive broad `sudo` access;
- NUT writes only a small request file under `/run/nut`;
- root-owned systemd services validate request type, ownership, mode and reason before acting;
- VM result reporting is one-way and HMAC-authenticated; the API has **no control endpoint**;
- report API access is restricted by source address/firewall and timestamp/nonce replay checks;
- the dashboard/controller are supplemental — host shutdown does not depend on them;
- secrets are stored outside Git and example values are non-secret placeholders;
- systemd service sandboxes are used where practical;
- direct UPS output-control commands are excluded from automation.

See [SECURITY.md](SECURITY.md). The project has had security-focused design/testing, but it has **not** received a professional independent security audit.

## Repository map

```text
AI_CONTEXT.md                   LLM/maintainer handoff; read this first
README.md
SECURITY.md
LICENSE                         GNU GPL v3 text

configs/common/                 site/mail examples
configs/pi/etc/nut/             NUT server examples
configs/pi/systemd/             controller service units
configs/rhel/etc/ups/           NUT client/upssched examples
configs/rhel/systemd/           validated host/VM request paths
firewall/                       example controller nftables rules

scripts/pi/                     dashboard/email/watcher/self-test/API/test observer
scripts/rhel/                   local poweroff, VM shutdown/reporting, warm client test

dashboard/dashboard.py          lightweight status/history dashboard
controller/controller-api.py    report-only HMAC API

docs/architecture.md
docs/installation-pi.md
docs/installation-rhel.md
docs/testing.md
docs/troubleshooting.md
docs/pitfalls.md
docs/incident-notes.md
docs/test-status.md
docs/publication-checklist.md
```

## Recommended implementation order

1. Read `AI_CONTEXT.md`, `SECURITY.md` and `docs/architecture.md`.
2. Create local site values from `configs/common/site.env.example`.
3. Make the UPS readable locally with `upsc` **without configuring shutdown**.
4. Configure `upsd`, firewall rules and one client; prove read-only monitoring first.
5. Configure all NUT clients and make sure `nut.target` itself is enabled on RHEL.
6. Configure email and dashboard; confirm they can fail without preventing local shutdown.
7. Install the request-file + systemd `.path` local shutdown mechanism.
8. Use validator/warm tests before any real shutdown test.
9. Add VM shutdown/reporting only after local host shutdown logic is understood.
10. Perform short real mains-loss tests that remain well below shutdown thresholds.
11. Perform a supervised full-duration acceptance test only when you are prepared for every protected host to shut down.

See [docs/testing.md](docs/testing.md) for the test ladder and included warm-test scripts.

## Important RHEL lessons from real testing

Two failures materially changed the design:

- A first implementation used `sudo systemctl poweroff` from the confined NUT context. The timer fired, but the command returned **126** because SELinux blocked `nut_upsmon_t` from executing `sudo`. The fix was architectural: a validated request file plus a root-owned systemd `.path`/service. SELinux remained enforcing.
- A later `upssched` helper used `hostname` without an absolute path. NUT's restricted execution environment did not contain the expected PATH, producing **127**. Production event scripts now avoid unnecessary dynamic commands and use absolute paths.

A boot-time issue was also found: `nut-monitor.service` could appear enabled through `nut.target.wants` while `nut.target` itself was disabled. Enabling `nut.target` was required for reliable monitor startup after boot.

See [docs/troubleshooting.md](docs/troubleshooting.md).

## License

This project is released under the **GNU General Public License, version 3 or (at your option) any later version — GPL-3.0-or-later**.

Commercial use is permitted by the GPL. If you distribute/convey a GPL-covered product or modified binary, you must comply with the GPL's corresponding-source and licensing obligations to recipients. The GPL does not replace any other laws or regulatory obligations that apply to your product. This paragraph is a practical summary, not legal advice; the `LICENSE` file is authoritative.

## No warranty

This project is provided **without warranty of any kind**. UPS automation can cause downtime, data loss or abrupt power removal when misconfigured. Test the sanitized reference code against your own hardware and operating systems before relying on it.
