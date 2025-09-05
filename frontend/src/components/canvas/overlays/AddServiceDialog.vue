<template>
  <v-dialog v-model="open" max-width="560">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>Add Service to {{ peerLabel }}</span>
        <v-btn icon="mdi-close" variant="text" @click="close" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <v-alert v-if="error" type="error" class="mb-3" density="comfortable" :text="error" />
        <v-form @submit.prevent="submit" ref="formRef">
          <v-text-field v-model="serviceName" label="Service Name" :disabled="loading" required density="comfortable" autofocus />
          <v-text-field v-model="department" label="Department" :disabled="loading" density="comfortable" />
          <v-text-field v-model.number="port" label="Port" :disabled="loading" type="number" min="1" max="65535" required density="comfortable" />
          <div class="text-caption text-medium-emphasis mb-3">
            Name must be unique across the network. Port must be free on this peer.
          </div>
          <v-btn :loading="loading" color="primary" type="submit" block prepend-icon="mdi-cloud-plus">Add Service</v-btn>
        </v-form>
        <v-expand-transition>
          <div v-if="conflicts.length" class="mt-3">
            <div class="text-caption font-italic mb-1">Conflicts:</div>
            <v-chip v-for="c in conflicts" :key="c" color="error" size="small" class="ma-1" variant="tonal">{{ c }}</v-chip>
          </div>
        </v-expand-transition>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useNetworkStore } from '@/stores/network'
import { useBackendInteractionStore } from '@/stores/backendInteraction'

const open = ref(false)
const loading = ref(false)
const error = ref('')
const serviceName = ref('')
const department = ref('')
const port = ref<number | null>(null)
const targetPeerId = ref<string | null>(null)
const conflicts = ref<string[]>([])
const formRef = ref()

const net = useNetworkStore()
const backend = useBackendInteractionStore()

const peer = computed(()=> net.peers.find(p=> p.id === targetPeerId.value))
const peerLabel = computed(()=> peer.value ? peer.value.name : 'Peer')

function show(peerId:string){
  targetPeerId.value = peerId
  serviceName.value=''
  department.value=''
  port.value=null
  error.value=''
  conflicts.value=[]
  open.value=true
}
function close(){ open.value=false }

function validateLocal(): boolean {
  conflicts.value=[]
  if (!serviceName.value.trim()) { error.value='Service name required'; return false }
  if (port.value == null || isNaN(port.value) || port.value<1 || port.value>65535){ error.value='Valid port required'; return false }
  // Global name uniqueness
  const nameExists = net.peers.some(p=> Object.keys(p.services||{}).some(n=> n === serviceName.value.trim()))
  if (nameExists) conflicts.value.push('Service name already exists')
  // Port uniqueness on this peer
  if (peer.value){
    const portClash = Object.values(peer.value.services||{}).some((s:any)=> Number(s.port) === Number(port.value))
    if (portClash) conflicts.value.push('Port already in use on this peer')
  }
  if (conflicts.value.length){ error.value='Resolve conflicts before submitting'; return false }
  error.value=''
  return true
}

async function submit(){
  if (!peer.value){ error.value='Peer not found'; return }
  if (!validateLocal()) return
  loading.value=true
  try {
    const ok = await backend.createService(peer.value.name, serviceName.value.trim(), department.value.trim(), Number(port.value))
    if (!ok){ error.value = backend.lastError || 'Failed to create service'; return }
    open.value=false
  } catch(e:any){
    error.value = e?.message || 'Unexpected error'
  } finally { loading.value=false }
}

defineExpose({ show, close })
</script>
