"""Bounded read-only mechanical/drawing candidates, not production registration."""

import importlib
import math


def feature_health(
    design, component_name: str = "", offset: int = 0, limit: int = 100
) -> dict:
    if (
        not isinstance(component_name, str)
        or type(offset) is not int
        or type(limit) is not int
        or offset < 0
        or not 1 <= limit <= 200
    ):
        raise ValueError("Invalid feature query pagination or component name")
    component = design.rootComponent
    if component_name:
        matches = [
            design.allComponents.item(index)
            for index in range(design.allComponents.count)
            if design.allComponents.item(index).name == component_name
        ]
        if len(matches) != 1:
            raise ValueError("Component name must identify exactly one component")
        component = matches[0]
    features = component.features
    rows = []
    for index in range(offset, min(offset + limit, features.count)):
        feature = features.item(index)
        rows.append(
            {
                "index": index,
                "name": feature.name,
                "object_type": feature.objectType,
                "health_state": int(feature.healthState),
                "message": feature.errorOrWarningMessage,
            }
        )
    return {
        "ok": True,
        "development_only": True,
        "component_name": component.name,
        "total": features.count,
        "offset": offset,
        "features": rows,
        "next_offset": offset + len(rows)
        if offset + len(rows) < features.count
        else None,
    }


def drawing_info(app, module_loader=importlib.import_module) -> dict:
    drawing_api = module_loader("adsk.drawing")
    drawing = drawing_api.Drawing.cast(app.activeProduct)
    if drawing is None:
        raise ValueError("Activate a drawing document to inspect its active sheet")
    document = app.activeDocument
    if document is None or not document.isValid or not drawing.isValid:
        raise ValueError("Drawing document is not valid")
    sheet = drawing.activeSheet
    return {
        "ok": True,
        "development_only": True,
        "preview_api": True,
        "document_name": document.name,
        "document_id": document.creationId,
        "active_sheet_name": sheet.name if sheet is not None else None,
        "object_type": drawing.objectType,
    }


def sandbox_project(app):
    projects = app.data.dataProjects
    matches = [
        projects.item(index)
        for index in range(projects.count)
        if projects.item(index).name == "MCP_Dev"
    ]
    if len(matches) != 1:
        raise ValueError("MCP_Dev must identify exactly one accessible project")
    return matches[0]


def document_state(app) -> dict:
    document = app.activeDocument
    if document is None or not document.isValid:
        raise ValueError("No valid active document")
    data_file = document.dataFile if document.isSaved else None
    return {
        "ok": True,
        "development_only": True,
        "document_id": document.creationId,
        "document_name": document.name,
        "is_saved": document.isSaved,
        "data_file_id": data_file.id if data_file else None,
        "project_name": data_file.parentProject.name if data_file else None,
    }


def create_design(app, name: str, module_loader=importlib.import_module) -> dict:
    if (
        not isinstance(name, str)
        or not name.strip()
        or not 1 <= len(name) <= 100
        or any(character in name for character in "/\\\r\n\t")
    ):
        raise ValueError("Use a bounded design name without path separators")
    core = module_loader("adsk.core")
    document = app.documents.add(core.DocumentTypes.FusionDesignDocumentType)
    if document is None or not document.isValid:
        raise RuntimeError("Document creation failed; inspect before retrying")
    document.name = name
    return document_state(app)


def save_design(
    app, document_id, name="", project_id="", description="", project_name=""
):
    if (
        not isinstance(document_id, str)
        or not document_id
        or any(
            not isinstance(value, str)
            for value in (name, project_id, description, project_name)
        )
        or len(description) > 1000
    ):
        raise ValueError("Invalid document save identity or arguments")
    document = app.activeDocument
    if document is None or not document.isValid or document.creationId != document_id:
        raise ValueError("Save requires the inspected active document identity")
    requested = {"document_id": document_id}
    if document.isSaved:
        if name or project_id or project_name:
            raise ValueError(
                "Existing document saves cannot rename or change destination"
            )
        accepted = document.save(description)
    else:
        if (
            not 1 <= len(name) <= 100
            or any(character in name for character in "/\\\r\n\t")
            or bool(project_id) == bool(project_name)
        ):
            raise ValueError(
                "First save requires a bounded name and exactly one project ID or name"
            )
        projects = app.data.dataProjects
        matches = [
            projects.item(index)
            for index in range(projects.count)
            if (
                projects.item(index).id == project_id
                if project_id
                else projects.item(index).name == project_name
            )
        ]
        if len(matches) != 1:
            raise ValueError("Project target must identify one accessible project")
        project = matches[0]
        files = project.rootFolder.dataFiles
        if any(files.item(index).name == name for index in range(files.count)):
            raise ValueError("Save destination name already exists")
        requested.update(
            requested_name=name,
            requested_project=project.name,
            requested_project_id=project.id,
        )
        accepted = document.saveAs(name, project.rootFolder, description, "")
    if not accepted:
        raise RuntimeError("Save failed; inspect cloud state before retrying")
    try:
        state = document_state(app)
        state.pop("development_only", None)
    except RuntimeError as exc:
        return {
            "ok": True,
            "save_accepted": True,
            "metadata_pending": True,
            "readback_error": str(exc),
            **requested,
        }
    return {**state, "save_accepted": True, "metadata_pending": False}


