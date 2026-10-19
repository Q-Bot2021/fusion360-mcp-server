"""Opt-in live acceptance for development assembly candidates."""

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

from tests.test_sandbox_live import tool_payload

pytestmark = pytest.mark.fusion_e2e

SOURCES = (
    "addon/server/command_handler.py",
    "addon/server/mechanical_queries.py",
    "src/fusion360_mcp/server.py",
    "src/fusion360_mcp/tools.py",
    "tests/development_mcp.py",
    "tests/test_assembly_live.py",
)


def _rotation_angle(before, after):
    trace = sum(
        sum(after[row][k] * before[col][k] for k in range(3))
        for row, col in ((0, 0), (1, 1), (2, 2))
    )
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1) / 2))))


class Recorder:
    def __init__(self, session, directory, profile="development"):
        root = Path(__file__).resolve().parents[1]
        self.session = session
        self.directory = directory
        self.report = {
            "status": "started",
            "profile": profile,
            "calls": [],
            "source_sha256": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                for path in SOURCES
            },
        }

    def save(self):
        (self.directory / "report.json").write_text(
            json.dumps(self.report, indent=2), encoding="utf-8"
        )

    async def call(self, name, arguments, expect_error=False):
        result = await self.session.call_tool(name, arguments)
        self.report["calls"].append({
            "tool": name, "arguments": arguments,
            "result": result.model_dump(mode="json"),
        })
        if result.isError and not expect_error:
            inspection = await self.session.call_tool("get_scene_info", {})
            self.report["post_error_scene"] = inspection.model_dump(mode="json")
            self.report["status"] = "failed_inspected_no_retry"
        self.save()
        assert result.isError == expect_error, result.content
        return None if expect_error else tool_payload(result)

    async def faces(self, body_name, occurrence_path):
        page = await self.call("get_body_topology", {
            "body_name": body_name, "entity_type": "faces",
            "occurrence_path": occurrence_path, "limit": 200,
        })
        return page["faces"]


def _session_parameters():
    return StdioServerParameters(
        command=sys.executable, args=["-m", "tests.development_mcp"]
    )


def _directory(prefix):
    directory = Path(".pytest_cache") / (
        prefix + "-" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    )
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def _face_at(faces, axis, side):
    def key(face):
        return face["bounding_box"][side][axis]

    planar = [face for face in faces if face["surface_type"] == "adsk::core::Plane"]
    target = (max if side == "max" else min)(key(face) for face in planar)
    matches = [
        face for face in planar
        if abs(key(face) - target) < 1e-6
        and abs(face["bounding_box"]["min"][axis]
                - face["bounding_box"]["max"][axis]) < 1e-6
    ]
    assert len(matches) == 1
    return matches[0]["index"]


def test_nested_as_built_occurrence_paths_live():
    async def check():
        nested_component_file_id = os.environ.get(
            "FUSION_TEST_NESTED_COMPONENT_DATA_FILE_ID"
        )
        assert nested_component_file_id, (
            "Set FUSION_TEST_NESTED_COMPONENT_DATA_FILE_ID to an accessible "
            "saved component design in MCP_Dev"
        )
        directory = _directory("nested-joint-paths")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                source = await call("get_document_state", {})
                assert source["is_saved"] and source["data_file_id"]
                capacity = await call("diagnose_document_save", {
                    "document_id": source["document_id"],
                })
                if capacity["quota_applies"]:
                    assert capacity["available_slots"] >= 1
                name = "MCP_" + directory.name
                created_document = await call("create_design", {"name": name})
                await call("create_component", {"name": "HingeFixture"})
                await call("save_design", {
                    "document_id": created_document["document_id"],
                    "name": name, "project_name": "MCP_Dev",
                })
                opened = None
                for _ in range(20):
                    candidate = await call("get_document_state", {})
                    if candidate["is_saved"] and candidate["data_file_id"]:
                        opened = candidate
                        break
                    await anyio.sleep(0.5)
                assert opened is not None, "Fixture cloud save remains pending"
                for translation in ([0, 0, 0], [5, 0, 0]):
                    await call("insert_design", {
                        "data_file_id": nested_component_file_id,
                        "parent_component_name": "HingeFixture",
                        "translation": translation, "referenced": True,
                    })
                inventory = await call("list_occurrences", {})
                children = [row for row in inventory["occurrences"]
                            if row["path"].startswith("HingeFixture:1+")]
                assert len(children) == 2
                assert children[0]["component_name"] == children[1]["component_name"]
                before = await call("list_joints", {})
                await call("create_as_built_joint", {
                    "component_one": children[0]["component_name"],
                    "component_two": children[1]["path"],
                    "joint_type": "rigid",
                }, expect_error=True)
                assert (await call("list_joints", {}))["total"] == before["total"]
                name = "NestedPathMount"
                existing = [joint for joint in before["joints"]
                            if joint["name"] == name]
                if not existing:
                    created = await call("create_as_built_joint", {
                        "component_one": children[0]["path"],
                        "component_two": children[1]["path"],
                        "joint_type": "rigid", "joint_name": name,
                    })
                    assert created["occurrence_one"] == children[0]["path"]
                    assert created["occurrence_two"] == children[1]["path"]
                after = await call("list_joints", {})
                assert after["total"] == before["total"] + (not existing)
                selected = next(row for row in after["joints"] if row["name"] == name)
                assert selected["joint_type"] == "rigid"
                assert selected["occurrence_one"] == children[0]["path"]
                assert selected["occurrence_two"] == children[1]["path"]
                restored_inventory = await call("list_occurrences", {})
                assert restored_inventory == inventory
                await call("save_design", {"document_id": opened["document_id"]})
                await call("open_design", {"data_file_id": source["data_file_id"]})
                recorder.report["status"] = "passed_nested_joint_path_selection"
                recorder.save()

    anyio.run(check)


