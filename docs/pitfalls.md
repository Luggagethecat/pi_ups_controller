# Pitfalls and Lessons Learned

- **Disabled is weaker than masked.** The controller's `nut-monitor` should be masked when this architecture requires it never to start.
- **NUT sudoers is not enough on SELinux RHEL.** A syntactically valid sudo rule can still be blocked by SELinux. Redesign privilege crossing rather than weakening MAC policy.
- **Do not use `audit2allow` as a reflex.** Understand the denial first.
- **UPS output control is a different blast radius from OS shutdown.** A mistaken UPS command can abruptly kill every attached device.
- **Elapsed time is not proof.** Report "threshold crossed" unless independent evidence supports stronger wording.
- **Restricted PATH matters.** Event scripts should use absolute commands or built-ins.
- **Enable `nut.target`, not only `nut-monitor`.** Verify boot behaviour, not just symlinks.
- **Test one failure signal at a time.** The warm tests intentionally remove NUT monitoring while leaving SSH/network alive.
- **Guest agents are guest-specific.** Verify QEMU Guest Agent inside Windows/Linux guests; retain ACPI fallback where appropriate.
- **HMAC is not encryption.** Protect report confidentiality separately if necessary.
- **Self-test state machines vary by UPS.** Do not assume every UPS uses the tested `CAL/BYPASS -> OL` pattern.
- **Do not manually invoke live timer actions.** With `.path` watchers enabled, creating a real request file can immediately shut a host down.
- **Do not publish backup archives.** They may contain NUT and SMTP secrets even when the Git tree is clean.
