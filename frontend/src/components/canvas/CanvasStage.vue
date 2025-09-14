<template>
  <div class="fill-height p-4 canvas-wrapper" @contextmenu.prevent>
    <canvas ref="canvasRef" class="vpn-canvas"></canvas>
    <!-- Lightweight overlays slot -->
    <slot />
    <!-- Tool mode cursor indicator -->
    <div
      v-if="indicator.visible"
      :style="indicatorStyle"
      class="tool-indicator"
    >
      <div class="icon" v-html="indicator.icon" />
      <div class="label">{{ indicator.label }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
const emit = defineEmits<{
  (e: "subnet-click", payload: { id: string; x: number; y: number }): void;
  (e: "peer-click", payload: { id: string; x: number; y: number }): void;
  (e: "canvas-context", payload: { x: number; y: number }): void;
  (
    e: "add-subnet-request",
    payload: {
      worldX: number;
      worldY: number;
      screenX: number;
      screenY: number;
    },
  ): void;
}>();
import { onMounted, onUnmounted, reactive, watch, computed } from "vue";
import { useCanvas } from "@/composables/canvas/useCanvas";
import { createRenderer } from "@/composables/canvas/useRenderer";
import { createInteractions } from "@/composables/canvas/useInteractions";
import { useNetworkStore } from "@/stores/network";
import { cidrContains, ipInCidr } from "@/utils/net";
import { bus } from "@/utils/bus";

const store = useNetworkStore();
const { canvasRef, withCtx, resizeToParent, loop, invalidate } = useCanvas();

// Flag to know if the latest store.selection change originated from inside the canvas.
// If true we suppress the automatic focus/zoom (only inspector-originated subnet selections should focus).
let selectionSetInternally = false;

// Interaction / UI ephemeral state not stored in Pinia (kept transient for perf)
const ui = reactive({
  hoverPeerId: null as string | null,
  hoverSubnetId: null as string | null,
  hoverLinkId: null as string | null,
  selection: null as null | { type: "peer" | "subnet" | "link"; id: string },
  tool: () => store.tool,
  connect: {
    active: false,
    fromPeerId: "",
    fromSubnetId: "",
    ghostTo: null as null | { x: number; y: number },
  },
  // when connecting from a subnet, store its id here
  // keep fromPeerId for peers to minimize changes elsewhere
  // ghostTo is shared
  // Note: renderer supports fromSubnetId as of this change
  // eslint-disable-next-line vue/no-unused-properties

  ghostSubnet: {
    active: false,
    x: 0,
    y: 0,
    width: 420,
    height: 260,
    frozen: false,
  } as {
    active: boolean;
    x: number;
    y: number;
    width: number;
    height: number;
    frozen: boolean;
  },
});

// Floating indicator reactive state
const indicator = reactive({ visible: false, x: 0, y: 0, label: "", icon: "" });
const indicatorStyle = computed(
  () =>
    ({
      position: "fixed",
      left: indicator.x + 14 + "px",
      top: indicator.y + 14 + "px",
      pointerEvents: "none" as const,
      transform: "translate(-50%, -50%)",
    }) as const,
);

const interactions = createInteractions(
  () => store.peers,
  () => store.subnets,
  () => store.links,
  () => store.zoom,
);

const renderer = createRenderer(() => ({
  peers: store.peers,
  subnets: store.subnets,
  links: store.links,
  panzoom: { x: store.pan.x, y: store.pan.y, zoom: store.zoom },
  grid: store.grid,
  theme: { colors: { peer: "#7AD7F0", subnet: "#7CF29A", link: "#86A1FF" } },
  ui: {
    hoverPeerId: ui.hoverPeerId,
    hoverSubnetId: ui.hoverSubnetId,
    hoverLinkId: ui.hoverLinkId,
    selection: ui.selection,
    tool: store.tool,
    connect: ui.connect,
    ghostSubnet:
      ui.ghostSubnet.active && store.tool === "add-subnet"
        ? ui.ghostSubnet
        : null,
  },
}));
renderer.setInvalidator(invalidate);

// Global handler to start connect mode from an external menu (PeerContext)
function handleStartConnect(e: any) {
  const id = e?.detail?.id as string;
  if (!id) return;
  const p = store.peers.find((pp) => pp.id === id);
  if (!p) return;
  // Ensure tool is connect and initialize connect state
  store.tool = "connect" as any;
  ui.connect.active = true;
  ui.connect.fromPeerId = id;
  ui.connect.fromSubnetId = "";
  ui.connect.ghostTo = { x: p.x, y: p.y };
  // Show selection outline on starting peer
  syncSelection({ type: "peer", id });
  invalidate();
}

// Global handler to start connect mode from a subnet
function handleStartConnectFromSubnet(e: any) {
  const id = e?.detail?.id as string;
  if (!id) return;
  const s = store.subnets.find((ss) => ss.id === id);
  if (!s) return;
  store.tool = "connect" as any;
  ui.connect.active = true;
  ui.connect.fromSubnetId = id;
  ui.connect.fromPeerId = "";
  ui.connect.ghostTo = { x: s.x, y: s.y };
  syncSelection({ type: "subnet", id });
  invalidate();
}

// Watch tool changes to clear connect state when leaving the connect tool
watch(
  () => store.tool,
  (newTool, oldTool) => {
    if (oldTool === "connect" && newTool !== "connect") {
      ui.connect.active = false;
      ui.connect.fromPeerId = "";
      ui.connect.fromSubnetId = "";
      ui.connect.ghostTo = null;
      // Also clear any peer selection outline to avoid stale highlight
      if (ui.selection?.type === "peer") {
        ui.selection = null;
        store.selection = null as any;
      }
      invalidate();
    }
  },
);

function draw() {
  withCtx((ctx, w, h) => renderer.draw(ctx, w, h));
}
function forceInitialRedraw() {
  resizeToParent();
  draw();
}

function screenToWorld(sx: number, sy: number) {
  return {
    x: (sx - store.pan.x) / store.zoom,
    y: (sy - store.pan.y) / store.zoom,
  };
}
function worldToScreen(wx: number, wy: number) {
  return { x: wx * store.zoom + store.pan.x, y: wy * store.zoom + store.pan.y };
}

function onResize() {
  resizeToParent();
  invalidate();
}

function onWheel(e: WheelEvent) {
  e.preventDefault();
  e.stopPropagation();
  const rect = canvasRef.value!.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  const wx = (mx - store.pan.x) / store.zoom;
  const wy = (my - store.pan.y) / store.zoom;
  const factor = Math.exp(-e.deltaY * 0.0015);
  store.zoom = Math.min(2.5, Math.max(0.4, store.zoom * factor));
  store.pan.x = mx - wx * store.zoom;
  store.pan.y = my - wy * store.zoom;
  invalidate();
}

const click = reactive({
  down: false,
  worldX: 0,
  worldY: 0,
  target: "",
  type: "" as "" | "peer" | "subnet" | "link",
  moved: false,
});

function syncSelection(
  sel: null | { type: "peer" | "subnet" | "link"; id: string },
) {
  ui.selection = sel;
  if (!sel) {
    store.selection = null as any;
    selectionSetInternally = true; // mark origin
    return;
  }
  if (sel.type === "peer") {
    const p = store.peers.find((p) => p.id === sel.id);
    store.selection = {
      type: "peer",
      id: sel.id,
      name: p?.name || "Peer",
    } as any;
  } else if (sel.type === "subnet") {
    const s = store.subnets.find((s) => s.id === sel.id);
    store.selection = {
      type: "subnet",
      id: sel.id,
      name: s?.name || "Subnet",
    } as any;
  } else {
    // sel.id passed for link will already be pairKey (a::b). Keep as is.
    store.selection = { type: "link", id: sel.id, name: "Links" } as any;
  }
  // Any selection initiated here is canvas-originated.
  selectionSetInternally = true;
}

function onMouseDown(e: MouseEvent) {
  (window as any).__lastMouseButton = e.button;
  const rect = canvasRef.value!.getBoundingClientRect();
  const sx = e.clientX - rect.left;
  const sy = e.clientY - rect.top;
  const pt = screenToWorld(sx, sy);
  // Pan with middle or shift+left
  if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
    store.pan.dragging = true;
    (store.pan as any).sx = sx;
    (store.pan as any).sy = sy;
    return;
  }

  // Hit tests
  const peer: any = interactions.hitTestPeer(pt);
  const linkHit: any = peer ? null : interactions.hitTestLink(pt);
  const subnet: any = peer || linkHit ? null : interactions.hitTestSubnet(pt);

  // Link takes precedence over subnet when clicked (so subnet menu doesn't steal click)
  if (linkHit) {
    // For cut tool we don't want to set click.type='link' (would skip empty-branch handler). We also avoid changing selection.
    if (store.tool === "cut") {
      click.down = true;
      click.worldX = pt.x;
      click.worldY = pt.y;
      click.type = "";
      click.target = linkHit.id;
      click.moved = false;
      (click as any).sx = sx;
      (click as any).sy = sy;
      // Ensure hoverLinkId reflects the link we clicked (in case mouse moved minimally before hover update)
      ui.hoverLinkId = linkHit.id;
      invalidate();
      return;
    } else {
      function pairKey(a: string, b: string) {
        return a < b ? `${a}::${b}` : `${b}::${a}`;
      }
      const pair = pairKey(linkHit.fromId, linkHit.toId);
      syncSelection({ type: "link", id: pair });
      click.down = true;
      click.worldX = pt.x;
      click.worldY = pt.y;
      click.type = "link";
      click.target = linkHit.id;
      click.moved = false;
      (click as any).sx = sx;
      (click as any).sy = sy;
      invalidate();
      return;
    }
  }

  if (store.tool === "connect" && (peer || subnet)) {
    const targetType = peer ? "peer" : "subnet";
    const tPeer: any = peer;
    const tSubnet: any = subnet;
    if (!ui.connect.active) {
      ui.connect.active = true;
      if (targetType === "peer") {
        ui.connect.fromPeerId = tPeer.id;
        ui.connect.fromSubnetId = "";
        ui.connect.ghostTo = { x: tPeer.x, y: tPeer.y };
        syncSelection({ type: "peer", id: tPeer.id });
      } else {
        ui.connect.fromSubnetId = tSubnet.id;
        ui.connect.fromPeerId = "";
        ui.connect.ghostTo = { x: tSubnet.x, y: tSubnet.y };
        syncSelection({ type: "subnet", id: tSubnet.id });
      }
      invalidate();
      return;
    } else {
      // Second pick
      const fromType = ui.connect.fromPeerId
        ? "peer"
        : ui.connect.fromSubnetId
          ? "subnet"
          : "";
      const fromId = ui.connect.fromPeerId || ui.connect.fromSubnetId;
      const toId = targetType === "peer" ? tPeer.id : tSubnet.id;
      if (!fromType || !fromId) {
        ui.connect.active = false;
        ui.connect.fromPeerId = "";
        ui.connect.fromSubnetId = "";
        ui.connect.ghostTo = null;
        invalidate();
        return;
      }
      if (fromId === toId) {
        ui.connect.active = false;
        ui.connect.fromPeerId = "";
        ui.connect.fromSubnetId = "";
        ui.connect.ghostTo = null;
        invalidate();
        return;
      }
      // Reset connect state
      ui.connect.active = false;
      const _fp = ui.connect.fromPeerId;
      const _fs = ui.connect.fromSubnetId;
      ui.connect.fromPeerId = "";
      ui.connect.fromSubnetId = "";
      ui.connect.ghostTo = null;
      emit("subnet-click", { id: "", x: 0, y: 0 });
      // Dispatch event with types for dialog
      const detail: any = {
        fromId,
        toId,
        fromType,
        toType: targetType,
        from: fromId,
        to: toId,
      };
      window.dispatchEvent(new CustomEvent("request-link-type", { detail }));
      invalidate();
      return;
    }
  }

  if (peer) {
    if (store.tool === "cut") {
      // In cut mode, peer clicks should do nothing.
      invalidate();
      return;
    }
    syncSelection({ type: "peer", id: peer.id });
    // Only start dragging on left button
    if (e.button === 0) {
      interactions.drag.active = true;
      interactions.drag.type = "peer";
      interactions.drag.id = peer.id;
      interactions.drag.offsetX = pt.x - peer.x;
      interactions.drag.offsetY = pt.y - peer.y;
    }
    click.down = true;
    click.worldX = pt.x;
    click.worldY = pt.y;
    click.target = peer.id;
    click.type = "peer";
    click.moved = false;
    (click as any).sx = sx;
    (click as any).sy = sy;
  } else if (subnet) {
    // Resize test first (edges) before move
    const edge = interactions.edgeAtPoint(subnet, pt);
    if (edge && e.button === 0) {
      interactions.resizeDrag.active = true;
      interactions.resizeDrag.id = subnet.id;
      interactions.resizeDrag.edge = edge;
      interactions.resizeDrag.left = subnet.x - subnet.width / 2;
      interactions.resizeDrag.right = subnet.x + subnet.width / 2;
      interactions.resizeDrag.top = subnet.y - subnet.height / 2;
      interactions.resizeDrag.bottom = subnet.y + subnet.height / 2;
      click.down = true;
      click.worldX = pt.x;
      click.worldY = pt.y;
      click.target = subnet.id;
      click.type = "subnet";
      click.moved = false;
      (click as any).sx = sx;
      (click as any).sy = sy;
      invalidate();
      return;
    }
    syncSelection({ type: "subnet", id: subnet.id });
    // Identify descendants using CIDR containment
    const descendants = store.subnets.filter(
      (s) =>
        s.id !== subnet.id &&
        s.cidr &&
        subnet.cidr &&
        cidrContains(subnet.cidr, s.cidr),
    );
    // Policy: a peer only moves with this subnet if its IP belongs to the subnet's CIDR OR its subnetId equals this subnet's id.
    // (Pure geometric overlap should not cause the peer to be captured.)
    interactions.drag.containedPeers = store.peers
      .filter((p) => {
        if (p.subnetId === subnet.id) return true;
        if (p.ip && subnet.cidr && ipInCidr(p.ip, subnet.cidr)) return true;
        return false;
      })
      .map((p) => p.id);
    interactions.drag.containedSubnets = descendants.map((s) => s.id);
    if (e.button === 0) {
      interactions.drag.active = true;
      interactions.drag.type = "subnet";
      interactions.drag.id = subnet.id;
      interactions.drag.offsetX = pt.x - subnet.x;
      interactions.drag.offsetY = pt.y - subnet.y;
    }
    click.down = true;
    click.worldX = pt.x;
    click.worldY = pt.y;
    click.target = subnet.id;
    click.type = "subnet";
    click.moved = false;
    (click as any).sx = sx;
    (click as any).sy = sy;
  } else {
    syncSelection(null);
    click.down = true; // allow empty click tracking (for subnet creation)
    click.worldX = pt.x;
    click.worldY = pt.y;
    click.type = "";
    click.target = "";
    click.moved = false;
    (click as any).sx = sx;
    (click as any).sy = sy;
  }
  invalidate();
}