def test_active_hinge_source_mounting_holes_live():
    async def check():
        directory = _directory("hinge-source-holes")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                state = await call("get_document_state", {})
                fixtures = {
                    "DoorHinge_FixedLeaf_20261018": ("FixedHingeLeaf", -1.8, 3),
                    "DoorHinge_MovingLeaf_20261018": ("MovingHingeLeaf", 1.8, 2),
                }
                assert state["document_name"] in fixtures
                body_name, hole_x, knuckle_count = fixtures[state["document_name"]]
                assert state["is_saved"] and state["data_file_id"]
                scene = await call("get_scene_info", {})
                assert scene["bodies_count"] == 1
                assert scene["bodies"][0]["name"] == body_name
                assert scene["bodies"][0]["volume"] > 0
                faces = await recorder.faces(body_name, "root")
                mounting_centers = []
                bores = []
                for face in faces:
                    if face["surface_type"] != "adsk::core::Cylinder":
                        continue
                    low = face["bounding_box"]["min"]
                    high = face["bounding_box"]["max"]
                    size = [high[axis] - low[axis] for axis in range(3)]
                    center = [(high[axis] + low[axis]) / 2 for axis in range(3)]
                    if size == pytest.approx([0.44, 0.25, 0.44], abs=1e-6):
                        assert low[1] == pytest.approx(0, abs=1e-6)
                        assert high[1] == pytest.approx(0.25, abs=1e-6)
                        mounting_centers.append(center)
                    elif size[:2] == pytest.approx([0.44, 0.44], abs=1e-6):
                        assert center[:2] == pytest.approx([0, 0], abs=1e-6)
                        bores.append(face)
                assert len(mounting_centers) == 3
                assert sorted(center[2] for center in mounting_centers) == (
                    pytest.approx([2, 5, 8], abs=1e-6)
                )
                assert all(
                    center[0] == pytest.approx(hole_x, abs=1e-6)
                    for center in mounting_centers
                )
                assert len(bores) == knuckle_count
                recorder.report["status"] = "passed_hinge_source_mounting_holes"
                recorder.report["document"] = state
                recorder.report["mounting_hole_centers"] = mounting_centers
                recorder.save()

    anyio.run(check)


def test_active_door_source_mortises_and_pilots_live():
    async def check():
        directory = _directory("door-source-mounting")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                state = await call("get_document_state", {})
                fixtures = {
                    "DoorFrame_Source_20261018": ("DoorFrame", -1.8, -3, -0.6),
                    "DoorPanel_Source_20261018": ("DoorPanel", 1.8, 0.6, 3),
                }
                assert state["document_name"] in fixtures
                body_name, hole_x, pocket_left, pocket_right = fixtures[
                    state["document_name"]
                ]
                assert state["is_saved"] and state["data_file_id"]
                scene = await call("get_scene_info", {})
                assert scene["bodies_count"] == 1
                assert scene["bodies"][0]["name"] == body_name
                faces = await recorder.faces(body_name, "root")
                centers = []
                pocket_starts = []
                for face in faces:
                    low = face["bounding_box"]["min"]
                    high = face["bounding_box"]["max"]
                    size = [high[axis] - low[axis] for axis in range(3)]
                    if face["surface_type"] == "adsk::core::Cylinder":
                        assert size == pytest.approx([0.3, 2.25, 0.3], abs=1e-6)
                        assert low[1] == pytest.approx(0.25, abs=1e-6)
                        assert high[1] == pytest.approx(2.5, abs=1e-6)
                        centers.append([(low[index] + high[index]) / 2
                                        for index in range(3)])
                    elif (
                        low[1] == pytest.approx(0.25, abs=1e-6)
                        and high[1] == pytest.approx(0.25, abs=1e-6)
                        and size[2] == pytest.approx(10, abs=1e-6)
                    ):
                        assert low[0] == pytest.approx(pocket_left, abs=1e-6)
                        assert high[0] == pytest.approx(pocket_right, abs=1e-6)
                        pocket_starts.append(low[2])
                assert len(centers) == 6
                assert sorted(center[2] for center in centers) == pytest.approx(
                    [17, 20, 23, 187, 190, 193], abs=1e-6
                )
                assert all(center[0] == pytest.approx(hole_x) for center in centers)
                assert sorted(pocket_starts) == pytest.approx([15, 185], abs=1e-6)
                recorder.report["status"] = "passed_mortises_and_pilot_alignment"
                recorder.report["document"] = state
                recorder.save()

    anyio.run(check)


