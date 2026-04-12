import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Save, Settings, Shield, Target, Activity, MessageSquare, AlertCircle, Loader2, Clock, ChevronDown } from 'lucide-react';
import { BASE_URL } from '../../services/config';

export default function StrategySettingsModal({ isOpen, onClose, userId }) {
    const { t } = useTranslation();
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    const [config, setConfig] = useState({
        symbols: 'BTC,ETH,SOL',
        max_positions: 3,
        risk_per_trade: 0.02,
        trading_interval: 60,
        agent_requirements: 'Focus on trend following strategy with strict risk management.'
    });

    useEffect(() => {
        if (isOpen && userId) {
            fetchConfig();
        }
    }, [isOpen, userId]);

    const fetchConfig = async () => {
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/config?user_id=${userId}`);
            if (res.ok) {
                const data = await res.json();
                setConfig({
                    symbols: data.symbols || 'BTC,ETH,SOL',
                    max_positions: data.max_positions || 3,
                    risk_per_trade: data.risk_per_trade || 0.02,
                    trading_interval: data.trading_interval || 60,
                    agent_requirements: data.agent_requirements || 'Focus on trend following strategy with strict risk management.'
                });
            }
        } catch (e) {
            console.error('Fetch config error:', e);
            setError('Failed to load settings');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setError('');
        setSuccess(false);
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/config/set?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            if (res.ok) {
                setSuccess(true);
                setTimeout(() => {
                    setSuccess(false);
                    onClose();
                }, 1500);
            } else {
                setError('Failed to save settings');
            }
        } catch (e) {
            console.error('Save config error:', e);
            setError('Error saving settings');
        } finally {
            setSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="bg-[#1a1f2e] rounded-2xl w-full max-w-xl shadow-2xl border border-slate-700/50 flex flex-col overflow-hidden animate-in fade-in zoom-in duration-200">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-slate-700/50 bg-[#131722]/50">
                    <div className="flex items-center gap-2">
                        <div className="p-2 bg-indigo-500/10 rounded-lg">
                            <Settings className="w-5 h-5 text-indigo-400" />
                        </div>
                        <h2 className="text-lg font-bold text-white">{t('strategy.settings.title', 'Trading Strategy Settings')}</h2>
                    </div>
                    <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6 overflow-y-auto max-h-[70vh]">
                    {loading ? (
                        <div className="py-12 flex flex-col items-center justify-center gap-3">
                            <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
                            <p className="text-slate-400 text-sm">Loading config...</p>
                        </div>
                    ) : (
                        <>
                            {/* Symbols */}
                            <div className="space-y-2">
                                <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                                    <Target className="w-4 h-4 text-indigo-400" />
                                    {t('strategy.settings.symbols', 'Trading Symbols (Full list, e.g. BTC,ETH,SOL)')}
                                </label>
                                <input
                                    type="text"
                                    value={config.symbols}
                                    onChange={(e) => setConfig({ ...config, symbols: e.target.value })}
                                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all font-mono text-sm"
                                    placeholder="BTC,ETH,SOL"
                                />
                                <p className="text-xs text-slate-500">Separated by commas. Agent will analyze these pairs for opportunities.</p>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                {/* Trading Frequency */}
                                <div className="space-y-2">
                                    <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                                        <Clock className="w-4 h-4 text-sky-400" />
                                        {t('strategy.settings.tradingInterval', 'Strategy Frequency')}
                                    </label>
                                    <div className="relative">
                                        <select
                                            value={config.trading_interval}
                                            onChange={(e) => setConfig({ ...config, trading_interval: parseInt(e.target.value) })}
                                            className="w-full bg-[#0d1117] border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all appearance-none"
                                        >
                                            <option value={15}>15 {t('common.minutes', 'Min')}</option>
                                            <option value={30}>30 {t('common.minutes', 'Min')}</option>
                                            <option value={60}>1 {t('common.hour', 'Hour')}</option>
                                            <option value={120}>2 {t('common.hours', 'Hours')}</option>
                                            <option value={240}>4 {t('common.hours', 'Hours')}</option>
                                            <option value={480}>8 {t('common.hours', 'Hours')}</option>
                                            <option value={1440}>1 {t('common.day', 'Day')}</option>
                                        </select>
                                        <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
                                    </div>
                                </div>

                                {/* Max Positions */}
                                <div className="space-y-2">
                                    <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                                        <Activity className="w-4 h-4 text-emerald-400" />
                                        {t('strategy.settings.maxPositions', 'Max Concurrent Positions')}
                                    </label>
                                    <input
                                        type="number"
                                        value={config.max_positions}
                                        onChange={(e) => setConfig({ ...config, max_positions: parseInt(e.target.value) || 1 })}
                                        className="w-full bg-[#0d1117] border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
                                        min="1"
                                        max="20"
                                    />
                                </div>
                            </div>
                            
                            <div className="space-y-2">
                                {/* Risk Per Trade */}
                                <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                                    <Shield className="w-4 h-4 text-amber-400" />
                                    {t('strategy.settings.riskPerTrade', 'Risk Per Trade %')}
                                </label>
                                <div className="relative">
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={config.risk_per_trade * 100}
                                        onChange={(e) => setConfig({ ...config, risk_per_trade: parseFloat(e.target.value) / 100 || 0.01 })}
                                        className="w-full bg-[#0d1117] border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all pr-10"
                                        min="0.1"
                                        max="10"
                                    />
                                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 font-medium">%</span>
                                </div>
                            </div>

                            {/* Agent Requirements */}
                            <div className="space-y-2">
                                <label className="flex items-center gap-2 text-sm font-medium text-slate-300">
                                    <MessageSquare className="w-4 h-4 text-violet-400" />
                                    {t('strategy.settings.agentRequirements', 'Agent Personality & Requirements')}
                                </label>
                                <textarea
                                    value={config.agent_requirements}
                                    onChange={(e) => setConfig({ ...config, agent_requirements: e.target.value })}
                                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all h-32 resize-none text-sm leading-relaxed"
                                    placeholder="e.g. Focus on trend following, only trade high volatility periods..."
                                />
                                <p className="text-xs text-slate-500">Provide specific instructions for your trading Agent. These will be added to its prompt.</p>
                            </div>

                            {error && (
                                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 flex items-center gap-3 text-red-400 text-sm">
                                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                    {error}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer */}
                {!loading && (
                    <div className="p-4 border-t border-slate-700/50 bg-[#131722]/50 flex items-center justify-end gap-3">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors"
                        >
                            {t('common.cancel')}
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving || success}
                            className={`flex items-center gap-2 px-6 py-2 rounded-xl text-sm font-bold transition-all shadow-lg ${
                                success 
                                    ? 'bg-green-500 text-white' 
                                    : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-500/20 active:scale-95'
                            } disabled:opacity-50`}
                        >
                            {saving ? (
                                <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
                            ) : success ? (
                                <><X className="w-4 h-4 rotate-45" /> Saved!</>
                            ) : (
                                <><Save className="w-4 h-4" /> {t('common.save')}</>
                            )}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
