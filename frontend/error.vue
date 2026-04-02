<template>
  <div class="min-h-screen w-screen bg-[#0a0a0f] text-white flex items-center justify-center px-6">
    <div class="max-w-md rounded-3xl border border-white/[0.06] bg-white/[0.02] px-8 py-9 text-center shadow-[0_30px_80px_rgba(0,0,0,0.35)] backdrop-blur-sm">
      <div class="flex justify-center mb-5">
        <PixelMascot :size="88" state="idle" :animate="true" />
      </div>
      <p class="text-[11px] uppercase tracking-[0.22em] text-gray-600 font-mono mb-3">StackMap Prism</p>
      <h1 class="text-2xl font-semibold tracking-tight text-gray-100 mb-2">
        {{ title }}
      </h1>
      <p class="text-sm text-gray-400 font-mono leading-6 mb-6">
        {{ description }}
      </p>
      <div class="flex items-center justify-center gap-3">
        <button
          class="rounded-xl border border-cyan-400/20 bg-cyan-500/10 px-4 py-2 text-sm font-mono text-cyan-300 transition hover:bg-cyan-500/15"
          @click="handleError"
        >
          Return to map
        </button>
        <NuxtLink
          to="/"
          class="rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2 text-sm font-mono text-gray-300 transition hover:bg-white/[0.06]"
        >
          Reload root
        </NuxtLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  error: {
    statusCode?: number
    statusMessage?: string
    message?: string
  }
}>()

const title = computed(() => {
  if (props.error?.statusCode === 404) return 'Map not found'
  return props.error?.statusMessage || 'Something went sideways'
})

const description = computed(() => {
  if (props.error?.message) return props.error.message
  if (props.error?.statusCode === 404) return 'Prism could not find the requested view. The route may be stale or the graph has not loaded yet.'
  return 'StackMap hit an unexpected UI error while preparing the view.'
})
</script>
