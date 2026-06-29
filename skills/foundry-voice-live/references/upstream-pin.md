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
    version: "2.44.0"
    specifier: "~=2.44.0"
    source: pypi
  - name: azure-identity
    version: "1.25.3"
    specifier: "~=1.25.3"
    source: pypi
  - name: fastrtc
    version: "0.0.34"
    specifier: "~=0.0.34"
    source: pypi
  - name: gradio
    version: "5.50.0"
    specifier: "~=5.50.0"
    source: pypi
  - name: azure-ai-voicelive
    version: "1.2.0"
    specifier: "~=1.2.0"
    source: pypi
known_issues: []
docs_to_revalidate:
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live"
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to"
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-04-10"
  - "https://learn.microsoft.com/azure/ai-foundry/openai/concepts/audio"
validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== foundry-voice-live pin validation ==="

    WORK=".upstream-pin-smoke/foundry-voice-live"
    rm -rf "$WORK"
    mkdir -p "$WORK"
    python -m venv "$WORK/.venv"
    . "$WORK/.venv/bin/activate"
    python -m pip install --quiet --upgrade pip

    echo "=== Installing packages ==="
    pip install --quiet \
      "openai~=2.44.0" \
      "azure-identity~=1.25.3" \
      "fastrtc~=0.0.34" \
      "gradio~=5.50.0" \
      "azure-ai-voicelive[aiohttp]~=1.2.0"

    echo "=== Import smoke tests ==="
    python -c "from openai import AsyncAzureOpenAI; print('openai.AsyncAzureOpenAI OK')"
    python -c "from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider; print('azure.identity.aio OK')"
    python -c "from fastrtc import AsyncStreamHandler, WebRTC, wait_for_item; print('fastrtc OK')"
    python -c "import gradio as gr; print('gradio OK')"
    python -c "
    from azure.ai.voicelive.aio import connect
    from azure.ai.voicelive.models import (
        AzureSemanticVad,
        AzureStandardVoice,
        MCPServer,
        RequestSession,
    )
    import inspect
    sig = inspect.signature(connect)
    assert 'endpoint' in sig.parameters, 'connect() missing endpoint kwarg'
    assert 'credential' in sig.parameters, 'connect() missing credential kwarg'
    assert 'api_version' in sig.parameters, 'connect() missing api_version kwarg'
    assert 'model' in sig.parameters, 'connect() missing model kwarg'
    fields = {f.name for f in AzureSemanticVad.__attrs_attrs__} if hasattr(AzureSemanticVad, '__attrs_attrs__') else set(dir(AzureSemanticVad))
    for ga_field in ('create_response', 'auto_truncate', 'interrupt_response'):
        assert ga_field in fields, f'AzureSemanticVad missing GA field: {ga_field}'
    print('voicelive-sdk-import-ok')
    "

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
    - "voicelive-sdk-import-ok"
    - "AsyncAzureOpenAI.realtime + websocket_base_url OK"
    - "VALIDATION_PASSED"
last_validated: "2026-06-29"
validated_by: "copilot-bot"
---

# Upstream Pin — foundry-voice-live

## Tier B — SDK / Demo Wrapper

This skill wraps the `unsafecode/voice-live-gradio` demo repository,
the `openai` SDK's realtime API surface for Azure Voice Live (GA
2026-04-10), and the native `azure-ai-voicelive` Python SDK.

### What's pinned

| Component | Pin | Tracks |
|-----------|-----|--------|
| Demo repo | SHA `ad612a6` on `main` | Three-rung architecture, benchmark harness, UI |
| `openai` | `~=2.0.0` | `AsyncAzureOpenAI.realtime.connect()` + `websocket_base_url` kwarg |
| `azure-identity` | `~=1.24.0` | `DefaultAzureCredential` + `get_bearer_token_provider` async |
| `fastrtc` | `~=0.0.34` | `AsyncStreamHandler`, `WebRTC`, `wait_for_item` |
| `gradio` | `~=5.42.0` | Blocks UI, state management |
| `azure-ai-voicelive` | `~=1.2.0` | Native `connect()` + `AzureSemanticVad` GA fields (`create_response`, `auto_truncate`, `interrupt_response`), `MCPServer`, `AzureStandardVoice` |

### Validation

The validation script verifies:
1. All five packages install cleanly (including `azure-ai-voicelive`
   with the `[aiohttp]` extra required for the async `connect` path).
2. Key imports succeed (`AsyncAzureOpenAI`, `DefaultAzureCredential`,
   `AsyncStreamHandler`, `gradio`, `azure.ai.voicelive.aio.connect`).
3. The `websocket_base_url` kwarg exists on `AsyncAzureOpenAI.__init__`
   (the critical Voice Live parameter for Rungs 2–3).
4. The `.realtime` attribute exists on the openai client class.
5. `azure.ai.voicelive.aio.connect()` accepts `endpoint`, `credential`,
   `api_version`, and `model` kwargs (Rung 4 surface).
6. `AzureSemanticVad` exposes the 2026-04-10 GA fields
   `create_response`, `auto_truncate`, and `interrupt_response`
   (catches preview→GA field drift).

### Audit trail

| Date | By | What |
|------|----|------|
| 2026-05-28 | ricchi | Initial pin. Verified against voice-live-gradio v0.3.0 (ad612a6). All imports pass, websocket_base_url confirmed in openai SDK. |
| 2026-06-08 | ricchi | Add `azure-ai-voicelive ~=1.2.0` (Rung 4). Bump docs URL to `voice-live-api-reference-2026-04-10` (302 OK). Extend validation.script with native SDK import + `AzureSemanticVad` GA field probe. Other 4 package versions unchanged (no upstream drift). |