def test_inserted_hinge_subassembly_motion_and_clearance_live():
    async def check():
        hinge_assembly_file_id = os.environ.get(
            "FUSION_TEST_HINGE_ASSEMBLY_DATA_FILE_ID"
        )
        assert hinge_assembly_file_id, (
            "Set FUSION_TEST_HINGE_ASSEMBLY_DATA_FILE_ID to the saved hinge "
            "assembly fixture"
        )
        directory = _directory("inserted-hinge-acceptance")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                state = await call("get_document_state", {})
                assert state["data_file_id"] == hinge_assembly_file_id
                components = [
                    "DoorHinge_FixedLeaf_20261018",
                    "DoorHinge_MovingLeaf_20261018",
                    "DoorHinge_Pin_20261018",
                ]
                inventory = await call("list_occurrences", {})
                assert inventory["total"] == 3
                assert all(row["is_referenced"] for row in inventory["occurrences"])
                scene = await call("get_scene_info", {})
                assert scene["bodies_count"] == 3
                assert all(row["occurrence_path"] != "root" for row in scene["bodies"])
                joints = await call("list_joints", {})
                active = {
                    row["name"]: row for row in joints["joints"]
                    if not row["is_suppressed"]
                }
                assert set(active) == {"PinRetainedInFixedLeaf", "HingeLeafRotation"}
                assert active["PinRetainedInFixedLeaf"]["joint_type"] == "rigid"
                assert active["HingeLeafRotation"]["joint_type"] == "revolute"
                baseline = await call("drive_joint", {
                    "joint_name": "HingeLeafRotation",
                    "values": {"rotation_degrees": 0},
                })
                moving_path = "DoorHinge_MovingLeaf_20261018:1"
                initial = baseline["occurrence_transforms"][moving_path]
                fixed = {
                    row["path"]: row["transform"]
                    for row in (await call("list_occurrences", {}))["occurrences"]
                    if row["component_name"] != components[1]
                }
                for angle in (0, -15, -30, -45, -60, -75, -90):
                    driven = await call("drive_joint", {
                        "joint_name": "HingeLeafRotation",
                        "values": {"rotation_degrees": angle},
                    })
                    moved = driven["occurrence_transforms"][moving_path]
                    assert _rotation_angle(initial["rotation"], moved["rotation"]) == (
                        pytest.approx(abs(angle), abs=1e-4)
                    )
                    collision = await call("check_interference", {
                        "component_names": components,
                        "cross_occurrence_only": True,
                    })
                    assert collision["count"] == 0, collision["interferences"]
                    current_fixed = {
                        row["path"]: row["transform"]
                        for row in (await call("list_occurrences", {}))["occurrences"]
                        if row["component_name"] != components[1]
                    }
                    assert current_fixed == fixed
                restored = await call("drive_joint", {
                    "joint_name": "HingeLeafRotation",
                    "values": {"rotation_degrees": 0},
                })
                for path, expected in baseline["occurrence_transforms"].items():
                    actual = restored["occurrence_transforms"][path]
                    assert actual["translation"] == pytest.approx(
                        expected["translation"], abs=1e-9
                    )
                    for actual_row, expected_row in zip(
                        actual["rotation"], expected["rotation"], strict=True
                    ):
                        assert actual_row == pytest.approx(expected_row, abs=1e-9)
                recorder.report["status"] = "passed_inserted_hinge_sampled_motion"
                recorder.report["sampled_angles_degrees"] = [
                    0, -15, -30, -45, -60, -75, -90
                ]
                recorder.save()

    anyio.run(check)


MOTION_CASES = {
    "rigid": {},
    "revolute": {"rotation_degrees": 90},
    "slider": {"slide": 1.5},
    "cylindrical": {"rotation_degrees": 45, "slide": 1.0},
    "pin_slot": {"rotation_degrees": 30, "slide": 0.75},
    "planar": {"primary_slide": 1.2, "secondary_slide": 0.5},
    "ball": {"pitch_degrees": 20},
}