function onMouseMove(e: MouseEvent) {
  const rect = canvasRef.value!.getBoundingClientRect();
  const sx = e.clientX - rect.left;
  const sy = e.clientY - rect.top;
  const pt = screenToWorld(sx, sy);
  (window as any).__lastPointerScreen = { x: sx, y: sy };
  if (store.pan.dragging) {
    store.pan.x += sx - (store.pan as any).sx;
    store.pan.y += sy - (store.pan as any).sy;
    (store.pan as any).sx = sx;
    (store.pan as any).sy = sy;
    invalidate();
    return;
  }
  if (interactions.resizeDrag.active) {
    const s = store.subnets.find((ss) => ss.id === interactions.resizeDrag.id);
    if (s) {
      let { left, right, top, bottom } = interactions.resizeDrag;
      const minW = interactions.resizeDrag.minW;
      const minH = interactions.resizeDrag.minH;
      if (interactions.resizeDrag.edge.includes("w")) left = pt.x;
      if (interactions.resizeDrag.edge.includes("e")) right = pt.x;
      if (interactions.resizeDrag.edge.includes("n")) top = pt.y; // top edge moves correctly
      if (interactions.resizeDrag.edge.includes("s")) bottom = pt.y;
      // Enforce min sizes
      if (right - left < minW) {
        if (interactions.resizeDrag.edge.includes("w")) left = right - minW;
        else right = left + minW;
      }
      if (bottom - top < minH) {
        if (interactions.resizeDrag.edge.includes("n")) top = bottom - minH;
        else bottom = top + minH;
      }
      // Clamp inside parent (most specific parent)
      const parents = store.subnets.filter(
        (ps) =>
          ps.id !== s.id && ps.cidr && s.cidr && cidrContains(ps.cidr, s.cidr),
      );
      if (parents.length) {
        parents.sort(
          (a, b) =>
            parseInt(b.cidr.split("/")[1]) - parseInt(a.cidr.split("/")[1]),
        );
        const parent = parents[0];
        const margin = 20;
        const pl = parent.x - parent.width / 2 + margin;
        const pr = parent.x + parent.width / 2 - margin;
        const ptp = parent.y - parent.height / 2 + margin;
        const pb = parent.y + parent.height / 2 - margin;
        if (left < pl) left = pl;
        if (right > pr) right = pr;
        if (top < ptp) top = ptp;
        if (bottom > pb) bottom = pb;
      }
      // Prevent shrinking parent past its children: keep all contained subnets fully inside with margin
      {
        const children = store.subnets.filter(
          (cs) =>
            cs.id !== s.id &&
            s.cidr &&
            cs.cidr &&
            cidrContains(s.cidr, cs.cidr),
        );
        if (children.length) {
          const margin = 20;
          let minChildLeft = Infinity,
            maxChildRight = -Infinity,
            minChildTop = Infinity,
            maxChildBottom = -Infinity;
          for (const c of children) {
            const cl = c.x - c.width / 2;
            const cr = c.x + c.width / 2;
            const ct = c.y - c.height / 2;
            const cb = c.y + c.height / 2;
            if (cl < minChildLeft) minChildLeft = cl;
            if (cr > maxChildRight) maxChildRight = cr;
            if (ct < minChildTop) minChildTop = ct;
            if (cb > maxChildBottom) maxChildBottom = cb;
          }
          // Allowed bounds for parent edges given children box + margin
          const minAllowedLeft = minChildLeft - margin;
          const maxAllowedRight = maxChildRight + margin;
          const minAllowedTop = minChildTop - margin;
          const minAllowedBottom = maxChildBottom + margin; // bottom must be at least this
          if (
            interactions.resizeDrag.edge.includes("w") &&
            left > minAllowedLeft
          )
            left = minAllowedLeft;
          if (
            interactions.resizeDrag.edge.includes("e") &&
            right < maxAllowedRight
          )
            right = maxAllowedRight;
          if (interactions.resizeDrag.edge.includes("n") && top > minAllowedTop)
            top = minAllowedTop;
          if (
            interactions.resizeDrag.edge.includes("s") &&
            bottom < minAllowedBottom
          )
            bottom = minAllowedBottom;
          // If resizing diagonally (e.g., 'nw','ne','sw','se'), multiple clamps above will apply together
          // Also ensure we still respect minimum sizes after clamping to children
          if (right - left < minW) {
            if (interactions.resizeDrag.edge.includes("w")) left = right - minW;
            else right = left + minW;
          }
          if (bottom - top < minH) {
            if (interactions.resizeDrag.edge.includes("n")) top = bottom - minH;
            else bottom = top + minH;
          }
        }
      }
      s.width = right - left;
      s.height = bottom - top;
      s.x = left + s.width / 2;
      s.y = top + s.height / 2;
      // Clamp peers now inside new bounds (remove any that fall out)
      const margin = 26;
      const pl = s.x - s.width / 2 + margin;
      const pr = s.x + s.width / 2 - margin;
      const ptp = s.y - s.height / 2 + margin;
      const pb = s.y + s.height / 2 - margin;
      for (const p of store.peers) {
        if (p.subnetId === s.id) {
          if (p.x < pl) p.x = pl;
          if (p.x > pr) p.x = pr;
          if (p.y < ptp) p.y = ptp;
          if (p.y > pb) p.y = pb;
        }
      }
      click.moved = true;
    }
    invalidate();
    return;
  }
  if (interactions.drag.active) {
    if (interactions.drag.type === "peer") {
      const n = store.peers.find((p) => p.id === interactions.drag.id);
      if (n) {
        n.x = pt.x - interactions.drag.offsetX;
        n.y = pt.y - interactions.drag.offsetY;
        interactions.clampPeerToSubnet(n);
      }
    } else if (interactions.drag.type === "subnet") {
      const s = store.subnets.find((ss) => ss.id === interactions.drag.id);
      if (s) {
        const oldX = s.x,
          oldY = s.y;
        s.x = pt.x - interactions.drag.offsetX;
        s.y = pt.y - interactions.drag.offsetY;
        let dx = s.x - oldX,
          dy = s.y - oldY;
        // Clamp inside immediate parent (most specific parent by CIDR length)
        const parents = store.subnets.filter(
          (ps) =>
            ps.id !== s.id &&
            ps.cidr &&
            s.cidr &&
            cidrContains(ps.cidr, s.cidr),
        );
        if (parents.length) {
          parents.sort(
            (a, b) =>
              parseInt(b.cidr.split("/")[1]) - parseInt(a.cidr.split("/")[1]),
          );
          const parent = parents[0];
          const margin = 20;
          const pl = parent.x - parent.width / 2 + margin;
          const pr = parent.x + parent.width / 2 - margin;
          const ptp = parent.y - parent.height / 2 + margin;
          const pb = parent.y + parent.height / 2 - margin;
          if (s.x - s.width / 2 < pl) {
            s.x = pl + s.width / 2;
          }
          if (s.x + s.width / 2 > pr) {
            s.x = pr - s.width / 2;
          }
          if (s.y - s.height / 2 < ptp) {
            s.y = ptp + s.height / 2;
          }
          if (s.y + s.height / 2 > pb) {
            s.y = pb - s.height / 2;
          }
          dx = s.x - oldX;
          dy = s.y - oldY;
        }
        for (const p of store.peers)
          if (interactions.drag.containedPeers.includes(p.id)) {
            p.x += dx;
            p.y += dy;
          }
        for (const sid of interactions.drag.containedSubnets) {
          const cs = store.subnets.find((x) => x.id === sid);
          if (cs) {
            cs.x += dx;
            cs.y += dy;
          }
        }
      }
    }
    if (click.down && !click.moved) {
      const dx = pt.x - click.worldX,
        dy = pt.y - click.worldY;
      if (Math.hypot(dx, dy) > 4 / store.zoom) click.moved = true;
    }
    invalidate();
    return;
  }
  if (click.down && !click.moved) {
    const dx = pt.x - click.worldX,
      dy = pt.y - click.worldY;
    if (Math.hypot(dx, dy) > 4 / store.zoom) click.moved = true;
  }
  // Hover targets
  const peer: any = interactions.hitTestPeer(pt);
  const link = peer ? null : interactions.hitTestLink(pt);
  const subnet: any = peer || link ? null : interactions.hitTestSubnet(pt);
  const newPeerId = peer ? peer.id : null;
  const newSubnetId = subnet ? subnet.id : null;
  // For hover, if a link is hit, store representative link id (first). (Aggregation done in renderer.)
  const newLinkId = link ? link.id : null;
  if (
    newPeerId !== ui.hoverPeerId ||
    newSubnetId !== ui.hoverSubnetId ||
    newLinkId !== ui.hoverLinkId
  ) {
    ui.hoverPeerId = newPeerId;
    ui.hoverSubnetId = newSubnetId;
    ui.hoverLinkId = newLinkId;
    invalidate();
  }
  // Resize cursor feedback when hovering subnet edge (not dragging/resizing)
  if (!interactions.drag.active && !interactions.resizeDrag.active) {
    if (ui.hoverLinkId) {
      (canvasRef.value as any).style.cursor = "pointer";
    } else if (subnet) {
      const edge = interactions.edgeAtPoint(subnet, pt);
      if (edge) {
        let cursor = "default";
        if (edge === "n" || edge === "s") cursor = "ns-resize";
        else if (edge === "e" || edge === "w") cursor = "ew-resize";
        else if (
          edge === "ne" ||
          edge === "en" ||
          edge === "sw" ||
          edge === "ws"
        )
          cursor = "nesw-resize";
        else if (
          edge === "nw" ||
          edge === "wn" ||
          edge === "se" ||
          edge === "es"
        )
          cursor = "nwse-resize";
        (canvasRef.value as any).style.cursor = cursor;
      } else {
        (canvasRef.value as any).style.cursor = peer ? "pointer" : "default";
      }
    } else {
      (canvasRef.value as any).style.cursor =
        peer || ui.hoverLinkId ? "pointer" : "default";
    }
  }
  // Connect ghost line
  if (
    store.tool === "connect" &&
    ui.connect.active &&
    (ui.connect.fromPeerId || (ui.connect as any).fromSubnetId)
  ) {
    ui.connect.ghostTo = { x: pt.x, y: pt.y };
    invalidate();
  }
  // Ghost subnet preview
  if (
    store.tool === "add-subnet" &&
    !interactions.drag.active &&
    !ui.ghostSubnet.frozen
  ) {
    ui.ghostSubnet.active = true;
    ui.ghostSubnet.x = pt.x;
    ui.ghostSubnet.y = pt.y;
    invalidate();
  }
  // Update tool indicator
  indicator.x = e.clientX;
  indicator.y = e.clientY;
  if (store.tool === "connect") {
    indicator.visible = true;
    indicator.label = ui.connect.active
      ? "Select target peer or subnet"
      : "Pick first peer or subnet";
    indicator.icon =
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="3"/><circle cx="19" cy="12" r="3"/><line x1="8" y1="12" x2="16" y2="12"/></svg>';
  } else if (store.tool === "cut") {
    indicator.visible = true;
    indicator.label = "Cut links";
    indicator.icon =
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="11"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="13" x2="20" y2="20"/></svg>';
  } else {
    indicator.visible = false;
  }
}

