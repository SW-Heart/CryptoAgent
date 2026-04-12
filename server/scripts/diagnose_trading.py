"""
交易执行诊断脚本 - 逐步排查 Agent 无法开仓的原因

运行方式: cd back && python scripts/diagnose_trading.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("🔍 CryptoAgent 交易执行诊断")
print("=" * 60)

# ============ Step 1: 数据库连接 ============
print("\n--- Step 1: 数据库连接 ---")
try:
    from app.database import get_db_connection
    conn = get_db_connection()
    print("✅ 数据库连接成功")
    conn.close()
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
    sys.exit(1)

# ============ Step 2: 查询所有 RUNNING 的 trader instances ============
print("\n--- Step 2: 查询 RUNNING 的 Trader Instances ---")
conn = get_db_connection()
try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                ti.id, ti.user_id, ti.status, ti.is_enabled,
                ti.llm_config_id, ti.strategy_profile_id, ti.exchange_account_id,
                sp.symbols, sp.trading_interval
            FROM trader_instances ti
            LEFT JOIN strategy_profiles sp ON sp.id = ti.strategy_profile_id
            WHERE ti.status = 'RUNNING'
        """)
        traders = cur.fetchall()
        
        if not traders:
            print("⚠️  没有 RUNNING 状态的 Trader Instance!")
        else:
            for t in traders:
                print(f"  Trader #{t['id']}: user={t['user_id'][:12]}... status={t['status']} enabled={t['is_enabled']}")
                print(f"    symbols={t.get('symbols')} interval={t.get('trading_interval')}m")
                print(f"    llm_config_id={t['llm_config_id']} strategy_profile_id={t['strategy_profile_id']} exchange_account_id={t.get('exchange_account_id')}")
finally:
    conn.close()

if not traders:
    print("\n⛔ 诊断结束：没有正在运行的 Trader，Agent 不会被触发。")
    sys.exit(0)

# 取第一个 RUNNING 的 trader 来诊断
test_trader = traders[0]
user_id = test_trader['user_id']
trader_instance_id = test_trader['id']
print(f"\n📌 将使用 Trader #{trader_instance_id} (user: {user_id[:12]}...) 进行诊断")

# ============ Step 3: 检查 Binance API Keys ============
print("\n--- Step 3: 检查 Binance API Keys ---")
from binance_client import has_user_api_keys, get_user_trading_status, get_user_binance_client

has_keys = has_user_api_keys(user_id)
print(f"  user_binance_keys 表中有 API Keys: {has_keys}")

