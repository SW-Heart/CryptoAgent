import React, { useState, useEffect } from 'react';
import { AdvancedRealTimeChart } from 'react-ts-tradingview-widgets';
import { Search, Plus, Trash2, LineChart, Star, X, Loader2 } from 'lucide-react';
import Button from '../components/common/Button';
import AddSymbolModal from '../components/AddSymbolModal';

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
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);

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

    const handleAddSymbol = (newSymbol) => {
        if (!watchlist.includes(newSymbol)) {
            const updated = [...watchlist, newSymbol];
            setWatchlist(updated);
            localStorage.setItem('cryptoquant_watchlist', JSON.stringify(updated));
        }
        setCurrentSymbol(newSymbol);
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
        <div className="h-full w-full flex flex-col min-h-0">
            {/* Main Workspace (TradingView Widget) - Truly Full Screen */}
            <div className="flex-1 bg-[#0B0E11] animate-in fade-in duration-1000 relative z-10 w-full h-full min-h-[500px]">
                
                {/* 底层转圈加载状态 */}
                <div className="absolute inset-0 flex flex-col items-center justify-center z-0 pointer-events-none">
                    <Loader2 className="w-10 h-10 text-emerald-500 animate-spin mb-4 opacity-80" />
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-widest animate-pulse">Initializing TradingView...</div>
                </div>

                {/* AdvancedRealTimeChart automatically expands to 100% */}
                <div className="absolute inset-0 z-10">
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
                        withdateranges={true}
                        details={true}
                        hotlist={true}
                        calendar={false}
                        watchlist={watchlist}
                        copyrightStyles={COPYRIGHT_STYLES}
                        studies={DEFAULT_STUDIES}
                    />
                </div>
            </div>
        </div>
    );
}
