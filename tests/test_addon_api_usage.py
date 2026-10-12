"""Guards against add-in code calling Fusion APIs that do not exist.

The add-in cannot be imported here — it needs Fusion's ``adsk`` runtime — so
these checks read it with ``ast`` the same way ``test_addon_sync.py`` does.

Both bugs these cover shared a root cause: the failing call sat inside a bare
``except Exception: pass``, so the tool reported success while doing nothing.
Neither would have been caught by a test that only asserted on return values.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import call as mock_call

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HANDLER = REPO_ROOT / "addon" / "server" / "command_handler.py"


def _method(name: str) -> ast.FunctionDef:
    tree = ast.parse(HANDLER.read_text())
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        if cls.name != "CommandHandler":
            continue
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
    raise AssertionError(f"CommandHandler.{name} not found in {HANDLER}")


@pytest.fixture
def object_info_case():
    def collection(items):
        return SimpleNamespace(count=len(items), item=items.__getitem__)

    body = SimpleNamespace(
        name="Part",
        volume=2,
        area=3,
        material=None,
        isVisible=True,
        faces=collection([object()]),
        edges=collection([object()]),
        vertices=collection([object()]),
        boundingBox="bounds",
    )
    sketch = SimpleNamespace(
        name="Labels",
        isVisible=True,
        profiles=collection([]),
        sketchCurves=collection([]),
    )
    component = SimpleNamespace(
        name="Nested", bRepBodies=collection([body]), sketches=collection([sketch])
    )
    occurrence = SimpleNamespace(
        fullPathName="Nested:1", component=component, bRepBodies=component.bRepBodies
    )
    root = SimpleNamespace(
        name="Root",
        bRepBodies=collection([]),
        sketches=collection([]),
        allOccurrences=[occurrence],
    )
    handler = SimpleNamespace(
        _root=lambda: root,
        _design=lambda: SimpleNamespace(allComponents=collection([root, component])),
        _bbox_dict=lambda bounds: {"min": [1, 2, 3], "max": [2, 3, 4]},
    )
    namespace = {}
    node = _method("get_object_info")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    return namespace["get_object_info"], handler, root, component, collection


def test_object_info_finds_nested_body(object_info_case):
    method, handler, root, component, collection = object_info_case
    result = method(handler, "Part")
    assert result["found"] and result["type"] == "body"
    assert result["volume"] == 2 and result["bounding_box"]["min"] == [1, 2, 3]


def test_object_info_finds_component_sketch(object_info_case):
    method, handler, root, component, collection = object_info_case
    result = method(handler, "Labels")
    assert result["found"] and result["type"] == "sketch"


def test_object_info_rejects_ambiguous_body_names(object_info_case):
    method, handler, root, component, collection = object_info_case
    root.bRepBodies = component.bRepBodies
    with pytest.raises(ValueError, match="ambiguous"):
        method(handler, "Part")


def test_object_info_preserves_not_found_result(object_info_case):
    method, handler, root, component, collection = object_info_case
    assert method(handler, "Missing") == {"found": False, "name": "Missing"}


def test_object_info_explicit_targets_resolve_duplicate_names(object_info_case):
    method, handler, root, component, collection = object_info_case
    root.bRepBodies = component.bRepBodies
    assert method(handler, "Part", entity_type="body", occurrence_path="Nested:1")[
        "found"
    ]
    assert method(handler, "Part", entity_type="body", occurrence_path="root")["found"]
    root.sketches = component.sketches
    with pytest.raises(ValueError, match="ambiguous"):
        method(handler, "Labels")
    assert method(handler, "Labels", entity_type="sketch", component_name="Nested")[
        "found"
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        {"entity_type": "unknown"},
        {"entity_type": "body", "component_name": "Nested"},
        {"entity_type": "sketch", "occurrence_path": "Nested:1"},
        {"component_name": "Missing"},
    ],
)
def test_object_info_rejects_invalid_or_missing_owner(object_info_case, arguments):
    method, handler, root, component, collection = object_info_case
    with pytest.raises(ValueError):
        method(handler, "Part", **arguments)


def test_scene_info_enumerates_root_nested_and_repeated_occurrences():
    def collection(items):
        return SimpleNamespace(count=len(items), item=items.__getitem__)

    material = SimpleNamespace(name="Steel")
    body = SimpleNamespace(
        name="Part", volume=1, area=6, material=material, isVisible=True
    )
    root = SimpleNamespace(
        name="Root", bRepBodies=collection([body]), allOccurrences=[]
    )
    nested_component = SimpleNamespace(
        name="Nested",
        sketches=collection(
            [
                SimpleNamespace(
                    name="Sketch",
                    profiles=collection([object()]),
                    isVisible=True,
                )
            ]
        ),
        features=collection([object()]),
    )
    for path, visible in (("Nested:1", True), ("Nested:2", False)):
        proxy = SimpleNamespace(
            name="Part", volume=1, area=6, material=material, isVisible=True
        )
        root.allOccurrences.append(
            SimpleNamespace(
                fullPathName=path,
                component=nested_component,
                bRepBodies=collection([proxy]),
                isVisible=visible,
            )
        )
    design = SimpleNamespace(
        parentDocument=SimpleNamespace(name="Assembly"),
        productType="Design",
        rootComponent=root,
        allComponents=collection(
            [
                SimpleNamespace(
                    name="Root", sketches=collection([]), features=collection([])
                ),
                nested_component,
            ]
        ),
        timeline=collection([object(), object()]),
    )
    namespace = {}
    node = _method("get_scene_info")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    handler = SimpleNamespace(
        _design=lambda: design,
        _root=lambda: root,
        _camera_info=lambda: {"eye": [0, 0, 1]},
    )
    result = namespace["get_scene_info"](handler)
    assert result["bodies_count"] == 3
    assert [item["occurrence_path"] for item in result["bodies"]] == [
        "root",
        "Nested:1",
        "Nested:2",
    ]
    assert result["bodies"][-1]["is_visible"] is False
    assert result["sketches"] == [
        {
            "name": "Sketch",
            "component_name": "Nested",
            "profile_count": 1,
            "is_visible": True,
        }
    ]
    assert result["components_count"] == 3


@pytest.mark.parametrize("nonuniform", [False, True])
@pytest.mark.parametrize("failure", ["", "input", "nonuniform", "feature"])
def test_scale_uses_owned_sketch_point_and_documented_input(nonuniform, failure):
    import math

    events = []
    anchor = object()
    sketch = SimpleNamespace(
        sketchPoints=SimpleNamespace(add=lambda point: anchor),
        modelToSketchSpace=lambda point: point,
        deleteMe=lambda: events.append("cleanup"),
    )
    scale_input = SimpleNamespace(
        setToNonUniform=lambda *values: (
            events.append(("nonuniform", values)) or failure != "nonuniform"
        )
    )

    def create_input(bodies, point, factor):
        assert bodies == [native]
        assert point is anchor
        events.append(("input", factor))
        return None if failure == "input" else scale_input

    scales = SimpleNamespace(
        createInput=create_input,
        add=lambda value: (
            None if failure == "feature" else SimpleNamespace(name="Scale1")
        ),
    )
    owner = SimpleNamespace(
        features=SimpleNamespace(scaleFeatures=scales), xYConstructionPlane=object(),
        sketches=SimpleNamespace(add=lambda plane: sketch),
    )
    native = SimpleNamespace(parentComponent=owner, isSolid=True)
    body = SimpleNamespace(nativeObject=native, assemblyContext=None)

    class Collection(list):
        def add(self, value):
            self.append(value)

    namespace = {"math": math, "adsk": SimpleNamespace(
        core=SimpleNamespace(
            ObjectCollection=SimpleNamespace(create=Collection),
            Point3D=SimpleNamespace(create=lambda *coordinates: coordinates),
            ValueInput=SimpleNamespace(createByReal=lambda value: value),
        ),
        fusion=SimpleNamespace(DesignTypes=SimpleNamespace(ParametricDesignType=1)),
    )}
    exec(compile(ast.Module(body=[_method("scale_body")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    handler = SimpleNamespace(
        _design=lambda: SimpleNamespace(designType=1),
        _body_by_name=lambda name: body,
    )
    arguments = {"scale_x": 2, "scale_y": 3, "scale_z": .5} if nonuniform else {}
    fails = failure in {"input", "feature"} or (nonuniform and failure == "nonuniform")
    if fails:
        with pytest.raises(RuntimeError):
            namespace["scale_body"](handler, "Part", 2, **arguments)
        assert "cleanup" in events
    else:
        assert namespace["scale_body"](handler, "Part", 2, **arguments)[
            "feature_name"
        ] == "Scale1"
        assert sketch.isVisible is False
        assert "cleanup" not in events
    assert ("input", 2) in events


@pytest.mark.parametrize("arguments", [
    {"scale": 0}, {"scale": float("nan")}, {"scale": True},
    {"scale": 2, "scale_x": 3}, {"scale": 2, "anchor_z": float("inf")},
    {"scale": 2, "scale_x": 1, "scale_y": -1, "scale_z": 1},
])
def test_scale_invalid_values_reject_before_api_access(arguments):
    import math

    namespace = {"math": math}
    exec(compile(ast.Module(body=[_method("scale_body")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    with pytest.raises(ValueError):
        namespace["scale_body"](SimpleNamespace(), "Part", **arguments)


def test_scale_rejects_direct_history_before_body_lookup():
    import math

    namespace = {"math": math, "adsk": SimpleNamespace(
        fusion=SimpleNamespace(DesignTypes=SimpleNamespace(ParametricDesignType=1))
    )}
    exec(compile(ast.Module(body=[_method("scale_body")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    with pytest.raises(ValueError, match="parametric"):
        namespace["scale_body"](
            SimpleNamespace(_design=lambda: SimpleNamespace(designType=0)), "Part", 2
        )


@pytest.mark.parametrize("direction,signed,symmetric", [
    ("positive", .2, False), ("negative", -.2, False), ("symmetric", .2, True),
])
def test_thicken_uses_native_owner_direction_and_symmetric_argument(
    direction, signed, symmetric
):
    import math

    calls = []
    face = object()
    thicken_input = SimpleNamespace()

    class Collection(list):
        def add(self, value):
            self.append(value)

    def create_input(faces, value, symmetry, operation, chain):
        calls.append((list(faces), value, symmetry, operation, chain))
        return thicken_input

    owner = SimpleNamespace(features=SimpleNamespace(thickenFeatures=SimpleNamespace(
        createInput=create_input, add=lambda value: SimpleNamespace(name="Thicken1")
    )))
    native = SimpleNamespace(isSolid=False, parentComponent=owner, faces=[face])
    handler = SimpleNamespace(_body_by_name=lambda name: SimpleNamespace(
        nativeObject=native
    ))
    namespace = {"math": math, "adsk": SimpleNamespace(
        core=SimpleNamespace(
            ObjectCollection=SimpleNamespace(create=Collection),
            ValueInput=SimpleNamespace(createByString=lambda value: value),
        ),
        fusion=SimpleNamespace(FeatureOperations=SimpleNamespace(NewBodyFeatureOperation=1)),
    )}
    exec(compile(ast.Module(body=[_method("thicken_surface")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    assert namespace["thicken_surface"](handler, "Patch", .2, direction)[
        "feature_name"
    ] == "Thicken1"
    distance = .1 if symmetric else signed
    assert calls == [([face], f"{distance:.17g} cm", symmetric, 1, False)]


@pytest.mark.parametrize("thickness,direction", [
    (0, "positive"), (float("nan"), "positive"), (.2, "unsupported"),
])
def test_thicken_invalid_input_rejects_before_body_lookup(thickness, direction):
    import math

    namespace = {"math": math}
    exec(compile(ast.Module(body=[_method("thicken_surface")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    with pytest.raises(ValueError):
        namespace["thicken_surface"](SimpleNamespace(), "Patch", thickness, direction)


@pytest.mark.parametrize("initial,target", [(1, "parametric"), (0, "direct"),
                                           (0, "parametric"), (1, "direct")])
def test_design_type_handler_roundtrip_and_noop(initial, target):
    design = SimpleNamespace(designType=initial)
    events = []
    namespace = {"adsk": SimpleNamespace(
        fusion=SimpleNamespace(DesignTypes=SimpleNamespace(
            ParametricDesignType=1, DirectDesignType=0,
        )), doEvents=lambda: events.append("event"),
    )}
    for name in ("set_design_type", "get_design_type"):
        exec(compile(ast.Module(body=[_method(name)], type_ignores=[]),
                     str(HANDLER), "exec"), namespace)
    handler = SimpleNamespace(_design=lambda: design)
    expected = 1 if target == "parametric" else 0
    result = namespace["set_design_type"](handler, target)
    assert result["changed"] is (initial != expected)
    assert design.designType == expected
    assert events == (["event"] if initial != expected else [])
    assert namespace["get_design_type"](handler) == {
        "design_type": target, "design_type_id": expected,
    }
    with pytest.raises(RuntimeError, match="Invalid design_type"):
        namespace["set_design_type"](handler, "invalid")
    assert design.designType == expected


def test_design_type_failed_parametric_switch_is_not_reported_success():
    class RefusingDesign:
        @property
        def designType(self):
            return 0

        @designType.setter
        def designType(self, value):
            pass

    namespace = {"adsk": SimpleNamespace(
        fusion=SimpleNamespace(DesignTypes=SimpleNamespace(
            ParametricDesignType=1, DirectDesignType=0,
        )), doEvents=lambda: None,
    )}
    exec(compile(ast.Module(body=[_method("set_design_type")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    with pytest.raises(RuntimeError, match="Failed to switch"):
        namespace["set_design_type"](
            SimpleNamespace(_design=lambda: RefusingDesign()), "parametric"
        )


@pytest.mark.parametrize("first", ["NestedBody", "1,2,3", "nan,2,3",
                                   "1,2", "Ambiguous", "Missing"])
def test_distance_uses_unique_body_resolver_and_actual_api_positions(first):
    import math

    calls = []
    body = object()

    def lookup(name):
        if name == "NestedBody":
            return body
        if name == "Ambiguous":
            raise ValueError("ambiguous body")
        raise RuntimeError("not found")

    def measure(entity_one, entity_two):
        calls.append((entity_one, entity_two))
        return SimpleNamespace(value=5, positionOne=SimpleNamespace(x=1, y=2, z=3),
                               positionTwo=SimpleNamespace(x=4, y=6, z=3))

    namespace = {"math": math, "adsk": SimpleNamespace(core=SimpleNamespace(
        Point3D=SimpleNamespace(create=lambda *values: values)
    ))}
    exec(compile(ast.Module(body=[_method("measure_distance")], type_ignores=[]),
                 str(HANDLER), "exec"), namespace)
    handler = SimpleNamespace(_body_by_name=lookup, app=SimpleNamespace(
        measureManager=SimpleNamespace(measureMinimumDistance=measure)
    ))
    if first in {"NestedBody", "1,2,3"}:
        assert namespace["measure_distance"](handler, first, "4,6,3") == {
            "distance": 5, "point_one": [1, 2, 3], "point_two": [4, 6, 3],
        }
        assert calls == [(body if first == "NestedBody" else (1., 2., 3.),
                          (4., 6., 3.))]
    else:
        with pytest.raises((ValueError, RuntimeError)):
            namespace["measure_distance"](handler, first, "4,6,3")
        assert calls == []


def test_legacy_body_lookup_rejects_duplicate_names(object_info_case):
    method, handler, root, component, collection = object_info_case
    namespace = {}
    node = _method("_body_by_name")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    lookup = namespace["_body_by_name"]
    assert lookup(handler, "Part") is component.bRepBodies.item(0)
    assert lookup(handler, "Part", "Nested:1") is component.bRepBodies.item(0)
    root.bRepBodies = component.bRepBodies
    with pytest.raises(ValueError, match="ambiguous"):
        lookup(handler, "Part")
    assert lookup(handler, "Part", "root") is root.bRepBodies.item(0)
    with pytest.raises(RuntimeError, match="not found"):
        lookup(handler, "Missing")


def test_legacy_component_lookup_rejects_duplicate_component_names(object_info_case):
    method, handler, root, component, collection = object_info_case
    namespace = {}
    node = _method("_component_by_name")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    lookup = namespace["_component_by_name"]
    assert lookup(handler, "Nested") is component
    root.name = component.name
    with pytest.raises(ValueError, match="ambiguous"):
        lookup(handler, "Nested")


def test_legacy_component_lookup_uses_unique_component_not_occurrence_count(
    object_info_case,
):
    method, handler, root, component, collection = object_info_case
    root.allOccurrences.append(root.allOccurrences[0])
    namespace = {}
    node = _method("_component_by_name")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    assert namespace["_component_by_name"](handler, "Nested") is component


def test_select_edges_accepts_explicit_current_indices_and_rejects_stale_indices():
    class ObjectCollection:
        def __init__(self):
            self.items = []

        def add(self, value):
            self.items.append(value)

        @property
        def count(self):
            return len(self.items)

    edges = [SimpleNamespace(nativeObject=None) for _ in range(3)]

    class EdgeCollection(list):
        @property
        def count(self):
            return len(self)

        def item(self, index):
            return self[index]

    body = SimpleNamespace(edges=EdgeCollection(edges), boundingBox=object())
    collection = ObjectCollection()
    namespace = {
        "adsk": SimpleNamespace(
            core=SimpleNamespace(
                ObjectCollection=SimpleNamespace(create=lambda: collection)
            )
        )
    }
    node = _method("_select_edges")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    assert namespace["_select_edges"](None, body, "explicit", [2, 0]) is collection
    assert collection.items == [edges[2], edges[0]]
    for indices in ([], [0, 0], [-1], [3], [True], list(range(201))):
        with pytest.raises(ValueError, match="Edge indices"):
            namespace["_select_edges"](None, body, "explicit", indices)


def test_mirror_forwards_explicit_occurrence_path():
    body = object()
    feature_input = object()
    feature = SimpleNamespace(name="Mirror1")
    plane = object()
    body_collection = SimpleNamespace(add=Mock())
    mirror_features = SimpleNamespace(
        createInput=Mock(return_value=feature_input),
        add=Mock(return_value=feature),
    )
    root = SimpleNamespace(
        features=SimpleNamespace(mirrorFeatures=mirror_features)
    )
    handler = SimpleNamespace(
        _root=Mock(return_value=root),
        _body_by_name=Mock(return_value=body),
        _construction_plane=Mock(return_value=plane),
    )
    create_collection = Mock(return_value=body_collection)
    namespace = {
        "adsk": SimpleNamespace(
            core=SimpleNamespace(
                ObjectCollection=SimpleNamespace(create=create_collection)
            )
        )
    }
    method = _method("mirror")
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )

    result = namespace["mirror"](
        handler, "yz", "NestedPart", occurrence_path="Assembly:1+Part:1"
    )

    assert result["feature_name"] == "Mirror1"
    assert handler._body_by_name.call_args == mock_call(
        "NestedPart", "Assembly:1+Part:1"
    )
    assert body_collection.add.call_args == mock_call(body)
    mirror_features.createInput.assert_called_once_with(body_collection, plane)
    mirror_features.add.assert_called_once_with(feature_input)


def test_fillet_and_chamfer_use_selected_body_owner_component():
    edges = SimpleNamespace(count=1)
    body = SimpleNamespace(nativeObject=None, edges=edges)
    body.parentComponent = SimpleNamespace(features=SimpleNamespace())
    fillet_input = SimpleNamespace(addConstantRadiusEdgeSet=Mock())
    fillet_feature = SimpleNamespace(name="Fillet1")
    body.parentComponent.features.filletFeatures = SimpleNamespace(
        createInput=Mock(return_value=fillet_input),
        add=Mock(return_value=fillet_feature),
    )
    chamfer_input = SimpleNamespace(setToEqualDistance=Mock())
    chamfer_feature = SimpleNamespace(name="Chamfer1")
    body.parentComponent.features.chamferFeatures = SimpleNamespace(
        createInput=Mock(return_value=chamfer_input),
        add=Mock(return_value=chamfer_feature),
    )
    handler = SimpleNamespace(
        _root=Mock(),
        _body_by_name=Mock(return_value=body),
        _select_edges=Mock(return_value=edges),
    )
    namespace = {
        "adsk": SimpleNamespace(
            core=SimpleNamespace(
                ValueInput=SimpleNamespace(createByReal=lambda value: value)
            )
        )
    }
    methods = [_method("fillet"), _method("chamfer")]
    exec(
        compile(ast.Module(body=methods, type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    assert namespace["fillet"](
        handler, 0.1, "NestedPart", edge_indices=[0], occurrence_path="Asm:1"
    )
    assert namespace["chamfer"](
        handler, 0.1, "NestedPart", edge_indices=[0], occurrence_path="Asm:1"
    )
    assert handler._body_by_name.call_args_list == [
        mock_call("NestedPart", "Asm:1"),
        mock_call("NestedPart", "Asm:1"),
    ]
    handler._root.assert_not_called()


def test_shell_explicit_face_indices_use_body_owner_and_validate_before_feature():
    class ObjectCollection:
        def __init__(self):
            self.items = []

        def add(self, item):
            self.items.append(item)

        @property
        def count(self):
            return len(self.items)

    face_native = object()
    face = SimpleNamespace(nativeObject=face_native)
    face_collection = SimpleNamespace(count=1, item=lambda index: face)
    owner = SimpleNamespace(features=SimpleNamespace())
    native_body = SimpleNamespace(isSolid=True, parentComponent=owner)
    body = SimpleNamespace(name="Part", nativeObject=native_body, faces=face_collection)
    feature = SimpleNamespace(name="Shell1")
    feature_input = SimpleNamespace()
    shells = SimpleNamespace(
        createInput=Mock(return_value=feature_input), add=Mock(return_value=feature)
    )
    owner.features.shellFeatures = shells
    collections = []

    def create_collection():
        collection = ObjectCollection()
        collections.append(collection)
        return collection
    namespace = {
        "adsk": SimpleNamespace(
            core=SimpleNamespace(
                ObjectCollection=SimpleNamespace(create=create_collection),
                ValueInput=SimpleNamespace(createByReal=lambda value: value),
            )
        )
    }
    node = _method("shell")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    handler = SimpleNamespace(_body_by_name=Mock(return_value=body), _root=Mock())
    result = namespace["shell"](
        handler, .1, "Part", face_indices=[0], occurrence_path="Asm:1"
    )
    assert result["faces_removed"] == 1 and collections[0].items == [face_native]
    assert collections[1].items == [native_body]
    assert feature_input.facesToRemove is collections[0]
    handler._body_by_name.assert_called_once_with("Part", "Asm:1")
    handler._root.assert_not_called()
    with pytest.raises(ValueError, match="face_indices"):
        namespace["shell"](handler, .1, "Part", face_indices=[2])


def test_sketch_lookup_selects_named_component_and_rejects_duplicate_names():
    def collection(items):
        return SimpleNamespace(count=len(items), item=items.__getitem__)

    root_sketch = SimpleNamespace(name="Profile")
    nested_sketch = SimpleNamespace(name="Profile")
    root = SimpleNamespace(name="Root", sketches=collection([root_sketch]))
    nested = SimpleNamespace(name="Nested", sketches=collection([nested_sketch]))
    design = SimpleNamespace(allComponents=collection([root, nested]))
    namespace = {}
    component_lookup = _method("_component_by_name")
    sketch_lookup = _method("_sketch_by_name")
    exec(
        compile(
            ast.Module(body=[component_lookup, sketch_lookup], type_ignores=[]),
            str(HANDLER),
            "exec",
        ),
        namespace,
    )
    handler = SimpleNamespace(_root=lambda: root, _design=lambda: design)
    handler._component_by_name = lambda name: namespace["_component_by_name"](
        handler, name
    )
    lookup = namespace["_sketch_by_name"]
    assert lookup(handler, "Profile", "Nested") is nested_sketch
    with pytest.raises(ValueError, match="ambiguous"):
        lookup(handler, "Profile")
    with pytest.raises(RuntimeError, match="not found"):
        lookup(handler, "Missing", "Nested")


def test_create_sketch_uses_explicit_component_local_plane():
    class Collection:
        def __init__(self):
            self.values = []
            self.count = 0

        def add(self, selected_plane):
            self.selected_plane = selected_plane
            self.values.append(sketch)
            self.count = len(self.values)
            return sketch

        def item(self, index):
            return self.values[index]

    sketch = SimpleNamespace(name="SketchYZ")
    plane = object()
    sketches = Collection()
    owner = SimpleNamespace(name="Part", sketches=sketches)
    handler = SimpleNamespace(
        _root=lambda: owner,
        _component_by_name=lambda name: owner if name == "Part" else None,
        _construction_plane=lambda plane_name, component_name: plane,
    )
    namespace = {}
    node = _method("create_sketch")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    result = namespace["create_sketch"](handler, plane="yz", component_name="Part")
    assert sketches.item(0) is sketch and sketches.selected_plane is plane
    assert result["sketch_name"] == "SketchYZ" and result["component_name"] == "Part"


@pytest.mark.parametrize(
    "method_name,arguments,sketch_argument",
    [
        ("draw_rectangle", {"width": 1, "height": 1}, "sketch_name"),
        ("draw_circle", {"radius": 1}, "sketch_name"),
        (
            "draw_line",
            {"start_x": 0, "start_y": 0, "end_x": 1, "end_y": 1},
            "sketch_name",
        ),
        (
            "draw_arc",
            {
                "center_x": 0,
                "center_y": 0,
                "start_x": 1,
                "start_y": 0,
                "sweep_angle": 90,
            },
            "sketch_name",
        ),
        (
            "draw_spline",
            {"spline_type": "fit_points", "points": [[0, 0], [1, 1]]},
            "sketch_name",
        ),
        ("create_polygon", {"sides": 4, "radius": 1}, "sketch_name"),
        ("add_constraint", {"constraint_type": "fix", "entity_one": 0}, "sketch_name"),
        ("auto_constrain", {}, "sketch_name"),
        (
            "add_dimension",
            {"dimension_type": "radial", "value": 1, "entity_one": 0},
            "sketch_name",
        ),
        ("offset_curve", {"curve_index": 0, "offset_distance": 0.1}, "sketch_name"),
        ("trim_curve", {"curve_index": 0, "point_x": 0, "point_y": 0}, "sketch_name"),
        ("extend_curve", {"curve_index": 0, "point_x": 0, "point_y": 0}, "sketch_name"),
        ("project_geometry", {"source_name": "Body"}, "sketch_name"),
        ("extrude", {"height": 1}, "sketch_name"),
        ("revolve", {"angle": 90}, "sketch_name"),
        (
            "sweep",
            {
                "profile_index": 0,
                "path_sketch_name": "Path",
                "profile_sketch_name": "Profile",
            },
            "profile_sketch_name",
        ),
        ("loft", {"profile_sketch_names": ["One", "Two"]}, "profile_sketch_names"),
    ],
)
def test_sketch_operations_forward_explicit_component_selector(
    method_name, arguments, sketch_argument
):
    class SelectedTarget(Exception):
        pass

    selection = Mock(side_effect=SelectedTarget)
    handler = SimpleNamespace(
        _sketch_by_name=selection,
        _last_sketch=Mock(side_effect=SelectedTarget),
    )
    namespace = {}
    node = _method(method_name)
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    arguments = {**arguments, "component_name": "RotatedPart"}
    if sketch_argument == "profile_sketch_names":
        arguments[sketch_argument] = ["One", "Two"]
    else:
        arguments[sketch_argument] = "SelectedSketch"
    with pytest.raises(SelectedTarget):
        namespace[method_name](handler, **arguments)
    if method_name == "loft":
        selection.assert_called_once_with("One", "RotatedPart")
    else:
        selection.assert_called_once_with("SelectedSketch", "RotatedPart")


def test_scene_info_enumerates_occurrence_instances_and_component_sketches():
    class Collection:
        def __init__(self, values):
            self.values = values
            self.count = len(values)

        def item(self, index):
            return self.values[index]

    def body(name, visible=True):
        return SimpleNamespace(
            name=name, volume=1, area=6, material=None, isVisible=visible
        )

    sketch = SimpleNamespace(
        name="Sketch", profiles=Collection([object()]), isVisible=True
    )
    nested = SimpleNamespace(
        name="Nested", sketches=Collection([sketch]), features=Collection([object()])
    )
    root = SimpleNamespace(
        name="Root", bRepBodies=Collection([body("RootBody")]), allOccurrences=[]
    )
    root.allOccurrences.extend(
        [
            SimpleNamespace(
                fullPathName="Nested:1",
                component=nested,
                bRepBodies=Collection([body("NestedBody")]),
                isVisible=True,
            ),
            SimpleNamespace(
                fullPathName="Nested:2",
                component=nested,
                bRepBodies=Collection([body("NestedBody")]),
                isVisible=False,
            ),
        ]
    )
    root_component = SimpleNamespace(
        name="Root", sketches=Collection([]), features=Collection([])
    )
    design = SimpleNamespace(
        parentDocument=SimpleNamespace(name="Assembly"),
        productType="Design",
        allComponents=Collection([root_component, nested]),
        timeline=Collection([]),
    )
    namespace = {}
    node = _method("get_scene_info")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    handler = SimpleNamespace(
        _design=lambda: design, _root=lambda: root, _camera_info=lambda: {}
    )
    result = namespace["get_scene_info"](handler)
    assert result["bodies_count"] == 3
    assert result["components_count"] == 3
    assert [body["occurrence_path"] for body in result["bodies"]] == [
        "root",
        "Nested:1",
        "Nested:2",
    ]
    assert [body["is_visible"] for body in result["bodies"]] == [True, True, False]
    assert result["sketches"][0]["component_name"] == "Nested"


def test_appearance_invalid_target_does_not_copy_library_material():
    appearance = SimpleNamespace(name="AvailableAppearance")
    library = SimpleNamespace(
        appearances=SimpleNamespace(count=1, item=lambda index: appearance)
    )
    local_appearances = SimpleNamespace(
        itemByName=Mock(return_value=None), addByCopy=Mock(return_value=object())
    )
    handler = SimpleNamespace(
        app=SimpleNamespace(
            materialLibraries=SimpleNamespace(itemByName=Mock(return_value=library))
        ),
        _design=lambda: SimpleNamespace(appearances=local_appearances),
        _body_by_name=Mock(side_effect=ValueError("ambiguous target")),
    )
    namespace = {}
    node = _method("set_appearance")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    with pytest.raises(ValueError, match="ambiguous"):
        namespace["set_appearance"](handler, "Part", "AvailableAppearance")
    local_appearances.addByCopy.assert_not_called()


@pytest.mark.parametrize(
    "target_type,face_index", [("invalid", None), ("face", -1), ("face", 2)]
)
def test_appearance_preflight_rejects_invalid_entity_before_library_access(
    target_type, face_index
):
    library = Mock()
    handler = SimpleNamespace(
        app=SimpleNamespace(materialLibraries=library),
        _body_by_name=lambda name: SimpleNamespace(faces=SimpleNamespace(count=1)),
    )
    namespace = {}
    node = _method("set_appearance")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    with pytest.raises(ValueError):
        namespace["set_appearance"](
            handler, "Part", "Appearance", target_type, face_index
        )
    library.itemByName.assert_not_called()


@pytest.mark.parametrize("target_type", ["body", "component", "face"])
def test_appearance_assigns_only_validated_target(target_type):
    target = SimpleNamespace(appearance=None)
    body = SimpleNamespace(faces=SimpleNamespace(count=1, item=lambda index: target))
    appearance = SimpleNamespace(name="Appearance")
    local = object()
    library = SimpleNamespace(
        appearances=SimpleNamespace(count=1, item=lambda index: appearance)
    )
    appearances = SimpleNamespace(itemByName=lambda name: local)
    handler = SimpleNamespace(
        app=SimpleNamespace(
            materialLibraries=SimpleNamespace(itemByName=lambda name: library)
        ),
        _design=lambda: SimpleNamespace(appearances=appearances),
        _body_by_name=lambda name: body if target_type == "face" else target,
        _component_by_name=lambda name: target,
    )
    namespace = {}
    node = _method("set_appearance")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    result = namespace["set_appearance"](handler, "Part", "Appearance", target_type, 0)
    assert result["applied"] and target.appearance is local


@pytest.mark.parametrize("method_name", ["execute_command", "execute_code"])
def test_disabled_execution_before_any_fusion_access(method_name):
    node = _method(method_name)
    namespace = {}
    compiled = compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec")
    exec(compiled, namespace)
    stub = SimpleNamespace(DISABLED_COMMANDS=frozenset({"execute_code"}))
    argument = (
        {"type": "execute_code", "params": {"code": "raise RuntimeError()"}}
        if method_name == "execute_command"
        else "raise RuntimeError()"
    )
    result = namespace[method_name](stub, argument)
    assert result["error_kind"] == "INVALID_INPUT"
    assert "disabled by policy" in result.get("message", result.get("error_message"))


def test_original_execution_body_is_retained():
    node = _method("execute_code")
    calls = {
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
    }
    assert {"exec", "eval"} <= calls


def test_startup_validates_host_before_constructing_handler():
    tree = ast.parse((REPO_ROOT / "addon/Fusion360MCP.py").read_text(encoding="utf-8"))
    calls = {
        child.func.id: child.lineno
        for child in ast.walk(tree)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id in {"validate_host", "CommandHandler", "Fusion360MCPServer"}
    }
    assert calls["validate_host"] < calls["CommandHandler"]
    assert calls["CommandHandler"] < calls["Fusion360MCPServer"]


def _called_attrs(node: ast.AST) -> set[str]:
    """Every ``x.name(...)`` attribute name called within *node*."""
    return {
        n.func.attr
        for n in ast.walk(node)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }


def _has_silent_except(node: ast.AST) -> bool:
    """True if any handler's whole body is ``pass``."""
    for handler in (n for n in ast.walk(node) if isinstance(n, ast.ExceptHandler)):
        if all(isinstance(stmt, ast.Pass) for stmt in handler.body):
            return True
    return False


