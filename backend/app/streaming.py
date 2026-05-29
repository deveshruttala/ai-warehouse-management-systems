"""Event streaming layer.

A small abstraction over a publish/subscribe event bus with two interchangeable
backends:

* ``memory`` - an in-process asyncio fan-out bus (zero dependencies, ideal for
  local dev / single-node deployments and tests).
* ``redis``  - Redis Streams (``XADD`` / ``XREAD``), giving durability, multiple
  consumers and horizontal scale for production.

Both expose the same interface: :meth:`EventBus.publish` and
:meth:`EventBus.subscribe` (an async iterator of :class:`Event`).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from .config import settings
from .schemas import Event

log = logging.getLogger("sis.streaming")


class EventBus:
    """Abstract interface for the event bus."""

    async def start(self) -> None:  # pragma: no cover - trivial
        ...

    async def stop(self) -> None:  # pragma: no cover - trivial
        ...

    async def publish(self, event: Event) -> None:
        raise NotImplementedError

    def subscribe(self) -> AsyncIterator[Event]:
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    """Fan-out bus backed by per-subscriber asyncio queues."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._maxsize = maxsize
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest item to keep real-time consumers current.
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._maxsize)
        async with self._lock:
            self._subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            async with self._lock:
                self._subscribers.discard(q)


class RedisStreamBus(EventBus):
    """Redis Streams backend (durable, multi-consumer)."""

    def __init__(self, url: str, stream: str, maxlen: int = 100_000) -> None:
        self._url = url
        self._stream = stream
        self._maxlen = maxlen
        self._redis = None

    async def start(self) -> None:
        import redis.asyncio as aioredis  # lazy import

        self._redis = aioredis.from_url(self._url, decode_responses=True)
        await self._redis.ping()
        log.info("Connected to Redis stream backend at %s", self._url)

    async def stop(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()

    async def publish(self, event: Event) -> None:
        assert self._redis is not None, "RedisStreamBus.start() not called"
        await self._redis.xadd(
            self._stream,
            {"data": event.model_dump_json()},
            maxlen=self._maxlen,
            approximate=True,
        )

    async def subscribe(self) -> AsyncIterator[Event]:
        assert self._redis is not None, "RedisStreamBus.start() not called"
        last_id = "$"  # only new messages
        while True:
            resp = await self._redis.xread({self._stream: last_id}, block=5000, count=64)
            if not resp:
                continue
            _, messages = resp[0]
            for msg_id, fields in messages:
                last_id = msg_id
                yield Event.model_validate_json(fields["data"])


_bus: EventBus | None = None


def get_bus() -> EventBus:
    """Return the process-wide event bus (created lazily from settings)."""
    global _bus
    if _bus is None:
        if settings.stream_backend == "redis":
            _bus = RedisStreamBus(settings.redis_url, settings.stream_name)
        else:
            _bus = InMemoryEventBus()
    return _bus
