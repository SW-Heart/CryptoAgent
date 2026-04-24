import asyncio
from app.database import init_db
from tools.alert_tools import set_price_alert, list_price_alerts, cancel_price_alert, get_active_alerts, mark_alert_triggered
from tools.strategy_context import build_strategy_context

# 模拟用户
TEST_USER_ID = "test-user-123"

# 1. 初始化数据库表
init_db()
print("✅ DB tables initialized")

# 2. 测试设置警报
print("\n--- Testing set_price_alert ---")
res = set_price_alert("BTC", 100000, "ABOVE", "Test Alert", user_id=TEST_USER_ID)
print(res)
alert_id = res.get("alert_id")

# 测试防重复
res_dup = set_price_alert("BTC", 100000, "ABOVE", "Test Alert", user_id=TEST_USER_ID)
print("Duplicate test:", res_dup)

# 3. 测试列表
print("\n--- Testing list_price_alerts ---")
alerts = list_price_alerts(user_id=TEST_USER_ID)
print(f"Count: {alerts['count']}")
for a in alerts['list']:
    print(f"  - [{a['id']}] {a['symbol']} {a['direction_label']} {a['target_price']}")

# 4. 测试上下文注入
print("\n--- Testing strategy_context injection ---")
ctx = build_strategy_context("BTC", "1d", "trend", user_id=TEST_USER_ID)
import json
ctx_data = json.loads(ctx)
if "alerts" in ctx_data:
    print(f"Alerts injected: {ctx_data['alerts']['count']} alerts found in context")
else:
    print("❌ Alerts missing from context")

# 5. 测试供调度器用的内部函数
print("\n--- Testing scheduler functions ---")
active = get_active_alerts()
print(f"Active alerts across all users: {len(active)}")
if active:
    print(f"Triggering alert ID {active[0]['id']}")
    mark_alert_triggered(active[0]['id'])
    
    active_after = get_active_alerts()
    print(f"Active alerts after trigger: {len(active_after)}")

# 6. 测试取消警报
print("\n--- Testing cancel_price_alert ---")
# 先再建一个
set_price_alert("ETH", 3000, "BELOW", "Cancel Test", user_id=TEST_USER_ID)
cancel_res = cancel_price_alert(symbol="ETH", user_id=TEST_USER_ID)
print(cancel_res)
