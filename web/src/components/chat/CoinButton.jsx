import React, { useState, useEffect } from 'react';
import { BarChart2 } from 'lucide-react';
import { COIN_DATA } from '../../utils/coinPatterns';
import { formatPrice } from '../../utils/formatters';

const CoinButton = React.memo(({ coin, onClick }) => {
    const data = COIN_DATA[coin];
    const [priceData, setPriceData] = useState(null);

    useEffect(() => {
        if (!data) return;

        const symbol = data.symbol.split(':')[1];
        const fetchPrice = async () => {
            try {
                const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbol=${symbol}`);
                if (res.ok) {
                    const json = await res.json();
                    setPriceData({
                        price: parseFloat(json.lastPrice),
                        change: parseFloat(json.priceChangePercent),
                    });
                }
            } catch (e) {
                console.error('Price fetch error:', e);
            }
        };

        fetchPrice();
        const interval = setInterval(fetchPrice, 30000);
        return () => clearInterval(interval);
    }, [data]);

    if (!data) return null;

    const isPositive = priceData?.change >= 0;

    return (
        <button
            onClick={() => onClick(coin)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[#131722] hover:bg-slate-700 transition-all duration-200 group"
        >
            <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: data.color }}
            />
            <div className="flex flex-col items-start">
                <span className="text-sm font-semibold text-white group-hover:text-slate-100">
                    {coin}
                </span>
                {priceData && (
                    <div className="flex items-center gap-1">
                        <span className="text-xs text-slate-400">{formatPrice(priceData.price)}</span>
                        <span className={`text-xs font-medium ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                            {isPositive ? '↑' : '↓'}{Math.abs(priceData.change).toFixed(1)}%
                        </span>
                    </div>
                )}
            </div>
            <BarChart2 className="w-4 h-4 text-slate-400 group-hover:text-white ml-1" />
        </button>
    );
});

export default CoinButton;
