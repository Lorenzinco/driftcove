<template>
  <v-dialog v-model="open" max-width="460">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span class="text-subtitle-1 font-weight-medium">Create Link</span>
        <v-btn icon="mdi-close" variant="text" size="small" @click="cancel" />
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
  <div class="mb-2"><strong>From:</strong> {{ fromLabel }}</div>
  <div class="mb-4"><strong>To:</strong> {{ toLabel }}</div>
  <v-alert v-if="error" type="error" density="comfortable" class="mb-3">{{ error }}</v-alert>
  <!-- Peer ↔ Peer: choose between p2p or service link -->
  <v-radio-group v-if="fromType==='peer' && toType==='peer'" v-model="mode" class="mt-2">
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
          <v-radio value="admin-p2p">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-shield-account" class="me-1 text-deep-purple-accent-2" />
                <v-icon size="18" icon="mdi-arrow-right" class="mx-1 text-deep-purple-accent-2" />
                <v-icon size="18" icon="mdi-account" class="ms-1 text-deep-purple-accent-2" />
                <span class="ms-2">Admin peer → Peer</span>
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

        <!-- Peer → Subnet: choose between membership (peer-subnet) or admin privilege (admin-peer-subnet) -->
        <v-radio-group v-if="fromType==='peer' && toType==='subnet'" v-model="mode" class="mt-2">
          <v-radio value="peer-subnet">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-account" class="me-1 text-green" />
                <v-icon size="18" icon="mdi-arrow-right" class="mx-1 text-green" />
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="ms-1 text-green" />
                <span class="ms-2">Subnet guest (membership)</span>
              </div>
            </template>
          </v-radio>
          <v-radio value="admin-peer-subnet">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-shield-account" class="me-1 text-deep-purple-accent-2" />
                <v-icon size="18" icon="mdi-arrow-right" class="mx-1 text-deep-purple-accent-2" />
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="ms-1 text-deep-purple-accent-2" />
                <span class="ms-2">Admin peer → Subnet</span>
              </div>
            </template>
          </v-radio>
        </v-radio-group>
        <!-- Subnet → Peer: choose between membership (peer-subnet) or subnet-service -->
        <v-radio-group v-if="fromType==='subnet' && toType==='peer'" v-model="mode" class="mt-2">
          <v-radio value="peer-subnet">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="me-1 text-green" />
                <v-icon size="18" icon="mdi-arrow-left-right" class="mx-1 text-green" />
                <v-icon size="18" icon="mdi-account" class="ms-1 text-green" />
                <span class="ms-2">Subnet membership (make peer a guest)</span>
              </div>
            </template>
          </v-radio>
          <v-radio :disabled="!toIsHost" value="subnet-service">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="me-1" :class="toIsHost ? 'text-primary' : 'text-disabled'" />
                <v-icon size="18" icon="mdi-arrow-left-right" class="mx-1" :class="toIsHost ? 'text-primary' : 'text-disabled'" />
                <v-icon size="18" icon="mdi-server" class="ms-1" :class="toIsHost ? 'text-primary' : 'text-disabled'" />
                <span class="ms-2">{{ toIsHost ? 'Subnet to Service' : 'Subnet to Service (destination has no services)' }}</span>
              </div>
            </template>
          </v-radio>
        </v-radio-group>
        <v-expand-transition>
          <div v-if="mode==='service' || mode==='subnet-service'" class="mt-2">
            <v-select
              v-model="selectedService"
              :items="toServiceItems"
              item-title="label"
              item-value="value"
              label="Service"
              density="comfortable"
              variant="outlined"
            />
          </div>
        </v-expand-transition>
        <div v-if="mode==='peer-subnet'" class="mt-2">
          <v-alert type="info" density="comfortable" text="Create a membership link from Peer to Subnet." />
        </div>
        <!-- Subnet -> Subnet: choose regular bidirectional public-based link or directed admin privilege link -->
        <v-radio-group v-if="fromType==='subnet' && toType==='subnet'" v-model="mode" class="mt-2">
          <v-radio value="subnet-subnet">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="me-1 text-green" />
                <v-icon size="18" icon="mdi-arrow-left-right" class="mx-1 text-green" />
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="ms-1 text-green" />
                <span class="ms-2">Subnet ↔ Subnet (public peers)</span>
              </div>
            </template>
          </v-radio>
          <v-radio value="admin-subnet-subnet">
            <template #label>
              <div class="d-flex align-center">
                <v-icon size="18" icon="mdi-shield" class="me-1 text-deep-purple-accent-2" />
                <v-icon size="18" icon="mdi-arrow-right" class="mx-1 text-deep-purple-accent-2" />
                <v-icon size="18" icon="mdi-hexagon-multiple-outline" class="ms-1 text-deep-purple-accent-2" />
                <span class="ms-2">Admin Subnet → Subnet</span>
              </div>
            </template>
          </v-radio>
        </v-radio-group>
        <div v-if="mode==='subnet-subnet'" class="mt-2">
          <v-alert type="info" density="comfortable" text="Subnet to Subnet linking means every peer from one subnet can communicate with every peer from another subnet." />
        </div>
        <div v-if="mode==='admin-subnet-subnet'" class="mt-2">
          <v-alert type="info" density="comfortable" text="Admin Subnet → Subnet grants initiation from every member of the admin subnet to all members of the target subnet regardless of their public flags." />
        </div>
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
import { ref, computed, watch } from 'vue'
import { useNetworkStore } from '@/stores/network'
import { useBackendInteractionStore } from '@/stores/backendInteraction'

