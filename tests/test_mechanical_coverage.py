"""Heuristic name references must never be treated as proven API coverage."""

import csv
from pathlib import Path

import pytest

from scripts.audit_mechanical_api import (
    audit,
    coverage_rows,
    handler_references,
    main,
    render_tool_ledger,
)


def test_html_renderer_escapes_data_and_does_not_infer_missing_gates(tmp_path):
    directory = tmp_path / "docs/mechanical"
    directory.mkdir(parents=True)
    (directory / "generic-tool-audit.tsv").write_text(
        "tool\tstatus\nunsafe<script>\taccepted_scope\npending\treview_required\n",
        encoding="utf-8",
    )
    (directory / "tool-status.tsv").write_text(
        "tool\tregistration\tunit_status\tprotocol_status\tlive_status\tproduction_live_status\treason\n"
        "pending\tproduction\tpassed\tpassed\tcreation_observed\t"
        "pending_restart\t<unsafe & note>\n",
        encoding="utf-8",
    )
    rendered = render_tool_ledger(tmp_path)
    assert "unsafe&lt;script&gt;" in rendered and "unsafe<script>" not in rendered
    assert "&lt;unsafe &amp; note&gt;" in rendered
    assert 'title="unrecorded"' in rendered
    assert 'class="mark pending" title="creation_observed"' in rendered
    assert 'class="mark pass" title="passed"' in rendered
    assert "&#10003;" in rendered and "&#10007;" in rendered
    assert rendered == render_tool_ledger(tmp_path)


def test_html_renderer_rejects_duplicate_and_unknown_status(tmp_path):
    directory = tmp_path / "docs/mechanical"
    directory.mkdir(parents=True)
    generic = directory / "generic-tool-audit.tsv"
    (directory / "tool-status.tsv").write_text(
        "tool\tregistration\tunit_status\tprotocol_status\tlive_status\tproduction_live_status\treason\n",
        encoding="utf-8",
    )
    generic.write_text(
        "tool\tstatus\npart\treview_required\npart\treview_required\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate"):
        render_tool_ledger(tmp_path)
    generic.write_text("tool\tstatus\npart\tguessed_pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown"):
        render_tool_ledger(tmp_path)


def test_existing_registration_with_unverified_gates_stays_pending(tmp_path):
    directory = tmp_path / "docs/mechanical"
    directory.mkdir(parents=True)
    (directory / "generic-tool-audit.tsv").write_text(
        "tool\tstatus\ncreate_box\treview_required\n", encoding="utf-8"
    )
    (directory / "tool-status.tsv").write_text(
        "tool\tregistration\tunit_status\tprotocol_status\tlive_status\t"
        "production_live_status\treason\n"
        "create_box\tproduction\tunverified\tpassed\tunverified\t"
        "root_scope_only\tcomponent targeting pending\n",
        encoding="utf-8",
    )
    rendered = render_tool_ledger(tmp_path)
    assert 'class="mark pending" title="unverified"' in rendered
    assert 'class="mark pending" title="root_scope_only"' in rendered
    assert 'class="mark pass" title="passed"' in rendered
    assert "component targeting pending" in rendered


def test_published_html_ledger_matches_authoritative_sources():
    root = Path(__file__).resolve().parents[1]
    published = (root / "docs/mechanical/audit-ledger.html").read_text(encoding="utf-8")
    assert published == render_tool_ledger(root), (
        "Regenerate: python -m scripts.audit_mechanical_api "
        "docs/mechanical/audit-ledger.html --html"
    )


def test_reference_matching_uses_active_handlers_only():
    source = (
        "def query():\n    return thing.volume\ndef disabled():\n    return x.create()"
    )
    assert handler_references(source, {"query"}) == {"query": {"volume"}}


def test_same_name_does_not_prove_receiver_identity():
    rows = coverage_rows(
        [
            {"symbol": "adsk.fusion.Body.volume", "kind": "property", "url": "body"},
            {"symbol": "adsk.drawing.Other.volume", "kind": "property", "url": "other"},
            {
                "symbol": "adsk.electron.Board.name",
                "kind": "property",
                "url": "excluded",
            },
            {"symbol": "adsk.fusion.Body", "kind": "object", "url": "excluded"},
        ],
        {"query": {"volume"}},
    )
    assert len(rows) == 2
    assert all(row["assignment_status"] == "receiver_review_required" for row in rows)
    assert all(row["live_status"] == "unverified" for row in rows)


