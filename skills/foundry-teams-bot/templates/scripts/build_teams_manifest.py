"""Build Teams manifest zip for sideloading (postprovision hook)."""

import json
import os
import zipfile
from pathlib import Path


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
    manifest["copilotAgents"]["customEngineAgents"][0]["id"] = bot_client_id
    manifest["bots"][0]["botId"] = bot_client_id
    manifest["name"]["short"] = agent_name[:30]            # max 30 chars
    manifest["name"]["full"] = agent_name[:100]             # max 100 chars
    if agent_description:
        manifest["description"]["short"] = agent_description[:80]   # max 80 chars
        manifest["description"]["full"] = agent_description[:4000]  # max 4000 chars
    if developer_name:
        manifest["developer"]["name"] = developer_name

    zip_path = out / "copilot_package.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for icon in ("color.png", "outline.png"):
            icon_path = src / icon
            if icon_path.exists():
                zf.write(icon_path, icon)

    print(f"Teams package: {zip_path}")
    return zip_path


if __name__ == "__main__":
    build_manifest(
        bot_client_id=os.environ.get("BOT_APP_ID", "<uami-client-id>"),
        agent_name=os.environ.get("AGENT_DISPLAY_NAME", "My Agent"),
        agent_description=os.environ.get("AGENT_DESCRIPTION", ""),
        developer_name=os.environ.get("DEVELOPER_NAME", ""),
    )
