import os
import sys

# Ensure the 'back' directory is in the path
sys.path.append(os.path.join(os.getcwd(), "back"))

from back.agents.trading_agent import trading_agent

def test_agent_tools():
    print("=== Testing Agent Tool Discovery ===")
    
    # 1. 检查 Agent 实例中注册的工具预览
    if not hasattr(trading_agent, 'tools') or not trading_agent.tools:
        print("❌ Error: Agent has no tools registered!")
        return

    print(f"✅ Found {len(trading_agent.tools)} tools registered.")
    
    # 2. 检查工具元数据（是否被正确 Wrap）
    first_tool = trading_agent.tools[0]
    print(f"First Tool Inspection:")
    print(f" - Name: {first_tool.__name__}")
    print(f" - Docstring exists: {bool(first_tool.__doc__)}")
    if first_tool.__doc__:
        print(f" - Docstring preview: {first_tool.__doc__[:50]}...")
    
    # 3. 运行一个简单的任务，强制要求调用工具
    print("\n=== Running Test Task ===")
    task = "获取全球市场概览，并告诉我现在的 BTC 主导率是多少。"
    
    # 启用调试输出
    trading_agent.debug_mode = True
    
    try:
        # 使用 run() 方法进行本地测试 (通常是同步或异步)
        response = trading_agent.run(task)
        print("\n--- Agent Response ---")
        print(response.content)
        
        # 检查是否有工具调用记录
        if response.tools_called:
            print("\n✅ Tools were successfully called during the run!")
        else:
            print("\n❌ No tools were called. This is the issue.")
            
    except Exception as e:
        print(f"❌ Error during agent run: {e}")

if __name__ == "__main__":
    test_agent_tools()
