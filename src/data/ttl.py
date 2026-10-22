"""Bounded TTL memoization for legacy raw source calls."""

from collections import OrderedDict
from functools import wraps
from threading import RLock
from time import monotonic


def ttl_lru_cache(maxsize: int, ttl_seconds: int, *, clock=monotonic):
    def decorate(function):
        entries = OrderedDict()
        lock = RLock()

        @wraps(function)
        def wrapped(*args, **kwargs):
            key = args + tuple(sorted(kwargs.items())) if kwargs else args
            now = clock()
            with lock:
                item = entries.get(key)
                if item is not None:
                    expires, value = item
                    if expires > now:
                        entries.move_to_end(key)
                        return value
                    del entries[key]
            value = function(*args, **kwargs)
            with lock:
                entries[key] = (clock() + ttl_seconds, value)
                entries.move_to_end(key)
                while len(entries) > maxsize:
                    entries.popitem(last=False)
            return value

        def cache_clear():
            with lock:
                entries.clear()

        wrapped.cache_clear = cache_clear
        return wrapped
    return decorate
