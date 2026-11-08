"""Exercise candidate calculations and errors without simulating live acceptance."""

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


class Collection:
    def __init__(self, values):
        self.values = values
        self.count = len(values)

    def item(self, index):
        return self.values[index]


@pytest.fixture
def queries():
    path = Path(__file__).resolve().parents[1] / "addon/server/mechanical_queries.py"
    spec = importlib.util.spec_from_file_location("_mechanical_queries", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def design():
    features = Collection(
        [
            SimpleNamespace(
                name="Extrude1",
                objectType="Feature",
                healthState=0,
                errorOrWarningMessage="",
            ),
            SimpleNamespace(
                name="Fillet1",
                objectType="Feature",
                healthState=1,
                errorOrWarningMessage="warning",
            ),
        ]
    )
    component = SimpleNamespace(name="Root", features=features)
    return SimpleNamespace(
        rootComponent=component, allComponents=Collection([component])
    )


def test_paginated_feature_health(queries, design):
    first = queries.feature_health(design, limit=1)
    assert first["total"] == 2 and first["next_offset"] == 1
    second = queries.feature_health(design, component_name="Root", offset=1)
    assert second["features"][0]["message"] == "warning"
    assert second["next_offset"] is None


def test_design_parameters_include_driving_roles_and_components(queries):
    parameters = Collection([
        SimpleNamespace(
            name="BottleDiameter", expression="58 mm", unit="mm", value=5.8,
            valueType=0, objectType="adsk::fusion::UserParameter",
        ),
        SimpleNamespace(
            name="d17", expression="BottleDiameter + 2 mm", unit="mm", value=6.0,
            valueType=0, objectType="adsk::fusion::ModelParameter",
            role="Depth", component=SimpleNamespace(name="NestedShelf"),
            createdBy=SimpleNamespace(
                objectType="adsk::fusion::ExtrudeFeature", name="ShelfExtrude",
                parentComponent=SimpleNamespace(name="NestedShelf"),
            ),
        ),
    ])
    handler = SimpleNamespace(
        app=SimpleNamespace(activeDocument=SimpleNamespace(
            isValid=True, creationId="parameter-test",
        )),
        _design=lambda: SimpleNamespace(allParameters=parameters),
    )
    before = [vars(parameter).copy() for parameter in parameters.values]
    first = queries.get_design_parameters(
        handler, document_id="parameter-test", limit=1,
    )
    assert first["total"] == 2 and first["next_offset"] == 1
    assert first["parameters"][0]["value_internal"] == 5.8
    second = queries.get_design_parameters(
        handler, document_id="parameter-test", offset=1,
    )
    assert second["parameters"] == [{
        "name": "d17", "expression": "BottleDiameter + 2 mm",
        "unit": "mm", "value_internal": 6.0,
        "object_type": "adsk::fusion::ModelParameter",
        "value_type": 0, "component_name": "NestedShelf",
        "role": "Depth", "created_by_type": "adsk::fusion::ExtrudeFeature",
        "created_by_name": "ShelfExtrude", "created_by_component_name": "NestedShelf",
    }]
    assert [vars(parameter) for parameter in parameters.values] == before


def test_parameter_expression_sets_one_inspected_model_parameter(queries):
    class Parameter:
        name = "d17"
        unit = "mm"
        valueType = 0
        objectType = "adsk::fusion::ModelParameter"
        role = "Depth"
        component = SimpleNamespace(name="NestedShelf")
        createdBy = SimpleNamespace(
            objectType="adsk::fusion::ExtrudeFeature", name="ShelfExtrude",
            parentComponent=SimpleNamespace(name="NestedShelf"),
        )
        expression = "60 mm"
        value = 6.0

    parameter = Parameter()
    calls = []
    handler = SimpleNamespace(
        app=SimpleNamespace(activeDocument=SimpleNamespace(
            isValid=True, creationId="parameter-test",
        )),
        _design=lambda: SimpleNamespace(
            allParameters=Collection([parameter]),
            unitsManager=SimpleNamespace(
                isValidExpression=lambda expression, unit:
                calls.append((expression, unit)) or True,
            ),
        ),
    )
    result = queries.set_parameter_expression(
        handler, document_id="parameter-test", name="d17",
        expected_expression="60 mm", expression="BottleDiameter + 2 mm",
    )
    assert parameter.expression == "BottleDiameter + 2 mm"
    assert calls == [("BottleDiameter + 2 mm", "mm")]
    assert result["parameter"]["expression"] == "BottleDiameter + 2 mm"
    assert result["parameter"]["component_name"] == "NestedShelf"


@pytest.mark.parametrize(
    "arguments, count, value_type, object_type, valid",
    [
        ({"document_id": "stale"}, 1, 0, "UserParameter", True),
        ({"name": "missing"}, 1, 0, "UserParameter", True),
        ({"name": ""}, 1, 0, "UserParameter", True),
        ({"expression": " "}, 1, 0, "UserParameter", True),
        ({"expression": 25}, 1, 0, "UserParameter", True),
        ({"expected_expression": "stale"}, 1, 0, "UserParameter", True),
        ({}, 0, 0, "UserParameter", True),
        ({}, 2, 0, "UserParameter", True),
        ({}, 1, 1, "UserParameter", True),
        ({}, 1, 0, "DerivedParameter", True),
        ({}, 1, 0, "UserParameter", False),
    ],
)
def test_invalid_parameter_edits_do_not_change_expressions(
    queries, arguments, count, value_type, object_type, valid,
):
    parameter = SimpleNamespace(
        name="Length", expression="60 mm", unit="mm", value=6.0,
        valueType=value_type, objectType=f"adsk::fusion::{object_type}",
    )
    handler = SimpleNamespace(
        app=SimpleNamespace(activeDocument=SimpleNamespace(
            isValid=True, creationId="parameter-test",
        )),
        _design=lambda: SimpleNamespace(
            allParameters=Collection([parameter] * count),
            unitsManager=SimpleNamespace(
                isValidExpression=lambda expression, unit: valid,
            ),
        ),
    )
    request = {
        "document_id": "parameter-test", "name": "Length",
        "expected_expression": "60 mm", "expression": "100 mm",
        **arguments,
    }
    with pytest.raises(ValueError):
        queries.set_parameter_expression(handler, **request)
    assert parameter.expression == "60 mm"


@pytest.mark.parametrize(
    "arguments",
    [
        {"document_id": "stale"}, {"offset": -1}, {"offset": True},
        {"limit": 0}, {"limit": 201}, {"limit": False},
    ],
)
def test_invalid_parameter_queries_reject_before_reading_design(queries, arguments):
    reads = []
    handler = SimpleNamespace(
        app=SimpleNamespace(activeDocument=SimpleNamespace(
            isValid=True, creationId="parameter-test",
        )),
        _design=lambda: reads.append(True),
    )
    with pytest.raises(ValueError):
        queries.get_design_parameters(
            handler, **{"document_id": "parameter-test", **arguments},
        )
    assert reads == []


def test_parameter_query_returns_text_without_reading_numeric_value(queries):
    parameter = SimpleNamespace(
        name="Label", expression="'Clean'", unit="text", textValue="Clean",
        valueType=1, objectType="adsk::fusion::UserParameter",
    )
    handler = SimpleNamespace(
        app=SimpleNamespace(activeDocument=SimpleNamespace(
            isValid=True, creationId="parameter-test",
        )),
        _design=lambda: SimpleNamespace(allParameters=Collection([parameter])),
    )
    result = queries.get_design_parameters(handler, "parameter-test")
    assert result["parameters"][0]["text_value"] == "Clean"
    assert "value_internal" not in result["parameters"][0]


@pytest.mark.parametrize(
    "params",
    [{"offset": -1}, {"offset": True}, {"limit": 201}, {"component_name": "missing"}],
)
def test_invalid_query_is_rejected(queries, design, params):
    with pytest.raises(ValueError):
        queries.feature_health(design, **params)


def test_ambiguous_component_is_rejected(queries, design):
    design.allComponents = Collection([design.rootComponent, design.rootComponent])
    with pytest.raises(ValueError, match="exactly one"):
        queries.feature_health(design, component_name="Root")


def test_drawing_metadata_and_wrong_product(queries):
    drawing = SimpleNamespace(
        isValid=True,
        activeSheet=SimpleNamespace(name="Sheet1"),
        objectType="adsk::drawing::Drawing",
    )
    app = SimpleNamespace(
        activeProduct=drawing,
        activeDocument=SimpleNamespace(isValid=True, name="Test", creationId="id"),
    )

    def loader(name):
        return SimpleNamespace(Drawing=SimpleNamespace(cast=lambda product: product))

    result = queries.drawing_info(app, loader)
    assert result["active_sheet_name"] == "Sheet1" and result["preview_api"] is True
    app.activeProduct = None
    with pytest.raises(ValueError, match="Activate"):
        queries.drawing_info(app, loader)
    app.activeProduct = drawing
    app.activeDocument.isValid = False
    with pytest.raises(ValueError, match="valid"):
        queries.drawing_info(app, loader)


def test_drawing_product_type_adapter_is_not_used(queries):
    class Drawing(SimpleNamespace):
        @property
        def productType(self):
            raise RuntimeError("InternalValidationError : adapter")

    drawing = Drawing(
        isValid=True,
        activeSheet=SimpleNamespace(name="Sheet1"),
        objectType="adsk::drawing::Drawing",
    )
    app = SimpleNamespace(
        activeProduct=drawing,
        activeDocument=SimpleNamespace(isValid=True, name="Drawing", creationId="id"),
    )

    def loader(name):
        return SimpleNamespace(Drawing=SimpleNamespace(cast=lambda product: product))

    assert queries.drawing_info(app, loader)["object_type"] == "adsk::drawing::Drawing"


@pytest.mark.parametrize(
    "name", ["get_feature_health", "get_document_state", "create_design"]
)
def test_production_wrappers_remove_development_marker(queries, design, name):
    handler_path = (
        Path(__file__).resolve().parents[1] / "addon/server/command_handler.py"
    )
    tree = ast.parse(handler_path.read_text(encoding="utf-8"))
    node = next(
        child for child in ast.walk(tree)
        if isinstance(child, ast.FunctionDef) and child.name == name
    )
    namespace = {"_mechanical_queries": queries}
    compiled = compile(
        ast.Module(body=[node], type_ignores=[]), str(handler_path), "exec"
    )
    exec(compiled, namespace)
    app = SimpleNamespace(activeDocument=SimpleNamespace(
        isValid=True, isSaved=False, creationId="id", name="Unsaved"
    ))
    handler = SimpleNamespace(app=app, _design=lambda: design)
    if name == "create_design":
        from unittest.mock import Mock

        namespace["_mechanical_queries"] = SimpleNamespace(
            create_design=Mock(return_value={"ok": True, "development_only": True})
        )
        result = namespace[name](handler, "MCP_New")
        namespace["_mechanical_queries"].create_design.assert_called_once_with(
            app, "MCP_New"
        )
    else:
        result = namespace[name](handler)
    assert result["ok"] is True
    assert "development_only" not in result
