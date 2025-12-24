import React from 'react';
import { Newspaper } from 'lucide-react';

const DEFAULT_NEWS = [
    { title: "Bitcoin holds steady as market awaits Fed decision" },
    { title: "Ethereum Layer 2 solutions see record TVL growth" },
    { title: "Institutional crypto adoption accelerates in Asia" },
    { title: "DeFi protocols show renewed growth momentum" },
    { title: "NFT market sees signs of recovery in Q4" },
    { title: "Regulatory clarity improves for crypto industry" }
];

export default function LatestNews({ news = [], onSelectNews }) {
    const displayNews = news.length > 0 ? news.slice(0, 6) : DEFAULT_NEWS;

    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <Newspaper className="w-4 h-4 text-blue-400" />
                Latest News
            </h3>
            <div className="space-y-1">
                {displayNews.map((item, i) => (
                    <button
                        key={i}
                        onClick={() => onSelectNews(`Analysis news: '${item.title}'`)}
                        className="w-full flex items-start gap-2 px-2 py-1.5 hover:bg-slate-800 rounded-lg transition-colors text-left"
                    >
                        <span className="text-xs text-slate-500 mt-0.5 flex-shrink-0">{i + 1}.</span>
                        <span className="flex-1 text-sm text-slate-300">{item.title}</span>
                    </button>
                ))}
            </div>
        </div>
    );
}
