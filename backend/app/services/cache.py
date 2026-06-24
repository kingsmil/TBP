"""Stale-while-revalidate in-memory cache.

For shared, read-only aggregates that are identical for every user and only
change when the underlying data changes (e.g. the estate comparison). Computes a
value once, serves it instantly thereafter, and refreshes it in a background
thread when it ages past `ttl` — so after the first fill no request ever blocks
on a recompute; it gets the cached value and a refresh is kicked off behind it.

Thread-safe: the API runs sync handlers in a threadpool and refreshes run in
their own daemon threads.
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class SWRCache:
    def __init__(self, ttl: float = 3600.0):
        self._ttl = ttl
        self._lock = threading.Lock()
        # key -> [value, timestamp, refreshing]
        self._entries: dict = {}

    def get(self, key, compute: Callable):
        with self._lock:
            entry = self._entries.get(key)
        if entry is None:
            value = compute()                      # first time: compute inline
            with self._lock:
                self._entries[key] = [value, time.time(), False]
            return value

        value, ts, _ = entry
        if time.time() - ts < self._ttl:
            return value                           # fresh

        # Stale: serve the stale value now, refresh in the background (once).
        with self._lock:
            if not self._entries[key][2]:
                self._entries[key][2] = True
                threading.Thread(target=self._refresh, args=(key, compute),
                                 daemon=True).start()
        return value

    def _refresh(self, key, compute: Callable):
        try:
            value = compute()
            with self._lock:
                self._entries[key] = [value, time.time(), False]
        except Exception:
            with self._lock:
                if key in self._entries:
                    self._entries[key][2] = False   # let a later request retry

    def warm(self, key, compute: Callable):
        """Pre-compute in a background thread (e.g. at startup) so the first
        request is already instant."""
        def run():
            try:
                value = compute()
                with self._lock:
                    self._entries[key] = [value, time.time(), False]
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def invalidate(self, key=None):
        with self._lock:
            if key is None:
                self._entries.clear()
            else:
                self._entries.pop(key, None)

    def age_seconds(self, key):
        with self._lock:
            entry = self._entries.get(key)
        return (time.time() - entry[1]) if entry else None
