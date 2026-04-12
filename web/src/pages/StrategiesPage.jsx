import React, { useState, useEffect, useCallback } from 'react';
import {
    Plus,
    Trash2,
    Save,
    Info,
    HelpCircle,
    Loader2,
    CheckCircle2,
    AlertCircle,
    Zap
} from 'lucide-react';
import Button from '../components/common/Button';
import ConfirmModal from '../components/modals/ConfirmModal';
import Toast from '../components/common/Toast';
import { getJson, postJson, putJson, deleteJson } from '../services/apiClient';

const StrategyHelp = ({ title, content }) => (
    <div className="group relative">
        <HelpCircle className="w-3.5 h-3.5 text-slate-500 hover:text-emerald-400 cursor-help transition-colors" />
        <div className="absolute right-0 bottom-full mb-2 w-64 p-4 bg-[#0a0d0f] border border-white/10 rounded-2xl shadow-2xl invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all z-50 pointer-events-none">
            <div className="font-bold text-[11px] text-white mb-1 uppercase tracking-wider">{title}</div>
            <div className="text-[10px] text-slate-400 leading-relaxed font-medium">{content}</div>
            <div className="absolute right-1 -bottom-1 w-2 h-2 bg-[#0a0d0f] border-r border-b border-white/10 rotate-45" />
        </div>
    </div>
);

