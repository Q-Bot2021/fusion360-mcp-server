"""Explicit authorized MCP_Dev save and preview drawing creation acceptance."""

import ast
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.fusion_e2e


@pytest.mark.parametrize(
    "tool, arguments, expected_size, expected_volume",
    [
        (
            "create_box",
            {
                "length": 2,
                "width": 3,
                "height": 4,
                "center_x": 5,
                "center_y": -2,
                "center_z": 1,
            },
            [2, 3, 4],
            24,
        ),
        (
            "create_cylinder",
            {"radius": 1, "height": 3, "axis": "z", "base_x": 5},
            [2, 2, 3],
            3 * math.pi,
        ),
        (
            "create_cylinder",
            {"radius": 0.5, "height": 4, "axis": "x", "base_y": -3},
            [4, 1, 1],
            math.pi,
        ),
        ("create_sphere", {"radius": 1, "center_z": 5}, [2, 2, 2], 4 * math.pi / 3),
        ("create_sphere", {"radius": 0.5, "center_x": -3}, [1, 1, 1], math.pi / 6),
        (
            "create_torus",
            {"major_radius": 2, "minor_radius": 0.5, "axis": "z"},
            [5, 5, 1],
            math.pi**2,
        ),
        (
            "create_torus",
            {"major_radius": 3, "minor_radius": 0.25, "axis": "x", "center_y": 4},
            [0.5, 6.5, 6.5],
            2 * math.pi**2 * 3 * 0.25**2,
        ),
    ],
)
def test_remaining_primitive_production_live(
    tool, arguments, expected_size, expected_volume
):
    async def check():
        directory = Path(".pytest_cache") / (
            "primitive-"
            + tool
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        installed = (
            Path(os.environ["APPDATA"])
            / "Autodesk/Autodesk Fusion 360/API/AddIns/Fusion360MCP/server"
        )
        report = {
            "status": "started",
            "profile": "production",
            "calls": [],
            "expected_size": expected_size,
            "expected_volume": expected_volume,
            "scope": "root-owned primitives; component targeting not supported",
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (
                    "addon/server/command_handler.py",
                    "src/fusion360_mcp/tools.py",
                    "tests/test_sandbox_live.py",
                )
            },
            "installed_sha256": {
                name: hashlib.sha256((installed / name).read_bytes()).hexdigest()
                for name in ("command_handler.py", "mechanical_queries.py")
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "fusion360_mcp", "--mode", "socket"],
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, values, allow_error=False):
                    result = await session.call_tool(name, values)
                    report["calls"].append(
                        {
                            "tool": name,
                            "arguments": values,
                            "result": result.model_dump(mode="json"),
                        }
                    )
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    if not allow_error:
                        assert not result.isError, result.content
                    return result

                await call("ping", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                before = tool_payload(await call("get_scene_info", {}))
                await call(tool, arguments)
                after = tool_payload(await call("get_scene_info", {}))
                assert len(after["bodies"]) == len(before["bodies"]) + 1
                body_name = after["bodies"][-1]["name"]
                await call(
                    "rename_body",
                    {
                        "body_name": body_name,
                        "new_name": "PrimitiveTarget",
                    },
                )
                bounds = tool_payload(
                    await call("get_bounding_box", {"name": "PrimitiveTarget"})
                )
                assert bounds["size"] == pytest.approx(expected_size, abs=1e-5)
                properties = tool_payload(
                    await call(
                        "get_physical_properties",
                        {"body_name": "PrimitiveTarget", "accuracy": "high"},
                    )
                )
                assert properties["volume"] == pytest.approx(expected_volume, rel=1e-4)
                assert properties["mass"] > 0 and properties["area"] > 0
                assert (
                    tool_payload(
                        await call(
                            "get_bounding_box",
                            {
                                "name": "MissingPrimitive",
                            },
                        )
                    )["found"]
                    is False
                )
                missing = await call(
                    "get_physical_properties",
                    {
                        "body_name": "MissingPrimitive",
                    },
                    allow_error=True,
                )
                assert missing.isError
                assert len(
                    tool_payload(await call("get_scene_info", {}))["bodies"]
                ) == len(after["bodies"])
                report["status"] = "passed_root_geometry_component_scope_pending"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize(
    "unit, value, updated, internal",
    [
        ("mm", 20, 35, 3.5),
        ("deg", 30, 90, math.pi / 2),
        ("", 2, 4, 4),
    ],
)
@pytest.mark.parametrize("profile", ["development", "production"])
def test_remaining_parameters_live(profile, unit, value, updated, internal):
    async def check():
        directory = Path(".pytest_cache") / (
            "parameter-" + profile + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started",
            "profile": profile,
            "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (
                    "addon/server/command_handler.py",
                    "addon/server/parameter_units.py",
                    "tests/test_sandbox_live.py",
                )
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments, allow_error=False):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append(
                        {
                            "tool": name,
                            "arguments": arguments,
                            "result": result.model_dump(mode="json"),
                        }
                    )
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    if not allow_error:
                        assert not result.isError, result.content
                    return result

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                baseline = tool_payload(await call("get_parameters", {}))
                await call(
                    "create_parameter",
                    {
                        "name": "AuditValue",
                        "value": value,
                        "unit": unit,
                        "comment": "Disposable acceptance parameter",
                    },
                )
                duplicate = await call(
                    "create_parameter",
                    {
                        "name": "AuditValue",
                        "value": value,
                        "unit": unit,
                    },
                    allow_error=True,
                )
                assert duplicate.isError
                await call("set_parameter", {"name": "AuditValue", "value": updated})
                actual = tool_payload(await call("get_parameters", {}))
                selected = [
                    parameter
                    for parameter in actual["parameters"]
                    if parameter["name"] == "AuditValue"
                ]
                assert len(selected) == 1
                assert selected[0]["value"] == pytest.approx(internal)
                assert actual["count"] == baseline["count"] + 1
                await call("delete_parameter", {"name": "AuditValue"})
                assert tool_payload(await call("get_parameters", {})) == baseline
                for name, arguments in (
                    ("set_parameter", {"name": "AuditValue", "value": 1}),
                    ("delete_parameter", {"name": "AuditValue"}),
                ):
                    assert (await call(name, arguments, allow_error=True)).isError
                assert tool_payload(await call("get_parameters", {})) == baseline
                report["status"] = "passed_parameter_units_and_rejections"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("profile", ["development", "production"])
def test_remaining_component_queries_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "component-queries-" + profile + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started", "profile": profile, "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in ("addon/server/command_handler.py",
                             "addon/server/mechanical_queries.py",
                             "tests/test_sandbox_live.py")
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(["-m", "tests.development_mcp"] if profile == "development"
                  else ["-m", "fusion360_mcp", "--mode", "socket"]),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments, allow_error=False):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append({
                        "tool": name, "arguments": arguments,
                        "result": result.model_dump(mode="json"),
                    })
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    if not allow_error:
                        assert not result.isError, result.content
                    return result

                if profile == "development":
                    await call("dev_reload_candidates", {})
                document = tool_payload(await call("create_design", {
                    "name": "MCP_" + directory.name,
                }))
                assert tool_payload(await call("get_design_type", {}))[
                    "design_type"
                ] == "parametric"
                for owner, plane in (("", "xy"), ("QueryOwner", "yz")):
                    if owner:
                        await call("create_component", {"name": owner})
                    name = "QueryBody" + (owner or "Root")
                    box = tool_payload(await call("create_box_parametric", {
                        "length": 2, "width": 3, "height": 4, "plane": plane,
                        "body_name": name,
                        **({"component_name": owner} if owner else {}),
                    }))
                    await call("rename_body", {
                        "body_name": name, "new_name": name + "Renamed",
                    })
                    bounds = tool_payload(await call("get_bounding_box", {
                        "name": name + "Renamed",
                    }))
                    assert sorted(bounds["size"]) == pytest.approx([2, 3, 4])
                    properties = tool_payload(await call("get_physical_properties", {
                        "body_name": name + "Renamed", "accuracy": "high",
                    }))
                    assert properties["volume"] == pytest.approx(24)
                    assert properties["center_of_mass"] == pytest.approx(
                        bounds["center"]
                    )
                    if owner:
                        component_bounds = tool_payload(await call(
                            "get_bounding_box", {"name": owner}
                        ))
                        assert component_bounds["min"] == pytest.approx(bounds["min"])
                        assert component_bounds["max"] == pytest.approx(bounds["max"])
                    features = []
                    offset = 0
                    while offset is not None:
                        page = tool_payload(await call("get_feature_health", {
                            "component_name": owner, "offset": offset, "limit": 1,
                        }))
                        assert page["total"] > 0
                        features.extend(page["features"])
                        offset = page["next_offset"]
                    assert len(features) == page["total"]
                    assert box["feature_name"] in {
                        feature["name"] for feature in features
                    }
                    assert all(feature["health_state"] == 0 for feature in features)
                components = tool_payload(await call("list_components", {}))
                assert components["count"] == 2
                assert sum(component["is_root"] for component in components[
                    "components"
                ]) == 1
                assert "QueryOwner" in {component["name"] for component in components[
                    "components"
                ]}
                baseline = tool_payload(await call("get_scene_info", {}))
                assert (await call("get_feature_health", {
                    "component_name": "MissingOwner",
                }, allow_error=True)).isError
                assert (await call("rename_body", {
                    "body_name": "MissingBody", "new_name": "ForbiddenRename",
                }, allow_error=True)).isError
                after = tool_payload(await call("get_scene_info", {}))
                assert after["bodies"] == baseline["bodies"]
                state = tool_payload(await call("get_document_state", {}))
                assert state["document_id"] == document["document_id"]
                assert state["document_name"] == document["document_name"]
                assert state["is_saved"] is False
                report["status"] = "passed_root_component_inventory_and_queries"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("owner", ["", "SolidOwner"])
