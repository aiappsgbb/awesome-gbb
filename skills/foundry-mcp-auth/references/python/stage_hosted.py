"""Canonical build-input staging for the Hosted extension's path boundary.

Source of truth for `../../SKILL.md § Local recipe`.
Copies only canonical sources to a new disposable deployment directory.
"""

import argparse
from pathlib import Path
import shutil


def stage_hosted(destination: Path) -> Path:
    source = Path(__file__).resolve().parents[2]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    copies = {
        "templates/hosted/azure.yaml": "azure.yaml",
        "references/python/hosted_agent.py": "app/references/python/hosted_agent.py",
        "references/python/agent_instructions.py": "app/references/python/agent_instructions.py",
        "templates/hosted/Dockerfile": "app/templates/hosted/Dockerfile",
        "templates/hosted/pyproject.toml": "app/templates/hosted/pyproject.toml",
    }
    for original, target in copies.items():
        output = destination / target
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / original, output)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(stage_hosted(args.destination))
