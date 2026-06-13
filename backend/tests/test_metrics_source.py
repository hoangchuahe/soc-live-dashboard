"""PsutilMetricsProvider with an injected fake psutil + clock."""

from __future__ import annotations

from app.sources.base import MetricsProvider
from app.sources.metrics_source import PsutilMetricsProvider


class _FakeMem:
    percent = 61.5


class _FakeDisk:
    percent = 55.0


class _FakeNetIO:
    def __init__(self, sent, recv):
        self.bytes_sent = sent
        self.bytes_recv = recv


class _FakePsutil:
    def __init__(self):
        self._net = _FakeNetIO(0, 0)

    def cpu_percent(self, interval=None):
        return 42.0

    def virtual_memory(self):
        return _FakeMem()

    def disk_usage(self, path):
        return _FakeDisk()

    def net_io_counters(self):
        return self._net

    def net_connections(self, kind="inet"):
        return [object(), object(), object()]   # 3 connections


def test_is_a_metrics_provider():
    assert isinstance(PsutilMetricsProvider(psutil_module=_FakePsutil()), MetricsProvider)


def test_reads_cpu_mem_disk_conns():
    fake = _FakePsutil()
    clock = iter([100.0, 101.0])
    p = PsutilMetricsProvider(psutil_module=fake, clock=lambda: next(clock))

    first = p.read()   # primes net counters; mbps 0 on first read
    assert first["cpu_percent"] == 42.0
    assert first["memory_percent"] == 61.5
    assert first["disk_percent"] == 55.0
    assert first["active_connections"] == 3
    assert first["network_in_mbps"] == 0.0
    assert first["network_out_mbps"] == 0.0


def test_network_mbps_computed_from_delta():
    fake = _FakePsutil()
    clock = iter([100.0, 101.0])   # 1 second elapsed between reads
    p = PsutilMetricsProvider(psutil_module=fake, clock=lambda: next(clock))

    p.read()                                  # prime at t=100, bytes 0/0
    fake._net = _FakeNetIO(125_000, 250_000)  # +125000 sent, +250000 recv over 1s
    second = p.read()                          # t=101

    # 125000 bytes/s * 8 / 1e6 = 1.0 Mbps out;  250000 -> 2.0 Mbps in
    assert second["network_out_mbps"] == 1.0
    assert second["network_in_mbps"] == 2.0


def test_read_is_defensive(monkeypatch):
    class _Broken(_FakePsutil):
        def virtual_memory(self):
            raise OSError("denied")

    p = PsutilMetricsProvider(psutil_module=_Broken())
    out = p.read()           # must not raise
    assert out["memory_percent"] == 0.0
