<template>
  <v-dialog v-model="open" max-width="420">
    <v-card>
      <v-card-title class="text-subtitle-1">
        <v-icon class="me-2" icon="mdi-link-variant-off" />
        Cut Link
      </v-card-title>
      <v-card-text>
        <template v-if="links.length > 0">
          <div class="text-body-2 mb-2">
            Links between <strong>{{ entityName(links[0].fromId) }}</strong> and <strong>{{ entityName(links[0].toId) }}</strong>
          </div>
          <v-select
            v-model="selectedId"
            density="comfortable"
            :disabled="links.length===1"
            item-value="value"
            :items="selectItems"
            label="Link"
            variant="outlined"
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props" density="compact" :title="item.raw.label">
                <template #prepend>
                  <div class="d-flex align-center ga-1">
                    <v-icon
                      :color="
                        item.raw.kind==='p2p' ? 'success' :
                        item.raw.kind==='service' ? 'primary' :
                        item.raw.kind==='admin-p2p' ? 'purple' :
                        item.raw.kind==='admin-subnet-subnet' ? 'purple' :
                        item.raw.kind==='admin-peer-subnet' ? 'purple' :
                        item.raw.kind==='subnet-subnet' ? 'success' :
                        'secondary'
                      "
                      :icon="
                        item.raw.kind==='p2p' ? 'mdi-account' :
                        item.raw.kind==='service' ? 'mdi-server' :
                        item.raw.kind==='admin-p2p' ? 'mdi-shield-account' :
                        item.raw.kind==='admin-subnet-subnet' ? 'mdi-shield' :
                        item.raw.kind==='admin-peer-subnet' ? 'mdi-shield-account' :
                        item.raw.kind==='subnet-subnet' ? 'mdi-lan' :
                        'mdi-account-multiple-outline'
                      "
                      size="16"
                    />
                    <v-icon v-if="item.raw.kind==='p2p' && problematicLinkIds.has(item.raw.id)" color="warning" icon="mdi-alert-circle" size="16" />
                  </div>
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <div class="d-flex align-center ga-1">
                <v-icon
                  :color="
                    item.raw.kind==='p2p' ? 'success' :
                    item.raw.kind==='service' ? 'primary' :
                    item.raw.kind==='admin-p2p' ? 'purple' :
                    item.raw.kind==='admin-subnet-subnet' ? 'purple' :
                    item.raw.kind==='admin-peer-subnet' ? 'purple' :
                    item.raw.kind==='subnet-subnet' ? 'primary' :
                    'secondary'
                  "
                  :icon="
                    item.raw.kind==='p2p' ? 'mdi-account' :
                    item.raw.kind==='service' ? 'mdi-server' :
                    item.raw.kind==='admin-p2p' ? 'mdi-shield-account' :
                    item.raw.kind==='admin-subnet-subnet' ? 'mdi-shield' :
                    item.raw.kind==='admin-peer-subnet' ? 'mdi-shield-account' :
                    item.raw.kind==='subnet-subnet' ? 'mdi-lan' :
                    'mdi-account-multiple-outline'
                  "
                  size="16"
                />
                <v-icon v-if="item.raw.kind==='p2p' && problematicLinkIds.has(item.raw.id)" color="warning" icon="mdi-alert-circle" size="16" />
                <span>{{ item.raw.label }}</span>
              </div>
            </template>
          </v-select>
          <v-alert
            v-if="links.length>1"
            class="mt-2"
            density="compact"
            text="Multiple overlapping links."
            type="info"
          />
        </template>
        <template v-else>
          <v-alert density="comfortable" text="No links found." type="info" />
        </template>
      </v-card-text>
      <v-card-actions class="justify-end ga-2">
        <v-btn variant="text" @click="cancel">Cancel</v-btn>
        <v-btn color="error" :disabled="!selectedId" @click="openConfirmDialog">Delete</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <ConfirmCutLinkDialog
    v-model="confirmOpen"
    :color="currentLink ? (
      currentLink.kind==='p2p' ? 'success' :
      currentLink.kind==='admin-p2p' ? 'purple' :
      currentLink.kind==='admin-subnet-subnet' ? 'purple' :
      currentLink.kind==='admin-peer-subnet' ? 'purple' :
      currentLink.kind==='membership' ? 'secondary' :
      currentLink.kind==='subnet-subnet' ? 'success' :
      'primary') : 'primary'"
    :link="currentLink"
    :loading="confirmLoading"
    :mode="currentLink ? (
      currentLink.kind==='p2p' ? 'p2p' :
      currentLink.kind==='admin-p2p' ? 'admin-p2p' :
      currentLink.kind==='admin-subnet-subnet' ? 'admin-subnet-subnet' :
      currentLink.kind==='admin-peer-subnet' ? 'admin-peer-subnet' :
      currentLink.kind==='membership' ? 'membership' :
      currentLink.kind==='subnet-subnet' ? 'subnet-subnet' :
      currentLink.kind==='subnet-service' ? 'subnet-service' :
      'service-generic') : ''"
    :peer-a="currentLink ? entityName(currentLink.fromId) : ''"
    :peer-b="currentLink ? entityName(currentLink.toId) : ''"
    :problematic="currentLink?.kind==='p2p' && problematicLinkIds.has(currentLink.id)"
    :service-name="currentLink?.serviceName"
    @confirm="performDelete"
  />
