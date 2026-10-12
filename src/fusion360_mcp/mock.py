"""
Mock responses for every Fusion 360 MCP command.

Used when the server is started with ``--mode mock`` so the full
tool→response pipeline can be tested without a running Fusion instance.
Every response includes ``"mode": "mock"`` so callers know it's simulated.

The envelope matches the real addon: success results carry ``ok: True``,
mutation results carry a ``deltas`` sub-dict, and an ``__mock_error__``
sentinel in params forces a classified error response for tests.
"""

import math
from typing import Any

from .hints import classify as _classify

# Mutation commands that get a synthetic deltas payload in mock mode.
# Keep in sync with CommandHandler._MUTATION_COMMANDS in the addon.
_MUTATION_MOCKS: frozenset[str] = frozenset(
    {
        "extrude",
        "extrude_sketch_entities",
        "chamfer_edges",
        "revolve",
        "sweep",
        "loft",
        "fillet",
        "chamfer",
        "shell",
        "mirror",
        "create_hole",
        "rectangular_pattern",
        "circular_pattern",
        "create_thread",
        "draft_faces",
        "split_body",
        "split_face",
        "offset_faces",
        "scale_body",
        "suppress_feature",
        "unsuppress_feature",
        "move_body",
        "boolean_operation",
        "create_box",
        "create_cylinder",
        "create_sphere",
        "create_torus",
        "thicken_surface",
        "patch_surface",
        "stitch_surfaces",
        "ruled_surface",
        "trim_surface",
        "create_flange",
        "create_bend",
        "flat_pattern",
        "unfold",
        "delete_all",
        "undo",
        "set_parameter",
        "execute_code",
        "auto_constrain",
        "create_ucs",
        "set_color",
    }
)

_MOCK_DELTAS = {
    "body_count_before": 0,
    "body_count_after": 1,
    "body_count_delta": 1,
    "mass_g_before": 0.0,
    "mass_g_after": 10.0,
    "mass_g_delta": 10.0,
    "bbox_before": None,
    "bbox_after": {"min": [0.0, 0.0, 0.0], "max": [1.0, 1.0, 1.0]},
}


def mock_command(command_type: str, params: dict[str, Any] | None = None) -> dict:
    """Return a plausible mock response for *command_type*.

    If *params* contains ``__mock_error__`` (a string message), the response
    simulates an addon-side failure: ``ok: False`` plus a classified
    ``error_kind`` and contextual ``hints``.
    """
    from .tools import DISABLED_COMMANDS

    if command_type in DISABLED_COMMANDS:
        return {
            "ok": False,
            "error_kind": "INVALID_INPUT",
            "error_message": f"{command_type} is disabled by policy",
            "hints": [],
            "mode": "mock",
        }
    params = params or {}

    forced = params.get("__mock_error__")
    if forced is not None:
        kind, hint_list = _classify(str(forced))
        return {
            "ok": False,
            "error_kind": kind,
            "error_message": str(forced),
            "hints": hint_list,
            "traceback": f"MockError: {forced}",
            "mode": "mock",
        }

    handler = _DISPATCH.get(command_type, _default_mock)
    result = handler(params)
    result.setdefault("ok", True)
    if command_type in _MUTATION_MOCKS and "deltas" not in result:
        result["deltas"] = dict(_MOCK_DELTAS)
    result["mode"] = "mock"
    return result


# ── individual mock handlers ──────────────────────────────────────────


def _ping(_p: dict) -> dict:
    return {"status": "pong"}


def _get_scene_info(_p: dict) -> dict:
    return {
        "design_name": "MockDesign",
        "bodies": [{"name": "Body1", "component_name": "RootComponent",
                    "occurrence_path": "root", "volume": 1, "area": 6,
                    "material": None, "is_visible": True}],
        "sketches": [{"name": "Sketch1", "component_name": "RootComponent",
                      "profile_count": 1, "is_visible": True}],
        "features": ["Extrude1"],
        "components": [{"name": "RootComponent", "occurrence_path": "root",
                        "is_visible": True}],
        "bodies_count": 1, "sketches_count": 1, "features_count": 1,
        "components_count": 1, "timeline_count": 1,
        "design_type": "DesignProductType",
        "camera": {"eye": [0, 0, 1], "target": [0, 0, 0], "up_vector": [0, 1, 0]},
    }


def _get_feature_health(p: dict) -> dict:
    offset = p.get("offset", 0)
    limit = p.get("limit", 100)
    if (
        type(offset) is not int
        or type(limit) is not int
        or offset < 0
        or not 1 <= limit <= 200
    ):
        return {
            "ok": False,
            "error_kind": "INVALID_INPUT",
            "error_message": "Invalid pagination",
        }
    features = [
        {
            "index": 0,
            "name": "Extrude1",
            "object_type": "adsk::fusion::ExtrudeFeature",
            "health_state": 0,
            "message": "",
        }
    ]
    return {
        "component_name": p.get("component_name") or "Root",
        "total": 1,
        "offset": offset,
        "features": features[offset : offset + limit],
        "next_offset": None,
    }