function onMouseUp() {
  store.pan.dragging = false;
  interactions.drag.active = false;
  if (interactions.resizeDrag.active) {
    interactions.resizeDrag.active = false;
    invalidate();
  }
  // Open peer context menu only on right-click when in select tool mode (left-click just selects)
  if (
    click.down &&
    !click.moved &&
    click.type === "peer" &&
    click.target &&
    store.tool === "select" &&
    (window as any).__lastMouseButton === 2
  ) {
    emit("peer-click", {
      id: click.target,
      x: (click as any).sx,
      y: (click as any).sy,
    });
  }
  if (
    click.down &&
    !click.moved &&
    ((click.type === "" && ui.hoverLinkId) ||
      (store.tool === "cut" && ui.hoverLinkId))
  ) {
    if (store.tool === "cut") {
      const baseLink = store.links.find((l) => l.id === ui.hoverLinkId);
      if (baseLink) {
        function pairKey(a: string, b: string) {
          return a < b ? `${a}::${b}` : `${b}::${a}`;
        }
        const pk = pairKey(baseLink.fromId, baseLink.toId);
        const related = store.links.filter(
          (l) => pairKey(l.fromId, l.toId) === pk,
        );
        window.dispatchEvent(
          new CustomEvent("request-cut-link", {
            detail: { pairKey: pk, links: related },
          }),
        );
      }
    } else {
      const real = store.links.find((l) => l.id === ui.hoverLinkId);
      if (real) {
        function pairKey(a: string, b: string) {
          return a < b ? `${a}::${b}` : `${b}::${a}`;
        }
        syncSelection({ type: "link", id: pairKey(real.fromId, real.toId) });
      }
    }
  }
  // Open subnet context menu only on right-click (left-click just selects)
  if (
    click.down &&
    !click.moved &&
    click.type === "subnet" &&
    click.target &&
    (window as any).__lastMouseButton === 2
  ) {
    emit("subnet-click", {
      id: click.target,
      x: (click as any).sx,
      y: (click as any).sy,
    });
  }
  // Create subnet on empty click in add-subnet tool
  if (
    click.down &&
    !click.moved &&
    click.type === "" &&
    store.tool === "add-subnet"
  ) {
    // Freeze current ghost position and emit request so parent can open creation dialog.
    ui.ghostSubnet.frozen = true;
    ui.ghostSubnet.active = true; // keep visible
    emit("add-subnet-request", {
      worldX: click.worldX,
      worldY: click.worldY,
      screenX: (click as any).sx,
      screenY: (click as any).sy,
    });
  }
  // Right-click on empty canvas opens network actions menu
  if (
    click.down &&
    !click.moved &&
    click.type === "" &&
    (window as any).__lastMouseButton === 2 &&
    store.tool === "select"
  ) {
    emit("canvas-context", { x: (click as any).sx, y: (click as any).sy });
  }
  click.down = false;
  interactions.enforceSubnetHierarchy();
  invalidate();
}

