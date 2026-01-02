"""
Cache warmup service - Pre-populate dashboard cache on startup.
This eliminates the ~30s loading time for first-time visitors.
"""
import threading
import asyncio
import time


def warmup_dashboard_cache():
    """
    Warmup all dashboard caches in background thread.
    Called on service startup to ensure fast first load.
    """
    # Wait for FastAPI to fully initialize
    time.sleep(3)
    
    print("[Cache Warmup] Starting dashboard cache warmup...")
    start_time = time.time()
    
    try:
        # Import endpoints (avoid circular imports)
        from app.routers.dashboard import (
            get_dashboard_tokens,
            get_dashboard_fear_greed,
            get_dashboard_indicators,
            get_dashboard_news,
            get_dashboard_onchain_hot
        )
        
        # Create event loop for async calls
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Warmup in priority order (fastest first for quick partial availability)
        warmup_tasks = [
            ("tokens", get_dashboard_tokens),
            ("fear-greed", get_dashboard_fear_greed),
            ("indicators", get_dashboard_indicators),
            ("onchain-hot", lambda: get_dashboard_onchain_hot(6)),
            ("news", get_dashboard_news),  # Slowest (AI summarization)
        ]
        
        for name, func in warmup_tasks:
            try:
                task_start = time.time()
                loop.run_until_complete(func())
                elapsed = time.time() - task_start
                print(f"[Cache Warmup] ✓ {name} cached ({elapsed:.1f}s)")
            except Exception as e:
                print(f"[Cache Warmup] ✗ {name} failed: {e}")
        
        loop.close()
        
        total_time = time.time() - start_time
        print(f"[Cache Warmup] Complete! Total time: {total_time:.1f}s")
        
    except Exception as e:
        print(f"[Cache Warmup] Error: {e}")


def start_warmup_thread():
    """Start cache warmup in a background thread"""
    thread = threading.Thread(target=warmup_dashboard_cache, daemon=True)
    thread.start()
    return thread
