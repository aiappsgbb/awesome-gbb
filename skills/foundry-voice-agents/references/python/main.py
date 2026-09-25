"""Canonical draft command entry point.

Source of truth for `../../SKILL.md § Run the candidate`.
Definition rendering is offline. Live subcommands require explicit approval flags.
"""

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from azure.ai.projects import AIProjectClient
from azure.ai.projects.aio import AIProjectClient as AsyncAIProjectClient
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential
from azure.identity.aio import AzureCliCredential as AsyncAzureCliCredential

from definition import Consent, build_definition, check_endpoint, require_consent
from lifecycle import connect, require_version
from session import exchange, read_pcm, save_pcm


def verify_context() -> None:
    required = ("AZURE_CONFIG_DIR", "AZD_CONFIG_DIR", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID")
    if any(not os.environ.get(name) for name in required):
        raise RuntimeError("Explicit isolated CLI paths, tenant and subscription are required")
    account = json.loads(subprocess.check_output(
        ["az", "account", "show", "--output", "json"], text=True, timeout=30
    ))
    if (account["tenantId"] != os.environ["AZURE_TENANT_ID"]
            or account["id"] != os.environ["AZURE_SUBSCRIPTION_ID"]):
        raise RuntimeError("Isolated CLI identity does not match the approved scope")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Voice Agent preview client; see the scoped validation record")
    commands = result.add_subparsers(dest="command", required=True)
    render = commands.add_parser("definition", help="Render the canonical definition without network access")
    render.add_argument("--model", required=True)
    render.add_argument("--model-type", choices=("managed", "self_deployed"), default="managed")
    create = commands.add_parser("create", help="Create only a new uniquely named voice agent")
    create.add_argument("--endpoint", required=True)
    create.add_argument("--model", required=True)
    create.add_argument("--model-type", choices=("managed", "self_deployed"), default="managed")
    create.add_argument("--approve-create", action="store_true")
    create.add_argument("--approve-store", action="store_true")
    talk = commands.add_parser("talk", help="Send approved synthetic WAV, never record a microphone")
    talk.add_argument("--endpoint", required=True)
    talk.add_argument("--name", required=True)
    talk.add_argument("--version", required=True)
    talk.add_argument("--input", type=Path, required=True)
    talk.add_argument("--interrupt", type=Path)
    talk.add_argument("--approve-send", action="store_true")
    talk.add_argument("--approve-store", action="store_true")
    talk.add_argument("--output", type=Path)
    talk.add_argument("--approve-local-audio", action="store_true")
    return result


async def talk(args: argparse.Namespace, consent: Consent) -> None:
    require_consent(args.approve_send, "sending the specified synthetic audio")
    if args.output:
        require_consent(consent.save_local_audio, "writing the specified output WAV")
        if args.output.exists():
            raise FileExistsError("Refusing to overwrite output")
    pcm = read_pcm(args.input)
    interrupt = read_pcm(args.interrupt) if args.interrupt else None
    verify_context()
    # Pin a unique, otherwise immutable name; the realtime SDK connects by name.
    with AzureCliCredential() as credential, AIProjectClient(
        endpoint=args.endpoint, credential=credential, allow_preview=True
    ) as project:
        definition = require_version(project, args.name, args.version)
        if definition.greeting is None:
            raise ValueError("This client requires the canonical startup greeting")
        if definition.as_dict() != build_definition(
            definition.model or "", model_type=definition.model_type or "", consent=consent
        ).as_dict():
            raise ValueError("Agent configuration differs from the canonical approved definition")
    async with AsyncAzureCliCredential() as credential, AsyncAIProjectClient(
        endpoint=args.endpoint, credential=credential, allow_preview=True
    ) as project:
        async with connect(project, args.name, uuid.uuid4().hex, consent) as connection:
            evidence = await exchange(connection, pcm, interruption=interrupt)
    with AzureCliCredential() as credential, AIProjectClient(
        endpoint=args.endpoint, credential=credential, allow_preview=True
    ) as project:
        require_version(project, args.name, args.version)
    if args.output:
        save_pcm(args.output, evidence.audio, consent)
    # Do not serialize audio, transcripts, service URLs or tool arguments.
    summary = asdict(evidence)
    del summary["audio"]
    del summary["output_transcripts"]
    del summary["reply_transcript"]
    summary.update(agent_name=args.name, agent_version=args.version, trace_verified=False)
    print(json.dumps(summary, indent=2))


def main() -> None:
    args = parser().parse_args()
    if args.command == "definition":
        print(json.dumps(build_definition(args.model, model_type=args.model_type).as_dict(), indent=2))
        return
    args.endpoint = check_endpoint(args.endpoint)
    consent = Consent(
        store=args.approve_store,
        save_local_audio=getattr(args, "approve_local_audio", False),
    )
    if args.command == "create":
        require_consent(args.approve_create, "creating a new agent version")
        definition = build_definition(args.model, model_type=args.model_type, consent=consent)
        verify_context()
        name = "ci-smoke-voice-" + uuid.uuid4().hex[:12]
        # Emit intent first: if the request is interrupted, inspect this exact name,
        # not a replacement. Keep stdout in the owner's private run inventory.
        print(json.dumps({"intent": "create", "agent_name": name}), flush=True)
        with AzureCliCredential() as credential, AIProjectClient(
            endpoint=args.endpoint, credential=credential, allow_preview=True
        ) as project:
            created = project.agents.create_version(agent_name=name, definition=definition)
            print(json.dumps({"agent_name": name, "version": created.version, "store": consent.store}))
    else:
        asyncio.run(talk(args, consent))


if __name__ == "__main__":
    try:
        main()
    except AzureError as error:
        print(f"Azure operation failed ({type(error).__name__}); use protected diagnostics", file=sys.stderr)
        sys.exit(1)
