import React, { useState, useEffect } from 'react';
import { 
    Key, 
    Cpu, 
    Target, 
    CheckCircle2, 
    ArrowRight, 
    ChevronRight,
    Zap,
    Play,
    Loader2
} from 'lucide-react';
import Button from '../components/common/Button';
import ConnectExchangeModal from '../components/modals/ConnectExchangeModal';
import ConnectLLMModal from '../components/modals/ConnectLLMModal';

export default function OnboardingWizard({ userId, onStepComplete, status }) {
    const [activeStep, setActiveStep] = useState(1);
    const [isExchangeModalOpen, setIsExchangeModalOpen] = useState(false);
    const [isLLMModalOpen, setIsLLMModalOpen] = useState(false);
    
    // We expect status to be { hasExchange: bool, hasLLM: bool, hasStrategy: bool }
    const { hasExchange, hasLLM, hasStrategy } = status || {};

    useEffect(() => {
        if (!hasExchange) setActiveStep(1);
        else if (!hasLLM) setActiveStep(2);
        else if (!hasStrategy) setActiveStep(3);
        else setActiveStep(4);
    }, [hasExchange, hasLLM, hasStrategy]);

    const steps = [
        {
            id: 1,
            title: "连接交易所 API",
            description: "授权模拟或实盘 API 密钥，让 AI 能够获取您的账户数据并执行订单。",
            icon: Key,
            completed: hasExchange,
            actionLabel: "立即连接",
            onAction: () => setIsExchangeModalOpen(true)
        },
        {
            id: 2,
            title: "配置决策大脑",
            description: "选择 AI 决策模型 (DeepSeek/GPT-4o) 用于实时行情分析和信号生成。",
            icon: Cpu,
            completed: hasLLM,
            actionLabel: "配置引擎",
            onAction: () => setIsLLMModalOpen(true)
        },
        {
            id: 3,
            title: "装载交易策略",
            description: "定义交易标的、扫描频率和单笔风控值，完成量化逻辑的最后拼图。",
            icon: Target,
            completed: hasStrategy,
            actionLabel: "构建逻辑",
            onAction: () => { window.location.hash = '/strategies'; }
        }
    ];

    if (hasExchange && hasLLM && hasStrategy) {
        return (
            <div className="flex flex-col items-center justify-center p-12 text-center animate-in zoom-in-95 duration-700">
                <div className="w-24 h-24 rounded-full bg-emerald-500/10 flex items-center justify-center mb-8 relative">
                    <div className="absolute inset-0 rounded-full border-4 border-emerald-500/20 animate-ping opacity-20" />
                    <Zap className="w-10 h-10 text-emerald-500 fill-current" />
                </div>
                <h2 className="text-3xl font-black text-white mb-2">配置全部就绪！</h2>
                <p className="text-slate-400 text-sm mb-8 max-w-sm">
                    所有核心模块已成功打通。现在，您可以进入控制台开启您的第一个 AI 交易实例。
                </p>
                <Button className="px-12 py-4 text-base font-black shadow-[0_20px_50px_rgba(99,102,241,0.3)]" onClick={() => onStepComplete('finish')}>
                    进入控制台
                </Button>
            </div>
        );
    }

    return (
        <div className="max-w-4xl w-full mx-auto p-12 flex flex-col items-center">
            {/* Logo/Identity */}
            <div className="w-16 h-16 rounded-2xl bg-indigo-600 flex items-center justify-center mb-10 shadow-2xl shadow-indigo-500/20">
                <Zap className="w-8 h-8 text-white fill-current" />
            </div>
            
            <div className="text-center mb-16">
                <h1 className="text-4xl font-black text-white mb-3 tracking-tight">激活 CryptoAgent</h1>
                <p className="text-slate-500 text-xs font-bold uppercase tracking-[4px]">三步开启 智能量化交易时代</p>
            </div>

            {/* Stepper Grid */}
            <div className="grid grid-cols-3 gap-6 w-full relative">
                {/* Connecting Lines */}
                <div className="absolute top-1/2 left-20 right-20 h-0.5 bg-white/5 -translate-y-1/2 z-0" />
                
                {steps.map((step, idx) => (
                    <div key={step.id} className="relative z-10 flex flex-col items-center group">
                        <div className={`
                            w-20 h-20 rounded-full flex items-center justify-center transition-all duration-500 border-4
                            ${step.completed 
                                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' 
                                : 'bg-indigo-600/5 border-white/10 text-white hover:bg-indigo-600/20 hover:border-indigo-500/30'}
                        `}>
                            {step.completed ? (
                                <CheckCircle2 className="w-8 h-8 animate-in zoom-in duration-500" />
                            ) : (
                                <step.icon className="w-8 h-8 opacity-80 group-hover:scale-110 group-hover:opacity-100 transition-all" />
                            )}
                        </div>

                        <div className="mt-8 text-center px-4 w-full">
                            <h3 className={`text-base font-black mb-2 transition-colors ${step.completed ? 'text-emerald-400' : 'text-white'}`}>
                                {step.title}
                            </h3>
                            <p className="text-[10px] text-slate-500 leading-relaxed font-medium mb-6 min-h-[32px]">
                                {step.description}
                            </p>
                            
                            {!step.completed ? (
                                <button 
                                    onClick={step.onAction}
                                    className="w-full bg-white text-black py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest hover:scale-[1.02] active:scale-95 transition-all shadow-xl shadow-white/5 active:shadow-none"
                                >
                                    {step.actionLabel}
                                </button>
                            ) : (
                                <div className="text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-1.5 py-2.5">
                                    配置就绪 <CheckCircle2 className="w-3.5 h-3.5" />
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <ConnectExchangeModal 
                userId={userId}
                isOpen={isExchangeModalOpen}
                onClose={() => setIsExchangeModalOpen(false)}
                onConnected={() => onStepComplete('exchange')}
            />

            <ConnectLLMModal 
                userId={userId}
                isOpen={isLLMModalOpen}
                onClose={() => setIsLLMModalOpen(false)}
                onConnected={() => onStepComplete('llm')}
            />
        </div>
    );
}
