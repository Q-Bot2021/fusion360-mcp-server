"""Reconstruct the three authorized image stencils through development MCP only."""

import argparse
import base64
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def stencil_layouts():
    small = {
        "name": "Circles_Small",
        "width": 105,
        "height": 200,
        "ruler_side": "right",
        "ruler_length": 180,
        "circles": [
            (12, center_y, diameter)
            for center_y, diameter in zip(
                [182.5, 164, 147, 132, 118, 105.5, 94, 84, 75, 67, 59.5],
                [15, 14, 12, 10, 9, 8, 7, 6, 5, 4, 3],
                strict=True,
            )
        ]
        + [
            (35, center_y, diameter)
            for center_y, diameter in zip(
                [187, 165.5, 141.5, 116, 86.5, 55, 20.5],
                [16, 18, 20, 22, 26, 28, 30],
                strict=True,
            )
        ]
        + [
            (70, center_y, diameter)
            for center_y, diameter in zip(
                [172, 124, 76, 28], [40, 38, 36, 32], strict=True
            )
        ],
        "squares": [],
        "hexagons": [],
        "triangles": [],
        "protractor": (70, 124, 19),
    }
    large = {
        "name": "Circles_Large",
        "width": 132,
        "height": 220,
        "ruler_side": "left",
        "ruler_length": 210,
        "circles": [
            (38, center_y, diameter)
            for center_y, diameter in zip(
                [189, 130, 78, 28], [50, 44, 40, 38], strict=True
            )
        ]
        + [
            (93, center_y, diameter)
            for center_y, diameter in zip([161, 95, 32], [60, 56, 52], strict=True)
        ],
        "squares": [],
        "hexagons": [],
        "triangles": [],
        "protractor": (38, 28, 19),
    }
    centers = [200, 172, 146, 122, 100, 81, 65, 50, 38, 28, 20, 14, 10, 7, 4.5]
    sizes = [25, 22, 20, 18, 16, 14, 12, 10, 8, 6, 5, 4, 3, 2, 1]
    polygon_centers = [210, 203, 196, 188, 176, 161, 145, 125, 105, 82, 57, 29]
    polygon_sizes = [4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25]
    mixed = {
        "name": "Mixed_Shapes",
        "width": 110,
        "height": 220,
        "ruler_side": "left",
        "ruler_length": 200,
        "circles": [
            (25, center_y, size) for center_y, size in zip(centers, sizes, strict=True)
        ],
        "squares": [
            (71, center_y, size) for center_y, size in zip(centers, sizes, strict=True)
        ],
        "hexagons": [
            (49, center_y, size)
            for center_y, size in zip(polygon_centers, polygon_sizes, strict=True)
        ],
        "triangles": [
            (94, center_y, size)
            for center_y, size in zip(polygon_centers, polygon_sizes, strict=True)
        ],
        "protractor": None,
    }
    return [small, large, mixed]


