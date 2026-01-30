import sys
import os

# Add the project root and back directory to the python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'back'))

from back.agents.trading_agent import trading_agent

if __name__ == "__main__":
    print("Running Polymarket Integration Test...")
    user_query = "查看 Bitcoin 2026 的 Polymarket 预测情绪"
    trading_agent.print_response(user_query, stream=True)
