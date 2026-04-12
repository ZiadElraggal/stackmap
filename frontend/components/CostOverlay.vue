<template>
  <div v-if="store.showCosts && store.costData" class="cost-overlay" :class="{ 'cost-overlay--panel-open': panelOpen }">
    <div class="cost-shell">
      <div class="cost-header">
        <div>
          <div class="cost-eyebrow">Forecasted cost</div>
          <h3 class="cost-title">Cost & usage</h3>
        </div>
        <button class="cost-close" @click="store.toggleCosts()">Hide</button>
      </div>

      <!-- Scope tabs -->
      <div class="cost-scope-tabs">
        <button
          v-for="tab in scopeTabs"
          :key="tab.key"
          class="cost-scope-tab"
          :class="{ active: scope === tab.key }"
          @click="scope = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="cost-total-row">
        <div>
          <div class="cost-total-label">{{ scopeLabel }} estimate</div>
          <div class="cost-total-value">${{ formatCost(scopedTotal) }}/mo</div>
          <div v-if="scope === 'visible' && visibleCount < totalCount" class="cost-scope-meta">
            {{ visibleCount }} of {{ totalCount }} resources
          </div>
        </div>
        <div v-if="scopedDelta !== null" class="cost-delta" :class="scopedDelta >= 0 ? 'cost-delta--up' : 'cost-delta--down'">
          {{ scopedDelta >= 0 ? '+' : '' }}${{ formatCost(Math.abs(scopedDelta)) }}
        </div>
      </div>

      <p class="cost-summary-copy">
        {{ hasOverrides ? 'Forecast includes usage inputs from the detail panel.' : 'Estimate uses resource metadata and built-in heuristics.' }}
      </p>

      <!-- Per-resource breakdown (top items in scope) -->
      <div class="cost-section">
        <div class="cost-section__header">
          <span>Top resources</span>
          <span class="cost-section__meta">{{ topResources.length }}{{ topResources.length >= 8 ? '+' : '' }}</span>
        </div>
        <div class="cost-component-list">
          <div v-for="item in topResources" :key="item.id" class="cost-component-row">
            <div class="min-w-0">
              <div class="cost-component-name">{{ item.name }}</div>
              <div class="cost-component-meta">{{ item.type }} &middot; {{ item.confidence }}</div>
            </div>
            <div class="cost-component-amount">${{ formatCost(item.cost) }}</div>
          </div>
        </div>
      </div>

      <div v-if="topComponents.length > 0" class="cost-section">
        <div class="cost-section__header">
          <span>By component</span>
          <span class="cost-section__meta">{{ topComponents.length }}</span>
        </div>
        <div class="cost-component-list">
          <div v-for="component in topComponents" :key="component.id" class="cost-component-row">
            <div class="min-w-0">
              <div class="cost-component-name">{{ component.name }}</div>
              <div class="cost-component-meta">{{ component.resourceCount }} resources</div>
            </div>
            <div class="cost-component-amount">${{ formatCost(component.total) }}</div>
          </div>
        </div>
      </div>

      <div class="cost-section">
        <div class="cost-section__header">
          <span>By category</span>
          <span class="cost-section__meta">{{ sortedCategories.length }}</span>
        </div>
        <div class="cost-category-list">
          <div
            v-for="[category, amount] in sortedCategories"
            :key="category"
            class="cost-category-row"
          >
            <span class="cost-category-name">{{ category }}</span>
            <span class="cost-category-amount">${{ formatCost(amount) }}</span>
          </div>
        </div>
      </div>

      <div class="cost-actions">
        <button
          class="cost-toggle-btn"
          :class="{ active: store.costHeatmap }"
          @click="store.toggleCostHeatmap()"
        >
          Heatmap {{ store.costHeatmap ? 'ON' : 'OFF' }}
        </button>
        <button
          v-if="hasOverrides"
          class="cost-reset-btn"
          @click="resetOverrides"
        >
          Reset usage inputs
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

type CostScope = 'all' | 'visible' | 'category'
const scope = ref<CostScope>('all')

const scopeTabs = [
  { key: 'all' as CostScope, label: 'All' },
  { key: 'visible' as CostScope, label: 'Visible' },
  { key: 'category' as CostScope, label: 'By category' },
]