def save_sandbox_design(app, document_id: str, name: str) -> dict:
    if (
        not isinstance(document_id, str)
        or not isinstance(name, str)
        or not name.startswith("MCP_")
        or not 4 < len(name) <= 100
        or any(character in name for character in "/\\\r\n\t")
    ):
        raise ValueError("Use a bounded MCP_ fixture name and document identity")
    state = document_state(app)
    if state["document_id"] != document_id or state["is_saved"]:
        raise ValueError("Save fixture requires the inspected, unsaved document")
    project = sandbox_project(app)
    files = project.rootFolder.dataFiles
    if any(files.item(index).name == name for index in range(files.count)):
        raise ValueError("Fixture name already exists; refusing duplicate save")
    document = app.activeDocument
    if not document.saveAs(name, project.rootFolder, "MCP development fixture", ""):
        raise RuntimeError("Save failed; inspect cloud state before retrying")
    try:
        result = document_state(app)
    except RuntimeError as exc:
        return {
            "ok": True,
            "development_only": True,
            "save_accepted": True,
            "metadata_pending": True,
            "requested_name": name,
            "requested_project": project.name,
            "requested_project_id": project.id,
            "hints": ["Read get_document_state again; do not repeat the save"],
            "readback_error": str(exc),
        }
    result["save_accepted"] = True
    result["metadata_pending"] = False
    return result


def sketch_component(handler, component_name):
    if not isinstance(component_name, str):
        raise ValueError("Component name must be a string")
    if not component_name:
        return handler._root()
    components = handler._design().allComponents
    matches = [
        components.item(index)
        for index in range(components.count)
        if components.item(index).name == component_name
    ]
    if len(matches) != 1:
        raise ValueError("Component name must identify exactly one component")
    return matches[0]


def draw_sketch_text(
    handler,
    sketch_name: str,
    text: str,
    x: float,
    y: float,
    height: float,
    width: float,
    box_height: float,
    module_loader=importlib.import_module,
    component_name: str = "",
) -> dict:
    if (
        not isinstance(text, str)
        or not 1 <= len(text) <= 100
        or any(character in text for character in "'\\\r\n")
        or not all(math.isfinite(value) for value in (x, y, height, width, box_height))
        or not 0.03 <= height <= 2
        or width <= 0
        or box_height < height
    ):
        raise ValueError("Invalid literal text or text rectangle")
    sketches = sketch_component(handler, component_name).sketches
    matches = [
        sketches.item(index)
        for index in range(sketches.count)
        if sketches.item(index).name == sketch_name
    ]
    if len(matches) != 1:
        raise ValueError("Sketch name must identify exactly one sketch")
    core = module_loader("adsk.core")
    texts = matches[0].sketchTexts
    text_input = texts.createInput3(
        "'" + text + "'", core.ValueInput.createByReal(height)
    )
    text_input.fontName = "Arial"
    if not text_input.setAsMultiLine(
        core.Point3D.create(x, y, 0),
        core.Point3D.create(x + width, y + box_height, 0),
        core.HorizontalAlignments.LeftHorizontalAlignment,
        core.VerticalAlignments.BottomVerticalAlignment,
        0,
    ):
        raise RuntimeError("Text rectangle creation failed")
    created = texts.add(text_input)
    if created is None:
        raise RuntimeError("Sketch text creation failed")
    return {
        "ok": True,
        "development_only": True,
        "sketch_name": sketch_name,
        "text": created.text,
        "text_count": texts.count,
    }


