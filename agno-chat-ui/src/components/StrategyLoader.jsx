import React, { useState, useEffect } from 'react';
import { TrendingUp, BarChart2, Activity, Shield, Target } from 'lucide-react';

const StrategyLoader = () => {
    const [currentStep, setCurrentStep] = useState(0);

    const loadingSteps = [
        { icon: Shield, text: 'Securing connection...', color: 'text-purple-400' },
        { icon: BarChart2, text: 'Loading market data...', color: 'text-blue-400' },
        { icon: Activity, text: 'Analyzing positions...', color: 'text-cyan-400' },
        { icon: TrendingUp, text: 'Calculating P&L...', color: 'text-green-400' },
        { icon: Target, text: 'Preparing dashboard...', color: 'text-amber-400' },
    ];

    useEffect(() => {
        const interval = setInterval(() => {
            setCurrentStep(prev => (prev + 1) % loadingSteps.length);
        }, 800);
        return () => clearInterval(interval);
    }, [loadingSteps.length]);

    const CurrentIcon = loadingSteps[currentStep].icon;

    return (
        <div className="flex-1 flex items-center justify-center bg-[#0d1117] relative overflow-hidden">
            {/* Animated background grid */}
            <div className="absolute inset-0 overflow-hidden opacity-20">
                <div
                    className="absolute inset-0"
                    style={{
                        backgroundImage: `
              linear-gradient(rgba(99, 102, 241, 0.15) 1px, transparent 1px),
              linear-gradient(90deg, rgba(99, 102, 241, 0.15) 1px, transparent 1px)
            `,
                        backgroundSize: '40px 40px',
                        animation: 'gridMove 15s linear infinite',
                    }}
                />
            </div>

            {/* Floating particles */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                {[...Array(12)].map((_, i) => (
                    <div
                        key={i}
                        className="absolute w-1.5 h-1.5 bg-indigo-400/20 rounded-full"
                        style={{
                            left: `${10 + Math.random() * 80}%`,
                            top: `${10 + Math.random() * 80}%`,
                            animation: `float ${3 + Math.random() * 3}s ease-in-out infinite`,
                            animationDelay: `${Math.random() * 2}s`,
                        }}
                    />
                ))}
            </div>

            {/* Main content */}
            <div className="relative z-10 flex flex-col items-center">
                {/* Animated icon container */}
                <div className="relative mb-6">
                    {/* Spinning outer ring */}
                    <div
                        className="absolute inset-0 w-24 h-24 rounded-full border-2 border-indigo-500/20"
                        style={{ animation: 'spin 8s linear infinite' }}
                    />

                    {/* Pulsing middle ring */}
                    <div
                        className="absolute inset-2 w-20 h-20 rounded-full border border-indigo-400/30"
                        style={{ animation: 'pulse 2s ease-in-out infinite' }}
                    />

                    {/* Center icon container */}
                    <div className="w-24 h-24 flex items-center justify-center">
                        <div
                            className={`p-4 rounded-2xl bg-gradient-to-br from-indigo-600/20 to-purple-600/20 backdrop-blur-sm border border-indigo-500/30 transition-all duration-300 ${loadingSteps[currentStep].color}`}
                        >
                            <CurrentIcon className="w-8 h-8" />
                        </div>
                    </div>
                </div>

                {/* Title */}
                <h2 className="text-xl font-semibold text-white mb-2">
                    Strategy Nexus
                </h2>

                {/* Current step text with fade animation */}
                <div className="h-6 flex items-center">
                    <p
                        key={currentStep}
                        className={`text-sm font-medium ${loadingSteps[currentStep].color} animate-pulse`}
                    >
                        {loadingSteps[currentStep].text}
                    </p>
                </div>

                {/* Loading dots */}
                <div className="flex gap-1.5 mt-4">
                    {[0, 1, 2].map((i) => (
                        <div
                            key={i}
                            className="w-2 h-2 bg-indigo-400 rounded-full"
                            style={{
                                animation: 'bounce 1s ease-in-out infinite',
                                animationDelay: `${i * 0.15}s`,
                            }}
                        />
                    ))}
                </div>

                {/* Crypto symbols decoration */}
                <div className="flex gap-8 mt-6 opacity-30">
                    {['₿', 'Ξ', '◎'].map((symbol, i) => (
                        <span
                            key={symbol}
                            className="text-xl text-indigo-400"
                            style={{
                                animation: `float ${2 + i * 0.3}s ease-in-out infinite`,
                                animationDelay: `${i * 0.2}s`,
                            }}
                        >
                            {symbol}
                        </span>
                    ))}
                </div>
            </div>

            {/* CSS Animations */}
            <style jsx>{`
        @keyframes gridMove {
          0% { transform: translate(0, 0); }
          100% { transform: translate(40px, 40px); }
        }
        
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
        
        @keyframes pulse {
          0%, 100% { transform: scale(1); opacity: 0.3; }
          50% { transform: scale(1.05); opacity: 0.6; }
        }
        
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        
        @keyframes bounce {
          0%, 100% { transform: translateY(0); opacity: 0.4; }
          50% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
        </div>
    );
};

export default StrategyLoader;
