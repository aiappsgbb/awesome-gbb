#!/usr/bin/env python3
"""
check-freshness.py — weekly freshness detector for the awesome-gbb skill catalog.

Walks every `skills/<name>/references/upstream-pin.md`, parses the
YAML front-matter (schema_version 2), and emits a per-skill freshness
report. Five drift signals are detected:

  1. SHA drift              — `git ls-remote` vs front-matter `pinned_sha`
  2. Package version drift  — PyPI JSON API vs front-matter `packages[].version`
  3. Upstream issue closure — GitHub issue/PR API for `known_issues[].upstream_url`
  4. Link rot               — HEAD on each `docs_to_revalidate[]` URL
  5. Validation age         — `today - last_validated > 180 days`

For each drift event the script can:
  - Print a Markdown report (`--print-report`)
  - Upsert ONE GitHub issue per skill+signal (`--upsert-issues`)
  - Auto-assign to `Copilot` if the skill's `automation_tier: auto`
    (`--assign-copilot-on-auto-tier`)

Run locally with `--dry-run` to preview without API writes.

Required env vars when `--upsert-issues` is set:
  GH_TOKEN   — token with `issues:write` on the repo
  GH_REPO    — `owner/name` (defaults to aiappsgbb/awesome-gbb)
"""

from __future__ import annotations

import argparse
import io
import os
import sys

# Force UTF-8 stdout/stderr so the rendered report (which contains emoji
# like 🪴 ⚠️ ✅) works on Windows consoles that default to cp1252. The
# GitHub Actions runner is already UTF-8, but contributors who run the
# script locally on Windows would otherwise crash with `UnicodeEncodeError:
# 'charmap' codec can't encode character …` on the very first `print(report)`.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
import dataclasses
import datetime as dt
import json
import pathlib
import re
import subprocess
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed — pip install pyyaml", file=sys.stderr)
    sys.exit(2)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed — pip install requests", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
DEFAULT_REPO = os.environ.get("GH_REPO", "aiappsgbb/awesome-gbb")
VALIDATION_AGE_DAYS = 180

# Copilot Coding Agent is a GitHub App bot (login slug: copilot-swe-agent,
# UI display name: Copilot). The REST /issues `assignees` field cannot
# accept Bot accounts — it returns HTTP 422 "invalid" — so assignment
# has to go through the GraphQL `replaceActorsForAssignable` mutation,
# which works on any Actor (User OR Bot).
#
# We discover the bot's node ID dynamically per-repo via
# `repository.suggestedActors(capabilities: [CAN_BE_ASSIGNED])` so the
# script works in any repo where the org has enabled the Coding Agent.
COPILOT_BOT_LOGIN = "copilot-swe-agent"

USER_AGENT = "awesome-gbb-freshness-bot/1.0"
HTTP_TIMEOUT = 10


_copilot_bot_id_cache: dict[str, str | None] = {}


