from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from ..ecs import make_event
from .base import SourceStatus

DATASET = "windows.security"

# Windows Security event IDs we translate into ECS.
_SEVERITY = {4625: "high", 4740: "high", 4688: "low", 4624: "low", 4672: "medium"}


def _clean_ip(value: str | None) -> str | None:
    if not value or value in {"-", "::1", "127.0.0.1", ""}:
        return None
    return value


def win_event_to_ecs(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Map a normalized Security-log record to an ECS event, or None if unknown.

    `rec` shape: {"event_id": int, "computer": str, "time_generated": iso-str,
                  "data": {field_name: value}}  (field names per MS schema).
    """
    eid = rec.get("event_id")
    data = rec.get("data", {}) or {}
    host = rec.get("computer")
    ts = rec.get("time_generated") or datetime.now(UTC).isoformat()
    sev = _SEVERITY.get(eid, "low")

    if eid in (4625, 4624):
        outcome = "failure" if eid == 4625 else "success"
        action = "auth_failure" if eid == 4625 else "logon"
        user = data.get("TargetUserName")
        return make_event(
            event_id=f"win-{eid}-{ts}",
            timestamp=ts, category="authentication", action=action, outcome=outcome,
            severity=sev, module="winevent",
            message=f"Windows {eid} logon {'failure' if eid == 4625 else 'success'} for {user}",
            source_ip=_clean_ip(data.get("IpAddress")),
            host_name=host, user_name=user, dataset=DATASET,
        )

    if eid == 4740:
        user = data.get("TargetUserName")
        return make_event(
            event_id=f"win-{eid}-{ts}", timestamp=ts, category="authentication",
            action="lockout", outcome="failure", severity=sev, module="winevent",
            message=f"Account locked out: {user}",
            host_name=host, user_name=user, dataset=DATASET,
        )

    if eid == 4688:
        raw = data.get("NewProcessName") or ""
        name = raw.replace("\\", "/").rsplit("/", 1)[-1] or raw
        evt = make_event(
            event_id=f"win-{eid}-{ts}", timestamp=ts, category="process",
            action="process_start", outcome="unknown", severity=sev, module="winevent",
            message=f"Process created: {name}",
            host_name=host, user_name=data.get("SubjectUserName"),
            process_name=name, dataset=DATASET,
        )
        evt.setdefault("process", {"name": name})["command_line"] = raw
        return evt

    if eid == 4672:
        user = data.get("SubjectUserName")
        return make_event(
            event_id=f"win-{eid}-{ts}", timestamp=ts, category="iam",
            action="special_privileges", outcome="success", severity=sev, module="winevent",
            message=f"Special privileges assigned to {user}",
            host_name=host, user_name=user, dataset=DATASET,
        )

    return None


# Positional StringInserts -> field names, per Microsoft's documented schema.
# Used only by the Windows reader (not exercised on CI).
_INSERTS = {
    4625: {5: "TargetUserName", 6: "TargetDomainName", 10: "LogonType",
           18: "ProcessName", 19: "IpAddress", 20: "IpPort"},
    4624: {5: "TargetUserName", 6: "TargetDomainName", 8: "LogonType", 18: "IpAddress"},
    4740: {0: "TargetUserName", 1: "TargetDomainName"},
    4688: {1: "SubjectUserName", 5: "NewProcessName", 8: "ProcessName"},
    4672: {1: "SubjectUserName", 2: "SubjectDomainName"},
}
_WANTED_IDS = set(_INSERTS)


class WinEventLogSource:
    """Reads new records from the Windows Security channel and maps them to ECS.

    Windows-only. On other platforms / without admin it preflights as
    unavailable and is excluded from the active source set.
    """

    name = "windows.security"
    dataset = DATASET
    interval_seconds = 4.0
    CHANNEL = "Security"

    def __init__(self) -> None:
        self._handle: Any | None = None
        self._last_record: int | None = None
        self._win32evtlog: Any | None = None

    def preflight(self) -> SourceStatus:
        if sys.platform != "win32":
            return SourceStatus(name=self.name, available=False, detail="not Windows")
        try:
            import win32evtlog  # type: ignore[import-not-found]
        except Exception:
            return SourceStatus(name=self.name, available=False, detail="pywin32 not installed")
        try:
            handle = win32evtlog.OpenEventLog(None, self.CHANNEL)
            win32evtlog.GetNumberOfEventLogRecords(handle)
            win32evtlog.CloseEventLog(handle)
        except Exception as exc:  # access denied -> needs admin
            return SourceStatus(name=self.name, available=False,
                                detail=f"requires admin ({exc.__class__.__name__})")
        return SourceStatus(name=self.name, available=True, detail="ok")

    def poll(self) -> list[dict]:
        if sys.platform != "win32":
            return []
        records = self._read_new_records()
        events: list[dict] = []
        for rec in records:
            evt = win_event_to_ecs(rec)
            if evt is not None:
                events.append(evt)
        return events

    def _read_new_records(self) -> list[dict]:
        """Read records newer than the bookmark. Windows-only; not run on CI."""
        try:
            import win32evtlog  # type: ignore[import-not-found]
        except Exception:
            return []
        if self._handle is None:
            self._handle = win32evtlog.OpenEventLog(None, self.CHANNEL)
            self._win32evtlog = win32evtlog
            # Seed the bookmark at the newest record so we tail, not replay history.
            total = win32evtlog.GetNumberOfEventLogRecords(self._handle)
            oldest = win32evtlog.GetOldestEventLogRecord(self._handle)
            self._last_record = oldest + total - 1
            return []

        wl = self._win32evtlog
        flags = wl.EVENTLOG_FORWARDS_READ | wl.EVENTLOG_SEQUENTIAL_READ
        out: list[dict] = []
        while True:
            batch = wl.ReadEventLog(self._handle, flags, 0)
            if not batch:
                break
            for ev in batch:
                if self._last_record is not None and ev.RecordNumber <= self._last_record:
                    continue
                self._last_record = ev.RecordNumber
                eid = ev.EventID & 0xFFFF
                if eid not in _WANTED_IDS:
                    continue
                inserts = list(ev.StringInserts or [])
                names = _INSERTS[eid]
                data = {names[i]: inserts[i] for i in names if i < len(inserts)}
                out.append({
                    "event_id": eid,
                    "computer": ev.ComputerName,
                    "time_generated": ev.TimeGenerated.Format("%Y-%m-%dT%H:%M:%S"),
                    "data": data,
                })
        return out
