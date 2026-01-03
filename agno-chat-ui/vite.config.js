import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // 提高警告阈值到 700KB，因为某些库本身就很大
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心
          'vendor-react': ['react', 'react-dom'],
          // Markdown 渲染相关
          'vendor-markdown': ['react-markdown', 'remark-gfm'],
          // 代码高亮（体积较大，单独分离）
          'vendor-syntax': ['react-syntax-highlighter'],
          // UI 图标库
          'vendor-icons': ['lucide-react'],
          // 国际化
          'vendor-i18n': ['i18next', 'react-i18next'],
          // 其他工具库
          'vendor-utils': ['uuid', 'html2canvas'],
        }
      }
    }
  },
  server: {
    proxy: {
      '/agents': {
        // 🔴 之前是 7777，现在改成 8000
        // ✅ 保持使用 127.0.0.1 以防 IPv6 问题
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})