const panelOpen = computed(() => !store.editorPanelCollapsed && (!!store.selectedNode || !!store.selectedEdge || store.editMode))
const hasOverrides = computed(() => Object.keys(store.costOverrides).length > 0)

const visibleNodeIds = computed(() => new Set(store.visibleNodes.map(n => n.id)))
const visibleCount = computed(() => visibleNodeIds.value.size)
const totalCount = computed(() => store.nodes.length)

const scopeLabel = computed(() => {
  if (scope.value === 'visible') return 'Visible resources'
  return 'Account-wide'
})

// Scoped total based on active tab
const scopedTotal = computed(() => {
  if (!store.costData?.by_node) return 0
  if (scope.value === 'all' || scope.value === 'category') {
    return store.costData.total_monthly
  }
  // visible scope
  let total = 0
  for (const [nodeId, estimate] of Object.entries(store.costData.by_node)) {
    if (visibleNodeIds.value.has(nodeId)) {
      total += estimate.monthly_estimate
    }
  }
  return total
})

// Delta compared to baseline
const scopedDelta = computed(() => {
  if (!store.baseCostData || !store.costData) return null
  if (scope.value === 'all' || scope.value === 'category') {
    const diff = store.costData.total_monthly - store.baseCostData.total_monthly
    return Math.abs(diff) >= 0.01 ? diff : null
  }
  // visible scope delta
  let current = 0
  let baseline = 0
  for (const nodeId of visibleNodeIds.value) {
    current += store.costData.by_node?.[nodeId]?.monthly_estimate || 0
    baseline += store.baseCostData.by_node?.[nodeId]?.monthly_estimate || 0
  }
  const diff = current - baseline
  return Math.abs(diff) >= 0.01 ? diff : null
})

// Per-resource breakdown (scoped)
const topResources = computed(() => {
  if (!store.costData?.by_node) return []
  const entries = Object.entries(store.costData.by_node)
    .filter(([nodeId, est]) => {
      if (est.monthly_estimate <= 0) return false
      if (scope.value === 'visible') return visibleNodeIds.value.has(nodeId)
      return true
    })
    .map(([nodeId, est]) => ({
      id: nodeId,
      name: est.resource_name,
      type: est.resource_type.replace(/^aws_/, '').replace(/_/g, ' '),
      cost: est.monthly_estimate,
      confidence: est.confidence,
    }))
    .sort((a, b) => b.cost - a.cost)
    .slice(0, 8)
  return entries
})

// Categories scoped
const sortedCategories = computed(() => {
  if (!store.costData?.by_node) return []
  if (scope.value !== 'visible') {
    // Use the pre-computed by_category from the report
    return Object.entries(store.costData.by_category || {})
      .filter(([, amount]) => amount > 0)
      .sort(([, a], [, b]) => b - a)
  }
  // Recompute for visible scope
  const byCategory: Record<string, number> = {}
  for (const node of store.visibleNodes) {
    const est = store.costData.by_node[node.id]
    if (est && est.monthly_estimate > 0) {
      const cat = node.category || 'other'
      byCategory[cat] = (byCategory[cat] || 0) + est.monthly_estimate
    }
  }
  return Object.entries(byCategory)
    .filter(([, amount]) => amount > 0)
    .sort(([, a], [, b]) => b - a)
})

const topComponents = computed(() => {
  if (!store.costData?.by_node) return []
  const scopeIds = scope.value === 'visible' ? visibleNodeIds.value : null
  return store.componentSummaries
    .map(component => {
      const nodeIds = scopeIds
        ? component.nodeIds.filter(id => scopeIds.has(id))
        : component.nodeIds
      const total = nodeIds.reduce((sum, nodeId) => {
        return sum + (store.costData?.by_node[nodeId]?.monthly_estimate || 0)
      }, 0)
      return {
        id: component.id,
        name: component.name.replace(/-/g, ' '),
        total,
        resourceCount: nodeIds.length,
      }
    })
    .filter(component => component.total > 0)
    .sort((a, b) => b.total - a.total)
    .slice(0, 5)
})

