from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Debate, DebateStatus
from ..utils.logger import logger


@dataclass
class DebateRuntime:
    debate_id: int
    status: DebateStatus = DebateStatus.DRAFT
    task: Optional[asyncio.Task] = None
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)


class DebateEngineManager:
    _engines: dict[int, DebateRuntime] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def start_debate(cls, debate_id: int, session: AsyncSession) -> None:
        async with cls._lock:
            runtime = cls._engines.get(debate_id)
            if runtime and runtime.status == DebateStatus.RUNNING:
                raise ValueError("Debate already running")
            if runtime is None:
                runtime = DebateRuntime(debate_id=debate_id)
                cls._engines[debate_id] = runtime
            runtime.stop_event.clear()
            runtime.pause_event.clear()
            runtime.status = DebateStatus.RUNNING

            if runtime.task is None or runtime.task.done():
                runtime.task = asyncio.create_task(cls._runner(debate_id))

        debate = (await session.execute(select(Debate).where(Debate.id == debate_id))).scalar_one_or_none()
        if debate:
            debate.status = DebateStatus.RUNNING
            if not debate.started_at:
                debate.started_at = datetime.utcnow()
            await session.commit()

    @classmethod
    async def pause_debate(cls, debate_id: int) -> None:
        runtime = cls._engines.get(debate_id)
        if not runtime:
            return
        runtime.pause_event.set()
        runtime.status = DebateStatus.PAUSED

    @classmethod
    async def resume_debate(cls, debate_id: int) -> None:
        runtime = cls._engines.get(debate_id)
        if not runtime:
            return
        runtime.pause_event.clear()
        runtime.status = DebateStatus.RUNNING

    @classmethod
    async def stop_debate(cls, debate_id: int) -> None:
        runtime = cls._engines.get(debate_id)
        if not runtime:
            return
        runtime.stop_event.set()
        runtime.pause_event.clear()
        runtime.status = DebateStatus.FINISHED
        if runtime.task:
            runtime.task.cancel()
            try:
                await runtime.task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            runtime.task = None

    @classmethod
    async def remove_engine(cls, debate_id: int) -> None:
        runtime = cls._engines.pop(debate_id, None)
        if runtime and runtime.task:
            runtime.task.cancel()
            try:
                await runtime.task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    @classmethod
    async def cleanup_all(cls) -> None:
        ids = list(cls._engines.keys())
        for debate_id in ids:
            await cls.remove_engine(debate_id)
        cls._engines.clear()

    @classmethod
    async def _runner(cls, debate_id: int) -> None:
        runtime = cls._engines.get(debate_id)
        if not runtime:
            return
        logger.info(f"Debate runtime started: {debate_id}")
        try:
            while not runtime.stop_event.is_set():
                if runtime.pause_event.is_set():
                    await asyncio.sleep(0.5)
                    continue
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info(f"Debate runtime stopped: {debate_id}")
