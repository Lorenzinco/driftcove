<template>
  <v-dialog v-model="internal" max-width="520">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-content-cut" class="me-2" color="error" />
        <span>Confirm Cut</span>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" @click="close" :disabled="loading" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <div v-if="link" class="mb-4 d-flex align-center ga-2 flex-wrap">
          <template v-if="mode==='p2p'">
            <v-icon icon="mdi-account" size="20" class="text-success" />
            <v-icon icon="mdi-arrow-left-right" size="18" class="text-success" />
            <v-icon icon="mdi-account" size="20" class="text-success" />
            <v-icon v-if="problematic" icon="mdi-alert-circle" color="warning" size="20" />
            <span class="font-weight-medium">{{ peerA }} ↔ {{ peerB }}</span>
          </template>
          <template v-else-if="mode==='membership'">
            <v-icon icon="mdi-account" size="20" class="text-secondary" />
            <v-icon icon="mdi-arrow-left-right" size="18" class="text-secondary" />
            <v-icon icon="mdi-lan" size="20" class="text-secondary" />
            <span class="font-weight-medium">{{ peerA }} ↔ {{ peerB }}</span>
          </template>
          <template v-else-if="mode==='service-host'">
            <span class="font-weight-medium">{{ peerB }}</span>
            <v-icon icon="mdi-arrow-right" size="16" class="text-primary" />
            <v-icon icon="mdi-server" size="18" class="text-primary" />
            <span class="font-weight-medium">{{ serviceName }}</span>
          </template>
          <template v-else-if="mode==='service-consumer'">
            <span class="font-weight-medium">This peer</span>
            <v-icon icon="mdi-arrow-right" size="16" class="text-primary" />
            <v-icon icon="mdi-server" size="18" class="text-primary" />
            <span class="font-weight-medium">{{ peerA }} / {{ serviceName }}</span>
          </template>
          <template v-else><!-- generic service -->
            <v-icon icon="mdi-server" size="18" class="text-primary" />
            <v-icon icon="mdi-arrow-right" size="16" class="text-primary" />
            <v-icon icon="mdi-account" size="18" class="text-primary" />
            <span class="font-weight-medium">{{ peerA }} -> {{ peerB }} ({{ serviceName }})</span>
          </template>
        </div>
  <p v-if="mode==='p2p'">Are you sure you want to remove this peer-to-peer link? Unrestricted traffic between these peers will stop.</p>
  <p v-else-if="mode==='membership'">Are you sure you want to remove this membership link? This peer will lose access within the subnet.</p>
  <p v-else>Are you sure you want to disconnect this service link? Access to the service will be revoked.</p>
        <v-alert v-if="mode==='p2p' && problematic" type="warning" density="compact" class="mt-2" text="This p2p link is problematic because a service link also exists between a host and this peer." />
      </v-card-text>
      <v-divider />
      <v-card-actions class="justify-end ga-2">
        <v-btn variant="text" @click="close" :disabled="loading">Cancel</v-btn>
        <v-btn color="error" :loading="loading" @click="emitConfirm">Cut Link</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Link } from '@/types/network';

interface Props { modelValue: boolean; link: Link|null; mode: 'p2p'|'membership'|'service-host'|'service-consumer'|'service-generic'|''; peerA?: string; peerB?: string; serviceName?: string; problematic?: boolean; loading?: boolean }
const props = defineProps<Props>();
const emit = defineEmits<{ (e:'update:modelValue', v:boolean):void; (e:'confirm'):void }>();

const internal = computed({ get:()=>props.modelValue, set:(v)=> emit('update:modelValue', v) });
const peerA = computed(()=> props.peerA || '');
const peerB = computed(()=> props.peerB || '');
const serviceName = computed(()=> props.serviceName || '');
const problematic = computed(()=> !!props.problematic);
const loading = computed(()=> !!props.loading);

function close(){ emit('update:modelValue', false); }
function emitConfirm(){ emit('confirm'); }
</script>

<style scoped>
</style>
