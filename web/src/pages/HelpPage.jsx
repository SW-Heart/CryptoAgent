import React, { useState } from 'react';
import { 
  ChevronDown, 
  ChevronRight, 
  Info, 
  Settings, 
  Bot, 
  BellRing,
  ShieldAlert
} from 'lucide-react';

const HELP_DATA = {
  intro: {
    title: '平台介绍',
    icon: Info,
    items: [
      {
        q: 'OG AI 是什么？',
        a: 'OG AI 是一个基于大语言模型（LLM）的自主加密货币交易 Agent 平台。它能够自动化地收集市场宏观数据、技术指标、新闻情绪，并像专业交易员一样进行深度思考、制定策略并自动执行交易。'
      },
      {
        q: 'AI Agent 是如何分析市场的？',
        a: 'Agent 会综合分析多维度数据：\n- 宏观数据：全网爆仓、多空比、资金费率等。\n- 技术面：各级别趋势、关键支撑/阻力位（如 EMA、Vegas 通道）、K线形态、量能异常。\n- 消息面：实时抓取重大新闻并分析情绪。\n结合上述数据，Agent 每隔一段时间会输出详细的思考过程和交易决策。'
      },
      {
        q: '为什么有时候 Agent 会选择不操作 (HOLD)？',
        a: 'Agent 内置了严格的风控逻辑（顺大逆小）。如果市场信号冲突（例如大级别看跌，小级别看涨），或者信号维度不足，Agent 会优先保证本金安全，输出 HOLD（观望）指令。'
      }
    ]
  },
  exchange: {
    title: '交易所配置',
    icon: Settings,
    items: [
      {
        q: '如何绑定 Binance / OKX 交易所？',
        a: '在左侧菜单点击「系统设置」，进入「交易所授权」模块。点击「添加账号」，选择对应的交易所（Binance 或 OKX），填入你的 API Key 和 Secret Key 即可（OKX 还需要额外填入 Passphrase）。'
      },
      {
        q: '如何在 Binance (币安) 申请 API Key？',
        a: '1. 登录 Binance 官网或 App，点击个人头像，进入【API 管理 (API Management)】。\n2. 点击【创建 API (Create API)】，选择【系统生成 (System generated)】。\n3. 输入 API 标签名称，完成短信/邮箱等安全验证。\n4. 点击【编辑限制 (Edit restrictions)】，务必勾选【允许读取 (Enable Reading)】和【允许合约交易 (Enable Futures)】。如果要交易现货，勾选【允许现货及杠杆交易】。\n5. ⚠️ 切勿勾选【提现 (Withdraw)】权限。\n6. (强烈推荐) 在“IP访问限制”处，勾选【限制只对受信任的IP访问】，并填入你部署本系统的服务器公网 IP。\n7. 保存后，复制 API Key 和 Secret Key (注意：Secret Key 仅显示一次，请先复制再关闭页面)。'
      },
      {
        q: '如何在 OKX (欧易) 申请 API Key？',
        a: '1. 登录 OKX 官网，点击右上角个人中心图标，选择【API】。\n2. 点击【申请 V5 API (Create V5 API key)】。\n3. 填写 API 名称，以及非常重要的【Passphrase (API 密码)】（请牢记此密码，在系统绑定时必须输入）。\n4. 在“权限 (Permissions)”设置中，勾选【读取 (Read)】和【交易 (Trade)】。\n5. ⚠️ 绝不能勾选【提现 (Withdraw)】。\n6. (强烈推荐) 在“绑定 IP 地址”栏中，填入你服务器的公网 IP。\n7. 点击确认并完成双重验证，随后复制保存你的 API Key 和 Secret Key。'
      },
      {
        q: 'API Key 需要开启哪些权限？',
        a: '为了保证资金安全，系统在设计之初就屏蔽了提现功能。请务必只勾选【读取】和【交易】权限，绝对不要勾选提现权限。'
      }
    ]
  },
  strategy: {
    title: '策略与机器人',
    icon: Bot,
    items: [
      {
        q: '如何创建一个交易机器人 (Agent)？',
        a: '进入「策略库 (Strategies)」页面，点击「新建策略」来创建一个独立的交易代理。\n\n核心配置项说明：\n1. 交易标的 (Symbols)：指定该机器人监控和交易的币种，可多选（例如 `BTC, ETH, SOL`）。\n2. 监控周期 (Timeframes)：指定 Agent 观察市场所使用的 K 线级别（例如 `1h, 4h, 1d`）。建议同时配置大小级别，这能让 Agent 执行“顺大势、逆小势”的多维判断。\n3. 交易规则 (Trading Rules)：设置容错、风控等硬性限制。\n\n配置保存后，在卡片上点击【启动 (Start)】。后台调度器将接管该机器人，并每分钟进行一次心跳触发，由 Agent 自主决定是否需要读取盘面或执行交易。'
      },
      {
        q: '如何创建不同风格的机器人？',
        a: '由于系统采用 Agent 架构，你可以通过给不同的机器人设定不同的“监控周期”和“标的”来赋予它们不同的性格：\n\n- 稳健长线机器人：监控周期设置为 `4h, 1d`，交易标的选定为主流币（如 `BTC, ETH`），容错和止损空间（SL Buffer）可以适当设宽。\n- 灵活波段机器人：监控周期设置为 `15m, 1h, 4h`，监控热门山寨币（如 `SOL, DOGE, SUI`）。由于小级别噪音多，可以在交易规则中将“最小共振维度 (Signal Min Dimensions)”设高，让 Agent 在多数时候保持观望 (HOLD)，仅在高胜率形态下出击。\n\n你可以同时运行多个完全不同的策略机器人，它们互相隔离，互不干扰。'
      },
      {
        q: '单次交易风险（Risk Per Trade）是什么意思？',
        a: '这是整个系统最核心的底线风控参数。如果你将它设置为 2%，意味着无论 Agent 杠杆开多大，当交易触发止损时，你的最大本金亏损将被严格控制在总账户余额的 2% 左右。\n\n工作原理：Agent 在开仓前必须强制计算止损点。一旦止损点确定，系统会根据 (进场价 - 止损价) 的距离，自动反推你应该开多少数量的仓位，从而将风险死死锁在 2%。'
      },
      {
        q: '什么是「智能价格警报 (Price Alerts)」？',
        a: '智能价格警报是 Agent 非常拟人化的特色功能。\n\n当 Agent 结束一次深度分析时，如果它认为此时不适合开仓，但它发现某个价格位置非常关键（比如即将突破日线级别的 Vegas 通道，或者下方有个极强的支撑带），它会【自主调用工具】给自己设定一个价格警报。\n\n当市场价格真正触及该点位时，底层的监控器会立刻拉响警报，打破常规的轮询周期，立即唤醒该 Agent 进行一次“紧急盘面分析”并迅速做出交易决策。这一切都是完全自主的。'
      }
    ]
  },
  notification: {
    title: '通知与告警',
    icon: BellRing,
    items: [
      {
        q: '如何配置钉钉 (DingTalk) 机器人接收通知？',
        a: '钉钉机器人的配置步骤如下：\n\n1. 打开钉钉电脑端，进入你想要接收通知的群聊（如果没有请先建一个群）。\n2. 点击群聊右上角的【群设置】（齿轮图标），找到并点击【智能群助手】。\n3. 点击【添加机器人】，在弹出的列表中选择【自定义（通过 Webhook 接入自定义服务）】并点击【添加】。\n4. 为机器人起一个名字（例如“OG AI 交易告警”）。\n5. ⚠️ 安全设置非常关键：请勾选【加签 (Sign)】，此时下方会生成一串以 `SEC` 开头的密钥 (Secret)。请务必将这串 Secret 复制保存下来。\n6. 勾选同意协议后点击【完成】。此时页面会显示该机器人的 Webhook URL，请复制该 URL。\n7. 回到我们系统的左侧菜单「系统设置」->「通知配置」，选择 DingTalk，将刚刚复制的 Webhook URL 和 Secret 分别填入对应输入框，点击保存并发送测试消息即可。'
      },
      {
        q: '如何配置飞书 (Feishu) 机器人接收通知？',
        a: '飞书机器人的配置步骤如下：\n\n1. 打开飞书客户端，进入接收通知的群聊。\n2. 点击右上角的【设置】（或群头像），进入【群设置】，找到并点击【群机器人】。\n3. 点击【添加机器人】，在列表中选择最下方的【自定义机器人】，点击【添加】。\n4. 输入机器人名称和描述，点击【添加】。\n5. 页面会生成一个 Webhook 地址，请将其复制保存。\n6. ⚠️ 在下方的安全设置中，强烈建议勾选【签名校验】，并复制生成的密钥 (Secret)。\n7. 回到本系统的「系统设置」->「通知配置」，选择 Feishu，将 Webhook URL 和签名密钥 (Secret) 填入，保存并测试即可。'
      },
      {
        q: '如何配置 Telegram 机器人接收通知？',
        a: 'Telegram 机器人的配置比国内软件稍复杂，需要 Token 和 Chat ID 两部分：\n\n第一步：获取 Bot Token\n1. 在 Telegram 搜索栏搜索 `@BotFather`（带有官方认证标识），点击 Start 开始对话。\n2. 发送指令 `/newbot`，然后按提示输入你的机器人名称（显示名称）。\n3. 接着输入 Username（必须以 bot 结尾，如 `og_crypto_bot`）。\n4. 创建成功后，BotFather 会给你一串红色的 `HTTP API Token`（例如 `123456:ABC-DEF123...`），请务必复制保存好。\n\n第二步：获取 Chat ID\n1. 在 Telegram 中新建一个群组，并将你刚才创建的机器人拉入该群组。\n2. 在群组里随便发送一条消息（例如“测试”）。\n3. 在浏览器中访问：`https://api.telegram.org/bot<你的Token>/getUpdates`（把 <你的Token> 替换为第一步拿到的字符串）。\n4. 在浏览器返回的复杂文字中，找到 `"chat":{"id":-100123456789}` 这个字段。群组的 Chat ID 通常是以负号 `-` 开头的一长串数字，请将这串数字复制下来。\n\n第三步：系统绑定\n回到本系统的「通知配置」，选择 Telegram，分别填入 Bot Token 和 Chat ID。'
      },
      {
        q: '如何配置企业微信 (WeChat) 机器人接收通知？',
        a: '企业微信机器人的配置最为简单：\n\n1. 打开企业微信电脑端，进入一个内部群聊。\n2. 右键点击群聊列表中的该群，或打开右上角群设置，选择【添加群机器人】。\n3. 点击【新创建一个机器人】，为其命名并点击【添加】。\n4. 系统会立刻生成一个 Webhook 地址（形如 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxx`）。请复制该完整链接。\n5. 回到本系统的「系统设置」->「通知配置」，选择 WeChat，填入该 Webhook URL 保存即可。'
      },
      {
        q: '系统会发送哪些类型的通知？会频繁发消息打扰我吗？',
        a: '绝对不会。我们在设计通知系统时遵循了“最小化打扰”的原则。\n\n为了避免信息轰炸，Agent 常规的每分钟行情监控、以及它决定“不操作 (HOLD)”的分析决策，均【不会】发送任何通知。\n\n系统只有在发生以下关键事件时，才会主动向你的群组推送图文并茂的消息：\n1. 【开仓通知】：明确告知开仓方向、杠杆、均价以及止损点位。\n2. 【平仓通知】：明确告知平仓原因及最终的盈亏情况（PNL）。\n3. 【止损/止盈触发】：触及止损线时的风险提示。\n4. 【每日/每周总结报告】：长文复盘历史表现。'
      }
    ]
  },
  risk: {
    title: '安全与风险提示',
    icon: ShieldAlert,
    items: [
      {
        q: '平台会动用我的资金吗？',
        a: '本系统代码完全私有化部署在你的本地或你自己的服务器上。你的 API Key 仅保存在本地数据库中，不会上传到任何第三方中心化服务器。'
      },
      {
        q: '系统有止损保护吗？',
        a: '有，且非常严格。系统内置了“禁止不设止损开仓”的硬性规定。任何一笔交易，Agent 必须在下单前计算并设置好止损价。'
      }
    ]
  }
};

