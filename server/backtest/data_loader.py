"""
回测K线数据加载器

支持两级缓存:
1. 数据库 kline_cache 表 (持久化)
2. Binance API (按需拉取并回填缓存)

Binance /api/v3/klines 限制: 每次最多 1000 根K线,
支持 startTime / endTime (毫秒时间戳).
"""
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Optional
import os

from app.database import get_db_connection

BINANCE_BASE_URL = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

# 各周期对应的毫秒数
INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
}


def _date_to_ms(date_str: str) -> int:
    """将日期字符串转为毫秒时间戳."""
    dt = pd.to_datetime(date_str)
    return int(dt.timestamp() * 1000)


def _fetch_from_binance(symbol: str, interval: str, start_ms: int, end_ms: int) -> list:
    """
    从 Binance API 批量拉取K线, 自动分页.
    每次最多 1000 根, 通过移动 startTime 分批获取.
    """
    pair = f"{symbol.upper().strip()}USDT"
    all_klines = []
    current_start = start_ms

    while current_start < end_ms:
        url = (
            f"{BINANCE_BASE_URL}/api/v3/klines"
            f"?symbol={pair}&interval={interval}"
            f"&startTime={current_start}&endTime={end_ms}"
            f"&limit=1000"
        )
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"[DataLoader] Binance API error: {resp.status_code}")
                break

            data = resp.json()
            if not data:
                break

            all_klines.extend(data)

            # 移动 startTime 到最后一根K线的 close_time + 1
            last_close_time = int(data[-1][6])
            if last_close_time >= end_ms:
                break
            current_start = last_close_time + 1

            # 限流: 每 3 次 API 调用 sleep 0.5s
            if len(all_klines) % 3000 == 0:
                time.sleep(0.5)

        except Exception as e:
            print(f"[DataLoader] Fetch error: {e}")
            if len(all_klines) == 0:
                raise ValueError(f"从币安拉取K线数据失败，请检查网络代理设置。异常信息: {str(e)}")
            break

    return all_klines


def _save_to_cache(symbol: str, interval: str, klines: list):
    """将K线数据批量写入数据库缓存 (ON CONFLICT 跳过已存在的)."""
    if not klines:
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 使用批量插入 + ON CONFLICT DO NOTHING
            from psycopg2.extras import execute_values
            values = []
            for k in klines:
                values.append((
                    symbol.upper(), interval,
                    int(k[0]),       # open_time
                    float(k[1]),     # open
                    float(k[2]),     # high
                    float(k[3]),     # low
                    float(k[4]),     # close
                    float(k[5]),     # volume
                    int(k[6]),       # close_time
                    float(k[7]),     # quote_volume
                    int(k[8]),       # trades
                ))

            execute_values(
                cur,
                """INSERT INTO kline_cache 
                   (symbol, interval, open_time, open, high, low, close, volume, close_time, quote_volume, trades)
                   VALUES %s
                   ON CONFLICT (symbol, interval, open_time) DO NOTHING""",
                values,
                page_size=500
            )
            conn.commit()
            print(f"[DataLoader] Cached {len(values)} klines for {symbol} {interval}")
    except Exception as e:
        print(f"[DataLoader] Cache write error: {e}")
        conn.rollback()
    finally:
        conn.close()


def _load_from_cache(symbol: str, interval: str, start_ms: int, end_ms: int) -> Optional[pd.DataFrame]:
    """从数据库缓存读取K线数据."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT open_time, open, high, low, close, volume, close_time, quote_volume, trades
                FROM kline_cache
                WHERE symbol = %s AND interval = %s
                  AND open_time >= %s AND open_time <= %s
                ORDER BY open_time ASC
            """, (symbol.upper(), interval, start_ms, end_ms))
            rows = cur.fetchall()

            if not rows:
                return None

            df = pd.DataFrame(rows, columns=[
                'time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades'
            ])
            # time 列保持为毫秒时间戳 (int), 后续按需转 datetime
            for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
    except Exception as e:
        print(f"[DataLoader] Cache read error: {e}")
        return None
    finally:
        conn.close()