</template>

<script setup lang="ts">
  import type { Link } from '@/types/network'
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useBackendInteractionStore } from '@/stores/backendInteraction'
  import { useNetworkStore } from '@/stores/network'
  import ConfirmCutLinkDialog from './ConfirmCutLinkDialog.vue'

  const store = useNetworkStore()
  const backend = useBackendInteractionStore()
  const open = ref(false)
  const links = ref<Link[]>([])
  const selectedId = ref<string>('')
  // Secondary confirmation dialog state
  const confirmOpen = ref(false)
  const confirmLoading = ref(false)

  const currentLink = computed(() => links.value.find(l => l.id === selectedId.value) || null)
  let pairKey = ''

  function entityName (id: string) {
    const p = store.peers.find(p => p.id === id)
    if (p) return p.name
    const s = store.subnets.find(s => s.id === id)
    if (s) return s.name
    return id
  }

  // Determine problematic p2p links (pair has at least one service link and a host peer)
  const problematicLinkIds = computed(() => {
    const set = new Set<string>()
    if (links.value.length === 0) return set
    const serviceLinks = links.value.filter(l => l.kind === 'service')
    if (serviceLinks.length === 0) return set // no service link => nothing problematic
    // Identify host peer id from a service link (fromId per topology builder)
    const hostIds = new Set(serviceLinks.map(l => l.fromId))
    // A p2p link is problematic if one side is a host present in hostIds
    for (const l of links.value) {
      if (l.kind === 'p2p' && (hostIds.has(l.fromId) || hostIds.has(l.toId))) {
        set.add(l.id)
      }
    }
    return set
  })

  const selectItems = computed(() => links.value.map(l => {
    const from = entityName(l.fromId)
    const to = entityName(l.toId)
    if (l.kind === 'p2p') {
      return { value: l.id, kind: l.kind, label: `${from} ↔ ${to}`, id: l.id }
    }
    if (l.kind === 'admin-p2p') {
      return { value: l.id, kind: l.kind, label: `${from} → ${to} (admin)`, id: l.id }
    }
    if (l.kind === 'service') {
      const fromPeer = store.peers.find(p => p.id === l.fromId)
      const svcRec = fromPeer?.services?.[l.serviceName || '']
      const port = svcRec?.port
      const svcName = l.serviceName || svcRec?.name || 'service'
      const portStr = port === undefined ? '' : `:${port}`
      return { value: l.id, kind: l.kind, label: `${from} -> ${to}${portStr} (${svcName})`, id: l.id }
    }
    if (l.kind === 'subnet-subnet') {
      return { value: l.id, kind: l.kind, label: `${from} ↔ ${to} (subnet link)`, id: l.id }
    }
    if (l.kind === 'admin-subnet-subnet') {
      return { value: l.id, kind: l.kind, label: `${from} → ${to}`, id: l.id }
    }
    if (l.kind === 'admin-peer-subnet') {
      return { value: l.id, kind: l.kind, label: `${from} → ${to}`, id: l.id }
    }
    if (l.kind === 'subnet-service') {
      const host = store.peers.find(p => p.id === l.fromId)
      const svcName = l.serviceName || ''
      const label = `${host?.name || from} → ${to} (${svcName || 'service'})`
      return { value: l.id, kind: l.kind, label, id: l.id }
    }
    if (l.kind === 'membership') {
      return { value: l.id, kind: l.kind, label: `${from} ↔ ${to}`, id: l.id }
    }
    return { value: l.id, kind: l.kind, label: `${from} -> ${to}`, id: l.id }
  }))

  function show (payload: {
    pairKey: string
    links: Link[]
  }) {
    pairKey = payload.pairKey
    links.value = payload.links
    selectedId.value = payload.links[0]?.id || ''
    open.value = true
  }

  function cancel () {
    open.value = false
    store.tool = 'select'
  }
  function openConfirmDialog () {
    if (!selectedId.value)
      return
    confirmOpen.value = true
  }
  function closeConfirm () {
    if (confirmLoading.value)
      return
    confirmOpen.value = false
  }
  async function performDelete () {
    if (!currentLink.value) {
      confirmOpen.value = false
      return
    }
    confirmLoading.value = true
    try {
      const link = currentLink.value
      switch (link.kind) {
        case 'p2p': {
          const a = store.peers.find(p => p.id === link.fromId)
          const b = store.peers.find(p => p.id === link.toId)
          if (a && b) await backend.disconnectPeers(a.name, b.name)
        }
        case 'admin-p2p': {
          const admin = store.peers.find(p => p.id === link.fromId)
          const regular = store.peers.find(p => p.id === link.toId)
          if (admin && regular) await backend.disconnectAdminPeerFromPeer(admin.name, regular.name)
        }
        case 'service': {
          const consumer = store.peers.find(p => p.id === link.toId)
          const svcName = link.serviceName || ''
          if (consumer && svcName) await backend.disconnectPeerFromService(consumer.name, svcName)
        }
        case 'membership': {
          const peer = store.peers.find(p => p.id === link.fromId) || store.peers.find(p => p.id === link.toId)
          if (!peer) return
          const subnetId = peer.id === link.fromId ? link.toId : link.fromId
          const subnet = store.subnets.find(s => s.id === subnetId)
          if (!subnet) return
          await backend.disconnectPeerFromSubnet(peer.name, subnet.cidr)
        }
        case 'subnet-subnet': {
          const a = store.subnets.find(s => s.id === link.fromId) || store.subnets.find(s => s.id === link.toId)
          const b = store.subnets.find(s => s.id === link.toId) || store.subnets.find(s => s.id === link.fromId)
          if (a && b) await backend.disconnectSubnetFromSubnet(a.cidr, b.cidr)
        }
        case 'admin-subnet-subnet': {
          // Directional: fromId is admin subnet source
          const adminSubnet = store.subnets.find(s => s.id === link.fromId)
          const targetSubnet = store.subnets.find(s => s.id === link.toId)
          if (adminSubnet && targetSubnet) await backend.disconnectAdminSubnetFromSubnet(adminSubnet.cidr, targetSubnet.cidr)
        }
        case 'subnet-service': {
          const subnet = store.subnets.find(s => s.id === link.toId) || store.subnets.find(s => s.id === link.fromId)
          const svcName = link.serviceName || ''
          if (subnet && svcName) await backend.disconnectSubnetFromService(subnet.cidr, svcName)
        }
        case 'admin-peer-subnet': {
          const adminPeer = store.peers.find(p => p.id === link.fromId)
          const subnet = store.subnets.find(s => s.id === link.toId)
          if (adminPeer && subnet) await backend.disconnectAdminPeerFromSubnet(adminPeer.name, subnet.cidr)
        }
      }
    } catch (e) {
      /* error handled in backend store */
    } finally {
      confirmLoading.value = false
      confirmOpen.value = false
      open.value = false
      store.tool = 'select'
    }
  }
  function handleRequestCut (e: any) {
    const detail = e.detail || {}
    show(detail)
  }
  onMounted(() => {
    window.addEventListener('request-cut-link', handleRequestCut)
  })
  onBeforeUnmount(() => {
    window.removeEventListener('request-cut-link', handleRequestCut)
  })
  // When dialog closes due to backdrop or ESC, revert to select tool
  watch(open, (now, prev) => {
    if (prev && !now) {
      store.tool = 'select'
    }
  })
  defineExpose({ show })
</script>

<style scoped>
</style>