class TestDeleteAll:
    def test_deletes_via_the_timeline_entity(self):
        """TimelineObject has no deleteMe(); the entity it wraps does.

        Calling deleteMe() on the TimelineObject raises AttributeError on
        every item, so delete_all removed nothing at all.
        """
        node = _method("delete_all")
        attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        assert "entity" in attrs, (
            "delete_all must reach the feature through TimelineObject.entity; "
            "TimelineObject itself has no deleteMe()"
        )

    def test_does_not_swallow_failures(self):
        node = _method("delete_all")
        assert not _has_silent_except(node), (
            "delete_all must not use a bare 'except: pass' — that is what let "
            "it report success while deleting nothing"
        )

    def test_reports_what_it_did(self):
        """The return value must carry enough to tell success from a no-op."""
        node = _method("delete_all")
        returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
        assert returns, "delete_all must return a result"
        keys: set[str] = set()
        for ret in returns:
            if isinstance(ret.value, ast.Dict):
                keys |= {k.value for k in ret.value.keys if isinstance(k, ast.Constant)}
        assert "remaining" in keys, (
            "delete_all should report what is still in the design, so a "
            "partial failure is visible to the caller"
        )


class TestCheckInterference:
    def test_uses_the_design_level_api(self):
        """Component.interfere() does not exist; the API is on Design."""
        node = _method("check_interference")
        called = _called_attrs(node)
        assert "interfere" not in called, (
            "Component.interfere() does not exist in the Fusion API — use "
            "Design.createInterferenceInput() + Design.analyzeInterference()"
        )
        assert {"createInterferenceInput", "analyzeInterference"} <= called, (
            "check_interference must go through the Design-level interference API"
        )

    def test_iterates_results_as_a_collection(self):
        """analyzeInterference returns a collection with .count / .item()."""
        node = _method("check_interference")
        attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        assert "interferenceResultCount" not in attrs, (
            "interferenceResultCount belongs to the old, non-existent API"
        )


