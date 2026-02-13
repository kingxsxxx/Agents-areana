import json
import time
from typing import Any, Optional

import redis.asyncio as redis

from ..config import settings


class RedisClient:
    def __init__(self) -> None:
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._fallback: dict[str, tuple[Any, Optional[float]]] = {}

    async def init_pool(self) -> None:
        self._pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.REDIS_POOL_SIZE,
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        await self._client.ping()

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._client = None
        self._pool = None

    def _fallback_get(self, key: str) -> Optional[str]:
        item = self._fallback.get(key)
        if not item:
            return None
        value, expires_at = item
        if expires_at is not None and time.time() > expires_at:
            self._fallback.pop(key, None)
            return None
        return value

    def _fallback_set(self, key: str, value: str, expire: Optional[int]) -> None:
        expires_at = (time.time() + expire) if expire else None
        self._fallback[key] = (value, expires_at)

    async def get(self, key: str) -> Optional[str]:
        if self._client:
            return await self._client.get(key)
        return self._fallback_get(key)

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        ttl = expire or settings.REDIS_CACHE_TTL
        if self._client:
            return bool(await self._client.set(key, value, ex=ttl))
        self._fallback_set(key, value, ttl)
        return True

    async def delete(self, key: str) -> bool:
        if self._client:
            return bool(await self._client.delete(key))
        return self._fallback.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        if self._client:
            return bool(await self._client.exists(key))
        return self._fallback_get(key) is not None

    async def expire(self, key: str, seconds: int) -> bool:
        if self._client:
            return bool(await self._client.expire(key, seconds))
        value = self._fallback_get(key)
        if value is None:
            return False
        self._fallback_set(key, value, seconds)
        return True

    async def ttl(self, key: str) -> int:
        if self._client:
            return int(await self._client.ttl(key))
        item = self._fallback.get(key)
        if not item:
            return -2
        _, expires_at = item
        if expires_at is None:
            return -1
        return max(0, int(expires_at - time.time()))

    async def incr(self, key: str) -> int:
        if self._client:
            return int(await self._client.incr(key))
        current = int(self._fallback_get(key) or 0) + 1
        ttl = await self.ttl(key)
        self._fallback_set(key, str(current), ttl if ttl > 0 else None)
        return current

    async def decr(self, key: str) -> int:
        if self._client:
            return int(await self._client.decr(key))
        current = int(self._fallback_get(key) or 0) - 1
        ttl = await self.ttl(key)
        self._fallback_set(key, str(current), ttl if ttl > 0 else None)
        return current

    async def hget(self, name: str, key: str) -> Optional[str]:
        if self._client:
            return await self._client.hget(name, key)
        data = self._fallback_get(name)
        if not data:
            return None
        obj = json.loads(data)
        return obj.get(key)

    async def hset(self, name: str, key: str, value: str, expire: Optional[int] = None) -> bool:
        if self._client:
            result = await self._client.hset(name, key, value)
            if expire:
                await self._client.expire(name, expire)
            return bool(result)
        data = self._fallback_get(name)
        obj = json.loads(data) if data else {}
        obj[key] = value
        self._fallback_set(name, json.dumps(obj, ensure_ascii=False), expire)
        return True

    async def hgetall(self, name: str) -> dict:
        if self._client:
            return await self._client.hgetall(name)
        data = self._fallback_get(name)
        return json.loads(data) if data else {}

    async def hdel(self, name: str, *keys: str) -> int:
        if self._client:
            return int(await self._client.hdel(name, *keys))
        data = self._fallback_get(name)
        if not data:
            return 0
        obj = json.loads(data)
        deleted = 0
        for key in keys:
            if key in obj:
                deleted += 1
                obj.pop(key, None)
        self._fallback_set(name, json.dumps(obj, ensure_ascii=False), None)
        return deleted

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        return await self.set(key, json.dumps(value, ensure_ascii=False), expire)


redis_client = RedisClient()
