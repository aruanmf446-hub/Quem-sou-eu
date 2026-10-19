import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Somente o build do GitHub Pages usa subpasta. O Vercel permanece na raiz.
  base: process.env.GITHUB_PAGES === 'true' ? '/Quem-sou-eu/' : '/',
  test: { environment: 'node' },
} as never);