function onKeydown(e: KeyboardEvent) {
  if (
    (e.key === "Delete" || e.key === "Backspace") &&
    !(e.target as HTMLElement).matches("input,textarea")
  ) {
    e.preventDefault();
    // Instead of immediate deletion, dispatch an event so the page can open the proper confirmation dialog.
    if (store.selection) {
      const sel = store.selection;
      window.dispatchEvent(
        new CustomEvent("request-delete", {
          detail: { type: sel.type, id: sel.id },
        }),
      );
    }
    return;
  }
  if (e.key === "Escape") {
    store.tool = "select";
    ui.connect.active = false;
    ui.connect.fromPeerId = "";
    ui.connect.fromSubnetId = "";
    ui.connect.ghostTo = null;
  }
}

onMounted(() => {
  function focusSubnet(id: string) {
    const s = store.subnets.find((ss) => ss.id === id);
    if (!s || !canvasRef.value) return;
    const canvas = canvasRef.value;
    const vw = canvas.width,
      vh = canvas.height;
    const margin = 100;
    let targetZoom = Math.min(
      (vw - margin * 2) / Math.max(40, s.width),
      (vh - margin * 2) / Math.max(40, s.height),
    );
    targetZoom = Math.min(2.5, Math.max(0.4, targetZoom));
    const startZoom = store.zoom;
    const startPanX = store.pan.x,
      startPanY = store.pan.y;
    const targetPanX = vw / 2 - s.x * targetZoom;
    const targetPanY = vh / 2 - s.y * targetZoom;
    const duration = 300;
    const start = performance.now();
    function step(ts: number) {
      const tRaw = (ts - start) / duration;
      const t = Math.min(1, Math.max(0, tRaw));
      // easeInOut (approx) for smoother motion
      const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
      store.zoom = startZoom + (targetZoom - startZoom) * ease;
      store.pan.x = startPanX + (targetPanX - startPanX) * ease;
      store.pan.y = startPanY + (targetPanY - startPanY) * ease;
      invalidate();
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function syncExternalSelection() {
    const sel = store.selection;
    if (!sel) {
      if (ui.selection) {
        ui.selection = null;
        invalidate();
      }
      // Reset the internal-origin flag so the next inspector subnet selection can trigger a focus
      selectionSetInternally = false;
      return;
    }
    // Update internal ui.selection if different
    if (
      !ui.selection ||
      ui.selection.id !== sel.id ||
      ui.selection.type !== sel.type
    ) {
      ui.selection = { type: sel.type as any, id: sel.id };
      invalidate();
    }
    // Decide focus behavior: focus only for inspector-originated subnet selections (not canvas clicks)
    const inspectorFlag = (window as any).__selectionFromInspector === true;
    if (sel.type === "subnet" && inspectorFlag && !selectionSetInternally) {
      focusSubnet(sel.id);
    }
    // Reset origin markers
    selectionSetInternally = false;
    if (inspectorFlag) {
      try {
        delete (window as any).__selectionFromInspector;
      } catch {}
    }
  }

  resizeToParent();
  loop(draw);
  // Redraw bus listener
  watch(
    () => bus.tick,
    () => invalidate(),
  );
  window.addEventListener("resize", onResize);
  window.addEventListener("topology-updated", forceInitialRedraw);
  // Allow external trigger to start connect from a specific peer
  window.addEventListener("start-connect-from-peer", handleStartConnect as any);
  window.addEventListener(
    "start-connect-from-subnet",
    handleStartConnectFromSubnet as any,
  );
  const c = canvasRef.value!;
  c.addEventListener("wheel", onWheel as any, { passive: false });
  c.addEventListener("mousedown", onMouseDown as any);
  window.addEventListener("mousemove", onMouseMove as any);
  window.addEventListener("mouseup", onMouseUp as any);
  window.addEventListener("keydown", onKeydown as any);

  // Initial sync (in case selection pre-exists)
  syncExternalSelection();
  // Watch for external selection changes (e.g., from inspector)
  watch(
    () => ({ id: store.selection?.id, type: store.selection?.type }),
    () => syncExternalSelection(),
  );
});

// External API to clear frozen ghost when dialog closes
function clearGhostSubnet() {
  ui.ghostSubnet.active = false;
  ui.ghostSubnet.frozen = false;
  invalidate();
}
defineExpose({ clearGhostSubnet });

onUnmounted(() => {
  window.removeEventListener("resize", onResize);
  window.removeEventListener("topology-updated", forceInitialRedraw);
  window.removeEventListener(
    "start-connect-from-peer",
    handleStartConnect as any,
  );
  window.removeEventListener(
    "start-connect-from-subnet",
    handleStartConnectFromSubnet as any,
  );
  const c = canvasRef.value;
  if (c) {
    c.removeEventListener("wheel", onWheel as any);
    c.removeEventListener("mousedown", onMouseDown as any);
  }
  window.removeEventListener("mousemove", onMouseMove as any);
  window.removeEventListener("mouseup", onMouseUp as any);
  window.removeEventListener("keydown", onKeydown as any);
});
</script>

<style scoped>
.vpn-canvas {
  background: #181818;
  border-radius: 10px;
  display: block;
}
.canvas-wrapper {
  position: relative;
}
.tool-indicator {
  position: fixed;
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  font-family: Roboto, sans-serif;
  font-size: 11px;
  font-weight: 500;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
}
.tool-indicator .icon {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
}
.tool-indicator .label {
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 5px;
}
</style>
