<template>
  <v-dialog v-model="open" max-width="560" persistent>
    <v-card>
      <v-card-title class="d-flex align-center justify-space-between">
        <span class="text-subtitle-1 font-weight-medium"><v-icon icon="mdi-plus" />Create Subnet</span>
        <v-btn icon="mdi-close" variant="text" size="small" @click="close" />
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-form @submit.prevent="submit">
          <v-text-field v-model="form.name" label="Name" variant="outlined" density="comfortable" required />
          <v-text-field v-model="form.subnet" label="CIDR (e.g. 10.0.2.0/24)" variant="outlined" density="comfortable" :error="!!cidrError" :error-messages="cidrError ? [cidrError] : []" required />
          <v-textarea v-model="form.description" label="Description" variant="outlined" auto-grow rows="2" density="comfortable" />
          <span class="pt-3"><v-icon icon="mdi-palette" />Color:</span>
          <div class="d-flex ga-4 mt-2">
            <v-color-picker hide-inputs v-model="picker" elevation="0" class="flex-grow-1" :modes="['rgba']"/>
          </div>
          <div class="text-caption mt-1">Alpha channel controls fill transparency; stroke will be full alpha.</div>
          <v-alert v-if="error" type="error" class="mt-4" density="comfortable">{{ error }}</v-alert>
        </v-form>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn color="primary" :loading="loading" :disabled="!canSubmit" @click="submit">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { useBackendInteractionStore } from '@/stores/backendInteraction'
import { useNetworkStore } from '@/stores/network'
import { cidrContains } from '@/utils/net'

const backend = useBackendInteractionStore()
const netStore = useNetworkStore()

const open = ref(false)
const loading = ref(false)
const error = ref<string|null>(null)
const anchor = reactive({ worldX:0, worldY:0 })

const form = reactive({ name:'', subnet:'', description:'', width:420, height:260, rgba:0x00FF0025 })
const parentCidr = ref<string|null>(null)
const cidrError = ref<string>('')

// Color handling
const picker = ref<any>({ r:0, g:255, b:0, a:0.15 })
const rgbaHex = ref('0x00FF0025')
watch(picker, v => {
  const r = (v.r ?? 0) & 0xFF
  const g = (v.g ?? 0) & 0xFF
  const b = (v.b ?? 0) & 0xFF
  const a = v.a ?? 1
  const alphaByte = Math.round(Math.min(1, Math.max(0,a))*255) & 0xFF
  // Pack as unsigned 32-bit: R (high) G B A (low)
  const packed = ((r<<24) | (g<<16) | (b<<8) | alphaByte) >>> 0
  form.rgba = packed
  rgbaHex.value = '0x' + packed.toString(16).padStart(8,'0').toUpperCase()
})
watch(rgbaHex, h => {
  if (/^0x[0-9a-fA-F]{8}$/.test(h)) {
    const val = parseInt(h,16) >>> 0
    form.rgba = val >>> 0
    const r=(val>>>24)&0xFF, g=(val>>>16)&0xFF, b=(val>>>8)&0xFF, a=(val&0xFF)/255
    picker.value = { r, g, b, a }
  }
})

function validateCidr(raw:string){
  if (!raw){ cidrError.value='CIDR is required'; return }
  const m = raw.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)\/(\d{1,2})$/)
  if (!m){ cidrError.value='Format must be a.b.c.d/len'; return }
  const oct = m.slice(1,5).map(n=> parseInt(n,10))
  const bits = parseInt(m[5],10)
  if (oct.some(o=> o<0||o>255)){ cidrError.value='Octets must be 0-255'; return }
  if (bits<0||bits>32){ cidrError.value='Mask must be 0-32'; return }
  // Compute base & host bits
  const ipInt = (oct[0]<<24)|(oct[1]<<16)|(oct[2]<<8)|oct[3]
  const mask = bits===0?0:(~0 << (32-bits))>>>0
  const base = ipInt & mask
  if (ipInt !== base){
    const n0=(base>>>24)&255, n1=(base>>>16)&255, n2=(base>>>8)&255, n3=base&255
    cidrError.value=`Host bits set; use ${n0}.${n1}.${n2}.${n3}/${bits}`; return
  }
  // Parent containment rules
  if (parentCidr.value){
    if (!cidrContains(parentCidr.value, raw)){ cidrError.value=`Must be inside parent ${parentCidr.value}`; return }
    const parentBits = parseInt(parentCidr.value.split('/')[1],10)
    if (bits <= parentBits){ cidrError.value=`Mask must be more specific than parent (/${parentBits})`; return }
  }
  cidrError.value=''
}

