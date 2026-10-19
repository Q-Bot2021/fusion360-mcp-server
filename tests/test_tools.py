"""Tests for the tool registry."""

from fusion360_mcp.tools import (
    DISABLED_COMMANDS,
    TOOLS,
    get_tool_by_name,
    get_tool_list,
)


def test_license_gated_tool_documents_entitlement_without_disabling_users():
    tool = get_tool_by_name("auto_constrain")
    assert tool is not None
    assert "License-gated" in tool["description"]
    assert "eligible licensed users" in tool["description"]
    assert "Exact subscription tier" in tool["description"]
    assert "auto_constrain" not in DISABLED_COMMANDS


def test_all_tools_have_required_keys():
    for t in TOOLS:
        assert "name" in t, f"Tool missing 'name': {t}"
        assert "title" in t, f"Tool {t['name']} missing 'title'"
        assert "description" in t, f"Tool {t['name']} missing 'description'"
        assert "inputSchema" in t, f"Tool {t['name']} missing 'inputSchema'"


def test_all_schemas_are_objects():
    for t in TOOLS:
        schema = t["inputSchema"]
        assert schema.get("type") == "object", (
            f"Tool {t['name']} schema type is not 'object'"
        )


def test_required_fields_exist_in_properties():
    """Every field listed in 'required' must also appear in 'properties'."""
    for t in TOOLS:
        schema = t["inputSchema"]
        required = schema.get("required", [])
        props = schema.get("properties", {})
        for field in required:
            assert field in props, (
                f"Tool {t['name']}: required field '{field}' "
                f"not in properties {list(props)}"
            )


def test_no_duplicate_tool_names():
    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names)), (
        f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"
    )


def test_get_tool_list_returns_mcp_types():
    tools = get_tool_list()
    assert len(tools) == len(TOOLS) - len(DISABLED_COMMANDS)
    for tool in tools:
        assert hasattr(tool, "name")
        assert hasattr(tool, "inputSchema")


def test_get_tool_by_name_found():
    assert get_tool_by_name("ping") is not None
    assert get_tool_by_name("extrude") is not None


def test_get_tool_by_name_missing():
    assert get_tool_by_name("nonexistent_tool") is None


def test_execute_code_retained_but_unavailable():
    assert any(tool["name"] == "execute_code" for tool in TOOLS)
    assert get_tool_by_name("execute_code") is None
    assert "execute_code" not in {tool.name for tool in get_tool_list()}


def test_expected_tools_present():
    """Verify the full set of commands we expect."""
    names = {t["name"] for t in TOOLS}
    expected = {
        # scene / query
        "get_scene_info",
        "get_feature_health",
        "get_document_state",
        "create_design",
        "draw_sketch_text",
        "extrude_sketch_entities",
        "get_body_topology",
        "chamfer_edges",
        "save_design",
        "get_object_info",
        "get_bounding_box",
        # sketch
        "create_sketch",
        "draw_rectangle",
        "draw_circle",
        "draw_line",
        # features
        "extrude",
        "revolve",
        "fillet",
        "chamfer",
        "shell",
        "mirror",
        # body ops
        "move_body",
        "export_stl",
        "boolean_operation",
        # scene control
        "delete_all",
        "undo",
        # code execution
        "execute_code",
        # health
        "ping",
        # new geometry
        "sweep",
        "loft",
        "create_polygon",
        "draw_arc",
        "create_hole",
        "rectangular_pattern",
        "circular_pattern",
        # assembly
        "create_component",
        "add_joint",
        "list_components",
        # export
        "export_step",
        "export_f3d",
        "export_view_sheet",
        "export",
        # import
        "import_mesh",
        # parameters
        "get_parameters",
        "create_parameter",
        "set_parameter",
        "delete_parameter",
        # sketch constraints & dimensions
        "add_constraint",
        "auto_constrain",
        "add_dimension",
        # construction geometry
        "create_construction_plane",
        "create_construction_axis",
        "create_ucs",
        # splines
        "draw_spline",
        # sketch curve operations
        "offset_curve",
        "trim_curve",
        "extend_curve",
        # advanced features
        "create_thread",
        "draft_faces",
        "split_body",
        "split_face",
        "offset_faces",
        "scale_body",
        # direct primitives
        "create_box",
        "create_cylinder",
        "create_sphere",
        "create_torus",
        "create_box_parametric",
        # assembly (extended)
        "create_as_built_joint",
        "open_design",
        "insert_design",
        "list_occurrences",
        "create_rigid_group",
        # inspection / analysis
        "measure_distance",
        "measure_angle",
        "get_physical_properties",
        "create_section_analysis",
        "check_interference",
        "compare_meshes",
        # appearance
        "set_appearance",
        "set_color",
        # project geometry
        "project_geometry",
        # timeline control
        "suppress_feature",
        "unsuppress_feature",
        # surface operations
        "patch_surface",
        "stitch_surfaces",
        "thicken_surface",
        "ruled_surface",
        "trim_surface",
        # sheet metal
        "create_flange",
        "create_bend",
        "flat_pattern",
        "unfold",
        # CAM / manufacturing
        "cam_create_setup",
        "cam_create_operation",
        "cam_generate_toolpath",
        "cam_post_process",
        "cam_list_setups",
        "cam_list_operations",
        "cam_get_operation_info",
        # design type safety
        "get_design_type",
        "set_design_type",
        # utility
        "rename_body",
        # perception
        "render_view",
    }
    missing = expected - names
    assert not missing, f"Missing tools: {missing}"
    extra = names - expected
    assert not extra, f"Unexpected tools: {extra}"


