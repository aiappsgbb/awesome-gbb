"""Execute the canonical voice contract against an explicitly approved project.

Private inventory is written before mutations; cleanup operates only on this run.
No shared resource setup, telemetry toggle, role grant or CI dispatch.
"""

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import wave
from urllib.parse import urlsplit

import requests

from azure.ai.projects import AIProjectClient, models
from azure.ai.projects.aio import AIProjectClient as AsyncAIProjectClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.identity.aio import AzureCliCredential as AsyncAzureCliCredential

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "references/python"))
from definition import Consent, build_definition, check_endpoint
from lifecycle import connect, delete_conversation, delete_empty_agent, delete_version, read_audio, read_transcript, require_version
from main import verify_context
from session import TurnCollector, error_diagnostic, exchange, read_pcm, save_pcm
from synthetic_audio import synthesize


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: object) -> None:
    temporary = path.with_suffix(".pending")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(data, output, indent=2, default=str)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def evidence_metadata(collector: TurnCollector) -> dict:
    data = asdict(collector.evidence)
    data.pop("audio")
    transcripts = data.pop("output_transcripts")
    data.pop("reply_transcript")
    data["transcript_sha256"] = hashlib.sha256("\n".join(transcripts).encode()).hexdigest()
    return data


def begin_ci_attempt() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=SKILL.parents[1], check=True)
    receipt = Path(os.environ["RUNNER_TEMP"]) / (
        f"voice-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}.started"
    )
    with receipt.open("x") as output:
        output.write(stamp() + "\n")


def public_evidence(inventory: dict) -> dict:
    return {
        key: inventory.get(key)
        for key in ("run_id", "mode", "functional", "cleanup", "privacy_preflight",
                    "trace", "source_sha256", "failure", "cleanup_errors")
    } | {
        "agents": [
            {
                "name": owned["name"], "versions": owned["versions"],
                "cleanup": owned.get("cleanup", "pending"),
                "sessions": [
                    {key: session.get(key) for key in (
                        "case", "functional", "completed_turns", "tool_calls",
                        "interruptions", "readback", "readback_shape", "stored_audio_frames", "errors",
                    )}
                    for session in owned["sessions"]
                ],
            }
            for owned in inventory["agents"]
        ]
    }


