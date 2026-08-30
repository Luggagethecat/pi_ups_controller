# RHEL Client Installation

This reference was developed across RHEL 9-family and RHEL 10 systems with SELinux enforcing.

## 1. Install NUT client tools

Use the NUT packages appropriate to your enabled RHEL repositories. Confirm the actual service names on your release.

Set NUT to netclient mode using the example `configs/rhel/etc/ups/nut.conf.example`, and adapt `upsmon.conf.example` with a dedicated client identity/password created on the controller.

## 2. Critical boot-time check: enable `nut.target`

A real test found that `nut-monitor.service` could appear enabled through `nut.target.wants` while `nut.target` itself was disabled. Explicitly enable the target:

```bash
systemctl enable --now nut.target
systemctl is-enabled nut.target
systemctl is-active nut.target
systemctl is-active nut-monitor
```

Also verify a persistent client connection exists on the controller.

## 3. Choose compute or storage `upssched` policy

Compute:

```text
180s -> VM shutdown request
240s -> local host poweroff request
```

Storage:

```text
300s -> local host poweroff request
```

Install the corresponding `upssched-*.conf.example` as your local `upssched.conf` after review.

## 4. Install validated local host shutdown path

Install:

```text
/usr/local/sbin/ups-local-poweroff
/etc/systemd/system/ups-local-poweroff.service
/etc/systemd/system/ups-local-poweroff.path
```

The NUT helper writes `/run/nut/local-poweroff-request`. The root service validates it before calling `systemctl --no-block poweroff`.

Keep SELinux enforcing. If `/run/nut` labels are wrong, fix the labeling/packaging issue rather than granting broad privileges.

## 5. Compute node: VM path

Install:

```text
/usr/local/sbin/upssched-cmd-compute
/usr/local/sbin/ups-vm-shutdown
/usr/local/sbin/ups-report-vm-result
/etc/systemd/system/ups-vm-shutdown.service
/etc/systemd/system/ups-vm-shutdown.path
```

The root VM service targets `qemu:///system`, snapshots the domains running at the moment the request begins, requests guest-agent shutdown first and ACPI as fallback, and requires `domstate == shut off` to mark a VM confirmed.

For Windows guests, install/enable QEMU Guest Agent if you expect agent mode to work. Confirm with `virsh qemu-agent-command` or the tools appropriate to your version before outage testing.

## 6. Compute node: HMAC report secret

Store the controller report secret as:

```text
/etc/nut/ups-report-secret
```

Recommended ownership/mode:

```text
root:root 0600
```

The reporter POSTs to the controller report-only API. There is no inbound listener required on the compute node.

## 7. Restricted NUT execution environment

Treat `upssched` event scripts as running in a minimal/restricted environment. A development test failed with exit `127` because `hostname` was called without a usable PATH. Use absolute paths for operational commands and avoid unnecessary external commands.

## 8. Validate before enabling live `.path` actions

The validator supports `--validate-only`, but once a `.path` watcher is active, creating the real request path is a real poweroff trigger. Follow `docs/testing.md` exactly; do not improvise by manually calling the live `shutdown-timer` event.
