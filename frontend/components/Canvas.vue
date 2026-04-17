<template>
  <div class="relative h-full w-full overflow-hidden" ref="containerRef">
    <svg ref="svgRef" class="h-full w-full" :style="{ background: '#0a0a0f' }">
      <defs>
        <pattern id="grid-cross" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
          <line x1="18.5" y1="20" x2="21.5" y2="20" stroke="rgba(255,255,255,0.04)" stroke-width="1" />
          <line x1="20" y1="18.5" x2="20" y2="21.5" stroke="rgba(255,255,255,0.04)" stroke-width="1" />
        </pattern>

        <marker
          v-for="edgeType in edgeTypesInGraph"
          :id="`arrow-${edgeType}`"
          :key="`marker-${edgeType}`"
          viewBox="0 0 6 5"
          refX="8"
          refY="2.5"
          markerWidth="6"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 6 2.5 L 0 5 Z" :fill="edgeColor(edgeType)" />
        </marker>

        <marker
          v-for="edge in visibleUserLinks"
          :id="`arrow-user-${sanitizeMarkerId(edge.id)}`"
          :key="`marker-user-${edge.id}`"
          viewBox="0 0 6 5"
          refX="8"
          refY="2.5"
          markerWidth="6"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 6 2.5 L 0 5 Z" :fill="edge.color || edgeColor(edge.edge_type)" />
        </marker>
      </defs>

      <rect width="100%" height="100%" fill="#0a0a0f" @click="clearSelection" />

      <g ref="zoomGroupRef">
        <g v-if="store.viewMode !== 'organization'">
          <rect
            v-for="band in tierBands"
            :key="`tier-band-${band.id}`"
            :x="graphBounds.minX - 260"
            :y="band.yStart"
            :width="graphBounds.width + 520"
            :height="band.yEnd - band.yStart"
            :fill="band.fill"
            :fill-opacity="tierBandOpacity(band.id)"
            :stroke="band.stroke"
            :stroke-opacity="tierBorderOpacity(band.id)"
            :stroke-width="store.dragTargetLayerId === band.id ? 1.8 : 1.2"
          />
        </g>

        <g v-if="store.viewMode !== 'organization'">
          <line
            v-for="divider in tierDividers"
            :key="`tier-divider-${divider.name}`"
            :x1="graphBounds.minX - 250"
            :x2="graphBounds.minX + graphBounds.width + 250"
            :y1="divider.y"
            :y2="divider.y"
            :stroke="divider.stroke"
            :stroke-opacity="tierDividerOpacity(divider.name)"
            stroke-width="1"
          />
        </g>

        <rect
          :x="graphBounds.minX - 500"
          :y="graphBounds.minY - 500"
          :width="graphBounds.width + 1000"
          :height="graphBounds.height + 1000"
          fill="url(#grid-cross)"
          @click="clearSelection"
        />

        <g v-if="store.viewMode !== 'organization'" v-for="band in tierBands" :key="`tier-${band.id}`">
          <rect
            :x="graphBounds.minX - 226"
            :y="band.yStart + 12"
            rx="8"
            ry="8"
            width="118"
            height="24"
            :fill="band.chipFill"
            :fill-opacity="tierChipOpacity(band.id)"
            :stroke="band.chipStroke"
            :stroke-opacity="tierChipOpacity(band.id)"
            :stroke-width="store.dragTargetLayerId === band.id ? 1.4 : 1"
          />
          <text
            :x="graphBounds.minX - 216"
            :y="band.yStart + 28"
            :fill="band.chipAccent"
            font-size="10"
            text-anchor="start"
            font-weight="700"
            letter-spacing="1.5"
            font-family="'JetBrains Mono', monospace"
          >{{ band.icon }}</text>
          <text
            :x="graphBounds.minX - 200"
            :y="band.yStart + 28"
            fill="rgba(229,231,235,0.95)"
            font-size="10"
            text-anchor="start"
            font-weight="600"
            letter-spacing="1.3"
            font-family="'JetBrains Mono', monospace"
          >{{ band.name.toUpperCase() }}</text>
          <text
            :x="graphBounds.minX - 60"
            :y="band.labelY"
            fill="rgba(255,255,255,0.1)"
            font-size="11"
            font-weight="600"
            letter-spacing="3"
            text-anchor="end"
            dominant-baseline="central"
            font-family="'JetBrains Mono', monospace"
          >{{ band.name.toUpperCase() }}</text>
        </g>

        <g v-if="store.viewMode !== 'organization'" v-for="(band, idx) in tierBands" :key="`flow-arrow-${band.id}`">
          <text
            v-if="idx < tierBands.length - 1"
            :x="graphBounds.minX + graphBounds.width / 2"
            :y="band.yEnd + 10"
            fill="rgba(255,255,255,0.06)"
            font-size="16"
            text-anchor="middle"
            dominant-baseline="central"
          >↓</text>
        </g>

        <GroupBoundary
          v-for="group in store.graphGroups"
          :key="group.id"
          :group="group"
          :positions="store.positions"
        />

        <GraphEdge
          v-for="(edge, idx) in store.visibleEdges"
          :key="edge.id"
          :edge="edge"
          :x1="edgeSourcePos(edge).x"
          :y1="edgeSourcePos(edge).y"
          :x2="edgeTargetPos(edge).x"
          :y2="edgeTargetPos(edge).y"
          :zoom-scale="zoomScale"
          :entry-delay="edgeEntryBaseDelay + idx * 4"
        />

        <GraphNode
          v-for="(node, idx) in orderedVisibleNodes"
          :key="node.id"
          :node="node"
          :x="store.positions[node.id]?.x ?? 0"
          :y="store.positions[node.id]?.y ?? 0"
          :entry-delay="idx * 15"
          @drag-node-start="onNodeDragStart"
          @drag-node-move="onNodeDragMove"
          @drag-node-end="onNodeDragEnd"
        />
      </g>
    </svg>

    <ComponentLanding v-if="store.viewMode === 'components'" />

    <Transition name="fade">
      <div
        v-if="store.viewMode === 'step_function' && !store.presentationMode"
        class="absolute left-1/2 top-4 z-50 w-[min(960px,calc(100vw-2rem))] -translate-x-1/2 rounded-xl border border-white/[0.08] bg-[#0e0e18]/95 px-4 py-3 backdrop-blur-md shadow-[0_18px_48px_rgba(0,0,0,0.45)]"
      >
        <div class="flex flex-wrap items-center gap-3">
          <button
            class="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.14em] text-gray-300 transition hover:bg-white/[0.06] hover:text-white"
            @click="store.returnToArchitectureFromStateMachine()"
          >
            Back to architecture
          </button>
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-semibold text-white">{{ activeWorkflowTitle }}</div>
            <div class="mt-0.5 text-[10px] font-mono text-gray-500">
              Workflow structure is available from the scan. Recent executions require states:ListExecutions; per-step debugging requires states:GetExecutionHistory.
            </div>
          </div>
          <label class="flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.14em] text-gray-300">
            <input
              type="checkbox"
              class="accent-cyan-400"
              :checked="store.showStateMachineTargets"
              @change="store.setShowStateMachineTargets(($event.target as HTMLInputElement).checked)"
            />
            Show target resources
          </label>
        </div>

        <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3">
          <button
            class="rounded-md border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.14em] text-cyan-200 transition hover:border-cyan-300/35 hover:bg-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="workflowExecutionsLoading"
            @click="loadWorkflowExecutions"
          >
            {{ workflowExecutionsLoading ? 'Loading executions' : workflowRecentExecutions.length ? 'Refresh executions' : 'Load recent executions' }}
          </button>
          <select
            v-if="workflowRecentExecutions.length"
            v-model="selectedWorkflowExecutionArn"
            class="max-w-[360px] rounded-md border border-white/10 bg-[#090b12] px-2 py-1.5 text-[10px] font-mono text-gray-200 outline-none"
          >
            <option value="">Choose an execution</option>
            <option
              v-for="execution in workflowRecentExecutions"
              :key="execution.execution_arn || execution.name"
              :value="execution.execution_arn"
            >
              {{ execution.name || shortExecutionArn(execution.execution_arn || '') }} · {{ execution.status || 'unknown' }}
            </option>
          </select>
          <button
            v-if="workflowRecentExecutions.length"
            class="rounded-md border border-emerald-400/20 bg-emerald-500/10 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.14em] text-emerald-200 transition hover:border-emerald-300/35 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!selectedWorkflowExecutionArn || workflowHistoryLoading"
            @click="loadWorkflowExecutionHistory"
          >
            {{ workflowHistoryLoading ? 'Loading history' : 'Overlay selected execution' }}
          </button>
          <span v-if="store.selectedStateMachineExecutionArn" class="text-[10px] font-mono text-emerald-300">
            overlay active
          </span>
          <span v-if="workflowExecutionError" class="text-[10px] font-mono text-amber-200">
            {{ workflowExecutionError }}
          </span>
        </div>
      </div>
    </Transition>

    <div v-if="!store.presentationMode && store.viewMode !== 'step_function'" class="absolute left-1/2 top-4 z-40 -translate-x-1/2">
      <SearchBar ref="searchBarRef" @pan-to="panToNode" />
    </div>

    <Transition name="fade">
      <div
        v-if="store.editMode && store.editSubmode === 'structure' && store.viewMode !== 'organization' && !store.presentationMode"
        class="absolute z-50 w-56 rounded-2xl border border-white/[0.08] bg-[#12121a]/92 p-3 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,0,0,0.45)]"
        :style="layerRailStyle"
      >
        <div
          class="mb-2 flex cursor-move items-center justify-between gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-2.5 py-2"
          @pointerdown="onLayerRailPointerDown"
        >
          <div>
            <div class="text-[9px] font-semibold uppercase tracking-[0.15em] text-gray-500">Layers</div>
            <div class="mt-1 text-[11px] text-gray-400">Drag rows to reorder. Drop nodes onto any row.</div>
          </div>
          <span class="select-none text-xs font-mono text-gray-600">move</span>
        </div>

        <div class="space-y-1.5">
          <div
            v-for="layer in layerRailLayers"
            :key="`rail-${layer.id}`"
            :data-layer-drop-target="layer.id"
            :data-layer-reorder-item="layer.id"
            draggable="true"
            class="group flex cursor-grab items-center gap-2 rounded-xl border px-2.5 py-2 transition-all"
            :class="{
              'border-emerald-400/35 bg-emerald-500/12 shadow-[0_0_0_1px_rgba(74,222,128,0.15)]': store.dragTargetLayerId === layer.id || layerRailDropTargetId === layer.id,
              'border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.05]': store.dragTargetLayerId !== layer.id && layerRailDropTargetId !== layer.id,
              'opacity-50': draggingLayerId === layer.id,
            }"
            @dragstart="onLayerRailDragStart($event, layer.id)"
            @dragover.prevent="onLayerRailDragOver(layer.id)"
            @drop.prevent="onLayerRailDrop(layer.id)"
            @dragend="onLayerRailDragEnd"
          >
            <span class="select-none text-sm leading-none text-gray-600 transition-colors group-hover:text-gray-400">⋮⋮</span>
            <span class="text-sm" :style="{ color: layer.accent }">{{ layer.icon }}</span>
            <div class="min-w-0 flex-1">
              <div class="truncate text-xs font-medium text-white">{{ layer.label }}</div>
              <div class="mt-0.5 text-[10px] font-mono uppercase tracking-wider" :class="layer.count > 0 ? 'text-gray-500' : 'text-amber-400/80'">
                {{ layer.count > 0 ? `${layer.count} nodes` : 'empty drop target' }}
              </div>
            </div>
            <button
              v-if="store.customLayers.some(customLayer => customLayer.id === layer.id)"
              class="flex h-6 w-6 items-center justify-center rounded-md border border-white/10 bg-white/5 text-[11px] text-gray-300 opacity-0 transition-all hover:bg-white/10 group-hover:opacity-100"
              title="Edit custom layer"
              @click.stop="openLayerEditor(layer.id)"
            >
              ✎
            </button>
            <button
              v-if="layer.canDelete"
              class="flex h-6 w-6 items-center justify-center rounded-md border border-red-400/20 bg-red-500/8 text-[11px] text-red-300 opacity-0 transition-all hover:bg-red-500/16 group-hover:opacity-100"
              title="Delete empty custom layer"
              @click.stop="deleteLayer(layer.id)"
            >
              ×
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="store.editMode && !store.presentationMode"
        class="absolute left-1/2 top-4 z-40 -translate-x-1/2 rounded-2xl border border-white/[0.08] bg-[#0e0e18]/95 px-4 py-2 backdrop-blur-md shadow-xl"
      >
        <div class="flex items-center gap-3">
          <span class="text-[9px] font-mono uppercase tracking-[0.18em] text-emerald-400">Editor</span>
          <span class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-white">{{ store.editSubmode }}</span>
          <span class="text-[10px] font-mono text-gray-500">{{ selectionStatus }}</span>
          <span class="hidden md:inline text-[10px] font-mono text-gray-600">{{ modeHint }}</span>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="store.editMode && selectedEditorItem && !store.presentationMode"
        class="absolute left-1/2 top-[4.75rem] z-40 -translate-x-1/2 rounded-2xl border border-white/[0.08] bg-[#10101a]/96 px-4 py-3 backdrop-blur-md shadow-[0_16px_40px_rgba(0,0,0,0.45)]"
      >
        <div class="flex flex-wrap items-center gap-3">
          <div class="min-w-0">
            <div class="text-[9px] font-mono uppercase tracking-[0.18em] text-gray-500">{{ selectedEditorItem.kind }}</div>
            <div class="mt-1 max-w-[280px] truncate text-xs font-medium text-white">{{ selectedEditorItem.label }}</div>
          </div>

          <span class="h-5 w-px bg-white/[0.08]" />

          <template v-if="store.selectedNode">
            <template v-if="store.editSubmode === 'inspect'">
              <button
                v-if="selectedNodeHasComponent"
                class="selection-action"
                @click="store.isolateSelectedComponent()"
              >Isolate Component</button>
              <button class="selection-action" @click="store.isolateSelectedNeighborhood(1)">Focus 1-Hop</button>
              <button class="selection-action" @click="store.setEditSubmode('structure')">Open Structure</button>
              <button class="selection-action selection-action--accent" @click="activateConnectForSelectedNode">Open Connect</button>
            </template>
            <template v-else-if="store.editSubmode === 'structure'">
              <button class="selection-action" @click="store.isolateSelectedLayer()">Isolate Layer</button>
              <button
                v-if="selectedNodeHasComponent"
                class="selection-action"
                @click="store.isolateSelectedComponent()"
              >Isolate Component</button>
              <button class="selection-action" @click="store.isolateSelectedNeighborhood(1)">Focus 1-Hop</button>
              <button class="selection-action selection-action--danger" @click="store.hideNode(store.selectedNode.id)">Hide</button>
              <button
                v-if="store.selectedNode.tags?._user_created"
                class="selection-action"
                @click="store.duplicateUserNode(store.selectedNode.id)"
              >Duplicate</button>
              <button
                v-if="store.selectedNode.tags?._user_created"
                class="selection-action selection-action--danger"
                @click="store.removeUserNode(store.selectedNode.id)"
              >Delete</button>
              <button
                v-else
                class="selection-action"
                @click="store.resetNodeEdits(store.selectedNode.id)"
              >Reset</button>
              <button class="selection-action selection-action--accent" @click="activateConnectForSelectedNode">Connect</button>
            </template>
            <template v-else>
              <button
                class="selection-action selection-action--accent"
                @click="activateConnectForSelectedNode"
              >{{ store.connectingFromNodeId === store.selectedNode.id ? 'Connecting…' : 'Start Link' }}</button>
              <button
                v-if="store.connectingFromNodeId"
                class="selection-action"
                @click="store.cancelConnecting()"
              >Cancel</button>
            </template>
          </template>

          <template v-else-if="store.selectedEdge">
            <template v-if="store.editSubmode !== 'connect'">
              <button class="selection-action selection-action--accent" @click="store.setEditSubmode('connect')">Open Connect</button>
            </template>
            <button
              v-if="selectedEdgeIsEditable"
              class="selection-action selection-action--danger"
              @click="store.removeUserEdge(store.selectedEdge.id)"
            >Delete Link</button>
          </template>

          <button class="selection-action" @click="clearSelection">Clear</button>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="store.editMode && !store.hasSeenEditWalkthrough && !store.presentationMode"
        class="absolute left-1/2 top-24 z-40 w-[420px] -translate-x-1/2 rounded-2xl border border-white/[0.08] bg-[#12121a]/96 p-4 backdrop-blur-xl shadow-[0_18px_48px_rgba(0,0,0,0.48)]"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400">Editor Tour</div>
            <div class="mt-2 text-sm text-white">Inspect keeps the graph safe. Structure lets you move, hide, and layer resources. Connect is for manual links.</div>
            <div class="mt-2 text-xs leading-relaxed text-gray-400">Select a node to edit it in the side panel, drag nodes only in Structure mode, and use the layer rail for empty-layer drops and reordering.</div>
          </div>
          <button
            class="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-mono text-gray-400 transition hover:bg-white/5 hover:text-white"
            @click="store.dismissEditWalkthrough()"
          >
            Dismiss
          </button>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="store.editMode && store.editSubmode === 'connect' && !store.presentationMode && showConnectHint"
        class="absolute left-1/2 top-[7.75rem] z-40 w-[460px] max-w-[calc(100vw-2rem)] -translate-x-1/2 rounded-2xl border border-amber-400/18 bg-[#12121a]/96 p-4 backdrop-blur-xl shadow-[0_18px_48px_rgba(0,0,0,0.45)]"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-[10px] font-mono uppercase tracking-[0.18em] text-amber-300">Connect Mode</div>
            <div class="mt-2 text-sm text-white">
              {{ store.connectingFromNodeId ? 'Click a destination resource to create the missing relationship.' : 'Select a source resource, then choose the destination on the graph.' }}
            </div>
            <div class="mt-2 text-xs leading-relaxed text-gray-400">
              Manual links appear in the side panel after creation, where you can rename them, recolor them, and set whether they represent request flow, events, data access, auth, or a generic relationship.
            </div>
          </div>
          <div class="flex items-start gap-2">
            <button
              class="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-mono text-gray-400 transition hover:bg-white/5 hover:text-white"
              @click="dismissConnectHint"
            >
              Hide hint
            </button>
            <button
              class="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-mono text-gray-400 transition hover:bg-white/5 hover:text-white"
              @click="store.cancelConnecting()"
            >
              Cancel
            </button>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <span
            v-for="hint in connectHints"
            :key="hint.label"
            class="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[10px] font-mono text-gray-400"
          >
            <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: hint.color }" />
            {{ hint.label }}
          </span>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="showLayerEditor && editingLayer"
        class="absolute left-1/2 top-1/2 z-[120] w-[360px] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#12121a]/98 p-5 shadow-[0_30px_80px_rgba(0,0,0,0.5)] backdrop-blur-xl"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400">Layer Editor</div>
            <div class="mt-2 text-sm text-white">Adjust how this custom layer appears across the editor.</div>
          </div>
          <button
            class="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-mono text-gray-400 transition hover:bg-white/5 hover:text-white"
            @click="closeLayerEditor"
          >
            Close
          </button>
        </div>

        <div class="mt-4 space-y-3">
          <label class="block">
            <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Label</span>
            <input
              v-model="layerEditLabel"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono outline-none focus:border-emerald-400/40"
              placeholder="Layer label"
            />
          </label>

          <div class="grid grid-cols-[1fr_auto] gap-3">
            <label class="block">
              <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Icon</span>
              <input
                v-model="layerEditIcon"
                maxlength="2"
                class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white font-mono outline-none focus:border-emerald-400/40"
                placeholder="✦"
              />
            </label>
            <label class="block">
              <span class="mb-1 block text-[10px] font-mono uppercase tracking-wider text-gray-500">Accent</span>
              <input
                v-model="layerEditAccent"
                type="color"
                class="h-[42px] w-16 rounded-lg border border-white/10 bg-white/5 p-1"
              />
            </label>
          </div>

          <div class="rounded-xl border border-white/[0.08] bg-black/20 px-3 py-3">
            <div class="mb-2 text-[10px] font-mono uppercase tracking-[0.15em] text-gray-500">Preview</div>
            <div class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5" :style="{ borderColor: `${layerEditAccent}55`, backgroundColor: `${layerEditAccent}14` }">
              <span class="text-sm" :style="{ color: layerEditAccent }">{{ layerEditIcon || '✦' }}</span>
              <span class="text-xs font-mono text-white">{{ layerEditLabel || editingLayer.label }}</span>
            </div>
          </div>
        </div>

        <div class="mt-4 flex justify-end gap-2">
          <button
            class="rounded-lg border border-white/10 px-4 py-2 text-xs font-mono text-gray-400 transition hover:bg-white/5"
            @click="closeLayerEditor"
          >
            Cancel
          </button>
          <button
            class="rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-4 py-2 text-xs font-mono text-emerald-300 transition hover:bg-emerald-500/25"
            @click="saveLayerEditor"
          >
            Save Layer
          </button>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="store.presentationMode"
        class="absolute right-4 top-4 z-50 flex items-center gap-2 rounded-xl border border-white/[0.08] bg-[#0e0e18]/95 px-3 py-2 backdrop-blur-md shadow-xl"
      >
        <span class="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400">Presentation</span>
        <button
          class="rounded-lg border border-white/10 px-2 py-1 text-[10px] font-mono text-gray-300 transition hover:bg-white/5 hover:text-white"
          @click="store.setPresentationMode(false)"
        >
          Exit
        </button>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="draggingNodeName"
        class="pointer-events-none absolute left-1/2 top-20 z-50 -translate-x-1/2 rounded-xl border border-emerald-400/25 bg-[#0e0e18]/95 px-4 py-2 backdrop-blur-md shadow-xl"
      >
        <div class="text-[10px] font-mono uppercase tracking-widest text-emerald-400">Moving Component</div>
        <div class="mt-1 text-xs text-gray-300">
          {{ draggingNodeName }}
          <span class="text-gray-500">→</span>
          <span class="text-emerald-300">{{ dragTargetLayerLabel || 'choose a layer' }}</span>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="store.activeBreadcrumb.length > 0 && !store.presentationMode && store.viewMode !== 'step_function'"
        class="absolute left-1/2 top-16 z-40 -translate-x-1/2 flex items-center gap-2 rounded-xl border border-white/[0.08] bg-[#0e0e18]/95 px-4 py-2 backdrop-blur-md shadow-xl"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" stroke-width="1.5" stroke-linecap="round" opacity="0.6">
          <circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3C8 7 8 17 12 21M12 3c4 4 4 14 0 18"/>
        </svg>
        <button
          v-if="store.activeComponentId"
          class="text-[10px] font-mono text-cyan-400 transition-colors hover:text-cyan-300"
          @click="store.returnToComponents()"
        >back to components</button>
        <button
          v-else
          class="text-[10px] font-mono text-cyan-400 transition-colors hover:text-cyan-300"
          @click="clearBreadcrumbScope"
        >all accounts</button>
        <span class="text-[10px] font-mono text-gray-600">/</span>
        <span class="text-[10px] font-mono text-gray-400">{{ store.activeBreadcrumb.join(' / ') }}</span>
      </div>
    </Transition>

    <Transition name="fade">
      <div
        v-if="diffSummaryMeta && !store.presentationMode"
        class="absolute left-1/2 top-16 z-40 -translate-x-1/2 flex items-center gap-3 rounded-xl border border-white/[0.08] bg-[#0e0e18]/95 px-4 py-2 backdrop-blur-md shadow-xl"
      >
        <span class="text-[10px] font-mono text-gray-500 tracking-widest uppercase">Diff</span>
        <span class="h-3 w-px bg-white/[0.08]" />
        <span class="text-[11px] font-mono font-semibold text-green-400">+{{ diffSummaryMeta.added }}</span>
        <span class="text-[11px] font-mono font-semibold text-red-400">-{{ diffSummaryMeta.removed }}</span>
        <span class="text-[11px] font-mono font-semibold text-amber-400">~{{ diffSummaryMeta.modified }}</span>
        <span class="text-[11px] font-mono text-gray-500">{{ diffSummaryMeta.unchanged }} unchanged</span>
        <span class="h-3 w-px bg-white/[0.08]" />
        <button
          v-if="store.diffMode"
          class="text-[10px] font-mono text-gray-400 transition-colors hover:text-white"
          :class="store.showOnlyChanges ? 'text-amber-400' : ''"
          @click="store.setShowOnlyChanges(!store.showOnlyChanges)"
        >{{ store.showOnlyChanges ? 'show all' : 'changes only' }}</button>
        <button
          v-else
          class="text-[10px] font-mono text-cyan-400 transition-colors hover:text-cyan-300"
          @click="store.setDiffMode(true)"
        >open timeline</button>
      </div>
    </Transition>

    <Minimap v-if="!store.presentationMode" :viewport="viewportRect" @pan-to-position="panToPosition" />

    <div v-if="!store.presentationMode" class="absolute right-4 top-4 z-30">
      <button
        class="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-xs text-gray-500 hover:text-gray-300 hover:bg-white/[0.06] transition-all backdrop-blur-sm"
        @click="showHelp = !showHelp"
        title="Keyboard shortcuts (?)"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="6" cy="6" r="5" /><path d="M4.5 4.5a1.5 1.5 0 0 1 3 0c0 .8-.7 1-1.5 1.5M6 8.5v.01" stroke-linecap="round"/>
        </svg>
      </button>
    </div>

    <Transition name="help-panel">
      <div
        v-if="showHelp && !store.presentationMode"
        class="absolute right-4 top-14 z-50 w-52 rounded-xl border border-white/[0.08] bg-[#14141e]/95 backdrop-blur-xl p-3.5 shadow-[0_12px_40px_rgba(0,0,0,0.5)]"
      >
        <h3 class="mb-3 text-[9px] font-semibold uppercase tracking-[0.15em] text-gray-500">Shortcuts</h3>
        <div class="space-y-2 text-xs">
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">⌘K</kbd><span class="text-gray-500">Palette</span></div>
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">/</kbd><span class="text-gray-500">Search</span></div>
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">{{ undoShortcutLabel }}</kbd><span class="text-gray-500">Undo edit</span></div>
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">{{ redoShortcutLabel }}</kbd><span class="text-gray-500">Redo edit</span></div>
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">Esc</kbd><span class="text-gray-500">Close</span></div>
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">0</kbd><span class="text-gray-500">Fit to screen</span></div>
          <div class="flex justify-between items-center"><kbd class="text-gray-400 bg-white/[0.05] px-1.5 py-0.5 rounded-md text-[10px] font-mono border border-white/[0.06]">+/−</kbd><span class="text-gray-500">Zoom</span></div>
        </div>
      </div>
    </Transition>

    <div
      v-if="edgeTypesInGraph.length && !store.presentationMode"
      class="absolute bottom-9 left-3 z-30 rounded-lg border border-white/[0.06] bg-[#0e0e18]/80 px-2.5 py-1.5 backdrop-blur-md"
    >
      <div class="flex items-center gap-3">
        <div v-for="edgeType in edgeTypesInGraph" :key="`legend-${edgeType}`" class="flex items-center gap-1.5">
          <span class="h-0.5 w-4 rounded-full" :style="{ backgroundColor: edgeColor(edgeType), opacity: 0.8 }" />
          <span class="text-[9px] text-gray-500 tracking-wide">{{ edgeTypeLegendLabel(edgeType) }}</span>
          <span
            class="rounded-full border px-1.5 py-0.5 text-[8px] font-mono uppercase tracking-wide"
            :class="edgeTypeKindClass(edgeType)"
          >
            {{ edgeTypeKindLabel(edgeType) }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="!store.presentationMode" class="status-glow absolute bottom-7 left-0 right-0 h-px" />

    <div
      v-if="!store.presentationMode"
      class="absolute bottom-0 left-0 right-0 flex h-7 items-center gap-3 border-t border-white/[0.04] bg-[#0e0e18]/95 backdrop-blur-sm px-4 font-mono text-[10px] text-gray-500"
    >
      <div class="flex items-center gap-1.5 text-gray-400">
        <span class="h-1.5 w-1.5 rounded-full bg-cyan-400/80" />
        <span class="font-semibold tracking-wider text-[10px]">StackMap</span>
      </div>
      <span class="h-3 w-px bg-white/[0.06]" />
      <span>{{ primaryResourceCount }}<span class="text-gray-600">/{{ store.nodes.length }}</span> resources</span>
      <span>{{ primaryConnectionCount }} connections</span>
      <span class="text-gray-600">{{ viewModeLabel }}</span>
      <span v-if="store.graphGroups.length > 0" class="text-gray-600">{{ store.graphGroups.length }} groups</span>
      <span v-if="store.metadata.terraform_version" class="text-gray-600">TF v{{ store.metadata.terraform_version }}</span>
      <span v-if="store.showCrossAccountEdges && store.metadata.cross_account_edges" class="text-gray-600">{{ store.metadata.cross_account_edges }} cross-account</span>
      <span class="text-gray-600">{{ Math.round(zoomScale * 100) }}%</span>
      <div class="flex items-center gap-0.5 rounded-md border border-white/[0.06] bg-white/[0.02] px-1 py-0.5">
        <div
          v-for="lane in architectureStrip"
          :key="`strip-${lane.name}`"
          class="flex items-center gap-0.5 rounded px-1 py-[1px]"
          :style="{ backgroundColor: lane.count > 0 ? lane.bg : 'transparent' }"
        >
          <span class="text-[8px] uppercase tracking-wide" :style="{ color: lane.count > 0 ? lane.accent : '#4b5563' }">{{ lane.short }}</span>
          <span v-if="lane.count > 0" class="text-[9px] text-gray-300">{{ lane.count }}</span>
        </div>
      </div>
      <span class="ml-auto text-gray-600 hidden sm:inline">scroll to zoom · drag to pan · ⌘K palette</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as d3 from 'd3'
import { useGraphStore, type NodePosition, type StackMapEdge, type StackMapNode } from '~/stores/graph'
import { useLayout } from '~/composables/useLayout'
import { EDGE_COLORS, MANUAL_EDGE_TYPES, buildLayerDefinitions, getNodeHeight } from '~/composables/useGraph'

const store = useGraphStore()
const { computeLayout, sortByTier } = useLayout()

const svgRef = ref<SVGSVGElement>()
const zoomGroupRef = ref<SVGGElement>()
const containerRef = ref<HTMLDivElement>()
const searchBarRef = ref<{ focus: () => void }>()
const showHelp = ref(false)
const draggingLayerId = ref<string | null>(null)
const layerRailDropTargetId = ref<string | null>(null)

const viewportRect = ref<{ x: number; y: number; width: number; height: number } | null>(null)
const zoomScale = ref(1)
const isMacLike = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.platform)

