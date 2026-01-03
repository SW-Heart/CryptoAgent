import React from 'react';

/**
 * Skeleton - 通用骨架屏加载组件
 * 用于数据加载时显示占位符效果，带流畅的脉冲动画
 */

// 基础骨架块
export function SkeletonBlock({ className = '', animate = true }) {
    return (
        <div
            className={`bg-slate-700/50 rounded ${animate ? 'animate-pulse' : ''} ${className}`}
        />
    );
}

// 行骨架（用于文本行）
export function SkeletonLine({ width = 'w-full', height = 'h-4', className = '' }) {
    return (
        <div className={`bg-slate-700/50 rounded animate-pulse ${width} ${height} ${className}`} />
    );
}

// 圆形骨架（用于头像、图标等）
export function SkeletonCircle({ size = 'w-4 h-4', className = '' }) {
    return (
        <div className={`bg-slate-700/50 rounded-full animate-pulse ${size} ${className}`} />
    );
}

// TrendingBar 骨架屏
export function TrendingBarSkeleton() {
    return (
        <div className="w-full bg-slate-900/50 border-b border-slate-800 h-10 overflow-hidden">
            <div className="flex items-center h-full w-full px-3 gap-6">
                {/* Trending icon placeholder */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                    <SkeletonCircle size="w-4 h-4" />
                    <SkeletonLine width="w-16" height="h-3" />
                </div>
                {/* Token placeholders */}
                {[...Array(6)].map((_, i) => (
                    <div key={i} className="flex items-center gap-2 flex-shrink-0">
                        <SkeletonCircle size="w-4 h-4" />
                        <SkeletonLine width="w-12" height="h-3" />
                        <SkeletonLine width="w-14" height="h-3" />
                        <SkeletonLine width="w-10" height="h-3" />
                    </div>
                ))}
            </div>
        </div>
    );
}

// KeyIndicators 骨架屏
export function KeyIndicatorsSkeleton() {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <SkeletonCircle size="w-4 h-4" />
                <SkeletonLine width="w-24" height="h-4" />
            </div>

            {/* Fear & Greed placeholder */}
            <div className="w-full flex items-center justify-between p-3 bg-slate-800/50 rounded-lg mb-3">
                <div className="flex items-center gap-2">
                    <SkeletonCircle size="w-4 h-4" />
                    <SkeletonLine width="w-20" height="h-3" />
                </div>
                <div className="flex items-center gap-2">
                    <SkeletonLine width="w-8" height="h-5" />
                    <SkeletonLine width="w-12" height="h-3" />
                </div>
            </div>

            {/* Indicators grid */}
            <div className="grid grid-cols-2 gap-2">
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="flex flex-col p-2.5 bg-slate-800/50 rounded-lg">
                        <SkeletonLine width="w-16" height="h-3" className="mb-1" />
                        <SkeletonLine width="w-12" height="h-4" />
                    </div>
                ))}
            </div>
        </div>
    );
}

// PopularTokens 骨架屏
export function PopularTokensSkeleton() {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <SkeletonCircle size="w-4 h-4" />
                    <SkeletonLine width="w-20" height="h-4" />
                </div>
                <div className="flex bg-slate-800/50 rounded-lg p-0.5 gap-1">
                    <SkeletonLine width="w-12" height="h-6" className="rounded-md" />
                    <SkeletonLine width="w-14" height="h-6" className="rounded-md" />
                </div>
            </div>

            {/* Table header */}
            <div className="grid grid-cols-4 px-2 pb-1 border-b border-slate-800/50 mb-1 flex-shrink-0">
                <SkeletonLine width="w-10" height="h-3" />
                <SkeletonLine width="w-10" height="h-3" className="ml-auto" />
                <SkeletonLine width="w-10" height="h-3" className="ml-auto" />
                <div />
            </div>

            {/* Token rows */}
            <div className="flex-1 flex flex-col justify-between">
                {[...Array(6)].map((_, i) => (
                    <div key={i} className="grid grid-cols-4 items-center px-2 py-1.5">
                        <SkeletonLine width="w-14" height="h-4" />
                        <SkeletonLine width="w-16" height="h-4" className="ml-auto" />
                        <SkeletonLine width="w-12" height="h-4" className="ml-auto" />
                        <SkeletonCircle size="w-4 h-4" className="ml-auto" />
                    </div>
                ))}
            </div>
        </div>
    );
}

// LatestNews 骨架屏
export function LatestNewsSkeleton() {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <SkeletonCircle size="w-4 h-4" />
                <SkeletonLine width="w-20" height="h-4" />
            </div>

            {/* News items */}
            <div className="space-y-1">
                {[...Array(6)].map((_, i) => (
                    <div key={i} className="flex items-start gap-2 px-2 py-1">
                        <SkeletonLine width="w-4" height="h-4" className="flex-shrink-0" />
                        <div className="flex-1">
                            <SkeletonLine width={`w-${['full', '5/6', '4/5', 'full', '5/6', '3/4'][i]}`} height="h-4" />
                            <SkeletonLine width="w-2/3" height="h-3" className="mt-1" />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// SuggestedQuestion 骨架屏
export function SuggestedQuestionSkeleton() {
    return (
        <div className="flex items-center justify-center py-3">
            <div className="relative" style={{ maxWidth: '600px' }}>
                <div className="relative flex items-center gap-4 px-6 py-4">
                    <SkeletonLine width="w-96" height="h-10" className="rounded-lg" />
                </div>
            </div>
        </div>
    );
}

// 完整首页骨架屏
export function DashboardSkeleton() {
    return (
        <div className="space-y-4">
            <TrendingBarSkeleton />
            <SuggestedQuestionSkeleton />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-4">
                <KeyIndicatorsSkeleton />
                <PopularTokensSkeleton />
                <LatestNewsSkeleton />
            </div>
        </div>
    );
}

export default {
    SkeletonBlock,
    SkeletonLine,
    SkeletonCircle,
    TrendingBarSkeleton,
    KeyIndicatorsSkeleton,
    PopularTokensSkeleton,
    LatestNewsSkeleton,
    SuggestedQuestionSkeleton,
    DashboardSkeleton
};
