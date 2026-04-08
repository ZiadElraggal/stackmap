<template>
  <div class="w-screen h-screen bg-[#0a0a0f] text-white overflow-hidden">
    <!-- Loading state -->
    <Transition name="fade-slow">
      <div
        v-if="!loaded"
        class="absolute inset-0 z-[200] flex items-center justify-center bg-[#0a0a0f]"
      >
        <div class="flex flex-col items-center gap-5 rounded-3xl border border-white/[0.06] bg-[#12121a]/80 px-10 py-8 shadow-[0_24px_64px_rgba(0,0,0,0.55)] backdrop-blur-2xl">
          <PixelMascot :size="80" state="scanning" :animate="true" />
          <div class="flex flex-col items-center gap-1.5">
            <span class="text-sm font-light tracking-wide" style="color: var(--sm-text)">Loading infrastructure map...</span>
            <span class="text-[10px] font-mono tracking-[0.22em] uppercase" style="color: var(--sm-primary, #4ADE80); opacity: 0.6">StackMap Prism</span>
          </div>
          <div class="h-0.5 w-24 overflow-hidden rounded-full bg-white/5">
            <div class="h-full w-full origin-left animate-pulse rounded-full" style="background: linear-gradient(90deg, transparent, var(--sm-primary), transparent)" />
          </div>
        </div>
      </div>
    </Transition>

    <FilterSidebar v-if="!store.presentationMode" />
    <Canvas ref="canvasRef" @toggle-command-palette="cmdRef?.toggle()" />
    <TimeTravelSlider v-if="!store.presentationMode" />
    <DetailPanel v-if="!store.presentationMode" />
    <CommandPalette v-if="!store.presentationMode" ref="cmdRef" @pan-to="onPanTo" @fit-to-screen="onFit" />
    <EditToolbar v-if="!store.presentationMode" />
    <DriftSummaryBar v-if="!store.presentationMode" />

    <!-- Empty state overlay -->
    <Transition name="fade">
      <div
        v-if="loaded && isEmpty"
        class="absolute inset-0 z-30 flex items-center justify-center pointer-events-none"
      >
        <div class="flex flex-col items-center gap-4 pointer-events-auto rounded-3xl border border-white/[0.06] bg-[#12121a]/80 px-10 py-8 shadow-[0_24px_64px_rgba(0,0,0,0.55)] backdrop-blur-2xl">
          <PixelMascot :size="84" state="idle" :animate="true" />
          <p class="text-sm font-light" style="color: var(--sm-text-muted)">No resources found</p>
          <p class="text-xs max-w-xs text-center leading-relaxed" style="color: rgba(245,245,247,0.35)">
            Run <code class="px-1.5 py-0.5 rounded" style="color: var(--sm-primary); background: rgba(74,222,128,0.08)">stackmap scan</code> or <code class="px-1.5 py-0.5 rounded" style="color: var(--sm-primary); background: rgba(74,222,128,0.08)">stackmap scan-repo</code> to generate an infrastructure map.
          </p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const canvasRef = ref<{ fitToViewport: () => void; panToNode: (id: string) => void }>()
const cmdRef = ref<{ toggle: () => void }>()

const loaded = computed(() => store.loaded)
const isEmpty = computed(() => store.loaded && store.nodes.length === 0)

function onPanTo(nodeId: string) {
  canvasRef.value?.panToNode(nodeId)
}
function onFit() {
  canvasRef.value?.fitToViewport()
}
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  /* StackMap Design Tokens */
  --sm-bg: #0a0a0f;
  --sm-surface: #12121a;
  --sm-surface-raised: #16161f;
  --sm-border: rgba(255, 255, 255, 0.06);
  --sm-border-hover: rgba(255, 255, 255, 0.10);
  --sm-border-subtle: rgba(255, 255, 255, 0.04);
  --sm-primary: #4ADE80;
  --sm-primary-glow: rgba(74, 222, 128, 0.15);
  --sm-secondary: #38BDF8;
  --sm-tertiary: #C084FC;
  --sm-warning: #FB923C;
  --sm-danger: #ef4444;
  --sm-danger-muted: rgba(239, 68, 68, 0.6);
  --sm-text: #f5f5f7;
  --sm-text-muted: rgba(245, 245, 247, 0.5);
  --sm-text-faint: rgba(245, 245, 247, 0.3);
  --sm-terminal-bg: #0d0d14;
  --sm-spacing-unit: 8px;
  --sm-radius-sm: 6px;
  --sm-radius-md: 10px;
  --sm-radius-lg: 16px;
  --sm-transition-fast: 120ms ease-out;
  --sm-transition-normal: 180ms ease-out;
  --sm-shadow-panel: 0 1px 3px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.03);
  --sm-shadow-elevated: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.04);
  --sm-shadow-overlay: 0 24px 64px rgba(0, 0, 0, 0.55);
}

html, body {
  margin: 0;
  padding: 0;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif;
  letter-spacing: -0.01em;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code, .font-mono {
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
}

::-webkit-scrollbar {
  width: 5px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.06);
  border-radius: 980px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.12);
}

/* Glassmorphic panel base */
.glass-panel {
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid var(--sm-border);
}

.fade-slow-enter-active { transition: opacity 0.3s cubic-bezier(0.25, 0.1, 0.25, 1); }
.fade-slow-leave-active { transition: opacity 0.6s cubic-bezier(0.25, 0.1, 0.25, 1); }
.fade-slow-enter-from, .fade-slow-leave-to { opacity: 0; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s cubic-bezier(0.25, 0.1, 0.25, 1); }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
