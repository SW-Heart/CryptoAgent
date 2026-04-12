"""
exchange_trading_tools.py - 向后兼容层

所有功能已迁移至 tools/trading/ 包。
此文件保留以兼容旧 import 路径: from tools.exchange_trading_tools import xxx
"""
from tools.trading import *  # noqa: F401,F403
# 下划线前缀的函数不会被 * 导出，需显式导入
from tools.trading._client import _get_trading_client, _get_effective_user_id  # noqa: F401

