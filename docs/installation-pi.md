# Controller Installation (Raspberry Pi / Debian-family)

Package names vary by release; confirm them locally. The development system used a Raspberry Pi/Debian-family controller with NUT, Python 3, nftables and Postfix.

## 1. Install core packages

Typical Debian-family packages:

```bash
apt update
apt install nut nut-server nut-client python3 nftables postfix libsasl2-modules ca-certificates
```

Do not copy commands blindly onto a different distribution.

## 2. Create local configuration directory

```bash
install -d -m 0750 -o root -g root /etc/nut-safe-monitoring
cp configs/common/site.env.example /etc/nut-safe-monitoring/site.env
cp configs/common/mail.env.example /etc/nut-safe-monitoring/mail.env
chmod 0600 /etc/nut-safe-monitoring/site.env /etc/nut-safe-monitoring/mail.env
```

Replace documentation addresses and generic names **locally**. Do not commit the real files.

## 3. Configure NUT server

Use the examples under `configs/pi/etc/nut/` as a starting point. Verify the USB device and driver first:

```bash
lsusb
nut-scanner -U
```

The tested Dynamix unit appeared as USB `0665:5161` and worked with `nutdrv_qx`. Your unit may differ.

After editing local NUT files, start/restart the appropriate driver/server units for your distribution and prove read-only access:

```bash
upsc ups@localhost
upsc ups@localhost ups.status
```

Expected normal state is typically `OL`.

## 4. Make the controller a server only

The controller should not run `upsmon` in this architecture:

```bash
systemctl stop nut-monitor.service 2>/dev/null || true
systemctl mask nut-monitor.service
systemctl is-enabled nut-monitor.service
```

Do not mask the NUT driver or `upsd` server.

## 5. Firewall

Adapt `firewall/nftables-pi.example` to your own ruleset. Do not restart/replace a remote firewall until you have validated syntax and retained management access.

Required reference flows are:

- protected clients -> controller TCP/3493;
- trusted admin network -> dashboard TCP/8080 if exposed;
- compute node -> controller TCP/8081 if VM reporting is used;
- controller -> SMTP relay/Internet as required by your mail design.

## 6. Service accounts/directories

Example:

```bash
useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin upsdash 2>/dev/null || true
useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin upstester 2>/dev/null || true
install -d -m 0750 -o upsdash -g upsdash /var/lib/ups-dashboard
install -d -m 0750 -o root -g upsdash /etc/ups-controller
```

Create a strong HMAC secret locally, e.g. 32+ random bytes represented safely. Store it as `/etc/ups-controller/report-secret`, readable only by the controller service group. Create the same secret on the compute node at `/etc/nut/ups-report-secret` with root-only permissions. Never commit it.

## 7. Install controller code

Example target paths:

```text
/opt/ups-dashboard/dashboard.py
/opt/ups-controller/controller-api.py
/usr/local/sbin/ups-send-alert
/usr/local/sbin/ups-power-watch
/usr/local/sbin/nut-quick-selftest
/usr/local/sbin/ups-warm-observer-test
```

Install the systemd units from `configs/pi/systemd/`, run `systemctl daemon-reload`, then enable only the services you have configured and tested.

## 8. Email

Configure Postfix or another local queue before enabling automated alerts. A local queue is useful because Internet connectivity may fail during the same outage: queued messages can be retried later.

See `docs/email.md`.

## 9. Self-test account

Create a dedicated NUT `upstester` user whose `instcmds` contains only:

```text
test.battery.start.quick
```

Store its password outside Git. Run the self-test manually under supervision before enabling the timer. On the tested UPS, the test produced `CAL`/`BYPASS` transitions and returned to plain `OL` without producing a real `OB` event.

## 10. Do not enable everything at once

Complete the test ladder in `docs/testing.md`. In particular, prove that the controller sees both clients connected before enabling unattended self-tests or depending on consolidated reports.
