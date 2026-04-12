import React, { useState, useEffect } from 'react';

/**
 * CryptoLoader - 加密风格简约加载动画
 * 
 * 特点：
 * - 快速、简洁、充满加密精神
 * - 区块链哈希滚动效果
 * - 霓虹灯光效
 */
export default function CryptoLoader({ isReady = false, onComplete }) {
    const [opacity, setOpacity] = useState(1);
    const [hash, setHash] = useState('');
    const [blockNum, setBlockNum] = useState(19847231);

    // 生成随机哈希
    const generateHash = () => {
        const chars = '0123456789abcdef';
        let h = '0x';
        for (let i = 0; i < 8; i++) {
            h += chars[Math.floor(Math.random() * 16)];
        }
        return h + '...';
    };

    // 哈希滚动效果
    useEffect(() => {
        const hashInterval = setInterval(() => {
            setHash(generateHash());
            setBlockNum(prev => prev + Math.floor(Math.random() * 3));
        }, 100);

        return () => clearInterval(hashInterval);
    }, []);

    // 数据准备好后淡出
    useEffect(() => {
        if (isReady) {
            const fadeTimer = setTimeout(() => {
                setOpacity(0);
            }, 200);

            const completeTimer = setTimeout(() => {
                if (onComplete) onComplete();
            }, 500);

            return () => {
                clearTimeout(fadeTimer);
                clearTimeout(completeTimer);
            };
        }
    }, [isReady, onComplete]);

    return (
        <div
            className="flex-1 flex flex-col items-center justify-center bg-[#0d1117] transition-opacity duration-300"
            style={{ opacity }}
        >
            {/* 主 Logo + 脉冲效果 */}
            <div className="relative mb-8">
                {/* 脉冲光环 */}
                <div className="absolute inset-0 rounded-full bg-cyan-500/20 animate-ping" style={{ animationDuration: '1s' }} />
                <div className="absolute inset-0 rounded-full bg-cyan-500/10 animate-pulse" />

                {/* 核心图标 */}
                <div className="relative w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/20 to-indigo-500/20 border border-cyan-500/30 flex items-center justify-center">
                    <svg className="w-8 h-8 text-cyan-400 animate-spin" style={{ animationDuration: '2s' }} viewBox="0 0 24 24" fill="none">
                        <path d="M12 2L12 6M12 18L12 22M6 12L2 12M22 12L18 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                        <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
                    </svg>
                </div>
            </div>

            {/* 滚动哈希 */}
            <div className="font-mono text-sm text-cyan-400/80 mb-2 tracking-wider">
                {hash}
            </div>

            {/* 区块号 */}
            <div className="font-mono text-xs text-slate-500">
                Block #{blockNum.toLocaleString()}
            </div>

            {/* 状态文字 */}
            <div className="mt-6 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-sm text-slate-400 font-medium tracking-wide">
                    Syncing...
                </span>
            </div>
        </div>
    );
}
