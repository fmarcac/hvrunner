from __future__ import annotations

import json

from hvrunner.display import Monitor, focused_monitor, parse_monitors

PAYLOAD = json.dumps(
    [
        {
            "name": "DP-3",
            "width": 2560,
            "height": 1440,
            "refreshRate": 200.013,
            "x": 0,
            "y": 0,
            "scale": 1.25,
            "focused": True,
        },
        {
            "name": "HDMI-A-1",
            "width": 1920,
            "height": 1080,
            "refreshRate": 60.0,
            "x": 2560,
            "y": 0,
            "scale": 1.0,
            "focused": False,
        },
    ]
)


def test_parses_every_monitor():
    found = parse_monitors(PAYLOAD)
    assert [monitor.name for monitor in found] == ["DP-3", "HDMI-A-1"]
    assert found[0].scale == 1.25
    assert found[0].refresh == 200.013


def test_spec_round_trips_into_hyprctl_form():
    monitor = parse_monitors(PAYLOAD)[0]
    assert monitor.spec(1.0) == "DP-3,2560x1440@200.013,0x0,1"
    assert monitor.spec(1.25) == "DP-3,2560x1440@200.013,0x0,1.25"


def test_scaled_detects_fractional_scaling():
    monitors = parse_monitors(PAYLOAD)
    assert monitors[0].scaled is True
    assert monitors[1].scaled is False


def test_scaled_tolerates_float_error():
    assert Monitor("X", 1, 1, 60.0, 0, 0, 1.0000001).scaled is False


def test_malformed_payloads_yield_nothing():
    assert parse_monitors("not json") == []
    assert parse_monitors(json.dumps({"not": "a list"})) == []
    assert parse_monitors("") == []


def test_entries_missing_fields_are_skipped():
    payload = json.dumps([{"name": "DP-1"}, {"name": "DP-2", "width": 800, "height": 600, "refreshRate": 60}])
    assert [monitor.name for monitor in parse_monitors(payload)] == ["DP-2"]


def test_non_dict_entries_are_skipped():
    payload = json.dumps(["nonsense", 42, {"name": "DP-2", "width": 8, "height": 6, "refreshRate": 60}])
    assert len(parse_monitors(payload)) == 1


def test_focused_monitor_picks_the_focused_one(monkeypatch):
    import hvrunner.display as display_module

    monkeypatch.setattr(display_module, "_run", lambda arguments: PAYLOAD)
    monitor = focused_monitor()
    assert monitor is not None
    assert monitor.name == "DP-3"


def test_focus_is_carried_on_the_monitor():
    found = parse_monitors(PAYLOAD)
    assert [monitor.focused for monitor in found] == [True, False]


def test_focused_monitor_falls_back_to_the_first(monkeypatch):
    """hyprctl can report every output unfocused, and a scale still has to be read."""
    import hvrunner.display as display_module

    payload = json.dumps([{"name": "DP-9", "width": 800, "height": 600, "refreshRate": 60}])
    monkeypatch.setattr(display_module, "_run", lambda arguments: payload)
    monitor = focused_monitor()
    assert monitor is not None
    assert monitor.name == "DP-9"


def test_focused_monitor_without_hyprctl(monkeypatch):
    import hvrunner.display as display_module

    monkeypatch.setattr(display_module, "_run", lambda arguments: None)
    assert focused_monitor() is None