const StrategiesPage = ({ userId }) => {
    const [profiles, setProfiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [selectedProfile, setSelectedProfile] = useState(null);
    const [availableModules, setAvailableModules] = useState([]);
    const [traderInstances, setTraderInstances] = useState([]);
    const [feedback, setFeedback] = useState(null);
    const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const showFeedback = (msg, type) => {
        setFeedback({ msg, type });
        setTimeout(() => setFeedback(null), 3000);
    };

    const parameterDocs = {
        symbols: { title: "交易标的", content: "AI 监控的币对，如 BTC, ETH, SOL。用英文逗号分隔。" },
        timeframes: { title: "分析周期", content: "AI 分析的 K 线周期，如 1h, 4h。" },
        risk_per_trade: { title: "单笔风险", content: "每笔交易占总仓位的比例 (0.01 = 1%)。" },
        trading_interval: { title: "扫描频率", content: "AI 每隔多少分钟扫描一次行情。" }
    };

    const fetchProfiles = useCallback(async () => {
        if (!userId) return;
        setLoading(true);
        try {
            const [profilesRes, tradersRes] = await Promise.all([
                getJson(`/api/workspace/strategy-profiles?user_id=${userId}`),
                getJson(`/api/workspace/trader-instances?user_id=${userId}`)
            ]);

            const list = profilesRes.profiles || [];
            setProfiles(list);
            setTraderInstances(tradersRes.traders || []);

            if (list.length > 0 && !selectedProfile) {
                setSelectedProfile(list[0]);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    }, [userId, selectedProfile]);

    const fetchModules = useCallback(async () => {
        try {
            const res = await getJson('/api/workspace/strategy-modules');
            setAvailableModules(res.modules || []);
        } catch (err) {
            console.error('Failed to load strategy modules:', err);
        }
    }, []);

    useEffect(() => {
        fetchProfiles();
        fetchModules();
    }, [userId]);

    const getEnabledModules = () => {
        const config = selectedProfile?.config || {};
        if (config.enabled_modules) return config.enabled_modules;
        // Default: modules with default_on=true
        return availableModules.filter(m => m.default_on && !m.always_on).map(m => m.id);
    };

    const toggleModule = (moduleId) => {
        const current = getEnabledModules();
        const next = current.includes(moduleId)
            ? current.filter(id => id !== moduleId)
            : [...current, moduleId];
        const config = { ...(selectedProfile?.config || {}), enabled_modules: next };
        updateField('config', config);
    };

    const handleCreate = async () => {
        setSaving(true);
        try {
            const res = await postJson(`/api/workspace/strategy-profiles?user_id=${userId}`, {
                name: "新策略草稿",
                description: "点击此处编辑策略描述",
                symbols: ["BTC", "ETH"],
                timeframes: ["1h"],
                risk_per_trade: 0.02,
                trading_interval: 60
            });
            const newList = res.profiles || [];
            setProfiles(newList);
            setSelectedProfile(newList[newList.length - 1]);
            showFeedback("策略已创建", "success");
        } catch (err) {
            showFeedback("创建失败", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleSave = async () => {
        if (!selectedProfile) return;
        setSaving(true);
        try {
            // Ensure symbols and timeframes are arrays if they were edited as strings
            const data = { ...selectedProfile };
            if (typeof data.symbols === 'string') data.symbols = data.symbols.split(',').map(s => s.trim());
            if (typeof data.timeframes === 'string') data.timeframes = data.timeframes.split(',').map(s => s.trim());

            const res = await putJson(`/api/workspace/strategy-profiles/${selectedProfile.id}?user_id=${userId}`, data);
            setProfiles(res.profiles || []);
            showFeedback("配置同步成功", "success");
        } catch (err) {
            showFeedback("保存失败", "error");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        setIsDeleting(true);
        try {
            const res = await deleteJson(`/api/workspace/strategy-profiles/${selectedProfile.id}?user_id=${userId}`);
            const newList = res.profiles || [];
            setProfiles(newList);
            setSelectedProfile(newList[0] || null);
            setIsConfirmingDelete(false);
            showFeedback("策略已删除", "success");
        } catch (err) {
            showFeedback("删除出错", "error");
        } finally {
            setIsDeleting(false);
        }
    };

    const handleUndo = () => {
        if (!selectedProfile) return;
        const original = profiles.find(p => p.id === selectedProfile.id);
        if (original) {
            setSelectedProfile({ ...original });
            showFeedback("已撤销更改", "success");
        }
    };

    const updateField = (field, value) => {
        setSelectedProfile(prev => ({ ...prev, [field]: value }));
    };

    if (loading && profiles.length === 0) {
        return (
            <div className="h-full flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col animate-in fade-in duration-500 relative">
            <Toast feedback={feedback} />

            <header className="mb-10 flex items-center justify-between">
                <div className="flex flex-col gap-1">
                    <h1 className="text-2xl font-bold text-white">策略库</h1>
                    <p className="text-slate-400 text-sm">定义您的交易逻辑与风控规则，AI 将严格执行。</p>
                </div>
                <Button icon={Plus} onClick={handleCreate} disabled={saving}>创建新策略</Button>
            </header>

            <div className="flex-1 flex gap-12 overflow-hidden">
                {/* Left Side: List */}
                <div className="w-48 flex flex-col gap-3 overflow-y-auto custom-scrollbar pr-2 flex-shrink-0">
                    {profiles.map(p => (
                        <button
                            key={p.id}
                            onClick={() => {
                                setSelectedProfile(p);
                                setIsConfirmingDelete(false);
                            }}
                            className={`p-4 rounded-2xl text-left border transition-all group shrink-0 ${selectedProfile?.id === p.id
                                ? 'bg-gradient-to-r from-white/10 to-transparent border-white/10 shadow-lg shadow-black/20'
                                : 'bg-[#0e1215]/50 border-white/5 hover:border-white/10'
                                }`}
                        >
                            <div className="flex items-center justify-between mb-2">
                                {(() => {
                                    const isRunning = traderInstances.some(t => t.strategy_profile_id === p.id && t.status === 'RUNNING');
                                    return (
                                        <div className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest ${isRunning ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-700/50 text-slate-400'
                                            }`}>
                                            {isRunning ? '运行中' : '未使用'}
                                        </div>
                                    );
                                })()}
                                <div className="text-[10px] text-slate-600 font-mono">#{p.id}</div>
                            </div>
                            <div className="font-bold text-slate-100 group-hover:text-emerald-400 transition-colors mb-1 truncate">{p.name}</div>
                        </button>
                    ))}
                    {profiles.length === 0 && (
                        <div className="p-8 border border-dashed border-white/10 rounded-2xl text-center">
                            <p className="text-xs text-slate-500">点击上方按钮创建您的第一个策略</p>
                        </div>
                    )}
                </div>

                {/* Right Side: Detail Editor */}
                {selectedProfile ? (
                    <main className="flex-1 bg-[#0e1215]/30 border border-white/5 rounded-[40px] flex flex-col overflow-hidden shadow-2xl relative backdrop-blur-sm">
                        <div className="p-10 overflow-y-auto custom-scrollbar flex-1">
                            {selectedProfile.source === 'legacy_import' && (
                                <div className="mb-6 px-4 py-3 bg-amber-500/5 border border-amber-500/20 rounded-xl flex items-center gap-3">
                                    <Info className="w-4 h-4 text-amber-400 flex-shrink-0" />
                                    <span className="text-xs text-amber-400/80 font-medium">系统默认策略，不可编辑或删除。如需自定义，请创建新策略。</span>
                                </div>
                            )}
                            <div className="max-w-3xl space-y-10">
                                <section>
                                    <div className="flex items-center gap-2 mb-6">
                                        <div className="w-1.5 h-4 bg-emerald-500 rounded-full" />
                                        <h3 className="text-sm font-bold text-white uppercase tracking-widest">基础信息</h3>
                                    </div>
                                    <div className="grid gap-6">
                                        <div>
                                            <label className="block text-xs font-bold text-slate-500 mb-2 ml-1 uppercase tracking-widest">策略名称</label>
                                            <input
                                                value={selectedProfile.name}
                                                onChange={e => updateField('name', e.target.value)}
                                                disabled={selectedProfile.source === 'legacy_import'}
                                                className={`w-full bg-[#060809] border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 transition-all font-medium text-white ${selectedProfile.source === 'legacy_import' ? 'opacity-50 cursor-not-allowed' : ''}`}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-bold text-slate-500 mb-2 ml-1 uppercase tracking-widest">策略描述</label>
                                            <textarea
                                                rows={2}
                                                value={selectedProfile.description || ''}
                                                onChange={e => updateField('description', e.target.value)}
                                                disabled={selectedProfile.source === 'legacy_import'}
                                                className={`w-full bg-[#060809] border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 transition-all resize-none font-medium text-white ${selectedProfile.source === 'legacy_import' ? 'opacity-50 cursor-not-allowed' : ''}`}
                                            />
                                        </div>
                                    </div>
                                </section>

                                <section>
                                    <div className="flex items-center gap-2 mb-6">
                                        <div className="w-1.5 h-4 bg-teal-500 rounded-full" />
                                        <h3 className="text-sm font-bold text-white uppercase tracking-widest">交易参数与风控</h3>
                                    </div>
                                    <div className="grid grid-cols-2 gap-8">
                                        {Object.entries(parameterDocs).map(([key, doc]) => (
                                            <div key={key}>
                                                <div className="flex items-center justify-between mb-2 mx-1">
                                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">{doc.title}</label>
                                                    <StrategyHelp title={doc.title} content={doc.content} />
                                                </div>
                                                <input
                                                    value={Array.isArray(selectedProfile[key]) ? selectedProfile[key].join(', ') : selectedProfile[key]}
                                                    onChange={e => updateField(key, e.target.value)}
                                                    disabled={selectedProfile.source === 'legacy_import'}
                                                    className={`w-full bg-[#060809] border border-white/10 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 transition-all font-mono text-white ${selectedProfile.source === 'legacy_import' ? 'opacity-50 cursor-not-allowed' : ''}`}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </section>

                                {/* 分析模块配置 */}
                                <section>
                                    <div className="flex items-center gap-2 mb-6">
                                        <div className="w-1.5 h-4 bg-emerald-500 rounded-full" />
                                        <h3 className="text-sm font-bold text-white uppercase tracking-widest">分析模块配置</h3>
                                        <div className="flex items-center gap-1 ml-auto">
                                            <Zap className="w-3 h-3 text-emerald-400" />
                                            <span className="text-[10px] text-slate-500 font-medium">选中的模块将在每次扫描中提供数据给 AI</span>
                                        </div>
                                    </div>

                                    {/* Core Modules (always on) */}
                                    <div className="mb-4">
                                        <div className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-3 ml-1">必选 · 始终启用</div>
                                        <div className="grid grid-cols-4 gap-3">
                                            {availableModules.filter(m => m.always_on).map(m => (
                                                <div key={m.id} className="bg-[#060809] border border-emerald-500/20 rounded-xl px-3 py-3 text-center opacity-80">
                                                    <div className="text-lg mb-1">{m.icon}</div>
                                                    <div className="text-[11px] font-bold text-emerald-400">{m.name}</div>
                                                    <div className="text-[9px] text-slate-600 mt-0.5 leading-tight">{m.description}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Optional Modules (toggleable) */}
                                    <div>
                                        <div className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-3 ml-1">可选 · 技术指标模块</div>
                                        <div className="grid grid-cols-3 gap-3">
                                            {availableModules.filter(m => !m.always_on).map(m => {
                                                const enabled = getEnabledModules().includes(m.id);
                                                return (
                                                    <button
                                                        key={m.id}
                                                        onClick={() => toggleModule(m.id)}
                                                        className={`bg-[#060809] border rounded-xl px-3 py-3 text-center transition-all group ${enabled
                                                            ? 'border-emerald-500/40 shadow-lg shadow-emerald-500/5'
                                                            : 'border-white/5 hover:border-white/15 opacity-50'
                                                            }`}
                                                    >
                                                        <div className="text-lg mb-1">{m.icon}</div>
                                                        <div className={`text-[11px] font-bold transition-colors ${enabled ? 'text-emerald-400' : 'text-slate-500'
                                                            }`}>{m.name}</div>
                                                        <div className="text-[9px] text-slate-600 mt-0.5 leading-tight">{m.description}</div>
                                                        <div className={`mt-2 text-[9px] font-bold uppercase tracking-widest ${enabled ? 'text-emerald-400' : 'text-slate-700'
                                                            }`}>
                                                            {enabled ? '✓ 已启用' : '关闭'}
                                                        </div>
                                                        {m.warning && enabled && (
                                                            <div className="text-[8px] text-amber-500/80 mt-1">⚠️ {m.warning}</div>
                                                        )}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </section>

                                <section>
                                    <div className="flex items-center gap-2 mb-6">
                                        <div className="w-1.5 h-4 bg-teal-500 rounded-full" />
                                        <h3 className="text-sm font-bold text-white uppercase tracking-widest">自定义交易指令 (选填)</h3>
                                    </div>
                                    <textarea
                                        rows={6}
                                        value={selectedProfile.prompt_template || ''}
                                        onChange={e => updateField('prompt_template', e.target.value)}
                                        disabled={selectedProfile.source === 'legacy_import'}
                                        className={`w-full bg-[#060809] border border-white/10 rounded-2xl px-4 py-3 text-sm focus:border-emerald-500 transition-all font-mono text-slate-300 leading-relaxed ${selectedProfile.source === 'legacy_import' ? 'opacity-50 cursor-not-allowed' : ''}`}
                                    />
                                </section>
                            </div>
                        </div>

                        <div className="p-6 bg-[#060809]/50 border-t border-white/5 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                {selectedProfile.source === 'legacy_import' ? (
                                    <span className="text-xs text-slate-600 font-medium">系统默认策略</span>
                                ) : (
                                    <Button variant="danger" icon={Trash2} onClick={() => setIsConfirmingDelete(true)}>删除策略</Button>
                                )}
                            </div>

                            {selectedProfile.source !== 'legacy_import' && (
                                <div className="flex items-center gap-3">
                                    <Button variant="outline" onClick={handleUndo}>撤销更改</Button>
                                    <Button icon={saving ? Loader2 : Save} onClick={handleSave} disabled={saving}>
                                        {saving ? "保存中..." : "保存并应用配置"}
                                    </Button>
                                </div>
                            )}
                        </div>
                    </main>
                ) : (
                    <main className="flex-1 flex flex-col items-center justify-center bg-[#0e1215]/30 border border-dashed border-white/5 rounded-[40px] text-slate-500 backdrop-blur-sm">
                        <div className="p-4 rounded-full bg-slate-800/50 mb-4">
                            <Info className="w-8 h-8" />
                        </div>
                        <p className="text-sm font-medium">请从左侧选择一个策略，或新建策略</p>
                    </main>
                )}
            </div>
            <ConfirmModal
                isOpen={isConfirmingDelete}
                onClose={() => setIsConfirmingDelete(false)}
                onConfirm={handleDelete}
                loading={isDeleting}
                title="删除策略"
                message="确定要永久删除此策略吗？关联的运行实例可能会受到影响。此动作无法撤销。"
                confirmText="删除"
                type="danger"
            />
        </div>
    );
};

export default StrategiesPage;
