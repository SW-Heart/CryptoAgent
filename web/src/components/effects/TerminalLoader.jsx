import React, { useState, useEffect, useCallback } from 'react';

/**
 * TerminalLoader - 终端风格加载动画
 * 
 * Props:
 * - onComplete: 加载完成时的回调（可选）
 * - minDuration: 最小显示时间（ms），默认 2500
 * - isReady: 外部数据是否准备好，只有当 isReady=true 且动画完成才会结束
 * - fullScreen: 是否全屏显示，默认 true
 */
const TerminalLoader = ({ onComplete, minDuration = 1500, isReady = false, fullScreen = true }) => {
    const [phase, setPhase] = useState(0); // 0: 唤醒, 1: 握手, 2: 数据注入, 3: 就绪
    const [progress, setProgress] = useState(0);
    const [showCursor, setShowCursor] = useState(true);
    const [logs, setLogs] = useState([]);
    const [statusText, setStatusText] = useState('');
    const [isExiting, setIsExiting] = useState(false);
    const [glitchActive, setGlitchActive] = useState(false);
    const [animationComplete, setAnimationComplete] = useState(false);

    // 日志内容库
    const logMessages = [
        '> BTC_Hash: 0x4f3e2d1a... [OK]',
        '> Loading Strategy: MACRO_V4',
        '> Checking Gas Fees... Low',
        '> Establishing secure handshake...',
        '> Mempool scan: COMPLETE',
        '> Retrieving whale wallet focus...',
        '> Node_ETH: Connected',
        '> Verifying Token Protocol...',
        '> Bypass Proxy... SUCCESS',
        '> Loading Neural Weights...',
        '> Chain sync: Block 19847231',
        '> Decrypt market signals...',
        '> Loading on-chain analytics...',
        '> API handshake: VERIFIED',
        '> Initializing trading engine...',
    ];

    const warningLogs = [
        '[WARN] High Volatility Detected...',
        '[INFO] Loading Neural Weights...',
        '[SYNC] Blockchain data streaming...',
        '[ALERT] Whale movement detected...',
    ];

    // 状态文案
    const statusMessages = [
        '// ESTABLISHING CONNECTION...',
        '// SYNCING BLOCKCHAIN DATA...',
        '// DECRYPTING SIGNALS...',
        '// LOADING MARKET DATA...',
    ];

    // 进度条渲染
    const renderProgressBar = useCallback(() => {
        const total = 20;
        const filled = Math.floor((progress / 100) * total);
        const empty = total - filled;
        const bar = '█'.repeat(filled) + '░'.repeat(empty);
        return `[${bar}]`;
    }, [progress]);

    // Glitch 效果
    useEffect(() => {
        if (phase >= 1) {
            const glitchInterval = setInterval(() => {
                setGlitchActive(true);
                setTimeout(() => setGlitchActive(false), 100);
            }, 2000);
            return () => clearInterval(glitchInterval);
        }
    }, [phase]);

    // 光标闪烁
    useEffect(() => {
        const cursorInterval = setInterval(() => {
            setShowCursor(prev => !prev);
        }, 500);
        return () => clearInterval(cursorInterval);
    }, []);

    // 日志滚动
    useEffect(() => {
        if (phase >= 1 && phase < 3) {
            const logInterval = setInterval(() => {
                const isWarning = Math.random() > 0.8;
                const pool = isWarning ? warningLogs : logMessages;
                const newLog = {
                    text: pool[Math.floor(Math.random() * pool.length)],
                    type: isWarning ? 'warning' : 'normal',
                    id: Date.now()
                };
                setLogs(prev => [...prev.slice(-8), newLog]);
            }, 150);
            return () => clearInterval(logInterval);
        }
    }, [phase]);

    // 主动画逻辑
    useEffect(() => {
        const timeline = [
            // 阶段 0: 唤醒 (0-500ms)
            { time: 300, action: () => setPhase(1) },
            // 阶段 1: 握手 (300-1000ms)
            { time: 400, action: () => setStatusText(statusMessages[0]) },
            { time: 500, action: () => setProgress(15) },
            { time: 700, action: () => setProgress(30) },
            { time: 900, action: () => setProgress(40) },
            { time: 1000, action: () => { setPhase(2); setStatusText(statusMessages[1]); } },
            // 阶段 2: 数据注入 (1000-2000ms) - 停在 90%
            { time: 1100, action: () => setProgress(50) },
            { time: 1300, action: () => setStatusText(statusMessages[2]) },
            { time: 1400, action: () => setProgress(60) },
            { time: 1600, action: () => setProgress(70) },
            { time: 1800, action: () => setStatusText(statusMessages[3]) },
            { time: 2000, action: () => setProgress(85) },
            { time: 2200, action: () => { setProgress(90); setAnimationComplete(true); } },
        ];

        const timeouts = timeline.map(({ time, action }) =>
            setTimeout(action, time)
        );

        return () => timeouts.forEach(clearTimeout);
    }, []);

    // 当数据准备好且动画完成时，进入就绪阶段
    useEffect(() => {
        if (isReady && animationComplete) {
            // 完成最后 10%
            setProgress(100);
            setPhase(3);
            setStatusText('SYSTEM READY');

            // 延迟后退场
            const exitTimer = setTimeout(() => {
                setIsExiting(true);
            }, 500);

            const completeTimer = setTimeout(() => {
                if (onComplete) onComplete();
            }, 800);

            return () => {
                clearTimeout(exitTimer);
                clearTimeout(completeTimer);
            };
        }
    }, [isReady, animationComplete, onComplete]);

    // 容器样式
    const containerClass = fullScreen
        ? `fixed inset-0 bg-black z-50 flex flex-col items-center justify-center overflow-hidden transition-all duration-300 ${isExiting ? 'scale-y-0' : 'scale-y-100'}`
        : `flex-1 bg-black flex flex-col items-center justify-center overflow-hidden transition-all duration-300 ${isExiting ? 'opacity-0' : 'opacity-100'}`;

    return (
        <div
            className={containerClass}
            style={{ fontFamily: "'JetBrains Mono', 'SF Mono', 'Consolas', monospace" }}
        >
            {/* Google Font */}
            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
        
        @keyframes glitch {
          0% { transform: translate(0); filter: hue-rotate(0deg); }
          20% { transform: translate(-2px, 2px); filter: hue-rotate(90deg); }
          40% { transform: translate(-2px, -2px); filter: hue-rotate(180deg); }
          60% { transform: translate(2px, 2px); filter: hue-rotate(270deg); }
          80% { transform: translate(2px, -2px); filter: hue-rotate(360deg); }
          100% { transform: translate(0); filter: hue-rotate(0deg); }
        }
      `}</style>

            {/* 背景网格 */}
            <div
                className="absolute inset-0 opacity-5"
                style={{
                    backgroundImage: `
            linear-gradient(rgba(0, 255, 204, 0.3) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 204, 0.3) 1px, transparent 1px)
          `,
                    backgroundSize: '40px 40px',
                }}
            />

            {/* 扫描线 */}
            <div
                className="absolute inset-0 pointer-events-none opacity-10"
                style={{
                    background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,204,0.03) 2px, rgba(0,255,204,0.03) 4px)',
                }}
            />

            {/* 中央核心区 */}
            <div className="flex flex-col items-center z-10">
                {/* 阶段 0: 光标 */}
                {phase === 0 && (
                    <div className="text-2xl text-cyan-400">
                        {showCursor ? '▊' : ' '}
                    </div>
                )}

                {/* 阶段 1+: Logo */}
                {phase >= 1 && (
                    <div className={`mb-8 ${glitchActive ? 'animate-[glitch_0.1s_ease]' : ''}`}>
                        <img
                            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                            alt="Logo"
                            className="w-16 h-16"
                        />
                    </div>
                )}

                {/* 进度条 */}
                {phase >= 1 && (
                    <div
                        className={`text-xl tracking-widest mb-4 transition-all duration-300 ${phase === 3 ? 'text-green-400' : 'text-cyan-400'
                            }`}
                        style={{ textShadow: phase === 3 ? '0 0 20px rgba(34,197,94,0.8)' : '0 0 15px rgba(0,255,204,0.6)' }}
                    >
                        {renderProgressBar()} {progress}%
                    </div>
                )}

                {/* 状态文字 */}
                {phase >= 1 && (
                    <div className={`text-sm tracking-wide transition-all duration-300 ${phase === 3 ? 'text-green-400 text-xl font-bold' : 'text-white'
                        }`}>
                        {statusText}
                        {phase < 3 && showCursor && <span className="ml-1">▊</span>}
                    </div>
                )}
            </div>

            {/* 滚动日志区 */}
            {phase >= 1 && phase < 3 && (
                <div className="mt-10 h-24 overflow-hidden text-center opacity-70">
                    {logs.map((log) => (
                        <div
                            key={log.id}
                            className={`text-xs leading-relaxed transition-all ${log.type === 'warning' ? 'text-orange-400' : 'text-slate-600'
                                }`}
                        >
                            {log.text}
                        </div>
                    ))}
                </div>
            )}

            {/* 角落信息 - 仅全屏模式显示 */}
            {fullScreen && (
                <>
                    <div className="absolute bottom-5 left-5 text-xs text-slate-700">
                        VER 2.0.4b
                    </div>
                    <div className="absolute bottom-5 right-5 text-xs text-slate-700">
                        ENCRYPTED // SECURE
                    </div>
                </>
            )}
        </div>
    );
};

export default TerminalLoader;
