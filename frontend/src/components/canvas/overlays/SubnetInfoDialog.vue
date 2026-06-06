<template>
  <v-dialog v-model="open" max-width="520">
    <v-card v-if="subnet">
      <v-card-title class="d-flex justify-space-between align-center">
        <span><v-icon icon="mdi-subnet" size="24" />{{ subnet.name }} ({{
          subnet.cidr
        }})</span>
        <v-btn icon="mdi-close" variant="text" @click="open = false" />
      </v-card-title>
      <v-divider />
      <v-card-text class="text-body-2">
        <div class="d-flex flex-column ga-2">
          <div v-if="subnet.description">{{ subnet.description }}</div>
          <!-- Color editing section -->
          <div v-if="subnet" class="mt-1 d-flex flex-column ga-2">
            <div
              class="text-medium-emphasis"
              style="font-size: 12px; letter-spacing: 0.5px"
            >
              Appearance
            </div>
            <div class="d-flex align-center flex-wrap ga-3">
              <div class="d-flex align-center ga-2">
                <input
                  v-model="colorPicker"
                  style="
                    width: 42px;
                    height: 42px;
                    padding: 0;
                    border: none;
                    background: transparent;
                    cursor: pointer;
                  "
                  type="color"
                  @input="applyColor"
                >
              </div>
              <v-slider
                v-model="alpha"
                density="compact"
                hide-details
                max="100"
                min="0"
                step="1"
                style="max-width: 180px"
                @end="applyColor"
              >
                <template #prepend>
                  <span
                    style="font-size: 12px; width: 34px; display: inline-block"
                  >Alpha</span>
                </template>
              </v-slider>
              <v-text-field
                v-model="hexFull"
                density="compact"
                hide-details
                label="Hex"
                style="max-width: 160px"
                @change="onHexFullChange"
                @keyup.enter="onHexFullChange"
              />
              <v-btn
                prepend-icon="mdi-autorenew"
                size="x-small"
                variant="tonal"
                @click="randomizeColor"
              >Random</v-btn>
            </div>
            <div class="text-caption" style="opacity: 0.7">
              You can click on the color box to open the color picker.
            </div>
          </div>
          <div class="mt-2 flex-grow-1">
            <v-expansion-panels class="w-100" multiple>
              <v-expansion-panel
                v-if="peersInside.length > 0"
                class="d-flex flex-column"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center">
                    <v-icon
                      class="text-success"
                      icon="mdi-account-multiple"
                      size="18"
                    />
                  </div>
                  Peers inside ({{ peersInside.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text class="pt-0">
                  <div v-if="peersInside.length === 0" class="text-medium-emphasis">
                    No peers
                  </div>
                  <v-list v-else class="py-0" density="compact" nav>
                    <v-list-item
                      v-for="(peer, key) in peersInside"
                      :key="key"
                      class="w-100"
                      @click="$emit('show-peer', peer.id)"
                    >
                      <v-list-item-title>
                        <v-icon
                          class="text-primary"
                          icon="mdi-account"
                          size="18"
                        />{{ peer.name || key }}
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        ip: {{ peer.ip }}
                        <span
                          v-if="
                            Date.now() / 1000 - (peer as any).lastHandshake <
                              300
                          "
                        >
                          | Connected
                          <v-icon
                            class="text-success"
                            icon="mdi-check"
                            size="18"
                          />
                        </span>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                  <div class="d-flex justify-end mt-2">
                    <v-btn
                      color="primary"
                      prepend-icon="mdi-plus"
                      size="small"
                      variant="tonal"
                      @click="$emit('create-peer', subnet.id)"
                    >Create Peer</v-btn>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
              <v-expansion-panel
                v-if="linksToSubnets.length > 0"
                class="d-flex flex-column"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center">
                    <v-icon
                      class="text-info"
                      icon="mdi-link-variant"
                      size="18"
                    />
                  </div>
                  Links to Subnets ({{ linksToSubnets.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text class="pt-0">
                  <div
                    v-if="linksToSubnets.length === 0"
                    class="text-medium-emphasis"
                  >
                    No links
                  </div>
                  <v-list v-else class="py-0" density="compact" nav>
                    <v-list-item
                      v-for="(link, key) in linksToSubnets"
                      :key="key"
                      class="w-100"
                    >
                      <v-list-item-title
                        style="cursor: pointer"
                        @click="
                          $emit(
                            'show-subnet',
                            link.fromId === subnet.id ? link.toId : link.fromId,
                          )
                        "
                      >
                        <v-icon
                          class="text-primary"
                          icon="mdi-lan"
                          size="18"
                        />{{
                          link.fromId === subnet.id
                            ? store.subnets.find((s) => s.id === link.toId)
                              ?.name
                            : store.subnets.find((s) => s.id === link.fromId)
                              ?.name
                        }}
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        {{
                          link.fromId === subnet.id
                            ? store.subnets.find((s) => s.id === link.toId)
                              ?.cidr
                            : store.subnets.find((s) => s.id === link.fromId)
                              ?.cidr
                        }}
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
              <v-expansion-panel
                v-if="servicesLinked.length > 0"
                class="d-flex flex-column"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center">
                    <v-icon class="text-info" icon="mdi-server" size="18" />
                  </div>
                  Services linked ({{ servicesLinked.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text class="pt-0">
                  <div
                    v-if="servicesLinked.length === 0"
                    class="text-medium-emphasis"
                  >
                    No services
                  </div>
                  <v-list v-else class="py-0" density="compact" nav>
                    <v-list-item
                      v-for="(svc, key) in servicesLinked"
                      :key="key"
                      class="w-100"
                    >
                      <v-list-item-title
                        style="cursor: pointer"
                        @click="$emit('show-peer', svc.hostId)"
                      >
                        <v-icon
                          class="text-primary"
                          icon="mdi-server"
                          size="18"
                        />{{ svc.serviceName
                        }}<span v-if="svc.port"> : {{ svc.port }}</span><span v-if="svc.protocol"> ({{ svc.protocol }})</span>
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        Host: {{ svc.hostName }}
                        <span v-if="svc.hostIp">({{ svc.hostIp }})</span>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
              <v-expansion-panel
                v-if="guestPeers.length > 0"
                class="d-flex flex-column"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center">
                    <v-icon class="text-green" icon="mdi-account" size="18" />
                  </div>
                  Guest peers ({{ guestPeers.length }})
                </v-expansion-panel-title>
                <v-expansion-panel-text class="pt-0">
                  <div v-if="guestPeers.length === 0" class="text-medium-emphasis">
                    No guests
                  </div>
                  <v-list v-else class="py-0" density="compact" nav>
                    <v-list-item
                      v-for="(peer, key) in guestPeers"
                      :key="key"
                      class="w-100"
                      @click="$emit('show-peer', peer.id)"
                    >
                      <v-list-item-title style="cursor: pointer">
                        <v-icon
                          class="text-green"
                          icon="mdi-account"
                          size="18"
                        />{{ peer.name || peer.id }}
                      </v-list-item-title>
                      <v-list-item-subtitle>
                        ip: {{ peer.ip }}
                        <span v-if="peer.subnetId" class="ms-2">
                          • home:
                          {{
                            store.subnets.find((s) => s.id === peer.subnetId)
                              ?.name ||
                              store.subnets.find((s) => s.id === peer.subnetId)
                                ?.cidr
                          }}
                        </span>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn
          color="primary"
          variant="elevated"
          @click="open = false"
        >Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useNetworkStore } from '@/stores/network'

  const emits = defineEmits<{
    (e: 'create-peer', subnetId: string): void
    (e: 'show-peer', peerId: string): void
    (e: 'show-subnet', subnetId: string): void
  }>()

  const store = useNetworkStore()
  const targetSubnetId = ref<string | null>(null)
  const model = defineModel<boolean>({ default: false })
  const open = computed({
    get: () => model.value,
    set: v => (model.value = v),
  })
  const subnet = computed(() =>
    store.subnets.find(s => s.id === targetSubnetId.value),
  )
  const peersInside = computed(() =>
    store.peers.filter(p => p.subnetId === targetSubnetId.value),
  )
  const linksToSubnets = computed(() =>
    store.links.filter(
      l =>
        (l.fromId === targetSubnetId.value && l.kind === 'subnet-subnet')
        || (l.toId === targetSubnetId.value && l.kind === 'subnet-subnet'),
    ),
  )
  const linksToServices = computed(() =>
    store.links.filter(
      l =>
        (l.fromId === targetSubnetId.value && l.kind === 'subnet-service')
        || (l.toId === targetSubnetId.value && l.kind === 'subnet-service'),
    ),
  )
  // Build a services list for this subnet using subnet-service links. Each entry shows service name/port/protocol and host peer info.
  const servicesLinked = computed(() => {
    const out: Array<{
      serviceName: string
      port?: number
      protocol?: string
      hostId: string
      hostName: string
      hostIp?: string
    }> = []
    const rel = linksToServices.value
    for (const link of rel) {
      // Link shape: fromId is host peer id, toId is subnet id
      const host = store.peers.find(p => p.id === link.fromId)
      const subnetId = link.toId
      const svcName = (link as any).serviceName as string | undefined
      if (!host || !svcName) continue
      const svcDef = (host.services || {})[svcName]
      out.push({
        serviceName: svcName,
        port: svcDef?.port,
        protocol: (svcDef as any)?.protocol,
        hostId: host.id,
        hostName: host.name,
        hostIp: host.ip,
      })
    }
    return out
  })
  const linksToPeers = computed(() =>
    store.links.filter(
      l =>
        (l.fromId === targetSubnetId.value && l.kind === 'membership')
        || (l.toId === targetSubnetId.value && l.kind === 'membership'),
    ),
  )

  // Peers that are guests of this subnet via membership links (exclude peers whose home subnet is this subnet)
  const guestPeers = computed(() => {
    const sid = targetSubnetId.value
    if (!sid) return [] as typeof store.peers
    const memberPeerIds = new Set<string>()
    for (const l of store.links) {
      if ((l as any).kind !== 'membership') continue
      // membership links are modeled as fromId=peerId toId=subnetId
      if (l.toId === sid) memberPeerIds.add(l.fromId)
    }
    return store.peers.filter(
      p => memberPeerIds.has(p.id) && p.subnetId !== sid,
    )
  })

  function show (id: string) {
    targetSubnetId.value = id
    open.value = true
  }

  // Expose API to parent
  defineExpose({ show })

  // ---------------- Color Editing State ----------------
  const colorPicker = ref<string>('#00ff00') // #RRGGBB
  const alpha = ref<number>(90) // 0..100
  const hexFull = ref<string>('#00ff00E5') // #RRGGBBAA
  let syncing = false

  function rgbaNumberFromParts (r: number, g: number, b: number, aByte: number) {
    return (
      (((r & 0xff) << 24)
        | ((g & 0xff) << 16)
        | ((b & 0xff) << 8)
        | (aByte & 0xff))
      >>> 0
    )
  }
  function partsFromRgbaNumber (raw: number) {
    return {
      r: (raw >> 24) & 0xff,
      g: (raw >> 16) & 0xff,
      b: (raw >> 8) & 0xff,
      a: raw & 0xff,
    }
  }
  function syncFromSubnet () {
    const s = subnet.value as any
    if (!s) return
    let raw = s.rgba
    if (typeof raw !== 'number') raw = 0x00_ff_00_e5
    const { r, g, b, a } = partsFromRgbaNumber(raw)
    syncing = true
    colorPicker.value
      = '#'
        + [r, g, b]
          .map(x => x.toString(16).padStart(2, '0'))
          .join('')
          .toLowerCase()
    alpha.value = Math.round((a / 255) * 100)
    hexFull.value
      = '#'
        + [r, g, b, a]
          .map(x => x.toString(16).padStart(2, '0'))
          .join('')
          .toUpperCase()
    syncing = false
  }

  watch(
    subnet,
    () => {
      if (open.value) syncFromSubnet()
    },
    { immediate: true },
  )
  watch(open, v => {
    if (v) syncFromSubnet()
  })

  function applyColor () {
    if (syncing) return
    const s = subnet.value as any
    if (!s) return
    const rgbHex = colorPicker.value.replace('#', '').trim()
    if (!/^([0-9a-fA-F]{6})$/.test(rgbHex)) return
    const r = Number.parseInt(rgbHex.slice(0, 2), 16)
    const g = Number.parseInt(rgbHex.slice(2, 4), 16)
    const b = Number.parseInt(rgbHex.slice(4, 6), 16)
    const aByte = Math.min(
      255,
      Math.max(0, Math.round((alpha.value / 100) * 255)),
    )
    const rgba = rgbaNumberFromParts(r, g, b, aByte)
    if (s.rgba !== rgba) s.rgba = rgba
    hexFull.value
      = '#'
        + [r, g, b, aByte]
          .map(x => x.toString(16).padStart(2, '0'))
          .join('')
          .toUpperCase()
  }

  function onHexFullChange () {
    const h = hexFull.value.replace('#', '').trim()
    if (!/^([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(h)) {
      syncFromSubnet()
      return
    }
    const r = Number.parseInt(h.slice(0, 2), 16)
    const g = Number.parseInt(h.slice(2, 4), 16)
    const b = Number.parseInt(h.slice(4, 6), 16)
    const aByte
      = h.length === 8
        ? Number.parseInt(h.slice(6, 8), 16)
        : Math.round((alpha.value / 100) * 255)
    alpha.value = Math.round((aByte / 255) * 100)
    colorPicker.value = '#' + h.slice(0, 6).toLowerCase()
    const s = subnet.value as any
    if (s) s.rgba = rgbaNumberFromParts(r, g, b, aByte)
    hexFull.value
      = '#'
        + [r, g, b, aByte]
          .map(x => x.toString(16).padStart(2, '0'))
          .join('')
          .toUpperCase()
  }

  function randomizeColor () {
    const r = Math.floor(Math.random() * 256)
    const g = Math.floor(Math.random() * 256)
    const b = Math.floor(Math.random() * 256)
    colorPicker.value
      = '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('')
    applyColor()
  }

  watch(alpha, () => applyColor())
</script>