let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null
let svgSelection: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null

const orderedVisibleNodes = computed(() => {
  if (store.viewMode === 'organization') {
    return [...store.visibleNodes].sort((a, b) => a.name.localeCompare(b.name))
  }
  return sortByTier(store.visibleNodes, store.layoutLayers)
})
const visibleNodeMap = computed(() => new Map(store.visibleNodes.map(n => [n.id, n])))
const edgeEntryBaseDelay = computed(() => orderedVisibleNodes.value.length * 15 + 200)
const edgeTypesInGraph = computed(() => [...new Set(store.visibleEdges.map(edge => edge.edge_type))])
const visibleUserLinks = computed(() => store.visibleEdges.filter(edge => edge.edge_type === 'user_link' || edge.id.startsWith('user:')))
const primaryResourceCount = computed(() => store.viewMode === 'components' ? store.architectureSourceNodes.length : store.visibleNodes.length)
const primaryConnectionCount = computed(() => store.viewMode === 'components' ? store.architectureSourceEdges.length : store.visibleEdges.length)
const selectedWorkflowExecutionArn = ref('')
const workflowExecutionsLoading = ref(false)
const workflowHistoryLoading = ref(false)
const workflowExecutionError = ref('')
const activeWorkflowTitle = computed(() => store.activeStateMachineNode?.name || 'Step Functions workflow')
const workflowRecentExecutions = computed(() => store.activeStateMachineAsl?.recent_executions || [])

