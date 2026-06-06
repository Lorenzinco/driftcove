import type { Link, Peer, Subnet } from '@/types/network'

function byId<T extends { id: string }> (a: T, b: T) {
  return a.id < b.id ? -1 : (a.id > b.id ? 1 : 0)
}

export function buildCoordinateSignature (subnets: Subnet[], peers: Peer[]): string {
  const serializedSubnets = subnets
    .map(s => ({ id: s.id, x: s.x, y: s.y, w: s.width, h: s.height, c: s.rgba }))
    .sort(byId)
  const serializedPeers = peers.map(p => ({ id: p.id, x: p.x, y: p.y })).sort(byId)
  return JSON.stringify({ S: serializedSubnets, P: serializedPeers })
}

export function buildTopologySignature (subnets: Subnet[], peers: Peer[], links: Link[]): string {
  const serializedSubnets = [...subnets]
    .map(s => ({
      id: s.id,
      name: s.name,
      cidr: s.cidr,
      x: s.x,
      y: s.y,
      w: s.width,
      h: s.height,
      rgba: s.rgba,
    }))
    .sort(byId)

  const serializedPeers = [...peers]
    .map(p => ({
      id: p.id,
      name: p.name,
      ip: p.ip,
      subnetId: p.subnetId || '',
      x: p.x,
      y: p.y,
      publicKey: p.publicKey || '',
      presharedKey: p.presharedKey || '',
      services: Object.keys(p.services || {})
        .sort()
        .map(name => {
          const service = p.services?.[name]
          return {
            name,
            port: service?.port,
            dept: service?.department,
            desc: service?.description,
          }
        }),
    }))
    .sort(byId)

  const serializedLinks = [...links]
    .map(l => ({
      kind: l.kind,
      from: l.fromId,
      to: l.toId,
      service: l.serviceName || '',
    }))
    .sort((a, b) => {
      if (a.kind !== b.kind) {
        return a.kind < b.kind ? -1 : 1
      }
      if (a.from !== b.from) {
        return a.from < b.from ? -1 : 1
      }
      if (a.to !== b.to) {
        return a.to < b.to ? -1 : 1
      }
      return a.service < b.service ? -1 : (a.service > b.service ? 1 : 0)
    })

  return JSON.stringify({ subnets: serializedSubnets, peers: serializedPeers, links: serializedLinks })
}
