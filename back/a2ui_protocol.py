"""
A2UI Protocol - Agent to UI Protocol Implementation

A2UI 是 Google 开源的声明式 UI 协议，允许 AI Agent 生成结构化的 UI 数据，
由客户端安全地渲染为原生组件。

本模块实现：
1. A2UI 组件类型定义
2. Surface（界面）生成器
3. 交易卡片专用生成器
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import json


# ==========================================
# A2UI 组件类型枚举
# ==========================================

class ComponentType(str, Enum):
    """A2UI 标准组件类型"""
    TEXT = "text"
    BUTTON = "button"
    CARD = "card"
    IMAGE = "image"
    ROW = "row"
    COLUMN = "column"
    DIVIDER = "divider"
    ICON = "icon"
    BADGE = "badge"
    PROGRESS = "progress"


class ButtonVariant(str, Enum):
    """按钮样式变体"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    SUCCESS = "success"
    GHOST = "ghost"


class TextStyle(str, Enum):
    """文本样式"""
    HEADING = "heading"
    SUBHEADING = "subheading"
    BODY = "body"
    CAPTION = "caption"
    LABEL = "label"
    MONO = "mono"


# ==========================================
# A2UI 组件数据类
# ==========================================

@dataclass
class A2UIComponent:
    """A2UI 组件基类"""
    id: str
    type: str
    props: Dict[str, Any] = None
    children: List[str] = None
    
    def to_dict(self) -> Dict:
        result = {"id": self.id, "type": self.type}
        if self.props:
            result["props"] = self.props
        if self.children:
            result["children"] = self.children
        return result


