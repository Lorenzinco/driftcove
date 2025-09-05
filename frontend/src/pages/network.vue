<template>
    <v-container fluid class="pa-4 fill-height w-100 network-page" :class="{'inspector-open': store.inspectorOpen}">
    <v-sheet rounded="lg" class="pa-0 w-100 layout-no-nested-right" elevation="2">
    <div class="d-flex align-center justify-space-between px-4 pt-4">
        <div class="d-flex align-center ga-2">
            <v-img src="@/assets/logo.png" alt="Application Logo" class="w-25" />
            <v-btn :variant="store.tool==='select' ? 'elevated' : 'tonal'" @click="store.tool='select'" prepend-icon="mdi-cursor-default">Select</v-btn>
            <v-btn :variant="store.tool==='connect' ? 'elevated' : 'tonal'" @click="store.tool='connect'" prepend-icon="mdi-connection">Connect</v-btn>
            <v-btn :variant="store.tool==='cut' ? 'elevated' : 'tonal'" @click="store.tool='cut'" prepend-icon="mdi-content-cut">Cut</v-btn>
            <v-divider vertical class="mx-2" />
            <v-btn :variant="store.tool==='add-subnet' ? 'elevated' : 'tonal'" @click="store.tool='add-subnet'" prepend-icon="mdi-lan">Subnet</v-btn>
            <v-switch v-model="store.grid" inset hide-details label="Grid" class="ma-0 pa-0 switch-inline" style="min-width:auto;" />
        </div>
        <div class="text-caption text-medium-emphasis">
            Zoom: {{ (store.zoom*100).toFixed(0) }}% &nbsp; | &nbsp; Pan: {{ store.pan.x.toFixed(0) }}, {{ store.pan.y.toFixed(0) }}
            <v-btn
            :prepend-icon="store.inspectorOpen ? 'mdi-chevron-right' : 'mdi-chevron-left'"
            @click="store.toggleInspector()"
            />
        </div>
    </div>


    <div style="height: 77vh;" class="px-3 pb-3 w-100">
                <CanvasStage ref="canvasStage" @subnet-click="onSubnetClick" @add-subnet-request="onAddSubnetRequest">
                    <SubnetContext ref="subnetContext" />
                    <PeerDetailsDialog />
                    <AddSubnetDialog ref="addSubnetDialog" />
                    <LinkTypeDialog ref="linkTypeDialog" />
                </CanvasStage>
    </div>
    </v-sheet>


    <v-card class="mt-4 w-100" variant="tonal">
    <v-card-text>
    <div class="d-flex align-center ga-6">
        <div><span class="legend-dot" style="background:#7AD7F0"></span> Peer</div>
        <div><span class="legend-dot" style="background:#7CF29A"></span> Subnet (boundary)</div>
        <div><span class="legend-dot" style="background:#86A1FF"></span> Link</div>
        <v-spacer />
        <div class="text-caption text-medium-emphasis">Wheel to zoom • Middle drag or Shift+Drag to pan • Del to delete • Esc to exit tool</div>
    </div>
    </v-card-text>
    </v-card>
    </v-container>
</template>


<script setup lang="ts">
    import CanvasStage from '@/components/canvas/CanvasStage.vue'
    import SubnetContext from '@/components/canvas/overlays/SubnetContext.vue'
    import PeerDetailsDialog from '@/components/canvas/overlays/PeerDetailsDialog.vue'
    import { useNetworkStore } from '@/stores/network'
    import AddSubnetDialog from '@/components/canvas/overlays/AddSubnetDialog.vue'
    import LinkTypeDialog from '@/components/canvas/overlays/LinkTypeDialog.vue'
    import { onMounted, onBeforeUnmount } from 'vue'
    import { useBackendInteractionStore } from '@/stores/backendInteraction'

    const store = useNetworkStore()
    const subnetContext = ref<InstanceType<typeof SubnetContext> | null>(null)
    const addSubnetDialog = ref<InstanceType<typeof AddSubnetDialog> | null>(null)
    const canvasStage = ref<any>(null)
    const linkTypeDialog = ref<InstanceType<typeof LinkTypeDialog> | null>(null)
    const backend = useBackendInteractionStore()

    function onSubnetClick(e:{ id:string; x:number; y:number }) {
        // Only open the subnet context menu while in select tool
        if (store.tool !== 'select') return;
        if (!e.id) { subnetContext.value?.hideMenu?.(); return; }
        subnetContext.value?.showMenu(e);
    }
    function onAddSubnetRequest(pos:{ worldX:number; worldY:number }) { addSubnetDialog.value?.showAt(pos.worldX, pos.worldY) }

    function handleSubnetDialogClosed(){ canvasStage.value?.clearGhostSubnet?.(); }
    function handleRequestLinkType(e: any){ const { from, to } = e.detail||{}; if (from && to) linkTypeDialog.value?.show(from, to); }
    onMounted(()=> { backend.startTopologyPolling(1000); window.addEventListener('add-subnet-dialog-closed', handleSubnetDialogClosed); window.addEventListener('request-link-type', handleRequestLinkType) })
    onBeforeUnmount(()=> { backend.stopTopologyPolling(); window.removeEventListener('add-subnet-dialog-closed', handleSubnetDialogClosed); window.removeEventListener('request-link-type', handleRequestLinkType) })
</script>


<style scoped>
    .legend-dot { width: 12px; height: 12px; border-radius: 9999px; display: inline-block; margin-right: 8px; }
    .switch-inline :deep(.v-label) { white-space: nowrap; display:inline-block; }
        .layout-no-nested-right { /* prevent cascading double right padding from drawer variable */
            --v-layout-right: 0 !important;
            padding-right: 0 !important;
            margin-right: 0 !important;
        }
        /* Only zero for nested content while keeping overall app shift */
        .network-page.inspector-open > .layout-no-nested-right { --v-layout-right: 0 !important; }
</style>