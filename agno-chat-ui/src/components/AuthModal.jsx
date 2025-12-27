import React, { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { X, Mail, Lock, Loader2, AlertCircle, CheckCircle, ArrowLeft, Eye, EyeOff, Wallet } from 'lucide-react'

// Google SVG Icon
const GoogleIcon = () => (
    <svg viewBox="0 0 24 24" className="w-5 h-5">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
)

const AuthModal = ({ isOpen, onClose }) => {
    const { t } = useTranslation()
    const { signIn, signUp, verifyOtp, signInWithGoogle, signInWithWallet } = useAuth()

    const [view, setView] = useState('login')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)
    const [verificationCode, setVerificationCode] = useState(['', '', '', '', '', ''])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [success, setSuccess] = useState('')

    const codeInputRefs = useRef([])

    useEffect(() => {
        if (view === 'verify' && codeInputRefs.current[0]) {
            codeInputRefs.current[0].focus()
        }
    }, [view])

    if (!isOpen) return null

    const resetState = () => {
        setError('')
        setSuccess('')
        setVerificationCode(['', '', '', '', '', ''])
        setConfirmPassword('')
    }

    const handleEmailAuth = async (e) => {
        e.preventDefault()
        resetState()

        // Check confirm password for registration
        if (view === 'register' && password !== confirmPassword) {
            setError(t('auth.passwordsNotMatch'))
            return
        }

        setLoading(true)

        try {
            if (view === 'login') {
                const { error } = await signIn(email, password)
                if (error) throw error
                onClose()
            } else if (view === 'register') {
                const { error } = await signUp(email, password)
                if (error) throw error
                setSuccess(t('auth.verificationSent'))
                setView('verify')
            }
        } catch (err) {
            setError(err.message || t('auth.operationFailed'))
        } finally {
            setLoading(false)
        }
    }

    const handleCodeChange = (index, value) => {
        if (!/^\d*$/.test(value)) return

        const newCode = [...verificationCode]
        newCode[index] = value.slice(-1)
        setVerificationCode(newCode)

        if (value && index < 5) {
            codeInputRefs.current[index + 1]?.focus()
        }
    }

    const handleCodeKeyDown = (index, e) => {
        if (e.key === 'Backspace' && !verificationCode[index] && index > 0) {
            codeInputRefs.current[index - 1]?.focus()
        }
    }

    const handleCodePaste = (e) => {
        e.preventDefault()
        const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
        if (pastedData) {
            const newCode = [...verificationCode]
            for (let i = 0; i < pastedData.length; i++) {
                newCode[i] = pastedData[i]
            }
            setVerificationCode(newCode)
            if (pastedData.length === 6) {
                codeInputRefs.current[5]?.focus()
            }
        }
    }

    const handleVerifyCode = async (e) => {
        e.preventDefault()
        const code = verificationCode.join('')
        if (code.length !== 6) return

        resetState()
        setLoading(true)

        try {
            const { error } = await verifyOtp(email, code)
            if (error) throw error
            setSuccess(t('auth.verificationSuccess'))
            setTimeout(() => onClose(), 800)
        } catch (err) {
            setError(err.message || t('auth.invalidCode'))
            setVerificationCode(['', '', '', '', '', ''])
            codeInputRefs.current[0]?.focus()
        } finally {
            setLoading(false)
        }
    }

    const handleGoogleLogin = async () => {
        setError('')
        setLoading(true)
        try {
            const { error } = await signInWithGoogle()
            if (error) throw error
        } catch (err) {
            setError(err.message || t('auth.googleLoginFailed'))
            setLoading(false)
        }
    }

    const handleWalletLogin = async () => {
        setError('')
        setLoading(true)
        try {
            const { error } = await signInWithWallet()
            if (error) throw error
            onClose()
        } catch (err) {
            setError(err.message || t('auth.walletConnectionFailed'))
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop with blur */}
            <div
                className="absolute inset-0 bg-slate-900/60 backdrop-blur-md"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative w-full max-w-[420px] animate-in zoom-in-95 fade-in duration-300">
                <div className="absolute -inset-0.5 bg-black rounded-3xl blur opacity-30" />

                <div className="relative bg-[#131722] rounded-2xl shadow-2xl overflow-hidden">
                    {/* Close button */}
                    <button
                        onClick={onClose}
                        className="absolute top-4 right-4 z-10 p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
                    >
                        <X className="w-5 h-5" />
                    </button>

                    {/* Back button for verify view */}
                    {view === 'verify' && (
                        <button
                            onClick={() => { setView('register'); resetState(); }}
                            className="absolute top-4 left-4 z-10 p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
                        >
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                    )}

                    {/* Content */}
                    <div className="p-8">
                        {/* Logo & Title */}
                        <div className="text-center mb-8">
                            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4">
                                <img
                                    src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                                    alt="Logo"
                                    className="w-14 h-14 rounded-xl object-contain"
                                />
                            </div>
                            <h2 className="text-2xl font-bold text-white">
                                {view === 'verify' ? t('auth.verifyEmail') : t('auth.launchTitle')}
                            </h2>
                            <p className="text-slate-400 text-sm mt-1">
                                {view === 'login' && t('auth.signInToAccount')}
                                {view === 'register' && t('auth.createAccount')}
                                {view === 'verify' && email}
                            </p>
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="mb-4 p-3 rounded-xl bg-red-900/30 border border-red-800 flex items-center gap-2 text-red-400 text-sm animate-in slide-in-from-top-2">
                                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* Success */}
                        {success && (
                            <div className="mb-4 p-3 rounded-xl bg-emerald-900/30 border border-emerald-800 flex items-center gap-2 text-emerald-400 text-sm animate-in slide-in-from-top-2">
                                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                                <span>{success}</span>
                            </div>
                        )}

                        {/* Verification View */}
                        {view === 'verify' ? (
                            <form onSubmit={handleVerifyCode} className="space-y-6">
                                {/* Code Input */}
                                <div className="flex justify-center gap-2" onPaste={handleCodePaste}>
                                    {verificationCode.map((digit, idx) => (
                                        <input
                                            key={idx}
                                            ref={el => codeInputRefs.current[idx] = el}
                                            type="text"
                                            inputMode="numeric"
                                            maxLength={1}
                                            value={digit}
                                            onChange={(e) => handleCodeChange(idx, e.target.value)}
                                            onKeyDown={(e) => handleCodeKeyDown(idx, e)}
                                            className="w-12 h-14 text-center text-xl font-semibold text-white bg-slate-800 rounded-xl focus:ring-0 outline-none transition-all"
                                        />
                                    ))}
                                </div>

                                <button
                                    type="submit"
                                    disabled={loading || verificationCode.join('').length !== 6}
                                    className="w-full h-12 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : t('auth.verify')}
                                </button>

                                <p className="text-center text-sm text-slate-500">
                                    {t('auth.didntReceive')}
                                    <button
                                        type="button"
                                        onClick={() => { setView('register'); handleEmailAuth({ preventDefault: () => { } }); }}
                                        className="text-slate-300 hover:text-white font-medium ml-1"
                                    >
                                        {t('auth.resend')}
                                    </button>
                                </p>
                            </form>
                        ) : (
                            <>
                                {/* OAuth Buttons */}
                                <div className="space-y-3 mb-6">
                                    <button
                                        onClick={handleGoogleLogin}
                                        disabled={loading}
                                        className="w-full h-12 rounded-xl bg-slate-700 hover:bg-slate-600 transition-all flex items-center justify-center gap-3 font-medium text-white disabled:opacity-50"
                                    >
                                        <GoogleIcon />
                                        {t('auth.continueWithGoogle')}
                                    </button>
                                    <button
                                        onClick={handleWalletLogin}
                                        disabled={loading}
                                        className="w-full h-12 rounded-xl bg-slate-700 hover:bg-slate-600 transition-all flex items-center justify-center gap-3 font-medium text-white disabled:opacity-50"
                                    >
                                        <Wallet className="w-5 h-5 text-indigo-400" />
                                        {t('auth.connectWallet')}
                                    </button>
                                </div>

                                {/* Divider */}
                                <div className="relative my-6">
                                    <div className="absolute inset-0 flex items-center">
                                        <div className="w-full border-t border-slate-700" />
                                    </div>
                                    <div className="relative flex justify-center">
                                        <span className="px-4 bg-[#131722] text-sm text-slate-400">{t('auth.or')}</span>
                                    </div>
                                </div>

                                {/* Email Form */}
                                <form onSubmit={handleEmailAuth} className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('auth.email')}</label>
                                        <div className="relative">
                                            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                            <input
                                                type="email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                placeholder={t('auth.emailPlaceholder')}
                                                required
                                                className="w-full h-12 pl-12 pr-4 rounded-xl bg-slate-800 text-white placeholder:text-slate-500 focus:ring-0 outline-none transition-all"
                                            />
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('auth.password')}</label>
                                        <div className="relative">
                                            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                            <input
                                                type={showPassword ? 'text' : 'password'}
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                placeholder={t('auth.passwordPlaceholder')}
                                                required
                                                minLength={6}
                                                className="w-full h-12 pl-12 pr-12 rounded-xl bg-slate-800 text-white placeholder:text-slate-500 focus:ring-0 outline-none transition-all"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                                            >
                                                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Confirm Password - only for register */}
                                    {view === 'register' && (
                                        <div>
                                            <label className="block text-sm font-medium text-slate-300 mb-1.5">{t('auth.confirmPassword')}</label>
                                            <div className="relative">
                                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                                                <input
                                                    type={showConfirmPassword ? 'text' : 'password'}
                                                    value={confirmPassword}
                                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                                    placeholder={t('auth.confirmPasswordPlaceholder')}
                                                    required
                                                    minLength={6}
                                                    className="w-full h-12 pl-12 pr-12 rounded-xl bg-slate-800 text-white placeholder:text-slate-500 focus:ring-0 outline-none transition-all"
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                                                >
                                                    {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className="w-full h-12 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                    >
                                        {loading ? (
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                        ) : (
                                            t('auth.continue')
                                        )}
                                    </button>
                                </form>

                                {/* Toggle */}
                                <p className="text-center text-sm text-slate-500 mt-6">
                                    {view === 'login' ? (
                                        <>
                                            {t('auth.noAccount')}
                                            <button
                                                onClick={() => { setView('register'); resetState(); }}
                                                className="text-slate-300 hover:text-white font-medium ml-1"
                                            >
                                                {t('auth.signUp')}
                                            </button>
                                        </>
                                    ) : (
                                        <>
                                            {t('auth.hasAccount')}
                                            <button
                                                onClick={() => { setView('login'); resetState(); }}
                                                className="text-slate-300 hover:text-white font-medium ml-1"
                                            >
                                                {t('auth.signIn')}
                                            </button>
                                        </>
                                    )}
                                </p>

                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default AuthModal
