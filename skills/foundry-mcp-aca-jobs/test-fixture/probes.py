"""Functional Jobs assertions. Resource mutation/custody is owned by the runner helper."""
import asyncio
import json
from urllib.parse import urlsplit


def dump(value):
    return value.model_dump(mode="json", by_alias=True) if hasattr(value, "model_dump") else value


def payload(result):
    for candidate in (getattr(result, "data", None), getattr(result, "structured_content", None), dump(result)):
        candidate = dump(candidate)
        if isinstance(candidate, dict):
            for key in ("structuredContent", "structured_content", "data"):
                if isinstance(candidate.get(key), dict):
                    return candidate[key]
            return candidate
    raise AssertionError("tool result has no structured object")


def result_url(value, storage_host):
    assert set(value) == {"status", "resultUrl"} and value["status"] == "Succeeded"
    parsed = urlsplit(value["resultUrl"])
    assert parsed.scheme == "https" and parsed.hostname == storage_host
    assert not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
    return value["resultUrl"]


def agent_calls(response, expected_input, expected_key):
    calls = [item for item in response.output if getattr(item, "type", None) == "mcp_call"]
    assert len(calls) == 2
    names = {item.name: item for item in calls}
    assert set(names) == {"start_aca_job", "get_aca_job_status"}
    outputs = {}
    for name, item in names.items():
        assert getattr(item, "error", None) in (None, "")
        output = json.loads(item.output)
        assert isinstance(output, dict) and not output.get("isError")
        if "structuredContent" in output:
            output = output["structuredContent"]
        elif "content" in output:
            texts = [entry["text"] for entry in output["content"] if entry.get("type") == "text"]
            assert len(texts) == 1
            output = json.loads(texts[0])
        outputs[name] = output
    start = outputs["start_aca_job"]
    assert isinstance(start["taskId"], str) and start["taskId"]
    assert json.loads(names["start_aca_job"].arguments) == {
        "jobType": "short-job", "idempotencyKey": expected_key,
        "inputRef": expected_input, "callbackAlias": "ops",
    }
    assert json.loads(names["get_aca_job_status"].arguments) == {"taskId": start["taskId"]}
    assert outputs["get_aca_job_status"]["taskId"] == start["taskId"]
    assert outputs["get_aca_job_status"]["errorCode"] is None
    return start["taskId"]


