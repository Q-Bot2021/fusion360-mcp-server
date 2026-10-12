"""Pointer extraction never copies reference descriptions or examples."""

import csv
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from scripts.index_fusion_api import (
    BASE_URL,
    TitleParser,
    build_index,
    main,
    reference_pointer,
)


@pytest.mark.parametrize(
    "kind", ["Method", "Property", "Event", "Object", "Enumeration"]
)
def test_reference_pointer_contains_only_identity_and_url(kind):
    source = (
        f"<html><head><title>Widget.create {kind}</title></head>"
        "<body>A lengthy description that must never be indexed.</body></html>"
    )
    assert reference_pointer("Widget_create.htm", source) == (
        "Widget.create", kind.lower(), BASE_URL + "Widget_create.htm"
    )


def test_title_parser_ignores_body_and_normalizes_entities():
    parser = TitleParser()
    parser.feed("<TITLE>Widget. create &amp; inspect Method</TITLE><body>secret</body>")
    assert "".join(parser.parts) == "Widget. create & inspect Method"
    pointer = reference_pointer("Widget.htm", "<title> Widget   Object </title>")
    assert pointer[0] == "Widget"


def test_non_reference_pages_are_not_indexed():
    assert reference_pointer("Sample.htm", "<title>Sample program</title>") is None
    assert reference_pointer("Topic.htm", "<p>No title</p>") is None


def test_path_escape_is_rejected():
    with pytest.raises(ValueError, match="basename"):
        reference_pointer("../Widget.htm", "<title>Widget Object</title>")


def test_official_canonical_links_and_namespace_are_preserved():
    source = (
        '<link rel="canonical" href="/cloudhelp/ENU/Fusion-360-API/files/'
        'fusion_TemporaryBRepManager_createBox.htm#!">'
        '<title>TemporaryBRepManager.createBox Method</title>'
    )
    assert reference_pointer("fusion_TemporaryBRepManager_createBox.htm", source) == (
        "adsk.fusion.TemporaryBRepManager.createBox", "method",
        BASE_URL + "fusion_TemporaryBRepManager_createBox.htm",
    )


def test_enumerator_title_is_indexed_as_an_enumeration():
    assert reference_pointer(
        "fusion_BooleanTypes.htm", "<title>BooleanTypes Enumerator</title>"
    ) == (
        "adsk.fusion.BooleanTypes", "enumeration", BASE_URL + "fusion_BooleanTypes.htm"
    )


def test_namespace_is_read_from_official_metadata_not_description():
    pointer = reference_pointer(
        "drawing_Widget.htm",
        '<title>Widget Object</title>Defined in namespace "adsk::drawing" '
        'and the header is &lt;Drawing/Widget.h&gt;<p>Description is excluded.</p>',
    )
    assert pointer == ("adsk.drawing.Widget", "object", BASE_URL + "drawing_Widget.htm")


@pytest.mark.parametrize("url", ["https://example.com/Widget.htm", "/other/Widget.htm"])
def test_non_api_canonical_links_are_rejected(url):
    source = f'<link rel="canonical" href="{url}"><title>Widget Object</title>'
    with pytest.raises(ValueError, match="Canonical URL"):
        reference_pointer("Widget.htm", source)


def test_build_index_is_sorted_and_pointer_only(tmp_path):
    source = tmp_path / "source/files"
    source.mkdir(parents=True)
    (source / "Widget_z.htm").write_text(
        "<title>Widget.z Method</title><body>description</body>", encoding="utf-8"
    )
    (source / "Widget_a.htm").write_text(
        "<title>Widget.a Method</title><pre>example code</pre>", encoding="utf-8"
    )
    (source / "Sample.htm").write_text("<title>Sample</title>", encoding="utf-8")
    output = tmp_path / "index.tsv"
    assert build_index(tmp_path / "source", output) == {"method": 2}
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert [row["symbol"] for row in rows] == ["Widget.a", "Widget.z"]
    assert all(set(row) == {"symbol", "kind", "url"} for row in rows)
    assert "description" not in output.read_text(encoding="utf-8")
    assert "example code" not in output.read_text(encoding="utf-8")


def test_empty_source_does_not_overwrite_existing_index(tmp_path):
    output = tmp_path / "index.tsv"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="No API method"):
        build_index(tmp_path / "missing", output)
    assert output.read_text(encoding="utf-8") == "existing"


def test_cli_generates_pointer_index(tmp_path, monkeypatch, capsys):
    source = tmp_path / "HTML"
    source.mkdir()
    (source / "core_Widget_create.htm").write_text(
        "<title>Widget.create Method</title>", encoding="utf-8"
    )
    output = tmp_path / "index.tsv"
    monkeypatch.setattr("sys.argv", ["index_fusion_api", str(tmp_path), str(output)])
    main()
    assert "method: 1" in capsys.readouterr().out
    assert output.is_file()


def test_committed_index_is_sorted_unique_and_pointer_only():
    root = Path(__file__).resolve().parents[1]
    path = root / "docs/fusion-api/index.tsv"
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        assert reader.fieldnames == ["symbol", "kind", "url"]
        rows = list(reader)
    assert rows
    keys = [(row["symbol"], row["kind"], row["url"]) for row in rows]
    assert keys == sorted(keys)
    assert len({row["url"] for row in rows}) == len(rows)
    assert {row["kind"] for row in rows} == {
        "method", "property", "event", "object", "enumeration"
    }
    for row in rows:
        assert row["symbol"].startswith("adsk.")
        assert all(part.isidentifier() for part in row["symbol"].split("."))
        url = urlsplit(row["url"])
        assert url.scheme == "https" and url.netloc == "help.autodesk.com"
        assert url.path.startswith(urlsplit(BASE_URL).path)
        assert url.path.endswith(".htm") and not url.query and not url.fragment
    symbols = {row["symbol"] for row in rows}
    assert {
        "adsk.core.Application.get",
        "adsk.fusion.TemporaryBRepManager.createBox",
        "adsk.cam.CAM.generateToolpath",
        "adsk.fusion.BooleanTypes",
    } <= symbols


@pytest.mark.parametrize(
    "relative", ["README.md", "AGENTS.md", "dev_rules.md",
                 ".claude/CLAUDE.md", ".github/copilot-instructions.md"]
)
def test_project_documentation_references_index(relative):
    root = Path(__file__).resolve().parents[1]
    source = (root / relative).read_text(encoding="utf-8")
    assert "docs/fusion-api/README.md" in source
    assert (root / "docs/fusion-api/README.md").is_file()