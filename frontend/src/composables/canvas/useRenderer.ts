import type { Link, PanZoom, Peer, Subnet } from "@/types/network";

export interface RenderDeps {
  peers: Peer[];
  subnets: Subnet[];
  links: Link[];
  panzoom: PanZoom;
  theme?: {
    colors: {
      peer: string;
      subnet: string;
      link: string;
    };
  };
  ui?: {
    hoverPeerId?: string | null;
    hoverSubnetId?: string | null;
    hoverLinkId?: string | null;
    selection?: {
      type: "peer" | "subnet" | "link";
      id: string;
    } | null;
    tool?: string;
    connect?: {
      active: boolean;
      fromPeerId?: string;
      ghostTo?: { x: number; y: number } | null;
    };
    ghostSubnet?: {
      active: boolean;
      x: number;
      y: number;
      width: number;
      height: number;
    } | null;
  };
}

export function createRenderer(deps: () => RenderDeps & { grid?: boolean }) {
  let frame = 0; // animation frame counter
  let lastTs = 0;
  let invalidateFn: (() => void) | null = null;
  function setInvalidator(fn: () => void) {
    invalidateFn = fn;
  }
  function toScreen(wx: number, wy: number) {
    const { panzoom } = deps();
    return {
      x: wx * panzoom.zoom + panzoom.x,
      y: wy * panzoom.zoom + panzoom.y,
    };
  }
  function toWorld(sx: number, sy: number) {
    const { panzoom } = deps();
    return {
      x: (sx - panzoom.x) / panzoom.zoom,
      y: (sy - panzoom.y) / panzoom.zoom,
    };
  }

  function clear(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
  }

  // glue: call the individual passes you’ll split out
  function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number) {
    const { panzoom } = deps();
    const step = 40 * panzoom.zoom;
    const ox = panzoom.x % step;
    const oy = panzoom.y % step;
    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let x = ox; x < w; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = oy; y < h; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawSubnets(ctx: CanvasRenderingContext2D) {
    const { subnets, panzoom, theme, ui } = deps();
    const color = theme?.colors.subnet || "#7CF29A";
    // Order: broader networks (smaller prefix) first, then more specific (larger prefix) last so they sit on top visually.
    const ordered = [...subnets].sort((a, b) => {
      const ap = parseInt(a.cidr.split("/")[1] || "0", 10);
      const bp = parseInt(b.cidr.split("/")[1] || "0", 10);
      if (ap !== bp) return ap - bp; // smaller prefix (broader) first
      // If equal prefix, draw larger area first so smaller area overlays
      const aArea = a.width * a.height;
      const bArea = b.width * b.height;
      if (aArea !== bArea) return bArea - aArea;
      return a.id.localeCompare(b.id);
    });
    for (const s of ordered) {
      const tl = toScreen(s.x - s.width / 2, s.y - s.height / 2);
      const w = s.width * panzoom.zoom;
      const h = s.height * panzoom.zoom;
      ctx.save();
      // Rounded rectangle for subnet box
      ctx.beginPath();
      const r = 8; // border radius in screen px
      if ((ctx as any).roundRect) (ctx as any).roundRect(tl.x, tl.y, w, h, r);
      else {
        const x0 = tl.x,
          y0 = tl.y;
        ctx.moveTo(x0 + r, y0);
        ctx.lineTo(x0 + w - r, y0);
        ctx.quadraticCurveTo(x0 + w, y0, x0 + w, y0 + r);
        ctx.lineTo(x0 + w, y0 + h - r);
        ctx.quadraticCurveTo(x0 + w, y0 + h, x0 + w - r, y0 + h);
        ctx.lineTo(x0 + r, y0 + h);
        ctx.quadraticCurveTo(x0, y0 + h, x0, y0 + h - r);
        ctx.lineTo(x0, y0 + r);
        ctx.quadraticCurveTo(x0, y0, x0 + r, y0);
      }
      // Subnet fill color: backend supplies 0xRRGGBBAA. Convert to rgba(). Also set stroke to same RGB with full alpha.
      let fillStyle = "rgba(124,242,154,0.07)";
      let strokeStyle = color;
      const raw = (s as any).rgba;
      if (typeof raw === "number") {
        const r = (raw >> 24) & 0xff;
        const g = (raw >> 16) & 0xff;
        const b = (raw >> 8) & 0xff;
        const aByte = raw & 0xff;
        const a = +(aByte / 255).toFixed(3);
        fillStyle = `rgba(${r},${g},${b},${a})`;
        strokeStyle = `rgba(${r},${g},${b},1)`;
      }
      ctx.fillStyle = fillStyle;
      ctx.fill();
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
      // Always show subnet name (if provided). Show improved hover label with box and CIDR shifted right.
      const hasName = !!(s as any).name && (s as any).name.trim().length > 0;
      const nameLabel = hasName ? (s as any).name : "";
      const isHover = ui?.hoverSubnetId === s.id;
      if (!isHover) {
        // Non-hover: keep simple name text if present
        if (hasName) {
          ctx.fillStyle = "rgba(255,255,255,0.9)";
          ctx.font = "600 14px Roboto, sans-serif";
          ctx.textAlign = "left";
          ctx.textBaseline = "bottom";
          ctx.fillText(nameLabel, tl.x + 8, tl.y - 6);
        }
      } else {
        // Hover: draw rounded outlined box like link labels, containing name and CIDR (CIDR further to the right)
        const padX = 8,
          padY = 6;
        ctx.save();
        // Measure segments
        ctx.font = "600 13px Roboto, sans-serif";
        const nameW = hasName ? ctx.measureText(nameLabel).width : 0;
        const gap = hasName ? 12 : 0; // extra space pushes CIDR noticeably to the right of the name
        ctx.font = "500 12px Roboto, sans-serif";
        const cidrText = `(${s.cidr})`;
        const cidrW = ctx.measureText(cidrText).width;
        const lineH = 14;
        const boxW = padX * 2 + nameW + gap + cidrW;
        const boxH = padY * 2 + lineH;
        // Position the box above the subnet's top-left corner
        const bx = tl.x + 6; // slight inset from left edge
        const by = tl.y - 8 - boxH; // above with small gap
        ctx.beginPath();
        (ctx as any).roundRect?.(bx, by, boxW, boxH, 5);
        ctx.fillStyle = "rgba(0,0,0,0.65)";
        ctx.fill();
        ctx.strokeStyle = strokeStyle;
        ctx.lineWidth = 1;
        ctx.stroke();
        // Draw text segments
        let tx = bx + padX;
        const ty = by + padY + lineH / 2;
        if (hasName) {
          ctx.font = "600 13px Roboto, sans-serif";
          ctx.fillStyle = "#fff";
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          ctx.fillText(nameLabel, tx, ty);
          tx += nameW + gap;
        }
        ctx.font = "500 12px Roboto, sans-serif";
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(cidrText, tx, ty);
        ctx.restore();
      }
      ctx.restore();
    }
  }

  // Aggregated hover/selection label storage so multiple link kinds between same endpoints produce a single box
  interface LabelAgg {
    xSum: number;
    ySum: number;
    count: number;
    lines: Set<string>;
    stroke?: string;
  }
  const linkLabelAgg: Record<string, LabelAgg> = {};
  function addLinkLabel(
    key: string,
    x: number,
    y: number,
    lines: string[] | string,
    stroke: string,
  ) {
    if (!key) return;
    let agg = linkLabelAgg[key];
    if (!agg)
      agg = linkLabelAgg[key] = {
        xSum: 0,
        ySum: 0,
        count: 0,
        lines: new Set<string>(),
        stroke,
      };
    agg.xSum += x;
    agg.ySum += y;
    agg.count++;
    if (Array.isArray(lines)) lines.forEach((l) => l && agg!.lines.add(l));
    else if (lines) agg.lines.add(lines);
    // Preserve first stroke if already set
    if (!agg.stroke) agg.stroke = stroke;
  }
  function drawAggregatedLinkLabels(ctx: CanvasRenderingContext2D) {
    for (const key of Object.keys(linkLabelAgg)) {
      const agg = linkLabelAgg[key];
      if (!agg.lines.size) continue;
      const mx = agg.xSum / agg.count;
      const my = agg.ySum / agg.count;
      const lines = Array.from(agg.lines.values());
      lines.sort();
      ctx.save();
      ctx.font = "600 12px Roboto, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const padX = 8,
        padY = 6;
      const lineH = 14;
      const maxW = Math.max(...lines.map((l) => ctx.measureText(l).width));
      const boxH = lineH * lines.length + (lines.length - 1) * 2 + padY * 2;
      const boxW = maxW + padX * 2;
      ctx.beginPath();
      (ctx as any).roundRect?.(mx - boxW / 2, my - boxH / 2, boxW, boxH, 5);
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fill();
      ctx.strokeStyle = agg.stroke || "#4CAF50";
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = "#fff";
      lines.forEach((ln, i) =>
        ctx.fillText(
          ln,
          mx,
          my - boxH / 2 + padY + lineH / 2 + i * (lineH + 2),
        ),
      );
      ctx.restore();
    }
  }

  function drawLinks(ctx: CanvasRenderingContext2D, ts: number) {
    const { links, peers, subnets, ui } = deps();
    // Determine hovered link (any kind) to propagate hover across all link types for the same endpoint pair
    const hoveredLink = ui?.hoverLinkId
      ? links.find((l) => (l as any).id === ui.hoverLinkId)
      : null;
    // Exclude admin links from aggregation; they are rendered separately with direction.
    const regularLinks = links.filter(
      (l) =>
        (l as any).kind !== "admin-p2p" &&
        (l as any).kind !== "admin-peer-subnet" &&
        (l as any).kind !== "admin-subnet-subnet",
    );
    // frame increment moved to draw() so all passes share same timing
    interface Agg {
      a: Peer;
      b: Peer;
      p2p: boolean;
      services: Set<string>;
      serviceHostId?: string;
      linkIds: string[];
      repId: string;
    }
    const byPair: Record<string, Agg> = {};
    function pairKey(aId: string, bId: string) {
      return aId < bId ? `${aId}::${bId}` : `${bId}::${aId}`;
    }
    for (const l of regularLinks) {
      if (
        l.kind === "membership" ||
        l.kind === "subnet-subnet" ||
        l.kind === "subnet-service"
      )
        continue;
      const a = peers.find((p) => p.id === l.fromId);
      const b = peers.find((p) => p.id === l.toId);
      if (!a || !b) continue;
      const key = pairKey(a.id, b.id);
      let agg = byPair[key];
      if (!agg)
        agg = byPair[key] = {
          a,
          b,
          p2p: false,
          services: new Set(),
          linkIds: [],
          repId: l.id,
        };
      agg.linkIds.push(l.id);
      if (l.kind === "p2p") {
        agg.p2p = true;
        if (!agg.repId || agg.services.size === 0) agg.repId = l.id;
      } else if (l.kind === "service") {
        if (l.serviceName) agg.services.add(l.serviceName);
        if (!agg.serviceHostId) agg.serviceHostId = l.fromId;
        if (!agg.p2p) agg.repId = l.id;
      }
    }
    ctx.save();
    ctx.lineWidth = 2;
    let anyAnim = false;
    for (const key of Object.keys(byPair)) {
      const agg = byPair[key];
      const { a, b } = agg;
      const A = toScreen(a.x, a.y);
      const B = toScreen(b.x, b.y);
      const isMixed = agg.p2p && agg.services.size > 0;
      const isServiceOnly = !agg.p2p && agg.services.size > 0;
      const isP2POnly = agg.p2p && agg.services.size === 0;
      // Stroke style
      if (isMixed) {
        ctx.strokeStyle = "#FFC107";
      } else if (isServiceOnly) {
        const grad = ctx.createLinearGradient(A.x, A.y, B.x, B.y);
        grad.addColorStop(0, "rgba(33,150,243,0.9)");
        grad.addColorStop(1, "rgba(33,150,243,0.15)");
        ctx.strokeStyle = grad;
      } else {
        ctx.strokeStyle = "#4CAF50";
      }
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(B.x, B.y);
      ctx.stroke();
      // selection.id for links now stores pairKey(a,b); compute once
      const pair = pairKey(a.id, b.id);
      let active =
        agg.linkIds.some((id) => ui?.hoverLinkId === id) ||
        (ui?.selection?.type === "link" && ui.selection.id === pair) ||
        ui?.hoverPeerId === a.id ||
        ui?.hoverPeerId === b.id;
      // If hovering an admin (or other) link whose endpoints match this pair, also activate
      if (!active && hoveredLink) {
        const ha = hoveredLink.fromId,
          hb = hoveredLink.toId;
        const hp = ha < hb ? `${ha}::${hb}` : `${hb}::${ha}`;
        if (hp === pair) active = true;
      }
      if (active) {
        const dx = B.x - A.x,
          dy = B.y - A.y;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len,
          uy = dy / len;
        const t = (frame / 60) % 1;
        const drawDot = (pos: number, color: string, r = 4) => {
          const px = A.x + ux * len * pos,
            py = A.y + uy * len * pos;
          ctx.save();
          ctx.beginPath();
          ctx.fillStyle = color;
          ctx.shadowColor = color;
          ctx.shadowBlur = 6;
          ctx.arc(px, py, r, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        };
        if (isServiceOnly) {
          // Maintain original directional flow
          drawDot(t, "rgba(255,255,255,0.85)");
        } else if (isP2POnly || isMixed) {
          // Slower triangle wave 0->1->0 bounce (2s cycle instead of 1s)
          const tbounce = (frame / 120) % 1; // half speed vs service flow
          const tri = tbounce < 0.5 ? tbounce * 2 : 1 - (tbounce - 0.5) * 2; // 0..1..0
          const pos = tri;
          const color = "rgba(255,255,255,0.9)";
          drawDot(pos, color, 4.5); // single bouncing projectile (no trailing echo)
        }
        anyAnim = true;
      }
      if (active) {
        let lines: string[] = [];
        if (isMixed) {
          lines = ["p2p", "services"];
        } else if (isServiceOnly)
          lines = Array.from(agg.services.values()).sort();
        else lines = ["p2p"];
        const stroke = isMixed
          ? "#FFC107"
          : isServiceOnly
            ? "#2196F3"
            : "#4CAF50";
        addLinkLabel(pair, (A.x + B.x) / 2, (A.y + B.y) / 2, lines, stroke);
      }
    }
    ctx.restore();
    if (anyAnim && invalidateFn)
      requestAnimationFrame(() => invalidateFn && invalidateFn());
  }

  // Admin directed links with lens-on-hover animation
  function drawAdminLinks(ctx: CanvasRenderingContext2D) {
    const { links, peers, subnets, ui } = deps();
    let anyAnim = false;
    const lensPulse = (Math.sin(frame / 25) + 1) / 2; // 0..1
    const hoveredLink = ui?.hoverLinkId
      ? links.find((l) => (l as any).id === ui.hoverLinkId)
      : null;
    for (const l of links) {
      const kind = (l as any).kind;
      if (
        kind !== "admin-p2p" &&
        kind !== "admin-peer-subnet" &&
        kind !== "admin-subnet-subnet"
      )
        continue;
      // Resolve endpoints in world space (peer center or subnet boundary)
      let Ax = 0,
        Ay = 0,
        Bx = 0,
        By = 0;
      let valid = true;
      if (kind === "admin-p2p") {
        const a = peers.find((p) => p.id === l.fromId);
        const b = peers.find((p) => p.id === l.toId);
        if (!a || !b) {
          valid = false;
        } else {
          Ax = a.x;
          Ay = a.y;
          Bx = b.x;
          By = b.y;
        }
      } else if (kind === "admin-peer-subnet") {
        const peer = peers.find((p) => p.id === l.fromId);
        const subnet =
          subnets.find((s) => s.id === l.toId) ||
          subnets.find((s) => s.id === l.fromId);
        if (!peer || !subnet) {
          valid = false;
        } else {
          Ax = peer.x;
          Ay = peer.y; // origin peer
          // target point: intersection of ray center->peer? Actually direction is peer -> subnet center boundary towards center
          const cx = subnet.x,
            cy = subnet.y,
            hw = subnet.width / 2,
            hh = subnet.height / 2;
          const vx = cx - peer.x,
            vy = cy - peer.y;
          let t = 1;
          if (vx !== 0 || vy !== 0) {
            const sx = Math.abs(vx) / (hw || 1e-6),
              sy = Math.abs(vy) / (hh || 1e-6);
            t = Math.max(sx, sy) || 1;
          }
          Bx = cx - vx / t;
          By = cy - vy / t; // boundary point entering subnet
        }
      } else if (kind === "admin-subnet-subnet") {
        const sA = subnets.find((s) => s.id === l.fromId);
        const sB = subnets.find((s) => s.id === l.toId);
        if (!sA || !sB) {
          valid = false;
        } else {
          const cxA = sA.x,
            cyA = sA.y,
            hwA = sA.width / 2,
            hhA = sA.height / 2;
          const cxB = sB.x,
            cyB = sB.y,
            hwB = sB.width / 2,
            hhB = sB.height / 2;
          const vx = cxB - cxA,
            vy = cyB - cyA;
          let Axw = cxA,
            Ayw = cyA,
            Bxw = cxB,
            Byw = cyB;
          if (vx === 0 && vy === 0) {
            Axw = cxA + hwA;
            Ayw = cyA;
            Bxw = cxB - hwB;
            Byw = cyB;
          } else {
            const tA =
              Math.max(
                Math.abs(vx) / (hwA || 1e-6),
                Math.abs(vy) / (hhA || 1e-6),
              ) || 1;
            Axw = cxA + vx / tA;
            Ayw = cyA + vy / tA;
            const tB =
              Math.max(
                Math.abs(vx) / (hwB || 1e-6),
                Math.abs(vy) / (hhB || 1e-6),
              ) || 1;
            Bxw = cxB - vx / tB;
            Byw = cyB - vy / tB;
          }
          Ax = Axw;
          Ay = Ayw;
          Bx = Bxw;
          By = Byw;
        }
      }
      if (!valid) continue;
      const A = toScreen(Ax, Ay);
      const B = toScreen(Bx, By);
      // Pair key (direction-agnostic) so selection of any link between the two endpoints animates it.
      const pk = (() => {
        const a = l.fromId,
          b = l.toId;
        return a < b ? `${a}::${b}` : `${b}::${a}`;
      })();
      let active =
        ui?.hoverLinkId === (l as any).id ||
        ui?.hoverPeerId === l.fromId ||
        ui?.hoverSubnetId === l.fromId ||
        (ui?.selection?.type === "link" && ui.selection.id === pk);
      if (!active && hoveredLink) {
        const ha = hoveredLink.fromId,
          hb = hoveredLink.toId;
        const hp = ha < hb ? `${ha}::${hb}` : `${hb}::${ha}`;
        if (hp === pk) active = true;
      }
      // Determine styling differences
      let strokeStyle = "rgba(255,255,255,0.25)";
      let dash: number[] | null = null;
      if (kind === "admin-subnet-subnet") {
        const srcSubnet = subnets.find((s) => s.id === l.fromId);
        if (srcSubnet && typeof (srcSubnet as any).rgba === "number") {
          const raw = (srcSubnet as any).rgba;
          const r = (raw >> 24) & 0xff,
            g = (raw >> 16) & 0xff,
            b = (raw >> 8) & 0xff;
          strokeStyle = `rgba(${r},${g},${b},1)`;
        } else strokeStyle = "#7CF29A";
        dash = [10, 6];
      } else if (kind === "admin-peer-subnet") {
        strokeStyle = "rgba(180,180,180,0.65)";
        dash = [6, 5];
      }
      // Base directed line
      ctx.save();
      ctx.lineWidth = 2;
      ctx.strokeStyle = strokeStyle;
      if (dash) ctx.setLineDash(dash);
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(B.x, B.y);
      ctx.stroke();
      if (dash) ctx.setLineDash([]);
      // Direction arrow head (static subtle)
      const dx = B.x - A.x,
        dy = B.y - A.y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len,
        uy = dy / len;
      const ah = 8 * deps().panzoom.zoom;
      const aw = 5 * deps().panzoom.zoom;
      ctx.beginPath();
      ctx.moveTo(B.x, B.y);
      ctx.lineTo(B.x - ux * ah + -uy * aw, B.y - uy * ah + ux * aw);
      ctx.lineTo(B.x - ux * ah + uy * aw, B.y - uy * ah - ux * aw);
      ctx.closePath();
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.fill();
      if (active) {
        anyAnim = true;
        // Lens animation: traveling magnifier circle from origin to target.
        const t = (frame / 90) % 1; // slow travel
        const px = A.x + dx * t;
        const py = A.y + dy * t;
        const radius = 10 * deps().panzoom.zoom * (0.75 + 0.35 * lensPulse);
        // Lens glass
        ctx.save();
        ctx.beginPath();
        ctx.arc(px, py, radius, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(80,160,255,0.15)";
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "rgba(120,190,255,0.9)";
        ctx.stroke();
        // Light sweep highlight
        const grad = ctx.createRadialGradient(
          px - radius * 0.3,
          py - radius * 0.3,
          radius * 0.1,
          px,
          py,
          radius,
        );
        grad.addColorStop(0, "rgba(255,255,255,0.6)");
        grad.addColorStop(0.4, "rgba(255,255,255,0.15)");
        grad.addColorStop(1, "rgba(255,255,255,0)");
        ctx.globalCompositeOperation = "lighter";
        ctx.beginPath();
        ctx.arc(px, py, radius, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.globalCompositeOperation = "source-over";
        // Focused segment (magnified) under lens: redraw a thicker sub segment inside circle
        ctx.save();
        ctx.beginPath();
        ctx.arc(px, py, radius * 0.9, 0, Math.PI * 2);
        ctx.clip();
        ctx.lineWidth = 4;
        ctx.strokeStyle = "rgba(160,220,255,0.9)";
        ctx.beginPath();
        ctx.moveTo(A.x, A.y);
        ctx.lineTo(B.x, B.y);
        ctx.stroke();
        ctx.restore();
        ctx.restore();
        // Hover label for admin peer->peer links (shadowed box like regular link labels)
        if (
          kind === "admin-p2p" ||
          kind === "admin-subnet-subnet" ||
          kind === "admin-peer-subnet"
        ) {
          const mx = (A.x + B.x) / 2;
          const my = (A.y + B.y) / 2;
          let strokeLbl = strokeStyle;
          if (kind === "admin-peer-subnet") strokeLbl = "rgba(180,180,180,0.9)";
          else if (kind === "admin-p2p") strokeLbl = "rgba(120,190,255,0.9)";
          const key = pk;
          addLinkLabel(key, mx, my, "admin", strokeLbl);
        }
      }
      ctx.restore();
    }
    if (anyAnim && invalidateFn)
      requestAnimationFrame(() => invalidateFn && invalidateFn());
  }

  function drawMembershipLinks(ctx: CanvasRenderingContext2D) {
    const { links, peers, subnets, ui } = deps();
    let anyAnim = false;
    const hoveredLink = ui?.hoverLinkId
      ? links.find((l) => (l as any).id === ui.hoverLinkId)
      : null;
    for (const l of links) {
      if ((l as any).kind !== "membership") continue;
      // Expect l.fromId = peerId, l.toId = subnetId; tolerate reversed
      let peer = peers.find((p) => p.id === l.fromId);
      let subnet = subnets.find((s) => s.id === l.toId);
      if (!peer || !subnet) {
        peer = peers.find((p) => p.id === l.toId) || peer;
        subnet = subnets.find((s) => s.id === l.fromId) || subnet;
      }
      if (!peer || !subnet) continue;
      // Do not draw membership links to the peer's own containing subnet
      if ((peer as any).subnetId && (peer as any).subnetId === subnet.id)
        continue;
      const A = toScreen(peer.x, peer.y);
      // Compute boundary point B on subnet rectangle along ray from center->peer
      const cx = subnet.x,
        cy = subnet.y;
      const hw = subnet.width / 2,
        hh = subnet.height / 2;
      const vx = peer.x - cx,
        vy = peer.y - cy;
      let Bx = cx,
        By = cy;
      if (vx === 0 && vy === 0) {
        Bx = cx + hw;
        By = cy;
      } else {
        const sx = Math.abs(vx) / (hw || 1e-6),
          sy = Math.abs(vy) / (hh || 1e-6);
        const t = Math.max(sx, sy) || 1;
        Bx = cx + vx / t;
        By = cy + vy / t;
      }
      const B = toScreen(Bx, By);
      const Mx = (A.x + B.x) / 2,
        My = (A.y + B.y) / 2;
      // Color from subnet rgba
      let strokeStyle = "#7CF29A";
      const raw = (subnet as any).rgba;
      if (typeof raw === "number") {
        const r = (raw >> 24) & 0xff,
          g = (raw >> 16) & 0xff,
          b = (raw >> 8) & 0xff;
        strokeStyle = `rgba(${r},${g},${b},1)`;
      }
      const pk = (() => {
        const a = peer.id,
          b = subnet.id;
        return a < b ? `${a}::${b}` : `${b}::${a}`;
      })();
      let active =
        ui?.hoverPeerId === peer.id ||
        ui?.hoverSubnetId === subnet.id ||
        ui?.hoverLinkId === (l as any).id ||
        (ui?.selection?.type === "link" && ui.selection.id === pk);
      if (!active && hoveredLink) {
        const ha = hoveredLink.fromId,
          hb = hoveredLink.toId;
        const hp = ha < hb ? `${ha}::${hb}` : `${hb}::${ha}`;
        if (hp === pk) active = true;
      }
      // Two dashed halves moving toward center when active
      ctx.save();
      ctx.lineWidth = 2;
      ctx.setLineDash([10, 6]);
      const speed = frame * 0.8;
      ctx.strokeStyle = strokeStyle;
      ctx.lineDashOffset = active ? -speed : 0;
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(Mx, My);
      ctx.stroke();
      ctx.strokeStyle = strokeStyle;
      ctx.lineDashOffset = active ? -speed : 0;
      ctx.beginPath();
      ctx.moveTo(B.x, B.y);
      ctx.lineTo(Mx, My);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      if (active) anyAnim = true;
      // Hover overlay label
      if (active) {
        addLinkLabel(pk, Mx, My, "subnet guest", strokeStyle);
      }
    }
    if (anyAnim && invalidateFn)
      requestAnimationFrame(() => invalidateFn && invalidateFn());
  }

  function drawSubnetServiceLinks(ctx: CanvasRenderingContext2D) {
    const { links, peers, subnets, ui } = deps();
    let anyAnim = false;
    const hoveredLink = ui?.hoverLinkId
      ? links.find((l) => (l as any).id === ui.hoverLinkId)
      : null;
    for (const l of links) {
      if (l.kind !== "subnet-service") continue;
      const host = peers.find((p) => p.id === l.fromId);
      const subnet =
        subnets.find((s) => s.id === l.toId) ||
        subnets.find((s) => s.id === l.fromId);
      if (!host || !subnet) continue;
      // Line from host to subnet border
      const A = toScreen(host.x, host.y);
      const cx = subnet.x,
        cy = subnet.y;
      const hw = subnet.width / 2,
        hh = subnet.height / 2;
      const vx = host.x - cx,
        vy = host.y - cy;
      let Bx = cx,
        By = cy;
      if (vx === 0 && vy === 0) {
        Bx = cx + hw;
        By = cy;
      } else {
        const sx = Math.abs(vx) / (hw || 1e-6),
          sy = Math.abs(vy) / (hh || 1e-6);
        const t = Math.max(sx, sy) || 1;
        Bx = cx + vx / t;
        By = cy + vy / t;
      }
      const B = toScreen(Bx, By);
      // Color from subnet rgba
      let strokeStyle = "#2196F3";
      const raw = (subnet as any).rgba;
      if (typeof raw === "number") {
        const r = (raw >> 24) & 0xff,
          g = (raw >> 16) & 0xff,
          b = (raw >> 8) & 0xff;
        strokeStyle = `rgba(${r},${g},${b},1)`;
      }
      const pk = (() => {
        const a = host.id,
          b = subnet.id;
        return a < b ? `${a}::${b}` : `${b}::${a}`;
      })();
      let active =
        ui?.hoverPeerId === host.id ||
        ui?.hoverSubnetId === subnet.id ||
        ui?.hoverLinkId === (l as any).id ||
        (ui?.selection?.type === "link" && ui.selection.id === pk);
      if (!active && hoveredLink) {
        const ha = hoveredLink.fromId,
          hb = hoveredLink.toId;
        const hp = ha < hb ? `${ha}::${hb}` : `${hb}::${ha}`;
        if (hp === pk) active = true;
      }
      ctx.save();
      ctx.lineWidth = 2;
      ctx.setLineDash([10, 6]);
      ctx.strokeStyle = strokeStyle;
      ctx.lineDashOffset = active ? -frame * 0.8 : 0;
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(B.x, B.y);
      ctx.stroke();
      ctx.setLineDash([]);
      if (active) {
        anyAnim = true;
        const label = (l as any).serviceName || "service";
        addLinkLabel(pk, (A.x + B.x) / 2, (A.y + B.y) / 2, label, strokeStyle);
      }
      ctx.restore();
    }
    if (anyAnim && invalidateFn)
      requestAnimationFrame(() => invalidateFn && invalidateFn());
  }

  function drawSubnetSubnetLinks(ctx: CanvasRenderingContext2D) {
    const { links, subnets, ui } = deps();
    let anyAnim = false;
    const hoveredLink = ui?.hoverLinkId
      ? links.find((l) => (l as any).id === ui.hoverLinkId)
      : null;
    for (const l of links) {
      if (l.kind !== "subnet-subnet") continue;
      const sA =
        subnets.find((s) => s.id === l.fromId) ||
        subnets.find((s) => s.id === l.toId);
      const sB =
        subnets.find((s) => s.id === l.toId) ||
        subnets.find((s) => s.id === l.fromId);
      if (!sA || !sB) continue;
      const cxA = sA.x,
        cyA = sA.y,
        hwA = sA.width / 2,
        hhA = sA.height / 2;
      const cxB = sB.x,
        cyB = sB.y,
        hwB = sB.width / 2,
        hhB = sB.height / 2;
      const vx = cxB - cxA,
        vy = cyB - cyA;
      let Ax = cxA,
        Ay = cyA,
        Bx = cxB,
        By = cyB;
      if (vx === 0 && vy === 0) {
        Ax = cxA + hwA;
        Ay = cyA;
        Bx = cxB - hwB;
        By = cyB;
      } else {
        const tA =
          Math.max(
            Math.abs(vx) / (hwA || 1e-6),
            Math.abs(vy) / (hhA || 1e-6),
          ) || 1;
        Ax = cxA + vx / tA;
        Ay = cyA + vy / tA;
        const tB =
          Math.max(
            Math.abs(vx) / (hwB || 1e-6),
            Math.abs(vy) / (hhB || 1e-6),
          ) || 1;
        Bx = cxB - vx / tB;
        By = cyB - vy / tB;
      }
      const A = toScreen(Ax, Ay),
        B = toScreen(Bx, By);
      const Mx = (A.x + B.x) / 2,
        My = (A.y + B.y) / 2;
      // Gradient color from subnet A to subnet B
      function rgbOf(raw: number) {
        return {
          r: (raw >> 24) & 0xff,
          g: (raw >> 16) & 0xff,
          b: (raw >> 8) & 0xff,
        };
      }
      let colorA = "#7CF29A";
      let colorB = "#7CF29A";
      if (typeof (sA as any).rgba === "number") {
        const a = rgbOf((sA as any).rgba);
        colorA = `rgba(${a.r},${a.g},${a.b},1)`;
      }
      if (typeof (sB as any).rgba === "number") {
        const b = rgbOf((sB as any).rgba);
        colorB = `rgba(${b.r},${b.g},${b.b},1)`;
      }
      // Mid color (for visual continuity at the center)
      function mix(c1: string, c2: string) {
        const m1 = /rgba?\((\d+),(\d+),(\d+)/.exec(c1);
        const m2 = /rgba?\((\d+),(\d+),(\d+)/.exec(c2);
        if (!m1 || !m2) return c1;
        const r = Math.round((+m1[1] + +m2[1]) / 2),
          g = Math.round((+m1[2] + +m2[2]) / 2),
          b = Math.round((+m1[3] + +m2[3]) / 2);
        return `rgba(${r},${g},${b},1)`;
      }
      const colorMid = mix(colorA, colorB);
      const pk = (() => {
        const a = sA.id,
          b = sB.id;
        return a < b ? `${a}::${b}` : `${b}::${a}`;
      })();
      let active =
        ui?.hoverSubnetId === sA.id ||
        ui?.hoverSubnetId === sB.id ||
        ui?.hoverLinkId === (l as any).id ||
        (ui?.selection?.type === "link" && ui.selection.id === pk);
      if (!active && hoveredLink) {
        const ha = hoveredLink.fromId,
          hb = hoveredLink.toId;
        const hp = ha < hb ? `${ha}::${hb}` : `${hb}::${ha}`;
        if (hp === pk) active = true;
      }
      // Draw two halves, each moving towards the center
      const speed = frame * 0.8;
      ctx.save();
      ctx.lineWidth = 2;
      ctx.setLineDash([10, 6]);
      // First half: A -> M
      const gradA = ctx.createLinearGradient(A.x, A.y, Mx, My);
      gradA.addColorStop(0, colorA);
      gradA.addColorStop(1, colorMid);
      ctx.strokeStyle = gradA;
      ctx.lineDashOffset = active ? -speed : 0;
      ctx.beginPath();
      ctx.moveTo(A.x, A.y);
      ctx.lineTo(Mx, My);
      ctx.stroke();
      // Second half: B -> M
      const gradB = ctx.createLinearGradient(B.x, B.y, Mx, My);
      gradB.addColorStop(0, colorB);
      gradB.addColorStop(1, colorMid);
      ctx.strokeStyle = gradB;
      ctx.lineDashOffset = active ? -speed : 0;
      ctx.beginPath();
      ctx.moveTo(B.x, B.y);
      ctx.lineTo(Mx, My);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      if (active) anyAnim = true;
      if (active) {
        addLinkLabel(
          pk,
          (A.x + B.x) / 2,
          (A.y + B.y) / 2,
          "subnets linked",
          colorA,
        );
      }
    }
    if (anyAnim && invalidateFn)
      requestAnimationFrame(() => invalidateFn && invalidateFn());
  }

  function drawPeers(ctx: CanvasRenderingContext2D) {
    const { peers, panzoom, theme, ui, links } = deps() as any;
    // Determine problematic peers (participate in at least one mixed p2p + service pair)
    const problematicPeers = new Set<string>();
    (function computeProblematic() {
      interface Agg {
        a: Peer;
        b: Peer;
        p2p: boolean;
        services: Set<string>;
      }
      const byPair: Record<string, Agg> = {};
      function pairKey(aId: string, bId: string) {
        return aId < bId ? `${aId}::${bId}` : `${bId}::${aId}`;
      }
      for (const l of links as Link[]) {
        if (l.kind === "membership") continue;
        const a = peers.find((p: Peer) => p.id === l.fromId);
        const b = peers.find((p: Peer) => p.id === l.toId);
        if (!a || !b) continue;
        const key = pairKey(a.id, b.id);
        let agg = byPair[key];
        if (!agg) agg = byPair[key] = { a, b, p2p: false, services: new Set() };
        if (l.kind === "p2p") agg.p2p = true;
        else if (l.kind === "service" && l.serviceName)
          agg.services.add(l.serviceName);
      }
      for (const k of Object.keys(byPair)) {
        const agg = byPair[k];
        if (agg.p2p && agg.services.size > 0) {
          problematicPeers.add(agg.a.id);
          problematicPeers.add(agg.b.id);
        }
      }
    })();

    function drawWifiOffBadge(x: number, y: number, z: number) {
      const r = 8 * z; // outer badge radius
      ctx.save();
      // Badge background
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = "#4d4d4d";
      ctx.fill();
      ctx.strokeStyle = "#7a7a7a";
      ctx.lineWidth = 1.1 * z;
      ctx.stroke();
      // Upward facing WiFi arcs (smile orientation). Dot anchored near bottom.
      const dotY = y + r * 0.45; // push dot toward bottom of badge
      const arcCenterY = y + r * 0.25; // slight upward shift so arcs sit above dot
      ctx.strokeStyle = "#e4e4e4";
      ctx.lineCap = "round";
      const radii = [r - 7 * z, r - 5 * z, r - 3 * z]; // small -> large
      for (let i = 0; i < radii.length; i++) {
        const rad = radii[i];
        if (rad <= 0) continue;
        ctx.beginPath();
        // Angles 225° to 315° (1.25π to 1.75π) produce an upward opening arc
        ctx.lineWidth = 1.2 * z;
        ctx.arc(x, arcCenterY, rad, Math.PI * 1.25, Math.PI * 1.75);
        ctx.stroke();
      }
      // Origin dot
      ctx.beginPath();
      ctx.arc(x, dotY, 1.0 * z, 0, Math.PI * 2);
      ctx.fillStyle = "#f0f0f0";
      ctx.fill();
      // Slash (thinner) to indicate disabled
      ctx.beginPath();
      ctx.strokeStyle = "#cfcfcf";
      ctx.lineWidth = 1 * z;
      ctx.moveTo(x - r * 0.62, y + r * 0.58);
      ctx.lineTo(x + r * 0.62, y - r * 0.58);
      ctx.stroke();
      ctx.restore();
    }
    function drawGlobeBadge(x: number, y: number, z: number) {
      const r = 7 * z;
      ctx.save();
      // Outer circle
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = "#2b2b2b";
      ctx.fill();
      ctx.strokeStyle = "#9ad0ff";
      ctx.lineWidth = 1.1 * z;
      ctx.stroke();
      // Longitudes (vertical meridians)
      ctx.strokeStyle = "#cfe8ff";
      ctx.lineWidth = 1 * z;
      ctx.beginPath();
      ctx.moveTo(x, y - r + 2 * z);
      ctx.lineTo(x, y + r - 2 * z);
      ctx.stroke();
      // Latitudes (parallels) as arcs
      for (const k of [-0.5, 0.5]) {
        ctx.beginPath();
        ctx.ellipse(x, y + k * r * 0.4, r * 0.78, r * 0.28, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    }
    function drawExclamationBadge(x: number, y: number, z: number) {
      const badgeR = 7 * z;
      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, badgeR, 0, Math.PI * 2);
      ctx.fillStyle = "#d3ad2fff";
      ctx.fill();
      ctx.font = `${9 * z}px Roboto, sans-serif`;
      ctx.fillStyle = "#fff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("!", x, y + 0.5 * z);
      ctx.restore();
    }
    function drawCrownBadge(x: number, y: number, z: number) {
      // Wider + flatter crown: base bar + 3 lower peaks
      const w = 24 * z;
      const h = 8 * z;
      const peakH = 4.5 * z;
      const radius = 2.5 * z;
      ctx.save();
      ctx.translate(x - w / 2, y - h - peakH);
      // Shadow / outline
      ctx.beginPath();
      ctx.moveTo(0, h + peakH);
      ctx.lineTo(0, peakH + radius * 0.6);
      // Left peak (short)
      ctx.lineTo(w * 0.22, peakH * 0.55);
      ctx.lineTo(w * 0.36, peakH + radius * 0.2);
      // Middle peak (taller but still flat)
      ctx.lineTo(w * 0.5, peakH * 0.05);
      ctx.lineTo(w * 0.64, peakH + radius * 0.2);
      // Right peak (short)
      ctx.lineTo(w * 0.78, peakH * 0.55);
      ctx.lineTo(w, peakH + radius * 0.6);
      ctx.lineTo(w, h + peakH);
      ctx.closePath();
      ctx.fillStyle = "#f1c40f";
      ctx.strokeStyle = "#b58500";
      ctx.lineWidth = 1.5 * z;
      ctx.fill();
      ctx.stroke();
      // Base jewels
      const jewelY = peakH + h * 0.4;
      const jewels = [w * 0.23, w * 0.5, w * 0.77];
      ctx.fillStyle = "#ffffffd0";
      for (const jx of jewels) {
        ctx.beginPath();
        ctx.arc(jx, jewelY, 1.1 * z, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    // Build set of peers having at least one non-membership link (p2p/service) — retained in case future styling needs it.
    const nonMembershipLinked = new Set<string>();
    for (const l of links as Link[]) {
      if (l.kind === "membership") continue;
      nonMembershipLinked.add(l.fromId);
      nonMembershipLinked.add(l.toId);
    }
    const peerColor = theme?.colors.peer || "#7AD7F0";
    for (const n of peers) {
      const S = toScreen(n.x, n.y);
      const isHost = n.services && Object.keys(n.services).length > 0; // Host = has at least one service
      const last = (n as any).lastHandshake || 0;
      const nowSec = Date.now() / 1000;
      let connected = nowSec - last < 300; // 5 minutes
      const isMaster = n.name === "master";
      if (isMaster) connected = true; // Master is always online
      const isPublic = !!(n as any).public; // membership to its own subnet
      const stroke = connected ? peerColor : "#888";
      const fill = connected ? "rgba(85, 148, 165, 1)" : "rgba(90, 90, 90, 1)";
      const z = panzoom.zoom;
      if (isHost) {
        // Server icon (stacked chassis)
        const rackW = 48 * z;
        const unitH = 12 * z;
        const gap = 3 * z;
        const units = 3;
        const totalH = units * unitH + (units - 1) * gap;
        const topY = S.y - totalH / 2;
        // Outer glow / outline
        ctx.save();
        ctx.beginPath();
        if ((ctx as any).roundRect)
          (ctx as any).roundRect(
            S.x - rackW / 2 - 4 * z,
            topY - 6 * z,
            rackW + 8 * z,
            totalH + 12 * z,
            6 * z,
          );
        else
          ctx.rect(
            S.x - rackW / 2 - 4 * z,
            topY - 6 * z,
            rackW + 8 * z,
            totalH + 12 * z,
          );
        ctx.fillStyle = "rgba(40,40,40,1)";
        ctx.fill();
        // Sequentially allocate service dots across units.
        const serviceCount = Object.keys(n.services || {}).length;
        const firstUnitCapacity = 4;
        const otherUnitCapacity = 5;
        let remaining = serviceCount;
        for (let i = 0; i < units; i++) {
          const y = topY + i * (unitH + gap);
          ctx.beginPath();
          if ((ctx as any).roundRect)
            (ctx as any).roundRect(S.x - rackW / 2, y, rackW, unitH, 4 * z);
          else ctx.rect(S.x - rackW / 2, y, rackW, unitH);
          ctx.fillStyle = fill;
          ctx.strokeStyle = stroke;
          ctx.lineWidth = 2;
          ctx.fill();
          ctx.stroke();
          const capacity = i === 0 ? firstUnitCapacity : otherUnitCapacity;
          const drawLights = Math.min(capacity, remaining);
          for (let l = 0; l < drawLights; l++) {
            const lx = S.x - rackW / 2 + 8 * z + l * 8 * z;
            const ly = y + unitH / 2;
            ctx.beginPath();
            ctx.arc(lx, ly, 1.8 * z, 0, Math.PI * 2);
            ctx.fillStyle = l % 2 === 0 ? "#2ECC71" : "#F1C40F";
            ctx.fill();
          }
          remaining -= drawLights;
          // Power button on top unit
          if (i === 0) {
            ctx.beginPath();
            ctx.arc(
              S.x + rackW / 2 - 10 * z,
              y + unitH / 2,
              3 * z,
              0,
              Math.PI * 2,
            );
            ctx.fillStyle = stroke;
            ctx.fill();
            ctx.beginPath();
            ctx.arc(
              S.x + rackW / 2 - 10 * z,
              y + unitH / 2,
              1.3 * z,
              0,
              Math.PI * 2,
            );
            ctx.fillStyle = "#181818";
            ctx.fill();
          }
        }
        ctx.restore();
        // Connection + problematic badges
        const hostBadgeX = S.x + rackW / 2 + 4 * z;
        const hostBadgeY = S.y + 24 * z;
        if (!connected) drawWifiOffBadge(hostBadgeX, hostBadgeY, z);
        if (problematicPeers.has(n.id))
          drawExclamationBadge(
            hostBadgeX,
            hostBadgeY - (connected ? 0 : 14 * z),
            z,
          ); // offset if stacked
        if (isPublic) drawGlobeBadge(hostBadgeX + 16 * z, hostBadgeY, z);
        const labelY = topY + totalH / 2 + 10 * z;
        const isHoverPeer = ui?.hoverPeerId === n.id;
        if (!isHoverPeer) {
          // Non-hover: show simple name under host
          ctx.save();
          ctx.fillStyle = "rgba(255,255,255,0.92)";
          ctx.font = "600 12px Roboto, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillText(n.name, S.x, labelY);
          ctx.restore();
        } else {
          // Hover: show dark rounded label with name and IP
          const nameText = n.name || "";
          const ipText = (n as any).ip || "(no ip)";
          const padX = 8,
            padY = 6,
            lineH = 14;
          ctx.save();
          // Measure max width across both lines
          ctx.font = "600 12px Roboto, sans-serif";
          const nameW = ctx.measureText(nameText).width;
          ctx.font = "500 12px Roboto, sans-serif";
          const ipW = ctx.measureText(ipText).width;
          const maxW = Math.max(nameW, ipW);
          const boxW = maxW + padX * 2;
          const boxH = lineH * 2 + padY * 2 + 2; // +2 interline spacing
          const bx = S.x - boxW / 2;
          const by = topY - 10 * z - boxH; // above the host icon
          ctx.beginPath();
          (ctx as any).roundRect?.(bx, by, boxW, boxH, 5);
          ctx.fillStyle = "rgba(0,0,0,0.65)";
          ctx.fill();
          ctx.strokeStyle = stroke;
          ctx.lineWidth = 1;
          ctx.stroke();
          // Text lines
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          ctx.font = "600 12px Roboto, sans-serif";
          ctx.fillStyle = "#fff";
          ctx.fillText(nameText, bx + padX, by + padY + lineH / 2);
          ctx.font = "500 12px Roboto, sans-serif";
          ctx.fillStyle = "rgba(255,255,255,0.9)";
          ctx.fillText(ipText, bx + padX, by + padY + lineH + 2 + lineH / 2);
          ctx.restore();
        }
        if (isMaster) {
          // Draw crown above top of host icon
          drawCrownBadge(S.x, topY - 4 * z, z);
        }
      } else {
        // Original monitor client icon
        const monitorW = 46 * z;
        const monitorH = 30 * z;
        const standH = 6 * z;
        const baseW = 20 * z;
        const totalH = monitorH + standH + 4 * z;
        const labelY = S.y + totalH / 2 + 4 * z;
        ctx.save();
        const x0 = S.x - monitorW / 2;
        const y0 = S.y - totalH / 2;
        ctx.beginPath();
        const r = 5 * z;
        if ((ctx as any).roundRect)
          (ctx as any).roundRect(x0, y0, monitorW, monitorH, r);
        else {
          ctx.moveTo(x0 + r, y0);
          ctx.lineTo(x0 + monitorW - r, y0);
          ctx.quadraticCurveTo(x0 + monitorW, y0, x0 + monitorW, y0 + r);
          ctx.lineTo(x0 + monitorW, y0 + monitorH - r);
          ctx.quadraticCurveTo(
            x0 + monitorW,
            y0 + monitorH,
            x0 + monitorW - r,
            y0 + monitorH,
          );
          ctx.lineTo(x0 + r, y0 + monitorH);
          ctx.quadraticCurveTo(x0, y0 + monitorH, x0, y0 + monitorH - r);
          ctx.lineTo(x0, y0 + r);
          ctx.quadraticCurveTo(x0, y0, x0 + r, y0);
        }
        ctx.fillStyle = fill;
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
        ctx.save();
        ctx.beginPath();
        if ((ctx as any).roundRect)
          (ctx as any).roundRect(
            x0 + 4 * z,
            y0 + 4 * z,
            monitorW - 8 * z,
            monitorH - 8 * z,
            r * 0.6,
          );
        else
          ctx.rect(x0 + 4 * z, y0 + 4 * z, monitorW - 8 * z, monitorH - 8 * z);
        ctx.clip();
        const grad = ctx.createLinearGradient(x0, y0, x0, y0 + monitorH);
        grad.addColorStop(0, "rgba(53, 53, 53, 1)");
        grad.addColorStop(1, "rgba(54, 54, 54, 1)");
        ctx.fillStyle = grad;
        ctx.fillRect(x0, y0, monitorW, monitorH);
        ctx.restore();
        // Stand
        const standY = y0 + monitorH;
        ctx.beginPath();
        ctx.moveTo(S.x - 6 * z, standY);
        ctx.lineTo(S.x + 6 * z, standY);
        ctx.lineTo(S.x + 2 * z, standY + standH);
        ctx.lineTo(S.x - 2 * z, standY + standH);
        ctx.closePath();
        ctx.fillStyle = stroke;
        ctx.fill();
        // Base
        ctx.beginPath();
        const baseY = standY + standH + 1 * z;
        ctx.rect(S.x - baseW / 2, baseY, baseW, 3 * z);
        ctx.fillStyle = stroke;
        ctx.fill();
        ctx.restore();
        // Badges for client/monitor icon
        const clientBadgeX = S.x + monitorW / 2 + 4 * z;
        const clientBadgeY = S.y; // center vertically around S.y
        if (!connected) drawWifiOffBadge(clientBadgeX, clientBadgeY, z);
        if (problematicPeers.has(n.id))
          drawExclamationBadge(
            clientBadgeX,
            clientBadgeY - (connected ? 0 : 14 * z),
            z,
          );
        if (isPublic) drawGlobeBadge(clientBadgeX + 16 * z, clientBadgeY, z);
        const isHoverClient = ui?.hoverPeerId === n.id;
        if (!isHoverClient) {
          // Non-hover: show simple name under client
          ctx.save();
          ctx.fillStyle = "rgba(255,255,255,0.92)";
          ctx.font = "600 12px Roboto, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillText(n.name, S.x, labelY);
          ctx.restore();
        } else {
          // Hover: show dark rounded label with name and IP
          const nameText = n.name || "";
          const ipText = (n as any).ip || "(no ip)";
          const padX = 8,
            padY = 6,
            lineH = 14;
          ctx.save();
          // Measure widths
          ctx.font = "600 12px Roboto, sans-serif";
          const nameW = ctx.measureText(nameText).width;
          ctx.font = "500 12px Roboto, sans-serif";
          const ipW = ctx.measureText(ipText).width;
          const maxW = Math.max(nameW, ipW);
          const boxW = maxW + padX * 2;
          const boxH = lineH * 2 + padY * 2 + 2;
          const bx = S.x - boxW / 2;
          const by = y0 - 10 * z - boxH; // above monitor
          ctx.beginPath();
          (ctx as any).roundRect?.(bx, by, boxW, boxH, 5);
          ctx.fillStyle = "rgba(0,0,0,0.65)";
          ctx.fill();
          ctx.strokeStyle = stroke;
          ctx.lineWidth = 1;
          ctx.stroke();
          ctx.textAlign = "left";
          ctx.textBaseline = "middle";
          ctx.font = "600 12px Roboto, sans-serif";
          ctx.fillStyle = "#fff";
          ctx.fillText(nameText, bx + padX, by + padY + lineH / 2);
          ctx.font = "500 12px Roboto, sans-serif";
          ctx.fillStyle = "rgba(255,255,255,0.9)";
          ctx.fillText(ipText, bx + padX, by + padY + lineH + 2 + lineH / 2);
          ctx.restore();
        }
        if (isMaster) {
          // For client icon, y0 is top of monitor area
          drawCrownBadge(S.x, y0 - 4 * z, z);
        }
      }
    }
  }

  function drawSelection(ctx: CanvasRenderingContext2D) {
    const { ui, peers, subnets, panzoom } = deps();
    if (!ui?.selection) return;
    const sel = ui.selection;
    ctx.save();
    ctx.strokeStyle = "#FFFFFF";
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 2;
    if (sel.type === "peer") {
      const n = peers.find((p) => p.id === sel.id);
      if (!n) {
        ctx.restore();
        return;
      }
      const S = toScreen(n.x, n.y);
      ctx.beginPath();
      ctx.arc(S.x, S.y, 30 * panzoom.zoom, 0, Math.PI * 2);
      ctx.stroke();
    } else if (sel.type === "subnet") {
      const s = subnets.find((ss) => ss.id === sel.id);
      if (!s) {
        ctx.restore();
        return;
      }
      const tl = toScreen(s.x - s.width / 2, s.y - s.height / 2);
      const w = s.width * panzoom.zoom,
        h = s.height * panzoom.zoom;
      const pad = 4;
      const x = tl.x - pad,
        y = tl.y - pad,
        sw = w + pad * 2,
        sh = h + pad * 2;
      const innerR = 8; // inner subnet corner radius in px
      const rSel = innerR + pad; // bump radius so outline matches inner curvature visually
      ctx.beginPath();
      if ((ctx as any).roundRect) (ctx as any).roundRect(x, y, sw, sh, rSel);
      else ctx.rect(x, y, sw, sh);
      ctx.stroke();
    }
    ctx.restore();
  }

  // Removed hover subnet trailing icon per UX request.
  function drawHoverSubnetGhost(_ctx: CanvasRenderingContext2D) {
    /* intentionally blank */
  }

  function drawGhostConnect(ctx: CanvasRenderingContext2D) {
    const { ui, peers, subnets } = deps() as any;
    const connect = ui?.connect;
    if (!(connect && connect.ghostTo)) return;
    let originX: number | undefined, originY: number | undefined;
    if (connect.fromPeerId) {
      const a = peers.find((p: any) => p.id === connect.fromPeerId);
      if (a) {
        originX = a.x;
        originY = a.y;
      }
    } else if ((connect as any).fromSubnetId) {
      const s = subnets.find(
        (ss: any) => ss.id === (connect as any).fromSubnetId,
      );
      if (s) {
        originX = s.x;
        originY = s.y;
      }
    }
    if (originX === undefined || originY === undefined) {
      return;
    }
    const A = toScreen(originX, originY);
    const B = toScreen(connect.ghostTo.x, connect.ghostTo.y);
    ctx.save();
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(A.x, A.y);
    ctx.lineTo(B.x, B.y);
    ctx.stroke();
    ctx.restore();
  }

  function drawGhostSubnet(ctx: CanvasRenderingContext2D) {
    const { ui, panzoom } = deps();
    const g = ui?.ghostSubnet;
    if (!(g && g.active)) return;
    const S = toScreen(g.x, g.y);
    const w = g.width * panzoom.zoom;
    const h = g.height * panzoom.zoom;
    ctx.save();
    ctx.globalAlpha = 0.18;
    ctx.fillStyle = "#4CAF50";
    ctx.beginPath();
    ctx.rect(S.x - w / 2, S.y - h / 2, w, h);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = "#4CAF50";
    ctx.lineWidth = 2;
    ctx.strokeRect(S.x - w / 2, S.y - h / 2, w, h);
    ctx.restore();
  }

  function draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    clear(ctx, w, h);
    if ((deps() as any).grid !== false) drawGrid(ctx, w, h); // default on unless explicitly false
    drawSubnets(ctx);
    // Reset label aggregator for this frame
    for (const k of Object.keys(linkLabelAgg)) delete linkLabelAgg[k];
    const now = performance.now();
    if (lastTs === 0) lastTs = now;
    // Advance shared animation frame for all passes
    frame += (now - lastTs) * 0.06;
    lastTs = now;
    drawAdminLinks(ctx); // draw first so regular links labels sit above if overlapping
    drawLinks(ctx, now);
    drawSubnetSubnetLinks(ctx);
    drawMembershipLinks(ctx);
    drawSubnetServiceLinks(ctx);
    drawAggregatedLinkLabels(ctx);
    drawPeers(ctx);
    drawSelection(ctx);
    drawHoverSubnetGhost(ctx); // no-op now
    drawGhostConnect(ctx);
    drawGhostSubnet(ctx);
  }

  return { draw, toScreen, toWorld, setInvalidator };
}
