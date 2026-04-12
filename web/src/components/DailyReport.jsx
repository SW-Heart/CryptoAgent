import { useTranslation } from 'react-i18next';
import { Newspaper, Wrench } from 'lucide-react';

export default function DailyReport() {
    const { i18n } = useTranslation();
    const isZh = i18n.language?.startsWith('zh');

    return (
        <div className="flex flex-col h-full w-full flex-1 bg-black">
            {/* Header */}
            <header className="h-16 flex items-center justify-between px-6 border-b border-slate-800 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <Newspaper className="w-5 h-5 text-indigo-400" />
                    <h1 className="text-lg font-semibold text-white">
                        {isZh ? '加密日报' : 'Daily Report'}
                    </h1>
                </div>
            </header>

            {/* Main Content - Upgrade Notice */}
            <div className="flex-1 flex items-center justify-center p-6">
                <div className="text-center max-w-md">
                    {/* Icon */}
                    <div className="mb-6 inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30">
                        <Wrench className="w-10 h-10 text-indigo-400" />
                    </div>

                    {/* Title */}
                    <h2 className="text-2xl font-bold text-white mb-3">
                        {isZh ? '功能升级中' : 'Feature Upgrading'}
                    </h2>

                    {/* Description */}
                    <p className="text-slate-400 text-lg mb-6">
                        {isZh ? '敬请期待' : 'Coming Soon'}
                    </p>

                    {/* Decorative line */}
                    <div className="flex items-center justify-center gap-2">
                        <div className="w-12 h-0.5 bg-gradient-to-r from-transparent to-indigo-500/50"></div>
                        <div className="w-2 h-2 rounded-full bg-indigo-500/50"></div>
                        <div className="w-12 h-0.5 bg-gradient-to-l from-transparent to-indigo-500/50"></div>
                    </div>
                </div>
            </div>
        </div>
    );
}
