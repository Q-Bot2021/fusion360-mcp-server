"""Sandbox document lifecycle guards prevent unintended saves or opens."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from tests import test_mechanical_queries

queries = test_mechanical_queries.queries
Collection = test_mechanical_queries.Collection


@pytest.fixture
def app():
    project = SimpleNamespace(
        name="MCP_Dev",
        id="project-id",
        rootFolder=SimpleNamespace(dataFiles=Collection([])),
    )
    document = SimpleNamespace(
        isValid=True, isSaved=False, creationId="doc-id", name="Untitled"
    )
    return SimpleNamespace(
        activeDocument=document,
        data=SimpleNamespace(dataProjects=Collection([project])),
        documents=SimpleNamespace(open=Mock()),
    )


def test_create_separate_sandbox_design(queries, app):
    previous = app.activeDocument
    created = SimpleNamespace(
        isValid=True, isSaved=False, creationId="new-id", name="Untitled"
    )

    def add(document_type):
        assert document_type == 7
        app.activeDocument = created
        return created

    app.documents.add = Mock(side_effect=add)
    core = SimpleNamespace(DocumentTypes=SimpleNamespace(FusionDesignDocumentType=7))
    result = queries.create_design(app, "MCP_Stencil", lambda name: core)
    assert result["document_id"] == "new-id"
    assert created.name == "MCP_Stencil"
    assert previous.name == "Untitled" and previous.isSaved is False
    app.documents.add.assert_called_once_with(7)


@pytest.mark.parametrize("failed_document", [None, SimpleNamespace(isValid=False)])
def test_create_sandbox_reports_failed_creation_without_retry(
    queries, app, failed_document
):
    previous = app.activeDocument
    app.documents.add = Mock(return_value=failed_document)
    core = SimpleNamespace(DocumentTypes=SimpleNamespace(FusionDesignDocumentType=7))
    with pytest.raises(RuntimeError, match="inspect before retrying"):
        queries.create_design(app, "MCP_New", lambda name: core)
    app.documents.add.assert_called_once_with(7)
    assert app.activeDocument is previous


def test_create_sandbox_without_previous_document(queries, app):
    app.activeDocument = None
    created = SimpleNamespace(
        isValid=True, isSaved=False, creationId="new-id", name="Untitled"
    )

    def add(document_type):
        app.activeDocument = created
        return created

    app.documents.add = Mock(side_effect=add)
    core = SimpleNamespace(DocumentTypes=SimpleNamespace(FusionDesignDocumentType=7))
    result = queries.create_design(app, "MCP_New", lambda name: core)
    assert result["document_id"] == "new-id"
    assert result["is_saved"] is False and result["data_file_id"] is None


@pytest.mark.parametrize("name", ["", "   ", "bad/path", None])
def test_create_sandbox_rejects_invalid_name(queries, app, name):
    app.documents.add = Mock()
    with pytest.raises(ValueError):
        queries.create_design(app, name)
    app.documents.add.assert_not_called()


def test_create_design_has_no_project_or_fixture_name_dependency(queries, app):
    app.data = None
    created = SimpleNamespace(
        isValid=True, isSaved=False, creationId="new", name="Untitled"
    )

    def add(document_type):
        app.activeDocument = created
        return created

    app.documents.add = Mock(side_effect=add)
    core = SimpleNamespace(DocumentTypes=SimpleNamespace(FusionDesignDocumentType=7))
    result = queries.create_design(app, "Bracket", lambda name: core)
    assert result["document_name"] == "Bracket"


@pytest.mark.parametrize("count,slots,needed", [(10, 1, 1), (9, 3, 2), (8, 2, 0)])
def test_save_quota_diagnostic_measures_slots_without_saving(
    queries, app, count, slots, needed
):
    app.data.personalUseLimits = SimpleNamespace(
        isValid=True, editableFileCount=count, maxEditableFileCount=10
    )
    app.activeDocument.save = Mock()
    app.activeDocument.saveAs = Mock()
    result = queries.diagnose_document_save(
        SimpleNamespace(app=app), "doc-id", required_slots=slots
    )
    assert result["documents_to_make_read_only"] == needed
    assert result["available_slots"] == 10 - count
    expected_status = (
        "EDITABLE_DOCUMENT_LIMIT_REACHED" if count >= 10
        else "INSUFFICIENT_EDITABLE_DOCUMENT_SLOTS" if needed else "SLOTS_AVAILABLE"
    )
    assert result["status"] == expected_status
    assert result["save_failure_cause_confirmed"] is False
    assert bool(result["instructions"]) == bool(needed)
    app.activeDocument.save.assert_not_called()
    app.activeDocument.saveAs.assert_not_called()


def test_save_quota_diagnostic_other_license(queries, app):
    app.data.personalUseLimits = None
    result = queries.diagnose_document_save(SimpleNamespace(app=app), "doc-id")
    assert result["quota_applies"] is False
    assert result["status"] == "NOT_PERSONAL_USE"


@pytest.mark.parametrize("count,maximum", [(-1, 10), (0, 0), (True, 10)])
def test_save_quota_diagnostic_rejects_invalid_counts(queries, app, count, maximum):
    app.data.personalUseLimits = SimpleNamespace(
        isValid=True, editableFileCount=count, maxEditableFileCount=maximum
    )
    with pytest.raises(RuntimeError, match="invalid editable-document quota"):
        queries.diagnose_document_save(SimpleNamespace(app=app), "doc-id")


def test_save_quota_diagnostic_rejects_unavailable_quota(queries, app):
    app.data.personalUseLimits = SimpleNamespace(isValid=False)
    with pytest.raises(RuntimeError, match="quota information is invalid"):
        queries.diagnose_document_save(SimpleNamespace(app=app), "doc-id")


@pytest.mark.parametrize("slots", [0, 101, True, 1.5])
def test_save_quota_diagnostic_rejects_invalid_slots(queries, app, slots):
    with pytest.raises(ValueError, match="required_slots"):
        queries.diagnose_document_save(SimpleNamespace(app=app), "doc-id", slots)


def test_save_quota_diagnostic_rejects_stale_identity(queries, app):
    with pytest.raises(ValueError, match="identity"):
        queries.diagnose_document_save(SimpleNamespace(app=app), "stale")


def test_open_design_refuses_to_switch_from_unsaved_document(queries, app):
    app.data.findFileById = Mock()
    with pytest.raises(ValueError, match="Save the active document"):
        queries.open_design(app, "saved-design-id")
    app.data.findFileById.assert_not_called()
    app.documents.open.assert_not_called()


def test_open_design_activates_and_verifies_saved_file(queries, app):
    project = SimpleNamespace(name="MCP_Dev", id="project-id")
    source = SimpleNamespace(id="source-id")
    data_file = SimpleNamespace(
        id="target-id",
        fileExtension="f3d",
        isComplete=True,
        parentProject=project,
    )
    active = SimpleNamespace(
        isValid=True,
        isSaved=True,
        dataFile=source,
    )
    opened = SimpleNamespace(
        isValid=True,
        isSaved=True,
        creationId="target-document-id",
        name="DoorPart",
        dataFile=data_file,
    )
    app.activeDocument = active
    app.data = SimpleNamespace(findFileById=Mock(return_value=data_file))

    def open_file(file):
        assert file is data_file
        app.activeDocument = opened
        return opened

    app.documents.open = Mock(side_effect=open_file)

    result = queries.open_design(app, "target-id")

    assert result["document_id"] == "target-document-id"
    assert result["document_name"] == "DoorPart"
    assert result["data_file_id"] == "target-id"
    assert result["project_name"] == "MCP_Dev"
    assert "development_only" not in result
    app.documents.open.assert_called_once_with(data_file)


@pytest.mark.parametrize(
    "file_extension,is_complete",
    [("f2d", True), ("f3d", False)],
)
def test_open_design_rejects_unsupported_saved_file(
    queries, app, file_extension, is_complete
):
    app.activeDocument = SimpleNamespace(
        isValid=True,
        isSaved=True,
        dataFile=SimpleNamespace(id="source-id"),
    )
    app.data = SimpleNamespace(
        findFileById=Mock(return_value=SimpleNamespace(
            id="target-id",
            fileExtension=file_extension,
            isComplete=is_complete,
        ))
    )
    with pytest.raises(ValueError, match="complete saved Fusion design"):
        queries.open_design(app, "target-id")
    app.documents.open.assert_not_called()


def test_document_state_preserves_file_id_when_project_metadata_is_pending(queries):
    class DataFile:
        id = "saved-file-id"
        isComplete = True

        @property
        def parentProject(self):
            raise RuntimeError("InternalValidationError : res")

    document = SimpleNamespace(
        isValid=True,
        isSaved=True,
        creationId="saved-document-id",
        name="SavedPart",
        dataFile=DataFile(),
    )
    app = SimpleNamespace(activeDocument=document)

    state = queries.document_state(app)

    assert state["document_id"] == "saved-document-id"
    assert state["is_saved"] is True
    assert state["data_file_id"] is None
    assert state["project_name"] is None
    assert state["metadata_pending"] is True


def test_document_state_returns_cloud_identity_only_for_complete_file(queries):
    project = SimpleNamespace(name="MCP_Dev")
    data_file = SimpleNamespace(
        id="urn:adsk.wipprod:dm.lineage:part-id",
        isComplete=True,
        parentProject=project,
    )
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(
            isValid=True,
            isSaved=True,
            creationId="saved-document-id",
            name="SavedPart",
            dataFile=data_file,
        )
    )

    state = queries.document_state(app)

    assert state["data_file_id"] == data_file.id
    assert state["project_name"] == "MCP_Dev"
    assert state["metadata_pending"] is False


@pytest.mark.parametrize("nested", [False, True])
def test_insert_design_returns_referenced_occurrence_metadata(queries, app, nested):
    project = SimpleNamespace(id="project-id", name="MCP_Dev")
    active_file = SimpleNamespace(id="assembly-file", parentProject=project)
    part_file = SimpleNamespace(
        id="part-file",
        name="FramePart",
        fileExtension="f3d",
        versionNumber=3,
        parentProject=project,
    )
    app.activeDocument = SimpleNamespace(
        isValid=True,
        isSaved=True,
        dataFile=active_file,
    )
    app.data = SimpleNamespace(findFileById=Mock(return_value=part_file))
    transform = SimpleNamespace(
        asArray=lambda: [1, 0, 0, 2, 0, 1, 0, 3, 0, 0, 1, 4, 0, 0, 0, 1]
    )
    occurrence = SimpleNamespace(
        component=SimpleNamespace(name="FramePart", isLibraryItem=False),
        definition=SimpleNamespace(objectType="adsk::fusion::Component"),
        fullPathName="FramePart:1",
        name="FramePart:1",
        isGrounded=False,
        isReferencedComponent=True,
        isLightBulbOn=True,
        bRepBodies=SimpleNamespace(count=1),
        childOccurrences=SimpleNamespace(count=0),
        transform2=transform,
    )
    root = SimpleNamespace(
        name="Root",
        occurrences=SimpleNamespace(addByInsert=Mock(return_value=occurrence)),
    )
    parent = root
    if nested:
        class NestedOccurrence(SimpleNamespace):
            @property
            def isGrounded(self):
                raise RuntimeError("Nested grounding unavailable")

            @isGrounded.setter
            def isGrounded(self, value):
                raise RuntimeError("Nested grounding unavailable")

        attributes = vars(occurrence).copy()
        attributes.pop("isGrounded")
        attributes["fullPathName"] = "Hinge:1+FramePart:1"
        occurrence = NestedOccurrence(**attributes)
        parent = SimpleNamespace(
            name="Hinge",
            occurrences=SimpleNamespace(addByInsert=Mock(return_value=occurrence)),
        )
        parent_occurrence = SimpleNamespace(component=parent, fullPathName="Hinge:1")
        root.allOccurrences = [parent_occurrence]
        occurrence.createForAssemblyContext = Mock(return_value=occurrence)
    handler = SimpleNamespace(
        app=app, _root=lambda: root,
        _design=lambda: SimpleNamespace(allComponents=Collection([root, parent])),
    )
    matrix = SimpleNamespace()
    core = SimpleNamespace(
        Matrix3D=SimpleNamespace(create=Mock(return_value=matrix)),
        Vector3D=SimpleNamespace(create=lambda *values: values),
    )

    result = queries.insert_design(
        handler,
        "part-file",
        translation=[2, 3, 4],
        referenced=True,
        parent_component_name="Hinge" if nested else "",
        module_loader=lambda name: core,
    )

    parent.occurrences.addByInsert.assert_called_once_with(part_file, matrix, True)
    assert result["is_referenced"] is True
    assert result["path"] == ("Hinge:1+FramePart:1" if nested else "FramePart:1")
    assert result["body_count"] == 1
    assert result["transform"]["translation"] == [2, 3, 4]
    assert result["data_file_id"] == "part-file"
    if nested:
        with pytest.raises(ValueError, match="root-level"):
            queries.insert_design(
                handler, "part-file", parent_component_name="Hinge", grounded=True
            )
        parent.occurrences.addByInsert.assert_called_once()


def test_insert_design_referenced_requires_same_project_before_mutation(
    queries, app
):
    active_project = SimpleNamespace(id="project-one")
    other_project = SimpleNamespace(id="project-two")
    active_file = SimpleNamespace(id="active-file", parentProject=active_project)
    part_file = SimpleNamespace(
        id="part-file",
        fileExtension="f3d",
        parentProject=other_project,
    )
    app.activeDocument = SimpleNamespace(
        isValid=True, isSaved=True, dataFile=active_file
    )
    app.data = SimpleNamespace(findFileById=Mock(return_value=part_file))
    handler = SimpleNamespace(app=app)
    handler._root = Mock()

    with pytest.raises(ValueError, match="same project"):
        queries.insert_design(handler, "part-file", referenced=True)

    handler._root.assert_not_called()


def test_list_occurrences_reports_reference_and_library_flags(queries):
    component = SimpleNamespace(name="HingePart", isLibraryItem=True)
    occurrence = SimpleNamespace(
        component=component,
        definition=SimpleNamespace(objectType="adsk::fusion::Component"),
        fullPathName="UpperHinge:1+HingePart:1",
        name="HingePart:1",
        isGrounded=False,
        isReferencedComponent=True,
        isLightBulbOn=True,
        bRepBodies=Collection([object()]),
        childOccurrences=Collection([]),
        transform2=SimpleNamespace(
            asArray=lambda: [1, 0, 0, 2, 0, 1, 0, 3, 0, 0, 1, 4, 0, 0, 0, 1]
        ),
    )
    root = SimpleNamespace(allOccurrences=[occurrence])
    handler = SimpleNamespace(_root=lambda: root)

    result = queries.list_occurrences(handler)

    assert result["total"] == 1
    assert result["occurrences"][0]["path"] == "UpperHinge:1+HingePart:1"
    assert result["occurrences"][0]["is_referenced"] is True
    assert result["occurrences"][0]["is_library_item"] is True
    assert result["occurrences"][0]["body_count"] == 1
    assert result["occurrences"][0]["transform"]["translation"] == [2, 3, 4]
    assert result["occurrences"][0]["is_grounded"] is None
    assert result["occurrences"][0]["grounding_supported"] is False


@pytest.mark.parametrize("component_name", ["", "Part"])
def test_sketch_text_uses_literal_text_api(queries, component_name):
    text_input = Mock()
    text_input.setAsMultiLine.return_value = True
    texts = SimpleNamespace(
        createInput3=Mock(return_value=text_input),
        add=Mock(return_value=SimpleNamespace(text="DIA 10 mm")),
        count=1,
    )
    sketch = SimpleNamespace(name="Labels", sketchTexts=texts)
    component = SimpleNamespace(name="Part", sketches=Collection([sketch]))
    handler = SimpleNamespace(
        _root=lambda: component,
        _design=lambda: SimpleNamespace(allComponents=Collection([component])),
    )
    core = SimpleNamespace(
        ValueInput=SimpleNamespace(createByReal=lambda value: value),
        Point3D=SimpleNamespace(create=lambda *values: values),
        HorizontalAlignments=SimpleNamespace(LeftHorizontalAlignment=0),
        VerticalAlignments=SimpleNamespace(BottomVerticalAlignment=0),
    )
    result = queries.draw_sketch_text(
        handler,
        "Labels",
        "DIA 10 mm",
        1,
        2,
        0.15,
        1,
        0.3,
        lambda name: core,
        component_name=component_name,
    )
    assert result["text"] == "DIA 10 mm"
    texts.createInput3.assert_called_once_with("'DIA 10 mm'", 0.15)
    assert text_input.fontName == "Arial"
    text_input.setAsMultiLine.assert_called_once_with((1, 2, 0), (2, 2.3, 0), 0, 0, 0)


@pytest.mark.parametrize(
    "text,height", [("'bad'", 0.1), ("", 0.1), ("good", 0), ("good", float("nan"))]
)
def test_text_rejects_invalid_input_before_mutation(queries, text, height):
    handler = Mock()
    with pytest.raises(ValueError):
        queries.draw_sketch_text(handler, "Labels", text, 0, 0, height, 1, 1)
    handler._root.assert_not_called()


@pytest.mark.parametrize("component_name", ["", "Part"])
@pytest.mark.parametrize("entity_type", ["texts", "profiles"])
@pytest.mark.parametrize("distance", [-0.001, 0.001])
@pytest.mark.parametrize("operation", ["cut", "join", "new_body"])
def test_extrude_text_preserves_text_entities(
    queries, component_name, entity_type, distance, operation
):
    text = object()
    sketch = SimpleNamespace(
        name="Labels",
        sketchTexts=Collection([text]),
        profiles=Collection([text]),
        isVisible=True,
    )
    feature = SimpleNamespace(name="Extrude1", healthState=0, errorOrWarningMessage="")
    extrusion = Mock()
    extrudes = SimpleNamespace(
        createInput=Mock(return_value=extrusion), add=Mock(return_value=feature)
    )
    root = SimpleNamespace(
        name="Part",
        sketches=Collection([sketch]),
        features=SimpleNamespace(extrudeFeatures=extrudes),
    )
    handler = SimpleNamespace(
        _root=lambda: root,
        _operation_type=lambda operation: operation,
        _design=lambda: SimpleNamespace(allComponents=Collection([root])),
    )
    selected = []
    extent = object()
    core = SimpleNamespace(
        ObjectCollection=SimpleNamespace(
            create=lambda: SimpleNamespace(add=selected.append)
        ),
        ValueInput=SimpleNamespace(createByReal=lambda value: value),
    )
    directions = SimpleNamespace(
        PositiveExtentDirection=1,
        NegativeExtentDirection=2,
    )
    fusion = SimpleNamespace(
        DistanceExtentDefinition=SimpleNamespace(
            create=Mock(return_value=extent)
        ),
        ExtentDirections=directions,
    )
    result = queries.extrude_sketch_entities(
        handler,
        "Labels",
        entity_type,
        distance,
        operation,
        "Text_Engraving",
        lambda name: {"adsk.core": core, "adsk.fusion": fusion}[name],
        component_name=component_name,
    )
    assert selected == [text] and result["entity_count"] == 1
    fusion.DistanceExtentDefinition.create.assert_called_once_with(abs(distance))
    extrusion.setOneSideExtent.assert_called_once_with(
        extent, directions.NegativeExtentDirection if distance < 0
        else directions.PositiveExtentDirection
    )
    extrudes.createInput.assert_called_once_with(
        extrudes.createInput.call_args.args[0], operation
    )
    assert feature.name == "Text_Engraving" and sketch.isVisible is False


def test_as_built_joint_info_uses_validity_without_feature_health(queries):
    occurrence = SimpleNamespace(fullPathName="Frame:1")
    joint = SimpleNamespace(
        name="DoorHinge",
        jointMotion=SimpleNamespace(jointType=0),
        occurrenceOne=occurrence,
        occurrenceTwo=occurrence,
        isSuppressed=False,
        isValid=True,
    )

    result = queries.joint_info(SimpleNamespace(name="Root"), "as_built", joint)

    assert result["joint_type"] == "rigid"
    assert result["is_valid"] is True
    assert result["health_state"] is None
    assert result["message"] == ""


def test_component_selection_rejects_missing_and_ambiguous_names(queries):
    first = SimpleNamespace(name="Part")
    handler = SimpleNamespace(
        _design=lambda: SimpleNamespace(allComponents=Collection([first, first]))
    )
    for name in ("Part", "Missing"):
        with pytest.raises(ValueError, match="exactly one"):
            queries.sketch_component(handler, name)
    with pytest.raises(ValueError, match="string"):
        queries.sketch_component(handler, None)


def test_component_selection_returns_explicit_owner(queries):
    component = SimpleNamespace(name="Part")
    handler = SimpleNamespace(
        _design=lambda: SimpleNamespace(allComponents=Collection([component]))
    )
    assert queries.sketch_component(handler, "Part") is component


def test_sketch_owner_resolution_requires_exactly_one_component(queries):
    sketch = object()
    owner = SimpleNamespace(name="Part", sketches=Collection([sketch]))
    design = SimpleNamespace(allComponents=Collection([owner]))
    handler = SimpleNamespace(_design=lambda: design)
    assert queries is not None
    command_path = (
        Path(__file__).resolve().parents[1] / "addon/server/command_handler.py"
    )
    import ast

    tree = ast.parse(command_path.read_text(encoding="utf-8"))
    command_class = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                         and node.name == "CommandHandler")
    method = next(
        node for node in command_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_component_for_sketch"
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), str(command_path), "exec"),
        namespace,
    )
    assert namespace["_component_for_sketch"](handler, sketch) is owner
    design.allComponents = Collection(
        [owner, SimpleNamespace(name="Part2", sketches=Collection([sketch]))]
    )
    with pytest.raises(ValueError, match="missing or ambiguous"):
        namespace["_component_for_sketch"](handler, sketch)


def test_explicit_chamfer_uses_owner_and_validates_adjacency(queries):
    face = SimpleNamespace(nativeObject=None, identity="first")
    other_face = SimpleNamespace(nativeObject=None, identity="second")
    edge = SimpleNamespace(nativeObject=None, faces=Collection([face, other_face]))
    sets = SimpleNamespace(addTwoDistancesChamferEdgeSet=Mock(return_value=True))
    feature = SimpleNamespace(name="", healthState=0, errorOrWarningMessage="")
    chamfers = SimpleNamespace(
        createInput2=Mock(return_value=SimpleNamespace(chamferEdgeSets=sets)),
        add=Mock(return_value=feature),
    )
    owner = SimpleNamespace(features=SimpleNamespace(chamferFeatures=chamfers))
    body = SimpleNamespace(
        edges=Collection([edge]),
        faces=Collection([face, other_face]),
        isSolid=True,
        nativeObject=None,
        parentComponent=owner,
    )
    body.name = "Part"
    handler = SimpleNamespace(
        _root=lambda: SimpleNamespace(bRepBodies=Collection([body]), allOccurrences=[])
    )
    core = SimpleNamespace(
        ObjectCollection=SimpleNamespace(create=lambda: SimpleNamespace(add=Mock())),
        ValueInput=SimpleNamespace(createByReal=lambda value: value),
    )
    result = queries.chamfer_edges(
        handler, "Part", [0], [1], 0.1, 0.2, "Bevel", lambda name: core
    )
    assert result["edge_count"] == 1 and feature.name == "Bevel"
    assert sets.addTwoDistancesChamferEdgeSet.call_args.args[1:] == (
        0.1,
        0.2,
        False,
        False,
    )
    for edges, faces in (([1], [0]), ([0], [2]), ([0, 0], [0, 0]), ([0], [])):
        with pytest.raises(ValueError):
            queries.chamfer_edges(
                handler, "Part", edges, faces, 0.1, 0.2, "Bevel", lambda name: core
            )
    chamfers.add.assert_called_once()


def test_topology_query_pages_and_reports_adjacency(queries):
    first, second = object(), object()
    edge = SimpleNamespace(faces=Collection([first, second]), boundingBox="bounds")
    body = SimpleNamespace(edges=Collection([edge]), faces=Collection([first, second]))
    handler = SimpleNamespace(
        _root=lambda: SimpleNamespace(bRepBodies=Collection([body]), allOccurrences=[]),
        _bbox_dict=lambda bounds: bounds,
    )
    body.name = "Part"
    result = queries.get_body_topology(handler, "Part", limit=1)
    assert result["edges"] == [
        {"index": 0, "bounding_box": "bounds", "face_indices": [0, 1]}
    ]
    assert result["next_offset"] is None
    assert queries.get_body_topology(handler, "Part", offset=1)["edges"] == []
    with pytest.raises(ValueError):
        queries.get_body_topology(handler, "Part", limit=201)


def test_topology_query_returns_paginated_face_targets(queries):
    faces = [
        SimpleNamespace(
            boundingBox=f"bounds-{index}", area=index + 1,
            geometry=SimpleNamespace(objectType=f"surface-{index}"),
        )
        for index in range(3)
    ]
    body = SimpleNamespace(name="Part", faces=Collection(faces), edges=Collection([]))
    handler = SimpleNamespace(
        _root=lambda: SimpleNamespace(bRepBodies=Collection([body]), allOccurrences=[]),
        _bbox_dict=lambda bounds: bounds,
    )
    result = queries.get_body_topology(
        handler, "Part", entity_type="faces", offset=1, limit=1
    )
    assert result["entity_type"] == "faces"
    assert result["faces"] == [{
        "index": 1, "bounding_box": "bounds-1", "area": 2,
        "surface_type": "surface-1",
    }]
    assert result["next_offset"] == 2
    with pytest.raises(ValueError, match="pagination"):
        queries.get_body_topology(handler, "Part", entity_type="vertices")


def test_explicit_body_target_rejects_ambiguity_and_selects_occurrence(queries):
    body = SimpleNamespace(name="Part")
    proxy = SimpleNamespace(name="Part")
    occurrence = SimpleNamespace(
        fullPathName="Assembly:1+Part:2", bRepBodies=Collection([proxy])
    )
    root = SimpleNamespace(bRepBodies=Collection([body]), allOccurrences=[occurrence])
    handler = SimpleNamespace(_root=lambda: root)
    with pytest.raises(ValueError, match="unique"):
        queries.selected_body(handler, "Part")
    assert queries.selected_body(handler, "Part", "root") is body
    assert queries.selected_body(handler, "Part", occurrence.fullPathName) is proxy


def test_live_payload_reader_handles_actual_production_text_contract():
    from tests.test_sandbox_live import tool_payload

    result = SimpleNamespace(
        structuredContent=None,
        content=[
            SimpleNamespace(
                text=(
                    "**save_design** OK\n  save_accepted: True\n"
                    "  document_id: identity\n  is_saved: True\n  data_file_id: None"
                )
            )
        ],
    )
    assert tool_payload(result) == {
        "save_accepted": True,
        "document_id": "identity",
        "is_saved": True,
        "data_file_id": None,
    }


@pytest.mark.parametrize(
    "entity_type,distance,operation",
    [
        ("code", 1, "cut"),
        ("texts", 0, "cut"),
        ("texts", 1, "execute"),
        ("texts", float("inf"), "cut"),
    ],
)
def test_extrusion_rejects_invalid_input(queries, entity_type, distance, operation):
    handler = Mock()
    with pytest.raises(ValueError):
        queries.extrude_sketch_entities(
            handler, "Labels", entity_type, distance, operation, "Feature"
        )
    handler._root.assert_not_called()


def test_selective_30_degree_chamfer(queries):
    def point(x, y, z):
        return SimpleNamespace(x=x, y=y, z=z)

    def bounds(low, high):
        return SimpleNamespace(minPoint=point(*low), maxPoint=point(*high))
    face = SimpleNamespace(boundingBox=bounds((0, 0, 0.25), (10, 20, 0.25)))
    edge = SimpleNamespace(
        boundingBox=bounds((0, 0, 0.25), (0, 20, 0.25)), faces=Collection([face])
    )
    face.loops = Collection([SimpleNamespace(isOuter=True, edges=Collection([edge]))])
    body = SimpleNamespace(
        boundingBox=bounds((0, 0, 0), (10, 20, 0.25)), faces=Collection([face])
    )
    edge_sets = SimpleNamespace(addTwoDistancesChamferEdgeSet=Mock(return_value=True))
    feature = SimpleNamespace(
        name="Chamfer1", faces=Collection([]), healthState=0, errorOrWarningMessage=""
    )
    chamfers = SimpleNamespace(
        createInput2=lambda: SimpleNamespace(chamferEdgeSets=edge_sets),
        add=Mock(return_value=feature),
    )
    handler = SimpleNamespace(
        _body_by_name=lambda name: body,
        _root=lambda: SimpleNamespace(
            features=SimpleNamespace(chamferFeatures=chamfers)
        ),
    )
    selection = []
    core = SimpleNamespace(
        ObjectCollection=SimpleNamespace(
            create=lambda: SimpleNamespace(add=selection.append)
        ),
        ValueInput=SimpleNamespace(createByReal=lambda value: value),
    )
    result = queries.chamfer_stencil_edges(
        handler, "Stencil", "left", 0.25, 30, "Ruler_Bevel", lambda name: core
    )
    assert result["horizontal_width_cm"] == pytest.approx(0.4330127019)
    assert selection == [edge]
    arguments = edge_sets.addTwoDistancesChamferEdgeSet.call_args.args
    assert arguments[1:3] == pytest.approx((0.4330127019, 0.25))
    assert arguments[3:] == (True, False)
    assert result["edge_count"] == 1
    with pytest.raises(ValueError, match="No matching"):
        queries.chamfer_stencil_edges(
            handler, "Stencil", "internal", 0.01, 30, "Internal", lambda name: core
        )
    with pytest.raises(ValueError, match="thickness"):
        queries.chamfer_stencil_edges(
            handler, "Stencil", "left", 0.3, 30, "TooDeep", lambda name: core
        )


@pytest.mark.parametrize(
    "scope,depth,angle",
    [
        ("all", 0.01, 30),
        ("left", 0, 30),
        ("left", 0.01, 45),
        ("left", float("nan"), 30),
    ],
)
def test_chamfer_rejects_invalid_input(queries, scope, depth, angle):
    handler = Mock()
    with pytest.raises(ValueError):
        queries.chamfer_stencil_edges(handler, "Stencil", scope, depth, angle, "Bevel")
    handler._body_by_name.assert_not_called()


def test_save_unsaved_fixture_and_inspect_destination(queries, app):
    project = queries.sandbox_project(app)

    def save(name, folder, description, tag):
        assert folder is project.rootFolder
        app.activeDocument.isSaved = True
        app.activeDocument.name = name
        app.activeDocument.dataFile = SimpleNamespace(
            id="file-id", parentProject=project, isComplete=True
        )
        return True

    app.activeDocument.saveAs = save
    result = queries.save_sandbox_design(app, "doc-id", "MCP_FeatureFixture")
    assert result["project_name"] == "MCP_Dev" and result["is_saved"] is True


def test_generic_save_uses_explicit_project_without_fixture_names(queries, app):
    project = queries.sandbox_project(app)
    project.name = "Engineering"

    def save(name, folder, description, tag):
        assert name == "Bracket" and folder is project.rootFolder
        app.activeDocument.name = name
        app.activeDocument.isSaved = True
        app.activeDocument.dataFile = SimpleNamespace(
            id="file", parentProject=project, isComplete=True
        )
        return True

    app.activeDocument.saveAs = Mock(side_effect=save)
    result = queries.save_design(app, "doc-id", "Bracket", "project-id")
    assert result["save_accepted"] and result["project_name"] == "Engineering"
    assert "development_only" not in result


def test_generic_save_versions_existing_document_in_place(queries, app):
    document = app.activeDocument
    document.isSaved = True
    document.dataFile = SimpleNamespace(
        id="file", parentProject=queries.sandbox_project(app), isComplete=True
    )
    document.save = Mock(return_value=True)
    result = queries.save_design(app, "doc-id", description="Correction")
    assert result["save_accepted"]
    document.save.assert_called_once_with("Correction")
    with pytest.raises(ValueError, match="cannot rename"):
        queries.save_design(app, "doc-id", name="Replacement")
    document.save.assert_called_once()


def test_generic_save_rejects_stale_identity_and_missing_project(queries, app):
    app.activeDocument.saveAs = Mock()
    for identity, name, project_id in (
        ("wrong", "Bracket", "project-id"),
        ("doc-id", "Bracket", "missing"),
        ("doc-id", "Bracket", ""),
    ):
        with pytest.raises(ValueError):
            queries.save_design(app, identity, name, project_id)
    app.activeDocument.saveAs.assert_not_called()


def test_generic_save_metadata_pending_never_repeats_save(queries, app):
    class PendingFile:
        id = "pending"
        isComplete = True

        @property
        def parentProject(self):
            raise RuntimeError("metadata pending")

    def save(name, folder, description, tag):
        app.activeDocument.isSaved = True
        app.activeDocument.dataFile = PendingFile()
        return True

    app.activeDocument.saveAs = Mock(side_effect=save)
    result = queries.save_design(app, "doc-id", "Bracket", "project-id")
    assert result["save_accepted"] and result["metadata_pending"]
    assert result["requested_project_id"] == "project-id"
    app.activeDocument.saveAs.assert_called_once()


def test_generic_save_failed_api_result_does_not_claim_success(queries, app):
    app.activeDocument.saveAs = Mock(return_value=False)
    with pytest.raises(RuntimeError, match="Save failed"):
        queries.save_design(app, "doc-id", "Bracket", "project-id")
    app.activeDocument.saveAs.assert_called_once()


def test_generic_save_project_name_must_be_unique_and_exclusive(queries, app):
    app.activeDocument.saveAs = Mock(return_value=False)
    with pytest.raises(ValueError, match="exactly one"):
        queries.save_design(
            app, "doc-id", "Bracket", "project-id", project_name="MCP_Dev"
        )
    project = queries.sandbox_project(app)
    app.data.dataProjects = Collection([project, project])
    with pytest.raises(ValueError, match="one accessible"):
        queries.save_design(app, "doc-id", "Bracket", project_name="MCP_Dev")
    app.activeDocument.saveAs.assert_not_called()


def test_save_metadata_pending_does_not_report_failed_mutation(queries, app):
    class PendingFile:
        id = "pending-file"
        isComplete = True

        @property
        def parentProject(self):
            raise RuntimeError("InternalValidationError : res")

    def save(name, folder, description, tag):
        app.activeDocument.isSaved = True
        app.activeDocument.dataFile = PendingFile()
        return True

    app.activeDocument.saveAs = Mock(side_effect=save)
    result = queries.save_sandbox_design(app, "doc-id", "MCP_Test")
    assert result["save_accepted"] is True and result["metadata_pending"] is True
    assert result["requested_project"] == "MCP_Dev"
    assert "project_name" not in result
    app.activeDocument.saveAs.assert_called_once()


def test_failed_save_remains_a_failure(queries, app):
    app.activeDocument.saveAs = Mock(return_value=False)
    with pytest.raises(RuntimeError, match="Save failed"):
        queries.save_sandbox_design(app, "doc-id", "MCP_Test")


@pytest.mark.parametrize(
    "document_id,name",
    [
        ("other", "MCP_Test"),
        ("doc-id", "UserFile"),
        ("doc-id", "MCP_../bad"),
    ],
)
def test_invalid_save_does_not_mutate(queries, app, document_id, name):
    app.activeDocument.saveAs = Mock()
    with pytest.raises(ValueError):
        queries.save_sandbox_design(app, document_id, name)
    app.activeDocument.saveAs.assert_not_called()


def test_missing_project_and_saved_document_fail_closed(queries, app):
    app.data.dataProjects = Collection([])
    with pytest.raises(ValueError, match="exactly one"):
        queries.sandbox_project(app)
    app.activeDocument.isSaved = True
    app.activeDocument.dataFile = None
    with pytest.raises(ValueError, match="unsaved"):
        queries.save_sandbox_design(app, "doc-id", "MCP_Test")


def test_create_and_open_only_sandbox_drawing(queries, app):
    project = queries.sandbox_project(app)
    source = SimpleNamespace(
        id="source", parentProject=project, fileExtension="f3d", isComplete=True
    )
    app.activeDocument.isSaved = True
    app.activeDocument.dataFile = source
    created = SimpleNamespace(
        id="drawing", name="Drawing", parentProject=project, fileExtension="f2d"
    )
    manager = SimpleNamespace(
        createDrawingInput=Mock(return_value=object()),
        createDrawing=Mock(return_value=created),
    )
    api = SimpleNamespace(
        DrawingManager=SimpleNamespace(get=lambda: manager),
        DrawingCreationModes=SimpleNamespace(AutomaticDrawingCreationMode=0),
    )
    result = queries.create_sandbox_drawing(app, "doc-id", lambda name: api)
    assert result["data_file_id"] == "drawing"
    project.rootFolder.dataFiles = Collection([created])
    app.documents.open.return_value = app.activeDocument
    queries.open_sandbox_drawing(app, "drawing")
    app.documents.open.assert_called_once_with(created)
    with pytest.raises(ValueError):
        queries.open_sandbox_drawing(app, "foreign-file")


def test_drawing_creation_rejects_incomplete_source(queries, app):
    project = queries.sandbox_project(app)
    app.activeDocument.isSaved = True
    app.activeDocument.dataFile = SimpleNamespace(
        id="source", parentProject=project, fileExtension="f3d", isComplete=False
    )
    manager = Mock()
    api = SimpleNamespace(DrawingManager=SimpleNamespace(get=lambda: manager))
    with pytest.raises(ValueError, match="incomplete"):
        queries.create_sandbox_drawing(app, "doc-id", lambda name: api)
    manager.createDrawing.assert_not_called()


def test_sandbox_operations_through_mcp(queries, app, monkeypatch):
    import fusion360_mcp.server as server
    import tests.development_mcp as development

    path = Path(__file__).parent / "fusion_addins/Fusion360MCPDev/Fusion360MCPDev.py"
    spec = importlib.util.spec_from_file_location("_sandbox_protocol", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = module.DevelopmentHandler(SimpleNamespace(app=app), queries=queries)
    project = queries.sandbox_project(app)

    def save(name, folder, description, tag):
        app.activeDocument.isSaved = True
        app.activeDocument.name = name
        app.activeDocument.dataFile = SimpleNamespace(
            id="saved", parentProject=project, isComplete=True
        )
        return True

    app.activeDocument.saveAs = save

    def send(mode, name, params, **kwargs):
        if name == "save_sandbox_design":
            assert kwargs["mutation"] is True
        return handler.execute_command({"type": name, "params": params})["result"]

    monkeypatch.setattr(server, "_send", send)
    monkeypatch.setattr(development, "_send", send)

    async def check():
        instance = server.build_server(
            "socket",
            tool_list=development.development_list,
            tool_lookup=development.development_lookup,
            structured_results=True,
            extra_resources=development.candidate_resources(),
            extra_resource_reader=lambda uri: development.read_candidate_resource(
                uri, 9877
            ),
        )
        async with create_connected_server_and_client_session(instance) as session:
            before = await session.call_tool("get_document_state", {})
            assert before.structuredContent["document_id"] == "doc-id"
            invalid = await session.call_tool(
                "save_sandbox_design",
                {
                    "document_id": "foreign",
                    "name": "MCP_Test",
                },
            )
            assert invalid.isError and not app.activeDocument.isSaved
            saved = await session.call_tool(
                "save_sandbox_design",
                {
                    "document_id": "doc-id",
                    "name": "MCP_Test",
                },
            )
            assert (
                not saved.isError
                and saved.structuredContent["project_name"] == "MCP_Dev"
            )
            resource = await session.read_resource("fusion360://development/document")
            assert json.loads(resource.contents[0].text)["is_saved"] is True
            assert (
                await session.call_tool(
                    "create_sandbox_drawing",
                    {
                        "document_id": "doc-id",
                        "code": "not allowed",
                    },
                )
            ).isError

    anyio.run(check)
