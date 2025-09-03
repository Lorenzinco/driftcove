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

  <!-- Peer Details Dialog -->
  <v-dialog v-model="peerDetails.open" max-width="520">
    <v-card v-if="selectedPeerEntity">
      <v-card-title class="d-flex align-center justify-space-between pr-2">
        <span class="text-subtitle-1 font-weight-medium">Peer Details</span>
  <v-btn icon="mdi-close" variant="text" size="small" @click="peerDetails.open=false; store.closePeerDetails()" />
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <div class="mb-3">
          <div class="text-body-2"><strong>Name:</strong> {{ selectedPeerEntity.name }}</div>
          <div class="text-body-2"><strong>IP:</strong> {{ selectedPeerEntity.ip || '—' }}</div>
          <div class="text-body-2"><strong>Public Key:</strong> {{ peerPublicKey }}</div>
          <div class="text-body-2"><strong>Preshared Key:</strong> {{ selectedPeerEntity.presharedKey || '—' }}</div>
          <div class="text-body-2"><strong>Subnet:</strong> {{ peerSubnetName || 'None' }}</div>
          <div class="text-body-2 d-flex align-center ga-2">
            <strong>Status:</strong>
            <v-chip :color="selectedPeerEntity.allowed ? 'primary' : 'warning'" size="x-small" variant="flat">{{ selectedPeerEntity.allowed ? 'Connected' : 'Isolated' }}</v-chip>
            <v-btn
              v-if="!hasSubnetMembership && selectedPeerEntity.subnetId"
              size="x-small"
              variant="text"
              icon="mdi-link-variant"
              color="green"
              :loading="connectLoading"
              :title="'Connect peer to its subnet'"
              @click="connectPeerToItsSubnet"
            />
            <v-btn
              v-if="hasSubnetMembership && selectedPeerEntity.subnetId"
              size="x-small"
              variant="text"
              icon="mdi-link-variant-off"
              color="red"
              :loading="connectLoading"
              :title="'Disconnect peer from its subnet'"
              @click="disconnectPeerFromItsSubnet"
            />
            <v-btn
              v-if="!selectedPeerEntity.allowed"
              size="x-small"
              variant="text"
              icon="mdi-information"
              color="primary"
              :title="'Why is this peer isolated?'"
              @click="isolationInfo.open = true"
            />
          </div>
          <div class="text-body-2"><strong>Host:</strong> {{ isHostPeer ? 'Yes' : 'No' }}</div>
        </div>
        <v-divider class="my-3" />
        <div>
          <div class="text-subtitle-2 mb-2 d-flex align-center">
            <v-icon size="18" class="mr-1">mdi-server</v-icon>
            Hosted Services ({{ serviceEntries.length }})
          </div>
          <div v-if="serviceEntries.length === 0" class="text-body-2 text-medium-emphasis">No hosted services.</div>
          <v-expansion-panels multiple v-else>
            <v-expansion-panel v-for="([svcKey, svc], idx) in serviceEntries" :key="svcKey">
              <v-expansion-panel-title>
                <div class="d-flex flex-column w-100">
                  <div class="d-flex align-center justify-space-between w-100">
                    <span>{{ svc.name || svcKey }}</span>
                    <v-chip size="x-small" color="primary" variant="tonal">Port {{ svc.port }}</v-chip>
                  </div>
                  <small v-if="svc.department" class="text-medium-emphasis">{{ svc.department }}</small>
                </div>
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div class="text-body-2 mb-1"><strong>Name:</strong> {{ svc.name || svcKey }}</div>
                <div class="text-body-2 mb-1"><strong>Port:</strong> {{ svc.port }}</div>
                <div class="text-body-2 mb-1"><strong>Department:</strong> {{ svc.department || '—' }}</div>
                <div class="text-body-2 mb-1"><strong>Description:</strong> {{ svc.description || 'No description' }}</div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="peerDetails.open=false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Subnet Creation Dialog (opened when add-subnet tool active and empty canvas clicked) -->
  <v-dialog v-model="subnetDialog.open" max-width="520">
    <v-card>
      <v-card-title class="text-subtitle-1 font-weight-medium">Create Subnet</v-card-title>
      <v-card-text class="pt-2">
        <v-text-field v-model="subnetDialog.subnet" label="CIDR" variant="outlined" density="comfortable" placeholder="10.0.2.0/24" :disabled="subnetDialog.loading" />
        <v-text-field v-model="subnetDialog.name" label="Name" variant="outlined" density="comfortable" :disabled="subnetDialog.loading" />
        <v-textarea v-model="subnetDialog.description" label="Description" variant="outlined" density="compact" auto-grow :disabled="subnetDialog.loading" />
  <div class="text-caption text-medium-emphasis mt-2">Position captured at click (X: {{ subnetDialog.x }}, Y: {{ subnetDialog.y }})</div>
        <v-alert v-if="subnetDialog.error" type="error" density="compact" class="mt-3" variant="tonal">{{ subnetDialog.error }}</v-alert>
        <v-alert v-else-if="subnetDialog.success" type="success" density="compact" class="mt-3" variant="tonal">Subnet created.</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="closeSubnetDialog" :disabled="subnetDialog.loading">Cancel</v-btn>
        <v-btn color="primary" :loading="subnetDialog.loading" :disabled="!canCreateSubnet" @click="submitSubnet">Create</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- Connection Choice Dialog -->
  <v-dialog v-model="connectState.dialogOpen" max-width="460">
    <v-card>
      <v-card-title class="text-subtitle-1 font-weight-medium">Create Connection</v-card-title>
      <v-card-text class="pt-2">
        <div class="text-body-2 mb-2">From: <strong>{{ peerName(connectState.fromPeerId) }}</strong></div>
        <div class="text-body-2 mb-4">To: <strong>{{ peerName(connectState.pendingPeerId) }}</strong></div>
        <v-radio-group v-model="connectState.selectedMode" class="mb-2 connection-mode-group" :disabled="false">
          <v-radio value="p2p" class="mb-2">
            <template #label>
              <div class="d-flex flex-column">
                <span class="d-flex align-center ga-1">
                  <v-icon size="16" color="green">mdi-account-arrow-right</v-icon>
                  <strong>Peer ↔ Peer</strong>
                </span>
                <span class="text-caption text-medium-emphasis">Direct link between two peers (green line).</span>
              </div>
            </template>
          </v-radio>
          <v-radio v-if="connectState.services.length" value="service" class="mb-1">
            <template #label>
              <div class="d-flex flex-column">
                <span class="d-flex align-center ga-1">
                  <v-icon size="16" color="primary">mdi-server-network</v-icon>
                  <strong>Peer ↔ Service</strong>
                </span>
                <span class="text-caption text-medium-emphasis">Route traffic to a specific hosted service on target (blue line).</span>
              </div>
            </template>
          </v-radio>
          <div v-else class="text-caption text-medium-emphasis mt-1">Target peer hosts no services.</div>
        </v-radio-group>
        <v-select
          v-if="connectState.selectedMode==='service' && connectState.services.length"
          :items="connectState.services.map(s=>({ title: s[0], value: s[0] }))"
          v-model="connectState.selectedService"
          label="Service"
          density="comfortable"
          variant="outlined"
        />
        <div v-else-if="connectState.selectedMode==='service'" class="text-caption text-medium-emphasis">No services available on target.</div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="resetConnection">Cancel</v-btn>
        <v-btn color="primary" @click="finalizeConnection" :disabled="connectState.selectedMode==='service' && !connectState.selectedService">Connect</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <v-bottom-sheet v-model="isolationInfo.open">
    <v-card>
      <v-card-title class="text-subtitle-1">Why is this peer isolated?</v-card-title>
      <v-card-text class="text-body-2">
        <p>This peer currently has no active connections (p2p, service, or subnet membership). A peer becomes Connected when it participates in at least one link.</p>
        <ul class="pl-4">
          <li>Create a Peer ↔ Peer link.</li>
          <li>Create a Peer ↔ Service link to a host's service.</li>
          <li>Use the green chain button to connect the peer to its subnet.</li>
        </ul>
        <p>After creating a connection the status updates on the next topology refresh (or immediately after the action).</p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="isolationInfo.open=false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-bottom-sheet>
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
    ctx.save(); ctx.lineWidth = 2
    for (const e of store.links) {
      const a = store.peers.find(p => p.id === e.fromId)
      const b = store.peers.find(p => p.id === e.toId)
      if (!a || !b) continue
      const A = toScreen(a.x, a.y); const B = toScreen(b.x, b.y)
      ctx.beginPath();
      // Color by kind
      if (e.kind === 'p2p') ctx.strokeStyle = '#4CAF50' // green
      else if (e.kind === 'service') ctx.strokeStyle = '#2196F3' // blue
      else ctx.strokeStyle = CATEGORY_COLORS.link
      ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke()
      // Service label midpoint
      if (e.kind === 'service' && e.serviceName) {
        const mx = (A.x + B.x)/2, my = (A.y + B.y)/2
        ctx.save(); ctx.fillStyle = 'rgba(33,150,243,0.15)'; ctx.strokeStyle = '#2196F3'; const pad=4; ctx.font = `${11*store.zoom}px ui-sans-serif`; const text = e.serviceName; const tw = ctx.measureText(text).width; const th = 12*store.zoom; ctx.beginPath(); ctx.roundRect?.(mx - tw/2 - pad, my - th/2 - pad, tw + pad*2, th + pad*2, 4*store.zoom); ctx.fill(); ctx.stroke(); ctx.fillStyle = '#FFFFFF'; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(text, mx, my); ctx.restore()
      }
    }
    // Ghost link
    if (connectState.active && connectState.fromPeerId && connectState.ghostTo) {
      const a = store.peers.find(p=>p.id===connectState.fromPeerId)
      if (a) {
        const A = toScreen(a.x, a.y)
        const B = toScreen(connectState.ghostTo.x, connectState.ghostTo.y)
        ctx.save(); ctx.setLineDash([6,4]); ctx.strokeStyle = '#FFFFFF'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke(); ctx.restore()
      }
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

  function drawServerIcon(ctx: CanvasRenderingContext2D, x: number, y: number, allowed: boolean) {
    const w = 34 * store.zoom, h = 44 * store.zoom
    ctx.save(); ctx.translate(x, y)
    const stroke = allowed ? CATEGORY_COLORS.peer : '#999999'
    const fill = allowed ? 'rgba(122,215,240,0.22)' : 'rgba(160,160,160,0.18)'
    ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2
    // Chassis
    ctx.beginPath(); (ctx as any).roundRect?.(-w/2, -h/2, w, h, 5); ctx.fill(); ctx.stroke()
    // Drive bays / slots
    ctx.fillStyle = stroke
    const slotH = 6 * store.zoom
    for (let i=0;i<3;i++) {
      ctx.beginPath(); ctx.roundRect?.(-w/2 + 6*store.zoom, -h/2 + 8*store.zoom + i* (slotH + 5*store.zoom), w - 12*store.zoom, slotH, 2*store.zoom)
      ctx.globalAlpha = 0.55; ctx.fill(); ctx.globalAlpha = 1
    }
    // Power indicator
    const r = 4 * store.zoom
    ctx.beginPath(); ctx.arc(0, h/2 - r - 6*store.zoom, r, 0, Math.PI*2); ctx.fillStyle = allowed ? '#4CAF50' : '#FFC107'; ctx.fill(); ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke()
    // Warning badge if isolated
    if (!allowed) {
      const rb = 7 * store.zoom
      const bx = w/2 - rb - 3*store.zoom
      const by = -h/2 + rb + 3*store.zoom
      ctx.beginPath(); ctx.arc(bx, by, rb, 0, Math.PI*2)
      ctx.fillStyle = '#FFC107'; ctx.fill(); ctx.strokeStyle = '#222'; ctx.lineWidth = 1; ctx.stroke()
      ctx.fillStyle = '#222'; ctx.font = `${9*store.zoom}px ui-sans-serif`; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText('!', bx, by+0.5*store.zoom)
    }
    ctx.restore()
  }

  function drawPeers(ctx: CanvasRenderingContext2D) {
    for (const n of store.peers) {
      const { x, y } = toScreen(n.x, n.y)
      const isHost = (n as any).host && n.host === true && n.services && Object.keys(n.services).length > 0
      ctx.save();
      if (isHost) {
        drawServerIcon(ctx, x, y, !!(n as any).allowed)
      } else {
        drawPCIcon(ctx, x, y, !!(n as any).allowed)
      }
      ctx.fillStyle = 'rgba(255,255,255,0.92)'; ctx.font = '600 12px ui-sans-serif, system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'top'
      const nameY = y + 24 * store.zoom; ctx.fillText(n.name, x, nameY)
      if (store.hoverPeerId === n.id) { ctx.font = '500 11px ui-sans-serif, system-ui'; ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.fillText(n.ip || '(no ip)', x, nameY + 14) }
      // Info icon when hovering a host peer
      if (store.hoverPeerId === n.id) {
        const iconR = 10 * store.zoom
        const ix = x + 30 * store.zoom
        const iy = y - 22 * store.zoom
        ctx.beginPath(); ctx.arc(ix, iy, iconR, 0, Math.PI*2)
        ctx.fillStyle = isHost ? '#2196F3' : '#555'
        ctx.fill()
        ctx.strokeStyle = isHost ? '#0D47A1' : '#222'
        ctx.lineWidth = 1.5; ctx.stroke()
        ctx.fillStyle = '#fff'; ctx.font = `${11*store.zoom}px ui-sans-serif`; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText('i', ix, iy+0.5*store.zoom)
      }
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
  drawGrid(ctx, width, height); drawSubnets(ctx); drawLinks(ctx); drawPeers(ctx); drawGhostConnectIcon(ctx); drawGhostSubnet(ctx); highlightSelection(ctx)
  }

  // Immediate redraw on grid toggle
  watch(() => store.grid, () => draw())

  // Redraw when selection changes (outline/highlight)
  watch(() => store.selection ? store.selection.id + ':' + store.selection.type : '', () => draw())

  // Aggregate watchers for peers/subnets/links to refresh on any field mutation (name/ip/coords/size/etc.)
  watch(
    () => [
  store.peers.map(p => `${p.id}:${p.x}:${p.y}:${p.name}:${p.ip}:${p.subnetId}:${(p as any).host?1:0}:${p.services ? Object.keys(p.services).length : 0}`).join('|'),
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

  const clickDetect = reactive({ down:false, x:0, y:0, targetPeerId:'', targetType:'' as ''|'peer'|'subnet', moved:false })
  // Connection state for connect tool
  const connectState = reactive({ active:false, fromPeerId:'', ghostTo: null as null | { x:number; y:number }, pendingPeerId:'', dialogOpen:false, targetPeer:null as any, services: [] as Array<[string, any]>, selectedMode:'p2p' as 'p2p'|'service', selectedService:'' })
  const connectCursor = reactive({ active:false, x:0, y:0 })

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
    if (store.tool === 'add-subnet') {
      // If clicking empty space (no peer/subnet), open dialog at position
      const peer = hitTestPeer(pt); const subnet = peer ? null : hitTestSubnet(pt)
      if (!peer && !subnet) {
        openSubnetDialog(pt.x, pt.y)
        return
      }
    }

    const peer = hitTestPeer(pt); const subnet = peer ? null : hitTestSubnet(pt)
    if (store.tool === 'connect') {
      if (peer) {
        if (!connectState.active) {
          connectState.active = true; connectState.fromPeerId = peer.id; connectState.ghostTo = { x: peer.x, y: peer.y }
        } else if (connectState.fromPeerId && connectState.fromPeerId !== peer.id) {
          // Second endpoint chosen -> open dialog
          connectState.pendingPeerId = peer.id
          const target = store.peers.find(p=>p.id===peer.id)
          connectState.targetPeer = target || null
          connectState.services = target && target.services ? Object.entries(target.services) : []
          connectState.selectedMode = connectState.services.length ? 'service' : 'p2p'
          connectState.selectedService = connectState.services.length ? connectState.services[0][0] : ''
          connectState.dialogOpen = true
        }
        store.selection = { type: 'peer', id: peer.id, name: peer.name }; draw()
      }
      return
    }

    if (peer) {
      store.selection = { type: 'peer', id: peer.id, name: peer.name }
      drag.active = true; drag.type='peer'; drag.id=peer.id; drag.offsetX = pt.x - peer.x; drag.offsetY = pt.y - peer.y; drag.containedPeers = []
      clickDetect.down = true; clickDetect.x = pt.x; clickDetect.y = pt.y; clickDetect.targetPeerId = peer.id; clickDetect.targetType = 'peer'; clickDetect.moved = false
    } else if (subnet) {
      store.selection = { type: 'subnet', id: subnet.id, name: subnet.name }
      // Capture peers inside subnet to move them with it
      const left = subnet.x - subnet.width/2, right = subnet.x + subnet.width/2, top = subnet.y - subnet.height/2, bottom = subnet.y + subnet.height/2
      drag.containedPeers = store.peers.filter(p => p.x >= left && p.x <= right && p.y >= top && p.y <= bottom).map(p=>p.id)
      drag.active = true; drag.type='subnet'; drag.id=subnet.id; drag.offsetX = pt.x - subnet.x; drag.offsetY = pt.y - subnet.y
      clickDetect.down = true; clickDetect.x = pt.x; clickDetect.y = pt.y; clickDetect.targetPeerId = ''; clickDetect.targetType = 'subnet'; clickDetect.moved = false
    } else {
      store.selection = null
      clickDetect.down = false
    }
    draw()
  }

  function onMousemove(e: MouseEvent) {
    const rect = canvasRef.value!.getBoundingClientRect()
  const sx = e.pageX - (rect.left + window.scrollX)
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
      // Mark movement for click detection
      if (clickDetect.down && !clickDetect.moved) {
        const mdx = pt.x - clickDetect.x, mdy = pt.y - clickDetect.y
        if (Math.hypot(mdx, mdy) > 4 / store.zoom) clickDetect.moved = true
      }
      draw(); return
    }
    if (clickDetect.down && !clickDetect.moved) {
      const dx = pt.x - clickDetect.x, dy = pt.y - clickDetect.y
      if (Math.hypot(dx, dy) > 4 / store.zoom) clickDetect.moved = true
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
    // Pointer cursor for host peers
  if (!edge && hoverPeer) { if (canvas) canvas.style.cursor = 'pointer' }
    // Update ghost connection line
    if (store.tool==='connect' && connectState.active && connectState.fromPeerId && !connectState.dialogOpen) {
      connectState.ghostTo = { x: pt.x, y: pt.y }
      draw()
    }
    if (store.tool==='connect' && !connectState.active && !connectState.dialogOpen) {
      connectCursor.active = true
      connectCursor.x = pt.x
      connectCursor.y = pt.y
      draw()
    }
    // Ghost subnet update when tool active
    if (store.tool === 'add-subnet' && !drag.active && !resizeDrag.active && !subnetDialog.open && !ghostSubnet.locked) {
      ghostSubnet.active = true
      ghostSubnet.x = pt.x
      ghostSubnet.y = pt.y
      draw()
    }
  }

  function onMouseup() {
    store.pan.dragging = false; drag.active = false
    if (resizeDrag.active) {
      const sub = store.subnets.find(s=>s.id===resizeDrag.id)
      if (sub) for (const p of store.peers) if (p.subnetId === sub.id) clampToSubnet(p)
      resizeDrag.active = false
    }
    // Single click detection: open peer detail dialog
    if (clickDetect.down && !clickDetect.moved && clickDetect.targetType === 'peer' && clickDetect.targetPeerId) {
      const peer = store.peers.find(p=>p.id===clickDetect.targetPeerId)
      if (peer) { store.openPeerDetails(peer.id) }
    }
    clickDetect.down = false
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

  // Peer details dialog state & computed data
  const peerDetails = reactive({ open:false })
  const isolationInfo = reactive({ open:false })
  const connectLoading = ref(false)
  watch(() => store.peerDetailsRequestVersion, () => {
    if (store.peerDetailsRequestId) peerDetails.open = true
  })
  const selectedPeerEntity = computed(() => store.selectedPeer)
  const peerSubnetName = computed(() => {
    const p = selectedPeerEntity.value; if (!p) return ''
    if (!p.subnetId) return ''
    const s = store.subnets.find(s=>s.id===p.subnetId)
    return s ? (s.name || s.cidr) : ''
  })
  const isHostPeer = computed(() => {
    const p = selectedPeerEntity.value; return !!(p && (p as any).host && p.services && Object.keys(p.services).length>0)
  })
  const serviceEntries = computed(() => {
    const p:any = selectedPeerEntity.value; if (!p || !p.services) return [] as Array<[string, any]>
    return Object.entries(p.services)
  })
  const peerPublicKey = computed(() => {
    const p = selectedPeerEntity.value; if (!p) return ''
    return p.id.startsWith('peer_') ? p.id.slice(5) : p.id
  })
  const selectedPeerSubnetCidr = computed(() => {
    const p = selectedPeerEntity.value; if (!p || !p.subnetId) return ''
    const s = store.subnets.find(s=>s.id===p.subnetId)
    return s?.cidr || ''
  })
  const hasSubnetMembership = computed(() => {
    const p = selectedPeerEntity.value; if (!p || !p.subnetId) return false
    return store.links.some(l => l.kind === 'membership' && l.fromId === p.id && l.toId === p.subnetId)
  })
  async function connectPeerToItsSubnet() {
    const p = selectedPeerEntity.value
    if (!p || !p.subnetId) return
    const cidr = selectedPeerSubnetCidr.value
    if (!cidr) return
    connectLoading.value = true
    try {
      await backend.connectPeerToSubnet(p.name, cidr)
    } finally { connectLoading.value = false }
  }
  async function disconnectPeerFromItsSubnet() {
    const p = selectedPeerEntity.value
    if (!p || !p.subnetId) return
    const cidr = selectedPeerSubnetCidr.value
    if (!cidr) return
    connectLoading.value = true
    try {
      await backend.disconnectPeerFromSubnet(p.name, cidr)
    } finally { connectLoading.value = false }
  }
  function peerName(id:string){ const p = store.peers.find(pp=>pp.id===id); return p? p.name : '' }

  // Subnet creation dialog state
  const subnetDialog = reactive({ open:false, subnet:'', name:'', description:'', x:0, y:0, loading:false, error:'', success:false })
  const canCreateSubnet = computed(() => !!subnetDialog.subnet && !!subnetDialog.name && !subnetDialog.loading)
  function openSubnetDialog(x:number,y:number){
    subnetDialog.open = true
    subnetDialog.subnet=''
    subnetDialog.name=''
    subnetDialog.description=''
    subnetDialog.x = Math.round(x)
    subnetDialog.y = Math.round(y)
    subnetDialog.loading=false
    subnetDialog.error=''
    subnetDialog.success=false
    // Lock ghost at click position
    ghostSubnet.active = true
    ghostSubnet.locked = true
    ghostSubnet.x = x
    ghostSubnet.y = y
    draw()
  }
  function closeSubnetDialog(){
    subnetDialog.open=false
    ghostSubnet.locked = false
    ghostSubnet.active = false
  store.tool = 'select'
    draw()
  }
  async function submitSubnet(){
    if (!canCreateSubnet.value) return
    subnetDialog.loading=true; subnetDialog.error=''; subnetDialog.success=false
    try {
      const ok = await backend.createSubnet(subnetDialog.subnet.trim(), subnetDialog.name.trim(), subnetDialog.description.trim(), subnetDialog.x, subnetDialog.y)
      if (!ok){ subnetDialog.error = backend.lastError || 'Failed to create subnet' }
      else {
        subnetDialog.success=true; await backend.fetchTopology(true)
        // Place newly created subnet at chosen coordinates (after topology merge assigns default layout)
        const newId = 'subnet_' + subnetDialog.subnet.trim()
        const created = store.subnets.find(s=>s.id===newId)
        if (created) { created.x = subnetDialog.x; created.y = subnetDialog.y }
        draw()
      }
    } catch(e:any){ subnetDialog.error = e?.message || 'Unexpected error' }
    finally { subnetDialog.loading=false }
  }

  // Ghost subnet state & drawing
  const ghostSubnet = reactive({ active:false, x:0, y:0, width:420, height:260, locked:false })
  function drawGhostSubnet(ctx: CanvasRenderingContext2D){
    if (!(ghostSubnet.active && store.tool==='add-subnet')) return
    const { x, y } = toScreen(ghostSubnet.x, ghostSubnet.y)
    const w = ghostSubnet.width * store.zoom
    const h = ghostSubnet.height * store.zoom
    ctx.save()
    ctx.globalAlpha = 0.18
    ctx.fillStyle = '#4CAF50'
    ctx.beginPath(); ctx.rect(x - w/2, y - h/2, w, h); ctx.fill()
    ctx.globalAlpha = 1
    ctx.setLineDash([6,4])
    ctx.strokeStyle = '#4CAF50'; ctx.lineWidth = 2
    ctx.strokeRect(x - w/2, y - h/2, w, h)
    // Plus sign under rectangle
    const plusY = y + h/2 + 14*store.zoom
    const plusX = x
    ctx.fillStyle = '#4CAF50'; ctx.font = `${22*store.zoom}px ui-sans-serif`; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText('+', plusX, plusY)
    ctx.restore()
  }
  watch(() => store.tool, (t) => {
    if (t!=='add-subnet') { ghostSubnet.active=false; ghostSubnet.locked=false }
    if (t!=='connect' && connectState.active) { resetConnection() }
    if (t!=='connect') { connectCursor.active = false }
    draw()
  })

  function drawGhostConnectIcon(ctx: CanvasRenderingContext2D){
    if (!(store.tool==='connect' && !connectState.active && connectCursor.active)) return
    const S = toScreen(connectCursor.x, connectCursor.y)
    ctx.save()
    const r = 20 * store.zoom
    // Outer soft halo
    ctx.globalAlpha = 0.16
    ctx.fillStyle = '#4D6DFF'
    ctx.beginPath(); ctx.arc(S.x, S.y, r, 0, Math.PI*2); ctx.fill()
    ctx.globalAlpha = 1
    ctx.strokeStyle = '#4D6DFF'; ctx.setLineDash([5,4]); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(S.x, S.y, r-1*store.zoom, 0, Math.PI*2); ctx.stroke(); ctx.setLineDash([])
    // Chain links (two interlocked paths)
    const linkW = 18 * store.zoom
    const linkH = 10 * store.zoom
    const gap = 4 * store.zoom
    ctx.lineWidth = 2.2 * store.zoom
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    // Left link
    ctx.strokeStyle = '#FFFFFF'
    ctx.beginPath()
    ctx.ellipse(S.x - gap/2, S.y, linkW/2, linkH/2, Math.PI/8, 0, Math.PI*2)
    ctx.stroke()
    // Right link
    ctx.beginPath()
    ctx.ellipse(S.x + gap/2, S.y, linkW/2, linkH/2, -Math.PI/8, 0, Math.PI*2)
    ctx.stroke()
    // Overlap highlight
    ctx.strokeStyle = '#86A1FF'
    ctx.beginPath()
    ctx.moveTo(S.x - gap*0.15, S.y - linkH*0.55)
    ctx.lineTo(S.x + gap*0.15, S.y - linkH*0.55)
    ctx.moveTo(S.x - gap*0.15, S.y + linkH*0.55)
    ctx.lineTo(S.x + gap*0.15, S.y + linkH*0.55)
    ctx.stroke()
    ctx.restore()
  }

  // Accept / create link from dialog
  function finalizeConnection() {
    if (!(connectState.fromPeerId && connectState.pendingPeerId)) return
    const id = 'link_' + Math.random().toString(36).slice(2,9)
    if (connectState.selectedMode === 'p2p') {
      store.links.push({ id, fromId: connectState.fromPeerId, toId: connectState.pendingPeerId, kind: 'p2p' })
    } else if (connectState.selectedMode === 'service' && connectState.selectedService) {
      store.links.push({ id, fromId: connectState.fromPeerId, toId: connectState.pendingPeerId, kind: 'service', serviceName: connectState.selectedService })
    }
    resetConnection()
    draw()
  }
  function resetConnection() {
    connectState.active = false
    connectState.fromPeerId=''
    connectState.pendingPeerId=''
    connectState.ghostTo=null
    connectState.dialogOpen=false
    connectState.targetPeer=null
    connectState.services=[]
    connectState.selectedService=''
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