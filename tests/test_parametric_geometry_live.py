"""Live constrained profiles and count-driven joined-feature acceptance."""

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.fusion_e2e


def test_constrained_profile_and_joined_pattern_live():
    async def check():
        root = Path(__file__).resolve().parents[1]
        destination = root / ".pytest_cache/issue-32-geometry-development-live.json"
        report = {
            "status": "started",
            "calls": [],
            "source_sha256": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in (
                    "addon/server/command_handler.py",
                    "addon/server/mechanical_queries.py",
                    "tests/development_mcp.py",
                    "tests/test_parametric_geometry_live.py",
                )
            },
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tests.development_mcp"],
        )
        with anyio.fail_after(180):
            async with stdio_client(parameters) as streams:
                async with ClientSession(
                    *streams,
                    read_timeout_seconds=timedelta(seconds=30),
                ) as session:
                    await session.initialize()

                    async def call(name, arguments, error=False):
                        result = await session.call_tool(name, arguments)
                        report["calls"].append(
                            {
                                "tool": name,
                                "arguments": arguments,
                                "result": result.model_dump(mode="json"),
                            }
                        )
                        destination.write_text(
                            json.dumps(report, indent=2),
                            encoding="utf-8",
                        )
                        assert result.isError is error, result.content
                        return result.structuredContent

                    report["loaded_source"] = await call("dev_reload_candidates", {})
                    for plane, component_name, axis in (
                        ("xy", None, "z"),
                        ("yz", "GeometryChild", "x"),
                    ):
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                        created = await call(
                            "create_design",
                            {
                                "name": f"MCP_GeometryAcceptance_{plane}_{stamp}",
                            },
                        )
                        identity = created["document_id"]
                        owner = (
                            {"component_name": component_name} if component_name else {}
                        )
                        if component_name:
                            await call("create_component", {"name": component_name})
                        for name, value, unit in (("Size", 40, "mm"), ("Count", 2, "")):
                            await call(
                                "create_parameter",
                                {
                                    "name": name,
                                    "value": value,
                                    "unit": unit,
                                },
                            )
                        await call(
                            "create_box_parametric",
                            {
                                "length": "3 mm",
                                "width": "20 mm",
                                "height": "100 mm",
                                "plane": plane,
                                "body_name": "PatternSpine",
                                **owner,
                            },
                        )
                        sketch = await call("create_sketch", {"plane": plane, **owner})
                        vertices = [
                            {"x": "0 mm", "y": "0 mm"},
                            {"x": "Size", "y": "0 mm"},
                            {"x": "Size", "y": "20 mm"},
                            {"x": "0 mm", "y": "20 mm"},
                        ]
                        profile = await call(
                            "draw_parametric_convex_profile",
                            {
                                "document_id": identity,
                                "sketch_name": sketch["sketch_name"],
                                "vertices": vertices,
                                **owner,
                            },
                        )
                        assert profile["is_fully_constrained"]
                        assert len(profile["dimension_names"]) == 8
                        shelf = await call(
                            "extrude",
                            {
                                "height": 0.2,
                                "operation": "join",
                                "sketch_name": sketch["sketch_name"],
                                **owner,
                            },
                        )
                        seed_scene = await call("get_scene_info", {})
                        assert seed_scene["bodies_count"] == 1
                        assert seed_scene["bodies"][0]["volume"] == pytest.approx(7.48)
                        for override in (
                            {"quantity": "1.5"},
                            {"quantity": "10 mm"},
                            {"spacing": "0 mm"},
                            {"feature_names": ["MissingSeed"]},
                            {"document_id": "stale"},
                        ):
                            await call(
                                "pattern_features",
                                {
                                    "document_id": identity,
                                    "feature_names": [shelf["feature_name"]],
                                    "axis": axis,
                                    "quantity": "Count",
                                    "spacing": "30 mm",
                                    "feature_name": "RejectedPattern",
                                    **owner,
                                    **override,
                                },
                                error=True,
                            )
                        unchanged_seed = await call("get_scene_info", {})
                        for key in ("bodies", "sketches", "timeline_count"):
                            assert unchanged_seed[key] == seed_scene[key]
                        pattern = await call(
                            "pattern_features",
                            {
                                "document_id": identity,
                                "feature_names": [shelf["feature_name"]],
                                "axis": axis,
                                "quantity": "Count",
                                "spacing": "30 mm",
                                "feature_name": "ShelfPattern",
                                **owner,
                            },
                        )
                        assert pattern["health_state"] == 0
                        scene = await call("get_scene_info", {})
                        assert scene["bodies_count"] == 1
                        assert scene["bodies"][0]["volume"] == pytest.approx(8.96)
                        await call(
                            "pattern_features",
                            {
                                "document_id": identity,
                                "feature_names": [shelf["feature_name"]],
                                "axis": axis,
                                "quantity": "Count",
                                "spacing": "30 mm",
                                "feature_name": "ShelfPattern",
                                **owner,
                            },
                            error=True,
                        )
                        unchanged_pattern = await call("get_scene_info", {})
                        for key in ("bodies", "sketches", "timeline_count"):
                            assert unchanged_pattern[key] == scene[key]

                        async def set_expression(name, expression):
                            inspected = await call(
                                "get_design_parameters",
                                {
                                    "document_id": identity,
                                },
                            )
                            previous = next(
                                row["expression"]
                                for row in inspected["parameters"]
                                if row["name"] == name
                            )
                            await call(
                                "set_parameter_expression",
                                {
                                    "document_id": identity,
                                    "name": name,
                                    "expected_expression": previous,
                                    "expression": expression,
                                },
                            )

                        for count, volume in ((1, 7.48), (3, 10.44)):
                            await set_expression("Count", str(count))
                            scene = await call("get_scene_info", {})
                            assert scene["bodies_count"] == 1
                            assert scene["bodies"][0]["volume"] == pytest.approx(volume)
                        await set_expression("Size", "50 mm")
                        scene = await call("get_scene_info", {})
                        assert scene["bodies_count"] == 1
                        assert scene["bodies"][0]["volume"] == pytest.approx(11.64)
                        health = await call("get_feature_health", owner)
                        assert all(
                            feature["health_state"] == 0
                            for feature in health["features"]
                        ), health
                        await set_expression("Size", "40 mm")
                        await set_expression("Count", "2")
                    report["status"] = "passed"
                    report["cleanup"] = (
                        "Separate unsaved test designs retained; source parameters "
                        "restored. No existing user design cleared or saved."
                    )
                    destination.write_text(
                        json.dumps(report, indent=2),
                        encoding="utf-8",
                    )

    anyio.run(check)
