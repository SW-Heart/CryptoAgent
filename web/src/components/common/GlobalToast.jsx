import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

// ============= Global Toast Event Bus =============
const listeners = new Set();

/**
 * 全局 Toast 触发函数 — 任何组件（包括 Modal）都可以直接调用
 * 
 * @param {string} msg - 提示内容
 * @param {'success' | 'error' | 'info'} type - 提示类型
 * @param {number} duration - 显示时长(ms)，默认 4000
 * 
 * 用法：
 *   import { showToast } from '../common/GlobalToast';
 *   showToast("操作成功", "success");
 *   showToast("API Key 无效", "error", 6000);
 */
export function showToast(msg, type = 'info', duration = 4000) {
    const id = Date.now() + Math.random();
    const toast = { id, msg, type, duration };
    listeners.forEach(fn => fn(toast));
}

// ============= Global Toast Container =============
export default function GlobalToastContainer() {
    const [toasts, setToasts] = useState([]);

    useEffect(() => {
        const handler = (toast) => {
            setToasts(prev => [...prev, toast]);
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== toast.id));
            }, toast.duration);
        };
        listeners.add(handler);
        return () => listeners.delete(handler);
    }, []);

    const dismiss = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    if (toasts.length === 0) return null;

    const styleMap = {
        success: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
        error: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
        info: 'bg-sky-500/10 border-sky-500/20 text-sky-400',
    };

    const iconMap = {
        success: <CheckCircle2 className="w-5 h-5 flex-shrink-0" />,
        error: <AlertCircle className="w-5 h-5 flex-shrink-0" />,
        info: <Info className="w-5 h-5 flex-shrink-0" />,
    };

    return createPortal(
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[99999] flex flex-col items-center gap-2 pointer-events-none">
            {toasts.map(t => (
                <div
                    key={t.id}
                    className={`pointer-events-auto flex items-center gap-3 px-6 py-3.5 rounded-2xl shadow-2xl border backdrop-blur-xl animate-in fade-in slide-in-from-top-4 duration-300 max-w-md ${styleMap[t.type] || styleMap.info}`}
                >
                    {iconMap[t.type] || iconMap.info}
                    <span className="text-sm font-bold">{t.msg}</span>
                    <button onClick={() => dismiss(t.id)} className="ml-2 opacity-50 hover:opacity-100 transition-opacity">
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>
            ))}
        </div>,
        document.body
    );
}
