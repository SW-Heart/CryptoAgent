"""
Cache warmup service - Pre-populate dashboard cache on startup and keep it fresh.
This eliminates the ~30s loading time for first-time visitors.
"""
import threading

import time


def warmup_dashboard_cache(once_only=False):
    """
    Warmup all dashboard caches in background thread.
    Called on service startup to ensure fast first load.
    
    Args:
        once_only: If True, run only once. If False, run periodically.
    """
    # Wait for FastAPI to fully initialize
    time.sleep(3)
    
    print("[Cache Warmup] Starting dashboard cache warmup...")
    
    while True:
        start_time = time.time()
        
        try:
            # Import endpoints (avoid circular imports)
            from app.routers.dashboard import (
                get_dashboard_tokens,
                get_dashboard_fear_greed,
                get_dashboard_indicators,
                get_dashboard_news,
                get_dashboard_onchain_hot,
                get_dashboard_trending
            )
            
            # Warmup in priority order (fastest first for quick partial availability)
            warmup_tasks = [
                ("tokens", get_dashboard_tokens),
                ("fear-greed", get_dashboard_fear_greed),
                ("indicators", get_dashboard_indicators),
                ("trending", lambda: get_dashboard_trending(10)),
                ("onchain-hot", lambda: get_dashboard_onchain_hot(6)),
                ("news", get_dashboard_news),  # Slowest (AI summarization)
            ]
            
            for name, func in warmup_tasks:
                try:
                    task_start = time.time()
                    func()
                    elapsed = time.time() - task_start
                    print(f"[Cache Warmup] ✓ {name} cached ({elapsed:.1f}s)")
                except Exception as e:
                    print(f"[Cache Warmup] ✗ {name} failed: {e}")
            
            total_time = time.time() - start_time
            print(f"[Cache Warmup] Complete! Total time: {total_time:.1f}s")
            
        except Exception as e:
            print(f"[Cache Warmup] Error: {e}")
        
        # Exit if only running once
        if once_only:
            break
        
        # Wait 5 minutes before next warmup cycle
        # This ensures caches are always fresh before they expire
        print("[Cache Warmup] Next refresh in 5 minutes...")
        time.sleep(300)


def start_warmup_thread():
    """Start cache warmup in a background thread with periodic refresh"""
    thread = threading.Thread(target=warmup_dashboard_cache, args=(False,), daemon=True)
    thread.start()
    return thread

