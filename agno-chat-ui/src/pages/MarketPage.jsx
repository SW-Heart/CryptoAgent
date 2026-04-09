import React, { useState, useEffect } from 'react';
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets';
import { Search, Plus, Trash2, LineChart, Star, X } from 'lucide-react';
import Button from '../components/common/Button';

// 默认自选列表
const DEFAULT_WATCHLIST = ['BINANCE:BTCUSDT', 'BINANCE:ETHUSDT', 'BINANCE:SOLUSDT'];

// 静态常量配置，防止每次渲染时内存引用变化导致图表重绘
const COPYRIGHT_STYLES = { parent: { display: "none" } };
const DEFAULT_STUDIES = [
    "Volume@tv-basicstudies",
    "MACD@tv-basicstudies"
];

export default function MarketPage() {
    const [watchlist, setWatchlist] = useState([]);
    const [currentSymbol, setCurrentSymbol] = useState('BINANCE:BTCUSDT');
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);

    // 页面加载时从 localStorage 读取用户的自选配置
    useEffect(() => {
        const saved = localStorage.getItem('cryptoquant_watchlist');
        if (saved) {
            try {
                setWatchlist(JSON.parse(saved));
            } catch (e) {
                setWatchlist(DEFAULT_WATCHLIST);
            }
        } else {
            setWatchlist(DEFAULT_WATCHLIST);
            localStorage.setItem('cryptoquant_watchlist', JSON.stringify(DEFAULT_WATCHLIST));
        }
    }, []);

    // 搜索框回车/添加逻辑
    const handleAddSymbol = (e) => {
        if (e.key === 'Enter' || e.type === 'click') {
            if (!searchQuery.trim()) return;
            // 简单处理：如果没有带交易所前缀，默认加 BINANCE:
            let newSymbol = searchQuery.trim().toUpperCase();
            if (!newSymbol.includes(':')) {
                newSymbol = `BINANCE:${newSymbol}`;
            }
            if (!newSymbol.endsWith('USDT') && !newSymbol.includes('USDT')) {
                newSymbol = `${newSymbol}USDT`;
            }

            if (!watchlist.includes(newSymbol)) {
                const updated = [...watchlist, newSymbol];
                setWatchlist(updated);
                localStorage.setItem('cryptoquant_watchlist', JSON.stringify(updated));
            }
            setCurrentSymbol(newSymbol);
            setSearchQuery('');
            setIsSearching(false);
        }
    };

    const handleRemoveSymbol = (e, symbolToRemove) => {
        e.stopPropagation();
        const updated = watchlist.filter(s => s !== symbolToRemove);
        setWatchlist(updated);
        localStorage.setItem('cryptoquant_watchlist', JSON.stringify(updated));
        if (currentSymbol === symbolToRemove && updated.length > 0) {
            setCurrentSymbol(updated[0]);
        }
    };

    return (
        <div className="h-full w-full flex flex-col gap-4 min-h-0">
            
            {/* Top Row: Watchlist Header (Glassmorphism style to match the app) */}
            <header className="bg-[#0e1215]/40 border border-white/5 rounded-3xl p-4 flex items-center justify-between shadow-2xl backdrop-blur-md flex-shrink-0 animate-in fade-in duration-700 z-50 relative">
                <div className="flex items-center gap-6 flex-1 overflow-hidden">
                    <div className="flex items-center gap-3 pr-6 border-r border-white/5 flex-shrink-0">
                        <div className="w-10 h-10 rounded-2xl flex items-center justify-center border bg-emerald-500/10 border-emerald-500/20 transition-all">
                            <LineChart className="w-5 h-5 text-emerald-400" />
                        </div>
                        <div>
                            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none mb-1">看盘面板</div>
                            <div className="text-sm font-bold text-white truncate max-w-[150px]">{currentSymbol.split(':')[1] || currentSymbol}</div>
                        </div>
                    </div>

                    {/* Watchlist Items */}
                    <div className="flex items-center gap-2 overflow-x-auto flex-1 custom-scrollbar min-w-0 pr-4">
                        {watchlist.map((symbol) => {
                            const isActive = symbol === currentSymbol;
                            const displayParams = symbol.split(':');
                            const displayName = displayParams[1] || symbol;

                            return (
                                <div 
                                    key={symbol}
                                    onClick={() => setCurrentSymbol(symbol)}
                                    className={`group flex items-center gap-2 px-4 py-2 rounded-xl border transition-all cursor-pointer flex-shrink-0
                                        ${isActive 
                                            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                                            : 'bg-[#0e1215]/60 border-white/5 text-slate-400 hover:text-slate-200 hover:border-white/10'
                                        }`}
                                >
                                    <Star className={`w-3.5 h-3.5 ${isActive ? 'fill-emerald-400' : ''}`} />
                                    <span className="text-xs font-bold font-mono">{displayName}</span>
                                    <button 
                                        onClick={(e) => handleRemoveSymbol(e, symbol)}
                                        className={`p-1 rounded-md transition-colors ${isActive ? 'text-emerald-400/50 hover:text-emerald-400 hover:bg-emerald-500/20' : 'text-slate-500 hover:text-rose-400 hover:bg-rose-500/10'} opacity-0 group-hover:opacity-100`}
                                    >
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Add New Symbol Action */}
                <div className="flex items-center gap-3 pl-6 border-l border-white/5 flex-shrink-0">
                    {isSearching ? (
                        <div className="flex items-center gap-2 bg-[#0e1215]/80 border border-emerald-500/30 rounded-xl px-3 py-1.5 animate-in fade-in slide-in-from-right-4 duration-200">
                            <Search className="w-4 h-4 text-emerald-400" />
                            <input 
                                autoFocus
                                type="text"
                                placeholder="输入代码 (如 BTCUSDT)..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleAddSymbol}
                                className="bg-transparent border-none text-xs font-bold text-white focus:outline-none w-40 placeholder-slate-600 font-mono"
                            />
                            <button onClick={() => setIsSearching(false)} className="text-slate-500 hover:text-white p-1"><X className="w-4 h-4" /></button>
                        </div>
                    ) : (
                        <Button 
                            variant="primary" 
                            size="sm" 
                            icon={Plus} 
                            onClick={() => setIsSearching(true)} 
                            className="h-9 px-5 font-black uppercase text-[10px] tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors shadow-none"
                        >
                            添加自选
                        </Button>
                    )}
                </div>
            </header>

            {/* Main Workspace (TradingView Widget) */}
            <div className="flex-1 bg-[#0B0E11] border border-white/5 rounded-lg overflow-hidden shadow-xl animate-in fade-in duration-1000 relative z-10 w-full h-full min-h-[500px]">
                {/* AdvancedRealTimeChart automatically expands to 100% width and height of its container */}
                <AdvancedRealTimeChart 
                    autosize={true}
                    theme="dark"
                    symbol={currentSymbol}
                    interval="1D"
                    timezone="Asia/Shanghai"
                    style="1"
                    locale="zh_CN"
                    enable_publishing={false}
                    backgroundColor="#0B0E11"
                    gridColor="#1f2937"
                    hide_top_toolbar={false}
                    hide_legend={false}
                    save_image={false}
                    allow_symbol_change={true}
                    withdateranges={false}
                    copyrightStyles={COPYRIGHT_STYLES}
                    studies={DEFAULT_STUDIES}
                />
            </div>

        </div>
    );
}
