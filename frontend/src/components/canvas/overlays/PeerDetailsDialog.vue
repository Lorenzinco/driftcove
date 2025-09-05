<template>
  <div>
  <v-dialog v-model="open" max-width="520">
    <v-card v-if="peer">
      <v-card-title class="d-flex justify-space-between align-center">
        <span>{{ peer.name }}</span>
        <v-btn icon="mdi-close" variant="text" @click="close()" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <div class="d-flex flex-column ga-2">
          <div><strong>IP:</strong> {{ peer.ip }}</div>
          <div><strong>Subnet:</strong> {{ peer.subnetId || 'None' }}</div>
          <div v-if="peer.presharedKey"><strong>PSK:</strong> <code class="code-inline">{{ peer.presharedKey }}</code></div>
          <div v-if="peer.publicKey"><strong>Pub:</strong> <code class="code-inline">{{ peer.publicKey }}</code></div>
          <div class="d-flex align-center ga-2">
            <strong>Connected:</strong>
            <v-icon :color="peer.allowed ? 'success' : 'error'" size="18" :title="peer.allowed? 'Connected' : 'Not Connected'">{{ peer.allowed ? 'mdi-wifi' : 'mdi-wifi-off' }}</v-icon>
            <v-icon color="primary" size="18" icon="mdi-information" @click="showInfo = true"></v-icon>
            <v-dialog v-model="showInfo" max-width="480">
              <v-card>
                <v-card-title class="d-flex justify-space-between align-center">
                  <span><v-icon :color="peer.allowed ? 'success' : 'error'" :icon="peer.allowed ? 'mdi-wifi' : 'mdi-wifi-off'" />Connection details</span>
                  <v-btn icon="mdi-close" variant="text" @click="showInfo = false" />
                </v-card-title>
                <v-divider />
                <v-card-text class="text-body-2">
                    {{ peer.allowed ? 'This peer is allowed to talk inside its subnetwork, if you wish it to be restricted click the disconnect icon right besides the connection status.' : 'This peer is not allowed to communicate in its own subnetwork, if you wish it to be allowed click the connect icon right besides the connection status.' }}
                </v-card-text>
                <v-divider />
              </v-card>
            </v-dialog>
          </div>

          <v-divider />

          <div v-if="problematicLinks.length" class="mb-2">
            <v-alert type="warning" density="comfortable" class="mb-0">
              <strong>Warning:</strong> This peer has {{ problematicLinks.length }} problematic link(s), those are p2p links to or from hosts to which there are also service links. A service link is a link that only allows for traffic on that service's specific port, if there's also  a peer to peer link to that host this invalidates the filter. Please review the links below.
            </v-alert>
          </div>

          <v-expansion-panels focusable inset>
            <v-expansion-panel v-if="p2pLinks.length">
              <v-expansion-panel-title>
                <div class="d-flex align-center">
                        <v-icon size="18" icon="mdi-account" class="text-green" />
                        <v-icon size="18" icon="mdi-arrow-left-right" class="mx-1 text-green" />
                        <v-icon size="18" icon="mdi-account" class="text-green" />
                </div>
                p2p Links ({{ p2pLinks.length }})
              </v-expansion-panel-title>
              <v-expansion-panel-text class="pt-0">
                <div v-if="!p2pLinks.length" class="text-medium-emphasis">No links</div>
                <v-list v-else density="compact" nav class="py-0">
                  <v-list-item v-for="link in p2pLinks" :key="link.id">
                    <v-list-item-title>
                      {{ peer?.name }}
                      <v-icon size="16" icon="mdi-arrow-left-right" class="mx-1 text-green" />
                      {{ store.peers.find(p=> p.id=== (link.toId===peer?.id ? link.fromId : link.toId))?.name}}
                    </v-list-item-title>
                    <v-list-item-subtitle>
                      
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel v-if="peer.host">
              <v-expansion-panel-title>
                <div class="d-flex align-center">
                  <v-icon size="18" icon="mdi-server" class="text-primary" />
                  <v-icon size="18" icon="mdi-arrow-left" class="mx-1 text-primary" />
                    <v-icon size="18" icon="mdi-account-multiple" class="text-primary" />
                </div>
                Incoming Service Links ({{ incomingServiceLinks.length }})
              </v-expansion-panel-title>
              <v-expansion-panel-text class="pt-0">
                <div v-if="!incomingServiceLinks.length" class="text-medium-emphasis">No links</div>
                <v-list v-else density="compact" nav class="py-0">
                  <v-list-item v-for="link in incomingServiceLinks" :key="link.id">
                    <v-list-item-title>
                      {{ store.peers.find(p=> p.id=== link.toId)?.name }}
                      <v-icon size="16" icon="mdi-arrow-right" class="mx-1 text-primary" />
                      <v-icon size="16" icon="mdi-server" class="mx-1 text-primary" />
                      {{ link.serviceName }}
                    </v-list-item-title>
                    <v-list-item-subtitle v-if="link.serviceName">
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel v-if="outgoingServiceLinks.length">
              <v-expansion-panel-title>
                <div class="d-flex align-center">
                  <v-icon size="18" icon="mdi-account" class="text-primary" />
                  <v-icon size="18" icon="mdi-arrow-right" class="mx-1 text-primary" />
                  <v-icon size="18" icon="mdi-server" class="text-primary" />
                </div>
                Outgoing Service Links ({{ outgoingServiceLinks.length }})
              </v-expansion-panel-title>
              <v-expansion-panel-text class="pt-0">
                <div v-if="!outgoingServiceLinks.length" class="text-medium-emphasis">No links</div>
                <v-list v-else density="compact" nav class="py-0">
                  <v-list-item v-for="link in outgoingServiceLinks" :key="link.id">
                    <v-list-item-title>
                      This peer
                      <v-icon size="16" icon="mdi-arrow-right" class="mx-1 text-primary" />
                      <v-icon size="16" icon="mdi-server" class="mx-1 text-primary" />
                      {{ store.peers.find(p=> p.id=== link.fromId)?.name }}
                      {{ link.serviceName }}
                    </v-list-item-title>
                    <v-list-item-subtitle v-if="link.serviceName">
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel>
              <v-expansion-panel-title>
                <div class="d-flex align-center">
                  <v-icon size="18" icon="mdi-server" class="text-secondary" />
                </div>
                Hosted Services ({{ Object.keys(peer.services||{}).length }})
              </v-expansion-panel-title>
              <v-expansion-panel-text class="pt-0">
                <div v-if="!Object.keys(peer.services||{}).length" class="text-medium-emphasis">No services</div>
                <v-list v-else density="compact" nav class="py-0">
                  <v-list-item v-for="(svc, key) in peer.services" :key="key">
                    <v-list-item-title>
                      <v-icon size="18" icon="mdi-server" class="text-primary" />{{ svc.name || key }}
                    </v-list-item-title>
                    <v-list-item-subtitle v-if="svc.port">
                      Port: {{ svc.port }} <span v-if="svc.department">| Dept: {{ svc.department }}</span> <span v-if="svc.description">| {{ svc.description }}</span>
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
                <div class="d-flex justify-end mt-2">
                  <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="openAddService(peer.id)">Add Service</v-btn>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>
      </v-card-text>
      <v-divider/>
      <v-card-actions>
        <v-spacer />
  <v-btn variant="text" prepend-icon="mdi-download" :loading="dlLoading" @click="downloadConfig">Download Config</v-btn>
  <v-btn color="primary" variant="elevated" @click="close()">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <AddServiceDialog ref="addServiceDialogRef" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import AddServiceDialog from './AddServiceDialog.vue';
