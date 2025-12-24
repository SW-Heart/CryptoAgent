import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/agents': {
        // 🔴 之前是 7777，现在改成 8000
        // ✅ 保持使用 127.0.0.1 以防 IPv6 问题
        target: 'http://127.0.0.1:8000', 
        changeOrigin: true,
        secure: false,
      },
    },
  },
})