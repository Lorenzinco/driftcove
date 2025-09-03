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
        <div class="text-subtitle-2 mb-2">Topology JSON</div>
            <v-textarea :model-value="json" auto-grow rows="8" readonly class="mono" />


            <div class="d-flex ga-2 mt-2">
                <v-btn prepend-icon="mdi-content-copy" @click="copyJson">Copy</v-btn>
                <v-btn variant="tonal" prepend-icon="mdi-content-save" @click="exportJson">Export</v-btn>
                <v-btn variant="tonal" prepend-icon="mdi-folder-open" @click="importJson">Import</v-btn>
            </div>
                <div style="height:80px; flex-shrink:0;"></div>
        </div>
    </template>


<script setup lang="ts">
import { computed, ref } from 'vue'
import { useNetworkStore } from '@/stores/network'


const store = useNetworkStore()
const confirmOpen = ref(false)


const json = computed(() => JSON.stringify({ peers: store.peers, subnets: store.subnets, links: store.links }, null, 2))


function copyJson() {
navigator.clipboard?.writeText(JSON.stringify({ peers: store.peers, subnets: store.subnets, links: store.links }))
}


function exportJson() {
const data = JSON.stringify({ peers: store.peers, subnets: store.subnets, links: store.links }, null, 2)
const blob = new Blob([data], { type: 'application/json' })
const url = URL.createObjectURL(blob)
const a = document.createElement('a'); a.href = url; a.download = 'topology.json'; a.click(); URL.revokeObjectURL(url)
}


async function importJson() {
try {
const [h] = await (window as any).showOpenFilePicker({ types: [{ description: 'JSON', accept: { 'application/json': ['.json'] } }] })
const f = await h.getFile(); const txt = await f.text(); const o = JSON.parse(txt)
if (o.peers && o.subnets && o.links) {
store.peers = o.peers
store.subnets = o.subnets
store.links = o.links
}
} catch {}
}

function performDelete() {
    store.deleteSelection()
    confirmOpen.value = false
}
</script>


<style scoped>
</style>