@pytest.mark.parametrize("profile", ["development", "production"])
@pytest.mark.parametrize("plane", ["xy", "yz"])
@pytest.mark.parametrize("operation", [
    "join", "cut", "intersect", "scale", "nonuniform_scale", "split_xy", "split_yz",
])
def test_remaining_solid_operations_live(profile, owner, operation, plane):
    async def check():
        directory = Path(".pytest_cache") / (
            "solid-" + profile + "-" + operation + "-" + plane + "-"
            + (owner or "root") + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started", "profile": profile, "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in ("addon/server/command_handler.py",
                             "tests/test_sandbox_live.py")
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(["-m", "tests.development_mcp"] if profile == "development"
                  else ["-m", "fusion360_mcp", "--mode", "socket"]),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append({
                        "tool": name, "arguments": arguments,
                        "result": result.model_dump(mode="json"),
                    })
                    if result.isError:
                        inspection = await session.call_tool("get_scene_info", {})
                        report["post_error_scene"] = inspection.model_dump(mode="json")
                        report["status"] = "failed_inspected_no_retry"
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                if profile == "development":
                    await call("dev_reload_candidates", {})
                document = await call(
                    "create_design", {"name": "MCP_" + directory.name}
                )
                if owner:
                    await call("create_component", {"name": owner})
                selector = {"component_name": owner} if owner else {}
                boolean = operation in {"join", "cut", "intersect"}
                target = {
                    "length": 2, "width": 2 if boolean else 3,
                    "height": 2 if boolean else 4,
                    "body_name": "SolidTarget", **selector,
                }
                if operation in {"scale", "nonuniform_scale"}:
                    target["plane"] = plane
                if operation.startswith("split"):
                    target.update(origin_x=-1, origin_y=-1.5, origin_z=-2)
                await call("create_box_parametric", target)
                if boolean:
                    await call("create_box_parametric", {
                        "length": 2, "width": 2, "height": 2, "origin_x": 1,
                        "body_name": "SolidTool", **selector,
                    })
                    await call("boolean_operation", {
                        "target_body": "SolidTarget", "tool_body": "SolidTool",
                        "operation": operation,
                    })
                    expected_volume = 12 if operation == "join" else 4
                    expected_count = 1
                elif operation in {"scale", "nonuniform_scale"}:
                    original = await call("get_bounding_box", {"name": "SolidTarget"})
                    anchor = [1, -2, 0.5]
                    arguments = {
                        "body_name": "SolidTarget", "scale": 2,
                        "anchor_x": anchor[0], "anchor_y": anchor[1],
                        "anchor_z": anchor[2],
                    }
                    if operation == "nonuniform_scale":
                        arguments.update(scale_x=2, scale_y=3, scale_z=0.5)
                    await call("scale_body", arguments)
                    expected_volume = 192 if operation == "scale" else 72
                    expected_count = 1
                    bounds = await call("get_bounding_box", {"name": "SolidTarget"})
                    factors = [2, 2, 2] if operation == "scale" else [2, 3, .5]
                    assert bounds["size"] == pytest.approx(
                        [size * factor for size, factor in zip(
                            original["size"], factors
                        )]
                    )
                    for key in ("min", "max"):
                        assert bounds[key] == pytest.approx([
                            origin + (coordinate - origin) * factor
                            for coordinate, origin, factor in zip(
                                original[key], anchor, factors
                            )
                        ])
                else:
                    await call("split_body", {
                        "body_name": "SolidTarget",
                        "splitting_plane": operation.removeprefix("split_"),
                    })
                    expected_volume = 24
                    expected_count = 2
                scene = await call("get_scene_info", {})
                assert len(scene["bodies"]) == expected_count
                volume = 0
                for body in scene["bodies"]:
                    properties = await call("get_physical_properties", {
                        "body_name": body["name"], "accuracy": "high",
                    })
                    volume += properties["volume"]
                assert volume == pytest.approx(expected_volume, rel=1e-5)
                state = await call("get_document_state", {})
                assert state["document_id"] == document["document_id"]
                report["status"] = "passed_geometry_assertions"
                report["volume"] = volume
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("owner", ["", "PatternOwner"])
@pytest.mark.parametrize("kind", ["rectangular", "circular_z", "circular_x"])
def test_remaining_patterns_production_live(owner, kind):
    async def check():
        directory = Path(".pytest_cache") / (
            "pattern-" + kind + "-" + (owner or "root") + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started", "profile": "production", "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in ("addon/server/command_handler.py",
                             "tests/test_sandbox_live.py")
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "fusion360_mcp", "--mode", "socket"],
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append({
                        "tool": name, "arguments": arguments,
                        "result": result.model_dump(mode="json"),
                    })
                    if result.isError:
                        inspection = await session.call_tool("get_scene_info", {})
                        report["post_error_scene"] = inspection.model_dump(mode="json")
                        report["status"] = "failed_inspected_no_retry"
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                await call("create_design", {"name": "MCP_" + directory.name})
                if owner:
                    await call("create_component", {"name": owner})
                await call("create_box_parametric", {
                    "length": .5, "width": .5, "height": .5,
                    "origin_x": 3 if kind != "circular_x" else 0,
                    "origin_y": 3 if kind == "circular_x" else 0,
                    "body_name": "PatternSeed",
                    **({"component_name": owner} if owner else {}),
                })
                if kind == "rectangular":
                    await call("rectangular_pattern", {
                        "body_name": "PatternSeed", "x_count": 3, "y_count": 2,
                        "x_spacing": 2, "y_spacing": 3,
                    })
                    expected_count = 6
                else:
                    await call("circular_pattern", {
                        "body_name": "PatternSeed", "count": 4,
                        "axis": kind.removeprefix("circular_"), "total_angle": 360,
                    })
                    expected_count = 4
                scene = await call("get_scene_info", {})
                assert len(scene["bodies"]) == expected_count
                centers = []
                for body in scene["bodies"]:
                    properties = await call("get_physical_properties", {
                        "body_name": body["name"], "accuracy": "high",
                    })
                    assert properties["volume"] == pytest.approx(.125)
                    centers.append(properties["center_of_mass"])
                if kind == "rectangular":
                    assert sorted({round(center[0], 6) for center in centers}) == [
                        3.25, 5.25, 7.25,
                    ]
                    assert sorted({round(center[1], 6) for center in centers}) == [
                        .25, 3.25,
                    ]
                else:
                    axis_index = 2 if kind == "circular_z" else 0
                    assert all(center[axis_index] == pytest.approx(.25)
                               for center in centers)
                    assert len({tuple(round(value, 5) for value in center)
                                for center in centers}) == 4
                report["status"] = "passed_copy_counts_spacing_and_volumes"
                report["centers"] = centers
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("plane", ["xy", "yz"])
@pytest.mark.parametrize("profile", ["development", "production"])
@pytest.mark.parametrize("kind", [
    "patch", "ruled", "stitch", "thicken_positive", "thicken_negative",
    "thicken_symmetric",
])
def test_remaining_surface_entrypoints_live(profile, plane, kind):
    async def check():
        directory = Path(".pytest_cache") / (
            "surface-" + profile + "-" + kind + "-" + plane + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started", "profile": profile, "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in ("addon/server/command_handler.py",
                             "tests/test_sandbox_live.py")
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(["-m", "tests.development_mcp"] if profile == "development"
                  else ["-m", "fusion360_mcp", "--mode", "socket"]),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append({
                        "tool": name, "arguments": arguments,
                        "result": result.model_dump(mode="json"),
                    })
                    if result.isError:
                        inspection = await session.call_tool("get_scene_info", {})
                        report["post_error_scene"] = inspection.model_dump(mode="json")
                        report["status"] = "failed_inspected_no_retry"
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                if kind != "ruled":
                    sketch = await call("create_sketch", {"plane": plane})
                    await call("draw_rectangle", {
                        "sketch_name": sketch["sketch_name"], "width": 2, "height": 3,
                    })
                    await call("patch_surface", {
                        "sketch_name": sketch["sketch_name"], "continuity": "connected",
                    })
                    initial = await call("get_scene_info", {})
                    await call("rename_body", {
                        "body_name": initial["bodies"][-1]["name"],
                        "new_name": "SurfaceSeed",
                    })
                    if kind == "stitch":
                        second = await call("create_sketch", {"plane": plane})
                        await call("draw_rectangle", {
                            "sketch_name": second["sketch_name"], "width": 2,
                            "height": 3, "origin_x": 2,
                        })
                        await call("patch_surface", {
                            "sketch_name": second["sketch_name"],
                        })
                        surfaces = await call("get_scene_info", {})
                        names = [body["name"] for body in surfaces["bodies"]]
                        await call("stitch_surfaces", {"body_names": names})
                    elif kind.startswith("thicken_"):
                        await call("thicken_surface", {
                            "body_name": "SurfaceSeed", "thickness": .2,
                            "direction": kind.removeprefix("thicken_"),
                        })
                else:
                    await call("create_box_parametric", {
                        "length": 2, "width": 3, "height": 1,
                        "plane": plane, "body_name": "RuledSeed",
                    })
                    await call("ruled_surface", {
                        "body_name": "RuledSeed", "edge_index": 0,
                        "distance": 1, "rule_type": "normal",
                    })
                scene = await call("get_scene_info", {})
                assert len(scene["bodies"]) == (
                    1 if kind in {"patch", "stitch"} else 2
                )
                info = await call("get_object_info", {
                    "name": scene["bodies"][-1]["name"], "entity_type": "body",
                })
                assert info["found"] is True
                properties = await call("get_physical_properties", {
                    "body_name": scene["bodies"][-1]["name"],
                })
                assert properties["area"] > 0
                if kind.startswith("thicken_"):
                    assert properties["volume"] == pytest.approx(1.2)
                    bounds = await call("get_bounding_box", {
                        "name": scene["bodies"][-1]["name"],
                    })
                    normal_axis = 2 if plane == "xy" else 0
                    expected = {
                        "thicken_positive": [0, .2],
                        "thicken_negative": [-.2, 0],
                        "thicken_symmetric": [-.1, .1],
                    }[kind]
                    assert [bounds["min"][normal_axis], bounds["max"][normal_axis]] \
                        == pytest.approx(expected)
                else:
                    assert properties["volume"] == pytest.approx(0, abs=1e-9)
                    if kind in {"patch", "stitch"}:
                        assert properties["area"] == pytest.approx(
                            6 if kind == "patch" else 12
                        )
                report["status"] = "passed_surface_count_and_type"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("profile", ["development", "production"])
@pytest.mark.parametrize("workflow", [
    "suppression", "design_type", "plane_offset", "plane_angle",
    "axis_intersection", "axis_two_points", "distance_root", "distance_child",
    "distance_points", "color_root", "color_child",
])
def test_remaining_timeline_controls_live(profile, workflow):
    async def check():
        directory = Path(".pytest_cache") / (
            "timeline-" + profile + "-" + workflow + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started", "profile": profile, "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in ("addon/server/command_handler.py",
                             "tests/test_sandbox_live.py")
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(["-m", "tests.development_mcp"] if profile == "development"
                  else ["-m", "fusion360_mcp", "--mode", "socket"]),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments, expect_error=False):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append({
                        "tool": name, "arguments": arguments,
                        "result": result.model_dump(mode="json"),
                    })
                    if result.isError:
                        inspection = await session.call_tool("get_scene_info", {})
                        report["post_error_scene"] = inspection.model_dump(mode="json")
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert result.isError == expect_error, result.content
                    return tool_payload(result)

                if profile == "development":
                    await call("dev_reload_candidates", {})
                document = await call(
                    "create_design", {"name": "MCP_" + directory.name}
                )
                if workflow == "suppression":
                    box = await call("create_box_parametric", {
                        "length": 2, "width": 3, "height": 4,
                        "body_name": "TimelineTarget",
                    })
                    original = await call("get_physical_properties", {
                        "body_name": "TimelineTarget",
                    })
                    await call("suppress_feature", {
                        "feature_name": box["feature_name"],
                    })
                    assert (await call("get_scene_info", {}))["bodies_count"] == 0
                    await call("unsuppress_feature", {
                        "feature_name": box["feature_name"],
                    })
                    assert (await call("get_scene_info", {}))["bodies_count"] == 1
                    restored = await call("get_physical_properties", {
                        "body_name": "TimelineTarget",
                    })
                    assert restored["volume"] == pytest.approx(original["volume"])
                    for name in ("suppress_feature", "unsuppress_feature"):
                        await call(name, {"feature_name": "MissingFeature"}, True)
                    assert (await call("get_scene_info", {}))["bodies_count"] == 1
                elif workflow == "design_type":
                    actual_type = await call("get_design_type", {})
                    assert actual_type["design_type"] == "parametric"
                    assert (await call("set_design_type", {
                        "design_type": "parametric",
                    }))["changed"] is False
                    for kind in ("direct", "parametric"):
                        assert (await call("set_design_type", {
                            "design_type": kind,
                        }))["changed"] is True
                        actual_type = await call("get_design_type", {})
                        assert actual_type["design_type"] == kind
                        assert (await call("set_design_type", {
                            "design_type": kind,
                        }))["changed"] is False
                    await call("set_design_type", {"design_type": "invalid"}, True)
                    actual_type = await call("get_design_type", {})
                    assert actual_type["design_type"] == "parametric"
                elif workflow.startswith("distance_") or workflow.startswith("color_"):
                    if workflow == "distance_points":
                        distance = await call("measure_distance", {
                            "entity_one": "1,2,3", "entity_two": "4,6,3",
                        })
                        assert distance["distance"] == pytest.approx(5)
                    else:
                        child = workflow.endswith("child")
                        if child:
                            await call("create_component", {"name": "InspectionOwner"})
                        selector = (
                            {"component_name": "InspectionOwner"} if child else {}
                        )
                        await call("create_box_parametric", {
                            "length": 2, "width": 2, "height": 2,
                            "body_name": "InspectionOne", **selector,
                        })
                        if workflow.startswith("distance_"):
                            await call("create_box_parametric", {
                                "length": 2, "width": 2, "height": 2,
                                "origin_x": 5, "body_name": "InspectionTwo", **selector,
                            })
                        before = await call("get_scene_info", {})
                        if workflow.startswith("distance_"):
                            distance = await call("measure_distance", {
                                "entity_one": "InspectionOne",
                                "entity_two": "InspectionTwo",
                            })
                            assert distance["distance"] == pytest.approx(3)
                            separation = math.dist(distance["point_one"],
                                                   distance["point_two"])
                            assert separation == pytest.approx(3)
                        else:
                            color = await call("set_color", {
                                "body_name": "InspectionOne", "red": 40,
                                "green": 170, "blue": 90, "opacity": 1,
                            })
                            assert color["color"] == [40, 170, 90]
                            assert color["appearance"]
                        after = await call("get_scene_info", {})
                        assert after["bodies"] == before["bodies"]
                else:
                    before = await call("get_scene_info", {})
                    if workflow == "plane_offset":
                        created = await call("create_construction_plane", {
                            "method": "offset", "plane": "yz", "offset": 2,
                        })
                    elif workflow == "plane_angle":
                        created = await call("create_construction_plane", {
                            "method": "angle", "plane": "xy", "edge_name": "x",
                            "angle": 35,
                        })
                    elif workflow == "axis_intersection":
                        created = await call("create_construction_axis", {
                            "method": "intersection", "plane_one": "xy",
                            "plane_two": "yz",
                        })
                    else:
                        created = await call("create_construction_axis", {
                            "method": "two_points", "point_one": [1, 2, 3],
                            "point_two": [2, 4, 6],
                        })
                    assert created["created"] and created["name"]
                    after = await call("get_scene_info", {})
                    assert after["timeline_count"] == before["timeline_count"] + 1
                    assert after["bodies"] == before["bodies"]
                state = await call("get_document_state", {})
                assert state["document_id"] == document["document_id"]
                report["status"] = "passed_roundtrip_and_rejections"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


def tool_payload(result):
    if result.structuredContent is not None:
        return result.structuredContent
    fields = {}
    for line in result.content[0].text.splitlines():
        if not line.startswith("  "):
            continue
        key, separator, value = line.strip().partition(": ")
        if separator:
            try:
                fields[key] = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                fields[key] = value
    return fields


@pytest.mark.parametrize("profile", ["development", "production"])
def test_step_export_live(profile):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    async def check():
        directory = Path(".pytest_cache") / (
            "step-acceptance-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        source_paths = (
            "addon/server/command_handler.py",
            "src/fusion360_mcp/tools.py",
            "tests/test_sandbox_live.py",
        )
        installed = (
            Path(os.environ["APPDATA"])
            / "Autodesk/Autodesk Fusion 360/API/AddIns"
            / ("Fusion360MCPDev" if profile == "development" else "Fusion360MCP")
            / "server/command_handler.py"
        )
        report = {
            "status": "started",
            "profile": profile,
            "calls": [],
            "exports": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in source_paths
            },
            "installed_handler_sha256": hashlib.sha256(
                installed.read_bytes()
            ).hexdigest(),
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
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
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    if result.structuredContent is not None:
                        return result.structuredContent
                    fields = {}
                    for line in result.content[0].text.splitlines():
                        if not line.startswith("  "):
                            continue
                        key, separator, value = line.strip().partition(": ")
                        if separator:
                            try:
                                fields[key] = ast.literal_eval(value)
                            except (ValueError, SyntaxError):
                                fields[key] = value
                    return fields

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_STEP_" + directory.name})
                await call(
                    "create_box_parametric",
                    {
                        "length": 2,
                        "width": 3,
                        "height": 4,
                        "body_name": "ExportRoot",
                    },
                )
                await call("create_component", {"name": "ExportComponent"})
                await call(
                    "create_box_parametric",
                    {
                        "length": 1,
                        "width": 2,
                        "height": 3,
                        "origin_x": 5,
                        "plane": "yz",
                        "component_name": "ExportComponent",
                        "body_name": "ExportNested",
                    },
                )
                await call(
                    "create_box_parametric",
                    {
                        "length": 4,
                        "width": 4,
                        "height": 4,
                        "origin_x": 10,
                        "component_name": "ExportComponent",
                        "body_name": "UnrelatedSibling",
                    },
                )
                before = await call("get_document_state", {})
                scene_before = await call("get_scene_info", {})
                for body_name in ("ExportRoot", "ExportNested"):
                    bounding_box = await call("get_bounding_box", {"name": body_name})
                    physical = await call(
                        "get_physical_properties", {"body_name": body_name}
                    )
                    assert bounding_box["found"]
                    geometry = {
                        "bounding_box": bounding_box,
                        "volume": physical["volume"],
                    }
                    destination = (directory / f"{body_name}.step").resolve()
                    exported = await call(
                        "export_step",
                        {
                            "body_name": body_name,
                            "file_path": str(destination),
                        },
                    )
                    assert exported["exported"]
                    assert destination.is_file() and destination.stat().st_size > 0
                    content = destination.read_text(encoding="ascii", errors="replace")
                    assert "ISO-10303-21;" in content and "END-ISO-10303-21;" in content
                    reader = STEPControl_Reader()
                    assert reader.ReadFile(str(destination)) == IFSelect_RetDone
                    assert reader.TransferRoots() > 0
                    shape = reader.OneShape()
                    solids = TopExp_Explorer(shape, TopAbs_SOLID)
                    solid_count = 0
                    while solids.More():
                        solid_count += 1
                        solids.Next()
                    assert solid_count == 1
                    bounds = Bnd_Box()
                    BRepBndLib.Add_s(shape, bounds)
                    minimum = bounds.CornerMin()
                    maximum = bounds.CornerMax()
                    assert [minimum.X(), minimum.Y(), minimum.Z()] == pytest.approx(
                        [
                            coordinate * 10
                            for coordinate in geometry["bounding_box"]["min"]
                        ],
                        abs=1e-5,
                    )
                    assert [maximum.X(), maximum.Y(), maximum.Z()] == pytest.approx(
                        [
                            coordinate * 10
                            for coordinate in geometry["bounding_box"]["max"]
                        ],
                        abs=1e-5,
                    )
                    properties = GProp_GProps()
                    BRepGProp.VolumeProperties_s(shape, properties)
                    assert properties.Mass() == pytest.approx(
                        geometry["volume"] * 1000, rel=1e-6
                    )
                    report["exports"].append(
                        {
                            "body": body_name,
                            "geometry": geometry,
                            "file": str(destination),
                            "bytes": destination.stat().st_size,
                        }
                    )
                    after = await call("get_document_state", {})
                    assert after == before
                    scene_after = await call("get_scene_info", {})
                    for field in (
                        "bodies_count",
                        "sketches_count",
                        "features_count",
                        "timeline_count",
                    ):
                        assert scene_after[field] == scene_before[field]
                report["status"] = "passed"
                report["round_trip"] = (
                    "OpenCascade STEP reader: one solid, "
                    "matching bounds and volume in mm"
                )
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("profile", ["development", "production"])
def test_generic_geometry_candidates_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "generic-geometry-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started",
            "calls": [],
            "images": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (
                    "addon/server/mechanical_queries.py",
                    "tests/development_mcp.py",
                    "tests/test_sandbox_live.py",
                )
            },
        }
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
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
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                async def capture(body_name, owner, phase):
                    import base64

                    image = await session.call_tool(
                        "render_view",
                        {
                            "view": "right" if owner else "top",
                            "fit": True,
                            "width": 1600,
                            "height": 1200,
                        },
                    )
                    assert not image.isError
                    for block in image.content:
                        if block.type == "image":
                            path = directory / f"{body_name}_{phase}.png"
                            path.write_bytes(base64.b64decode(block.data))
                            report["images"].append(str(path))

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                for owner, plane in (("", "xy"), ("VerticalPart", "yz")):
                    if owner:
                        await call("create_component", {"name": owner})
                    body_name = "Plate" + (owner or "Root")
                    box = await call(
                        "create_box_parametric",
                        {
                            "length": 6,
                            "width": 4,
                            "height": 0.25,
                            **({"component_name": owner} if owner else {}),
                            "plane": plane,
                            "body_name": body_name,
                        },
                    )
                    sketch_name = box["sketch_name"]
                    if owner:
                        local_sketch = await call(
                            "create_sketch",
                            {
                                "plane": "xz",
                                "component_name": owner,
                            },
                        )
                        local_name = local_sketch["sketch_name"]
                        local_target = {
                            "sketch_name": local_name,
                            "component_name": owner,
                        }
                        await call(
                            "draw_rectangle",
                            {
                                **local_target,
                                "width": 0.5,
                                "height": 0.5,
                                "origin_x": 0.5,
                                "origin_y": 0.5,
                            },
                        )
                        await call(
                            "draw_circle",
                            {
                                **local_target,
                                "radius": 0.2,
                                "center_x": 2,
                                "center_y": 1,
                            },
                        )
                        await call(
                            "draw_line",
                            {
                                **local_target,
                                "start_x": 3,
                                "start_y": 1,
                                "end_x": 3.5,
                                "end_y": 1.5,
                            },
                        )
                        await call(
                            "draw_arc",
                            {
                                **local_target,
                                "center_x": 4,
                                "center_y": 1,
                                "start_x": 4.3,
                                "start_y": 1,
                                "sweep_angle": 90,
                            },
                        )
                        await call(
                            "draw_spline",
                            {
                                **local_target,
                                "spline_type": "fit_points",
                                "points": [[0.5, 2], [1, 2.2], [1.5, 2]],
                            },
                        )
                        await call(
                            "create_polygon",
                            {
                                **local_target,
                                "sides": 5,
                                "radius": 0.3,
                                "center_x": 2.5,
                                "center_y": 2.5,
                            },
                        )
                        await call(
                            "add_constraint",
                            {
                                "constraint_type": "horizontal",
                                "entity_one": 2,
                                **local_target,
                            },
                        )
                        await call(
                            "add_dimension",
                            {
                                "dimension_type": "horizontal",
                                "value": 0.5,
                                "entity_one": 2,
                                "entity_two": 3,
                                **local_target,
                            },
                        )
                        await call(
                            "offset_curve",
                            {
                                "curve_index": 1,
                                "offset_distance": 0.05,
                                **local_target,
                            },
                        )
                        await call(
                            "trim_curve",
                            {
                                "curve_index": 5,
                                "point_x": 1,
                                "point_y": 2,
                                **local_target,
                            },
                        )
                        await call(
                            "extend_curve",
                            {
                                "curve_index": 2,
                                "point_x": 3.4,
                                "point_y": 1.4,
                                **local_target,
                            },
                        )
                        await call(
                            "project_geometry",
                            {
                                "source_name": body_name,
                                **local_target,
                            },
                        )
                        inventory = await call(
                            "get_object_info",
                            {
                                "name": local_name,
                                "entity_type": "sketch",
                                "component_name": owner,
                            },
                        )
                        assert inventory["found"] and inventory["curve_count"] >= 12
                        revolve_sketch = await call(
                            "create_sketch",
                            {
                                "plane": "xz",
                                "component_name": owner,
                            },
                        )
                        revolve_name = revolve_sketch["sketch_name"]
                        revolve_target = {
                            "sketch_name": revolve_name,
                            "component_name": owner,
                        }
                        await call(
                            "draw_rectangle",
                            {
                                **revolve_target,
                                "width": 0.25,
                                "height": 0.5,
                                "origin_x": 1,
                                "origin_y": 1,
                            },
                        )
                        revolved = await call(
                            "revolve",
                            {
                                **revolve_target,
                                "angle": 90,
                                "axis_origin_x": 0,
                                "axis_origin_y": 0,
                                "axis_origin_z": 0,
                                "axis_direction_x": 0,
                                "axis_direction_y": 0,
                                "axis_direction_z": 1,
                                "operation": "new_body",
                            },
                        )
                        assert revolved["operation"] == "new_body"
                        automatic = await call(
                            "create_sketch",
                            {
                                "plane": "xy",
                                "component_name": owner,
                            },
                        )
                        automatic_target = {
                            "sketch_name": automatic["sketch_name"],
                            "component_name": owner,
                        }
                        await call(
                            "draw_rectangle",
                            {
                                **automatic_target,
                                "width": 0.4,
                                "height": 0.4,
                                "origin_x": 6,
                                "origin_y": 0,
                            },
                        )
                        constrained = await session.call_tool(
                            "auto_constrain", automatic_target
                        )
                        report["calls"].append(
                            {
                                "tool": "auto_constrain",
                                "arguments": automatic_target,
                                "result": constrained.model_dump(mode="json"),
                            }
                        )
                        if constrained.isError:
                            error_text = constrained.content[0].text
                            if (
                                "AutoConstrain is not available since user is "
                                "restricted" not in error_text
                            ):
                                raise AssertionError(error_text)
                            report.setdefault("pending_prerequisites", []).append(
                                {
                                    "tool": "auto_constrain",
                                    "reason": error_text,
                                }
                            )
                        else:
                            assert (
                                constrained.structuredContent["sketch"]
                                == automatic["sketch_name"]
                            )

                        path_sketch = await call(
                            "create_sketch",
                            {
                                "plane": "xy",
                                "component_name": owner,
                            },
                        )
                        await call(
                            "draw_line",
                            {
                                "sketch_name": path_sketch["sketch_name"],
                                "component_name": owner,
                                "start_x": 0,
                                "start_y": 8,
                                "end_x": 2,
                                "end_y": 8,
                            },
                        )
                        sweep_profile = await call(
                            "create_sketch",
                            {
                                "plane": "yz",
                                "component_name": owner,
                            },
                        )
                        await call(
                            "draw_circle",
                            {
                                "sketch_name": sweep_profile["sketch_name"],
                                "component_name": owner,
                                "center_y": 8,
                                "radius": 0.15,
                            },
                        )
                        swept = await call(
                            "sweep",
                            {
                                "profile_sketch_name": sweep_profile["sketch_name"],
                                "path_sketch_name": path_sketch["sketch_name"],
                                "profile_index": 0,
                                "path_curve_index": 0,
                                "operation": "new_body",
                                "component_name": owner,
                            },
                        )
                        assert swept["operation"] == "new_body"

                        loft_profiles = []
                        for offset in (8, 10):
                            loft_sketch = await call(
                                "create_sketch",
                                {
                                    "plane": "xy",
                                    "z_offset": offset,
                                    "component_name": owner,
                                },
                            )
                            loft_profiles.append(loft_sketch["sketch_name"])
                            await call(
                                "draw_circle",
                                {
                                    "sketch_name": loft_sketch["sketch_name"],
                                    "component_name": owner,
                                    "center_x": 4,
                                    "center_y": 8,
                                    "radius": 0.3 if offset == 8 else 0.2,
                                },
                            )
                        lofted = await call(
                            "loft",
                            {
                                "profile_sketch_names": loft_profiles,
                                "operation": "new_body",
                                "component_name": owner,
                            },
                        )
                        assert lofted["operation"] == "new_body"
                    text = await call(
                        "draw_sketch_text",
                        {
                            "sketch_name": sketch_name,
                            "component_name": owner,
                            "text": "20 mm",
                            "x": 1,
                            "y": 1,
                            "height": 0.15,
                            "width": 2,
                            "box_height": 0.3,
                        },
                    )
                    assert text["text"] == "20 mm"
                    await capture(body_name, owner, "placement")
                    raised = await call(
                        "extrude_sketch_entities",
                        {
                            "sketch_name": sketch_name,
                            "component_name": owner,
                            "entity_type": "texts",
                            "distance": 0.3,
                            "operation": "join",
                            "feature_name": "RaisedText" + (owner or "Root"),
                        },
                    )
                    assert raised["health_state"] == 0
                    engraved = await call(
                        "extrude_sketch_entities",
                        {
                            "sketch_name": sketch_name,
                            "component_name": owner,
                            "entity_type": "texts",
                            "distance": 0.001,
                            "operation": "cut",
                            "feature_name": "LocalEngraving" + (owner or "Root"),
                        },
                    )
                    assert engraved["health_state"] == 0
                    await capture(body_name, owner, "extrusion")
                    opposite = await call(
                        "extrude_sketch_entities",
                        {
                            "sketch_name": sketch_name,
                            "component_name": owner,
                            "entity_type": "profiles",
                            "distance": -0.1,
                            "operation": "new_body",
                            "feature_name": "ReverseProfile" + (owner or "Root"),
                        },
                    )
                    assert (
                        opposite["health_state"] == 0 and opposite["entity_count"] >= 1
                    )
                    topology = await call("get_body_topology", {"body_name": body_name})
                    edges = list(topology["edges"])
                    while topology["next_offset"] is not None:
                        topology = await call(
                            "get_body_topology",
                            {
                                "body_name": body_name,
                                "offset": topology["next_offset"],
                            },
                        )
                        edges.extend(topology["edges"])
                    eligible = [
                        edge
                        for edge in edges
                        if len(edge["face_indices"]) == 2
                        and sum(
                            (high - low) ** 2
                            for low, high in zip(
                                edge["bounding_box"]["min"], edge["bounding_box"]["max"]
                            )
                        )
                        > 1
                    ]
                    assert eligible
                    selected = eligible[0]
                    chamfered = await call(
                        "chamfer_edges",
                        {
                            "body_name": body_name,
                            "edge_indices": [selected["index"]],
                            "reference_face_indices": [selected["face_indices"][0]],
                            "distance_one": 0.02,
                            "distance_two": 0.04,
                            "feature_name": "ExplicitBevel" + (owner or "Root"),
                        },
                    )
                    assert (
                        chamfered["health_state"] == 0 and chamfered["edge_count"] == 1
                    )
                    await capture(body_name, owner, "chamfer")
                    fillet_body = "ExplicitFillet" + (owner or "Root")
                    await call(
                        "create_box_parametric",
                        {
                            "length": 0.8,
                            "width": 0.8,
                            "height": 0.8,
                            "origin_x": 8,
                            **({"component_name": owner} if owner else {}),
                            "plane": plane,
                            "body_name": fillet_body,
                        },
                    )
                    fillet_before = await call(
                        "get_physical_properties", {"body_name": fillet_body}
                    )
                    fillet_result = await call(
                        "fillet",
                        {
                            "body_name": fillet_body,
                            "radius": 0.05,
                            "edge_indices": [0],
                            "occurrence_path": "root" if not owner else "",
                        },
                    )
                    assert fillet_result["edges_count"] == 1
                    fillet_after = await call(
                        "get_physical_properties", {"body_name": fillet_body}
                    )
                    assert fillet_after["volume"] < fillet_before["volume"]

                    chamfer_body = "ExplicitChamfer" + (owner or "Root")
                    await call(
                        "create_box_parametric",
                        {
                            "length": 0.8,
                            "width": 0.8,
                            "height": 0.8,
                            "origin_x": 10,
                            **({"component_name": owner} if owner else {}),
                            "plane": plane,
                            "body_name": chamfer_body,
                        },
                    )
                    chamfer_before = await call(
                        "get_physical_properties", {"body_name": chamfer_body}
                    )
                    chamfer_result = await call(
                        "chamfer",
                        {
                            "body_name": chamfer_body,
                            "distance": 0.05,
                            "edge_indices": [0],
                            "occurrence_path": "root" if not owner else "",
                        },
                    )
                    assert chamfer_result["edges_count"] == 1
                    chamfer_after = await call(
                        "get_physical_properties", {"body_name": chamfer_body}
                    )
                    assert chamfer_after["volume"] < chamfer_before["volume"]
                report["status"] = "passed_geometry_visual_review_pending"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.fusion_e2e