import { useNetworkStore } from '@/stores/network';
import { useBackendInteractionStore } from '@/stores/backendInteraction';

const showInfo = ref(false);
const dlLoading = ref(false);
const store = useNetworkStore();
const backend = useBackendInteractionStore();
const open = computed({
  get: ()=> !!store.peerDetailsRequestId,
  set: (v)=> { if(!v){ store.peerDetailsRequestId=null; store.closePeerDetails(); } }
});
const peer = computed(()=> store.peers.find(p=> p.id===store.peerDetailsRequestId));
const p2pLinks = computed(() => {
  const p = peer.value;
  if (!p) return [];
  return store.links.filter(l => (l.toId === p.id || l.fromId === p.id)&& l.kind === 'p2p');
});
const incomingServiceLinks = computed(() => {
  const p = peer.value;
  if (!p) return [];
  return store.links.filter(l => l.fromId === p.id && l.kind === 'service');
});
const outgoingServiceLinks = computed(() => {
  const p = peer.value;
  if (!p) return [];
  return store.links.filter(l => l.toId === p.id && l.kind === 'service');
});
const problematicLinks = computed(() => {
  const p = peer.value;
  if (!p) return [];

  // Pre-compute all host->client service link pairs
  const servicePairs = new Set<string>();
  for (const l of store.links) {
    if (l.kind === 'service') {
      const hostPeer = store.peers.find(pp => pp.id === l.fromId);
      if (hostPeer?.host) {
        servicePairs.add(`${l.fromId}|${l.toId}`); // hostId|clientId
      }
    }
  }

  // A problematic link (we flag the p2p link) is when there is a p2p link
  // between this peer and a host peer AND a service link between that host and this peer.
  return store.links.filter(l => {
    if (l.kind !== 'p2p') return false;
    if (l.fromId !== p.id && l.toId !== p.id) return false;

    const otherId = l.fromId === p.id ? l.toId : l.fromId;
    const other = store.peers.find(pp => pp.id === otherId);
    if (!other) return false;

    // Determine which side is host (either other or current peer)
    let hostId: string | null = null;
    let clientId: string | null = null;

    if (other.host) {
      hostId = otherId;
      clientId = p.id;
    } else if (p.host) {
      hostId = p.id;
      clientId = otherId;
    } else {
      return false; // Neither side is a host, can't be problematic.
    }

    return servicePairs.has(`${hostId}|${clientId}`);
  });
});
function close(){ open.value=false; }

const addServiceDialogRef = ref<InstanceType<typeof AddServiceDialog>|null>(null)
function openAddService(peerId:string){
  addServiceDialogRef.value?.show(peerId)
}

async function downloadConfig(){
  if (!peer.value) return;
  dlLoading.value = true;
  try {
    const cfg = await backend.fetchPeerConfig(peer.value.name);
    if (cfg){
      const blob = new Blob([cfg], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${peer.value.name}.conf`;
      document.body.appendChild(a); a.click();
      setTimeout(()=> { document.body.removeChild(a); URL.revokeObjectURL(url); },0);
    }
  } finally { dlLoading.value=false; }
}
</script>

<style scoped>
.code-inline { font-size:11px; padding:2px 4px; border-radius:4px; }
</style>
