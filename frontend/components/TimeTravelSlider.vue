<template>
  <Transition name="slider-slide">
    <div
      v-if="store.diffMode"
      class="time-travel-bar absolute bottom-7 left-0 right-0 z-40 flex h-10 items-center gap-3 border-t border-white/[0.06] bg-[#0a0a14]/95 px-5 backdrop-blur-sm"
    >
      <button
        class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.04] text-gray-400 transition-all hover:bg-white/[0.08] hover:text-white"
        :title="isPlaying ? 'Pause' : 'Play (animate before to after)'"
        @click="togglePlay"
      >
        <svg v-if="!isPlaying" width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <path d="M2 1.5l7 3.5-7 3.5V1.5z" />
        </svg>
        <svg v-else width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
          <rect x="1.5" y="1.5" width="3" height="7" rx="0.5" />
          <rect x="5.5" y="1.5" width="3" height="7" rx="0.5" />
        </svg>
      </button>

      <div class="shrink-0 text-right" style="min-width: 96px;">
        <span class="text-[10px] font-mono tracking-wide text-gray-600">{{ fromLabel }}</span>
      </div>

      <div class="relative flex flex-1 items-center">
        <div class="absolute inset-x-0 h-1 rounded-full bg-white/[0.06]" />
        <div
          class="absolute left-0 h-1 rounded-l-full"
          style="background: linear-gradient(90deg, #ef4444, #6b7280);"
          :style="{ width: `${store.diffSlider * 100}%` }"
        />
        <div
          class="absolute h-1 rounded-r-full"
          style="background: linear-gradient(90deg, #6b7280, #22c55e);"
          :style="{ left: `${store.diffSlider * 100}%`, right: '0' }"
        />

        <div
          v-for="tick in [0, 0.25, 0.5, 0.75, 1]"
          :key="tick"
          class="absolute top-1/2 h-2 w-px -translate-y-1/2"
          :class="tick === 0.5 ? 'bg-white/[0.2]' : 'bg-white/[0.08]'"
          :style="{ left: `${tick * 100}%` }"
        />

        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          class="slider-input absolute inset-0 h-full w-full cursor-pointer opacity-0"
          :value="store.diffSlider"
          @input="onSliderInput"
        />

        <div
          class="pointer-events-none absolute h-4 w-4 -translate-x-1/2 rounded-full border-2 border-white/50 bg-[#1a1a2e] shadow-lg transition-[left] duration-75"
          :style="{ left: `${store.diffSlider * 100}%` }"
        >
          <div class="absolute inset-0.5 rounded-full" :style="{ backgroundColor: thumbColor }" />
        </div>
      </div>

      <div class="shrink-0 text-left" style="min-width: 96px;">
        <span class="text-[10px] font-mono tracking-wide text-gray-600">{{ toLabel }}</span>
      </div>

      <div class="shrink-0 w-14 text-center">
        <span class="text-[11px] font-mono font-semibold tabular-nums" :style="{ color: thumbColor }">
          {{ positionLabel }}
        </span>
      </div>

      <button
        class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.04] text-gray-500 transition-all hover:bg-white/[0.08] hover:text-gray-300"
        title="Exit diff mode"
        @click="store.setDiffMode(false)"
      >
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M1 1l6 6M7 1L1 7" />
        </svg>
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()
const isPlaying = ref(false)
let playRafId: number | null = null
let playStartTime: number | null = null
const PLAY_DURATION_MS = 3000

function togglePlay() {
  if (isPlaying.value) {
    stopPlay()
  } else {
    startPlay()
  }
}

function startPlay() {
  isPlaying.value = true
  if (store.diffSlider >= 0.98) store.setDiffSlider(0)
  playStartTime = performance.now() - store.diffSlider * PLAY_DURATION_MS

  function tick(now: number) {
    if (!isPlaying.value) return
    const elapsed = now - (playStartTime ?? now)
    const nextValue = Math.min(1, elapsed / PLAY_DURATION_MS)
    store.setDiffSlider(nextValue)
    if (nextValue >= 1) {
      isPlaying.value = false
      playRafId = null
      return
    }
    playRafId = requestAnimationFrame(tick)
  }

  playRafId = requestAnimationFrame(tick)
}

function stopPlay() {
  isPlaying.value = false
  if (playRafId !== null) {
    cancelAnimationFrame(playRafId)
    playRafId = null
  }
}

function onSliderInput(event: Event) {
  stopPlay()
  const value = parseFloat((event.target as HTMLInputElement).value)
  store.setDiffSlider(value)
}

function formatTimestamp(value: string): string {
  if (!value) return 'Before'
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

const fromLabel = computed(() => formatTimestamp(store.metadata?.diff_from_scanned_at || ''))
const toLabel = computed(() => formatTimestamp(store.metadata?.diff_to_scanned_at || ''))

const positionLabel = computed(() => {
  if (store.diffSlider <= 0.02) return 'Before'
  if (store.diffSlider >= 0.98) return 'After'
  return `${Math.round(store.diffSlider * 100)}%`
})

const thumbColor = computed(() => {
  const value = store.diffSlider
  if (value <= 0.5) {
    const t = value * 2
    const r = Math.round(239 + (107 - 239) * t)
    const g = Math.round(68 + (114 - 68) * t)
    const b = Math.round(68 + (128 - 68) * t)
    return `rgb(${r},${g},${b})`
  }

  const t = (value - 0.5) * 2
  const r = Math.round(107 + (34 - 107) * t)
  const g = Math.round(114 + (197 - 114) * t)
  const b = Math.round(128 + (94 - 128) * t)
  return `rgb(${r},${g},${b})`
})

onUnmounted(() => {
  stopPlay()
})
</script>

<style scoped>
.slider-slide-enter-active,
.slider-slide-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.slider-slide-enter-from,
.slider-slide-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

.slider-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.slider-input::-moz-range-thumb {
  width: 20px;
  height: 20px;
  cursor: pointer;
  background: transparent;
  border: none;
}
</style>