class TestDraftFaces:
    """``DraftFeatures.createInput(inputFaces, plane, isTangentChain)``.

    ``inputFaces`` is a BRepFace *array* — an ObjectCollection is rejected —
    and the angle is not a parameter at all; it goes on the returned input via
    ``setSingleAngle(isSymmetric, angle)``. Passing four arguments raised
    "Wrong number or type of arguments for overloaded function", so every
    ``draft_faces`` call failed.
    """

    def test_create_input_takes_three_arguments(self):
        node = _method("draft_faces")
        calls = [
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "createInput"
        ]
        assert calls, "draft_faces must build a DraftFeatureInput"
        for call in calls:
            assert len(call.args) == 3, (
                "DraftFeatures.createInput takes (inputFaces, plane, "
                "isTangentChain); the angle is not a createInput parameter"
            )

    def test_sets_the_angle_on_the_input(self):
        node = _method("draft_faces")
        assert "setSingleAngle" in _called_attrs(node), (
            "the draft angle must be applied with setSingleAngle(isSymmetric, "
            "angle) on the DraftFeatureInput, not passed to createInput"
        )

    def test_passes_faces_as_an_array(self):
        node = _method("draft_faces")
        builds_a_list = any(
            isinstance(n, (ast.ListComp, ast.List)) for n in ast.walk(node)
        )
        assert builds_a_list, (
            "inputFaces must be a BRepFace array — _select_faces returns an "
            "ObjectCollection, which createInput rejects"
        )

    def test_does_not_swallow_failures(self):
        node = _method("draft_faces")
        assert not _has_silent_except(node), (
            "draft_faces must not use a bare 'except: pass'"
        )


