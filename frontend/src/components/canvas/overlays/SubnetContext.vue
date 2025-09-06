<template>
  <SubnetMenu
    :open="menu.open"
    :x="menu.x"
    :y="menu.y"
    @create-peer="openAddPeer(menu.subnetId)"
  @create-subnet="openCreateSubnet()"
    @info="openInfo(menu.subnetId)"
  @connect="startConnect(menu.subnetId)"
  />
  <div v-if="menu.open" class="subnet-menu-backdrop" @mousedown.stop @click="hideMenu" />
  <SubnetInfoDialog ref="infoDialog" v-model="infoOpen" />
  <AddPeerDialog ref="addPeerDialog" />
  <PeerConfigDialog ref="peerConfigDialog" />
</template>
<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue';
import SubnetMenu from './SubnetMenu.vue';
import SubnetInfoDialog from './SubnetInfoDialog.vue';
import AddPeerDialog from './AddPeerDialog.vue';
import PeerConfigDialog from './PeerConfigDialog.vue';
import { useNetworkStore } from '@/stores/network';

const store = useNetworkStore();
const menu = reactive({ open:false, x:0, y:0, subnetId:'' });
const infoOpen = ref(false);
const infoDialog = ref<InstanceType<typeof SubnetInfoDialog> | null>(null);
const addPeerDialog = ref<InstanceType<typeof AddPeerDialog> | null>(null);
const peerConfigDialog = ref<InstanceType<typeof PeerConfigDialog> | null>(null);

function showMenu(payload:{ id:string; x:number; y:number }){
  menu.open=true; menu.x=payload.x; menu.y=payload.y; menu.subnetId=payload.id;
}
function hideMenu(){ menu.open=false; }

function openAddPeer(id:string){ hideMenu(); addPeerDialog.value?.show(id); }

function openInfo(id:string){ hideMenu(); infoDialog.value?.show(id); }

function openCreateSubnet(){
  hideMenu();
  // Use the same flow as clicking on canvas with add-subnet: emit global event consumed by page
  const x = menu.x, y = menu.y;
  // We need world coords; page handler already expects worldX/worldY from click flow.
  // Fallback: let page convert using last pointer; we can dispatch a custom event.
  window.dispatchEvent(new CustomEvent('request-add-subnet-at-screen', { detail: { screenX: x, screenY: y } }));
}

function startConnect(id:string){
  hideMenu();
  // Switch tool mode to connect and notify the canvas to initialize with this subnet as source
  store.tool = 'connect' as any;
  store.selection = { type: 'subnet', id, name: store.subnets.find(s=>s.id===id)?.name || 'Subnet' } as any;
  window.dispatchEvent(new CustomEvent('start-connect-from-subnet', { detail: { id } }));
}

function onKey(e:KeyboardEvent){ if (e.key==='Escape' && menu.open) hideMenu(); }
onMounted(()=> window.addEventListener('keydown', onKey));
onUnmounted(()=> window.removeEventListener('keydown', onKey));

window.addEventListener('peer-created-with-config', (e:any)=> {
  const { username, configuration } = e.detail || {};
  if (username && configuration) peerConfigDialog.value?.showImmediate(username, configuration);
});

defineExpose({ showMenu, hideMenu });
</script>

<style scoped>
.subnet-menu-backdrop { position:fixed; inset:0; z-index: 500; background: transparent; }
</style>

