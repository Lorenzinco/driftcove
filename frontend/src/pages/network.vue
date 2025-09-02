<template>
  <v-container fluid class="pa-0 fill-height">
    <v-row no-gutters class="h-100">
      <v-col cols="12" md="9" class="pa-4">
        <v-sheet rounded="lg" class="pa-0" elevation="2">
          <div class="d-flex align-center justify-space-between px-4 pt-4">
            <div class="d-flex align-center ga-2">
                <v-img
                    src="@/assets/logo.png"
                    alt="Application Logo"
                    class="w-25"
                />
                <v-btn :variant="state.tool==='select' ? 'elevated' : 'tonal'" @click="state.tool='select'" prepend-icon="mdi-cursor-default">Select</v-btn>
                <v-btn :variant="state.tool==='connect' ? 'elevated' : 'tonal'" @click="state.tool='connect'" prepend-icon="mdi-connection">Connect</v-btn>
                <v-divider vertical class="mx-2"/>
                <v-btn :variant="state.tool==='add-peer' ? 'elevated' : 'tonal'" @click="state.tool='add-peer'" prepend-icon="mdi-lan-connect">Peer</v-btn>
                <v-btn :variant="state.tool==='add-subnet' ? 'elevated' : 'tonal'" @click="state.tool='add-subnet'" prepend-icon="mdi-lan">Subnet</v-btn>
                <v-switch
                  v-model="state.grid"
                  inset
                  hide-details
                  label="Grid"
                  class="ma-0 pa-0 switch-inline"
                  style="min-width:auto;"
                />
            </div>
            <div class="text-caption text-medium-emphasis">
              Zoom: {{ (state.zoom*100).toFixed(0) }}% &nbsp; | &nbsp; Pan: {{ state.pan.x.toFixed(0) }}, {{ state.pan.y.toFixed(0) }}
            </div>
          </div>
          <div style="height: 77vh;" class="mr-2 ml-3 canvas-wrapper">
            <canvas ref="canvasRef" class="vpn-canvas"></canvas>
            <!-- Subnet action + button (inside top-right corner) -->
            <v-btn
              v-if="plusSubnet"
              icon="mdi-plus"
              size="x-small"
              class="subnet-add-btn"
              variant="elevated"
              :style="subnetPlusStyle as any"
              @click="onSubnetPlus(plusSubnet)"
            />
          </div>
        </v-sheet>

        <v-card class="mt-4" variant="tonal">
          <v-card-text>
            <div class="d-flex align-center ga-6">
              <div>
                <span class="legend-dot" :style="{background: '#7AD7F0'}"></span> Peer
              </div>
              <div>
                <span class="legend-dot" :style="{background: '#7CF29A'}"></span> Subnet (boundary)
              </div>
              <div>
                <span class="legend-dot" :style="{background: '#86A1FF'}"></span> Link
              </div>
              <v-spacer></v-spacer>
              <div class="text-caption text-medium-emphasis">Wheel to zoom • Middle drag or Shift+Drag to pan • Del to delete • Esc to exit tool</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="3" class="sidebar pa-4">
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="text-h6">Inspector</div>
          <v-btn icon="mdi-delete" variant="text" :disabled="!state.selection" @click="deleteSelection()"></v-btn>
        </div>
        <v-divider class="mb-3"/>

        <template v-if="selectedPeer">
          <div class="text-subtitle-1 mb-2">Peer</div>
          <v-text-field v-model="selectedPeer.name" label="Name" density="comfortable" />
          <v-text-field v-model="selectedPeer.ip" label="IP address" density="comfortable" />
          <v-select
            :items="[{title:'(none)', value:null}, ...state.subnets.map(s=>({title: s.name + ' ('+s.cidr+')', value: s.id}))]"
            v-model="selectedPeer.subnetId" label="Subnet" density="comfortable"
            @update:modelValue="v => assignToSubnet(selectedPeer!.id, v as string | null)"
          />
        </template>

        <template v-else-if="selectedSubnet">
          <div class="text-subtitle-1 mb-2">Subnet</div>
          <v-text-field v-model="selectedSubnet.name" label="Name" density="comfortable" />
          <v-text-field v-model="selectedSubnet.cidr" label="CIDR" density="comfortable" />
          <div class="d-flex ga-2">
            <v-text-field v-model.number="selectedSubnet.width" type="number" label="Width" density="comfortable" hide-details="auto" />
            <v-text-field v-model.number="selectedSubnet.height" type="number" label="Height" density="comfortable" hide-details="auto" />
          </div>
          <div class="text-caption text-medium-emphasis mt-1">Drag edges or edit width/height.</div>
        </template>

        <template v-else>
          <div class="text-medium-emphasis">No selection</div>
        </template>

        <v-divider class="my-4"/>
        <div class="text-subtitle-2 mb-2">Topology JSON</div>
        <v-textarea
          :model-value="JSON.stringify({peers: state.peers, subnets: state.subnets, links: state.links}, null, 2)"
          auto-grow rows="8" readonly class="mono"
        />

        <div class="d-flex ga-2 mt-2">
          <v-btn prepend-icon="mdi-content-copy" @click="copyJson">Copy</v-btn>
          <v-btn variant="tonal" prepend-icon="mdi-content-save" @click="exportJson">Export</v-btn>
          <v-btn variant="tonal" prepend-icon="mdi-folder-open" @click="importJson">Import</v-btn>
        </div>
  <div style="height:80px; flex-shrink:0;"></div>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import type { CSSProperties } from 'vue'