watch(()=>form.subnet, v=> validateCidr(v))

const canSubmit = computed(()=> !!form.name && !cidrError.value)

function showAt(worldX:number, worldY:number){
  anchor.worldX = worldX; anchor.worldY = worldY
  // Determine most specific parent candidate by position (geometry) first, then we validate CIDR later.
  // Use point-in-rectangle test relative to stored subnet positions.
  const candidates = netStore.subnets.filter(s=> {
    const left = s.x - s.width/2, right = s.x + s.width/2, top = s.y - s.height/2, bottom = s.y + s.height/2
    return worldX >= left && worldX <= right && worldY >= top && worldY <= bottom
  })
  candidates.sort((a,b)=> parseInt(b.cidr.split('/')[1]) - parseInt(a.cidr.split('/')[1]))
  parentCidr.value = candidates[0]?.cidr || null
  open.value = true
}

async function submit(){
  if (!canSubmit.value) return
  loading.value = true; error.value=null
  try {
    // Compute clamped width/height if parent exists
    let { width, height } = form
    const parent = netStore.subnets
      .filter(s=> s.cidr && cidrContains(s.cidr, form.subnet))
      .sort((a,b)=> parseInt(b.cidr.split('/')[1]) - parseInt(a.cidr.split('/')[1]))[0]
    let x = anchor.worldX, y = anchor.worldY
    if (parent){
      const margin = 20
      const maxW = parent.width - margin*2
      const maxH = parent.height - margin*2
      if (width > maxW) width = maxW
      if (height > maxH) height = maxH
      // Clamp position so box stays inside
      const left = parent.x - parent.width/2 + margin + width/2
      const right = parent.x + parent.width/2 - margin - width/2
      const top = parent.y - parent.height/2 + margin + height/2
      const bottom = parent.y + parent.height/2 - margin - height/2
      if (x < left) x = left
      if (x > right) x = right
      if (y < top) y = top
      if (y > bottom) y = bottom
    }
  // Normalize to base network (safe because validation guarantees host bits zero)
  const normalized = form.subnet
  const ok = await backend.createSubnet(normalized, form.name, form.description, x, y, width, height, (form.rgba>>>0))
    if (ok){
      // Refresh topology so new subnet exists in store
      await backend.fetchTopology(true)
      const id = form.subnet
      const s = netStore.subnets.find(s=> s.id===id || s.cidr===form.subnet)
      if (s) netStore.selection = { type:'subnet', id: s.id, name: s.name } as any
      // Reuse close logic to switch tool back to select and clear ghost subnet
      close()
    }
  } catch(e:any){ error.value = e?.message || 'Failed to create subnet' } finally { loading.value=false }
}

function close(){
  open.value=false
  // Reset tool to select and clear ghost subnet
  netStore.tool = 'select'
  // Attempt to clear ghost via exposed method on canvas stage (parent passes ref) - emit event upward
  // We'll use a custom event so parent page can call canvasStage.clearGhostSubnet()
  // (Simpler than injecting directly.)
  const evt = new CustomEvent('add-subnet-dialog-closed')
  window.dispatchEvent(evt)
}

defineExpose({ showAt })
</script>
