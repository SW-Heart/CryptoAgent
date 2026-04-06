import React from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle, X, Loader2 } from 'lucide-react';

export default function ConfirmModal({ 
    isOpen, 
    onClose, 
    onConfirm, 
    title, 
    message, 
    confirmText = "确认", 
    cancelText = "取消",
    loading = false,
    type = "danger" // danger, warning
}) {
    if (!isOpen) return null;

    const accentColor = type === 'danger' ? 'rose' : 'amber';

    const modalContent = (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-hidden">
            <div 
                className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"
                onClick={loading ? undefined : onClose}
            />
            
            <div className="relative w-full max-w-sm bg-[#1c2230] border border-white/10 rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 fade-in duration-300">
                <div className={`h-1.5 w-full bg-${accentColor}-500/50`} />
                
                <div className="p-6">
                    <div className="flex items-start gap-4">
                        <div className={`p-3 rounded-2xl bg-${accentColor}-500/10 text-${accentColor}-500`}>
                            <AlertTriangle className="w-6 h-6" />
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-black text-white mb-2">{title}</h3>
                            <p className="text-slate-400 text-sm leading-relaxed font-medium">
                                {message}
                            </p>
                        </div>
                        <button 
                            onClick={onClose}
                            className="text-slate-500 hover:text-white transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="mt-8 flex gap-3">
                        <button
                            onClick={onClose}
                            disabled={loading}
                            className="flex-1 px-4 py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-bold transition-all disabled:opacity-50"
                        >
                            {cancelText}
                        </button>
                        <button
                            onClick={onConfirm}
                            disabled={loading}
                            className={`flex-1 px-4 py-3 rounded-2xl bg-${accentColor}-500 hover:bg-${accentColor}-600 text-white text-xs font-bold transition-all shadow-lg shadow-${accentColor}-500/20 active:scale-95 flex items-center justify-center gap-2 disabled:opacity-50`}
                        >
                            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                            {confirmText}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
