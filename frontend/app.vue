<template>
  <div class="w-screen h-screen bg-[#0a0a0f] text-white overflow-hidden">
    <!-- Loading state -->
    <Transition name="fade-slow">
      <div
        v-if="!loaded"
        class="absolute inset-0 z-[200] flex items-center justify-center bg-[#0a0a0f]"
      >
        <div class="flex flex-col items-center gap-4">
          <div class="loading-ring" />
          <span class="text-sm text-gray-500 font-mono tracking-wide">Loading infrastructure map...</span>
        </div>
      </div>
    </Transition>

    <FilterSidebar />
    <Canvas ref="canvasRef" @toggle-command-palette="cmdRef?.toggle()" />
    <TimeTravelSlider />
    <DetailPanel />
    <CommandPalette ref="cmdRef" @pan-to="onPanTo" @fit-to-screen="onFit" />

    <!-- Empty state overlay -->
    <Transition name="fade">
      <div
        v-if="loaded && isEmpty"
        class="absolute inset-0 z-30 flex items-center justify-center pointer-events-none"
      >
        <div class="flex flex-col items-center gap-3 pointer-events-auto">
          <div class="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center text-gray-600">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <path d="M9 9l6 6M15 9l-6 6" />
            </svg>
          </div>
          <p class="text-sm text-gray-500 font-mono">No resources found</p>
          <p class="text-xs text-gray-600 font-mono max-w-xs text-center">
            Run <code class="text-gray-400">stackmap scan</code> or <code class="text-gray-400">stackmap scan-repo</code> to generate an infrastructure map.
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body {
  margin: 0;
  padding: 0;
  overflow: hidden;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.15);
}

.loading-ring {
  width: 40px;
  height: 40px;
  border: 2px solid rgba(255,255,255,0.06);
  border-top-color: rgba(96, 165, 250, 0.6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.fade-slow-enter-active { transition: opacity 0.3s ease; }
.fade-slow-leave-active { transition: opacity 0.6s ease; }
.fade-slow-enter-from, .fade-slow-leave-to { opacity: 0; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
