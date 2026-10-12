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
