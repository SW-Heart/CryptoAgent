
import requests

def fetch_prices_batch(symbols: list, base_url: str = "https://api.binance.com") -> dict:
    """
    Fetch prices for multiple symbols in one or minimal requests.
    Returns a dict {symbol: price}.
    """
    if not symbols:
        return {}
        
    prices = {}
    
    # Method 1: Get ALL prices (efficient if many symbols, heavy if few)
    # But usually < 2MB for all tickers. Faster than 10 HTTPS handshakes.
    try:
        resp = requests.get(f"{base_url}/api/v3/ticker/price", timeout=5)
        if resp.status_code == 200:
            for item in resp.json():
                s = item["symbol"]
                # We expect symbols like "BTCUSDT"
                prices[s] = float(item["price"])
    except Exception as e:
        print(f"[Strategy] Batch price fetch failed: {e}")
        
    return prices