def _get_document_state(p: dict) -> dict:
    return {
        "document_id": "mock-document",
        "document_name": "MockDesign",
        "is_saved": False,
        "data_file_id": None,
        "project_name": None,
    }


def _create_design(p: dict) -> dict:
    name = p.get("name")
    if (
        not isinstance(name, str)
        or not name.strip()
        or not 1 <= len(name) <= 100
        or any(character in name for character in "/\\\r\n\t")
    ):
        return {
            "ok": False,
            "error_kind": "INVALID_INPUT",
            "error_message": "Use a bounded design name without path separators",
        }
    return {
        "document_id": "mock-new-document",
        "document_name": name,
        "is_saved": False,
        "data_file_id": None,
        "project_name": None,
    }


def _candidate_error(message):
    return {"ok": False, "error_kind": "INVALID_INPUT", "error_message": message}


def _draw_sketch_text(p):
    text = p.get("text", "")
    if (
        not all(
            math.isfinite(p.get(key, 0))
            for key in ("x", "y", "height", "width", "box_height")
        )
        or not isinstance(text, str)
        or not 1 <= len(text) <= 100
        or any(character in text for character in "'\\\r\n")
        or not p.get("sketch_name")
        or not 0.03 <= p.get("height", 0) <= 2
        or p.get("width", 0) <= 0
        or p.get("box_height", 0) < p.get("height", 0)
    ):
        return _candidate_error("Invalid literal text or text rectangle")
    return {
        "simulated": True,
        "sketch_name": p["sketch_name"],
        "text": text,
        "text_count": 1,
    }


def _extrude_sketch_entities(p):
    if (
        not math.isfinite(p.get("distance", 0))
        or p.get("entity_type") not in {"texts", "profiles"}
        or p.get("operation") not in {"cut", "join", "new_body"}
        or not 0 < abs(p.get("distance", 0)) <= 10
        or not p.get("sketch_name")
        or not p.get("feature_name")
    ):
        return _candidate_error("Invalid sketch extrusion arguments")
    return {
        "simulated": True,
        "feature_name": p["feature_name"],
        "entity_count": 1,
        "distance_cm": p["distance"],
        "health_state": 0,
        "message": "",
    }


def _get_body_topology(p):
    offset, limit = p.get("offset", 0), p.get("limit", 100)
    if (
        not p.get("body_name")
        or type(offset) is not int
        or offset < 0
        or type(limit) is not int
        or not 1 <= limit <= 200
    ):
        return _candidate_error("Invalid topology pagination or body")
    entity_type = p.get("entity_type", "edges")
    if entity_type not in {"edges", "faces"}:
        return _candidate_error("Unsupported topology entity type")
    if entity_type == "faces":
        faces = [
            {
                "index": index,
                "bounding_box": {"min": [0, 0, 0], "max": [1, 1, 0]},
                "area": 1.0,
                "surface_type": "mock-plane",
            }
            for index in range(6)
        ]
        return {
            "simulated": True, "body_name": p["body_name"],
            "entity_type": "faces", "edge_count": 12, "face_count": 6,
            "faces": faces[offset : offset + limit], "next_offset": None,
        }
    rows = [
        {
            "index": 0,
            "bounding_box": {"min": [0, 0, 0], "max": [1, 0, 0]},
            "face_indices": [0, 1],
        }
    ]
    return {
        "simulated": True,
        "body_name": p["body_name"],
        "edge_count": 1,
        "face_count": 2,
        "edges": rows[offset : offset + limit],
        "next_offset": None,
    }


def _chamfer_edges(p):
    edges, faces = p.get("edge_indices", []), p.get("reference_face_indices", [])
    if (
        not all(
            math.isfinite(p.get(key, 0)) for key in ("distance_one", "distance_two")
        )
        or not isinstance(edges, list)
        or not 1 <= len(edges) <= 200
        or any(type(index) is not int or index < 0 for index in edges)
        or len(set(edges)) != len(edges)
        or not isinstance(faces, list)
        or len(faces) != len(edges)
        or any(type(index) is not int or index < 0 for index in faces)
        or not p.get("body_name")
        or not p.get("feature_name")
        or p.get("distance_one", 0) <= 0
        or p.get("distance_two", 0) <= 0
    ):
        return _candidate_error("Invalid explicit-edge chamfer arguments")
    return {
        "simulated": True,
        "feature_name": p["feature_name"],
        "edge_count": len(edges),
        "health_state": 0,
        "message": "",
    }


def _save_design(p):
    if not p.get("document_id"):
        return _candidate_error("Document identity is required")
    if p.get("name"):
        if (
            bool(p.get("project_id")) == bool(p.get("project_name"))
            or not 1 <= len(p["name"]) <= 100
            or any(character in p["name"] for character in "/\\\r\n\t")
        ):
            return _candidate_error(
                "First save requires a bounded name and one project target"
            )
    elif p.get("project_id") or p.get("project_name"):
        return _candidate_error("Project target requires a first-save name")
    return {
        "simulated": True,
        "save_accepted": True,
        "metadata_pending": False,
        "document_id": p["document_id"],
        "document_name": p.get("name", "MockDesign"),
        "is_saved": True,
        "data_file_id": "mock-file",
        "project_name": p.get("project_name", "MockProject"),
    }


