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
    version: "2.53.0"
    specifier: "~=2.53.0"
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
    hold_below: "6.0.0"
    hold_reason: KI-001
  - name: azure-ai-voicelive
    version: "1.3.0"
    specifier: "~=1.3.0"
    source: pypi
known_issues:
  - id: KI-001
    description: "FastRTC 0.0.34 requires gradio>=4,<6; hold Gradio below 6 until FastRTC lifts its upper bound."
    upstream_url: https://github.com/gradio-app/fastrtc/issues/428
    status: open
    workaround_location: SKILL.md § "Dependencies"
docs_to_revalidate:
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live"
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to"
  - "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-04-10"
  - "https://learn.microsoft.com/azure/foundry-classic/openai/concepts/audio"
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
      "openai~=2.53.0" \
      "azure-identity~=1.25.3" \
      "fastrtc~=0.0.34" \
      "gradio~=5.50.0" \
      "azure-ai-voicelive[aiohttp]~=1.3.0"

    echo "=== Import smoke tests ==="
    python - <<'PY'
    import inspect
    from importlib.metadata import version

    import fastrtc
    import gradio
    from azure.ai.voicelive.aio import connect
    from azure.ai.voicelive.models import AzureSemanticVad, ItemType, MCPApprovalResponseRequestItem, MCPApprovalType, MCPServer
    from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
    from fastrtc import AsyncStreamHandler, WebRTC, wait_for_item
    from openai import AsyncAzureOpenAI

    assert AsyncAzureOpenAI is not None
    print("openai.AsyncAzureOpenAI OK")
    assert DefaultAzureCredential is not None and get_bearer_token_provider is not None
    print("azure.identity.aio OK")
    assert AsyncStreamHandler is not None and WebRTC is not None and wait_for_item is not None
    print("fastrtc OK")
    assert gradio is not None and fastrtc is not None
    print("gradio OK")

    connect_sig = inspect.signature(connect)
    assert "endpoint" in connect_sig.parameters, "connect() missing endpoint kwarg"
    assert "credential" in connect_sig.parameters, "connect() missing credential kwarg"
    assert "api_version" in connect_sig.parameters, "connect() missing api_version kwarg"
    assert "model" in connect_sig.parameters, "connect() missing model kwarg"
    assert connect_sig.parameters["api_version"].default == "2026-07-15", (
        "connect() api_version default drifted from 2026-07-15"
    )

    init_sig = inspect.signature(AsyncAzureOpenAI.__init__)
    assert "azure_endpoint" in init_sig.parameters, "azure_endpoint missing from AsyncAzureOpenAI.__init__"
    assert "azure_deployment" in init_sig.parameters, "azure_deployment missing from AsyncAzureOpenAI.__init__"
    assert "api_version" in init_sig.parameters, "api_version missing from AsyncAzureOpenAI.__init__"
    assert "websocket_base_url" in init_sig.parameters, "websocket_base_url missing from AsyncAzureOpenAI.__init__"
    assert hasattr(AsyncAzureOpenAI, "realtime"), "AsyncAzureOpenAI missing class realtime attribute"

    fields = set(getattr(AzureSemanticVad, "__annotations__", {}))
    fields.update(getattr(AzureSemanticVad, "model_fields", {}))
    if hasattr(AzureSemanticVad, "__attrs_attrs__"):
        fields.update(field.name for field in AzureSemanticVad.__attrs_attrs__)
    fields.update(dir(AzureSemanticVad))
    for ga_field in ("create_response", "auto_truncate", "interrupt_response"):
        assert ga_field in fields, f"AzureSemanticVad missing GA field: {ga_field}"

    assert MCPServer is not None, "MCPServer missing from azure-ai-voicelive models"
    assert MCPApprovalType is not None, "MCPApprovalType missing from azure-ai-voicelive models"
    assert MCPApprovalResponseRequestItem is not None, (
        "MCPApprovalResponseRequestItem missing from azure-ai-voicelive models"
    )
    assert ItemType.MCP_APPROVAL_REQUEST.value == "mcp_approval_request", (
        "ItemType.MCP_APPROVAL_REQUEST wire value drifted"
    )
    assert ItemType.MCP_APPROVAL_RESPONSE.value == "mcp_approval_response", (
        "ItemType.MCP_APPROVAL_RESPONSE wire value drifted"
    )
    approval_members = getattr(MCPApprovalType, "__members__", {})
    assert "NEVER" in approval_members, "MCPApprovalType.NEVER missing"
    assert "ALWAYS" in approval_members, "MCPApprovalType.ALWAYS missing"
    assert MCPApprovalType.NEVER is not None
    assert MCPApprovalType.ALWAYS is not None

    assert version("openai").startswith("2.53.")
    assert version("azure-identity").startswith("1.25.")
    assert version("fastrtc").startswith("0.0.")
    assert version("gradio").startswith("5.50.")
    assert version("azure-ai-voicelive").startswith("1.3.")

    print("voicelive-sdk-13-default-2026-07-15")
    print("voicelive-mcp-approval-request-response-surface")
    print("openai-253-realtime-surface")
    print("fastrtc-gradio5-compatible")
    PY

    echo "=== All checks passed ==="
    echo "VALIDATION_PASSED"
  expected_output:
    - "openai.AsyncAzureOpenAI OK"
    - "azure.identity.aio OK"
    - "fastrtc OK"
    - "gradio OK"
    - "voicelive-sdk-13-default-2026-07-15"
    - "voicelive-mcp-approval-request-response-surface"
    - "openai-253-realtime-surface"
    - "fastrtc-gradio5-compatible"
    - "VALIDATION_PASSED"