@pytest.mark.parametrize("parent", ["", "Fixture"])
@pytest.mark.parametrize("joint_type", list(MOTION_CASES))
def test_joint_types_drive_and_animate_live(joint_type, parent):
    async def check():
        directory = _directory(f"joint-{joint_type}-{parent or 'root'}")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                if parent:
                    await call("create_component", {"name": parent})
                for name in ("Base", "Mover"):
                    await call("create_component", {
                        "name": name, **({"parent_name": parent} if parent else {}),
                    })
                await call("create_box_parametric", {
                    "length": 4, "width": 4, "height": 1, "plane": "xy",
                    "component_name": "Base", "body_name": "BaseBlock",
                })
                await call("create_box_parametric", {
                    "length": 2, "width": 2, "height": 1, "origin_x": 8,
                    "plane": "yz" if parent else "xy",
                    "component_name": "Mover", "body_name": "MoverBlock",
                })
                occurrences = await call("list_occurrences", {})
                paths = {row["component_name"]: row["path"]
                         for row in occurrences["occurrences"]}
                prefix = f"{parent}:1+" if parent else ""
                assert paths["Base"] == prefix + "Base:1"
                assert paths["Mover"] == prefix + "Mover:1"
                base_top = _face_at(
                    await recorder.faces("BaseBlock", paths["Base"]), 2, "max"
                )
                mover_bottom = _face_at(
                    await recorder.faces("MoverBlock", paths["Mover"]),
                    0 if parent else 2, "min",
                )
                limits = {}
                if joint_type == "revolute":
                    limits["rotation_limits_degrees"] = [-10, 100]
                if joint_type == "slider":
                    limits["slide_limits"] = [-2, 2]
                created = await call("create_joint", {
                    "joint_name": f"Matrix_{joint_type}",
                    "joint_type": joint_type,
                    "geometry_one": {
                        "occurrence_path": paths["Mover"], "entity": "face",
                        "body_name": "MoverBlock", "index": mover_bottom,
                        "key_point": "center",
                    },
                    "geometry_two": {
                        "occurrence_path": paths["Base"], "entity": "face",
                        "body_name": "BaseBlock", "index": base_top,
                        "key_point": "center",
                    },
                    "is_flipped": True,
                    **limits,
                })
                assert created["joint_type"] == joint_type
                assert created["occurrence_one"] == paths["Mover"]
                assert created["health_state"] == 0, created["message"]
                for field, (minimum, maximum) in (
                    ("rotation_degrees", limits.get("rotation_limits_degrees",
                                                    (None, None))),
                    ("slide", limits.get("slide_limits", (None, None))),
                ):
                    if minimum is not None:
                        assert created["limits"][field]["minimum"] == pytest.approx(
                            minimum
                        )
                        assert created["limits"][field]["maximum"] == pytest.approx(
                            maximum
                        )
                mover_bounds = await call("get_bounding_box", {"name": "MoverBlock"})
                base_bounds = await call("get_bounding_box", {"name": "BaseBlock"})
                assert mover_bounds["min"][2] == pytest.approx(
                    base_bounds["max"][2], abs=1e-6
                )
                assert mover_bounds["center"][:2] == pytest.approx(
                    base_bounds["center"][:2], abs=1e-6
                )
                listed = await call("list_joints", {})
                assert [joint["name"] for joint in listed["joints"]] == [
                    f"Matrix_{joint_type}"
                ]
                values = MOTION_CASES[joint_type]
                if not values:
                    await call("drive_joint", {
                        "joint_name": "Matrix_rigid",
                        "values": {"rotation_degrees": 10},
                    }, expect_error=True)
                    recorder.report["status"] = "passed_rigid_alignment"
                    recorder.save()
                    return
                baseline = await call("drive_joint", {
                    "joint_name": f"Matrix_{joint_type}",
                    "values": {field: 0 for field in values},
                })
                before = baseline["occurrence_transforms"][paths["Mover"]]
                driven = await call("drive_joint", {
                    "joint_name": f"Matrix_{joint_type}", "values": values,
                })
                for field, value in values.items():
                    assert driven["motion"][field] == pytest.approx(value, abs=1e-6)
                after = driven["occurrence_transforms"][paths["Mover"]]
                rotations = [v for f, v in values.items() if f.endswith("_degrees")]
                slides = [v for f, v in values.items() if not f.endswith("_degrees")]
                angle = _rotation_angle(before["rotation"], after["rotation"])
                assert angle == pytest.approx(abs(sum(rotations)), abs=1e-4)
                if not rotations:
                    displacement = math.dist(before["translation"],
                                             after["translation"])
                    assert displacement == pytest.approx(
                        math.hypot(*slides), abs=1e-6
                    )

                def flat(transform):
                    return [*transform["translation"],
                            *(value for row in transform["rotation"]
                              for value in row)]

                assert flat(driven["occurrence_transforms"][paths["Base"]]) == (
                    pytest.approx(
                        flat(baseline["occurrence_transforms"][paths["Base"]]),
                        abs=1e-9,
                    )
                )
                field = next(iter(values))
                if joint_type == "revolute":
                    await call("drive_joint", {
                        "joint_name": "Matrix_revolute",
                        "values": {"rotation_degrees": 120},
                    }, expect_error=True)
                await call("drive_joint", {
                    "joint_name": f"Matrix_{joint_type}",
                    "values": {"unsupported_field": 1},
                }, expect_error=True)
                frame_values = [0, values[field] / 2, values[field]]
                animation = await call("animate_joint", {
                    "joint_name": f"Matrix_{joint_type}", "field": field,
                    "values": frame_values, "view": "iso",
                    "width": 640, "height": 480,
                })
                assert [frame["actual"] for frame in animation["frames"]] == (
                    pytest.approx(frame_values, abs=1e-6)
                )
                for frame in animation["frames"]:
                    path = Path(frame["path"])
                    assert path.is_file() and path.stat().st_size == frame["bytes"]
                    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                assert animation["final"]["motion"][field] == pytest.approx(
                    values[field], abs=1e-6
                )
                recorder.report["frames"] = [
                    frame["path"] for frame in animation["frames"]
                ]
                recorder.report["status"] = "passed_create_drive_animate"
                recorder.save()

    anyio.run(check)


