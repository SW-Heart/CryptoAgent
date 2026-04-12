from typing import Optional
from exchanges.base import ExchangeClient
from exchanges.binance import BinanceFuturesClient
from exchanges.okx import OKXFuturesClient
from exchanges.bybit import BybitFuturesClient
from exchanges.bitget import BitgetFuturesClient
from exchanges.gate import GateFuturesClient

def create_exchange_client(
    provider: str,
    api_key: str,
    api_secret: str,
    passphrase: Optional[str] = None,
    environment: str = "live"
) -> ExchangeClient:
    """
    交易所客户端工厂方法。
    根据 provider 类型返回统一接口的 ExchangeClient 实例。

    Args:
        provider: "binance" 或 "okx"
        api_key: API Key
        api_secret: API Secret
        passphrase: OKX 必需的 API Passphrase
        environment: "live", "testnet", 或 "demo"

    Returns:
        实现 ExchangeClient 接口的客户端实例
    """
    provider = provider.lower()
    is_simulated = environment in ("testnet", "demo")

    if provider == "binance":
        return BinanceFuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=is_simulated
        )
    elif provider == "okx":
        return OKXFuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase or "",
            simulated=is_simulated
        )
    elif provider == "bybit":
        return BybitFuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            environment=environment
        )
    elif provider == "bitget":
        return BitgetFuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase or "",
            environment=environment
        )
    elif provider == "gate":
        return GateFuturesClient(
            api_key=api_key,
            api_secret=api_secret,
            environment=environment
        )
    else:
        raise ValueError(f"不支持的交易所提供商: {provider}")
