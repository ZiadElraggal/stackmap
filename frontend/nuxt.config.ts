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
      ]
    }
  }
})
