<template>
  <v-dialog v-model="open" max-width="520">
    <v-card v-if="subnet">
      <v-card-title class="d-flex justify-space-between align-center">
        <span><v-icon icon="mdi-subnet" size="24"></v-icon>{{ subnet.name }} ({{ subnet.cidr }})</span>
        <v-btn icon="mdi-close" variant="text" @click="open=false" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <div class="d-flex flex-column ga-2">
          <div v-if="subnet.description"> {{ subnet.description }}</div>
          <div class="mt-2 flex-grow-1">
            <v-expansion-panels class="w-100" multiple>
                <v-expansion-panel v-if="peersInside.length" class="d-flex flex-column">
                  <v-expansion-panel-title>
                    <div class="d-flex align-center">
                      <v-icon size="18" icon="mdi-account-multiple" class="text-success" />
                    </div>
                    Peers inside ({{ peersInside.length }})
                  </v-expansion-panel-title>
                  <v-expansion-panel-text class="pt-0">
                    <div v-if="!peersInside.length" class="text-medium-emphasis">No peers</div>
                    <v-list v-else density="compact" nav class="py-0">
                      <v-list-item v-for="(peer, key) in peersInside" :key="key" @click="$emit('show-peer', peer.id)" class="w-100">
                        <v-list-item-title>
                          <v-icon size="18" icon="mdi-account" class="text-primary" />{{ peer.name || key }}
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          ip: {{ peer.ip }}
                          <span v-if="(Date.now()/1000 - (peer as any).lastHandshake) < 300">
                            | Connected  <v-icon size="18" icon="mdi-check" class="text-success" />
                          </span>
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                    <div class="d-flex justify-end mt-2">
                      <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="$emit('create-peer', subnet.id)">Create Peer</v-btn>
                    </div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
                <v-expansion-panel v-if="linksToSubnets.length" class="d-flex flex-column">
                  <v-expansion-panel-title>
                    <div class="d-flex align-center">
                      <v-icon size="18" icon="mdi-link-variant" class="text-info" />
                    </div>
                    Links to Subnets ({{ linksToSubnets.length }})
                  </v-expansion-panel-title>
                  <v-expansion-panel-text class="pt-0">
                    <div v-if="!linksToSubnets.length" class="text-medium-emphasis">No links</div>
                    <v-list v-else density="compact" nav class="py-0">
                      <v-list-item v-for="(link, key) in linksToSubnets" :key="key" class="w-100">
                        <v-list-item-title @click="$emit('show-subnet', link.fromId === subnet.id ? link.toId : link.fromId)" style="cursor:pointer">
                          <v-icon size="18" icon="mdi-lan" class="text-primary" />{{ link.fromId === subnet.id ? store.subnets.find(s => s.id === link.toId)?.name : store.subnets.find(s => s.id === link.fromId)?.name }}
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          {{ link.fromId === subnet.id ? store.subnets.find(s => s.id === link.toId)?.cidr : store.subnets.find(s => s.id === link.fromId)?.cidr }}
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
                <v-expansion-panel v-if="servicesLinked.length" class="d-flex flex-column">
                  <v-expansion-panel-title>
                    <div class="d-flex align-center">
                      <v-icon size="18" icon="mdi-server" class="text-info" />
                    </div>
                    Services linked ({{ servicesLinked.length }})
                  </v-expansion-panel-title>
                  <v-expansion-panel-text class="pt-0">
                    <div v-if="!servicesLinked.length" class="text-medium-emphasis">No services</div>
                    <v-list v-else density="compact" nav class="py-0">
                      <v-list-item v-for="(svc, key) in servicesLinked" :key="key" class="w-100">
                        <v-list-item-title style="cursor:pointer" @click="$emit('show-peer', svc.hostId)">
                          <v-icon size="18" icon="mdi-server" class="text-primary" />{{ svc.serviceName }}<span v-if="svc.port"> : {{ svc.port }}</span>
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          Host: {{ svc.hostName }} <span v-if="svc.hostIp">({{ svc.hostIp }})</span>
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
                <v-expansion-panel v-if="guestPeers.length" class="d-flex flex-column">
                  <v-expansion-panel-title>
                    <div class="d-flex align-center">
                      <v-icon size="18" icon="mdi-account" class="text-green" />
                    </div>
                    Guest peers ({{ guestPeers.length }})
                  </v-expansion-panel-title>
                  <v-expansion-panel-text class="pt-0">
                    <div v-if="!guestPeers.length" class="text-medium-emphasis">No guests</div>
                    <v-list v-else density="compact" nav class="py-0">
                      <v-list-item v-for="(peer, key) in guestPeers" :key="key" class="w-100" @click="$emit('show-peer', peer.id)">
                        <v-list-item-title style="cursor:pointer">
                          <v-icon size="18" icon="mdi-account" class="text-green" />{{ peer.name || peer.id }}
                        </v-list-item-title>
                        <v-list-item-subtitle>
                          ip: {{ peer.ip }}
                          <span v-if="peer.subnetId" class="ms-2">
                            • home: {{ store.subnets.find(s=> s.id===peer.subnetId)?.name || store.subnets.find(s=> s.id===peer.subnetId)?.cidr }}
                          </span>
                        </v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-expansion-panel-text>
                </v-expansion-panel>
            </v-expansion-panels>

          </div>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" variant="elevated" @click="open=false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue';
