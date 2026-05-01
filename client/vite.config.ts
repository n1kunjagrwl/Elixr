import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // Activate new service worker immediately without waiting for all tabs to close.
      injectRegister: 'auto',
      workbox: {
        skipWaiting: true,
        clientsClaim: true,
        // Always fetch HTML from network first so a new deploy is picked up
        // immediately — avoids serving stale JS chunk URLs from cache.
        runtimeCaching: [
          {
            urlPattern: ({ request }: { request: Request }) => request.mode === 'navigate',
            handler: 'NetworkFirst' as const,
            options: {
              cacheName: 'pages-cache',
              networkTimeoutSeconds: 3,
            },
          },
        ],
      },
      includeAssets: ['icons/*.png'],
      manifest: {
        name: 'Elixir — Personal Finance',
        short_name: 'Elixir',
        description: 'Personal finance tracker for India',
        theme_color: '#0891b2',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Bind to IPv6 wildcard (::). With macOS dual-stack (v6only=0) this also
    // accepts IPv4 connections on 127.0.0.1, fixing Safari's localhost resolution.
    host: '::',
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
