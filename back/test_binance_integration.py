#!/usr/bin/env python3
"""
Binance Futures API Integration Test

This script tests the binance_trading_tools module on the testnet.
It performs:
1. Get account balance
2. Open a small test position
3. Check positions
4. Close the position

Usage:
    python test_binance_integration.py <user_id>
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from binance_client import (
    has_user_api_keys,
    get_user_trading_status,
    get_user_binance_client
)
from binance_trading_tools import (
    binance_open_position,
    binance_close_position,
    binance_get_positions_summary,
    binance_get_current_price
)

def print_separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_account_status(user_id: str) -> bool:
    """Test 1: Check account status and balance"""
    print_separator("TEST 1: Account Status")
    
    # Check if API keys are configured
    if not has_user_api_keys(user_id):
        print("❌ No API keys configured for this user")
        return False
    print("✅ API keys found")
    
    # Check trading status
    status = get_user_trading_status(user_id)
    print(f"   Trading enabled: {status.get('is_trading_enabled', False)}")
    print(f"   Is testnet: {status.get('is_testnet', True)}")
    
    if not status.get('is_trading_enabled'):
        print("❌ Trading is not enabled")
        return False
    print("✅ Trading enabled")
    
    # Get balance
    summary = binance_get_positions_summary(user_id)
    if "error" in summary:
        print(f"❌ Error getting balance: {summary['error']}")
        return False
    
    print(f"✅ Account balance retrieved:")
    print(f"   Available: ${summary.get('available_balance', 0):.2f}")
    print(f"   Equity: ${summary.get('equity', 0):.2f}")
    print(f"   Unrealized PnL: ${summary.get('unrealized_pnl', 0):.2f}")
    print(f"   Open positions: {summary.get('position_count', 0)}")
    
    # Check balance breakdown
    if summary.get('balance_breakdown'):
        print(f"   Balance breakdown:")
        for asset in summary['balance_breakdown']:
            print(f"      {asset['asset']}: ${asset['available_balance']:.2f}")
    
    return True


def test_get_price(symbol: str = "BTC", user_id: str = None) -> float:
    """Test 2: Get current price"""
    print_separator("TEST 2: Get Price")
    
    price = binance_get_current_price(symbol, user_id)
    if price <= 0:
        print(f"❌ Failed to get price for {symbol}")
        return 0
    
    print(f"✅ {symbol} current price: ${price:,.2f}")
    return price


def test_open_position(user_id: str, symbol: str = "BTC", margin: float = 20) -> dict:
    """Test 3: Open a small test position (min notional $100, so need $20 x 10x = $200)"""
    print_separator("TEST 3: Open Position")
    
    print(f"Opening LONG position on {symbol} with ${margin} margin...")
    
    result = binance_open_position(
        user_id=user_id,
        symbol=symbol,
        direction="LONG",
        margin=margin,
        leverage=10,
        stop_loss=None,  # No SL for test
        take_profit=None  # No TP for test
    )
    
    if "error" in result:
        print(f"❌ Failed to open position: {result['error']}")
        return result
    
    print(f"✅ Position opened successfully!")
    print(f"   Order ID: {result.get('order_id')}")
    print(f"   Symbol: {result.get('symbol')}")
    print(f"   Direction: {result.get('direction')}")
    print(f"   Entry price: ${result.get('entry_price', 0):,.2f}")
    print(f"   Quantity: {result.get('quantity')}")
    print(f"   Fee: ${result.get('fee', 0):.4f}")
    
    return result


def test_check_positions(user_id: str) -> list:
    """Test 4: Check current positions"""
    print_separator("TEST 4: Check Positions")
    
    summary = binance_get_positions_summary(user_id)
    
    if "error" in summary:
        print(f"❌ Error: {summary['error']}")
        return []
    
    positions = summary.get('open_positions', [])
    
    if not positions:
        print("ℹ️ No open positions")
        return []
    
    print(f"✅ Found {len(positions)} open position(s):")
    
    for pos in positions:
        print(f"\n   {pos.get('symbol')} {pos.get('direction')}")
        print(f"   Entry: ${pos.get('entry_price', 0):,.2f}")
        print(f"   Current: ${pos.get('current_price', 0):,.2f}")
        print(f"   Quantity: {pos.get('quantity')}")
        print(f"   Unrealized PnL: ${pos.get('unrealized_pnl', 0):.2f}")
        print(f"   ROI: {pos.get('roi_percent', 0):.2f}%")
    
    return positions


def test_close_position(user_id: str, symbol: str = "BTCUSDT") -> dict:
    """Test 5: Close position"""
    print_separator("TEST 5: Close Position")
    
    print(f"Closing position on {symbol}...")
    
    result = binance_close_position(
        user_id=user_id,
        symbol=symbol,
        close_percent=100,
        reason="integration_test"
    )
    
    if "error" in result:
        print(f"❌ Failed to close: {result['error']}")
        return result
    
    print(f"✅ Position closed successfully!")
    print(f"   Symbol: {result.get('symbol')}")
    print(f"   Close price: ${result.get('close_price', 0):,.2f}")
    print(f"   Realized PnL: ${result.get('realized_pnl', 0):.2f}")
    print(f"   Fee: ${result.get('fee', 0):.4f}")
    
    return result


def run_full_test(user_id: str):
    """Run complete integration test"""
    print("\n" + "="*60)
    print("  🧪 BINANCE FUTURES API INTEGRATION TEST")
    print("="*60)
    print(f"\nUser ID: {user_id[:8]}...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Account status
    if not test_account_status(user_id):
        print("\n❌ Test 1 failed. Stopping tests.")
        return False
    
    # Test 2: Get price
    price = test_get_price("BTC", user_id)
    if price <= 0:
        print("\n❌ Test 2 failed. Stopping tests.")
        return False
    
    # Test 3: Open position (use $20 margin x 10 leverage = $200 notional, above $100 minimum)
    open_result = test_open_position(user_id, "BTC", margin=20)
    if "error" in open_result:
        print("\n❌ Test 3 failed. Stopping tests.")
        return False
    
    # Wait a moment for order to process
    print("\n⏳ Waiting 2 seconds for order to process...")
    time.sleep(2)
    
    # Test 4: Check positions
    positions = test_check_positions(user_id)
    
    # Test 5: Close position
    close_result = test_close_position(user_id, "BTCUSDT")
    if "error" in close_result:
        print(f"\n⚠️ Test 5 failed: {close_result['error']}")
        print("Position may need to be closed manually on Binance")
        return False
    
    # Final summary
    print_separator("TEST SUMMARY")
    print("✅ All tests passed!")
    print(f"   Opened and closed LONG BTC position")
    print(f"   Net P&L from test: ${close_result.get('realized_pnl', 0):.4f}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_binance_integration.py <user_id>")
        print("\nExample:")
        print("  python test_binance_integration.py ee20fa53-5ac2-44bc-9237-41b308e291d8")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    success = run_full_test(user_id)
    
    sys.exit(0 if success else 1)
