import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 局域网模式：前端监听 0.0.0.0，手机扫码后可访问；API 代理到本地后端。
// 用法：npm run dev:lan   （后端端口由 LAN_API 决定，默认 8001）
const LAN_API = process.env.LAN_API || 'http://127.0.0.1:8001'
const LAN_PORT = Number(process.env.LAN_PORT || 5174)

const proxy = {
  '/api': { target: LAN_API, changeOrigin: true },
  '/api/uploads': { target: LAN_API, changeOrigin: true },
  '/uploads': { target: LAN_API, changeOrigin: true },
  '/ws': { target: LAN_API, changeOrigin: true, ws: true },
}

export default defineConfig({
  plugins: [vue()],
  base: '/',
  resolve: {
    alias: { '@': resolve(__dirname, 'src') }
  },
  server: {
    host: '0.0.0.0',
    port: LAN_PORT,
    strictPort: true,
    proxy,
  },
  preview: {
    host: '0.0.0.0',
    port: LAN_PORT,
    strictPort: true,
    proxy,
  },
})
