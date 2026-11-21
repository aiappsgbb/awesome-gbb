"""Local SIGKILL crash-recovery test for the resilient Responses handler.

Exercises `references/python/resilience/resilient_agent.py` (the canonical handler
behind SKILL.md § Long-running and crash-resilient agents) with the SDK's local
file-backed task, response and stream stores. No Azure, no model calls.

Scenario:
1. Start the handler, POST ``store=true, background=true, stream=true``.
2. Read SSE until the first phase is checkpointed, then SIGKILL the process
   while the second phase is in flight.
3. Restart with the same ``AGENTSERVER_STATE_ROOT``. Startup recovery must
   re-enter the handler with ``is_recovery=True`` and ``start == 1``.
4. The response completes; each side effect is issued once; the SSE replay
   (``GET /responses/{id}?stream=true``) carries exactly one
   ``response.created`` and one ``response.completed``; reconnecting with
   ``starting_after=<last seen sequence_number>`` returns only later events.

Requires the pinned stack in `references/python/resilience/requirements.txt`.
Run: ``python -m unittest discover -s skills/foundry-hosted-agents/tests -v``
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

AGENT = (Path(__file__).resolve().parents[1] / "references" / "python" / "resilience" / "resilient_agent.py")
PHASE_SECONDS = 2.0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(port: int, proc: subprocess.Popen, deadline: float = 60.0) -> None:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with {proc.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError("server did not start")


def _events(lines):
    for raw in lines:
        line = raw.decode().strip()
        if line.startswith("data:"):
            yield json.loads(line[5:].strip())


def _read_journal(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class ResilientRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.journal = root / "journal.jsonl"
        self.port = _free_port()
        self.env = dict(os.environ)
        self.env.update({
            "AGENTSERVER_STATE_ROOT": str(root / "state"),
            "AGENTSERVER_TASKS_BACKEND": "local",
            "RESILIENCE_JOURNAL": str(self.journal),
            "RESILIENCE_PHASE_SECONDS": str(PHASE_SECONDS),
            "PORT": str(self.port),
            "AZURE_AI_AGENTSERVER_DISABLE_EXPERIMENTAL_WARNING": "1",
        })
        for key in ("FOUNDRY_HOSTING_ENVIRONMENT", "FOUNDRY_PROJECT_ENDPOINT",
                    "APPLICATIONINSIGHTS_CONNECTION_STRING", "OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.env.pop(key, None)
        self.procs: list[subprocess.Popen] = []

    def tearDown(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=10)
        self.tmp.cleanup()

    def _start(self) -> subprocess.Popen:
        proc = subprocess.Popen([sys.executable, str(AGENT)], env=self.env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(proc)
        _wait_ready(self.port, proc)
        return proc

    def _get(self, path: str) -> dict:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 200, body[:300])
        return json.loads(body)

    def test_sigkill_mid_phase_resumes_from_last_checkpoint(self) -> None:
        first = self._start()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("POST", "/responses", headers={"Content-Type": "application/json"},
                     body=json.dumps({"model": "local", "input": "crash me",
                                      "store": True, "background": True, "stream": True}))
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        response_id = None
        last_seq = -1
        for event in _events(resp):
            last_seq = event.get("sequence_number", last_seq)
            if event["type"] == "response.created":
                response_id = event["response"]["id"]
            checkpoints = [r for r in _read_journal(self.journal) if r["event"] == "checkpoint"]
            if checkpoints:
                break
        self.assertIsNotNone(response_id)
        # Phase 2 ("generate") is now in flight; kill before it can checkpoint.
        time.sleep(PHASE_SECONDS / 2)
        first.send_signal(signal.SIGKILL)
        first.wait(timeout=10)
        conn.close()
        self.assertEqual([r["phase"] for r in _read_journal(self.journal) if r["event"] == "checkpoint"],
                         ["analyze"])

        self._start()
        deadline = time.monotonic() + 90
        status = None
        while time.monotonic() < deadline:
            status = self._get(f"/responses/{response_id}").get("status")
            if status in ("completed", "failed", "cancelled", "incomplete"):
                break
            time.sleep(0.5)
        self.assertEqual(status, "completed")

        journal = _read_journal(self.journal)
        entries = [r for r in journal if r["event"] == "enter"]
        self.assertEqual([(e["is_recovery"], e["start"]) for e in entries], [(False, 0), (True, 1)])
        starts = [r["phase"] for r in journal if r["event"] == "phase_start"]
        self.assertEqual(starts, ["analyze", "generate", "generate", "refine"])
        effects = [r["phase"] for r in journal if r["event"] == "effect"]
        self.assertEqual(sorted(effects), ["analyze", "generate", "refine"])

        final = self._get(f"/responses/{response_id}")
        self.assertEqual(len(final["output"]), 3)

        full = self._replay(f"/responses/{response_id}?stream=true")
        types = [event["type"] for event in full]
        self.assertEqual(types.count("response.created"), 1, types)
        self.assertEqual(types.count("response.completed"), 1, types)
        # The recovered attempt's response.in_progress is the snapshot reset point.
        self.assertGreaterEqual(types.count("response.in_progress"), 2, types)
        seqs = [event["sequence_number"] for event in full]
        self.assertEqual(seqs, sorted(set(seqs)), "replay sequence numbers must be unique and ordered")

        # Reconnect from the last sequence number the client saw before the crash.
        tail = self._replay(f"/responses/{response_id}?stream=true&starting_after={last_seq}")
        self.assertTrue(tail, "reconnect returned no events")
        self.assertTrue(all(event["sequence_number"] > last_seq for event in tail))
        self.assertEqual(tail[-1]["type"], "response.completed")

    def _replay(self, path: str) -> list[dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("GET", path)
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        events = list(_events(resp))
        conn.close()
        return events

if __name__ == "__main__":
    unittest.main()