// Types
interface Peer { id: string; name: string; ip: string; subnetId: string | null; x: number; y: number }
interface Subnet { id: string; name: string; cidr: string; x: number; y: number; width: number; height: number }
interface Link { id: string; fromId: string; toId: string }

const canvasRef = ref<HTMLCanvasElement | null>(null)
const ctxRef = ref<CanvasRenderingContext2D | null>(null)
const dpr = window.devicePixelRatio || 1

const CATEGORY_COLORS = {
  peer: '#7AD7F0',
  subnet: '#7CF29A',
  link: '#86A1FF',
}

const state = reactive({
  peers: [
    { id: uid('p_'), name: 'Peer 1', ip: '10.0.1.10', subnetId: null, x: 540, y: 300 } as Peer,
  ],
  subnets: [
    { id: uid('s_'), name: 'Office LAN', cidr: '10.0.1.0/24', x: 520, y: 300, width: 360, height: 240 } as Subnet,
  ],
  links: [] as Link[],
  selection: null as null | {type:'peer'|'subnet'|'link', id: string},
  tool: 'select' as 'select' | 'connect' | 'add-peer' | 'add-subnet',
  pan: { x: 0, y: 0, dragging: false, sx: 0, sy: 0 },
  zoom: 1,
  drag: { active: false, id: '' as string | null, type: null as null | 'peer' | 'subnet' | 'subnet-resize', offsetX: 0, offsetY: 0, startRadius: 0, handle: '' as string, origX:0, origY:0, origW:0, origH:0, containedPeers: [] as string[] },
  connectFrom: null as string | null,
  grid: true,
  hoverPeerId: null as string | null,
  hoverSubnetId: null as string | null,
  debug: false,
  lastPointer: { sx:0, sy:0, wx:0, wy:0 },
})

function uid(prefix = 'id') { return prefix + Math.random().toString(36).slice(2, 9) }
function dist(a: {x:number;y:number}, b: {x:number;y:number}) { const dx=a.x-b.x, dy=a.y-b.y; return Math.hypot(dx,dy) }

// Convert a Mouse/Wheel event to canvas-relative CSS pixel coordinates (independent of world transform)
function pointerToCanvas(e: MouseEvent | WheelEvent) {
  const canvas = canvasRef.value
  if (!canvas) return { sx:0, sy:0 }
  const rect = canvas.getBoundingClientRect()
  return { sx: e.clientX - rect.left, sy: e.clientY - rect.top }
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = (canvas.parentElement as HTMLElement).getBoundingClientRect()
  const width = Math.max(600, rect.width)
  const height = Math.max(400, rect.height)
  canvas.width = width * dpr
  canvas.height = height * dpr
  canvas.style.width = width + 'px'
  canvas.style.height = height + 'px'
  const ctx = canvas.getContext('2d')!
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctxRef.value = ctx
  draw()
}

