import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  base: './',
  root: 'src/renderer',
  build: {
    outDir: '../../dist',
    emptyOutDir: true,
    assetsInclude: ['**/*.glb', '**/*.png']
  },
  publicDir: 'public',
  resolve: {
    alias: {
      '@assets': path.resolve(__dirname, './assets'),
      'three': path.resolve(__dirname, 'node_modules/three')
    }
  }
});