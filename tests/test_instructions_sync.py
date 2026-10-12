"""Enforce complete agent-instruction equality, not approximate semantic similarity."""

from difflib import unified_diff
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def assert_equivalent(claude, copilot):
    claude = claude.replace("\r\n", "\n")
    copilot = copilot.replace("\r\n", "\n")
    difference = "".join(
        unified_diff(
            claude.splitlines(keepends=True),
            copilot.splitlines(keepends=True),
            fromfile=".claude/CLAUDE.md",
            tofile=".github/copilot-instructions.md",
        )
    )
    assert claude == copilot, (
        "Update both instruction files in the same change:\n" + difference
    )


def test_instruction_files_are_identical():
    claude = (ROOT / ".claude/CLAUDE.md").read_bytes().decode("utf-8")
    copilot = (ROOT / ".github/copilot-instructions.md").read_bytes().decode("utf-8")
    assert_equivalent(claude, copilot)


def test_line_endings_are_the_only_allowed_difference():
    assert_equivalent("same\r\n", "same\n")
    with pytest.raises(AssertionError, match="Update both"):
        assert_equivalent("same\n", "same \n")
    with pytest.raises(AssertionError, match="Update both"):
        assert_equivalent("old\n", "new\n")


@pytest.mark.parametrize(
    "path", [".claude/CLAUDE.md", ".github/copilot-instructions.md"]
)
def test_instruction_context_and_required_policies(path):
    file = ROOT / path
    source = file.read_text(encoding="utf-8")
    assert "[Development and testing rules](../dev_rules.md)" in source
    assert (file.parent / "../dev_rules.md").resolve().is_file()
    for policy in ("[UNIT]", "[E2E]", "[SYNC]", "live local-Fusion", "same change"):
        assert policy in source
    assert "before production registration" in source


def test_developer_rules_cover_framework_and_gates():
    source = (ROOT / "dev_rules.md").read_text(encoding="utf-8")
    for policy in (
        "pytest",
        "Ruff",
        "[UNIT]",
        "[E2E]",
        "[SYNC]",
        "skipped",
        "before production registration",
    ):
        assert policy in source


def test_electronics_scope_is_excluded_and_prototypes_are_removed():
    for relative in (".claude/CLAUDE.md", ".github/copilot-instructions.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "Electronics development is excluded from this MCP" in source
        assert "Fusion 2705.1.25" in source
        assert "no end-to-end path" in source
        assert "explicit scope approval" in source
    assert not (ROOT / "addon/server/electronics_support.py").exists()
    assert (ROOT / "tests/development_mcp.py").is_file()
    assert not (ROOT / "docs/electronics/README.md").exists()
    from fusion360_mcp.tools import get_tool_list

    assert not any(tool.name.startswith("ecad_") for tool in get_tool_list())


def test_shared_development_profile_is_retained():
    for relative in (".claude/CLAUDE.md", ".github/copilot-instructions.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "Keep the reusable CAD development MCP" in source
        assert "unless explicitly requested" in source
    assert (ROOT / "tests/fusion_addins/Fusion360MCPDev/Fusion360MCPDev.py").is_file()


@pytest.mark.parametrize(
    "relative",
    [
        ".github/copilot-instructions.md",
        ".claude/CLAUDE.md",
        "AGENTS.md",
        "dev_rules.md",
    ],
)
def test_agent_guidance_requires_audit_ledger_maintenance(relative):
    source = (ROOT / relative).read_text(encoding="utf-8")
    for required in (
        "generic-tool-audit.tsv",
        "tool-status.tsv",
        "audit-ledger.html",
        "same change",
        "scripts.audit_mechanical_api",
    ):
        assert required in source
