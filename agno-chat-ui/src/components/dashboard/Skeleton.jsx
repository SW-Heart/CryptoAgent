import React from 'react';

/**
 * Skeleton - 通用骨架屏加载组件
 * 用于数据加载时显示占位符效果，带流畅的脉冲动画
 * 使用固定样式确保首次渲染时尺寸正确
 */

// 基础骨架块 - 使用固定 Tailwind 类
const skeletonBase = "bg-slate-700/50 animate-pulse";

// KeyIndicators 骨架屏
export function KeyIndicatorsSkeleton() {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <div className={`${skeletonBase} rounded-full w-4 h-4 flex-shrink-0`} />
                <div className={`${skeletonBase} rounded w-24 h-4`} />
            </div>

            {/* Fear & Greed placeholder */}
            <div className="w-full flex items-center justify-between p-3 bg-slate-800/50 rounded-lg mb-3">
                <div className="flex items-center gap-2">
                    <div className={`${skeletonBase} rounded-full w-4 h-4 flex-shrink-0`} />
                    <div className={`${skeletonBase} rounded w-20 h-3`} />
                </div>
                <div className="flex items-center gap-2">
                    <div className={`${skeletonBase} rounded w-8 h-5`} />
                    <div className={`${skeletonBase} rounded w-12 h-3`} />
                </div>
            </div>

            {/* Indicators grid - 6 个指标匹配实际组件 */}
            <div className="grid grid-cols-2 gap-2">
                {[...Array(6)].map((_, i) => (
                    <div key={i} className="flex flex-col p-2.5 bg-slate-800/50 rounded-lg">
                        <div className={`${skeletonBase} rounded w-16 h-3 mb-1`} />
                        <div className={`${skeletonBase} rounded w-12 h-4`} />
                    </div>
                ))}
            </div>
        </div>
    );
}

// PopularTokens 骨架屏
export function PopularTokensSkeleton() {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden flex flex-col" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <div className={`${skeletonBase} rounded-full w-4 h-4 flex-shrink-0`} />
                    <div className={`${skeletonBase} rounded w-20 h-4`} />
                </div>
                <div className="flex bg-slate-800/50 rounded-lg p-0.5 gap-1">
                    <div className={`${skeletonBase} rounded-md w-12 h-6`} />
                    <div className={`${skeletonBase} rounded-md w-14 h-6`} />
                </div>
            </div>

            {/* Table header */}
            <div className="grid grid-cols-4 px-2 pb-1 border-b border-slate-800/50 mb-1 flex-shrink-0">
                <div className={`${skeletonBase} rounded w-10 h-3`} />
                <div className={`${skeletonBase} rounded w-10 h-3 ml-auto`} />
                <div className={`${skeletonBase} rounded w-10 h-3 ml-auto`} />
                <div />
            </div>

            {/* Token rows */}
            <div className="flex-1 flex flex-col justify-between">
                {[...Array(6)].map((_, i) => (
                    <div key={i} className="grid grid-cols-4 items-center px-2 py-1.5">
                        <div className={`${skeletonBase} rounded w-14 h-4`} />
                        <div className={`${skeletonBase} rounded w-16 h-4 ml-auto`} />
                        <div className={`${skeletonBase} rounded w-12 h-4 ml-auto`} />
                        <div className={`${skeletonBase} rounded-full w-4 h-4 ml-auto flex-shrink-0`} />
                    </div>
                ))}
            </div>
        </div>
    );
}

// LatestNews 骨架屏
export function LatestNewsSkeleton() {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
            {/* Header - 与实际组件匹配 */}
            <div className="flex items-center gap-2 mb-3">
                <div className={`${skeletonBase} rounded-full w-4 h-4 flex-shrink-0`} />
                <div className={`${skeletonBase} rounded w-20 h-4`} />
            </div>

            {/* News items - 使用 flex 布局匹配实际组件 */}
            <div className="flex flex-col justify-between h-[calc(100%-32px)] overflow-hidden">
                {[...Array(5)].map((_, i) => (
                    <div key={i} className="flex items-start gap-2 px-2 py-1 overflow-hidden">
                        <div className={`${skeletonBase} rounded w-4 h-4 flex-shrink-0 mt-0.5`} />
                        <div className="flex-1 overflow-hidden">
                            <div className={`${skeletonBase} rounded h-4`} style={{ width: '90%' }} />
                            <div className={`${skeletonBase} rounded h-3 mt-1`} style={{ width: '60%' }} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// TrendingBar 骨架屏
export function TrendingBarSkeleton() {
    return (
        <div className="w-full bg-slate-900/50 border-b border-slate-800 h-10 overflow-hidden" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
            <div className="flex items-center h-full w-full px-3 gap-6">
                {/* Trending icon placeholder */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                    <div className={`${skeletonBase} rounded-full w-4 h-4`} />
                    <div className={`${skeletonBase} rounded w-16 h-3`} />
                </div>
                {/* Token placeholders */}
                {[...Array(6)].map((_, i) => (
                    <div key={i} className="flex items-center gap-2 flex-shrink-0">
                        <div className={`${skeletonBase} rounded-full w-4 h-4`} />
                        <div className={`${skeletonBase} rounded w-12 h-3`} />
                        <div className={`${skeletonBase} rounded w-14 h-3`} />
                        <div className={`${skeletonBase} rounded w-10 h-3`} />
                    </div>
                ))}
            </div>
        </div>
    );
}

// SuggestedQuestion 骨架屏
export function SuggestedQuestionSkeleton() {
    return (
        <div className="flex items-center justify-center py-3 w-full" style={{ width: '100%', maxWidth: '100%', boxSizing: 'border-box' }}>
            <div className="relative w-full max-w-[600px]">
                {/* 模拟内容区域 - 匹配实际组件的 px-6 py-4 */}
                <div className="relative flex items-center gap-4 px-6 py-4">
                    {/* 模拟标题文本 */}
                    <div className={`${skeletonBase} rounded-lg w-full h-9`} />
                </div>
            </div>
        </div>
    );
}

// 完整首页骨架屏
export function DashboardSkeleton() {
    return (
        <div className="space-y-4 w-full">
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

// 导出用于单独使用的基础组件（已弃用，保留兼容性）
export function SkeletonBlock({ className = '' }) {
    return <div className={`${skeletonBase} rounded ${className}`} />;
}

export function SkeletonLine({ className = '' }) {
    return <div className={`${skeletonBase} rounded h-4 w-full ${className}`} />;
}

export function SkeletonCircle({ className = '' }) {
    return <div className={`${skeletonBase} rounded-full w-4 h-4 ${className}`} />;
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
