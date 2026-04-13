import React, { useState } from 'react';
import Modal from '../common/Modal';
import Input from '../common/Input';
import Button from '../common/Button';
import {
    Cpu,
    ChevronDown,
    CheckCircle2,
    Loader2,
    AlertCircle,
    Globe,
    Key,
    Check,
    Zap,
    MessageSquare,
    ShieldCheck,
    Wifi
} from 'lucide-react';
import { postJson } from '../../services/apiClient';
import { showToast } from '../common/GlobalToast';

// --- Icon Picker for Providers ---
function ProviderIcon({ provider, size = "w-5 h-5", active = true }) {
    const baseClass = `${size} flex items-center justify-center transition-all`;

    const icons = {
        openai: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/openai.svg",
        deepseek: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/deepseek.svg",
        anthropic: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Claude.svg",
        google: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/google.svg",
        qwen: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/qwen.svg",
        minimax: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/MiniMax.svg",
        kimi: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/kimi.svg",
        glm: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/%E6%99%BA%E8%B0%B1.svg"
    };

    if (icons[provider]) {
        return (
            <div className={baseClass}>
                <img src={icons[provider]} alt={provider} className="w-full h-full object-contain" />
            </div>
        );
    }

    return <div className={`${baseClass} text-slate-400`}><Globe className="w-4 h-4" /></div>;
}