@pytest.mark.parametrize("profile", ["development", "production"])
def test_component_sketch_family_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "component-sketch-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started",
            "profile": profile,
            "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (
                    "addon/server/command_handler.py",
                    "tests/test_sandbox_live.py",
                )
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
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
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call(
                    "create_design", {"name": "ComponentSketch_" + directory.name}
                )
                await call("create_component", {"name": "RotatedSketchOwner"})
                sketch = await call(
                    "create_sketch",
                    {
                        "plane": "yz",
                        "component_name": "RotatedSketchOwner",
                    },
                )
                target = {
                    "sketch_name": sketch["sketch_name"],
                    "component_name": "RotatedSketchOwner",
                }
                await call(
                    "draw_rectangle",
                    {
                        **target,
                        "width": 0.5,
                        "height": 0.5,
                        "origin_x": 0.5,
                        "origin_y": 0.5,
                    },
                )
                await call(
                    "draw_circle",
                    {
                        **target,
                        "radius": 0.2,
                        "center_x": 2,
                        "center_y": 1,
                    },
                )
                await call(
                    "draw_line",
                    {
                        **target,
                        "start_x": 3,
                        "start_y": 1,
                        "end_x": 3.5,
                        "end_y": 1.5,
                    },
                )
                await call(
                    "draw_arc",
                    {
                        **target,
                        "center_x": 4,
                        "center_y": 1,
                        "start_x": 4.3,
                        "start_y": 1,
                        "sweep_angle": 90,
                    },
                )
                await call(
                    "draw_spline",
                    {
                        **target,
                        "spline_type": "fit_points",
                        "points": [[0.5, 2], [1, 2.2], [1.5, 2]],
                    },
                )
                await call(
                    "create_polygon",
                    {
                        **target,
                        "sides": 5,
                        "radius": 0.3,
                        "center_x": 2.5,
                        "center_y": 2.5,
                    },
                )
                await call(
                    "add_constraint",
                    {
                        **target,
                        "constraint_type": "horizontal",
                        "entity_one": 2,
                    },
                )
                await call(
                    "add_dimension",
                    {
                        **target,
                        "dimension_type": "horizontal",
                        "value": 0.5,
                        "entity_one": 2,
                        "entity_two": 3,
                    },
                )
                await call(
                    "offset_curve",
                    {
                        **target,
                        "curve_index": 1,
                        "offset_distance": 0.05,
                    },
                )
                await call(
                    "trim_curve",
                    {
                        **target,
                        "curve_index": 5,
                        "point_x": 1,
                        "point_y": 2,
                    },
                )
                await call(
                    "extend_curve",
                    {
                        **target,
                        "curve_index": 2,
                        "point_x": 3.4,
                        "point_y": 1.4,
                    },
                )
                await call(
                    "create_sketch",
                    {
                        "plane": "xz",
                        "component_name": "RotatedSketchOwner",
                    },
                )
                inventory = await call(
                    "get_object_info",
                    {
                        "name": sketch["sketch_name"],
                        "entity_type": "sketch",
                        "component_name": "RotatedSketchOwner",
                    },
                )
                assert inventory["found"] and inventory["curve_count"] >= 12
                report["status"] = "passed_component_local_sketch_family"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("profile", ["development", "production"])