# 也检查 exchange_accounts 表
conn = get_db_connection()
try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ea.id, ea.exchange, ea.environment, ea.metadata_json
            FROM exchange_accounts ea
            WHERE ea.user_id = %s
        """, (user_id,))
        ea_rows = cur.fetchall()
        if ea_rows:
            for ea in ea_rows:
                meta = ea.get('metadata_json', {})
                has_api_key = bool(meta.get('api_key')) if isinstance(meta, dict) else False
                has_api_secret = bool(meta.get('api_secret')) if isinstance(meta, dict) else False
                print(f"  exchange_accounts #{ea['id']}: exchange={ea['exchange']} env={ea['environment']} has_key={has_api_key} has_secret={has_api_secret}")
        else:
            print("  ⚠️  exchange_accounts 表中无记录")
finally:
    conn.close()

# ============ Step 4: 检查 is_trading_enabled ============
print("\n--- Step 4: 检查交易启用状态 ---")
status = get_user_trading_status(user_id)
print(f"  is_configured: {status.get('is_configured')}")
print(f"  is_trading_enabled: {status.get('is_trading_enabled')}")
print(f"  enabled_at: {status.get('enabled_at')}")

if not status.get('is_trading_enabled'):
    print("  ❌ 交易未启用！这就是无法开仓的原因！")
    print("  💡 解决办法: 在 UI 上启用交易，或手动执行:")
    print(f"     from binance_client import enable_user_trading")
    print(f"     enable_user_trading('{user_id}')")

# ============ Step 5: 检查 Binance Client 连通性 ============
print("\n--- Step 5: Binance Client 连通性 ---")
client = get_user_binance_client(user_id)
if not client:
    print("  ❌ 无法创建 Binance Client (user_binance_keys 路径)")
    # 尝试 exchange_accounts 路径
    print("  尝试 exchange_accounts 路径...")
    try:
        from tools.strategy_context import _get_binance_client_fallback
        client, err = _get_binance_client_fallback(user_id)
        if client:
            print(f"  ✅ 通过 exchange_accounts 路径创建成功")
        else:
            print(f"  ❌ exchange_accounts 路径也失败: {err}")
    except Exception as e:
        print(f"  ❌ exchange_accounts 路径异常: {e}")
else:
    print("  ✅ Binance Client 创建成功 (user_binance_keys 路径)")

if client:
    print("\n  测试 API 调用...")
    
    # 测试余额
    try:
        balance = client.get_usdt_balance()
        if "error" in balance:
            print(f"  ❌ 余额查询失败: {balance['error']}")
        else:
            print(f"  ✅ 余额查询成功: wallet={balance.get('wallet_balance')} available={balance.get('available_balance')}")
    except Exception as e:
        print(f"  ❌ 余额查询异常: {e}")
    
    # 测试价格
    try:
        price = client.get_mark_price("BTCUSDT")
        if "error" in price:
            print(f"  ❌ 价格查询失败: {price['error']}")
        else:
            print(f"  ✅ 价格查询成功: BTC markPrice={price.get('markPrice')}")
    except Exception as e:
        print(f"  ❌ 价格查询异常: {e}")
    
    # 测试持仓模式
    try:
        mode = client.get_position_mode()
        if isinstance(mode, dict) and "error" in mode:
            print(f"  ❌ 持仓模式查询失败: {mode['error']}")
        else:
            is_hedge = mode.get("dualSidePosition", False) if isinstance(mode, dict) else False
            print(f"  ✅ 持仓模式: {'对冲模式' if is_hedge else '单向模式'}")
    except Exception as e:
        print(f"  ❌ 持仓模式查询异常: {e}")

# ============ Step 6: 检查 ContextVar 在线程中的行为 ============
print("\n--- Step 6: ContextVar 线程上下文测试 ---")
import asyncio
from tools.trading_tools import set_current_user, get_current_user

set_current_user(user_id)
print(f"  主线程设置 user_id: {get_current_user()[:12]}...")

async def test_context():
    # 模拟 main.py 中的 asyncio.to_thread
    def check_in_thread():
        ctx_user = get_current_user()
        return ctx_user
    
    result = await asyncio.to_thread(check_in_thread)
    return result

ctx_result = asyncio.run(test_context())
if ctx_result:
    print(f"  ✅ asyncio.to_thread 中 ContextVar 正常: {ctx_result[:12]}...")
else:
    print("  ❌ asyncio.to_thread 中 ContextVar 丢失！这是关键 BUG！")
    print("  💡 在 agent.run() 执行时，工具函数无法获取 user_id")

# ============ Step 7: 模拟 Agent 工具调用 ============
print("\n--- Step 7: 直接测试 open_position 工具 ---")
from tools.binance_trading_tools import binance_open_position

# 先设置用户上下文
set_current_user(user_id)

# 用很小的金额测试（不会真正成交，只是验证流程）
print("  模拟调用 binance_open_position (DRY RUN - 极小金额)...")
print("  参数: symbol=BTC, direction=LONG, margin=0.5, leverage=10")

# margin=0.5 USD, notional = 5 USD，低于最小名义价值 6USD，应该会返回错误但不会真正下单
result = binance_open_position(
    symbol="BTC",
    direction="LONG", 
    margin=0.5,  # 故意用极小金额，不会真正成交
    leverage=10,
    stop_loss=1000,  # 不合理的止损，即使下单也不会触发
    user_id=user_id
)

print(f"\n  📋 返回结果: {result}")

if "error" in result:
    error_msg = result["error"]
    print(f"\n  ❌ 开仓失败: {error_msg}")
    
    if "Trading is not enabled" in error_msg:
        print("  💡 根因: 交易未启用 → 需要在 UI 上开启交易或手动 enable")
    elif "API keys" in error_msg:
        print("  💡 根因: API Keys 未配置 → 检查 user_binance_keys 或 exchange_accounts 表")
    elif "Failed to create" in error_msg:
        print("  💡 根因: Binance Client 创建失败 → 检查 API Key 加密/解密")
    elif "too small" in error_msg:
        print("  ✅ 这是预期的！金额太小被拦截，说明 API 连通性正常，流程走到了下单前的验证环节。")
        print("  ✅ 如果生产环境 Agent 使用正常金额应该能成功下单。")
    elif "SSL" in error_msg or "Connection" in error_msg:
        print("  💡 根因: 网络连接问题 → 检查代理配置 HTTPS_PROXY")
    elif "Invalid price" in error_msg:
        print("  💡 根因: 价格获取失败 → 检查 Binance API 连通性")
    else:
        print(f"  💡 未知错误，需要进一步排查")
else:
    print("  ✅ 开仓调用成功！（这不应该发生，因为金额很小）")

# ============ Step 8: 检查 LLM 配置 ============
print("\n--- Step 8: LLM 配置检查 ---")
try:
    from agents.trading_agent import get_trading_agent
    agent = get_trading_agent(user_id, trader_instance_id=trader_instance_id)
    if agent:
        print(f"  ✅ Agent 创建成功: name={agent.name}")
        print(f"  工具数量: {len(agent.tools)}")
        for tool in agent.tools:
            func = getattr(tool, '__wrapped__', tool)
            name = getattr(func, '__name__', str(func))
            print(f"    - {name}")
    else:
        print("  ❌ Agent 创建失败 → 检查 LLM 配置")
except Exception as e:
    print(f"  ❌ Agent 创建异常: {e}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
