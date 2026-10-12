"""Real MCP stdio sessions against the CLI; mock Fusion is not live acceptance."""

import json
import os
import sys
from datetime import timedelta

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from fusion360_mcp.server import build_server
from fusion360_mcp.tools import (
    DIRECT_TOOL_CALLS,
    TEXT_VISIBILITY_REVIEW,
    get_tool_list,
)
from tests import test_addon_api_usage

pytestmark = pytest.mark.protocol_e2e


@pytest.fixture
def step_export():
    return test_addon_api_usage.step_export.__wrapped__()


@pytest.fixture
def object_info_case():
    return test_addon_api_usage.object_info_case.__wrapped__()


def test_component_object_info_through_request_handlers(object_info_case, monkeypatch):
    import fusion360_mcp.server as server

    method, handler, root, component, collection = object_info_case
    monkeypatch.setattr(
        server, "_send", lambda mode, name, params, **kwargs: method(handler, **params)
    )

    async def check():
        async with create_connected_server_and_client_session(
            build_server("socket")
        ) as session:
            body = await session.call_tool("get_object_info", {"name": "Part"})
            assert not body.isError and "volume: 2" in body.content[0].text
            root.bRepBodies = component.bRepBodies
            assert (
                await session.call_tool("get_object_info", {"name": "Part"})
            ).isError
            selected = await session.call_tool(
                "get_object_info",
                {
                    "name": "Part",
                    "entity_type": "body",
                    "occurrence_path": "Nested:1",
                },
            )
            assert not selected.isError and "found: True" in selected.content[0].text
            sketch = await session.call_tool(
                "get_object_info",
                {
                    "name": "Labels",
                    "entity_type": "sketch",
                    "component_name": "Nested",
                },
            )
            assert not sketch.isError and "type: sketch" in sketch.content[0].text
            assert (
                await session.call_tool(
                    "get_object_info", {"name": "Part", "entity_type": "unknown"}
                )
            ).isError

    anyio.run(check)


def test_appearance_target_preflight_through_request_handlers(
    object_info_case, monkeypatch
):
    import ast
    from unittest.mock import Mock

    import fusion360_mcp.server as server

    method, handler, root, component, collection = object_info_case
    namespace = {}
    node = test_addon_api_usage._method("set_appearance")
    exec(
        compile(
            ast.Module(body=[node], type_ignores=[]), "appearance_protocol", "exec"
        ),
        namespace,
    )
    node = test_addon_api_usage._method("_component_by_name")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), "component_protocol", "exec"),
        namespace,
    )
    library = Mock()
    handler.app = type("Application", (), {"materialLibraries": library})()
    handler._body_by_name = Mock(side_effect=ValueError("ambiguous body"))
    root.name = component.name
    handler._component_by_name = lambda name: namespace["_component_by_name"](
        handler, name
    )
    monkeypatch.setattr(
        server,
        "_send",
        lambda mode, name, params, **kwargs: namespace["set_appearance"](
            handler, **params
        ),
    )

    async def check():
        async with create_connected_server_and_client_session(
            build_server("socket")
        ) as session:
            for target_type in ("body", "face", "component"):
                result = await session.call_tool(
                    "set_appearance",
                    {
                        "target_name": "Part"
                        if target_type != "component"
                        else component.name,
                        "appearance_name": "NotRead",
                        "target_type": target_type,
                        "face_index": 0,
                    },
                )
                assert result.isError and "ambiguous" in result.content[0].text
            library.itemByName.assert_not_called()

    anyio.run(check)


def test_step_export_errors_and_results_through_request_handlers(
    step_export, tmp_path, monkeypatch
):
    import fusion360_mcp.server as server

    method, handler, manager = step_export
    destination = tmp_path / "protocol.step"

    def send(mode, name, params, **kwargs):
        assert name == "export_step"
        return method(handler, **params)

    monkeypatch.setattr(server, "_send", send)

    async def check():
        async with create_connected_server_and_client_session(
            build_server("socket")
        ) as session:
            manager.execute.return_value = False
            failed = await session.call_tool(
                "export_step", {"body_name": "Part", "file_path": str(destination)}
            )
            assert failed.isError and "STEP export failed" in failed.content[0].text

            def execute(options):
                destination.write_text(
                    "ISO-10303-21;\nEND-ISO-10303-21;", encoding="ascii"
                )
                return True

            manager.execute.side_effect = execute
            result = await session.call_tool(
                "export_step", {"body_name": "Part", "file_path": str(destination)}
            )
            assert not result.isError
            assert "exported: True" in result.content[0].text
            assert str(destination) in result.content[0].text
            existing = await session.call_tool(
                "export_step", {"body_name": "Part", "file_path": str(destination)}
            )
            assert existing.isError and "already exists" in existing.content[0].text

    anyio.run(check)


async def run_session(check, *, mode="mock"):
    env = dict(os.environ, FUSION_MCP_HOST="127.0.0.1", FUSION_MCP_PORT="9876")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fusion360_mcp", "--mode", mode],
        env=env,
    )
    with anyio.fail_after(30):
        async with stdio_client(params) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=10)
            ) as session:
                initialized = await session.initialize()
                assert initialized.instructions == (
                    DIRECT_TOOL_CALLS + " " + TEXT_VISIBILITY_REVIEW
                )
                assert "inspect and edit that same document in place" in (
                    initialized.instructions
                )
                assert "Verify the intended document is active" in (
                    initialized.instructions
                )
                assert "ask for approval before creating a replacement" in (
                    initialized.instructions
                )
                await check(session)


