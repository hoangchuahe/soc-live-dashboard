from __future__ import annotations

import json
from typing import Any, Protocol


class _Sendable(Protocol):
    async def send_text(self, text: str) -> None: ...


class ConnectionHub:
    """Tracks connected WebSocket clients and broadcasts frames to all of them.

    A single Producer calls broadcast(); each client just registers and waits.
    Clients whose send raises are dropped so one dead socket can't wedge the loop.
    """

    def __init__(self) -> None:
        self._clients: set[_Sendable] = set()

    async def register(self, ws: _Sendable) -> None:
        self._clients.add(ws)

    def unregister(self, ws: _Sendable) -> None:
        self._clients.discard(ws)

    async def broadcast(self, frame: dict[str, Any]) -> None:
        text = json.dumps(frame, default=str)
        dead: list[_Sendable] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    @property
    def count(self) -> int:
        return len(self._clients)
