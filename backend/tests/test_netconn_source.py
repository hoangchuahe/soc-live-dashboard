"""NetConnSource: priming + diff of newly-established connections."""

from __future__ import annotations

from app.sources.base import Source
from app.sources.netconn_source import NetConnSource


class _Addr:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port


class _Conn:
    def __init__(self, rip, rport, pid, status="ESTABLISHED"):
        self.laddr = _Addr("192.168.1.10", 5000)
        self.raddr = _Addr(rip, rport) if rip else ()
        self.pid = pid
        self.status = status


class _FakePsutil:
    def __init__(self, conns):
        self._conns = conns

    def net_connections(self, kind="inet"):
        return self._conns

    def Process(self, pid):  # noqa: N802 - mirrors psutil API
        raise Exception("no name in test")


def test_is_a_source():
    assert isinstance(NetConnSource(psutil_module=_FakePsutil([])), Source)


def test_first_poll_primes_and_emits_nothing():
    fake = _FakePsutil([_Conn("8.8.8.8", 443, 1000)])
    src = NetConnSource(psutil_module=fake)
    assert src.poll() == []          # priming poll seeds baseline


def test_emits_only_new_connections():
    c1 = _Conn("8.8.8.8", 443, 1000)
    fake = _FakePsutil([c1])
    src = NetConnSource(psutil_module=fake)
    src.poll()                                    # prime with c1

    c2 = _Conn("1.1.1.1", 80, 2000)
    fake._conns = [c1, c2]                         # c1 still there, c2 is new
    events = src.poll()

    assert len(events) == 1
    e = events[0]
    assert e["destination"]["ip"] == "1.1.1.1"
    assert e["source"]["ip"] == "192.168.1.10"
    assert e["event"]["category"] == "network"
    assert e["event"]["dataset"] == "host.network"
    assert "labels" not in e                        # live events carry no provenance label


def test_ignores_non_established_and_no_raddr():
    listening = _Conn(None, 0, 3000, status="LISTEN")
    fake = _FakePsutil([listening])
    src = NetConnSource(psutil_module=fake)
    src.poll()
    fake._conns = [listening]
    assert src.poll() == []