def test_tool_discovery_and_calls():
    async def check(session):
        listed = await session.list_tools()
        assert {tool.name for tool in listed.tools} == {
            tool.name for tool in get_tool_list()
        }
        assert "execute_code" not in {tool.name for tool in listed.tools}
        render = next(tool for tool in listed.tools if tool.name == "render_view")
        assert DIRECT_TOOL_CALLS in render.description
        assert TEXT_VISIBILITY_REVIEW in render.description
        ping = await session.call_tool("ping", {})
        assert not ping.isError
        assert "pong" in ping.content[0].text
        scene = await session.call_tool("get_scene_info", {})
        assert not scene.isError
        assert "occurrence_path" in scene.content[0].text
        assert "bodies_count" in scene.content[0].text
        blocked = await session.call_tool(
            "execute_code", {"code": "raise RuntimeError()"}
        )
        assert blocked.isError
        assert "execute_code" in blocked.content[0].text
        unknown = await session.call_tool("not_registered", {})
        assert unknown.isError

    anyio.run(run_session, check)


def test_valid_and_invalid_tool_arguments():
    async def check(session):
        valid = await session.call_tool("get_object_info", {"name": "ProtocolBody"})
        assert not valid.isError
        assert "ProtocolBody" in valid.content[0].text
        invalid = await session.call_tool("get_object_info", {"name": 123})
        assert invalid.isError
        nested_body = await session.call_tool(
            "get_object_info",
            {"name": "Part", "entity_type": "body", "occurrence_path": "Part:1"},
        )
        assert not nested_body.isError and "type: body" in nested_body.content[0].text
        component_sketch = await session.call_tool(
            "get_object_info",
            {"name": "Sketch", "entity_type": "sketch", "component_name": "Part"},
        )
        assert not component_sketch.isError
        assert "type: sketch" in component_sketch.content[0].text
        invalid_selector = await session.call_tool(
            "get_object_info",
            {"name": "Part", "entity_type": "body", "component_name": "Part"},
        )
        assert invalid_selector.isError
        sketch_calls = {
            "create_sketch": {"plane": "yz", "component_name": "ProtocolPart"},
            "draw_rectangle": {
                "width": 1,
                "height": 1,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "draw_circle": {
                "radius": 0.5,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "draw_line": {
                "start_x": 0,
                "start_y": 0,
                "end_x": 1,
                "end_y": 1,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "draw_arc": {
                "center_x": 0,
                "center_y": 0,
                "start_x": 1,
                "start_y": 0,
                "sweep_angle": 90,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "draw_spline": {
                "spline_type": "fit_points",
                "points": [[0, 0], [1, 1]],
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "create_polygon": {
                "sides": 5,
                "radius": 0.5,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "add_constraint": {
                "constraint_type": "horizontal",
                "entity_one": 0,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "auto_constrain": {
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "add_dimension": {
                "dimension_type": "horizontal",
                "value": 1,
                "entity_one": 0,
                "entity_two": 1,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "offset_curve": {
                "curve_index": 0,
                "offset_distance": 0.1,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "trim_curve": {
                "curve_index": 0,
                "point_x": 0,
                "point_y": 0,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "extend_curve": {
                "curve_index": 0,
                "point_x": 0,
                "point_y": 0,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "project_geometry": {
                "source_name": "Part",
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "extrude": {
                "height": 1,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "revolve": {
                "angle": 90,
                "sketch_name": "Sketch",
                "component_name": "ProtocolPart",
            },
            "sweep": {
                "profile_index": 0,
                "path_sketch_name": "Path",
                "profile_sketch_name": "Profile",
                "component_name": "ProtocolPart",
            },
            "loft": {
                "profile_sketch_names": ["A", "B"],
                "component_name": "ProtocolPart",
            },
        }
        for tool_name, arguments in sketch_calls.items():
            result = await session.call_tool(tool_name, arguments)
            assert not result.isError, (tool_name, result.content)
        forced = await session.call_tool(
            "extrude", {"height": 1, "__mock_error__": "No profiles in sketch"}
        )
        assert forced.isError
        assert "PROFILE_NOT_CLOSED" in forced.content[0].text

    anyio.run(run_session, check)


def test_resource_discovery_and_reads():
    async def check(session):
        listed = await session.list_resources()
        assert {str(resource.uri) for resource in listed.resources} == {
            "fusion360://status",
            "fusion360://design",
            "fusion360://parameters",
        }
        for resource in listed.resources:
            response = await session.read_resource(resource.uri)
            payload = json.loads(response.contents[0].text)
            assert "error" not in payload
            if str(resource.uri) == "fusion360://status":
                assert payload["connected"] is True
            else:
                assert payload["ok"] is True
        with pytest.raises(Exception, match="Unknown resource"):
            await session.read_resource("fusion360://not_registered")

    anyio.run(run_session, check)


def test_resource_templates_and_prompts():
    async def check(session):
        templates = await session.list_resource_templates()
        assert {template.uriTemplate for template in templates.resourceTemplates} == {
            "fusion360://body/{name}",
            "fusion360://component/{name}",
        }
        for kind in ("body", "component"):
            response = await session.read_resource(f"fusion360://{kind}/ProtocolBody")
            assert json.loads(response.contents[0].text)["name"] == "ProtocolBody"
            encoded = await session.read_resource(f"fusion360://{kind}/Protocol%20Body")
            assert json.loads(encoded.contents[0].text)["name"] == "Protocol Body"
        prompts = await session.list_prompts()
        for prompt in prompts.prompts:
            response = await session.get_prompt(prompt.name, {})
            assert response.messages[0].content.text

    anyio.run(run_session, check)
