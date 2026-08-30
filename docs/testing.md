# Testing — Required Ladder

UPS automation should be tested progressively. Do **not** start with a full-duration outage.

## Level 0 — static/syntax checks

From a checked-out repository:

```bash
python3 -m py_compile dashboard/dashboard.py controller/controller-api.py scripts/pi/ups-power-watch scripts/pi/ups-warm-observer-test scripts/rhel/ups-report-vm-result
bash -n scripts/pi/ups-send-alert scripts/pi/nut-quick-selftest scripts/rhel/ups-vm-shutdown scripts/rhel/ups-warm-client-test
sh -n scripts/rhel/ups-local-poweroff scripts/rhel/upssched-cmd-compute scripts/rhel/upssched-cmd-storage
```

Also run ShellCheck/Bandit/other linters if available. Linters are supplemental; they do not prove safe power behaviour.

## Level 1 — read-only UPS/client checks

Controller:

```bash
upsc ups@localhost ups.status
ss -Htn state established | grep ':3493'
```

Protected host:

```bash
upsc ups@CONTROLLER_IP ups.status
systemctl is-active nut.target nut-monitor
```

Require `OL` before active tests.

## Level 2 — warm client tests (no shutdown)

Install the included scripts:

```text
controller: /usr/local/sbin/ups-warm-observer-test
clients:    /usr/local/sbin/ups-warm-client-test
```

First run `--check` on each client. It changes nothing.

Test **one client at a time**. On the controller:

```bash
/usr/local/sbin/ups-warm-observer-test baseline
/usr/local/sbin/ups-warm-observer-test observe compute
```

Only after the observer says it is ready, run on the compute host:

```bash
/usr/local/sbin/ups-warm-client-test --run
```

The client stops only `nut-monitor` for about 20 seconds, checks that the UPS remains safely `OL` every second, then restores `nut-monitor` and verifies the persistent NUT connection returned. The controller should see SSH still reachable but NUT disconnected and therefore report `WARNING - CONFLICTING OBSERVATION`.

Repeat with:

```bash
/usr/local/sbin/ups-warm-observer-test observe storage
```

and the storage client. Run `baseline` after each test. Do not proceed unless both hosts are again `REACHABLE` + `CONNECTED`.

## Level 3 — self-test under supervision

Run the quick internal battery self-test manually. Confirm your UPS does **not** report a real `OB` state during the self-test and that it returns to `OL`. Only then consider enabling the weekly timer.

## Level 4 — local request validation

Do not create a live poweroff request while `ups-local-poweroff.path` is active unless you are intentionally testing a real host shutdown.

A safe validation pattern is to disable/stop the `.path` watcher, create a correctly owned/mode request as the NUT user, invoke `/usr/local/sbin/ups-local-poweroff --validate-only`, remove the request, and re-enable the `.path`. Adapt commands carefully for local UID/GID and SELinux labels.

## Level 5 — VM-only test

On the compute host, test the VM request path separately from the physical host poweroff path. Ensure the host poweroff `.path` cannot be triggered by the VM-only test. Confirm:

- intended currently-running VMs are the target set;
- agent/ACPI requests are logged;
- all intended VMs reach `shut off`;
- result JSON is written;
- the controller accepts the HMAC report;
- replaying the exact signed request is rejected;
- VMs can be manually restarted afterward.

## Level 6 — short real mains-loss test

Disconnect mains to the UPS only long enough to prove `OB` detection, dashboard/event logging, email and `ONLINE` cancellation well **before** any shutdown threshold.

Reconnect mains and require clean `OL` state.

## Level 7 — supervised full acceptance test

Only when backups are current and you are prepared for the protected hosts to shut down:

- initiate a real sustained mains outage;
- confirm the immediate power-failure alert;
- confirm VM request near 3 minutes;
- confirm compute local shutdown near 4 minutes;
- confirm storage local shutdown near 5 minutes;
- confirm the consolidated controller report near 6:30 if still on battery;
- verify its language reflects actual evidence rather than assumed success;
- restore mains;
- confirm the restoration alert;
- manually recover systems if your design intentionally has no automatic WOL.

## Safety stop conditions

Abort an active warm/self-test if UPS status contains `OB`, `LB` or `FSD`, communication is lost, an unexpected request file appears, or a protected host becomes unreachable when it should remain up.
