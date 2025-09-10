<template>
  <SubnetMenu
    :open="menu.open"
    :x="menu.x"
    :y="menu.y"
    @create-peer="openAddPeer(menu.subnetId)"
  @create-subnet="openCreateSubnet()"
    @info="openInfo(menu.subnetId)"
  @connect="startConnect(menu.subnetId)"
  @delete="confirmDelete(menu.subnetId)"
  />
  <div v-if="menu.open" class="subnet-menu-backdrop" @mousedown.stop @click="hideMenu" />
  <SubnetInfoDialog ref="infoDialog" v-model="infoOpen" @create-peer="openAddPeer(menu.subnetId)" @show-peer="onShowPeer" @show-subnet="onShowSubnet" />
  <AddPeerDialog ref="addPeerDialog" />
  <PeerConfigDialog ref="peerConfigDialog" />
  <ConfirmDeleteSubnetDialog
    v-model="deleteState.open"
    :subnet-name="deleteState.subnetName"
    :loading="deleteState.loading"
    @confirm="doDeleteSubnet"
  />
</template>
<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue';
import SubnetMenu from './SubnetMenu.vue';
import SubnetInfoDialog from './SubnetInfoDialog.vue';
import AddPeerDialog from './AddPeerDialog.vue';
import PeerConfigDialog from './PeerConfigDialog.vue';
import { useNetworkStore } from '@/stores/network';
import { useBackendInteractionStore } from '@/stores/backendInteraction';
import ConfirmDeleteSubnetDialog from '@/components/canvas/overlays/ConfirmDeleteSubnetDialog.vue';


const store = useNetworkStore();
const backend = useBackendInteractionStore();
const menu = reactive({ open:false, x:0, y:0, subnetId:'' });
const infoOpen = ref(false);
const infoDialog = ref<InstanceType<typeof SubnetInfoDialog> | null>(null);
const addPeerDialog = ref<InstanceType<typeof AddPeerDialog> | null>(null);
const peerConfigDialog = ref<InstanceType<typeof PeerConfigDialog> | null>(null);
const deleteState = reactive({ open:false, subnetId:'', subnetName:'', loading:false });

function showMenu(payload:{ id:string; x:number; y:number }){
  menu.open=true; menu.x=payload.x; menu.y=payload.y; menu.subnetId=payload.id;
}
function hideMenu(){ menu.open=false; }

function openAddPeer(id:string){ hideMenu(); addPeerDialog.value?.show(id); }

function openInfo(id:string){ hideMenu(); infoDialog.value?.show(id); }

function confirmDelete(id:string){
  const subnet = store.subnets.find(s=>s.id===id); if (!subnet) return;
  hideMenu();
  deleteState.subnetId = id; deleteState.subnetName = subnet.name || subnet.cidr || 'Subnet'; deleteState.open = true;
}

function openCreateSubnet(){
  hideMenu();
  // Use the same flow as clicking on canvas with add-subnet: emit global event consumed by page
  const x = menu.x, y = menu.y;
  // We need world coords; page handler already expects worldX/worldY from click flow.
  // Fallback: let page convert using last pointer; we can dispatch a custom event.
  window.dispatchEvent(new CustomEvent('request-add-subnet-at-screen', { detail: { screenX: x, screenY: y } }));
}

function onShowPeer(id:string){
  hideMenu();
  // Open peer details dialog for this peer id
  store.openPeerDetails(id);
}

function onShowSubnet(id:string){
  hideMenu();
  // Open subnet info dialog for this subnet id
  if (infoOpen.value) {
    infoOpen.value = false;
    requestAnimationFrame(() => infoDialog.value?.show(id));
    return;
  }
  infoDialog.value?.show(id);
}


function startConnect(id:string){
  hideMenu();
  // Switch tool mode to connect and notify the canvas to initialize with this subnet as source
  store.tool = 'connect' as any;
  store.selection = { type: 'subnet', id, name: store.subnets.find(s=>s.id===id)?.name || 'Subnet' } as any;
  window.dispatchEvent(new CustomEvent('start-connect-from-subnet', { detail: { id } }));
}

function onKey(e:KeyboardEvent){ if (e.key==='Escape' && menu.open) hideMenu(); }
function onExternalDeleteRequest(e:any){ const id = e?.detail?.id; if (!id) return; confirmDelete(id); }
onMounted(()=> { window.addEventListener('keydown', onKey); window.addEventListener('subnet-context-request-delete', onExternalDeleteRequest as any); });
onUnmounted(()=> { window.removeEventListener('keydown', onKey); window.removeEventListener('subnet-context-request-delete', onExternalDeleteRequest as any); });

window.addEventListener('peer-created-with-config', (e:any)=> {
  const { username, configuration } = e.detail || {};
  if (username && configuration) peerConfigDialog.value?.showImmediate(username, configuration);
});

defineExpose({ showMenu, hideMenu });

async function doDeleteSubnet(payload:{ withPeers:boolean }){
  if (!deleteState.subnetId) return; deleteState.loading = true;
  try {
    const subnet = store.subnets.find(s=> s.id===deleteState.subnetId);
    const cidr = subnet?.cidr || deleteState.subnetName;
    const ok = payload.withPeers ? await backend.deleteSubnetWithPeers(cidr) : await backend.deleteSubnet(cidr);
    if (ok) deleteState.open = false;
  } finally { deleteState.loading = false; }
}
</script>

<style scoped>
.subnet-menu-backdrop { position:fixed; inset:0; z-index: 500; background: transparent; }
</style>

