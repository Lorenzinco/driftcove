import { reactive } from 'vue';
import type { Peer, Subnet, Link, Tool } from '@/types/network';
import { cidrContains, ipInCidr } from '@/utils/net';

export interface InteractionState {
  hoverPeerId: string | null;
  hoverSubnetId: string | null;
  selection: { type: 'peer' | 'subnet' | 'link'; id: string } | null;
  tool: Tool;
}

export interface DragState { active:boolean; type:''|'peer'|'subnet'; id:string; offsetX:number; offsetY:number; containedPeers:string[]; containedSubnets:string[] }

export interface ResizeDrag { active:boolean; id:string; edge:string; left:number; top:number; right:number; bottom:number; minW:number; minH:number }

// Use getter functions so that if Pinia replaces array instances (e.g. applyBackendTopology),
// hit tests always see the latest collections instead of stale captured arrays.
export function createInteractions(getPeers:()=>Peer[], getSubnets:()=>Subnet[], getLinks:()=>Link[], getZoom:()=>number) {
  const drag: DragState = reactive({ active:false, type:'', id:'', offsetX:0, offsetY:0, containedPeers:[], containedSubnets:[] }) as DragState;
  const resizeDrag: ResizeDrag = reactive({ active:false, id:'', edge:'', left:0, top:0, right:0, bottom:0, minW:160, minH:120 }) as ResizeDrag;

  function hitTestPeer(pt:{x:number;y:number}) {
    const peers = getPeers();
    for (let i = peers.length - 1; i >= 0; i--) {
      const n:any = peers[i];
      if (Math.hypot(pt.x - n.x, pt.y - n.y) <= 24) return n;
    }
    return null;
  }
  function hitTestSubnet(pt:{x:number;y:number}) {
    const subnets = getSubnets();
    for (let i=subnets.length-1;i>=0;i--) {
      const s = subnets[i];
      const left = s.x - s.width/2, right = s.x + s.width/2, top = s.y - s.height/2, bottom = s.y + s.height/2;
      if (pt.x>=left && pt.x<=right && pt.y>=top && pt.y<=bottom) return s;
    }
    return null;
  }

  function hitTestLink(pt:{x:number;y:number}) {
    const peers = getPeers(); const subnets = getSubnets(); const links = getLinks();
    const threshold = 8 / getZoom();
    function distPointToSeg(px:number,py:number, ax:number,ay:number,bx:number,by:number){
      const vx=bx-ax, vy=by-ay; const wx=px-ax, wy=py-ay; const c1 = vx*wx + vy*wy; if (c1<=0) return Math.hypot(px-ax,py-ay);
      const c2 = vx*vx+vy*vy; if (c2<=c1) return Math.hypot(px-bx,py-by); const t=c1/c2; const ix=ax+vx*t, iy=ay+vy*t; return Math.hypot(px-ix,py-iy);
    }
    for (let i=links.length-1;i>=0;i--){
      const l = links[i];
      if ((l as any).kind === 'membership') {
        // Peer to subnet edge
        const peer:any = peers.find(p=> p.id===l.fromId) || peers.find(p=> p.id===l.toId);
        const subnet = subnets.find(s=> s.id===l.toId) || subnets.find(s=> s.id===l.fromId);
        if (!peer || !subnet) continue;
        // Ignore membership link if it targets the peer's own containing subnet
        if (peer.subnetId && peer.subnetId === subnet.id) continue;
        const cx = subnet.x, cy = subnet.y; const hw = subnet.width/2, hh = subnet.height/2;
        const vx = peer.x - cx, vy = peer.y - cy;
        let Bx = cx, By = cy;
        if (vx === 0 && vy === 0){ Bx = cx + hw; By = cy; }
        else { const sx = Math.abs(vx)/(hw||1e-6), sy = Math.abs(vy)/(hh||1e-6); const t = Math.max(sx,sy)||1; Bx = cx + vx/t; By = cy + vy/t; }
        const d = distPointToSeg(pt.x, pt.y, peer.x, peer.y, Bx, By);
        if (d <= threshold) return l;
        continue;
      }
      const a = peers.find(p=>p.id===l.fromId); const b = peers.find(p=>p.id===l.toId); if (!a||!b) continue;
      const d = distPointToSeg(pt.x, pt.y, a.x, a.y, b.x, b.y);
      if (d <= threshold) return l;
    }
    return null;
  }

  function edgeAtPoint(sub:Subnet, pt:{x:number;y:number}) {
    const left = sub.x - sub.width/2, right = sub.x + sub.width/2, top = sub.y - sub.height/2, bottom = sub.y + sub.height/2;
    const threshold = 8 / getZoom();
    let vertical=''; let horizontal='';
    if (pt.x>=left-threshold && pt.x<=left+threshold && pt.y>=top-threshold && pt.y<=bottom+threshold) horizontal='w';
    if (pt.x>=right-threshold && pt.x<=right+threshold && pt.y>=top-threshold && pt.y<=bottom+threshold) horizontal=horizontal||'e';
    if (pt.y>=top-threshold && pt.y<=top+threshold && pt.x>=left-threshold && pt.x<=right+threshold) vertical='n';
    if (pt.y>=bottom-threshold && pt.y<=bottom+threshold && pt.x>=left-threshold && pt.x<=right+threshold) vertical=vertical||'s';
    const combo = (vertical+horizontal) as any;
    if (['n','s','e','w'].includes(combo)) return combo;
    if (vertical && horizontal) return combo;
    return '';
  }

  function subnetContains(a:string,b:string){ return cidrContains(a,b); }

  function enforceSubnetHierarchy() {
    const subnets = getSubnets();
    for (const child of subnets) {
      const parents = subnets.filter(p=>p.id!==child.id && subnetContains(p.cidr, child.cidr));
      if (!parents.length) continue;
      let left=-Infinity, top=-Infinity, right=Infinity, bottom=Infinity;
      const margin = 20;
      for (const p of parents) {
        const pl = p.x - p.width/2 + margin;
        const pr = p.x + p.width/2 - margin;
        const pt = p.y - p.height/2 + margin;
        const pb = p.y + p.height/2 - margin;
        if (pl>left) left=pl; if (pt>top) top=pt; if (pr<right) right=pr; if (pb<bottom) bottom=pb;
      }
      if (left<right && top<bottom) {
        if (child.x<left) child.x=left; if (child.x>right) child.x=right;
        if (child.y<top) child.y=top; if (child.y>bottom) child.y=bottom;
      }
    }
  }

  function mostSpecificSubnetForIp(ip:string) {
    const subnets = getSubnets();
    const candidates = subnets.filter(s=> ipInCidr(ip, s.cidr));
    if (!candidates.length) return null;
    return candidates.sort((a,b)=> (parseInt(b.cidr.split('/')[1]||'0') - parseInt(a.cidr.split('/')[1]||'0')))[0];
  }

  function clampPeerToSubnet(peer:any) {
    if (peer.ip) {
      const match = mostSpecificSubnetForIp(peer.ip);
      if (match && peer.subnetId !== match.id) peer.subnetId = match.id;
    }
    if (!peer.subnetId) return;
    const subnets = getSubnets();
    const s = subnets.find(s=>s.id===peer.subnetId); if (!s) return;
    const margin = 26;
    const left = s.x - s.width/2 + margin;
    const right = s.x + s.width/2 - margin;
    const top = s.y - s.height/2 + margin;
    const bottom = s.y + s.height/2 - margin;
    if (peer.x<left) peer.x=left; if (peer.x>right) peer.x=right; if (peer.y<top) peer.y=top; if (peer.y>bottom) peer.y=bottom;
  }

  return { drag, resizeDrag, hitTestPeer, hitTestSubnet, hitTestLink, edgeAtPoint, enforceSubnetHierarchy, clampPeerToSubnet };
}
