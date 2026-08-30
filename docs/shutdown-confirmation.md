# Shutdown Confirmation Model

## Physical hosts

A local timer firing proves only that a request should have been made. The controller therefore uses two independent observations:

- network/TCP-22 response;
- persistent NUT client session on controller TCP/3493.

Result policy:

| SSH/network | NUT session | Report wording |
|---|---|---|
| gone | gone | `SHUTDOWN OBSERVED` |
| present | present | `WARNING - STILL ONLINE` in a real outage |
| present | gone | `WARNING - CONFLICTING OBSERVATION` |
| gone | present | `WARNING - CONFLICTING OBSERVATION` |
| check unavailable | any | `WARNING - CHECK INCOMPLETE` |

`ECONNREFUSED` from TCP/22 still proves the remote IP stack answered and therefore counts as reachable.

## Virtual machines

The compute helper has stronger evidence because it queries libvirt directly and only marks a target confirmed when `virsh domstate` becomes exactly `shut off`. The result is signed and posted to the controller.

For a real outage, the controller accepts the VM report for the consolidated message only when its controller-side receipt timestamp is at or after the current outage start. This prevents a successful old VM test from being misreported as evidence for a new outage.

Test-mode reports may intentionally show the most recent historical VM result to validate email formatting without shutting VMs again.
