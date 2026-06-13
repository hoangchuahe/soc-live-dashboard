"""WinEventLogSource: pure event-id -> ECS mapper (cross-platform)."""

from __future__ import annotations

import sys

import pytest

from app.sources.winevent_source import WinEventLogSource, win_event_to_ecs


def _rec(event_id, data, computer="WKS-HOANG-01", ts="2026-06-14T00:00:00+00:00"):
    return {"event_id": event_id, "computer": computer, "time_generated": ts, "data": data}


def test_4625_failed_logon_maps_to_auth_failure():
    rec = _rec(4625, {"TargetUserName": "administrator", "IpAddress": "203.0.113.42"})
    evt = win_event_to_ecs(rec)
    assert evt is not None
    assert evt["event"]["category"] == "authentication"
    assert evt["event"]["outcome"] == "failure"
    assert evt["event"]["action"] == "auth_failure"
    assert evt["event"]["dataset"] == "windows.security"
    assert evt["source"]["ip"] == "203.0.113.42"
    assert evt["user"]["name"] == "administrator"
    assert evt["host"]["name"] == "WKS-HOANG-01"
    assert "labels" not in evt   # real event


def test_4624_successful_logon_maps_to_success():
    rec = _rec(4624, {"TargetUserName": "h.pham", "IpAddress": "192.168.1.5"})
    evt = win_event_to_ecs(rec)
    assert evt["event"]["category"] == "authentication"
    assert evt["event"]["outcome"] == "success"


def test_4740_lockout_maps_to_auth_failure():
    evt = win_event_to_ecs(_rec(4740, {"TargetUserName": "guest"}))
    assert evt["event"]["category"] == "authentication"
    assert evt["event"]["outcome"] == "failure"
    assert evt["user"]["name"] == "guest"


def test_4688_process_creation_maps_to_process():
    rec = _rec(4688, {"NewProcessName": "C:\\Windows\\System32\\cmd.exe", "SubjectUserName": "h.pham"})
    evt = win_event_to_ecs(rec)
    assert evt["event"]["category"] == "process"
    assert evt["event"]["action"] == "process_start"
    assert evt["process"]["name"] == "cmd.exe"


def test_unknown_event_id_returns_none():
    assert win_event_to_ecs(_rec(9999, {})) is None


def test_missing_ip_omits_source_block():
    evt = win_event_to_ecs(_rec(4625, {"TargetUserName": "bob", "IpAddress": "-"}))
    assert "source" not in evt   # "-" is treated as no IP


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only event log read")
def test_preflight_on_windows_reports_status():
    st = WinEventLogSource().preflight()
    assert st.name == "windows.security"
    # available True (admin) or False (requires admin) — both are valid here
    assert isinstance(st.available, bool)


def test_preflight_off_windows_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.sources.winevent_source.sys", _FakeSys("linux"))
    st = WinEventLogSource().preflight()
    assert st.available is False


class _FakeSys:
    def __init__(self, platform):
        self.platform = platform
