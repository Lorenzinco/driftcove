import type { PanZoom, Peer, Subnet, Link } from '@/types/network';

export interface RenderDeps {
  peers: Peer[];
  subnets: Subnet[];
  links: Link[];
  panzoom: PanZoom;
  theme?: { colors: { peer: string; subnet: string; link: string } };
  ui?: {
    hoverPeerId?: string|null;
    hoverSubnetId?: string|null;
  hoverLinkId?: string|null;
    selection?: { type:'peer'|'subnet'|'link'; id:string } | null;
    tool?: string;
    connect?: { active:boolean; fromPeerId?:string; ghostTo?: { x:number; y:number } | null };
    ghostSubnet?: { active:boolean; x:number; y:number; width:number; height:number } | null;
  }
}

export function createRenderer(deps: () => RenderDeps & { grid?: boolean }) {
  let frame = 0; // animation frame counter
  let lastTs = 0;
  let invalidateFn: (()=>void)|null = null;
  function setInvalidator(fn: ()=>void){ invalidateFn = fn }
  function toScreen(wx:number, wy:number) {
    const { panzoom } = deps();
    return { x: wx * panzoom.zoom + panzoom.x, y: wy * panzoom.zoom + panzoom.y };
  }
  function toWorld(sx:number, sy:number) {
    const { panzoom } = deps();
    return { x: (sx - panzoom.x) / panzoom.zoom, y: (sy - panzoom.y) / panzoom.zoom };
  }

  function clear(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0,0,w,h);
  }

  // glue: call the individual passes you’ll split out
  function drawGrid(ctx:CanvasRenderingContext2D, w:number, h:number) {
    const { panzoom } = deps();
    const step = 40 * panzoom.zoom;
    const ox = panzoom.x % step; const oy = panzoom.y % step;
    ctx.save(); ctx.strokeStyle='rgba(255,255,255,0.06)'; ctx.lineWidth=1;
    for (let x=ox; x<w; x+=step){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,h); ctx.stroke(); }
    for (let y=oy; y<h; y+=step){ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke(); }
    ctx.restore();
  }

  function drawSubnets(ctx:CanvasRenderingContext2D){
    const { subnets, panzoom, theme, ui } = deps();
    const color = theme?.colors.subnet || '#7CF29A';
    for (const s of subnets){
      const tl = toScreen(s.x - s.width/2, s.y - s.height/2);
      const w = s.width * panzoom.zoom; const h = s.height * panzoom.zoom;
  ctx.save(); ctx.beginPath(); ctx.rect(tl.x, tl.y, w, h);
  // Subnet fill color: backend supplies 0xRRGGBBAA. Convert to rgba(). Also set stroke to same RGB with full alpha.
  let fillStyle = 'rgba(124,242,154,0.07)'; let strokeStyle = color;
  const raw = (s as any).rgba;
  if (typeof raw === 'number') {
    const r = (raw >> 24) & 0xFF;
    const g = (raw >> 16) & 0xFF;
    const b = (raw >> 8) & 0xFF;
    const aByte = raw & 0xFF;
    const a = +(aByte / 255).toFixed(3);
    fillStyle = `rgba(${r},${g},${b},${a})`;
    strokeStyle = `rgba(${r},${g},${b},1)`;
  }
  ctx.fillStyle=fillStyle; ctx.fill();
  ctx.strokeStyle=strokeStyle; ctx.lineWidth=2; ctx.setLineDash([8,6]); ctx.stroke(); ctx.setLineDash([]);
      // Always show subnet name (if provided). Show CIDR only when hovered.
      const hasName = !!(s as any).name && (s as any).name.trim().length>0;
      const nameLabel = hasName ? (s as any).name : '';
      ctx.fillStyle='rgba(255,255,255,0.9)'; ctx.font='600 14px Roboto, sans-serif'; ctx.textAlign='left'; ctx.textBaseline='bottom';
      if (hasName) {
        // Base name always visible
        ctx.fillText(nameLabel, tl.x + 8, tl.y - 6);
        if (ui?.hoverSubnetId === s.id) {
          // Append CIDR to right of name (or below) – here appended inline unless name equals CIDR.
          ctx.save();
          ctx.font='500 12px Roboto, sans-serif';
          const nameWidth = ctx.measureText(nameLabel + ' ').width;
          ctx.fillStyle='rgba(255,255,255,0.75)';
          ctx.fillText(`(${s.cidr})`, tl.x + 8 + nameWidth, tl.y - 6);
          ctx.restore();
        }
      } else if (ui?.hoverSubnetId === s.id) {
        // No name set: only show CIDR on hover per requirement
        ctx.fillText(s.cidr, tl.x + 8, tl.y - 6);
      }
      ctx.restore();
    }
  }

  function drawLinks(ctx:CanvasRenderingContext2D, ts:number){
  const { links, peers, ui } = deps();
  // frame increment moved to draw() so all passes share same timing
    interface Agg { a: Peer; b: Peer; p2p: boolean; services: Set<string>; serviceHostId?: string; linkIds: string[]; repId: string }
    const byPair: Record<string, Agg> = {};
    function pairKey(aId:string,bId:string){ return aId < bId ? `${aId}::${bId}` : `${bId}::${aId}`; }
    for (const l of links){
      if (l.kind==='membership') continue;
      const a = peers.find(p=>p.id===l.fromId); const b = peers.find(p=>p.id===l.toId); if (!a||!b) continue;
      const key = pairKey(a.id,b.id);
      let agg = byPair[key]; if (!agg) agg = byPair[key] = { a, b, p2p:false, services:new Set(), linkIds:[], repId:l.id };
      agg.linkIds.push(l.id);
      if (l.kind==='p2p'){ agg.p2p = true; if (!agg.repId || agg.services.size===0) agg.repId = l.id; }
      else if (l.kind==='service'){ if (l.serviceName) agg.services.add(l.serviceName); if (!agg.serviceHostId) agg.serviceHostId = l.fromId; if (!agg.p2p) agg.repId = l.id; }
    }
    ctx.save(); ctx.lineWidth=2; let anyAnim=false;
    for (const key of Object.keys(byPair)){
      const agg = byPair[key]; const { a, b } = agg; const A = toScreen(a.x,a.y); const B = toScreen(b.x,b.y);
      const isMixed = agg.p2p && agg.services.size>0;
      const isServiceOnly = !agg.p2p && agg.services.size>0;
      const isP2POnly = agg.p2p && agg.services.size===0;
      // Stroke style
      if (isMixed){ ctx.strokeStyle='#FFC107'; }
      else if (isServiceOnly){ const grad = ctx.createLinearGradient(A.x,A.y,B.x,B.y); grad.addColorStop(0,'rgba(33,150,243,0.9)'); grad.addColorStop(1,'rgba(33,150,243,0.15)'); ctx.strokeStyle=grad; }
      else { ctx.strokeStyle='#4CAF50'; }
      ctx.beginPath(); ctx.moveTo(A.x,A.y); ctx.lineTo(B.x,B.y); ctx.stroke();
  // selection.id for links now stores pairKey(a,b); compute once
  const pair = pairKey(a.id,b.id);
  const active = agg.linkIds.some(id => ui?.hoverLinkId===id) || (ui?.selection?.type==='link' && ui.selection.id===pair) || ui?.hoverPeerId===a.id || ui?.hoverPeerId===b.id;
      if (active){
        const dx=B.x-A.x, dy=B.y-A.y; const len=Math.hypot(dx,dy)||1; const ux=dx/len, uy=dy/len; const t=(frame/60)%1;
        const drawDot=(pos:number,color:string,r=4)=>{ const px=A.x+ux*len*pos, py=A.y+uy*len*pos; ctx.save(); ctx.beginPath(); ctx.fillStyle=color; ctx.shadowColor=color; ctx.shadowBlur=6; ctx.arc(px,py,r,0,Math.PI*2); ctx.fill(); ctx.restore(); };
        if (isServiceOnly){
          // Maintain original directional flow
          drawDot(t,'rgba(255,255,255,0.85)');
        } else if (isP2POnly || isMixed){
          // Slower triangle wave 0->1->0 bounce (2s cycle instead of 1s)
          const tbounce = (frame/120)%1; // half speed vs service flow
          const tri = tbounce < 0.5 ? tbounce*2 : (1 - (tbounce-0.5)*2); // 0..1..0
          const pos = tri;
          const color = 'rgba(255,255,255,0.9)';
          drawDot(pos,color,4.5); // single bouncing projectile (no trailing echo)
        }
        anyAnim=true;
      }
      if (active){
        let lines:string[]=[];
        if (isMixed) lines=['p2p ⚠'];
        else if (isServiceOnly) lines=Array.from(agg.services.values()).sort();
        else lines=['p2p'];
        const mx=(A.x+B.x)/2, my=(A.y+B.y)/2; ctx.save(); ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.font='600 12px Roboto, sans-serif';
        const padX=8, padY=6, lineH=14; const maxW=Math.max(...lines.map(l=>ctx.measureText(l).width)); const boxH=lineH*lines.length + (lines.length-1)*2 + padY*2; const boxW=maxW + padX*2;
        ctx.beginPath(); (ctx as any).roundRect?.(mx-boxW/2, my-boxH/2, boxW, boxH, 5);
        ctx.fillStyle='rgba(0,0,0,0.65)'; ctx.fill();
        ctx.strokeStyle = isMixed? '#FFC107' : (isServiceOnly? '#2196F3':'#4CAF50'); ctx.lineWidth=1; ctx.stroke();
        ctx.fillStyle='#fff'; lines.forEach((ln,i)=> ctx.fillText(ln, mx, my - boxH/2 + padY + lineH/2 + i*(lineH+2)) );
        ctx.restore();
      }
    }
    ctx.restore(); if (anyAnim && invalidateFn) requestAnimationFrame(()=> invalidateFn && invalidateFn());
  }

  function drawMembershipLinks(ctx:CanvasRenderingContext2D){
    const { links, peers, subnets, ui } = deps();
    let anyAnim = false;
    for (const l of links){
      if ((l as any).kind !== 'membership') continue;
      // Expect l.fromId = peerId, l.toId = subnetId; tolerate reversed
      let peer = peers.find(p=> p.id===l.fromId);
      let subnet = subnets.find(s=> s.id===l.toId);
      if (!peer || !subnet){
        peer = peers.find(p=> p.id===l.toId) || peer;
        subnet = subnets.find(s=> s.id===l.fromId) || subnet;
      }
      if (!peer || !subnet) continue;
      // Do not draw membership links to the peer's own containing subnet
      if ((peer as any).subnetId && (peer as any).subnetId === subnet.id) continue;
      const A = toScreen(peer.x, peer.y);
      // Compute boundary point B on subnet rectangle along ray from center->peer
      const cx = subnet.x, cy = subnet.y; const hw = subnet.width/2, hh = subnet.height/2;
      const vx = peer.x - cx, vy = peer.y - cy;
      let Bx = cx, By = cy;
      if (vx === 0 && vy === 0){ Bx = cx + hw; By = cy; }
      else {
        const sx = Math.abs(vx) / (hw || 1e-6);
        const sy = Math.abs(vy) / (hh || 1e-6);
        const t = Math.max(sx, sy) || 1; // scale to border
        Bx = cx + vx / t; By = cy + vy / t;
      }
      const B = toScreen(Bx, By);
      // Color from subnet rgba
      let strokeStyle = '#7CF29A';
      const raw = (subnet as any).rgba;
      if (typeof raw === 'number'){
        const r = (raw >> 24) & 0xFF; const g = (raw >> 16) & 0xFF; const b = (raw >> 8) & 0xFF;
        strokeStyle = `rgba(${r},${g},${b},1)`;
      }
      const active = (ui?.hoverPeerId === peer.id) || (ui?.hoverSubnetId === subnet.id) || (ui?.hoverLinkId === (l as any).id);
      ctx.save();
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 2;
      // Match subnet dash pattern
      ctx.setLineDash([8, 6]);
      // Much slower sliding animation
      ctx.lineDashOffset = active ? -(frame * 0.50) : 0;
      ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
      ctx.restore();
      if (active) anyAnim = true;

  // Hover overlay: show when hovering the link or either endpoint (peer/subnet)
  if (active) {
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
        const label = 'subnet guest';
        ctx.save();
        ctx.font = '600 12px Roboto, sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const padX=8, padY=6; const textW = ctx.measureText(label).width; const boxW = textW + padX*2; const boxH = 14 + padY*2;
        ctx.beginPath(); (ctx as any).roundRect?.(mx - boxW/2, my - boxH/2, boxW, boxH, 5);
        ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fill();
        ctx.strokeStyle = strokeStyle; ctx.lineWidth = 1; ctx.stroke();
        ctx.fillStyle = '#fff'; ctx.fillText(label, mx, my);
        ctx.restore();
      }
    }
    if (anyAnim && invalidateFn) requestAnimationFrame(()=> invalidateFn && invalidateFn());
  }

  function drawPeers(ctx:CanvasRenderingContext2D){
    const { peers, panzoom, theme, ui, links } = deps() as any;
    // Determine problematic peers (participate in at least one mixed p2p + service pair)
    const problematicPeers = new Set<string>();
    (function computeProblematic(){
      interface Agg { a: Peer; b: Peer; p2p: boolean; services: Set<string> }
      const byPair: Record<string, Agg> = {};
      function pairKey(aId:string,bId:string){ return aId < bId ? `${aId}::${bId}` : `${bId}::${aId}`; }
      for (const l of links as Link[]) {
        if (l.kind==='membership') continue;
        const a = peers.find((p:Peer)=>p.id===l.fromId); const b = peers.find((p:Peer)=>p.id===l.toId); if (!a||!b) continue;
        const key = pairKey(a.id,b.id);
        let agg = byPair[key]; if (!agg) agg = byPair[key] = { a, b, p2p:false, services:new Set() };
        if (l.kind==='p2p') agg.p2p = true; else if (l.kind==='service' && l.serviceName) agg.services.add(l.serviceName);
      }
      for (const k of Object.keys(byPair)){
        const agg = byPair[k]; if (agg.p2p && agg.services.size>0){ problematicPeers.add(agg.a.id); problematicPeers.add(agg.b.id); }
      }
    })();

    function drawWifiOffBadge(x:number,y:number,z:number){
      const r = 8 * z; // outer badge radius
      ctx.save();
      // Badge background
      ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2); ctx.fillStyle='#4d4d4d'; ctx.fill();
      ctx.strokeStyle='#7a7a7a'; ctx.lineWidth=1.1*z; ctx.stroke();
      // Upward facing WiFi arcs (smile orientation). Dot anchored near bottom.
      const dotY = y + r*0.45; // push dot toward bottom of badge
      const arcCenterY = y + r*0.25; // slight upward shift so arcs sit above dot
      ctx.strokeStyle='#e4e4e4';
      ctx.lineCap='round';
      const radii = [r-7*z, r-5*z, r-3*z]; // small -> large
      for (let i=0;i<radii.length;i++) {
        const rad = radii[i]; if (rad <= 0) continue;
        ctx.beginPath();
        // Angles 225° to 315° (1.25π to 1.75π) produce an upward opening arc
        ctx.lineWidth = 1.2*z;
        ctx.arc(x, arcCenterY, rad, Math.PI*1.25, Math.PI*1.75);
        ctx.stroke();
      }
      // Origin dot
      ctx.beginPath(); ctx.arc(x, dotY, 1.0*z, 0, Math.PI*2); ctx.fillStyle='#f0f0f0'; ctx.fill();
      // Slash (thinner) to indicate disabled
      ctx.beginPath(); ctx.strokeStyle='#cfcfcf'; ctx.lineWidth=1*z; ctx.moveTo(x - r*0.62, y + r*0.58); ctx.lineTo(x + r*0.62, y - r*0.58); ctx.stroke();
      ctx.restore();
    }
    function drawExclamationBadge(x:number,y:number,z:number){
      const badgeR = 7 * z;
      ctx.save(); ctx.beginPath(); ctx.arc(x, y, badgeR, 0, Math.PI*2);
      ctx.fillStyle = '#d3ad2fff'; ctx.fill();
      ctx.font = `${9*z}px Roboto, sans-serif`; ctx.fillStyle='#fff'; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText('!', x, y+0.5*z);
      ctx.restore();
    }
    // Build set of peers having at least one non-membership link (p2p/service) — retained in case future styling needs it.
    const nonMembershipLinked = new Set<string>();
    for (const l of links as Link[]) {
      if (l.kind==='membership') continue;
      nonMembershipLinked.add(l.fromId); nonMembershipLinked.add(l.toId);
    }
    const peerColor = theme?.colors.peer || '#7AD7F0';
    for (const n of peers){
      const S = toScreen(n.x, n.y);
  const isHost = n.services && Object.keys(n.services).length>0; // Host = has at least one service
      const stroke = n.allowed?peerColor:'#888';
      const fill = n.allowed?'rgba(85, 148, 165, 1)':'rgba(90, 90, 90, 1)';
      const z = panzoom.zoom;
  if (isHost) {
        // Server icon (stacked chassis)
        const rackW = 48 * z;
        const unitH = 12 * z;
        const gap = 3 * z;
        const units = 3;
        const totalH = units*unitH + (units-1)*gap;
        const topY = S.y - totalH/2;
        // Outer glow / outline
        ctx.save();
        ctx.beginPath(); if ((ctx as any).roundRect) (ctx as any).roundRect(S.x - rackW/2 - 4*z, topY - 6*z, rackW + 8*z, totalH + 12*z, 6*z); else ctx.rect(S.x - rackW/2 - 4*z, topY - 6*z, rackW + 8*z, totalH + 12*z);
        ctx.fillStyle = 'rgba(40,40,40,1)'; ctx.fill();
        // Sequentially allocate service dots across units.
        const serviceCount = Object.keys(n.services||{}).length;
        const firstUnitCapacity = 4;
        const otherUnitCapacity = 5;
        let remaining = serviceCount;
        for (let i=0;i<units;i++){
          const y = topY + i*(unitH+gap);
          ctx.beginPath(); if ((ctx as any).roundRect) (ctx as any).roundRect(S.x - rackW/2, y, rackW, unitH, 4*z); else ctx.rect(S.x - rackW/2, y, rackW, unitH);
          ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth=2; ctx.fill(); ctx.stroke();
          const capacity = i===0 ? firstUnitCapacity : otherUnitCapacity;
          const drawLights = Math.min(capacity, remaining);
          for (let l=0; l<drawLights; l++) {
            const lx = S.x - rackW/2 + 8*z + l*8*z;
            const ly = y + unitH/2;
            ctx.beginPath(); ctx.arc(lx, ly, 1.8*z, 0, Math.PI*2); ctx.fillStyle = (l % 2 === 0) ? '#2ECC71' : '#F1C40F'; ctx.fill();
          }
          remaining -= drawLights;
          // Power button on top unit
          if (i===0){ ctx.beginPath(); ctx.arc(S.x + rackW/2 - 10*z, y + unitH/2, 3*z, 0, Math.PI*2); ctx.fillStyle = stroke; ctx.fill(); ctx.beginPath(); ctx.arc(S.x + rackW/2 - 10*z, y + unitH/2, 1.3*z, 0, Math.PI*2); ctx.fillStyle='#181818'; ctx.fill(); }
        }
        ctx.restore();
  // Connection + problematic badges
  const hostBadgeX = S.x + rackW/2 + 4*z;
  const hostBadgeY = S.y + 24*z;
  if (!n.allowed) drawWifiOffBadge(hostBadgeX, hostBadgeY, z);
  if (problematicPeers.has(n.id)) drawExclamationBadge(hostBadgeX, hostBadgeY - (n.allowed?0: (14*z)), z); // offset if stacked
        const labelY = topY + totalH/2 + 10*z;
        ctx.save(); ctx.fillStyle='rgba(255,255,255,0.92)'; ctx.font='600 12px Roboto, sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top'; ctx.fillText(n.name, S.x, labelY); ctx.restore();
        if (ui?.hoverPeerId === n.id){ ctx.save(); ctx.fillStyle='rgba(255,255,255,0.7)'; ctx.font='500 11px Roboto, sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top'; ctx.fillText((n as any).ip || '(no ip)', S.x, labelY + 14); ctx.restore(); }
      } else {
        // Original monitor client icon
        const monitorW = 46 * z;
        const monitorH = 30 * z;
        const standH = 6 * z;
        const baseW = 20 * z;
        const totalH = monitorH + standH + 4*z;
        const labelY = S.y + totalH/2 + 4*z;
        ctx.save();
        const x0 = S.x - monitorW/2;
        const y0 = S.y - totalH/2;
        ctx.beginPath();
        const r = 5 * z;
        if ((ctx as any).roundRect) (ctx as any).roundRect(x0, y0, monitorW, monitorH, r);
        else { ctx.moveTo(x0+r,y0); ctx.lineTo(x0+monitorW-r,y0); ctx.quadraticCurveTo(x0+monitorW,y0,x0+monitorW,y0+r); ctx.lineTo(x0+monitorW,y0+monitorH-r); ctx.quadraticCurveTo(x0+monitorW,y0+monitorH,x0+monitorW-r,y0+monitorH); ctx.lineTo(x0+r,y0+monitorH); ctx.quadraticCurveTo(x0,y0+monitorH,x0,y0+monitorH-r); ctx.lineTo(x0,y0+r); ctx.quadraticCurveTo(x0,y0,x0+r,y0); }
        ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.fill(); ctx.stroke();
        ctx.save(); ctx.beginPath(); if ((ctx as any).roundRect) (ctx as any).roundRect(x0+4*z, y0+4*z, monitorW-8*z, monitorH-8*z, r*0.6); else ctx.rect(x0+4*z,y0+4*z,monitorW-8*z,monitorH-8*z); ctx.clip();
        const grad = ctx.createLinearGradient(x0, y0, x0, y0+monitorH);
        grad.addColorStop(0,'rgba(53, 53, 53, 1)'); grad.addColorStop(1,'rgba(54, 54, 54, 1)');
        ctx.fillStyle = grad; ctx.fillRect(x0, y0, monitorW, monitorH);
        ctx.restore();
        // Stand
        const standY = y0 + monitorH;
        ctx.beginPath(); ctx.moveTo(S.x - 6*z, standY); ctx.lineTo(S.x + 6*z, standY); ctx.lineTo(S.x + 2*z, standY + standH); ctx.lineTo(S.x - 2*z, standY + standH); ctx.closePath(); ctx.fillStyle=stroke; ctx.fill();
        // Base
        ctx.beginPath(); const baseY = standY + standH + 1*z; ctx.rect(S.x - baseW/2, baseY, baseW, 3*z); ctx.fillStyle=stroke; ctx.fill();
        ctx.restore();
  // Badges for client/monitor icon
  const clientBadgeX = S.x + monitorW/2 + 4*z;
  const clientBadgeY = S.y; // center vertically around S.y
  if (!n.allowed) drawWifiOffBadge(clientBadgeX, clientBadgeY, z);
  if (problematicPeers.has(n.id)) drawExclamationBadge(clientBadgeX, clientBadgeY - (n.allowed?0: (14*z)), z);
        ctx.save(); ctx.fillStyle='rgba(255,255,255,0.92)'; ctx.font='600 12px Roboto, sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top'; ctx.fillText(n.name, S.x, labelY); ctx.restore();
        if (ui?.hoverPeerId === n.id) { ctx.save(); ctx.fillStyle='rgba(255,255,255,0.7)'; ctx.font='500 11px Roboto, sans-serif'; ctx.textAlign='center'; ctx.textBaseline='top'; ctx.fillText((n as any).ip || '(no ip)', S.x, labelY + 14); ctx.restore(); }
      }
    }
  }

  function drawSelection(ctx:CanvasRenderingContext2D){
    const { ui, peers, subnets, panzoom } = deps();
    if (!ui?.selection) return; const sel = ui.selection;
    ctx.save(); ctx.strokeStyle='#FFFFFF'; ctx.setLineDash([4,4]); ctx.lineWidth=2;
    if (sel.type==='peer') { const n = peers.find(p=>p.id===sel.id); if (!n){ ctx.restore(); return;} const S=toScreen(n.x,n.y); ctx.beginPath(); ctx.arc(S.x,S.y,30*panzoom.zoom,0,Math.PI*2); ctx.stroke(); }
    else if (sel.type==='subnet') { const s=subnets.find(ss=>ss.id===sel.id); if (!s){ ctx.restore(); return;} const tl=toScreen(s.x - s.width/2, s.y - s.height/2); const w=s.width*panzoom.zoom, h=s.height*panzoom.zoom; ctx.beginPath(); ctx.rect(tl.x-4, tl.y-4, w+8, h+8); ctx.stroke(); }
    ctx.restore();
  }

  // Removed hover subnet trailing icon per UX request.
  function drawHoverSubnetGhost(_ctx:CanvasRenderingContext2D){ /* intentionally blank */ }

  function drawGhostConnect(ctx:CanvasRenderingContext2D){
    const { ui, peers, subnets } = deps() as any; const connect = ui?.connect; if (!(connect && connect.ghostTo)) return;
    let originX:number|undefined, originY:number|undefined;
    if (connect.fromPeerId){ const a = peers.find((p: any)=>p.id===connect.fromPeerId); if (a){ originX=a.x; originY=a.y; } }
    else if ((connect as any).fromSubnetId){ const s = subnets.find((ss:any)=> ss.id===(connect as any).fromSubnetId); if (s){ originX=s.x; originY=s.y; } }
    if (originX===undefined || originY===undefined) return;
    const A = toScreen(originX,originY); const B = toScreen(connect.ghostTo.x, connect.ghostTo.y);
    ctx.save(); ctx.setLineDash([6,4]); ctx.strokeStyle='#FFFFFF'; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(A.x,A.y); ctx.lineTo(B.x,B.y); ctx.stroke(); ctx.restore(); }

  function drawGhostSubnet(ctx:CanvasRenderingContext2D){
    const { ui, panzoom } = deps(); const g = ui?.ghostSubnet; if (!(g && g.active)) return; const S = toScreen(g.x, g.y); const w = g.width * panzoom.zoom; const h = g.height * panzoom.zoom; ctx.save(); ctx.globalAlpha=0.18; ctx.fillStyle='#4CAF50'; ctx.beginPath(); ctx.rect(S.x - w/2, S.y - h/2, w, h); ctx.fill(); ctx.globalAlpha=1; ctx.setLineDash([6,4]); ctx.strokeStyle='#4CAF50'; ctx.lineWidth=2; ctx.strokeRect(S.x - w/2, S.y - h/2, w, h); ctx.restore(); }

  function draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    clear(ctx, w, h);
  if ((deps() as any).grid !== false) drawGrid(ctx,w,h); // default on unless explicitly false
    drawSubnets(ctx);
  const now = performance.now();
  if (lastTs===0) lastTs = now;
  // Advance shared animation frame for all passes
  frame += (now - lastTs) * 0.06; lastTs = now;
  drawLinks(ctx, now);
    drawMembershipLinks(ctx);
    drawPeers(ctx);
    drawSelection(ctx);
  drawHoverSubnetGhost(ctx); // no-op now
    drawGhostConnect(ctx);
    drawGhostSubnet(ctx);
  }

  return { draw, toScreen, toWorld, setInvalidator };
}
