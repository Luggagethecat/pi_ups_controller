# AI / Maintainer Context — Do Not Re-Architect Before Reading

This file is intentionally written so a small/free LLM, a new maintainer, or a future contributor can understand the project without reconstructing months of troubleshooting.

## One-sentence goal

Use NUT to **observe one USB UPS centrally while allowing each protected Linux host to shut itself down locally**, with staged VM shutdown, conservative confirmation, email/dashboard reporting, and no automated UPS output-off commands.

## Non-negotiable safety invariants

1. The central controller is a NUT **server**, not a shutdown client. Its `nut-monitor`/`upsmon` service is masked.
2. Do not add `upsmon -c fsd`, `upsdrvctl shutdown`, `load.off`, `load.on`, `shutdown.return`, `shutdown.stayoff`, `driver.killpower` or equivalent UPS-output control to automation.
3. The only intentionally approved UPS instant command in this reference is `test.battery.start.quick`, under a dedicated NUT identity limited to that command.
4. RHEL clients shut **themselves** down. They do not ask the Pi/controller to shut them down and do not expose an inbound remote-control service for this purpose.
5. Keep SELinux enforcing. Do not solve a denial by disabling SELinux or blindly running `audit2allow`.
6. NUT does not get broad sudo. Privilege crossing is through a validated request file watched by root-owned systemd units.
7. Dashboard, email and controller reporting are supplemental. A failure of any of them must not block the local NUT shutdown path.
8. Never infer successful physical shutdown from elapsed time alone. The controller uses independent observations; conflicting evidence produces a warning rather than a false success.
9. VM reporting is authenticated but not secret transport in this reference. HMAC gives integrity/authentication, not confidentiality. Use TLS/mTLS if report contents need network confidentiality.
10. Every installation must pass staged tests before a full mains-loss acceptance test.

## Reference topology and roles

Use generic names in source/documentation:

- `ups-controller` — Raspberry Pi/Debian-family host, USB-attached UPS, NUT `netserver`.
- `compute-node` — RHEL client with libvirt VMs.
- `storage-node` — RHEL client without VM staging in the reference design.

Example addresses are RFC 5737 documentation addresses only:

- controller `192.0.2.10`
- compute `192.0.2.20`
- storage `192.0.2.30`

Real deployments must replace them locally and must not commit private values or secrets.

## Event model

### Normal state

- UPS is `OL`.
- controller's NUT driver + `upsd` active.
- controller `nut-monitor` masked/inactive.
- both clients run NUT monitoring and maintain TCP connections to controller port 3493.
- compute VM shutdown `.path` and host shutdown `.path` are active.
- storage host shutdown `.path` is active.

### Real outage

`ups.status` contains `OB`:

- t=0: immediate power-failure email.
- t=180s: compute `upssched` creates VM-shutdown request.
- t=240s: compute creates local-poweroff request.
- t=300s: storage creates local-poweroff request.
- t=390s: controller re-reads UPS immediately; only if still `OB`, sends one consolidated report.

### Return to mains

When `OL` returns, `upssched` cancels pending timers. If a host already shut down, the reference design does not automatically wake it. Operator/WOL recovery can be added later as a separate feature; it must not be coupled to shutdown correctness.

## Local RHEL privilege boundary

Bad early approach:

```text
nut_upsmon_t -> sudo systemctl poweroff
```

It failed under SELinux enforcing with `upssched` return 126 / AVC denial on `sudo_exec_t`.

Current approach:

```text
NUT / upssched (unprivileged/confined)
    -> atomically writes /run/nut/local-poweroff-request
       owner nut:nut, mode 0600, exact allowed reason
    -> root systemd .path notices request
    -> root validator rejects symlink/wrong type/wrong owner/wrong mode/bad reason
    -> systemctl --no-block poweroff
```

The VM path uses the same idea with `/run/nut/vm-shutdown-request` and a separate root service.

## Compute VM behaviour

At the VM threshold:

- snapshot **currently running** domains from `qemu:///system`;
- request guest-agent shutdown first;
- if agent shutdown is unavailable/fails, request ACPI shutdown;
- wait/poll for a bounded period (reference: 45 seconds);
- consider success only when `virsh domstate` is exactly `shut off`;
- write a JSON result with targets, confirmed and remaining;
- POST the result to controller through the report-only HMAC API.

