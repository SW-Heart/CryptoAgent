import React from 'react';
import { TrendingUp, Search } from 'lucide-react';

export default function PopularTokens({ tokens = [], onAnalyzeToken }) {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                Popular Tokens
            </h3>
            <div className="space-y-1">
                <div className="grid grid-cols-4 text-xs text-slate-500 px-2 pb-1">
                    <span>Name</span>
                    <span className="text-right">Price</span>
                    <span className="text-right">24h(%)</span>
                    <span className="text-right"></span>
                </div>
                {tokens.slice(0, 6).map((token, i) => (
                    <div key={i} className="grid grid-cols-4 items-center px-2 py-1.5 hover:bg-slate-800 rounded text-sm">
                        <span className="text-white font-medium">{token.name}</span>
                        <span className="text-right text-slate-300 text-xs">
                            ${token.price < 1 ? token.price.toFixed(4) : token.price < 1000 ? token.price.toFixed(2) : token.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </span>
                        <span className={`text-right text-xs ${token.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {token.change_24h >= 0 ? '+' : ''}{token.change_24h?.toFixed(2)}%
                        </span>
                        <button
                            onClick={() => onAnalyzeToken(`Analyze token: ${token.name}`)}
                            className="text-right text-indigo-400 hover:text-indigo-300"
                        >
                            <Search className="w-3.5 h-3.5 ml-auto" />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
