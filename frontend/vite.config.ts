import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api/v1': {
          target: process.env.API_PROXY_TARGET || env.API_PROXY_TARGET || 'http://localhost:8000',
          // Preserve Host/Origin: the API checks the browser's allowed origin.
          changeOrigin: false,
        },
      },
    },
    preview: { host: '0.0.0.0', port: 5173, strictPort: true },
  };
});