def test_generic_save_candidate_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "generic-save-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started",
            "profile": profile,
            "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (
                    "addon/server/mechanical_queries.py",
                    "src/fusion360_mcp/tools.py",
                    "tests/test_sandbox_live.py",
                )
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments, allow_error=False):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append(
                        {
                            "tool": name,
                            "arguments": arguments,
                            "result": result.model_dump(mode="json"),
                        }
                    )
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    if not allow_error:
                        assert not result.isError, result.content
                    return result

                if profile == "development":
                    await call("dev_reload_candidates", {})
                name = "MCP_" + directory.name
                created = tool_payload(await call("create_design", {"name": name}))
                rejected = await call(
                    "save_design",
                    {"document_id": "wrong", "name": name, "project_name": "MCP_Dev"},
                    allow_error=True,
                )
                assert rejected.isError
                saved = tool_payload(
                    await call(
                        "save_design",
                        {
                            "document_id": created["document_id"],
                            "name": name,
                            "project_name": "MCP_Dev",
                            "description": "Generic save acceptance",
                        },
                    )
                )
                assert saved["save_accepted"]
                inspected = None
                with anyio.fail_after(60):
                    while inspected is None:
                        result = await call("get_document_state", {}, allow_error=True)
                        if (
                            not result.isError
                            and tool_payload(result).get("project_name") == "MCP_Dev"
                        ):
                            inspected = tool_payload(result)
                        else:
                            await anyio.sleep(0.5)
                assert inspected["document_name"] == name and inspected["is_saved"]
                assert inspected["data_file_id"]
                await call(
                    "create_parameter",
                    {"name": "AcceptanceLength", "value": 20, "unit": "mm"},
                )
                updated = tool_payload(
                    await call(
                        "save_design",
                        {
                            "document_id": inspected["document_id"],
                            "description": "In-place correction",
                        },
                    )
                )
                assert updated["save_accepted"]
                after = tool_payload(await call("get_document_state", {}))
                assert after["data_file_id"] == inspected["data_file_id"]
                assert after["document_name"] == name
                report["status"] = "passed"
                report["saved_fixture"] = after
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.fusion_e2e
@pytest.mark.parametrize("profile", ["development", "production"])
def test_mirror_nested_occurrence_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "mirror-occurrence-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        report = {"status": "started", "profile": profile, "calls": []}
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
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
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                await call("create_component", {"name": "MirrorComponent"})
                await call(
                    "create_box_parametric",
                    {
                        "length": 2,
                        "width": 1,
                        "height": 1,
                        "origin_x": 1,
                        "component_name": "MirrorComponent",
                        "body_name": "MirrorTarget",
                    },
                )
                before = await call("get_scene_info", {})
                targets = [
                    body for body in before["bodies"] if body["name"] == "MirrorTarget"
                ]
                assert len(targets) == 1
                occurrence_path = targets[0]["occurrence_path"]
                assert occurrence_path != "root"
                mirrored = await call(
                    "mirror",
                    {
                        "mirror_plane": "yz",
                        "body_name": "MirrorTarget",
                        "occurrence_path": occurrence_path,
                    },
                )
                assert mirrored["feature_name"]
                after = await call("get_scene_info", {})
                assert len(after["bodies"]) == len(before["bodies"]) + 1
                report["status"] = "passed_nested_occurrence_mirror"
                report["occurrence_path"] = occurrence_path
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.fusion_e2e
@pytest.mark.parametrize("profile", ["development", "production"])
def test_shell_explicit_face_component_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "shell-face-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        report = {"status": "started", "profile": profile, "calls": []}
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
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
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return tool_payload(result)

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                await call("create_component", {"name": "ShellComponent"})
                await call(
                    "create_box_parametric",
                    {
                        "length": 4,
                        "width": 3,
                        "height": 2,
                        "plane": "yz",
                        "component_name": "ShellComponent",
                        "body_name": "ShellPlate",
                    },
                )
                topology = await call(
                    "get_body_topology",
                    {
                        "body_name": "ShellPlate",
                        "entity_type": "faces",
                    },
                )
                assert topology["faces"]
                selected = max(topology["faces"], key=lambda face: face["area"])
                before = await call(
                    "get_physical_properties", {"body_name": "ShellPlate"}
                )
                feature = await call(
                    "shell",
                    {
                        "body_name": "ShellPlate",
                        "thickness": 0.1,
                        "face_indices": [selected["index"]],
                    },
                )
                assert feature["faces_removed"] == 1
                after = await call(
                    "get_physical_properties", {"body_name": "ShellPlate"}
                )
                assert 0 < after["volume"] < before["volume"]
                report["selected_face"] = selected
                report["volume_before"] = before["volume"]
                report["volume_after"] = after["volume"]
                report["status"] = "passed_component_yz_shell"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


