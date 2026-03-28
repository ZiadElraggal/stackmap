export default defineNuxtConfig({
  compatibilityDate: '2025-03-01',
  devtools: { enabled: true },
  modules: [
    '@pinia/nuxt',
    '@nuxtjs/tailwindcss',
  ],
  ssr: false,
  app: {
    head: {
      title: 'StackMap',
      meta: [
        { name: 'description', content: 'Architecture diagrams that generate themselves' }
      ]
    }
  }
})