function toWorld(x:number, y:number) { return { x: (x - state.pan.x) / state.zoom, y: (y - state.pan.y) / state.zoom } }
function toScreen(wx:number, wy:number) { return { x: wx * state.zoom + state.pan.x, y: wy * state.zoom + state.pan.y } }

function hitTestPeer(pt: {x:number;y:number}) {
  for (let i = state.peers.length - 1; i >= 0; i--) {
    const n = state.peers[i]
    if (dist(pt, n) <= 24) return n
  }
  return null
}
function hitTestSubnet(pt:{x:number;y:number}) {
  for (let i= state.subnets.length-1; i>=0; i--) {
    const s = state.subnets[i]
    const left = s.x - s.width/2, right = s.x + s.width/2, top = s.y - s.height/2, bottom = s.y + s.height/2
    if (pt.x >= left && pt.x <= right && pt.y >= top && pt.y <= bottom) return s
  }
  return null
}

function drawGrid(ctx: CanvasRenderingContext2D, width: number, height: number) {
  if (!state.grid) return
  const step = 40 * state.zoom
  const ox = state.pan.x % step
  const oy = state.pan.y % step
  ctx.save()
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'
  ctx.lineWidth = 1
  for (let x = ox; x < width; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke() }
  for (let y = oy; y < height; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke() }
  ctx.restore()
}

function drawSubnets(ctx: CanvasRenderingContext2D) {
  for (const s of state.subnets) {
    const tl = toScreen(s.x - s.width/2, s.y - s.height/2)
    const w = s.width * state.zoom
    const h = s.height * state.zoom
    ctx.save()
    ctx.beginPath(); ctx.rect(tl.x, tl.y, w, h)
    ctx.fillStyle = 'rgba(124,242,154,0.07)'; ctx.fill()
    ctx.strokeStyle = CATEGORY_COLORS.subnet; ctx.lineWidth = 2; ctx.setLineDash([8,6]); ctx.stroke(); ctx.setLineDash([])
    ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.font = '600 14px ui-sans-serif, system-ui'; ctx.textAlign='left'; ctx.textBaseline='bottom'
    ctx.fillText(`${s.name} (${s.cidr})`, tl.x + 8, tl.y - 6)
    ctx.restore()
  }
}

function drawLinks(ctx: CanvasRenderingContext2D) {
  ctx.save(); ctx.lineWidth = 2; ctx.strokeStyle = CATEGORY_COLORS.link
  for (const e of state.links) {
    const a = state.peers.find(p => p.id === e.fromId)
    const b = state.peers.find(p => p.id === e.toId)
    if (!a || !b) continue
    const A = toScreen(a.x, a.y); const B = toScreen(b.x, b.y)
    ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke()
  }
  ctx.restore()
}

function drawPCIcon(ctx: CanvasRenderingContext2D, x: number, y: number) {
  // Simple PC/monitor icon
  const w = 36 * state.zoom
  const h = 24 * state.zoom
  ctx.save()
  ctx.translate(x, y)
  ctx.fillStyle = 'rgba(122,215,240,0.18)'
  ctx.strokeStyle = CATEGORY_COLORS.peer
  ctx.lineWidth = 2
  // Screen
  ctx.beginPath(); ctx.roundRect(-w/2, -h/2, w, h, 4); ctx.fill(); ctx.stroke()
  // Stand
  ctx.beginPath(); ctx.moveTo(-8*state.zoom, h/2); ctx.lineTo(8*state.zoom, h/2); ctx.lineTo(4*state.zoom, h/2 + 8*state.zoom); ctx.lineTo(-4*state.zoom, h/2 + 8*state.zoom); ctx.closePath(); ctx.fillStyle = CATEGORY_COLORS.peer; ctx.fill()
  ctx.restore()
}

function drawPeers(ctx: CanvasRenderingContext2D) {
  for (const n of state.peers) {
    const { x, y } = toScreen(n.x, n.y)
    ctx.save()
    drawPCIcon(ctx, x, y)
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    ctx.font = '600 12px ui-sans-serif, system-ui'
    ctx.textAlign = 'center'; ctx.textBaseline = 'top'
    // Name just below icon
    const nameY = y + 24 * state.zoom
    ctx.fillText(n.name, x, nameY)
    if (state.hoverPeerId === n.id) {
      ctx.font = '500 11px ui-sans-serif, system-ui'
      ctx.fillStyle = 'rgba(255,255,255,0.7)'
      ctx.fillText(n.ip || '(no ip)', x, nameY + 14)
    }
    ctx.restore()
  }
}