def test_as_built_joint_schema_exposes_explicit_motion_directions():
    properties = get_tool_by_name("create_as_built_joint")["inputSchema"][
        "properties"
    ]
    assert properties["joint_name"]["maxLength"] == 100
    for field in (
        "rotation_axis",
        "slide_direction",
        "normal_direction",
        "pitch_direction",
        "yaw_direction",
    ):
        assert properties[field]["enum"] == ["x", "y", "z"]


def test_interference_schema_has_explicit_occurrence_scope():
    properties = get_tool_by_name("check_interference")["inputSchema"][
        "properties"
    ]
    assert properties["cross_occurrence_only"]["default"] is False


def test_all_tools_have_annotations():
    """Every tool should have annotations after module load."""
    for t in TOOLS:
        ann = t.get("annotations")
        assert ann is not None, f"Tool {t['name']} missing annotations"
        for key in ("readOnlyHint", "destructiveHint", "idempotentHint"):
            assert key in ann, f"Tool {t['name']} missing annotation '{key}'"
            assert isinstance(ann[key], bool), f"Tool {t['name']}.{key} should be bool"


def test_property_types_are_valid():
    """Every property in every schema should have a valid JSON Schema type."""
    valid_types = {"string", "number", "integer", "boolean", "array", "object"}
    for t in TOOLS:
        props = t["inputSchema"].get("properties", {})
        for field, spec in props.items():
            if "type" in spec:
                assert spec["type"] in valid_types, (
                    f"Tool {t['name']}.{field}: invalid type '{spec['type']}'"
                )


def test_enum_fields_are_lists():
    """Every 'enum' in a property should be a non-empty list."""
    for t in TOOLS:
        props = t["inputSchema"].get("properties", {})
        for field, spec in props.items():
            if "enum" in spec:
                assert isinstance(spec["enum"], list), (
                    f"Tool {t['name']}.{field}: enum not a list"
                )
                assert len(spec["enum"]) > 0, f"Tool {t['name']}.{field}: enum is empty"


def test_minimum_less_than_maximum():
    """If both min and max are set, min should be < max."""
    for t in TOOLS:
        props = t["inputSchema"].get("properties", {})
        for field, spec in props.items():
            if "minimum" in spec and "maximum" in spec:
                assert spec["minimum"] < spec["maximum"], (
                    f"Tool {t['name']}.{field}: "
                    f"min ({spec['minimum']}) >= max ({spec['maximum']})"
                )


def test_descriptions_are_nonempty():
    """Every tool should have a non-empty description."""
    for t in TOOLS:
        assert len(t["description"].strip()) > 0, (
            f"Tool {t['name']} has empty description"
        )
        assert len(t["title"].strip()) > 0, f"Tool {t['name']} has empty title"


def test_tool_names_are_snake_case():
    """Tool names should be snake_case."""
    import re

    for t in TOOLS:
        assert re.match(r"^[a-z][a-z0-9_]*$", t["name"]), (
            f"Tool name '{t['name']}' is not snake_case"
        )


def test_get_tool_list_annotations_propagated():
    """MCP Tool objects should carry annotations."""
    tools = get_tool_list()
    for tool in tools:
        assert tool.annotations is not None, f"MCP Tool {tool.name} missing annotations"


def test_get_tool_by_name_returns_correct_tool():
    """get_tool_by_name should return the exact matching tool."""
    for t in TOOLS:
        found = get_tool_by_name(t["name"])
        if t["name"] in DISABLED_COMMANDS:
            assert found is None
            continue
        assert found is t, f"get_tool_by_name('{t['name']}') returned wrong object"


def test_get_tool_by_name_edge_cases():
    assert get_tool_by_name("") is None
    assert get_tool_by_name("PING") is None  # case sensitive
    assert get_tool_by_name("ping ") is None  # trailing space
