import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  build: {
    // Served as plain static files by the existing nginx, so no base path
    // trickery and no server runtime.
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Keep the framework in its own chunk so page code can change often
        // without busting the biggest cached asset.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          motion: ['framer-motion'],
        },
      },
    },
  },
});
