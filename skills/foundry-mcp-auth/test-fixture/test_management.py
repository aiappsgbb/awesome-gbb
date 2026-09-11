"""Offline serialization/write-boundary tests; project methods are local fakes."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
from uuid import UUID
import httpx
from openai import OpenAI

from references.python.configure_foundry import build_definitions, create_bindings


class ManagementTests(unittest.TestCase):
    def test_identity_rendering_contract_is_shared_and_requires_a_fresh_tool_call(self):
        from references.python.agent_instructions import INSTRUCTIONS
        from references.python.configure_foundry import build_prompt_toolbox_definition
        direct, _ = build_definitions("model", "https://mcp.example.com/mcp", "connection")
        toolbox = build_prompt_toolbox_definition(
            "model", "https://example.services.ai.azure.com/api/projects/demo/toolboxes/tools/versions/2/mcp?api-version=v1",
            "bridge",
        )
        self.assertEqual(direct.instructions, INSTRUCTIONS)
        self.assertEqual(toolbox.instructions, INSTRUCTIONS)
        for required in ("freshly in the current turn", "oid, tid, aud, scp and azp",
                         "correlation_id", "only when the user explicitly asks", "not exposed"):
            self.assertIn(required, INSTRUCTIONS)

    def test_toolbox_bridge_is_first_party_only_and_never_embeds_a_bearer(self):
        from references.python.provision_connection import build_toolbox_bridge_properties
        from references.python.configure_foundry import build_prompt_toolbox_definition
        props = build_toolbox_bridge_properties("https://example.services.ai.azure.com/api/projects/demo", "tools", "2")
        self.assertEqual(props["authType"], "UserEntraToken")
        self.assertEqual(props["audience"], "https://ai.azure.com")
        self.assertNotIn("credentials", props)
        definition = build_prompt_toolbox_definition("model", props["target"], "bridge-id").as_dict()
        self.assertEqual(definition["tools"][0]["project_connection_id"], "bridge-id")
        self.assertNotIn("authorization", definition["tools"][0])
        with self.assertRaises(ValueError):
            build_toolbox_bridge_properties("https://custom-mcp.example.com/api/projects/demo", "tools", "2")

    def test_invocation_routes_hosted_to_bound_endpoint_not_agent_reference(self):
        from references.python.invoke_agent import invoke_agent
        for kind in ("prompt", "hosted"):
            with self.subTest(kind=kind):
                client = MagicMock()
                client.responses.create.return_value = SimpleNamespace(status="completed", output=[object()])
                client.__enter__.return_value = client
                project = SimpleNamespace(get_openai_client=Mock(return_value=client))
                transport = object()
                invoke_agent(project, "demo", kind, "Call the demo tools", http_client_factory=lambda: transport)
                project.get_openai_client.assert_called_once_with(
                    agent_name="demo" if kind == "hosted" else None, http_client=transport, max_retries=0,
                )
                options = client.responses.create.call_args.kwargs
                self.assertEqual("extra_body" in options, kind == "prompt")

    def test_failed_responses_never_become_successful_empty_results(self):
        from references.python.invoke_agent import invoke_agent
        client = MagicMock(); client.__enter__.return_value = client
        client.responses.create.return_value = SimpleNamespace(
            status="failed", error=SimpleNamespace(code="server_error"), id="response-id",
        )
        with self.assertRaisesRegex(RuntimeError, "server_error"):
            invoke_agent(SimpleNamespace(get_openai_client=Mock(return_value=client)),
                         "demo", "hosted", "Call tools", http_client_factory=object)

    def test_consent_continuation_uses_previous_response_without_auto_approval(self):
        from references.python.invoke_agent import invoke_agent
        client = MagicMock(); client.__enter__.return_value = client
        response = SimpleNamespace(status="completed", output=[SimpleNamespace(type="oauth_consent_request")])
        client.responses.create.return_value = response
        result = invoke_agent(SimpleNamespace(get_openai_client=Mock(return_value=client)),
                              "demo", "prompt", "Call tools", http_client_factory=object, previous_response_id="prior")
        self.assertIs(result, response)
        self.assertEqual(client.responses.create.call_args.kwargs["previous_response_id"], "prior")
        self.assertNotIn("mcp_approval_response", str(client.responses.create.call_args.kwargs))

    def test_real_transport_lifetime_supports_two_turns_and_continuation(self):
        from references.python.invoke_agent import invoke_agent
        requests = []
        transports = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={
                "id": f"response-{len(requests)}", "object": "response", "created_at": 0,
                "status": "completed", "output": [{
                    "type": "message", "id": "message-1", "role": "assistant",
                    "status": "completed", "content": [{"type": "output_text", "text": "fixture", "annotations": []}],
                }],
            })
        def transport_factory():
            transport = httpx.Client(transport=httpx.MockTransport(respond))
            transports.append(transport)
            return transport
        project = SimpleNamespace(get_openai_client=lambda **kwargs: OpenAI(
            api_key="local-test-only", base_url="https://example.test/v1",
            http_client=kwargs["http_client"], max_retries=0,
        ))
        first = invoke_agent(project, "demo", "prompt", "First", http_client_factory=transport_factory, agent_version="1")
        invoke_agent(project, "demo", "prompt", "Continue", http_client_factory=transport_factory,
                     previous_response_id=first.id, agent_version="1")
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(t.is_closed for t in transports))
        import json
        payload = json.loads(requests[1].content)
        self.assertEqual(payload["previous_response_id"], first.id)
        self.assertEqual(payload["extra_body"]["agent_reference"]["version"] if "extra_body" in payload else payload["agent_reference"]["version"], "1")

    def test_completed_empty_response_is_not_successful_demo_output(self):
        from references.python.invoke_agent import invoke_agent
        client = MagicMock(); client.__enter__.return_value = client
        client.responses.create.return_value = SimpleNamespace(status="completed", output=[], id="empty")
        with self.assertRaisesRegex(RuntimeError, "empty"):
            invoke_agent(SimpleNamespace(get_openai_client=Mock(return_value=client)), "demo", "hosted",
                         "Call tools", http_client_factory=object)

    def test_ga_oauth_properties_use_custom_audience_and_scope(self):
        from references.python.provision_connection import build_oauth_properties
        tenant, api, client = (str(UUID(int=i)) for i in range(1, 4))
        props = build_oauth_properties("https://mcp.example.com/mcp", tenant, api, client, "test-only-secret")
        self.assertEqual(props["authType"], "OAuth2")
        self.assertEqual(props["scopes"], [f"api://{api}/demo.read", "offline_access"])
        self.assertEqual(props["credentials"]["clientId"], client)
        self.assertNotIn("audience", props)
        self.assertEqual(props["authorizationUrl"], f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize")

    def test_connection_creation_requires_explicit_approval(self):
        from references.python.provision_connection import provision_connection
        with self.assertRaises(PermissionError):
            provision_connection(Mock(), "/not-used", {})

    def test_connection_replacement_requires_matching_target(self):
        from references.python.provision_connection import provision_connection
        arm = SimpleNamespace(resources=SimpleNamespace(
            get_by_id=lambda *args: SimpleNamespace(properties={"authType": "OAuth2", "target": "https://other.example.com/mcp"}),
        ))
        with self.assertRaises(ValueError):
            provision_connection(arm, "/subscriptions/example/resourceGroups/example/providers/Microsoft.CognitiveServices/accounts/a/projects/p/connections/c",
                                 {"authType": "OAuth2", "target": "https://mcp.example.com/mcp"},
                                 approved=True, replace_existing=True)

    def test_definitions_reference_connection_without_bearer_or_user_headers(self):
        prompt, toolbox = build_definitions("demo-model", "https://mcp.example.com/mcp", "connection-id")
        for tool in (prompt.as_dict()["tools"][0], toolbox.as_dict()):
            self.assertEqual(tool["project_connection_id"], "connection-id")
            self.assertEqual(tool["server_url"], "https://mcp.example.com/mcp")
            self.assertEqual(tool["allowed_tools"], ["who_am_i", "list_my_demo_items"])
            self.assertNotIn("authorization", tool)
            self.assertNotIn("headers", tool)

    def test_invalid_definition_is_rejected_before_any_cloud_operation(self):
        for model, url, connection in (
            ("", "https://mcp.example.com/mcp", "connection"),
            ("model", "http://mcp.example.com/mcp", "connection"),
            ("model", "https://secret@mcp.example.com/mcp", "connection"),
            ("model", "https://mcp.example.com/mcp?token=secret", "connection"),
            ("model", "https://mcp.example.com/mcp", ""),
        ):
            with self.assertRaises(ValueError):
                build_definitions(model, url, connection)

    def test_create_is_opt_in_and_reads_without_credentials(self):
        calls = []
        project = SimpleNamespace(
            connections=SimpleNamespace(get=lambda name, **kw: (
                calls.append(("read", name, kw))
                or SimpleNamespace(id="connection-id", target="https://mcp.example.com/mcp")
            )),
            toolboxes=SimpleNamespace(create_version=lambda **kw: calls.append(("toolbox", kw)) or "toolbox"),
            agents=SimpleNamespace(create_version=lambda **kw: calls.append(("agent", kw)) or "agent"),
        )
        args = (project, "model", "https://mcp.example.com/mcp", "connection", "demo")
        with self.assertRaises(PermissionError):
            create_bindings(*args)
        with self.assertRaises(PermissionError):
            create_bindings(*args, approved="yes")
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            create_bindings(project, "model", "https://mcp.example.com/mcp", "", "demo", approved=True)
        self.assertEqual(calls, [])
        self.assertEqual(create_bindings(*args, approved=True), ("agent", "toolbox"))
        self.assertEqual(calls[0], ("read", "connection", {"include_credentials": False}))
        self.assertEqual([c[0] for c in calls], ["read", "toolbox", "agent"])

    def test_target_mismatch_never_creates_resources(self):
        project = SimpleNamespace(connections=SimpleNamespace(
            get=lambda *a, **kw: SimpleNamespace(id="connection", target="https://other.example.com/mcp")
        ))
        with self.assertRaises(ValueError):
            create_bindings(project, "model", "https://mcp.example.com/mcp", "connection", "demo", approved=True)


if __name__ == "__main__":
    unittest.main()
