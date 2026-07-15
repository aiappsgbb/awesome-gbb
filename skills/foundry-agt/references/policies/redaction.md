# PII redaction policy

> Referenced by `redaction_policy` in the `build_evidence()` call
> (see `../runtime-audit-export.md § Step 5`).

This document defines which fields are stripped from AGT audit events before
they are included in the committed evidence record or forwarded to the
telemetry sink.

---

## Redaction mode

**Mode:** `strip-sensitive` — the evidence producer keeps only the fields
declared in `_SAFE_FIELDS` (see `../runtime-audit-export.md § Step 3`) and
discards everything else. No field values are masked or hashed; they are
omitted entirely.

---

## Fields stripped

| Field | Why stripped |
|-------|-------------|
| `prompt` | May contain user PII or confidential instructions |
| `response` | May contain model-generated content referencing sensitive data |
| `arguments` | Tool call arguments may include credentials, queries, or PII |
| `credentials` | Explicit secret material — never recorded |
| `tool_arguments` | Alias for `arguments` used by some AGT versions |
| `message` | Free-form text — may contain any sensitive data |
| Any field not in `_SAFE_FIELDS` | Default-deny: unknown fields are omitted |

---

## Fields retained

Only the following fields survive into the evidence record or telemetry event:

```
event_id, timestamp, event_type, agent_id, session_id,
policy_name, tool_name, decision, reason, evaluation_ms
```

These fields contain no prompt text, no response content, no argument
values, and no credentials. They are safe to commit to source control.

---

## Compliance notes

- This policy satisfies the OWASP ASI 2026 data-minimisation requirement
  for audit trails.
- Operators subject to GDPR or CCPA MUST NOT widen `_SAFE_FIELDS` to
  include user-supplied content without a legal basis review.
- Review this policy whenever the AGT event schema gains new fields.
