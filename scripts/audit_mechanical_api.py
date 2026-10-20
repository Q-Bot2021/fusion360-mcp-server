"""Build a conservative mechanical/drawing coverage ledger, not automatic wrappers."""

import argparse
import ast
import csv
import hashlib
import html
import json
from pathlib import Path
from string import Template

FIELDS = (
    "symbol",
    "kind",
    "url",
    "handler_candidates",
    "assignment_status",
    "unit_status",
    "protocol_status",
    "live_status",
    "production_eligible",
)
MODE_FIELDS = (
    "tool",
    "mode",
    "generic_scope_status",
    "unit_status",
    "protocol_status",
    "development_live_status",
    "production_live_status",
    "evidence_revision",
    "evidence",
    "blocker",
)
MODE_GATE_STATUSES = {"blocked", "failed", "passed", "pending", "stale", "unverified"}


def advertised_modes(tools) -> list[tuple[str, str]]:
    """Return explicit enum and boolean input choices as independent modes."""
    modes = []
    for tool in tools:
        properties = tool.inputSchema.get("properties", {})
        choices = []
        for name, schema in properties.items():
            if "enum" in schema:
                choices.extend((name, value) for value in schema["enum"])
            elif schema.get("type") == "boolean":
                choices.extend((name, value) for value in (False, True))
        if not choices:
            modes.append((tool.name, "default"))
            continue
        for name, value in choices:
            encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
            modes.append((tool.name, f"{name}={encoded}"))
    return sorted(modes)


