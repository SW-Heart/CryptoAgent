import React, { useState, useMemo } from 'react';
import Modal from '../common/Modal';
import { Search, Plus, TrendingUp, Check } from 'lucide-react';

const ALL_SYMBOLS = [
    { code: 'BTCUSDT', name: 'Bitcoin', exchange: 'BINANCE', type: 'crypto', icon: '₿' },
    { code: 'ETHUSDT', name: 'Ethereum', exchange: 'BINANCE', type: 'crypto', icon: 'Ξ' },
    { code: 'SOLUSDT', name: 'Solana', exchange: 'BINANCE', type: 'crypto', icon: 'S' },
    { code: 'BNBUSDT', name: 'Binance Coin', exchange: 'BINANCE', type: 'crypto', icon: 'B' },
    { code: 'XRPUSDT', name: 'Ripple', exchange: 'BINANCE', type: 'crypto', icon: '✕' },
    { code: 'ADAUSDT', name: 'Cardano', exchange: 'BINANCE', type: 'crypto', icon: '₳' },
    { code: 'DOGEUSDT', name: 'Dogecoin', exchange: 'BINANCE', type: 'crypto', icon: 'Ð' },
    { code: 'DOTUSDT', name: 'Polkadot', exchange: 'BINANCE', type: 'crypto', icon: 'P' },
    { code: 'AVAXUSDT', name: 'Avalanche', exchange: 'BINANCE', type: 'crypto', icon: '▲' },
    { code: 'LINKUSDT', name: 'Chainlink', exchange: 'BINANCE', type: 'crypto', icon: 'L' },
    { code: 'MATICUSDT', name: 'Polygon', exchange: 'BINANCE', type: 'crypto', icon: 'M' },
    { code: 'LTCUSDT', name: 'Litecoin', exchange: 'BINANCE', type: 'crypto', icon: 'Ł' },
    { code: 'APTUSDT', name: 'Aptos', exchange: 'BINANCE', type: 'crypto', icon: 'A' },
    { code: 'SUIUSDT', name: 'Sui', exchange: 'BINANCE', type: 'crypto', icon: 'S' },
    { code: 'OPUSDT', name: 'Optimism', exchange: 'BINANCE', type: 'crypto', icon: 'O' },
    { code: 'ARBUSDT', name: 'Arbitrum', exchange: 'BINANCE', type: 'crypto', icon: 'A' },
    { code: 'NEARUSDT', name: 'NEAR Protocol', exchange: 'BINANCE', type: 'crypto', icon: 'N' },
    { code: 'FTMUSDT', name: 'Fantom', exchange: 'BINANCE', type: 'crypto', icon: 'F' },
    { code: 'PEPEUSDT', name: 'Pepe', exchange: 'BINANCE', type: 'crypto', icon: 'P' },
    { code: 'SHIBUSDT', name: 'Shiba Inu', exchange: 'BINANCE', type: 'crypto', icon: 'S' },
    { code: 'WIFUSDT', name: 'dogwifhat', exchange: 'BINANCE', type: 'crypto', icon: 'W' },
    { code: 'ORDIUSDT', name: 'ORDI', exchange: 'BINANCE', type: 'crypto', icon: 'O' },
    { code: 'TIAUSDT', name: 'Celestia', exchange: 'BINANCE', type: 'crypto', icon: 'T' },
];

