---
skill: foundry-voice-live
freshness_tier: B
automation_tier: auto
schema_version: 2
upstream:
  repo: "https://github.com/unsafecode/voice-live-gradio"
  ref: "main"
  pinned_sha: "ad612a644a60b041c37a3c98407e48f51a9e43cb"
packages:
  - name: openai
    version: "2.0.0"
    specifier: "~=2.0.0"
    source: pypi
  - name: azure-identity
    version: "1.24.0"
    specifier: "~=1.24.0"
    source: pypi
  - name: fastrtc
    version: "0.0.34"
    specifier: "~=0.0.34"
    source: pypi
  - name: gradio
    version: "5.42.0"
    specifier: "~=5.42.0"
    source: pypi
known_issues: []
docs_to_revalidate:
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live"
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to"
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2025-10-01"
  - "https://learn.microsoft.com/azure/ai-services/openai/concepts/realtime-audio"
validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== foundry-voice-live pin validation ==="

    echo "=== Installing packages ==="
    pip install --quiet \
      "openai~=2.0.0" \
      "azure-identity~=1.24.0" \
      "fastrtc~=0.0.34" \
      "gradio~=5.42.0"

    echo "=== Import smoke tests ==="
    python -c "from openai import AsyncAzureOpenAI; print('openai.AsyncAzureOpenAI OK')"
    python -c "from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider; print('azure.identity.aio OK')"
    python -c "from fastrtc import AsyncStreamHandler, WebRTC, wait_for_item; print('fastrtc OK')"
    python -c "import gradio as gr; print('gradio OK')"

    echo "=== Realtime connect API surface ==="
    python -c "
    from openai import AsyncAzureOpenAI
    import inspect
    client_cls = AsyncAzureOpenAI
    assert hasattr(client_cls, 'realtime'), 'AsyncAzureOpenAI missing .realtime'
    sig = inspect.signature(client_cls.__init__)
    assert 'websocket_base_url' in sig.parameters, 'websocket_base_url not in AsyncAzureOpenAI.__init__'
    print('AsyncAzureOpenAI.realtime + websocket_base_url OK')
    "

    echo "=== All checks passed ==="
    echo "VALIDATION_PASSED"
  expected_output:
    - "openai.AsyncAzureOpenAI OK"
    - "azure.identity.aio OK"
    - "fastrtc OK"
    - "gradio OK"
    - "AsyncAzureOpenAI.realtime + websocket_base_url OK"
    - "VALIDATION_PASSED"
last_validated: "2026-05-28"
validated_by: "ricchi"
---

# Upstream Pin — foundry-voice-live

## Tier B — SDK / Demo Wrapper

This skill wraps the `unsafecode/voice-live-gradio` demo repository and
the `openai` SDK's realtime API surface for Azure Voice Live (GA 2025-10-01).

### What's pinned

| Component | Pin | Tracks |
|-----------|-----|--------|
| Demo repo | SHA `ad612a6` on `main` | Three-rung architecture, benchmark harness, UI |
| `openai` | `~=2.0.0` | `AsyncAzureOpenAI.realtime.connect()` + `websocket_base_url` kwarg |
| `azure-identity` | `~=1.24.0` | `DefaultAzureCredential` + `get_bearer_token_provider` async |
| `fastrtc` | `~=0.0.34` | `AsyncStreamHandler`, `WebRTC`, `wait_for_item` |
| `gradio` | `~=5.42.0` | Blocks UI, state management |

### Validation

The validation script verifies:
1. All four packages install cleanly
2. Key imports succeed (`AsyncAzureOpenAI`, `DefaultAzureCredential`,
   `AsyncStreamHandler`, `gradio`)
3. The `websocket_base_url` kwarg exists on `AsyncAzureOpenAI.__init__`
   (the critical Voice Live parameter)
4. The `.realtime` attribute exists on the client class

### Audit trail

| Date | By | What |
|------|----|------|
| 2026-05-28 | ricchi | Initial pin. Verified against voice-live-gradio v0.3.0 (ad612a6). All imports pass, websocket_base_url confirmed in openai SDK. |
