"""Persistent development refresh preserves external edits and runtime caches."""

import pytest

from scripts.install_development_addin import install, main


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    fixture = root / "tests/fusion_addins/Fusion360MCPDev"
    fixture.mkdir(parents=True)
    (fixture / "Fusion360MCPDev.py").write_text("fixture")
    server = root / "addon/server"
    server.mkdir(parents=True)
    (server / "event_bridge.py").write_text("bridge")
    return root


def test_install_and_refresh_preserve_unknown_cache(repository, tmp_path):
    target = tmp_path / "installed"
    target.mkdir()
    cache = target / "cache.txt"
    cache.write_text("user cache")
    assert install(repository, target) == 2
    (repository / "addon/server/event_bridge.py").write_text("updated bridge")
    assert install(repository, target) == 2
    assert (target / "server/event_bridge.py").read_text() == "updated bridge"
    assert cache.read_text() == "user cache"


def test_modified_source_is_preserved(repository, tmp_path):
    target = tmp_path / "installed"
    install(repository, target)
    (target / "Fusion360MCPDev.py").write_text("user edit")
    with pytest.raises(ValueError, match="preserved"):
        install(repository, target)
    assert (target / "Fusion360MCPDev.py").read_text() == "user edit"


def test_unowned_collision_and_missing_sources_rejected(repository, tmp_path):
    target = tmp_path / "installed"
    target.mkdir()
    (target / "Fusion360MCPDev.py").write_text("unowned")
    with pytest.raises(ValueError, match="unowned"):
        install(repository, target)
    with pytest.raises(ValueError, match="missing"):
        install(tmp_path / "missing", tmp_path / "other")


def test_cli_installs_owned_fixture(repository, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["installer", str(tmp_path / "target")])
    monkeypatch.setattr("scripts.install_development_addin.install", lambda *args: 2)
    main()
    assert "Installed 2 owned files" in capsys.readouterr().out