def _get_object_info(p: dict) -> dict:
    name = p.get("name", "Unknown")
    kind = p.get("entity_type", "auto")
    occurrence_path, component_name = (
        p.get("occurrence_path", ""),
        p.get("component_name", ""),
    )
    if (
        kind not in {"auto", "body", "sketch"}
        or (occurrence_path and component_name)
        or (kind == "sketch" and occurrence_path)
        or (kind == "body" and component_name)
    ):
        return _candidate_error("Invalid explicit object target")
    if kind == "sketch" or component_name:
        return {
            "found": True,
            "name": name,
            "type": "sketch",
            "is_visible": True,
            "profile_count": 1,
            "curve_count": 4,
        }
    return {
        "found": True,
        "name": name,
        "type": "body",
        "volume": 1,
        "area": 6,
        "material": None,
        "is_visible": True,
        "faces_count": 6,
        "edges_count": 12,
        "vertices_count": 8,
        "faces": 6,
        "edges": 12,
        "vertices": 8,
        "bounding_box": {"min": [0, 0, 0], "max": [1, 1, 1]},
    }


def _get_bounding_box(p: dict) -> dict:
    name = p.get("name", "Unknown")
    return {
        "found": True,
        "type": "body",
        "name": name,
        "min": [0.0, 0.0, 0.0],
        "max": [50.0, 30.0, 15.0],
        "size": [50.0, 30.0, 15.0],
        "center": [25.0, 15.0, 7.5],
    }


def _create_sketch(p: dict) -> dict:
    plane = p.get("plane", "xy")
    return {"sketch_name": f"Sketch_mock_{plane}", "plane": plane}


def _draw_rectangle(p: dict) -> dict:
    return {
        "sketch_name": "Sketch_mock_xy",
        "width": p.get("width", 1),
        "height": p.get("height", 1),
    }


def _draw_circle(p: dict) -> dict:
    return {"sketch_name": "Sketch_mock_xy", "radius": p.get("radius", 1)}


def _draw_line(p: dict) -> dict:
    return {
        "sketch_name": "Sketch_mock_xy",
        "start": [p.get("start_x", 0), p.get("start_y", 0)],
        "end": [p.get("end_x", 1), p.get("end_y", 1)],
    }


def _extrude(p: dict) -> dict:
    return {
        "body_name": "Body_mock",
        "height": p.get("height", 1),
        "operation": p.get("operation", "new_body"),
    }


def _revolve(p: dict) -> dict:
    return {
        "body_name": "Body_mock_revolve",
        "angle": p.get("angle", 360),
        "operation": p.get("operation", "new_body"),
    }


def _fillet(p: dict) -> dict:
    return {
        "simulated": True,
        "body_name": p.get("body_name", "Body1"),
        "radius": p.get("radius", 0.1),
        "edge_selection": p.get("edge_selection", "all"),
        "edge_indices": p.get("edge_indices"),
        "occurrence_path": p.get("occurrence_path", ""),
    }


def _chamfer(p: dict) -> dict:
    return {
        "simulated": True,
        "body_name": p.get("body_name", "Body1"),
        "distance": p.get("distance", 0.1),
        "edge_selection": p.get("edge_selection", "all"),
        "edge_indices": p.get("edge_indices"),
        "occurrence_path": p.get("occurrence_path", ""),
    }


def _shell(p: dict) -> dict:
    return {
        "simulated": True,
        "body_name": p.get("body_name", "Body1"),
        "thickness": p.get("thickness", 0.1),
        "face_selection": p.get("face_selection", "top"),
        "face_indices": p.get("face_indices"),
        "occurrence_path": p.get("occurrence_path", ""),
    }


def _mirror(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "mirror_plane": p.get("mirror_plane", "yz"),
        "occurrence_path": p.get("occurrence_path", ""),
        "new_body_name": "Body1_mirrored",
    }


def _rename_body(p: dict) -> dict:
    return {
        "renamed": True,
        "old_name": p.get("body_name", "Body1"),
        "new_name": p.get("new_name", "RenamedBody"),
    }


def _move_body(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "translation": [p.get("x", 0), p.get("y", 0), p.get("z", 0)],
    }


def _export_stl(p: dict) -> dict:
    name = p.get("body_name", "Body1")
    path = p.get("file_path", f"~/Desktop/{name}.stl")
    return {"body_name": name, "file_path": path}


def _boolean_operation(p: dict) -> dict:
    return {
        "target_body": p.get("target_body", "Body1"),
        "tool_body": p.get("tool_body", "Body2"),
        "operation": p.get("operation", "join"),
        "result_body": p.get("target_body", "Body1"),
    }