@pytest.mark.parametrize("profile", ["development", "production"])
def test_component_object_info_live(profile):
    async def check():
        directory = Path(".pytest_cache") / (
            "object-inspection-"
            + profile
            + "-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        root = Path(__file__).resolve().parents[1]
        report = {
            "status": "started",
            "profile": profile,
            "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in (
                    "addon/server/command_handler.py",
                    "src/fusion360_mcp/tools.py",
                    "tests/test_sandbox_live.py",
                )
            },
        }
        parameters = StdioServerParameters(
            command=sys.executable,
            args=(
                ["-m", "tests.development_mcp"]
                if profile == "development"
                else ["-m", "fusion360_mcp", "--mode", "socket"]
            ),
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()

                async def call(name, arguments, allow_error=False):
                    result = await session.call_tool(name, arguments)
                    report["calls"].append(
                        {
                            "tool": name,
                            "arguments": arguments,
                            "result": result.model_dump(mode="json"),
                        }
                    )
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    if not allow_error:
                        assert not result.isError, result.content
                    return result

                if profile == "development":
                    await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                await call(
                    "create_box_parametric",
                    {
                        "length": 2,
                        "width": 3,
                        "height": 4,
                        "body_name": "DuplicatePart",
                    },
                )
                await call("create_component", {"name": "NestedInspection"})
                nested = tool_payload(
                    await call(
                        "create_box_parametric",
                        {
                            "length": 1,
                            "width": 2,
                            "height": 3,
                            "plane": "yz",
                            "component_name": "NestedInspection",
                            "body_name": "DuplicatePart",
                        },
                    )
                )
                scene = tool_payload(await call("get_scene_info", {}))
                assert scene["bodies_count"] == 2
                assert {body["occurrence_path"] for body in scene["bodies"]} == {
                    "root",
                    "NestedInspection:1",
                }
                assert any(
                    sketch["component_name"] == "NestedInspection"
                    for sketch in scene["sketches"]
                )
                before = tool_payload(await call("get_document_state", {}))
                rejected = await call(
                    "get_object_info", {"name": "DuplicatePart"}, allow_error=True
                )
                assert rejected.isError and "ambiguous" in rejected.content[0].text
                root_body = tool_payload(
                    await call(
                        "get_object_info",
                        {
                            "name": "DuplicatePart",
                            "entity_type": "body",
                            "occurrence_path": "root",
                        },
                    )
                )
                assert root_body["found"] and root_body["volume"] == pytest.approx(24)
                nested_body = tool_payload(
                    await call(
                        "get_object_info",
                        {
                            "name": "DuplicatePart",
                            "entity_type": "body",
                            "occurrence_path": "NestedInspection:1",
                        },
                    )
                )
                assert nested_body["found"] and nested_body["volume"] == pytest.approx(
                    6
                )
                guarded_calls = {
                    "get_bounding_box": {"name": "DuplicatePart"},
                    "get_physical_properties": {"body_name": "DuplicatePart"},
                    "project_geometry": {"source_name": "DuplicatePart"},
                    "fillet": {"body_name": "DuplicatePart", "radius": 0.1},
                    "chamfer": {"body_name": "DuplicatePart", "distance": 0.1},
                    "shell": {"body_name": "DuplicatePart", "thickness": 0.1},
                    "mirror": {"body_name": "DuplicatePart", "mirror_plane": "xy"},
                    "create_hole": {
                        "body_name": "DuplicatePart",
                        "diameter": 0.1,
                        "depth": 0.1,
                    },
                    "rectangular_pattern": {"body_name": "DuplicatePart"},
                    "circular_pattern": {"body_name": "DuplicatePart", "count": 2},
                    "create_thread": {"body_name": "DuplicatePart", "face_index": 0},
                    "draft_faces": {"body_name": "DuplicatePart", "angle": 1},
                    "split_body": {"body_name": "DuplicatePart"},
                    "split_face": {"body_name": "DuplicatePart"},
                    "offset_faces": {"body_name": "DuplicatePart", "distance": 0.1},
                    "scale_body": {"body_name": "DuplicatePart", "scale": 1.1},
                    "rename_body": {
                        "body_name": "DuplicatePart",
                        "new_name": "MustNotRename",
                    },
                    "export_stl": {"body_name": "DuplicatePart"},
                    "export_step": {"body_name": "DuplicatePart"},
                    "boolean_operation": {
                        "target_body": "DuplicatePart",
                        "tool_body": "DuplicatePart",
                    },
                    "set_color": {
                        "body_name": "DuplicatePart",
                        "red": 20,
                        "green": 30,
                        "blue": 40,
                    },
                    "stitch_surfaces": {
                        "body_names": ["DuplicatePart", "DuplicatePart"]
                    },
                    "thicken_surface": {"body_name": "DuplicatePart", "thickness": 0.1},
                    "ruled_surface": {"body_name": "DuplicatePart", "edge_index": 0},
                    "trim_surface": {
                        "body_name": "DuplicatePart",
                        "tool_name": "DuplicatePart",
                    },
                    "create_flange": {"body_name": "DuplicatePart", "edge_index": 0},
                    "create_bend": {"body_name": "DuplicatePart"},
                    "flat_pattern": {"body_name": "DuplicatePart"},
                    "unfold": {"body_name": "DuplicatePart"},
                    "set_appearance": {
                        "target_name": "DuplicatePart",
                        "appearance_name": "UnusedGuardAppearance",
                    },
                    "create_construction_axis": {
                        "method": "edge",
                        "body_name": "DuplicatePart",
                        "edge_index": 0,
                    },
                }
                for tool_name, arguments in guarded_calls.items():
                    guarded = await call(tool_name, arguments, allow_error=True)
                    assert guarded.isError and "ambiguous" in guarded.content[0].text, (
                        tool_name,
                        guarded.content,
                    )
                face_appearance = await call(
                    "set_appearance",
                    {
                        "target_name": "DuplicatePart",
                        "appearance_name": "UnusedGuardAppearance",
                        "target_type": "face",
                        "face_index": 0,
                    },
                    allow_error=True,
                )
                assert (
                    face_appearance.isError
                    and "ambiguous" in face_appearance.content[0].text
                )
                blocked_mutation = await call(
                    "move_body",
                    {
                        "body_name": "DuplicatePart",
                        "x": 10,
                        "y": 0,
                        "z": 0,
                    },
                    allow_error=True,
                )
                assert (
                    blocked_mutation.isError
                    and "ambiguous" in blocked_mutation.content[0].text
                )
                for path, expected in (
                    ("root", root_body),
                    ("NestedInspection:1", nested_body),
                ):
                    preserved = tool_payload(
                        await call(
                            "get_object_info",
                            {
                                "name": "DuplicatePart",
                                "entity_type": "body",
                                "occurrence_path": path,
                            },
                        )
                    )
                    assert preserved["bounding_box"] == expected["bounding_box"]
                    assert preserved["volume"] == expected["volume"]
                sketch = tool_payload(
                    await call(
                        "get_object_info",
                        {
                            "name": nested["sketch_name"],
                            "entity_type": "sketch",
                            "component_name": "NestedInspection",
                        },
                    )
                )
                assert sketch["found"] and sketch["profile_count"] == 1
                missing = tool_payload(
                    await call("get_object_info", {"name": "AbsentInspectionObject"})
                )
                assert missing["found"] is False
                await call(
                    "create_box_parametric",
                    {
                        "length": 1,
                        "width": 1,
                        "height": 1,
                        "origin_x": 8,
                        "component_name": "NestedInspection",
                        "body_name": "UniqueInspectionBody",
                    },
                )
                unique_before = tool_payload(
                    await call("get_object_info", {"name": "UniqueInspectionBody"})
                )
                await call(
                    "move_body",
                    {"body_name": "UniqueInspectionBody", "x": 1, "y": 0, "z": 0},
                )
                unique_after = tool_payload(
                    await call("get_object_info", {"name": "UniqueInspectionBody"})
                )
                assert unique_after["volume"] == pytest.approx(unique_before["volume"])
                for corner in ("min", "max"):
                    expected = list(unique_before["bounding_box"][corner])
                    expected[0] += 1
                    assert unique_after["bounding_box"][corner] == pytest.approx(
                        expected
                    )
                after = tool_payload(await call("get_document_state", {}))
                assert after == before
                report["status"] = "passed"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


def test_set_appearance_valid_target_live():
    async def check():
        directory = Path(".pytest_cache") / (
            "appearance-production-"
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        )
        directory.mkdir(parents=True, exist_ok=False)
        report = {"status": "started", "calls": []}
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "fusion360_mcp", "--mode", "socket"]
        )
        async with stdio_client(parameters) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
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
                    (directory / "report.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    assert not result.isError, result.content
                    return result

                name = "MCP_" + directory.name
                created = await call("create_design", {"name": name})
                await call(
                    "create_box_parametric",
                    {
                        "length": 2,
                        "width": 3,
                        "height": 1,
                        "body_name": "AppearanceAcceptanceBody",
                    },
                )
                before = await call(
                    "get_bounding_box", {"name": "AppearanceAcceptanceBody"}
                )
                applied = await call(
                    "set_appearance",
                    {
                        "target_name": "AppearanceAcceptanceBody",
                        "appearance_name": "Aluminum - Anodized Red",
                        "target_type": "body",
                    },
                )
                assert "applied: True" in applied.content[0].text
                after = await call(
                    "get_bounding_box", {"name": "AppearanceAcceptanceBody"}
                )
                assert before.content == after.content
                image = await session.call_tool(
                    "render_view",
                    {
                        "view": "iso",
                        "fit": True,
                        "width": 1200,
                        "height": 900,
                    },
                )
                assert not image.isError
                import base64

                for block in image.content:
                    if block.type == "image":
                        path = directory / "appearance.png"
                        path.write_bytes(base64.b64decode(block.data))
                        report["image"] = str(path)
                report["document"] = tool_payload(created)
                report["status"] = "passed_assignment_render_review_pending"
                (directory / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )

    anyio.run(check)


def test_stencil_tools_live():
    async def check():
        path = Path(".pytest_cache/stencil-tools-live.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        report = {"status": "started", "production_eligible": False, "calls": []}
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "tests.development_mcp"]
        )

        async with stdio_client(params) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=60)
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
                    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    assert not result.isError, result.content
                    return result.structuredContent

                await call("dev_reload_candidates", {})
                name = "MCP_StencilAcceptance_" + datetime.now(timezone.utc).strftime(
                    "%Y%m%d_%H%M%S"
                )
                created = await call("create_design", {"name": name})
                assert created["document_name"] == name and not created["is_saved"]
                await call(
                    "create_box_parametric",
                    {
                        "length": 10,
                        "width": 6,
                        "height": 0.25,
                        "body_name": "StencilAcceptance",
                    },
                )
                ruler = await call(
                    "chamfer_stencil_edges",
                    {
                        "body_name": "StencilAcceptance",
                        "scope": "left",
                        "vertical_depth": 0.25,
                        "angle_degrees": 30,
                        "feature_name": "Ruler_30deg",
                    },
                )
                assert ruler["health_state"] == 0 and ruler["edge_count"] == 1
                assert any(
                    abs(abs(face["normal"][2]) - 0.8660254038) < 1e-6
                    for face in ruler["bevel_faces"]
                    if face["normal"]
                )
                sketch = await call("create_sketch", {"plane": "xy"})
                await call("draw_circle", {"radius": 0.5, "center_x": 2, "center_y": 3})
                await call(
                    "extrude_sketch_entities",
                    {
                        "sketch_name": sketch["sketch_name"],
                        "entity_type": "profiles",
                        "distance": 0.25,
                        "operation": "cut",
                        "feature_name": "Aperture",
                    },
                )
                internal = await call(
                    "chamfer_stencil_edges",
                    {
                        "body_name": "StencilAcceptance",
                        "scope": "internal",
                        "vertical_depth": 0.01,
                        "angle_degrees": 30,
                        "feature_name": "Aperture_30deg",
                    },
                )
                assert internal["health_state"] == 0 and internal["edge_count"] == 1
                labels = await call("create_sketch", {"plane": "xy", "z_offset": 0.25})
                text = await call(
                    "draw_sketch_text",
                    {
                        "sketch_name": labels["sketch_name"],
                        "text": "DIA 10 mm",
                        "x": 4,
                        "y": 3,
                        "height": 0.15,
                        "width": 2,
                        "box_height": 0.3,
                    },
                )
                assert text["text"] == "DIA 10 mm" and text["text_count"] == 1
                engraved = await call(
                    "extrude_sketch_entities",
                    {
                        "sketch_name": labels["sketch_name"],
                        "entity_type": "texts",
                        "distance": -0.001,
                        "operation": "cut",
                        "feature_name": "Text_0p01mm",
                    },
                )
                assert engraved["health_state"] == 0 and engraved["entity_count"] == 1
                info = await call("get_object_info", {"name": "StencilAcceptance"})
                assert info["found"] and info["volume"] > 0
                assert info["bounding_box"]["max"][2] == pytest.approx(0.25)
                report["status"] = "passed"
                path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    anyio.run(check)


