# Development Incident Notes

These notes explain why some design choices look more conservative than a typical small homelab NUT setup.

## 1. UPS-level control had too much blast radius

During early experimentation, a shutdown/control test produced unexpected shutdown/power behaviour that was not safely isolated to the single host being tested. UPS output control can affect every attached load, so the project stopped using outlet/output shutdown commands in automated outage handling.

The retained development record does **not** reliably identify one exact UPS command as the causal command. For that reason, this public repository does not invent a precise attribution. Instead, it records the conservative policy that followed:

```text
DO NOT automate:
  upsmon -c fsd
  upsdrvctl shutdown
  load.off / load.on
  shutdown.return
  shutdown.stayoff
  driver.killpower
```

Host shutdown is now a local OS action initiated by each protected host. The central UPS controller only observes status, receives reports, sends alerts and performs a narrowly-scoped internal quick battery test.

## 2. SELinux rejected the first privilege design

An early RHEL implementation attempted to let NUT run `sudo systemctl poweroff`. The outage timer fired, but `upssched` returned `126`. SELinux AVC logs showed the confined `nut_upsmon_t` domain was denied execution of `sudo_exec_t`.

The project did **not** disable SELinux and did not generate a broad `audit2allow` rule. It redesigned the boundary around a request file and root-owned systemd `.path`/service.

## 3. Restricted PATH broke an event script

A later test reached the NUT event handler but returned `127` because the script called `hostname` through a PATH that was not present in NUT's restricted execution environment. Event scripts were simplified and operational commands use absolute paths.

## 4. `nut-monitor` enablement was misleading

On RHEL, `nut-monitor.service` had an enablement relationship under `nut.target.wants`, but the target itself was disabled. The monitor therefore did not reliably start after boot. The installation instructions explicitly enable and start `nut.target`.

## 5. Confirmation language was tightened

The project originally described elapsed timer thresholds as though shutdown had happened. That is unsafe wording. Current reporting distinguishes:

- **threshold crossed** — a scheduled action should have been requested;
- **VM shutdown confirmed** — libvirt observed the domain `shut off` and reported it through authenticated API;
- **physical shutdown observed** — controller independently sees both network/SSH and NUT session disappear;
- **conflicting/incomplete** — evidence does not justify claiming success.
