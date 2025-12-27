import React from 'react';

/**
 * HomePage - 专门用于 Google OAuth 审核的静态页面
 * 深色设计，包含产品介绍和必要的合规链接
 */
export default function HomePage() {
    return (
        <div className="min-h-screen bg-[#0a0e17] text-white flex flex-col">
            {/* Navbar */}
            <header className="border-b border-slate-800 px-6 py-4">
                <div className="max-w-6xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <img
                            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                            alt="OG AI Logo"
                            className="w-10 h-10"
                        />
                        <span className="text-xl font-bold text-white">OG AI</span>
                    </div>
                    <a
                        href="/"
                        className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white px-6 py-2 rounded-lg font-medium transition-colors"
                    >
                        Launch App
                    </a>
                </div>
            </header>

            {/* Hero Section */}
            <main className="flex-1">
                <section className="max-w-4xl mx-auto px-6 py-16 text-center">
                    <h1 className="text-4xl font-bold text-white mb-4">
                        OG AI - Professional Crypto Market Analysis Tool
                    </h1>
                    <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
                        OG AI is a professional cryptocurrency market analysis tool designed to help traders and investors
                        make informed decisions. Our platform provides real-time market data, AI-powered trading strategies,
                        and comprehensive risk management tools.
                    </p>
                    <a
                        href="/"
                        className="inline-block bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white px-8 py-3 rounded-lg font-medium text-lg transition-colors"
                    >
                        Get Started
                    </a>
                </section>

                {/* Features Section */}
                <section className="bg-[#0d1117] py-16">
                    <div className="max-w-4xl mx-auto px-6">
                        <h2 className="text-2xl font-bold text-white mb-8 text-center">Key Features</h2>
                        <div className="grid md:grid-cols-3 gap-8">
                            <div className="bg-[#131722] p-6 rounded-xl border border-slate-800">
                                <h3 className="text-lg font-semibold text-cyan-400 mb-2">📊 Real-time Monitoring</h3>
                                <p className="text-slate-400">
                                    Monitor cryptocurrency prices, market trends, and trading volumes in real-time
                                    with our advanced data aggregation system.
                                </p>
                            </div>
                            <div className="bg-[#131722] p-6 rounded-xl border border-slate-800">
                                <h3 className="text-lg font-semibold text-purple-400 mb-2">🤖 AI Strategy</h3>
                                <p className="text-slate-400">
                                    Leverage AI-powered trading strategies and market analysis to identify
                                    potential opportunities in the crypto market.
                                </p>
                            </div>
                            <div className="bg-[#131722] p-6 rounded-xl border border-slate-800">
                                <h3 className="text-lg font-semibold text-indigo-400 mb-2">🛡️ Risk Control</h3>
                                <p className="text-slate-400">
                                    Comprehensive risk management tools to help you protect your investments
                                    and manage your portfolio effectively.
                                </p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* About Section */}
                <section className="py-16">
                    <div className="max-w-4xl mx-auto px-6">
                        <h2 className="text-2xl font-bold text-white mb-4 text-center">About OG AI</h2>
                        <p className="text-slate-400 text-center max-w-2xl mx-auto">
                            OG AI provides professional cryptocurrency market analysis services. Our platform
                            aggregates data from multiple sources to deliver accurate market insights and
                            trading recommendations. We are committed to helping users navigate the complex
                            world of cryptocurrency trading with confidence.
                        </p>
                    </div>
                </section>
            </main>

            {/* Footer */}
            <footer className="border-t border-slate-800 py-8 px-6">
                <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2 text-slate-500">
                        <img
                            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                            alt="OG AI"
                            className="w-6 h-6"
                        />
                        <span>© 2025 OG AI. All rights reserved.</span>
                    </div>
                    <div className="flex items-center gap-6">
                        <a
                            href="/privacy"
                            className="text-indigo-400 hover:text-indigo-300 hover:underline"
                        >
                            Privacy Policy
                        </a>
                        <a
                            href="/terms"
                            className="text-indigo-400 hover:text-indigo-300 hover:underline"
                        >
                            Terms of Service
                        </a>
                    </div>
                </div>
            </footer>
        </div>
    );
}
