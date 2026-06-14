"""Verify Windows Security event-log field maps against REAL records.

The ``WinEventLogSource._INSERTS`` table maps positional ``StringInserts`` to
named fields per Microsoft's documented schema. Those positions are only
exercised on Windows-with-admin and are NOT covered by the cross-platform unit
tests (only the pure ``win_event_to_ecs`` mapper is). This script lets you
sanity-check the positions against the machine's actual Security log.

Run in an **Administrator** terminal (reading the Security channel needs admin):

    cd backend
    python scripts/verify_winevent.py

For each recent record whose Event ID we map (4625/4624/4740/4688/4672), it
prints the raw ``StringInserts``, the named fields our positional map extracts,
and the resulting ECS event — so you can confirm IpAddress / TargetUserName /
NewProcessName land in the right fields. If nothing shows, trigger an event
(e.g. a failed ``runas`` for a 4625) and re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import win32evtlog  # type: ignore[import-not-found]

# Allow running as `python scripts/verify_winevent.py` from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sources.winevent_source import _INSERTS, _WANTED_IDS, win_event_to_ecs  # noqa: E402

CHANNEL = "Security"
SCAN_LIMIT = 400   # how many recent records to scan
SHOW_LIMIT = 12    # how many matching records to print


def main() -> int:
    if sys.platform != "win32":
        print("Windows only.")
        return 1

    try:
        handle = win32evtlog.OpenEventLog(None, CHANNEL)
    except Exception as exc:
        print(f"Cannot open the Security log — run this in an Administrator terminal. ({exc!r})")
        return 2

    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    scanned = 0
    shown = 0
    try:
        while scanned < SCAN_LIMIT and shown < SHOW_LIMIT:
            batch = win32evtlog.ReadEventLog(handle, flags, 0)
            if not batch:
                break
            for ev in batch:
                scanned += 1
                eid = ev.EventID & 0xFFFF
                if eid not in _WANTED_IDS:
                    continue
                inserts = list(ev.StringInserts or [])
                names = _INSERTS[eid]
                data = {names[i]: inserts[i] for i in names if i < len(inserts)}
                rec = {
                    "event_id": eid,
                    "computer": ev.ComputerName,
                    "time_generated": ev.TimeGenerated.Format("%Y-%m-%dT%H:%M:%S"),
                    "data": data,
                }
                ecs = win_event_to_ecs(rec)
                src = (ecs or {}).get("source", {}).get("ip")
                user = (ecs or {}).get("user", {}).get("name")
                proc = (ecs or {}).get("process", {}).get("name")
                print("=" * 72)
                print(f"EventID={eid}  Computer={ev.ComputerName}  Time={rec['time_generated']}")
                print(f"  raw StringInserts : {inserts}")
                print(f"  extracted fields  : {data}")
                print(f"  -> ECS            : category={ecs['event']['category']} "
                      f"outcome={ecs['event'].get('outcome')} source.ip={src} user={user} process={proc}")
                shown += 1
                if shown >= SHOW_LIMIT:
                    break
    finally:
        win32evtlog.CloseEventLog(handle)

    if shown == 0:
        print(f"No mapped Security records in the last {SCAN_LIMIT} entries. "
              f"Trigger one (e.g. a failed `runas`) and re-run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
