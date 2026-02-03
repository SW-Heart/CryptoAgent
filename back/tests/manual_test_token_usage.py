
import requests
import json
import time
import os

# 配置
API_URL = "http://localhost:8000/agents/trading-strategy-agent/runs"
USER_ID = "test_user_token_check"
SESSION_ID = f"token_test_{int(time.time())}"

def test_strategy_execution():
    print(f"🚀 开始测试 Token 消耗...")
    print(f"User ID: {USER_ID}")
    print(f"Session ID: {SESSION_ID}")
    
    # 模拟 Scheduler 发送的 Prompt
    # 注意：这里我们故意通过 Prompt 强调"分析 BTC"，看它是否会滥用视觉分析
    prompt = """构建合约交易策略，分析币种(BTC, ETH)：

1. 分析市场多维共振信号
2. 检查当前持仓状态
3. 根据分析结果执行策略
4. 记录策略分析结果
"""
    
    start_time = time.time()
    
    try:
        response = requests.post(
            API_URL,
            data={
                "message": prompt,
                "user_id": USER_ID,
                "session_id": SESSION_ID,
                "stream": "False"
            },
            timeout=120
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", "")
            
            print(f"\n✅ 请求成功 (耗时: {duration:.2f}s)")
            print(f"📝 响应长度: {len(content)} 字符")
            print("-" * 50)
            print("部分响应内容:")
            print(content[:500] + "...")
            print("-" * 50)
            
            # 检查是否包含视觉分析的迹象
            if "analyze_kline" in str(data) or "图表" in content or "形态" in content:
                print("\n⚠️  注意：响应中包含图表/形态分析相关内容，请检查后台日志确认是否调用了视觉工具。")
            else:
                print("\n✨ 响应中未发现明显的视觉分析内容，符合'按需调用'的预期。")
                
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")

if __name__ == "__main__":
    test_strategy_execution()
