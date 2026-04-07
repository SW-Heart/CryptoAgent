import React from 'react';
import { CheckCircle2, AlertCircle } from 'lucide-react';

export default function Toast({ feedback }) {
    if (!feedback) return null;

    return (
        <div className={`fixed top-12 left-1/2 -translate-x-1/2 px-6 py-3 rounded-2xl shadow-2xl z-[200] flex items-center gap-3 animate-in fade-in slide-in-from-top-4 duration-300 border backdrop-blur-md ${
            feedback.type === 'success' 
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
        }`}>
            {feedback.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <span className="text-sm font-bold">{feedback.msg}</span>
        </div>
    );
}
