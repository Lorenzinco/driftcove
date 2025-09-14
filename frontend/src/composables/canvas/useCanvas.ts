import { ref, onMounted, onUnmounted } from 'vue';

export function useCanvas() {
  const canvasRef = ref<HTMLCanvasElement|null>(null);
  const ctxRef = ref<CanvasRenderingContext2D|null>(null);
  const dpr = window.devicePixelRatio || 1;
  let rafId: number | null = null;
  let needsDraw = true;
  let ro: ResizeObserver | null = null;

  function withCtx<T>(fn:(ctx:CanvasRenderingContext2D, w:number, h:number)=>T): T|undefined {
    const canvas = canvasRef.value; const ctx = ctxRef.value;
    if (!canvas || !ctx) return;
  // Report logical drawing size in CSS pixels (1:1 with canvas attrs).
  const w = canvas.width, h = canvas.height;
    return fn(ctx, w, h);
  }

  function resizeToParent() {
    const c = canvasRef.value; if (!c) return;
  const parent = c.parentElement as HTMLElement | null; if (!parent) return;
  // Compute parent's content box (client size minus paddings) to fit inside padding nicely.
  const cs = getComputedStyle(parent);
  const padL = parseFloat(cs.paddingLeft || '0');
  const padR = parseFloat(cs.paddingRight || '0');
  const padT = parseFloat(cs.paddingTop || '0');
  const padB = parseFloat(cs.paddingBottom || '0');
  const width = Math.max(1, Math.floor(parent.clientWidth - padL - padR));
  const height = Math.max(1, Math.floor(parent.clientHeight - padT - padB));
  // Control size via element attributes only (no CSS scaling, no DPR back buffer scaling).
  c.width = Math.max(1, Math.floor(width));
  c.height = Math.max(1, Math.floor(height));
    const ctx = c.getContext('2d')!;
  // Identity transform; drawing coordinates are in CSS pixels.
  ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctxRef.value = ctx;
    invalidate();
  }

  function loop(draw: ()=>void) {
    const tick = () => {
      rafId = requestAnimationFrame(tick);
      if (needsDraw) { needsDraw = false; draw(); }
    };
    rafId = requestAnimationFrame(tick);
  }

  function invalidate() { needsDraw = true; }

  onMounted(() => {
    resizeToParent();
    // Observe parent size changes (e.g., layout panes opening/closing) and resize canvas accordingly.
    const c = canvasRef.value; const parent = c?.parentElement as HTMLElement | null;
    if (parent && 'ResizeObserver' in window) {
      ro = new ResizeObserver(() => resizeToParent());
      ro.observe(parent);
    }
  });
  onUnmounted(() => {
    if (rafId != null) cancelAnimationFrame(rafId);
    if (ro) { try { ro.disconnect(); } catch {}
      ro = null; }
  });

  return { canvasRef, ctxRef, dpr, withCtx, resizeToParent, loop, invalidate };
}
