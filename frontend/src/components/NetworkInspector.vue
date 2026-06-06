<template>
  <div class="pa-4">
    <div class="d-flex align-center justify-space-between mb-2">
      <div class="text-h6 d-flex align-center">Network</div>
    </div>
    <v-divider class="my-4" />
    <v-expansion-panels multiple>
      <v-expansion-panel value="subnets">
        <v-expansion-panel-title class="text-subtitle-2">
          <v-icon class="me-1" icon="mdi-lan" size="18" /> Subnetworks ({{
            store.subnets.length
          }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item
              v-for="s in store.subnets"
              :key="s.id"
              :active="
                !!(
                  store.selection &&
                  store.selection.type === 'subnet' &&
                  store.selection.id === s.id
                )
              "
              rounded="sm"
              :title="s.name + ' (' + s.cidr + ')'"
              @click="selectSubnet(s)"
            >
              <template #prepend>
                <v-icon
                  class="me-1"
                  icon="mdi-hexagon-multiple-outline"
                  size="16"
                />
              </template>
            </v-list-item>
            <v-list-item
              v-if="store.subnets.length === 0"
              disabled
              title="No subnets"
            />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
      <v-expansion-panel v-if="store.selectedSubnet" value="hosts">
        <v-expansion-panel-title class="text-subtitle-2">
          <v-icon class="me-1" icon="mdi-server" size="18" /> Hosts ({{
            hostPeers.length
          }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item
              v-for="p in hostPeers"
              :key="p.id"
              :active="
                !!(
                  store.selection &&
                  store.selection.type === 'peer' &&
                  store.selection.id === p.id
                )
              "
              rounded="sm"
              :title="p.name + (p.ip ? ' (' + p.ip + ')' : '')"
              @click="selectPeer(p)"
            >
              <template #prepend>
                <v-icon class="me-1" icon="mdi-server" size="16" />
              </template>
              <template #append>
                <v-icon
                  :color="
                    Date.now() / 1000 - (p as any).lastHandshake < 300
                      ? 'blue'
                      : 'yellow'
                  "
                  icon="mdi-lightbulb"
                  size="16"
                />
              </template>
            </v-list-item>
            <v-list-item v-if="hostPeers.length === 0" disabled title="No hosts" />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
      <v-expansion-panel v-if="store.selectedSubnet" value="peers">
        <v-expansion-panel-title class="text-subtitle-2">
          <v-icon class="me-1" icon="mdi-account-group" size="18" /> Peers ({{
            nonHostPeers.length
          }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-list density="compact">
            <v-list-item
              v-for="p in nonHostPeers"
              :key="p.id"
              :active="
                !!(
                  store.selection &&
                  store.selection.type === 'peer' &&
                  store.selection.id === p.id
                )
              "
              rounded="sm"
              :title="p.name + (p.ip ? ' (' + p.ip + ')' : '')"
              @click="selectPeer(p)"
            >
              <template #prepend>
                <v-icon
                  class="me-1"
                  icon="mdi-account-circle-outline"
                  size="16"
                />
              </template>
              <template #append>
                <v-icon
                  :color="
                    Date.now() / 1000 - (p as any).lastHandshake < 300
                      ? 'blue'
                      : 'yellow'
                  "
                  icon="mdi-lightbulb"
                  size="16"
                />
              </template>
            </v-list-item>
            <v-list-item
              v-if="nonHostPeers.length === 0"
              disabled
              title="No peers"
            />
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
    <div class="d-flex mt-3 ga-2 w-100">
      <v-btn
        class="flex-grow-1"
        color="primary"
        :disabled="applying"
        prepend-icon="mdi-download"
        variant="outlined"
        @click="exportTopology"
      >
        Export
      </v-btn>
      <v-btn
        class="flex-grow-1"
        color="primary"
        :disabled="applying"
        prepend-icon="mdi-upload"
        variant="outlined"
        @click="beginImport"
      >
        Import
      </v-btn>
      <input
        ref="importInput"
        accept="application/json"
        class="d-none"
        type="file"
        @change="handleImportFile"
      >
    </div>
    <div class="mt-3">
      <v-btn
        block
        :color="backend.topologyDirty ? 'info' : 'success'"
        :disabled="applying || !backend.topologyDirty"
        :loading="applying"
        prepend-icon="mdi-content-save"
        @click="applyToBackend"
      >
        {{
          backend.topologyDirty && !applying
            ? "Save Changes"
            : "All Changes Saved"
        }}
      </v-btn>
    </div>
    <v-alert
      v-if="applyMessage"
      class="mt-3"
      density="comfortable"
      dismissible
      :type="applySuccess ? 'success' : 'error'"
      @click:close="applyMessage = ''"
    >
      {{ applyMessage }}
    </v-alert>
    <div style="height: 80px; flex-shrink: 0" />
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useBackendInteractionStore } from '@/stores/backendInteraction'
  import { useNetworkStore } from '@/stores/network'
  import { emitRedraw } from '@/utils/bus'
  import {
    componentsToHex,
    componentsToRgbaNumber,
    parseHexColor,
    type RgbaComponents,
    rgbaNumberToComponents,
  } from '@/utils/color'

  const store = useNetworkStore()
  const backend = useBackendInteractionStore()
  const applying = ref(false)
  const applyMessage = ref('')
  const applySuccess = ref(false)
  const importInput = ref<HTMLInputElement | null>(null)

  // Categorised peer lists
  const hostPeers = computed(() => {
    const selSubnetId = store.selectedSubnet?.id || null
    if (!selSubnetId) return []
    return store.peers.filter(p => p.host && p.subnetId === selSubnetId)
  })
  const nonHostPeers = computed(() => {
    const selSubnetId = store.selectedSubnet?.id || null
    if (!selSubnetId) return []
    return store.peers.filter(p => !p.host && p.subnetId === selSubnetId)
  })

  // Subnet color handling
  const hexColor = ref('')
  // Vuetify v-color-picker in rgba mode emits object { r,g,b,a } (numbers 0-255 except a 0-1)
  const pickerRgba = ref<RgbaComponents | null>(null)

  function updateColorModels () {
    const s = store.selectedSubnet as any
    if (!s || typeof s.rgba !== 'number') {
      hexColor.value = ''
      pickerRgba.value = null
      return
    }

    const components = rgbaNumberToComponents(s.rgba)
    hexColor.value = componentsToHex(components)
    pickerRgba.value = components
  }
  function applyHexColor () {
    const s = store.selectedSubnet as any
    const components = parseHexColor(hexColor.value)
    if (!s || !components) return

    s.rgba = componentsToRgbaNumber(components)
    pickerRgba.value = components
    invalidateCanvas()
  }
  function applyPicker (val: RgbaComponents | null) {
    const s = store.selectedSubnet as any
    if (!s || !val) return

    const components = {
      r: val.r ?? 0,
      g: val.g ?? 0,
      b: val.b ?? 0,
      a: val.a ?? 1,
    }
    s.rgba = componentsToRgbaNumber(components)
    hexColor.value = componentsToHex(components)
    invalidateCanvas()
  }
  function invalidateCanvas () {
    emitRedraw()
  }
  watch(
    () => store.selectedSubnet?.id,
    () => updateColorModels(),
    { immediate: true },
  )
  watch(
    () => (store.selectedSubnet as any)?.rgba,
    () => updateColorModels(),
  )

  function selectPeer (p: any) {
    // Flag that this selection originated from the inspector (read by canvas logic)
    (window as any).__selectionFromInspector = true
    store.openPeerDetails(p.id)
    emitRedraw()
  }
  function selectSubnet (s: any) {
    // Flag that this selection originated from the inspector (read by canvas logic)
    (window as any).__selectionFromInspector = true
    store.selection = { type: 'subnet', id: s.id, name: s.name }
    emitRedraw()
  }

  async function applyToBackend () {
    applying.value = true
    applyMessage.value = ''
    try {
      const payload = backend.buildCurrentTopologyPayload()
      const ok = await backend.uploadTopology(payload)
      applySuccess.value = !!ok
      applyMessage.value = ok
        ? 'Topology uploaded successfully'
        : backend.lastError || 'Upload failed'
      if (ok) {
        // Refresh topology from backend to sync any generated keys / adjustments
        await backend.fetchTopology(true)
      }
    } catch (error: any) {
      applySuccess.value = false
      applyMessage.value = error?.message || 'Unexpected error while uploading'
    } finally {
      applying.value = false
    }
  }

  function exportTopology () {
    try {
      const payload = backend.buildCurrentTopologyPayload()
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `topology-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
      document.body.append(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      applyMessage.value = 'Topology exported'
      applySuccess.value = true
    } catch (error: any) {
      applyMessage.value = error?.message || 'Failed to export topology'
      applySuccess.value = false
    }
  }

  function beginImport () {
    importInput.value?.click()
  }

  function handleImportFile (ev: Event) {
    const input = ev.target as HTMLInputElement
    const file = input.files && input.files[0]
    if (!file) return
    const reader = new FileReader()
    applying.value = true
    applyMessage.value = ''
    reader.addEventListener('load', async () => {
      try {
        const text = String(reader.result || '')
        const parsed = JSON.parse(text)
        const ok = await backend.uploadTopology(parsed)
        applySuccess.value = !!ok
        applyMessage.value = ok
          ? `Imported ${file.name}`
          : backend.lastError || 'Import failed'
        if (ok) await backend.fetchTopology(true)
      } catch (error: any) {
        applySuccess.value = false
        applyMessage.value = error?.message || 'Failed to import file'
      } finally {
        applying.value = false
        // reset input so same file can be chosen again
        if (input) input.value = ''
      }
    })
    reader.onerror = () => {
      applySuccess.value = false
      applyMessage.value = 'Failed to read file'
      applying.value = false
    }
    reader.readAsText(file)
  }
</script>

<style scoped></style>
