"""Bounded read-only mechanical/drawing candidates, not production registration."""

import importlib
import math
import os
import tempfile


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
    data_file_id = None
    project_name = None
    if data_file is not None:
        try:
            if data_file.isComplete:
                parent_project = data_file.parentProject
                data_file_id = data_file.id
                project_name = parent_project.name
        except RuntimeError:
            pass
    return {
        "ok": True,
        "development_only": True,
        "document_id": document.creationId,
        "document_name": document.name,
        "is_saved": document.isSaved,
        "data_file_id": data_file_id,
        "project_name": project_name,
        "metadata_pending": bool(data_file is not None and data_file_id is None),
    }


def diagnose_document_save(handler, document_id, required_slots=1):
    if not isinstance(document_id, str) or not document_id:
        raise ValueError("An inspected document identity is required")
    if type(required_slots) is not int or not 1 <= required_slots <= 100:
        raise ValueError("required_slots must be an integer from 1 to 100")
    app = handler.app
    document = app.activeDocument
    if document is None or not document.isValid or document.creationId != document_id:
        raise ValueError("Diagnostic requires the inspected active document identity")
    result = {
        "ok": True,
        "development_only": True,
        "document_id": document_id,
        "is_saved": bool(document.isSaved),
        "required_slots": required_slots,
        "save_failure_cause_confirmed": False,
        "save_retried": False,
    }
    limits = app.data.personalUseLimits
    if limits is None:
        return {**result, "status": "NOT_PERSONAL_USE", "quota_applies": False}
    if not limits.isValid:
        raise RuntimeError("Personal Use quota information is invalid; inspect Fusion")
    count = limits.editableFileCount
    maximum = limits.maxEditableFileCount
    if type(count) is not int or type(maximum) is not int or count < 0 or maximum < 1:
        raise RuntimeError("Fusion returned invalid editable-document quota counts")
    available = max(0, maximum - count)
    release_count = max(0, required_slots - available)
    status = "SLOTS_AVAILABLE"
    if count >= maximum:
        status = "EDITABLE_DOCUMENT_LIMIT_REACHED"
    elif release_count:
        status = "INSUFFICIENT_EDITABLE_DOCUMENT_SLOTS"
    return {
        **result,
        "quota_applies": True,
        "editable_file_count": count,
        "max_editable_file_count": maximum,
        "available_slots": available,
        "documents_to_make_read_only": release_count,
        "status": status,
        "evidence": (
            "Fusion PersonalUseLimits counts are current quota evidence, not a "
            "record of a previous save failure. Existing editable-file saves "
            "may not require a new slot. Pending uploads alone do not prove "
            "quota failure."
        ),
        "instructions": (
            [
                f"In Fusion's Data Panel, change at least {release_count} unused "
                "editable document(s) to Read-Only. Do not delete the files.",
                "Keep documents needed for this assembly editable. Re-run this "
                "diagnostic after changing their status.",
                "Inspect the document and cloud save state before explicitly "
                "retrying a failed save; never repeat an accepted pending save.",
            ] if release_count else []
        ),
    }


