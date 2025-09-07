<template>
  <v-dialog v-model="model" max-width="520">
    <v-card>
      <v-card-title class="text-h6"><v-icon icon="mdi-delete" class="text-error"></v-icon>Delete Subnet</v-card-title>
      <v-card-text>
        <div v-if="step===1">
          <p>Choose what to delete for <strong>{{ subnetName }}</strong>:</p>
          <v-radio-group v-model="withPeers" hide-details>
            <v-radio :value="false" label="Delete subnet only">
              <template #label>
                <div>
                  <div class="font-weight-medium">Delete subnet only</div>
                  <div class="text-medium-emphasis text-caption">Peers inside will be kept; their access and links to this subnet will be removed.</div>
                </div>
              </template>
            </v-radio>
            <v-radio :value="true">
              <template #label>
                <div>
                  <div class="font-weight-medium text-error">Delete subnet and all peers inside</div>
                  <div class="text-medium-emphasis text-caption">All peers contained in this subnet will be permanently deleted.</div>
                </div>
              </template>
            </v-radio>
          </v-radio-group>
        </div>
        <div v-else>
          <p class="mb-2">Please confirm this action:</p>
          <p v-if="withPeers">
            You are about to delete the subnet <strong>{{ subnetName }}</strong> and <strong>all peers inside it</strong>. This cannot be undone.
          </p>
          <p v-else>
            You are about to delete the subnet <strong>{{ subnetName }}</strong>. Peers will remain, but will be disconnected from this subnet.
          </p>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <template v-if="step===1">
          <v-btn variant="text" @click="cancel" :disabled="loading">Cancel</v-btn>
          <v-btn color="primary" @click="step=2" :disabled="loading">Continue</v-btn>
        </template>
        <template v-else>
          <v-btn variant="text" @click="step=1" :disabled="loading">Back</v-btn>
          <v-btn :color="withPeers ? 'error' : 'warning'" :loading="loading" @click="confirm">
            {{ withPeers ? 'Delete Subnet + Peers' : 'Delete Subnet' }}
          </v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{ modelValue: boolean; subnetName: string; loading?: boolean }>()
const emit = defineEmits<{ (e:'update:modelValue', v:boolean):void; (e:'confirm', payload:{ withPeers:boolean }):void }>()

const model = computed({ get:()=>props.modelValue, set:(v:boolean)=> emit('update:modelValue', v) })
const step = ref(1)
const withPeers = ref(false)
const loading = computed(()=> !!props.loading)

watch(() => props.modelValue, v => { if (v){ step.value = 1; withPeers.value = false } })

function cancel(){ model.value = false }
function confirm(){ emit('confirm', { withPeers: withPeers.value }) }
</script>
