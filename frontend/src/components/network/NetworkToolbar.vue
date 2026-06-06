<template>
  <div class="d-flex align-center justify-space-between px-4 pt-4">
    <div class="d-flex align-center ga-2">
      <BrandLogo height="72px" />
      <v-btn prepend-icon="mdi-cursor-default" :variant="buttonVariant('select')" @click="store.tool = 'select'">
        Select
      </v-btn>
      <v-btn prepend-icon="mdi-connection" :variant="buttonVariant('connect')" @click="store.tool = 'connect'">
        Connect
      </v-btn>
      <v-btn prepend-icon="mdi-content-cut" :variant="buttonVariant('cut')" @click="store.tool = 'cut'">
        Cut
      </v-btn>
      <v-divider class="mx-2" vertical />
      <v-btn prepend-icon="mdi-lan" :variant="buttonVariant('add-subnet')" @click="store.tool = 'add-subnet'">
        Subnet
      </v-btn>
      <v-switch
        v-model="store.grid"
        class="ma-0 pa-0 switch-inline"
        hide-details
        inset
        label="Grid"
        style="min-width: auto"
      />
    </div>

    <div class="text-caption text-medium-emphasis">
      Zoom: {{ (store.zoom * 100).toFixed(0) }}% &nbsp; | &nbsp; Pan:
      {{ store.pan.x.toFixed(0) }}, {{ store.pan.y.toFixed(0) }}
      <v-btn
        :prepend-icon="store.inspectorOpen ? 'mdi-chevron-right' : 'mdi-chevron-left'"
        @click="store.toggleInspector()"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import type { Tool } from '@/types/network'
  import BrandLogo from '@/components/BrandLogo.vue'
  import { useNetworkStore } from '@/stores/network'

  const store = useNetworkStore()

  function buttonVariant (tool: Tool) {
    return store.tool === tool ? 'elevated' : 'tonal'
  }
</script>

<style scoped>
.switch-inline :deep(.v-label) {
  white-space: nowrap;
  display: inline-block;
}
</style>
