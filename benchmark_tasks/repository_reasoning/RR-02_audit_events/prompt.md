# Task RR-02: Missing audit events and an ignored audit setting

The `app` package wires together a settings loader, an event bus, a user service and an audit log
(see `app/factory.py` for how they are connected). Two problems have been reported:

1. **Deleted users never appear in the audit log.** Creating and renaming users is audited correctly, but
   deletions are silently missing. No exception reaches the caller.
2. **Auditing cannot be switched off.** Setting `audit.enabled = false` in the settings text passed to
   `create_app()` has no effect; entries are still recorded.

Find and fix the root causes. Requirements:
- Every user lifecycle event must publish a payload that follows the payload schema documented in `app/events.py`.
- With auditing enabled, `created`, `renamed` and `deleted` events each produce exactly one audit entry.
- The boolean settings `audit.enabled` and `audit.include_names` accept `true/false/yes/no/on/off/1/0`
  (case-insensitive, surrounding whitespace ignored). Any other value raises `ValueError`. Both default to true.
- Do not weaken the event bus's error isolation (a failing handler must still not break publishers) and keep
  all public signatures unchanged.

Standard library only; you may add tests under `tests/`.