@pytest.fixture
def step_export():
    body = SimpleNamespace(assemblyContext=None)
    manager = SimpleNamespace(
        createSTEPExportOptions=Mock(return_value=object()), execute=Mock()
    )
    root = SimpleNamespace(
        bRepBodies=SimpleNamespace(add=Mock(return_value=SimpleNamespace(name="")))
    )
    design = SimpleNamespace(rootComponent=root, exportManager=manager)
    source = SimpleNamespace(activate=Mock(return_value=True))
    scratch = SimpleNamespace(close=Mock(return_value=True))
    app = SimpleNamespace(
        activeDocument=source,
        activeProduct=design,
        documents=SimpleNamespace(add=Mock(return_value=scratch)),
    )
    namespace = {
        "os": os,
        "Path": Path,
        "adsk": SimpleNamespace(
            core=SimpleNamespace(
                DocumentTypes=SimpleNamespace(FusionDesignDocumentType=7)
            ),
            fusion=SimpleNamespace(
                TemporaryBRepManager=SimpleNamespace(
                    get=lambda: SimpleNamespace(copy=lambda target: object())
                ),
                Design=SimpleNamespace(cast=lambda product: product),
                DesignTypes=SimpleNamespace(DirectDesignType=0),
            ),
        ),
    }
    node = _method("export_step")
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(HANDLER), "exec"),
        namespace,
    )
    handler = SimpleNamespace(
        _body_by_name=Mock(return_value=body),
        _design=lambda: SimpleNamespace(exportManager=manager),
        app=app,
    )
    return namespace["export_step"], handler, manager


