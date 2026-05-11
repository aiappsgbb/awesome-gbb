"""Build Teams manifest zip for sideloading (postprovision hook).

Prompt starters (M365 Copilot prompt-suggestion chips) for a Custom
Engine Agent are defined as `bots[0].commandLists[0].commands[]`
entries with `{title, description}` (see Microsoft Learn:
"Create prompt suggestions" — bots/how-to/conversations/prompt-suggestions).
NOT in `customEngineAgents[].conversationStarters[]` — that field is
NOT in the Teams v1.21 schema (additionalProperties: false on the
customEngineAgents item allows only `id` + `type`).

User-customizable prompt starters via env vars:
    STARTER_<N>_TITLE / STARTER_<N>_PROMPT  (N = 1..3)

Title becomes the visible chip, PROMPT becomes the description text.
If env vars are not set, the placeholder STARTER_<N> commands are
stripped (the bot still ships with the built-in `!reset` command).
"""

import json
import os
import zipfile
from pathlib import Path


def _resolve_starters() -> list[dict]:
    """Return commandLists-shaped {title, description} entries from env."""
    starters: list[dict] = []
    for n in (1, 2, 3):
        title = os.environ.get(f"STARTER_{n}_TITLE", "").strip()
        prompt = os.environ.get(f"STARTER_{n}_PROMPT", "").strip()
        if title and prompt:
            starters.append(
                {"title": title[:32], "description": prompt[:128]}
            )
    return starters


def build_manifest(
    bot_client_id: str,
    agent_name: str,
    agent_description: str = "",
    developer_name: str = "",
    output_dir: str = "copilot",
):
    """Build the Teams app package zip, replacing all placeholder tokens."""
    src = Path("copilot/teams_package")
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    manifest = json.loads((src / "manifest.json").read_text())

    # Replace all tokens — respect Teams manifest length limits
    manifest["id"] = bot_client_id
    cea = manifest["copilotAgents"]["customEngineAgents"][0]
    cea["id"] = bot_client_id
    manifest["bots"][0]["botId"] = bot_client_id
    manifest["name"]["short"] = agent_name[:30]            # max 30 chars
    manifest["name"]["full"] = agent_name[:100]             # max 100 chars
    if agent_description:
        manifest["description"]["short"] = agent_description[:80]   # max 80 chars
        manifest["description"]["full"] = agent_description[:4000]  # max 4000 chars
    if developer_name:
        manifest["developer"]["name"] = developer_name

    # Prompt starters — replace placeholder STARTER_<N> commands with
    # env-provided values, or strip them entirely (leaving the bot with
    # just the built-in `!reset` command).
    starters = _resolve_starters()
    cmd_list = manifest["bots"][0]["commandLists"][0]
    cmd_list["commands"] = [
        c for c in cmd_list["commands"]
        if not (
            isinstance(c.get("title"), str)
            and c["title"].startswith("__STARTER_")
        )
    ]
    cmd_list["commands"].extend(starters)

    zip_path = out / "copilot_package.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for icon in ("color.png", "outline.png"):
            icon_path = src / icon
            if icon_path.exists():
                zf.write(icon_path, icon)

    print(f"Teams package: {zip_path}")
    if starters:
        print(f"  prompt starters: {len(starters)}")
    return zip_path


if __name__ == "__main__":
    build_manifest(
        bot_client_id=os.environ.get("BOT_APP_ID", "<uami-client-id>"),
        agent_name=os.environ.get("AGENT_DISPLAY_NAME", "My Agent"),
        agent_description=os.environ.get("AGENT_DESCRIPTION", ""),
        developer_name=os.environ.get("DEVELOPER_NAME", ""),
    )
