<template>
  <SubnetMenu
    :open="menu.open"
    :x="menu.x"
    :y="menu.y"
    @create-peer="openAddPeer(menu.subnetId)"
    @info="openInfo(menu.subnetId)"
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

