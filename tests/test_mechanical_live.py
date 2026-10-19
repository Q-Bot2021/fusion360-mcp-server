"""Explicit read-only acceptance against active CAD or drawing fixtures."""

import hashlib
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


def test_document_save_quota_live():
    async def check():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "tests.development_mcp"]
        )
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                reload_result = await session.call_tool("dev_reload_candidates", {})
                assert not reload_result.isError, reload_result.content
                before = await session.call_tool("get_document_state", {})
                assert not before.isError, before.content
                identity = before.structuredContent["document_id"]
                result = await session.call_tool("diagnose_document_save", {
                    "document_id": identity,
                })
                assert not result.isError, result.content
                payload = result.structuredContent
                assert payload["save_retried"] is False
                assert payload["save_failure_cause_confirmed"] is False
                if payload["quota_applies"]:
                    expected = max(0, 1 - payload["available_slots"])
                    assert payload["documents_to_make_read_only"] == expected
                    if expected:
                        assert payload["status"] == "EDITABLE_DOCUMENT_LIMIT_REACHED"
                        assert payload["instructions"]
                    else:
                        assert payload["status"] == "SLOTS_AVAILABLE"
                        assert payload["instructions"] == []
                after = await session.call_tool("get_document_state", {})
                assert not after.isError, after.content
                assert after.structuredContent["document_id"] == identity
                root = Path(__file__).resolve().parents[1]
                sources = (
                    "addon/server/mechanical_queries.py",
                    "addon/server/command_handler.py",
                    "tests/development_mcp.py",
                    "tests/test_mechanical_live.py",
                )
                report = {
                    "result": payload,
                    "source_sha256": {
                        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                        for name in sources
                    },
                    "loaded_source_sha256": reload_result.structuredContent,
                }
                path = root / ".pytest_cache/document-save-quota-live.json"
                path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    anyio.run(check)


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