def test_unreferenced_members_remain_unassigned():
    rows = coverage_rows(
        [{"symbol": "adsk.fusion.Widget.add", "kind": "method", "url": "url"}], {}
    )
    assert rows[0]["assignment_status"] == "unassigned_review_required"


def test_generic_audit_tracks_every_active_tool_without_certifying_unknowns():
    from fusion360_mcp.tools import get_tool_list

    root = Path(__file__).resolve().parents[1]
    with (root / "docs/mechanical/generic-tool-audit.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    names = [row["tool"] for row in rows]
    assert len(names) == len(set(names))
    assert set(names) == {tool.name for tool in get_tool_list()}
    assert all(
        row["status"] in {
            "accepted_scope", "development_accepted", "review_required",
            "blocked_prerequisite",
        }
        for row in rows
    )
    assert (
        next(row for row in rows if row["tool"] == "get_object_info")["status"]
        == "accepted_scope"
    )


def test_promotion_status_matches_eligible_registry():
    from fusion360_mcp.tools import get_tool_by_name

    root = Path(__file__).resolve().parents[1]
    status_path = root / "docs/mechanical/tool-status.tsv"
    with status_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    with (root / "docs/mechanical/generic-tool-audit.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        scopes = {row["tool"]: row["status"] for row in csv.DictReader(
            stream, delimiter="\t"
        )}
    for row in rows:
        registered = get_tool_by_name(row["tool"])
        assert bool(registered) == (row["registration"] == "production")
        if registered:
            assert type(registered["annotations"]["readOnlyHint"]) is bool
            assert type(registered["annotations"]["destructiveHint"]) is bool
            assert type(registered["annotations"]["idempotentHint"]) is bool
            if row["tool"] == "create_design":
                assert registered["annotations"]["destructiveHint"] is False
                assert registered["annotations"]["idempotentHint"] is False
            assert row["unit_status"] in {"passed", "pending", "unverified", "failed"}
            assert row["protocol_status"] in {
                "passed", "pending", "unverified", "failed"
            }
            if scopes[row["tool"]] == "accepted_scope":
                assert row["unit_status"] == "passed"
                assert row["protocol_status"] == "passed"


def test_html_cli_publishes_snapshot_without_rebuilding_api_ledger(
    tmp_path, monkeypatch, capsys
):
    destination = tmp_path / "report/audit.html"
    monkeypatch.setattr("sys.argv", ["audit", str(destination), "--html"])
    monkeypatch.setattr(
        "scripts.audit_mechanical_api.render_tool_ledger",
        lambda root: "<html>snapshot</html>",
    )
    unexpected_audit = []
    monkeypatch.setattr(
        "scripts.audit_mechanical_api.audit",
        lambda *args: unexpected_audit.append(args),
    )
    main()
    assert destination.read_text(encoding="utf-8") == "<html>snapshot</html>"
    assert not unexpected_audit
    assert "Rendered audit ledger" in capsys.readouterr().out


def test_committed_ledger_has_all_mechanical_and_drawing_members():
    root = Path(__file__).resolve().parents[1]
    with (root / "docs/fusion-api/index.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        pointers = list(csv.DictReader(stream, delimiter="\t"))
    with (root / "docs/mechanical/capability-coverage.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    expected = {
        (row["symbol"], row["kind"], row["url"])
        for row in pointers
        if row["symbol"].startswith(("adsk.fusion.", "adsk.drawing."))
        and row["kind"] in {"method", "property"}
    }
    assert {(row["symbol"], row["kind"], row["url"]) for row in rows} == expected
    assert len(rows) == len(expected)


def test_audit_cli_delegates(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["audit", "output.tsv"])
    monkeypatch.setattr("scripts.audit_mechanical_api.audit", lambda *args: 3)
    main()
    assert "members: 3" in capsys.readouterr().out


def test_empty_index_does_not_overwrite_ledger(tmp_path):
    (tmp_path / "docs/fusion-api").mkdir(parents=True)
    (tmp_path / "docs/fusion-api/index.tsv").write_text("symbol\tkind\turl\n")
    (tmp_path / "addon/server").mkdir(parents=True)
    (tmp_path / "addon/server/command_handler.py").write_text("pass")
    output = tmp_path / "ledger.tsv"
    output.write_text("existing")
    with pytest.raises(ValueError, match="empty"):
        audit(tmp_path, output)
    assert output.read_text() == "existing"
