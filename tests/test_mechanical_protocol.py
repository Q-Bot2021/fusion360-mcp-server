"""Actual MCP tool/resource request paths for isolated inspection candidates."""

import json

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from fusion360_mcp.server import build_server
from fusion360_mcp.tools import get_tool_by_name
from tests import test_mechanical_queries
from tests.development_mcp import (
    candidate_resources,
    development_list,
    development_lookup,
    read_candidate_resource,
)

queries = test_mechanical_queries.queries
design = test_mechanical_queries.design


def test_save_diagnostic_candidate_protocol(queries, monkeypatch):
    from types import SimpleNamespace

    import fusion360_mcp.server as server

    handler = SimpleNamespace(app=SimpleNamespace(
        activeDocument=SimpleNamespace(
            isValid=True, creationId="quota-doc", isSaved=False
        ),
        data=SimpleNamespace(personalUseLimits=SimpleNamespace(
            isValid=True, editableFileCount=10, maxEditableFileCount=10
        )),
    ))

    def send(mode, name, params, **kwargs):
        assert name == "diagnose_document_save"
        assert not kwargs.get("mutation", False)
        return queries.diagnose_document_save(handler, **params)

    monkeypatch.setattr(server, "_send", send)

    async def check():
        app = build_server(
            "socket", tool_list=development_list,
            tool_lookup=development_lookup, structured_results=True,
        )
        async with create_connected_server_and_client_session(app) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert tools["diagnose_document_save"].annotations.readOnlyHint
            result = await session.call_tool("diagnose_document_save", {
                "document_id": "quota-doc", "required_slots": 3,
            })
            assert not result.isError
            assert result.structuredContent["documents_to_make_read_only"] == 3
            for arguments in ({"document_id": "stale"}, {
                "document_id": "quota-doc", "required_slots": 0,
            }):
                assert (await session.call_tool(
                    "diagnose_document_save", arguments
                )).isError
        assert get_tool_by_name("diagnose_document_save") is None

    anyio.run(check)


def test_candidates_and_resources_through_mcp(queries, design, monkeypatch):
    import fusion360_mcp.server as server
    import tests.development_mcp as development

    def send(mode, name, params, **kwargs):
        if name == "get_feature_health":
            return queries.feature_health(design, **params)
        return {
            "ok": False,
            "error_kind": "INVALID_INPUT",
            "error_message": "Activate drawing",
        }

    monkeypatch.setattr(server, "_send", send)
    monkeypatch.setattr(development, "_send", send)

    async def check():
        app = build_server(
            "socket",
            tool_list=development_list,
            tool_lookup=development_lookup,
            structured_results=True,
            extra_resources=candidate_resources(),
            extra_resource_reader=lambda uri: read_candidate_resource(uri, 9877),
        )
        async with create_connected_server_and_client_session(app) as session:
            result = await session.call_tool("get_feature_health", {"limit": 1})
            assert not result.isError and result.structuredContent["total"] == 2
            assert (
                await session.call_tool("get_feature_health", {"limit": 201})
            ).isError
            assert (await session.call_tool("get_drawing_info", {})).isError
            resources = {
                str(item.uri) for item in (await session.list_resources()).resources
            }
            assert "fusion360://development/feature-health" in resources
            response = await session.read_resource(
                "fusion360://development/feature-health"
            )
            assert (
                json.loads(response.contents[0].text)["features"][0]["name"]
                == "Extrude1"
            )
            with pytest.raises(Exception, match="Activate drawing"):
                await session.read_resource("fusion360://development/drawing")
        assert get_tool_by_name("get_feature_health") is not None
        assert get_tool_by_name("get_drawing_info") is None

    anyio.run(check)