const graphBounds = computed(() => {
  const points = Object.values(store.positions)
  if (!points.length) {
    return { minX: -800, minY: -400, width: 2200, height: 1900 }
  }
  const minX = Math.min(...points.map(p => p.x))
  const maxX = Math.max(...points.map(p => p.x))
  const minY = Math.min(...points.map(p => p.y))
  const maxY = Math.max(...points.map(p => p.y))
  return {
    minX,
    minY,
    width: Math.max(600, maxX - minX),
    height: Math.max(600, maxY - minY),
  }
})

const layerDefinitions = computed(() => buildLayerDefinitions(store.layoutLayers, store.customLayers))
const visibleLayerIds = computed(() => {
  const ids = new Set<string>()
  for (const node of store.visibleNodes) {
    ids.add(node.position_hint?.tier || 'compute')
  }
  return ids
})
const visibleLayerDefinitions = computed(() =>
  layerDefinitions.value.filter(layer => visibleLayerIds.value.has(layer.id))
)
const layerRailLayers = computed(() =>
  layerDefinitions.value.map(layer => ({
    ...layer,
    count: store.visibleNodes.filter(node => (node.position_hint?.tier || 'compute') === layer.id).length,
    canDelete: store.customLayers.some(customLayer => customLayer.id === layer.id)
      && [...store.nodes, ...store.userNodes].filter(node => (node.position_hint?.tier || 'compute') === layer.id).length === 0,
  }))
)

