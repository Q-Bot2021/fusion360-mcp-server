"""Read-only live acceptance; unavailable Fusion is a failure when opted in."""

import json

import anyio
import pytest

from tests.test_protocol_e2e import run_session

pytestmark = pytest.mark.fusion_e2e


def test_live_status_design_and_parameters():
    async def check(session):
        ping = await session.call_tool("ping", {})
        assert not ping.isError, ping.content
        scene = await session.call_tool("get_scene_info", {})
        assert not scene.isError, scene.content
        assert "mode: mock" not in scene.content[0].text
        for uri in ("fusion360://status", "fusion360://design", "fusion360://parameters"):
            result = await session.read_resource(uri)
            payload = json.loads(result.contents[0].text)
            assert "error" not in payload, payload
            assert payload.get("ok", True) is True, payload
            if uri == "fusion360://status":
                assert payload["connected"] is True

    async def run():
        await run_session(check, mode="socket")

    anyio.run(run)


@pytest.mark.parametrize("kind", ["body", "component"])
def test_live_named_resource_template(request, kind):
    name = request.config.getoption(f"--fusion-test-{kind}")
    assert name, f"Provide --fusion-test-{kind} for a known disposable-design fixture"

    async def check(session):
        from urllib.parse import quote

        response = await session.read_resource(
            f"fusion360://{kind}/{quote(name, safe='')}"
        )
        payload = json.loads(response.contents[0].text)
        assert "error" not in payload, payload
        assert payload.get("ok") is True, payload
        assert payload["name"] == name

    async def run():
        await run_session(check, mode="socket")

    anyio.run(run)