"""
crypto_tools.py - 向后兼容层

所有功能已迁移至 tools/market/ 包。
此文件保留以兼容旧 import 路径: from tools.crypto_tools import xxx
"""
from tools.market import *  # noqa: F401,F403