def _check_cache_coverage(symbol: str, interval: str, start_ms: int, end_ms: int) -> dict:
    """检查缓存中已有多少K线, 以及是否覆盖完整区间."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MIN(open_time), MAX(open_time), COUNT(*)
                FROM kline_cache
                WHERE symbol = %s AND interval = %s
                  AND open_time >= %s AND open_time <= %s
            """, (symbol.upper(), interval, start_ms, end_ms))
            row = cur.fetchone()
            if row and row[2] > 0:
                # 估算理论K线数
                interval_ms = INTERVAL_MS.get(interval, 3_600_000)
                expected = (end_ms - start_ms) // interval_ms
                return {
                    "cached_count": row[2],
                    "expected_count": expected,
                    "min_time": row[0],
                    "max_time": row[1],
                    "coverage": round(row[2] / max(expected, 1) * 100, 1),
                }
            return {"cached_count": 0, "expected_count": 0, "coverage": 0}
    except Exception as e:
        print(f"[DataLoader] Coverage check error: {e}")
        return {"cached_count": 0, "expected_count": 0, "coverage": 0}
    finally:
        conn.close()


def load_historical_klines(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    warm_up_bars: int = 200,
) -> pd.DataFrame:
    """
    加载指定日期范围的历史K线数据.
    
    策略:
    1. 检查本地缓存覆盖率
    2. 缺失部分从 Binance API 拉取并回填缓存
    3. 返回完整 DataFrame
    
    Args:
        symbol: 交易对 (如 "BTC")
        interval: K线周期 (如 "4h", "1d")
        start_date: 开始日期 "YYYY-MM-DD"
        end_date:   结束日期 "YYYY-MM-DD"
        warm_up_bars: 预热K线数量 (用于计算 EMA200 等长周期指标)
        
    Returns:
        DataFrame with columns: time, open, high, low, close, volume, close_time, quote_volume, trades
        time 列为毫秒时间戳 (int64)
    """
    start_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date)

    # 向前扩展 warm_up_bars 根K线, 确保首根回测K线就有足够的指标数据
    interval_ms = INTERVAL_MS.get(interval, 3_600_000)
    warmup_ms = warm_up_bars * interval_ms
    fetch_start_ms = start_ms - warmup_ms

    # 1. 检查缓存
    coverage = _check_cache_coverage(symbol, interval, fetch_start_ms, end_ms)
    print(f"[DataLoader] Cache coverage for {symbol} {interval}: {coverage['coverage']}% ({coverage['cached_count']}/{coverage['expected_count']})")

    # 2. 如果缓存不完整 (无论缺多少), 从 API 拉取缺失部分
    # 注意: 不能用 < 95%，因为如果 200跟预热+6根回测 = 206根，缺这6根回测刚好是 3%，会导致 97% coverage 从而跳过拉取!
    if coverage["coverage"] < 100 or coverage["cached_count"] < coverage["expected_count"]:
        print(f"[DataLoader] Fetching from Binance API: {symbol} {interval} ...")
        raw_klines = _fetch_from_binance(symbol, interval, fetch_start_ms, end_ms)
        if raw_klines:
            _save_to_cache(symbol, interval, raw_klines)
            print(f"[DataLoader] Fetched & cached {len(raw_klines)} klines")

    # 3. 从缓存读取完整数据
    df = _load_from_cache(symbol, interval, fetch_start_ms, end_ms)
    if df is None or len(df) == 0:
        raise ValueError(f"无法加载 {symbol} {interval} 的K线数据 ({start_date} ~ {end_date})")

    print(f"[DataLoader] Loaded {len(df)} klines for {symbol} {interval} (含 {warm_up_bars} 根预热)")
    return df


def estimate_kline_count(interval: str, start_date: str, end_date: str) -> int:
    """估算回测区间内的K线数量 (不含预热)."""
    start_ms = _date_to_ms(start_date)
    end_ms = _date_to_ms(end_date)
    interval_ms = INTERVAL_MS.get(interval, 3_600_000)
    return max(1, (end_ms - start_ms) // interval_ms)
