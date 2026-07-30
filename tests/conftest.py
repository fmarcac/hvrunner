from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hvrunner.config import default_config  # noqa: E402


@pytest.fixture
def state_home(tmp_path, monkeypatch):
    """Redirect log output away from the real state directory."""
    root = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(root))
    return root


@pytest.fixture
def fake_proton(tmp_path):
    proton = tmp_path / "Proton"
    proton.mkdir()
    (proton / "proton").write_text("stub")
    (proton / "toolmanifest.vdf").write_text("stub")
    return proton


@pytest.fixture
def fake_umu(tmp_path):
    umu = tmp_path / "umu-run"
    umu.write_text("stub")
    return umu


@pytest.fixture
def game_dir(tmp_path):
    folder = tmp_path / "BFResynced"
    folder.mkdir()
    (folder / "ACBlackFlag.exe").write_text("stub")
    return folder


@pytest.fixture
def config(fake_proton, fake_umu, tmp_path):
    values = default_config()
    values.update({
        "proton_path": str(fake_proton),
        "umu_path": str(fake_umu),
        "library_roots": [str(tmp_path)],
    })
    return values


@pytest.fixture
def stub_tools(monkeypatch):
    """Make MangoHud and gamemode lookups deterministic."""
    import hvrunner.launcher as launcher

    def which(name):
        return f"/usr/bin/{name}" if name in {"mangohud", "gamemoderun"} else None

    monkeypatch.setattr(launcher.shutil, "which", which)
