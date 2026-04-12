import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown } from 'lucide-react';

function OptionLogo({ src, fallback }) {
    const [err, setErr] = useState(false);
    if (!src || err) {
        return fallback ? (
            <div className="w-4 h-4 rounded-full bg-white/10 flex items-center justify-center text-[8px] font-black text-slate-400">
                {fallback.charAt(0).toUpperCase()}
            </div>
        ) : null;
    }
    return <img src={src} alt="" className="w-4 h-4 rounded-sm object-contain" onError={() => setErr(true)} />;
}

export function CustomDropdown({ label, options, value, onChange, disabled, icon: Icon }) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);
    const selectedOption = options.find(o => String(o.id) === String(value));

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false);
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="relative" ref={dropdownRef}>
            <div className="flex items-center justify-between mb-1.5 px-0.5">
                <label className="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-1.5">
                    {Icon && <Icon className="w-3 h-3 text-slate-500" />} {label}
                </label>
            </div>
            <button
                type="button"
                disabled={disabled}
                onClick={() => setIsOpen(!isOpen)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2.5 bg-[#0e1215]/60 border border-white/5 rounded-xl text-xs font-bold hover:border-white/10 transition-all focus:outline-none ${disabled ? 'opacity-40 cursor-not-allowed' : 'text-slate-200'}`}
            >
                <span className="flex items-center gap-2 truncate">
                    {selectedOption?.logo && <OptionLogo src={selectedOption.logo} fallback={selectedOption.name} />}
                    {selectedOption ? selectedOption.name : '未选择'}
                </span>
                <ChevronDown className={`w-3.5 h-3.5 text-slate-500 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && !disabled && (
                <div className="absolute top-[calc(100%+4px)] left-0 right-0 z-[100] bg-[#111516] border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200 border-t-emerald-500/50">
                    <div className="max-h-60 overflow-y-auto custom-scrollbar">
                        {options.map(opt => (
                            <button
                                key={opt.id}
                                onClick={() => { onChange(opt.id); setIsOpen(false); }}
                                className={`w-full text-left px-4 py-3 text-[11px] font-bold transition-colors flex items-center gap-2.5 ${String(opt.id) === String(value) ? 'bg-emerald-500 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
                            >
                                {opt.logo && <OptionLogo src={opt.logo} fallback={opt.name} />}
                                {opt.name}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export function MiniDropdown({ options, value, onChange }) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);
    const selectedOption = options.find(o => String(o.key) === String(value)) || options[0];

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false);
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="relative text-[10px] group" ref={dropdownRef}>
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className={`flex items-center gap-1.5 px-2 py-1 transition-all rounded-[6px] border font-bold focus:outline-none ${isOpen ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-transparent border-transparent text-slate-500 hover:bg-white/5 hover:text-slate-300'}`}
            >
                {selectedOption.label}
                <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : 'opacity-50'}`} />
            </button>
            {isOpen && (
                <div className="absolute top-[calc(100%+4px)] right-0 w-[84px] bg-[#0e1215] border border-white/10 rounded-lg shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-1 duration-200 z-[100] py-1">
                    {options.map(opt => (
                        <button
                            key={opt.key}
                            onClick={() => { onChange(opt.key); setIsOpen(false); }}
                            className={`w-full text-left px-3 py-1.5 text-[9px] font-bold transition-colors ${String(opt.key) === String(value) ? 'bg-emerald-500/10 text-emerald-400' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