def _delete_all(_p: dict) -> dict:
    return {"deleted": True}


def _undo(_p: dict) -> dict:
    return {"undone": True, "design_type": 1}


def _execute_code(p: dict) -> dict:
    return {"executed": True, "code": p.get("code", ""), "result": "None", "output": ""}


# ── design type safety ───────────────────────────────────────────────


def _get_design_type(_p: dict) -> dict:
    return {"design_type": "parametric", "design_type_id": 1}


def _set_design_type(p: dict) -> dict:
    dt = p.get("design_type", "parametric")
    return {"changed": True, "design_type": dt}


# ── new geometry tools ────────────────────────────────────────────────


def _sweep(p: dict) -> dict:
    return {
        "body_name": "Body_mock_sweep",
        "path_sketch_name": p.get("path_sketch_name", "PathSketch"),
        "operation": p.get("operation", "new_body"),
    }


def _loft(p: dict) -> dict:
    return {
        "body_name": "Body_mock_loft",
        "profile_sketch_names": p.get("profile_sketch_names", []),
        "operation": p.get("operation", "new_body"),
    }


def _create_polygon(p: dict) -> dict:
    return {
        "sketch_name": "Sketch_mock_xy",
        "sides": p.get("sides", 6),
        "radius": p.get("radius", 1),
    }


def _draw_arc(p: dict) -> dict:
    return {
        "sketch_name": "Sketch_mock_xy",
        "center": [p.get("center_x", 0), p.get("center_y", 0)],
        "sweep_angle": p.get("sweep_angle", 90),
    }


def _create_hole(p: dict) -> dict:
    body = p.get("body_name") or f"Body{p.get('body_index', 0) + 1}"
    diameter = p.get("diameter", 0.5)
    return {
        "feature_name": "Hole_mock",
        "body_name": body,
        "diameter": diameter,
        "depth": p.get("depth", 1),
        "actual_diameter": diameter,
        "cut_bodies": [body],
        "resolved_center": [p.get("center_x", 0), p.get("center_y", 0), 0.0],
    }


def _rectangular_pattern(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "x_count": p.get("x_count", 1),
        "y_count": p.get("y_count", 1),
        "created_bodies": p.get("x_count", 1) * p.get("y_count", 1),
    }


def _circular_pattern(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "count": p.get("count", 3),
        "axis": p.get("axis", "z"),
        "total_angle": p.get("total_angle", 360),
    }


# ── assembly tools ────────────────────────────────────────────────────


def _create_component(p: dict) -> dict:
    return {
        "component_name": p.get("name", "Component1"),
        "parent": p.get("parent_name", "RootComponent"),
    }


def _add_joint(p: dict) -> dict:
    return {
        "component_one": p.get("component_one", "Comp1"),
        "component_two": p.get("component_two", "Comp2"),
        "joint_type": p.get("joint_type", "rigid"),
        "joint_name": "Joint_mock",
    }


def _list_components(_p: dict) -> dict:
    return {
        "components": [
            {"name": "RootComponent", "bodies": ["Body1"]},
            {"name": "SubComponent1", "bodies": []},
        ],
    }


# ── export tools ──────────────────────────────────────────────────────


def _export_step(p: dict) -> dict:
    name = p.get("body_name", "Body1")
    path = p.get("file_path", f"~/Desktop/{name}.step")
    if not isinstance(path, str) or not path.strip():
        return {
            "ok": False,
            "error_kind": "INVALID_INPUT",
            "error_message": "STEP destination must be a nonempty file path",
        }
    return {"exported": True, "body": name, "file_path": path, "simulated": True}


def _export_f3d(p: dict) -> dict:
    path = p.get("file_path", "~/Desktop/MockDesign.f3d")
    return {"file_path": path}


def _export_view_sheet(p: dict) -> dict:
    views = p.get("views") or ["iso", "front", "top", "right"]
    size = p.get("image_size") or [1200, 900]
    out = p.get("output_dir", "~/Desktop/MockDesign_views_mock")
    title = p.get("title", "MockDesign")
    return {
        "html_path": f"{out}/view_sheet.html",
        "output_dir": out,
        "title": title,
        "image_size": list(size),
        "views": [{"view": v, "path": f"{out}/{v}.png"} for v in views],
    }


def _export(p: dict) -> dict:
    fmt = (p.get("format") or "").lower()
    path = p.get("file_path", "")
    if not fmt and path:
        fmt = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    name = p.get("body_name", "Body1")
    return {
        "exported": True,
        "format": fmt or "f3d",
        "body": name,
        "file_path": path or f"~/Desktop/{name}.{fmt or 'f3d'}",
    }


def _import_mesh(p: dict) -> dict:
    path = p.get("file_path", "/tmp/mesh.stl")
    units = p.get("units", "mm")
    component = p.get("component_name") or "RootComponent"
    return {
        "imported": True,
        "file_path": path,
        "mesh_name": "MeshBody_mock",
        "component": component,
        "units": units,
        "bounding_box": {
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 5.0, 2.0],
            "size": [10.0, 5.0, 2.0],
        },
    }


