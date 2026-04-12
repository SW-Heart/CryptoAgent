import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

if (!supabaseUrl || !supabaseAnonKey) {
    console.warn('Supabase 配置缺失，请设置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY 环境变量')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
