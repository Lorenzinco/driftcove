import type { Subnet } from '@/types/network'

export interface Point {
  x: number
  y: number
}

export interface RectBounds {
  left: number
  right: number
  top: number
  bottom: number
}

export function pairKey (a: string, b: string) {
  return a < b ? `${a}::${b}` : `${b}::${a}`
}

export function cidrPrefixLength (cidr: string) {
  return Number.parseInt(cidr.split('/')[1] || '0', 10)
}

export function subnetBounds (subnet: Pick<Subnet, 'x' | 'y' | 'width' | 'height'>, margin = 0): RectBounds {
  return {
    left: subnet.x - subnet.width / 2 + margin,
    right: subnet.x + subnet.width / 2 - margin,
    top: subnet.y - subnet.height / 2 + margin,
    bottom: subnet.y + subnet.height / 2 - margin,
  }
}

export function containsPoint (bounds: RectBounds, point: Point) {
  return point.x >= bounds.left && point.x <= bounds.right && point.y >= bounds.top && point.y <= bounds.bottom
}

export function distancePointToSegment (point: Point, a: Point, b: Point) {
  const vx = b.x - a.x
  const vy = b.y - a.y
  const wx = point.x - a.x
  const wy = point.y - a.y
  const c1 = vx * wx + vy * wy
  if (c1 <= 0) {
    return Math.hypot(point.x - a.x, point.y - a.y)
  }

  const c2 = vx * vx + vy * vy
  if (c2 <= c1) {
    return Math.hypot(point.x - b.x, point.y - b.y)
  }

  const t = c1 / c2
  return Math.hypot(point.x - (a.x + vx * t), point.y - (a.y + vy * t))
}

export function rectangleBoundaryTowardPoint (subnet: Pick<Subnet, 'x' | 'y' | 'width' | 'height'>, point: Point): Point {
  const vx = point.x - subnet.x
  const vy = point.y - subnet.y
  if (vx === 0 && vy === 0) {
    return { x: subnet.x + subnet.width / 2, y: subnet.y }
  }

  const scaleX = Math.abs(vx) / (subnet.width / 2 || 1e-6)
  const scaleY = Math.abs(vy) / (subnet.height / 2 || 1e-6)
  const t = Math.max(scaleX, scaleY) || 1
  return { x: subnet.x + vx / t, y: subnet.y + vy / t }
}
