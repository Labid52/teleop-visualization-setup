"""Bounded latest-data queue with an explicit drop-oldest policy."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Generic, TypeVar


T = TypeVar("T")


class QueueClosed(RuntimeError):
    pass


@dataclass(frozen=True)
class QueueStats:
    max_size: int
    depth: int
    maximum_observed_depth: int
    produced: int
    consumed: int
    dropped_oldest: int


class DropOldestQueue(Generic[T]):
    """Keep memory bounded; when full, discard the oldest queued item."""

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._items: deque[T] = deque()
        self._condition = threading.Condition()
        self._closed = False
        self._produced = 0
        self._consumed = 0
        self._dropped_oldest = 0
        self._maximum_observed_depth = 0

    def put(self, item: T) -> None:
        with self._condition:
            if self._closed:
                raise QueueClosed("queue is closed")
            self._produced += 1
            if len(self._items) >= self._max_size:
                self._items.popleft()
                self._dropped_oldest += 1
            self._items.append(item)
            self._maximum_observed_depth = max(self._maximum_observed_depth, len(self._items))
            self._condition.notify()

    def get(self, timeout: float | None = None) -> T:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while not self._items:
                if self._closed:
                    raise QueueClosed("queue is closed")
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError
                self._condition.wait(remaining)
            self._consumed += 1
            return self._items.popleft()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def stats(self) -> QueueStats:
        with self._condition:
            return QueueStats(
                max_size=self._max_size,
                depth=len(self._items),
                maximum_observed_depth=self._maximum_observed_depth,
                produced=self._produced,
                consumed=self._consumed,
                dropped_oldest=self._dropped_oldest,
            )
