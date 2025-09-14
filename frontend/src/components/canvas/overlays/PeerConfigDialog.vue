<template>
  <v-dialog v-model="open" max-width="640">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span class="text-subtitle-1 font-weight-medium"><v-icon icon="mdi-file-document" /> Peer Configuration</span>
        <v-btn icon="mdi-close" variant="text" size="small" @click="close" />
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-alert v-if="error" type="error" class="mb-3" density="comfortable">{{ error }}</v-alert>
        <div v-if="config" class="mb-3">
          <v-textarea v-model="config" readonly auto-grow rows="12" variant="outlined" density="compact" label="WireGuard Configuration" />
        </div>
        <div v-else class="d-flex align-center ga-2 text-medium-emphasis">
          <v-progress-circular indeterminate size="20" class="mr-2" /> Loading configuration...
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Close</v-btn>
        <v-btn :disabled="!config" color="primary" prepend-icon="mdi-download" @click="download">Download</v-btn>
        <v-btn :disabled="!config" color="secondary" variant="outlined" prepend-icon="mdi-content-copy" @click="copyConfig">Copy</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useBackendInteractionStore } from '@/stores/backendInteraction'

const backend = useBackendInteractionStore()
const open = ref(false)
const username = ref('')
const config = ref<string|null>(null)
const error = ref<string|null>(null)

function showImmediate(usernameParam: string, configText: string){
  username.value = usernameParam
  config.value = configText
  error.value = null
  open.value = true
}

async function showFetch(usernameParam: string){
  username.value = usernameParam
  config.value = null
  error.value = null
  open.value = true
  const cfg = await backend.fetchPeerConfig(usernameParam)
  if (cfg) config.value = cfg; else error.value = backend.lastError || 'Failed to load configuration'
}

function download(){
  if (!config.value) return
  const blob = new Blob([config.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${username.value || 'peer'}.conf`
  document.body.appendChild(a)
  a.click()
  setTimeout(()=> { document.body.removeChild(a); URL.revokeObjectURL(url) }, 0)
}
async function copyConfig(){
  if (config.value) await navigator.clipboard.writeText(config.value)
}
function close(){ open.value=false }

defineExpose({ showImmediate, showFetch })
</script>
<style scoped>
</style>