@dataclass
class A2UISurface:
    """A2UI Surface 容器"""
    id: str
    components: List[A2UIComponent]
    
    def to_dict(self) -> Dict:
        return {
            "type": "surfaceUpdate",
            "surface": {
                "id": self.id,
                "components": [c.to_dict() for c in self.components]
            }
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ==========================================
# 交易卡片专用生成器
# ==========================================

def create_swap_card_surface(
    from_token: str,
    to_token: str,
    from_amount: float,
    to_amount: float,
    exchange_rate: float,
    price_usd: float,
    gas_estimate: str,
    price_impact: float = 0.0,
    transaction_data: Dict = None,
    surface_id: str = "swap_card_1"
) -> A2UISurface:
    """
    生成符合 A2UI 协议的 Swap 交易卡片。
    
    Args:
        from_token: 源代币符号 (e.g., "USDT")
        to_token: 目标代币符号 (e.g., "WBTC")
        from_amount: 源代币数量
        to_amount: 目标代币预计数量
        exchange_rate: 汇率
        price_usd: 目标代币 USD 价格
        gas_estimate: Gas 费用估算 (e.g., "$2.50")
        price_impact: 价格影响百分比
        transaction_data: 链上交易数据 (calldata, routerAddress 等)
        surface_id: Surface 唯一标识
    
    Returns:
        A2UISurface 对象
    """
    
    # 交易参数（用于 action 执行）
    action_params = {
        "chainId": 1,  # Ethereum Mainnet
        "fromToken": from_token,
        "toToken": to_token,
        "fromAmount": str(from_amount),
        "toAmount": str(to_amount),
        "exchangeRate": exchange_rate,
        "priceUsd": price_usd,
        "gasEstimate": gas_estimate,
        "priceImpact": price_impact,
    }
    
    # 合并链上交易数据
    if transaction_data:
        action_params.update(transaction_data)
    
    components = [
        # 卡片容器
        A2UIComponent(
            id="card_main",
            type=ComponentType.CARD.value,
            props={
                "title": "确认交易",
                "variant": "elevated",
                "padding": "lg"
            },
            children=["row_tokens", "divider_1", "row_rate", "row_gas", "row_impact", "divider_2", "row_actions"]
        ),
        
        # 代币对显示行
        A2UIComponent(
            id="row_tokens",
            type=ComponentType.ROW.value,
            props={"justify": "space-between", "align": "center"},
            children=["col_from", "icon_arrow", "col_to"]
        ),
        
        # 源代币列
        A2UIComponent(
            id="col_from",
            type=ComponentType.COLUMN.value,
            props={"align": "start", "gap": "xs"},
            children=["text_from_label", "text_from_amount"]
        ),
        A2UIComponent(
            id="text_from_label",
            type=ComponentType.TEXT.value,
            props={"value": "支付", "style": TextStyle.CAPTION.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_from_amount",
            type=ComponentType.TEXT.value,
            props={"value": f"{from_amount:,.2f} {from_token}", "style": TextStyle.HEADING.value}
        ),
        
        # 箭头图标
        A2UIComponent(
            id="icon_arrow",
            type=ComponentType.ICON.value,
            props={"name": "arrow-right", "size": "lg", "color": "primary"}
        ),
        
        # 目标代币列
        A2UIComponent(
            id="col_to",
            type=ComponentType.COLUMN.value,
            props={"align": "end", "gap": "xs"},
            children=["text_to_label", "text_to_amount"]
        ),
        A2UIComponent(
            id="text_to_label",
            type=ComponentType.TEXT.value,
            props={"value": "获得", "style": TextStyle.CAPTION.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_to_amount",
            type=ComponentType.TEXT.value,
            props={"value": f"{to_amount:.6f} {to_token}", "style": TextStyle.HEADING.value, "color": "success"}
        ),
        
        # 分隔线
        A2UIComponent(id="divider_1", type=ComponentType.DIVIDER.value),
        
        # 汇率行
        A2UIComponent(
            id="row_rate",
            type=ComponentType.ROW.value,
            props={"justify": "space-between"},
            children=["text_rate_label", "text_rate_value"]
        ),
        A2UIComponent(
            id="text_rate_label",
            type=ComponentType.TEXT.value,
            props={"value": "汇率", "style": TextStyle.BODY.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_rate_value",
            type=ComponentType.TEXT.value,
            props={"value": f"1 {to_token} = ${price_usd:,.2f}", "style": TextStyle.BODY.value}
        ),
        
        # Gas 费用行
        A2UIComponent(
            id="row_gas",
            type=ComponentType.ROW.value,
            props={"justify": "space-between"},
            children=["text_gas_label", "text_gas_value"]
        ),
        A2UIComponent(
            id="text_gas_label",
            type=ComponentType.TEXT.value,
            props={"value": "预计 Gas 费用", "style": TextStyle.BODY.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_gas_value",
            type=ComponentType.TEXT.value,
            props={"value": gas_estimate, "style": TextStyle.BODY.value}
        ),
        
        # 价格影响行
        A2UIComponent(
            id="row_impact",
            type=ComponentType.ROW.value,
            props={"justify": "space-between"},
            children=["text_impact_label", "text_impact_value"]
        ),
        A2UIComponent(
            id="text_impact_label",
            type=ComponentType.TEXT.value,
            props={"value": "价格影响", "style": TextStyle.BODY.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_impact_value",
            type=ComponentType.TEXT.value,
            props={
                "value": f"{price_impact:.2f}%",
                "style": TextStyle.BODY.value,
                "color": "danger" if price_impact > 1.0 else "success"
            }
        ),
        
        # 分隔线
        A2UIComponent(id="divider_2", type=ComponentType.DIVIDER.value),
        
        # 操作按钮行
        A2UIComponent(
            id="row_actions",
            type=ComponentType.ROW.value,
            props={"justify": "end", "gap": "md"},
            children=["btn_cancel", "btn_confirm"]
        ),
        A2UIComponent(
            id="btn_cancel",
            type=ComponentType.BUTTON.value,
            props={
                "label": "取消",
                "variant": ButtonVariant.SECONDARY.value,
                "action_id": "CANCEL_SWAP",
                "action_params": {}
            }
        ),
        A2UIComponent(
            id="btn_confirm",
            type=ComponentType.BUTTON.value,
            props={
                "label": "确认交易",
                "variant": ButtonVariant.PRIMARY.value,
                "action_id": "EXECUTE_ONCHAIN_SWAP",
                "action_params": action_params
            }
        ),
    ]
    
    return A2UISurface(id=surface_id, components=components)


def wrap_a2ui_in_markdown(surface: A2UISurface) -> str:
    """
    将 A2UI Surface 包装在 Markdown 代码块中，
    供 Agent 返回给客户端解析。
    
    Args:
        surface: A2UISurface 对象
    
    Returns:
        包含 a2ui 代码块的字符串
    """
    json_str = surface.to_json(indent=2)
    return f"```a2ui\n{json_str}\n```"


# ==========================================
# 验证工具
# ==========================================

def validate_surface(surface_dict: Dict) -> bool:
    """
    验证 A2UI Surface JSON 格式是否正确。
    
    Args:
        surface_dict: A2UI Surface 字典
    
    Returns:
        True if valid
    
    Raises:
        ValueError: 格式错误时
    """
    if "type" not in surface_dict or surface_dict["type"] != "surfaceUpdate":
        raise ValueError("Missing or invalid 'type' field")
    
    if "surface" not in surface_dict:
        raise ValueError("Missing 'surface' field")
    
    surface = surface_dict["surface"]
    if "id" not in surface:
        raise ValueError("Surface missing 'id'")
    
    if "components" not in surface or not isinstance(surface["components"], list):
        raise ValueError("Surface missing or invalid 'components'")
    
    # 验证每个组件
    component_ids = set()
    for comp in surface["components"]:
        if "id" not in comp or "type" not in comp:
            raise ValueError(f"Component missing 'id' or 'type': {comp}")
        if comp["id"] in component_ids:
            raise ValueError(f"Duplicate component id: {comp['id']}")
        component_ids.add(comp["id"])
        
        # 验证 children 引用
        if "children" in comp:
            for child_id in comp["children"]:
                if child_id not in [c["id"] for c in surface["components"]]:
                    raise ValueError(f"Invalid child reference: {child_id}")
    
    return True



# ==========================================
# 市场行情卡片专用生成器
# ==========================================

def create_market_ticker_surface(
    symbol: str,
    price: float,
    change_24h: float,
    volume_24h: float = 0,
    high_24h: float = 0,
    low_24h: float = 0,
    surface_id: str = "market_ticker_1"
) -> A2UISurface:
    """
    生成市场行情 A2UI 卡片。
    """
    
    is_up = change_24h >= 0
    change_color = "success" if is_up else "danger"
    change_sign = "+" if is_up else ""
    
    components = [
        # 卡片容器
        A2UIComponent(
            id="card_ticker",
            type=ComponentType.CARD.value,
            props={
                "title": f"{symbol} Market",
                "variant": "glass",
                "padding": "md"
            },
            children=["row_header", "divider_1", "row_stats", "divider_2", "btn_chart"]
        ),
        
        # 头部：价格 + 涨跌幅 Badge
        A2UIComponent(
            id="row_header",
            type=ComponentType.ROW.value,
            props={"justify": "space-between", "align": "center"},
            children=["text_price", "badge_change"]
        ),
        A2UIComponent(
            id="text_price",
            type=ComponentType.TEXT.value,
            props={
                "value": f"${price:,.2f}", 
                "style": TextStyle.HEADING.value
            }
        ),
        A2UIComponent(
            id="badge_change",
            type="badge", 
            props={
                "label": f"{change_sign}{change_24h:.2f}%", 
                "color": change_color
            }
        ),
        
        # 分隔线
        A2UIComponent(id="divider_1", type=ComponentType.DIVIDER.value),
        
        # 统计数据行
        A2UIComponent(
            id="row_stats",
            type=ComponentType.ROW.value,
            props={"justify": "space-between"},
            children=["col_vol", "col_range"]
        ),
        
        # 交易量列
        A2UIComponent(
            id="col_vol",
            type=ComponentType.COLUMN.value,
            props={"align": "start", "gap": "xs"},
            children=["label_vol", "text_vol"]
        ),
        A2UIComponent(
            id="label_vol",
            type=ComponentType.TEXT.value,
            props={"value": "24h Vol", "style": TextStyle.CAPTION.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_vol",
            type=ComponentType.TEXT.value,
            props={"value": f"${volume_24h:,.0f}", "style": TextStyle.BODY.value}
        ),

        # 高低点列
        A2UIComponent(
            id="col_range",
            type=ComponentType.COLUMN.value,
            props={"align": "end", "gap": "xs"},
            children=["label_range", "text_range"]
        ),
        A2UIComponent(
            id="label_range",
            type=ComponentType.TEXT.value,
            props={"value": "24h High/Low", "style": TextStyle.CAPTION.value, "color": "muted"}
        ),
        A2UIComponent(
            id="text_range",
            type=ComponentType.TEXT.value,
            props={"value": f"{low_24h:,.0f} - {high_24h:,.0f}", "style": TextStyle.BODY.value}
        ),
        
        # 分隔线
        A2UIComponent(id="divider_2", type=ComponentType.DIVIDER.value),
        
        # 按钮：查看图表
        A2UIComponent(
            id="btn_chart",
            type=ComponentType.BUTTON.value,
            props={
                "label": "View Chart on TradingView",
                "variant": ButtonVariant.SECONDARY.value,
                "action_id": "OPEN_CHART", 
                "action_params": {"symbol": symbol}
            }
        )
    ]
    
    return A2UISurface(id=surface_id, components=components)

# ==========================================
# 测试
# ==========================================

if __name__ == "__main__":
    # 测试生成交易卡片
    surface = create_swap_card_surface(
        from_token="USDT",
        to_token="WBTC",
        from_amount=1000.0,
        to_amount=0.012345,
        exchange_rate=0.000012345,
        price_usd=81000.0,
        gas_estimate="$3.50",
        price_impact=0.15,
        transaction_data={
            "routerAddress": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "calldata": "0x...",
            "value": "0"
        }
    )
    
    # 输出 JSON
    print("=== A2UI Surface JSON ===")
    print(surface.to_json())
    
    # 验证
    print("\n=== Validation ===")
    validate_surface(surface.to_dict())
    print("✅ Valid A2UI Surface")
    
    # 输出 Markdown 包装
    print("\n=== Markdown Wrapped ===")
    print(wrap_a2ui_in_markdown(surface))
