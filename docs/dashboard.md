# Dashboard

`dashboard/dashboard.py` is intentionally dependency-light: Python standard library + SQLite + `upsc`.

It records current UPS status, battery charge/voltage, input/output voltage, load, frequency, minute-level historical samples and notable events such as power failure/restoration and communication loss/restoration.

The public default bind is `127.0.0.1`. In a LAN deployment, set `DASHBOARD_LISTEN` and `DASHBOARD_PORT` through the private site environment and restrict access with a firewall. The dashboard has no authentication layer in this reference, so it should not be exposed to untrusted networks or the Internet.

The dashboard is **not part of the shutdown dependency chain**. If it fails, local NUT/upssched/systemd shutdown protection should continue.
