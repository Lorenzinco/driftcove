import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { defineStore } from 'pinia'
import { useNetworkStore, type Peer, type Subnet, type Link } from '@/stores/network'

// Types for backend data (adjust to actual backend schema as needed)
// Incoming backend format example:
// {
//   networks: [ { "10.128.0.0/9": [ { username, public_key, preshared_key, address }, ... ] }, ...],
//   links: [ { "10.128.0.0/9": { username, ... } }, { "peerAId": "peerBId" } ... ]
// }
export interface RawPeer { username: string; public_key: string; preshared_key?: string; address: string }
export interface RawTopology { networks: Array<Record<string, RawPeer[]>>; links: Array<Record<string, any>> }

function resolveBaseURL() {
	// Prefer explicit env var; fallback to same origin (dev: Vite proxy or direct port 8000)
	const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
	if (explicit) return explicit.replace(/\/$/, '')
	// If running on :5173 (default Vite) assume backend at :8000 same host
	try {
		const url = new URL(window.location.href)
		if (url.port === '5173') { url.port = '8000' }
		return url.origin
	} catch { return 'http://localhost:8000' }
}

let client: AxiosInstance | null = null
function getClient() {
	if (!client) {
		client = axios.create({ baseURL: resolveBaseURL(), timeout: 10000 })
	}
	return client
}

export const useBackendInteractionStore = defineStore('backendInteraction', {
	state: () => ({
		loading: false,
		lastError: '' as string | null,
		topology: null as { peers: any[]; subnets: any[]; links: any[] } | null,
		lastFetchedAt: 0,
		pollingId: null as number | null,
		pollingIntervalMs: 1000,
		subnetDetails: {} as Record<string, { name: string; description?: string; fetchedAt: number }>,
	}),
	actions: {
		async fetchTopology(force = false) {
			if (this.loading) return
			if (!force && this.topology && Date.now() - this.lastFetchedAt < 5000) return
			this.loading = true; this.lastError = null
			try {
				// Refresh subnet metadata cache first (throttled inside helper)
				const subnets = await this.fetchSubnets()
				const { data } = await getClient().get<RawTopology>('/api/network/topology')
				// Transform backend structure to internal metadata arrays (no coordinates so existing positions persist)
				const subnetsMeta: Array<{ id: string; name: string; cidr: string; description?: string }> = []
				const peersMeta: Array<{ id: string; name: string; ip: string; subnetId: string | null }> = []
				const links: Link[] = []

				// Map to track subnet bounds layout (simple grid placement)
				for (const netObj of data.networks || []) {
					const cidr = Object.keys(netObj)[0]
					if (!cidr) continue
					const rawPeers = netObj[cidr] || []
					const subnetId = `subnet_${cidr}`
					const subnetName = subnets.find(s => s.id === subnetId)?.name || cidr
                    const subnetDescription = subnets.find(s => s.id === subnetId)?.description || "Couldn't fetch any description for this subnet"
					subnetsMeta.push({ id: subnetId, name: subnetName, cidr, description: subnetDescription})
					for (const rp of rawPeers) {
							peersMeta.push({ id: `peer_${rp.public_key}`, name: rp.username, ip: rp.address, subnetId })
						}
				}
                console.log("Fetched peers from backend:", peersMeta)
                console.log("Fetched subnets from backend:", subnetsMeta)

				// Build link set: interpret each object; key->value meaning connected (using meta ids)
				const peerIds = new Set(peersMeta.map(p => p.id))
				const subnetIds = new Set(subnetsMeta.map(s => s.id))
				let linkCounter = 0
				for (const linkObj of data.links || []) {
					const keys = Object.keys(linkObj)
					if (keys.length !== 1) continue
					const fromKey = keys[0]
					const value = linkObj[fromKey]
					// value may be an object describing a peer (matching one in network) or a CIDR string or peer public_key
					let fromId: string | null = null
					let toId: string | null = null
					// Determine fromId
					if (subnetIds.has(`subnet_${fromKey}`)) fromId = `subnet_${fromKey}`
					else if (peerIds.has(`peer_${fromKey}`)) fromId = `peer_${fromKey}`
					// Determine toId
					if (typeof value === 'string') {
						if (subnetIds.has(`subnet_${value}`)) toId = `subnet_${value}`
						else if (peerIds.has(`peer_${value}`)) toId = `peer_${value}`
					} else if (value && typeof value === 'object') {
						// See if matches an existing peer by public key
						if (value.public_key && peerIds.has(`peer_${value.public_key}`)) {
							toId = `peer_${value.public_key}`
						}
					}
					if (fromId && toId) links.push({ id: `link_${linkCounter++}`, fromId, toId })
				}
				// Cache simplified topology
				this.topology = { peers: peersMeta, subnets: subnetsMeta, links: links.map(l => ({ id: l.id, fromId: l.fromId, toId: l.toId })) }
				// Update visual store with incremental merge (no coordinates overridden)
				useNetworkStore().applyBackendTopology({ peers: peersMeta, subnets: subnetsMeta, links })
				this.lastFetchedAt = Date.now()
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to fetch topology'
			} finally { this.loading = false }
		},
		async fetchSubnets() {
            const subnetsMeta: Array<{ id: string; name: string; cidr: string; description?: string }> = []
			try {
				const { data } = await getClient().get<{ subnets: Array<{ subnet: string; name: string; description?: string }> }>('/api/network/subnets')
				// Update existing displayed subnets with new metadata (no coordinate change)
				for (const item of data.subnets || []) {
					subnetsMeta.push({ id: `subnet_${item.subnet}`, name: item.name, cidr: item.subnet, description: item.description })
				}
			} catch (e) { /* silent */ }
            return subnetsMeta
		},
		async createPeer(username: string, subnetCidr: string) {
			// Backend create endpoint (POST /api/peer/create) expects simple query parameters: username & subnet
			// Response: { configuration: string }
			try {
				this.lastError = null
				const { data } = await getClient().post<{ configuration: string }>(
					'/api/peer/create',
					null,
					{ params: { username, subnet: subnetCidr } }
				)
				// After creation, refresh topology so new peer (with assigned IP/public key) appears
				await this.fetchTopology(true)
				return data.configuration
			} catch (e: any) {
				this.lastError = e?.message || 'Failed to create peer'
				return null
			}
		},
		startTopologyPolling(intervalMs = 1000) {
			if (this.pollingId) return
			this.pollingIntervalMs = intervalMs
			// Immediate fetch
			this.fetchTopology(true)
			this.pollingId = window.setInterval(() => {
				this.fetchTopology(true)
			}, intervalMs)
		},
		stopTopologyPolling() {
			if (this.pollingId) {
				clearInterval(this.pollingId)
				this.pollingId = null
			}
		},
		async fetchSubnet(_subnetId: string) {
			// Endpoint not yet adapted to new raw structure; placeholder for future expansion
		},
		clearError() { this.lastError = null },
	},
	getters: {
		peers: (s) => s.topology?.peers || [],
		subnets: (s) => s.topology?.subnets || [],
		links: (s) => s.topology?.links || [],
	}
})

// Optional: helper to eagerly fetch once on import (comment out if undesired)
// const _store = useBackendInteractionStore()
// _store.fetchTopology().catch(()=>{})
