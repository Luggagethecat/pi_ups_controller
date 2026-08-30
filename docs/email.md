# Email Notifications

The reference design uses a local mail submission helper and expects a local MTA/queue such as Postfix. The upstream relay may be Gmail or another SMTP service.

Why queue locally: during an outage, Internet connectivity may fail before or while an important notification is generated. A local queue can retain mail and retry when connectivity returns.

Keep SMTP credentials out of Git. If using Gmail, use an App Password where required by your account security settings; never put it in scripts or documentation.

The current low-spam notification model is:

- immediate `UPS POWER FAILURE` on real `OB`;
- one consolidated `UPS - Shutdown Report` around 6:30 only if still `OB`;
- `UPS POWER RESTORED` on return to `OL`;
- communication lost/restored alerts after a debounce period;
- separate quick self-test pass/skip/fail messages.

There are intentionally no separate 4-minute and 5-minute threshold emails in the final reference watcher.