export default function ConnectLLMModal({ isOpen, onClose, onConnected, userId }) {
    const [provider, setProvider] = useState('deepseek');
    const [showProviders, setShowProviders] = useState(false);
    const [testStatus, setTestStatus] = useState('none'); // none, testing, success, error
    const [loading, setLoading] = useState(false);

    const [formData, setFormData] = useState({
        name: '',
        model: 'deepseek-chat',
        api_key: '',
        base_url: 'https://api.deepseek.com/v1'
    });

    const providers = [
        { id: 'deepseek', name: 'DeepSeek', defaultModel: 'deepseek-chat', defaultUrl: 'https://api.deepseek.com/v1' },
        { id: 'openai', name: 'OpenAI', defaultModel: 'gpt-5.4', defaultUrl: 'https://api.openai.com/v1' },
        { id: 'google', name: 'Gemini (Google)', defaultModel: 'gemini-3.1-pro', defaultUrl: 'https://generativelanguage.googleapis.com' },
        { id: 'anthropic', name: 'Anthropic', defaultModel: 'claude-4.6-sonnet', defaultUrl: 'https://api.anthropic.com/v1' },
        { id: 'qwen', name: '通义千问 (Qwen)', defaultModel: 'qwen-plus', defaultUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
        { id: 'glm', name: '智谱 (GLM)', defaultModel: 'glm-4', defaultUrl: 'https://open.bigmodel.cn/api/paas/v4' },
        { id: 'minimax', name: 'MiniMax', defaultModel: 'abab6.5s-chat', defaultUrl: 'https://api.minimax.chat/v1' },
        { id: 'kimi', name: '月之暗面 (Kimi)', defaultModel: 'moonshot-v1-8k', defaultUrl: 'https://api.moonshot.cn/v1' },
        { id: 'custom', name: '自定义 (Custom)', defaultModel: '', defaultUrl: '' }
    ];

    // 关闭弹窗时重置所有状态
    const handleClose = () => {
        setProvider('deepseek');
        setShowProviders(false);
        setTestStatus('none');
        setLoading(false);
        setFormData({
            name: '',
            model: 'deepseek-chat',
            api_key: '',
            base_url: 'https://api.deepseek.com/v1'
        });
        onClose();
    };

    // 任何表单变动都重置测试状态
    const resetTest = () => { setTestStatus('none'); };

    const handleProviderChange = (p) => {
        setProvider(p.id);
        setShowProviders(false);
        setFormData(prev => ({
            ...prev,
            model: p.defaultModel,
            base_url: p.defaultUrl
        }));
        resetTest();
    };

    const handleTestConnection = async () => {
        if (!formData.api_key.trim()) {
            showToast("请输入 API Key", "error");
            return;
        }
        if (!formData.model.trim()) {
            showToast("请输入模型型号", "error");
            return;
        }

        setTestStatus('testing');
        try {
            const res = await postJson(`/api/workspace/llm-configs/test`, { ...formData, provider });
            if (res.status === 'success') {
                setTestStatus('success');
                showToast("连接验证通过，模型响应正常", "success");
            } else {
                setTestStatus('error');
                showToast(res.message || "连接测试失败，请检查 API Key", "error", 6000);
            }
        } catch (err) {
            setTestStatus('error');
            showToast("连接异常: " + err.message, "error", 6000);
        }
    };

    const handleSubmit = async () => {
        if (!formData.name.trim()) {
            showToast("请为该配置设置一个别名", "error");
            return;
        }

        setLoading(true);
        try {
            await postJson(`/api/workspace/llm-configs?user_id=${userId}`, {
                ...formData,
                provider
            });
            showToast("LLM 配置已保存并启用", "success");
            onConnected?.();
            handleClose();
        } catch (err) {
            showToast("保存失败: " + err.message, "error");
        } finally {
            setLoading(false);
        }
    };

    // 主按钮：两阶段 — 测试连接 → 保存并启用
    const handlePrimaryAction = () => {
        if (testStatus === 'success') {
            handleSubmit();
        } else {
            handleTestConnection();
        }
    };

    const isFormReady = formData.api_key.trim() && formData.model.trim();
    const isBusy = loading || testStatus === 'testing';

    const modalFooter = (
        <div className="flex gap-3">
            <Button variant="outline" className="flex-1 py-4" onClick={handleClose}>取消</Button>
            <Button
                className={`flex-1 py-4 shadow-xl transition-all duration-300 ${
                    testStatus === 'success'
                        ? 'shadow-emerald-500/20'
                        : 'shadow-indigo-500/20'
                }`}
                icon={testStatus === 'success' ? CheckCircle2 : Wifi}
                loading={isBusy}
                disabled={isBusy || !isFormReady}
                onClick={handlePrimaryAction}
            >
                {loading ? "保存中..." :
                 testStatus === 'testing' ? "验证中..." :
                 testStatus === 'success' ? "保存并启用" :
                 "测试连接"}
            </Button>
        </div>
    );

    return (
        <Modal isOpen={isOpen} onClose={handleClose} title="配置决策大脑 (LLM)" maxWidth="max-w-md" footer={modalFooter}>
            <div className="space-y-6">

                {/* Provider Selection */}
                <div className="relative">
                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 ml-1">AI 渠道/提供商</label>
                    <button
                        onClick={() => setShowProviders(!showProviders)}
                        className="w-full flex items-center justify-between bg-[#0B0E11] border border-white/5 rounded-2xl px-5 py-4 hover:border-white/10 transition-all text-sm group"
                    >
                        <div className="flex items-center gap-3">
                            <ProviderIcon provider={provider} />
                            <span className="font-bold text-white uppercase">{providers.find(p => p.id === provider).name}</span>
                        </div>
                        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${showProviders ? 'rotate-180' : ''}`} />
                    </button>

                    {showProviders && (
                        <div className="absolute top-full left-0 right-0 mt-2 p-2 bg-[#1a1f2e] border border-white/10 rounded-2xl shadow-2xl z-50 animate-in fade-in slide-in-from-top-2">
                            {providers.map(p => (
                                <button
                                    key={p.id}
                                    onClick={() => handleProviderChange(p)}
                                    className={`w-full flex items-center justify-between px-4 py-3 rounded-xl hover:bg-white/5 transition-all text-sm ${provider === p.id ? 'text-indigo-400 bg-indigo-500/5' : 'text-slate-400'}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <ProviderIcon provider={p.id} size="w-4 h-4" active={provider === p.id} />
                                        <span className="font-bold">{p.name}</span>
                                    </div>
                                    {provider === p.id && <Check className="w-4 h-4" />}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Form Fields */}
                <div className="space-y-4">
                    <Input
                        label="配置别名"
                        placeholder="例如：主决策模型"
                        value={formData.name}
                        onChange={v => setFormData(f => ({ ...f, name: v }))}
                    />

                    <Input
                        label="模型型号 (Model ID)"
                        placeholder="例如：deepseek-chat"
                        value={formData.model}
                        onChange={v => { setFormData(f => ({ ...f, model: v })); resetTest(); }}
                    />

                    <Input
                        label="API Key"
                        type="password"
                        placeholder="输入该平台的 API 秘钥"
                        icon={Key}
                        value={formData.api_key}
                        onChange={v => { setFormData(f => ({ ...f, api_key: v })); resetTest(); }}
                    />

                    <Input
                        label="API 代理地址 (Base URL)"
                        placeholder="https://api.example.com/v1"
                        icon={Globe}
                        value={formData.base_url}
                        onChange={v => { setFormData(f => ({ ...f, base_url: v })); resetTest(); }}
                    />
                </div>

                {/* 测试成功 — Modal 内提示引导保存 */}
                {testStatus === 'success' && (
                    <div className="flex items-center gap-2 p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-black animate-in fade-in slide-in-from-bottom-2">
                        <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                        <span>验证通过！点击下方按钮保存配置。</span>
                    </div>
                )}

                <div className="p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 space-y-2">
                    <div className="flex items-center gap-2 text-indigo-400">
                        <ShieldCheck className="w-4 h-4" />
                        <span className="text-[10px] font-black uppercase tracking-widest">集成说明</span>
                    </div>
                    <p className="text-[10px] text-slate-400 leading-relaxed font-medium">我们将通过加密通道存储您的 API Key，仅在代理生成决策时调用。我们建议为该 API Key 设置额度上限以保障安全。</p>
                </div>
            </div>
        </Modal>
    );
}

