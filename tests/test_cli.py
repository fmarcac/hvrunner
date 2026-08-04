from __future__ import annotations

from hvrunner.cli import build_parser, main


def test_install_flag_is_parsed():
    args = build_parser().parse_args(["--install", "/tmp/setup.exe", "--name", "Witcher3"])
    assert args.install == "/tmp/setup.exe"
    assert args.name == "Witcher3"


def test_install_rejects_a_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HVRUNNER_CONFIG", str(tmp_path / "config.json"))
    assert main(["--install", str(tmp_path / "absent.exe")]) == 1
    assert "absent.exe" in capsys.readouterr().err