const tierBands = computed(() => {
  if (store.viewMode === 'organization') return []
  const tierNodes: Record<string, number[]> = {}
  for (const node of store.visibleNodes) {
    const tier = node.position_hint?.tier || 'compute'
    const pos = store.positions[node.id]
    if (!pos) continue
    if (!tierNodes[tier]) tierNodes[tier] = []
    tierNodes[tier].push(pos.y)
  }

  const bands: Array<{
    id: string
    name: string
    yStart: number
    yEnd: number
    fill: string
    stroke: string
    chipFill: string
    chipStroke: string
    chipAccent: string
    labelY: number
    icon: string
  }> = []
  for (const layer of visibleLayerDefinitions.value) {
    const ys = tierNodes[layer.id]
    if (!ys || ys.length === 0) continue
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const padding = 80
    bands.push({
      id: layer.id,
      name: layer.label,
      yStart: minY - padding,
      yEnd: maxY + padding,
      fill: layer.fill,
      stroke: layer.stroke,
      chipFill: layer.fill,
      chipStroke: layer.stroke,
      chipAccent: layer.accent,
      labelY: (minY + maxY) / 2,
      icon: layer.icon,
    })
  }

  return bands
})

const tierDividers = computed(() => {
  const dividers: Array<{ name: string; y: number; stroke: string }> = []
  if (store.viewMode === 'organization') return dividers
  for (let i = 0; i < tierBands.value.length - 1; i++) {
    const current = tierBands.value[i]
    const next = tierBands.value[i + 1]
    dividers.push({
      name: `${current.name}-${next.name}`,
      y: (current.yEnd + next.yStart) / 2,
      stroke: 'rgba(255,255,255,0.18)',
    })
  }
  return dividers
})

