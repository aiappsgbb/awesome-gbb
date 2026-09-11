"""Canonical user-authenticated Prompt and Hosted Responses routing.

Source of truth for `../../SKILL.md § Agent integration`.
The caller owns its isolated credential, private transport and consent UX.
"""


def invoke_agent(
    project, agent_name: str, kind: str, user_input: str, *,
    http_client_factory, previous_response_id: str | None = None,
    agent_version: str | None = None,
    require_tool: bool = True,
):
    if kind not in ("prompt", "hosted") or not agent_name.strip() or not user_input.strip():
        raise ValueError("Explicit prompt/hosted kind, agent name and input are required")
    if agent_version is not None and (kind != "prompt" or not agent_version.isdigit()):
        raise ValueError("Explicit versions here apply only to Prompt agent references")
    if type(require_tool) is not bool:
        raise ValueError("require_tool must be an explicit boolean")
    options = {
        "input": user_input,
        "max_output_tokens": 1000,
    }
    if require_tool:
        options["tool_choice"] = "required"
    if kind == "prompt":
        options["extra_body"] = {"agent_reference": {"type": "agent_reference", "name": agent_name}}
        if agent_version is not None:
            options["extra_body"]["agent_reference"]["version"] = agent_version
    if previous_response_id:
        options["previous_response_id"] = previous_response_id
    with project.get_openai_client(
        agent_name=agent_name if kind == "hosted" else None,
        http_client=http_client_factory(), max_retries=0,
    ) as client:
        response = client.responses.create(**options)
    if response.status == "failed":
        code = response.error.code if response.error else "unknown"
        raise RuntimeError(f"Agent response failed ({code}); inspect response {response.id} before retrying")
    if not response.output:
        raise RuntimeError(f"Agent response {response.id} has empty output; no demo success was demonstrated")
    return response
