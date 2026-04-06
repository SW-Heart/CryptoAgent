import React, { useState, useEffect, useCallback } from 'react';
import {
    User,
    Cpu,
    Globe,
    Settings,
    Shield,
    Bell,
    Database,
    ChevronRight,
    CheckCircle2,
    AlertCircle,
    Loader2,
    Trash2,
    Plus,
    LogOut,
    Mail,
    Calendar,
    Moon,
    Languages,
    AlertTriangle,
    Key,
    ShieldCheck,
    Copy
} from 'lucide-react';
import { supabase } from '../lib/supabaseClient';
import { getJson, postJson, deleteJson } from '../services/apiClient';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import ConnectExchangeModal from '../components/ConnectExchangeModal';
import ConnectLLMModal from '../components/ConnectLLMModal';
import ConfirmModal from '../components/ConfirmModal';

// --- Sub-components for Settings Sections ---

function AccountSection({ userId, user: initialUser }) {
    const [stats, setStats] = useState({ llms: 0, exchanges: 0 });
    const [user, setUser] = useState(initialUser);
    const [loading, setLoading] = useState(true);
    const [isEditing, setIsEditing] = useState(false);
    const [editName, setEditName] = useState(initialUser?.user_metadata?.full_name || '');
    const [saving, setSaving] = useState(false);
    const [showNukeConfirm, setShowNukeConfirm] = useState(false);
    const [isNuking, setIsNuking] = useState(false);

    useEffect(() => {
        async function loadProfileAndStats() {
            if (!userId) return;
            try {
                // Fetch full fresh user to ensure we have created_at and full metadata
                const { data: { user: freshUser } } = await supabase.auth.getUser();
                if (freshUser) {
                    setUser(freshUser);
                    setEditName(freshUser.user_metadata?.full_name || '');
                }

                const [llmRes, exchRes] = await Promise.all([
                    getJson(`/api/workspace/llm-configs?user_id=${userId}`),
                    getJson(`/api/workspace/exchange-accounts?user_id=${userId}`)
                ]);
                setStats({
                    llms: llmRes.configs?.length || 0,
                    exchanges: exchRes.accounts?.length || 0
                });
            } catch (e) { console.error("Data load failed", e); }
            setLoading(false);
        }
        loadProfileAndStats();
    }, [userId]);

    const handleUpdateProfile = async () => {
        setSaving(true);
        try {
            const { error } = await supabase.auth.updateUser({
                data: { full_name: editName }
            });
            if (error) throw error;
            await supabase.auth.refreshSession();
            setIsEditing(false);
            window.location.reload();
        } catch (e) {
            alert("更新失败: " + e.message);
        } finally {
            setSaving(false);
        }
    };

    const handleUpdateAvatar = async () => {
        const newAvatar = window.prompt("请输入新的头像 URL:", user?.user_metadata?.avatar_url);
        if (!newAvatar) return;
        setSaving(true);
        try {
            const { error } = await supabase.auth.updateUser({
                data: { avatar_url: newAvatar }
            });
            if (error) throw error;
            await supabase.auth.refreshSession();
            window.location.reload();
        } catch (e) {
            alert("头像更新失败");
        } finally {
            setSaving(false);
        }
    };

    const handleLogout = async () => {
        await supabase.auth.signOut();
        window.location.href = '/welcome';
    };

    const handleNukeData = () => {
        setShowNukeConfirm(true);
    };

    const executeNukeData = async () => {
        setIsNuking(true);
        try {
            await postJson(`/api/workspace/nuke?user_id=${userId}`);
            setShowNukeConfirm(false);
            window.location.reload();
        } catch (e) {
            alert("操作失败");
        } finally {
            setIsNuking(false);
        }
    };

    const getLoginIdentifier = () => {
        const provider = user?.app_metadata?.provider || user?.identities?.[0]?.provider || 'email';
        const account = user?.email || user?.identities?.[0]?.identity_data?.email || 'N/A';
        return `${provider.toUpperCase()}: ${account}`;
    };

    const formatJoinDate = (dateStr) => {
        if (!dateStr) return '2026/03/25';
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) return '2026/03/25';
            return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
        } catch (e) { return '2026/03/25'; }
    };

    return (
        <div className="max-w-4xl space-y-6 animate-in fade-in duration-500">
            {/* --- Compact Professional Header --- */}
            <div className="bg-[#0A0D0F]/50 border border-white/5 rounded-2xl p-6 flex flex-col md:flex-row items-center gap-6">
                <div className="relative group cursor-pointer" onClick={handleUpdateAvatar}>
                    <img
                        src={user?.user_metadata?.avatar_url || `https://api.dicebear.com/7.x/initials/svg?seed=${user?.email}`}
                        className="w-20 h-20 rounded-full border-2 border-white/10 group-hover:border-emerald-500 transition-all shadow-lg"
                        alt="avatar"
                    />
                    <div className="absolute inset-0 bg-black/40 rounded-full opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                        <Plus className="w-5 h-5 text-white" />
                    </div>
                </div>

                <div className="flex-1 space-y-2 text-center md:text-left">
                    <div className="flex items-center justify-center md:justify-start gap-3">
                        {isEditing ? (
                            <div className="flex items-center gap-2">
                                <input
                                    className="bg-black/20 border border-emerald-500/50 rounded-lg px-3 py-1 text-white text-lg font-bold focus:outline-none"
                                    value={editName}
                                    onChange={(e) => setEditName(e.target.value)}
                                    autoFocus
                                />
                                <button onClick={handleUpdateProfile} disabled={saving} className="text-emerald-500 hover:text-emerald-400 p-1">
                                    <CheckCircle2 className="w-5 h-5" />
                                </button>
                                <button onClick={() => setIsEditing(false)} className="text-rose-500 hover:text-rose-400 p-1">
                                    <AlertCircle className="w-5 h-5" />
                                </button>
                            </div>
                        ) : (
                            <>
                                <h2 className="text-xl font-bold text-white tracking-tight">{user?.user_metadata?.full_name || '探索者'}</h2>
                                <button onClick={() => setIsEditing(true)} className="text-slate-500 hover:text-emerald-400 opacity-0 group-hover:opacity-100 md:opacity-100 transition-all p-1">
                                    <Settings className="w-3.5 h-3.5" />
                                </button>
                            </>
                        )}
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-wider border border-emerald-500/20">
                            Pro Account
                        </span>
                    </div>
                    <p className="text-slate-500 text-sm font-medium flex items-center justify-center md:justify-start gap-2">
                        {user?.email} <span className="w-1 h-1 bg-emerald-500 rounded-full"></span> 已验证
                    </p>
                </div>

                <div className="flex gap-2">
                    <button onClick={handleLogout} className="px-4 py-2 rounded-xl bg-white/5 hover:bg-rose-500/10 hover:text-rose-500 text-slate-300 text-xs font-bold transition-all flex items-center gap-2 border border-white/5">
                        <LogOut className="w-3.5 h-3.5" /> 退出
                    </button>
                </div>
            </div>

            {/* --- Account Stats Inline --- */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                    { label: "AI 模型", value: stats.llms, color: "text-emerald-400", icon: Cpu },
                    { label: "交易所", value: stats.exchanges, color: "text-emerald-400", icon: Globe },
                    { label: "活跃策略", value: 1, color: "text-amber-400", icon: ShieldCheck },
                    { label: "运行天数", value: 15, color: "text-slate-400", icon: Calendar },
                ].map((item, i) => (
                    <div key={i} className="bg-white/[0.02] border border-white/5 p-4 rounded-xl flex items-center gap-4">
                        <div className={`p-2.5 rounded-lg bg-white/5 ${item.color}`}><item.icon className="w-5 h-5" /></div>
                        <div>
                            <div className="text-xs font-bold text-slate-500 uppercase tracking-tighter">{item.label}</div>
                            <div className="text-lg font-black text-white leading-none mt-0.5">{loading ? '...' : item.value}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* --- Detailed Info Grid --- */}
            <div className="bg-[#0A0D0F]/30 border border-white/5 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-6 py-4 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white flex items-center gap-2"><Shield className="w-4 h-4 text-emerald-400" /> 身份认证与安全</h3>
                    <span className="text-[10px] font-black text-emerald-500 uppercase bg-emerald-500/10 px-2 py-0.5 rounded">Security LV.2</span>
                </div>
                <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-y-6 gap-x-12">
                    <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-loose">UID (用户标识)</span>
                        <code className="text-slate-300 text-xs font-mono bg-black/20 p-2 rounded-lg flex items-center justify-between group">
                            {userId?.substring(0, 18) || 'Loading...'}...
                            <button
                                onClick={() => {
                                    navigator.clipboard.writeText(userId);
                                    alert("UID 已复制本地");
                                }}
                                className="text-emerald-400 opacity-0 group-hover:opacity-100 transition-all p-1 hover:bg-white/5 rounded-md active:scale-90"
                            >
                                <Copy className="w-3.5 h-3.5" />
                            </button>
                        </code>
                    </div>
                    <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-loose">登录方式</span>
                        <div className="text-slate-300 text-sm font-bold flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-emerald-500"></div> {getLoginIdentifier()}
                        </div>
                    </div>
                    <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-loose">注册时间</span>
                        <div className="text-slate-300 text-sm font-bold">{formatJoinDate(user?.created_at)}</div>
                    </div>
                    <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-loose">账户等级</span>
                        <div className="text-emerald-500 text-sm font-bold flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4" /> 账户受加密保护
                        </div>
                    </div>
                </div>
            </div>

            {/* --- Subtle Danger Zone --- */}
            <div className="p-6 rounded-2xl border border-rose-500/10 bg-rose-500/[0.01] flex items-center justify-between">
                <div>
                    <h4 className="text-sm font-bold text-rose-500 mb-0.5">重置工作区</h4>
                    <p className="text-slate-500 text-[10px] font-medium uppercase tracking-tight">清空所有配置、密钥及历史记录</p>
                </div>
                <button onClick={handleNukeData} className="px-4 py-2 rounded-lg bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white text-[10px] font-bold transition-all uppercase">
                    物理清空数据
                </button>
            </div>

            <ConfirmModal
                isOpen={showNukeConfirm}
                onClose={() => setShowNukeConfirm(false)}
                onConfirm={executeNukeData}
                loading={isNuking}
                title="危险：物理清空工作区"
                message="此操作将永久删除您的所有模型配置、交易所 API 密钥、持仓记录及决策日志。该动作无法被撤销，您的账户将恢复至初始未配置状态。确定要继续吗？"
                confirmText="同步清除所有数据"
                type="danger"
            />
        </div>
    );
}