const hoveredTier = computed(() => {
  if (!store.hoveredNodeId) return null
  const node =
    store.graphNodes.find(n => n.id === store.hoveredNodeId) ||
    store.userNodes.find(n => n.id === store.hoveredNodeId) ||
    store.nodes.find(n => n.id === store.hoveredNodeId)
  return node?.position_hint?.tier || null
})

const architectureStrip = computed(() => {
  const counts: Record<string, number> = Object.fromEntries(store.layoutLayers.map(layerId => [layerId, 0]))
  const sourceNodes = store.viewMode === 'components' ? store.architectureSourceNodes : store.visibleNodes
  for (const node of sourceNodes) {
    const tier = node.position_hint?.tier || 'compute'
    counts[tier] = (counts[tier] || 0) + 1
  }
  return layerDefinitions.value.map(layer => ({
    name: layer.id,
    short: layer.short,
    count: counts[layer.id] || 0,
    accent: layer.accent,
    bg: layer.fill.replace('0.09', '0.16').replace('0.085', '0.16').replace('0.10', '0.16').replace('0.08', '0.16'),
  }))
})

const draggingNodeName = computed(() => {
  if (!store.draggingNodeId) return null
  return store.visibleNodes.find(node => node.id === store.draggingNodeId)?.name
    || store.userNodes.find(node => node.id === store.draggingNodeId)?.name
    || store.nodes.find(node => node.id === store.draggingNodeId)?.name
    || null
})

const dragTargetLayerLabel = computed(() => {
  if (!store.dragTargetLayerId) return null
  return layerDefinitions.value.find(layer => layer.id === store.dragTargetLayerId)?.label || store.dragTargetLayerId
})
const selectionStatus = computed(() => {
  if (store.selectedNode) return `selected: ${store.selectedNode.name}`
  if (store.selectedEdge) return `selected link: ${store.selectedEdge.label || store.selectedEdge.edge_type}`
  return 'nothing selected'
})
const selectedEditorItem = computed(() => {
  if (store.selectedNode) {
    return {
      kind: 'selected node',
      label: store.selectedNode.name,
    }
  }
  if (store.selectedEdge) {
    return {
      kind: 'selected link',
      label: store.selectedEdge.label || store.selectedEdge.edge_type,
    }
  }
  return null
})
const selectedEdgeIsEditable = computed(() => {
  const edge = store.selectedEdge
  if (!edge) return false
  return edge.edge_type.startsWith('manual_') || edge.edge_type === 'user_link' || edge.id.startsWith('user:')
})
const selectedNodeHasComponent = computed(() => {
  if (!store.selectedNodeId) return false
  return store.componentSummaries.some(summary => summary.nodeIds.includes(store.selectedNodeId as string))
})
const modeHint = computed(() => {
  switch (store.editSubmode) {
    case 'inspect':
      return 'safe mode: review and select items'
    case 'structure':
      return 'move nodes, manage layers, add components'
    case 'connect':
      return store.connectingFromNodeId ? 'choose a target node to create a link' : 'select a node and start a link'
    default:
      return ''
  }
})

const viewModeLabel = computed(() => {
  if (store.viewMode === 'step_function') return 'Step Functions workflow'
  if (store.viewMode === 'architecture') return 'architecture view'
  if (store.viewMode === 'components') return 'component landing'
  if (store.viewMode === 'organization') return 'organization view'
  const sourceType = String(store.metadata?.source_type || '').toLowerCase()
  if (sourceType === 'cloudformation') return 'cloudformation raw view'
  if (sourceType === 'terraform') return 'terraform raw view'
  return 'raw view'
})

function shortExecutionArn(arn: string): string {
  return arn.split(':').pop()?.split('/').pop() || arn
}

