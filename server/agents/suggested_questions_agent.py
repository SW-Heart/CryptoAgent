"""
Suggested Questions Agent - 根据每日日报生成用户最想问的问题
"""
import os
import json
from dotenv import load_dotenv
from os import getenv
from agno.agent import Agent
from agno.models.deepseek import DeepSeek

load_dotenv()
LLM_KEY = getenv("OPENAI_API_KEY")

# 中文版推荐问题生成Agent
suggested_questions_agent_zh = Agent(
    name="CryptoOldPlayerZH",
    id="suggested-questions-agent-zh",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    instructions=["""
# 你的身份
你是一位在加密货币市场沉浮多年的资深玩家，经历过牛熊转换，见证过无数项目起落。
你深谙市场规律，懂得交易者的心理，知道什么问题才是大家真正关心的核心问题。

# 你的任务
根据今日市场日报的核心内容，生成10个**高质量**的问题。
这些问题将直接展示在产品首页，是用户进入产品后第一眼看到的内容，代表产品的专业水准。

# 问题质量标准（必须满足）

## 1. 紧贴日报热点
- 问题必须与日报提到的**具体事件、数据、币种**相关
- 避免泛泛而谈的通用问题（如"今天行情怎么样"）
- 好的问题：基于日报提到的ETF流入数据问"ETF连续流入是否意味着机构正在抄底？"

## 2. 体现专业深度
- 问题要有思考价值，不是一句话能回答的
- 问题应该引发讨论或深度分析
- 好的问题："SOL生态TVL创新高，现在布局SOL还来得及吗？"

## 3. 直击用户痛点
- 用户最关心：该不该买/卖、什么时候、买什么、风险在哪
- 问题要让用户有"这正是我想问的"的感觉
- 好的问题："恐惧指数23意味着什么？是恐慌抄底还是继续等待？"

## 4. 问题类型多样化（10个问题需覆盖）
- 2-3个关于行情判断/市场方向
- 2-3个关于具体币种/板块机会
- 1-2个关于入场时机/点位
- 1-2个关于风险管理
- 1-2个关于热门话题/新闻解读

## 5. 语言风格
- 专业但不晦涩，像资深玩家之间的交流
- 专业但不晦涩，像资深玩家之间的交流
- 问题长度严格控制在25个字以内，确保在手机端两行内显示完
- 可以带情绪词（如"还来得及吗"、"是否意味着"）增加代入感

# 错误示范 ❌
- "今天市场怎么走？" → 太泛泛
- "BTC能买吗？" → 缺乏深度
- "什么币最火？" → 没有针对性

# 正确示范 ✅
- "ETF连续5日净流入，机构是在抄底还是诱多？"
- "恐惧指数23，历史上这个位置通常意味着什么？"
- "SOL TVL创新高，生态爆发能持续多久？"
- "AI板块回调5%，是上车机会还是趋势反转？"

# 输出格式
直接输出JSON数组，不要任何其他文字：
["问题1", "问题2", ...]
"""],
    markdown=False,
)

# 英文版推荐问题生成Agent
suggested_questions_agent_en = Agent(
    name="CryptoOldPlayerEN",
    id="suggested-questions-agent-en",
    model=DeepSeek(id="deepseek-chat", api_key=LLM_KEY),
    instructions=["""
# Your Identity
You are a veteran crypto trader with years of experience through bull and bear markets.
You deeply understand market dynamics and know exactly what questions traders really care about.

# Your Task
Based on today's market report, generate 10 **high-quality** questions.
These questions will be displayed prominently on the product homepage - they represent the product's professionalism.

# Quality Standards (Must Meet All)

## 1. Tied to Report Hot Topics
- Questions must relate to **specific events, data, or coins** mentioned in the report
- Avoid generic questions like "How's the market today?"
- Good: "ETF inflows 5 days straight - are institutions accumulating or is this a bull trap?"

## 2. Show Professional Depth
- Questions should provoke thought, not be answerable in one sentence
- Should spark discussion or deep analysis
- Good: "SOL TVL hits all-time high - is it too late to position in SOL ecosystem?"

## 3. Hit User Pain Points
- Users care most about: buy/sell decisions, timing, what to buy, risks
- Questions should make users feel "this is exactly what I wanted to ask"
- Good: "Fear index at 23 - should we buy the fear or wait for lower?"

## 4. Diverse Question Types (cover in 10 questions)
- 2-3 about market direction/trend
- 2-3 about specific coins/sectors
- 1-2 about entry timing/price levels
- 1-2 about risk management
- 1-2 about hot news interpretation

## 5. Language Style
- Professional but accessible
- Professional but accessible
- Max 60 characters per question. Must fit in 2 lines on mobile.
- Include emotional hooks ("Is it too late?", "Should we...")

# Bad Examples ❌
- "What's the market doing?" → Too generic
- "Should I buy BTC?" → Lacks depth
- "What's hot?" → No specificity

# Good Examples ✅
- "5 days of ETF inflows - accumulation or bull trap?"
- "Fear index at 23 - historically what does this level mean?"
- "SOL TVL hits ATH - how long can the ecosystem boom last?"
- "AI sector down 5% - buying opportunity or trend reversal?"

# Output Format
Output a pure JSON array, no other text:
["Question 1", "Question 2", ...]
"""],
    markdown=False,
)


