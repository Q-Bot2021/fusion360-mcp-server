"""Persistent development infrastructure excludes electronics and arbitrary code."""

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from fusion360_mcp.server import build_server
from fusion360_mcp.tools import (
    DIRECT_TOOL_CALLS,
    TEXT_VISIBILITY_REVIEW,
    get_tool_by_name,
    get_tool_list,
)
from tests.development_mcp import (
    ASSEMBLY_CANDIDATES,
    DOCUMENT_CANDIDATES,
    STENCIL_CANDIDATES,
    development_list,
    development_lookup,
)


@pytest.fixture
def addon():
    path = Path(__file__).parent / "fusion_addins/Fusion360MCPDev/Fusion360MCPDev.py"
    spec = importlib.util.spec_from_file_location("_cad_development", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cad_development_discovery_stays_separate():
    names = {tool.name for tool in development_list()}
    assert names == {tool.name for tool in get_tool_list()} | {
        "dev_reload_candidates",
        "get_feature_health",
        "get_drawing_info",
    } | {
        definition["name"] for definition in (*DOCUMENT_CANDIDATES, *STENCIL_CANDIDATES)
    } | {definition["name"] for definition in ASSEMBLY_CANDIDATES}
    promoted_assembly_tools = {
        definition["name"]
        for definition in ASSEMBLY_CANDIDATES
        if get_tool_by_name(definition["name"]) is not None
    }
    assert promoted_assembly_tools == {
        "open_design",
        "insert_design",
        "list_occurrences",
    }
    assert get_tool_by_name("dev_reload_candidates") is None
    assert development_lookup("execute_code") is None
    assert not any(name.startswith("ecad_") for name in names)


def test_promoted_design_tool_has_identical_metadata_in_both_profiles():
    production = get_tool_by_name("create_design")
    assert development_lookup("create_design") is production
    discovered = next(
        tool for tool in development_list() if tool.name == "create_design"
    )
    assert discovered.title == production["title"]
    assert "Development:" not in discovered.title
    assert discovered.description == production["description"]


@pytest.mark.parametrize(
    "name",
    [
        "draw_sketch_text",
        "extrude_sketch_entities",
        "chamfer_edges",
        "get_body_topology",
        "save_design",
    ],
)
def test_generic_promotions_share_production_metadata(name):
    production = get_tool_by_name(name)
    assert development_lookup(name) is production
    discovered = [tool for tool in development_list() if tool.name == name]
    assert len(discovered) == 1
    assert discovered[0].title == production["title"]
    assert "Development:" not in discovered[0].title


@pytest.mark.fusion_e2e
@pytest.mark.parametrize("profile", ["production", "development"])
def test_create_new_fusion_design_live(profile):
    async def check():
        root = Path(__file__).resolve().parents[1]
        destination = root / f".pytest_cache/new-design-{profile}-live.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        report = {"status": "started", "calls": [], "source_sha256": {}}
        for relative in (
            "addon/server/mechanical_queries.py",
            "tests/development_mcp.py",
            "tests/test_development_registration.py",
        ):
            report["source_sha256"][relative] = hashlib.sha256(
                (root / relative).read_bytes()
            ).hexdigest()
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        with anyio.fail_after(90):
            async with stdio_client(parameters) as streams:
                async with ClientSession(
                    streams[0],
                    streams[1],
                    read_timeout_seconds=timedelta(seconds=30),
                ) as session:
                    await session.initialize()

                    async def call(name, arguments):
                        result = await session.call_tool(name, arguments)
                        report["calls"].append(
                            {
                                "tool": name,
                                "arguments": arguments,
                                "result": result.model_dump(mode="json"),
                            }
                        )
                        destination.write_text(
                            json.dumps(report, indent=2), encoding="utf-8"
                        )
                        return result

                    before = await call("get_document_state", {})
                    assert not before.isError, before.content
                    definition = next(
                        tool
                        for tool in (await session.list_tools()).tools
                        if tool.name == "create_design"
                    )
                    assert not definition.annotations.destructiveHint
                    invalid = await call("create_design", {"name": ""})
                    assert invalid.isError
                    unchanged = await call("get_document_state", {})
                    assert unchanged.content == before.content
                    name = "MCP_NewDesignAcceptance_" + datetime.now(
                        timezone.utc
                    ).strftime("%Y%m%d_%H%M%S")
                    created = await call("create_design", {"name": name})
                    assert not created.isError, created.content
                    state_text = created.content[0].text
                    assert "development_only" not in state_text
                    assert f"document_name: {name}" in state_text
                    assert "is_saved: False" in state_text
                    assert "data_file_id: None" in state_text
                    assert name not in before.content[0].text
                    inspected = await call("get_document_state", {})
                    assert not inspected.isError, inspected.content
                    assert f"document_name: {name}" in inspected.content[0].text
                    assert "is_saved: False" in inspected.content[0].text
                    identity_lines = [
                        line
                        for line in state_text.splitlines()
                        if line.startswith("  document_id:")
                    ]
                    assert len(identity_lines) == 1
                    assert identity_lines[0] in inspected.content[0].text
                    assert identity_lines[0] not in before.content[0].text
                    scene = await call("get_scene_info", {})
                    assert not scene.isError, scene.content
                    assert f"design_name: {name}" in scene.content[0].text
                    for count in (
                        "bodies_count",
                        "sketches_count",
                        "features_count",
                        "timeline_count",
                    ):
                        assert f"{count}: 0" in scene.content[0].text
                    report["status"] = "passed"
                    report["fixture"] = inspected.model_dump(mode="json")
                    report["cleanup"] = (
                        "Unsaved empty acceptance document retained; "
                        "no existing document closed or saved."
                    )
                    destination.write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )

    anyio.run(check)


