/* eslint-env node */
import { configure } from 'quasar/wrappers'

export default configure(function (/* ctx */) {
  return {
    boot: ['pinia'],

    css: ['app.scss'],

    extras: ['roboto-font', 'material-icons'],

    build: {
      target: { browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'] },
      vueRouterMode: 'history',
    },

    devServer: {
      open: false,
      proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
      },
    },

    framework: {
      config: {
        dark: 'auto',
        // Единая палитра: один зелёный цвет действия (как шапка),
        // красный — только для удаления и отмены. Цветные кнопки
        // «по разделам» (зелёная, синяя, оранжевая…) больше не используются.
        brand: {
          primary: '#2d6a4f',
          secondary: '#40916c',
          accent: '#b7791f',
          positive: '#2d6a4f',
          negative: '#c0392b',
          warning: '#e0a100',
          info: '#3a6ea5',
        },
      },
      plugins: ['Notify', 'Dialog', 'Loading', 'LocalStorage'],
    },

    pwa: {
      workboxMode: 'generateSW',
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
      useCredentialsForManifestTag: false,
      manifest: {
        name: 'СНТ Платформа',
        short_name: 'СНТ',
        description: 'Управление садоводческим товариществом',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#ffffff',
        theme_color: '#4CAF50',
        icons: [
          { src: 'icons/icon-128x128.png', sizes: '128x128', type: 'image/png' },
          { src: 'icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-256x256.png', sizes: '256x256', type: 'image/png' },
          { src: 'icons/icon-384x384.png', sizes: '384x384', type: 'image/png' },
          { src: 'icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    },

    ssr: { pwa: false },
    capacitor: {},
    electron: {},
    bex: {},
  }
})
