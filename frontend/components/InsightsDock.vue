<template>
  <div class="insights-dock" :class="{ 'insights-dock--panel-open': panelOpen }">
    <button
      class="dock-btn"
      :class="{ active: store.showCosts }"
      title="Cost & usage"
      @click="store.toggleCosts()"
    >
      <span class="dock-icon">$</span>
      <span class="dock-label">Cost</span>
    </button>

    <button
      v-if="store.logsAvailable"
      class="dock-btn"
      :class="{ active: store.showLogs }"
      title="CloudWatch live logs"
      @click="store.toggleLogs()"
    >
      <span class="dock-icon">≋</span>
      <span class="dock-label">Logs</span>
    </button>

    <button
      v-if="store.metadata?.drift_summary"
      class="dock-btn"
      :class="{ active: store.driftMode }"
      title="Drift analysis"
      @click="store.setDriftMode(!store.driftMode)"
    >
      <span class="dock-icon">⚠</span>
      <span class="dock-label">Drift</span>
    </button>

    <button
      v-if="store.findings.length > 0"
      class="dock-btn"
      :class="{ active: showFindings }"
      :title="`${store.findings.length} findings`"
      @click="showFindings = !showFindings"
    >
      <span class="dock-icon">◈</span>
      <span class="dock-label">Findings</span>
      <span class="dock-badge">{{ store.findings.length }}</span>
    </button>

    <button
      v-if="store.availableProfiles.length > 0"
      class="dock-btn"
      title="AWS profile"
      @click="showProfiles = !showProfiles"
    >
      <span class="dock-icon">id</span>
      <span class="dock-label">{{ store.activeProfile || 'Profile' }}</span>
    </button>

    <!-- Findings flyout -->
    <Transition name="flyout">
      <div v-if="showFindings && store.findings.length > 0" class="findings-flyout">
        <FindingsPanel />
      </div>
    </Transition>

    <Transition name="flyout">
      <div v-if="showProfiles && store.availableProfiles.length > 0" class="findings-flyout profile-flyout">
        <ProfileSwitcher />
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'
import FindingsPanel from './FindingsPanel.vue'
import ProfileSwitcher from './ProfileSwitcher.vue'

const store = useGraphStore()
const showFindings = ref(false)
const showProfiles = ref(false)

const panelOpen = computed(
  () => !store.editorPanelCollapsed && (!!store.selectedNode || !!store.selectedEdge || store.editMode)
)

</script>

<style scoped>
.insights-dock {
  position: fixed;
  top: 72px;
  right: 16px;
  z-index: 990;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px;
  border: 1px solid var(--sm-border, rgba(255,255,255,0.06));
  border-radius: 12px;
  background: rgba(18, 18, 26, 0.85);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: var(--sm-shadow-panel, 0 1px 3px rgba(0,0,0,0.3));
  transition: right 0.2s ease;
}

.insights-dock--panel-open {
  right: calc(24rem + 16px);
}

.dock-btn {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 44px;
  padding: 6px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--sm-text-muted, rgba(245,245,247,0.55));
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.dock-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text, #e0e0e8);
}

.dock-btn.active {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.25);
  color: #4ade80;
}

.dock-icon {
  font-size: 13px;
  font-weight: 700;
  width: 14px;
  text-align: center;
  opacity: 0.9;
}

.dock-label {
  letter-spacing: 0.04em;
}

.dock-badge {
  margin-left: auto;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(251, 146, 60, 0.18);
  color: #fdba74;
  font-size: 10px;
  font-weight: 600;
}

.findings-flyout {
  position: absolute;
  top: 0;
  right: calc(100% + 8px);
  width: min(320px, 90vw);
  max-height: 60vh;
  overflow-y: auto;
  border: 1px solid var(--sm-border, rgba(255,255,255,0.06));
  border-radius: 12px;
  background: rgba(18, 18, 26, 0.97);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: var(--sm-shadow-elevated, 0 8px 32px rgba(0,0,0,0.4));
  padding: 10px;
}


.flyout-enter-active,
.flyout-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.flyout-enter-from,
.flyout-leave-to {
  opacity: 0;
  transform: translateX(6px);
}

@media (max-width: 768px) {
  .insights-dock {
    top: auto;
    bottom: 16px;
    right: 16px;
    flex-direction: row;
  }
  .findings-flyout {
    top: auto;
    bottom: calc(100% + 8px);
    right: 0;
  }
}
</style>
