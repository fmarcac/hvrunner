from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core import installer
from hvrunner.core.models import HvrunnerError


def test_prepare_target_creates_the_folder(tmp_path):
    target = installer.prepare_target(tmp_path, "Witcher3")
    assert target == tmp_path / "Witcher3"
    assert target.is_dir()


def test_prepare_target_refuses_an_existing_folder(tmp_path):
    (tmp_path / "Witcher3").mkdir()
    with pytest.raises(HvrunnerError, match="already exists"):
        installer.prepare_target(tmp_path, "Witcher3")


def test_install_command_is_bare(tmp_path, config, stub_tools):
    """No MangoHud, no gamemode: neither means anything for a setup wizard."""
    source = tmp_path / "setup.exe"
    source.write_text("stub")
    target = installer.prepare_target(tmp_path, "Witcher3")
    command, environment, prefix = installer.install_command(source, target, config)
    proton = Path(config["proton_path"]) / "proton"
    assert command == [str(proton), "waitforexitandrun", str(source)]
    assert "MANGOHUD" not in environment
    assert prefix == target / ".hvrunner-proton"
    assert environment["WINEPREFIX"] == str(prefix)


def test_install_command_rejects_a_missing_installer(tmp_path, config, stub_tools):
    target = installer.prepare_target(tmp_path, "Witcher3")
    with pytest.raises(HvrunnerError, match="installer"):
        installer.install_command(tmp_path / "absent.exe", target, config)


def _prefix_with(tmp_path, *relative: str) -> Path:
    prefix = tmp_path / ".hvrunner-proton"
    for item in relative:
        path = prefix / "pfx" / "drive_c" / item
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stub")
    return prefix


def test_discover_finds_the_installed_binary(tmp_path):
    prefix = _prefix_with(tmp_path, "Program Files/Witcher3/witcher3.exe")
    assert [path.name for path in installer.discover(prefix, "Witcher3")] == ["witcher3.exe"]


def test_discover_ranks_the_name_match_first(tmp_path):
    prefix = _prefix_with(
        tmp_path,
        "Program Files/Witcher3/launcher.exe",
        "Program Files/Witcher3/witcher3.exe",
    )
    assert installer.discover(prefix, "Witcher3")[0].name == "witcher3.exe"


def test_discover_skips_windows_and_uninstallers(tmp_path):
    prefix = _prefix_with(
        tmp_path,
        "windows/system32/explorer.exe",
        "Program Files/Witcher3/unins000.exe",
        "Program Files/Witcher3/witcher3.exe",
    )
    assert [path.name for path in installer.discover(prefix, "Witcher3")] == ["witcher3.exe"]


def test_discover_on_an_empty_prefix(tmp_path):
    assert installer.discover(tmp_path / "absent", "Witcher3") == []
