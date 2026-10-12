"""Guard the reconstruction geometry and sequential MCP workflow."""

import json
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anyio
import pytest

from scripts.create_stencils import (
    Workflow,
    annotation_obstacles,
    label_box,
    label_is_clear,
    rotated_rectangle,
    run,
    stencil_labels,
    stencil_layouts,
)


@pytest.mark.parametrize("layout", stencil_layouts(), ids=lambda layout: layout["name"])
def test_all_label_boxes_survive_apertures_bevels_and_scale_marks(layout):
    occupied = annotation_obstacles(layout)
    labels = stencil_labels(layout)
    expected = sum(
        len(layout[kind]) for kind in ("circles", "squares", "hexagons", "triangles")
    )
    expected += layout["ruler_length"] // 10 + 1
    expected += 12 if layout["protractor"] else 0
    expected += 2 if layout["name"] == "Mixed_Shapes" else 1
    assert len(labels) == expected
    for label in labels:
        box = label_box(*label)
        assert label_is_clear(layout, box, occupied), label
        occupied.append(box)


def test_small_circle_label_original_position_overlaps_neighbor():
    layout = stencil_layouts()[0]
    original = label_box("16 mm", 23, 182, 0.9)
    assert not label_is_clear(layout, original, annotation_obstacles(layout))


def test_impossible_labels_stop_before_any_fusion_mutation(tmp_path):
    layout = dict(stencil_layouts()[0], width=5)
    workflow = Workflow(SimpleNamespace(), tmp_path / "report.json")
    workflow.call = AsyncMock()
    with pytest.raises(ValueError, match="No visible"):
        anyio.run(workflow.build, layout, "test")
    workflow.call.assert_not_awaited()


def test_label_repair_cannot_resume_and_overwrite_original_report(tmp_path):
    with pytest.raises(ValueError, match="separate report"):
        anyio.run(run, tmp_path / "report.json", True, True)


def test_layout_report_comparison_accepts_json_round_trip():
    recorded = json.loads(json.dumps(stencil_layouts()))
    assert recorded == json.loads(json.dumps(stencil_layouts()))
    recorded[0]["circles"][0][2] += 1
    assert recorded != json.loads(json.dumps(stencil_layouts()))


def test_three_layouts_exclude_crossed_out_ellipse_template():
    layouts = stencil_layouts()
    assert [layout["name"] for layout in layouts] == [
        "Circles_Small",
        "Circles_Large",
        "Mixed_Shapes",
    ]
    assert [len(layout["circles"]) for layout in layouts] == [22, 7, 15]
    assert len(layouts[2]["squares"]) == 15
    assert len(layouts[2]["hexagons"]) == len(layouts[2]["triangles"]) == 12
    for layout in layouts:
        for center_x, center_y, diameter in layout["circles"]:
            assert (
                0 < center_x - diameter / 2 < center_x + diameter / 2 < layout["width"]
            )
            assert (
                0 < center_y - diameter / 2 < center_y + diameter / 2 < layout["height"]
            )
        for index, first in enumerate(layout["circles"]):
            for second in layout["circles"][index + 1 :]:
                assert (
                    math.dist(first[:2], second[:2]) > (first[2] + second[2]) / 2 + 0.35
                )


def test_rotated_tick_is_rectangular_and_does_not_change_size():
    for angle in [0, 30, 90, 180, 355]:
        points = rotated_rectangle(2, 3, 1.5, 0.12, angle)
        assert math.dist(points[0], points[1]) == pytest.approx(1.5)
        assert math.dist(points[1], points[2]) == pytest.approx(0.12)
        assert sum(point[0] for point in points) / 4 == pytest.approx(2)
        assert sum(point[1] for point in points) / 4 == pytest.approx(3)


def result(payload=None, error=False):
    return SimpleNamespace(
        isError=error,
        content="test failure",
        structuredContent=payload,
        model_dump=lambda **kwargs: {"isError": error, "structuredContent": payload},
    )


def test_call_does_not_retry_errors_and_preserves_report(tmp_path):
    session = SimpleNamespace(call_tool=AsyncMock(return_value=result(error=True)))
    workflow = Workflow(session, tmp_path / "report.json")

    async def check():
        with pytest.raises(RuntimeError, match="failed"):
            await workflow.call("extrude_sketch_entities", {})
        session.call_tool.assert_awaited_once()
        assert workflow.report["status"] == "failed_inspect_before_retry"
        assert workflow.report_path.exists()

    anyio.run(check)


