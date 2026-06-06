<template>
  <v-container
    class="pa-4 fill-height w-100 network-page"
    :class="{ 'inspector-open': store.inspectorOpen }"
    fluid
  >
    <v-sheet
      class="pa-0 w-100 layout-no-nested-right"
      elevation="2"
      rounded="lg"
    >
      <NetworkToolbar />

      <div class="px-3 pb-3 w-100" style="height: 77vh">
        <CanvasStage
          ref="canvasStage"
          @add-subnet-request="onAddSubnetRequest"
          @canvas-context="onCanvasContext"
          @peer-click="onPeerClick"
          @subnet-click="onSubnetClick"
        >
          <SubnetContext ref="subnetContext" />
          <NetworkContext ref="networkContext" />
          <PeerContext ref="peerContext" />
          <PeerDetailsDialog />
          <AddSubnetDialog ref="addSubnetDialog" />
          <LinkTypeDialog ref="linkTypeDialog" />
          <CutLinkDialog ref="cutLinkDialog" />
        </CanvasStage>
      </div>
    </v-sheet>

    <NetworkLegend />
  </v-container>
</template>

<script setup lang="ts">
  import { onBeforeUnmount, onMounted, ref } from 'vue'
  import CanvasStage from '@/components/canvas/CanvasStage.vue'
  import AddSubnetDialog from '@/components/canvas/overlays/AddSubnetDialog.vue'
  import CutLinkDialog from '@/components/canvas/overlays/CutLinkDialog.vue'
  import LinkTypeDialog from '@/components/canvas/overlays/LinkTypeDialog.vue'
  import NetworkContext from '@/components/canvas/overlays/NetworkContext.vue'
  import PeerContext from '@/components/canvas/overlays/PeerContext.vue'
  import PeerDetailsDialog from '@/components/canvas/overlays/PeerDetailsDialog.vue'
  import SubnetContext from '@/components/canvas/overlays/SubnetContext.vue'
  import NetworkLegend from '@/components/network/NetworkLegend.vue'
  import NetworkToolbar from '@/components/network/NetworkToolbar.vue'
  import { useBackendInteractionStore } from '@/stores/backendInteraction'
  import { useNetworkStore } from '@/stores/network'
  import { pairKey } from '@/utils/networkTopology'

  const store = useNetworkStore()
  const backend = useBackendInteractionStore()

  const subnetContext = ref<InstanceType<typeof SubnetContext> | null>(null)
  const peerContext = ref<InstanceType<typeof PeerContext> | null>(null)
  const networkContext = ref<InstanceType<typeof NetworkContext> | null>(null)
  const addSubnetDialog = ref<InstanceType<typeof AddSubnetDialog> | null>(null)
  const canvasStage = ref<InstanceType<typeof CanvasStage> | null>(null)
  const linkTypeDialog = ref<InstanceType<typeof LinkTypeDialog> | null>(null)
  const cutLinkDialog = ref<InstanceType<typeof CutLinkDialog> | null>(null)

  function onSubnetClick (event: { id: string, x: number, y: number }) {
    if (store.tool !== 'select') return
    if (!event.id) {
      subnetContext.value?.hideMenu?.()
      return
    }
    subnetContext.value?.showMenu(event)
  }

  function onPeerClick (event: { id: string, x: number, y: number }) {
    if (store.tool !== 'select') return
    if (!event.id) {
      peerContext.value?.hideMenu?.()
      return
    }

    const lastPointer = (window as any).__lastPointerScreen
    peerContext.value?.showMenu({
      id: event.id,
      x: typeof event.x === 'number' ? event.x : lastPointer?.x || 0,
      y: typeof event.y === 'number' ? event.y : lastPointer?.y || 0,
    })
  }

  function onCanvasContext (event: { x: number, y: number }) {
    if (store.tool === 'select') networkContext.value?.showMenu(event)
  }

  function onAddSubnetRequest (position: { worldX: number, worldY: number }) {
    addSubnetDialog.value?.showAt(position.worldX, position.worldY)
  }

  function handleSubnetDialogClosed () {
    canvasStage.value?.clearGhostSubnet?.()
  }

  function handleRequestLinkType (event: CustomEvent) {
    const { fromId, toId, fromType, toType } = event.detail || {}
    const from = fromId || event.detail?.from
    const to = toId || event.detail?.to
    if (from && to) linkTypeDialog.value?.show(from, to, { fromType, toType })
  }

  function handleRequestCutLink (event: CustomEvent) {
    const detail = event.detail || {}
    if (detail.links) cutLinkDialog.value?.show(detail)
  }

  function handleRequestAddSubnetAtScreen (event: CustomEvent) {
    const { screenX, screenY } = event.detail || {}
    if (typeof screenX !== 'number' || typeof screenY !== 'number') return

    addSubnetDialog.value?.showAt(
      (screenX - store.pan.x) / store.zoom,
      (screenY - store.pan.y) / store.zoom,
    )
  }

  function handleRequestDelete (event: CustomEvent) {
    const { type, id } = event.detail || {}
    if (!type || !id) return

    if (type === 'peer') {
      window.dispatchEvent(
        new CustomEvent('peer-context-request-delete', { detail: { id } }),
      )
      return
    }
    if (type === 'subnet') {
      window.dispatchEvent(
        new CustomEvent('subnet-context-request-delete', { detail: { id } }),
      )
      return
    }
    if (type === 'link') {
      const related = store.links.filter(
        link => pairKey(link.fromId, link.toId) === id,
      )
      if (related.length > 0)
        cutLinkDialog.value?.show({ pairKey: id, links: related })
    }
  }

  const windowEventHandlers = [
    ['add-subnet-dialog-closed', handleSubnetDialogClosed],
    ['request-link-type', handleRequestLinkType],
    ['request-cut-link', handleRequestCutLink],
    ['request-add-subnet-at-screen', handleRequestAddSubnetAtScreen],
    ['request-delete', handleRequestDelete],
  ] as const

  onMounted(() => {
    backend.startTopologyPolling(2000)
    for (const [eventName, handler] of windowEventHandlers) {
      window.addEventListener(eventName, handler as EventListener)
    }
  })

  onBeforeUnmount(() => {
    backend.stopTopologyPolling()
    for (const [eventName, handler] of windowEventHandlers) {
      window.removeEventListener(eventName, handler as EventListener)
    }
  })
</script>

<style scoped>
.layout-no-nested-right {
  --v-layout-right: 0 !important;
  padding-right: 0 !important;
  margin-right: 0 !important;
}

.network-page.inspector-open > .layout-no-nested-right {
  --v-layout-right: 0 !important;
}
</style>