async def direct(ledger, lifecycle):
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity.aio import AzureCliCredential
    from azure.storage.blob.aio import BlobClient
    from fastmcp import Client
    from fastmcp_tasks.client import TasksClientExtension, call_tool_task

    env = lifecycle.environment(ledger)
    storage = ledger.a["storage_url"]
    async with AzureCliCredential(tenant_id=ledger.a["native"]["tenant_id"]) as credential:
        token = (await credential.get_token("api://" + ledger.a["auth_client_id"] + "/.default")).token
        lifecycle.before_probe(ledger, lifecycle.Arm(ledger), "direct")
        request = {
            "jobType": "short-job", "idempotencyKey": "direct-" + env["SUFFIX"],
            "inputRef": storage + "/" + env["MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME"] + "/inputs/direct-" + env["SUFFIX"] + ".json",
            "callbackAlias": "ops",
        }
        async with Client(env["MCP_URL"], extensions=[TasksClientExtension()], auth=token, timeout=90) as client:
            ledger.gate(1200)
            task = await call_tool_task(client, "start_aca_job", request, timeout=90)
            terminal = await task.wait(timeout=600)
            assert dump(terminal)["status"] == "completed"
            direct_result = payload(await task.result())
            direct_url = result_url(direct_result, urlsplit(storage).hostname)
            ledger.gate(600)
            duplicate = await call_tool_task(client, "start_aca_job", request, timeout=90)
            assert dump(await duplicate.wait(timeout=120))["status"] == "completed"
            assert duplicate.task_id == task.task_id and payload(await duplicate.result()) == direct_result
            cancel_request = {**request, "idempotencyKey": "cancel-" + env["SUFFIX"]}
            ledger.gate(600)
            cancel_task = await call_tool_task(client, "start_aca_job", cancel_request, timeout=90)
            ledger.gate(400)
            await cancel_task.cancel()
            assert dump(await cancel_task.wait(timeout=300))["status"] in {"cancelled", "completed"}
        async with Client(env["MCP_URL"], mode="legacy", extensions=[], auth=token, timeout=90) as client:
            ledger.gate(600)
            started = payload(await client.call_tool("start_aca_job", {**request, "idempotencyKey": "fallback-" + env["SUFFIX"]}))
            assert "resultType" not in started
            fallback_id = started["taskId"]
            status = payload(await client.call_tool("get_aca_job_status", {"taskId": fallback_id}))
            assert status["taskId"] == fallback_id and "resultType" not in status
            ledger.gate(400)
            cancelled = payload(await client.call_tool("cancel_aca_job", {"taskId": fallback_id}))
            assert cancelled["taskId"] == fallback_id and "resultType" not in cancelled
            for _ in range(30):
                if cancelled["status"] in {"Succeeded", "Failed", "Cancelled"}:
                    break
                await asyncio.sleep(5)
                cancelled = payload(await client.call_tool("get_aca_job_status", {"taskId": fallback_id}))
            assert cancelled["status"] in {"Succeeded", "Failed", "Cancelled"}
        async with BlobClient.from_blob_url(env["CALLBACK_CONTAINER_URL"] + "/callbacks/" + task.task_id + ".json",
                                           credential=credential, retry_total=0) as blob:
            for _ in range(60):
                try:
                    callback = json.loads(await (await blob.download_blob()).readall())
                    break
                except ResourceNotFoundError as error:
                    assert error.status_code == 404
                    await asyncio.sleep(5)
            else:
                raise TimeoutError("callback did not arrive in 300 seconds")
        assert set(callback) == {"taskId", "acaExecutionId", "status", "resultUrl"}
        assert callback["taskId"] == task.task_id and callback["acaExecutionId"]
        assert result_url({"status": callback["status"], "resultUrl": callback["resultUrl"]},
                          urlsplit(storage).hostname) == direct_url
    for marker in ("MCP_TASKS_COMPLETED", "FALLBACK_TOOLS_COMPLETED", "IDEMPOTENCY_DUPLICATE_SAME_TASK",
                   "CALLBACK_PAYLOAD_VALID", "CANCELLATION_TERMINAL"):
        print(marker)


def invoke(ledger, lifecycle, kind):
    from azure.ai.projects import AIProjectClient
    from azure.core.credentials import AccessToken
    from azure.identity import AzureCliCredential
    env, a = lifecycle.environment(ledger), ledger.a["native"]
    with AzureCliCredential(tenant_id=a["tenant_id"], process_timeout=20) as credential:
        token = credential.get_token("https://ai.azure.com/.default")
    class FrozenCredential:
        def get_token(self, *scopes, **kwargs):
            assert scopes == ("https://ai.azure.com/.default",)
            ledger.gate(600)
            return AccessToken(token.token, token.expires_on)
    name = env["HOSTED_NAME" if kind == "hosted" else "PROMPT_NAME"]
    marker = kind.upper() + "_AGENT_MCP_PASS"
    expected_input = ledger.a["storage_url"] + "/" + env["MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME"] + \
        "/inputs/" + marker + "-" + env["SUFFIX"] + ".json"
    with AIProjectClient(endpoint=a["project_endpoint"], credential=FrozenCredential(),
                         retry_total=0, redirect_max=0, connection_timeout=20, read_timeout=120) as project:
        client = project.get_openai_client(**({"agent_name": name} if kind == "hosted" else {}))
        # Transport retries must not silently create extra model/tool invocations.
        client = client.with_options(max_retries=0, timeout=120)
        lifecycle.before_invoke(ledger, lifecycle.Arm(ledger), kind)
        response = client.responses.create(
            input="Call start_aca_job with jobType short-job, idempotencyKey " + kind + "-" + env["SUFFIX"] +
                  ", inputRef " + expected_input + ", and callbackAlias ops. "
                  "Then call get_aca_job_status with the returned taskId.",
            store=False, stream=False,
            **({"extra_body": {"agent_reference": {"name": name, "type": "agent_reference"}}} if kind == "prompt" else {}),
        )
        ledger.data.setdefault("responses", {})[kind] = {"id": response.id, "store": False}
        ledger.save()
        task_id = agent_calls(response, expected_input, kind + "-" + env["SUFFIX"])
        ledger.data["responses"][kind]["task_id"] = task_id
        ledger.save()
        client.close()
    print(kind.upper() + "_AGENT_MCP_CALLS_VALID")
