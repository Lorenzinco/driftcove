import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { defineStore } from 'pinia'
import { type Peer, type Subnet, type Link, type ServiceInfo} from '@/types/network'
import { useNetworkStore } from '@/stores/network'

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
		// Fetch and adapt new normalized topology structure from backend
		async fetchTopology(force = false) {
			if (this.loading) return
			this.loading = true; this.lastError = null
			try {
				const { data } = await getClient().get<any>('/api/network/topology')
				const topo = data.topology || {}
				const subnetsDict = topo.subnets || {}
				const peersDict = topo.peers || {}
				// New normalized dict-based link containers
				const serviceLinksDict: Record<string, any[]> = topo.service_links || {}
				const p2pLinksDict: Record<string, any[]> = topo.p2p_links || {}
				const subnetLinksDict: Record<string, any[]> = topo.subnet_links || {}

				// Subnets
				const subnetsMeta: Array<{ id: string; name: string; cidr: string; description?: string; x?: number; y?: number; width?: number; height?: number; rgba?: number }> = []
				for (const cidr of Object.keys(subnetsDict)) {
					const s = subnetsDict[cidr]
					if (!s) continue
					const id = cidr // use raw cidr as id (unique by design)
					subnetsMeta.push({ id, name: s.name || cidr, cidr, description: s.description, x: s.x, y: s.y, width: s.width, height: s.height, rgba: s.rgba })
				}

				// Membership map: peer public key -> subnetId
				const membership: Record<string, string> = {}
				for (const cidr of Object.keys(subnetLinksDict)) {
					const sid = cidr
					for (const p of subnetLinksDict[cidr] || []) {
						if (p?.public_key) membership[p.public_key] = sid
					}
				}

				// Peers
				const peersMeta: Array<{ id: string; name: string; ip: string; subnetId: string | null; x?: number; y?: number; services?: Record<string, any>; host?: boolean; presharedKey?: string; publicKey?: string }> = []
				for (const addr of Object.keys(peersDict)) {
					const p = peersDict[addr]
					if (!p || !p.public_key) continue
					const servicesRaw = p.services || {}
					const services: Record<string, any> = {}
					for (const k of Object.keys(servicesRaw)) services[k] = servicesRaw[k]
					const subnetId = membership[p.public_key] || null
					const id = p.public_key // raw public key as id
					const host = Object.values(services).some((sv:any)=> sv && typeof sv.port === 'number' && !isNaN(sv.port))
					peersMeta.push({ id, name: p.username, ip: p.address, subnetId, x: p.x, y: p.y, services, host, presharedKey: p.preshared_key, publicKey: p.public_key })
				}

				// Map for quick lookup
				const peerByPublic: Record<string, any> = {}
				for (const p of peersMeta) peerByPublic[p.publicKey!] = p

				// Links
				const links: Link[] = []
				let linkCounter = 0
				// Membership
				for (const cidr of Object.keys(subnetLinksDict)) {
					const sid = cidr
					for (const peerObj of subnetLinksDict[cidr] || []) {
						if (peerObj?.public_key && peerByPublic[peerObj.public_key]) {
							links.push({ id: `link_${linkCounter++}`, fromId: peerObj.public_key, toId: sid, kind: 'membership' })
						}
					}
				}
				// p2p (adjacency dict: basePeerAddress -> [linkedPeerObjects])
				const seenPairs = new Set<string>()
				for (const baseAddr of Object.keys(p2pLinksDict)) {
					const neighbors = p2pLinksDict[baseAddr]
					if (!Array.isArray(neighbors)) continue
					// find base peer by address
					const basePeer = peersMeta.find(p => p.ip === baseAddr)
					if (!basePeer) continue
					for (const n of neighbors) {
						if (!n?.public_key) continue
						const neighborPeer = peerByPublic[n.public_key]
						if (!neighborPeer) continue
						if (neighborPeer.publicKey === basePeer.publicKey) continue
						const aId = basePeer.publicKey!, bId = neighborPeer.publicKey!
						const pairKey = aId < bId ? `${aId}::${bId}` : `${bId}::${aId}`
						if (seenPairs.has(pairKey)) continue
						seenPairs.add(pairKey)
						links.push({ id: `link_${linkCounter++}`, fromId: aId, toId: bId, kind: 'p2p' })
					}
				}
				// Service links (serviceName -> [consumerPeerObjs]) host inferred via services map
				for (const serviceName of Object.keys(serviceLinksDict)) {
					const consumers = serviceLinksDict[serviceName] || []
					const hostPeer = peersMeta.find(p => p.services && p.services[serviceName])
					if (!hostPeer) continue
					for (const c of consumers) {
						if (c?.public_key && c.public_key !== hostPeer.publicKey && peerByPublic[c.public_key]) {
							links.push({ id: `link_${linkCounter++}`, fromId: hostPeer.id, toId: c.public_key, kind: 'service', serviceName })
						}
					}
				}

				// Finalize
				this.topology = { peers: peersMeta, subnets: subnetsMeta, links: links.map(l => ({ id: l.id, fromId: l.fromId, toId: l.toId, kind: l.kind, serviceName: (l as any).serviceName })) }
				useNetworkStore().applyBackendTopology({ peers: peersMeta, subnets: subnetsMeta, links })
				// Notify canvas to force an immediate redraw (initial real data)
				window.dispatchEvent(new CustomEvent('topology-updated'))
				this.lastFetchedAt = Date.now()
			} catch (e:any) {
				this.lastError = e?.message || 'Failed to fetch topology'
			} finally { this.loading = false }
		},

		// Upload current in-memory topology (already converted by caller)
		async uploadTopology(payload: any){
			try {
				this.lastError = null
				await getClient().post('/api/network/topology', payload)
				return true
			} catch(e:any){ this.lastError = e?.message || 'Failed to upload topology'; return false }
		},

		// Build payload matching backend Topology model
		buildCurrentTopologyPayload(){
			const netStore = useNetworkStore()
			// Subnets dict
			const subnets: Record<string, any> = {}
			for (const s of netStore.subnets){
				let rgba:any = (s as any).rgba
				if (rgba == null || isNaN(rgba)) rgba = 0x00FF0025
				rgba = (Number(rgba) >>> 0) & 0xFFFFFFFF
				subnets[s.cidr] = { subnet: s.cidr, name: s.name, description: s.description, x: s.x, y: s.y, width: s.width, height: s.height, rgba }
			}
			// Peers dict keyed by address
			const peers: Record<string, any> = {}
			// Services aggregated
			const services: Record<string, any> = {}
			// Helper mapping subnet cidr -> peer objects
			const subnetMembers: Record<string, any[]> = {}

			// Build peer objects first
			const peerObjById: Record<string, any> = {}
			for (const p of netStore.peers){
				const peerObj: any = {
					username: p.name,
					address: p.ip,
					public_key: p.publicKey || `placeholder_${p.id}`,
					preshared_key: p.presharedKey || '',
					x: p.x,
					y: p.y,
					services: p.host ? (p.services || {}) : {}
				}
				peers[p.ip || p.name] = peerObj
				peerObjById[p.id] = peerObj
				for (const [svcName, svc] of Object.entries(p.services || {})) {
					services[svcName] = { name: svcName, department: (svc as any).department, port: (svc as any).port, description: (svc as any).description || '' }
				}
			}

			// Collect memberships from links (explicit only)
			for (const l of netStore.links.filter(l=> l.kind==='membership')){
				const peer = netStore.peers.find(p=> p.id === l.fromId)
				const subnet = netStore.subnets.find(s=> s.id === l.toId)
				if (peer && subnet){
					const arr = subnetMembers[subnet.cidr] || (subnetMembers[subnet.cidr] = [])
					const pobj = peerObjById[peer.id]
					if (pobj && !arr.some(x=> x.public_key === pobj.public_key)) arr.push(pobj)
				}
			}

				// p2p links adjacency dict: address -> [linked peer objects]
				const p2p_links: Record<string, any[]> = {}
				const addedPairs = new Set<string>()
				function addAdj(baseAddr:string, neighborObj:any){
					if (!baseAddr || !neighborObj) return
					const arr = p2p_links[baseAddr] || (p2p_links[baseAddr] = [])
					if (!arr.some(p=> p.public_key === neighborObj.public_key)) arr.push(neighborObj)
				}
				for (const l of netStore.links.filter(l=> l.kind==='p2p')){
					const a = netStore.peers.find(p=> p.id === l.fromId)
					const b = netStore.peers.find(p=> p.id === l.toId)
					if (!a || !b) continue
					const aObj = peerObjById[a.id]; const bObj = peerObjById[b.id]; if (!aObj || !bObj) continue
					const aAddr = a.ip, bAddr = b.ip; if (!aAddr || !bAddr) continue
					const pairKey = aAddr < bAddr ? `${aAddr}::${bAddr}` : `${bAddr}::${aAddr}`
					if (addedPairs.has(pairKey)) continue
					addedPairs.add(pairKey)
					// Store only under lexicographically smaller address to keep single direction
					const base = aAddr < bAddr ? aAddr : bAddr
					const neighbor = aAddr < bAddr ? bObj : aObj
					addAdj(base, neighbor)
				}

			// service links aggregated into dict serviceName -> [consumers]
			const service_links: Record<string, any[]> = {}
			for (const l of netStore.links.filter(l=> l.kind==='service')){
				const svcName = (l as any).serviceName; if (!svcName) continue
				const consumer = netStore.peers.find(p=> p.id === l.toId); if (!consumer) continue
				const consumerObj = peerObjById[consumer.id]; if (!consumerObj) continue
				const arr = service_links[svcName] || (service_links[svcName] = [])
				if (!arr.some(x=> x.public_key === consumerObj.public_key)) arr.push(consumerObj)
			}

			// subnet links dict
			const subnet_links: Record<string, any[]> = {}
			for (const [cidr, arr] of Object.entries(subnetMembers)) subnet_links[cidr] = arr

			return { subnets, peers, services, p2p_links, service_links, subnet_links }
		},
		// Create subnet helper (legacy endpoints retained if still active backend-side)
		async createSubnet(subnet: string, name: string, description: string, x:number, y:number, width:number, height:number, rgba:number){
			try { this.lastError=null; await getClient().post('/api/subnet/create',{subnet,name,description,x,y,width,height,rgba}); return true } catch(e:any){ this.lastError = e?.message || 'Failed to create subnet'; return false }
		},
		async connectPeerToSubnet(username: string, subnetCidr: string){
			try { this.lastError=null; await getClient().post('/api/subnet/connect', null, { params:{ username, subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect peer to subnet'; return false }
		},
		async disconnectPeerFromSubnet(username: string, subnetCidr: string){
			try { this.lastError=null; await getClient().delete('/api/subnet/disconnect', { params:{ username, subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect peer from subnet'; return false }
		},
		async connectPeers(peer1: string, peer2: string){
			try { this.lastError=null; await getClient().post('/api/peer/connect', null, { params:{ peer1_username: peer1, peer2_username: peer2 }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect peers'; return false }
		},
		async connectPeerToService(username: string, serviceName: string){
			try { this.lastError=null; await getClient().post('/api/service/connect', null, { params:{ username, service_name: serviceName }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect peer to service'; return false }
		},
		async fetchPeerConfig(username: string){
			try { this.lastError=null; const { data } = await getClient().get<{configuration:string}>('/api/peer/config', { params:{ username } }); return data.configuration } catch(e:any){ this.lastError = e?.message || 'Failed to fetch config'; return null }
		},
		// Create peer (used by AddPeerDialog). Backend assigns keys and maybe address if omitted.
		async createPeer(username: string, subnetCidr: string, address?: string){
			try {
				this.lastError = null
				const { data } = await getClient().post<{ configuration: string }>('/api/peer/create', null, { params: { username, subnet: subnetCidr, address } })
				await this.fetchTopology(true)
				return data.configuration
			} catch(e:any){ this.lastError = e?.message || 'Failed to create peer'; return null }
		},
		// Create service bound to existing peer (host). Returns boolean success.
		async createService(username: string, serviceName: string, department: string, port: number){
			try {
				this.lastError = null
				const { data } = await getClient().post<{ message: string }>('/api/service/create', null, { params: { service_name: serviceName, department, username, port } })
				if (data?.message && /already exists/i.test(data.message)) {
					this.lastError = data.message
					return false
				}
				await this.fetchTopology(true)
				return true
			} catch(e:any){ this.lastError = e?.message || 'Failed to create service'; return false }
		},
		startTopologyPolling(intervalMs = 1000){
			if (this.pollingId) return
			this.pollingIntervalMs = intervalMs
			this.fetchTopology(true)
			this.pollingId = window.setInterval(()=> this.fetchTopology(true), intervalMs)
		},
		stopTopologyPolling(){
			if (this.pollingId){ clearInterval(this.pollingId); this.pollingId = null }
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
