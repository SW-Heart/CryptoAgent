import React from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft } from 'lucide-react';

const TermsOfService = ({ onBack }) => {
    const { t } = useTranslation();

    return (
        <div className="min-h-screen bg-[#0a0e17] text-white">
            <div className="max-w-4xl mx-auto px-6 py-12">
                {/* Back button */}
                <button
                    onClick={onBack}
                    className="flex items-center gap-2 text-slate-400 hover:text-white mb-8 transition-colors"
                >
                    <ArrowLeft className="w-5 h-5" />
                    Back
                </button>

                <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>
                <p className="text-slate-400 mb-8">Last updated: December 27, 2024</p>

                <div className="prose prose-invert max-w-none space-y-6">
                    <section>
                        <h2 className="text-xl font-semibold mb-4">1. Acceptance of Terms</h2>
                        <p className="text-slate-300 leading-relaxed">
                            By accessing or using OG Agent ("Service"), you agree to be bound by these Terms of
                            Service ("Terms"). If you do not agree to these Terms, please do not use the Service.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">2. Description of Service</h2>
                        <p className="text-slate-300 leading-relaxed">
                            OG Agent is an AI-powered cryptocurrency analysis and trading simulation platform.
                            The Service provides:
                        </p>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4 mt-4">
                            <li>AI-driven market analysis and insights</li>
                            <li>Virtual trading simulation (paper trading)</li>
                            <li>Cryptocurrency news and data aggregation</li>
                            <li>Technical analysis tools</li>
                            <li>Daily market reports</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">3. Important Disclaimers</h2>
                        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 mb-4">
                            <p className="text-yellow-200 font-medium mb-2">⚠️ NOT FINANCIAL ADVICE</p>
                            <p className="text-slate-300">
                                The information provided by OG Agent is for educational and informational purposes
                                only. It should NOT be considered as financial, investment, or trading advice.
                                Always conduct your own research and consult with a qualified financial advisor
                                before making any investment decisions.
                            </p>
                        </div>
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                            <p className="text-red-200 font-medium mb-2">⚠️ SIMULATION ONLY</p>
                            <p className="text-slate-300">
                                All trading features on this platform are SIMULATIONS using virtual money.
                                No real cryptocurrency transactions occur. Past performance in simulations
                                does not guarantee future results in real trading.
                            </p>
                        </div>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">4. User Accounts</h2>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>You must be at least 18 years old to use this Service</li>
                            <li>You are responsible for maintaining the security of your account</li>
                            <li>You must provide accurate and complete information</li>
                            <li>You may not share your account with others</li>
                            <li>We reserve the right to suspend or terminate accounts that violate these Terms</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">5. Acceptable Use</h2>
                        <p className="text-slate-300 leading-relaxed mb-4">You agree NOT to:</p>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>Use the Service for any illegal purpose</li>
                            <li>Attempt to gain unauthorized access to the Service</li>
                            <li>Interfere with or disrupt the Service</li>
                            <li>Use automated systems or bots to access the Service</li>
                            <li>Reverse engineer or attempt to extract the source code</li>
                            <li>Redistribute or resell the Service without permission</li>
                            <li>Use the Service to spread misinformation or manipulate markets</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">6. Intellectual Property</h2>
                        <p className="text-slate-300 leading-relaxed">
                            All content, features, and functionality of the Service are owned by OG Agent and
                            are protected by copyright, trademark, and other intellectual property laws. You
                            may not copy, modify, distribute, or create derivative works without our explicit
                            permission.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">7. Credits and Usage Limits</h2>
                        <p className="text-slate-300 leading-relaxed">
                            The Service operates on a credit-based system. Credits are consumed when using
                            AI analysis features. We reserve the right to modify the credit system, pricing,
                            and usage limits at any time.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">8. Third-Party Services</h2>
                        <p className="text-slate-300 leading-relaxed">
                            Our Service integrates with third-party services (e.g., Binance API for market data,
                            CoinGecko, CryptoPanic). We are not responsible for the accuracy, availability, or
                            actions of these third-party services.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">9. Limitation of Liability</h2>
                        <p className="text-slate-300 leading-relaxed">
                            TO THE MAXIMUM EXTENT PERMITTED BY LAW, OG AGENT SHALL NOT BE LIABLE FOR ANY
                            INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING
                            BUT NOT LIMITED TO LOSS OF PROFITS, DATA, OR TRADING LOSSES, ARISING OUT OF
                            YOUR USE OF THE SERVICE.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">10. Disclaimer of Warranties</h2>
                        <p className="text-slate-300 leading-relaxed">
                            THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND,
                            EITHER EXPRESS OR IMPLIED. WE DO NOT GUARANTEE THE ACCURACY, COMPLETENESS, OR
                            RELIABILITY OF ANY CONTENT OR ANALYSIS PROVIDED.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">11. Indemnification</h2>
                        <p className="text-slate-300 leading-relaxed">
                            You agree to indemnify and hold harmless OG Agent and its affiliates from any
                            claims, damages, or expenses arising from your use of the Service or violation
                            of these Terms.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">12. Modifications to Terms</h2>
                        <p className="text-slate-300 leading-relaxed">
                            We reserve the right to modify these Terms at any time. We will notify users of
                            significant changes. Your continued use of the Service after changes constitutes
                            acceptance of the new Terms.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">13. Termination</h2>
                        <p className="text-slate-300 leading-relaxed">
                            We may terminate or suspend your access to the Service immediately, without prior
                            notice or liability, for any reason, including breach of these Terms.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">14. Governing Law</h2>
                        <p className="text-slate-300 leading-relaxed">
                            These Terms shall be governed by and construed in accordance with applicable laws,
                            without regard to conflict of law principles.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">15. Contact Information</h2>
                        <p className="text-slate-300 leading-relaxed">
                            For questions about these Terms, please contact us at: {' '}
                            <a href="mailto:support@ogagent.org" className="text-purple-400 hover:underline">support@ogagent.org</a>
                        </p>
                    </section>
                </div>
            </div>
        </div>
    );
};

export default TermsOfService;
