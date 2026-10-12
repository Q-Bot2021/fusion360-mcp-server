"""Persistent, isolated CAD development add-in with fixed handler reload."""

import hashlib
import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from types import ModuleType

RUNTIME_PACKAGE = "_fusion360_mcp_development_runtime"
CANDIDATE_MODULES = (
    "hints",
    "hole_geometry",
    "parameter_units",
    "mechanical_queries",
    "command_handler",
)
_server = None
_bridge = None


def load_runtime():
    root = str(Path(__file__).resolve().parent)
    package = sys.modules.get(RUNTIME_PACKAGE)
    if package is None:
        package = ModuleType(RUNTIME_PACKAGE)
        package.__path__ = [root]
        sys.modules[RUNTIME_PACKAGE] = package
    elif getattr(package, "__path__", None) != [root]:
        raise ImportError("Development runtime belongs to another directory")
    return tuple(
        importlib.import_module(f"{RUNTIME_PACKAGE}.server.{name}")
        for name in ("event_bridge", "command_handler", "socket_server")
    )


def reload_handler():
    root = Path(__file__).resolve().parent
    record = json.loads((root / ".fusion-mcp-test-ownership.json").read_text("utf-8"))
    if record.get("kind") != "fusion-mcp-development-fixture":
        raise ImportError("Unrecognized development ownership record")
    modules = []
    hashes = {}
    for name in CANDIDATE_MODULES:
        relative = f"server/{name}.py"
        path = root / relative
        module = sys.modules.get(f"{RUNTIME_PACKAGE}.server.{name}")
        if (
            module is None
            or path.is_symlink()
            or not path.resolve().is_relative_to(root)
            or Path(module.__file__).resolve() != path
        ):
            raise ImportError(f"Invalid fixed candidate module: {name}")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if record.get("files", {}).get(relative) != checksum:
            raise ImportError(f"Candidate differs from staging record: {name}")
        compile(path.read_bytes(), str(path), "exec")
        cache = Path(importlib.util.cache_from_source(str(path)))
        if cache.is_symlink() or not cache.resolve().is_relative_to(root):
            raise ImportError("Unsafe candidate bytecode cache")
        modules.append((module, cache))
        hashes[name] = checksum
    importlib.invalidate_caches()
    for module, cache in modules:
        cache.unlink(missing_ok=True)
        importlib.reload(module)
    handlers = modules[-1][0]
    handler = handlers.CommandHandler()
    handler.__class__._COMMANDS = None
    return handler, hashes