def extrude_sketch_entities(
    handler,
    sketch_name: str,
    entity_type: str,
    distance: float,
    operation: str,
    feature_name: str,
    module_loader=importlib.import_module,
    component_name: str = "",
) -> dict:
    if (
        entity_type not in {"texts", "profiles"}
        or operation not in {"cut", "new_body", "join"}
        or not math.isfinite(distance)
        or distance == 0
        or abs(distance) > 10
        or not isinstance(feature_name, str)
        or not 1 <= len(feature_name) <= 100
    ):
        raise ValueError("Invalid sketch extrusion arguments")
    root = sketch_component(handler, component_name)
    sketches = root.sketches
    matches = [
        sketches.item(index)
        for index in range(sketches.count)
        if sketches.item(index).name == sketch_name
    ]
    if len(matches) != 1:
        raise ValueError("Sketch name must identify exactly one sketch")
    sketch = matches[0]
    entities = sketch.sketchTexts if entity_type == "texts" else sketch.profiles
    if not 1 <= entities.count <= 1000:
        raise ValueError("Sketch must contain 1 to 1000 extrusion entities")
    core = module_loader("adsk.core")
    selection = core.ObjectCollection.create()
    for index in range(entities.count):
        selection.add(entities.item(index))
    extrudes = root.features.extrudeFeatures
    extrusion = extrudes.createInput(selection, handler._operation_type(operation))
    if extrusion is None:
        raise RuntimeError("Extrusion input creation failed")
    if not extrusion.setDistanceExtent(
        distance < 0, core.ValueInput.createByReal(abs(distance))
    ):
        raise RuntimeError("Extrusion extent creation failed")
    feature = extrudes.add(extrusion)
    if feature is None:
        raise RuntimeError("Extrusion creation failed; inspect before retrying")
    feature.name = feature_name
    sketch.isVisible = False
    return {
        "ok": True,
        "development_only": True,
        "feature_name": feature.name,
        "entity_count": entities.count,
        "distance_cm": distance,
        "health_state": int(feature.healthState),
        "message": feature.errorOrWarningMessage,
    }


def selected_body(handler, body_name, occurrence_path=""):
    if (
        not isinstance(body_name, str)
        or not body_name
        or not isinstance(occurrence_path, str)
    ):
        raise ValueError("Explicit body name and occurrence path must be strings")
    root = handler._root()
    matches = []
    if occurrence_path in {"", "root"}:
        matches.extend(
            root.bRepBodies.item(index)
            for index in range(root.bRepBodies.count)
            if root.bRepBodies.item(index).name == body_name
        )
    if occurrence_path != "root":
        for occurrence in root.allOccurrences:
            if occurrence_path and occurrence.fullPathName != occurrence_path:
                continue
            matches.extend(
                occurrence.bRepBodies.item(index)
                for index in range(occurrence.bRepBodies.count)
                if occurrence.bRepBodies.item(index).name == body_name
            )
    if len(matches) != 1:
        raise ValueError("Body target must be unique; supply occurrence_path or root")
    return matches[0]


def get_body_topology(
    handler, body_name, offset=0, limit=100, occurrence_path="", entity_type="edges"
):
    if (
        type(offset) is not int
        or offset < 0
        or type(limit) is not int
        or not 1 <= limit <= 200
        or entity_type not in {"edges", "faces"}
    ):
        raise ValueError("Invalid topology pagination")
    body = selected_body(handler, body_name, occurrence_path)
    if entity_type == "faces":
        rows = []
        for index in range(offset, min(body.faces.count, offset + limit)):
            face = body.faces.item(index)
            rows.append({
                "index": index,
                "bounding_box": handler._bbox_dict(face.boundingBox),
                "area": face.area,
                "surface_type": face.geometry.objectType,
            })
        return {
            "ok": True, "body_name": body_name, "entity_type": "faces",
            "edge_count": body.edges.count, "face_count": body.faces.count,
            "faces": rows,
            "next_offset": offset + len(rows)
            if offset + len(rows) < body.faces.count else None,
        }
    rows = []
    for index in range(offset, min(body.edges.count, offset + limit)):
        edge = body.edges.item(index)
        adjacent = [
            face_index
            for face_index in range(body.faces.count)
            if any(
                body.faces.item(face_index) == edge.faces.item(adjacent_index)
                for adjacent_index in range(edge.faces.count)
            )
        ]
        rows.append(
            {
                "index": index,
                "bounding_box": handler._bbox_dict(edge.boundingBox),
                "face_indices": adjacent,
            }
        )
    return {
        "ok": True,
        "body_name": body_name,
        "entity_type": "edges",
        "edge_count": body.edges.count,
        "face_count": body.faces.count,
        "edges": rows,
        "next_offset": offset + len(rows)
        if offset + len(rows) < body.edges.count
        else None,
    }


