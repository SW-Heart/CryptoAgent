"""
诊断脚本：追踪 trading agent 获取余额的完整链路
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import get_db_connection

# Step 1: 查看所有活跃的 trader_instances
print("=" * 60)
print("Step 1: 查看活跃的 trader_instances")
print("=" * 60)
conn = get_db_connection()
with conn.cursor() as cur:
    cur.execute("""
        SELECT ti.id, ti.user_id, ti.exchange_account_id, ti.llm_config_id, 
               ti.strategy_profile_id, ti.status, ti.is_enabled
        FROM trader_instances ti
        WHERE ti.status = 'RUNNING' AND ti.is_enabled = TRUE
    """)
    traders = cur.fetchall()
    for t in traders:
        print(f"  Trader #{t['id']}: user={t['user_id'][:12]}..., exchange_acc={t['exchange_account_id']}, status={t['status']}")

if not traders:
    print("  (无活跃的 trader instances)")
    conn.close()
    sys.exit(0)

user_id = traders[0]['user_id']
print(f"\n使用 user_id: {user_id}")

# Step 2: 检查 user_binance_keys 表
print("\n" + "=" * 60)
print("Step 2: 检查 user_binance_keys 表")
print("=" * 60)
with conn.cursor() as cur:
    cur.execute("SELECT user_id, is_testnet FROM user_binance_keys WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row:
        print(f"  找到 user_binance_keys: testnet={row['is_testnet']}")
    else:
        print(f"  ❌ user_binance_keys 中没有找到 user_id={user_id[:12]}...")

# Step 3: 检查 exchange_accounts 表
print("\n" + "=" * 60)
print("Step 3: 检查 exchange_accounts 表")
print("=" * 60)
with conn.cursor() as cur:
    cur.execute("""
        SELECT ea.id, ea.user_id, ea.exchange, ea.environment, ea.is_connected, ea.is_default,
               LEFT(ea.metadata_json::text, 100) as meta_preview
        FROM exchange_accounts ea
        WHERE ea.user_id = %s
    """, (user_id,))
    accounts = cur.fetchall()
    for ea in accounts:
        print(f"  ExchangeAccount #{ea['id']}: exchange={ea['exchange']}, env={ea['environment']}, connected={ea['is_connected']}, default={ea['is_default']}")
        print(f"    meta_preview: {ea['meta_preview']}")

if not accounts:
    print(f"  ❌ exchange_accounts 中没有找到 user_id={user_id[:12]}...")

# Step 4: 检查 ADMIN 用户的 keys
print("\n" + "=" * 60)
print("Step 4: 检查 STRATEGY_ADMIN_USER_ID 的配置")
print("=" * 60)
from tools.trading_tools import STRATEGY_ADMIN_USER_ID
print(f"  ADMIN_USER_ID: {STRATEGY_ADMIN_USER_ID}")

with conn.cursor() as cur:
    cur.execute("SELECT user_id, is_testnet FROM user_binance_keys WHERE user_id = %s", (STRATEGY_ADMIN_USER_ID,))
    row = cur.fetchone()
    if row:
        print(f"  ADMIN user_binance_keys: testnet={row['is_testnet']}")
    else:
        print(f"  ❌ ADMIN 在 user_binance_keys 中没有记录")

    cur.execute("SELECT id, environment, is_connected FROM exchange_accounts WHERE user_id = %s", (STRATEGY_ADMIN_USER_ID,))
    admin_accounts = cur.fetchall()
    if admin_accounts:
        for ea in admin_accounts:
            print(f"  ADMIN ExchangeAccount #{ea['id']}: env={ea['environment']}, connected={ea['is_connected']}")
    else:
        print(f"  ❌ ADMIN 在 exchange_accounts 中没有记录")

conn.close()

# Step 5: 模拟 _get_effective_user_id 的 fallback 行为
print("\n" + "=" * 60)
print("Step 5: 模拟 _get_effective_user_id 行为")
print("=" * 60)
from tools.trading_tools import get_current_user, set_current_user

# 不设置 context，看 fallback 到哪里
print(f"  get_current_user() (未设置): {get_current_user()}")

from tools.binance_trading_tools import _get_effective_user_id
effective = _get_effective_user_id(None)
print(f"  _get_effective_user_id(None) = {effective}")
print(f"  等于 ADMIN? {effective == STRATEGY_ADMIN_USER_ID}")

# 设置 context 再测试
set_current_user(user_id)
effective2 = _get_effective_user_id(None)
print(f"  设置 context 后, _get_effective_user_id(None) = {effective2}")
print(f"  等于 user_id? {effective2 == user_id}")

# Step 6: 直接测试 _get_trading_client
print("\n" + "=" * 60)
print("Step 6: 测试 _get_trading_client (Path-A + Path-B)")
print("=" * 60)
from tools.binance_trading_tools import _get_trading_client

# 用真实 user_id 测试
client, err = _get_trading_client(user_id, require_trading_enabled=False)
if client:
    print(f"  ✅ _get_trading_client({user_id[:12]}...) 成功!")
    # Step 7: 直接测试余额
    print("\n" + "=" * 60)
    print("Step 7: 直接调用 client.get_usdt_balance()")
    print("=" * 60)
    balance = client.get_usdt_balance()
    print(f"  结果: {balance}")
else:
    print(f"  ❌ _get_trading_client 失败: {err}")

# 用 ADMIN user_id 测试
print(f"\n  用 ADMIN ID 测试:")
client2, err2 = _get_trading_client(STRATEGY_ADMIN_USER_ID, require_trading_enabled=False)
if client2:
    print(f"  ✅ _get_trading_client(ADMIN) 成功!")
    balance2 = client2.get_usdt_balance()
    print(f"  ADMIN 余额: {balance2}")
else:
    print(f"  ❌ _get_trading_client(ADMIN) 失败: {err2}")

# Step 8: 测试 binance_get_positions_summary
print("\n" + "=" * 60)
print("Step 8: 测试 binance_get_positions_summary")
print("=" * 60)
from tools.binance_trading_tools import binance_get_positions_summary
set_current_user(user_id)
result = binance_get_positions_summary(user_id=user_id)
if "error" in result:
    print(f"  ❌ 有 error: {result['error']}")
    print(f"  完整返回: {result}")
else:
    print(f"  ✅ available_balance: {result.get('available_balance')}")
    print(f"  ✅ margin_balance: {result.get('margin_balance')}")
    print(f"  ✅ wallet_balance: {result.get('wallet_balance')}")

# Step 9: 测试完整的 _fetch_account
print("\n" + "=" * 60)
print("Step 9: 测试 _fetch_account (strategy_context)")
print("=" * 60)
from tools.strategy_context import _fetch_account
account = _fetch_account(user_id)
print(f"  结果: {account}")

# Step 10: 不传 user_id 测试（模拟 LLM 调用场景）
print("\n" + "=" * 60)
print("Step 10: 模拟 LLM 调用 build_strategy_context (不传 user_id)")
print("=" * 60)
set_current_user(user_id)
account_no_uid = _fetch_account(None)
print(f"  _fetch_account(None) 结果: {account_no_uid}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
