"""Explicit disposable-design acceptance for driving-parameter candidates."""

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


@pytest.mark.parametrize("profile", ["development", "production"])
def test_parameter_expression_regenerates_local_components_live(profile):
    async def check():
        root = Path(__file__).resolve().parents[1]
        destination = root / f".pytest_cache/issue-32-parameter-{profile}-live.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "status": "started",
            "calls": [],
            "source_sha256": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in (
                    "addon/server/command_handler.py",
                    "addon/server/mechanical_queries.py",
                    "tests/development_mcp.py",
                    "tests/test_parametric_parameters_live.py",
                )
            },
        }

        def persist():
            destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

        parameters = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "tests.development_mcp",
                "--port",
                "9876" if profile == "production" else "9877",
            ],
        )
        if profile == "production":
            installed = Path(os.environ["APPDATA"]) / (
                "Autodesk\\Autodesk Fusion 360\\API\\AddIns\\Fusion360MCP"
            )
            for name in ("command_handler.py", "mechanical_queries.py"):
                actual = hashlib.sha256((installed / "server" / name).read_bytes())
                assert (
                    actual.hexdigest()
                    == report["source_sha256"][f"addon/server/{name}"]
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
                        persist()
                        assert result.isError is error, result.content
                        return result.structuredContent

                    if profile == "development":
                        report["loaded_source"] = await call(
                            "dev_reload_candidates", {}
                        )
                    await call("ping", {})
                    for plane, component_name in (
                        ("xy", None),
                        ("yz", "ParameterChild"),
                    ):
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                        created = await call(
                            "create_design",
                            {
                                "name": f"MCP_ParameterAcceptance_{plane}_{stamp}",
                            },
                        )
                        identity = created["document_id"]
                        await call("get_document_state", {})
                        await call(
                            "create_parameter",
                            {
                                "name": "Size",
                                "value": 40,
                                "unit": "mm",
                            },
                        )
                        for name, value, unit, expression, expected in (
                            ("Angle", 30, "deg", "45 deg", math.pi / 4),
                            ("Count", 3, "", "ceil(9 / 2)", 5.0),
                        ):
                            await call(
                                "create_parameter",
                                {
                                    "name": name,
                                    "value": value,
                                    "unit": unit,
                                },
                            )
                            listed = await call(
                                "get_design_parameters",
                                {
                                    "document_id": identity,
                                },
                            )
                            previous = next(
                                row["expression"]
                                for row in listed["parameters"]
                                if row["name"] == name
                            )
                            edited = await call(
                                "set_parameter_expression",
                                {
                                    "document_id": identity,
                                    "name": name,
                                    "expected_expression": previous,
                                    "expression": expression,
                                },
                            )
                            assert edited["parameter"]["value_internal"] == (
                                pytest.approx(expected)
                            )
                            await call(
                                "set_parameter_expression",
                                {
                                    "document_id": identity,
                                    "name": name,
                                    "expected_expression": edited["parameter"][
                                        "expression"
                                    ],
                                    "expression": previous,
                                },
                            )
                        await call(
                            "create_parameter",
                            {
                                "name": "DoubleCount",
                                "value": 1,
                                "unit": "",
                            },
                        )
                        derived = await call(
                            "set_parameter_expression",
                            {
                                "document_id": identity,
                                "name": "DoubleCount",
                                "expected_expression": "1",
                                "expression": "Count * 2",
                            },
                        )
                        assert derived["parameter"]["value_internal"] == 6
                        if component_name:
                            await call("create_component", {"name": component_name})
                        arguments = {
                            "length": "Size",
                            "width": "30 mm",
                            "height": "20 mm",
                            "plane": plane,
                            "body_name": "ParameterBox",
                        }
                        if component_name:
                            arguments["component_name"] = component_name
                        await call("create_box_parametric", arguments)
                        inspected = await call(
                            "get_design_parameters",
                            {
                                "document_id": identity,
                            },
                        )
                        models = [
                            row
                            for row in inspected["parameters"]
                            if row["object_type"] == "adsk::fusion::ModelParameter"
                            and math.isclose(row["value_internal"], 4.0)
                        ]
                        assert len(models) == 1, inspected
                        model = models[0]
                        if component_name:
                            assert model["created_by_component_name"] == component_name
                        await call(
                            "set_parameter_expression",
                            {
                                "document_id": identity,
                                "name": model["name"],
                                "expected_expression": model["expression"],
                                "expression": "Size + 2 mm",
                            },
                        )
                        bounds = await call(
                            "get_bounding_box", {"name": "ParameterBox"}
                        )
                        assert sorted(bounds["size"]) == pytest.approx([2, 3, 4.2])
                        size = next(
                            row
                            for row in inspected["parameters"]
                            if row["name"] == "Size"
                        )
                        await call(
                            "set_parameter_expression",
                            {
                                "document_id": identity,
                                "name": "Size",
                                "expected_expression": size["expression"],
                                "expression": "52 mm",
                            },
                        )
                        changed = await call(
                            "get_bounding_box",
                            {"name": "ParameterBox"},
                        )
                        assert sorted(changed["size"]) == pytest.approx([2, 3, 5.4])
                        current = await call(
                            "get_design_parameters",
                            {
                                "document_id": identity,
                            },
                        )
                        expression = next(
                            row["expression"]
                            for row in current["parameters"]
                            if row["name"] == "Size"
                        )
                        for override in (
                            {"document_id": "stale"},
                            {"expected_expression": "stale"},
                            {"expression": "1 deg"},
                            {"name": "missing"},
                        ):
                            await call(
                                "set_parameter_expression",
                                {
                                    "document_id": identity,
                                    "name": "Size",
                                    "expected_expression": expression,
                                    "expression": "60 mm",
                                    **override,
                                },
                                error=True,
                            )
                        unchanged = await call(
                            "get_bounding_box",
                            {"name": "ParameterBox"},
                        )
                        assert unchanged == changed
                        health_arguments = (
                            {"component_name": component_name} if component_name else {}
                        )
                        health = await call("get_feature_health", health_arguments)
                        assert all(
                            feature["health_state"] == 0
                            for feature in health["features"]
                        ), health
                        await call(
                            "set_parameter_expression",
                            {
                                "document_id": identity,
                                "name": "Size",
                                "expected_expression": expression,
                                "expression": "40 mm",
                            },
                        )
                        await call(
                            "set_parameter_expression",
                            {
                                "document_id": identity,
                                "name": model["name"],
                                "expected_expression": "Size + 2 mm",
                                "expression": model["expression"],
                            },
                        )
                        restored = await call(
                            "get_bounding_box",
                            {"name": "ParameterBox"},
                        )
                        assert sorted(restored["size"]) == pytest.approx([2, 3, 4])
                    report.update(
                        status="passed",
                        cleanup=(
                            "Unsaved test designs retained; parameters restored. "
                            "No existing user document cleared or saved."
                        ),
                    )
                    persist()

    anyio.run(check)