const store = useNetworkStore()
const open = ref(false)
const fromId = ref('')
const toId = ref('')
const fromType = ref<'peer'|'subnet'>('peer')
const toType = ref<'peer'|'subnet'>('peer')
const mode = ref<'p2p'|'service'|'peer-subnet'|'subnet-subnet'|'subnet-service'|'admin-p2p'|'admin-subnet-subnet'|'admin-peer-subnet'>('p2p')
const selectedService = ref<string| null>(null)
const error = ref<string|null>(null)

const fromPeer = computed(()=> fromType.value==='peer' ? store.peers.find(p=> p.id===fromId.value) : null)
const toPeer = computed(()=> toType.value==='peer' ? store.peers.find(p=> p.id===toId.value) : null)
const fromSubnet = computed(()=> fromType.value==='subnet' ? store.subnets.find(s=> s.id===fromId.value) : null)
const toSubnet = computed(()=> toType.value==='subnet' ? store.subnets.find(s=> s.id===toId.value) : null)
const fromLabel = computed(()=> fromType.value==='peer' ? (fromPeer.value?.name || '') : (fromSubnet.value?.name || fromSubnet.value?.cidr || 'Subnet'))
const toLabel = computed(()=> toType.value==='peer' ? (toPeer.value?.name || '') : (toSubnet.value?.name || toSubnet.value?.cidr || 'Subnet'))
const toIsHost = computed(()=> toType.value==='peer' && !!toPeer.value?.host && Object.keys(toPeer.value?.services||{}).length>0)
const toServiceItems = computed(()=> {
  // If destination is a host peer, list its services. If destination is a subnet, we need a service list elsewhere; for now support host peer path
  return Object.entries(toPeer.value?.services||{}).map(([name, svc]:any)=> ({ label: `${name}${svc.port? ' (:'+svc.port+')':''}`, value: name }))
})
const serviceItems = computed(()=> Object.entries(toPeer.value?.services||{}).map(([name, svc]:any)=> ({ label: `${name}${svc.port? ' (:'+svc.port+')':''}`, value: name })))

const backend = useBackendInteractionStore()
const submitting = ref(false)
const canSubmit = computed(()=> {
  if (submitting.value) return false
  switch (mode.value) {
    case 'peer-subnet':
    case 'admin-peer-subnet':
      return !!fromPeer.value && !!toSubnet.value
    case 'subnet-subnet':
    case 'admin-subnet-subnet':
      return !!fromSubnet.value && !!toSubnet.value
    case 'subnet-service':
      return !!fromSubnet.value && !!toPeer.value && toIsHost.value && !!selectedService.value
    case 'service':
      return !!fromPeer.value && !!toPeer.value && !!selectedService.value
    case 'p2p':
    case 'admin-p2p':
      return !!fromPeer.value && !!toPeer.value
    default:
      return false
  }
})

