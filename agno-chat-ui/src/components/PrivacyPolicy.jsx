import React from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft } from 'lucide-react';

const PrivacyPolicy = ({ onBack }) => {
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

                <h1 className="text-3xl font-bold mb-8">Privacy Policy</h1>
                <p className="text-slate-400 mb-8">Last updated: December 27, 2024</p>

                <div className="prose prose-invert max-w-none space-y-6">
                    <section>
                        <h2 className="text-xl font-semibold mb-4">1. Introduction</h2>
                        <p className="text-slate-300 leading-relaxed">
                            Welcome to OG Agent ("we," "our," or "us"). We are committed to protecting your privacy
                            and ensuring the security of your personal information. This Privacy Policy explains how
                            we collect, use, disclose, and safeguard your information when you use our cryptocurrency
                            analysis and trading assistant service.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">2. Information We Collect</h2>
                        <h3 className="text-lg font-medium mb-2 text-slate-200">2.1 Account Information</h3>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>Email address (when you sign up via Google OAuth)</li>
                            <li>Display name and profile picture (from your Google account)</li>
                            <li>Unique user identifier</li>
                        </ul>

                        <h3 className="text-lg font-medium mb-2 mt-4 text-slate-200">2.2 Usage Data</h3>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>Chat history and conversation logs</li>
                            <li>Trading simulation data (virtual positions, virtual wallet balance)</li>
                            <li>Feature usage patterns and preferences</li>
                            <li>Session information and timestamps</li>
                        </ul>

                        <h3 className="text-lg font-medium mb-2 mt-4 text-slate-200">2.3 Technical Data</h3>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>IP address and browser type</li>
                            <li>Device information and operating system</li>
                            <li>Cookies and similar tracking technologies</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">3. How We Use Your Information</h2>
                        <p className="text-slate-300 leading-relaxed mb-4">We use the collected information to:</p>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>Provide and maintain our AI-powered cryptocurrency analysis service</li>
                            <li>Process and manage your virtual trading simulations</li>
                            <li>Personalize your experience and improve our services</li>
                            <li>Send important updates and notifications</li>
                            <li>Analyze usage patterns to enhance functionality</li>
                            <li>Prevent fraud and ensure security</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">4. Data Sharing and Disclosure</h2>
                        <p className="text-slate-300 leading-relaxed mb-4">
                            We do not sell your personal information. We may share your data with:
                        </p>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li><strong>Service Providers:</strong> Third-party services that help us operate our platform (e.g., Supabase for authentication, hosting providers)</li>
                            <li><strong>AI Model Providers:</strong> Your queries are processed by AI providers (DeepSeek) to generate responses</li>
                            <li><strong>Legal Requirements:</strong> When required by law or to protect our rights</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">5. Data Security</h2>
                        <p className="text-slate-300 leading-relaxed">
                            We implement industry-standard security measures including encryption, secure data
                            transmission (HTTPS), and access controls to protect your information. However, no
                            method of transmission over the Internet is 100% secure.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">6. Data Retention</h2>
                        <p className="text-slate-300 leading-relaxed">
                            We retain your data for as long as your account is active or as needed to provide
                            services. You can request deletion of your data at any time by contacting us.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">7. Your Rights</h2>
                        <p className="text-slate-300 leading-relaxed mb-4">You have the right to:</p>
                        <ul className="list-disc list-inside text-slate-300 space-y-2 ml-4">
                            <li>Access your personal data</li>
                            <li>Correct inaccurate data</li>
                            <li>Request deletion of your data</li>
                            <li>Opt-out of marketing communications</li>
                            <li>Export your data in a portable format</li>
                        </ul>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">8. Cookies</h2>
                        <p className="text-slate-300 leading-relaxed">
                            We use cookies and similar technologies to maintain your session, remember your
                            preferences, and improve your experience. You can control cookie settings through
                            your browser.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">9. Children's Privacy</h2>
                        <p className="text-slate-300 leading-relaxed">
                            Our service is not intended for users under 18 years of age. We do not knowingly
                            collect personal information from children.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">10. Changes to This Policy</h2>
                        <p className="text-slate-300 leading-relaxed">
                            We may update this Privacy Policy from time to time. We will notify you of any
                            significant changes by posting the new policy on this page and updating the
                            "Last updated" date.
                        </p>
                    </section>

                    <section>
                        <h2 className="text-xl font-semibold mb-4">11. Contact Us</h2>
                        <p className="text-slate-300 leading-relaxed">
                            If you have questions about this Privacy Policy or our data practices, please
                            contact us at: <a href="mailto:support@ogagent.org" className="text-purple-400 hover:underline">support@ogagent.org</a>
                        </p>
                    </section>
                </div>
            </div>
        </div>
    );
};

export default PrivacyPolicy;
