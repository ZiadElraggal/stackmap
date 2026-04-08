<template>
  <div v-if="store.showCosts && store.costData" class="cost-overlay">
    <div class="cost-header">
      <h3 class="cost-title">Cost Estimate</h3>
      <span class="cost-total">${{ formatCost(store.costData.total_monthly) }}/mo</span>
    </div>

    <div class="cost-categories">
      <div
        v-for="[category, amount] in sortedCategories"
        :key="category"
        class="cost-category-row"
      >
        <span class="cost-category-name">{{ category }}</span>
        <span class="cost-category-amount">${{ formatCost(amount) }}</span>
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()

const sortedCategories = computed(() => {
  if (!store.costData?.by_category) return []
  return Object.entries(store.costData.by_category)
    .filter(([, amount]) => amount > 0)
    .sort(([, a], [, b]) => b - a)
})

function formatCost(amount: number): string {
  if (amount >= 1000) return amount.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  return amount.toFixed(2)
}
</script>

<style scoped>
.cost-overlay {
  padding: 12px 0;
  border-top: 1px solid var(--sm-border, #2a2a3a);
}

.cost-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px 8px;
}

.cost-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sm-text, #e0e0e8);
  margin: 0;
}

.cost-total {
  font-size: 15px;
  font-weight: 700;
  color: var(--sm-primary, #4ADE80);
}

.cost-categories {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 16px;
}

.cost-category-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
}

.cost-category-name {
  color: var(--sm-text-secondary, #a0a0b0);
  text-transform: capitalize;
}

.cost-category-amount {
  color: var(--sm-text, #e0e0e8);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.cost-actions {
  padding: 8px 16px 0;
}

.cost-toggle-btn {
  width: 100%;
  padding: 5px 10px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--sm-border, #2a2a3a);
  border-radius: 6px;
  color: var(--sm-text-secondary, #a0a0b0);
  cursor: pointer;
  transition: all 0.15s;
}

.cost-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--sm-text, #e0e0e8);
}

.cost-toggle-btn.active {
  border-color: var(--sm-primary, #4ADE80);
  color: var(--sm-primary, #4ADE80);
}
</style>
