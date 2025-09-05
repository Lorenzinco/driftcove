import { ref, onMounted, onUnmounted } from 'vue';

export function useCanvas() {
  const canvasRef = ref<HTMLCanvasElement|null>(null);
  const ctxRef = ref<CanvasRenderingContext2D|null>(null);
  const dpr = window.devicePixelRatio || 1;
  let rafId: number | null = null;
  let needsDraw = true;

  function withCtx<T>(fn:(ctx:CanvasRenderingContext2D, w:number, h:number)=>T): T|undefined {
    const canvas = canvasRef.value; const ctx = ctxRef.value;
    if (!canvas || !ctx) return;
    const w = canvas.width / dpr, h = canvas.height / dpr;
    return fn(ctx, w, h);
  }

  function resizeToParent() {
    const c = canvasRef.value; if (!c) return;
    const rect = (c.parentElement as HTMLElement).getBoundingClientRect();
    const width = Math.max(600, rect.width);
    const height = Math.max(400, rect.height);
    c.width = Math.round(width * dpr);
    c.height = Math.round(height * dpr);
    const ctx = c.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
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

  onMounted(() => resizeToParent());
  onUnmounted(() => { if (rafId != null) cancelAnimationFrame(rafId); });

  return { canvasRef, ctxRef, dpr, withCtx, resizeToParent, loop, invalidate };
}
