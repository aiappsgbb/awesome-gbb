"""Canonical instructions for rendering authenticated identity tool results.

Source of truth for `../../SKILL.md § Agent integration`.
Shared by Prompt and Hosted without importing either SDK cohort.
"""

INSTRUCTIONS = (
    "For every question about who the caller is, their identity, or their token claims, "
    "call who_am_i freshly in the current turn, including follow-up questions such as "
    "'Chi sono?'. Never answer identity questions from conversation history. "
    "When the tool returns oid, tid, aud, scp and azp, show those exact values and "
    "correlation_id prominently in the final answer. These are the caller's own "
    "validated claims, explicitly exposed by the operator-approved identity view. "
    "Do not replace them with subject_label, user-a, a pseudonym, or synthetic records. "
    "If the tool returns only a pseudonymous receipt, state that actual claims are "
    "not exposed; do not invent or infer them. Never infer an identity from a prompt "
    "or invent a receipt. Only show name or preferred_username if actually returned "
    "by the authenticated tool; an object ID is not a display name. "
    "For a UPN question, show upn only if that exact claim is returned. "
    "If upn is absent, explicitly state that the MCP token has no upn claim. "
    "A returned preferred_username must be labeled preferred_username only: "
    "NEVER call it UPN, 'UPN / preferred_username', or an equivalent UPN. "
    "Do not infer a missing upn even when the value looks like an email address "
    "or a previous answer incorrectly called it UPN. "
    "Call list_my_demo_items only when the user explicitly asks for demo items, "
    "never automatically for an identity question. Never show a raw bearer token. "
    "If authorization is required or denied, report that; do not claim tool success. "
    "Reply in the user's language."
)
