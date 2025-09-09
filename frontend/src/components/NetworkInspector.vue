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


                <!-- Unified selection detail block to prevent conflicting parallel v-if trees -->
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
                        <v-expansion-panels multiple v-if="store.selectedPeer.host && store.selectedPeer.services && Object.keys(store.selectedPeer.services).length">
                            <v-expansion-panel value="services">
                                <v-expansion-panel-title class="text-subtitle-2">
                                    <v-icon icon="mdi-server" size="18" class="me-1"/> Services ({{ Object.keys(store.selectedPeer.services).length }})
                                </v-expansion-panel-title>
                                <v-expansion-panel-text>
                                    <v-list density="compact">
                                        <v-list-item
                                            v-for="(svc,name) in store.selectedPeer.services"
                                            :key="name"
                                            :title="name + (svc.port ? ' :'+svc.port : '')"
                                            rounded="sm"
                                        >
                                            <template #prepend>
                                                <v-icon icon="mdi-lan" size="16" class="me-1" />
                                            </template>
                                            <template #append>
                                                <span class="text-caption text-medium-emphasis" v-if="svc.description">{{ svc.description }}</span>
                                            </template>
                                        </v-list-item>
                                        <v-list-item v-if="!Object.keys(store.selectedPeer.services).length" title="No services" disabled />
                                    </v-list>
                                </v-expansion-panel-text>
                            </v-expansion-panel>
                        </v-expansion-panels>
        </template>


    <template v-else-if="store.selectedSubnet">
            <v-text-field v-model="store.selectedSubnet.name" label="Name" density="comfortable" />
            <v-text-field v-model="store.selectedSubnet.cidr" label="CIDR" density="comfortable" />
            <div class="d-flex ga-2">
                <v-text-field v-model.number="store.selectedSubnet.width" type="number" label="Width" density="comfortable" hide-details="auto" />
                <v-text-field v-model.number="store.selectedSubnet.height" type="number" label="Height" density="comfortable" hide-details="auto" />
            </div>
            <v-spacer class="mt-3 mb-3"/>
                                    <div class="d-flex flex-column ga-2 w-100 mt-2 align-start">
                                        <v-text-field
                                            v-model="hexColor"
                                            label="Hex color"
                                            density="comfortable"
                                            hide-details="auto"
                                            class="flex-grow-1 w-100"
                                            spellcheck="false"
                                            autocapitalize="off"
                                            autocomplete="off"
                                            @change="applyHexColor"
                                            @blur="applyHexColor"
                                            @keydown.enter.prevent="applyHexColor"
                                        />
                                        <v-color-picker
                                            v-model="pickerRgba"
                                            mode="rgba"
                                            show-alpha
                                            :hide-canvas="false"
                                            hide-inputs
                                            elevation="1"
                                            @update:modelValue="applyPicker"
                                        />
                                    </div>
            <div class="text-caption text-medium-emphasis mt-1">Drag edges or edit width/height.</div>
        </template>

        <template v-else-if="store.selection?.type==='link' && store.selectedLinks && store.selectedLinks.length">
            <div class="mb-2 text-subtitle-2">Links between selected peers ({{ store.selectedLinks.length }})</div>
            <v-alert v-if="store.selectedLinks.some(l=>l.kind==='p2p') && store.selectedLinks.some(l=>l.kind==='service')" type="warning" density="comfortable" class="mb-2">
                <strong>Warning:</strong> Mixed p2p + service links detected between these peers. Consider simplifying.
            </v-alert>
            <v-table density="compact" class="mb-2">
                <thead>
                    <tr>
                        <th class="text-left">Kind</th>
                        <th class="text-left">From</th>
                        <th class="text-left">To</th>
                        <th class="text-left">Service</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="l in store.selectedLinks" :key="l.id">
                        <td>{{ l.kind }}</td>
                        <td>{{ store.peers.find(p => p.id === l.fromId)?.name }}</td>
                        <td>{{ store.peers.find(p => p.id === l.toId)?.name }}</td>
                        <td>{{ l.serviceName || (l.kind==='p2p' ? '-' : '') }}</td>
                    </tr>
                </tbody>
            </v-table>
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
                                <v-icon :color="(Date.now()/1000 - (p as any).lastHandshake) < 300 ? 'blue' : 'yellow'" icon="mdi-lightbulb" size="16" />
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
                                <v-icon :color="(Date.now()/1000 - (p as any).lastHandshake) < 300 ? 'blue' : 'yellow'" icon="mdi-lightbulb" size="16" />
                            </template>
                        </v-list-item>
                        <v-list-item v-if="!nonHostPeers.length" title="No peers" disabled />
                    </v-list>
                </v-expansion-panel-text>
            </v-expansion-panel>
        </v-expansion-panels>
            <div class="d-flex mt-3 ga-2 w-100">
                <v-btn class="flex-grow-1" color="primary" variant="outlined" prepend-icon="mdi-download" @click="exportTopology" :disabled="applying">
                    Export
                </v-btn>
                <v-btn class="flex-grow-1" color="primary" variant="outlined" prepend-icon="mdi-upload" @click="beginImport" :disabled="applying">
                    Import
                </v-btn>
                <input ref="importInput" type="file" accept="application/json" class="d-none" @change="handleImportFile" />
            </div>
            <div class="mt-3">
                <v-btn block color="success" :loading="applying" prepend-icon="mdi-content-save" @click="applyToBackend">
                    Save Changes
                </v-btn>
            </div>
            <v-alert v-if="applyMessage" :type="applySuccess ? 'success' : 'error'" density="comfortable" class="mt-3" dismissible @click:close="applyMessage=''">
                {{ applyMessage }}
            </v-alert>
                <div style="height:80px; flex-shrink:0;"></div>
        </div>
    </template>


