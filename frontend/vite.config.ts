import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { readFileSync } from 'node:fs'
import { VitePWA } from 'vite-plugin-pwa'

// When running inside Docker (docker-compose), the api-proxy is reachable
// via its service name.  Outside Docker (npm run dev on the host), it is
// reachable via the published port on localhost.
// Set VITE_PROXY_TARGET in the environment to override.
const PROXY_TARGET = process.env.VITE_PROXY_TARGET ?? 'http://localhost:18002'

export default defineConfig({
  plugins: [
    // Intercept /dev-sw.js before Vite's SPA fallback so the browser gets the
    // actual service worker script instead of index.html.  VitePWA's own virtual
    // middleware does not fire reliably inside Docker (volume-mounted dev server),
    // so we short-circuit it here with a direct read from dev-dist/sw.js.
    {
      name: 'dev-sw-serve',
      apply: 'serve',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // Match /dev-sw.js with or without the ?dev-sw query string
          if (req.url && req.url.split('?')[0] === '/dev-sw.js') {
            const swFile = path.resolve(__dirname, 'dev-dist/sw.js')
            try {
              const content = readFileSync(swFile, 'utf-8')
              res.setHeader('Content-Type', 'application/javascript; charset=utf-8')
              res.setHeader('Service-Worker-Allowed', '/')
              res.statusCode = 200
              res.end(content)
            } catch {
              next()
            }
            return
          }
          next()
        })
      },
    },
    react(),
    VitePWA({
      registerType: 'autoUpdate',

      // Dev: enable SW in development so installability can be tested locally
      devOptions: {
        enabled: true,
        type: 'classic',
      },

      // Workbox options — app-shell caching ONLY
      workbox: {
        // Cache app-shell routes (HTML navigation requests)
        navigateFallback: '/index.html',

        // Do NOT cache these — they must always hit the network
        navigateFallbackDenylist: [
          /^\/api\//,
          /^\/ws\//,
          /^\/socket\.io\//,
        ],

        // Static asset caching strategies
        runtimeCaching: [
          {
            // Google Fonts stylesheets
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Google Fonts webfonts
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],

        // Vite build assets — cache-first (they have content hashes)
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],

        // Never precache API / WS endpoints
        globIgnores: ['**/api/**', '**/ws/**', '**/socket.io/**'],

        // Keep SW slim — skip waiting and claim clients immediately on update
        skipWaiting: true,
        clientsClaim: true,
      },

      // Web App Manifest
      manifest: {
        name: 'Fear Allah Operations',
        short_name: 'FearAllah',
        description: 'Operational platform for Fear Allah business management',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait-primary',
        theme_color: '#313338',
        background_color: '#313338',
        lang: 'en',
        categories: ['business', 'productivity'],
        icons: [
          {
            src: '/pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any',
          },
          {
            src: '/maskable-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: '/maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
        shortcuts: [
          {
            name: 'Sales',
            short_name: 'Sales',
            description: 'View sales dashboard',
            url: '/sales',
            icons: [{ src: '/pwa-192x192.png', sizes: '192x192' }],
          },
          {
            name: 'Orders',
            short_name: 'Orders',
            description: 'View orders',
            url: '/orders',
            icons: [{ src: '/pwa-192x192.png', sizes: '192x192' }],
          },
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
    host: '0.0.0.0',
    port: 3000,
    // Allow any external host (ngrok, LAN, etc.) — dev only, not used in prod build
    allowedHosts: true,
    // No hmr.host — Vite's client uses window.location.hostname automatically,
    // which resolves to the correct IP for both localhost and LAN (mobile).
    // Setting hmr.host:'0.0.0.0' tells the browser to connect to 0.0.0.0
    // which is never a valid browser target → ERR_ADDRESS_INVALID.
    hmr: {
      clientPort: 3000,
    },
    proxy: {
      '/api': {
        target: PROXY_TARGET,
        changeOrigin: true,
      },
      '/ws': {
        target: PROXY_TARGET,
        ws: true,
      },
      '/socket.io': {
        target: PROXY_TARGET,
        ws: true,
      },
    },
  },
})
