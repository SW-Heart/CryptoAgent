"""
Strategy Templates API - 策略广场预置模板

提供预定义的策略模板列表，前端直接展示为"策略广场"。
用户点击"使用此策略"后，前端把模板参数传给现有的 POST /api/workspace/strategy-profiles 创建。

注意：这里是纯内存数据，不涉及数据库。
"""
from fastapi import APIRouter

router = APIRouter(tags=["strategy-templates"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 策略模板定义
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRATEGY_TEMPLATES = [
    {
        "id": "conservative",
        "name": "🛡 稳健防守",
        "description": "低杠杆保守交易，优先保护本金。只在强信号共振时入场，宽止损严止盈。适合风险厌恶型交易者。",
        "tags": ["低风险", "低频", "趋势跟踪"],
        "color": "#3B82F6",  # 蓝色
        "symbols": "BTC,ETH",
        "timeframes": "4h,1d",
        "risk_per_trade": 0.01,
        "trading_interval": 120,
        "prompt_template": "你是一个极度保守的交易者。只做最确定的机会，宁可错过也不做错。使用大周期趋势确认为主，只顺势操作。如果没有非常强烈的信号，保持 HOLD 不操作。",
        "config": {
            "enabled_modules": ["trend", "levels", "volume"],
            "trading_rules": {
                "signal_min_dimensions": 4,
                "allow_weak_signal": False,
                "max_position_pct": 10,
                "volatility_reduce": True,
                "sl_buffer_pct": 1.0,
                "breakeven_at_r": 0.5,
                "trail_at_r": 1.5,
                "default_leverage": 3,
                "entry_standards": "需要4个以上维度信号一致才可开仓。趋势必须在高级别周期(4h/1d)确认为 strong。价格必须处于关键支撑/阻力位 1% 以内。量能必须配合方向。不追单、不接飞刀。",
                "position_management": "盈利达到0.5R立即移止损到成本价保本。盈利1.5R时设置追踪止损。不做加仓操作。亏损中严格持有到止损线，不提前平仓。"
            }
        }
    },
    {
        "id": "balanced",
        "name": "⚖️ 均衡策略",
        "description": "平衡风险与收益的标准策略，适合大多数市场环境。中等杠杆，标准信号过滤。",
        "tags": ["中风险", "中频", "均衡"],
        "color": "#10B981",  # 翡翠色
        "symbols": "BTC,ETH,SOL",
        "timeframes": "1h,4h",
        "risk_per_trade": 0.02,
        "trading_interval": 60,
        "prompt_template": "Focus on trend following strategy with strict risk management. 均衡风险收益，在趋势明确时果断入场，在震荡市场中保持观望。",
        "config": {
            "enabled_modules": ["trend", "levels", "volume", "derivatives"],
            "trading_rules": {
                "signal_min_dimensions": 3,
                "allow_weak_signal": False,
                "max_position_pct": 20,
                "volatility_reduce": True,
                "sl_buffer_pct": 0.5,
                "breakeven_at_r": 1.0,
                "trail_at_r": 2.0,
                "default_leverage": 5,
                "entry_standards": "",
                "position_management": ""
            }
        }
    },
    {
        "id": "aggressive",
        "name": "🔥 激进突破",
        "description": "高杠杆主动交易，更宽松的入场标准，追求更高收益。适合经验丰富且能承担较大回撤的交易者。",
        "tags": ["高风险", "高频", "突破"],
        "color": "#F97316",  # 橙色
        "symbols": "BTC,ETH,SOL,DOGE",
        "timeframes": "15m,1h",
        "risk_per_trade": 0.03,
        "trading_interval": 30,
        "prompt_template": "你是一个积极进取的交易者。善于捕捉趋势的早期阶段和突破行情。在信号出现时果断入场，用止损控制风险。允许在中等信号时用小仓位试探。",
        "config": {
            "enabled_modules": ["trend", "levels", "volume", "pattern", "volatility", "derivatives"],
            "trading_rules": {
                "signal_min_dimensions": 2,
                "allow_weak_signal": True,
                "max_position_pct": 25,
                "volatility_reduce": False,
                "sl_buffer_pct": 0.3,
                "breakeven_at_r": 1.5,
                "trail_at_r": 3.0,
                "default_leverage": 10,
                "entry_standards": "接受2个维度信号共振即可入场。趋势方向一致 + 量能配合即为有效信号。弱信号时可用50%仓位试探性建仓。高波动环境不减仓，但要设更紧的止损。",
                "position_management": "盈利1.5R后才移止损到成本价，给持仓更多空间。盈利3R时开始追踪止损。允许在已有仓位的基础上加仓（但总仓位不超过上限）。"
            }
        }
    },
    {
        "id": "scalping",
        "name": "⚡ 超短线量化",
        "description": "高频短周期交易，专注5m/15m级别的动量突破。快进快出，追求高胜率的小利润累积。",
        "tags": ["高频", "动量", "短线"],
        "color": "#8B5CF6",  # 紫色
        "symbols": "BTC,ETH",
        "timeframes": "5m,15m",
        "risk_per_trade": 0.015,
        "trading_interval": 15,
        "prompt_template": "你是一个超短线动量交易者。专注于5分钟和15分钟级别的价格突破和动量变化。目标是快速捕捉短期波动的利润。严格控制每笔交易的持仓时间和风险。",
        "config": {
            "enabled_modules": ["trend", "volume", "volatility"],
            "trading_rules": {
                "signal_min_dimensions": 2,
                "allow_weak_signal": False,
                "max_position_pct": 15,
                "volatility_reduce": True,
                "sl_buffer_pct": 0.2,
                "breakeven_at_r": 0.8,
                "trail_at_r": 1.5,
                "default_leverage": 5,
                "entry_standards": "关注短周期(5m/15m)的量价突破信号。趋势方向判断以短周期为主。RSI 突破 50 线配合量能放大为有效入场信号。不做逆势单。",
                "position_management": "盈利0.8R快速移止损到成本价。盈利1.5R开始追踪止损。目标利润较小但胜率要高。如果持仓超过2小时未盈利考虑平仓。"
            }
        }
    },
]


@router.get("/strategy-templates")
async def get_strategy_templates():
    """返回策略广场预置模板列表"""
    return {"templates": STRATEGY_TEMPLATES}


@router.get("/strategy-templates/{template_id}")
async def get_strategy_template(template_id: str):
    """获取单个策略模板详情"""
    for tpl in STRATEGY_TEMPLATES:
        if tpl["id"] == template_id:
            return {"template": tpl}
    return {"error": "Template not found"}
