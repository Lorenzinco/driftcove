import type { Link } from '@/types/network'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useNetworkStore } from '../network'

function resetStore () {
  setActivePinia(createPinia())
  const store = useNetworkStore()
  store.peers = []
  store.subnets = []
  store.links = []
  store.selection = null
  store.baselineSignature = null
  return store
}

describe('network store', () => {
  beforeEach(() => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
  })

  it('adds a subnet at the requested location and selects it', () => {
    const store = resetStore()

    store.addSubnetAt(120, 240, 0x11_22_33_44)

    expect(store.subnets).toHaveLength(1)
    expect(store.subnets[0]).toMatchObject({
      name: 'Subnet',
      cidr: '10.0.0.0/24',
      x: 120,
      y: 240,
      width: 320,
      height: 200,
      rgba: 0x11_22_33_44,
    })
    expect(store.selection).toEqual({
      type: 'subnet',
      id: store.subnets[0].id,
      name: 'Subnet',
    })
    expect(store.tool).toBe('select')
  })

  it('deletes selected peers and removes their links', () => {
    const store = resetStore()
    store.peers = [
      { id: 'peer-a', name: 'Peer A', ip: '10.0.0.2', x: 0, y: 0, rx: 0, tx: 0, lastHandshake: 0 },
      { id: 'peer-b', name: 'Peer B', ip: '10.0.0.3', x: 0, y: 0, rx: 0, tx: 0, lastHandshake: 0 },
    ]
    store.links = [
      { id: 'link-1', fromId: 'peer-a', toId: 'peer-b', kind: 'p2p' },
      { id: 'link-2', fromId: 'peer-b', toId: 'subnet-a', kind: 'membership' },
    ]
    store.selection = { type: 'peer', id: 'peer-a', name: 'Peer A' }

    store.deleteSelection()

    expect(store.peers.map(peer => peer.id)).toEqual(['peer-b'])
    expect(store.links).toEqual([{ id: 'link-2', fromId: 'peer-b', toId: 'subnet-a', kind: 'membership' }])
    expect(store.selection).toBeNull()
  })

  it('applies backend topology while preserving existing subnet geometry and color edits', () => {
    const store = resetStore()
    store.subnets = [
      {
        id: '10.0.0.0/24',
        name: 'Old name',
        cidr: '10.0.0.0/24',
        x: 10,
        y: 20,
        width: 300,
        height: 200,
        rgba: 0xaa_bb_cc_dd,
      },
    ]
    store.peers = [
      {
        id: 'peer-a-key',
        name: 'Old Peer',
        ip: '10.0.0.2',
        subnetId: '10.0.0.0/24',
        x: 15,
        y: 25,
        public: false,
        services: {},
        rx: 1,
        tx: 2,
        lastHandshake: 3,
      },
    ]
    const links: Link[] = [
      { id: 'link-1', fromId: 'peer-a-key', toId: '10.0.0.0/24', kind: 'membership' },
    ]

    store.applyBackendTopology({
      subnets: [
        {
          id: '10.0.0.0/24',
          name: 'Office LAN',
          cidr: '10.0.0.0/24',
          description: 'Main subnet',
          x: 999,
          y: 999,
          width: 999,
          height: 999,
          rgba: 0x01_02_03_04,
        },
      ],
      peers: [
        {
          id: 'peer-a-key',
          name: 'Peer A',
          ip: '10.0.0.2',
          subnetId: '10.0.0.0/24',
          services: { http: { name: 'http', port: 80, protocol: 'tcp' } },
          publicKey: 'peer-a-key',
          presharedKey: 'psk',
          rx: 10,
          tx: 20,
          lastHandshake: 30,
        },
      ],
      links,
    })

    expect(store.subnets[0]).toMatchObject({
      name: 'Office LAN',
      cidr: '10.0.0.0/24',
      description: 'Main subnet',
      x: 10,
      y: 20,
      width: 300,
      height: 200,
      rgba: 0xaa_bb_cc_dd,
    })
    expect(store.peers[0]).toMatchObject({
      id: 'peer-a-key',
      name: 'Peer A',
      ip: '10.0.0.2',
      subnetId: '10.0.0.0/24',
      public: true,
      host: true,
      publicKey: 'peer-a-key',
      presharedKey: 'psk',
      rx: 10,
      tx: 20,
      lastHandshake: 30,
    })
    expect(store.links).toEqual(links)
    expect(store.topologyDirty).toBe(false)
  })
})