def _create_box_parametric(p: dict) -> dict:
    return {
        "created": True,
        "body_name": p.get("body_name") or "BoxParametric_mock",
        "feature_name": "Extrude_mock",
        "sketch_name": "Sketch_mock",
        "length": p.get("length", 1),
        "width": p.get("width", 1),
        "height": p.get("height", 1),
        "origin": [
            p.get("origin_x", 0),
            p.get("origin_y", 0),
            p.get("origin_z", 0),
        ],
        "plane": p.get("plane", "xy"),
        "component": p.get("component_name") or "RootComponent",
    }


# ── parameter tools ───────────────────────────────────────────────────


def _get_parameters(_p: dict) -> dict:
    return {
        "parameters": [
            {"name": "width", "value": 10.0, "unit": "mm", "comment": ""},
            {"name": "height", "value": 5.0, "unit": "mm", "comment": ""},
        ],
    }


def _create_parameter(p: dict) -> dict:
    value = p.get("value", 0)
    # The addon trims the unit and treats blank as unitless; mirror both so
    # mock and real modes agree. "unit" is required by the schema, so the
    # default only covers a caller that omitted it entirely.
    unit = ("mm" if p.get("unit") is None else p["unit"]).strip()
    return {
        "created": True,
        "name": p.get("name", "param1"),
        "value": value,
        "unit": unit,
        "expression": f"{value} {unit}" if unit else f"{value}",
        "comment": p.get("comment", ""),
    }


def _set_parameter(p: dict) -> dict:
    # The real handler reports the unit the target parameter already declares
    # and the expression Fusion stored. Mock mode holds no design, so it
    # cannot know either -- report null rather than invent "mm".
    return {
        "updated": True,
        "name": p.get("name", "param1"),
        "value": p.get("value", 0),
        "unit": None,
        "expression": None,
    }


def _delete_parameter(p: dict) -> dict:
    return {"name": p.get("name", "param1"), "deleted": True}


# ── sketch constraints & dimensions ───────────────────────────────────


def _add_constraint(p: dict) -> dict:
    return {
        "constraint_type": p.get("constraint_type", "coincident"),
        "entity_one": p.get("entity_one", 0),
        "entity_two": p.get("entity_two", 1),
        "sketch_name": p.get("sketch_name", "Sketch1"),
    }


def _auto_constrain(p: dict) -> dict:
    return {
        "sketch": p.get("sketch_name", "Sketch1"),
        "is_fully_constrained": True,
        "constraints_added": 4,
        "dimensions_added": 2,
        "entities_moved": 0,
        "result_option": p.get("result_option", 1),
    }


def _add_dimension(p: dict) -> dict:
    return {
        "dimension_type": p.get("dimension_type", "distance"),
        "value": p.get("value", 1.0),
        "entity_one": p.get("entity_one", 0),
        "sketch_name": p.get("sketch_name", "Sketch1"),
    }


# ── construction geometry ─────────────────────────────────────────────


def _create_construction_plane(p: dict) -> dict:
    return {
        "plane_name": "ConstructionPlane_mock",
        "method": p.get("method", "offset"),
    }


def _create_construction_axis(p: dict) -> dict:
    return {
        "axis_name": "ConstructionAxis_mock",
        "method": p.get("method", "two_points"),
    }


# ── splines ───────────────────────────────────────────────────────────


def _draw_spline(p: dict) -> dict:
    return {
        "sketch_name": "Sketch_mock_xy",
        "spline_type": p.get("spline_type", "fit_points"),
        "point_count": len(p.get("points", [])),
    }


# ── sketch curve operations ──────────────────────────────────────────


def _offset_curve(p: dict) -> dict:
    return {
        "sketch_name": p.get("sketch_name", "Sketch1"),
        "offset_distance": p.get("offset_distance", 0.5),
        "new_curve_count": 4,
    }


def _trim_curve(p: dict) -> dict:
    return {
        "sketch_name": p.get("sketch_name", "Sketch1"),
        "curve_index": p.get("curve_index", 0),
        "trimmed": True,
    }


def _extend_curve(p: dict) -> dict:
    return {
        "sketch_name": p.get("sketch_name", "Sketch1"),
        "curve_index": p.get("curve_index", 0),
        "extended": True,
    }


# ── advanced features ─────────────────────────────────────────────────


def _create_thread(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "face_index": p.get("face_index", 0),
        "is_modeled": p.get("is_modeled", False),
        "thread_designation": p.get("thread_designation", "M10x1.5"),
    }


def _draft_faces(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "angle": p.get("angle", 5),
        "face_count": 4,
    }


def _split_body(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "result_bodies": ["Body1", "Body1_split"],
    }


def _split_face(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "faces_split": 2,
    }


def _offset_faces(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "distance": p.get("distance", 0.5),
    }


