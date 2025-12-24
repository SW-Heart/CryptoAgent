import React, { createContext, useContext, useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'

const AuthContext = createContext({})

export const useAuth = () => {
    const context = useContext(AuthContext)
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null)
    const [loading, setLoading] = useState(true)
    const [session, setSession] = useState(null)

    useEffect(() => {
        // 获取初始会话
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session)
            setUser(session?.user ?? null)
            setLoading(false)
        })

        // 监听认证状态变化
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event, session) => {
                setSession(session)
                setUser(session?.user ?? null)
                setLoading(false)
            }
        )

        return () => subscription.unsubscribe()
    }, [])

    // 邮箱注册
    const signUp = async (email, password) => {
        const { data, error } = await supabase.auth.signUp({
            email,
            password,
        })
        return { data, error }
    }

    // 邮箱登录
    const signIn = async (email, password) => {
        const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password,
        })
        return { data, error }
    }

    // 验证邮箱验证码 (OTP)
    const verifyOtp = async (email, token) => {
        const { data, error } = await supabase.auth.verifyOtp({
            email,
            token,
            type: 'signup',
        })
        return { data, error }
    }

    // Google OAuth 登录
    const signInWithGoogle = async () => {
        const { data, error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: window.location.origin,
            },
        })
        return { data, error }
    }

    // Web3 钱包登录 (MetaMask)
    const signInWithWallet = async () => {
        if (typeof window.ethereum === 'undefined') {
            return { data: null, error: { message: 'Please install MetaMask wallet extension' } }
        }

        try {
            // 请求连接钱包
            const accounts = await window.ethereum.request({
                method: 'eth_requestAccounts',
            })
            const address = accounts[0]

            // 使用 Supabase Web3 登录
            const { data, error } = await supabase.auth.signInWithWeb3({
                chain: 'ethereum',
                statement: 'Sign in to Alpha Crypto Agent',
            })

            return { data, error }
        } catch (err) {
            // 如果 Supabase Web3 不可用，使用自定义签名验证作为备选
            try {
                const accounts = await window.ethereum.request({
                    method: 'eth_requestAccounts',
                })
                const address = accounts[0]

                // 创建签名消息
                const message = `Sign in to Alpha Crypto Agent\n\nWallet: ${address}\nTime: ${new Date().toISOString()}`

                // 请求签名
                const signature = await window.ethereum.request({
                    method: 'personal_sign',
                    params: [message, address],
                })

                // 使用钱包地址作为邮箱的替代方案（临时方案）
                // 注意：这里使用钱包地址生成一个唯一用户
                const walletEmail = `${address.toLowerCase()}@wallet.local`
                const walletPassword = signature.slice(0, 72) // 使用签名的一部分作为密码

                // 尝试登录，如果失败则注册
                let { data, error } = await supabase.auth.signInWithPassword({
                    email: walletEmail,
                    password: walletPassword,
                })

                if (error) {
                    // 用户不存在，创建新用户
                    const signUpResult = await supabase.auth.signUp({
                        email: walletEmail,
                        password: walletPassword,
                        options: {
                            data: {
                                wallet_address: address,
                                auth_type: 'wallet',
                            },
                        },
                    })
                    data = signUpResult.data
                    error = signUpResult.error
                }

                return { data, error }
            } catch (walletErr) {
                return { data: null, error: { message: walletErr.message || 'Wallet connection failed' } }
            }
        }
    }

    // 退出登录
    const signOut = async () => {
        const { error } = await supabase.auth.signOut()
        return { error }
    }

    const value = {
        user,
        session,
        loading,
        signUp,
        signIn,
        verifyOtp,
        signInWithGoogle,
        signInWithWallet,
        signOut,
    }

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    )
}

export default AuthContext