@pytest.mark.fusion_e2e
@pytest.mark.parametrize("profile", ["production", "development"])
def test_visible_workflow_instructions_live(profile):
    async def check():
        arguments = (
            ["-m", "tests.development_mcp"]
            if profile == "development"
            else ["-m", "fusion360_mcp", "--mode", "socket"]
        )
        parameters = StdioServerParameters(command=sys.executable, args=arguments)
        report = {"profile": profile, "status": "started", "source_sha256": {}}
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "src/fusion360_mcp/server.py",
            "src/fusion360_mcp/tools.py",
            "tests/development_mcp.py",
        ):
            report["source_sha256"][relative] = hashlib.sha256(
                (root / relative).read_bytes()
            ).hexdigest()
        with anyio.fail_after(90):
            async with stdio_client(parameters) as streams:
                async with ClientSession(
                    streams[0],
                    streams[1],
                    read_timeout_seconds=timedelta(seconds=30),
                ) as session:
                    initialized = await session.initialize()
                    assert initialized.instructions == (
                        DIRECT_TOOL_CALLS + " " + TEXT_VISIBILITY_REVIEW
                    )
                    listed = (await session.list_tools()).tools
                    reviewed = {"render_view"}
                    if profile == "development":
                        reviewed.update(tool["name"] for tool in STENCIL_CANDIDATES)
                    descriptions = {
                        tool.name: tool.description
                        for tool in listed
                        if tool.name in reviewed
                    }
                    assert set(descriptions) == reviewed
                    for name, description in descriptions.items():
                        assert DIRECT_TOOL_CALLS in description
                        if name not in {"create_design", "get_body_topology"}:
                            assert TEXT_VISIBILITY_REVIEW in description
                    ping = await session.call_tool("ping", {})
                    assert not ping.isError, ping.content
                    rendered = await session.call_tool(
                        "render_view",
                        {"view": "current", "fit": False, "width": 800, "height": 1200},
                    )
                    assert not rendered.isError, rendered.content
                    assert any(block.type == "image" for block in rendered.content)
                    report.update(
                        status="passed",
                        instructions=initialized.instructions,
                        descriptions=descriptions,
                        live_viewport_image=True,
                        ping=ping.model_dump(mode="json"),
                    )
        destination = root / ".pytest_cache" / f"visible-workflow-{profile}-live.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    anyio.run(check)