last_validated: "2026-08-05"
validated_by: "ricchi"
known_issues_count: 1
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
| `openai` | `~=2.53.0` | `AsyncAzureOpenAI.realtime.connect()` + `websocket_base_url` kwarg |
| `azure-identity` | `~=1.25.3` | `DefaultAzureCredential` + `get_bearer_token_provider` async |
| `fastrtc` | `~=0.0.34` | `AsyncStreamHandler`, `WebRTC`, `wait_for_item`; requires `gradio>=4,<6` |
| `gradio` | `~=5.50.0` | Blocks UI, state management; held below 6 by KI-001 |
| `azure-ai-voicelive` | `~=1.3.0` | Native `connect()` default API version `2026-07-15`, `AzureSemanticVad` GA fields, and MCP approval request/response item models |

### Known issues

#### KI-001 - FastRTC blocks Gradio 6

FastRTC `0.0.34` declares `gradio>=4,<6`, so this pin holds
`gradio~=5.50.0` and records the hold with `hold_below: "6.0.0"` +
`hold_reason: KI-001` until upstream issue #428 resolves.

### Validation

The validation script verifies:
1. All five packages install cleanly (including `azure-ai-voicelive`
   with the `[aiohttp]` extra required for the async `connect` path).
2. Key imports succeed (`AsyncAzureOpenAI`, `DefaultAzureCredential`,
   `AsyncStreamHandler`, `gradio`, `azure.ai.voicelive.aio.connect`,
   `MCPServer`, `MCPApprovalType`, `ItemType`,
   `MCPApprovalResponseRequestItem`).
3. The `websocket_base_url` kwarg exists on `AsyncAzureOpenAI.__init__`
   (the critical Voice Live parameter for Rungs 2–3).
4. The `.realtime` attribute exists on the openai client class.
5. `azure.ai.voicelive.aio.connect()` accepts `endpoint`, `credential`,
   `api_version`, and `model` kwargs, with default API version
   `2026-07-15` (Rung 4 surface).
6. `AzureSemanticVad` exposes the 2026-04-10 GA fields
   `create_response`, `auto_truncate`, and `interrupt_response`
   (catches preview→GA field drift).
7. `MCPApprovalType.NEVER` and `.ALWAYS` exist alongside `MCPServer`,
   `MCPApprovalResponseRequestItem`, and exact `ItemType` wire values
   `mcp_approval_request` / `mcp_approval_response` (catches SDK
   item-model symbol drift).

### Audit trail

| Date | By | What |
|------|----|------|
| 2026-05-28 | ricchi | Initial pin. Verified against voice-live-gradio v0.3.0 (ad612a6). All imports pass, websocket_base_url confirmed in openai SDK. |
| 2026-06-08 | ricchi | Add `azure-ai-voicelive ~=1.2.0` (Rung 4). Bump docs URL to `voice-live-api-reference-2026-04-10` (302 OK). Extend validation.script with native SDK import + `AzureSemanticVad` GA field probe. Other 4 package versions unchanged (no upstream drift). |
| 2026-08-05 | ricchi | Refresh compatible SDK stack: `openai ~=2.53.0`, `azure-ai-voicelive ~=1.3.0`, and keep `gradio ~=5.50.0` below 6 per FastRTC KI-001. Migrate Realtime concepts docs URL to `foundry-classic`. Correct MCP approval validation to smoke `ItemType.MCP_APPROVAL_REQUEST` / `.MCP_APPROVAL_RESPONSE` exact wire values and `MCPApprovalResponseRequestItem`. |
