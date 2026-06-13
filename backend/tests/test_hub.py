"""ConnectionHub: register, broadcast, drop dead clients."""

from __future__ import annotations

from app.hub import ConnectionHub


class _FakeWS:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(text)


async def test_broadcast_sends_json_to_all():
    hub = ConnectionHub()
    a, b = _FakeWS(), _FakeWS()
    await hub.register(a)
    await hub.register(b)

    await hub.broadcast({"tick": 1, "event": None})

    assert a.sent == ['{"tick": 1, "event": null}']
    assert b.sent == ['{"tick": 1, "event": null}']
    assert hub.count == 2


async def test_broadcast_drops_dead_clients():
    hub = ConnectionHub()
    good, bad = _FakeWS(), _FakeWS(fail=True)
    await hub.register(good)
    await hub.register(bad)

    await hub.broadcast({"tick": 1})

    assert hub.count == 1            # dead client removed
    assert len(good.sent) == 1


async def test_unregister_removes_client():
    hub = ConnectionHub()
    a = _FakeWS()
    await hub.register(a)
    hub.unregister(a)
    await hub.broadcast({"tick": 1})
    assert a.sent == []
    assert hub.count == 0