def test_stencil_candidates_have_protocol_routing(addon, monkeypatch):
    import fusion360_mcp.server as server

    cad = Mock(app=object())
    cad.execute_command.return_value = {
        "status": "success",
        "result": {"ok": True, "operation": "create_design"},
    }
    helpers = Mock()
    handler = addon.DevelopmentHandler(cad, queries=helpers)
    cases = {
        "get_body_topology": {"body_name": "Part", "limit": 1},
        "save_design": {
            "document_id": "owned",
            "name": "Bracket",
            "project_id": "project",
        },
        "chamfer_edges": {
            "body_name": "Part",
            "edge_indices": [0],
            "reference_face_indices": [0],
            "distance_one": 0.1,
            "distance_two": 0.2,
            "feature_name": "Bevel",
        },
        "create_design": {"name": "MCP_Stencil"},
        "draw_sketch_text": {
            "sketch_name": "Labels",
            "text": "10 mm",
            "x": 0,
            "y": 0,
            "height": 0.1,
            "width": 1,
            "box_height": 0.2,
        },
        "extrude_sketch_entities": {
            "sketch_name": "Labels",
            "entity_type": "texts",
            "distance": -0.001,
            "operation": "cut",
            "feature_name": "Engrave",
        },
        "chamfer_stencil_edges": {
            "body_name": "Stencil",
            "scope": "left",
            "vertical_depth": 0.25,
            "angle_degrees": 30,
            "feature_name": "Bevel",
        },
    }
    for name in cases:
        getattr(helpers, name).return_value = {"ok": True, "operation": name}
        if name == "chamfer_stencil_edges":
            assert get_tool_by_name(name) is None

    def delegated(command):
        name = command["type"]
        if name == "create_design":
            return {"status": "success", "result": {"ok": True, "operation": name}}
        return {
            "status": "success",
            "result": getattr(helpers, name)(**command["params"]),
        }

    cad.execute_command.side_effect = delegated

    def send(mode, name, params, **kwargs):
        assert kwargs["mutation"] is (name != "get_body_topology")
        return handler.execute_command({"type": name, "params": params})["result"]

    monkeypatch.setattr(server, "_send", send)

    async def check():
        instance = build_server(
            "socket",
            tool_list=development_list,
            tool_lookup=development_lookup,
            structured_results=True,
        )
        async with create_connected_server_and_client_session(instance) as session:
            listed = (await session.list_tools()).tools
            names = {tool.name for tool in listed}
            assert set(cases) <= names
            for tool in listed:
                if tool.name in cases:
                    if tool.name != "get_body_topology":
                        assert DIRECT_TOOL_CALLS in tool.description
                    if tool.name not in {
                        "create_design",
                        "get_body_topology",
                        "save_design",
                    }:
                        assert TEXT_VISIBILITY_REVIEW in tool.description
            for name, params in cases.items():
                result = await session.call_tool(name, params)
                assert (
                    not result.isError and result.structuredContent["operation"] == name
                )
                assert (
                    await session.call_tool(name, {**params, "code": "forbidden"})
                ).isError
                assert (await session.call_tool(name, {})).isError
                if name == "create_design":
                    helpers.create_design.assert_not_called()
                else:
                    getattr(helpers, name).assert_called_once()

    anyio.run(check)


def test_reload_replaces_handler_and_delegates_cad(addon):
    original, refreshed = Mock(), Mock()
    refreshed.execute_command.return_value = {"status": "success"}
    handler = addon.DevelopmentHandler(original, lambda: (refreshed, {"fixed": "hash"}))
    result = handler.execute_command({"type": "dev_reload_candidates"})
    assert result["result"]["generation"] == 1
    assert handler.execute_command({"type": "ping"}) == {"status": "success"}
    original.execute_command.assert_not_called()


@pytest.mark.parametrize("params", [{"code": "x"}, {"path": "x"}, [], None])
def test_reload_rejects_arguments(addon, params):
    reloader = Mock()
    handler = addon.DevelopmentHandler(Mock(), reloader)
    assert (
        handler.execute_command({"type": "dev_reload_candidates", "params": params})[
            "status"
        ]
        == "error"
    )
    reloader.assert_not_called()


def test_failed_reload_keeps_handler(addon):
    original = Mock()
    handler = addon.DevelopmentHandler(
        original, Mock(side_effect=RuntimeError("failed"))
    )
    with pytest.raises(RuntimeError):
        handler.execute_command({"type": "dev_reload_candidates"})
    assert handler.cad_handler is original and handler.generation == 0