class DevelopmentHandler:
    def __init__(self, cad_handler, reloader=reload_handler, queries=None):
        self.cad_handler = cad_handler
        self.reloader = reloader
        self.generation = 0
        self.queries = queries

    def execute_command(self, command):
        name = command.get("type")
        if name in {
            "save_design",
            "get_body_topology",
            "chamfer_edges",
            "draw_sketch_text",
            "extrude_sketch_entities",
        }:
            return self.cad_handler.execute_command(command)
        if name == "save_design" and self.queries is not None:
            params = command.get("params", {})
            if (
                not isinstance(params, dict)
                or "document_id" not in params
                or set(params)
                - {"document_id", "name", "project_id", "project_name", "description"}
            ):
                return {"status": "error", "message": "Invalid save arguments"}
            return {
                "status": "success",
                "result": self.queries.save_design(self.cad_handler.app, **params),
            }
        if name == "get_body_topology" and self.queries is not None:
            params = command.get("params", {})
            if (
                not isinstance(params, dict)
                or "body_name" not in params
                or set(params) - {"body_name", "offset", "limit"}
            ):
                return {"status": "error", "message": "Invalid topology arguments"}
            return {
                "status": "success",
                "result": self.queries.get_body_topology(self.cad_handler, **params),
            }
        document_operations = {
            "get_document_state": ("document_state", set()),
            "save_sandbox_design": ("save_sandbox_design", {"document_id", "name"}),
            "create_sandbox_drawing": ("create_sandbox_drawing", {"document_id"}),
            "open_sandbox_drawing": ("open_sandbox_drawing", {"data_file_id"}),
        }
        if name in document_operations and self.queries is not None:
            helper_name, required = document_operations[name]
            params = command.get("params", {})
            if not isinstance(params, dict) or set(params) != required:
                return {
                    "status": "error",
                    "message": "Invalid document operation arguments",
                }
            helper = getattr(self.queries, helper_name)
            return {
                "status": "success",
                "result": helper(self.cad_handler.app, **params),
            }
        stencil_operations = {
            "chamfer_edges": {
                "body_name",
                "edge_indices",
                "reference_face_indices",
                "distance_one",
                "distance_two",
                "feature_name",
            },
            "draw_sketch_text": {
                "sketch_name",
                "text",
                "x",
                "y",
                "height",
                "width",
                "box_height",
            },
            "extrude_sketch_entities": {
                "sketch_name",
                "entity_type",
                "distance",
                "operation",
                "feature_name",
            },
            "chamfer_stencil_edges": {
                "body_name",
                "scope",
                "vertical_depth",
                "angle_degrees",
                "feature_name",
            },
        }
        if name in stencil_operations and self.queries is not None:
            params = command.get("params", {})
            optional = (
                {"component_name"}
                if name in {"draw_sketch_text", "extrude_sketch_entities"}
                else set()
            )
            if (
                not isinstance(params, dict)
                or not stencil_operations[name] <= set(params)
                or set(params) - stencil_operations[name] - optional
            ):
                return {
                    "status": "error",
                    "message": "Invalid stencil operation arguments",
                }
            return {
                "status": "success",
                "result": getattr(self.queries, name)(self.cad_handler, **params),
            }
        if (
            name in {"get_feature_health", "get_drawing_info"}
            and self.queries is not None
        ):
            params = command.get("params", {})
            if not isinstance(params, dict):
                return {
                    "status": "error",
                    "message": "Query parameters must be an object",
                }
            if name == "get_feature_health":
                if set(params) - {"component_name", "offset", "limit"}:
                    return {
                        "status": "error",
                        "message": "Unsupported feature query parameters",
                    }
                result = self.queries.feature_health(
                    self.cad_handler._design(), **params
                )
            else:
                if params:
                    return {
                        "status": "error",
                        "message": "Drawing inspection accepts no arguments",
                    }
                result = self.queries.drawing_info(self.cad_handler.app)
            return {"status": "success", "result": result}
        if command.get("type") == "dev_reload_candidates":
            params = command.get("params", {})
            if not isinstance(params, dict) or params:
                return {"status": "error", "message": "Reload accepts no arguments"}
            handler, hashes = self.reloader()
            self.cad_handler = handler
            self.generation += 1
            return {
                "status": "success",
                "result": {
                    "ok": True,
                    "development_only": True,
                    "generation": self.generation,
                    "source_sha256": hashes,
                },
            }
        return self.cad_handler.execute_command(command)


def run(context):
    global _server, _bridge
    if _server is not None:
        return
    core = importlib.import_module("adsk.core")
    app = core.Application.get()
    try:
        bridge, handlers, sockets = load_runtime()
        queries = importlib.import_module(
            f"{RUNTIME_PACKAGE}.server.mechanical_queries"
        )
        bridge.CUSTOM_EVENT_ID = "Fusion360MCP_Development_BridgeEvent"
        _bridge = bridge.EventBridge(
            app, DevelopmentHandler(handlers.CommandHandler(), queries=queries)
        )
        _server = sockets.Fusion360MCPServer(_bridge, host="127.0.0.1", port=9877)
        _server.start()
    except Exception:
        stop(context)
        app.userInterface.messageBox(traceback.format_exc())


def stop(context):
    global _server, _bridge
    server, bridge = _server, _bridge
    _server = None
    _bridge = None
    try:
        if server is not None:
            server.stop()
    finally:
        if bridge is not None:
            bridge.stop()
