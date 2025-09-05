<template>
  <v-dialog v-model="open" max-width="520">
    <v-card v-if="subnet">
      <v-card-title class="d-flex justify-space-between align-center">
        <span><v-icon icon="mdi-subnet" size="24"></v-icon>{{ subnet.name }}</span>
        <v-btn icon="mdi-close" variant="text" @click="open=false" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <div class="d-flex flex-column ga-2">
          <div><strong>Address Space:</strong> {{ subnet.cidr }}</div>
          <div v-if="subnet.description"><strong>Description:</strong> {{ subnet.description }}</div>
          <div><strong>Peers inside:</strong> {{ peersInside.length }}</div>
          <div class="mt-2">
            <strong>Peer List:</strong>
            <div v-if="!peersInside.length" class="text-medium-emphasis">None</div>
            <v-chip-group v-else column class="mt-1">
              <v-chip v-for="p in peersInside" :key="p.id" size="small" density="comfortable">{{ p.name }}</v-chip>
            </v-chip-group>
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

const store = useNetworkStore();
const targetSubnetId = ref<string|null>(null);
const model = defineModel<boolean>({ default:false });
const open = computed({ get:()=> model.value, set:(v)=> model.value = v });
const subnet = computed(()=> store.subnets.find(s=> s.id=== targetSubnetId.value));
const peersInside = computed(()=> store.peers.filter(p=> p.subnetId === targetSubnetId.value));

function show(id:string){ targetSubnetId.value = id; open.value=true; }

// Expose API to parent
defineExpose({ show });
</script>
