from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def content_hash(*parts: bytes | str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8") if isinstance(p, str) else p)
    return h.hexdigest()[:24]


def disk_cached(cache_dir: str, namespace: str, key: str, compute_fn: Callable[[], T], enabled: bool = True) -> T:
    """Generic pickle-backed disk cache, keyed on a content hash the caller
    computes (so a changed input or config naturally misses the cache
    instead of needing explicit invalidation logic). Deliberately simple:
    no TTL or eviction -- entries are cheap to recompute and the cache
    directory is disposable.
    """
    if not enabled:
        return compute_fn()

    cache_path = Path(cache_dir) / namespace / f"{key}.pkl"

    if cache_path.exists():
        try:
            with cache_path.open("rb") as f:
                return pickle.load(f)
        except Exception:
            pass  # corrupt or incompatible entry -- fall through and recompute

    result = compute_fn()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as f:
        pickle.dump(result, f)

    return result
