import React, { useState } from 'react';
import Modal from './common/Modal';
import Input from './common/Input';
import Button from './common/Button';
import { 
    ShieldCheck, 
    HelpCircle, 
    CheckCircle2, 
    Loader2, 
    ChevronDown, 
    Copy, 
    Globe, 
    AlertCircle, 
    Key,
    Lock,
    Layout,
    Zap
} from 'lucide-react';
import { postJson } from '../services/apiClient';
import { supabase } from '../lib/supabaseClient';

// --- Improved Logo Component with local fallback ---
function ExchangeLogo({ src, name, size = "w-5 h-5", disabled = false }) {
    const [error, setError] = useState(false);
    if (error || !src) {
        return (
            <div className={`${size} rounded-full bg-indigo-500/20 flex items-center justify-center text-[10px] font-black text-indigo-400 border border-indigo-500/20 ${disabled ? 'grayscale opacity-30 text-slate-500' : ''}`}>
                {name?.charAt(0).toUpperCase()}
            </div>
        );
    }
    return (
        <img 
            src={src} 
            alt={name} 
            className={`${size} rounded-full object-cover ${disabled ? 'grayscale opacity-30' : ''} transition-all`} 
            onError={() => setError(true)}
        />
    );
}

export default function ConnectExchangeModal({ isOpen, onClose, onConnected, userId }) {
    const [platform, setPlatform] = useState('binance');
    const [showPlatforms, setShowPlatforms] = useState(false);
    
    // Default environment to live for real traders, but demo is common for starters
    const [environment, setEnvironment] = useState('live'); 

    const [formData, setFormData] = useState({
        name: '',
        api_key: '',
        api_secret: '',
        passphrase: '', 
    });
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const SERVER_IP = "47.243.12.88"; 

    const platforms = [
        { id: 'okx', name: 'OKX', icon: 'https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Okx.svg', comingSoon: false },
        { id: 'binance', name: 'Binance', icon: 'https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/binance.svg', comingSoon: false }
    ];

    const handleSubmit = async () => {
        // Validate inputs first
        if (!formData.name.trim()) {
            setError("请输入账户别名，便于管理");
            return;
        }
        if (!formData.api_key.trim() || !formData.api_secret.trim()) {
            setError("API Key 和 Secret Key 是连接交易所的必填信息");
            return;
        }

        setLoading(true);
        setError(null);

        try {
            // Self-healing: Try to get actual ID if prop is missing
            let actualUserId = userId;
            if (!actualUserId) {
                const { data: { user } } = await supabase.auth.getUser();
                actualUserId = user?.id;
            }

            if (!actualUserId) {
                setError("用户会话已过期，请重新登录 (userId missing)");
                setLoading(false);
                return;
            }

            await postJson(`/api/workspace/exchange-accounts?user_id=${actualUserId}`, {
                ...formData,
                exchange: platform,
                environment: environment
            });
            onConnected?.();
            onClose();
        } catch (err) {
            setError(err.message || "连接失败，请检查 API 配置或权限设置");
        } finally {
            setLoading(false);
        }
    };

    const handleCopyIp = () => {
        navigator.clipboard.writeText(SERVER_IP);
    };

    const selectedPlatform = platforms.find(p => p.id === platform);

    const modalFooter = (
        <div className="flex gap-3">
            <Button variant="outline" className="flex-1 py-4" onClick={onClose}>取消</Button>
            <Button className="flex-1 py-4 shadow-xl shadow-indigo-500/20" icon={loading ? Loader2 : CheckCircle2} disabled={loading} onClick={handleSubmit}>
                {loading ? "连接中..." : "确认连接"}
            </Button>
        </div>
    );

    // Dynamic placeholder based on environment
    const placeholderText = environment === 'live' ? "例如：我的币安实盘主账户" : "例如：我的币安模拟账户";

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="连接交易所账户" maxWidth="max-w-md" footer={modalFooter}>
            <div className="space-y-6">
                
                {/* 1. Platform Selector */}
                <div className="relative">
                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2 ml-1">交易所平台</label>
                    <button 
                        onClick={() => setShowPlatforms(!showPlatforms)}
                        className="w-full flex items-center justify-between bg-[#0B0E11] border border-white/5 rounded-2xl px-5 py-4 hover:border-white/10 transition-all text-sm group"
                    >
                        <div className="flex items-center gap-3">
                            <ExchangeLogo key={selectedPlatform.id} src={selectedPlatform.icon} name={selectedPlatform.name} />
                            <span className="font-bold text-white uppercase">{selectedPlatform.name}</span>
                        </div>
                        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${showPlatforms ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {showPlatforms && (
                        <div className="absolute top-full left-0 right-0 mt-2 p-2 bg-[#1a1f2e] border border-white/10 rounded-2xl shadow-2xl z-50 animate-in fade-in slide-in-from-top-2">
                            {platforms.map(p => (
                                <button 
                                    key={p.id}
                                    disabled={p.comingSoon}
                                    onClick={() => { 
                                        if (!p.comingSoon) {
                                            setPlatform(p.id); 
                                            setShowPlatforms(false); 
                                            setError(null); 
                                        }
                                    }}
                                    className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all text-sm ${
                                        p.comingSoon ? 'opacity-30 cursor-not-allowed grayscale' : 'hover:bg-white/5 text-slate-400'
                                    } ${platform === p.id ? 'text-indigo-400' : ''}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <ExchangeLogo src={p.icon} name={p.name} size="w-4 h-4" disabled={p.comingSoon} />
                                        <span className="font-bold">{p.name}</span>
                                    </div>
                                    {p.comingSoon && <span className="px-2 py-0.5 rounded-md bg-white/5 text-[8px] font-black text-slate-500 uppercase">即将上线</span>}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* 2. Environment Toggle */}
                <div className="p-1 px-1 bg-[#0B0E11] rounded-2xl flex gap-1 border border-white/5">
                    {[
                        { id: 'live', label: '实盘交易 (Live)', icon: Zap },
                        { id: 'demo', label: '模拟交易 (Demo)', icon: Layout }
                    ].map(env => (
                        <button
                            key={env.id}
                            onClick={() => setEnvironment(env.id)}
                            className={`flex-1 py-3 rounded-xl flex items-center justify-center gap-2 text-[10px] font-black uppercase transition-all ${
                                environment === env.id ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
                            }`}
                        >
                            <env.icon className="w-3 h-3" />
                            {env.label}
                        </button>
                    ))}
                </div>

                <div className="space-y-4">
                    <Input label="账户别名" placeholder={placeholderText} value={formData.name} onChange={v => { setFormData(f => ({ ...f, name: v })); setError(null); }} />

                    <Input label="API Key" placeholder="请输入 API Key" icon={Key} value={formData.api_key} onChange={v => { setFormData(f => ({ ...f, api_key: v })); setError(null); }} />

                    <Input label="Secret Key" type="password" placeholder="请输入 Secret Key" value={formData.api_secret} onChange={v => { setFormData(f => ({ ...f, api_secret: v })); setError(null); }} />
                    
                    {platform === 'okx' && (
                        <Input label="Passphrase" type="password" placeholder="请输入 API Passphrase" value={formData.passphrase} onChange={v => { setFormData(f => ({ ...f, passphrase: v })); setError(null); }} />
                    )}

                    <div className="space-y-2 p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 animate-in slide-in-from-top-2">
                        <label className="block text-[10px] font-black text-indigo-400 uppercase tracking-widest ml-1 flex items-center justify-between">
                            IP 白名单配置
                            <button onClick={handleCopyIp} className="hover:text-indigo-300 flex items-center gap-1 font-black text-[9px] uppercase tracking-wider"><Copy className="w-3 h-3"/> 复制 IP</button>
                        </label>
                        <div className="text-xs font-mono text-slate-300 break-all bg-black/20 p-2.5 rounded-xl border border-white/5">{SERVER_IP}</div>
                        <p className="text-[10px] text-slate-500 leading-relaxed font-medium">{selectedPlatform?.name || '交易平台'}强烈建议开启 IP 绑定。请将上方 IP 填入 API 设置的白名单中。</p>
                    </div>
                </div>

                {error && (
                    <div className="flex items-center gap-2 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-[11px] font-black animate-in shake-200">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        <span>{error}</span>
                    </div>
                )}
                
                <div className="bg-amber-500/5 border border-amber-500/10 rounded-2xl p-4 space-y-2">
                    <div className="flex items-center gap-2 text-amber-500">
                        <ShieldCheck className="w-4 h-4" />
                        <span className="text-[10px] font-black uppercase tracking-widest leading-none">资产安全保障</span>
                    </div>
                    <p className="text-[10px] text-amber-200/60 leading-relaxed font-bold">
                        为了您的资金安全，请务必关闭 API 的“提现”权限。我们仅需要读取行情与下单交易权限。
                    </p>
                </div>
            </div>
        </Modal>
    );
}
