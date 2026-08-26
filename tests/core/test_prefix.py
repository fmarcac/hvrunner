from __future__ import annotations

import pytest

from hvrunner.core import prefix as prefix_module
from hvrunner.core.models import HvrunnerError

REGISTERED = (
    "WINE REGISTRY Version 2\n\n"
    "[Software\\\\Microsoft\\\\WindowsRuntime\\\\ActivatableClassId\\\\Windows.System.DispatcherQueue] 1\n"
    '"DllPath"="C:\\\\windows\\\\system32\\\\coremessaging.dll"\n'
)

# What Proton actually writes: the Controller, and nothing for the plain class.
CONTROLLER_ONLY = (
    "WINE REGISTRY Version 2\n\n"
    "[Software\\\\Microsoft\\\\WindowsRuntime\\\\ActivatableClassId\\\\Windows.System.DispatcherQueueController] 1\n"
    '"DllPath"="C:\\\\windows\\\\system32\\\\coremessaging.dll"\n'
)


def test_create_makes_the_prefix(tmp_path):
    target = tmp_path / "deep" / "prefix"
    prefix_module.create(target)
    assert target.is_dir()


def test_create_is_idempotent(tmp_path):
    prefix_module.create(tmp_path / "p")
    prefix_module.create(tmp_path / "p")
    assert (tmp_path / "p").is_dir()


def test_create_rejects_a_file_in_the_way(tmp_path):
    blocker = tmp_path / "p"
    blocker.write_text("not a directory")
    with pytest.raises(HvrunnerError):
        prefix_module.create(blocker)


def test_link_pfx_points_back_at_the_prefix(tmp_path):
    prefix_module.create(tmp_path / "p")
    prefix_module.link_pfx(tmp_path / "p")
    link = tmp_path / "p" / "pfx"
    assert link.is_symlink()
    assert link.resolve() == (tmp_path / "p").resolve()


def test_link_pfx_leaves_an_existing_link_alone(tmp_path):
    prefix = tmp_path / "p"
    prefix_module.create(prefix)
    prefix_module.link_pfx(prefix)
    prefix_module.link_pfx(prefix)
    assert (prefix / "pfx").is_symlink()


def test_a_real_directory_named_pfx_is_not_replaced(tmp_path):
    """umu builds some prefixes this way; clobbering it would lose the saves."""
    prefix = tmp_path / "p"
    (prefix / "pfx").mkdir(parents=True)
    prefix_module.link_pfx(prefix)
    assert (prefix / "pfx").is_dir()
    assert not (prefix / "pfx").is_symlink()


def test_missing_finds_the_unregistered_class(tmp_path):
    """Wine registers DispatcherQueueController but not DispatcherQueue."""
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "system.reg").write_text(CONTROLLER_ONLY)
    assert "Windows.System.DispatcherQueue" in prefix_module.missing(prefix)


def test_nothing_is_missing_once_registered(tmp_path):
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "system.reg").write_text(REGISTERED)
    assert prefix_module.missing(prefix) == {}


def test_an_unbuilt_prefix_asks_for_nothing(tmp_path):
    """No system.reg means Proton has not built it yet.

    Registering would mean running wineboot and making the user wait, and
    Proton writes the stock registrations when it builds the prefix anyway.
    """
    prefix = tmp_path / "p"
    prefix.mkdir()
    assert prefix_module.missing(prefix) == {}


def test_repair_does_nothing_when_nothing_is_missing(tmp_path):
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "system.reg").write_text(REGISTERED)
    assert prefix_module.repair(prefix, tmp_path / "Proton") == []


def test_register_reports_a_missing_wine_instead_of_raising(tmp_path):
    """A prefix that cannot be repaired must still get its launch attempted."""
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "system.reg").write_text(CONTROLLER_ONLY)
    reported = prefix_module.repair(prefix, tmp_path / "NoProton")
    assert len(reported) == 1
    assert "no wine at" in reported[0]


def test_register_builds_the_expected_command(tmp_path, monkeypatch):
    proton = tmp_path / "Proton"
    wine = proton / "files" / "bin" / "wine"
    wine.parent.mkdir(parents=True)
    wine.write_text("stub")
    recorded: dict = {}

    class Finished:
        returncode = 0

    def fake_run(command, **kwargs):
        recorded["command"] = command
        recorded["env"] = kwargs.get("env")
        return Finished()

    monkeypatch.setattr(prefix_module.process, "run", fake_run)
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "system.reg").write_text(CONTROLLER_ONLY)

    prefix_module.repair(prefix, proton)
    assert recorded["command"][:3] == [str(wine), "reg", "add"]
    assert recorded["command"][3].endswith("ActivatableClassId\\Windows.System.DispatcherQueue")
    assert any("coremessaging.dll" in part for part in recorded["command"])
    assert recorded["env"]["WINEPREFIX"] == str(prefix)


def test_a_nonzero_exit_is_reported_not_raised(tmp_path, monkeypatch):
    proton = tmp_path / "Proton"
    wine = proton / "files" / "bin" / "wine"
    wine.parent.mkdir(parents=True)
    wine.write_text("stub")

    class Finished:
        returncode = 5
        stderr = "Unable to open registry\n"

    monkeypatch.setattr(prefix_module.process, "run", lambda command, **kwargs: Finished())
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "system.reg").write_text(CONTROLLER_ONLY)
    assert "exited 5" in prefix_module.repair(prefix, proton)[0]


def test_marker_matches_how_wine_writes_the_key(tmp_path):
    """Wine doubles every backslash in system.reg, not just the last one."""
    assert prefix_module.marker("Windows.System.DispatcherQueue") == (
        "[Software\\\\Microsoft\\\\WindowsRuntime\\\\ActivatableClassId\\\\Windows.System.DispatcherQueue]"
    )
