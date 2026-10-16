import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: 'localhost',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api/v1': {
          // The integrated API owns the private study/model volumes. The native
          // diagnostic API on :8000 does not have those files.
          target: process.env.API_PROXY_TARGET || env.API_PROXY_TARGET || 'http://localhost:18000',
          // Preserve Host/Origin: the API checks the browser's allowed origin.
          changeOrigin: false,
        },
      },
    },
    preview: { host: 'localhost', port: 5173, strictPort: true },
  };
});
