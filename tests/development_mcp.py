"""Persistent CAD development profile, separate from the production CLI."""

import json

import anyio
import click
import mcp.types as types
from mcp.server.stdio import stdio_server

from fusion360_mcp.server import _send, build_server
from fusion360_mcp.tools import (
    DIRECT_TOOL_CALLS,
    TEXT_VISIBILITY_REVIEW,
    get_tool_by_name,
    get_tool_list,
)

RELOAD_CANDIDATES = {
    "name": "dev_reload_candidates",
    "title": "Development: Reload CAD Candidates",
    "description": "Reload fixed installed CAD handler modules; accepts no arguments",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "annotations": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
}


FEATURE_HEALTH = {
    "name": "get_feature_health",
    "title": "Development: Feature Health",
    "description": "Inspect paginated component feature names, types and health",
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "component_name": {"type": "string"},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
    },
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
}
DRAWING_INFO = {
    "name": "get_drawing_info",
    "title": "Development: Drawing Metadata",
    "description": "Inspect active drawing sheet metadata using preview API",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
}
RESOURCE_COMMANDS = {
    "fusion360://development/feature-health": "get_feature_health",
    "fusion360://development/drawing": "get_drawing_info",
    "fusion360://development/document": "get_document_state",
}

STENCIL_CANDIDATES = (
    get_tool_by_name("create_design"),
    {
        "name": "get_body_topology",
        "title": "Body Edge Topology",
        "description": (
            "Read paginated body edges, bounds and adjacent face indices. "
            "Indices are valid only for the current geometry. "
            + DIRECT_TOOL_CALLS
            + " "
            + TEXT_VISIBILITY_REVIEW
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["body_name"],
            "properties": {
                "body_name": {"type": "string"},
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
    {
        "name": "chamfer_edges",
        "title": "Chamfer Selected Edges",
        "description": (
            "Chamfer explicit solid-body edge indices with adjacent reference "
            "face indices and two distances in cm, in the body owner's frame. "
            "Indices refer to current topology and must be re-inspected after "
            "geometry edits. No tangent-chain propagation. "
            + DIRECT_TOOL_CALLS
            + " "
            + TEXT_VISIBILITY_REVIEW
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "body_name",
                "edge_indices",
                "reference_face_indices",
                "distance_one",
                "distance_two",
                "feature_name",
            ],
            "properties": {
                "body_name": {"type": "string"},
                "edge_indices": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 200,
                    "uniqueItems": True,
                    "items": {"type": "integer", "minimum": 0},
                },
                "reference_face_indices": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 200,
                    "items": {"type": "integer", "minimum": 0},
                },
                "distance_one": {"type": "number", "exclusiveMinimum": 0},
                "distance_two": {"type": "number", "exclusiveMinimum": 0},
                "feature_name": {"type": "string", "minLength": 1, "maxLength": 100},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    },
    {
        "name": "draw_sketch_text",
        "title": "Sketch Text",
        "description": (
            "Place bounded literal Arial text in a named sketch; coordinates "
            "and sizes in the selected sketch's local coordinates, in cm. "
            "Optional component_name uniquely selects the owning component; "
            "omitting it selects the root. "
            + DIRECT_TOOL_CALLS
            + " "
            + TEXT_VISIBILITY_REVIEW
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "sketch_name",
                "text",
                "x",
                "y",
                "height",
                "width",
                "box_height",
            ],
            "properties": {
                "sketch_name": {"type": "string"},
                "component_name": {"type": "string"},
                "text": {"type": "string", "minLength": 1, "maxLength": 100},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "height": {"type": "number", "minimum": 0.03, "maximum": 2},
                "width": {"type": "number", "exclusiveMinimum": 0},
                "box_height": {"type": "number", "exclusiveMinimum": 0},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "extrude_sketch_entities",
        "title": "Extrude Sketch Entities",
        "description": (
            "Create one extrusion from all texts or profiles in a named sketch; "
            "signed distance along the sketch normal in cm. Optional "
            "component_name selects its owning component; default root. "
            + DIRECT_TOOL_CALLS
            + " "
            + TEXT_VISIBILITY_REVIEW
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "sketch_name",
                "entity_type",
                "distance",
                "operation",
                "feature_name",
            ],
            "properties": {
                "sketch_name": {"type": "string"},
                "component_name": {"type": "string"},
                "entity_type": {"enum": ["texts", "profiles"]},
                "distance": {"type": "number", "minimum": -10, "maximum": 10},
                "operation": {"enum": ["cut", "new_body", "join"]},
                "feature_name": {"type": "string", "minLength": 1, "maxLength": 100},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    },
    {
        "name": "chamfer_stencil_edges",
        "title": "Development: Selective Stencil Bevel",
        "description": (
            "Chamfer top internal loops or one ruler side; explicit vertical "
            "depth cm and acute angle. "
            + DIRECT_TOOL_CALLS
            + " "
            + TEXT_VISIBILITY_REVIEW
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "body_name",
                "scope",
                "vertical_depth",
                "angle_degrees",
                "feature_name",
            ],
            "properties": {
                "body_name": {"type": "string"},
                "scope": {"enum": ["internal", "left", "right", "top", "bottom"]},
                "vertical_depth": {"type": "number", "exclusiveMinimum": 0},
                "angle_degrees": {"type": "number", "minimum": 10, "maximum": 30},
                "feature_name": {"type": "string", "minLength": 1, "maxLength": 100},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    },
)


DOCUMENT_CANDIDATES = (
    {
        "name": "save_design",
        "title": "Save Design",
        "description": (
            "Save the inspected active document. For first save provide name "
            "and either project_id or unique project_name; uses its root folder and "
            "rejects duplicate names. Existing document: omit both to save a "
            "new version in place. An accepted save can have pending metadata; "
            "query state, never repeat the save blindly. " + DIRECT_TOOL_CALLS
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["document_id"],
            "properties": {
                "document_id": {"type": "string", "minLength": 1},
                "name": {"type": "string", "maxLength": 100},
                "project_id": {"type": "string"},
                "project_name": {"type": "string"},
                "description": {"type": "string", "maxLength": 1000},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "get_document_state",
        "title": "Development: Document Identity",
        "description": "Inspect active document identity and saved project",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
    {
        "name": "save_sandbox_design",
        "title": "Development: Save New Sandbox Fixture",
        "description": "Save an inspected unsaved MCP_ fixture only in MCP_Dev",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["document_id", "name"],
            "properties": {
                "document_id": {"type": "string", "minLength": 1},
                "name": {"type": "string", "pattern": "^MCP_", "maxLength": 100},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "create_sandbox_drawing",
        "title": "Development: Create Sandbox Drawing",
        "description": "Preview drawing creation from inspected saved MCP_Dev design",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["document_id"],
            "properties": {
                "document_id": {"type": "string", "minLength": 1},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "open_sandbox_drawing",
        "title": "Development: Open Sandbox Drawing",
        "description": "Open only a drawing file in MCP_Dev root folder",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["data_file_id"],
            "properties": {
                "data_file_id": {"type": "string", "minLength": 1},
            },
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
)


STENCIL_CANDIDATES = tuple(
    get_tool_by_name(definition["name"]) or definition
    for definition in STENCIL_CANDIDATES
)


def _annotations(read_only: bool, idempotent: bool = False) -> dict:
    return {
        "readOnlyHint": read_only,
        "destructiveHint": False,
        "idempotentHint": read_only or idempotent,
    }


_PAGINATION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "offset": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
    },
}
_VECTOR = {
    "type": "array",
    "minItems": 3,
    "maxItems": 3,
    "items": {"type": "number"},
}
_PLACEMENT = {
    "translation": {
        **_VECTOR,
        "description": "Offset in cm in the parent component frame",
    },
    "rotation": {
        "type": "object",
        "additionalProperties": False,
        "required": ["axis", "angle_degrees"],
        "description": "Rotation about an axis through the parent origin",
        "properties": {"axis": _VECTOR, "angle_degrees": {"type": "number"}},
    },
    "grounded": {"type": "boolean"},
    "parent_component_name": {
        "type": "string",
        "description": "Unique owning component; omit for the root",
    },
}
_JOINT_GEOMETRY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["occurrence_path", "entity"],
    "description": (
        "Occurrence full path from list_occurrences (or root) and an entity: "
        "component origin, or a body face/edge index from get_body_topology "
        "with that occurrence_path. Planar faces use center; cylindrical or "
        "conical faces use start/middle/end; edges use any key point."
    ),
    "properties": {
        "occurrence_path": {"type": "string", "minLength": 1},
        "entity": {"enum": ["face", "edge", "origin"]},
        "body_name": {"type": "string", "minLength": 1},
        "index": {"type": "integer", "minimum": 0},
        "key_point": {"enum": ["start", "middle", "end", "center"]},
    },
}
_DIRECTION = {"enum": ["x", "y", "z"]}
_LIMITS = {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "items": {"type": "number"},
}
_MOTION_VALUES = {
    name: {"type": "number"}
    for name in (
        "rotation_degrees", "slide", "primary_slide", "secondary_slide",
        "pitch_degrees", "yaw_degrees", "roll_degrees",
    )
}
_JOINT_TYPES = [
    "rigid", "revolute", "slider", "cylindrical", "pin_slot", "planar", "ball",
]

ASSEMBLY_CANDIDATES = (
    {
        "name": "diagnose_document_save",
        "title": "Development: Diagnose Document Save",
        "description": (
            "Read Personal Use editable-document quota and calculate slots to free "
            "manually. Does not save or change editability. Quota evidence alone "
            "does not prove a previous save failed because of the limit."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["document_id"],
            "properties": {
                "document_id": {"type": "string", "minLength": 1},
                "required_slots": {
                    "type": "integer", "minimum": 1, "maximum": 100, "default": 1
                },
            },
        },
        "annotations": _annotations(True),
    },
    {
        "name": "open_design",
        "title": "Development: Open Saved Design",
        "description": (
            "Open a saved Fusion design by data_file_id. The active document "
            "must be saved before switching."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["data_file_id"],
            "properties": {"data_file_id": {"type": "string", "minLength": 1}},
        },
        "annotations": _annotations(False),
    },
    {
        "name": "list_occurrences",
        "title": "Development: List Occurrences",
        "description": (
            "Paginate all occurrences with full paths, components, grounding, "
            "external-reference and library/fastener flags, and transforms in cm"
        ),
        "inputSchema": _PAGINATION,
        "annotations": _annotations(True),
    },
    {
        "name": "add_occurrence",
        "title": "Development: Add Component Occurrence",
        "description": (
            "Place another occurrence of an existing uniquely named component "
            "in a parent component with explicit translation/rotation. "
            + DIRECT_TOOL_CALLS
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["component_name"],
            "properties": {
                "component_name": {"type": "string", "minLength": 1},
                **_PLACEMENT,
            },
        },
        "annotations": _annotations(False),
    },
    {
        "name": "insert_design",
        "title": "Development: Insert Saved Design",
        "description": (
            "Insert a saved Fusion design by data_file_id as an occurrence. "
            "Referenced inserts require the active document saved in the same "
            "project; embedded inserts copy the design. " + DIRECT_TOOL_CALLS
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["data_file_id"],
            "properties": {
                "data_file_id": {"type": "string", "minLength": 1},
                "parent_component_name": {"type": "string"},
                "referenced": {"type": "boolean"},
                **_PLACEMENT,
            },
        },
        "annotations": _annotations(False),
    },
    {
        "name": "set_design_intent",
        "title": "Development: Set Design Intent",
        "description": (
            "Preview API: set active design intent to part, assembly or hybrid; "
            "Fusion rejects unsupported transitions"
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["intent"],
            "properties": {"intent": {"enum": ["part", "assembly", "hybrid"]}},
        },
        "annotations": _annotations(False, idempotent=True),
    },
    {
        "name": "list_joints",
        "title": "Development: List Joints",
        "description": (
            "Paginate joints and as-built joints in all components with types, "
            "occurrences, motion values (degrees/cm), limits and health"
        ),
        "inputSchema": _PAGINATION,
        "annotations": _annotations(True),
    },
    {
        "name": "create_joint",
        "title": "Development: Create Joint",
        "description": (
            "Create a named rigid, revolute, slider, cylindrical, pin_slot, "
            "planar or ball joint in the root between explicit geometries of two "
            "occurrences. geometry_one's occurrence moves to geometry_two. "
            "Directions are joint-frame axes; omit for type defaults. Limits use "
            "degrees or cm. " + DIRECT_TOOL_CALLS
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["joint_name", "joint_type", "geometry_one", "geometry_two"],
            "properties": {
                "joint_name": {"type": "string", "minLength": 1, "maxLength": 100},
                "joint_type": {"enum": _JOINT_TYPES},
                "geometry_one": _JOINT_GEOMETRY,
                "geometry_two": _JOINT_GEOMETRY,
                "offset": {"type": "number"},
                "angle_degrees": {"type": "number"},
                "is_flipped": {"type": "boolean"},
                "rotation_axis": _DIRECTION,
                "slide_direction": _DIRECTION,
                "normal_direction": _DIRECTION,
                "pitch_direction": _DIRECTION,
                "yaw_direction": _DIRECTION,
                "rotation_limits_degrees": _LIMITS,
                "slide_limits": _LIMITS,
            },
        },
        "annotations": _annotations(False),
    },
    {
        "name": "drive_joint",
        "title": "Development: Drive Joint",
        "description": (
            "Set one named joint's motion values (degrees or cm) within enabled "
            "limits and return resulting occurrence transforms. Fields depend on "
            "joint type. " + DIRECT_TOOL_CALLS
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["joint_name", "values"],
            "properties": {
                "joint_name": {"type": "string", "minLength": 1},
                "values": {
                    "type": "object",
                    "additionalProperties": False,
                    "minProperties": 1,
                    "properties": _MOTION_VALUES,
                },
            },
        },
        "annotations": _annotations(False, idempotent=True),
    },
    {
        "name": "animate_joint",
        "title": "Development: Animate Joint",
        "description": (
            "Step one joint motion field through 2-24 values, capturing a PNG "
            "viewport frame per step into a new temporary directory, then "
            "restore the initial value by default. Returns frame paths and "
            "actual values."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["joint_name", "field", "values"],
            "properties": {
                "joint_name": {"type": "string", "minLength": 1},
                "field": {"enum": list(_MOTION_VALUES)},
                "values": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 24,
                    "items": {"type": "number"},
                },
                "view": {
                    "enum": [
                        "current", "iso", "front", "back", "top", "bottom",
                        "left", "right",
                    ],
                },
                "width": {"type": "integer", "minimum": 64, "maximum": 1600},
                "height": {"type": "integer", "minimum": 64, "maximum": 1600},
                "restore": {"type": "boolean"},
            },
        },
        "annotations": _annotations(False, idempotent=True),
    },
)
DOCUMENT_CANDIDATES = tuple(
    get_tool_by_name(definition["name"]) or definition
    for definition in DOCUMENT_CANDIDATES
)


def candidate_resources() -> tuple[types.Resource, ...]:
    return tuple(
        types.Resource(
            uri=uri,
            name=command,
            mimeType="application/json",
            description="Development-only inspection; live acceptance pending",
        )
        for uri, command in RESOURCE_COMMANDS.items()
    )


def read_candidate_resource(uri: str, port: int) -> str:
    result = _send("socket", RESOURCE_COMMANDS[uri], {}, host="127.0.0.1", port=port)
    if result.get("ok") is False:
        raise ValueError(result.get("error_message", "Candidate query failed"))
    return json.dumps(result)


def development_lookup(name: str) -> dict | None:
    for definition in (
        FEATURE_HEALTH,
        DRAWING_INFO,
        *DOCUMENT_CANDIDATES,
        *STENCIL_CANDIDATES,
        *ASSEMBLY_CANDIDATES,
    ):
        if name == definition["name"]:
            return get_tool_by_name(name) or definition
    if name == RELOAD_CANDIDATES["name"]:
        return RELOAD_CANDIDATES
    return get_tool_by_name(name)


def development_list() -> list[types.Tool]:
    return [
        *get_tool_list(),
        *(
            types.Tool(**definition)
            for definition in (
                RELOAD_CANDIDATES,
                FEATURE_HEALTH,
                DRAWING_INFO,
                *DOCUMENT_CANDIDATES,
                *STENCIL_CANDIDATES,
                *ASSEMBLY_CANDIDATES,
            )
            if get_tool_by_name(definition["name"]) is None
        ),
    ]


@click.command()
@click.option("--port", type=click.IntRange(1, 65535), default=9877)
def main(port: int) -> None:
    app = build_server(
        "socket",
        host="127.0.0.1",
        port=port,
        tool_list=development_list,
        tool_lookup=development_lookup,
        structured_results=True,
        extra_resources=candidate_resources(),
        extra_resource_reader=lambda uri: read_candidate_resource(uri, port),
    )

    async def run():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    anyio.run(run)


if __name__ == "__main__":
    main()
