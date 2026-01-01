"""
Cache service for dashboard data with persistence.
"""
import threading
import json
import os
from datetime import datetime
from pathlib import Path

# Cache storage configuration
CACHE_FILE = Path("data/dashboard_cache.json")
_cache_lock = threading.Lock()
_memory_cache = {}

def _ensure_cache_dir():
    """Ensure cache directory exists"""
    if not CACHE_FILE.parent.exists():
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_cache_from_disk():
    """Load cache from disk into memory"""
    global _memory_cache
    if not CACHE_FILE.exists():
        return

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert timestamp strings back to datetime objects
            for key, value in data.items():
                if value.get("last_update"):
                    value["last_update"] = datetime.fromisoformat(value["last_update"])
            _memory_cache = data
    except Exception as e:
        print(f"[Cache] Failed to load cache from disk: {e}")
        _memory_cache = {}

def _save_cache_to_disk():
    """Save memory cache to disk"""
    _ensure_cache_dir()
    try:
        # Prepare data for serialization (convert datetime to isoformat)
        serializable_cache = {}
        for key, value in _memory_cache.items():
            serializable_cache[key] = {
                "data": value.get("data"),
                "last_update": value.get("last_update").isoformat() if value.get("last_update") else None
            }
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Cache] Failed to save cache to disk: {e}")

# Initialize cache on module load
_load_cache_from_disk()

def is_cache_valid(cache_key: str, ttl_seconds: int) -> bool:
    """Check if cache is still valid"""
    with _cache_lock:
        cache = _memory_cache.get(cache_key, {})
        if cache.get("data") is None or cache.get("last_update") is None:
            return False
        
        # Check TTL
        age = (datetime.now() - cache["last_update"]).total_seconds()
        return age < ttl_seconds

def set_cache(cache_key: str, data):
    """Set cache data and persist to disk"""
    with _cache_lock:
        _memory_cache[cache_key] = {
            "data": data,
            "last_update": datetime.now()
        }
        _save_cache_to_disk()

def get_cache(cache_key: str):
    """Get cache data"""
    with _cache_lock:
        return _memory_cache.get(cache_key, {}).get("data")