def test_labels_and_extrusions_convert_mm_to_cm(tmp_path):
    session = SimpleNamespace(call_tool=AsyncMock(return_value=result({"ok": True})))
    workflow = Workflow(session, tmp_path / "report.json")

    async def check():
        await workflow.label("Labels", "10 mm", 50, 20, 1.2)
        arguments = session.call_tool.call_args.args[1]
        assert arguments["height"] == 0.12 and arguments["y"] == 2
        assert arguments["text"] == "10 mm"
        assert arguments["width"] == pytest.approx(0.9)
        assert arguments["box_height"] == pytest.approx(0.18)
        await workflow.extrusion("Labels", "texts", -0.001, "Text")
        arguments = session.call_tool.call_args.args[1]
        assert arguments["distance"] == -0.001
        assert arguments["entity_type"] == "texts" and arguments["operation"] == "cut"

    anyio.run(check)


def test_small_circle_columns_use_compact_single_line_unit_labels():
    labels = stencil_labels(stencil_layouts()[0])[:22]
    assert all(
        text.endswith(" mm") and not text.startswith("DIA")
        for text, *position in labels
    )
    assert all("\n" not in text for text, *position in labels)


def test_workflow_creates_new_document_and_saves_only_after_validation(tmp_path):
    session = SimpleNamespace(call_tool=AsyncMock())
    workflow = Workflow(session, tmp_path / "report.json")
    calls = []

    async def call(name, arguments):
        calls.append((name, arguments))
        if name == "create_design":
            return {"document_id": "owned"}
        if name == "create_sketch":
            return {"sketch_name": "Sketch"}
        if name == "get_object_info":
            return {"bounding_box": {"max": [10.5, 20, 0.25]}}
        if name == "get_feature_health":
            return {"features": [{"health_state": 0}]}
        if name == "get_document_state":
            return {"project_name": "MCP_Dev"}
        return {"ok": True}

    workflow.call = call
    workflow.capture = AsyncMock()
    anyio.run(workflow.build, stencil_layouts()[0], "test")
    assert calls[0][0] == "create_design"
    assert calls[-3][0] == "get_feature_health"
    assert calls[-2][0] == "save_sandbox_design"
    assert calls[-2][1]["document_id"] == "owned"
    assert not any(name in {"delete_all", "execute_code"} for name, arguments in calls)
    text_calls = [arguments for name, arguments in calls if name == "draw_sketch_text"]
    assert any("RULER cm" in arguments["text"] for arguments in text_calls)
    assert any("deg" in arguments["text"] for arguments in text_calls)


@pytest.mark.parametrize("changed_identity", [False, True])
def test_resume_reconciles_save_without_repeating_mutation(tmp_path, changed_identity):
    workflow = Workflow(SimpleNamespace(), tmp_path / "report.json")
    name = "MCP_Stencil_Circles_Small_Approx_test"
    workflow.report["calls"] = [
        {
            "tool": "save_sandbox_design",
            "arguments": {"document_id": "owned", "name": name},
            "result": {"isError": False, "structuredContent": {"save_accepted": True}},
        }
    ]
    workflow.call = AsyncMock(
        side_effect=[
            {
                "document_id": "saved" if changed_identity else "owned",
                "document_name": name,
                "project_name": "MCP_Dev",
                "is_saved": True,
                "data_file_id": "cloud-owned",
            },
            {"found": True},
            {"features": [{"health_state": 0}]},
        ]
    )
    workflow.capture = AsyncMock()
    suffix = anyio.run(workflow.reconcile_accepted_save)
    assert suffix == "test" and len(workflow.report["designs"]) == 1
    assert [entry.args[0] for entry in workflow.call.call_args_list] == [
        "get_document_state",
        "get_object_info",
        "get_feature_health",
    ]


def test_resume_rejects_unaccepted_save_and_wrong_document(tmp_path):
    workflow = Workflow(SimpleNamespace(), tmp_path / "report.json")
    with pytest.raises(RuntimeError, match="exactly one"):
        anyio.run(workflow.reconcile_accepted_save)
    workflow.report["calls"] = [
        {
            "tool": "save_sandbox_design",
            "arguments": {
                "document_id": "owned",
                "name": "MCP_Stencil_Circles_Small_Approx_test",
            },
            "result": {"isError": False, "structuredContent": {"save_accepted": True}},
        }
    ]
    workflow.call = AsyncMock(
        return_value={
            "document_id": "other",
            "document_name": "other",
            "project_name": "MCP_Dev",
        }
    )
    with pytest.raises(RuntimeError, match="exact saved stencil"):
        anyio.run(workflow.reconcile_accepted_save)
