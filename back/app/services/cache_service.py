"""
Cache service for dashboard data.
"""
import threading
from datetime import datetime

# Cache storage
_dashboard_cache = {
    "news": {"data": None, "last_update": None},
    "tokens": {"data": None, "last_update": None},
    "fear_greed": {"data": None, "last_update": None},
    "indicators": {"data": None, "last_update": None}
}
_cache_lock = threading.Lock()

def is_cache_valid(cache_key: str, ttl_seconds: int) -> bool:
    """Check if cache is still valid"""
    with _cache_lock:
        cache = _dashboard_cache.get(cache_key, {})
        if cache.get("data") is None or cache.get("last_update") is None:
            return False
        return (datetime.now() - cache["last_update"]).total_seconds() < ttl_seconds

def set_cache(cache_key: str, data):
    """Set cache data"""
    with _cache_lock:
        _dashboard_cache[cache_key] = {
            "data": data,
            "last_update": datetime.now()
        }

def get_cache(cache_key: str):
    """Get cache data"""
    with _cache_lock:
        return _dashboard_cache.get(cache_key, {}).get("data")