import { useNetworkStore } from '@/stores/network';

const emits = defineEmits<{
  (e:'create-peer', subnetId: string): void;
  (e:'show-peer', peerId: string): void;
  (e:'show-subnet', subnetId: string): void;
}>();

const store = useNetworkStore();
const targetSubnetId = ref<string|null>(null);
const model = defineModel<boolean>({ default:false });
const open = computed({ get:()=> model.value, set:(v)=> model.value = v });
const subnet = computed(()=> store.subnets.find(s=> s.id=== targetSubnetId.value));
const peersInside = computed(()=> store.peers.filter(p=> p.subnetId === targetSubnetId.value));
const linksToSubnets = computed(()=> store.links.filter(l=> (l.fromId === targetSubnetId.value && l.kind==='subnet-subnet') || (l.toId === targetSubnetId.value && l.kind==='subnet-subnet') ));
const linksToServices = computed(()=> store.links.filter(l=> (l.fromId === targetSubnetId.value && l.kind==='subnet-service') || (l.toId === targetSubnetId.value && l.kind==='subnet-service') ));
// Build a services list for this subnet using subnet-service links. Each entry shows service name/port and host peer info.
const servicesLinked = computed(()=> {
  const out: Array<{ serviceName: string; port?: number; hostId: string; hostName: string; hostIp?: string }>=[]
  const rel = linksToServices.value
  for (const link of rel){
    // Link shape: fromId is host peer id, toId is subnet id
    const host = store.peers.find(p=> p.id === link.fromId)
    const subnetId = link.toId
    const svcName = (link as any).serviceName as string | undefined
    if (!host || !svcName) continue
    const svcDef = (host.services || {})[svcName]
    out.push({ serviceName: svcName, port: svcDef?.port, hostId: host.id, hostName: host.name, hostIp: host.ip })
  }
  return out
})
const linksToPeers = computed(()=> store.links.filter(l=> (l.fromId === targetSubnetId.value && l.kind==='membership') || (l.toId === targetSubnetId.value && l.kind==='membership') ));

// Peers that are guests of this subnet via membership links (exclude peers whose home subnet is this subnet)
const guestPeers = computed(()=> {
  const sid = targetSubnetId.value
  if (!sid) return [] as typeof store.peers
  const memberPeerIds = new Set<string>()
  for (const l of store.links){
    if ((l as any).kind !== 'membership') continue
    // membership links are modeled as fromId=peerId toId=subnetId
    if (l.toId === sid) memberPeerIds.add(l.fromId)
  }
  return store.peers.filter(p => memberPeerIds.has(p.id) && p.subnetId !== sid)
})

function show(id:string){ targetSubnetId.value = id; open.value=true; }

// Expose API to parent
defineExpose({ show });
</script>
