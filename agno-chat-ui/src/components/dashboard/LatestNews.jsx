import React from 'react';
import { Newspaper } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const DEFAULT_NEWS = [
    { title_en: "Bitcoin holds steady as market awaits Fed decision", title_zh: "比特币保持稳定，市场等待美联储决议" },
    { title_en: "Ethereum Layer 2 solutions see record TVL growth", title_zh: "以太坊二层解决方案TVL创历史新高" },
    { title_en: "Institutional crypto adoption accelerates in Asia", title_zh: "亚洲机构加密货币采用加速" },
    { title_en: "DeFi protocols show renewed growth momentum", title_zh: "DeFi协议增长势头强劲" },
    { title_en: "NFT market sees signs of recovery in Q4", title_zh: "NFT市场第四季度复苏迹象显现" },
    { title_en: "Regulatory clarity improves for crypto industry", title_zh: "加密货币行业监管逐渐明朗" }
];

export default function LatestNews({ news = [], onSelectNews }) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language?.startsWith('zh');

    const displayNews = news.length > 0 ? news.slice(0, 6) : DEFAULT_NEWS;

    // Get title based on current language
    const getTitle = (item) => {
        // Support both new format (title_en/title_zh) and old format (title)
        if (isZh) {
            return item.title_zh || item.title || item.title_en || '';
        }
        return item.title_en || item.title || '';
    };

    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <Newspaper className="w-4 h-4 text-blue-400" />
                {t('dashboard.latestNews', 'Latest News')}
            </h3>
            <div className="space-y-1">
                {displayNews.map((item, i) => {
                    const title = getTitle(item);
                    return (
                        <button
                            key={i}
                            onClick={() => onSelectNews(`Analysis news: '${item.title_en || item.title || title}'`)}
                            className="w-full flex items-start gap-2 px-2 py-1.5 hover:bg-slate-800 rounded-lg transition-colors text-left"
                        >
                            <span className="text-xs text-slate-500 mt-0.5 flex-shrink-0">{i + 1}.</span>
                            <span className="flex-1 text-sm text-slate-300">{title}</span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
