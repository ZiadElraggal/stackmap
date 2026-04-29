<template>
  <div class="profile-switcher">
    <div class="profile-note">Applies to live logs and billing. Rescan to change the graph.</div>
    <button
      v-for="profile in store.availableProfiles"
      :key="profile"
      class="profile-option"
      :class="{ active: profile === store.activeProfile }"
      :disabled="store.profileSwitching"
      @click="activate(profile)"
    >
      {{ profile }}
    </button>
    <div v-if="message" class="profile-message">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useGraphStore } from '~/stores/graph'

const store = useGraphStore()
const message = ref('')

async function activate(profile: string) {
  message.value = 'Switching...'
  const result = await store.activateProfile(profile)
  message.value = result.ok ? 'Profile active' : (result.error || 'Switch failed')
}
</script>

<style scoped>
.profile-switcher {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.profile-note {
  color: rgba(245,245,247,0.45);
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  line-height: 1.35;
  padding: 0 2px 2px;
}

.profile-option {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--sm-text-muted, rgba(245,245,247,0.55));
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 6px 8px;
  text-align: left;
}

.profile-option:disabled {
  cursor: wait;
  opacity: 0.6;
}

.profile-option:hover,
.profile-option.active {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.22);
  color: #4ade80;
}

.profile-message {
  color: rgba(245,245,247,0.55);
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  padding: 4px 2px 0;
}
</style>