@pytest.mark.parametrize("angle", [0, 90])
def test_rigid_planar_face_mount_probe_live(angle):
    """Record how planar-face center joints orient a plate in a pocket."""

    async def check():
        directory = _directory(f"rigid-mount-{angle}")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                for name in ("Jamb", "Plate"):
                    await call("create_component", {"name": name})
                await call("create_box_parametric", {
                    "length": 4, "width": 10, "height": 40, "origin_x": -4,
                    "component_name": "Jamb", "body_name": "JambBody",
                })
                await call("create_box_parametric", {
                    "length": 0.25, "width": 2.85, "height": 10, "origin_x": -0.25,
                    "origin_y": 7.15, "origin_z": 15,
                    "component_name": "Jamb", "body_name": "Pocket",
                })
                await call("boolean_operation", {
                    "target_body": "JambBody", "tool_body": "Pocket",
                    "operation": "cut",
                })
                await call("create_box_parametric", {
                    "length": 0.25, "width": 2.85, "height": 10, "origin_x": -0.4,
                    "origin_y": -3.5, "origin_z": -5,
                    "component_name": "Plate", "body_name": "PlateBody",
                })
                jamb_faces = await recorder.faces("JambBody", "Jamb:1")
                pocket = [
                    face["index"] for face in jamb_faces
                    if face["bounding_box"]["min"][0] == pytest.approx(-0.25)
                    and face["bounding_box"]["max"][0] == pytest.approx(-0.25)
                ]
                plate_back = _face_at(
                    await recorder.faces("PlateBody", "Plate:1"), 0, "min"
                )
                assert len(pocket) == 1
                joint = await call("create_joint", {
                    "joint_name": "PlateMount", "joint_type": "rigid",
                    "geometry_one": {
                        "occurrence_path": "Plate:1", "entity": "face",
                        "body_name": "PlateBody", "index": plate_back,
                    },
                    "geometry_two": {
                        "occurrence_path": "Jamb:1", "entity": "face",
                        "body_name": "JambBody", "index": pocket[0],
                    },
                    "is_flipped": True, "angle_degrees": angle,
                })
                bounds = await call("get_bounding_box", {"name": "PlateBody"})
                recorder.report["plate_bounds"] = bounds
                recorder.report["joint"] = joint
                recorder.report["status"] = "recorded"
                recorder.save()
                assert joint["health_state"] == 0
                assert bounds["center"] == pytest.approx([-0.125, 8.575, 20])
                assert bounds["size"] == pytest.approx(
                    [0.25, 2.85, 10] if angle == 0 else [0.25, 10, 2.85]
                )
                recorder.report["status"] = "passed_pocket_alignment"
                recorder.save()

    anyio.run(check)


@pytest.mark.parametrize("plane", ["yz", "xz"])
def test_offset_sketch_plane_mapping_probe_live(plane):
    """Record component-local sketch axes for offset yz/xz planes."""

    async def check():
        directory = _directory(f"sketch-map-{plane}")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("create_design", {"name": "MCP_" + directory.name})
                sketch = await call("create_sketch", {"plane": plane, "z_offset": 3})
                await call("draw_circle", {
                    "radius": 0.5, "center_x": 1, "center_y": 2,
                    "sketch_name": sketch["sketch_name"],
                })
                await call("extrude", {
                    "height": 1, "sketch_name": sketch["sketch_name"],
                })
                scene = await call("get_scene_info", {})
                bounds = await call("get_bounding_box", {
                    "name": scene["bodies"][0]["name"],
                })
                recorder.report["bounds"] = bounds
                recorder.report["status"] = "recorded"
                recorder.save()

    anyio.run(check)


async def _edges(recorder, body_name, occurrence_path):
    page = await recorder.call("get_body_topology", {
        "body_name": body_name, "entity_type": "edges",
        "occurrence_path": occurrence_path, "limit": 200,
    })
    return page["edges"]


def _circle_edges_on_plane(edges, axis, coordinate, diameter):
    selected = []
    for edge in edges:
        low, high = edge["bounding_box"]["min"], edge["bounding_box"]["max"]
        sizes = [high[index] - low[index] for index in range(3)]
        if (
            abs(low[axis] - coordinate) < 1e-6
            and abs(high[axis] - coordinate) < 1e-6
            and all(abs(sizes[index] - diameter) < 1e-4
                    for index in range(3) if index != axis)
        ):
            selected.append(edge)
    return selected


