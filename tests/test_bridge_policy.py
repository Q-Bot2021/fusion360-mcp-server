"""Check bridge scripts fail before their retained networking implementation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wrapper_disabled_before_relay():
    source = (ROOT / "devcontainer/fusion-mcp-wrapper.sh").read_text(encoding="utf-8")
    assert source.index("exit 1") < source.index("python3 -")
    assert "stdio" in source[:source.index("exit 1")]


def test_bridge_setup_disabled_but_cleanup_retained():
    source = (ROOT / "devcontainer/fusion-mcp-bridge.ps1").read_text(encoding="utf-8")
    assert source.index("if (-not $Remove)") < source.index("Get-NetIPAddress")
    assert source.index("exit 1") < source.index("netsh interface portproxy add")
    assert "if ($Remove)" in source
    assert "netsh interface portproxy delete" in source