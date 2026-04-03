<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  size?: number
  state?: 'idle' | 'scanning' | 'happy'
  animate?: boolean
}>(), {
  size: 64,
  state: 'idle',
  animate: true,
})

const height = computed(() => props.size * (112 / 128))
</script>

<template>
  <svg
    :width="props.size"
    :height="height"
    viewBox="0 0 128 112"
    xmlns="http://www.w3.org/2000/svg"
    shape-rendering="crispEdges"
    role="img"
    aria-label="StackMap Prism mascot"
  >
    <g :class="['prism-body', props.animate && `prism-body--${props.state}`]">
      <rect x="52" y="0" width="24" height="4" fill="#7B8EA8" opacity="0.25" />
      <rect x="48" y="4" width="32" height="4" fill="#1e2436" />
      <rect x="40" y="8" width="48" height="4" fill="#1e2436" />

      <rect x="32" y="12" width="64" height="8" fill="#1e2436" />
      <rect x="28" y="20" width="72" height="24" fill="#1e2436" />
      <rect x="32" y="16" width="64" height="24" fill="#0d1018" />

      <g :class="['prism-eyes', props.animate && props.state !== 'scanning' && 'prism-eyes--blink']">
        <rect
          x="40"
          :y="props.state === 'happy' ? 26 : 24"
          width="12"
          :height="props.state === 'happy' ? 4 : 8"
          fill="#4ADE80"
        />
        <rect
          x="40"
          :y="props.state === 'happy' ? 26 : 24"
          width="6"
          :height="props.state === 'happy' ? 2 : 4"
          fill="#6FFFB0"
        />
        <rect
          x="76"
          :y="props.state === 'happy' ? 26 : 24"
          width="12"
          :height="props.state === 'happy' ? 4 : 8"
          fill="#4ADE80"
        />
        <rect
          x="76"
          :y="props.state === 'happy' ? 26 : 24"
          width="6"
          :height="props.state === 'happy' ? 2 : 4"
          fill="#6FFFB0"
        />
      </g>

      <rect
        v-if="props.animate"
        x="32" y="32" width="64" height="4"
        fill="#4ADE80"
        :class="['prism-scan', `prism-scan--${props.state}`]"
      />

      <g :class="['prism-ray prism-ray--left', props.animate && `prism-ray--${props.state}`]">
        <rect x="16" y="28" width="12" height="4" fill="#4ADE80" opacity="0.15" />
        <rect x="8" y="28" width="4" height="4" fill="#4ADE80" opacity="0.08" />
      </g>

      <g :class="['prism-ray prism-ray--right', props.animate && `prism-ray--${props.state}`]">
        <rect x="100" y="28" width="12" height="4" fill="#4ADE80" opacity="0.15" />
        <rect x="116" y="28" width="4" height="4" fill="#4ADE80" opacity="0.08" />
      </g>

      <rect x="28" y="44" width="72" height="8" fill="#252a3a" />

      <rect x="32" y="48" width="4" height="4" fill="#4ADE80" :class="['prism-led', props.animate && `prism-led--${props.state}`, 'prism-led--0']" />
      <rect x="56" y="48" width="4" height="4" fill="#4ADE80" :class="['prism-led', props.animate && `prism-led--${props.state}`, 'prism-led--1']" />
      <rect x="92" y="48" width="4" height="4" fill="#4ADE80" :class="['prism-led', props.animate && `prism-led--${props.state}`, 'prism-led--2']" />

      <g :class="['prism-arms', props.state === 'happy' && 'prism-arms--raised']">
        <rect x="24" :y="props.state === 'happy' ? 48 : 52" width="12" height="4" fill="#252a3a" />
        <rect x="20" :y="props.state === 'happy' ? 52 : 56" width="8" height="12" fill="#252a3a" />
        <rect x="16" :y="props.state === 'happy' ? 56 : 60" width="8" height="4" fill="#4ADE80" opacity="0.25" />

        <rect x="92" :y="props.state === 'happy' ? 48 : 52" width="12" height="4" fill="#252a3a" />
        <rect x="100" :y="props.state === 'happy' ? 52 : 56" width="8" height="12" fill="#252a3a" />
        <rect x="104" :y="props.state === 'happy' ? 56 : 60" width="8" height="4" fill="#4ADE80" opacity="0.25" />
      </g>

      <rect x="36" y="52" width="56" height="20" fill="#1e2436" />

      <rect x="40" y="72" width="20" height="4" fill="#252a3a" />
      <rect x="68" y="72" width="20" height="4" fill="#252a3a" />
      <rect x="44" y="76" width="16" height="12" fill="#1a1f2e" />
      <rect x="68" y="76" width="16" height="12" fill="#1a1f2e" />

      <rect x="40" y="88" width="24" height="4" fill="#252a3a" />
      <rect x="64" y="88" width="24" height="4" fill="#252a3a" />
    </g>
  </svg>