@pytest.mark.parametrize("flipped", [False, True])
def test_countersunk_screw_edge_joint_probe_live(flipped):
    async def check():
        directory = _directory(f"screw-joint-{flipped}")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                await call("create_design", {"name": "MCP_" + directory.name})
                for name in ("Leaf", "Screw"):
                    await call("create_component", {"name": name})
                await call("create_box_parametric", {
                    "length": 0.25, "width": 2.85, "height": 10, "origin_x": -0.4,
                    "origin_y": -3.5, "origin_z": -5,
                    "component_name": "Leaf", "body_name": "LeafPlate",
                })
                hole = await call("create_sketch", {
                    "plane": "yz", "z_offset": -0.15, "component_name": "Leaf",
                })
                await call("draw_circle", {
                    "radius": 0.22, "center_x": 0, "center_y": -2.15,
                    "sketch_name": hole["sketch_name"], "component_name": "Leaf",
                })
                await call("extrude", {
                    "height": 0.5, "direction": "negative", "operation": "cut",
                    "sketch_name": hole["sketch_name"], "component_name": "Leaf",
                })
                edges = _circle_edges_on_plane(
                    await _edges(recorder, "LeafPlate", "Leaf:1"), 0, -0.15, 0.44
                )
                faces = await recorder.faces("LeafPlate", "Leaf:1")
                front = [face["index"] for face in faces
                         if face["bounding_box"]["min"][0] == pytest.approx(-0.15)
                         and face["bounding_box"]["max"][0] == pytest.approx(-0.15)]
                assert len(edges) == 1 and len(front) == 1
                await call("chamfer_edges", {
                    "body_name": "LeafPlate", "occurrence_path": "Leaf:1",
                    "edge_indices": [edges[0]["index"]],
                    "reference_face_indices": [front[0]],
                    "distance_one": 0.2, "distance_two": 0.2,
                    "feature_name": "Countersink",
                })
                profile = await call("create_sketch", {
                    "plane": "xy", "component_name": "Screw",
                })
                points = [(0, 0), (0, 0.42), (-0.2, 0.22), (-0.2, 0.2),
                          (-2.7, 0.2), (-2.7, 0), (0, 0)]
                for start, end in zip(points, points[1:]):
                    await call("draw_line", {
                        "start_x": start[0], "start_y": start[1],
                        "end_x": end[0], "end_y": end[1],
                        "sketch_name": profile["sketch_name"],
                        "component_name": "Screw",
                    })
                await call("revolve", {
                    "angle": 360, "sketch_name": profile["sketch_name"],
                    "component_name": "Screw",
                })
                scene = await call("get_scene_info", {})
                screw_body = next(body for body in scene["bodies"]
                                  if body.get("occurrence_path") == "Screw:1"
                                  or body.get("component") == "Screw")
                await call("rename_body", {
                    "body_name": screw_body["name"], "new_name": "ScrewBody",
                })
                screw_edges = _circle_edges_on_plane(
                    await _edges(recorder, "ScrewBody", "Screw:1"), 0, 0, 0.84
                )
                leaf_edges = _circle_edges_on_plane(
                    await _edges(recorder, "LeafPlate", "Leaf:1"), 0, -0.15, 0.84
                )
                assert len(screw_edges) == 1 and len(leaf_edges) == 1
                joint = await call("create_joint", {
                    "joint_name": "ScrewSeat", "joint_type": "rigid",
                    "geometry_one": {
                        "occurrence_path": "Screw:1", "entity": "edge",
                        "body_name": "ScrewBody", "index": screw_edges[0]["index"],
                        "key_point": "center",
                    },
                    "geometry_two": {
                        "occurrence_path": "Leaf:1", "entity": "edge",
                        "body_name": "LeafPlate", "index": leaf_edges[0]["index"],
                        "key_point": "center",
                    },
                    "is_flipped": flipped,
                })
                bounds = await call("get_bounding_box", {"name": "ScrewBody"})
                interference = await call("check_interference", {
                    "component_names": ["Leaf", "Screw"],
                })
                recorder.report.update(
                    joint=joint, screw_bounds=bounds, interference=interference,
                    status="recorded",
                )
                recorder.save()
                assert joint["health_state"] == 0
                expected_x = [-2.85, -0.15] if not flipped else [-0.15, 2.55]
                assert [bounds["min"][0], bounds["max"][0]] == pytest.approx(
                    expected_x
                )
                assert bounds["center"][1:] == pytest.approx([-2.15, 0])
                if not flipped:
                    assert interference["count"] == 0, interference
                recorder.report["status"] = "passed_seated_orientation"
                recorder.save()

    anyio.run(check)


