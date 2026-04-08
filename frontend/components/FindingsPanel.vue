<template>
  <div class="findings-panel" v-if="store.findings.length > 0">
    <div class="findings-header">
      <h3 class="findings-title">
        Findings
        <span class="findings-badge">{{ store.findings.length }}</span>
      </h3>
    </div>

    <div class="findings-list">
      <div
        v-for="group in groupedFindings"
        :key="group.severity"
        class="findings-severity-group"
      >
        <div class="severity-label" :class="`severity-${group.severity}`">
          {{ severityIcon(group.severity) }} {{ group.severity.toUpperCase() }}
          <span class="severity-count">({{ group.items.length }})</span>
        </div>
        <button
          v-for="finding in group.items"
          :key="finding.id"
          class="finding-item"
          :class="{ active: store.activeFindingFilter === finding.pattern_id }"
          @click="toggleFinding(finding)"
        >
          <div class="finding-title">{{ finding.title }}</div>
          <div class="finding-resources">
            {{ finding.node_ids.slice(0, 2).join(', ') }}
            <span v-if="finding.node_ids.length > 2"> +{{ finding.node_ids.length - 2 }}</span>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

interface Finding {
  id: string
  pattern_id: string
  title: string
  severity: string
  node_ids: string[]
}

const groupedFindings = computed(() => {
  const groups: Record<string, Finding[]> = {}
  const order = ['critical', 'warning', 'info']

  for (const f of store.findings) {
    if (!groups[f.severity]) groups[f.severity] = []
    groups[f.severity].push(f)
  }

  return order
    .filter(sev => groups[sev])
    .map(sev => ({ severity: sev, items: groups[sev] }))
})

function severityIcon(severity: string): string {
  switch (severity) {
    case 'critical': return '!'
    case 'warning': return '?'
    case 'info': return 'i'
    default: return '-'
  }
}

function toggleFinding(finding: Finding) {
  if (store.activeFindingFilter === finding.pattern_id) {
    store.setFindingFilter(null)
  } else {
    store.setFindingFilter(finding.pattern_id)
    // Select the first affected node
    if (finding.node_ids.length > 0) {
      store.selectNode(finding.node_ids[0])
    }
  }
}
</script>

<style scoped>
.findings-panel {
  padding: 12px 0;
  border-top: 1px solid var(--sm-border, #2a2a3a);
}

.findings-header {
  padding: 0 16px 8px;
}

.findings-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sm-text, #e0e0e8);
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.findings-badge {
  background: var(--sm-danger, #ef4444);
  color: white;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  font-weight: 600;
}

.findings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.severity-label {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 16px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.severity-critical { color: #ef4444; }
.severity-warning { color: #f59e0b; }
.severity-info { color: #3b82f6; }

.severity-count {
  font-weight: 400;
  opacity: 0.7;
}

.finding-item {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  padding: 6px 16px 6px 24px;
  cursor: pointer;
  color: var(--sm-text-secondary, #a0a0b0);
  font-size: 12px;
  transition: all 0.15s;
}

.finding-item:hover,
.finding-item.active {
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text, #e0e0e8);
}

.finding-title {
  font-weight: 500;
}

.finding-resources {
  font-size: 11px;
  opacity: 0.6;
  margin-top: 2px;
}
</style>