def test_step_export_filename_only_resolves_to_working_directory(
    step_export, tmp_path, monkeypatch
):
    method, handler, manager = step_export
    monkeypatch.chdir(tmp_path)

    def execute(options):
        (tmp_path / "part.step").write_text(
            "ISO-10303-21;\nEND-ISO-10303-21;", encoding="ascii"
        )
        return True

    manager.execute.side_effect = execute
    result = method(handler, "Part", "part.step")
    assert result["exported"] is True
    assert Path(result["file_path"]) == tmp_path / "part.step"
    assert (
        manager.createSTEPExportOptions.call_args.args[1]
        is handler.app.activeProduct.rootComponent
    )
    handler.app.documents.add.return_value.close.assert_called_once_with(False)
    handler.app.activeDocument.activate.assert_called_once()


def test_step_export_rejected_by_fusion_is_not_success(step_export, tmp_path):
    method, handler, manager = step_export
    manager.execute.return_value = False
    with pytest.raises(RuntimeError, match="STEP export failed"):
        method(handler, "Part", str(tmp_path / "part.step"))
    handler.app.documents.add.return_value.close.assert_called_once_with(False)
    handler.app.activeDocument.activate.assert_called_once()


def test_step_export_success_without_output_is_not_success(step_export, tmp_path):
    method, handler, manager = step_export
    manager.execute.return_value = True
    with pytest.raises(RuntimeError, match="output"):
        method(handler, "Part", str(tmp_path / "part.step"))