def _scale_body(p: dict) -> dict:
    allowed = {"body_name", "scale", "scale_x", "scale_y", "scale_z",
               "anchor_x", "anchor_y", "anchor_z"}
    if (
        set(p) - allowed or not isinstance(p.get("body_name"), str)
        or not p["body_name"]
    ):
        return _candidate_error("Scaling requires a named body and supported arguments")
    factors = [p.get(key) for key in ("scale_x", "scale_y", "scale_z")]
    nonuniform = any(value is not None for value in factors)
    if nonuniform and any(value is None for value in factors):
        return _candidate_error("Provide all three nonuniform scale factors")
    for value in [p.get("scale"), *(factors if nonuniform else [])]:
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            return _candidate_error("Scale factors must be finite and positive")
    for key in ("anchor_x", "anchor_y", "anchor_z"):
        value = p.get(key, 0)
        if type(value) not in (int, float) or not math.isfinite(value):
            return _candidate_error("Scale anchor must be finite")
    return {
        "body_name": p["body_name"],
        "scale": p["scale"],
        "feature_name": "Scale_mock",
        "simulated": True,
    }


# ── direct primitives ────────────────────────────────────────────────


def _create_box(p: dict) -> dict:
    return {
        "body_name": "Box_mock",
        "length": p.get("length", 1),
        "width": p.get("width", 1),
        "height": p.get("height", 1),
    }


def _create_cylinder(p: dict) -> dict:
    return {
        "body_name": "Cylinder_mock",
        "radius": p.get("radius", 1),
        "height": p.get("height", 1),
    }


def _create_sphere(p: dict) -> dict:
    return {
        "body_name": "Sphere_mock",
        "radius": p.get("radius", 1),
    }


def _create_torus(p: dict) -> dict:
    return {
        "body_name": "Torus_mock",
        "major_radius": p.get("major_radius", 2),
        "minor_radius": p.get("minor_radius", 0.5),
    }


# ── assembly (extended) ──────────────────────────────────────────────


def _create_as_built_joint(p: dict) -> dict:
    return {
        "component_one": p.get("component_one", "Comp1"),
        "component_two": p.get("component_two", "Comp2"),
        "joint_type": p.get("joint_type", "rigid"),
        "joint_name": "AsBuiltJoint_mock",
    }


def _create_rigid_group(p: dict) -> dict:
    return {
        "component_names": p.get("component_names", []),
        "rigid_group_name": "RigidGroup_mock",
    }


# ── inspection / analysis ────────────────────────────────────────────


def _measure_distance(p: dict) -> dict:
    return {
        "entity_one": p.get("entity_one", "Body1"),
        "entity_two": p.get("entity_two", "Body2"),
        "distance": 2.54,
        "point_one": [0, 0, 0],
        "point_two": [2.54, 0, 0],
    }


def _measure_angle(p: dict) -> dict:
    return {
        "entity_one": p.get("entity_one", "Face1"),
        "entity_two": p.get("entity_two", "Face2"),
        "angle_degrees": 90.0,
    }


def _get_physical_properties(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "mass": 0.785,
        "volume": 1.0,
        "area": 6.0,
        "density": 0.00785,
        "center_of_mass": [0.5, 0.5, 0.5],
    }


def _create_section_analysis(p: dict) -> dict:
    return {
        "plane": p.get("plane", "yz"),
        "offset": p.get("offset", 0),
        "analysis_name": "SectionAnalysis_mock",
    }


def _check_interference(p: dict) -> dict:
    return {
        "component_names": p.get("component_names", []),
        "interference_count": 0,
        "interferences": [],
    }


def _compare_meshes(p: dict) -> dict:
    return {
        "mesh_a": p.get("mesh_name_a", "Mesh1"),
        "mesh_b": p.get("mesh_name_b", "Mesh2"),
        "node_count": 1200,
        "min_deviation": -0.004,
        "max_deviation": 0.006,
        "mean_abs_deviation": 0.001,
        "rms_deviation": 0.0015,
        "max_abs_deviation": 0.006,
        "units": "cm",
    }


def _create_ucs(p: dict) -> dict:
    name = p.get("name", "UCS1")
    return {
        "name": name,
        "origin": [p.get("x", 0), p.get("y", 0), p.get("z", 0)],
        "angles_deg": [
            p.get("angle_x", 0),
            p.get("angle_y", 0),
            p.get("angle_z", 0),
        ],
        "reference_sketch": f"UCS_{name}_ref",
    }


def _set_color(p: dict) -> dict:
    r, g, b = p.get("red", 255), p.get("green", 0), p.get("blue", 0)
    alpha = round(p.get("opacity", 1.0) * 255)
    return {
        "body": p.get("body_name", "Body1"),
        "color": [r, g, b],
        "opacity": p.get("opacity", 1.0),
        "appearance": f"MCP_{r}_{g}_{b}_{alpha}",
    }


# ── appearance ────────────────────────────────────────────────────────


