# Binance API Configuration
# This module provides a centralized configuration for Binance API base URL
# Supports both Binance (global) and Binance.US through environment variable

import os

# Read from environment variable, default to global Binance API
# Set BINANCE_API_BASE=https://api.binance.us in .env for US servers
BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

# Binance Futures API (only available on global, not on Binance.US)
BINANCE_FUTURES_API_BASE = os.getenv("BINANCE_FUTURES_API_BASE", "https://fapi.binance.com")
