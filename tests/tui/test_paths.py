from __future__ import annotations

from pathlib import Path

from hvrunner.tui.paths import browse_root


def test_browse_root_is_the_first_library_folder_that_exists(config, tmp_path):
    missing = tmp_path / "gone"
    real = tmp_path / "library"
    real.mkdir()
    config["library_roots"] = [str(missing), str(real)]
    assert browse_root(config) == real


def test_browse_root_falls_back_to_home(config):
    config["library_roots"] = []
    assert browse_root(config) == Path.home()


def test_browse_root_expands_a_tilde(config, monkeypatch, tmp_path):
    """library_roots is whatever the user typed, and config does not expand it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "games").mkdir()
    config["library_roots"] = ["~/games"]
    assert browse_root(config) == tmp_path / "games"