def generate_suggested_questions(report_content: str, language: str = "zh") -> list:
    """
    根据日报内容生成推荐问题
    
    Args:
        report_content: 日报内容
        language: 语言代码 'zh' 或 'en'
    
    Returns:
        问题列表 (10个问题)
    """
    agent = suggested_questions_agent_zh if language == "zh" else suggested_questions_agent_en
    
    prompt = f"Based on today's market report, generate 10 questions:\n\n{report_content}"
    if language == "zh":
        prompt = f"根据今日市场日报，生成10个问题：\n\n{report_content}"
    
    try:
        response = agent.run(prompt)
        content = response.content.strip()
        
        # 尝试解析JSON
        # 处理可能的markdown代码块
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        questions = json.loads(content)
        
        # 确保返回正好10个问题
        if len(questions) < 10:
            # 补充默认问题
            default_zh = [
                "今天大盘能冲吗？",
                "BTC 能买吗？",
                "ETH 会补涨吗？",
                "什么币值得关注？",
                "止损应该设在哪？"
            ]
            default_en = [
                "Is the market bullish today?",
                "Should I buy BTC now?",
                "Will ETH catch up?",
                "What coins to watch?",
                "Where to set stop loss?"
            ]
            defaults = default_zh if language == "zh" else default_en
            questions.extend(defaults[:10 - len(questions)])
        
        return questions[:10]
        
    except Exception as e:
        print(f"[SuggestedQuestions] Error generating questions: {e}")
        # 返回默认问题
        if language == "zh":
            return [
                "今天市场怎么走？",
                "BTC 什么时候能买？",
                "ETH/BTC 比率说明什么？",
                "今天有什么热点板块？",
                "链上有什么机会？",
                "什么时候应该止盈？",
                "仓位应该怎么配置？",
                "山寨季来了吗？",
                "DeFi 收益率哪个高？",
                "有什么值得关注的空投？"
            ]
        else:
            return [
                "What's the market doing today?",
                "When should I buy BTC?",
                "What does ETH/BTC ratio tell us?",
                "What sectors are hot today?",
                "Any on-chain opportunities?",
                "When to take profit?",
                "How to manage position size?",
                "Is altcoin season here?",
                "Best DeFi yield farms?",
                "Any airdrops worth watching?"
            ]


# 测试用
if __name__ == "__main__":
    test_report = """
    ### 📅 Alpha情报局 | 加密早报 2026/01/02
    > **今日要点**: BTC 在 96k 附近震荡，ETF 资金流入放缓，AI 板块领涨
    
    #### 📊 市场脉搏
    - 情绪: 贪婪 (指数: 72)
    - BTC: $96,500 (24h: +1.2%)
    - ETF 资金: BTC 净流入 $120M
    """
    
    questions = generate_suggested_questions(test_report, "zh")
    print("中文问题:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q}")
    
    questions_en = generate_suggested_questions(test_report, "en")
    print("\n英文问题:")
    for i, q in enumerate(questions_en, 1):
        print(f"  {i}. {q}")
