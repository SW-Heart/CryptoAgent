import React, { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Search, X, Check, Filter } from 'lucide-react';

const EXCHANGE_LOGOS = {
    binance: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/binance.svg",
    okx: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Okx.svg",
    bybit: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/bybit.svg",
    bitget: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/Bitget.svg",
    gate: "https://crypto-ai.oss-cn-hangzhou.aliyuncs.com/cryptoquant/gate.io.svg"
};

const getBaseCoin = (sym, ex) => {
    if (!sym) return '';
    let base = sym.toUpperCase();
    if (ex === 'OKX') base = base.split('-')[0];
    else if (ex === 'Gate') base = base.split('_')[0];
    else base = base.replace(/USDT$/, '').replace(/USD$/, '');
    return base;
};

export default function SymbolSelectModal({
    isOpen,
    onClose,
    options = [],
    selected = [],
    onConfirm
}) {
    const [search, setSearch] = useState('');
    const [exchangeFilter, setExchangeFilter] = useState('ALL');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [localSelected, setLocalSelected] = useState([]);
    const dropdownRef = useRef(null);

    // Group options by base coin
    const groupedOptions = useMemo(() => {
        const map = new Map();
        options.forEach(opt => {
            if (!opt || !opt.symbol) return;
            const baseCoin = getBaseCoin(opt.symbol, opt.exchange);
            if (!baseCoin) return;

            const exKey = opt.exchange.toLowerCase();
            if (!map.has(baseCoin)) {
                map.set(baseCoin, {
                    baseCoin,
                    exchanges: new Set([exKey]),
                    desc: `${baseCoin} 永续合约`
                });
            } else {
                map.get(baseCoin).exchanges.add(exKey);
            }
        });

        return Array.from(map.values()).map(item => ({
            ...item,
            exchanges: Array.from(item.exchanges).sort()
        })).sort((a, b) => a.baseCoin.localeCompare(b.baseCoin));
    }, [options]);

    // Derive available exchanges for the dropdown
    const exchanges = ['ALL', ...new Set(options.map(o => o?.exchange).filter(Boolean))];

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    useEffect(() => {
        if (isOpen) {
            setSearch('');
            setExchangeFilter('ALL');
            
            // Map selected 'BTCUSDT' -> 'BTC' for local state
            const mappedSelected = selected.map(s => {
                let base = s.toUpperCase();
                if (base.endsWith('USDT')) base = base.replace('USDT', '');
                else if (base.endsWith('USD')) base = base.replace('USD', '');
                else if (base.includes('-')) base = base.split('-')[0];
                return base;
            }).filter(Boolean);
            
            setLocalSelected([...new Set(mappedSelected)]);
        }
    }, [isOpen, selected]);

    if (!isOpen) return null;

    const filteredOptions = groupedOptions.filter(opt => {
        if (exchangeFilter !== 'ALL' && !opt.exchanges.includes(exchangeFilter.toLowerCase())) {
            return false;
        }
        if (search.trim() !== '') {
            const query = search.toLowerCase();
            return opt.baseCoin.toLowerCase().includes(query) || opt.desc.toLowerCase().includes(query);
        }
        return true;
    });

    const toggleOption = (baseCoin) => {
        if (localSelected.includes(baseCoin)) {
            setLocalSelected(prev => prev.filter(x => x !== baseCoin));
        } else {
            setLocalSelected(prev => [...prev, baseCoin]);
        }
    };

    const handleConfirm = () => {
        onConfirm(localSelected);
        onClose();
    };

    const modalContent = (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-hidden">
            <div 
                className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"
                onClick={onClose}
            />
            
            <div className="relative w-full max-w-2xl bg-[#121619] border border-white/10 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh] animate-in zoom-in-95 fade-in duration-300">
                <div className="flex items-center justify-between p-6 border-b border-white/5">
                    <h3 className="text-lg font-bold text-white">选择交易标的</h3>
                    <button 
                        onClick={onClose}
                        className="text-slate-500 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 pb-2">
                    <div className="flex bg-black/40 border border-emerald-500/30 rounded-xl overflow-visible transition-colors relative z-20">
                        <div className="relative flex-1">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-500/70" />
                            <input
                                type="text"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="搜索标的名称，如 BTC..."
                                className="w-full bg-transparent pl-11 pr-4 py-3.5 text-white text-[15px] focus:outline-none font-mono placeholder-slate-500"
                                autoFocus
                            />
                        </div>
                        <div className="relative flex items-center bg-white/5 border-l border-white/5" ref={dropdownRef}>
                            <button 
                                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                                className="flex items-center justify-between px-4 py-3.5 bg-transparent text-sm text-slate-200 focus:outline-none font-bold cursor-pointer hover:bg-white/10 transition-colors min-w-[120px] rounded-r-xl"
                            >
                                <div className="flex items-center">
                                    <Filter className="w-4 h-4 text-emerald-500 mr-2" />
                                    <span>{exchangeFilter === 'ALL' ? '全来源' : exchangeFilter}</span>
                                </div>
                                <svg className={`w-4 h-4 ml-2 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180 text-emerald-400' : 'text-slate-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                            </button>
                            
                            {isDropdownOpen && (
                                <div className="absolute top-[calc(100%+8px)] right-0 w-48 bg-[#1a2024] border border-white/10 rounded-xl shadow-2xl shadow-black/80 overflow-hidden z-50 py-1.5 animate-in slide-in-from-top-2 duration-200">
                                    <div className="px-3 py-1.5 text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1">过滤特定支持的数据源</div>
                                    {exchanges.map(ex => (
                                        <div
                                            key={ex}
                                            onClick={() => {
                                                setExchangeFilter(ex);
                                                setIsDropdownOpen(false);
                                            }}
                                            className={`px-4 py-2.5 text-sm cursor-pointer font-bold transition-all flex items-center justify-between group ${
                                                exchangeFilter === ex 
                                                ? 'bg-emerald-500/15 text-emerald-400 border-l-2 border-emerald-400' 
                                                : 'text-slate-300 hover:bg-white/5 hover:text-white border-l-2 border-transparent'
                                            }`}
                                        >
                                            <div className="flex items-center gap-2">
                                                {ex !== 'ALL' && EXCHANGE_LOGOS[ex.toLowerCase()] ? (
                                                    <img src={EXCHANGE_LOGOS[ex.toLowerCase()]} alt="" className="w-3.5 h-3.5 object-contain" />
                                                ) : <span className="w-3.5" />}
                                                <span>{ex === 'ALL' ? '全部来源' : ex}</span>
                                            </div>
                                            {exchangeFilter === ex && <Check className="w-4 h-4" />}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                    
                    <div className="flex justify-between items-center mt-4 px-1">
                        <span className="text-[13px] font-bold text-slate-400">总计筛选: {filteredOptions.length} 个标的 | <span className="text-emerald-400 ml-1">已勾选: {localSelected.length}</span></span>
                        <button 
                            onClick={() => setLocalSelected([])}
                            className="flex items-center text-[13px] font-bold text-emerald-500/80 hover:text-emerald-400 transition-colors bg-emerald-500/10 px-3 py-1 rounded-lg border border-emerald-500/20"
                        >
                            <X className="w-3.5 h-3.5 mr-1" /> 清空重置
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar px-6 pb-6 mt-1 relative z-10">
                    {filteredOptions.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-slate-500 mt-8 bg-white/5 rounded-2xl border border-dashed border-white/10 mx-auto max-w-sm">
                            <Filter className="w-8 h-8 opacity-40 mb-3" />
                            <span className="text-[15px] font-medium text-slate-300">无匹配的标准化资产</span>
                            <span className="text-xs mt-2 opacity-50 px-8 text-center leading-relaxed">未能在当前筛选所选的体系内找到对应的同基底品种。请尝试切换数据源或检查代码前缀。</span>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {filteredOptions.map((opt, idx) => {
                                const isSelected = localSelected.includes(opt.baseCoin);
                                return (
                                    <div
                                        key={`${opt.baseCoin}-${idx}`}
                                        onClick={() => toggleOption(opt.baseCoin)}
                                        className={`flex items-center px-4 py-3.5 rounded-2xl cursor-pointer transition-all border group ${
                                            isSelected 
                                            ? 'bg-gradient-to-r from-emerald-500/10 to-transparent border-emerald-500/40' 
                                            : 'bg-[#161b1e] border-white/5 hover:bg-white/5 hover:border-white/10 shadow-sm'
                                        }`}
                                    >
                                        <div className="flex items-center gap-4 flex-1 overflow-hidden">
                                            {isSelected ? (
                                                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/30">
                                                    <Check className="w-3 h-3 text-white stroke-[3px]" />
                                                </div>
                                            ) : (
                                                <div className="w-5 h-5 rounded-full border border-slate-500/30 flex items-center justify-center shrink-0 group-hover:border-emerald-500/50 transition-colors bg-black/20 text-emerald-500" />
                                            )}
                                            
                                            <div className="flex flex-col shrink-0">
                                                <span className={`text-[16px] font-black font-mono tracking-tight ${isSelected ? 'text-emerald-400' : 'text-slate-200'}`}>
                                                    {opt.baseCoin}
                                                </span>
                                            </div>
                                        </div>
                                        
                                        <div className="flex items-center gap-1.5 ml-auto">
                                            {opt.exchanges.map(ex => (
                                                EXCHANGE_LOGOS[ex] ? (
                                                    <div 
                                                        key={ex} 
                                                        className={`w-[22px] h-[22px] rounded-full flex items-center justify-center transition-all duration-300 ${isSelected ? 'bg-white/10 opacity-100' : 'bg-black/40 opacity-100 group-hover:bg-white/10'}`}
                                                        title={ex.toUpperCase()}
                                                    >
                                                        <img 
                                                            src={EXCHANGE_LOGOS[ex]} 
                                                            alt={ex} 
                                                            className={`w-3.5 h-3.5 object-contain`}
                                                        />
                                                    </div>
                                                ) : null
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                <div className="p-6 border-t border-white/5 bg-[#0a0d0f] flex gap-4">
                    <button
                        onClick={onClose}
                        className="w-32 px-4 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 text-white text-sm font-bold transition-all border border-white/5 hover:border-white/10"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleConfirm}
                        disabled={localSelected.length === 0}
                        className="flex-1 px-4 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 active:bg-emerald-700 text-white text-[15px] font-black transition-all shadow-[0_0_15px_rgba(16,185,129,0.2)] hover:shadow-[0_0_25px_rgba(16,185,129,0.4)] hover:-translate-y-0.5 disabled:opacity-50 disabled:grayscale disabled:hover:translate-y-0 disabled:hover:shadow-none"
                    >
                        确认选择资产 ({localSelected.length}) 
                    </button>
                </div>
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}