function highlightSelection(ctx: CanvasRenderingContext2D) {
  const sel = state.selection; if (!sel) return
  ctx.save(); ctx.strokeStyle = '#FFFFFF'; ctx.setLineDash([4, 4]); ctx.lineWidth = 2
  if (sel.type === 'peer') {
    const n = state.peers.find(p => p.id === sel.id); if (!n) return
    const { x, y } = toScreen(n.x, n.y)
    ctx.beginPath(); ctx.arc(x, y, 30 * state.zoom, 0, Math.PI * 2); ctx.stroke()
  } else if (sel.type === 'subnet') {
    const s = state.subnets.find(s => s.id === sel.id); if (!s) return
    const tl = toScreen(s.x - s.width/2, s.y - s.height/2)
    const w = s.width * state.zoom, h = s.height * state.zoom
    ctx.beginPath(); ctx.rect(tl.x - 4, tl.y - 4, w + 8, h + 8); ctx.stroke()
    // resize handles (centers of edges)
    const handles = subnetHandlesScreen(s)
    ctx.setLineDash([])
    for (const hdl of handles) {
      ctx.fillStyle = '#ffffff'; ctx.strokeStyle = '#000'; ctx.beginPath(); ctx.rect(hdl.x-6, hdl.y-6, 12, 12); ctx.fill(); ctx.stroke()
    }
  }
  ctx.restore()
}

function subnetHandlesScreen(s: Subnet) {
  const halfW = s.width/2, halfH = s.height/2
  const top = toScreen(s.x, s.y - halfH)
  const bottom = toScreen(s.x, s.y + halfH)
  const left = toScreen(s.x - halfW, s.y)
  const right = toScreen(s.x + halfW, s.y)
  return [ {name:'top',...top}, {name:'right',...right}, {name:'bottom',...bottom}, {name:'left',...left} ]
}
function hitSubnetHandle(s: Subnet, sx:number, sy:number) {
  const hs = subnetHandlesScreen(s)
  for (const h of hs) if (Math.abs(sx - h.x)<=10 && Math.abs(sy - h.y)<=10) return h.name
  return null
}

function edgeHandleAt(s: Subnet, sx: number, sy: number): string | null {
  const tl = toScreen(s.x - s.width/2, s.y - s.height/2)
  const br = toScreen(s.x + s.width/2, s.y + s.height/2)
  const threshold = 10
  let handle: string | null = null
  if (Math.abs(sx - tl.x) <= threshold && sy >= tl.y - threshold && sy <= br.y + threshold) handle = 'left'
  else if (Math.abs(sx - br.x) <= threshold && sy >= tl.y - threshold && sy <= br.y + threshold) handle = 'right'
  else if (Math.abs(sy - tl.y) <= threshold && sx >= tl.x - threshold && sx <= br.x + threshold) handle = 'top'
  else if (Math.abs(sy - br.y) <= threshold && sx >= tl.x - threshold && sx <= br.x + threshold) handle = 'bottom'
  return handle
}

function clampToSubnet(node: Peer) {
  if (!node.subnetId) return
  const s = state.subnets.find(s => s.id === node.subnetId); if (!s) return
  const margin = 26
  const left = s.x - s.width/2 + margin
  const right = s.x + s.width/2 - margin
  const top = s.y - s.height/2 + margin
  const bottom = s.y + s.height/2 - margin
  if (node.x < left) node.x = left
  if (node.x > right) node.x = right
  if (node.y < top) node.y = top
  if (node.y > bottom) node.y = bottom
}