def initialize_mode_status(repository: Path, output: Path) -> int:
    """Create an unverified mode baseline without overwriting reviewed results."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing mode ledger: {output}")

    from fusion360_mcp.tools import get_tool_list

    with (repository / "docs/mechanical/generic-tool-audit.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        generic = {
            row["tool"]: row["status"]
            for row in csv.DictReader(stream, delimiter="\t")
        }
    tools = get_tool_list()
    names = {tool.name for tool in tools}
    if names != set(generic):
        raise ValueError("Generic audit does not match the active production registry")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=MODE_FIELDS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for tool_name, mode in advertised_modes(tools):
            scope_status = generic[tool_name]
            blocker = (
                "No mode-specific acceptance evidence bound to a source revision "
                "is recorded."
            )
            if scope_status == "blocked_prerequisite":
                blocker += (
                    " The recorded AutoConstrain live blocker is the required "
                    "eligible Fusion account entitlement."
                )
            writer.writerow(
                {
                    "tool": tool_name,
                    "mode": mode,
                    "generic_scope_status": scope_status,
                    "unit_status": "unverified",
                    "protocol_status": "unverified",
                    "development_live_status": (
                        "blocked"
                        if scope_status == "blocked_prerequisite"
                        else "unverified"
                    ),
                    "production_live_status": (
                        "blocked"
                        if scope_status == "blocked_prerequisite"
                        else "unverified"
                    ),
                    "evidence_revision": "unrecorded",
                    "evidence": (
                        "generic-tool-audit.tsv (scope); tool-status.tsv "
                        "(aggregate context only)"
                    ),
                    "blocker": blocker,
                }
            )
    return len(advertised_modes(tools))


def handler_references(source: str, active_names: set[str]) -> dict[str, set[str]]:
    tree = ast.parse(source)
    references = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in active_names:
            references[node.name] = {
                child.attr
                for child in ast.walk(node)
                if isinstance(child, ast.Attribute)
            }
    return references


def coverage_rows(pointers: list[dict], references: dict[str, set[str]]) -> list[dict]:
    rows = []
    for pointer in pointers:
        symbol, kind = pointer["symbol"], pointer["kind"]
        if not symbol.startswith(("adsk.fusion.", "adsk.drawing.")):
            continue
        if kind not in {"method", "property"}:
            continue
        member = symbol.rsplit(".", 1)[1]
        matches = sorted(
            name for name, attributes in references.items() if member in attributes
        )
        rows.append(
            {
                "symbol": symbol,
                "kind": kind,
                "url": pointer["url"],
                "handler_candidates": ";".join(matches),
                "assignment_status": "receiver_review_required"
                if matches
                else "unassigned_review_required",
                "unit_status": "unverified",
                "protocol_status": "unverified",
                "live_status": "unverified",
                "production_eligible": "unverified",
            }
        )
    return sorted(rows, key=lambda row: (row["symbol"], row["kind"], row["url"]))


def audit(repository: Path, output: Path) -> int:
    from fusion360_mcp.tools import get_tool_list

    with (repository / "docs/fusion-api/index.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["symbol", "kind", "url"]:
            raise ValueError("Unexpected API pointer columns")
        pointers = list(reader)
    references = handler_references(
        (repository / "addon/server/command_handler.py").read_text(encoding="utf-8"),
        {tool.name for tool in get_tool_list()},
    )
    rows = coverage_rows(pointers, references)
    if not rows:
        raise ValueError("Mechanical/drawing index is empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def render_tool_ledger(repository: Path) -> str:
    directory = repository / "docs/mechanical"

    def read_rows(filename, columns):
        with (directory / filename).open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames != columns:
                raise ValueError(f"Unexpected ledger columns: {filename}")
            rows = list(reader)
        names = [row["tool"] for row in rows]
        if any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError(f"Missing or duplicate tool in {filename}")
        return {row["tool"]: row for row in rows}

    generic = read_rows("generic-tool-audit.tsv", ["tool", "status"])
    gates = read_rows(
        "tool-status.tsv",
        [
            "tool",
            "registration",
            "unit_status",
            "protocol_status",
            "live_status",
            "production_live_status",
            "evidence_revision",
            "reason",
        ],
    )
    with (directory / "tool-mode-status.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != list(MODE_FIELDS):
            raise ValueError("Unexpected ledger columns: tool-mode-status.tsv")
        modes = list(reader)
    mode_keys = [(row["tool"], row["mode"]) for row in modes]
    if (
        any(not tool or not mode for tool, mode in mode_keys)
        or len(mode_keys) != len(set(mode_keys))
    ):
        raise ValueError("Missing or duplicate tool/mode in tool-mode-status.tsv")
    allowed = {
        "accepted_scope",
        "development_accepted",
        "review_required",
        "blocked_prerequisite",
    }
    if any(row["status"] not in allowed for row in generic.values()):
        raise ValueError("Unknown generic audit status")
    if any(
        row["registration"] not in {"production", "development"}
        for row in gates.values()
    ):
        raise ValueError("Unknown registration status")
    if any(
        row["generic_scope_status"] not in allowed
        or any(row[key] not in MODE_GATE_STATUSES for key in MODE_FIELDS[3:7])
        for row in modes
    ):
        raise ValueError("Unknown tool mode status")
    if any(row["tool"] not in generic for row in modes):
        raise ValueError("Mode ledger includes a tool missing from the generic audit")
    if any(
        row["generic_scope_status"] != generic[row["tool"]]["status"]
        for row in modes
    ):
        raise ValueError("Mode ledger generic scope disagrees with the tool audit")

    def indicator(passed, detail):
        css = "pass" if passed else "pending"
        symbol = "&#10003;" if passed else "&#10007;"
        return (
            f'<span class="mark {css}" title="{html.escape(detail, quote=True)}">'
            f'<span aria-hidden="true">{symbol}</span>'
            f'<span class="sr-only">{"Passed" if passed else "Not confirmed"}'
            '</span></span>'
        )

    def evidence_links(value):
        rendered = []
        for reference in value.split(";"):
            reference = reference.strip()
            token = reference.split(maxsplit=1)[0] if reference else ""
            if token in {"generic-tool-audit.tsv", "tool-status.tsv"}:
                target = token
            elif token.startswith("tests/"):
                target = f"../../{token.split('::', 1)[0]}"
            else:
                rendered.append(html.escape(reference))
                continue
            rendered.append(
                f'<a href="{html.escape(target, quote=True)}">'
                f"{html.escape(reference)}</a>"
            )
        return "<br>".join(rendered)

    rows = []
    development_count = 0
    for name in sorted(generic.keys() | gates.keys()):
        gate = gates.get(name, {})
        registration = gate.get("registration", "production")
        development_count += registration == "development"
        status = generic.get(name, {}).get("status", "development_only")
        review = status == "accepted_scope"
        cells = []
        for key in (
            "unit_status",
            "protocol_status",
            "live_status",
            "production_live_status",
        ):
            detail = gate.get(key, "unrecorded")
            passed = detail == "passed" or detail.startswith("passed_")
            cells.append(
                f'<td class="gate">{indicator(passed, detail)}<small>'
                f"{html.escape(detail.replace('_', ' '))}</small></td>"
            )
        note = gate.get(
            "reason", "Detailed acceptance gates are not recorded in tool-status.tsv."
        )
        rows.append(
            f'<tr data-tool="{html.escape(name, quote=True)}" data-status="{status}" '
            f'data-registration="{registration}"><th scope="row"><code>'
            f"{html.escape(name)}</code></th>"
            f'<td>{registration}</td><td class="gate">{indicator(review, status)}'
            f"<small>{html.escape(status.replace('_', ' '))}</small></td>"
            + "".join(cells)
            + f'<td>{html.escape(gate.get("evidence_revision", "unrecorded"))}</td>'
            + f'<td class="note">{html.escape(note)}</td></tr>'
        )
    rendered_modes = []
    for row in modes:
        scope = row["generic_scope_status"]
        rendered_modes.append(
            f'<tr><th scope="row"><code>{html.escape(row["tool"])}</code></th>'
            f'<td><code>{html.escape(row["mode"])}</code></td>'
            f'<td class="gate">{indicator(scope == "accepted_scope", scope)}'
            f'<small>{html.escape(scope.replace("_", " "))}</small></td>'
            + "".join(
                f'<td class="gate">{indicator(row[key] == "passed", row[key])}'
                f'<small>{html.escape(row[key].replace("_", " "))}</small></td>'
                for key in (
                    "unit_status",
                    "protocol_status",
                    "development_live_status",
                    "production_live_status",
                )
            )
            + f'<td>{html.escape(row["evidence_revision"])}</td>'
            f'<td class="note">{evidence_links(row["evidence"])}<br>'
            f'{html.escape(row["blocker"])}</td></tr>'
        )
    accepted_count = sum(row["status"] == "accepted_scope" for row in generic.values())
    hashes = " ".join(
        f"{filename}: {hashlib.sha256((directory / filename).read_bytes()).hexdigest()}"
        for filename in (
            "generic-tool-audit.tsv",
            "tool-status.tsv",
            "tool-mode-status.tsv",
        )
    )
    template = Template(
        (
            Path(__file__).resolve().parents[1]
            / "docs/mechanical/audit-ledger.template.html"
        ).read_text(encoding="utf-8")
    )
    return template.substitute(
        production_count=len(generic),
        accepted_count=accepted_count,
        development_count=development_count,
        rows="\n".join(rows),
        mode_count=len(modes),
        mode_rows="\n".join(rendered_modes),
        hashes=html.escape(hashes),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--html",
        action="store_true",
        help="Render the tool audit HTML without modifying TSV ledgers",
    )
    parser.add_argument(
        "--initialize-mode-status",
        action="store_true",
        help="Create a new unverified mode-status ledger without overwriting one",
    )
    args = parser.parse_args()
    if args.html:
        rendered = render_tool_ledger(Path(__file__).resolve().parents[1])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Rendered audit ledger: {args.output}")
        return
    if args.initialize_mode_status:
        count = initialize_mode_status(
            Path(__file__).resolve().parents[1], args.output
        )
        print(f"Initialized mode-status ledger: {args.output} ({count} modes)")
        return
    print(f"Indexed mechanical/drawing members: {audit(Path.cwd(), args.output)}")


if __name__ == "__main__":
    main()
