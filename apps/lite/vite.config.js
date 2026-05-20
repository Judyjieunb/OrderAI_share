import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// order-ai-share: 로컬 운영 기본. Nginx 뒤단 마운트가 필요하면
// VITE_BASE_PATH 환경변수로 base 를 override.
const BASE_PATH = process.env.VITE_BASE_PATH || '/'

export default defineConfig({
  base: BASE_PATH,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 로컬 dev: vite(5173) → FastAPI(8000) 프록시.
      // 백엔드는 `uvicorn server.api:app --port 8000` 로 기동.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