// --- Mouse handlers modifications ---
function onMousedown(e: MouseEvent) {
  // Derive canvas-relative coordinates from full-page (pageX/pageY) to ensure stability if page is scrolled.
  const canvas = canvasRef.value!
  const rect = canvas.getBoundingClientRect()
  const sx = e.pageX - (rect.left + window.scrollX)
  const sy = e.pageY - (rect.top + window.scrollY)
  const pt = toWorld(sx, sy)
  // Edge resize detection before selection
  for (let i = state.subnets.length -1; i>=0; i--) {
    const s = state.subnets[i]
    const handle = edgeHandleAt(s, sx, sy) || (state.selection?.id===s.id ? hitSubnetHandle(s, sx, sy) : null)
    if (handle) {
      state.selection = { type:'subnet', id: s.id }
      state.drag = { active:true, id: s.id, type:'subnet-resize', offsetX:0, offsetY:0, startRadius:0, handle, origX: s.x, origY: s.y, origW: s.width, origH: s.height, containedPeers: [] }
      draw(); return
    }
  }
  if (e.button === 1 || (e.button === 0 && e.shiftKey)) { state.pan.dragging = true; state.pan.sx = sx; state.pan.sy = sy; return }
  if (state.tool === 'add-peer') {
    const n: Peer = { id: uid('n_'), name: 'Peer', ip: '', subnetId: null, x: pt.x, y: pt.y }
    state.peers.push(n); state.selection = { type:'peer', id:n.id }; state.tool='select'; draw(); return
  }
  if (state.tool === 'add-subnet') {
    const s: Subnet = { id: uid('s_'), name:'Subnet', cidr:'10.0.0.0/24', x: pt.x, y: pt.y, width: 320, height: 200 }
    state.subnets.push(s); state.selection = { type:'subnet', id:s.id }; state.tool='select'; draw(); return
  }
  const peer = hitTestPeer(pt)
  const subnet = peer ? null : hitTestSubnet(pt)
  if (state.tool === 'connect') {
    if (peer) {
      if (!state.connectFrom) { state.connectFrom = peer.id; state.selection = { type:'peer', id: peer.id } }
      else if (state.connectFrom !== peer.id) { state.links.push({ id: uid('l_'), fromId: state.connectFrom, toId: peer.id }); state.connectFrom = null; state.selection = { type:'peer', id: peer.id } }
      draw()
    }
    return
  }
  if (peer) {
    state.selection = { type:'peer', id: peer.id }
    state.drag = { active:true, id: peer.id, type:'peer', offsetX: pt.x - peer.x, offsetY: pt.y - peer.y, startRadius:0, handle:'', origX:0, origY:0, origW:0, origH:0, containedPeers: [] }
  } else if (subnet) {
    state.selection = { type:'subnet', id: subnet.id }
    const left = subnet.x - subnet.width/2, right = subnet.x + subnet.width/2, top = subnet.y - subnet.height/2, bottom = subnet.y + subnet.height/2
    const contained = state.peers.filter(p => p.x >= left && p.x <= right && p.y >= top && p.y <= bottom).map(p=>p.id)
    state.drag = { active:true, id: subnet.id, type:'subnet', offsetX: pt.x - subnet.x, offsetY: pt.y - subnet.y, startRadius:0, handle:'', origX: subnet.x, origY: subnet.y, origW: subnet.width, origH: subnet.height, containedPeers: contained }
  } else {
    state.selection = null
  }
  draw()
}

