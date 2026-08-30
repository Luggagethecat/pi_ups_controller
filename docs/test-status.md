# Development Test Status

This is a record of what was exercised while developing the reference design. It does not replace your own acceptance testing.

## Exercised on real hardware

- local NUT communication with the USB UPS;
- remote NUT client sessions from RHEL-family systems;
- real short mains-loss events producing `OB`, and restoration to `OL`;
- dashboard event/history logging;
- queued email notifications;
- quick internal battery self-test, with `CAL` / `BYPASS` observed and return to `OL`;
- compute and storage `upssched` timers;
- the failed SELinux/sudo path (`126`) and redesigned systemd request-file path;
- real physical local shutdown through the validated request-file path on both protected hosts;
- staged compute VM shutdown using guest-agent first with ACPI fallback;
- a Windows guest after installing QEMU Guest Agent;
- authenticated HMAC VM-shutdown report delivery;
- replay rejection (`409`) for a repeated signed request;
- controller-side NUT session detection;
- warm tests where each RHEL client's `nut-monitor` was stopped temporarily while SSH remained reachable;
- automatic restoration of `nut-monitor` after the warm test and return to a clean baseline.

## Platforms in the development environment

- RHEL 9 family;
- RHEL 10 family;
- Raspberry Pi / Debian-family controller;
- Dynamix UPSD1200 Defender, 1200 VA / 720 W;
- NUT `nutdrv_qx`, Voltronic-QS-compatible USB behaviour (`0665:5161` on the tested unit);
- libvirt/QEMU/KVM Linux and Windows guests.

## What every new installation still must prove

Your hardware/firmware/software combination can differ. Before relying on it, prove:

- the exact UPS status transitions on mains loss, restore and self-test;
- the selected shutdown timings provide enough runtime under realistic load;
- all NUT clients restart automatically after boot;
- local shutdown request validation and systemd paths behave correctly with SELinux/AppArmor in your environment;
- all important VMs respond to guest-agent or ACPI shutdown within the configured time;
- firewall rules permit required monitoring/reporting but nothing broader;
- queued email still behaves acceptably if Internet connectivity disappears during the outage;
- the final full-duration outage powers down the intended hosts gracefully and does **not** unexpectedly cut UPS output.

The sanitized public package itself should be syntax/static checked after any placeholder substitution or AI-generated edit.
