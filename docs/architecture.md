# Architecture

## Design objective

The controller owns the **UPS USB connection and observation plane**. Protected hosts own their **shutdown decision/execution plane**. This limits the consequences of a controller bug and avoids using the UPS as a remote power switch.

## Controller responsibilities

The controller runs:

- NUT USB driver (`nutdrv_qx` in the tested profile);
- `upsd` in `netserver` mode;
- a lightweight Python/SQLite dashboard;
- local Postfix or another local mail queue;
- a read-only outage watcher;
- an optional report-only HMAC API for VM shutdown results;
- an optional guarded quick internal battery self-test.

The controller intentionally does **not** run `upsmon`. Mask it:

```bash
systemctl mask nut-monitor.service
```

This makes accidental activation harder than merely disabling it.

## Protected host responsibilities

Each RHEL client runs its own NUT monitor. `upssched` arms timers when it receives `ONBATT` and cancels them on `ONLINE`.

The storage reference uses a 300-second host timer. The compute reference adds a 180-second VM timer and a 240-second host timer.

The NUT event handler cannot directly perform arbitrary root actions. Instead it atomically writes an allow-listed request under `/run/nut`. A root systemd `.path` unit detects the file and launches a validator/action service.

## Compute VM path

```text
ONBATT 180s
  -> /run/nut/vm-shutdown-request
  -> ups-vm-shutdown.path
  -> root ups-vm-shutdown.service
  -> validate request
  -> snapshot all running qemu:///system domains
  -> guest-agent shutdown; ACPI fallback
  -> confirm exact "shut off" state
  -> write result JSON
  -> HMAC report to controller
```

The VM path is intentionally independent from the later host poweroff request. If VM reporting fails, the host's local NUT shutdown timer still exists.

## Physical-host observation

The controller does not receive a privileged remote callback saying "I powered off." It observes:

1. TCP/22 reachability; and
2. presence of the host's persistent NUT TCP connection on controller port 3493.

Both gone -> shutdown observed. One gone -> conflicting observation. This avoids treating a stopped NUT service as proof that the entire server is off.

## Report API

The API is deliberately one-way:

```text
compute-node -> POST /api/v1/report/vm-shutdown -> controller
```

It accepts only signed VM result data. There is no API call for shutdown, poweroff, VM control or UPS control.

## Failure independence

The following failures should **not** prevent local host shutdown:

- dashboard down;
- email relay/Internet down;
- controller API down;
- VM report lost;
- SQLite history unavailable.

The essential shutdown chain is NUT notification -> local `upssched` timer -> validated local request -> root systemd action.