function LLMSection({ userId, onUpdate }) {
    const [configs, setConfigs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isConnecting, setIsConnecting] = useState(false);
    const [acting, setActing] = useState(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [idToDelete, setIdToDelete] = useState(null);

    const fetchConfigs = useCallback(async (isInitial = false) => {
        if (isInitial) setLoading(true);
        try {
            const res = await getJson(`/api/workspace/llm-configs?user_id=${userId}`);
            setConfigs(res.configs || []);
        } catch (err) {
            console.error(err);
        } finally {
            if (isInitial) setLoading(false);
        }
    }, [userId]);

    useEffect(() => {
        fetchConfigs(true);
        const onFocus = () => fetchConfigs(false);
        window.addEventListener('focus', onFocus);
        return () => window.removeEventListener('focus', onFocus);
    }, [fetchConfigs]);

    const handleDeleteClick = (id) => {
        setIdToDelete(id);
        setShowDeleteConfirm(true);
    };

    const executeDelete = async () => {
        if (!idToDelete) return;
        setActing(idToDelete);
        try {
            await deleteJson(`/api/workspace/llm-configs/${idToDelete}?user_id=${userId}`);
            await fetchConfigs();
            onUpdate?.();
        } catch (err) {
            alert("删除失败");
        } finally {
            setActing(null);
            setShowDeleteConfirm(false);
            setIdToDelete(null);
        }
    };

    const llmIcons = {
        openai: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/openai.svg",
        deepseek: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/deepseek.svg",
        anthropic: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Claude.svg",
        google: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/google.svg"
    };

    if (loading) {
        return (
            <div className="h-64 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-4">
                <p className="text-xs font-bold text-slate-500">配置多个 AI 决策大脑以实现不同场景下的交易研判</p>
                <Button variant="secondary" size="sm" onClick={() => setIsConnecting(true)} icon={Plus}>添加新模型</Button>
            </div>

            <div className="grid gap-4">
                {configs.map(cfg => (
                    <div key={cfg.id} className="p-6 rounded-3xl border border-white/5 bg-[#0e1215]/50 flex items-center justify-between group hover:border-emerald-500/20 transition-all">
                        <div className="flex items-center gap-5">
                            <div className="w-5 h-5 flex items-center justify-center">
                                {llmIcons[cfg.provider] ? (
                                    <img src={llmIcons[cfg.provider]} alt={cfg.provider} className="w-full h-full object-contain" />
                                ) : (
                                    <Cpu className="w-5 h-5 text-emerald-400" />
                                )}
                            </div>
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <h4 className="text-white font-black text-base">{cfg.name}</h4>
                                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[8px] font-black uppercase tracking-widest">
                                        {cfg.provider.toUpperCase()}
                                    </span>
                                </div>
                                <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest flex items-center gap-1">
                                    模型 ID: {cfg.model} <span className="opacity-20">•</span> 状态: 已测试通畅
                                </p>
                            </div>
                        </div>

                        <button
                            onClick={() => handleDeleteClick(cfg.id)}
                            disabled={acting === cfg.id}
                            className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 hover:text-rose-500 hover:bg-rose-500/10 transition-all disabled:opacity-50"
                        >
                            {acting === cfg.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                        </button>
                    </div>
                ))}


                {configs.length === 0 && (
                    <div className="p-12 rounded-3xl border border-dashed border-white/10 flex flex-col items-center justify-center text-center">
                        <div className="w-16 h-16 rounded-full bg-white/[0.02] flex items-center justify-center mb-4">
                            <Cpu className="w-6 h-6 text-slate-600" />
                        </div>
                        <h4 className="text-slate-300 font-black mb-2 px-2">暂无已装载的 AI 大脑</h4>
                        <p className="text-slate-500 text-xs mb-8 max-w-[240px]">至少配置一个大模型 API，AI 才能开始为您分析行情并制定策略。</p>
                        <Button variant="primary" onClick={() => setIsConnecting(true)} icon={Plus}>立即配置大模型</Button>
                    </div>
                )}
            </div>

            <ConnectLLMModal
                userId={userId}
                isOpen={isConnecting}
                onClose={() => setIsConnecting(false)}
                onConnected={() => { fetchConfigs(); onUpdate?.(); }}
            />

            <ConfirmModal
                isOpen={showDeleteConfirm}
                onClose={() => setShowDeleteConfirm(false)}
                onConfirm={executeDelete}
                loading={!!acting}
                title="删除模型配置"
                message="确定要删除此 AI 模型配置吗？删除后，相关交易实例将无法调用该模型进行研判。此动作无法撤销。"
                confirmText="同步删除"
                type="danger"
            />
        </div>
    );
}

function ExchangeSection({ userId, onUpdate }) {
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isConnecting, setIsConnecting] = useState(false);
    const [acting, setActing] = useState(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [idToDelete, setIdToDelete] = useState(null);

    const fetchAccounts = useCallback(async (isInitial = false) => {
        if (isInitial) setLoading(true);
        try {
            const res = await getJson(`/api/workspace/exchange-accounts?user_id=${userId}`);
            setAccounts(res.accounts || []);
        } catch (err) {
            console.error(err);
        } finally {
            if (isInitial) setLoading(false);
        }
    }, [userId]);

    useEffect(() => {
        fetchAccounts(true);

        // Silent refresh
        const onFocus = () => fetchAccounts(false);
        window.addEventListener('focus', onFocus);
        return () => window.removeEventListener('focus', onFocus);
    }, [fetchAccounts]);

    const handleDeleteClick = (id) => {
        setIdToDelete(id);
        setShowDeleteConfirm(true);
    };

    const executeDelete = async () => {
        if (!idToDelete) return;
        setActing(idToDelete);
        try {
            await deleteJson(`/api/workspace/exchange-accounts/${idToDelete}?user_id=${userId}`);
            await fetchAccounts();
            onUpdate?.();
        } catch (err) {
            alert("解除绑定失败");
        } finally {
            setActing(null);
            setShowDeleteConfirm(false);
            setIdToDelete(null);
        }
    };

    const exchangeIcons = {
        binance: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/binance.svg",
        okx: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Okx.svg"
    };

    if (loading) {
        return (
            <div className="h-64 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-4">
                <p className="text-xs font-bold text-slate-500">连接您的交易所 API 以开启实盘/模拟交易</p>
                <Button variant="secondary" size="sm" onClick={() => setIsConnecting(true)} icon={Plus}>连接新账户</Button>
            </div>

            <div className="grid gap-4">
                {accounts.map(acc => (
                    <div key={acc.id} className="p-6 rounded-3xl border border-white/5 bg-[#0e1215]/50 flex items-center justify-between group hover:border-emerald-500/20 transition-all">
                        <div className="flex items-center gap-5">
                            <div className="w-5 h-5 flex items-center justify-center">
                                {exchangeIcons[acc.provider] ? (
                                    <img src={exchangeIcons[acc.provider]} alt={acc.provider} className="w-full h-full object-contain" />
                                ) : (
                                    <Globe className="w-5 h-5 text-slate-400" />
                                )}
                            </div>
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <h4 className="text-white font-black text-base">{acc.display_name}</h4>
                                    <span className={`px-2 py-0.5 rounded-full text-[8px] font-black uppercase tracking-widest ${acc.environment === 'live' ? 'bg-amber-500/10 text-amber-500' : 'bg-emerald-500/10 text-emerald-500'
                                        }`}>
                                        {acc.environment === 'live' ? '实盘' : '模拟'}
                                    </span>
                                </div>
                                <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest flex items-center gap-1">
                                    平台: {acc.provider.toUpperCase()}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => handleDeleteClick(acc.id)}
                                disabled={acting === acc.id}
                                className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 hover:text-rose-500 hover:bg-rose-500/10 transition-all disabled:opacity-50"
                            >
                                {acting === acc.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>
                ))}

                {accounts.length === 0 && (
                    <div className="p-12 rounded-3xl border border-dashed border-white/10 flex flex-col items-center justify-center text-center">
                        <div className="w-16 h-16 rounded-full bg-white/[0.02] flex items-center justify-center mb-4">
                            <Key className="w-6 h-6 text-slate-600" />
                        </div>
                        <h4 className="text-slate-300 font-black mb-2 px-2">暂无绑定的交易所 API</h4>
                        <p className="text-slate-500 text-xs mb-8 max-w-[240px]">请首先建立与交易所的连接，以便 AI 能够获取市场深度并下单。</p>
                        <Button variant="primary" onClick={() => setIsConnecting(true)} icon={Plus}>立即连接交易所</Button>
                    </div>
                )}
            </div>

            <ConnectExchangeModal
                userId={userId}
                isOpen={isConnecting}
                onClose={() => setIsConnecting(false)}
                onConnected={() => { fetchAccounts(); onUpdate?.(); }}
            />

            <ConfirmModal
                isOpen={showDeleteConfirm}
                onClose={() => setShowDeleteConfirm(false)}
                onConfirm={executeDelete}
                loading={!!acting}
                title="解除交易所绑定"
                message="确定要解除此交易所 API 的绑定吗？解除后，所有依赖此账户的交易实例将立即停止运行，且历史持仓数据可能无法实时同步。此银作不可撤销。"
                confirmText="确认解除"
                type="danger"
            />
        </div>
    );
}

const TABS = [
    { id: 'account', label: '账户信息', icon: User },
    { id: 'llm', label: '大模型配置', icon: Cpu },
    { id: 'exc', label: '交易所配置', icon: Globe },
];

export default function SettingsPage({ userId, initialTab = 'account', onConfigUpdated }) {
    const [activeTab, setActiveTab] = useState(initialTab);

    useEffect(() => {
        if (initialTab) setActiveTab(initialTab);
    }, [initialTab]);

    return (
        <div className="h-full flex flex-col">
            <header className="mb-10 flex flex-col gap-1">
                <h1 className="text-2xl font-bold text-white">系统设置</h1>
                <p className="text-slate-400 text-sm">管理您的账户安全、模型连接及交易所授权。</p>
            </header>

            <div className="flex-1 flex gap-12 overflow-hidden">
                {/* Internal Sidebar */}
                <nav className="w-48 space-y-1.5 flex-shrink-0">
                    {TABS.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`w-full group px-6 py-4 rounded-2xl flex items-center gap-4 transition-all duration-300 ${activeTab === tab.id
                                    ? 'bg-gradient-to-r from-white/10 to-transparent border border-white/10 shadow-lg shadow-black/20 text-white'
                                    : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02] border border-transparent'
                                }`}
                        >
                            <tab.icon className={`w-5 h-5 transition-transform group-hover:scale-110 ${activeTab === tab.id ? 'text-white' : 'text-slate-500'}`} />
                            <span className="text-sm font-black tracking-wide uppercase">{tab.label}</span>
                            {activeTab === tab.id && <ChevronRight className="w-4 h-4 ml-auto" />}
                        </button>
                    ))}
                </nav>

                {/* Content Area */}
                <main className="flex-1 bg-[#0e1215]/30 border border-white/5 rounded-[40px] p-10 overflow-y-auto custom-scrollbar shadow-2xl backdrop-blur-sm">
                    {activeTab === 'account' && <AccountSection userId={userId} />}
                    {activeTab === 'llm' && <LLMSection userId={userId} onUpdate={onConfigUpdated} />}
                    {activeTab === 'exc' && <ExchangeSection userId={userId} onUpdate={onConfigUpdated} />}
                </main>
            </div>
        </div>
    );
}