def get_copilot_bot_id(repo: str, gh_token: str) -> str | None:
    """Return the GraphQL node ID of the Copilot Coding Agent bot for `repo`,
    or None if the bot is not enabled there. Cached per-repo."""
    if repo in _copilot_bot_id_cache:
        return _copilot_bot_id_cache[repo]

    owner, name = repo.split("/", 1)
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        suggestedActors(capabilities: [CAN_BE_ASSIGNED], first: 100) {
          nodes {
            __typename
            ... on Bot { id login }
            ... on User { id login }
          }
        }
      }
    }
    """
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"owner": owner, "name": name}},
        headers={
            "Authorization": f"Bearer {gh_token}",
            "User-Agent": USER_AGENT,
        },
        timeout=HTTP_TIMEOUT,
    )
    bot_id: str | None = None
    if r.status_code == 200:
        data = r.json().get("data") or {}
        nodes = (data.get("repository") or {}).get("suggestedActors", {}).get("nodes", []) or []
        for n in nodes:
            if n.get("__typename") == "Bot" and n.get("login") == COPILOT_BOT_LOGIN:
                bot_id = n["id"]
                break
    else:
        print(f"WARN: suggestedActors GraphQL returned {r.status_code}: {r.text[:200]}", file=sys.stderr)
    _copilot_bot_id_cache[repo] = bot_id
    return bot_id


def assign_copilot_to_issue(issue_node_id: str, bot_id: str, gh_token: str) -> bool:
    """Use GraphQL `replaceActorsForAssignable` to assign the Coding Agent
    bot to an issue. Returns True on success."""
    mutation = """
    mutation($issueId: ID!, $botId: ID!) {
      replaceActorsForAssignable(input: { assignableId: $issueId, actorIds: [$botId] }) {
        assignable { ... on Issue { number } }
      }
    }
    """
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": mutation, "variables": {"issueId": issue_node_id, "botId": bot_id}},
        headers={
            "Authorization": f"Bearer {gh_token}",
            "User-Agent": USER_AGENT,
        },
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200 or (r.json().get("errors")):
        print(
            f"WARN: GraphQL assign for issue {issue_node_id} failed: "
            f"{r.status_code} {r.text[:300]}",
            file=sys.stderr,
        )
        return False
    return True


# ──────────────────────────── data model ────────────────────────────


@dataclasses.dataclass
class Signal:
    skill: str
    signal_type: str      # sha_drift | pkg_drift | issue_closed | link_rot | stale_validation
    severity: str         # info | warn | error
    title: str            # used as issue title
    body: str             # Markdown body
    automation_tier: str  # auto | issue_only — copied from the pin file


@dataclasses.dataclass
class PinFile:
    skill: str
    path: pathlib.Path
    fm: dict[str, Any]

    @property
    def tier(self) -> str:
        return self.fm.get("freshness_tier", "?")

    @property
    def automation_tier(self) -> str:
        return self.fm.get("automation_tier", "issue_only")

    @property
    def upstream(self) -> dict[str, Any]:
        return self.fm.get("upstream") or {}

    @property
    def packages(self) -> list[dict[str, Any]]:
        return self.fm.get("packages") or []

    @property
    def docs(self) -> list[str]:
        return self.fm.get("docs_to_revalidate") or []

    @property
    def known_issues(self) -> list[dict[str, Any]]:
        return self.fm.get("known_issues") or []

    @property
    def last_validated(self) -> dt.date | None:
        v = self.fm.get("last_validated")
        if not v:
            return None
        if isinstance(v, dt.date):
            return v
        try:
            return dt.date.fromisoformat(str(v))
        except ValueError:
            return None


# ──────────────────────────── parsing ───────────────────────────────


def parse_pin_file(path: pathlib.Path) -> PinFile | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    skill = path.parent.parent.name
    return PinFile(skill=skill, path=path, fm=fm)


def discover_pin_files() -> list[PinFile]:
    pins: list[PinFile] = []
    for p in sorted(SKILLS_DIR.glob("*/references/upstream-pin.md")):
        pf = parse_pin_file(p)
        if pf is None:
            print(f"WARN: could not parse {p}", file=sys.stderr)
            continue
        pins.append(pf)
    return pins


# ──────────────────────────── detectors ─────────────────────────────


def detect_sha_drift(pin: PinFile, gh_token: str | None) -> Signal | None:
    upstream = pin.upstream
    if upstream.get("type") != "github_repo":
        return None
    repo = upstream.get("repo")
    ref = upstream.get("ref")
    pinned = upstream.get("pinned_sha")
    if not (repo and ref and pinned):
        return None

    try:
        out = subprocess.run(
            ["git", "ls-remote", f"https://github.com/{repo}", ref],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return Signal(
            skill=pin.skill,
            signal_type="sha_drift",
            severity="error",
            title=f"🔄 Refresh `{pin.skill}` — could not query upstream {repo}@{ref}",
            body=f"`git ls-remote https://github.com/{repo} {ref}` failed: {e}",
            automation_tier=pin.automation_tier,
        )

    if not out.strip():
        return Signal(
            skill=pin.skill,
            signal_type="sha_drift",
            severity="error",
            title=f"🔄 Refresh `{pin.skill}` — upstream ref `{ref}` not found",
            body=f"`git ls-remote https://github.com/{repo} {ref}` returned no rows.",
            automation_tier=pin.automation_tier,
        )

    current_sha = out.split()[0]
    if current_sha == pinned:
        return None

    body_lines = [
        f"## 🔄 Refresh `{pin.skill}` — upstream SHA drift",
        "",
        f"**Skill**: `skills/{pin.skill}/`",
        f"**Pin file**: `skills/{pin.skill}/references/upstream-pin.md`",
        f"**Automation tier**: `{pin.automation_tier}`",
        "",
        "### Drift detected",
        "",
        f"- **Upstream**: `{repo}@{ref}`",
        f"- **Pinned SHA**: `{pinned}`",
        f"- **Current SHA**: `{current_sha}`",
        "",
        "### Required action",
        "",
        "1. Update `upstream.pinned_sha` in the pin file front-matter to "
        f"`{current_sha}`.",
        "2. Run the Verification Checklist (§ 3 of the pin file). The "
        "machine-runnable script is in `validation.script`.",
        "3. If pass → update `last_validated` to today, bump SKILL.md "
        "`metadata.version` PATCH, open PR.",
        "4. If fail → comment on this issue with the failure mode; do NOT "
        "open a PR.",
        "",
        "### ⚠️ Surgical edits only — no search-and-replace",
        "",
        "Edit ONLY these fields, in these files:",
        "- `references/upstream-pin.md`: `upstream.pinned_sha`, "
        "`last_validated`, `validated_by` (set to `copilot-bot`)",
        "- `SKILL.md`: `metadata.version` (PATCH bump)",
        "",
        "Do **NOT** run a global search-and-replace on the SHA or any "
        "version strings. SKILL.md body and pin-file prose contain "
        "historical proof-of-validation text (e.g. `verified against "
        "<short-sha>`); those are records, not refresh targets. The gate "
        "will reject any SKILL.md body change without `[skill-rewrite]`.",
        "",
        "### Acceptance criteria",
        "",
        "- [ ] PR touches ONLY `references/upstream-pin.md` and "
        "`SKILL.md` (frontmatter only)",
        "- [ ] `metadata.version` bumped PATCH only",
        "- [ ] CI gate `automation-pr-gate.yml` passes",
        "- [ ] CI gate `skill-validation.yml` passes",
        "- [ ] CI gate `pin-validation.yml` passes "
        "(re-runs `validation.script` on the runner — proof, not claim)",
    ]

    if pin.automation_tier == "auto":
        body_lines.extend(
            [
                "",
                "---",
                "",
                "🤖 This issue is assigned to @Copilot. The coding agent "
                "will execute the Verification Checklist embedded in the "
                "pin file and open a PR. A human reviews + merges.",
            ]
        )
    else:
        body_lines.extend(
            [
                "",
                "---",
                "",
                "👤 **Human action required** — validation requires credentials "
                f"({pin.fm.get('validation', {}).get('requires', [])}) that we "
                "don't ship to the coding agent.",
            ]
        )

    return Signal(
        skill=pin.skill,
        signal_type="sha_drift",
        severity="warn",
        title=f"🔄 Refresh `{pin.skill}` — upstream SHA drift",
        body="\n".join(body_lines),
        automation_tier=pin.automation_tier,
    )


def detect_pkg_drift(pin: PinFile) -> list[Signal]:
    out: list[Signal] = []
    for pkg in pin.packages:
        if pkg.get("source") != "pypi":
            continue
        name = pkg.get("name")
        pinned = pkg.get("version")
        if not (name and pinned):
            continue
        try:
            r = requests.get(
                f"https://pypi.org/pypi/{name}/json",
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            out.append(
                Signal(
                    skill=pin.skill,
                    signal_type="pkg_drift",
                    severity="error",
                    title=f"🔄 Refresh `{pin.skill}` — PyPI lookup failed for `{name}`",
                    body=f"PyPI JSON API for `{name}` failed: {e}",
                    automation_tier=pin.automation_tier,
                )
            )
            continue

        latest = (data.get("info") or {}).get("version")
        if latest and latest != pinned:
            body = "\n".join(
                [
                    f"## 🔄 Refresh `{pin.skill}` — PyPI package `{name}` drift",
                    "",
                    f"- **Pinned**: `{name}~={pinned}` (cap window covers patch upgrades)",
                    f"- **Latest**: `{name}=={latest}`",
                    f"- **Changelog**: {pkg.get('upstream_changelog', '(none)')}",
                    "",
                    "Run the pin file's `validation.script` with "
                    f"`PINNED_VERSION={latest}` to verify the skill still "
                    "works against the new release.",
                    "",
                    "### ⚠️ Surgical edits only — no search-and-replace",
                    "",
                    "Edit ONLY these fields:",
                    f"- `references/upstream-pin.md`: `packages[name={name}].version` → `{latest}`",
                    "- `references/upstream-pin.md`: the matching cap in "
                    "`validation.script` (e.g. bump `~=X.Y.Z` floor — keep "
                    "the `~=` operator, never switch to bare `==`)",
                    "- `references/upstream-pin.md`: `last_validated`, "
                    "`validated_by: copilot-bot`",
                    "- `SKILL.md`: `metadata.version` (PATCH bump)",
                    "",
                    "Do **NOT** run a global search-and-replace on the "
                    "version number. SKILL.md body and pin-file prose "
                    f"contain historical proof-of-validation text (e.g. "
                    f"`verified against {name} {pinned}`); those are "
                    "records, not refresh targets. The gate will reject "
                    "any SKILL.md body change without `[skill-rewrite]`.",
                    "",
                    "### Acceptance criteria",
                    "",
                    "- [ ] PR touches ONLY `references/upstream-pin.md` and "
                    "`SKILL.md` (frontmatter only)",
                    "- [ ] `metadata.version` bumped PATCH only",
                    "- [ ] All pip specifiers stay `~=X.Y.Z` (compatible release)",
                    "- [ ] CI gate `automation-pr-gate.yml` passes",
                    "- [ ] CI gate `skill-validation.yml` passes",
                    "- [ ] CI gate `pin-validation.yml` passes "
                    "(re-runs `validation.script` on the runner — proof, not claim)",
                ]
            )
            out.append(
                Signal(
                    skill=pin.skill,
                    signal_type="pkg_drift",
                    severity="warn",
                    title=f"🔄 Refresh `{pin.skill}` — `{name}` {pinned} → {latest}",
                    body=body,
                    automation_tier=pin.automation_tier,
                )
            )
    return out


def detect_issue_closure(pin: PinFile, gh_token: str | None) -> list[Signal]:
    out: list[Signal] = []
    for ki in pin.known_issues:
        url = ki.get("upstream_url")
        status = ki.get("status", "open")
        if not url or status != "open":
            continue

        # Parse https://github.com/<owner>/<repo>/(issues|pull|discussions)/<n>
        m = re.match(
            r"^https://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)/?",
            url,
        )
        if not m:
            continue

        owner, repo, kind, num = m.groups()
        api_kind = "issues" if kind == "issues" else "pulls"
        headers = {"User-Agent": USER_AGENT}
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        try:
            r = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/{api_kind}/{num}",
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(
                f"WARN: github API failed for {url}: {e}",
                file=sys.stderr,
            )
            continue

        state = data.get("state")  # open | closed
        if state == "closed":
            body = "\n".join(
                [
                    f"## 🔄 Refresh `{pin.skill}` — upstream issue {ki['id']} CLOSED",
                    "",
                    f"- **Workaround**: {ki.get('description')}",
                    f"- **Upstream**: {url}",
                    f"- **Closed at**: {data.get('closed_at')}",
                    "",
                    "Re-run the pin file's `validation.script` **without** "
                    "the workaround and confirm the skill still passes. "
                    "If green:",
                    "",
                    "1. Update the pin file's `known_issues[].status` to "
                    "`closed_upstream_fixed`",
                    "2. Open a PR removing the workaround prose from SKILL.md",
                    "   (include `[skill-rewrite]` in the commit message — "
                    "required by `automation-pr-gate.yml`)",
                    "",
                    "If validation fails without the workaround → upstream "
                    "marked the issue closed but the symptom persists. "
                    "Comment here and leave `status: open`.",
                ]
            )
            out.append(
                Signal(
                    skill=pin.skill,
                    signal_type="issue_closed",
                    severity="info",
                    title=f"🔄 Refresh `{pin.skill}` — upstream {ki['id']} closed",
                    body=body,
                    automation_tier=pin.automation_tier,
                )
            )
    return out


def detect_link_rot(pin: PinFile) -> list[Signal]:
    broken: list[tuple[str, str]] = []
    for url in pin.docs:
        try:
            r = requests.head(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
                allow_redirects=True,
            )
            if r.status_code >= 400:
                broken.append((url, f"HTTP {r.status_code}"))
        except requests.RequestException as e:
            broken.append((url, str(e)))

    if not broken:
        return []

    body = ["## 🔄 Refresh `{}` — link rot detected".format(pin.skill), ""]
    for url, reason in broken:
        body.append(f"- `{url}` — {reason}")
    body.extend(
        [
            "",
            "Audit each URL: if upstream moved the doc, update the pin "
            "file's `docs_to_revalidate[]` AND the corresponding link in "
            "SKILL.md. Removing the URL altogether requires `[skill-rewrite]` "
            "commit-message opt-in.",
        ]
    )
    return [
        Signal(
            skill=pin.skill,
            signal_type="link_rot",
            severity="warn",
            title=f"🔄 Refresh `{pin.skill}` — link rot ({len(broken)} URL(s))",
            body="\n".join(body),
            automation_tier="issue_only",
        )
    ]


def detect_stale_validation(pin: PinFile, today: dt.date) -> Signal | None:
    lv = pin.last_validated
    if lv is None:
        return None
    age = (today - lv).days
    if age <= VALIDATION_AGE_DAYS:
        return None
    body = "\n".join(
        [
            f"## 🔄 Refresh `{pin.skill}` — validation age {age} days",
            "",
            f"- **Last validated**: {lv.isoformat()} ({age} days ago)",
            f"- **Cutoff**: {VALIDATION_AGE_DAYS} days",
            "",
            "Re-run the pin file's `validation.script` to confirm the "
            "skill still works against the currently pinned upstream. "
            "If green, update `last_validated` to today and bump SKILL.md "
            "`metadata.version` PATCH.",
        ]
    )
    return Signal(
        skill=pin.skill,
        signal_type="stale_validation",
        severity="info",
        title=f"🔄 Refresh `{pin.skill}` — validation age {age} days",
        body=body,
        automation_tier=pin.automation_tier,
    )


# ──────────────────────────── reporting ─────────────────────────────


def collect_signals(pins: list[PinFile], gh_token: str | None) -> list[Signal]:
    today = dt.date.today()
    signals: list[Signal] = []
    for pin in pins:
        s = detect_sha_drift(pin, gh_token)
        if s:
            signals.append(s)
        signals.extend(detect_pkg_drift(pin))
        signals.extend(detect_issue_closure(pin, gh_token))
        signals.extend(detect_link_rot(pin))
        s = detect_stale_validation(pin, today)
        if s:
            signals.append(s)
    return signals


def render_report(signals: list[Signal], pin_count: int) -> str:
    today = dt.date.today().isoformat()
    if not signals:
        return (
            f"# 🪴 Skill freshness — {today}\n\n"
            f"✅ All {pin_count} pinned skills are current. No drift "
            "detected across SHA / PyPI / upstream-issue / link-rot / "
            "validation-age signals."
        )

    by_signal: dict[str, list[Signal]] = {}
    for s in signals:
        by_signal.setdefault(s.signal_type, []).append(s)

    lines = [f"# 🪴 Skill freshness — {today}", ""]
    lines.append(
        f"Detected {len(signals)} drift event(s) across {pin_count} pinned skills.\n"
    )

    for sig_type in (
        "sha_drift",
        "pkg_drift",
        "issue_closed",
        "link_rot",
        "stale_validation",
    ):
        bucket = by_signal.get(sig_type) or []
        if not bucket:
            continue
        lines.append(f"## {sig_type} ({len(bucket)})")
        lines.append("")
        for s in bucket:
            assignee_note = (
                " — assigned to @Copilot"
                if s.automation_tier == "auto"
                else " — human action required"
            )
            lines.append(f"- **{s.skill}** — {s.title}{assignee_note}")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────── issue upsert ──────────────────────────


def upsert_issue(
    signal: Signal,
    repo: str,
    gh_token: str,
    assign_copilot: bool,
    labels: list[str],
    dry_run: bool,
) -> None:
    body = signal.body
    title = signal.title

    # Find an existing open issue with this title (idempotent upsert).
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_token}",
        "User-Agent": USER_AGENT,
    }
    search = requests.get(
        "https://api.github.com/search/issues",
        params={
            "q": f'repo:{repo} is:issue is:open in:title "{title}"',
        },
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )
    if search.status_code == 200:
        items = search.json().get("items", [])
        matched = next((it for it in items if it.get("title") == title), None)
    else:
        matched = None
        print(f"WARN: search API returned {search.status_code}", file=sys.stderr)

    payload: dict[str, Any] = {"body": body}
    if labels:
        payload["labels"] = labels

    want_copilot_assign = assign_copilot and signal.automation_tier == "auto"

    if matched:
        url = matched["url"]
        issue_node_id = matched.get("node_id")
        action = "edit"
        method = requests.patch
    else:
        url = f"https://api.github.com/repos/{repo}/issues"
        payload["title"] = title
        issue_node_id = None
        action = "create"
        method = requests.post

    if dry_run:
        print(f"[DRY-RUN] would {action} issue: {title}")
        if want_copilot_assign:
            print(f"[DRY-RUN] would assign @{COPILOT_BOT_LOGIN} via GraphQL")
        return

    r = method(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT)

    if r.status_code >= 300:
        print(
            f"ERROR: issue {action} for {signal.skill} returned "
            f"{r.status_code}: {r.text[:300]}",
            file=sys.stderr,
        )
        return

    print(f"✓ {action} issue: {title}", file=sys.stderr)

    # Now assign the Coding Agent bot via GraphQL (REST `assignees` doesn't
    # accept Bot accounts — this is the supported path).
    if want_copilot_assign:
        if not issue_node_id:
            issue_node_id = r.json().get("node_id")
        bot_id = get_copilot_bot_id(repo, gh_token)
        if not bot_id:
            print(
                f"WARN: Copilot Coding Agent ({COPILOT_BOT_LOGIN}) not in "
                f"suggestedActors for {repo} — leaving issue unassigned. "
                "Enable the Coding Agent feature on the repo/org to assign.",
                file=sys.stderr,
            )
        elif issue_node_id:
            ok = assign_copilot_to_issue(issue_node_id, bot_id, gh_token)
            if ok:
                print(f"  ↳ assigned @{COPILOT_BOT_LOGIN} via GraphQL", file=sys.stderr)


# ──────────────────────────── main ──────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print-report", action="store_true", help="emit Markdown to stdout")
    ap.add_argument("--output", type=pathlib.Path, help="write report to FILE")
    ap.add_argument("--upsert-issues", action="store_true", help="upsert GitHub issues")
    ap.add_argument(
        "--assign-copilot-on-auto-tier",
        action="store_true",
        help="auto-assign issues to @Copilot for skills with automation_tier=auto",
    )
    ap.add_argument(
        "--labels",
        default="freshness,automation",
        help="comma-separated labels to apply",
    )
    ap.add_argument("--dry-run", action="store_true", help="no API writes")
    ap.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repo (default: {DEFAULT_REPO})",
    )
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        print(f"ERROR: {SKILLS_DIR} does not exist", file=sys.stderr)
        return 2

    gh_token = os.environ.get("GH_TOKEN")
    if args.upsert_issues and not gh_token and not args.dry_run:
        print("ERROR: GH_TOKEN required for --upsert-issues", file=sys.stderr)
        return 2

    pins = discover_pin_files()
    print(f"Discovered {len(pins)} pin files", file=sys.stderr)

    signals = collect_signals(pins, gh_token)

    iso_week = dt.date.today().isocalendar()
    iso_week_str = f"{iso_week.year}-W{iso_week.week:02d}"
    print(f"::set-output name=iso_week::{iso_week_str}")  # for old-style GH Actions
    print(f"iso_week={iso_week_str}")

    report = render_report(signals, len(pins))

    if args.print_report:
        print(report)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
        print(f"Wrote report to {args.output}", file=sys.stderr)

    if args.upsert_issues:
        labels = [l.strip() for l in args.labels.split(",") if l.strip()]
        for signal in signals:
            upsert_issue(
                signal,
                repo=args.repo,
                gh_token=gh_token or "",
                assign_copilot=args.assign_copilot_on_auto_tier,
                labels=labels,
                dry_run=args.dry_run,
            )

    print(
        f"Done — {len(signals)} drift signal(s) across {len(pins)} pins",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
