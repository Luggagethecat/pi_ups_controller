# Troubleshooting

## `upssched ... returned 126`

If the timer fires but the old script used `sudo` and returns 126, inspect SELinux:

```bash
ausearch -m AVC,USER_AVC -ts recent
```

A denial where `nut_upsmon_t` tries to execute `sudo_exec_t` means the privilege model is wrong. Use the request-file + systemd path design. Keep SELinux enforcing and do not blindly generate an `audit2allow` module.

## `upssched ... returned 127`

A development event script used `hostname` without an absolute path. NUT's restricted event environment did not have the expected PATH. Use absolute executable paths and remove nonessential command discovery from event scripts.

## `nut-monitor` is enabled but inactive after reboot

Check the target itself:

```bash
systemctl is-enabled nut.target
systemctl is-active nut.target
systemctl is-enabled nut-monitor
systemctl is-active nut-monitor
```

If appropriate for your RHEL packaging:

```bash
systemctl enable --now nut.target
```

Then verify the controller sees the persistent TCP/3493 session.

## Controller self-test says `nut-monitor` is active

The controller is intentionally not a shutdown client. Stop and mask the service:

```bash
systemctl stop nut-monitor.service
systemctl mask nut-monitor.service
```

Confirm the NUT driver and server remain active.

## Warm test says NUT disconnected but host reachable

That is the expected test state. It proves the controller refuses to treat loss of one NUT session as proof that the physical host is shut down.

## `ss` path differs on RHEL

The warm client uses `command -v ss` because some systems expose it as `/sbin/ss` rather than `/usr/bin/ss`. Production NUT event handlers avoid this type of PATH dependency where possible.

## Windows VM ignores graceful shutdown

Install and enable QEMU Guest Agent in the guest, then verify the libvirt channel is connected. The compute shutdown helper tries agent mode first and ACPI fallback second.

## Controller API rejects a valid-looking report

Check:

- source IP matches firewall/API allow-list;
- compute/controller clocks are synchronized within the allowed skew;
- the exact same HMAC secret exists on both sides;
- event/source JSON values match configured generic/local values;
- request body was not changed after signing;
- nonce has not already been used.

A repeated signed request should return `409` as replay protection.

## HMAC works but traffic is readable on the LAN

Expected: HMAC is integrity/authentication, not encryption. Add TLS/mTLS or a trusted tunnel if confidentiality is required.

## Self-test command returns an odd result

Do not trust the `upscmd` exit code alone. The test helper requires observable `CAL`/`BYPASS` and a return to plain `OL`. If your UPS reports different states, adapt only after supervised hardware testing.

## Email submission fails inside systemd sandbox

If direct mail works but the service fails around Postfix `postdrop`, inspect service sandbox/group access. The example units grant only the Postfix submission group and writable maildrop path needed by that service.
