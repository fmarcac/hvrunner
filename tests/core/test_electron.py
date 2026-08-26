"""Electron builds, which need two things no other native game does."""

from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core import electron
from hvrunner.core.models import Game
from hvrunner.core.planning import plan


@pytest.fixture
def electron_game(tmp_path):
    """A folder shaped like an unpacked Electron build."""
    folder = tmp_path / "CD Market"
    (folder / "resources").mkdir(parents=True)
    (folder / "resources" / "app.asar").write_bytes(b"asar")
    for name in ("v8_context_snapshot.bin", "libffmpeg.so"):
        (folder / name).write_bytes(b"payload")
    sandbox = folder / "chrome-sandbox"
    sandbox.write_bytes(b"helper")
    sandbox.chmod(0o755)
    binary = folder / "cdmarket"
    binary.write_bytes(b"\x7fELF\x02\x01\x01\x00" + bytes(8))
    binary.chmod(0o755)
    return Game("CD Market", "Custom", str(folder), str(binary))


def test_an_electron_build_is_recognised(electron_game):
    assert electron.is_electron(Path(electron_game.executable))


def test_an_ordinary_native_binary_is_not(tmp_path):
    binary = tmp_path / "plain"
    binary.write_bytes(b"\x7fELF")
    assert not electron.is_electron(binary)


def test_a_helper_without_setuid_is_unusable(electron_game):
    """Chromium aborts rather than falling back, so the launch just dies."""
    assert not electron.sandbox_usable(Path(electron_game.executable).parent)
    assert electron.arguments(Path(electron_game.executable)) == ["--no-sandbox"]


def test_a_correctly_installed_helper_is_left_alone(electron_game, monkeypatch):
    folder = Path(electron_game.executable).parent

    class Rooted:
        st_uid = 0
        st_mode = 0o104755

    monkeypatch.setattr(Path, "stat", lambda self, **kwargs: Rooted())
    assert electron.sandbox_usable(folder)
    assert electron.arguments(Path(electron_game.executable)) == []


def test_an_argument_the_entry_already_passes_is_not_repeated(electron_game):
    assert electron.arguments(Path(electron_game.executable), ("--no-sandbox",)) == []


def test_the_ozone_hint_defaults_to_x11():
    """The NVIDIA Wayland path cannot allocate scanout buffers."""
    assert electron.environment({})[electron.OZONE_HINT] == "x11"


def test_enable_wayland_asks_for_the_native_backend():
    assert electron.environment({"enable_wayland": True})[electron.OZONE_HINT] == "wayland"


def test_a_launch_carries_both(electron_game, config, stub_tools):
    prepared = plan(electron_game, config, prepare=True)
    assert prepared.prefix is None
    assert prepared.command[-1] == "--no-sandbox"
    assert prepared.environment[electron.OZONE_HINT] == "x11"


def test_the_entrys_own_environment_still_wins(electron_game, config, stub_tools):
    from dataclasses import replace

    game = replace(electron_game, env=((electron.OZONE_HINT, "wayland"),))
    assert plan(game, config, prepare=True).environment[electron.OZONE_HINT] == "wayland"


def test_launch_args_come_after_what_the_build_needs(electron_game, config, stub_tools):
    from dataclasses import replace

    game = replace(electron_game, launch_args=("--fullscreen",))
    command = plan(game, config, prepare=True).command
    assert command[-2:] == ["--no-sandbox", "--fullscreen"]
