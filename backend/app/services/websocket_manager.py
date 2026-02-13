import asyncio
import json
import time
from collections import defaultdict
from typing import Any, Optional

from fastapi import WebSocket

from ..config import settings
from ..utils.logger import logger


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, dict[int, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, debate_id: int, user_id: Optional[int] = None) -> None:
        await websocket.accept()
        connection_id = user_id if user_id is not None else id(websocket)
        async with self._lock:
            self.active_connections[debate_id][connection_id] = websocket
        await self._safe_send(
            websocket,
            {"type": "connected", "debate_id": debate_id, "user_id": user_id},
        )

    async def disconnect(self, websocket: WebSocket, debate_id: int, user_id: Optional[int] = None) -> None:
        async with self._lock:
            if debate_id not in self.active_connections:
                return
            connection_id = user_id if user_id is not None else id(websocket)
            self.active_connections[debate_id].pop(connection_id, None)
            if not self.active_connections[debate_id]:
                self.active_connections.pop(debate_id, None)

    async def send_to_client(self, user_id: Optional[int], message: dict[str, Any], debate_id: Optional[int] = None) -> None:
        if debate_id is None:
            await self.broadcast(message, None)
            return
        if debate_id not in self.active_connections:
            return
        if user_id is None:
            await self.broadcast(message, debate_id)
            return
        websocket = self.active_connections[debate_id].get(user_id)
        if websocket:
            await self._safe_send(websocket, message)

    async def broadcast(self, message: dict[str, Any], debate_id: Optional[int]) -> None:
        targets: list[WebSocket] = []
        async with self._lock:
            if debate_id is None:
                for room in self.active_connections.values():
                    targets.extend(room.values())
            else:
                targets.extend(self.active_connections.get(debate_id, {}).values())

        for websocket in targets:
            await self._safe_send(websocket, message)

    async def send_notification(self, debate_id: int, notification_type: str, message: str) -> None:
        await self.broadcast(
            {
                "type": "notification",
                "notification_type": notification_type,
                "message": message,
            },
            debate_id,
        )

    async def close_all_connections(self) -> None:
        async with self._lock:
            all_sockets = [ws for room in self.active_connections.values() for ws in room.values()]
            self.active_connections.clear()
        for websocket in all_sockets:
            try:
                await websocket.close()
            except Exception:
                pass

    @staticmethod
    async def _safe_send(websocket: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            logger.warning(f"WebSocket send failed: {exc}")


class HeartbeatManager:
    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._heartbeats: dict[tuple[int, int], float] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._task = None
        self._heartbeats.clear()

    async def update(self, websocket: WebSocket, debate_id: int) -> None:
        self._heartbeats[(debate_id, id(websocket))] = time.time()

    async def _loop(self) -> None:
        try:
            while self._running:
                now = time.time()
                timeout = settings.WS_CONNECTION_TIMEOUT
                stale = [k for k, ts in self._heartbeats.items() if now - ts > timeout]
                for key in stale:
                    self._heartbeats.pop(key, None)
                await asyncio.sleep(max(5, settings.WS_HEARTBEAT_INTERVAL))
        except asyncio.CancelledError:
            return


ws_manager = WebSocketManager()
heartbeat_manager = HeartbeatManager()
