import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  base: './',
  root: 'src/renderer',
  build: {
    outDir: '../../dist',
    emptyOutDir: true
  },
  publicDir: '../../assets',
  resolve: {
    alias: {
      '@assets': path.resolve(__dirname, './assets')
    }
  }
});