#!/usr/bin/env bash
# setup-automerge-pat.sh — create the AUTOMERGE_PAT fine-grained token and
# install it as a repo secret, in one guided run.
#
# WHY THIS IS GUIDED, NOT FULLY AUTOMATED: GitHub exposes NO API to mint a
# personal access token (fine-grained or classic) non-interactively. Only
# GitHub Apps can mint tokens via API. So this script automates everything
# AROUND the one unavoidable manual step: it preflights auth, opens the
# creation page pre-described with the exact settings, validates the token you
# paste, and sets the repo secret. Re-run it any time to rotate the PAT.
#
# The PAT powers .github/workflows/copilot-pr-autorun.yml, which marks Copilot
# refresh PRs ready and re-runs their gated CI runs so the freshness delivery
# loop self-closes. See AGENTS.md § 9.6.
#
# Usage:
#   bash scripts/setup-automerge-pat.sh                 # defaults to aiappsgbb/awesome-gbb
#   REPO=owner/repo bash scripts/setup-automerge-pat.sh # override target repo
set -euo pipefail

REPO="${REPO:-aiappsgbb/awesome-gbb}"
SECRET_NAME="AUTOMERGE_PAT"
OWNER="${REPO%%/*}"
CREATE_URL="https://github.com/settings/personal-access-tokens/new"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
err()  { printf '\033[31m%s\033[0m\n' "$1" >&2; }
ok()   { printf '\033[32m%s\033[0m\n' "$1"; }

# ── 1. Preflight: gh present + authenticated + repo admin ────────────────────
command -v gh >/dev/null 2>&1 || { err "gh CLI not found — install: https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || { err "gh not authenticated — run: gh auth login"; exit 1; }

if ! gh api "/repos/$REPO" --jq '.permissions.admin' 2>/dev/null | grep -q true; then
  err "Your gh account lacks admin on $REPO (needed to set repo secrets)."
  err "Ask a repo admin to run this, or set REPO=<owner/repo> you administer."
  exit 1
fi

# ── 2. Print the exact settings + open the creation page ─────────────────────
bold "Create a FINE-GRAINED PAT with these EXACT settings:"
cat <<EOF

  Token name:        awesome-gbb ${SECRET_NAME}
  Resource owner:    ${OWNER}        # the org/owner that owns ${REPO}
  Expiration:        90 days (rotate by re-running this script)
  Repository access: Only select repositories → ${REPO}
  Repository permissions:
    • Actions ............ Read and write   (re-run action_required runs)
    • Pull requests ...... Read and write   (mark draft refresh PRs ready)
    • Contents ........... Read-only
    • Metadata ........... Read-only (auto-selected)

Opening ${CREATE_URL} ...
EOF

if command -v open >/dev/null 2>&1; then open "$CREATE_URL" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$CREATE_URL" >/dev/null 2>&1 || true
else echo "Open this URL manually: ${CREATE_URL}"; fi

# ── 3. Read the pasted token silently ────────────────────────────────────────
printf '\nPaste the generated token (starts with github_pat_), then press Enter: '
read -rs TOKEN
echo
[ -n "${TOKEN:-}" ] || { err "No token entered."; exit 1; }

# ── 4. Validate scope BEFORE storing it ──────────────────────────────────────
# Fine-grained PAT permissions are a single Read | Read-and-write dropdown per
# resource, so we can only confirm the permission is at least present (read).
# Write can't be safely probed without performing a write; the printed settings
# above are the source of truth for selecting "Read and write".
bold "Validating token …"
api() { GH_TOKEN="$TOKEN" gh api -H "Accept: application/vnd.github+json" "$@"; }

if ! api "/repos/$REPO" --jq '.full_name' >/dev/null 2>&1; then
  err "Token cannot read ${REPO} — check the 'Only select repositories' selection."
  exit 1
fi
if ! api "/repos/$REPO/actions/runs?per_page=1" >/dev/null 2>&1; then
  err "Token lacks the Actions permission — re-create with Actions: Read and write."
  exit 1
fi
if ! api "/repos/$REPO/pulls?per_page=1" >/dev/null 2>&1; then
  err "Token lacks the Pull requests permission — re-create with Pull requests: Read and write."
  exit 1
fi
ok "  ✓ token reads ${REPO} and carries Actions + Pull requests permissions"
echo "    (ensure both were set to 'Read and write', not just 'Read')"

# ── 5. Set the repo secret ───────────────────────────────────────────────────
bold "Setting secret ${SECRET_NAME} on ${REPO} …"
printf '%s' "$TOKEN" | gh secret set "$SECRET_NAME" --repo "$REPO"

if gh secret list --repo "$REPO" --json name --jq '.[].name' 2>/dev/null | grep -qx "$SECRET_NAME"; then
  ok "✓ ${SECRET_NAME} installed on ${REPO}"
else
  # Older gh without --json on secret list
  if gh secret list --repo "$REPO" 2>/dev/null | grep -q "$SECRET_NAME"; then
    ok "✓ ${SECRET_NAME} installed on ${REPO}"
  else
    err "Secret set call returned, but ${SECRET_NAME} not found in secret list — verify manually."
    exit 1
  fi
fi

cat <<EOF

Done. The delivery loop is now armed:
  • copilot-pr-autorun.yml (every ~10 min) marks Copilot refresh PRs ready and
    re-runs their gated CI runs.
  • auto-merge-copilot.yml merges them once all gates pass.

Trigger an immediate pass instead of waiting for the cron:
  gh workflow run "Copilot PR autorun" --repo ${REPO}
EOF