def require_no_telemetry(credential, account_id: str, endpoint: str, speech_endpoint: str) -> None:
    account_name = account_id.rsplit("/accounts/", 1)[-1]
    project_name = urlsplit(endpoint).path.removeprefix("/api/projects/")
    if (
        not account_id.startswith("/subscriptions/" + os.environ["AZURE_SUBSCRIPTION_ID"] + "/")
        or "/" in account_name
        or not account_name
        or urlsplit(endpoint).hostname != account_name + ".services.ai.azure.com"
        or speech_endpoint.rstrip("/") != "https://" + account_name + ".cognitiveservices.azure.com"
        or not project_name or "/" in project_name
    ):
        raise ValueError("Account, project, Speech endpoint and approved subscription must agree")
    headers = {"Authorization": "Bearer " + credential.get_token("https://management.azure.com/.default").token}
    for scope in (account_id, account_id + "/projects/" + project_name):
        response = requests.get(
            "https://management.azure.com" + scope + "/connections",
            params={"api-version": "2026-07-01"}, headers=headers,
            timeout=(10, 30), allow_redirects=False,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Telemetry privacy preflight failed HTTP {response.status_code}")
        if any(item["properties"]["category"] == "AppInsights" for item in response.json()["value"]):
            raise PermissionError("Configured server tracing requires new content-capture consent; refusing invocation")


class RecordedConnection:
    def __init__(self, connection, record, persist):
        self.connection, self.record, self.persist = connection, record, persist

    def __getattr__(self, name):
        return getattr(self.connection, name)

    async def recv(self):
        event = await self.connection.recv()
        if isinstance(event, models.RealtimeServerEventSessionCreated):
            self.record.update(session_id=event.session.get("id"), conversation_id=event.conversation_id)
        if isinstance(event, models.RealtimeServerEventError):
            self.record.setdefault("errors", []).append(error_diagnostic(event))
        for key in ("event_id", "item_id", "response_id", "call_id"):
            value = event.get(key)
            if value:
                self.record.setdefault("returned_ids", {}).setdefault(key, [])
                if value not in self.record["returned_ids"][key]:
                    self.record["returned_ids"][key].append(value)
        self.persist()
        return event


async def run_session(endpoint, name, version, pcm, interruption, consent, record, persist):
    collector = TurnCollector()
    record.update(started=stamp(), client_session_id=uuid.uuid4().hex)
    persist()
    try:
        async with AsyncAzureCliCredential() as credential, AsyncAIProjectClient(
            endpoint=endpoint, credential=credential, allow_preview=True,
            retry_total=0, connection_timeout=15, read_timeout=45,
        ) as client:
            async with connect(client, name, record["client_session_id"], consent) as connection:
                result = await exchange(
                    RecordedConnection(connection, record, persist),
                    pcm, interruption=interruption, collector=collector,
                )
        if result.tool_calls < 1:
            raise RuntimeError("No real harmless function call observed")
        text = result.reply_transcript.lower()
        if not ("nine" in text or "9" in text or "09" in text):
            raise RuntimeError("Spoken transcript did not contain opening time")
        if not ("five" in text or "17" in text or "5" in text):
            raise RuntimeError("Spoken transcript did not contain closing time")
        record["functional"] = "pass"
        return result
    except Exception:
        record["functional"] = "fail"
        raise
    finally:
        record.update(ended=stamp(), **evidence_metadata(collector))
        persist()


def run(args) -> None:
    if not args.approve_live_synthetic:
        raise PermissionError("Explicit synthetic run/lifecycle approval is required")
    begin_ci_attempt()
    verify_context()
    endpoint = check_endpoint(args.endpoint)
    directory = args.evidence_dir.resolve()
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    run_id = uuid.uuid4().hex[:12]
    inventory = {
        "run_id": run_id, "owner": "authorized CI fixture operator",
        "purpose": "managed voice synthetic acceptance", "expiry": "end of this run",
        "started": stamp(), "endpoint": endpoint, "agents": [],
        "mode": "full_functional_without_configured_tracing",
        "consent": {
            "synthetic_transmission": True, "local_private_capture": True,
            "stored_cycle": True, "transcript_read": True, "audio_read": True,
            "delete_owned": True, "global_trace_content_toggle": False,
        },
        "local_files": [f"{key}.wav" for key in ("hours", "long", "interrupt")],
        "functional": "pending", "cleanup": "pending", "trace": "not_exercised",
        "source_sha256": {
            str(file.relative_to(SKILL)): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(SKILL.rglob("*"))
            if file.is_file() and "__pycache__" not in file.parts
        },
    }
    path = directory / "inventory.json"
    def persist():
        write_json(path, inventory)
        if getattr(args, "public_evidence", None):
            write_json(args.public_evidence, public_evidence(inventory))
    persist()
    error = None
    cleanup_errors = []
    with AzureCliCredential() as credential, AIProjectClient(
        endpoint=endpoint, credential=credential, allow_preview=True,
        retry_total=0, connection_timeout=15, read_timeout=45,
    ) as client:
        try:
            require_no_telemetry(credential, args.account_id, endpoint, args.speech_endpoint)
            inventory["privacy_preflight"] = "no_configured_account_or_project_tracing"
            persist()
            inputs = synthesize(directory, args.speech_endpoint, args.account_id, credential)
            pcm = {name: read_pcm(path) for name, path in inputs.items()}
            inventory["input_sha256"] = {
                name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in inputs.items()
            }
            persist()
            for stored in (False, True):
                name = f"ci-smoke-voice-{run_id}-{'stored' if stored else 'ephemeral'}"
                owned = {"name": name, "versions": [], "sessions": [], "create": "intent"}
                inventory["agents"].append(owned)
                persist()
                verify_context()
                created = client.agents.create_version(
                    agent_name=name, definition=build_definition(args.model, consent=Consent(store=stored)),
                    metadata={"voice_acceptance_run": run_id},
                )
                owned.update(create="returned", version=created.version)
                owned["versions"].append(created.version)
                persist()
                require_version(client, name, created.version)
                cases = ("hours",) if stored else ("hours", "interrupt")
                for case in cases:
                    record = {"case": case, "functional": "pending"}
                    owned["sessions"].append(record)
                    persist()
                    consent = Consent(store=stored, save_local_audio=True)
                    require_no_telemetry(credential, args.account_id, endpoint, args.speech_endpoint)
                    result = asyncio.run(run_session(
                        endpoint, name, created.version,
                        pcm["long"] if case == "interrupt" else pcm["hours"],
                        pcm["interrupt"] if case == "interrupt" else None,
                        consent, record, persist,
                    ))
                    require_version(client, name, created.version)
                    output = f"{name}-{case}.wav"
                    inventory["local_files"].append(output)
                    persist()
                    save_pcm(directory / output, result.audio, consent)
                    if not stored and result.conversation_id:
                        try:
                            client.beta.voice_agents.conversations.get(name, result.conversation_id)
                        except ResourceNotFoundError:
                            record["persistence_disabled"] = "verified_not_stored"
                        else:
                            raise RuntimeError("store=False unexpectedly yielded a persisted conversation")
                        persist()
                    if stored:
                        if not result.conversation_id:
                            raise RuntimeError("Stored cycle returned no conversation ID")
                        items = read_transcript(client, name, result.conversation_id, Consent(read_transcript=True))
                        roles = {item.get("role") for item in items}
                        if not {"user", "assistant"} <= roles:
                            raise RuntimeError("Stored caller/assistant transcript incomplete")
                        texts = {}
                        record["readback_shape"] = []
                        for item in items:
                            role = item.get("role")
                            parts = item.get("content") or []
                            texts.setdefault(role, []).extend(
                                part.get("transcript") or part.get("text") or "" for part in parts
                            )
                            record["readback_shape"].append({
                                "role": role, "type": item.get("type"),
                                "part_types": [part.get("type") for part in parts],
                                "text_characters": sum(len(part.get("transcript") or part.get("text") or "")
                                                       for part in parts),
                            })
                        persist()
                        caller = " ".join(texts.get("user", [])).lower()
                        assistant = " ".join(texts.get("assistant", [])).lower()
                        if "hours" not in caller or "fictional" not in assistant:
                            raise RuntimeError("Stored transcript does not match the synthetic scenario")
                        recording = read_audio(client, name, result.conversation_id, Consent(read_audio=True))
                        with wave.open(io.BytesIO(recording), "rb") as audio:
                            if audio.getnchannels() != 2 or audio.getnframes() == 0:
                                raise RuntimeError("Stored recording is not nonempty stereo audio")
                            record["stored_audio_frames"] = audio.getnframes()
                        record["stored_items"] = len(items)
                        record["readback"] = "pass"
                        record["transcript_meaning"] = "synthetic_hours_verified"
                        persist()
            inventory["functional"] = "pass"
        except Exception as exc:
            # This boundary retains non-success and always reconciles run-owned effects.
            error = exc
            inventory["functional"] = "fail"
            inventory["failure"] = {
                "type": type(exc).__name__,
                "status": getattr(exc, "status_code", None),
                "code": getattr(getattr(exc, "error", None), "code", None),
            }
            persist()
        finally:
            for owned in reversed(inventory["agents"]):
                try:
                    verify_context()
                    try:
                        client.agents.get(agent_name=owned["name"])
                    except ResourceNotFoundError:
                        owned["cleanup"] = "verified_absent"
                        persist()
                        continue
                    conversations = list(client.beta.voice_agents.conversations.list(owned["name"]))
                    owned["conversation_ids"] = [c.id for c in conversations]
                    versions = list(client.agents.list_versions(agent_name=owned["name"]))
                    if any(v.metadata.get("voice_acceptance_run") != run_id for v in versions):
                        raise RuntimeError("Version custody mismatch; refusing deletion")
                    owned["versions"] = [v.version for v in versions]
                    persist()
                    for conversation in conversations:
                        delete_conversation(client, owned["name"], conversation.id, Consent(delete=True))
                    for version in versions:
                        delete_version(client, owned["name"], version.version, Consent(delete=True))
                    delete_empty_agent(client, owned["name"], Consent(delete=True))
                    owned["cleanup"] = "verified_absent"
                except Exception as exc:
                    owned["cleanup"] = "blocked"
                    cleanup_errors.append(type(exc).__name__)
                persist()
            for relative in inventory["local_files"]:
                local = directory / relative
                local.unlink(missing_ok=True)
                if local.exists():
                    cleanup_errors.append("LocalFileStillPresent")
            inventory.update(
                cleanup="blocked" if cleanup_errors else "verified_absent",
                cleanup_errors=cleanup_errors, finished=stamp(),
            )
            persist()
    if cleanup_errors:
        raise RuntimeError("Owned cleanup blocked; reconcile private inventory before any new run") from error
    if error:
        raise RuntimeError("Voice acceptance failed; private inventory retains classification") from error
    print("VOICE_FUNCTIONAL=PASS CLEANUP=PASS TRACE=NOT_EXERCISED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--speech-endpoint", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--model", default="gpt-realtime")
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--approve-live-synthetic", action="store_true")
    parser.add_argument("--public-evidence", type=Path, help="Sanitized receipt retained outside the private run directory")
    run(parser.parse_args())
