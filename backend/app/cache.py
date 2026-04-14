import logging
from typing import Optional, Dict, Any
from threading import Lock
from datetime import datetime

logger = logging.getLogger(__name__)

class DataCache:
    def __init__(self, ttl_seconds: Optional[int] = None):
        self._data: Optional[Dict[str, Any]] = None
        self._lock = Lock()
        self._loaded_at: Optional[datetime] = None
        self._ttl = ttl_seconds
        logger.info(f"DataCache initialized with TTL: {ttl_seconds}")

    def load(self, load_func, *args, **kwargs) -> None:
        with self._lock:
            try:
                logger.info("Loading data into cache...")
                self._data = load_func(*args, **kwargs)
                self._loaded_at = datetime.now()
                logger.info(
                    f"Successfully loaded {len(self._data.get('features', []))} "
                    f"features into cache"
                )
            except Exception as e:
                logger.error(f"Failed to load data into cache: {e}", exc_info=True)
                self._data = None
                self._loaded_at = None
                raise

    def get(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._data is None:
                logger.warning("Cache is empty")
                return None

            # Check if data has expired
            if self._ttl and self._loaded_at:
                elapsed = (datetime.now() - self._loaded_at).total_seconds()
                if elapsed > self._ttl:
                    logger.warning(f"Cache expired (TTL: {self._ttl}s, Elapsed: {elapsed}s)")
                    self._data = None
                    self._loaded_at = None
                    return None
            logger.debug("Returning cached data")
            return self._data

    def is_loaded(self) -> bool:
        with self._lock:
            return self._data is not None

    def clear(self) -> None:
        with self._lock:
            logger.info("Clearing cache")
            self._data = None
            self._loaded_at = None

    def size(self) -> int:

        with self._lock:
            if self._data is None:
                return 0
            return len(self._data.get("features", []))

# Global cache instance
data_cache = DataCache(ttl_seconds=None)  # No TTL - data doesn't change often