function onMousemove(e: MouseEvent) {
  // Use page coordinates adjusted by scroll to derive consistent canvas-relative pointer.
  const canvas = canvasRef.value!
  const rect = canvas.getBoundingClientRect()
  const sx = e.pageX - (rect.left + window.scrollX)
  const sy = e.pageY - (rect.top + window.scrollY)
  if (state.pan.dragging) { state.pan.x += sx - state.pan.sx; state.pan.y += sy - state.pan.sy; state.pan.sx = sx; state.pan.sy = sy; draw(); return }
  const pt = toWorld(sx, sy)
  if (!state.drag.active) {
    const hoverPeer = hitTestPeer(pt)
    const hoverSubnet = hoverPeer ? null : hitTestSubnet(pt)
    const newPeerId = hoverPeer ? hoverPeer.id : null
    const newSubnetId = hoverSubnet ? hoverSubnet.id : null
    if (newPeerId !== state.hoverPeerId || newSubnetId !== state.hoverSubnetId) { state.hoverPeerId = newPeerId; state.hoverSubnetId = newSubnetId; draw() }
  }
  if (!state.drag.active) {
    // update cursor for resize feedback even before selection
    let cursor = 'default'
    if (state.hoverSubnetId) {
      const s = state.subnets.find(s=>s.id===state.hoverSubnetId)
      if (s) {
        const handle = edgeHandleAt(s, sx, sy)
        if (handle === 'left' || handle === 'right') cursor = 'ew-resize'
        else if (handle === 'top' || handle === 'bottom') cursor = 'ns-resize'
      }
    }
    if (canvas.style.cursor !== cursor) canvas.style.cursor = cursor
    return
  }
  if (state.drag.type === 'peer') {
    const n = state.peers.find(p => p.id === state.drag.id)!; n.x = pt.x - state.drag.offsetX; n.y = pt.y - state.drag.offsetY; clampToSubnet(n)
  } else if (state.drag.type === 'subnet') {
    const s = state.subnets.find(s => s.id === state.drag.id)!; const oldX = s.x, oldY = s.y; s.x = pt.x - state.drag.offsetX; s.y = pt.y - state.drag.offsetY; const dx = s.x - oldX; const dy = s.y - oldY;
    for (const p of state.peers) if (state.drag.containedPeers.includes(p.id)) { p.x += dx; p.y += dy }
  } else if (state.drag.type === 'subnet-resize') {
    const s = state.subnets.find(s => s.id === state.drag.id)!; const handle = state.drag.handle
    // Convert pointer to world each time
    const world = pt
    const minW = 120, minH = 100
    let left = s.x - s.width/2, right = s.x + s.width/2, top = s.y - s.height/2, bottom = s.y + s.height/2
    if (handle === 'right') { right = world.x; if (right - left < minW) right = left + minW } 
    else if (handle === 'left') { left = world.x; if (right - left < minW) left = right - minW }
    else if (handle === 'bottom') { bottom = world.y; if (bottom - top < minH) bottom = top + minH }
    else if (handle === 'top') { top = world.y; if (bottom - top < minH) top = bottom - minH }
    s.width = right - left; s.height = bottom - top; s.x = left + s.width/2; s.y = top + s.height/2
    // Clamp contained peers
    for (const p of state.peers) if (p.subnetId === s.id) clampToSubnet(p)
  }
  draw()
}

function assignToSubnet(peerId: string, subnetId: string | null) {
  const n = state.peers.find(p => p.id === peerId)!; const s = state.subnets.find(s => s.id === subnetId)
  n.subnetId = subnetId || null
  if (s) {
    const margin = 40
    const left = s.x - s.width/2 + margin
    const right = s.x + s.width/2 - margin
    const top = s.y - s.height/2 + margin
    const bottom = s.y + s.height/2 - margin
    n.x = left + Math.random() * (right - left)
    n.y = top + Math.random() * (bottom - top)
  }
  draw()
}

// (hoverSubnet & subnetPlusStyle defined later with other computed values)

// JSON import mapping update: convert legacy radius to width/height if present
async function importJson() {
  try {
    // @ts-ignore
    const [h] = await window.showOpenFilePicker({types:[{description:'JSON', accept:{'application/json':['.json']}}]})
    const f = await h.getFile(); const txt = await f.text(); const o = JSON.parse(txt)
    if (o.peers && o.subnets && o.links) {
      const mappedPeers = o.peers.map((p:any)=>({ id: p.id||uid('p_'), name: p.name||'Peer', ip: p.ip||'', subnetId: p.subnetId||null, x: p.x||0, y: p.y||0 }))
      const mappedSubnets = o.subnets.map((s:any)=>({ id: s.id||uid('s_'), name: s.name||'Subnet', cidr: s.cidr||'10.0.0.0/24', x: s.x||0, y: s.y||0, width: s.width || (s.radius? s.radius*2: 320), height: s.height || (s.radius? s.radius*2: 200) }))
      state.peers.splice(0, state.peers.length, ...mappedPeers)
      state.subnets.splice(0, state.subnets.length, ...mappedSubnets)
      state.links.splice(0, state.links.length, ...o.links)
      draw()
    }
  } catch {}
}

