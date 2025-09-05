import { defineStore } from 'pinia'
import type { Peer, Subnet, Link, Tool, ServiceInfo } from '@/types/network'

// Local helper type for service info (embedded inside Peer.services)

function uid(prefix = 'id') { return prefix + Math.random().toString(36).slice(2, 9) }

export const useNetworkStore = defineStore('network', {
    state: () => ({
    peers: [ { id: uid('p_'), name: 'Peer 1', ip: '10.0.1.10', subnetId: null, x: 540, y: 300, allowed: true, services: {}, host: false } as Peer ],
        subnets: [ { id: uid('s_'), name: 'Office LAN', cidr: '10.0.1.0/24', x: 520, y: 300, width: 360, height: 240, rgba: 0x00FF00E5 } as Subnet ],
        links: [] as Link[],


    // selection.id semantics for type==='link': stores a pair key "aId::bId" (sorted) representing ALL links between those two peers
    selection: null as null | { type: 'peer' | 'subnet' | 'link', name:string, id: string },
        tool: 'select' as Tool,


    pan: { x: 0, y: 0, dragging: false, sx: 0, sy: 0 },
    zoom: 1,


        grid: true,
        hoverPeerId: null as string | null,
        hoverSubnetId: null as string | null,


    inspectorOpen: true,
    peerDetailsRequestId: null as string | null,
    peerDetailsRequestVersion: 0,
    }),

    getters: {
        selectedPeer(state) {
            return state.selection?.type === 'peer' ? state.peers.find(p => p.id === state.selection!.id) || null : null
        },
        selectedSubnet(state) {
            return state.selection?.type === 'subnet' ? state.subnets.find(s => s.id === state.selection!.id) || null : null
        },
        // All links between a selected peer pair (if selection.type==='link')
        selectedLinks(state) {
            if (state.selection?.type !== 'link') return [] as Link[];
            const key = state.selection.id;
            function pairKey(a:string,b:string){ return a < b ? `${a}::${b}` : `${b}::${a}`; }
            return state.links.filter(l => pairKey(l.fromId,l.toId) === key);
        },
        // Backwards compatibility: first link in selection (if any)
        selectedLink(): Link | null {
            // @ts-ignore access root state via this
            const arr: Link[] = (this as any).selectedLinks;
            return arr.length ? arr[0] : null;
        },
    },

    actions: {
        toggleInspector() { this.inspectorOpen = !this.inspectorOpen },
        openPeerDetails(peerId: string) {
            this.selection = { type: 'peer', id: peerId, name: this.peers.find(p=>p.id===peerId)?.name || 'Peer' }
            this.peerDetailsRequestId = peerId
            this.peerDetailsRequestVersion++
        },
        closePeerDetails() { /* hook for future side-effects */ },

    // (Peer add functionality removed per latest requirements)

        addSubnetAt(x: number, y: number, rgba:number = 0x00FF00E5) {
            const id = uid('s_')
            this.subnets.push({ id, name: 'Subnet', cidr: '10.0.0.0/24', x, y, width: 320, height: 200, rgba })
            this.selection = { type: 'subnet', id, name: 'Subnet' }
            this.tool = 'select'
        },


        deleteSelection() {
            if (!this.selection) return;
            if (this.selection.type === 'peer') {
                this.links = this.links.filter(l => l.fromId !== this.selection!.id && l.toId !== this.selection!.id);
                this.peers = this.peers.filter(p => p.id !== this.selection!.id);
            } else if (this.selection.type === 'subnet') {
                this.peers.forEach(p => { if (p.subnetId === this.selection!.id) p.subnetId = null });
                this.subnets = this.subnets.filter(s => s.id !== this.selection!.id);
            } else if (this.selection.type === 'link') {
                // selection.id is pair key
                const pairKey = this.selection.id;
                function mk(a:string,b:string){ return a < b ? `${a}::${b}` : `${b}::${a}`; }
                this.links = this.links.filter(l => mk(l.fromId,l.toId) !== pairKey);
            }
            this.selection = null;
        },


        assignToSubnet(peerId: string, subnetId: string | null) {
            const n = this.peers.find(p => p.id === peerId);
            if (!n) return
            const s = this.subnets.find(s => s.id === subnetId!)
            n.subnetId = subnetId || null
            if (s) {
                const margin = 40
                const left = s.x - s.width / 2 + margin
                const right = s.x + s.width / 2 - margin
                const top = s.y - s.height / 2 + margin
                const bottom = s.y + s.height / 2 - margin
                n.x = left + Math.random() * (right - left)
                n.y = top + Math.random() * (bottom - top)
            }
        },

    applyBackendTopology(payload: { subnets: Array<{ id: string; name: string; cidr: string; description?: string; x?: number; y?: number; width?: number; height?: number; rgba?: number }>; peers: Array<{ id: string; name: string; ip: string; subnetId: string | null; x?: number; y?: number; services?: Record<string, ServiceInfo>; host?: boolean; presharedKey?: string; publicKey?: string }>; links: Link[] }) {
            const oldSelection = this.selection

            // --- Subnets ---
            const incomingSubnetIds = new Set(payload.subnets.map(s => s.id))
            // Update or remove
            this.subnets = this.subnets.filter(existing => {
                if (!incomingSubnetIds.has(existing.id)) return false // remove missing
                const incoming = payload.subnets.find(s => s.id === existing.id)!
                if (existing.name !== incoming.name) existing.name = incoming.name
                if (existing.cidr !== incoming.cidr) existing.cidr = incoming.cidr
                if (incoming.description !== undefined && existing.description !== incoming.description) existing.description = incoming.description
                // Intentionally do NOT overwrite existing.rgba so in-progress user color edits aren't reset by polling.
                // (Treat color like x,y,width,height: only set on initial add below.)
                return true
            })
            // Add new
            const existingSubnets = this.subnets
            for (const inc of payload.subnets) {
                if (!existingSubnets.find(s => s.id === inc.id)) {
                    // Use backend provided coordinates if present; else layout heuristic
                    let width = inc.width ?? 420
                    let height = inc.height ?? 260
                    let x = inc.x ?? 520
                    let y = inc.y ?? 300
                    if ((inc.x === undefined || inc.y === undefined) && existingSubnets.length) {
                        const rightMost = existingSubnets.reduce((a,b)=> (a.x + a.width/2 > b.x + b.width/2 ? a : b))
                        x = rightMost.x + rightMost.width/2 + width/2 + 120
                        y = rightMost.y
                    }
                    let rgba = inc.rgba
                    if (rgba != null) rgba = (Number(rgba) >>> 0) & 0xFFFFFFFF
                    this.subnets.push({ id: inc.id, name: inc.name, cidr: inc.cidr, description: inc.description, x, y, width, height, rgba })
                }
            }

            // --- Peers ---
            // Allowed rule (updated): a peer is allowed ONLY if it has a membership link to its own subnet.
            // (Previously: any link qualified. Now restrict to membership kind linking peer -> subnetId.)
            const peerAllowed: Record<string, boolean> = {}
            const incomingPeerIds = new Set(payload.peers.map(p => p.id))
            // Build quick lookup of membership links for efficiency
            for (const l of payload.links) {
                if ((l as any).kind === 'membership') {
                    // Expect pattern: fromId = peerId, toId = subnetId
                    peerAllowed[l.fromId] = true
                }
            }
            // (incomingPeerIds defined above)
            // Update or remove peers
            this.peers = this.peers.filter(existing => {
                if (!incomingPeerIds.has(existing.id)) return false
                const incoming = payload.peers.find(p => p.id === existing.id)!
                if (existing.name !== incoming.name) existing.name = incoming.name
                if (existing.ip !== incoming.ip) existing.ip = incoming.ip
                if (existing.subnetId !== incoming.subnetId) {
                    existing.subnetId = incoming.subnetId
                    // DO NOT change x,y per requirement
                }
                existing.services = incoming.services || {}
                // Derive host only from services map (at least one service with numeric port)
                existing.host = Object.values(existing.services||{}).some((s:any)=> s && typeof s.port==='number' && !isNaN(s.port))
                if (incoming.presharedKey && existing.presharedKey !== incoming.presharedKey) existing.presharedKey = incoming.presharedKey
                if (incoming.publicKey && existing.publicKey !== incoming.publicKey) existing.publicKey = incoming.publicKey
                existing.allowed = !!peerAllowed[existing.id]
                return true
            })
            for (const inc of payload.peers) {
                if (!this.peers.find(p => p.id === inc.id)) {
                    // Use backend coordinates if provided, else derive
                    let x = inc.x ?? 300 + Math.random()*200
                    let y = inc.y ?? 300 + Math.random()*200
                    if ((inc.x === undefined || inc.y === undefined) && inc.subnetId) {
                        const s = this.subnets.find(s => s.id === inc.subnetId)
                        if (s) {
                            const margin = 60
                            const left = s.x - s.width/2 + margin
                            const top = s.y - s.height/2 + margin
                            const right = s.x + s.width/2 - margin
                            const bottom = s.y + s.height/2 - margin
                            x = left + Math.random()*(right-left)
                            y = top + Math.random()*(bottom-top)
                        }
                    }
                    const services = inc.services || {}
                    const host = Object.values(services).some((s:any)=> s && typeof s.port==='number' && !isNaN(s.port))
                    this.peers.push({ id: inc.id, name: inc.name, ip: inc.ip, subnetId: inc.subnetId, x, y, allowed: !!peerAllowed[inc.id], services, host, presharedKey: inc.presharedKey, publicKey: inc.publicKey })
                }
            }

            // --- Links --- (replace wholesale; link ids deterministic so selection can persist)
            this.links = payload.links

            if (oldSelection) {
                if (oldSelection.type === 'link') {
                    function pairKey(a:string,b:string){ return a < b ? `${a}::${b}` : `${b}::${a}`; }
                    let key = oldSelection.id;
                    // Legacy case: selection stored a single link id; translate to pairKey if match.
                    const match = this.links.find(l => l.id === key);
                    if (match) key = pairKey(match.fromId, match.toId);
                    const exists = this.links.some(l => pairKey(l.fromId,l.toId) === key);
                    this.selection = exists ? { ...oldSelection, id: key, name: 'Links' } : null;
                } else {
                    const stillExists = (
                        oldSelection.type === 'peer' && this.peers.some(p => p.id === oldSelection.id) ||
                        oldSelection.type === 'subnet' && this.subnets.some(s => s.id === oldSelection.id)
                    );
                    this.selection = stillExists ? oldSelection : null;
                }
            }
        },
        sanitizeColors(){
            for (const s of this.subnets){
                if ((s as any).rgba != null){ (s as any).rgba = (Number((s as any).rgba) >>> 0) & 0xFFFFFFFF }
            }
        }
    },
})