def test_saved_door_joint_inventory_live():
    async def check():
        directory = _directory("door-joint-inventory")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                scene = await call("get_scene_info", {})
                assert scene["design_name"].startswith("MCP_DoorAssembly_20261018")
                joints = await call("list_joints", {})
                door_joints = [
                    joint for joint in joints["joints"]
                    if {joint["occurrence_one"], joint["occurrence_two"]}
                    == {"Frame:1", "Door:1"}
                ]
                active_rigid = [
                    joint for joint in door_joints
                    if joint["joint_type"] == "rigid"
                    and not joint["is_suppressed"]
                ]
                assert len(active_rigid) <= 1
                if active_rigid:
                    await call("suppress_feature", {
                        "feature_name": active_rigid[0]["name"],
                    })
                    joints = await call("list_joints", {})
                    door_joints = [
                        joint for joint in joints["joints"]
                        if {joint["occurrence_one"], joint["occurrence_two"]}
                        == {"Frame:1", "Door:1"}
                    ]
                active = [joint for joint in door_joints if not joint["is_suppressed"]]
                assert len(active) == 1
                assert active[0]["joint_type"] == "revolute"
                recorder.report["status"] = "passed_single_active_revolute"
                recorder.save()

    anyio.run(check)


def test_saved_door_has_no_cross_occurrence_interference_live():
    async def check():
        directory = _directory("door-interference")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                scene = await call("get_scene_info", {})
                assert scene["design_name"].startswith("MCP_DoorAssembly_20261018")
                collisions = await call("check_interference", {
                    "component_names": ["Frame", "Door"],
                    "cross_occurrence_only": True,
                })
                recorder.report["interferences"] = collisions["interferences"]
                recorder.report["status"] = (
                    "passed_no_cross_occurrence_interference"
                    if collisions["count"] == 0
                    else "interference_detected"
                )
                recorder.save()
                assert collisions["count"] == 0, collisions["interferences"]
                full = await call("check_interference", {
                    "component_names": ["Frame", "Door"],
                })
                allowed_pairs = {
                    frozenset((
                        ("Frame:1", "LeftJamb"),
                        ("Frame:1", "HeadJamb"),
                    )),
                    frozenset((
                        ("Frame:1", "RightJamb"),
                        ("Frame:1", "HeadJamb"),
                    )),
                }
                measured = {
                    frozenset((
                        (item["occurrence_one"], item["body_one"]),
                        (item["occurrence_two"], item["body_two"]),
                    )): item["volume"]
                    for item in full["interferences"]
                }
                assert measured.keys() == allowed_pairs
                assert all(
                    volume == pytest.approx(1200, abs=1e-6)
                    for volume in measured.values()
                )

    anyio.run(check)


@pytest.mark.parametrize("parent", ["", "HingeFixture"])
def test_referenced_component_insert_and_open_live(parent):
    async def check():
        directory = _directory("inserted-component")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})

                async def wait_for_cloud_identity():
                    for _ in range(20):
                        state = await call("get_document_state", {})
                        if (
                            state["is_saved"]
                            and state["data_file_id"]
                            and state["project_name"]
                        ):
                            return state
                        await anyio.sleep(0.5)
                    raise AssertionError("Saved design upload metadata stayed pending")

                part_name = f"MCP_{directory.name}_Part"
                part = await call("create_design", {"name": part_name})
                await call("create_box_parametric", {
                    "length": "2 cm", "width": "2 cm", "height": "1 cm",
                    "body_name": "InsertedBody",
                })
                await call("save_design", {
                    "document_id": part["document_id"],
                    "name": part_name,
                    "project_name": "MCP_Dev",
                })
                part_state = await wait_for_cloud_identity()
                part_file_id = part_state["data_file_id"]
                assert part_file_id

                assembly_name = f"MCP_{directory.name}_Assembly"
                assembly = await call("create_design", {"name": assembly_name})
                await call("create_component", {"name": parent or "AssemblyMarker"})
                await call("save_design", {
                    "document_id": assembly["document_id"],
                    "name": assembly_name,
                    "project_name": "MCP_Dev",
                })
                assembly_state = await wait_for_cloud_identity()
                inserted = await call("insert_design", {
                    "data_file_id": part_file_id,
                    "referenced": True,
                    "parent_component_name": parent,
                })
                assert inserted["is_referenced"] is True
                occurrence_path = inserted["path"]
                if parent:
                    assert occurrence_path.startswith(parent + ":1+")
                occurrences = await call("list_occurrences", {})
                matches = [
                    row for row in occurrences["occurrences"]
                    if row["path"] == occurrence_path
                ]
                assert len(matches) == 1 and matches[0]["is_referenced"] is True
                assert matches[0]["body_count"] == 1
                scene = await call("get_scene_info", {})
                assert len(scene["bodies"]) == 1
                assert scene["bodies"][0]["occurrence_path"] == occurrence_path
                await call("save_design", {
                    "document_id": assembly_state["document_id"],
                })
                assembly_state = await wait_for_cloud_identity()
                assembly_file_id = assembly_state["data_file_id"]
                assert assembly_file_id

                reopened_part = await call("open_design", {
                    "data_file_id": part_file_id,
                })
                assert reopened_part["data_file_id"] == part_file_id
                opened = await call("open_design", {
                    "data_file_id": assembly_file_id,
                })
                assert opened["data_file_id"] == assembly_file_id
                assert opened["document_name"] == assembly_name
                recorder.report["status"] = "passed_referenced_insert_and_reopen"
                recorder.report["part_file_id"] = part_file_id
                recorder.report["assembly_file_id"] = assembly_file_id
                recorder.report["occurrence_path"] = occurrence_path
                recorder.report["parent_component_name"] = parent
                recorder.save()

    anyio.run(check)