<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { nextTick } from 'vue'
import { emitRedraw } from '@/utils/bus'
import { useNetworkStore } from '@/stores/network'
import { useBackendInteractionStore } from '@/stores/backendInteraction'


const store = useNetworkStore()
const backend = useBackendInteractionStore()
const confirmOpen = ref(false)
const applying = ref(false)
const applyMessage = ref('')
const applySuccess = ref(false)
const importInput = ref<HTMLInputElement | null>(null)


// Categorised peer lists
const hostPeers = computed(() => store.peers.filter(p => p.host))
const nonHostPeers = computed(() => store.peers.filter(p => !p.host))

const problematicLinksInNetwork = computed(() => {
    const links = store.links;
    const problems: any[] = []
    for (const p of store.peers) {
        const outgoingP2P = links.filter(l => l.fromId === p.id && l.kind === 'p2p')
        const incomingP2P = links.filter(l => l.toId === p.id && l.kind === 'p2p')
        const outgoingService = links.filter(l => l.fromId === p.id && l.kind === 'service')
        const incomingService = links.filter(l => l.toId === p.id && l.kind === 'service')
        // Outgoing p2p vs outgoing service
        for (const pp of outgoingP2P) {
            for (const ps of outgoingService) if (pp.toId === ps.toId) problems.push(pp)
        }
        // Outgoing p2p vs incoming service
        for (const pp of outgoingP2P) {
            for (const ps of incomingService) if (pp.toId === ps.fromId) problems.push(pp)
        }
        // Incoming p2p vs outgoing service
        for (const pp of incomingP2P) {
            for (const ps of outgoingService) if (pp.fromId === ps.toId) problems.push(pp)
        }
        // Incoming p2p vs incoming service
        for (const pp of incomingP2P) {
            for (const ps of incomingService) if (pp.fromId === ps.fromId) problems.push(pp)
        }
    }
    return problems
})

// Subnet color handling
const hexColor = ref('')
// Vuetify v-color-picker in rgba mode emits object { r,g,b,a } (numbers 0-255 except a 0-1)
const pickerRgba = ref<{ r:number; g:number; b:number; a:number } | null>(null)

