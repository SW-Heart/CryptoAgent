import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe } from 'lucide-react';

const LandingPage = ({ onLogin, onLanguageChange, currentLanguage }) => {
    const { t, i18n } = useTranslation();
    const [terminalLines, setTerminalLines] = useState([]);
    const [currentPhase, setCurrentPhase] = useState(0);
    const [glitchActive, setGlitchActive] = useState(false);
    const [latency, setLatency] = useState(12);

    const isZh = i18n.language === 'zh';

    // Dynamic latency simulation
    useEffect(() => {
        const latencyInterval = setInterval(() => {
            // Most of the time show low latency (8-28ms), occasionally spike
            const random = Math.random();
            if (random > 0.95) {
                setLatency(Math.floor(Math.random() * 50) + 30); // 30-80ms spike
            } else if (random > 0.8) {
                setLatency(Math.floor(Math.random() * 10) + 20); // 20-30ms
            } else {
                setLatency(Math.floor(Math.random() * 15) + 8); // 8-23ms (most common)
            }
        }, 2000);
        return () => clearInterval(latencyInterval);
    }, []);

    // Color for latency
    const getLatencyColor = (ms) => {
        if (ms < 30) return 'text-green-400';
        if (ms < 60) return 'text-yellow-400';
        return 'text-red-400';
    };

    // Terminal animation sequences with color coding
    const sequences = [
        {
            commands: [
                { type: 'input', text: '> agent.run --target=BTC --strategy=macro_scan' },
                { type: 'dim', text: '[INIT] Connecting to node... OK' },
                { type: 'dim', text: '[SCAN] Analyzing on-chain volume...' },
                { type: 'hash', text: '0x4f3e2d1a8b7c... [MEMPOOL HASH]' },
                { type: 'dim', text: '> Filtering noise patterns... DONE.' },
                { type: 'bullish', text: isZh ? '>> [信号] 检测到看涨背离' : '>> [SIGNAL] BULLISH DIVERGENCE DETECTED' },
            ]
        },
        {
            commands: [
                { type: 'input', text: '> agent.scan --asset=ETH --mode=deep' },
                { type: 'dim', text: '[INIT] Loading neural network...' },
                { type: 'dim', text: '[DATA] Fetching 24h trading data...' },
                { type: 'hash', text: '0x8a9b7c6d5e4f... [BLOCK HASH]' },
                { type: 'dim', text: '> Pattern recognition complete.' },
                { type: 'bullish', text: isZh ? '>> [信号] 吸筹阶段进行中' : '>> [SIGNAL] ACCUMULATION PHASE ACTIVE' },
            ]
        },
        {
            commands: [
                { type: 'input', text: '> agent.analyze --pair=SOL/USDT' },
                { type: 'dim', text: '[SYNC] Synchronizing market feeds...' },
                { type: 'dim', text: '[CALC] Computing resistance levels...' },
                { type: 'hash', text: '0x1f2e3d4c5b6a... [TX HASH]' },
                { type: 'alert', text: isZh ? '>> [警报] 剧烈波动预警' : '>> [ALERT] HIGH VOLATILITY WARNING' },
                { type: 'bullish', text: isZh ? '>> [信号] 突破在即 - 87% 置信度' : '>> [SIGNAL] BREAKOUT IMMINENT - 87% CONF' },
            ]
        }
    ];

    // Glitch effect for logo
    useEffect(() => {
        const glitchInterval = setInterval(() => {
            setGlitchActive(true);
            setTimeout(() => setGlitchActive(false), 150);
        }, 5000);
        return () => clearInterval(glitchInterval);
    }, []);

    // Terminal animation
    useEffect(() => {
        let lineIndex = 0;
        let charIndex = 0;
        let currentText = '';
        const sequence = sequences[currentPhase];
        let cancelled = false;

        const typeWriter = () => {
            if (cancelled) return;

            if (lineIndex >= sequence.commands.length) {
                setTimeout(() => {
                    if (!cancelled) {
                        setTerminalLines([]);
                        setCurrentPhase((prev) => (prev + 1) % sequences.length);
                    }
                }, 2500);
                return;
            }

            const cmd = sequence.commands[lineIndex];
            const delay = cmd.type === 'input' ? 40 : cmd.type === 'dim' ? 25 : 15;

            if (charIndex < cmd.text.length) {
                currentText += cmd.text[charIndex];
                setTerminalLines(prev => {
                    const newLines = [...prev];
                    newLines[lineIndex] = { type: cmd.type, text: currentText };
                    return newLines;
                });
                charIndex++;
                setTimeout(typeWriter, delay);
            } else {
                lineIndex++;
                charIndex = 0;
                currentText = '';
                setTimeout(typeWriter, 150);
            }
        };

        typeWriter();

        return () => { cancelled = true; };
    }, [currentPhase, isZh]);

    // Get line color based on type
    const getLineColor = (type) => {
        switch (type) {
            case 'input': return 'text-cyan-300';
            case 'dim': return 'text-slate-500';
            case 'hash': return 'text-orange-400/70';
            case 'alert': return 'text-red-400 font-bold';
            case 'bullish': return 'text-cyan-400 text-lg font-bold mt-2';
            default: return 'text-green-400/80';
        }
    };

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col relative overflow-hidden">
            {/* Fonts */}
            <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
        
        * {
          font-family: 'JetBrains Mono', 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace !important;
        }
        
        @keyframes data-flow {
          0% { transform: translateX(-100%) translateY(-100%); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { transform: translateX(200%) translateY(200%); opacity: 0; }
        }
        
        @keyframes glitch {
          0% { transform: translate(0); }
          20% { transform: translate(-2px, 2px); }
          40% { transform: translate(-2px, -2px); }
          60% { transform: translate(2px, 2px); }
          80% { transform: translate(2px, -2px); }
          100% { transform: translate(0); }
        }
        
        @keyframes border-glow {
          0%, 100% { box-shadow: 0 0 20px rgba(0, 255, 255, 0.3), inset 0 0 20px rgba(0, 255, 255, 0.1); }
          50% { box-shadow: 0 0 40px rgba(0, 255, 255, 0.5), inset 0 0 30px rgba(0, 255, 255, 0.15); }
        }
      `}</style>

            {/* Isometric Grid Background */}
            <div
                className="absolute inset-0 opacity-15"
                style={{
                    backgroundImage: `
            linear-gradient(rgba(0, 255, 255, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 255, 255, 0.1) 1px, transparent 1px),
            linear-gradient(45deg, rgba(138, 43, 226, 0.05) 1px, transparent 1px)
          `,
                    backgroundSize: '50px 50px, 50px 50px, 70px 70px',
                }}
            />

            {/* Data Flow Lines */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                {[...Array(3)].map((_, i) => (
                    <div
                        key={i}
                        className="absolute w-32 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-60"
                        style={{
                            top: `${20 + i * 30}%`,
                            left: '0',
                            animation: `data-flow ${4 + i}s linear infinite`,
                            animationDelay: `${i * 2}s`,
                        }}
                    />
                ))}
            </div>

            {/* Vignette */}
            <div
                className="absolute inset-0 pointer-events-none"
                style={{
                    background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.7) 100%)',
                }}
            />

            {/* Scanline Effect */}
            <div
                className="absolute inset-0 pointer-events-none opacity-5"
                style={{
                    background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.03) 2px, rgba(255,255,255,0.03) 4px)',
                }}
            />

            {/* Header */}
            <header className="relative z-10 flex items-center justify-between px-6 py-4">
                {/* Logo + Status */}
                <div className="flex items-center gap-4">
                    <div className={`${glitchActive ? 'animate-[glitch_0.15s_ease]' : ''}`}>
                        <img
                            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                            alt="OGAgent"
                            className="w-10 h-10"
                        />
                    </div>
                    <div className="text-xs text-cyan-400/70">
                        {isZh ? '状态' : 'STATUS'}: <span className="text-green-400">{isZh ? '在线' : 'ONLINE'}</span> | {isZh ? '延迟' : 'LATENCY'}: <span className={getLatencyColor(latency)}>{latency}ms</span>
                    </div>
                </div>

                {/* Right Actions */}
                <div className="flex items-center gap-4">
                    <button
                        onClick={onLanguageChange}
                        className="p-2 text-slate-500 hover:text-cyan-400 transition-colors"
                    >
                        <Globe className="w-5 h-5" />
                    </button>
                    <button
                        onClick={() => onLogin('login')}
                        className="px-4 py-2 border border-cyan-500/50 text-cyan-400 text-sm hover:bg-cyan-500/10 hover:border-cyan-400 transition-all"
                    >
                        [ {isZh ? '连接' : 'CONNECT'} ]
                    </button>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 flex flex-col items-center justify-center px-6 relative z-10">
                {/* Title - Always English as main */}
                <h1 className="text-4xl md:text-5xl font-bold mb-2 text-center tracking-wider">
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-purple-400 to-cyan-400">
                        DECODE THE SIGNAL.
                    </span>
                </h1>
                {/* Subtitle - Chinese when in zh mode */}
                <p className="text-slate-500 text-sm mb-8">
                    {isZh ? '// 链上信号 · 实时破译' : '// Autonomous Intelligence for Decentralized Markets.'}
                </p>

                {/* Terminal Window */}
                <div
                    className="w-full max-w-2xl border border-cyan-500/30 bg-black/60 backdrop-blur-sm"
                    style={{ animation: 'border-glow 3s ease-in-out infinite' }}
                >
                    {/* Terminal Header */}
                    <div className="flex items-center gap-2 px-4 py-2 border-b border-cyan-500/20 bg-black/40">
                        <div className="w-3 h-3 rounded-full bg-red-500/70" />
                        <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
                        <div className="w-3 h-3 rounded-full bg-green-500/70" />
                        <span className="ml-4 text-xs text-slate-500">agent_terminal_v2.0.4b</span>
                    </div>

                    {/* Terminal Content */}
                    <div className="p-4 h-48 overflow-hidden">
                        {terminalLines.map((line, idx) => (
                            <div
                                key={idx}
                                className={`text-sm leading-relaxed ${getLineColor(line.type)}`}
                            >
                                {line.text}
                                {idx === terminalLines.length - 1 && !['bullish', 'alert'].includes(line.type) && (
                                    <span className="animate-pulse">▊</span>
                                )}
                            </div>
                        ))}
                        {terminalLines.length === 0 && (
                            <div className="text-cyan-300">
                                <span className="animate-pulse">▊</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* CTA Button */}
                <button
                    onClick={() => onLogin('register')}
                    className="mt-8 px-8 py-3 border-2 border-cyan-500/70 text-cyan-400 font-medium tracking-wider hover:bg-cyan-500/10 hover:border-cyan-400 hover:shadow-[0_0_30px_rgba(0,255,255,0.3)] transition-all duration-300 relative overflow-hidden group"
                >
                    <span className="relative z-10">[ {isZh ? '执行指令' : 'INITIALIZE AGENT'} ]</span>
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-500/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
                </button>
            </main>

            {/* Footer */}
            <footer className="relative z-10 py-4 px-6 flex items-center justify-between">
                <div className="text-xs text-slate-600">
                    {isZh ? '系统版本: 2.0.4b // 已加密' : 'SYS.VER: 2.0.4b // ENCRYPTED'}
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                    <a href="/privacy" className="hover:text-cyan-400 transition-colors">
                        {t('landing.footer.privacy')}
                    </a>
                    <span className="text-slate-700">|</span>
                    <a href="/terms" className="hover:text-cyan-400 transition-colors">
                        {t('landing.footer.terms')}
                    </a>
                </div>
            </footer>
        </div>
    );
};

export default LandingPage;