Windows guests were materially more reliable after installing the QEMU Guest Agent. Linux guests may shut down by ACPI fallback.

## HMAC report-only controller

The controller API exists only to receive VM shutdown results. It must not grow a shutdown/control endpoint casually.

Reference protections:

- bind to a trusted management/LAN address;
- firewall allow only the compute source address;
- shared random secret stored outside Git;
- HMAC-SHA256 over `timestamp + "\\n" + nonce + "\\n" + body`;
- timestamp skew limit (reference: 120s);
- random nonce and replay cache;
- small maximum request body (reference: 64 KiB);
- strict JSON/event/source/list validation;
- atomic result-file replacement and restrictive mode.

Replay cache is in memory, so an API restart clears it. Timestamp validation still limits the useful replay window. For stronger controls, persist nonces or use mTLS.

## How physical shutdown is reported

The controller intentionally avoids saying a physical host is shut down based on one signal.

Two observations are used:

- SSH/TCP-22 reachability (connection refused still proves the remote IP stack answered);
- whether a persistent NUT client TCP session to controller port 3493 exists.

Interpretation:

- SSH gone + NUT gone -> `SHUTDOWN OBSERVED`;
- SSH present + NUT present -> still online;
- one present/one absent -> `WARNING - CONFLICTING OBSERVATION`;
- NUT check unavailable -> `WARNING - CHECK INCOMPLETE`.

The warm tests deliberately create the conflicting state by stopping `nut-monitor` while leaving the server running.

## Why direct UPS-output commands are excluded

Early experimentation demonstrated that an UPS-level shutdown/output action can affect the entire load, not one host. An unexpected shutdown/power event during that phase had a larger blast radius than desired. The retained notes do not prove which exact command was causal, so do not manufacture that detail. The design response is the important part: outage automation reads UPS state and requests local OS shutdown only.

The quick battery self-test is different: it is an internal self-test, not a request to turn UPS output off. On the tested UPS it moved through `CAL`/`BYPASS` while remaining online, then returned to plain `OL`. If another UPS reports `OB` during self-test, this project's assumptions must be revisited.

## Real bugs already found

Do not reintroduce these:

- SELinux blocked NUT executing sudo: exit 126.
- restricted NUT execution PATH caused `hostname` lookup failure: exit 127. Use absolute command paths or avoid the call.
- `nut-monitor` showed enabled but did not start after boot because `nut.target` itself was disabled. Enable `nut.target`.
- a timer threshold is not proof of completed shutdown.
- a disabled controller `nut-monitor` could still be started; masking is stronger.
- systemd sandboxing can prevent Postfix `postdrop`; the mail-sending services need the narrowly required group/path access.
- self-test command return value alone was not trustworthy; confirm physical status transitions.

## Test evidence from development

Successfully exercised on real hardware during development:

- NUT USB discovery/readout and remote client connections;
- real short mains-loss `OB`/restore `OL` handling;
- email queue/relay and dashboard events;
- weekly-style quick battery self-test with observed `CAL/BYPASS -> OL`;
- RHEL shutdown timers;
- failed sudo/SELinux design and replacement request-file design;
- real physical local shutdown via the systemd request path on both protected RHEL hosts;
- compute VM-only staged test with all running VMs confirmed shut off;
- authenticated HMAC report and replay rejection;
- dual-signal monitoring by deliberately dropping each client's NUT session while SSH remained reachable;
- warm-test restoration returning both clients to normal monitoring.

A sanitized public copy must still be treated as needing fresh local validation because genericizing addresses/names and future edits can introduce errors.

## How to help with this project as an LLM

When asked to modify the project:

- preserve the safety invariants above;
- make small changes and explain their failure modes;
- prefer complete replacement files when giving operational scripts so users do not paste fragments into the wrong location;
- distinguish read-only tests, warm tests, host-shutdown tests and UPS-output commands;
- never request real secrets in chat or put them in examples;
- use documentation/test networks and generic hostnames in public output;
- do not claim a shutdown succeeded unless there is evidence;
- keep control-plane additions separate from the fail-safe local shutdown path;
- run syntax/static checks before suggesting live tests;
- recommend a supervised test ladder rather than jumping directly to a full outage.

If a proposed feature conflicts with an invariant, state the conflict before writing code.