async function loadWorkflowExecutions() {
  const nodeId = store.activeStateMachineNodeId
  if (!nodeId) return
  workflowExecutionsLoading.value = true
  workflowExecutionError.value = ''
  try {
    const res = await fetch('/api/sfn-executions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error || 'Could not load recent executions.')
    const machine = store.activeStateMachineNode
    if (machine?.properties?.asl_graph) {
      machine.properties.asl_graph.recent_executions = Array.isArray(data.executions) ? data.executions : []
    }
    selectedWorkflowExecutionArn.value = data.executions?.[0]?.execution_arn || ''
  } catch (err) {
    workflowExecutionError.value = err instanceof Error
      ? err.message
      : 'Your AWS profile can view the state machine definition, but not execution history. Add states:ListExecutions and states:GetExecutionHistory to use debugging overlays.'
  } finally {
    workflowExecutionsLoading.value = false
  }
}

async function loadWorkflowExecutionHistory() {
  const nodeId = store.activeStateMachineNodeId
  const executionArn = selectedWorkflowExecutionArn.value
  if (!nodeId || !executionArn) return
  workflowHistoryLoading.value = true
  workflowExecutionError.value = ''
  try {
    const res = await fetch('/api/sfn-execution-history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, execution_arn: executionArn }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error || 'Could not load execution history.')
    store.applyStateMachineExecutionHistory(nodeId, executionArn, data.states || {}, data.execution || {})
  } catch (err) {
    workflowExecutionError.value = err instanceof Error
      ? err.message
      : 'Your AWS profile can view the state machine definition, but not execution history. Add states:ListExecutions and states:GetExecutionHistory to use debugging overlays.'
  } finally {
    workflowHistoryLoading.value = false
  }
}

const diffSummaryMeta = computed(() => {
  const summary = store.metadata?.diff_summary
  if (!summary || typeof summary !== 'object') return null
  return summary as { added: number; removed: number; modified: number; unchanged: number }
})

const undoShortcutLabel = computed(() => isMacLike ? '⌘Z' : 'Ctrl+Z')
const redoShortcutLabel = computed(() => isMacLike ? '⇧⌘Z' : 'Ctrl+Y')
const connectHints = computed(() =>
  MANUAL_EDGE_TYPES.map(type => ({
    label: type.label,
    color: EDGE_COLORS[type.id] || '#94a3b8',
  }))
)
const showConnectHint = ref(true)
const layerRailPosition = ref({ x: 0, y: 152 })
const layerRailDragOffset = ref({ x: 0, y: 0 })
const draggingLayerRail = ref(false)
const showLayerEditor = ref(false)
const editingLayerId = ref<string | null>(null)
const layerEditLabel = ref('')
const layerEditIcon = ref('')
const layerEditAccent = ref('#4ADE80')
const editingLayer = computed(() =>
  editingLayerId.value ? store.customLayers.find(layer => layer.id === editingLayerId.value) || null : null
)
const layerRailStyle = computed(() => ({
  left: `${layerRailPosition.value.x}px`,
  top: `${layerRailPosition.value.y}px`,
}))

function tierBandOpacity(bandName: string): number {
  if (store.dragTargetLayerId) return store.dragTargetLayerId === bandName ? 0.95 : 0.36
  if (!hoveredTier.value) return 0.65
  return hoveredTier.value === bandName ? 0.95 : 0.28
}

function tierBorderOpacity(bandName: string): number {
  if (store.dragTargetLayerId) return store.dragTargetLayerId === bandName ? 0.95 : 0.26
  if (!hoveredTier.value) return 0.45
  return hoveredTier.value === bandName ? 0.9 : 0.2
}

function tierDividerOpacity(dividerName: string): number {
  if (!hoveredTier.value) return 0.22
  return dividerName.includes(hoveredTier.value) ? 0.45 : 0.15
}

function tierChipOpacity(bandName: string): number {
  if (store.dragTargetLayerId) return store.dragTargetLayerId === bandName ? 1 : 0.56
  if (!hoveredTier.value) return 0.9
  return hoveredTier.value === bandName ? 1 : 0.45
}

function edgeColor(edgeType: string): string {
  return EDGE_COLORS[edgeType] || '#64748b'
}

function edgeTypeLegendLabel(edgeType: string): string {
  if (edgeType.startsWith('manual_')) {
    return edgeType.replace('manual_', '').replace(/_/g, ' ')
  }
  if (edgeType === 'cross_account_reference') return 'cross-account'
  return edgeType.replace(/_/g, ' ')
}

function edgeTypeKindLabel(edgeType: string): string {
  if (edgeType.startsWith('manual_') || edgeType === 'user_link') return 'manual'
  if (edgeType === 'cross_account_reference') return 'cross'
  return 'inferred'
}

function edgeTypeKindClass(edgeType: string): string {
  if (edgeType.startsWith('manual_') || edgeType === 'user_link') return 'legend-pill legend-pill--manual'
  if (edgeType === 'cross_account_reference') return 'legend-pill legend-pill--cross'
  return 'legend-pill legend-pill--inferred'
}

function sanitizeMarkerId(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '-')
}

function edgeSourcePos(edge: StackMapEdge) {
  const pos = store.positions[edge.source]
  if (!pos) return { x: 0, y: 0 }
  const node = visibleNodeMap.value.get(edge.source)
  if (!node) return pos
  const h = getNodeHeight(node)
  const targetPos = store.positions[edge.target]
  if (!targetPos) return pos
  const dy = targetPos.y - pos.y
  return { x: pos.x, y: pos.y + (dy > 0 ? h / 2 : -h / 2) }
}

function edgeTargetPos(edge: StackMapEdge) {
  const pos = store.positions[edge.target]
  if (!pos) return { x: 0, y: 0 }
  const node = visibleNodeMap.value.get(edge.target)
  if (!node) return pos
  const h = getNodeHeight(node)
  const sourcePos = store.positions[edge.source]
  if (!sourcePos) return pos
  const dy = sourcePos.y - pos.y
  return { x: pos.x, y: pos.y + (dy > 0 ? h / 2 : -h / 2) }
}

function onPanToNodeEvent(event: Event) {
  const nodeId = (event as CustomEvent<{ nodeId?: string }>).detail?.nodeId
  if (nodeId) panToNode(nodeId)
}

onMounted(async () => {
  try {
    await store.loadFromJSON('/api/graph')
  } catch {
    // Fallback for static/offline exports that only ship sample-data.json.
    await store.loadFromJSON('/sample-data.json')
  }

  recomputeLayout()

  if (svgRef.value && zoomGroupRef.value) {
    svgSelection = d3.select(svgRef.value)
    const g = d3.select(zoomGroupRef.value)

    zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', event => {
        g.attr('transform', event.transform.toString())
        zoomScale.value = event.transform.k
        store.setZoomScale(event.transform.k)
        updateViewport(event.transform)
      })

    svgSelection.call(zoomBehavior)
    fitToViewport()
  }

  window.addEventListener('keydown', onKeydown)
  window.addEventListener('stackmap-fit-view', onFitViewEvent)
  window.addEventListener('stackmap-pan-to-node', onPanToNodeEvent)
  initializeLayerRailPosition()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('stackmap-fit-view', onFitViewEvent)
  window.removeEventListener('stackmap-pan-to-node', onPanToNodeEvent)
  stopLayerRailDrag()
})

watch(
  () => ({
    viewMode: store.viewMode,
    diffMode: store.diffMode,
    diffSlider: store.diffSlider,
    zoomTier: store.zoomTier,
    visibleNodeIds: store.visibleNodes.map(n => n.id).join('|'),
    visibleEdgeIds: store.visibleEdges.map(e => e.id).join('|'),
    groupIds: store.graphGroups.map(g => g.id).join('|'),
    activeAccountId: store.activeAccountId,
    activeComponentId: store.activeComponentId,
    layoutVersion: store.layoutVersion,
  }),
  async (nextState, prevState) => {
    if (!store.loaded) return
    recomputeLayout()
    await nextTick()
    const zoomTierOnly = Boolean(prevState)
      && nextState.zoomTier !== prevState.zoomTier
      && nextState.viewMode === prevState.viewMode
      && nextState.diffMode === prevState.diffMode
      && nextState.diffSlider === prevState.diffSlider
      && nextState.groupIds === prevState.groupIds
      && nextState.activeAccountId === prevState.activeAccountId
      && nextState.activeComponentId === prevState.activeComponentId
      && nextState.layoutVersion === prevState.layoutVersion
    if (!zoomTierOnly) fitToViewport()
  }
)

watch(
  () => [store.editSubmode, store.connectingFromNodeId],
  ([submode, connectingFromNodeId], [prevSubmode, prevConnectingFromNodeId]) => {
    if (submode !== 'connect') {
      showConnectHint.value = true
      return
    }
    if (prevSubmode !== 'connect' || connectingFromNodeId !== prevConnectingFromNodeId) {
      showConnectHint.value = true
    }
  }
)

function onFitViewEvent() {
  fitToViewport()
}

function dismissConnectHint() {
  showConnectHint.value = false
}

function initializeLayerRailPosition() {
  const container = containerRef.value
  if (!container) return
  const width = container.clientWidth || 1200
  const maxX = Math.max(16, width - 240)
  layerRailPosition.value = {
    x: Math.min(maxX, Math.max(Math.floor(width * 0.72), width - 280)),
    y: 152,
  }
}

function onKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') {
    if (e.key === 'Escape') {
      ;(e.target as HTMLElement).blur()
      store.selectNode(null)
    }
    return
  }

  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    emit('toggleCommandPalette')
    return
  }

  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
    e.preventDefault()
    if (e.shiftKey) {
      store.redoEdits()
    } else {
      store.undoEdits()
    }
    return
  }

  if (!isMacLike && e.ctrlKey && e.key.toLowerCase() === 'y') {
    e.preventDefault()
    store.redoEdits()
    return
  }

  switch (e.key) {
    case '/':
      e.preventDefault()
      searchBarRef.value?.focus()
      break
    case 'Escape':
      if (store.connectingFromNodeId) {
        store.cancelConnecting()
      } else {
        clearSelection()
      }
      showHelp.value = false
      break
    case '0':
    case ' ':
      e.preventDefault()
      fitToViewport()
      break
    case '=':
    case '+':
      e.preventDefault()
      zoomBy(1.3)
      break
    case '-':
      e.preventDefault()
      zoomBy(0.7)
      break
    case '?':
      showHelp.value = !showHelp.value
      break
    case 'p':
    case 'P':
      store.setPresentationMode(!store.presentationMode)
      break
  }
}

const SIDEBAR_WIDTH = 256
const DETAIL_PANEL_WIDTH = 0 // Detail panel overlaps, accounted only when open

function fitToViewport() {
  if (!svgSelection || !zoomBehavior) return

  const positions = Object.values(store.positions)
  if (!positions.length) return

  const padding = 120
  const minX = Math.min(...positions.map(p => p.x)) - padding
  const maxX = Math.max(...positions.map(p => p.x)) + padding
  const minY = Math.min(...positions.map(p => p.y)) - padding
  const maxY = Math.max(...positions.map(p => p.y)) + padding

  const totalWidth = svgRef.value?.clientWidth || 1000
  const height = (svgRef.value?.clientHeight || 800) - 40 // subtract status bar
  // Account for sidebar taking space on the left
  const availableWidth = totalWidth - SIDEBAR_WIDTH
  const offsetX = SIDEBAR_WIDTH

  const graphWidth = Math.max(1, maxX - minX)
  const graphHeight = Math.max(1, maxY - minY)
  const scale = Math.min(availableWidth / graphWidth, height / graphHeight, 1.45)
  const tx = offsetX + availableWidth / 2 - (minX + graphWidth / 2) * scale
  const ty = height / 2 - (minY + graphHeight / 2) * scale

  svgSelection.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
}

function clearSelection() {
  store.selectNode(null)
  store.selectEdge(null)
}

function activateConnectForSelectedNode() {
  if (!store.selectedNode) return
  store.setEditSubmode('connect')
  store.startConnecting(store.selectedNode.id)
}

function recomputeLayout() {
  const allNodes = store.visibleNodes
  const allEdges = store.visibleEdges
  const positions = store.diffMode
    ? computeDiffLayout()
    : computeLayout(allNodes, allEdges, store.graphGroups, visibleLayerDefinitions.value.map(layer => layer.id), { mode: store.relayoutMode })
  store.setPositions(positions)
}

function onNodeDragStart(payload: { nodeId: string; clientX: number; clientY: number }) {
  if (!store.editMode || store.editSubmode !== 'structure' || store.viewMode === 'organization') return
  store.startDraggingNode(payload.nodeId)
  updateDragTargetFromPointer(payload.clientX, payload.clientY)
}

function onNodeDragMove(payload: { nodeId: string; clientX: number; clientY: number }) {
  if (store.draggingNodeId !== payload.nodeId) return
  updateDragTargetFromPointer(payload.clientX, payload.clientY)
}

async function onNodeDragEnd(payload: { nodeId: string; clientX: number; clientY: number }) {
  if (store.draggingNodeId !== payload.nodeId) return
  updateDragTargetFromPointer(payload.clientX, payload.clientY)
  const targetLayerId = store.dragTargetLayerId
  store.finishDraggingNode(targetLayerId)
  if (targetLayerId) {
    reorderNodeWithinLayer(payload.nodeId, targetLayerId, payload.clientX, payload.clientY)
  }
  await nextTick()
  fitToViewport()
}

function reorderNodeWithinLayer(nodeId: string, layerId: string, clientX: number, clientY: number) {
  const graphPoint = graphPointFromClient(clientX, clientY)
  if (!graphPoint) return
  const peerNodes = store.visibleNodes
    .filter(node => node.id !== nodeId && (node.position_hint?.tier || 'compute') === layerId)
    .sort((a, b) => (store.positions[a.id]?.x || 0) - (store.positions[b.id]?.x || 0))

  const orderedIds = peerNodes.map(node => node.id)
  const insertionIndex = peerNodes.findIndex(node => graphPoint.x < (store.positions[node.id]?.x || 0))
  if (insertionIndex === -1) {
    orderedIds.push(nodeId)
  } else {
    orderedIds.splice(insertionIndex, 0, nodeId)
  }
  store.reorderNodesWithinLayer(orderedIds, layerId)
}

function graphPointFromClient(clientX: number, clientY: number) {
  const svg = svgRef.value
  if (!svg || !zoomGroupRef.value || !zoomBehavior) return null
  const screenPoint = svg.createSVGPoint()
  screenPoint.x = clientX
  screenPoint.y = clientY
  const zoomMatrix = zoomGroupRef.value.getScreenCTM()
  if (!zoomMatrix) return null
  return screenPoint.matrixTransform(zoomMatrix.inverse())
}

function updateDragTargetFromPointer(clientX: number, clientY: number) {
  const hoveredElement = document.elementFromPoint(clientX, clientY) as HTMLElement | null
  const explicitLayerTarget = hoveredElement?.closest?.('[data-layer-drop-target]')?.getAttribute('data-layer-drop-target')
  if (explicitLayerTarget) {
    store.setDragTargetLayer(explicitLayerTarget)
    return
  }

  const graphPoint = graphPointFromClient(clientX, clientY)
  if (!graphPoint) return
  const targetBand = tierBands.value.find(band => graphPoint.y >= band.yStart && graphPoint.y <= band.yEnd)
  if (targetBand) {
    store.setDragTargetLayer(targetBand.id)
    return
  }

  const nearestBand = [...tierBands.value].sort((a, b) => {
    const aCenter = (a.yStart + a.yEnd) / 2
    const bCenter = (b.yStart + b.yEnd) / 2
    return Math.abs(aCenter - graphPoint.y) - Math.abs(bCenter - graphPoint.y)
  })[0]
  store.setDragTargetLayer(nearestBand?.id || null)
}

function onLayerRailPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  const container = containerRef.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  draggingLayerRail.value = true
  layerRailDragOffset.value = {
    x: event.clientX - rect.left - layerRailPosition.value.x,
    y: event.clientY - rect.top - layerRailPosition.value.y,
  }
  window.addEventListener('pointermove', onLayerRailPointerMove)
  window.addEventListener('pointerup', stopLayerRailDrag)
  window.addEventListener('pointercancel', stopLayerRailDrag)
}

function onLayerRailPointerMove(event: PointerEvent) {
  const container = containerRef.value
  if (!container || !draggingLayerRail.value) return
  const rect = container.getBoundingClientRect()
  const nextX = event.clientX - rect.left - layerRailDragOffset.value.x
  const nextY = event.clientY - rect.top - layerRailDragOffset.value.y
  layerRailPosition.value = {
    x: Math.min(Math.max(16, nextX), Math.max(16, rect.width - 240)),
    y: Math.min(Math.max(16, nextY), Math.max(16, rect.height - 220)),
  }
}

function stopLayerRailDrag() {
  draggingLayerRail.value = false
  window.removeEventListener('pointermove', onLayerRailPointerMove)
  window.removeEventListener('pointerup', stopLayerRailDrag)
  window.removeEventListener('pointercancel', stopLayerRailDrag)
}

function onLayerRailDragStart(event: DragEvent, layerId: string) {
  event.dataTransfer?.setData('text/plain', layerId)
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
  draggingLayerId.value = layerId
  layerRailDropTargetId.value = layerId
}

function onLayerRailDragOver(layerId: string) {
  layerRailDropTargetId.value = layerId
}

function onLayerRailDrop(layerId: string) {
  if (!draggingLayerId.value) return
  store.reorderLayers(draggingLayerId.value, layerId)
  relayoutAndFit()
  draggingLayerId.value = null
  layerRailDropTargetId.value = null
}

