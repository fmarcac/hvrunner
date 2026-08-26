from __future__ import annotations

from pathlib import Path

import pytest

from hvrunner.core.browsing import PARENT_NAME, Want, human_size, listing, start_directory


@pytest.fixture
def tree(tmp_path):
    """A folder with a subdirectory, a game, a plain file and a hidden prefix."""
    (tmp_path / "Hitman").mkdir()
    (tmp_path / ".hvrunner-proton").mkdir()
    (tmp_path / "HMA.exe").write_text("stub")
    (tmp_path / "readme.txt").write_text("stub")
    return tmp_path


def names(entries):
    return [entry.name for entry in entries]


def test_directory_mode_lists_no_files(tree):
    assert names(listing(tree, Want.DIRECTORY)) == [PARENT_NAME, "Hitman/"]


def test_executable_mode_lists_directories_and_exes(tree):
    assert names(listing(tree, Want.EXECUTABLE)) == [PARENT_NAME, "Hitman/", "HMA.exe"]


def test_a_plain_file_is_not_offered_as_something_to_launch(tree):
    """readme.txt is neither a Windows program nor executable."""
    assert "readme.txt" not in names(listing(tree, Want.EXECUTABLE))


def test_a_native_binary_is_offered_without_an_extension(tree):
    """A Linux build's launcher has the executable bit instead of a suffix."""
    launcher = tree / "start"
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)
    assert "start" in names(listing(tree, Want.EXECUTABLE))


def test_a_batch_file_is_offered(tree):
    (tree / "play.bat").write_text("stub")
    assert "play.bat" in names(listing(tree, Want.EXECUTABLE))


def test_hidden_entries_are_skipped(tree):
    """The Proton prefix lives in the game folder and holds a whole Windows tree."""
    assert not any(".hvrunner-proton" in name for name in names(listing(tree, Want.DIRECTORY)))


def test_directories_sort_before_files(tree):
    (tree / "aaa.exe").write_text("stub")
    assert names(listing(tree, Want.EXECUTABLE)) == [PARENT_NAME, "Hitman/", "aaa.exe", "HMA.exe"]


def test_root_offers_no_parent():
    assert PARENT_NAME not in names(listing(Path("/"), Want.DIRECTORY))


def test_unreadable_directory_still_offers_the_way_out(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o000)
    try:
        assert names(listing(locked, Want.EXECUTABLE)) == [PARENT_NAME]
    finally:
        locked.chmod(0o755)


def test_a_file_size_is_reported(tree):
    entry = next(item for item in listing(tree, Want.EXECUTABLE) if item.name == "HMA.exe")
    assert entry.size == len("stub")


def test_start_directory_uses_what_was_typed(tree):
    assert start_directory(str(tree / "Hitman"), Path.home()) == tree / "Hitman"


def test_start_directory_climbs_to_what_exists(tree):
    """A path being typed names a folder that exists even before the file does."""
    typed = str(tree / "Hitman" / "nothing here" / "HMA.exe")
    assert start_directory(typed, Path.home()) == tree / "Hitman"


def test_start_directory_falls_back_when_nothing_is_typed(tree):
    assert start_directory("   ", tree) == tree


def test_start_directory_climbs_out_of_a_fallback_that_is_gone(tmp_path):
    """A library folder can be deleted after it was configured."""
    assert start_directory("", tmp_path / "missing") == tmp_path


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "0B"), (512, "512B"), (1024, "1.0K"), (35651584, "34.0M")],
)
def test_human_size(count, expected):
    assert human_size(count) == expected
