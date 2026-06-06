export interface RgbaComponents {
  r: number
  g: number
  b: number
  a: number
}

export function rgbaNumberToComponents (rgba: number): RgbaComponents {
  return {
    r: (rgba >> 24) & 0xff,
    g: (rgba >> 16) & 0xff,
    b: (rgba >> 8) & 0xff,
    a: (rgba & 0xff) / 255,
  }
}

export function componentsToRgbaNumber ({ r, g, b, a }: RgbaComponents): number {
  const aByte = Math.round(a * 255) & 0xff
  return ((r & 0xff) << 24) | ((g & 0xff) << 16) | ((b & 0xff) << 8) | aByte
}

export function alphaToHex (a: number): string {
  return Math.round(a * 255).toString(16).padStart(2, '0')
}

export function componentsToHex ({ r, g, b, a }: RgbaComponents): string {
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}${alphaToHex(a)}`
}

export function parseHexColor (value: string, defaultAlpha = 0.9): RgbaComponents | null {
  const hex = value.replace('#', '').trim()
  if (![6, 8].includes(hex.length)) {
    return null
  }

  const r = Number.parseInt(hex.slice(0, 2), 16)
  const g = Number.parseInt(hex.slice(2, 4), 16)
  const b = Number.parseInt(hex.slice(4, 6), 16)
  const a = hex.length === 8 ? Number.parseInt(hex.slice(6, 8), 16) / 255 : defaultAlpha

  if ([r, g, b, a].some(part => Number.isNaN(part))) {
    return null
  }
  return { r, g, b, a }
}
