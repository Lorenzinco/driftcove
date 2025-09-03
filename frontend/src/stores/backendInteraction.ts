import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { defineStore } from 'pinia'
import { useNetworkStore, type Peer, type Subnet, type Link, type ServiceInfo } from '@/stores/network'

// Types for backend data (new preferred format + backward compatibility)
// New format (full subnet details bundled):
// {
//   networks: [ { subnet: { subnet, name, description, x, y, width, height }, peers: [ { username, public_key, address, x, y, services:{} }, ... ] } ],
//   links: [ { "peerA <-> peerB": [peerAObj, peerBObj] }, { "ServiceName": [peerObj, ...] }, ... ]
// }
// Legacy format (still supported for fallback):
// { networks: [ { "10.0.0.0/24": [ peerObj, ... ] }, ... ], links: [...] }
export interface RawService extends ServiceInfo { }
export interface RawPeer { username: string; public_key: string; preshared_key?: string; address: string; x: number; y: number; services?: Record<string | number, RawService> }
export interface RawSubnet { subnet: string; name: string; description?: string; x: number; y: number; width: number; height: number }
export interface RawTopologyNew { networks: Array<{ subnet: RawSubnet; peers: RawPeer[] }>; links: Array<Record<string, any>> }
export interface RawTopologyLegacy { networks: Array<Record<string, RawPeer[]>>; links: Array<Record<string, any>> }

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
				const { data } = await getClient().get<any>('/api/network/topology')
				const subnetsMeta: Array<{ id: string; name: string; cidr: string; description?: string; x?: number; y?: number; width?: number; height?: number }> = []
				const peersMeta: Array<{ id: string; name: string; ip: string; subnetId: string | null; x?: number; y?: number; services?: Record<string, any>; host?: boolean; presharedKey?: string; publicKey?: string }> = []
				const links: Link[] = []

				const networksArr = data.networks || []
				// New backend shape: separate subnets array holds full metadata (preferred)
				const backendSubnets: RawSubnet[] = data.subnets || []
				const providedSubnetIds = new Set<string>()
				for (const s of backendSubnets) {
					const subnetId = `subnet_${s.subnet}`
					providedSubnetIds.add(subnetId)
					subnetsMeta.push({ id: subnetId, name: s.name, cidr: s.subnet, description: s.description, x: s.x, y: s.y, width: s.width, height: s.height })
				}
				// Legacy networks list (cidr -> peers) still supplies peers; use coordinates from peers (x,y) and link them to existing subnets
				for (const netObj of networksArr as RawTopologyLegacy['networks']) {
					const cidr = Object.keys(netObj)[0]
					if (!cidr) continue
					const rawPeers = (netObj as any)[cidr] || []
					const subnetId = `subnet_${cidr}`
					if (!providedSubnetIds.has(subnetId)) {
						// Subnet was not in data.subnets; create minimal entry
						subnetsMeta.push({ id: subnetId, name: cidr, cidr })
						providedSubnetIds.add(subnetId)
					}
					for (const rp of rawPeers) {
						const servicesRaw = rp.services || {}
						const services: Record<string, any> = {}
						for (const k of Object.keys(servicesRaw)) services[String(k)] = servicesRaw[k]
						peersMeta.push({ id: `peer_${rp.public_key}`, name: rp.username, ip: rp.address, subnetId, x: rp.x, y: rp.y, services, host: Object.keys(services).length > 0, presharedKey: rp.preshared_key, publicKey: rp.public_key })
					}
				}

				// Links (simple pass-through mapping similar to legacy behaviour)
				const peerIds = new Set(peersMeta.map(p => p.id))
				const subnetIds = new Set(subnetsMeta.map(s => s.id))
				let linkCounter = 0
				for (const linkObj of data.links || []) {
					const keys = Object.keys(linkObj)
					if (keys.length !== 1) continue
					const rawKey = keys[0]
					const value = linkObj[rawKey]
					// Pattern matching new backend link key styles
					if (rawKey.includes(' <-p2p-> ')) {
						if (Array.isArray(value) && value.length === 2 && value[0]?.public_key && value[1]?.public_key) {
							const a = `peer_${value[0].public_key}`
							const b = `peer_${value[1].public_key}`
							if (peerIds.has(a) && peerIds.has(b)) {
								links.push({ id: `link_${linkCounter++}`, fromId: a, toId: b, kind: 'p2p' })
							}
						}
						continue
					}
					if (rawKey.includes(' <-service->')) {
						// Key format: "ServiceName <-service->"
						const serviceName = rawKey.replace(' <-service->', '').trim()
						if (Array.isArray(value) && value.length > 1) {
							const ids = value.filter(v => v?.public_key).map(v => `peer_${v.public_key}`).filter(id => peerIds.has(id))
							if (ids.length > 1) {
								for (let i = 1; i < ids.length; i++) {
									links.push({ id: `link_${linkCounter++}`, fromId: ids[0], toId: ids[i], kind: 'service', serviceName })
								}
							}
						}
						continue
					}
					if (rawKey.includes(' <-subnet-> ')) {
						// Format: "CIDR <-subnet-> username" value: [subnetObj, peerObj]
						if (Array.isArray(value) && value.length === 2) {
							const subnetObj = value[0]
							const peerObj = value[1]
							if (subnetObj?.subnet && peerObj?.public_key) {
								const sid = `subnet_${subnetObj.subnet}`
								const pid = `peer_${peerObj.public_key}`
								if (subnetIds.has(sid) && peerIds.has(pid)) {
									links.push({ id: `link_${linkCounter++}`, fromId: pid, toId: sid, kind: 'membership' as any })
								}
							}
						}
						continue
					}
					// Fallback legacy handling (shouldn't generally be used now)
					let fromId: string | null = null; let toId: string | null = null
					if (subnetIds.has(`subnet_${rawKey}`)) fromId = `subnet_${rawKey}`
					else if (peerIds.has(`peer_${rawKey}`)) fromId = `peer_${rawKey}`
					if (value && typeof value === 'object' && value.public_key) {
						const pid = `peer_${value.public_key}`
						if (peerIds.has(pid)) toId = pid
					}
					if (fromId && toId) links.push({ id: `link_${linkCounter++}`, fromId, toId })
				}

				this.topology = { peers: peersMeta, subnets: subnetsMeta, links: links.map(l => ({ id: l.id, fromId: l.fromId, toId: l.toId, kind: (l as any).kind, serviceName: (l as any).serviceName })) }
				useNetworkStore().applyBackendTopology({ peers: peersMeta, subnets: subnetsMeta, links })
				this.lastFetchedAt = Date.now()
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to fetch topology'
			} finally { this.loading = false }
		},
		async uploadTopology(topology: any) {
			try {
				this.lastError = null
				await getClient().post('/api/network/topology', topology)
				return true
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to upload topology'
				return false
			}
		},
		buildCurrentTopologyPayload() {
			// Construct a generic payload matching backend expectations
			// peers: include username (name), address (ip), x,y; public_key unknown on frontend for unsynced peers
			const netStore = useNetworkStore()
			const subnets = netStore.subnets.map(s => ({
				subnet: s.cidr,
				name: s.name,
				description: s.description,
				x: s.x,
				y: s.y,
				width: s.width,
				height: s.height
			}))
			// Build networks dict mapping cidr -> peers (peers defined with placeholder keys if unknown)
			const networks: Record<string, any[]> = {}
				for (const peer of netStore.peers) {
				const subnet = netStore.subnets.find(s => s.id === peer.subnetId)
				const cidr = subnet?.cidr
				if (!cidr) continue
				if (!networks[cidr]) networks[cidr] = []
						networks[cidr].push({
							username: peer.name,
							address: peer.ip,
							public_key: peer.publicKey || `placeholder_${peer.id}`,
							preshared_key: peer.presharedKey || '',
							x: peer.x,
							y: peer.y,
							services: peer.services || {}
						})
			}
			// Links: build list of [key, value] pairs matching backend expectation (for key,value in links)
			const links: Array<[string, any]> = []
			// Subnet membership links
			for (const [cidr, peers] of Object.entries(networks)) {
				const subnetMeta = subnets.find(s => s.subnet === cidr)
				if (!subnetMeta) continue
				for (const p of peers) {
					links.push([`${cidr} <-subnet-> ${p.username}`, [subnetMeta, p]])
				}
			}
			// p2p links (from store links of kind p2p)
			for (const l of netStore.links.filter(l => l.kind === 'p2p')) {
				const a = netStore.peers.find(p => p.id === l.fromId)
				const b = netStore.peers.find(p => p.id === l.toId)
				if (a && b) {
					const aObj = networks[a.subnetId ? netStore.subnets.find(s => s.id === a.subnetId)?.cidr || '' : '']?.find(pp => pp.username === a.name)
					const bObj = networks[b.subnetId ? netStore.subnets.find(s => s.id === b.subnetId)?.cidr || '' : '']?.find(pp => pp.username === b.name)
					if (aObj && bObj) links.push([`${a.name} <-p2p-> ${b.name}`, [aObj, bObj]])
				}
			}
			// service links: group by serviceName across peers
			const serviceGroups: Record<string, any[]> = {}
			for (const peer of netStore.peers) {
				for (const svcName of Object.keys(peer.services || {})) {
					const peerObj = networks[netStore.subnets.find(s => s.id === peer.subnetId)?.cidr || '']?.find(pp => pp.username === peer.name)
					if (!peerObj) continue
					if (!serviceGroups[svcName]) serviceGroups[svcName] = []
					serviceGroups[svcName].push(peerObj)
				}
			}
			for (const [svc, peersArr] of Object.entries(serviceGroups)) {
				if (peersArr.length > 0) links.push([`${svc} <-service->`, peersArr])
			}
			return { subnets, networks, links }
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
		async createPeer(username: string, subnetCidr: string, cidr: string|undefined=undefined) {
			// Backend create endpoint (POST /api/peer/create) expects simple query parameters: username & subnet
			// Response: { configuration: string }
			try {
				this.lastError = null
				const { data } = await getClient().post<{ configuration: string }>(
					'/api/peer/create',
					null,
					{ params: { username, subnet: subnetCidr, address: cidr } }
				)
				// After creation, refresh topology so new peer (with assigned IP/public key) appears
				await this.fetchTopology(true)
				// Center the newly created peer inside its subnet (requirement)
				const netStore = useNetworkStore()
				const targetSubnetId = `subnet_${subnetCidr}`
				const subnet = netStore.subnets.find(s => s.id === targetSubnetId || s.cidr === subnetCidr)
				if (subnet) {
					// Find peer by username (names map to usernames)
					const peer = netStore.peers.find(p => p.name === username && p.subnetId === targetSubnetId)
					if (peer) {
						peer.x = subnet.x
						peer.y = subnet.y
					}
				}
				return data.configuration
			} catch (e: any) {
				this.lastError = e?.message || 'Failed to create peer'
				return null
			}
		},
		async createSubnet(subnet: string, name: string, description: string, x:number, y:number) {
			try {
				this.lastError = null
				await getClient().post('/api/subnet/create', { subnet, name, description, x, y })
				return true
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to create subnet'
				return false
			}
		},
		async connectPeerToSubnet(username: string, subnetCidr: string) {
			try {
				this.lastError = null
				await getClient().post('/api/subnet/connect', null, { params: { username, subnet: subnetCidr } })
				await this.fetchTopology(true)
				return true
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to connect peer to subnet'
				return false
			}
		},
		async disconnectPeerFromSubnet(username: string, subnetCidr: string) {
			try {
				this.lastError = null
				await getClient().delete('/api/subnet/disconnect', { params: { username, subnet: subnetCidr } })
				await this.fetchTopology(true)
				return true
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to disconnect peer from subnet'
				return false
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
