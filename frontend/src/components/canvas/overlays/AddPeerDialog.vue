<template>
  <v-dialog v-model="open" max-width="520">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>Add Peer to {{ subnetLabel }}</span>
        <v-btn icon="mdi-close" variant="text" @click="close()" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <v-alert v-if="error" type="error" class="mb-3" density="comfortable" :text="error" />
        <v-form @submit.prevent="submit" ref="formRef">
          <v-text-field v-model="username" label="Username" autofocus :disabled="loading" required density="comfortable" />
          <v-text-field v-model="address" label="Specific IP (optional)" :disabled="loading" placeholder="e.g. 10.0.10.42" density="comfortable" />
          <div class="text-caption text-medium-emphasis mb-2">Leave IP blank to auto-assign the next available address.</div>
          <v-btn :loading="loading" color="primary" type="submit" prepend-icon="mdi-account-plus" block>Add Peer</v-btn>
        </v-form>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close()">Cancel</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue';
import { useNetworkStore } from '@/stores/network';
import { useBackendInteractionStore } from '@/stores/backendInteraction';

const store = useNetworkStore();
const backend = useBackendInteractionStore();

const open = ref(false);
const targetSubnetId = ref<string | null>(null);
const username = ref('');
const address = ref('');
const loading = ref(false);
const error = ref('');
const formRef = ref();

const subnet = computed(()=> store.subnets.find(s=> s.id===targetSubnetId.value));
const subnetLabel = computed(()=> subnet.value ? (subnet.value.name || subnet.value.cidr) : 'Subnet');

function show(subnetId:string){
  targetSubnetId.value = subnetId;
  username.value = '';
  address.value = '';
  error.value='';
  open.value = true;
}
function close(){ open.value=false; }

async function submit(){
  if (!username.value.trim()) { error.value='Username required'; return; }
  if (!subnet.value) { error.value='Subnet not found'; return; }
  loading.value=true; error.value='';
  try {
    const cidr = subnet.value.cidr;
  const cfg = await backend.createPeer(username.value.trim(), cidr, address.value.trim() || undefined);
    if (!cfg) { error.value = backend.lastError || 'Failed to create peer'; return; }
  // Fire global event to display configuration popup
  window.dispatchEvent(new CustomEvent('peer-created-with-config', { detail: { username: username.value.trim(), configuration: cfg } }));
    // After topology refresh, open the details for peer
  // Suppress immediate peer details popup to avoid overlapping configuration dialog
    open.value=false;
  } catch(e:any){
    error.value = e?.message || 'Unexpected error';
  } finally { loading.value=false; }
}

defineExpose({ show, close });
</script>