def test_flat_loader_uses_private_package(addon, tmp_path, monkeypatch):
    server = tmp_path / "server"
    server.mkdir()
    (server / "__init__.py").write_text("MARKER = 'cad'")
    for name in ("event_bridge", "command_handler", "socket_server"):
        (server / f"{name}.py").write_text("from . import MARKER")
    monkeypatch.setattr(addon, "__file__", str(tmp_path / "Fusion360MCPDev.py"))
    monkeypatch.setattr(addon, "RUNTIME_PACKAGE", "_test_cad_development")
    addon.__package__ = None
    try:
        assert all(module.MARKER == "cad" for module in addon.load_runtime())
    finally:
        for name in list(sys.modules):
            if name.startswith("_test_cad_development"):
                del sys.modules[name]


def test_lifecycle_uses_distinct_event_and_loopback(addon, monkeypatch):
    app = SimpleNamespace(userInterface=SimpleNamespace(messageBox=Mock()))
    core = SimpleNamespace(Application=SimpleNamespace(get=lambda: app))
    bridge = SimpleNamespace(EventBridge=Mock())
    handlers = SimpleNamespace(CommandHandler=Mock())
    sockets = SimpleNamespace(Fusion360MCPServer=Mock())
    monkeypatch.setattr(addon.importlib, "import_module", lambda name: core)
    monkeypatch.setattr(addon, "load_runtime", lambda: (bridge, handlers, sockets))
    addon.run(None)
    assert bridge.CUSTOM_EVENT_ID == "Fusion360MCP_Development_BridgeEvent"
    sockets.Fusion360MCPServer.assert_called_once_with(
        addon._bridge, host="127.0.0.1", port=9877
    )
    listener, event = addon._server, addon._bridge
    addon.stop(None)
    listener.stop.assert_called_once()
    event.stop.assert_called_once()


def test_development_protocol_rejects_execution(monkeypatch):
    import fusion360_mcp.server as server

    monkeypatch.setattr(server, "_send", lambda *args, **kwargs: {"ok": True})

    async def check():
        app = build_server(
            "socket",
            tool_list=development_list,
            tool_lookup=development_lookup,
            structured_results=True,
        )
        async with create_connected_server_and_client_session(app) as session:
            assert not (await session.call_tool("dev_reload_candidates", {})).isError
            assert (
                await session.call_tool("dev_reload_candidates", {"code": "x"})
            ).isError
            assert (await session.call_tool("execute_code", {"code": "x"})).isError

    anyio.run(check)


def test_fixed_cad_reload_checks_hashes_before_loading(addon, tmp_path, monkeypatch):
    root = tmp_path / "fixture"
    (root / "server").mkdir(parents=True)
    hashes = {}
    modules = []
    monkeypatch.setattr(addon, "__file__", str(root / "Fusion360MCPDev.py"))
    monkeypatch.setattr(addon, "RUNTIME_PACKAGE", "_cad_reload_test")
    handler = Mock()
    for name in addon.CANDIDATE_MODULES:
        relative = f"server/{name}.py"
        path = root / relative
        path.write_text("VALUE = 1\n")
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        module = SimpleNamespace(
            __file__=str(path), CommandHandler=Mock(return_value=handler)
        )
        monkeypatch.setitem(sys.modules, f"_cad_reload_test.server.{name}", module)
        modules.append(module)
    (root / ".fusion-mcp-test-ownership.json").write_text(
        json.dumps(
            {
                "kind": "fusion-mcp-development-fixture",
                "files": hashes,
            }
        )
    )
    reloader = Mock(side_effect=lambda module: module)
    monkeypatch.setattr(addon.importlib, "reload", reloader)
    result, receipts = addon.reload_handler()
    assert result is handler
    assert set(receipts) == set(addon.CANDIDATE_MODULES)
    assert reloader.call_count == len(addon.CANDIDATE_MODULES)
    reloader.reset_mock()
    (root / "server/hints.py").write_text("unreviewed change")
    with pytest.raises(ImportError, match="staging record"):
        addon.reload_handler()
    reloader.assert_not_called()
