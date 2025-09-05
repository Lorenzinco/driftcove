<template>
  <v-dialog v-model="open" max-width="460">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span class="text-subtitle-1 font-weight-medium">Create Link</span>
        <v-btn icon="mdi-close" variant="text" size="small" @click="cancel" />
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <div class="mb-2"><strong>From:</strong> {{ fromPeer?.name }}</div>
        <div class="mb-4"><strong>To:</strong> {{ toPeer?.name }}</div>
        <v-alert v-if="error" type="error" density="comfortable" class="mb-3">{{ error }}</v-alert>
        <v-radio-group v-model="mode" class="mt-2">
          <v-radio value="p2p">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-account" class="me-1 text-green" />
                <v-icon size="18" icon="mdi-arrow-left-right" class="mx-1 text-green" />
                <v-icon size="18" icon="mdi-account" class="ms-1 text-green" />
                <span class="ms-2">Peer to Peer</span>
              </div>
            </template>
          </v-radio>
            <v-radio :disabled="!toIsHost" value="service">
            <template #label>
              <div class="d-flex align-center">
              <v-icon size="18" icon="mdi-account" class="me-1" :class="toIsHost ? 'text-primary' : 'text-disabled'" />
              <v-icon size="18" icon="mdi-arrow-left-right" class="mx-1" :class="toIsHost ? 'text-primary' : 'text-disabled'" />
              <v-icon size="18" icon="mdi-server" class="ms-1" :class="toIsHost ? 'text-primary' : 'text-disabled'" />
              <span class="ms-2">{{ toIsHost ? 'Peer to Service' : 'Peer to Service (destination has no services)' }}</span>
              </div>
            </template>
            </v-radio>
        </v-radio-group>
        <v-expand-transition>
          <div v-if="mode==='service'" class="mt-2">
            <v-select v-model="selectedService" :items="serviceItems" item-title="label" item-value="value" label="Service" density="comfortable" variant="outlined" />
          </div>
        </v-expand-transition>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="cancel">Cancel</v-btn>
        <v-btn color="primary" :disabled="!canSubmit" @click="submit" prepend-icon="mdi-link-variant">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useNetworkStore } from '@/stores/network'
import { useBackendInteractionStore } from '@/stores/backendInteraction'

const store = useNetworkStore()
const open = ref(false)
const fromId = ref('')
const toId = ref('')
const mode = ref<'p2p'|'service'>('p2p')
const selectedService = ref<string| null>(null)
const error = ref<string|null>(null)

const fromPeer = computed(()=> store.peers.find(p=> p.id===fromId.value))
const toPeer = computed(()=> store.peers.find(p=> p.id===toId.value))
const toIsHost = computed(()=> !!toPeer.value?.host && Object.keys(toPeer.value?.services||{}).length>0)
const serviceItems = computed(()=> Object.entries(toPeer.value?.services||{}).map(([name, svc]:any)=> ({ label: `${name}${svc.port? ' (:'+svc.port+')':''}`, value: name })))

const backend = useBackendInteractionStore()
const submitting = ref(false)
const canSubmit = computed(()=> !submitting.value && !!fromPeer.value && !!toPeer.value && (mode.value==='p2p' || (mode.value==='service' && selectedService.value)))

function show(from:string, to:string){
  fromId.value=from; toId.value=to; mode.value='p2p'; selectedService.value=null; error.value=null; open.value=true
}
function cancel(){ open.value=false; store.tool='select' }
async function submit(){
  if (!canSubmit.value) return
  const existing = store.links.find(l=> l.fromId===fromId.value && l.toId===toId.value && l.kind===(mode.value==='p2p'?'p2p':'service') && (mode.value==='p2p' || (l as any).serviceName===selectedService.value))
  if (existing){ error.value='Link already exists'; return }
  error.value=null; submitting.value=true
  try {
    if (mode.value==='p2p') {
      // Derive usernames from peer objects for backend
      const aUser = fromPeer.value?.name; const bUser = toPeer.value?.name
      if (!aUser || !bUser) { error.value='Missing peer usernames'; return }
      const ok = await backend.connectPeers(aUser, bUser)
      if (!ok){ error.value = backend.lastError || 'Backend connect failed'; return }
      // The topology refresh will add the p2p link; no manual push needed
    } else {
      const aUser = fromPeer.value?.name
      const svcName = selectedService.value
      if (!aUser || !svcName){ error.value='Missing peer or service'; return }
      const ok = await backend.connectPeerToService(aUser, svcName)
      if (!ok){ error.value = backend.lastError || 'Backend service connect failed'; return }
      // Topology refresh will cause service link(s) to appear via new service grouping.
    }
  open.value=false; store.tool='select'
  } finally { submitting.value=false }
}

defineExpose({ show })
</script>
