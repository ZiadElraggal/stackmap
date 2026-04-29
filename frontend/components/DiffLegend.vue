<template>
  <Transition name="fade">
    <div v-if="store.diffMode && summary" class="diff-legend">
      <button class="legend-chip legend-chip--added" @click="store.setShowOnlyChanges(!store.showOnlyChanges)">
        <span class="legend-dot" /> {{ summary.added }} added
      </button>
      <button class="legend-chip legend-chip--removed" @click="store.setShowOnlyChanges(!store.showOnlyChanges)">
        <span class="legend-dot" /> {{ summary.removed }} removed
      </button>
      <button class="legend-chip legend-chip--modified" @click="store.setShowOnlyChanges(!store.showOnlyChanges)">
        <span class="legend-dot" /> {{ summary.modified }} changed
      </button>
      <button
        v-if="store.timelineDiffs.length > 0"
        class="legend-chip"
        title="Jump to next changed resource"
        @click="store.jumpToNextTimelineChange()"
      >
        Jump
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const summary = computed(() => store.diffSummary || store.activeTimelineDiff?.summary || null)
</script>

<style scoped>
.diff-legend {
  position: fixed;
  bottom: 84px;
  left: 50%;
  z-index: 42;
  display: flex;
  transform: translateX(-50%);
  gap: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(10, 10, 20, 0.92);
  padding: 6px;
  backdrop-filter: blur(12px);
}

.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(245, 245, 247, 0.72);
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  padding: 4px 8px;
}

.legend-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
}

.legend-chip--added { color: #22c55e; }
.legend-chip--removed { color: #ef4444; }
.legend-chip--modified { color: #f59e0b; }

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