export default function AddSymbolModal({ isOpen, onClose, onAdd }) {
    const [searchQuery, setSearchQuery] = useState('');
    const [activeTab, setActiveTab] = useState('all');

    const handleAdd = (symbol) => {
        let newSymbol = symbol.trim().toUpperCase();
        if (!newSymbol) return;
        if (!newSymbol.includes(':')) {
            newSymbol = `BINANCE:${newSymbol}`;
        }
        if (!newSymbol.endsWith('USDT') && !newSymbol.includes('USDT')) {
            newSymbol = `${newSymbol}USDT`;
        }
        onAdd(newSymbol);
        // Do not close immediately, allow adding multiple
        setSearchQuery('');
    };

    const filteredSymbols = useMemo(() => {
        let result = ALL_SYMBOLS;
        if (searchQuery) {
            const upQuery = searchQuery.toUpperCase();
            result = result.filter(sym => 
                sym.code.includes(upQuery) || 
                sym.name.toUpperCase().includes(upQuery)
            );
        } else {
            // default view simply shows the top ones
            result = result.slice(0, 15);
        }
        return result;
    }, [searchQuery]);

    // If typing custom, let's inject a custom option at the top or bottom
    const showCustomAdd = searchQuery && !ALL_SYMBOLS.find(s => s.code === searchQuery.toUpperCase());

    return (
        <Modal 
            isOpen={isOpen} 
            onClose={() => { setSearchQuery(''); onClose(); }} 
            title="添加商品代码"
            maxWidth="max-w-2xl"
        >
            <div className="flex flex-col h-[60vh]">
                
                {/* Search Header */}
                <div className="flex-shrink-0 space-y-4 pb-4">
                    <div className="relative group">
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-emerald-400 transition-colors">
                            <Search className="w-5 h-5" />
                        </div>
                        <input 
                            autoFocus
                            type="text"
                            placeholder="商品代码"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && searchQuery.trim()) {
                                    handleAdd(searchQuery);
                                }
                            }}
                            className="w-full bg-[#0B0E11] border border-white/10 rounded-2xl pl-12 pr-4 py-4 text-sm text-slate-100 font-bold placeholder:text-slate-600 transition-all focus:border-emerald-500/50 focus:ring-4 focus:ring-emerald-500/10 focus:outline-none"
                        />
                    </div>
                    
                    {/* Mock Tabs */}
                    <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar pb-1">
                        {['全部', '股票', '加密货币', '外汇', '指数'].map(tab => (
                            <button 
                                key={tab}
                                onClick={() => setActiveTab(tab === '全部' ? 'all' : 'crypto')}
                                className={`px-4 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all ${
                                    (tab === '全部' && activeTab === 'all') || (tab === '加密货币' && activeTab === 'crypto')
                                        ? 'bg-slate-200 text-slate-900' 
                                        : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200'
                                }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>
                    
                    <div className="flex items-center justify-between text-[11px] font-bold text-slate-500 border-b border-white/5 pb-2 px-2">
                        <div className="flex-1">名称</div>
                        <div className="w-32 text-right pr-12">来源</div>
                    </div>
                </div>

                {/* List Body */}
                <div className="flex-1 overflow-y-auto custom-scrollbar -mx-4 px-4">
                    <div className="space-y-1">
                        
                        {showCustomAdd && (
                            <div className="flex items-center justify-between py-3 px-4 hover:bg-white/5 rounded-xl cursor-pointer group transition-colors" onClick={() => handleAdd(searchQuery)}>
                                <div className="flex items-center gap-4 flex-1">
                                    <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 font-black text-xs border border-emerald-500/20">
                                        ?
                                    </div>
                                    <div className="flex flex-col">
                                        <div className="text-sm font-bold text-white font-mono">{searchQuery.toUpperCase()}</div>
                                        <div className="text-[11px] text-slate-500 font-medium">添加自定义代码</div>
                                    </div>
                                </div>
                                <div className="text-[10px] text-slate-500 uppercase tracking-widest px-2">BINANCE</div>
                                <button className="p-2 rounded-lg text-emerald-500 hover:bg-emerald-500/20 transition-all">
                                    <Plus className="w-5 h-5" />
                                </button>
                            </div>
                        )}

                        {filteredSymbols.map(sym => (
                            <div 
                                key={sym.code}
                                onClick={() => handleAdd(sym.code)}
                                className="flex items-center justify-between py-3 px-4 hover:bg-[#1a1f2e] border border-transparent hover:border-white/5 rounded-xl cursor-pointer group transition-all"
                            >
                                <div className="flex items-center gap-4 flex-1 overflow-hidden">
                                    <div className="w-8 h-8 flex-shrink-0 rounded-full bg-slate-800 flex items-center justify-center text-slate-300 font-bold text-sm shadow-inner overflow-hidden border border-white/5">
                                        {/* Mocking the icon representation */}
                                        {sym.icon}
                                    </div>
                                    <div className="flex flex-col truncate">
                                        <div className="text-sm font-bold text-white font-mono truncate">{sym.code}</div>
                                        <div className="text-[11px] text-slate-500 font-medium truncate">{sym.name}</div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-4 flex-shrink-0 pl-4">
                                    <div className="text-[10px] text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                                        <span className="opacity-70 font-mono">crypto</span>
                                        <span className="font-bold text-slate-400">{sym.exchange}</span>
                                    </div>
                                    <button className="p-1.5 rounded-lg text-slate-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors">
                                        <Plus className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                        ))}

                        {filteredSymbols.length === 0 && !showCustomAdd && (
                            <div className="text-center py-10 text-slate-500 text-xs">
                                未找到相关商品代码
                            </div>
                        )}
                    </div>
                </div>

            </div>
        </Modal>
    );
}