def open_design(app, data_file_id: str) -> dict:
    if not isinstance(data_file_id, str) or not data_file_id:
        raise ValueError("Saved design data_file_id is required")
    active = app.activeDocument
    if active is not None and active.isValid and not active.isSaved:
        raise ValueError("Save the active document before opening another design")
    data_file = app.data.findFileById(data_file_id)
    if (
        data_file is None
        or data_file.fileExtension != "f3d"
        or not data_file.isComplete
    ):
        raise ValueError("data_file_id must identify a complete saved Fusion design")
    if active is not None and active.isValid and active.dataFile.id == data_file_id:
        opened = active
    else:
        opened = app.documents.open(data_file)
    if opened is None or not opened.isValid:
        raise RuntimeError(
            "Design open failed; inspect active document before retrying"
        )
    if app.activeDocument is None or app.activeDocument.dataFile.id != data_file_id:
        raise RuntimeError("Fusion did not activate the requested saved design")
    state = document_state(app)
    state.pop("development_only", None)
    return state


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
    metadata_pending = not state["data_file_id"] or not state["project_name"]
    if metadata_pending:
        state["metadata_pending"] = True
        state["save_accepted"] = True
        return {**requested, **state}
    return {
        **state,
        "save_accepted": True,
        "metadata_pending": False,
    }


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
    if result["metadata_pending"]:
        result.pop("project_name", None)
        return {
            **result,
            "development_only": True,
            "save_accepted": True,
            "metadata_pending": True,
            "requested_name": name,
            "requested_project": project.name,
            "requested_project_id": project.id,
            "hints": ["Read get_document_state again; do not repeat the save"],
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
    fusion = module_loader("adsk.fusion")
    set_extrude_extent(
        extrusion,
        core,
        fusion,
        abs(distance),
        "negative" if distance < 0 else "positive",
    )
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


def set_extrude_extent(extrusion, core, fusion, extent_cm, direction):
    if not math.isfinite(extent_cm) or extent_cm <= 0:
        raise ValueError("Extrude extent must be a positive finite distance")
    if direction == "symmetric":
        accepted = extrusion.setSymmetricExtent(
            core.ValueInput.createByReal(extent_cm), True
        )
    elif direction in {"positive", "negative"}:
        extent = fusion.DistanceExtentDefinition.create(
            core.ValueInput.createByReal(extent_cm)
        )
        direction_value = (
            fusion.ExtentDirections.PositiveExtentDirection
            if direction == "positive"
            else fusion.ExtentDirections.NegativeExtentDirection
        )
        accepted = extrusion.setOneSideExtent(extent, direction_value)
    else:
        raise ValueError("Extrude direction must be positive, negative or symmetric")
    if not accepted:
        raise RuntimeError("Extrude extent definition was rejected")
    return True


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
    if state["document_id"] != document_id:
        raise ValueError("Drawing source must be the inspected saved MCP_Dev document")
    source = app.activeDocument.dataFile
    if source is None or source.fileExtension != "f3d":
        raise ValueError("Drawing source must be a saved Fusion design")
    if not source.isComplete:
        raise ValueError("Source cloud upload is incomplete; inspect before creation")
    if state["project_name"] != "MCP_Dev":
        raise ValueError("Drawing source must be the inspected saved MCP_Dev document")
    drawing_api = module_loader("adsk.drawing")
    manager = drawing_api.DrawingManager.get()
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


# ----------------------------------------------------------------------
# Assembly candidates: occurrences, joints and joint motion
# ----------------------------------------------------------------------

JOINT_TYPES = (
    "rigid", "revolute", "slider", "cylindrical", "pin_slot", "planar", "ball",
)
_JOINT_TYPE_NAMES = (*JOINT_TYPES, "inferred")
JOINT_DIRECTION_OPTIONS = {
    "rigid": {},
    "revolute": {"rotation_axis": "z"},
    "slider": {"slide_direction": "z"},
    "cylindrical": {"rotation_axis": "z"},
    "pin_slot": {"rotation_axis": "z", "slide_direction": "x"},
    "planar": {"normal_direction": "z"},
    "ball": {"pitch_direction": "z", "yaw_direction": "x"},
}
JOINT_MOTION_FIELDS = {
    "rigid": {},
    "revolute": {"rotation_degrees": "rotationValue"},
    "slider": {"slide": "slideValue"},
    "cylindrical": {"rotation_degrees": "rotationValue", "slide": "slideValue"},
    "pin_slot": {"rotation_degrees": "rotationValue", "slide": "slideValue"},
    "planar": {
        "rotation_degrees": "rotationValue",
        "primary_slide": "primarySlideValue",
        "secondary_slide": "secondarySlideValue",
    },
    "ball": {
        "pitch_degrees": "pitchValue",
        "yaw_degrees": "yawValue",
        "roll_degrees": "rollValue",
    },
}
_LIMIT_FIELDS = {
    "rotation_degrees": "rotationLimits",
    "slide": "slideLimits",
}
_KEY_POINTS = ("start", "middle", "end", "center")
_GEOMETRY_KEYS = {"occurrence_path", "entity", "body_name", "index", "key_point"}
DESIGN_INTENTS = ("part", "assembly", "hybrid")


def _is_angle(field):
    return field.endswith("_degrees")


def _to_internal(field, value):
    return math.radians(value) if _is_angle(field) else value


def _from_internal(field, value):
    return math.degrees(value) if _is_angle(field) else value


def _finite_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _matrix_payload(matrix):
    cells = list(matrix.asArray())
    return {
        "translation": [cells[3], cells[7], cells[11]],
        "rotation": [cells[0:3], cells[4:7], cells[8:11]],
    }


def _transform(core, translation=None, rotation=None):
    translation = [0, 0, 0] if translation is None else translation
    if (
        not isinstance(translation, list)
        or len(translation) != 3
        or not all(_finite_number(value) for value in translation)
    ):
        raise ValueError("Translation must be three finite cm values")
    matrix = core.Matrix3D.create()
    if rotation is not None:
        if (
            not isinstance(rotation, dict)
            or set(rotation) != {"axis", "angle_degrees"}
            or not isinstance(rotation["axis"], list)
            or len(rotation["axis"]) != 3
            or not all(_finite_number(value) for value in rotation["axis"])
            or not _finite_number(rotation["angle_degrees"])
            or math.hypot(*rotation["axis"]) < 1e-9
        ):
            raise ValueError(
                "Rotation requires a nonzero axis and finite angle_degrees"
            )
        if not matrix.setToRotation(
            math.radians(rotation["angle_degrees"]),
            core.Vector3D.create(*rotation["axis"]),
            core.Point3D.create(0, 0, 0),
        ):
            raise RuntimeError("Rotation transform creation failed")
    matrix.translation = core.Vector3D.create(*translation)
    return matrix


def _occurrence_row(occurrence):
    component = occurrence.component
    definition = getattr(occurrence, "definition", None)
    grounding_supported = "+" not in occurrence.fullPathName
    grounded = bool(occurrence.isGrounded) if grounding_supported else None
    return {
        "path": occurrence.fullPathName,
        "name": occurrence.name,
        "component_name": component.name,
        "is_grounded": grounded,
        "grounding_supported": grounding_supported,
        "is_referenced": bool(occurrence.isReferencedComponent),
        "is_visible": bool(occurrence.isLightBulbOn),
        "body_count": occurrence.bRepBodies.count,
        "child_count": occurrence.childOccurrences.count,
        "is_library_item": getattr(component, "isLibraryItem", None),
        "definition_type": getattr(definition, "objectType", None),
        "transform": _matrix_payload(occurrence.transform2),
    }


def occurrence_by_path(handler, occurrence_path):
    if not isinstance(occurrence_path, str) or not occurrence_path:
        raise ValueError("Explicit occurrence path is required")
    if occurrence_path == "root":
        return None
    matches = [
        occurrence
        for occurrence in handler._root().allOccurrences
        if occurrence.fullPathName == occurrence_path
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Occurrence path '{occurrence_path}' must identify one occurrence"
        )
    return matches[0]


def list_occurrences(handler, offset=0, limit=100):
    if (
        type(offset) is not int
        or type(limit) is not int
        or offset < 0
        or not 1 <= limit <= 200
    ):
        raise ValueError("Invalid occurrence pagination")
    occurrences = list(handler._root().allOccurrences)
    rows = [_occurrence_row(item) for item in occurrences[offset:offset + limit]]
    return {
        "ok": True,
        "development_only": True,
        "total": len(occurrences),
        "offset": offset,
        "occurrences": rows,
        "next_offset": offset + len(rows)
        if offset + len(rows) < len(occurrences)
        else None,
    }


def _parent_component(handler, parent_component_name):
    if not isinstance(parent_component_name, str):
        raise ValueError("Parent component name must be a string")
    return sketch_component(handler, parent_component_name)


def add_occurrence(
    handler,
    component_name,
    parent_component_name="",
    translation=None,
    rotation=None,
    grounded=False,
    module_loader=importlib.import_module,
):
    if not isinstance(component_name, str) or not component_name:
        raise ValueError("Explicit non-root component name is required")
    if not isinstance(grounded, bool):
        raise ValueError("Grounded must be boolean")
    component = sketch_component(handler, component_name)
    parent = _parent_component(handler, parent_component_name)
    if component == handler._root() or component == parent:
        raise ValueError("A component cannot be placed inside itself or the root")
    matrix = _transform(module_loader("adsk.core"), translation, rotation)
    occurrence = parent.occurrences.addExistingComponent(component, matrix)
    if occurrence is None:
        raise RuntimeError("Occurrence creation failed; inspect before retrying")
    occurrence.isGrounded = grounded
    return {"ok": True, "development_only": True, **_occurrence_row(occurrence)}


def insert_design(
    handler,
    data_file_id,
    parent_component_name="",
    translation=None,
    rotation=None,
    grounded=False,
    referenced=True,
    module_loader=importlib.import_module,
):
    if not isinstance(data_file_id, str) or not data_file_id:
        raise ValueError("Saved design data_file_id is required")
    if not isinstance(grounded, bool) or not isinstance(referenced, bool):
        raise ValueError("Grounded and referenced must be boolean")
    app = handler.app
    document = app.activeDocument
    if document is None or not document.isValid:
        raise ValueError("No valid active document")
    data_file = app.data.findFileById(data_file_id)
    if data_file is None or data_file.fileExtension != "f3d":
        raise ValueError("data_file_id must identify a saved Fusion design")
    if document.isSaved and document.dataFile.id == data_file.id:
        raise ValueError("A design cannot be inserted into itself")
    if referenced and (
        not document.isSaved
        or not document.dataFile
    ):
        raise ValueError(
            "Referenced insertion requires the active document saved in the "
            "same project as the inserted design"
        )
    if referenced:
        try:
            active_project_id = document.dataFile.parentProject.id
            inserted_project_id = data_file.parentProject.id
        except RuntimeError as exc:
            raise ValueError(
                "Referenced insertion requires complete project metadata"
            ) from exc
        if active_project_id != inserted_project_id:
            raise ValueError(
                "Referenced insertion requires the active document saved in the "
                "same project as the inserted design"
            )
    parent = _parent_component(handler, parent_component_name)
    nested = parent != handler._root()
    if nested and grounded:
        raise ValueError("Grounding is only supported for root-level occurrences")
    parent_occurrence = None
    if nested:
        parents = [
            item for item in handler._root().allOccurrences
            if item.component == parent
        ]
        if len(parents) != 1:
            raise ValueError("Nested insert requires one unambiguous parent occurrence")
        parent_occurrence = parents[0]
    matrix = _transform(module_loader("adsk.core"), translation, rotation)
    occurrence = parent.occurrences.addByInsert(data_file, matrix, referenced)
    if occurrence is None:
        raise RuntimeError("Design insertion failed; inspect before retrying")
    if not nested:
        occurrence.isGrounded = grounded
    else:
        occurrence = occurrence.createForAssemblyContext(parent_occurrence)
        if occurrence is None:
            raise RuntimeError(
                "Inserted occurrence context unavailable; inspect design"
            )
    return {
        "ok": True,
        "development_only": True,
        "data_file_id": data_file.id,
        "data_file_name": data_file.name,
        "version_number": data_file.versionNumber,
        **_occurrence_row(occurrence),
    }


def set_design_intent(handler, intent, module_loader=importlib.import_module):
    if intent not in DESIGN_INTENTS:
        raise ValueError("Design intent must be part, assembly or hybrid")
    fusion = module_loader("adsk.fusion")
    values = {
        "part": fusion.DesignIntentTypes.PartDesignIntentType,
        "assembly": fusion.DesignIntentTypes.AssemblyDesignIntentType,
        "hybrid": fusion.DesignIntentTypes.HybridDesignIntentType,
    }
    names = {int(value): name for name, value in values.items()}
    design = handler._design()
    before = names.get(int(design.designIntent), "unknown")
    if before != intent:
        design.designIntent = values[intent]
    after = names.get(int(design.designIntent), "unknown")
    if after != intent:
        raise RuntimeError("Fusion rejected the requested design intent")
    return {
        "ok": True,
        "development_only": True,
        "preview_api": True,
        "intent_before": before,
        "intent": after,
        "changed": before != after,
    }


def _all_joints(handler):
    design = handler._design()
    joints = []
    for component_index in range(design.allComponents.count):
        component = design.allComponents.item(component_index)
        for kind, collection in (
            ("joint", component.joints),
            ("as_built", component.asBuiltJoints),
        ):
            for index in range(collection.count):
                joints.append((component, kind, collection.item(index)))
    return joints


def _joint_by_name(handler, joint_name):
    if not isinstance(joint_name, str) or not joint_name:
        raise ValueError("Explicit joint name is required")
    matches = [
        joint for _, _, joint in _all_joints(handler) if joint.name == joint_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Joint '{joint_name}' must identify exactly one joint")
    return matches[0]


def _joint_type(joint):
    index = int(joint.jointMotion.jointType)
    if not 0 <= index < len(_JOINT_TYPE_NAMES):
        raise RuntimeError("Unknown joint motion type")
    return _JOINT_TYPE_NAMES[index]


def _limit_payload(limits, field):
    return {
        "minimum": _from_internal(field, limits.minimumValue)
        if limits.isMinimumValueEnabled else None,
        "maximum": _from_internal(field, limits.maximumValue)
        if limits.isMaximumValueEnabled else None,
    }


def joint_info(component, kind, joint):
    joint_type = _joint_type(joint)
    motion = joint.jointMotion
    fields = JOINT_MOTION_FIELDS.get(joint_type, {})
    health_state = getattr(joint, "healthState", None)
    limits = {
        field: _limit_payload(getattr(motion, _LIMIT_FIELDS[field]), field)
        for field in fields
        if field in _LIMIT_FIELDS
    }
    return {
        "name": joint.name,
        "kind": kind,
        "joint_type": joint_type,
        "owner_component": component.name,
        "occurrence_one": joint.occurrenceOne.fullPathName
        if joint.occurrenceOne else "root",
        "occurrence_two": joint.occurrenceTwo.fullPathName
        if joint.occurrenceTwo else "root",
        "motion": {
            field: _from_internal(field, getattr(motion, attribute))
            for field, attribute in fields.items()
        },
        "limits": limits,
        "is_suppressed": bool(joint.isSuppressed),
        "is_valid": bool(joint.isValid),
        "health_state": int(health_state) if health_state is not None else None,
        "message": getattr(joint, "errorOrWarningMessage", ""),
    }


def list_joints(handler, offset=0, limit=100):
    if (
        type(offset) is not int
        or type(limit) is not int
        or offset < 0
        or not 1 <= limit <= 200
    ):
        raise ValueError("Invalid joint pagination")
    joints = _all_joints(handler)
    rows = [joint_info(*item) for item in joints[offset:offset + limit]]
    return {
        "ok": True,
        "development_only": True,
        "total": len(joints),
        "offset": offset,
        "joints": rows,
        "next_offset": offset + len(rows)
        if offset + len(rows) < len(joints)
        else None,
    }


def _joint_geometry(handler, spec, fusion):
    if not isinstance(spec, dict) or not {"occurrence_path", "entity"} <= set(spec):
        raise ValueError("Joint geometry requires occurrence_path and entity")
    if set(spec) - _GEOMETRY_KEYS:
        raise ValueError("Unsupported joint geometry fields")
    path, entity = spec["occurrence_path"], spec["entity"]
    occurrence = occurrence_by_path(handler, path)
    if entity == "origin":
        if set(spec) != {"occurrence_path", "entity"}:
            raise ValueError("Origin geometry accepts no body, index or key point")
        if occurrence is None:
            point = handler._root().originConstructionPoint
        else:
            point = occurrence.component.originConstructionPoint
            point = point.createForAssemblyContext(occurrence)
        return fusion.JointGeometry.createByPoint(point)
    if entity not in {"face", "edge"}:
        raise ValueError("Joint geometry entity must be face, edge or origin")
    index, key_point = spec.get("index"), spec.get("key_point", "center")
    if type(index) is not int or index < 0 or key_point not in _KEY_POINTS:
        raise ValueError("Face/edge geometry requires index and a valid key_point")
    body = selected_body(handler, spec.get("body_name"), path)
    keys = fusion.JointKeyPointTypes
    key = {
        "start": keys.StartKeyPoint,
        "middle": keys.MiddleKeyPoint,
        "end": keys.EndKeyPoint,
        "center": keys.CenterKeyPoint,
    }[key_point]
    if entity == "edge":
        if index >= body.edges.count:
            raise ValueError("Joint edge index is out of range")
        geometry = fusion.JointGeometry.createByCurve(body.edges.item(index), key)
    else:
        if index >= body.faces.count:
            raise ValueError("Joint face index is out of range")
        face = body.faces.item(index)
        surface = face.geometry.objectType
        if surface == "adsk::core::Plane":
            if key_point != "center":
                raise ValueError("Planar face geometry supports key_point center")
            geometry = fusion.JointGeometry.createByPlanarFace(face, None, key)
        elif surface in {"adsk::core::Cylinder", "adsk::core::Cone"}:
            if key_point == "center":
                raise ValueError(
                    "Cylindrical/conical faces support start, middle or end"
                )
            geometry = fusion.JointGeometry.createByCylinderOrConeFace(
                face, fusion.JointQuadrantAngleTypes.StartJointQuadrantAngleType, key
            )
        else:
            raise ValueError(
                "Face geometry supports planar, cylindrical or conical faces"
            )
    if geometry is None:
        raise ValueError("Fusion could not create joint geometry from selection")
    return geometry


def create_joint(
    handler,
    joint_name,
    joint_type,
    geometry_one,
    geometry_two,
    offset=0,
    angle_degrees=0,
    is_flipped=False,
    rotation_axis=None,
    slide_direction=None,
    normal_direction=None,
    pitch_direction=None,
    yaw_direction=None,
    rotation_limits_degrees=None,
    slide_limits=None,
    module_loader=importlib.import_module,
):
    if joint_type not in JOINT_TYPES:
        raise ValueError("Unsupported joint type")
    if (
        not isinstance(joint_name, str)
        or not 1 <= len(joint_name) <= 100
        or not _finite_number(offset)
        or not _finite_number(angle_degrees)
        or not isinstance(is_flipped, bool)
    ):
        raise ValueError("Invalid joint name, offset, angle or flip")
    directions = {
        "rotation_axis": rotation_axis,
        "slide_direction": slide_direction,
        "normal_direction": normal_direction,
        "pitch_direction": pitch_direction,
        "yaw_direction": yaw_direction,
    }
    allowed = JOINT_DIRECTION_OPTIONS[joint_type]
    supplied = {key for key, value in directions.items() if value is not None}
    if supplied - set(allowed):
        raise ValueError(f"{joint_type} joints do not accept {sorted(supplied)}")
    selected = {
        key: directions[key] if directions[key] is not None else default
        for key, default in allowed.items()
    }
    if any(value not in {"x", "y", "z"} for value in selected.values()):
        raise ValueError("Joint directions must be x, y or z")
    if len(set(selected.values())) != len(selected):
        raise ValueError("Joint motion directions must differ")
    requested_limits = {}
    for field, value in (
        ("rotation_degrees", rotation_limits_degrees),
        ("slide", slide_limits),
    ):
        if value is None:
            continue
        if field not in JOINT_MOTION_FIELDS[joint_type] or field not in _LIMIT_FIELDS:
            raise ValueError(f"{joint_type} joints do not accept {field} limits")
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(_finite_number(item) for item in value)
            or value[0] >= value[1]
        ):
            raise ValueError("Limits must be [minimum, maximum] with minimum < maximum")
        requested_limits[field] = value
    if any(joint.name == joint_name for _, _, joint in _all_joints(handler)):
        raise ValueError("Joint name already exists")
    if (
        isinstance(geometry_one, dict)
        and isinstance(geometry_two, dict)
        and geometry_one.get("occurrence_path") == geometry_two.get("occurrence_path")
    ):
        raise ValueError("Joint geometries must belong to different occurrences")
    core = module_loader("adsk.core")
    fusion = module_loader("adsk.fusion")
    first = _joint_geometry(handler, geometry_one, fusion)
    second = _joint_geometry(handler, geometry_two, fusion)
    joints = handler._root().joints
    joint_input = joints.createInput(first, second)
    if joint_input is None:
        raise RuntimeError("Joint input creation failed")
    joint_input.offset = core.ValueInput.createByReal(offset)
    joint_input.angle = core.ValueInput.createByReal(math.radians(angle_degrees))
    joint_input.isFlipped = is_flipped
    direction = {
        "x": fusion.JointDirections.XAxisJointDirection,
        "y": fusion.JointDirections.YAxisJointDirection,
        "z": fusion.JointDirections.ZAxisJointDirection,
    }
    if joint_type == "rigid":
        accepted = joint_input.setAsRigidJointMotion()
    elif joint_type == "revolute":
        accepted = joint_input.setAsRevoluteJointMotion(
            direction[selected["rotation_axis"]]
        )
    elif joint_type == "slider":
        accepted = joint_input.setAsSliderJointMotion(
            direction[selected["slide_direction"]]
        )
    elif joint_type == "cylindrical":
        accepted = joint_input.setAsCylindricalJointMotion(
            direction[selected["rotation_axis"]]
        )
    elif joint_type == "pin_slot":
        accepted = joint_input.setAsPinSlotJointMotion(
            direction[selected["rotation_axis"]],
            direction[selected["slide_direction"]],
        )
    elif joint_type == "planar":
        accepted = joint_input.setAsPlanarJointMotion(
            direction[selected["normal_direction"]]
        )
    else:
        accepted = joint_input.setAsBallJointMotion(
            direction[selected["pitch_direction"]],
            direction[selected["yaw_direction"]],
        )
    if not accepted:
        raise ValueError("Fusion rejected the joint motion definition")
    joint = joints.add(joint_input)
    if joint is None:
        raise RuntimeError("Joint creation failed; inspect before retrying")
    joint.name = joint_name
    for field, (minimum, maximum) in requested_limits.items():
        limits = getattr(joint.jointMotion, _LIMIT_FIELDS[field])
        limits.isMinimumValueEnabled = True
        limits.minimumValue = _to_internal(field, minimum)
        limits.isMaximumValueEnabled = True
        limits.maximumValue = _to_internal(field, maximum)
    return {
        "ok": True,
        "development_only": True,
        "directions": selected,
        **joint_info(handler._root(), "joint", joint),
    }


def _validated_motion_values(joint, values):
    joint_type = _joint_type(joint)
    fields = JOINT_MOTION_FIELDS.get(joint_type, {})
    if (
        not isinstance(values, dict)
        or not values
        or set(values) - set(fields)
        or not all(_finite_number(value) for value in values.values())
    ):
        raise ValueError(
            f"{joint_type} joints accept finite values for {sorted(fields)}"
        )
    for field, value in values.items():
        if field in _LIMIT_FIELDS:
            limits = _limit_payload(
                getattr(joint.jointMotion, _LIMIT_FIELDS[field]), field
            )
            if (limits["minimum"] is not None and value < limits["minimum"] - 1e-9) or (
                limits["maximum"] is not None and value > limits["maximum"] + 1e-9
            ):
                raise ValueError(f"{field} value {value} is outside joint limits")
    return fields


def _apply_motion(joint, fields, values):
    for field, value in values.items():
        setattr(joint.jointMotion, fields[field], _to_internal(field, value))


def _joint_owner(handler, joint):
    for component, kind, candidate in _all_joints(handler):
        if candidate == joint:
            return component, kind
    raise RuntimeError("Joint owner was not found")


def _motion_state(handler, joint):
    owner, kind = _joint_owner(handler, joint)
    state = joint_info(owner, kind, joint)
    state["occurrence_transforms"] = {
        occurrence.fullPathName: _matrix_payload(occurrence.transform2)
        for occurrence in (joint.occurrenceOne, joint.occurrenceTwo)
        if occurrence is not None
    }
    return state


def drive_joint(handler, joint_name, values):
    joint = _joint_by_name(handler, joint_name)
    fields = _validated_motion_values(joint, values)
    _apply_motion(joint, fields, values)
    return {
        "ok": True,
        "development_only": True,
        "requested": values,
        **_motion_state(handler, joint),
    }


def animate_joint(
    handler,
    joint_name,
    field,
    values,
    view="current",
    width=800,
    height=600,
    restore=True,
    module_loader=importlib.import_module,
):
    if (
        not isinstance(values, list)
        or not 2 <= len(values) <= 24
        or not isinstance(field, str)
        or type(width) is not int
        or type(height) is not int
        or not 64 <= width <= 1600
        or not 64 <= height <= 1600
        or not isinstance(restore, bool)
        or (view != "current" and view not in handler._VIEW_DIRS)
    ):
        raise ValueError("Invalid animation frames, field, view or image size")
    joint = _joint_by_name(handler, joint_name)
    fields = _validated_motion_values(joint, {field: values[0]})
    for value in values:
        _validated_motion_values(joint, {field: value})
    attribute = fields[field]
    initial = _from_internal(field, getattr(joint.jointMotion, attribute))
    viewport = handler.app.activeViewport
    if viewport is None:
        raise RuntimeError("No active viewport")
    core = module_loader("adsk.core")
    original_camera = None
    if view != "current":
        camera = viewport.camera
        original_camera = (
            camera.eye, camera.target, camera.upVector, camera.cameraType
        )
        handler._orient_camera(viewport, handler._VIEW_DIRS[view])
        viewport.fit()
    directory = tempfile.mkdtemp(prefix="fusion_joint_animation_")
    frames = []
    try:
        for frame_index, value in enumerate(values):
            _apply_motion(joint, fields, {field: value})
            viewport.refresh()
            path = os.path.join(directory, f"frame_{frame_index:02d}.png")
            if not viewport.saveAsImageFile(path, width, height):
                raise RuntimeError("Animation frame capture failed")
            frames.append({
                "index": frame_index,
                "requested": value,
                "actual": _from_internal(field, getattr(joint.jointMotion, attribute)),
                "path": path,
                "bytes": os.path.getsize(path),
            })
    finally:
        if restore:
            _apply_motion(joint, fields, {field: initial})
        if original_camera is not None:
            camera = viewport.camera
            camera.isSmoothTransition = False
            camera.eye, camera.target, camera.upVector, camera.cameraType = (
                core.Point3D.create(
                    original_camera[0].x, original_camera[0].y, original_camera[0].z
                ),
                core.Point3D.create(
                    original_camera[1].x, original_camera[1].y, original_camera[1].z
                ),
                core.Vector3D.create(
                    original_camera[2].x, original_camera[2].y, original_camera[2].z
                ),
                original_camera[3],
            )
            viewport.camera = camera
            viewport.refresh()
    return {
        "ok": True,
        "development_only": True,
        "joint_name": joint.name,
        "field": field,
        "directory": directory,
        "frames": frames,
        "restored": restore,
        "final": _motion_state(handler, joint),
    }
