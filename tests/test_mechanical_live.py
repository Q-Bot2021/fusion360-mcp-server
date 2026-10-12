"""Explicit read-only acceptance against active CAD or drawing fixtures."""

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.fusion_e2e


@pytest.mark.parametrize(
    "name, uri",
    [
        ("get_feature_health", "fusion360://development/feature-health"),
        ("get_drawing_info", "fusion360://development/drawing"),
    ],
)
def test_mechanical_inspection_live(name, uri):
    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tests.development_mcp"],
            env=dict(os.environ, FUSION_MCP_HOST="127.0.0.1"),
        )
        with anyio.fail_after(30):
            async with stdio_client(params) as streams:
                async with ClientSession(
                    streams[0], streams[1], read_timeout_seconds=timedelta(seconds=10)
                ) as session:
                    await session.initialize()
                    result = await session.call_tool(name, {})
                    assert not result.isError, result.content
                    payload = result.structuredContent
                    assert payload["development_only"] is True
                    if name == "get_feature_health":
                        assert payload["total"] > 0, (
                            "Use a named CAD fixture with features"
                        )
                        assert payload["features"]
                    else:
                        assert payload["active_sheet_name"], (
                            "Use a drawing with a sheet"
                        )
                    resource = await session.read_resource(uri)
                    assert json.loads(resource.contents[0].text) == payload
                    path = Path(f".pytest_cache/{name}-live.json")
                    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    anyio.run(check)
