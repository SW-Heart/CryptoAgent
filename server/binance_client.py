"""
binance_client.py - 向后兼容层

所有功能已迁移至 exchanges/binance.py。
此文件保留以兼容旧 import 路径: from binance_client import xxx
"""
from exchanges.binance import *  # noqa: F401,F403
