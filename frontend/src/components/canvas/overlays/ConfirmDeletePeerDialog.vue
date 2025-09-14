<template>
  <v-dialog v-model="internal" max-width="440">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-delete-outline" color="error" class="me-2" />
        Delete Peer
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" @click="close" :disabled="loading" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <p class="mb-2">This will remove peer <strong>{{ peerName }}</strong> and all associated links {{  }}.</p>
        <v-alert type="warning" density="compact" text="This action cannot be undone." />
      </v-card-text>
      <v-divider />
      <v-card-actions class="justify-end ga-2">
        <v-btn variant="text" @click="close" :disabled="loading">Cancel</v-btn>
        <v-btn color="error" :loading="loading" @click="confirm">Delete Peer</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { computed } from 'vue';
const props = defineProps<{ modelValue:boolean; peerName:string; loading?:boolean }>();
const emit = defineEmits<{ (e:'update:modelValue', v:boolean):void; (e:'confirm'):void }>();
const internal = computed({ get:()=>props.modelValue, set:(v)=> emit('update:modelValue', v) });
const loading = computed(()=> !!props.loading);
const peerName = computed(()=> props.peerName || '');
function close(){ emit('update:modelValue', false); }
function confirm(){ emit('confirm'); }
</script>
