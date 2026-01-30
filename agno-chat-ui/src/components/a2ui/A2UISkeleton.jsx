/**
 * A2UI Skeleton - 骨架屏加载组件
 * 
 * 在 A2UI JSON 流式输出时显示，避免用户看到原始 JSON
 */

import React from 'react';

const A2UISkeleton = ({ type = 'card' }) => {
    return (
        <div className="animate-pulse w-full max-w-md rounded-xl border border-slate-700/50 bg-slate-800/30 p-4 mt-4">
            {/* Header: 价格 + Badge */}
            <div className="flex justify-between items-center mb-4">
                <div className="h-7 bg-slate-700/60 rounded w-28"></div>
                <div className="h-5 bg-emerald-500/20 rounded w-16"></div>
            </div>

            {/* Divider */}
            <div className="border-t border-slate-700/50 my-3"></div>

            {/* Stats Row */}
            <div className="flex justify-between">
                <div className="space-y-2">
                    <div className="h-3 bg-slate-700/40 rounded w-14"></div>
                    <div className="h-4 bg-slate-700/60 rounded w-24"></div>
                </div>
                <div className="space-y-2 text-right">
                    <div className="h-3 bg-slate-700/40 rounded w-20 ml-auto"></div>
                    <div className="h-4 bg-slate-700/60 rounded w-28"></div>
                </div>
            </div>

            {/* Divider */}
            <div className="border-t border-slate-700/50 my-3"></div>

            {/* Button */}
            <div className="h-9 bg-slate-700/40 rounded-lg w-full"></div>
        </div>
    );
};

export default A2UISkeleton;
