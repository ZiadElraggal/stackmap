export default defineNuxtConfig({
  compatibilityDate: '2023-01-01',
  devtools: { enabled: false },
  modules: [
    '@pinia/nuxt',
  ],
  css: ['~/assets/css/tailwind.css'],
  ssr: true,
  nitro: {
    preset: 'static',
  },
  postcss: {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  },
  app: {
    head: {
      title: 'StackMap',
      meta: [
        { name: 'description', content: 'Architecture diagrams that generate themselves' }
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/prism-head.svg' },
        { rel: 'apple-touch-icon', href: '/prism-head.svg' },
      ],
    }
  }
})