async function resetOverrides() {
  store.costOverrides = {}
  await store.refreshCostData()
}

function formatCost(amount: number): string {
  return amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>

<style scoped>
.cost-overlay {
  position: fixed;
  top: 64px;
  right: 16px;
  z-index: 995;
  width: min(380px, calc(100vw - 32px));
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  transition: right 0.2s ease;
}

.cost-overlay--panel-open {
  right: calc(24rem + 16px);
}

.cost-shell {
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(18, 18, 26, 0.96), rgba(10, 10, 15, 0.95)),
    radial-gradient(circle at top right, rgba(74, 222, 128, 0.14), transparent 42%);
  box-shadow: var(--sm-shadow-elevated, 0 8px 32px rgba(0, 0, 0, 0.4));
  backdrop-filter: blur(18px);
  padding: 14px;
}

.cost-header,
.cost-total-row,
.cost-section__header,
.cost-component-row,
.cost-category-row,
.cost-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.cost-eyebrow {
  color: rgba(74, 222, 128, 0.8);
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.cost-title {
  margin: 4px 0 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--sm-text, #e0e0e8);
}

.cost-scope-tabs {
  display: flex;
  gap: 2px;
  margin-top: 10px;
  padding: 2px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
}

.cost-scope-tab {
  flex: 1;
  padding: 5px 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.55));
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  transition: all 0.15s;
}

.cost-scope-tab:hover {
  color: var(--sm-text, #e0e0e8);
  background: rgba(255, 255, 255, 0.06);
}

.cost-scope-tab.active {
  background: rgba(74, 222, 128, 0.12);
  color: #4ade80;
}

.cost-close,
.cost-toggle-btn,
.cost-reset-btn {
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--sm-text-secondary, #a0a0b0);
  cursor: pointer;
  transition: all 0.15s;
}

.cost-close {
  padding: 6px 10px;
  font-size: 11px;
}

.cost-close:hover,
.cost-toggle-btn:hover,
.cost-reset-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--sm-text, #e0e0e8);
}

.cost-total-row {
  margin-top: 14px;
}

.cost-total-label,
.cost-summary-copy,
.cost-component-meta,
.cost-section__meta,
.cost-category-name,
.cost-scope-meta {
  color: var(--sm-text-muted, rgba(245, 245, 247, 0.55));
}

.cost-total-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.cost-total-value {
  margin-top: 2px;
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
  color: #4ade80;
}

.cost-scope-meta {
  margin-top: 4px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

.cost-delta {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}

.cost-delta--up {
  background: rgba(251, 146, 60, 0.14);
  color: #fdba74;
}

.cost-delta--down {
  background: rgba(74, 222, 128, 0.14);
  color: #86efac;
}

.cost-summary-copy {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.cost-section {
  margin-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 14px;
}

.cost-section__header {
  margin-bottom: 8px;
  color: var(--sm-text, #e0e0e8);
  font-size: 12px;
  font-weight: 600;
}

.cost-component-list,
.cost-category-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cost-component-row,
.cost-category-row {
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
}

.cost-component-name,
.cost-component-amount,
.cost-category-amount {
  color: var(--sm-text, #e0e0e8);
}

.cost-component-name {
  font-size: 12px;
  text-transform: capitalize;
}

.cost-component-meta {
  margin-top: 2px;
  font-size: 11px;
}

.cost-component-amount,
.cost-category-amount {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.cost-category-name {
  text-transform: capitalize;
  font-size: 12px;
}

.cost-actions {
  margin-top: 14px;
}

.cost-toggle-btn,
.cost-reset-btn {
  flex: 1;
  padding: 8px 10px;
  font-size: 12px;
}

.cost-toggle-btn.active {
  border-color: var(--sm-primary, #4ADE80);
  color: var(--sm-primary, #4ADE80);
}

@media (max-width: 1100px) {
  .cost-overlay--panel-open {
    right: 16px;
  }
}

@media (max-width: 768px) {
  .cost-overlay {
    top: auto;
    bottom: 16px;
    left: 16px;
    right: 16px;
    width: auto;
  }

  .cost-overlay--panel-open {
    right: 16px;
  }
}
</style>
