import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export default function Input({ label, type = 'text', value, onChange, placeholder, icon: Icon, error, helperText }) {
    const [showPassword, setShowPassword] = useState(false);
    const isPassword = type === 'password';
    
    return (
        <div className="flex flex-col gap-2 group">
            {label && (
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-[2px] ml-1 group-focus-within:text-indigo-400 transition-colors">
                    {label}
                </label>
            )}
            
            <div className="relative">
                {Icon && (
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">
                        <Icon className="w-4 h-4" />
                    </div>
                )}
                
                <input 
                    type={isPassword ? (showPassword ? 'text' : 'password') : type}
                    value={value || ''}
                    onChange={e => onChange?.(e.target.value)}
                    placeholder={placeholder}
                    className={`
                        w-full bg-[#0B0E11] border border-white/5 rounded-2xl px-5 py-4 text-sm text-slate-100 font-medium 
                        placeholder:text-slate-700 transition-all focus:border-indigo-500/50 focus:ring-8 focus:ring-indigo-500/5 
                        ${Icon ? 'pl-12' : ''} ${isPassword ? 'pr-12' : ''} ${error ? 'border-rose-500/50 ring-rose-500/5' : ''}
                    `}
                />
                
                {isPassword && (
                    <button 
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-lg hover:bg-white/5 text-slate-500 hover:text-indigo-400 transition-all"
                    >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                )}
            </div>
            
            {(error || helperText) && (
                <p className={`text-[10px] font-bold ml-1 tracking-widest uppercase ${error ? 'text-rose-500' : 'text-slate-600'}`}>
                    {error || helperText}
                </p>
            )}
        </div>
    );
}
