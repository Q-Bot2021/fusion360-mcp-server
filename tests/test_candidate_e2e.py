"""Test-only candidate registration through the production request handlers."""

from datetime import timedelta

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from fusion360_mcp import mock, tools
from fusion360_mcp.server import build_server

pytestmark = pytest.mark.protocol_e2e


def test_candidate_can_be_tested_before_production_registration(monkeypatch):
    candidate = {
        "name": "acceptance_candidate",
        "title": "Isolated candidate",
        "description": "Only registered inside this test",
        "inputSchema": {
            "type": "object", "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    }
    assert tools.get_tool_by_name(candidate["name"]) is None

    async def check():
        app = build_server("mock")
        async with create_connected_server_and_client_session(
            app, read_timeout_seconds=timedelta(seconds=5)
        ) as session:
            listed = await session.list_tools()
            assert candidate["name"] in {tool.name for tool in listed.tools}
            result = await session.call_tool(candidate["name"], {"name": "TestOwned"})
            assert not result.isError
            assert "TestOwned" in result.content[0].text
            invalid = await session.call_tool(candidate["name"], {"name": 123})
            assert invalid.isError
            blocked = await session.call_tool("execute_code", {"code": "1 + 1"})
            assert blocked.isError

    with monkeypatch.context() as isolated:
        isolated.setattr(tools, "TOOLS", [*tools.TOOLS, candidate])
        isolated.setitem(
            mock._DISPATCH, candidate["name"], lambda params: {"name": params["name"]}
        )
        anyio.run(check)
    assert tools.get_tool_by_name(candidate["name"]) is None
    assert candidate["name"] not in mock._DISPATCH