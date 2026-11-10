import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Plain Vite + React. Firebase settings are read from VITE_FIREBASE_* variables
// (see .env.example) or from src/config/firebase.config.json (see README).
export default defineConfig({
  plugins: [react()],
  server: { host: '0.0.0.0', port: 3000 },
  build: { target: 'es2020', sourcemap: false, chunkSizeWarningLimit: 900 },
  test: { environment: 'node', include: ['tests/**/*.test.{ts,tsx}'] }
});