function subnetRgbaToComponents(rgbaNum:number){
    const r = (rgbaNum >> 24) & 0xFF;
    const g = (rgbaNum >> 16) & 0xFF;
    const b = (rgbaNum >> 8) & 0xFF;
    const a = (rgbaNum & 0xFF) / 255;
    return { r, g, b, a };
}
function componentsToRgbaNumber(r:number,g:number,b:number,a:number){
    const aByte = Math.round(a*255) & 0xFF;
    return ((r & 0xFF) << 24) | ((g & 0xFF) << 16) | ((b & 0xFF) << 8) | aByte;
}
function updateColorModels(){
    const s = store.selectedSubnet as any;
    if (!s || typeof s.rgba !== 'number') { hexColor.value=''; pickerRgba.value=null; return; }
    const { r,g,b,a } = subnetRgbaToComponents(s.rgba);
    hexColor.value = `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}${aByteHex(a)}`;
    pickerRgba.value = { r, g, b, a };
}
function aByteHex(a:number){ const v = Math.round(a*255); return v.toString(16).padStart(2,'0'); }
function applyHexColor(){
    const s = store.selectedSubnet as any; if (!s) return;
    const v = hexColor.value.replace('#','').trim();
    if (![6,8].includes(v.length)) return; // ignore invalid
    const r = parseInt(v.slice(0,2),16); const g = parseInt(v.slice(2,4),16); const b = parseInt(v.slice(4,6),16); const a = v.length===8 ? parseInt(v.slice(6,8),16)/255 : 0.9;
    s.rgba = componentsToRgbaNumber(r,g,b,a); pickerRgba.value = { r,g,b,a }; invalidateCanvas();
}
function applyPicker(val:any){
    if (!val) return; const s = store.selectedSubnet as any; if (!s) return;
    const r = val.r ?? 0, g = val.g ?? 0, b = val.b ?? 0, a = val.a ?? 1;
    s.rgba = componentsToRgbaNumber(r,g,b,a);
    hexColor.value = `#${r.toString(16).padStart(2,'0')}${g.toString(16).padStart(2,'0')}${b.toString(16).padStart(2,'0')}${aByteHex(a)}`;
    invalidateCanvas();
}
function invalidateCanvas(){ emitRedraw(); }
watch(()=>store.selectedSubnet?.id, ()=> updateColorModels(), { immediate:true });
watch(()=> (store.selectedSubnet as any)?.rgba, ()=> updateColorModels());

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

function exportTopology(){
    try {
        const payload = backend.buildCurrentTopologyPayload()
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `topology-${new Date().toISOString().replace(/[:.]/g,'-')}.json`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
        applyMessage.value = 'Topology exported'
        applySuccess.value = true
    } catch(e:any){
        applyMessage.value = e?.message || 'Failed to export topology'
        applySuccess.value = false
    }
}

function beginImport(){
    importInput.value?.click()
}

function handleImportFile(ev: Event){
    const input = ev.target as HTMLInputElement
    const file = input.files && input.files[0]
    if(!file) return
    const reader = new FileReader()
    applying.value = true
    applyMessage.value = ''
    reader.onload = async () => {
        try {
            const text = String(reader.result || '')
            const parsed = JSON.parse(text)
            const ok = await backend.uploadTopology(parsed)
            applySuccess.value = !!ok
            applyMessage.value = ok ? `Imported ${file.name}` : (backend.lastError || 'Import failed')
            if (ok) await backend.fetchTopology(true)
        } catch(e:any){
            applySuccess.value = false
            applyMessage.value = e?.message || 'Failed to import file'
        } finally {
            applying.value = false
            // reset input so same file can be chosen again
            if (input) input.value = ''
        }
    }
    reader.onerror = () => {
        applySuccess.value = false
        applyMessage.value = 'Failed to read file'
        applying.value = false
    }
    reader.readAsText(file)
}
</script>


<style scoped>
</style>