def rotated_rectangle(center_x, center_y, length, width, angle_degrees):
    angle = math.radians(angle_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [
        (
            center_x + along * cosine - across * sine,
            center_y + along * sine + across * cosine,
        )
        for along, across in [
            (-length / 2, -width / 2),
            (length / 2, -width / 2),
            (length / 2, width / 2),
            (-length / 2, width / 2),
        ]
    ]


def label_box(text, center_x, bottom_y, height):
    width = max(len(text) * height * 1.5, height * 2)
    return (
        center_x - width / 2,
        bottom_y,
        center_x + width / 2,
        bottom_y + height * 1.5,
    )


def boxes_overlap(first, second, clearance=0.25):
    return not (
        first[2] + clearance <= second[0]
        or second[2] + clearance <= first[0]
        or first[3] + clearance <= second[1]
        or second[3] + clearance <= first[1]
    )


def annotation_obstacles(layout):
    obstacles = []
    for kind in ("squares", "hexagons", "triangles"):
        for center_x, center_y, size in layout[kind]:
            half_width = size / 2
            if kind == "hexagons":
                half_width = size / (2 * math.cos(math.pi / 6))
            obstacles.append(
                (
                    center_x - half_width - 0.18,
                    center_y - size / 2 - 0.18,
                    center_x + half_width + 0.18,
                    center_y + size / 2 + 0.18,
                )
            )
    ruler_start = (layout["height"] - layout["ruler_length"]) / 2
    for millimeter in range(layout["ruler_length"] + 1):
        length = 3.8 if millimeter % 10 == 0 else 2.6 if millimeter % 5 == 0 else 1.4
        origin_x = (
            4.6 if layout["ruler_side"] == "left" else layout["width"] - 4.6 - length
        )
        bottom = ruler_start + millimeter - 0.06
        obstacles.append((origin_x, bottom, origin_x + length, bottom + 0.12))
    if layout["protractor"]:
        center_x, center_y, radius = layout["protractor"]
        for degree in range(0, 360, 5):
            length = 1.5 if degree % 30 == 0 else 0.9 if degree % 10 == 0 else 0.5
            tick_radius = radius + 0.35 + length / 2
            points = rotated_rectangle(
                center_x + tick_radius * math.cos(math.radians(degree)),
                center_y + tick_radius * math.sin(math.radians(degree)),
                length,
                0.12,
                degree,
            )
            obstacles.append(
                (
                    min(point[0] for point in points),
                    min(point[1] for point in points),
                    max(point[0] for point in points),
                    max(point[1] for point in points),
                )
            )
    return obstacles


def label_is_clear(layout, box, occupied):
    bevel = 2.5 / math.tan(math.radians(30))
    left = bevel if layout["ruler_side"] == "left" else 0
    right = layout["width"] - (bevel if layout["ruler_side"] == "right" else 0)
    if (
        box[0] < left + 0.25
        or box[2] > right - 0.25
        or box[1] < 0.25
        or box[3] > layout["height"] - 0.25
    ):
        return False
    for center_x, center_y, diameter in layout["circles"]:
        nearest_x = min(max(center_x, box[0]), box[2])
        nearest_y = min(max(center_y, box[1]), box[3])
        if (
            math.hypot(center_x - nearest_x, center_y - nearest_y)
            < diameter / 2 + 0.18 + 0.25
        ):
            return False
    return not any(boxes_overlap(box, other) for other in occupied)


def stencil_labels(layout):
    requested = []

    def add(text, center_x, bottom_y, height=1.2):
        requested.append((text, center_x, bottom_y, height))

    for center_x, center_y, diameter in layout["circles"]:
        if layout["name"] == "Circles_Small" and center_x == 12:
            add(f"{diameter:g} mm", center_x + diameter / 2 + 3, center_y - 0.5, 0.9)
        elif layout["name"] == "Mixed_Shapes" and diameter <= 6:
            add(f"{diameter:g} mm", 31, center_y - 0.4, 0.8)
        else:
            add(f"{diameter:g} mm", center_x, center_y - diameter / 2 - 1.6, 1.0)
    for center_x, center_y, side in layout["squares"]:
        add(
            f"{side:g} mm",
            66 if side <= 6 else center_x,
            center_y - 0.4 if side <= 6 else center_y - side / 2 - 1.6,
            0.8 if side <= 6 else 1.0,
        )
    for kind, prefix in [("hexagons", "AF"), ("triangles", "S")]:
        for center_x, center_y, size in layout[kind]:
            add(f"{prefix}{size:g} mm", center_x, center_y - size / 2 - 0.9, 0.8)
    ruler_start = (layout["height"] - layout["ruler_length"]) / 2
    for centimeter in range(layout["ruler_length"] // 10 + 1):
        add(
            str(centimeter),
            10 if layout["ruler_side"] == "left" else layout["width"] - 10,
            ruler_start + centimeter * 10 - 0.55,
            1.1,
        )
    if layout["protractor"]:
        center_x, center_y, radius = layout["protractor"]
        for degree in range(0, 360, 30):
            add(
                f"{degree} deg",
                center_x + (radius + 4) * math.cos(math.radians(degree)),
                center_y + (radius + 4) * math.sin(math.radians(degree)) - 0.4,
                0.8,
            )
    if layout["name"] == "Circles_Small":
        add("CIRCLES mm / RULER cm", 66, 2, 1.0)
    elif layout["name"] == "Circles_Large":
        add("CIRCLES mm / RULER cm", 94, 214, 1.0)
    else:
        add("DIA / HEX AF / SQ / TRI SIDE: mm", 62, 217, 0.9)
        add("RULER cm", 17, 214, 0.9)
    occupied = annotation_obstacles(layout)
    placed = []
    offsets = sorted(
        (
            (horizontal / 2, vertical / 2)
            for horizontal in range(-30, 31)
            for vertical in range(-30, 31)
        ),
        key=lambda offset: (math.hypot(*offset), abs(offset[0]), offset),
    )
    for text, center_x, bottom_y, height in requested:
        for horizontal, vertical in offsets:
            candidate = (text, center_x + horizontal, bottom_y + vertical, height)
            box = label_box(*candidate)
            if label_is_clear(layout, box, occupied):
                occupied.append(box)
                placed.append(candidate)
                break
        else:
            raise ValueError(
                f"No visible top-surface position for {layout['name']}: {text}"
            )
    return placed


class Workflow:
    def __init__(self, session, report_path):
        self.session = session
        self.report_path = report_path
        self.report = {
            "status": "started",
            "estimated_from_image": True,
            "units": "mm",
            "thickness_mm": 2.5,
            "engraving_depth_mm": 0.01,
            "bevel_degrees": 30,
            "internal_bevel_vertical_depth_mm": 0.1,
            "layouts": stencil_layouts(),
            "calls": [],
            "designs": [],
        }

    async def call(self, name, arguments):
        result = await self.session.call_tool(name, arguments)
        self.report["calls"].append(
            {
                "tool": name,
                "arguments": arguments,
                "result": result.model_dump(mode="json"),
            }
        )
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(self.report, indent=2), encoding="utf-8")
        if result.isError:
            self.report["status"] = "failed_inspect_before_retry"
            self.report_path.write_text(
                json.dumps(self.report, indent=2), encoding="utf-8"
            )
            raise RuntimeError(f"{name} failed: {result.content}")
        payload = result.structuredContent
        if payload is None:
            raise RuntimeError(f"{name} returned no structured result")
        if payload.get("health_state", 0) != 0:
            raise RuntimeError(f"{name} produced unhealthy feature: {payload}")
        return payload

    async def sketch(self, offset=0):
        result = await self.call("create_sketch", {"plane": "xy", "z_offset": offset})
        return result["sketch_name"]

    async def polygon(self, points):
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            await self.call(
                "draw_line",
                {
                    "start_x": start[0] / 10,
                    "start_y": start[1] / 10,
                    "end_x": end[0] / 10,
                    "end_y": end[1] / 10,
                },
            )

    async def label(self, sketch, text, center_x, bottom_y, height=1.2):
        left, bottom, right, top = label_box(text, center_x, bottom_y, height)
        await self.call(
            "draw_sketch_text",
            {
                "sketch_name": sketch,
                "text": text,
                "x": left / 10,
                "y": bottom / 10,
                "height": height / 10,
                "width": (right - left) / 10,
                "box_height": (top - bottom) / 10,
            },
        )

    async def extrusion(self, sketch, kind, distance, name, operation="cut"):
        return await self.call(
            "extrude_sketch_entities",
            {
                "sketch_name": sketch,
                "entity_type": kind,
                "distance": distance,
                "operation": operation,
                "feature_name": name,
            },
        )

    async def capture(self, name):
        result = await self.session.call_tool(
            "render_view", {"view": "top", "width": 1200, "height": 2000, "fit": True}
        )
        if result.isError:
            raise RuntimeError(f"Viewport capture failed: {result.content}")
        images = [content for content in result.content if content.type == "image"]
        if len(images) != 1:
            raise RuntimeError("Expected one viewport image")
        path = self.report_path.parent / f"{name}_top.png"
        path.write_bytes(base64.b64decode(images[0].data, validate=True))
        self.report.setdefault("images", []).append(str(path))

    async def reconcile_accepted_save(self):
        accepted = [
            entry
            for entry in self.report["calls"]
            if entry["tool"] == "save_sandbox_design"
            and not entry["result"]["isError"]
            and entry["result"].get("structuredContent", {}).get("save_accepted")
        ]
        if len(accepted) != len(self.report["designs"]) + 1:
            raise RuntimeError("Resume requires exactly one accepted, unverified save")
        pending = accepted[-1]
        inspected = await self.call("get_document_state", {})
        saved_identity = inspected.get("is_saved") and inspected.get("data_file_id")
        if (
            (
                inspected["document_id"] != pending["arguments"]["document_id"]
                and not saved_identity
            )
            or inspected["document_name"] != pending["arguments"]["name"]
            or inspected["project_name"] != "MCP_Dev"
        ):
            raise RuntimeError("Activate the exact saved stencil before resuming")
        layout = stencil_layouts()[len(self.report["designs"])]
        prefix = f"MCP_Stencil_{layout['name']}_Approx_"
        if not inspected["document_name"].startswith(prefix):
            raise RuntimeError("Saved name does not match the next expected stencil")
        body_name = "Stencil_" + layout["name"]
        info = await self.call("get_object_info", {"name": body_name})
        health = await self.call("get_feature_health", {})
        if not info.get("found") or any(
            feature["health_state"] != 0 for feature in health["features"]
        ):
            raise RuntimeError("Saved stencil geometry failed inspection")
        await self.capture(inspected["document_name"])
        self.report["designs"].append(
            {
                "name": inspected["document_name"],
                "state": inspected,
                "save": pending["result"]["structuredContent"],
                "body": info,
                "feature_health": health,
            }
        )
        return inspected["document_name"][len(prefix) :]

    async def build(self, layout, suffix):
        planned_labels = stencil_labels(layout)
        name = f"MCP_Stencil_{layout['name']}_Approx_{suffix}"
        state = await self.call("create_design", {"name": name})
        body_name = "Stencil_" + layout["name"]
        await self.call(
            "create_box_parametric",
            {
                "length": layout["width"] / 10,
                "width": layout["height"] / 10,
                "height": 0.25,
                "body_name": body_name,
            },
        )
        await self.call(
            "chamfer_stencil_edges",
            {
                "body_name": body_name,
                "scope": layout["ruler_side"],
                "vertical_depth": 0.25,
                "angle_degrees": 30,
                "feature_name": "Ruler_30deg_FullHeight",
            },
        )
        holes = await self.sketch()
        for center_x, center_y, diameter in layout["circles"]:
            await self.call(
                "draw_circle",
                {
                    "center_x": center_x / 10,
                    "center_y": center_y / 10,
                    "radius": diameter / 20,
                },
            )
        for center_x, center_y, side in layout["squares"]:
            await self.call(
                "draw_rectangle",
                {
                    "width": side / 10,
                    "height": side / 10,
                    "origin_x": (center_x - side / 2) / 10,
                    "origin_y": (center_y - side / 2) / 10,
                },
            )
        for center_x, center_y, across_flats in layout["hexagons"]:
            await self.call(
                "create_polygon",
                {
                    "sides": 6,
                    "radius": across_flats / (20 * math.cos(math.pi / 6)),
                    "center_x": center_x / 10,
                    "center_y": center_y / 10,
                },
            )
        for center_x, center_y, side in layout["triangles"]:
            altitude = side * math.sqrt(3) / 2
            await self.polygon(
                [
                    (center_x - altitude * 2 / 3, center_y),
                    (center_x + altitude / 3, center_y - side / 2),
                    (center_x + altitude / 3, center_y + side / 2),
                ]
            )
        await self.extrusion(holes, "profiles", 0.25, "Nominal_Apertures_mm")
        await self.call(
            "chamfer_stencil_edges",
            {
                "body_name": body_name,
                "scope": "internal",
                "vertical_depth": 0.01,
                "angle_degrees": 30,
                "feature_name": "Internal_30deg_0p1mm",
            },
        )
        await self.call("get_object_info", {"name": body_name})
        ticks = await self.sketch(0.25)
        ruler_start = (layout["height"] - layout["ruler_length"]) / 2
        for millimeter in range(layout["ruler_length"] + 1):
            length = (
                3.8 if millimeter % 10 == 0 else 2.6 if millimeter % 5 == 0 else 1.4
            )
            origin_x = (
                4.6
                if layout["ruler_side"] == "left"
                else layout["width"] - 4.6 - length
            )
            await self.call(
                "draw_rectangle",
                {
                    "width": length / 10,
                    "height": 0.012,
                    "origin_x": origin_x / 10,
                    "origin_y": (ruler_start + millimeter - 0.06) / 10,
                },
            )
        if layout["protractor"]:
            center_x, center_y, radius = layout["protractor"]
            for degree in range(0, 360, 5):
                length = 1.5 if degree % 30 == 0 else 0.9 if degree % 10 == 0 else 0.5
                tick_radius = radius + 0.35 + length / 2
                points = rotated_rectangle(
                    center_x + tick_radius * math.cos(math.radians(degree)),
                    center_y + tick_radius * math.sin(math.radians(degree)),
                    length,
                    0.12,
                    degree,
                )
                await self.polygon(points)
        await self.extrusion(ticks, "profiles", -0.001, "Scale_Ticks_0p01mm")
        labels = await self.sketch(0.25)
        for text, center_x, bottom_y, height in planned_labels:
            await self.label(labels, text, center_x, bottom_y, height)
        await self.extrusion(labels, "texts", -0.001, "Top_Text_0p01mm_SquareEdges")
        info = await self.call("get_object_info", {"name": body_name})
        if abs(info["bounding_box"]["max"][2] - 0.25) > 1e-6:
            raise RuntimeError("Unexpected stencil thickness")
        health = await self.call("get_feature_health", {})
        if any(feature["health_state"] != 0 for feature in health["features"]):
            raise RuntimeError("Stencil contains an unhealthy feature")
        saved = await self.call(
            "save_sandbox_design", {"document_id": state["document_id"], "name": name}
        )
        await self.capture(name)
        inspected = await self.call("get_document_state", {})
        if inspected["project_name"] != "MCP_Dev":
            raise RuntimeError("Save destination not verified; do not retry save")
        self.report["designs"].append(
            {
                "name": name,
                "state": inspected,
                "save": saved,
                "body": info,
                "feature_health": health,
            }
        )
        print(f"Saved {name} in MCP_Dev", flush=True)


async def run(report_path, resume=False, repair_small_labels=False):
    if resume and repair_small_labels:
        raise ValueError(
            "Label repair must use a separate report, not resume the original build"
        )
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "tests.development_mcp"]
    )
    async with stdio_client(parameters) as streams:
        async with ClientSession(
            streams[0], streams[1], read_timeout_seconds=timedelta(seconds=90)
        ) as session:
            await session.initialize()
            workflow = Workflow(session, report_path)
            if resume:
                previous = json.loads(report_path.read_text(encoding="utf-8"))
                if previous.get("layouts") != json.loads(json.dumps(stencil_layouts())):
                    raise RuntimeError(
                        "Resume report does not match the authorized layouts"
                    )
                workflow.report = previous
            await workflow.call("dev_reload_candidates", {})
            suffix = (
                (await workflow.reconcile_accepted_save())
                if resume
                else datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            layouts = (
                stencil_layouts()[:1]
                if repair_small_labels
                else stencil_layouts()[len(workflow.report["designs"]) :]
            )
            if repair_small_labels:
                suffix += "_LabelsV2"
            for layout in layouts:
                await workflow.build(layout, suffix)
            workflow.report["status"] = "passed"
            report_path.write_text(
                json.dumps(workflow.report, indent=2), encoding="utf-8"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create-authorized-stencils", action="store_true", required=True
    )
    parser.add_argument("--resume-report", action="store_true")
    parser.add_argument("--repair-small-labels", action="store_true")
    parser.add_argument(
        "--report", type=Path, default=Path(".pytest_cache/stencil-build.json")
    )
    arguments = parser.parse_args()
    anyio.run(
        run, arguments.report, arguments.resume_report, arguments.repair_small_labels
    )


if __name__ == "__main__":
    main()
