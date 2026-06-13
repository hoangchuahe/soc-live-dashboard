"""ProcessSource: priming + diff of newly-started processes."""

from __future__ import annotations

from app.sources.base import Source
from app.sources.process_source import ProcessSource


class _Proc:
    def __init__(self, pid, name, ppid=1, cmdline=None):
        self.info = {"pid": pid, "name": name, "ppid": ppid,
                     "cmdline": cmdline or [name], "create_time": 0.0}


class _FakePsutil:
    def __init__(self, procs):
        self._procs = procs

    def process_iter(self, attrs=None):
        return self._procs


def test_is_a_source():
    assert isinstance(ProcessSource(psutil_module=_FakePsutil([])), Source)


def test_first_poll_primes_and_emits_nothing():
    fake = _FakePsutil([_Proc(100, "explorer.exe")])
    src = ProcessSource(psutil_module=fake)
    assert src.poll() == []


def test_emits_only_new_processes():
    p1 = _Proc(100, "explorer.exe")
    fake = _FakePsutil([p1])
    src = ProcessSource(psutil_module=fake)
    src.poll()                                       # prime

    p2 = _Proc(200, "powershell.exe", ppid=100, cmdline=["powershell.exe", "-enc", "AAA"])
    fake._procs = [p1, p2]
    events = src.poll()

    assert len(events) == 1
    e = events[0]
    assert e["process"]["name"] == "powershell.exe"
    assert e["event"]["category"] == "process"
    assert e["event"]["action"] == "process_start"
    assert e["event"]["dataset"] == "host.process"