// Export uses new schema
function exportJson() {
  const data = JSON.stringify({peers: state.peers, subnets: state.subnets, links: state.links}, null, 2)
  const blob = new Blob([data], {type:'application/json'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = 'topology.json'; a.click(); URL.revokeObjectURL(url)
}

// --- Newly (re)added functions that were removed during refactor ---
function draw() {
  const canvas = canvasRef.value; if (!canvas) return
  const ctx = ctxRef.value; if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const width = canvas.width / dpr, height = canvas.height / dpr
  drawGrid(ctx, width, height)
  drawSubnets(ctx)
  drawLinks(ctx)
  drawPeers(ctx)
  highlightSelection(ctx)
  if ((state as any).debug) {
    const dbg = (state as any)
    ctx.save()
    const sx = dbg.lastPointer?.sx ?? 0, sy = dbg.lastPointer?.sy ?? 0
    const wx = dbg.lastPointer?.wx ?? 0, wy = dbg.lastPointer?.wy ?? 0
    // Crosshair at recorded pointer
    ctx.strokeStyle = 'rgba(255,0,0,0.85)'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(sx-8, sy); ctx.lineTo(sx+8, sy); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(sx, sy-8); ctx.lineTo(sx, sy+8); ctx.stroke()
    // Reproject world back to screen to detect transform mismatch
    const scr = toScreen(wx, wy)
    const dx = scr.x - sx, dy = scr.y - sy
    if (Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) {
      ctx.strokeStyle = 'rgba(255,0,0,0.4)'; ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(scr.x, scr.y); ctx.stroke()
      ctx.fillStyle = 'rgba(255,0,0,0.6)'; ctx.beginPath(); ctx.arc(scr.x, scr.y, 4, 0, Math.PI*2); ctx.fill()
    }
    ctx.fillStyle='rgba(255,255,255,0.9)'; ctx.font='10px monospace'; ctx.textAlign='left'; ctx.textBaseline='top'
    const lines = [
      `sx:${sx.toFixed(2)} sy:${sy.toFixed(2)} -> re:${scr.x.toFixed(2)},${scr.y.toFixed(2)}`,
      `wx:${wx.toFixed(2)} wy:${wy.toFixed(2)} Δ:${dx.toFixed(3)},${dy.toFixed(3)}`,
      `zoom:${state.zoom.toFixed(3)} pan:${state.pan.x.toFixed(1)},${state.pan.y.toFixed(1)} dpr:${dpr}`
    ]
    let bx = Math.min(sx + 12, width - 250); let by = Math.min(sy + 12, height - lines.length*12 - 4)
    lines.forEach((ln,i)=> ctx.fillText(ln, bx, by + i*12))
    // Outline hit regions for debugging
    for (const s of state.subnets) {
      const tl = toScreen(s.x - s.width/2, s.y - s.height/2)
      const w = s.width * state.zoom, h = s.height * state.zoom
      ctx.strokeStyle='rgba(0,200,255,0.5)'; ctx.strokeRect(tl.x, tl.y, w, h)
    }
    for (const p of state.peers) {
      const ps = toScreen(p.x, p.y)
      ctx.beginPath(); ctx.arc(ps.x, ps.y, 24*state.zoom, 0, Math.PI*2); ctx.strokeStyle='rgba(255,255,0,0.5)'; ctx.stroke()
    }
    ctx.restore()
  }
}

function onWheel(e: WheelEvent) {
  e.preventDefault(); e.stopPropagation()
  const { sx: mx, sy: my } = pointerToCanvas(e)
  const worldX = (mx - state.pan.x) / state.zoom
  const worldY = (my - state.pan.y) / state.zoom
  const zoomFactor = Math.exp(-e.deltaY * 0.0015)
  const newZoom = Math.min(2.5, Math.max(0.4, state.zoom * zoomFactor))
  state.zoom = newZoom
  state.pan.x = mx - worldX * state.zoom
  state.pan.y = my - worldY * state.zoom
  draw()
}

function onMouseup() { state.drag.active = false; state.pan.dragging = false }

function deleteSelection() {
  const sel = state.selection; if (!sel) return
  if (sel.type === 'peer') {
    const i = state.peers.findIndex(p => p.id === sel.id); if (i !== -1) state.peers.splice(i, 1)
    state.links = state.links.filter(l => l.fromId !== sel.id && l.toId !== sel.id)
  } else if (sel.type === 'subnet') {
    const i = state.subnets.findIndex(s => s.id === sel.id); if (i !== -1) state.subnets.splice(i, 1)
    for (const p of state.peers) if (p.subnetId === sel.id) p.subnetId = null
  }
  state.selection = null; draw()
}

function onKeydown(e: KeyboardEvent) {
  if ((e.key === 'Delete' || e.key === 'Backspace') && !(e.target as HTMLElement).matches('input, textarea')) { e.preventDefault(); deleteSelection() }
  if (e.key === 'Escape') { state.tool = 'select'; state.connectFrom = null }
  if (e.key === 'F2') { state.debug = !state.debug; draw() }
}

function copyJson() {
  const data = JSON.stringify({peers: state.peers, subnets: state.subnets, links: state.links})
  navigator.clipboard?.writeText(data)
}

function onSubnetPlus(s: Subnet) { /* placeholder for future action */ }

// Computed selections & plus button logic
const selectedPeer = computed(() => state.selection?.type === 'peer' ? state.peers.find(p => p.id === state.selection!.id) || null : null)
const selectedSubnet = computed(() => state.selection?.type === 'subnet' ? state.subnets.find(s => s.id === state.selection!.id) || null : null)
const hoverSubnet = computed(()=> state.hoverSubnetId ? state.subnets.find(s=>s.id===state.hoverSubnetId) || null : null)
// Show plus button if hovering a subnet or one is selected (priority hover)
const plusSubnet = computed(()=> hoverSubnet.value || selectedSubnet.value || null)
const subnetPlusStyle = computed<CSSProperties>(()=> {
  if (!plusSubnet.value) return {}
  const s = plusSubnet.value
  const inset = 14 // keep inside bounds to avoid hover flicker
  const topRight = toScreen(s.x + s.width/2, s.y - s.height/2)
  return {
    position: 'absolute',
    left: (topRight.x - inset) + 'px',
    top: (topRight.y + inset) + 'px',
    transform: 'translate(-50%, -50%)',
    zIndex: 5
  }
})

// Lifecycle wiring
onMounted(() => {
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)
  const c = canvasRef.value!
  c.addEventListener('wheel', onWheel, { passive: false })
  c.addEventListener('mousedown', onMousedown)
  window.addEventListener('mousemove', onMousemove)
  window.addEventListener('mouseup', onMouseup)
  window.addEventListener('keydown', onKeydown)
  document.body.classList.add('no-page-scroll')
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
  const c = canvasRef.value
  if (c) { c.removeEventListener('wheel', onWheel as any); c.removeEventListener('mousedown', onMousedown as any) }
  window.removeEventListener('mousemove', onMousemove as any)
  window.removeEventListener('mouseup', onMouseup as any)
  window.removeEventListener('keydown', onKeydown as any)
  document.body.classList.remove('no-page-scroll')
})

// Reactive redraws
watch(() => state.grid, () => draw())
watch(() => [state.zoom, state.pan.x, state.pan.y, state.peers.length, state.subnets.length, state.links.length, state.subnets.map(s=>s.width+s.height).join(',')], draw, { deep: true })
</script>

<style>
.fill-height { height: 100%; }
.vpn-canvas { background: #181818; border-radius: 10px; display: block; }
.sidebar { width: 100%; border-left: 1px solid rgb(245, 245, 245); overflow-y:auto; max-height:100vh; overscroll-behavior:contain; padding-bottom: 120px; /* prevent footer overlap */ }
body.no-page-scroll { overflow:hidden; }
html, body, #app { height:100%; }
/* Force horizontal label; prevent wrapping */
.switch-inline :deep(.v-label) { white-space: nowrap; display:inline-block; }
/* Harmonize form/control surfaces inside sidebar */
.sidebar :deep(.v-field),
.sidebar :deep(.v-text-field),
.sidebar :deep(.v-textarea),
.sidebar :deep(.v-select),
.sidebar :deep(.v-card),
.sidebar :deep(.v-sheet) { background:#ffffff !important; box-shadow:none; }
.sidebar :deep(.v-field__outline) { --v-field-border-opacity:0.25; }
.sidebar :deep(.v-btn) { background-color:#ffffff; }
.sidebar :deep(.v-btn:not(.v-btn--variant-text)) { box-shadow:none; }
.legend-dot { width: 12px; height: 12px; border-radius: 9999px; display: inline-block; margin-right: 8px; }
.mono textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.subnet-add-btn { pointer-events: auto; }
</style>