function onLayerRailDragEnd() {
  draggingLayerId.value = null
  layerRailDropTargetId.value = null
}

function deleteLayer(layerId: string) {
  if (!store.removeCustomLayer(layerId)) return
  relayoutAndFit()
}

function openLayerEditor(layerId: string) {
  const layer = store.customLayers.find(candidate => candidate.id === layerId)
  if (!layer) return
  editingLayerId.value = layer.id
  layerEditLabel.value = layer.label
  layerEditIcon.value = layer.icon || ''
  layerEditAccent.value = layer.accent || '#4ADE80'
  showLayerEditor.value = true
}

function closeLayerEditor() {
  showLayerEditor.value = false
  editingLayerId.value = null
}

function saveLayerEditor() {
  if (!editingLayer.value) return
  store.updateCustomLayer(editingLayer.value.id, {
    label: layerEditLabel.value,
    icon: layerEditIcon.value.trim() || undefined,
    accent: layerEditAccent.value,
  })
  relayoutAndFit()
  closeLayerEditor()
}

function computeDiffLayout(): Record<string, NodePosition> {
  const allNodes = [...store.graphNodes, ...store.userNodes]
  const allEdges = [...store.graphEdges, ...store.userEdges]
  const nodeDiffStatus = store.nodeDiffStatus
  const edgeDiffStatus = store.edgeDiffStatus

  const beforeNodes = allNodes.filter(node => nodeDiffStatus[node.id] !== 'added')
  const afterNodes = allNodes.filter(node => nodeDiffStatus[node.id] !== 'removed')
  const beforeIds = new Set(beforeNodes.map(node => node.id))
  const afterIds = new Set(afterNodes.map(node => node.id))

  const beforeEdges = allEdges.filter(edge =>
    edgeDiffStatus[edge.id] !== 'added' && beforeIds.has(edge.source) && beforeIds.has(edge.target)
  )
  const afterEdges = allEdges.filter(edge =>
    edgeDiffStatus[edge.id] !== 'removed' && afterIds.has(edge.source) && afterIds.has(edge.target)
  )

  const beforePositions = computeLayout(beforeNodes, beforeEdges, store.graphGroups, store.layoutLayers, { mode: store.relayoutMode })
  const afterPositions = computeLayout(afterNodes, afterEdges, store.graphGroups, store.layoutLayers, { mode: store.relayoutMode })
  const beforeFallback = centroidForPositions(beforePositions)
  const afterFallback = centroidForPositions(afterPositions)

  const positions: Record<string, NodePosition> = {}
  for (const node of allNodes) {
    const beforePos =
      beforePositions[node.id] ??
      inferAnchorPosition(node, beforeEdges, beforePositions, beforeFallback)
    const afterPos =
      afterPositions[node.id] ??
      inferAnchorPosition(node, afterEdges, afterPositions, afterFallback)

    positions[node.id] = {
      x: lerp(beforePos.x, afterPos.x, store.diffSlider),
      y: lerp(beforePos.y, afterPos.y, store.diffSlider),
    }
  }

  return positions
}

function inferAnchorPosition(
  node: StackMapNode,
  edges: StackMapEdge[],
  positions: Record<string, NodePosition>,
  fallback: NodePosition
): NodePosition {
  const neighborPositions: NodePosition[] = []

  for (const edge of edges) {
    if (edge.source !== node.id && edge.target !== node.id) continue
    const neighborId = edge.source === node.id ? edge.target : edge.source
    const neighborPos = positions[neighborId]
    if (neighborPos) neighborPositions.push(neighborPos)
  }

  if (neighborPositions.length > 0) {
    return centroidForList(neighborPositions)
  }

  const tierPeers = [...store.graphNodes, ...store.userNodes]
    .filter(candidate => candidate.position_hint?.tier === node.position_hint?.tier)
    .map(candidate => positions[candidate.id])
    .filter((pos): pos is NodePosition => Boolean(pos))

  if (tierPeers.length > 0) {
    return centroidForList(tierPeers)
  }

  return fallback
}

function centroidForPositions(positions: Record<string, NodePosition>): NodePosition {
  const all = Object.values(positions)
  if (all.length === 0) return { x: 0, y: 0 }
  return centroidForList(all)
}

function centroidForList(points: NodePosition[]): NodePosition {
  const total = points.reduce(
    (acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }),
    { x: 0, y: 0 }
  )
  return {
    x: total.x / points.length,
    y: total.y / points.length,
  }
}

function lerp(from: number, to: number, t: number): number {
  return from + (to - from) * t
}

function zoomBy(factor: number) {
  if (!svgSelection || !zoomBehavior) return
  svgSelection.transition().duration(300).call(zoomBehavior.scaleBy, factor)
}

function relayoutAndFit() {
  recomputeLayout()
  nextTick(() => fitToViewport())
}

function panToNode(nodeId: string) {
  if (!svgSelection || !zoomBehavior) return
  const pos = store.positions[nodeId]
  if (!pos) return

  const width = svgRef.value?.clientWidth || 1000
  const height = svgRef.value?.clientHeight || 800
  const scale = 1.2

  svgSelection
    .transition()
    .duration(500)
    .call(zoomBehavior.transform, d3.zoomIdentity.translate(width / 2 - pos.x * scale, height / 2 - pos.y * scale).scale(scale))
}

function panToPosition(position: { x: number; y: number }) {
  if (!svgSelection || !zoomBehavior) return
  const width = svgRef.value?.clientWidth || 1000
  const height = svgRef.value?.clientHeight || 800
  const scale = zoomScale.value || 1
  svgSelection.call(
    zoomBehavior.transform,
    d3.zoomIdentity.translate(width / 2 - position.x * scale, height / 2 - position.y * scale).scale(scale)
  )
}

function updateViewport(transform: d3.ZoomTransform) {
  if (!svgRef.value) return
  const w = svgRef.value.clientWidth
  const h = svgRef.value.clientHeight

  viewportRect.value = {
    x: -transform.x / transform.k,
    y: -transform.y / transform.k,
    width: w / transform.k,
    height: h / transform.k,
  }
}

function clearBreadcrumbScope() {
  store.activeComponentId = null
  store.setActiveOrgGroup(null)
  store.setActiveAccount(null)
  if (store.hasOrganizationData && store.metadata?.scan_mode === 'organization') {
    store.setViewMode('organization')
    return
  }
  if (store.shouldUseComponentLanding) {
    store.setViewMode('components')
    return
  }
  store.setViewMode('architecture')
}

const emit = defineEmits<{
  toggleCommandPalette: []
}>()

defineExpose({ fitToViewport, panToNode })
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.help-panel-enter-active {
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}
.help-panel-leave-active {
  transition: all 0.12s ease;
}
.help-panel-enter-from {
  opacity: 0;
  transform: scale(0.95) translateY(-4px);
}
.help-panel-leave-to {
  opacity: 0;
  transform: scale(0.97);
}

.selection-action {
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  padding: 6px 10px;
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  color: rgba(209, 213, 219, 0.9);
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.selection-action:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.98);
}

.selection-action--accent {
  border-color: rgba(74, 222, 128, 0.24);
  background: rgba(74, 222, 128, 0.12);
  color: rgba(167, 243, 208, 0.98);
}

.selection-action--accent:hover {
  background: rgba(74, 222, 128, 0.18);
}

.selection-action--danger {
  border-color: rgba(248, 113, 113, 0.22);
  background: rgba(239, 68, 68, 0.12);
  color: rgba(252, 165, 165, 0.98);
}

.selection-action--danger:hover {
  background: rgba(239, 68, 68, 0.18);
}

.legend-pill {
  color: rgba(156, 163, 175, 0.9);
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.legend-pill--manual {
  color: rgba(167, 243, 208, 0.96);
  border-color: rgba(74, 222, 128, 0.18);
  background: rgba(74, 222, 128, 0.08);
}

.legend-pill--cross {
  color: rgba(221, 214, 254, 0.96);
  border-color: rgba(192, 132, 252, 0.18);
  background: rgba(192, 132, 252, 0.08);
}

.legend-pill--inferred {
  color: rgba(191, 219, 254, 0.96);
  border-color: rgba(148, 163, 184, 0.18);
  background: rgba(148, 163, 184, 0.08);
}

.status-glow {
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0));
}
</style>
