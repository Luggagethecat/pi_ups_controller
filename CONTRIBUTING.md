# Contributing

Contributions are welcome, especially support for additional UPS models, distributions, notification methods and safer recovery workflows.

Before changing code, read `AI_CONTEXT.md` and `SECURITY.md`. This project treats power control as a high-impact action.

## Contribution rules

- Do not add real credentials, production hostnames, private IPs, MAC addresses or personal email addresses to examples, tests, screenshots or issue logs.
- Use RFC 5737 documentation addresses (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and `example.invalid` for public examples.
- Do not add automated UPS-output shutdown/off commands to the normal outage path without an explicit design discussion that addresses blast radius and hardware-specific behaviour.
- Do not weaken SELinux/AppArmor or grant broad sudo merely to make an event script work.
- Keep dashboard/reporting/control enhancements independent from the essential local shutdown path.
- Add a safe test for behaviour you change. Prefer read-only or warm simulation before destructive testing.
- Document what was tested on real hardware versus what is inferred or syntax-tested only.
- Preserve conservative wording: do not call a host shut down merely because a timer expired.

## Suggested pre-commit checks

```bash
python3 tests/public-release-scan.py
python3 -m py_compile dashboard/dashboard.py controller/controller-api.py scripts/pi/ups-power-watch scripts/pi/ups-warm-observer-test scripts/rhel/ups-report-vm-result
bash -n scripts/pi/ups-send-alert scripts/pi/nut-quick-selftest scripts/rhel/ups-vm-shutdown scripts/rhel/ups-warm-client-test
sh -n scripts/rhel/ups-local-poweroff scripts/rhel/upssched-cmd-compute scripts/rhel/upssched-cmd-storage
```

A clean static check is not a substitute for supervised hardware testing.
