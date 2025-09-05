<template>
  <v-dialog v-model="open" max-width="420">
    <v-card>
      <v-card-title class="text-subtitle-1">
        <v-icon icon="mdi-link-variant-off" class="me-2"></v-icon>
        Cut Link
      </v-card-title>
      <v-card-text>
        <template v-if="links.length">
          <div class="text-body-2 mb-2">
            Links between <strong>{{ peerName(links[0].fromId) }}</strong> and <strong>{{ peerName(links[0].toId) }}</strong>
          </div>
          <v-select
            v-model="selectedId"
            :items="selectItems"
            item-value="value"
            label="Link"
            density="comfortable"
            variant="outlined"
            :disabled="links.length===1"
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props" :title="item.raw.label" density="compact">
                <template #prepend>
                  <div class="d-flex align-center ga-1">
                    <v-icon :icon="item.raw.kind==='service' ? 'mdi-server' : 'mdi-account-multiple-outline'" :color="item.raw.kind==='service' ? 'primary' : 'success'" size="16" />
                    <v-icon v-if="item.raw.kind==='p2p' && problematicLinkIds.has(item.raw.id)" icon="mdi-alert-circle" color="warning" size="16" />
                  </div>
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <div class="d-flex align-center ga-1">
                <v-icon :icon="item.raw.kind==='service' ? 'mdi-server' : 'mdi-account-multiple-outline'" :color="item.raw.kind==='service' ? 'primary' : 'success'" size="16" />
                <v-icon v-if="item.raw.kind==='p2p' && problematicLinkIds.has(item.raw.id)" icon="mdi-alert-circle" color="warning" size="16" />
                <span>{{ item.raw.label }}</span>
              </div>
            </template>
          </v-select>
          <v-alert v-if="links.length>1" type="info" density="compact" class="mt-2" text="Multiple overlapping links." />
        </template>
        <template v-else>
          <v-alert type="info" density="comfortable" text="No links found." />
        </template>
      </v-card-text>
      <v-card-actions class="justify-end ga-2">
        <v-btn variant="text" @click="cancel">Cancel</v-btn>
        <v-btn color="error" :disabled="!selectedId" @click="openConfirmDialog">Delete</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <ConfirmCutLinkDialog
    v-model="confirmOpen"
    :link="currentLink"
    :mode="currentLink ? (currentLink.kind==='p2p' ? 'p2p' : 'service-generic') : ''"
    :peer-a="currentLink ? peerName(currentLink.fromId) : ''"
    :peer-b="currentLink ? peerName(currentLink.toId) : ''"
    :service-name="currentLink?.serviceName"
    :problematic="currentLink?.kind==='p2p' && problematicLinkIds.has(currentLink.id)"
    :loading="confirmLoading"
    @confirm="performDelete"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import ConfirmCutLinkDialog from './ConfirmCutLinkDialog.vue';
import { useNetworkStore } from '@/stores/network';
import { useBackendInteractionStore } from '@/stores/backendInteraction';
import type { Link } from '@/types/network';

const store = useNetworkStore();
const backend = useBackendInteractionStore();
const open = ref(false);
const links = ref<Link[]>([]);
const selectedId = ref<string>('');
// Secondary confirmation dialog state
const confirmOpen = ref(false);
const confirmLoading = ref(false);

const currentLink = computed(()=> links.value.find(l=> l.id===selectedId.value) || null);
let pairKey = '';

function peerName(id:string){ return store.peers.find(p=>p.id===id)?.name || id; }

// Determine problematic p2p links (pair has at least one service link and a host peer)
const problematicLinkIds = computed(()=> {
  const set = new Set<string>();
  if (!links.value.length) return set;
  const serviceLinks = links.value.filter(l=> l.kind==='service');
  if (!serviceLinks.length) return set; // no service link => nothing problematic
  // Identify host peer id from a service link (fromId per topology builder)
  const hostIds = new Set(serviceLinks.map(l=> l.fromId));
  // A p2p link is problematic if one side is a host present in hostIds
  for (const l of links.value){
    if (l.kind==='p2p' && (hostIds.has(l.fromId) || hostIds.has(l.toId))){ set.add(l.id); }
  }
  return set;
});

const selectItems = computed(()=> links.value.map(l=> {
  const from = peerName(l.fromId);
  const to = peerName(l.toId);
  if (l.kind === 'p2p') {
    return { value: l.id, kind: l.kind, label: `${from} ↔ ${to}`, id: l.id };
  }
  if (l.kind === 'service') {
    const fromPeer = store.peers.find(p=> p.id===l.fromId);
    const svcRec = fromPeer?.services?.[l.serviceName || ''];
    const port = svcRec?.port;
    const svcName = l.serviceName || svcRec?.name || 'service';
    const portStr = port!==undefined ? `:${port}` : '';
    return { value: l.id, kind: l.kind, label: `${from} -> ${to}${portStr} (${svcName})`, id: l.id };
  }
  return { value: l.id, kind: l.kind, label: `${from} -> ${to}`, id: l.id };
}));

function show(payload:{ pairKey:string; links:Link[] }){
  pairKey = payload.pairKey;
  links.value = payload.links;
  selectedId.value = payload.links[0]?.id || '';
  open.value = true;
}

function cancel(){ open.value=false; store.tool='select'; }
function openConfirmDialog(){ if (!selectedId.value) return; confirmOpen.value=true; }
function closeConfirm(){ if (confirmLoading.value) return; confirmOpen.value=false; }
async function performDelete(){
  if (!currentLink.value){ confirmOpen.value=false; return; }
  confirmLoading.value=true;
  try {
    const link = currentLink.value;
    if (link.kind === 'p2p') {
      const a = store.peers.find(p=> p.id===link.fromId);
      const b = store.peers.find(p=> p.id===link.toId);
      if (a && b) await backend.disconnectPeers(a.name, b.name);
    } else if (link.kind === 'service') {
      const consumer = store.peers.find(p=> p.id===link.toId);
      const svcName = link.serviceName || '';
      if (consumer && svcName) await backend.disconnectPeerFromService(consumer.name, svcName);
    }
  } catch(e){ /* error handled in backend store */ }
  finally {
    confirmLoading.value=false; confirmOpen.value=false; open.value=false; store.tool='select';
  }
}

function handleRequestCut(e:any){ const detail=e.detail||{}; show(detail); }

onMounted(()=> { window.addEventListener('request-cut-link', handleRequestCut); });
onBeforeUnmount(()=> { window.removeEventListener('request-cut-link', handleRequestCut); });

defineExpose({ show });
</script>

<style scoped>
</style>