const AccordionItem = ({ q, a, isOpen, onClick }) => {
  return (
    <div className="border-b border-white/5 last:border-0">
      <button 
        className="w-full flex items-center justify-between py-4 text-left focus:outline-none group"
        onClick={onClick}
      >
        <span className="text-slate-200 font-medium group-hover:text-emerald-400 transition-colors">
          {q}
        </span>
        <ChevronDown 
          className={`w-5 h-5 text-slate-500 transition-transform duration-300 ${isOpen ? 'rotate-180 text-emerald-400' : ''}`}
        />
      </button>
      <div 
        className={`overflow-hidden transition-all duration-300 ease-in-out ${isOpen ? 'max-h-96 opacity-100 pb-4' : 'max-h-0 opacity-0'}`}
      >
        <div className="text-slate-400 text-sm leading-relaxed whitespace-pre-wrap pl-2 border-l-2 border-emerald-500/30">
          {a}
        </div>
      </div>
    </div>
  );
};

export default function HelpPage() {
  const [activeCategory, setActiveCategory] = useState('intro');
  const [openItems, setOpenItems] = useState({});

  const toggleItem = (index) => {
    setOpenItems(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const handleCategoryChange = (key) => {
    setActiveCategory(key);
    setOpenItems({}); // Reset expanded items on category change
  };

  const currentData = HELP_DATA[activeCategory];

  return (
    <div className="h-full flex flex-col md:flex-row gap-6 text-slate-100">
      
      {/* Left Sidebar - Categories */}
      <div className="w-full md:w-64 flex-shrink-0 flex flex-col">
        <div className="text-xl font-bold text-white mb-6 px-2 tracking-tight">帮助与反馈</div>
        <div className="space-y-1 flex-1 overflow-y-auto custom-scrollbar pr-2">
          {Object.entries(HELP_DATA).map(([key, data]) => {
            const Icon = data.icon;
            const isActive = activeCategory === key;
            return (
              <button
                key={key}
                onClick={() => handleCategoryChange(key)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-sm font-medium ${
                  isActive 
                    ? 'bg-gradient-to-r from-emerald-500/20 to-transparent text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]' 
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
                {data.title}
                {isActive && <ChevronRight className="w-4 h-4 ml-auto opacity-50" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Right Content Area */}
      <div className="flex-1 bg-[#0a0d0f]/50 backdrop-blur-md border border-white/5 rounded-2xl p-6 lg:p-10 overflow-y-auto custom-scrollbar relative flex flex-col">
        <div className="absolute top-0 left-0 w-full h-32 bg-gradient-to-b from-emerald-500/5 to-transparent pointer-events-none rounded-t-2xl"></div>
        
        <div className="relative z-10 max-w-4xl flex-1">
          <div className="flex items-center gap-3 mb-8">
            {currentData.icon && <currentData.icon className="w-8 h-8 text-emerald-400" />}
            <h2 className="text-2xl font-bold text-white tracking-tight">{currentData.title}</h2>
          </div>
          
          <div className="bg-black/30 rounded-2xl border border-white/5 p-2 sm:p-6 shadow-lg">
            {currentData.items.map((item, index) => (
              <AccordionItem 
                key={index}
                q={item.q}
                a={item.a}
                isOpen={!!openItems[index]}
                onClick={() => toggleItem(index)}
              />
            ))}
          </div>
        </div>

        {/* Footer feedback prompt */}
        <div className="mt-12 pt-8 border-t border-white/5 text-center relative z-10 max-w-4xl">
          <p className="text-slate-400 text-sm">
            没有找到你想问的问题？或者发现了系统的 Bug？
          </p>
          <button className="mt-4 px-6 py-2.5 bg-white/5 hover:bg-white/10 text-white rounded-xl text-sm font-medium transition-all duration-200 border border-white/10 hover:border-white/20 hover:shadow-lg shadow-black/20">
            提交意见反馈
          </button>
        </div>
      </div>
      
    </div>
  );
}
