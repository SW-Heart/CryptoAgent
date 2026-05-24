import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Bell, X, Check, Trash2, AlertTriangle, Info, AlertCircle } from 'lucide-react';
import { getJson, putJson } from '../../services/apiClient';

export default function NotificationModal({ isOpen, onClose, userId, onReadStatusChanged }) {
    const [notifications, setNotifications] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (isOpen && userId) {
            fetchNotifications();
        }
    }, [isOpen, userId]);

    const fetchNotifications = async () => {
        setLoading(true);
        try {
            const res = await getJson(`/api/workspace/notifications?user_id=${userId}&limit=50`);
            setNotifications(res.notifications || []);
        } catch (error) {
            console.error('Failed to fetch notifications:', error);
        } finally {
            setLoading(false);
        }
    };

    const markAsRead = async (notifId) => {
        try {
            await putJson(`/api/workspace/notifications/${notifId}/read?user_id=${userId}`);
            setNotifications(prev => prev.map(n => n.id === notifId ? { ...n, is_read: true } : n));
            if (onReadStatusChanged) onReadStatusChanged();
        } catch (error) {
            console.error('Failed to mark read:', error);
        }
    };

    const markAllAsRead = async () => {
        try {
            await putJson(`/api/workspace/notifications/read?user_id=${userId}`);
            setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
            if (onReadStatusChanged) onReadStatusChanged();
        } catch (error) {
            console.error('Failed to mark all read:', error);
        }
    };

    if (!isOpen) return null;

    const unreadCount = notifications.filter(n => !n.is_read).length;

    const modalContent = (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-hidden">
            <div 
                className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"
                onClick={onClose}
            />
            
            <div className="relative w-full max-w-2xl max-h-[80vh] flex flex-col bg-[#121619] border border-white/10 rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 fade-in duration-300">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/5 bg-[#0a0d0f]">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400">
                            <Bell className="w-5 h-5" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                                系统消息
                                {unreadCount > 0 && (
                                    <span className="bg-rose-500 text-white text-[10px] font-black px-2 py-0.5 rounded-full">
                                        {unreadCount} 未读
                                    </span>
                                )}
                            </h2>
                            <p className="text-xs text-slate-400 mt-1">系统运行的重要通知和错误警报</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {unreadCount > 0 && (
                            <button
                                onClick={markAllAsRead}
                                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs font-bold transition-colors flex items-center gap-1"
                            >
                                <Check className="w-3 h-3" />
                                全部标为已读
                            </button>
                        )}
                        <button 
                            onClick={onClose}
                            className="p-2 rounded-xl text-slate-500 hover:text-white hover:bg-white/5 transition-all"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-6 bg-[#0a0d0f]/50">
                    {loading ? (
                        <div className="flex items-center justify-center py-10">
                            <div className="text-slate-500 text-sm animate-pulse">加载中...</div>
                        </div>
                    ) : notifications.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                            <Bell className="w-12 h-12 mb-4 opacity-20" />
                            <p className="text-sm font-medium">暂无系统消息</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {notifications.map(notif => {
                                const isError = notif.type === 'error';
                                const isWarning = notif.type === 'warning';
                                const Icon = isError ? AlertCircle : (isWarning ? AlertTriangle : Info);
                                const colorClass = isError ? 'rose' : (isWarning ? 'amber' : 'emerald');

                                return (
                                    <div 
                                        key={notif.id}
                                        className={`group p-4 rounded-2xl border transition-all ${notif.is_read ? 'bg-[#0e1215] border-white/5 opacity-70' : `bg-[#161a1e] border-${colorClass}-500/30 shadow-lg shadow-black/20`}`}
                                    >
                                        <div className="flex items-start gap-4">
                                            <div className={`mt-0.5 p-2 rounded-lg ${notif.is_read ? 'bg-slate-800 text-slate-500' : `bg-${colorClass}-500/10 text-${colorClass}-400`}`}>
                                                <Icon className="w-4 h-4" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between mb-1.5">
                                                    <h4 className={`text-sm font-bold truncate ${notif.is_read ? 'text-slate-300' : 'text-white'}`}>
                                                        {notif.title}
                                                    </h4>
                                                    <span className="text-[10px] text-slate-500 font-mono whitespace-nowrap ml-4">
                                                        {new Date(notif.created_at).toLocaleString()}
                                                    </span>
                                                </div>
                                                <div className={`text-xs whitespace-pre-wrap leading-relaxed ${notif.is_read ? 'text-slate-500' : 'text-slate-300'}`}>
                                                    {notif.content}
                                                </div>
                                            </div>
                                        </div>
                                        {!notif.is_read && (
                                            <div className="mt-3 ml-12 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                                                <button
                                                    onClick={() => markAsRead(notif.id)}
                                                    className="text-[10px] font-bold text-slate-400 hover:text-white px-2 py-1 rounded bg-white/5 hover:bg-white/10 transition-colors"
                                                >
                                                    标为已读
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
