# Public Release Checklist

Before publishing a fork or build artifact:

- search recursively for real IPs, hostnames, email addresses, MAC addresses and usernames;
- search for `password`, `secret`, `token`, `BEGIN .* PRIVATE KEY`, `sasl_passwd` and HMAC key material;
- ensure real `upsd.users`, `upsmon.conf`, `site.env`, `mail.env` and backup archives are not staged;
- inspect Git history as well as the current tree — deleting a secret from the latest commit does not remove it from history;
- rotate any credential that was ever committed or pasted into a public issue;
- verify example IPs are documentation/test addresses, not production networks;
- run Python compile checks and `bash -n` / `sh -n` as appropriate;
- run ShellCheck/Bandit/other linters if available, but do not treat a clean linter as proof of operational safety;
- test the warm-test scripts before any full outage;
- retain the GPL license and notices when distributing covered modified versions;
- update `docs/test-status.md` when claiming new hardware/OS compatibility.