</template>

<style scoped>
@keyframes prism-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

@keyframes prism-float-happy {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

.prism-body--idle,
.prism-body--scanning {
  animation: prism-float 4s ease-in-out infinite;
}

.prism-body--happy {
  animation: prism-float-happy 2.5s ease-in-out infinite;
}

@keyframes prism-blink {
  0%, 88%, 92%, 100% { opacity: 1; }
  89%, 91% { opacity: 0; }
}

.prism-eyes--blink {
  animation: prism-blink 4s step-end infinite;
}

@keyframes prism-scan-idle {
  0% { transform: translateY(-3px); opacity: 0; }
  50% { opacity: 0.4; }
  100% { transform: translateY(4px); opacity: 0; }
}

@keyframes prism-scan-active {
  0% { transform: translateY(-3px); opacity: 0; }
  50% { opacity: 0.9; }
  100% { transform: translateY(4px); opacity: 0; }
}

@keyframes prism-scan-relaxed {
  0% { transform: translateY(-3px); opacity: 0; }
  50% { opacity: 0.2; }
  100% { transform: translateY(4px); opacity: 0; }
}

.prism-scan--idle {
  animation: prism-scan-idle 1.8s ease-in-out infinite;
}

.prism-scan--scanning {
  animation: prism-scan-active 0.8s ease-in-out infinite;
}

.prism-scan--happy {
  animation: prism-scan-relaxed 3s ease-in-out infinite;
}

@keyframes prism-ray-idle {
  0%, 100% { opacity: 0.1; transform: scaleX(1); }
  50% { opacity: 0.4; transform: scaleX(1.3); }
}

@keyframes prism-ray-scanning {
  0%, 100% { opacity: 0.15; transform: scaleX(1); }
  50% { opacity: 0.6; transform: scaleX(1.4); }
}

@keyframes prism-ray-happy {
  0%, 100% { opacity: 0.08; transform: scaleX(1); }
  50% { opacity: 0.2; transform: scaleX(1.1); }
}

.prism-ray--left {
  transform-origin: 28px 30px;
}

.prism-ray--right {
  transform-origin: 100px 30px;
}

.prism-ray--idle.prism-ray--left {
  animation: prism-ray-idle 2s ease-in-out infinite;
}

.prism-ray--idle.prism-ray--right {
  animation: prism-ray-idle 2s ease-in-out 0.3s infinite;
}

.prism-ray--scanning.prism-ray--left,
.prism-ray--scanning.prism-ray--right {
  animation: prism-ray-scanning 1s ease-in-out infinite;
}

.prism-ray--happy.prism-ray--left,
.prism-ray--happy.prism-ray--right {
  animation: prism-ray-happy 3s ease-in-out infinite;
}

@keyframes prism-led-pulse {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.7; }
}

@keyframes prism-led-chase-0 {
  0%, 100% { opacity: 0.15; }
  0%, 33% { opacity: 0.9; }
}

@keyframes prism-led-chase-1 {
  0%, 100% { opacity: 0.15; }
  33%, 66% { opacity: 0.9; }
}

@keyframes prism-led-chase-2 {
  0%, 100% { opacity: 0.15; }
  66%, 100% { opacity: 0.9; }
}

.prism-led--idle {
  animation: prism-led-pulse 2s ease-in-out infinite;
}

.prism-led--happy {
  animation: prism-led-pulse 3s ease-in-out infinite;
}

.prism-led--scanning.prism-led--0 {
  animation: prism-led-chase-0 0.6s linear infinite;
}

.prism-led--scanning.prism-led--1 {
  animation: prism-led-chase-1 0.6s linear infinite;
}

.prism-led--scanning.prism-led--2 {
  animation: prism-led-chase-2 0.6s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .prism-body--idle,
  .prism-body--scanning,
  .prism-body--happy,
  .prism-eyes--blink,
  .prism-scan--idle,
  .prism-scan--scanning,
  .prism-scan--happy,
  .prism-ray--idle,
  .prism-ray--scanning,
  .prism-ray--happy,
  .prism-led--idle,
  .prism-led--scanning,
  .prism-led--happy {
    animation: none !important;
  }
}
</style>
