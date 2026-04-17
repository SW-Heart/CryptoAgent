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
import { getJson, postJson, deleteJson, uploadFile } from '../services/apiClient';
import Button from '../components/common/Button';
import Input from '../components/common/Input';
import ConnectExchangeModal from '../components/modals/ConnectExchangeModal';
import ConnectLLMModal from '../components/modals/ConnectLLMModal';
import ConfirmModal from '../components/modals/ConfirmModal';

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
            const { data: { user: freshUser } } = await supabase.auth.getUser();
            setUser(freshUser);
            setIsEditing(false);
        } catch (e) {
            alert("更新失败: " + e.message);
        } finally {
            setSaving(false);
        }
    };

    const handleUpdateAvatar = async () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            setSaving(true);
            try {
                const uploadRes = await uploadFile('/api/workspace/upload-avatar', file);
                if (!uploadRes || !uploadRes.url) throw new Error("上传失败，未返回URL");

                const { error } = await supabase.auth.updateUser({
                    data: { avatar_url: uploadRes.url }
                });

                if (error) throw error;
                const { data: { user: freshUser } } = await supabase.auth.getUser();
                setUser(freshUser);
            } catch (err) {
                alert("头像上传失败: " + err.message);
            } finally {
                setSaving(false);
            }
        };
        input.click();
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
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                    { label: "AI 模型", value: stats.llms, color: "text-emerald-400", icon: Cpu },
                    { label: "交易所", value: stats.exchanges, color: "text-emerald-400", icon: Globe },
                    { label: "活跃策略", value: 1, color: "text-amber-400", icon: ShieldCheck },
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
                    <h4 className="text-sm font-bold text-rose-500 mb-0.5">注销账号</h4>
                    <p className="text-slate-500 text-[10px] font-medium uppercase tracking-tight">永久删除您的账号及所有相关数据</p>
                </div>
                <button onClick={handleNukeData} className="px-4 py-2 rounded-lg bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white text-[10px] font-bold transition-all uppercase">
                    确认注销
                </button>
            </div>

            <ConfirmModal
                isOpen={showNukeConfirm}
                onClose={() => setShowNukeConfirm(false)}
                onConfirm={executeNukeData}
                loading={isNuking}
                title="危险：系统账号注销"
                message="此操作将永久删除您的账号，并物理清空所有的模型配置、交易所 API 密钥、持仓记录及决策日志。该动作无法被撤销。如果您确定要注销，请输入确认文字。"
                confirmText="永久注销"
                requireInputText="确认注销"
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
        google: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/google.svg",
        gemini: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/google.svg",
        qwen: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/qwen.svg",
        minimax: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/MiniMax.svg",
        kimi: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/kimi.svg",
        glm: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/%E6%99%BA%E8%B0%B1.svg"
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
                                {llmIcons[cfg.provider?.toLowerCase()] ? (
                                    <img src={llmIcons[cfg.provider?.toLowerCase()]} alt={cfg.provider} className="w-full h-full object-contain" />
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
        okx: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Okx.svg",
        bybit: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/bybit.svg",
        bitget: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Bitget.svg",
        gate: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/gate.io.svg"
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
                                {exchangeIcons[acc.provider?.toLowerCase()] ? (
                                    <img src={exchangeIcons[acc.provider?.toLowerCase()]} alt={acc.provider} className="w-full h-full object-contain" />
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

function NotificationSection({ userId }) {
    const [configs, setConfigs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [formChannel, setFormChannel] = useState('telegram');

    const [formData, setFormData] = useState({
        webhook_url: '',
        bot_token: '',
        chat_id: '',
        secret: ''
    });
    const [enabledEvents, setEnabledEvents] = useState({
        "TRADE_OPEN": true,
        "TRADE_CLOSE": true,
        "RISK_ALERT": true,
        "NEWS_ALERT": true,
        "SYSTEM_ALERT": true
    });
    const [isActive, setIsActive] = useState(true);

    const fetchConfigs = useCallback(async () => {
        try {
            const res = await getJson('/api/notifier/configs', {}, { 'X-User-Id': userId });
            if (res.configs) {
                setConfigs(res.configs);
                if (res.configs.length > 0) {
                    const first = res.configs[0];
                    setFormChannel(first.channel);
                    setFormData({
                        webhook_url: first.config.webhook_url || '',
                        bot_token: first.config.bot_token || '',
                        chat_id: first.config.chat_id || '',
                        secret: first.config.secret || ''
                    });
                    setIsActive(first.is_active);
                    const newEvents = { ...enabledEvents };
                    Object.keys(newEvents).forEach(k => newEvents[k] = false);
                    (first.enabled_events || []).forEach(e => newEvents[e] = true);
                    setEnabledEvents(newEvents);
                }
            }
        } catch (e) { console.error(e); }
        setLoading(false);
    }, [userId]);

    useEffect(() => {
        fetchConfigs();
    }, [fetchConfigs]);

    const loadConfigToForm = (cfg) => {
        setFormChannel(cfg.channel);
        setFormData({
            webhook_url: cfg.config.webhook_url || '',
            bot_token: cfg.config.bot_token || '',
            chat_id: cfg.config.chat_id || '',
            secret: cfg.config.secret || ''
        });
        setIsActive(cfg.is_active);
        const newEvents = {
            "TRADE_OPEN": false, "TRADE_CLOSE": false, "RISK_ALERT": false, "NEWS_ALERT": false, "SYSTEM_ALERT": false
        };
        (cfg.enabled_events || []).forEach(e => {
            if (newEvents[e] !== undefined) newEvents[e] = true;
        });
        setEnabledEvents(newEvents);
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const activeEvents = Object.keys(enabledEvents).filter(k => enabledEvents[k]);
            const payload = {
                channel: formChannel,
                config: formData,
                enabled_events: activeEvents,
                is_active: isActive
            };
            await postJson('/api/notifier/configs', payload, { 'X-User-Id': userId });
            alert("✅ 通知配置保存成功");
            fetchConfigs();
        } catch (e) {
            alert("保存失败: " + e.message);
        }
        setSaving(false);
    };

    const handleTest = async () => {
        try {
            const activeEvents = Object.keys(enabledEvents).filter(k => enabledEvents[k]);
            const payload = {
                channel: formChannel,
                config: formData,
                enabled_events: activeEvents,
                is_active: isActive
            };
            await postJson('/api/notifier/test', payload, { 'X-User-Id': userId });
            alert("📩 测试消息已发送，请检查您的接收端。");
        } catch (e) {
            alert("测试失败: " + e.message);
        }
    };

    if (loading) return <div className="p-8 flex justify-center"><Loader2 className="animate-spin text-emerald-500" /></div>;

    const channels = [
        { id: 'telegram', name: 'Telegram Bot' },
        { id: 'feishu', name: '飞书机器人' },
        { id: 'dingtalk', name: '钉钉群机器人' },
        { id: 'wechat', name: '企业微信机器人' },
    ];

    const EVENT_LABELS = {
        "TRADE_OPEN": "自动开仓通知",
        "TRADE_CLOSE": "自动平仓通知",
        "RISK_ALERT": "风控预警",
        "NEWS_ALERT": "重大新闻推送",
        "SYSTEM_ALERT": "系统运行异常"
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-4">
                <p className="text-xs font-bold text-slate-500">配置多个平台的消息推送，实时掌握交易动态与风险预警</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="col-span-1 space-y-2">
                    {channels.map(ch => {
                        const hasConfig = configs.find(c => c.channel === ch.id && c.is_active);
                        return (
                            <button
                                key={ch.id}
                                onClick={() => {
                                    const cfg = configs.find(c => c.channel === ch.id);
                                    if (cfg) loadConfigToForm(cfg);
                                    else {
                                        setFormChannel(ch.id);
                                        setFormData({ webhook_url: '', bot_token: '', chat_id: '', secret: '' });
                                        setIsActive(true);
                                    }
                                }}
                                className={`w-full p-4 rounded-xl flex items-center justify-between text-sm font-bold border transition-all ${formChannel === ch.id ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-400' : 'bg-white/5 border-white/5 text-slate-400 hover:text-white'}`}
                            >
                                {ch.name}
                                {hasConfig && <span className="w-2 h-2 rounded-full bg-emerald-500"></span>}
                            </button>
                        );
                    })}
                </div>

                <div className="col-span-3 bg-[#0e1215]/50 border border-white/5 rounded-3xl p-8 space-y-6 relative overflow-hidden">
                    {/* Decorative Blob */}
                    <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -mr-32 -mt-32 pointer-events-none"></div>

                    <div className="flex items-center justify-between relative z-10">
                        <h3 className="text-xl font-black text-white flex items-center gap-2">
                            {channels.find(c => c.id === formChannel)?.name}
                        </h3>
                        <label className="flex items-center justify-center cursor-pointer gap-2">
                            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{isActive ? '启用推送' : '已停用'}</span>
                            <div className="relative">
                                <input type="checkbox" className="sr-only" checked={isActive} onChange={e => setIsActive(e.target.checked)} />
                                <div className={`block w-10 h-6 pl-1 rounded-full flex flex-col justify-center transition-colors ${isActive ? 'bg-emerald-500' : 'bg-slate-700'}`}>
                                    <div className={`w-4 h-4 bg-white rounded-full transition-transform ${isActive ? 'translate-x-4' : 'translate-x-0'}`}></div>
                                </div>
                            </div>
                        </label>
                    </div>

                    <div className="space-y-4 relative z-10">
                        {formChannel === 'telegram' ? (
                            <>
                                <Input label="Bot Token" placeholder="例如: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" value={formData.bot_token} onChange={e => setFormData({ ...formData, bot_token: e.target.value })} type="password" />
                                <Input label="Chat ID (个人或群组)" placeholder="例如: -10012345678 或 12345678" value={formData.chat_id} onChange={e => setFormData({ ...formData, chat_id: e.target.value })} />
                            </>
                        ) : (
                            <>
                                <Input label="Webhook URL" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." value={formData.webhook_url} onChange={e => setFormData({ ...formData, webhook_url: e.target.value })} type="password" />
                                {(formChannel === 'dingtalk' || formChannel === 'feishu') && (
                                    <Input label="加签密钥 Secret (可选，若平台配置了加签则必填)" placeholder="SEC..." value={formData.secret} onChange={e => setFormData({ ...formData, secret: e.target.value })} type="password" />
                                )}
                            </>
                        )}
                    </div>

                    <div className="pt-6 border-t border-white/10 relative z-10">
                        <h4 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-4">订阅事件列表</h4>
                        <div className="grid grid-cols-2 gap-y-3 gap-x-6">
                            {Object.entries(EVENT_LABELS).map(([key, label]) => (
                                <label key={key} className="flex items-center gap-3 cursor-pointer group">
                                    <div className="relative flex items-center justify-center">
                                        <input type="checkbox" checked={enabledEvents[key] || false} onChange={e => setEnabledEvents({ ...enabledEvents, [key]: e.target.checked })} className="peer sr-only" />
                                        <div className="w-5 h-5 rounded flex items-center justify-center border-2 border-white/10 bg-white/5 peer-checked:bg-emerald-500/20 peer-checked:border-emerald-500 transition-all">
                                            {enabledEvents[key] && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />}
                                        </div>
                                    </div>
                                    <span className={`text-sm font-bold transition-colors ${enabledEvents[key] ? 'text-white' : 'text-slate-400 group-hover:text-slate-300'}`}>{label}</span>
                                </label>
                            ))}
                        </div>
                    </div>

                    <div className="pt-6 flex items-center justify-end gap-4 relative z-10">
                        <Button variant="secondary" onClick={handleTest} disabled={saving} icon={Bell}>推送测试</Button>
                        <Button variant="primary" onClick={handleSave} disabled={saving} icon={CheckCircle2}>{saving ? '保存中...' : '保存配置'}</Button>
                    </div>
                </div>
            </div>
        </div>
    );
}

const TABS = [
    { id: 'account', label: '账户信息', icon: User },
    { id: 'llm', label: '大模型配置', icon: Cpu },
    { id: 'exc', label: '交易所配置', icon: Globe },
    { id: 'notify', label: '通知推送', icon: Bell },
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
                    {activeTab === 'notify' && <NotificationSection userId={userId} />}
                </main>
            </div>
        </div>
    );
}
