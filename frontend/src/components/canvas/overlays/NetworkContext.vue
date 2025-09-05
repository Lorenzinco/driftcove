<template>
  <NetworkMenu :open="menu.open" :x="menu.x" :y="menu.y" @create-subnet="createSubnet" />
  <div v-if="menu.open" class="network-menu-backdrop" @mousedown.stop @click="hideMenu" />
</template>
<script setup lang="ts">
import { reactive, onMounted, onUnmounted } from 'vue';
import NetworkMenu from './NetworkMenu.vue';

const menu = reactive({ open:false, x:0, y:0 });

function showMenu(payload:{ x:number; y:number }){ menu.open=true; menu.x=payload.x; menu.y=payload.y; }
function hideMenu(){ menu.open=false; }
function createSubnet(){
  hideMenu();
  window.dispatchEvent(new CustomEvent('request-add-subnet-at-screen', { detail: { screenX: menu.x, screenY: menu.y } }));
}
function onKey(e:KeyboardEvent){ if (e.key==='Escape' && menu.open) hideMenu(); }

onMounted(()=> window.addEventListener('keydown', onKey));
onUnmounted(()=> window.removeEventListener('keydown', onKey));

defineExpose({ showMenu, hideMenu });
</script>

<style scoped>
.network-menu-backdrop { position:fixed; inset:0; z-index: 500; background: transparent; }
</style>
