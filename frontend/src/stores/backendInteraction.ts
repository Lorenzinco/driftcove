import { defineStore } from 'pinia'
import {
  configureUnauthorizedHandler,
  getClient,
  setRuntimeApiToken,
} from '@/services/api/client'
import {
  adaptBackendTopology,
  buildCurrentTopologyPayload as buildTopologyPayload,
} from '@/services/topology/adapter'
import {
  buildCoordinateSignature as serializeCoordinateSignature,
  buildTopologySignature as serializeTopologySignature,
} from '@/services/topology/signatures'
import { useNetworkStore } from '@/stores/network'

export const useBackendInteractionStore = defineStore('backendInteraction', {
  state: () => ({
    loading: false,
    lastError: '' as string | null,
    topology: null as { peers: any[], subnets: any[], links: any[] } | null,
    lastFetchedAt: 0,
    pollingId: null as number | null,
    pollingIntervalMs: 5000,
    coordPushId: null as number | null,
    coordPushIntervalMs: 10_000,
    pushing: false,
    hasFetchedOnce: false,
    lastSentCoordsSig: null as string | null,
    subnetDetails: {} as Record<
      string,
      { name: string, description?: string, fetchedAt: number }
    >,
    // Baseline topology signature (set after successful fetch)
    lastFetchedTopologySig: null as string | null,
    // API token (memory-only, not persisted across refresh)
    apiToken: '',
  }),
  actions: {
    setApiToken (token: string) {
      this.apiToken = token || ''
      setRuntimeApiToken(this.apiToken)
    },
    // Build a stable signature of current coordinates/sizes/colors to detect changes
    buildCoordinateSignature (): string {
      const net = useNetworkStore()
      return serializeCoordinateSignature(net.subnets, net.peers)
    },

    // Build a deterministic structural topology signature used to detect unsaved changes
    buildTopologySignature (): string {
      const net = useNetworkStore()
      return serializeTopologySignature(net.subnets, net.peers, net.links)
    },

    // Push current coordinates/sizes/colors to backend using the update endpoint (non-destructive)
    async pushCoordinatesOnce () {
      if (this.pushing || !this.hasFetchedOnce) {
        return
      }
      const sig = this.buildCoordinateSignature()
      if (this.lastSentCoordsSig && sig === this.lastSentCoordsSig) {
        return
      }
      this.pushing = true
      try {
        const payload = this.buildCurrentTopologyPayload()
        await getClient().post('/api/network/update_coordinates', payload)
        this.lastSentCoordsSig = sig
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to push coordinates'
      } finally {
        this.pushing = false
      }
    },

    startCoordinatePushing (intervalMs = 1000) {
      if (this.coordPushId) {
        return
      }
      this.coordPushIntervalMs = intervalMs
      // Immediate push will happen only if hasFetchedOnce is true
      this.pushCoordinatesOnce()
      this.coordPushId = window.setInterval(
        () => this.pushCoordinatesOnce(),
        intervalMs,
      )
    },

    stopCoordinatePushing () {
      if (this.coordPushId) {
        clearInterval(this.coordPushId)
        this.coordPushId = null
      }
    },
    // Fetch and adapt normalized topology structure from backend
    async fetchTopology (force = false) {
      if (this.loading) {
        return
      }
      this.loading = true
      this.lastError = null
      try {
        const { data } = await getClient().get<any>('/api/network/topology')
        const topology = adaptBackendTopology(data)

        this.topology = {
          peers: topology.peers,
          subnets: topology.subnets,
          links: topology.links.map(link => ({
            id: link.id,
            fromId: link.fromId,
            toId: link.toId,
            kind: link.kind,
            serviceName: link.serviceName,
          })),
        }

        useNetworkStore().applyBackendTopology(topology)
        window.dispatchEvent(new CustomEvent('topology-updated'))
        this.lastFetchedAt = Date.now()
        this.lastFetchedTopologySig = this.buildTopologySignature()

        if (!this.hasFetchedOnce) {
          this.hasFetchedOnce = true
          if (!this.coordPushId) {
            this.startCoordinatePushing(this.pollingIntervalMs)
          }
        }
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to fetch topology'
      } finally {
        this.loading = false
      }
    },

    // Upload current in-memory topology (already converted by caller)
    async uploadTopology (payload: any) {
      try {
        this.lastError = null
        await getClient().post('/api/network/topology', payload)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to upload topology'
        return false
      }
    },

    // Build payload matching backend Topology model
    buildCurrentTopologyPayload () {
      return buildTopologyPayload(useNetworkStore())
    },
    // Create subnet helper (legacy endpoints retained if still active backend-side)
    async createSubnet (
      subnet: string,
      name: string,
      description: string,
      x: number,
      y: number,
      width: number,
      height: number,
      rgba: number,
    ) {
      try {
        this.lastError = null
        await getClient().post('/api/subnet/create', {
          subnet,
          name,
          description,
          x,
          y,
          width,
          height,
          rgba,
        })
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to create subnet'
        return false
      }
    },
    async connectPeerToSubnet (username: string, subnetCidr: string) {
      try {
        this.lastError = null
        await getClient().post('/api/subnet/connect', null, {
          params: { username, subnet: subnetCidr },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect peer to subnet'
        return false
      }
    },
    async connectAdminPeerToSubnet (adminUsername: string, subnetCidr: string) {
      try {
        this.lastError = null
        await getClient().post('/api/subnet/admin/connect', null, {
          params: { admin_username: adminUsername, subnet: subnetCidr },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect admin peer to subnet'
        return false
      }
    },
    async disconnectPeerFromSubnet (username: string, subnetCidr: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/subnet/disconnect', {
          params: { username, subnet: subnetCidr },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to disconnect peer from subnet'
        return false
      }
    },
    async disconnectAdminPeerFromSubnet (
      adminUsername: string,
      subnetCidr: string,
    ) {
      try {
        this.lastError = null
        await getClient().delete('/api/subnet/admin/disconnect', {
          params: { admin_username: adminUsername, subnet: subnetCidr },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError
          = error?.message || 'Failed to disconnect admin peer from subnet'
        return false
      }
    },
    async connectPeers (peer1: string, peer2: string) {
      try {
        this.lastError = null
        await getClient().post('/api/peer/connect', null, {
          params: { peer1_username: peer1, peer2_username: peer2 },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect peers'
        return false
      }
    },
    async disconnectPeers (peer1: string, peer2: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/peer/disconnect', {
          params: { peer1_username: peer1, peer2_username: peer2 },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to disconnect peers'
        return false
      }
    },
    async connectAdminPeerToPeer (adminUsername: string, peerUsername: string) {
      try {
        this.lastError = null
        await getClient().post('/api/peer/admin/peer/connect', null, {
          params: {
            admin_username: adminUsername,
            peer_username: peerUsername,
          },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to create admin peer link'
        return false
      }
    },
    async disconnectAdminPeerFromPeer (
      adminUsername: string,
      peerUsername: string,
    ) {
      try {
        this.lastError = null
        await getClient().delete('/api/peer/admin/peer/disconnect', {
          params: {
            admin_username: adminUsername,
            peer_username: peerUsername,
          },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to remove admin peer link'
        return false
      }
    },
    async connectPeerToService (username: string, serviceName: string) {
      try {
        this.lastError = null
        await getClient().post('/api/service/connect', null, {
          params: { username, service_name: serviceName },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect peer to service'
        return false
      }
    },
    async disconnectPeerFromService (username: string, serviceName: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/service/disconnect', {
          params: { username, service_name: serviceName },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to disconnect peer from service'
        return false
      }
    },
    async connectSubnetToSubnet (subnetA: string, subnetB: string) {
      try {
        this.lastError = null
        await getClient().post('/api/network/subnets/connect', null, {
          params: { subnet_a: subnetA, subnet_b: subnetB },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect subnets'
        return false
      }
    },
    async connectAdminSubnetToSubnet (adminSubnet: string, subnet: string) {
      // Directed (adminSubnet -> subnet) admin privilege link
      try {
        this.lastError = null
        await getClient().post('/api/network/admin/connect_subnets', null, {
          params: { admin_subnet: adminSubnet, subnet },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect admin subnets'
        return false
      }
    },
    async disconnectSubnetFromSubnet (subnetA: string, subnetB: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/network/subnets/connect', {
          params: { subnet_a: subnetA, subnet_b: subnetB },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to disconnect subnets'
        return false
      }
    },
    async disconnectAdminSubnetFromSubnet (adminSubnet: string, subnet: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/network/admin/disconnect_subnets', {
          params: { admin_subnet: adminSubnet, subnet },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to disconnect admin subnet link'
        return false
      }
    },
    async connectSubnetToService (subnetCidr: string, serviceName: string) {
      try {
        this.lastError = null
        await getClient().post('/api/service/subnet/connect', null, {
          params: { subnet_address: subnetCidr, service_name: serviceName },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to connect subnet to service'
        return false
      }
    },
    async disconnectSubnetFromService (subnetCidr: string, serviceName: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/service/subnet/disconnect', {
          params: { subnet_address: subnetCidr, service_name: serviceName },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError
          = error?.message || 'Failed to disconnect subnet from service'
        return false
      }
    },
    async fetchPeerConfig (username: string) {
      try {
        this.lastError = null
        const { data } = await getClient().get<{ configuration: string }>(
          '/api/peer/config',
          { params: { username } },
        )
        return data.configuration
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to fetch config'
        return null
      }
    },
    // Delete subnet only (keep peers; memberships and links removed server-side)
    async deleteSubnet (subnetCidr: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/subnet/', {
          params: { subnet: subnetCidr },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to delete subnet'
        return false
      }
    },
    // Delete subnet and all peers inside
    async deleteSubnetWithPeers (subnetCidr: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/subnet/with_peers', {
          params: { subnet: subnetCidr },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to delete subnet with peers'
        return false
      }
    },
    // Delete a peer by username
    async deletePeer (username: string) {
      try {
        this.lastError = null
        // Use trailing slash to avoid 307 redirect to /peer/ which can bypass the dev proxy
        await getClient().delete('/api/peer/', { params: { username } })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to delete peer'
        return false
      }
    },
    // Create peer (used by AddPeerDialog). Backend assigns keys and maybe address if omitted.
    async createPeer (username: string, subnetCidr: string, address?: string) {
      try {
        this.lastError = null
        const { data } = await getClient().post<{ configuration: string }>(
          '/api/peer/create',
          null,
          { params: { username, subnet: subnetCidr, address } },
        )
        await this.fetchTopology(true)
        return data.configuration
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to create peer'
        return null
      }
    },
    // Create service bound to existing peer (host). Returns boolean success.
    async createService (
      username: string,
      serviceName: string,
      department: string,
      port: number,
      description: string,
      protocol: 'tcp' | 'udp' | 'both',
    ) {
      try {
        this.lastError = null
        const { data } = await getClient().post<{ message: string }>(
          '/api/service/create',
          null,
          {
            params: {
              service_name: serviceName,
              department,
              username,
              port,
              description,
              protocol,
            },
          },
        )
        if (data?.message && /already exists/i.test(data.message)) {
          this.lastError = data.message
          return false
        }
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to create service'
        return false
      }
    },
    async deleteService (serviceName: string) {
      try {
        this.lastError = null
        await getClient().delete('/api/service/delete', {
          params: { service_name: serviceName },
        })
        await this.fetchTopology(true)
        return true
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to delete service'
        return false
      }
    },
    startTopologyPolling (intervalMs = 1000) {
      if (this.pollingId) {
        return
      }
      this.pollingIntervalMs = intervalMs
      // On first successful fetch, we'll start coordinate pushing
      this.fetchTopology(true)
      this.pollingId = window.setInterval(
        () => this.fetchTopology(true),
        intervalMs,
      )
    },
    stopTopologyPolling () {
      if (this.pollingId) {
        clearInterval(this.pollingId)
        this.pollingId = null
      }
      // Optionally stop coordinate pushing when polling stops
      this.stopCoordinatePushing()
    },
    async fetchSubnet (_subnetId: string) {
      // Endpoint not yet adapted to new raw structure; placeholder for future expansion
    },
    clearError () {
      this.lastError = null
    },
    async getNftTableRules () {
      try {
        this.lastError = null
        const { data } = await getClient().get<{ nft_rules: string[] }>(
          '/api/network/nft_rules',
        )
        return data.nft_rules || []
      } catch (error: any) {
        this.lastError = error?.message || 'Failed to fetch nftables rules'
        return []
      }
    },
  },
  getters: {
    peers: s => s.topology?.peers || [],
    subnets: s => s.topology?.subnets || [],
    links: s => s.topology?.links || [],
    // True if current topology differs from last fetched baseline
    topologyDirty (state): boolean {
      const current = (this as any).buildTopologySignature()
      if (state.lastFetchedTopologySig == null) {
        return false
      }
      return current !== state.lastFetchedTopologySig
    },
  },
})

configureUnauthorizedHandler(() => {
  try {
    useBackendInteractionStore().apiToken = ''
  } catch {
    // Store may not be active during early app bootstrap.
  }
})

// Optional: helper to eagerly fetch once on import (comment out if undesired)
// const _store = useBackendInteractionStore()
// _store.fetchTopology().catch(()=>{})
