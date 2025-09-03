<template>
  <div class="fill-height p-4">
    <canvas ref="canvasRef" class="vpn-canvas"></canvas>
  </div>
  <v-menu
    v-model="menu.open"
    :close-on-content-click="false"
    location="end"
    origin="top left"
    :offset="[4,0]"
    eager
  >
    <template #activator="{ props }">
      <v-btn
        v-if="plusSubnet"
        icon="mdi-plus"
        size="x-small"
        class="subnet-add-btn"
        variant="elevated"
        v-bind="props"
        :style="subnetPlusStyle as any"
        @click.stop="setMenuSubnet(plusSubnet)"
      />
    </template>
    <v-list density="compact" class="py-1" style="min-width:180px">
      <v-list-subheader class="text-uppercase text-caption">Subnet Actions</v-list-subheader>
      <v-list-item @click="openCreatePeerDialog" prepend-icon="mdi-account-plus-outline" title="Add Peer in this Subnet" />
      <v-divider class="my-1" />
      <v-list-item disabled title="More coming soon" prepend-icon="mdi-dots-horizontal" />
    </v-list>
  </v-menu>

  <!-- Create Peer Dialog -->
  <v-dialog v-model="createPeerDialog.open" max-width="480">
    <v-card>
      <v-card-title class="text-subtitle-1 font-weight-medium">
        Create Peer in Subnet
      </v-card-title>
      <v-card-text class="pt-2">
        <div v-if="activeSubnetForDialog" class="mb-3 text-caption text-medium-emphasis">
          Subnet: <strong>{{ activeSubnetForDialog.name }}</strong>
          <span class="ml-1">({{ activeSubnetForDialog.cidr }})</span>
        </div>
        <v-text-field
          v-model="createPeerDialog.username"
          label="Username"
          density="comfortable"
          variant="outlined"
          :disabled="createPeerDialog.loading || !!createPeerDialog.config"
          :error-messages="createPeerDialog.error ? [createPeerDialog.error] : []"
          autofocus
        />
        <v-alert
          v-if="createPeerDialog.config"
          type="success"
          variant="tonal"
          class="mt-2"
          density="comfortable"
        >
          Peer created successfully. Generated WireGuard configuration below.
        </v-alert>
        <v-expand-transition>
          <div v-if="createPeerDialog.config" class="mt-3">
            <v-textarea
              v-model="createPeerDialog.config"
              label="Configuration"
              density="compact"
              variant="outlined"
              auto-grow
              readonly
              rows="6"
            />
            <div class="d-flex ga-2">
              <v-btn size="small" prepend-icon="mdi-content-copy" @click="copyConfig">Copy</v-btn>
              <v-btn size="small" variant="text" color="secondary" @click="resetCreatePeerDialog">Create another</v-btn>
            </div>
          </div>
        </v-expand-transition>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="closeCreatePeerDialog" :disabled="createPeerDialog.loading">Close</v-btn>
        <v-btn
          color="primary"
            :loading="createPeerDialog.loading"
            :disabled="!canSubmitPeer || !!createPeerDialog.config"
            @click="submitCreatePeer"
        >Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
  import { ref, onMounted, onUnmounted, watch, computed, reactive } from 'vue'
  import type { CSSProperties } from 'vue'
  import { useDisplay } from 'vuetify'
  import { useNetworkStore, type Subnet } from '@/stores/network'
  import { useBackendInteractionStore } from '@/stores/backendInteraction'

  const store = useNetworkStore()
  const display = useDisplay()

  const canvasRef = ref<HTMLCanvasElement | null>(null)
  const ctxRef = ref<CanvasRenderingContext2D | null>(null)
  const dpr = window.devicePixelRatio || 1

  const CATEGORY_COLORS = { peer: '#7AD7F0', subnet: '#7CF29A', link: '#86A1FF' }

  function toWorld(x:number, y:number) { return { x: (x - store.pan.x) / store.zoom, y: (y - store.pan.y) / store.zoom } }
  function toScreen(wx:number, wy:number) { return { x: wx * store.zoom + store.pan.x, y: wy * store.zoom + store.pan.y } }
  function dist(a:{x:number;y:number}, b:{x:number;y:number}) { const dx=a.x-b.x, dy=a.y-b.y; return Math.hypot(dx,dy) }

  function pointerToCanvas(e: MouseEvent | WheelEvent) {
    const canvas = canvasRef.value!
    const rect = canvas.getBoundingClientRect()
    return { sx: e.clientX - rect.left, sy: e.clientY - rect.top }
  }

  function resizeCanvas() {
    const canvas = canvasRef.value; if (!canvas) return
    const rect = (canvas.parentElement as HTMLElement).getBoundingClientRect()
    const width = Math.max(600, rect.width)
    const height = Math.max(400, rect.height)
    canvas.width = width * dpr
    canvas.height = height * dpr
    const ctx = canvas.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctxRef.value = ctx
    draw()
  }

  function hitTestPeer(pt:{x:number;y:number}) {
    for (let i = store.peers.length - 1; i >= 0; i--) {
      const n = store.peers[i]
      if (dist(pt, n) <= 24) return n
    }
    return null
  }
  function hitTestSubnet(pt:{x:number;y:number}) {
    for (let i= store.subnets.length-1; i>=0; i--) {
      const s = store.subnets[i]
      const left = s.x - s.width/2, right = s.x + s.width/2, top = s.y - s.height/2, bottom = s.y + s.height/2
      if (pt.x >= left && pt.x <= right && pt.y >= top && pt.y <= bottom) return s
    }
    return null
  }

  function drawGrid(ctx: CanvasRenderingContext2D, width: number, height: number) {
    if (!store.grid) return
    const step = 40 * store.zoom
    const ox = store.pan.x % step
    const oy = store.pan.y % step
    ctx.save(); ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1
    for (let x = ox; x < width; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke() }
    for (let y = oy; y < height; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke() }
    ctx.restore()
  }

  function drawSubnets(ctx: CanvasRenderingContext2D) {
    for (const s of store.subnets) {
      const tl = toScreen(s.x - s.width/2, s.y - s.height/2)
      const w = s.width * store.zoom
      const h = s.height * store.zoom
      ctx.save()
      ctx.beginPath(); ctx.rect(tl.x, tl.y, w, h)
      ctx.fillStyle = 'rgba(124,242,154,0.07)'; ctx.fill()
      ctx.strokeStyle = CATEGORY_COLORS.subnet; ctx.lineWidth = 2; ctx.setLineDash([8,6]); ctx.stroke(); ctx.setLineDash([])
      ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.font = '600 14px ui-sans-serif, system-ui'; ctx.textAlign='left'; ctx.textBaseline='bottom'
  const label = (s.name && s.name !== s.cidr) ? s.name : s.cidr
  ctx.fillText(label, tl.x + 8, tl.y - 6)
      ctx.restore()
    }
  }

  function drawLinks(ctx: CanvasRenderingContext2D) {
    ctx.save(); ctx.lineWidth = 2; ctx.strokeStyle = CATEGORY_COLORS.link
    for (const e of store.links) {
      const a = store.peers.find(p => p.id === e.fromId)
      const b = store.peers.find(p => p.id === e.toId)
      if (!a || !b) continue
      const A = toScreen(a.x, a.y); const B = toScreen(b.x, b.y)
      ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke()
    }
    ctx.restore()
  }

  function drawPCIcon(ctx: CanvasRenderingContext2D, x: number, y: number, allowed: boolean) {
    const w = 36 * store.zoom, h = 24 * store.zoom
    ctx.save(); ctx.translate(x, y)
    const stroke = allowed ? CATEGORY_COLORS.peer : '#999999'
    const fill = allowed ? 'rgba(122,215,240,0.18)' : 'rgba(160,160,160,0.15)'
    ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2
    ctx.beginPath(); (ctx as any).roundRect?.(-w/2, -h/2, w, h, 4); ctx.fill(); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(-8*store.zoom, h/2); ctx.lineTo(8*store.zoom, h/2); ctx.lineTo(4*store.zoom, h/2 + 8*store.zoom); ctx.lineTo(-4*store.zoom, h/2 + 8*store.zoom); ctx.closePath(); ctx.fillStyle = stroke; ctx.fill()
    // Warning badge if not allowed
    if (!allowed) {
      const r = 7 * store.zoom
      const bx = w/2 - r - 2*store.zoom
      const by = -h/2 + r + 2*store.zoom
      ctx.beginPath(); ctx.arc(bx, by, r, 0, Math.PI*2)
      ctx.fillStyle = '#FFC107'
      ctx.fill(); ctx.strokeStyle = '#222'; ctx.lineWidth = 1; ctx.stroke()
      ctx.fillStyle = '#222'; ctx.font = `${9*store.zoom}px ui-sans-serif`; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText('!', bx, by+0.5*store.zoom)
    }
    ctx.restore()
  }

  function drawPeers(ctx: CanvasRenderingContext2D) {
    for (const n of store.peers) {
      const { x, y } = toScreen(n.x, n.y)
  ctx.save(); drawPCIcon(ctx, x, y, !!(n as any).allowed)
      ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.font = '600 12px ui-sans-serif, system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'top'
      const nameY = y + 24 * store.zoom; ctx.fillText(n.name, x, nameY)
      if (store.hoverPeerId === n.id) { ctx.font = '500 11px ui-sans-serif, system-ui'; ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.fillText(n.ip || '(no ip)', x, nameY + 14) }
      ctx.restore()
    }
  }

  function highlightSelection(ctx: CanvasRenderingContext2D) {
    const sel = store.selection; if (!sel) return
    ctx.save(); ctx.strokeStyle = '#FFFFFF'; ctx.setLineDash([4, 4]); ctx.lineWidth = 2
    if (sel.type === 'peer') {
      const n = store.peers.find(p => p.id === sel.id); if (!n) return
      const { x, y } = toScreen(n.x, n.y)
      ctx.beginPath(); ctx.arc(x, y, 30 * store.zoom, 0, Math.PI * 2); ctx.stroke()
    } else if (sel.type === 'subnet') {
      const s = store.subnets.find(s => s.id === sel.id); if (!s) return
      const tl = toScreen(s.x - s.width/2, s.y - s.height/2)
      const w = s.width * store.zoom, h = s.height * store.zoom
      ctx.beginPath(); ctx.rect(tl.x - 4, tl.y - 4, w + 8, h + 8); ctx.stroke()
    }
    ctx.restore()
  }

  function draw() {
    const canvas = canvasRef.value; const ctx = ctxRef.value; if (!canvas || !ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const width = canvas.width / dpr, height = canvas.height / dpr
    drawGrid(ctx, width, height); drawSubnets(ctx); drawLinks(ctx); drawPeers(ctx); highlightSelection(ctx)
  }

  // Immediate redraw on grid toggle
  watch(() => store.grid, () => draw())

  // Redraw when selection changes (outline/highlight)
  watch(() => store.selection ? store.selection.id + ':' + store.selection.type : '', () => draw())

  // Aggregate watchers for peers/subnets/links to refresh on any field mutation (name/ip/coords/size/etc.)
  watch(
    () => [
      store.peers.map(p => `${p.id}:${p.x}:${p.y}:${p.name}:${p.ip}:${p.subnetId}`).join('|'),
      store.subnets.map(s => `${s.id}:${s.x}:${s.y}:${s.width}:${s.height}:${s.name}:${s.cidr}`).join('|'),
      store.links.map(l => `${l.id}:${l.fromId}:${l.toId}`).join('|')
    ],
    () => draw(),
    { deep: false }
  )

  function onWheel(e: WheelEvent) {
    e.preventDefault(); e.stopPropagation()
    const { sx: mx, sy: my } = pointerToCanvas(e)
    const worldX = (mx - store.pan.x) / store.zoom
    const worldY = (my - store.pan.y) / store.zoom
    const zoomFactor = Math.exp(-e.deltaY * 0.0015)
    store.zoom = Math.min(2.5, Math.max(0.4, store.zoom * zoomFactor))
    store.pan.x = mx - worldX * store.zoom
    store.pan.y = my - worldY * store.zoom
    draw()
  }

  const drag = reactive({ active:false, type:'' as '' | 'peer' | 'subnet', id:'', offsetX:0, offsetY:0, containedPeers: [] as string[] })

  function clampToSubnet(peer: any) {
    if (!peer.subnetId) return
    const s = store.subnets.find(s=>s.id===peer.subnetId); if (!s) return
    const margin = 26
    const left = s.x - s.width/2 + margin
    const right = s.x + s.width/2 - margin
    const top = s.y - s.height/2 + margin
    const bottom = s.y + s.height/2 - margin
    if (peer.x < left) peer.x = left
    if (peer.x > right) peer.x = right
    if (peer.y < top) peer.y = top
    if (peer.y > bottom) peer.y = bottom
  }

  // Edge-based resizing
  type EdgeDir = '' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
  const resizeDrag = reactive({ active:false, id:'', edge:'' as EdgeDir, left:0, top:0, right:0, bottom:0, minW:160, minH:120 })
  function edgeAtPoint(sub: Subnet, pt:{x:number;y:number}): EdgeDir {
    const left = sub.x - sub.width/2, right = sub.x + sub.width/2, top = sub.y - sub.height/2, bottom = sub.y + sub.height/2
    const threshold = 8 / store.zoom
    let vertical = ''
    let horizontal = ''
    if (pt.x >= left - threshold && pt.x <= left + threshold && pt.y >= top - threshold && pt.y <= bottom + threshold) horizontal = 'w'
    if (pt.x >= right - threshold && pt.x <= right + threshold && pt.y >= top - threshold && pt.y <= bottom + threshold) horizontal = horizontal ? horizontal : 'e'
    if (pt.y >= top - threshold && pt.y <= top + threshold && pt.x >= left - threshold && pt.x <= right + threshold) vertical = 'n'
    if (pt.y >= bottom - threshold && pt.y <= bottom + threshold && pt.x >= left - threshold && pt.x <= right + threshold) vertical = vertical ? vertical : 's'
    const combo = (vertical + horizontal) as EdgeDir
    if (combo === 'n' || combo === 's' || combo === 'e' || combo === 'w') return combo
    if (vertical && horizontal) return (vertical + horizontal) as EdgeDir
    return ''
  }
  function cursorForEdge(edge: EdgeDir) {
    switch(edge){
      case 'n': return 'n-resize'; case 's': return 's-resize'; case 'e': return 'e-resize'; case 'w': return 'w-resize';
      case 'ne': return 'ne-resize'; case 'nw': return 'nw-resize'; case 'se': return 'se-resize'; case 'sw': return 'sw-resize';
      default: return ''
    }
  }

  function onMousedown(e: MouseEvent) {
    const rect = canvasRef.value!.getBoundingClientRect()
    const sx = e.pageX - (rect.left + window.scrollX)
    const sy = e.pageY - (rect.top + window.scrollY)
    const pt = toWorld(sx, sy)

    const edgeHover = (resizeDrag as any)._edgeHover as EdgeDir | undefined
    if (edgeHover) {
      for (let i = store.subnets.length -1; i>=0; i--) { const s = store.subnets[i]; if (edgeAtPoint(s, pt)) { resizeDrag.active = true; resizeDrag.id = s.id; resizeDrag.edge = edgeHover; resizeDrag.left = s.x - s.width/2; resizeDrag.top = s.y - s.height/2; resizeDrag.right = s.x + s.width/2; resizeDrag.bottom = s.y + s.height/2; e.preventDefault(); e.stopPropagation(); return } }
    }

    if (e.button === 1 || (e.button === 0 && e.shiftKey)) { store.pan.dragging = true; store.pan.sx = sx; store.pan.sy = sy; return }
    if (store.tool === 'add-peer') { store.addPeerAt(pt.x, pt.y); draw(); return }
    if (store.tool === 'add-subnet') { store.addSubnetAt(pt.x, pt.y); draw(); return }

    const peer = hitTestPeer(pt); const subnet = peer ? null : hitTestSubnet(pt)
    if (store.tool === 'connect') {
      if (peer) {
        if (!(store as any).connectFrom) (store as any).connectFrom = peer.id
        else if ((store as any).connectFrom !== peer.id) { store.links.push({ id: 'l_' + Math.random().toString(36).slice(2,9), fromId: (store as any).connectFrom, toId: peer.id }); (store as any).connectFrom = null }
        store.selection = { type: 'peer', id: peer.id, name: peer.name }; draw()
      }
      return
    }

    if (peer) {
      store.selection = { type: 'peer', id: peer.id, name: peer.name }
      drag.active = true; drag.type='peer'; drag.id=peer.id; drag.offsetX = pt.x - peer.x; drag.offsetY = pt.y - peer.y; drag.containedPeers = []
    } else if (subnet) {
      store.selection = { type: 'subnet', id: subnet.id, name: subnet.name }
      // Capture peers inside subnet to move them with it
      const left = subnet.x - subnet.width/2, right = subnet.x + subnet.width/2, top = subnet.y - subnet.height/2, bottom = subnet.y + subnet.height/2
      drag.containedPeers = store.peers.filter(p => p.x >= left && p.x <= right && p.y >= top && p.y <= bottom).map(p=>p.id)
      drag.active = true; drag.type='subnet'; drag.id=subnet.id; drag.offsetX = pt.x - subnet.x; drag.offsetY = pt.y - subnet.y
    } else {
      store.selection = null
    }
    draw()
  }

  function onMousemove(e: MouseEvent) {
    const rect = canvasRef.value!.getBoundingClientRect()
    const sx = e.pageX - (rect.left + window.scrollY)
    const sy = e.pageY - (rect.top + window.scrollY)
    if (store.pan.dragging) { store.pan.x += sx - store.pan.sx; store.pan.y += sy - store.pan.sy; store.pan.sx = sx; store.pan.sy = sy; draw(); return }
    const pt = toWorld(sx, sy)
    if (resizeDrag.active) {
      const sub = store.subnets.find(s=>s.id===resizeDrag.id)
      if (sub) {
        let { left, top, right, bottom } = resizeDrag
        if (resizeDrag.edge.includes('w')) left = Math.min(right - resizeDrag.minW, pt.x)
        if (resizeDrag.edge.includes('e')) right = Math.max(left + resizeDrag.minW, pt.x)
        if (resizeDrag.edge.includes('n')) top = Math.min(bottom - resizeDrag.minH, pt.y)
        if (resizeDrag.edge.includes('s')) bottom = Math.max(top + resizeDrag.minH, pt.y)
        sub.width = right - left
        sub.height = bottom - top
        sub.x = (left + right)/2
        sub.y = (top + bottom)/2
      }
      draw(); return
    }
    if (drag.active) {
      if (drag.type==='peer') {
        const n = store.peers.find(p=>p.id===drag.id); if (n) { n.x = pt.x - drag.offsetX; n.y = pt.y - drag.offsetY; clampToSubnet(n) }
      } else if (drag.type==='subnet') {
        const s = store.subnets.find(s=>s.id===drag.id); if (s) {
          const oldX = s.x, oldY = s.y
          s.x = pt.x - drag.offsetX; s.y = pt.y - drag.offsetY
          const dx = s.x - oldX, dy = s.y - oldY
          for (const p of store.peers) if (drag.containedPeers.includes(p.id)) { p.x += dx; p.y += dy }
        }
      }
      draw(); return
    }
    // Edge hover detection
    let edge: EdgeDir = ''
    for (let i = store.subnets.length -1; i>=0; i--) { const s = store.subnets[i]; const e2 = edgeAtPoint(s, pt); if (e2) { edge = e2; break } }
    const canvas = canvasRef.value
    if (canvas) canvas.style.cursor = edge ? cursorForEdge(edge) : ''
    ;(resizeDrag as any)._edgeHover = edge

    const hoverPeer = hitTestPeer(pt)
    const hoverSubnet = hoverPeer ? null : hitTestSubnet(pt)
    const newPeerId = hoverPeer ? hoverPeer.id : null
    const newSubnetId = hoverSubnet ? hoverSubnet.id : null
    if (newPeerId !== store.hoverPeerId || newSubnetId !== store.hoverSubnetId) { store.hoverPeerId = newPeerId; store.hoverSubnetId = newSubnetId; draw() }
  }

  function onMouseup() {
    store.pan.dragging = false; drag.active = false
    if (resizeDrag.active) {
      const sub = store.subnets.find(s=>s.id===resizeDrag.id)
      if (sub) for (const p of store.peers) if (p.subnetId === sub.id) clampToSubnet(p)
      resizeDrag.active = false
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if ((e.key === 'Delete' || e.key === 'Backspace') && !(e.target as HTMLElement).matches('input, textarea')) { e.preventDefault(); store.deleteSelection(); draw() }
    if (e.key === 'Escape') { store.tool = 'select'; (store as any).connectFrom = null }
  }

  function onSubnetPlus(_s: Subnet) { /* future action */ }

  const menu = reactive({ open: false, subnetId: '' as string })
  function setMenuSubnet(s: Subnet) { menu.subnetId = s.id }
  // --- Peer creation dialog logic ---
  const backend = useBackendInteractionStore()
  const createPeerDialog = reactive({ open: false, username: '', loading: false, error: '', config: '' })
  const activeSubnetForDialog = computed(() => store.subnets.find(s => s.id === menu.subnetId) || null)
  const canSubmitPeer = computed(() => createPeerDialog.username.trim().length > 0 && !!activeSubnetForDialog.value && !createPeerDialog.loading)

  function openCreatePeerDialog() {
    createPeerDialog.open = true
    createPeerDialog.username = ''
    createPeerDialog.error = ''
    createPeerDialog.config = ''
    menu.open = false
  }
  function closeCreatePeerDialog() { createPeerDialog.open = false }
  function resetCreatePeerDialog() { createPeerDialog.username=''; createPeerDialog.error=''; createPeerDialog.config='' }
  async function submitCreatePeer() {
    if (!canSubmitPeer.value || !activeSubnetForDialog.value) return
    createPeerDialog.loading = true
    createPeerDialog.error = ''
    try {
      const cfg = await backend.createPeer(createPeerDialog.username.trim(), activeSubnetForDialog.value.cidr)
      if (!cfg) {
        createPeerDialog.error = backend.lastError || 'Failed to create peer'
      } else {
        createPeerDialog.config = cfg
      }
    } catch (e:any) {
      createPeerDialog.error = e?.message || 'Unexpected error'
    } finally { createPeerDialog.loading = false }
  }
  function copyConfig() {
    if (!createPeerDialog.config) return
    navigator.clipboard?.writeText(createPeerDialog.config).catch(()=>{})
  }

  const hoverSubnet = computed(() => store.hoverSubnetId ? store.subnets.find(s=>s.id===store.hoverSubnetId) || null : null)
  const selectedSubnet = computed(() => store.selectedSubnet)
  const plusSubnet = computed(() => hoverSubnet.value || selectedSubnet.value || null)
  const subnetPlusStyle = computed<CSSProperties>(() => {
    if (!plusSubnet.value) return {}
    const s = plusSubnet.value
    const edge = toScreen(s.x+s.width/2, s.y)
    const btn = 24
    return { position: 'absolute', left: (edge.x - btn / 2) + 'px', top: (edge.y - btn / 2) + 'px', zIndex: 5, transform: 'none' }
  })

  let ro: ResizeObserver | null = null
  onMounted(() => {
    resizeCanvas()
    const c = canvasRef.value!
    c.addEventListener('wheel', onWheel, { passive: false })
    c.addEventListener('mousedown', onMousedown)
    window.addEventListener('mousemove', onMousemove)
    window.addEventListener('mouseup', onMouseup)
    window.addEventListener('keydown', onKeydown)

    // When drawer opens/closes and pushes layout (desktop), wait for transition
    watch(() => store.inspectorOpen, (open) => {
      if (display.smAndDown.value) return
      setTimeout(resizeCanvas, 300)
    })

    // ResizeObserver so canvas always matches its wrapper
    const parent = c.parentElement
    if (parent) {
      ro = new ResizeObserver(() => resizeCanvas())
      ro.observe(parent)
    }
  })

  onUnmounted(() => {
    const c = canvasRef.value
    if (c) { c.removeEventListener('wheel', onWheel as any); c.removeEventListener('mousedown', onMousedown as any) }
    window.removeEventListener('mousemove', onMousemove as any)
    window.removeEventListener('mouseup', onMouseup as any)
    window.removeEventListener('keydown', onKeydown as any)
    if (ro) { ro.disconnect(); ro = null }
  })
</script>

<style scoped>
.vpn-canvas { background: #181818; border-radius: 10px; display: block; }
.subnet-add-btn { pointer-events: auto; }
</style>