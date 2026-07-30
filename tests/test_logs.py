from __future__ import annotations

from hvrunner.constants import log_dir
from hvrunner.logs import LogReader, classify, clean_line, new_log_path, prune_logs, recent_logs
from hvrunner.models import Game


def make_game(name="Black Flag"):
    return Game(name, "Custom", "/games/bf", "/games/bf/game.exe")


def test_clean_line_strips_ansi():
    assert clean_line("\x1b[31mred\x1b[0m text") == "red text"


def test_clean_line_keeps_last_carriage_return_segment():
    assert clean_line("10%\r50%\r100%") == "100%"


def test_clean_line_strips_control_characters():
    assert clean_line("a\x00b\x07c") == "abc"


def test_clean_line_strips_osc_titles():
    assert clean_line("\x1b]0;window title\x07done") == "done"


def test_classify_command_header():
    assert classify("$ gamemoderun mangohud umu-run game.exe") == "command"


def test_classify_known_noise_beats_error_wording():
    """The expected gamemode line contains "cannot open", so noise wins."""
    assert classify("gamemodeauto: dlopen failed - libgamemode.so: cannot open shared object file") == "noise"
    assert classify("[MANGOHUD] process 'explorer.exe' is blacklisted in MangoHud") == "noise"
    assert classify("[error] No player is being controlled by playerctld") == "noise"
    assert classify("X Error of failed request:  XI_BadDevice") == "noise"


def test_classify_real_error():
    assert classify("vulkan: failed to create device") == "error"


def test_classify_warning():
    assert classify("wine: deprecated call used") == "warning"


def test_classify_plain():
    assert classify("Spawning child process") == "plain"


def test_new_log_path_is_named_by_time_and_game(state_home):
    path = new_log_path(make_game(), now=0)
    assert path.parent == log_dir()
    assert path.name.endswith("-black-flag.log")
    assert path.parent.is_dir()


def test_prune_keeps_the_newest(state_home):
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(8):
        (directory / f"2026010{index}-000000-game.log").write_text("x")
    prune_logs(keep=3)
    remaining = sorted(path.name for path in directory.glob("*.log"))
    assert len(remaining) == 3
    assert remaining[-1] == "20260107-000000-game.log"


def test_recent_logs_is_newest_first(state_home):
    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("20260101-000000-a.log", "20260202-000000-b.log"):
        (directory / name).write_text("x")
    assert [path.name for path in recent_logs()][0] == "20260202-000000-b.log"


def test_recent_logs_without_directory(state_home):
    assert recent_logs() == []


def test_reader_appends_incrementally(tmp_path):
    path = tmp_path / "a.log"
    path.write_text("first\nsecond\n")
    reader = LogReader(path)
    assert reader.poll() is True
    assert reader.lines == ["first", "second"]
    # No growth means nothing new.
    assert reader.poll() is False
    with path.open("a") as handle:
        handle.write("third\n")
    assert reader.poll() is True
    assert reader.lines == ["first", "second", "third"]


def test_reader_holds_partial_lines_until_complete(tmp_path):
    path = tmp_path / "a.log"
    path.write_text("compl")
    reader = LogReader(path)
    reader.poll()
    assert reader.lines == []
    with path.open("a") as handle:
        handle.write("ete\n")
    reader.poll()
    assert reader.lines == ["complete"]


def test_reader_restarts_after_truncation(tmp_path):
    path = tmp_path / "a.log"
    path.write_text("one\ntwo\n")
    reader = LogReader(path)
    reader.poll()
    path.write_text("fresh\n")
    reader.poll()
    assert reader.lines == ["fresh"]


def test_reader_tolerates_missing_file(tmp_path):
    reader = LogReader(tmp_path / "absent.log")
    assert reader.poll() is False
    assert reader.lines == []


def test_reader_limits_initial_read(tmp_path):
    path = tmp_path / "big.log"
    path.write_text("".join(f"line{index}\n" for index in range(5000)))
    reader = LogReader(path, tail_bytes=200)
    reader.poll()
    assert 0 < len(reader.lines) < 50
    assert reader.lines[-1] == "line4999"


def test_reader_discards_the_partial_first_line_after_seeking(tmp_path):
    """Seeking to a byte offset lands mid line; that fragment must not show."""
    path = tmp_path / "big.log"
    path.write_text("".join(f"line{index:05d}\n" for index in range(1000)))
    reader = LogReader(path, tail_bytes=50)
    reader.poll()
    # Every surviving line is whole, not a tail such as "ne00993".
    assert all(line.startswith("line") for line in reader.lines), reader.lines


def test_reader_keeps_all_lines_when_under_the_limit(tmp_path):
    path = tmp_path / "small.log"
    path.write_text("alpha\nbeta\n")
    reader = LogReader(path, tail_bytes=10_000)
    reader.poll()
    assert reader.lines == ["alpha", "beta"]


def test_reader_decodes_invalid_utf8(tmp_path):
    path = tmp_path / "a.log"
    path.write_bytes(b"good\n\xff\xfe bad\n")
    reader = LogReader(path)
    reader.poll()
    assert reader.lines[0] == "good"
    assert len(reader.lines) == 2