function show(from:string, to:string, options?: { fromType?: 'peer'|'subnet'; toType?: 'peer'|'subnet' }){
  fromId.value=from; toId.value=to; error.value=null; selectedService.value=null;
  fromType.value = options?.fromType || 'peer';
  toType.value = options?.toType || 'peer';
  // Determine mode
  if (fromType.value==='peer' && toType.value==='peer') mode.value='p2p';
  else if (fromType.value==='peer' && toType.value==='peer' /* service override left via UI */) mode.value='p2p';
  else if (fromType.value==='peer' && toType.value==='subnet') mode.value='peer-subnet';
  else if (fromType.value==='subnet' && toType.value==='peer') {
    // Treat as peer-subnet by swapping roles for UX: we only allow creating membership from a peer to a subnet
    mode.value='peer-subnet';
  }
  else if (fromType.value==='subnet' && toType.value==='subnet') mode.value='subnet-subnet';
  // For subnet -> peer, user can choose subnet-service via radio if destination hosts services
  open.value=true
}
function cancel(){ open.value=false; store.tool='select' }
async function submit(){
  if (!canSubmit.value) return
  // Existing check only for p2p/service kinds; membership/service links handled differently
  if (mode.value==='p2p' || mode.value==='service' || mode.value==='admin-p2p'){
    const existing = store.links.find(l=> l.fromId===fromId.value && l.toId===toId.value && l.kind===((mode.value==='p2p')?'p2p': (mode.value==='admin-p2p'?'admin-p2p':'service')) && (mode.value==='p2p' || mode.value==='admin-p2p' || (l as any).serviceName===selectedService.value))
    if (existing){ error.value='Link already exists'; return }
  }
  error.value=null; submitting.value=true
  try {
    if (mode.value==='p2p') {
      // Derive usernames from peer objects for backend
      const aUser = fromPeer.value?.name; const bUser = toPeer.value?.name
      if (!aUser || !bUser) { error.value='Missing peer usernames'; return }
      const ok = await backend.connectPeers(aUser, bUser)
      if (!ok){ error.value = backend.lastError || 'Backend connect failed'; return }
      // The topology refresh will add the p2p link; no manual push needed
    } else if (mode.value==='admin-p2p') {
      const adminUser = fromPeer.value?.name; const peerUser = toPeer.value?.name
      if (!adminUser || !peerUser){ error.value='Missing peer usernames'; return }
      const ok = await backend.connectAdminPeerToPeer(adminUser, peerUser)
      if (!ok){ error.value = backend.lastError || 'Backend admin link failed'; return }
    } else if (mode.value==='service') {
      const aUser = fromPeer.value?.name
      const svcName = selectedService.value
      if (!aUser || !svcName){ error.value='Missing peer or service'; return }
      const ok = await backend.connectPeerToService(aUser, svcName)
      if (!ok){ error.value = backend.lastError || 'Backend service connect failed'; return }
      // Topology refresh will cause service link(s) to appear via new service grouping.
    } else if (mode.value==='peer-subnet'){
      const aUser = fromPeer.value?.name; const subnetCidr = toSubnet.value?.cidr
      if (!aUser || !subnetCidr){ error.value='Missing peer or subnet'; return }
      const ok = await backend.connectPeerToSubnet(aUser, subnetCidr)
      if (!ok){ error.value = backend.lastError || 'Backend peer-subnet connect failed'; return }
    } else if (mode.value==='admin-peer-subnet') {
      const adminUser = fromPeer.value?.name; const subnetCidr = toSubnet.value?.cidr
      if (!adminUser || !subnetCidr){ error.value='Missing peer or subnet'; return }
      const ok = await backend.connectAdminPeerToSubnet(adminUser, subnetCidr)
      if (!ok){ error.value = backend.lastError || 'Backend admin peer-subnet connect failed'; return }
    } else if (mode.value==='subnet-subnet'){
      const aCidr = fromSubnet.value?.cidr; const bCidr = toSubnet.value?.cidr
      if (!aCidr || !bCidr){ error.value='Missing subnets'; return }
      const ok = await backend.connectSubnetToSubnet(aCidr, bCidr)
      if (!ok){ error.value = backend.lastError || 'Backend subnet-subnet connect failed'; return }
    } else if (mode.value==='admin-subnet-subnet') {
      const adminCidr = fromSubnet.value?.cidr; const targetCidr = toSubnet.value?.cidr
      if (!adminCidr || !targetCidr){ error.value='Missing subnets'; return }
      const ok = await backend.connectAdminSubnetToSubnet(adminCidr, targetCidr)
      if (!ok){ error.value = backend.lastError || 'Backend admin subnet link failed'; return }
    } else if (mode.value==='subnet-service'){
      // From subnet to destination host peer's chosen service
      const subnetCidr = fromSubnet.value?.cidr
      const svcName = selectedService.value
      if (!subnetCidr || !svcName){ error.value='Missing subnet or service'; return }
      const ok = await backend.connectSubnetToService(subnetCidr, svcName)
      if (!ok){ error.value = backend.lastError || 'Backend subnet-service connect failed'; return }
    }
  open.value=false; store.tool='select'
  } finally { submitting.value=false }
}

// When dialog closes by clicking outside or pressing ESC, also revert to select tool
watch(open, (now, prev)=>{
  if (prev && !now) {
    store.tool = 'select'
  }
})

defineExpose({ show })
</script>