def chamfer_edges(
    handler,
    body_name,
    edge_indices,
    reference_face_indices,
    distance_one,
    distance_two,
    feature_name,
    module_loader=importlib.import_module,
    occurrence_path="",
):
    if (
        not isinstance(edge_indices, list)
        or not edge_indices
        or len(edge_indices) > 200
        or any(type(index) is not int or index < 0 for index in edge_indices)
        or len(set(edge_indices)) != len(edge_indices)
        or not isinstance(reference_face_indices, list)
        or len(reference_face_indices) != len(edge_indices)
        or any(type(index) is not int or index < 0 for index in reference_face_indices)
        or not all(
            math.isfinite(value) and value > 0 for value in (distance_one, distance_two)
        )
        or not isinstance(feature_name, str)
        or not 1 <= len(feature_name) <= 100
    ):
        raise ValueError("Invalid explicit-edge chamfer arguments")
    body = selected_body(handler, body_name, occurrence_path)
    selected = []
    for edge_index, face_index in zip(edge_indices, reference_face_indices):
        if edge_index >= body.edges.count or face_index >= body.faces.count:
            raise ValueError("Chamfer edge or face index is out of range")
        edge, face = body.edges.item(edge_index), body.faces.item(face_index)
        if edge.faces.count != 2 or not any(
            edge.faces.item(index) == face for index in range(edge.faces.count)
        ):
            raise ValueError("Reference face must be adjacent to a two-face solid edge")
        selected.append((edge, face))
    if not body.isSolid:
        raise ValueError("Chamfer requires a solid BRep body")
    core = module_loader("adsk.core")
    owner = (
        body.nativeObject.parentComponent if body.nativeObject else body.parentComponent
    )
    chamfers = owner.features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    for edge, face in selected:
        collection = core.ObjectCollection.create()
        collection.add(edge.nativeObject if edge.nativeObject else edge)
        native_face = face.nativeObject if face.nativeObject else face
        native_edge = edge.nativeObject if edge.nativeObject else edge
        if not chamfer_input.chamferEdgeSets.addTwoDistancesChamferEdgeSet(
            collection,
            core.ValueInput.createByReal(distance_one),
            core.ValueInput.createByReal(distance_two),
            native_edge.faces.item(0) == native_face,
            False,
        ):
            raise RuntimeError("Chamfer edge-set creation failed")
    feature = chamfers.add(chamfer_input)
    if feature is None:
        raise RuntimeError("Chamfer creation failed; inspect before retrying")
    feature.name = feature_name
    return {
        "ok": True,
        "feature_name": feature.name,
        "edge_count": len(selected),
        "health_state": int(feature.healthState),
        "message": feature.errorOrWarningMessage,
    }


