<template>
    <div class="pa-4">
        <div class="d-flex align-center justify-space-between mb-2">
            <div class="text-h6 d-flex align-center" v-if="store.selection">
                {{ store.selection.name }}
            </div>
                        <v-btn
                            v-if="store.selection"
                            icon="mdi-delete"
                            color="error"
                            :title="`Delete ${store.selection.type}`"
                            @click="confirmOpen = true"
                        />
        </div>
        <v-divider class="mb-3"/>

                <v-dialog v-model="confirmOpen" max-width="460">
                    <v-card>
                        <v-card-title class="text-wrap">Delete selection?</v-card-title>
                        <v-card-text class="text-body-2">
                            You are deleting {{ store.selection?.type }} from the network. <br/> Are you sure?
                        </v-card-text>
                        <v-card-actions class="justify-end ga-2">
                            <v-btn variant="text" @click="confirmOpen=false">No</v-btn>
                            <v-btn color="error" variant="elevated" @click="performDelete">Yes</v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>


        <template v-if="store.selectedPeer">
            <v-text-field v-model="store.selectedPeer.name" label="Name" density="comfortable" />
            <v-text-field v-model="store.selectedPeer.ip" label="IP address" density="comfortable" />
            <v-select
            :items="[{title:'(none)', value:null}, ...store.subnets.map(s=>({title: s.name + ' ('+s.cidr+')', value: s.id}))]"
            v-model="store.selectedPeer.subnetId"
            label="Subnet"
            density="comfortable"
            @update:modelValue="v => store.assignToSubnet(store.selectedPeer!.id, v as string | null)"
            />
        </template>


        <template v-else-if="store.selectedSubnet">
            <v-text-field v-model="store.selectedSubnet.name" label="Name" density="comfortable" />
            <v-text-field v-model="store.selectedSubnet.cidr" label="CIDR" density="comfortable" />
            <div class="d-flex ga-2">
                <v-text-field v-model.number="store.selectedSubnet.width" type="number" label="Width" density="comfortable" hide-details="auto" />
                <v-text-field v-model.number="store.selectedSubnet.height" type="number" label="Height" density="comfortable" hide-details="auto" />
            </div>
            <div class="text-caption text-medium-emphasis mt-1">Drag edges or edit width/height.</div>
        </template>


        <template v-else>
            <div class="text-medium-emphasis">No selection</div>
        </template>


        <v-divider class="my-4"/>
        <v-expansion-panels multiple>
            <v-expansion-panel value="subnets">
                <v-expansion-panel-title class="text-subtitle-2">
                    <v-icon icon="mdi-lan" size="18" class="me-1"/> Subnetworks ({{ store.subnets.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                    <v-list density="compact">
                        <v-list-item
                            v-for="s in store.subnets"
                            :key="s.id"
                            :title="s.name + ' (' + s.cidr + ')'"
                            @click="selectSubnet(s)"
                            :active="!!(store.selection && store.selection.type==='subnet' && store.selection.id===s.id)"
                            rounded="sm"
                        >
                            <template #prepend>
                                <v-icon icon="mdi-hexagon-multiple-outline" size="16" class="me-1" />
                            </template>
                        </v-list-item>
                        <v-list-item v-if="!store.subnets.length" title="No subnets" disabled />
                    </v-list>
                </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel value="hosts">
                <v-expansion-panel-title class="text-subtitle-2">
                    <v-icon icon="mdi-server" size="18" class="me-1"/> Hosts ({{ hostPeers.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                    <v-list density="compact">
                        <v-list-item
                            v-for="p in hostPeers"
                            :key="p.id"
                            :title="p.name + (p.ip ? ' ('+p.ip+')' : '')"
                            @click="selectPeer(p)"
                            :active="!!(store.selection && store.selection.type==='peer' && store.selection.id===p.id)"
                            rounded="sm"
                        >
                            <template #prepend>
                                <v-icon icon="mdi-server" size="16" class="me-1" />
                            </template>
                            <template #append>
                                <v-icon :color="p.allowed ? 'blue' : 'yellow'" icon="mdi-lightbulb" size="16" />
                            </template>
                        </v-list-item>
                        <v-list-item v-if="!hostPeers.length" title="No hosts" disabled />
                    </v-list>
                </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel value="peers">
                <v-expansion-panel-title class="text-subtitle-2">
                    <v-icon icon="mdi-account-group" size="18" class="me-1"/> Peers ({{ nonHostPeers.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                    <v-list density="compact">
                        <v-list-item
                            v-for="p in nonHostPeers"
                            :key="p.id"
                            :title="p.name + (p.ip ? ' ('+p.ip+')' : '')"
                            @click="selectPeer(p)"
                            :active="!!(store.selection && store.selection.type==='peer' && store.selection.id===p.id)"
                            rounded="sm"
                        >
                            <template #prepend>
                                <v-icon icon="mdi-account-circle-outline" size="16" class="me-1" />
                            </template>
                            <template #append>
                                <v-icon :color="p.allowed ? 'blue' : 'yellow'" icon="mdi-lightbulb" size="16" />
                            </template>
                        </v-list-item>
                        <v-list-item v-if="!nonHostPeers.length" title="No peers" disabled />
                    </v-list>
                </v-expansion-panel-text>
            </v-expansion-panel>
        </v-expansion-panels>
            <div class="mt-3">
                <v-btn block color="primary" :loading="applying" prepend-icon="mdi-cloud-upload" @click="applyToBackend">Apply Topology To Backend</v-btn>
            </div>
            <v-alert v-if="applyMessage" :type="applySuccess ? 'success' : 'error'" density="comfortable" class="mt-3" dismissible @click:close="applyMessage=''">
                {{ applyMessage }}
            </v-alert>
                <div style="height:80px; flex-shrink:0;"></div>
        </div>
    </template>


<script setup lang="ts">
import { computed, ref } from 'vue'
import { useNetworkStore } from '@/stores/network'
import { useBackendInteractionStore } from '@/stores/backendInteraction'


const store = useNetworkStore()
const backend = useBackendInteractionStore()
const confirmOpen = ref(false)
const applying = ref(false)
const applyMessage = ref('')
const applySuccess = ref(false)


// Categorised peer lists
const hostPeers = computed(() => store.peers.filter(p => p.host))
const nonHostPeers = computed(() => store.peers.filter(p => !p.host))

function selectPeer(p:any) { store.openPeerDetails(p.id) }
function selectSubnet(s:any) {
    store.selection = { type: 'subnet', id: s.id, name: s.name }
}

function performDelete() {
    store.deleteSelection()
    confirmOpen.value = false
}

async function applyToBackend() {
    applying.value = true
    applyMessage.value = ''
    try {
        const payload = backend.buildCurrentTopologyPayload()
        const ok = await backend.uploadTopology(payload)
        applySuccess.value = !!ok
        applyMessage.value = ok ? 'Topology uploaded successfully' : (backend.lastError || 'Upload failed')
        if (ok) {
            // Refresh topology from backend to sync any generated keys / adjustments
            await backend.fetchTopology(true)
        }
    } catch (e:any) {
        applySuccess.value = false
        applyMessage.value = e?.message || 'Unexpected error while uploading'
    } finally {
        applying.value = false
    }
}
</script>


<style scoped>
</style>