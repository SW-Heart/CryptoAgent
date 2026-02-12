import React from 'react';
import { useTranslation } from 'react-i18next';

/**
 * SuggestedQuestion - 固定标语组件
 * 显示"计划你的交易、交易你的计划" / "Plan your trade, trade your plan"
 * 
 * 注：原动态推荐问题功能已暂停，等待后续新交互设计
 */
export default function SuggestedQuestion({ userId, onFillInput }) {
    const { i18n } = useTranslation();

    // 获取当前语言
    const isZh = i18n.language?.startsWith('zh');

    // 固定标语
    const slogan = isZh
        ? '计划你的交易、交易你的计划'
        : 'Plan your trade, trade your plan';

    return (
        <div className="flex items-center justify-center py-3">
            <div
                className="relative"
                style={{ maxWidth: '768px' }}
            >
                {/* 内容区域 - 纯展示，无点击交互 */}
                <div className="relative flex items-center gap-4 px-6 py-4">
                    {/* 标语文本 */}
                    <h2 className="text-2xl md:text-3xl lg:text-4xl font-bold bg-gradient-to-r from-orange-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                        {slogan}
                    </h2>
                </div>
            </div>
        </div>
    );
}
