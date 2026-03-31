import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Trophy, Lock, Sparkles, TrendingUp,
    ArrowRight, Users, Calendar, Crown, UserCircle
} from 'lucide-react';
import { BASE_URL } from '../services/config';
import { useAuth } from '../context/AuthContext';

/**
 * BetaGate - 内测门户组件
 * 
 * 功能：
 * 1. 显示内测排行榜
 * 2. 邀请码输入验证
 * 3. 成功后进入 StrategyNexus
 */
export default function BetaGate({ userId, onAccessGranted }) {
    const { t, i18n } = useTranslation();
    const { user } = useAuth(); // 获取当前用户详情
    const [code, setCode] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [leaderboard, setLeaderboard] = useState([]);
    const [betaPeriod, setBetaPeriod] = useState({ start: '', end: '' });
    const [totalParticipants, setTotalParticipants] = useState(0);

    const isZh = i18n.language?.startsWith('zh');

    // 加载排行榜
    useEffect(() => {
        fetchLeaderboard();
    }, []);

    const fetchLeaderboard = async () => {
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/beta/leaderboard`);
            const data = await res.json();
            setLeaderboard(data.leaderboard || []);
            setBetaPeriod(data.beta_period || { start: '2026-04-01', end: '2026-05-31' });
            setTotalParticipants(data.total_participants || 0);
        } catch (e) {
            console.error('Failed to fetch leaderboard:', e);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!code.trim() || loading) return;

        setLoading(true);
        setError('');

        // 提取用户信息
        let username = '';
        let avatarUrl = '';

        if (user?.user_metadata) {
            username = user.user_metadata.full_name || user.user_metadata.name || user.user_metadata.username || user.email?.split('@')[0] || '';
            avatarUrl = user.user_metadata.avatar_url || '';
        }

        try {
            // 构建带参数的 URL
            const params = new URLSearchParams({
                user_id: userId,
                code: code.trim()
            });

            if (username) params.append('username', username);
            if (avatarUrl) params.append('avatar_url', avatarUrl);

            const res = await fetch(
                `${BASE_URL}/api/strategy/beta/verify?${params.toString()}`,
                { method: 'POST' }
            );
            const data = await res.json();

            if (data.success) {
                onAccessGranted();
            } else {
                setError(isZh ? data.error : data.error_en);
            }
        } catch (e) {
            setError(isZh ? '验证失败，请重试' : 'Verification failed, please try again');
        } finally {
            setLoading(false);
        }
    };

    // 获取排名颜色和图标
    const getRankStyle = (rank) => {
        switch (rank) {
            case 1:
                return {
                    bg: 'bg-gradient-to-r from-yellow-500/20 to-amber-500/20',
                    border: 'border-yellow-500/50',
                    text: 'text-yellow-400',
                    icon: '🥇',
                    glow: 'shadow-lg shadow-yellow-500/20'
                };
            case 2:
                return {
                    bg: 'bg-gradient-to-r from-slate-400/20 to-gray-400/20',
                    border: 'border-slate-400/50',
                    text: 'text-slate-300',
                    icon: '🥈',
                    glow: 'shadow-lg shadow-slate-400/20'
                };
            case 3:
                return {
                    bg: 'bg-gradient-to-r from-orange-600/20 to-amber-600/20',
                    border: 'border-orange-500/50',
                    text: 'text-orange-400',
                    icon: '🥉',
                    glow: 'shadow-lg shadow-orange-500/20'
                };
            default:
                return {
                    bg: 'bg-slate-800/30',
                    border: 'border-slate-700/30',
                    text: 'text-slate-400',
                    icon: rank.toString(),
                    glow: ''
                };
        }
    };

    return (
        <div className="flex-1 flex flex-col items-center justify-center bg-[#0d1117] p-8 overflow-auto">
            {/* 背景动画 */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl animate-pulse" />
                <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
            </div>

            <div className="relative z-10 max-w-2xl w-full space-y-6">
                {/* 标题 */}
                <div className="text-center space-y-2">
                    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 text-sm">
                        <Lock className="w-4 h-4" />
                        <span>{isZh ? '内测阶段' : 'Beta Phase'}</span>
                    </div>
                    <h1 className="text-3xl font-bold text-white flex items-center justify-center gap-3">
                        <Sparkles className="w-8 h-8 text-indigo-400" />
                        Strategy Nexus
                        <span className="text-indigo-400">Beta</span>
                    </h1>
                    <p className="text-slate-400">
                        {isZh
                            ? '交易功能目前处于内测阶段，请输入邀请码进入'
                            : 'Trading features are in beta. Enter your invite code to access.'
                        }
                    </p>
                </div>

                {/* 排行榜卡片 */}
                <div className="bg-[#131722] rounded-2xl border border-slate-700/50 overflow-hidden">
                    {/* 排行榜标题 */}
                    <div className="p-4 border-b border-slate-700/50 bg-gradient-to-r from-indigo-500/10 to-purple-500/10">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-xl bg-gradient-to-br from-yellow-500 to-amber-600">
                                    <Trophy className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h2 className="text-white font-semibold flex items-center gap-2">
                                        {isZh ? '内测精英榜' : 'Beta Leaderboard'}
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                                        </span>
                                    </h2>
                                    <p className="text-slate-400 text-xs">
                                        {isZh ? '实时胜率排名' : 'Real-time Win Rate Ranking'}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 text-slate-400 text-sm">
                                <Users className="w-4 h-4" />
                                <span>{totalParticipants} {isZh ? '人参与' : 'traders'}</span>
                            </div>
                        </div>
                    </div>

                    {/* 排行榜列表 */}
                    <div className="p-4 space-y-2 max-h-80 overflow-y-auto">
                        {leaderboard.length > 0 ? (
                            leaderboard.map((item) => {
                                const style = getRankStyle(item.rank);
                                return (
                                    <div
                                        key={item.rank}
                                        className={`flex items-center gap-4 p-3 rounded-xl border ${style.bg} ${style.border} ${style.glow} transition-all hover:scale-[1.02]`}
                                    >
                                        {/* 排名 */}
                                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold ${style.text}`}>
                                            {style.icon}
                                        </div>

                                        {/* 头像 */}
                                        <div className="w-10 h-10 rounded-full overflow-hidden bg-slate-700 flex-shrink-0 border border-slate-600">
                                            {item.avatar_url ? (
                                                <img src={item.avatar_url} alt={item.display_name} className="w-full h-full object-cover" />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-slate-400">
                                                    <UserCircle className="w-6 h-6" />
                                                </div>
                                            )}
                                        </div>

                                        {/* 用户信息 */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className="text-white font-medium truncate max-w-[120px]">{item.display_name}</span>
                                                {item.rank <= 3 && <Crown className={`w-4 h-4 ${style.text}`} />}
                                                {/* 当前用户标记 */}
                                                {item.display_name === (user?.user_metadata?.full_name || user?.user_metadata?.name || '') && (
                                                    <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded border border-indigo-500/30">YOU</span>
                                                )}
                                            </div>
                                            <div className="text-slate-500 text-xs">
                                                {item.total_trades} {isZh ? '笔交易' : 'trades'}
                                            </div>
                                        </div>

                                        {/* 胜率 */}
                                        <div className="text-right">
                                            <div className={`text-lg font-bold ${item.win_rate >= 60 ? 'text-green-400' : item.win_rate >= 40 ? 'text-yellow-400' : 'text-slate-400'}`}>
                                                {item.win_rate}%
                                            </div>
                                            <div className="text-xs text-slate-500">Win Rate</div>
                                        </div>
                                    </div>
                                );
                            })
                        ) : (
                            <div className="text-center py-12">
                                <Trophy className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                                <p className="text-slate-400">
                                    {isZh ? '暂无交易数据' : 'No trading data yet'}
                                </p>
                                <p className="text-slate-500 text-sm mt-1">
                                    {isZh ? '成为第一个上榜的交易者！' : 'Be the first to join the leaderboard!'}
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* 邀请码输入区域 */}
                <div className="bg-[#131722] rounded-2xl border border-slate-700/50 p-6 space-y-4">
                    {/* 内测信息 */}
                    <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-2 text-slate-400">
                            <Calendar className="w-4 h-4" />
                            <span>
                                {isZh ? '内测期间' : 'Beta Period'}: {betaPeriod.start} ~ {betaPeriod.end}
                            </span>
                        </div>
                    </div>

                    <div className="text-slate-400 text-sm">
                        {isZh
                            ? '📧 邀请码请联系开发者获取'
                            : '📧 Contact developer for invite code'
                        }
                    </div>

                    {/* 输入表单 */}
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="relative">
                            <input
                                type="text"
                                value={code}
                                onChange={(e) => setCode(e.target.value.toUpperCase())}
                                placeholder={isZh ? '请输入邀请码' : 'Enter invite code'}
                                maxLength={6}
                                className="w-full bg-slate-800/50 border border-slate-600 rounded-xl px-4 py-3 text-white text-center text-lg tracking-widest font-mono placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                            />
                        </div>

                        {error && (
                            <p className="text-red-400 text-sm text-center">{error}</p>
                        )}

                        <button
                            type="submit"
                            disabled={!code.trim() || loading}
                            className="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed group"
                        >
                            {loading ? (
                                <span className="animate-pulse">
                                    {isZh ? '验证中...' : 'Verifying...'}
                                </span>
                            ) : (
                                <>
                                    <span>{isZh ? '进入内测' : 'Enter Beta'}</span>
                                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                                </>
                            )}
                        </button>
                    </form>
                </div>

                {/* 底部提示 */}
                <div className="text-center text-slate-500 text-xs">
                    {isZh
                        ? '内测功能仅对受邀用户开放，功能可能存在变动'
                        : 'Beta features are invite-only and subject to change'
                    }
                </div>
            </div>
        </div>
    );
}