def test_promoted_queries_through_production_stdio():
    from tests.test_protocol_e2e import run_session

    async def check(session):
        names = {tool.name for tool in (await session.list_tools()).tools}
        licensed = next(tool for tool in (await session.list_tools()).tools
                if tool.name == "auto_constrain")
        assert "License-gated" in licensed.description
        assert "eligible licensed users" in licensed.description
        assert {
            "get_feature_health",
            "get_document_state",
            "open_design",
            "insert_design",
            "list_occurrences",
        } <= names
        assert "get_drawing_info" not in names
        assert "dev_reload_candidates" not in names
        feature = await session.call_tool("get_feature_health", {"limit": 1})
        assert not feature.isError and "Extrude1" in feature.content[0].text
        state = await session.call_tool("get_document_state", {})
        assert not state.isError and "mock-document" in state.content[0].text
        assert "development_only" not in feature.content[0].text
        assert "development_only" not in state.content[0].text
        opened = await session.call_tool(
            "open_design", {"data_file_id": "saved-design-id"}
        )
        assert not opened.isError and "saved-design-id" in opened.content[0].text
        inserted = await session.call_tool("insert_design", {
            "data_file_id": "part-file-id", "referenced": True,
        })
        assert not inserted.isError and "is_referenced" in inserted.content[0].text
        occurrences = await session.call_tool("list_occurrences", {})
        assert not occurrences.isError and "occurrences" in occurrences.content[0].text
        selected_joint = await session.call_tool("create_as_built_joint", {
            "component_one": "Upper:1+HingeLeaf:1",
            "component_two": "Door:1",
            "joint_type": "rigid",
            "joint_name": "PathMount",
        })
        assert not selected_joint.isError
        assert "Upper:1+HingeLeaf:1" in selected_joint.content[0].text
        distance = await session.call_tool("measure_distance", {
            "entity_one": "1,2,3", "entity_two": "4,6,3",
        })
        assert not distance.isError and "distance" in distance.content[0].text
        assert (await session.call_tool("measure_distance", {
            "entity_one": "1,2,3",
        })).isError
        assert (await session.call_tool("get_feature_health", {"limit": 201})).isError
        for arguments in (
            {"body_name": "Part", "scale": 2, "anchor_x": 1, "anchor_y": -2},
            {"body_name": "Part", "scale": 1, "scale_x": 2,
             "scale_y": 3, "scale_z": .5},
        ):
            result = await session.call_tool("scale_body", arguments)
            assert not result.isError and "scale_body" in result.content[0].text
        for arguments in (
            {"body_name": "Part", "scale": 0},
            {"body_name": "Part", "scale": 2, "scale_x": "invalid"},
            {"body_name": "Part", "scale": 2, "code": "forbidden"},
        ):
            assert (await session.call_tool("scale_body", arguments)).isError
        for tool_name, arguments in (
            (
                "shell",
                {"body_name": "Part", "thickness": .1, "face_indices": [1],
                 "occurrence_path": "Assembly:1+Part:1"},
            ),
            (
                "fillet",
                {
                    "body_name": "Part",
                    "radius": 0.1,
                    "edge_indices": [0],
                    "occurrence_path": "Assembly:1+Part:1",
                },
            ),
            (
                "chamfer",
                {
                    "body_name": "Part",
                    "distance": 0.1,
                    "edge_indices": [0],
                    "occurrence_path": "root",
                },
            ),
            (
                "mirror",
                {
                    "body_name": "Part",
                    "mirror_plane": "yz",
                    "occurrence_path": "Assembly:1+Part:1",
                },
            ),
        ):
            result = await session.call_tool(tool_name, arguments)
            assert not result.isError and tool_name in result.content[0].text
            invalid_field = {
                "shell": "face_indices",
                "mirror": "occurrence_path",
            }.get(tool_name, "edge_indices")
            invalid = await session.call_tool(
                tool_name, {**arguments, invalid_field: ["old"]}
            )
            assert invalid.isError
        moved = await session.call_tool(
            "move_body", {"body_name": "UniquePart", "x": 1, "y": 0, "z": 0}
        )
        assert not moved.isError and "UniquePart" in moved.content[0].text
        assert (
            await session.call_tool(
                "move_body", {"body_name": "UniquePart", "x": "invalid"}
            )
        ).isError
        for tool_name, params in (
            (
                "fillet",
                {
                    "body_name": "UniquePart",
                    "radius": 0.1,
                    "edge_indices": [0],
                    "occurrence_path": "Assembly:1+UniquePart:1",
                },
            ),
            (
                "chamfer",
                {
                    "body_name": "UniquePart",
                    "distance": 0.1,
                    "edge_indices": [1],
                    "occurrence_path": "root",
                },
            ),
        ):
            result = await session.call_tool(tool_name, params)
            assert not result.isError, result.content
            assert (
                await session.call_tool(
                    tool_name, {**params, "edge_indices": ["stale"]}
                )
            ).isError
        created = await session.call_tool("create_design", {"name": "MCP_ProtocolNew"})
        assert not created.isError
        assert "MCP_ProtocolNew" in created.content[0].text
        assert "development_only" not in created.content[0].text
        candidates = {
            "draw_sketch_text": {
                "sketch_name": "Labels",
                "text": "20 mm",
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
                "feature_name": "Text",
            },
            "get_body_topology": {"body_name": "Part"},
            "chamfer_edges": {
                "body_name": "Part",
                "edge_indices": [0],
                "reference_face_indices": [0],
                "distance_one": 0.1,
                "distance_two": 0.2,
                "feature_name": "Bevel",
            },
            "save_design": {
                "document_id": "mock-document",
                "name": "Part",
                "project_name": "Engineering",
            },
        }
        assert candidates.keys() <= names
        for tool_name, params in candidates.items():
            result = await session.call_tool(tool_name, params)
            assert not result.isError, result.content
            assert "development_only" not in result.content[0].text
            assert (
                await session.call_tool(tool_name, {**params, "code": "forbidden"})
            ).isError
        face_topology = await session.call_tool(
            "get_body_topology", {"body_name": "Part", "entity_type": "faces"}
        )
        assert not face_topology.isError and "faces" in face_topology.content[0].text
        shell = await session.call_tool("shell", {
            "body_name": "Part", "thickness": .1,
            "face_indices": [0], "occurrence_path": "root",
        })
        assert not shell.isError and "Part" in shell.content[0].text
        invalid_shell = await session.call_tool("shell", {
            "body_name": "Part", "thickness": .1, "face_indices": ["stale"],
        })
        assert invalid_shell.isError
        assert (
            await session.call_tool("create_sandbox_design", {"name": "MCP_OldName"})
        ).isError
        for name in ("", "   ", "bad/path"):
            assert (await session.call_tool("create_design", {"name": name})).isError

    anyio.run(run_session, check)