def _set_appearance(p: dict) -> dict:
    return {
        "target_name": p.get("target_name", "Body1"),
        "appearance_name": p.get("appearance_name", "Steel - Satin"),
        "applied": True,
    }


# ── project geometry ─────────────────────────────────────────────────


def _project_geometry(p: dict) -> dict:
    return {
        "source_name": p.get("source_name", "Body1"),
        "sketch_name": p.get("sketch_name", "Sketch1"),
        "projected_curves": 4,
    }


# ── timeline control ─────────────────────────────────────────────────


def _suppress_feature(p: dict) -> dict:
    return {
        "feature_name": p.get("feature_name", "Feature1"),
        "suppressed": True,
    }


def _unsuppress_feature(p: dict) -> dict:
    return {
        "feature_name": p.get("feature_name", "Feature1"),
        "suppressed": False,
    }


# ── surface operations ──────────────────────────────────────────────


def _patch_surface(p: dict) -> dict:
    return {
        "sketch_name": p.get("sketch_name", "Sketch1"),
        "body_name": "PatchSurface_mock",
        "continuity": p.get("continuity", "connected"),
    }


def _stitch_surfaces(p: dict) -> dict:
    return {
        "body_names": p.get("body_names", []),
        "result_body": "StitchedBody_mock",
        "tolerance": p.get("tolerance", 0.01),
    }


def _thicken_surface(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Surface1"),
        "thickness": p.get("thickness", 0.1),
        "result_body": "ThickenedBody_mock",
    }


def _ruled_surface(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Body1"),
        "edge_index": p.get("edge_index", 0),
        "distance": p.get("distance", 1.0),
        "result_body": "RuledSurface_mock",
    }


def _trim_surface(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "Surface1"),
        "tool_name": p.get("tool_name", "Tool1"),
        "trimmed": True,
    }


# ── sheet metal ─────────────────────────────────────────────────────


def _create_flange(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "SheetBody1"),
        "edge_index": p.get("edge_index", 0),
        "height": p.get("height", 1.0),
        "angle": p.get("angle", 90),
    }


def _create_bend(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "SheetBody1"),
        "angle": p.get("angle", 90),
        "bend_radius": p.get("bend_radius", 0.1),
    }


def _flat_pattern(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "SheetBody1"),
        "flat_pattern_name": "FlatPattern_mock",
    }


def _unfold(p: dict) -> dict:
    return {
        "body_name": p.get("body_name", "SheetBody1"),
        "bends_unfolded": len(p.get("bend_indices", [0, 1])),
    }


# ── CAM / manufacturing ─────────────────────────────────────────────


def _cam_create_setup(p: dict) -> dict:
    return {
        "setup_name": p.get("name", "Setup1"),
        "body_name": p.get("body_name", "Body1"),
        "operation_type": p.get("operation_type", "milling"),
        "stock_mode": p.get("stock_mode", "relative_box"),
    }


def _cam_create_operation(p: dict) -> dict:
    return {
        "setup_name": p.get("setup_name", "Setup1"),
        "operation_name": p.get("name", "Operation1"),
        "strategy": p.get("strategy", "2d_contour"),
        "tool_diameter": p.get("tool_diameter", 0.6),
    }


def _cam_generate_toolpath(p: dict) -> dict:
    return {
        "setup_name": p.get("setup_name", "Setup1"),
        "operation_name": p.get("operation_name"),
        "generated": True,
        "toolpath_count": 1,
    }


def _cam_post_process(p: dict) -> dict:
    setup = p.get("setup_name", "Setup1")
    post = p.get("post_processor", "fanuc")
    return {
        "setup_name": setup,
        "post_processor": post,
        "output_file": f"~/Desktop/{setup}.nc",
        "output_units": p.get("output_units", "mm"),
    }


def _cam_list_setups(_p: dict) -> dict:
    return {
        "setups": [
            {
                "name": "Setup1",
                "operation_type": "milling",
                "operation_count": 2,
            },
        ],
    }


def _cam_list_operations(p: dict) -> dict:
    return {
        "setup_name": p.get("setup_name", "Setup1"),
        "operations": [
            {
                "name": "Face1",
                "strategy": "face",
                "has_toolpath": True,
            },
            {
                "name": "2D Contour1",
                "strategy": "2d_contour",
                "has_toolpath": False,
            },
        ],
    }


def _cam_get_operation_info(p: dict) -> dict:
    return {
        "setup_name": p.get("setup_name", "Setup1"),
        "operation_name": p.get("operation_name", "Face1"),
        "strategy": "face",
        "tool_diameter": 0.6,
        "stepdown": 0.1,
        "feed_rate": 100.0,
        "spindle_speed": 10000,
        "has_toolpath": True,
        "toolpath_valid": True,
    }


# ── perception (viewport render) ─────────────────────────────────────

# 1x1 transparent PNG, enough to exercise the image-content code path.
_MOCK_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0l"
    "EQVR42mNkAAIAAAoAAv/lxKUAAAAASUVORK5CYII="
)


