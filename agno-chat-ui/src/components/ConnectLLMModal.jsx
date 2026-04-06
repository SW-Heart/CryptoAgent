import React, { useState } from 'react';
import Modal from './common/Modal';
import Input from './common/Input';
import Button from './common/Button';
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
    ShieldCheck
} from 'lucide-react';
import { postJson } from '../services/apiClient';

// --- Icon Picker for Providers ---
function ProviderIcon({ provider, size = "w-5 h-5", active = true }) {
    const baseClass = `${size} flex items-center justify-center transition-all`;

    const icons = {
        openai: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/openai.svg",
        deepseek: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/deepseek.svg",
        anthropic: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Claude.svg",
        google: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/google.svg"
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
    const [error, setError] = useState(null);

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
        { id: 'custom', name: '自定义 (Custom)', defaultModel: '', defaultUrl: '' }
    ];

    const handleProviderChange = (p) => {
        setProvider(p.id);
        setShowProviders(false);
        setFormData(prev => ({
            ...prev,
            model: p.defaultModel,
            base_url: p.defaultUrl
        }));
        setTestStatus('none');
    };

    const handleTestConnection = async () => {
        if (!formData.api_key.trim()) {
            setError("请先输入 API Key 进行测试");
            return;
        }

        setTestStatus('testing');
        setError(null);
        try {
            const res = await postJson(`/api/workspace/llm-configs/test`, formData);
            if (res.status === 'success') {
                setTestStatus('success');
            } else {
                setTestStatus('error');
                setError(res.message || "连接测试失败，请检查 API Key 或网络");
            }
        } catch (err) {
            setTestStatus('error');
            setError("连接异常: " + err.message);
        }
    };

    const handleSubmit = async () => {
        if (!formData.name.trim()) {
            setError("请为该配置设置一个别名 (如：我的主力 DeepSeek)");
            return;
        }
        if (testStatus !== 'success') {
            setError("请先点击【测试连接】并通过验证后再保存");
            return;
        }

        setLoading(true);
        try {
            await postJson(`/api/workspace/llm-configs?user_id=${userId}`, {
                ...formData,
                provider
            });
            onConnected?.();
            onClose();
        } catch (err) {
            setError("保存失败: " + err.message);
        } finally {
            setLoading(false);
        }
    };

    const modalFooter = (
        <div className="flex gap-3">
            <Button variant="outline" className="flex-1 py-4" onClick={onClose}>取消</Button>
            <Button
                className="flex-1 py-4 shadow-xl shadow-indigo-500/20"
                icon={loading ? Loader2 : CheckCircle2}
                disabled={loading || testStatus !== 'success'}
                onClick={handleSubmit}
            >
                {loading ? "集成中..." : "保存并启用"}
            </Button>
        </div>
    );

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="配置决策大脑 (LLM)" maxWidth="max-w-md" footer={modalFooter}>
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
                        onChange={v => { setFormData(f => ({ ...f, name: v })); setError(null); }}
                    />

                    <Input
                        label="模型型号 (Model ID)"
                        placeholder="例如：deepseek-chat"
                        value={formData.model}
                        onChange={v => { setFormData(f => ({ ...f, model: v })); setTestStatus('none'); }}
                    />

                    <div className="flex gap-2 items-end">
                        <div className="flex-1">
                            <Input
                                label="API Key"
                                type="password"
                                placeholder="输入该平台的 API 秘钥"
                                icon={Key}
                                value={formData.api_key}
                                onChange={v => { setFormData(f => ({ ...f, api_key: v })); setTestStatus('none'); }}
                            />
                        </div>
                        <Button
                            variant="secondary"
                            className={`h-[52px] px-6 rounded-2xl font-black text-[10px] uppercase tracking-widest ${testStatus === 'success' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : ''}`}
                            onClick={handleTestConnection}
                            disabled={testStatus === 'testing' || !formData.api_key}
                        >
                            {testStatus === 'testing' ? <Loader2 className="w-4 h-4 animate-spin" /> :
                                testStatus === 'success' ? <div className="flex items-center gap-1"><Check className="w-3 h-3" /> 已通</div> : "测试连接"}
                        </Button>
                    </div>

                    <Input
                        label="API 代理地址 (Base URL)"
                        placeholder="https://api.example.com/v1"
                        icon={Globe}
                        value={formData.base_url}
                        onChange={v => { setFormData(f => ({ ...f, base_url: v })); setTestStatus('none'); }}
                    />
                </div>

                {error && (
                    <div className="flex items-center gap-2 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-[11px] font-black animate-in shake-200">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        <span>{error}</span>
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
