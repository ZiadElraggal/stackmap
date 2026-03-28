import type { Config } from 'tailwindcss'

export default {
  content: [
    './components/**/*.{vue,ts}',
    './composables/**/*.ts',
    './layouts/**/*.vue',
    './pages/**/*.vue',
    './app.vue',
  ],
  theme: {
    extend: {
      colors: {
        canvas: {
          bg: '#0a0a0f',
          panel: '#12121a',
        }
      }
    },
  },
} satisfies Config