def _render_view(p: dict) -> dict:
    return {
        "view": p.get("view", "current"),
        "width": int(p.get("width", 1024)),
        "height": int(p.get("height", 768)),
        "image_format": "png",
        "image_base64": _MOCK_PNG_B64,
        "bytes": len(_MOCK_PNG_B64),
    }


# ── default fallback ─────────────────────────────────────────────────


def _default_mock(p: dict) -> dict:
    return {"warning": "no mock handler for this command", "params_received": p}


# ── dispatch table ────────────────────────────────────────────────────

_DISPATCH: dict[str, Any] = {
    "get_feature_health": _get_feature_health,
    "get_document_state": _get_document_state,
    "create_design": _create_design,
    "ping": _ping,
    "get_scene_info": _get_scene_info,
    "get_object_info": _get_object_info,
    "draw_sketch_text": _draw_sketch_text,
    "extrude_sketch_entities": _extrude_sketch_entities,
    "get_body_topology": _get_body_topology,
    "chamfer_edges": _chamfer_edges,
    "save_design": _save_design,
    "get_bounding_box": _get_bounding_box,
    "create_sketch": _create_sketch,
    "draw_rectangle": _draw_rectangle,
    "draw_circle": _draw_circle,
    "draw_line": _draw_line,
    "extrude": _extrude,
    "revolve": _revolve,
    "fillet": _fillet,
    "chamfer": _chamfer,
    "shell": _shell,
    "mirror": _mirror,
    "rename_body": _rename_body,
    "move_body": _move_body,
    "export_stl": _export_stl,
    "boolean_operation": _boolean_operation,
    "delete_all": _delete_all,
    "undo": _undo,
    "execute_code": _execute_code,
    "sweep": _sweep,
    "loft": _loft,
    "create_polygon": _create_polygon,
    "draw_arc": _draw_arc,
    "create_hole": _create_hole,
    "rectangular_pattern": _rectangular_pattern,
    "circular_pattern": _circular_pattern,
    "create_component": _create_component,
    "add_joint": _add_joint,
    "list_components": _list_components,
    "export_step": _export_step,
    "export_f3d": _export_f3d,
    "export_view_sheet": _export_view_sheet,
    "export": _export,
    "import_mesh": _import_mesh,
    "create_box_parametric": _create_box_parametric,
    "get_parameters": _get_parameters,
    "create_parameter": _create_parameter,
    "set_parameter": _set_parameter,
    "delete_parameter": _delete_parameter,
    # sketch constraints & dimensions
    "add_constraint": _add_constraint,
    "auto_constrain": _auto_constrain,
    "add_dimension": _add_dimension,
    # construction geometry
    "create_construction_plane": _create_construction_plane,
    "create_construction_axis": _create_construction_axis,
    # splines
    "draw_spline": _draw_spline,
    # sketch curve operations
    "offset_curve": _offset_curve,
    "trim_curve": _trim_curve,
    "extend_curve": _extend_curve,
    # advanced features
    "create_thread": _create_thread,
    "draft_faces": _draft_faces,
    "split_body": _split_body,
    "split_face": _split_face,
    "offset_faces": _offset_faces,
    "scale_body": _scale_body,
    # direct primitives
    "create_box": _create_box,
    "create_cylinder": _create_cylinder,
    "create_sphere": _create_sphere,
    "create_torus": _create_torus,
    # assembly (extended)
    "create_as_built_joint": _create_as_built_joint,
    "create_rigid_group": _create_rigid_group,
    # inspection / analysis
    "measure_distance": _measure_distance,
    "measure_angle": _measure_angle,
    "get_physical_properties": _get_physical_properties,
    "create_section_analysis": _create_section_analysis,
    "check_interference": _check_interference,
    "compare_meshes": _compare_meshes,
    "create_ucs": _create_ucs,
    "set_color": _set_color,
    # appearance
    "set_appearance": _set_appearance,
    # project geometry
    "project_geometry": _project_geometry,
    # timeline control
    "suppress_feature": _suppress_feature,
    "unsuppress_feature": _unsuppress_feature,
    # surface operations
    "patch_surface": _patch_surface,
    "stitch_surfaces": _stitch_surfaces,
    "thicken_surface": _thicken_surface,
    "ruled_surface": _ruled_surface,
    "trim_surface": _trim_surface,
    # sheet metal
    "create_flange": _create_flange,
    "create_bend": _create_bend,
    "flat_pattern": _flat_pattern,
    "unfold": _unfold,
    # CAM / manufacturing
    "cam_create_setup": _cam_create_setup,
    "cam_create_operation": _cam_create_operation,
    "cam_generate_toolpath": _cam_generate_toolpath,
    "cam_post_process": _cam_post_process,
    "cam_list_setups": _cam_list_setups,
    "cam_list_operations": _cam_list_operations,
    "cam_get_operation_info": _cam_get_operation_info,
    # design type safety
    "get_design_type": _get_design_type,
    "set_design_type": _set_design_type,
    # perception
    "render_view": _render_view,
}