@pytest.mark.parametrize("destination", ["", "   "])
def test_step_export_rejects_empty_path_before_document_creation(
    step_export, destination
):
    method, handler, manager = step_export
    with pytest.raises(ValueError, match="nonempty"):
        method(handler, "Part", destination)
    handler.app.documents.add.assert_not_called()
    manager.execute.assert_not_called()


def test_step_export_preserves_existing_output(step_export, tmp_path):
    method, handler, manager = step_export
    destination = tmp_path / "existing.step"
    destination.write_text("user-owned", encoding="ascii")
    with pytest.raises(ValueError, match="already exists"):
        method(handler, "Part", str(destination))
    assert destination.read_text(encoding="ascii") == "user-owned"
    handler.app.documents.add.assert_not_called()


def test_step_export_exception_restores_source_document(step_export, tmp_path):
    method, handler, manager = step_export
    manager.execute.side_effect = RuntimeError("translator error")
    with pytest.raises(RuntimeError, match="translator error"):
        method(handler, "Part", str(tmp_path / "failed.step"))
    handler.app.documents.add.return_value.close.assert_called_once_with(False)
    handler.app.activeDocument.activate.assert_called_once()


def test_step_export_expands_home_path(step_export, tmp_path, monkeypatch):
    method, handler, manager = step_export
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    def execute(options):
        (tmp_path / "part.step").write_text("STEP", encoding="ascii")
        return True

    manager.execute.side_effect = execute
    result = method(handler, "Part", "~/part.step")
    assert Path(result["file_path"]) == tmp_path / "part.step"


def test_step_export_empty_file_is_not_success(step_export, tmp_path):
    method, handler, manager = step_export

    def execute(options):
        (tmp_path / "empty.step").touch()
        return True

    manager.execute.side_effect = execute
    with pytest.raises(RuntimeError, match="output"):
        method(handler, "Part", str(tmp_path / "empty.step"))