def test_resume_nested_insertion_context_live():
    async def check():
        previous_directory = max(
            Path(".pytest_cache").glob("inserted-component-*"),
            key=lambda path: path.stat().st_mtime,
        )
        previous = json.loads((previous_directory / "report.json").read_text("utf-8"))
        states = [
            entry["result"].get("structuredContent")
            for entry in previous["calls"]
            if entry["tool"] == "get_document_state"
        ]
        part = next(
            state for state in reversed(states)
            if state and state.get("document_name", "").endswith("_Part")
            and state.get("data_file_id")
        )
        assembly = next(
            state for state in reversed(states)
            if state and state.get("document_name", "").endswith("_Assembly")
            and state.get("data_file_id")
        )
        directory = _directory("nested-context")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                active = await call("get_document_state", {})
                assert active["data_file_id"] == assembly["data_file_id"]
                before = await call("list_occurrences", {})
                children = [
                    item for item in before["occurrences"]
                    if item["path"].startswith("HingeFixture:1+")
                ]
                assert len(children) == 1 and children[0]["is_referenced"]
                inserted = await call("insert_design", {
                    "data_file_id": part["data_file_id"],
                    "parent_component_name": "HingeFixture",
                    "translation": [5, 0, 0],
                    "referenced": True,
                })
                assert inserted["path"].startswith("HingeFixture:1+")
                assert inserted["path"] != children[0]["path"]
                assert inserted["is_grounded"] is None
                assert inserted["grounding_supported"] is False
                assert inserted["is_referenced"] is True
                after = await call("list_occurrences", {})
                assert after["total"] == before["total"] + 1
                assert inserted["path"] in {
                    item["path"] for item in after["occurrences"]
                }
                await call("save_design", {"document_id": active["document_id"]})
                recorder.report["status"] = "passed_nested_context_insertion"
                recorder.save()

    anyio.run(check)


def test_saved_door_assembly_joint_animation_live():
    async def check():
        directory = _directory("door-joint-animation")
        async with stdio_client(_session_parameters()) as streams:
            async with ClientSession(
                streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
            ) as session:
                await session.initialize()
                recorder = Recorder(session, directory)
                call = recorder.call
                await call("dev_reload_candidates", {})
                scene = await call("get_scene_info", {})
                assert scene["design_name"].startswith("MCP_DoorAssembly_20261018")
                joints = await call("list_joints", {})
                door_joints = [
                    joint for joint in joints["joints"]
                    if joint["kind"] == "as_built"
                    and {joint["occurrence_one"], joint["occurrence_two"]}
                    == {"Frame:1", "Door:1"}
                ]
                hinges = [
                    joint for joint in door_joints
                    if joint["name"] == "DoorAssemblyRevolute"
                    and joint["joint_type"] == "revolute"
                    and not joint["is_suppressed"]
                ]
                if not hinges:
                    active = [
                        joint for joint in door_joints if not joint["is_suppressed"]
                    ]
                    assert len(active) <= 2
                    for joint in active:
                        suppressed = await call("suppress_feature", {
                            "feature_name": joint["name"],
                        })
                        assert suppressed["suppressed"] is True
                    created = await call("create_as_built_joint", {
                        "component_one": "Frame",
                        "component_two": "Door",
                        "joint_type": "revolute",
                        "joint_name": "DoorAssemblyRevolute",
                        "rotation_axis": "z",
                    })
                    assert created["joint_type"] == "revolute"
                    joint_name = created["joint_name"]
                else:
                    assert len(hinges) == 1
                    joint_name = hinges[0]["name"]
                baseline = await call("drive_joint", {
                    "joint_name": joint_name,
                    "values": {"rotation_degrees": 0},
                })
                animation = await call("animate_joint", {
                    "joint_name": joint_name,
                    "field": "rotation_degrees",
                    "values": [0, 45, 90],
                    "view": "iso",
                    "width": 800,
                    "height": 600,
                    "restore": True,
                })
                assert [frame["actual"] for frame in animation["frames"]] == (
                    pytest.approx([0, 45, 90], abs=1e-6)
                )
                for frame in animation["frames"]:
                    path = Path(frame["path"])
                    assert path.is_file() and path.stat().st_size == frame["bytes"]
                    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                assert animation["final"]["motion"]["rotation_degrees"] == (
                    pytest.approx(0, abs=1e-6)
                )
                restored = await call("drive_joint", {
                    "joint_name": joint_name,
                    "values": {"rotation_degrees": 0},
                })
                assert restored["occurrence_transforms"] == baseline[
                    "occurrence_transforms"
                ]
                recorder.report["frames"] = [
                    frame["path"] for frame in animation["frames"]
                ]
                recorder.report["status"] = "passed_saved_door_opening_animation"
                recorder.save()

    anyio.run(check)
