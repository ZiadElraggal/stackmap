<template>
  <div class="w-screen h-screen bg-[#0a0a0f] text-white overflow-hidden">
    <FilterSidebar />
    <Canvas ref="canvasRef" @toggle-command-palette="cmdRef?.toggle()" />
    <DetailPanel />
    <CommandPalette ref="cmdRef" @pan-to="onPanTo" @fit-to-screen="onFit" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const canvasRef = ref<{ fitToViewport: () => void; panToNode: (id: string) => void }>()
const cmdRef = ref<{ toggle: () => void }>()

function onPanTo(nodeId: string) {
  canvasRef.value?.panToNode(nodeId)
}
function onFit() {
  canvasRef.value?.fitToViewport()
}
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body {
  margin: 0;
  padding: 0;
  overflow: hidden;
  font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.2);
}
</style>
