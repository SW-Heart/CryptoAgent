import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'back'))

from back.tools.binance_trading_tools import binance_open_position

def test_limit_order():
    print("Testing Limit Order Logic...")
    
    # Mock dependencies
    with patch('back.tools.binance_trading_tools.has_user_api_keys', return_value=True), \
         patch('back.tools.binance_trading_tools.get_user_trading_status', return_value={"is_trading_enabled": True}), \
         patch('back.tools.binance_trading_tools.get_user_binance_client') as mock_get_client:
         
        # Setup Mock Client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock API responses
        mock_client.set_leverage.return_value = {"leverage": 10}
        mock_client.get_mark_price.return_value = {"markPrice": "100.0"}
        mock_client.place_batch_orders.return_value = [{
            "orderId": "12345",
            "type": "LIMIT",
            "price": "95.0",
            "origQty": "1.0",
            "executedQty": "0.0",
            "status": "NEW"
        }]
        
        # Test Call: Limit Order
        result = binance_open_position(
            symbol="ETHUSDT",
            direction="LONG",
            margin=100,
            leverage=10,
            order_type="LIMIT",
            price=95.0,
            user_id="mock_user_id_12345"
        )
        
        # Verify
        if result.get("success") and result.get("order_type") == "LIMIT":
            print("✅ Limit Order Test Passed")
            print(f"Message: {result['message']}")
            
            # Verify call args
            calls = mock_client.place_batch_orders.call_args[0][0]
            print(f"Order Params Sent: {calls}")
            if calls[0]['type'] == 'LIMIT' and calls[0]['timeInForce'] == 'GTC':
                 print("✅ Order Type and TIF Correct")
            else:
                 print("❌ Order Type/TIF Incorrect")
        else:
            print(f"❌ Limit Order Test Failed: {result}")

if __name__ == "__main__":
    test_limit_order()