def chamfer_stencil_edges(
    handler,
    body_name: str,
    scope: str,
    vertical_depth: float,
    angle_degrees: float,
    feature_name: str,
    module_loader=importlib.import_module,
) -> dict:
    if (
        scope not in {"internal", "left", "right", "top", "bottom"}
        or not math.isfinite(vertical_depth)
        or vertical_depth <= 0
        or not math.isfinite(angle_degrees)
        or not 10 <= angle_degrees <= 30
        or not isinstance(feature_name, str)
        or not 1 <= len(feature_name) <= 100
    ):
        raise ValueError("Invalid stencil chamfer arguments")
    body = handler._body_by_name(body_name)
    bounds = body.boundingBox
    if vertical_depth > bounds.maxPoint.z - bounds.minPoint.z:
        raise ValueError("Chamfer depth exceeds body thickness")
    selected = []
    for face_index in range(body.faces.count):
        face = body.faces.item(face_index)
        face_bounds = face.boundingBox
        if not (
            abs(face_bounds.minPoint.z - bounds.maxPoint.z) < 1e-6
            and abs(face_bounds.maxPoint.z - bounds.maxPoint.z) < 1e-6
        ):
            continue
        for loop_index in range(face.loops.count):
            loop = face.loops.item(loop_index)
            if (scope == "internal") == loop.isOuter:
                continue
            for edge_index in range(loop.edges.count):
                edge = loop.edges.item(edge_index)
                edge_bounds = edge.boundingBox
                if scope != "internal":
                    axis = "x" if scope in {"left", "right"} else "y"
                    reference = (
                        bounds.minPoint
                        if scope in {"left", "bottom"}
                        else bounds.maxPoint
                    )
                    if not all(
                        abs(getattr(point, axis) - getattr(reference, axis)) < 1e-6
                        for point in (edge_bounds.minPoint, edge_bounds.maxPoint)
                    ):
                        continue
                selected.append((edge, face))
    if not selected:
        raise ValueError("No matching top stencil edges")
    core = module_loader("adsk.core")
    horizontal_width = vertical_depth / math.tan(math.radians(angle_degrees))
    chamfers = handler._root().features.chamferFeatures
    chamfer_input = chamfers.createInput2()
    for edge, face in selected:
        edges = core.ObjectCollection.create()
        edges.add(edge)
        if not chamfer_input.chamferEdgeSets.addTwoDistancesChamferEdgeSet(
            edges,
            core.ValueInput.createByReal(horizontal_width),
            core.ValueInput.createByReal(vertical_depth),
            edge.faces.item(0) == face,
            False,
        ):
            raise RuntimeError("Chamfer edge-set creation failed")
    feature = chamfers.add(chamfer_input)
    feature.name = feature_name
    faces = []
    for index in range(feature.faces.count):
        face = feature.faces.item(index)
        geometry = face.geometry
        normal = getattr(geometry, "normal", None)
        faces.append(
            {
                "bounding_box": handler._bbox_dict(face.boundingBox),
                "normal": [normal.x, normal.y, normal.z] if normal else None,
            }
        )
    return {
        "ok": True,
        "development_only": True,
        "feature_name": feature.name,
        "edge_count": len(selected),
        "vertical_depth_cm": vertical_depth,
        "horizontal_width_cm": horizontal_width,
        "angle_degrees": angle_degrees,
        "health_state": int(feature.healthState),
        "message": feature.errorOrWarningMessage,
        "bevel_faces": faces,
    }


def create_sandbox_drawing(
    app, document_id: str, module_loader=importlib.import_module
) -> dict:
    state = document_state(app)
    if state["document_id"] != document_id or state["project_name"] != "MCP_Dev":
        raise ValueError("Drawing source must be the inspected saved MCP_Dev document")
    drawing_api = module_loader("adsk.drawing")
    manager = drawing_api.DrawingManager.get()
    source = app.activeDocument.dataFile
    if source.fileExtension != "f3d":
        raise ValueError("Drawing source must be a saved Fusion design")
    if not source.isComplete:
        raise ValueError("Source cloud upload is incomplete; inspect before creation")
    drawing_input = manager.createDrawingInput(
        source, drawing_api.DrawingCreationModes.AutomaticDrawingCreationMode
    )
    if drawing_input is None:
        raise RuntimeError("Drawing input creation failed")
    created = manager.createDrawing(drawing_input)
    if created is None:
        raise RuntimeError("Drawing creation failed; inspect project before retrying")
    if created.parentProject.id != source.parentProject.id:
        raise RuntimeError("Created drawing outside source project; do not retry")
    return {
        "ok": True,
        "development_only": True,
        "preview_api": True,
        "data_file_id": created.id,
        "name": created.name,
        "project_name": created.parentProject.name,
    }


def open_sandbox_drawing(app, data_file_id: str) -> dict:
    if not isinstance(data_file_id, str) or not data_file_id:
        raise ValueError("Drawing file identity is required")
    files = sandbox_project(app).rootFolder.dataFiles
    matches = [
        files.item(index)
        for index in range(files.count)
        if files.item(index).id == data_file_id
    ]
    if len(matches) != 1 or matches[0].fileExtension != "f2d":
        raise ValueError("Drawing must identify a saved MCP_Dev root-folder drawing")
    document = app.documents.open(matches[0])
    if document is None:
        raise RuntimeError("Drawing open failed")
    return document_state(app)
