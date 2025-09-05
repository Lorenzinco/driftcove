<template>
  <PeerMenu
    :open="menu.open"
    :x="menu.x"
    :y="menu.y"
    @info="openInfo(menu.peerId)"
    @delete="confirmDelete(menu.peerId)"
  />
  <div v-if="menu.open" class="peer-menu-backdrop" @mousedown.stop @click="hideMenu" />
  <ConfirmDeletePeerDialog
    v-model="deleteState.open"
    :peer-name="deleteState.peerName"
  :loading="deleteState.loading"
    @confirm="doDeletePeer"
  />
</template>
<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted, computed } from 'vue';
import PeerMenu from './PeerMenu.vue';
import { useNetworkStore } from '@/stores/network';
import { useBackendInteractionStore } from '@/stores/backendInteraction';
import ConfirmDeletePeerDialog from '@/components/canvas/overlays/ConfirmDeletePeerDialog.vue';

const store = useNetworkStore();
const menu = reactive({ open:false, x:0, y:0, peerId:'' });
const deleteState = reactive({ open:false, peerId:'', peerName:'', loading:false });
const backend = useBackendInteractionStore();

function showMenu(payload:{ id:string; x:number; y:number }){
  menu.open=true; menu.x=payload.x; menu.y=payload.y; menu.peerId=payload.id;
}
function hideMenu(){ menu.open=false; }

function openInfo(id:string){ hideMenu(); store.openPeerDetails(id); }
function confirmDelete(id:string){
  const peer = store.peers.find(p=>p.id===id); if (!peer) return;
  hideMenu();
  deleteState.peerId = id; deleteState.peerName = peer.name; deleteState.open=true;
}
async function doDeletePeer(){
  if (!deleteState.peerId) return; deleteState.loading=true;
  try {
    // Backend uses username (peer name) not public key id
    const username = deleteState.peerName;
    const ok = await backend.deletePeer(username);
    if (ok){ deleteState.open=false; }
  } finally { deleteState.loading=false; }
}
function onKey(e:KeyboardEvent){ if (e.key==='Escape' && menu.open) hideMenu(); }

onMounted(()=> window.addEventListener('keydown', onKey));
onUnmounted(()=> window.removeEventListener('keydown', onKey));

defineExpose({ showMenu, hideMenu });
</script>

<style scoped>
.peer-menu-backdrop { position:fixed; inset:0; z-index: 500; background: transparent; }
</style>
