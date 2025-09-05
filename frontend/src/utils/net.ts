export function ipToInt(ip: string): number | null {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;
  let n = 0;
  for (const p of parts) {
    const v = Number(p);
    if (!Number.isInteger(v) || v < 0 || v > 255) return null;
    n = (n << 8) | v;
  }
  return n >>> 0;
}

export function cidrRange(cidr: string): { base: number; mask: number; bits: number } | null {
  const [ip, bitsStr] = cidr.split('/');
  const bits = Number(bitsStr);
  if (!ip || !Number.isInteger(bits) || bits < 0 || bits > 32) return null;
  const base = ipToInt(ip); if (base == null) return null;
  const mask = bits === 0 ? 0 : (~0 << (32 - bits)) >>> 0;
  return { base: base & mask, mask, bits };
}

export function ipInCidr(ip: string, cidr: string): boolean {
  const r = cidrRange(cidr); const v = ipToInt(ip);
  return !!(r && v != null && ((v & r.mask) === r.base));
}

export function cidrContains(a: string, b: string): boolean {
  const A = cidrRange(a), B = cidrRange(b);
  if (!A || !B) return false;
  if (A.bits > B.bits) return false;
  return (B.base & A.mask) === A.base;
}
