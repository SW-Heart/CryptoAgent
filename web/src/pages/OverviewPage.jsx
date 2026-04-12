import React from 'react';
import { Activity, Bot, ChevronRight, Cpu, ShieldCheck, Wallet } from 'lucide-react';

function StatusBadge({ label, value, tone = 'slate' }) {
    const tones = {
        green: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
        amber: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
        red: 'bg-red-500/10 text-red-300 border-red-500/20',
        slate: 'bg-slate-500/10 text-slate-300 border-slate-500/20',
    };

    return (
        <div className={`rounded-2xl border px-4 py-3 ${tones[tone]}`}>
            <div className="text-xs uppercase tracking-[0.2em] opacity-70">{label}</div>
            <div className="mt-2 text-sm font-semibold">{value}</div>
        </div>
    );
}

function QuickAction({ title, description, onClick }) {
    return (
        <button
            onClick={onClick}
            className="group rounded-2xl border border-white/8 bg-white/[0.03] p-5 text-left transition-all hover:border-indigo-500/30 hover:bg-indigo-500/[0.06]"
        >
            <div className="flex items-start justify-between gap-4">
                <div>
                    <div className="text-sm font-semibold text-white">{title}</div>
                    <div className="mt-2 text-sm leading-6 text-slate-400">{description}</div>
                </div>
                <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-500 transition-transform group-hover:translate-x-1 group-hover:text-indigo-300" />
            </div>
        </button>
    );
}

export default function OverviewPage({
    llmConfig,
    exchangeStatus,
    onNavigate,
    onOpenSettings,
}) {
    const llmTone = llmConfig?.has_api_key ? 'green' : 'amber';
    const exchangeTone = exchangeStatus?.is_configured
        ? (exchangeStatus?.is_trading_enabled ? 'green' : 'amber')
        : 'red';

    const exchangeLabel = !exchangeStatus?.is_configured
        ? '未连接'
        : exchangeStatus?.is_testnet
            ? 'Binance 测试网'
            : 'Binance 主网';

    const runtimeLabel = exchangeStatus?.is_trading_enabled ? '运行中' : '已停止';

    return (
        <div className="flex h-full min-h-0 flex-col overflow-y-auto pb-6 pr-1">
            <section className="rounded-3xl border border-white/8 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.24),_transparent_40%),linear-gradient(135deg,_rgba(17,24,39,0.95),_rgba(7,10,15,0.98))] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.35)]">
                <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div className="max-w-2xl">
                        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-indigo-200">
                            <Activity className="h-3.5 w-3.5" />
                            策略交易驾驶舱
                        </div>
                        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white">
                            聚焦策略配置、运行控制与执行复盘。
                        </h1>
                        <p className="mt-4 max-w-xl text-sm leading-6 text-slate-300">
                            当前版本以策略交易为核心，总览页用于快速确认系统状态，并进入策略与执行页面。
                        </p>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-3">
                        <StatusBadge
                            label="LLM 配置"
                            value={llmConfig?.has_api_key ? llmConfig.llm_model : '缺少 API Key'}
                            tone={llmTone}
                        />
                        <StatusBadge
                            label="交易所账户"
                            value={exchangeLabel}
                            tone={exchangeTone}
                        />
                        <StatusBadge
                            label="运行状态"
                            value={runtimeLabel}
                            tone={exchangeStatus?.is_trading_enabled ? 'green' : 'slate'}
                        />
                    </div>
                </div>
            </section>

            <section className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                <div className="rounded-3xl border border-white/8 bg-[#111827]/80 p-6">
                    <div className="flex items-center gap-3 text-white">
                        <ShieldCheck className="h-5 w-5 text-emerald-300" />
                        <h2 className="text-lg font-semibold">关键入口</h2>
                    </div>
                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                        <QuickAction
                            title="打开执行控制台"
                            description="查看当前交易实例，执行启动、暂停、停止等运行操作。"
                            onClick={() => onNavigate('execution')}
                        />
                        <QuickAction
                            title="管理策略对象"
                            description="创建与编辑策略档案，并维护交易实例绑定。"
                            onClick={() => onNavigate('strategies')}
                        />
                        <QuickAction
                            title="配置交易所"
                            description="管理 Binance 主网 / 测试网连接及凭证状态。"
                            onClick={() => onOpenSettings('exchange')}
                        />
                        <QuickAction
                            title="配置 LLM 模型"
                            description="管理模型服务商、模型名称与 API Key。"
                            onClick={() => onOpenSettings('llm')}
                        />
                    </div>
                </div>

                <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-6">
                    <h2 className="text-lg font-semibold text-white">架构目标</h2>
                    <div className="mt-5 space-y-3">
                        <div className="flex items-start gap-3 rounded-2xl border border-white/6 bg-black/20 p-4">
                            <Bot className="mt-0.5 h-4 w-4 text-indigo-300" />
                            <div>
                                <div className="text-sm font-medium text-white">策略档案</div>
                                <div className="mt-1 text-sm text-slate-400">将交易标的、周期、风控与提示词固化为可复用策略对象。</div>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 rounded-2xl border border-white/6 bg-black/20 p-4">
                            <Wallet className="mt-0.5 h-4 w-4 text-cyan-300" />
                            <div>
                                <div className="text-sm font-medium text-white">交易实例</div>
                                <div className="mt-1 text-sm text-slate-400">把策略、交易所账户与模型配置绑定为独立运行单元。</div>
                            </div>
                        </div>
                        <div className="flex items-start gap-3 rounded-2xl border border-white/6 bg-black/20 p-4">
                            <Cpu className="mt-0.5 h-4 w-4 text-amber-300" />
                            <div>
                                <div className="text-sm font-medium text-white">执行控制台</div>
                                <div className="mt-1 text-sm text-slate-400">统一查看运行状态、审计事件、持仓订单与执行异常。</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
