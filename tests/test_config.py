from __future__ import annotations

import json

import pytest

from hvrunner.config import default_config, expand, load_config, save_config
from hvrunner.models import HvrunnerError


def test_missing_file_yields_defaults(tmp_path):
    assert load_config(tmp_path / "absent.json") == default_config()


def test_rejects_string_where_list_expected(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"library_roots": "/not/a/list"}))
    with pytest.raises(HvrunnerError, match="library_roots"):
        load_config(path)


def test_rejects_string_where_bool_expected(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"enforce_all_cpus": "yes"}))
    with pytest.raises(HvrunnerError, match="enforce_all_cpus"):
        load_config(path)


def test_rejects_list_where_dict_expected(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"extra_env": ["FOO=bar"]}))
    with pytest.raises(HvrunnerError, match="extra_env"):
        load_config(path)


def test_rejects_non_object_top_level(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(HvrunnerError, match="must be an object"):
        load_config(path)


def test_accepts_valid_values(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"library_roots": ["/ok"], "enforce_all_cpus": False, "extra_env": {"A": "b"}}))
    loaded = load_config(path)
    assert loaded["library_roots"] == ["/ok"]
    assert loaded["enforce_all_cpus"] is False
    assert loaded["extra_env"] == {"A": "b"}


def test_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"nonsense": 1}))
    assert "nonsense" not in load_config(path)


def test_save_creates_parents_and_leaves_no_temp(tmp_path):
    path = tmp_path / "nested" / "cfg.with.dots.json"
    save_config(path, default_config())
    assert path.is_file()
    assert not list(path.parent.glob("*.tmp"))
    assert json.loads(path.read_text())["enforce_all_cpus"] is True


def test_save_round_trips(tmp_path):
    path = tmp_path / "c.json"
    values = default_config()
    values["favorites"] = ["Custom:/x/y.exe"]
    save_config(path, values)
    assert load_config(path)["favorites"] == ["Custom:/x/y.exe"]


def test_expand_resolves_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert expand("~/games") == str(tmp_path / "games")
