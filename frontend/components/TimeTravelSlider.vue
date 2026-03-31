<template>
  <Transition name="slider-slide">
    <div
      v-if="store.diffMode"
      class="time-travel-bar absolute bottom-7 left-0 right-0 z-40 flex h-10 items-center gap-3 border-t border-white/[0.06] bg-[#0a0a14]/95 backdrop-blur-sm px-5"
    >
      <!-- Play/pause button -->
      <button
        class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.04] text-gray-400 hover:text-white hover:bg-white/[0.08] transition-all"
        :title="isPlaying ? 'Pause' : 'Play (animate before → after)'"
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

      <!-- Before label -->
      <div class="shrink-0 text-right" style="min-width: 80px;">
        <span class="text-[10px] font-mono text-gray-600 tracking-wide">{{ fromLabel }}</span>
      </div>

      <!-- Slider track -->
      <div class="relative flex-1 flex items-center">
        <!-- Track background -->
        <div class="absolute inset-x-0 h-1 rounded-full bg-white/[0.06]" />

        <!-- Filled portion (before side = red, after side = green) -->
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

        <!-- Tick marks at 0%, 25%, 50%, 75%, 100% -->
        <div
          v-for="tick in [0, 0.25, 0.5, 0.75, 1]"
          :key="tick"
          class="absolute top-1/2 h-2 w-px -translate-y-1/2"
          :class="tick === 0.5 ? 'bg-white/[0.2]' : 'bg-white/[0.08]'"
          :style="{ left: `${tick * 100}%` }"
        />

        <!-- Hidden native range input for accessibility and drag -->
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          class="slider-input absolute inset-0 w-full opacity-0 cursor-pointer h-full"
          :value="store.diffSlider"
          @input="onSliderInput"
        />

        <!-- Visible thumb -->
        <div
          class="pointer-events-none absolute h-4 w-4 -translate-x-1/2 -translate-y-0 rounded-full border-2 border-white/50 bg-[#1a1a2e] shadow-lg transition-[left] duration-75"
          :style="{ left: `${store.diffSlider * 100}%` }"
        >
          <div class="absolute inset-0.5 rounded-full" :style="{ backgroundColor: thumbColor }" />
        </div>
      </div>

      <!-- After label -->
      <div class="shrink-0 text-left" style="min-width: 80px;">
        <span class="text-[10px] font-mono text-gray-600 tracking-wide">{{ toLabel }}</span>
      </div>

      <!-- Current position indicator -->
      <div class="shrink-0 w-14 text-center">
        <span
          class="text-[11px] font-mono font-semibold tabular-nums"
          :style="{ color: thumbColor }"
        >{{ positionLabel }}</span>
      </div>

      <!-- Close diff mode -->
      <button
        class="shrink-0 flex h-6 w-6 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.04] text-gray-500 hover:text-gray-300 hover:bg-white/[0.08] transition-all"
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
  // Start from current position if near the end, otherwise from 0
  if (store.diffSlider >= 0.98) store.setDiffSlider(0)
  playStartTime = performance.now() - store.diffSlider * PLAY_DURATION_MS

  function tick(now: number) {
    if (!isPlaying.value) return
    const elapsed = now - (playStartTime ?? now)
    const t = Math.min(1, elapsed / PLAY_DURATION_MS)
    store.setDiffSlider(t)
    if (t >= 1) {
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

function onSliderInput(e: Event) {
  stopPlay()
  const val = parseFloat((e.target as HTMLInputElement).value)
  store.setDiffSlider(val)
}

onUnmounted(() => {
  stopPlay()
})

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------

function formatTs(ts: string): string {
  if (!ts) return 'Before'
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

const fromLabel = computed(() => formatTs(store.metadata?.diff_from_scanned_at || ''))
const toLabel = computed(() => formatTs(store.metadata?.diff_to_scanned_at || ''))

const positionLabel = computed(() => {
  const v = store.diffSlider
  if (v <= 0.02) return 'Before'
  if (v >= 0.98) return 'After'
  return `${Math.round(v * 100)}%`
})

const thumbColor = computed(() => {
  const v = store.diffSlider
  // Lerp from red (#ef4444) through grey (#6b7280) to green (#22c55e)
  if (v <= 0.5) {
    // red → grey
    const t = v * 2
    const r = Math.round(239 + (107 - 239) * t)
    const g = Math.round(68 + (114 - 68) * t)
    const b = Math.round(68 + (128 - 68) * t)
    return `rgb(${r},${g},${b})`
  } else {
    // grey → green
    const t = (v - 0.5) * 2
    const r = Math.round(107 + (34 - 107) * t)
    const g = Math.round(114 + (197 - 114) * t)
    const b = Math.round(128 + (94 - 128) * t)
    return `rgb(${r},${g},${b})`
  }
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

/* Style the native range input to be invisible but fully interactive */
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
