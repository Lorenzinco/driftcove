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
		pollingIntervalMs: 5000,
		coordPushId: null as number | null,
		coordPushIntervalMs: 10000,
		pushing: false,
		hasFetchedOnce: false,
		lastSentCoordsSig: null as string | null,
		subnetDetails: {} as Record<string, { name: string; description?: string; fetchedAt: number }>,
	}),
	actions: {
		// Build a stable signature of current coordinates/sizes/colors to detect changes
		buildCoordinateSignature(): string {
			const net = useNetworkStore()
			const subnets = (net.subnets || []).map(s => ({ id: s.id, x: s.x, y: s.y, w: s.width, h: s.height, c: (s as any).rgba }))
			const peers = (net.peers || []).map(p => ({ id: p.id, x: p.x, y: p.y }))
			// Sort for deterministic order
			subnets.sort((a,b)=> (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
			peers.sort((a,b)=> (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
			return JSON.stringify({ S: subnets, P: peers })
		},

		// Push current coordinates/sizes/colors to backend using the update endpoint (non-destructive)
		async pushCoordinatesOnce(){
			// Don't push until we've fetched real data at least once to avoid sending mock/seed state
			if (this.pushing || !this.hasFetchedOnce) return
			// Skip if no coordinate changes since last push
			const sig = this.buildCoordinateSignature()
			if (this.lastSentCoordsSig && sig === this.lastSentCoordsSig) return
			this.pushing = true
			try {
				const payload = this.buildCurrentTopologyPayload()
				await getClient().post('/api/network/update_coordinates', payload)
				this.lastSentCoordsSig = sig
			} catch (e:any) {
				// Keep quiet but track lastError for visibility
				this.lastError = e?.message || 'Failed to push coordinates'
			} finally {
				this.pushing = false
			}
		},

		startCoordinatePushing(intervalMs = 1000){
			if (this.coordPushId) return
			this.coordPushIntervalMs = intervalMs
			// Immediate push will happen only if hasFetchedOnce is true
			this.pushCoordinatesOnce()
			this.coordPushId = window.setInterval(()=> this.pushCoordinatesOnce(), intervalMs)
		},

		stopCoordinatePushing(){
			if (this.coordPushId){ clearInterval(this.coordPushId); this.coordPushId = null }
		},
		// Fetch and adapt new normalized topology structure from backend
		async fetchTopology(force = false) {
			if (this.loading) return
			this.loading = true; this.lastError = null
			try {
				const { data } = await getClient().get<any>('/api/network/topology')
				const rules = await this.getNftTableRules()
				//console.log(rules)
				const topo = data.topology || {}
				const subnetsDict = topo.subnets || {}
				const peersDict = topo.peers || {}
				// New normalized dict-based link containers
				const serviceLinksDict: Record<string, any[]> = topo.service_links || {}
				const p2pLinksDict: Record<string, any[]> = topo.p2p_links || {}
				const subnetLinksDict: Record<string, any[]> = topo.subnet_links || {}
				// New link types
				const subnetToSubnetDict: Record<string, any[]> = topo.subnet_to_subnet_links || {}
				// Renamed backend field: now subnet_to_service_links (subnet -> [Service])
				const subnetToServiceDict: Record<string, any[]> = topo.subnet_to_service_links || {}
				// Admin directed link dicts
				const adminPeerToPeer: Record<string, any[]> = topo.admin_peer_to_peer_links || {}
				const adminPeerToSubnet: Record<string, any[]> = topo.admin_peer_to_subnet_links || {}
				const adminSubnetToSubnet: Record<string, any[]> = topo.admin_subnet_to_subnet_links || {}
				const networkDict: Record<string, any[]> = topo.network || {}

				// Subnets
				const subnetsMeta: Array<{ id: string; name: string; cidr: string; description?: string; x?: number; y?: number; width?: number; height?: number; rgba?: number }> = []
				for (const cidr of Object.keys(subnetsDict)) {
					const s = subnetsDict[cidr]
					if (!s) continue
					const id = cidr // use raw cidr as id (unique by design)
					subnetsMeta.push({ id, name: s.name || cidr, cidr, description: s.description, x: s.x, y: s.y, width: s.width, height: s.height, rgba: s.rgba })
				}

				// Containment map from new 'network' field: peer public key -> subnetId (cidr)
				const contained: Record<string, string> = {}
				for (const cidr of Object.keys(networkDict)) {
					const sid = cidr
					for (const p of networkDict[cidr] || []) {
						if (p?.public_key) contained[p.public_key] = sid
					}
				}

				// Peers
				const peersMeta: Array<{ id: string; name: string; ip: string; subnetId: string | null; x?: number; y?: number; services?: Record<string, any>; host?: boolean; presharedKey?: string; publicKey?: string; rx: number; tx: number; lastHandshake: number }> = []
				for (const addr of Object.keys(peersDict)) {
					const p = peersDict[addr]
					if (!p || !p.public_key) continue
					const servicesRaw = p.services || {}
					const services: Record<string, any> = {}
					for (const k of Object.keys(servicesRaw)) services[k] = servicesRaw[k]
					const subnetId = contained[p.public_key] || null
					const id = p.public_key // raw public key as id
					const host = Object.values(services).some((sv:any)=> sv && typeof sv.port === 'number' && !isNaN(sv.port))
					const rx = typeof p.rx === 'number' && !isNaN(p.rx) ? p.rx : 0
					const tx = typeof p.tx === 'number' && !isNaN(p.tx) ? p.tx : 0
					const lastHandshake = typeof p.last_handshake === 'number' && !isNaN(p.last_handshake) ? p.last_handshake : 0
					peersMeta.push({ id, name: p.username, ip: p.address, subnetId, x: p.x, y: p.y, services, host, presharedKey: p.preshared_key, publicKey: p.public_key, rx, tx, lastHandshake })
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

				// Subnet-to-subnet links: dict cidrA -> [subnetObjB,...] (undirected)
				{
					const seen = new Set<string>()
					function pairKey(a:string,b:string){ return a < b ? `${a}::${b}` : `${b}::${a}` }
					for (const cidrA of Object.keys(subnetToSubnetDict)){
						const sidA = cidrA
						const arr = subnetToSubnetDict[cidrA] || []
						for (const s of arr){
							const cidrB = s?.subnet || s?.cidr || s // tolerate shapes
							if (!cidrB || typeof cidrB !== 'string') continue
							const sidB = cidrB
							if (sidA === sidB) continue
							const pk = pairKey(sidA,sidB)
							if (seen.has(pk)) continue
							seen.add(pk)
							links.push({ id: `link_${linkCounter++}`, fromId: sidA, toId: sidB, kind: 'subnet-subnet' })
						}
					}
				}

				// Subnet-to-service links: dict subnetCIDR -> [Service]
				for (const cidr of Object.keys(subnetToServiceDict)){
					const sid = cidr
					const servicesArr = subnetToServiceDict[cidr] || []
					for (const svc of servicesArr){
						const svcName = (svc && (svc.name || (typeof svc === 'string' ? svc : '')))
						if (!svcName) continue
						const hostPeer = peersMeta.find(p => p.services && p.services[svcName])
						if (!hostPeer) continue
						links.push({ id: `link_${linkCounter++}`, fromId: hostPeer.id, toId: sid, kind: 'subnet-service', serviceName: svcName })
					}
				}

				// Admin directed links
				// admin_peer_to_peer_links: key = source peer address, values = peer objects (targets)
				for (const srcAddr of Object.keys(adminPeerToPeer)) {
					const srcPeer = peersMeta.find(p => p.ip === srcAddr)
					if (!srcPeer) continue
					for (const tgt of adminPeerToPeer[srcAddr] || []) {
						if (!tgt?.public_key) continue
						const tgtPeer = peersMeta.find(p => p.publicKey === tgt.public_key)
						if (!tgtPeer) continue
						links.push({ id: `link_${linkCounter++}`, fromId: srcPeer.id, toId: tgtPeer.id, kind: 'admin-p2p' })
					}
				}
				// admin_peer_to_subnet_links: key = source peer address, values = subnet objects (targets)
				for (const srcAddr of Object.keys(adminPeerToSubnet)) {
					const srcPeer = peersMeta.find(p => p.ip === srcAddr)
					if (!srcPeer) continue
					for (const tgt of adminPeerToSubnet[srcAddr] || []) {
						const tgtCidr = tgt?.subnet || tgt?.cidr || (typeof tgt === 'string' ? tgt : null)
						if (!tgtCidr) continue
						// Ensure subnet exists (will by id=cidr) else skip
						links.push({ id: `link_${linkCounter++}`, fromId: srcPeer.id, toId: tgtCidr, kind: 'admin-peer-subnet' })
					}
				}
				// admin_subnet_to_subnet_links: key = source subnet cidr, values = subnet objects (targets)
				for (const srcCidr of Object.keys(adminSubnetToSubnet)) {
					for (const tgt of adminSubnetToSubnet[srcCidr] || []) {
						const tgtCidr = tgt?.subnet || tgt?.cidr || (typeof tgt === 'string' ? tgt : null)
						if (!tgtCidr || tgtCidr === srcCidr) continue
						links.push({ id: `link_${linkCounter++}`, fromId: srcCidr, toId: tgtCidr, kind: 'admin-subnet-subnet' })
					}
				}

				// Finalize
				this.topology = { peers: peersMeta, subnets: subnetsMeta, links: links.map(l => ({ id: l.id, fromId: l.fromId, toId: l.toId, kind: l.kind, serviceName: (l as any).serviceName })) }
				// Pass through rx/tx/lastHandshake so the network store can update live stats
				useNetworkStore().applyBackendTopology({ peers: peersMeta.map(p=> ({
					id: p.id,
					name: p.name,
					ip: p.ip,
					subnetId: p.subnetId,
					x: p.x,
					y: p.y,
					services: p.services,
					host: p.host,
					presharedKey: p.presharedKey,
					publicKey: p.publicKey,
					rx: p.rx,
					tx: p.tx,
					lastHandshake: p.lastHandshake
				})), subnets: subnetsMeta, links })
				// Notify canvas to force an immediate redraw (initial real data)
				window.dispatchEvent(new CustomEvent('topology-updated'))
				this.lastFetchedAt = Date.now()
				// Mark that we have fetched real data at least once and kick off coord pushing if not running
				if (!this.hasFetchedOnce) {
					this.hasFetchedOnce = true
					if (!this.coordPushId) this.startCoordinatePushing(this.pollingIntervalMs)
				}
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

			// subnet_to_subnet_links: dict subnetCIDR -> [Subnet]
			const subnet_to_subnet_links: Record<string, any[]> = {}
			;(function buildSubnetToSubnet(){
				function pairKey(a:string,b:string){ return a < b ? `${a}::${b}` : `${b}::${a}` }
				const seen = new Set<string>()
				for (const l of netStore.links.filter(l=> l.kind==='subnet-subnet')){
					const a = netStore.subnets.find(s=> s.id===l.fromId)
					const b = netStore.subnets.find(s=> s.id===l.toId)
					if (!a || !b) continue
					const pk = pairKey(a.cidr, b.cidr); if (seen.has(pk)) continue; seen.add(pk)
					const arrA = subnet_to_subnet_links[a.cidr] || (subnet_to_subnet_links[a.cidr] = [])
					arrA.push({ subnet: b.cidr, name: b.name, description: b.description, x: b.x, y: b.y, width: b.width, height: b.height, rgba: (b as any).rgba })
					const arrB = subnet_to_subnet_links[b.cidr] || (subnet_to_subnet_links[b.cidr] = [])
					arrB.push({ subnet: a.cidr, name: a.name, description: a.description, x: a.x, y: a.y, width: a.width, height: a.height, rgba: (a as any).rgba })
				}
			})()

			// subnet_to_service_links: dict subnetCIDR -> [Service]
			const subnet_to_service_links: Record<string, any[]> = {}
			for (const l of netStore.links.filter(l=> l.kind==='subnet-service')){
				const subnet = netStore.subnets.find(s=> s.id===l.toId) || netStore.subnets.find(s=> s.id===l.fromId)
				const svcName = (l as any).serviceName as string | undefined
				if (!subnet || !svcName) continue
				// Find service definition (from services map we built above if available)
				const svcDef = services[svcName] || (function(){
					// Fallback: attempt to build from host peer services
					const host = netStore.peers.find(p=> (p.services||{})[svcName])
					const svc = host?.services?.[svcName]
					return svc ? { name: svcName, department: (svc as any).department, port: (svc as any).port, description: (svc as any).description || '' } : undefined
				})()
				if (!svcDef) continue
				const arr = subnet_to_service_links[subnet.cidr] || (subnet_to_service_links[subnet.cidr] = [])
				// Ensure uniqueness by name
				if (!arr.some((s:any)=> (s && s.name) === svcDef.name)) arr.push(svcDef)
			}

			return { subnets, peers, services, p2p_links, service_links, subnet_links, subnet_to_subnet_links, subnet_to_service_links }
		},
		// Create subnet helper (legacy endpoints retained if still active backend-side)
		async createSubnet(subnet: string, name: string, description: string, x:number, y:number, width:number, height:number, rgba:number){
			try { this.lastError=null; await getClient().post('/api/subnet/create',{subnet,name,description,x,y,width,height,rgba}); return true } catch(e:any){ this.lastError = e?.message || 'Failed to create subnet'; return false }
		},
		async connectPeerToSubnet(username: string, subnetCidr: string){
			try { this.lastError=null; await getClient().post('/api/subnet/connect', null, { params:{ username, subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect peer to subnet'; return false }
		},
		async connectAdminPeerToSubnet(adminUsername: string, subnetCidr: string){
			try { this.lastError=null; await getClient().post('/api/subnet/admin/connect', null, { params:{ admin_username: adminUsername, subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect admin peer to subnet'; return false }
		},
		async disconnectPeerFromSubnet(username: string, subnetCidr: string){
			try { this.lastError=null; await getClient().delete('/api/subnet/disconnect', { params:{ username, subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect peer from subnet'; return false }
		},
		async disconnectAdminPeerFromSubnet(adminUsername: string, subnetCidr: string){
			try { this.lastError=null; await getClient().delete('/api/subnet/admin/disconnect', { params:{ admin_username: adminUsername, subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect admin peer from subnet'; return false }
		},
		async connectPeers(peer1: string, peer2: string){
			try { this.lastError=null; await getClient().post('/api/peer/connect', null, { params:{ peer1_username: peer1, peer2_username: peer2 }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect peers'; return false }
		},
		async disconnectPeers(peer1: string, peer2: string){
			try { this.lastError=null; await getClient().delete('/api/peer/disconnect', { params:{ peer1_username: peer1, peer2_username: peer2 }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect peers'; return false }
		},
		async connectAdminPeerToPeer(adminUsername: string, peerUsername: string){
			try { this.lastError=null; await getClient().post('/api/peer/admin/peer/connect', null, { params:{ admin_username: adminUsername, peer_username: peerUsername }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to create admin peer link'; return false }
		},
		async disconnectAdminPeerFromPeer(adminUsername: string, peerUsername: string){
			try { this.lastError=null; await getClient().delete('/api/peer/admin/peer/disconnect', { params:{ admin_username: adminUsername, peer_username: peerUsername }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to remove admin peer link'; return false }
		},
		async connectPeerToService(username: string, serviceName: string){
			try { this.lastError=null; await getClient().post('/api/service/connect', null, { params:{ username, service_name: serviceName }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect peer to service'; return false }
		},
		async disconnectPeerFromService(username: string, serviceName: string){
			try { this.lastError=null; await getClient().delete('/api/service/disconnect', { params:{ username, service_name: serviceName }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect peer from service'; return false }
		},
		async connectSubnetToSubnet(subnetA: string, subnetB: string){
			try { this.lastError=null; await getClient().post('/api/network/subnets/connect', null, { params:{ subnet_a: subnetA, subnet_b: subnetB }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect subnets'; return false }
		},
		async connectAdminSubnetToSubnet(adminSubnet: string, subnet: string){
			// Directed (adminSubnet -> subnet) admin privilege link
			try { this.lastError=null; await getClient().post('/api/network/admin/connect_subnets', null, { params:{ admin_subnet: adminSubnet, subnet }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect admin subnets'; return false }
		},
		async disconnectSubnetFromSubnet(subnetA: string, subnetB: string){
			try { this.lastError=null; await getClient().delete('/api/network/subnets/connect', { params:{ subnet_a: subnetA, subnet_b: subnetB }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect subnets'; return false }
		},
		async disconnectAdminSubnetFromSubnet(adminSubnet: string, subnet: string){
			try { this.lastError=null; await getClient().delete('/api/network/admin/disconnect_subnets', { params:{ admin_subnet: adminSubnet, subnet }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect admin subnet link'; return false }
		},
		async connectSubnetToService(subnetCidr: string, serviceName: string){
			try { this.lastError=null; await getClient().post('/api/service/subnet/connect', null, { params:{ subnet_address: subnetCidr, service_name: serviceName }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to connect subnet to service'; return false }
		},
		async disconnectSubnetFromService(subnetCidr: string, serviceName: string){
			try { this.lastError=null; await getClient().delete('/api/service/subnet/disconnect', { params:{ subnet_address: subnetCidr, service_name: serviceName }}); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to disconnect subnet from service'; return false }
		},
		async fetchPeerConfig(username: string){
			try { this.lastError=null; const { data } = await getClient().get<{configuration:string}>('/api/peer/config', { params:{ username } }); return data.configuration } catch(e:any){ this.lastError = e?.message || 'Failed to fetch config'; return null }
		},
		// Delete subnet only (keep peers; memberships and links removed server-side)
		async deleteSubnet(subnetCidr: string){
			try { this.lastError=null; await getClient().delete('/api/subnet/', { params:{ subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to delete subnet'; return false }
		},
		// Delete subnet and all peers inside
		async deleteSubnetWithPeers(subnetCidr: string){
			try { this.lastError=null; await getClient().delete('/api/subnet/with_peers', { params:{ subnet: subnetCidr } }); await this.fetchTopology(true); return true } catch(e:any){ this.lastError = e?.message || 'Failed to delete subnet with peers'; return false }
		},
		// Delete a peer by username
		async deletePeer(username: string){
			try {
				this.lastError = null
				// Use trailing slash to avoid 307 redirect to /peer/ which can bypass the dev proxy
				await getClient().delete('/api/peer/', { params: { username } })
				await this.fetchTopology(true)
				return true
			} catch(e:any){ this.lastError = e?.message || 'Failed to delete peer'; return false }
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
		async createService(username: string, serviceName: string, department: string, port: number, description: string){
			try {
				this.lastError = null
				const { data } = await getClient().post<{ message: string }>('/api/service/create', null, { params: { service_name: serviceName, department, username, port, description } })
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
			// On first successful fetch, we'll start coordinate pushing
			this.fetchTopology(true)
			this.pollingId = window.setInterval(()=> this.fetchTopology(true), intervalMs)
		},
		stopTopologyPolling(){
			if (this.pollingId){ clearInterval(this.pollingId); this.pollingId = null }
			// Optionally stop coordinate pushing when polling stops
			this.stopCoordinatePushing()
		},
		async fetchSubnet(_subnetId: string) {
			// Endpoint not yet adapted to new raw structure; placeholder for future expansion
		},
		clearError() { this.lastError = null },
		async getNftTableRules(){
			try { this.lastError=null; const { data } = await getClient().get<{ nft_rules: string[] }>('/api/network/nft_rules'); return data.nft_rules || [] } catch(e:any){ this.lastError = e?.message || 'Failed to fetch nftables rules'; return [] }
		}
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