def test_save_fixture_create_and_open_drawing():
    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tests.development_mcp"],
            env=dict(os.environ, FUSION_MCP_HOST="127.0.0.1"),
        )
        path = Path(".pytest_cache/sandbox-drawing-live.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        report = {"status": "started", "production_eligible": False}
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        with anyio.fail_after(120):
            async with stdio_client(params) as streams:
                async with ClientSession(
                    streams[0], streams[1], read_timeout_seconds=timedelta(seconds=50)
                ) as session:
                    await session.initialize()
                    inspected = await session.call_tool("get_document_state", {})
                    assert not inspected.isError, inspected.content
                    state = inspected.structuredContent
                    report["source_before"] = state
                    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    if not state["is_saved"]:
                        name = "MCP_FeatureFixture_" + datetime.now(
                            timezone.utc
                        ).strftime("%Y%m%d_%H%M%S")
                        saved = await session.call_tool(
                            "save_sandbox_design",
                            {
                                "document_id": state["document_id"],
                                "name": name,
                            },
                        )
                        report["save"] = saved.model_dump(mode="json")
                        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                        assert not saved.isError, saved.content
                        state = saved.structuredContent
                        if state.get("metadata_pending"):
                            inspected = await session.call_tool(
                                "get_document_state", {}
                            )
                            report["save_readback"] = inspected.model_dump(mode="json")
                            path.write_text(
                                json.dumps(report, indent=2), encoding="utf-8"
                            )
                            assert not inspected.isError, inspected.content
                            state = inspected.structuredContent
                    assert state["project_name"] == "MCP_Dev", state
                    report["status"] = "drawing_creation_requested"
                    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    created = await session.call_tool(
                        "create_sandbox_drawing",
                        {
                            "document_id": state["document_id"],
                        },
                    )
                    report["creation"] = created.model_dump(mode="json")
                    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    assert not created.isError, created.content
                    opened = await session.call_tool(
                        "open_sandbox_drawing",
                        {
                            "data_file_id": created.structuredContent["data_file_id"],
                        },
                    )
                    report["open"] = opened.model_dump(mode="json")
                    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                    assert not opened.isError, opened.content
                    assert opened.structuredContent["project_name"] == "MCP_Dev"
                    drawing = await session.call_tool("get_drawing_info", {})
                    assert not drawing.isError, drawing.content
                    assert drawing.structuredContent["active_sheet_name"]
                    resource = await session.read_resource(
                        "fusion360://development/drawing"
                    )
                    assert (
                        json.loads(resource.contents[0].text)
                        == drawing.structuredContent
                    )
                    report["drawing"] = drawing.structuredContent
                    report["status"] = "passed"
                    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    anyio.run(check)
