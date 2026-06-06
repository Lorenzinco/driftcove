import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useBackendInteractionStore } from '../backendInteraction'
import { useNetworkStore } from '../network'

const mockClient = {
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
  defaults: { headers: { common: {} as Record<string, string> } },
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
}

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockClient),
  },
}))

function resetStores () {
  setActivePinia(createPinia())
  const network = useNetworkStore()
  network.peers = []
  network.subnets = []
  network.links = []
  const backend = useBackendInteractionStore()
  backend.stopCoordinatePushing()
  backend.stopTopologyPolling()
  backend.hasFetchedOnce = false
  backend.lastError = null
  return { backend, network }
}

describe('backend interaction store', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockClient.get.mockReset()
    mockClient.post.mockReset()
    mockClient.delete.mockReset()
    mockClient.post.mockResolvedValue({ data: {} })
    mockClient.defaults.headers.common = {}
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
  })

  it('stores API tokens in memory and applies them to the axios client', async () => {
    const { backend } = resetStores()

    backend.setApiToken('token-123')

    expect(backend.apiToken).toBe('token-123')
    // Force client creation; the request interceptor will also read the token at request time.
    await backend.uploadTopology({})
    backend.setApiToken('token-456')
    expect(mockClient.defaults.headers.common.Authorization).toBe(
      'Bearer token-456',
    )

    backend.setApiToken('')
    expect(mockClient.defaults.headers.common.Authorization).toBeUndefined()
  })

  it('fetches normalized topology and adapts it into the network store', async () => {
    const { backend, network } = resetStores()
    const topologyUpdated = vi.fn()
    window.addEventListener('topology-updated', topologyUpdated)
    mockClient.get.mockResolvedValueOnce({
      data: {
        topology: {
          subnets: {
            '10.0.1.0/24': {
              subnet: '10.0.1.0/24',
              name: 'Office',
              description: 'Office subnet',
              x: 500,
              y: 300,
              width: 420,
              height: 260,
              rgba: 0x00_ff_00_e5,
            },
          },
          peers: {
            '10.0.1.10': {
              username: 'alice',
              address: '10.0.1.10',
              public_key: 'alice-key',
              preshared_key: 'alice-psk',
              x: 530,
              y: 310,
              rx: 100,
              tx: 200,
              last_handshake: 300,
              services: {
                ssh: {
                  name: 'ssh',
                  port: 22,
                  protocol: 'tcp',
                  department: 'ops',
                },
              },
            },
            '10.0.1.11': {
              username: 'bob',
              address: '10.0.1.11',
              public_key: 'bob-key',
              x: 560,
              y: 330,
              rx: 10,
              tx: 20,
              last_handshake: 30,
              services: {},
            },
          },
          network: {
            '10.0.1.0/24': [
              { public_key: 'alice-key' },
              { public_key: 'bob-key' },
            ],
          },
          subnet_links: {
            '10.0.1.0/24': [{ public_key: 'alice-key' }],
          },
          p2p_links: {
            '10.0.1.10': [{ public_key: 'bob-key' }],
          },
          service_links: {
            ssh: [{ public_key: 'bob-key' }],
          },
        },
      },
    })

    await backend.fetchTopology(true)
    backend.stopCoordinatePushing()
    window.removeEventListener('topology-updated', topologyUpdated)

    expect(mockClient.get).toHaveBeenCalledWith('/api/network/topology')
    expect(network.subnets).toEqual([
      expect.objectContaining({
        id: '10.0.1.0/24',
        name: 'Office',
        cidr: '10.0.1.0/24',
        description: 'Office subnet',
        x: 500,
        y: 300,
        width: 420,
        height: 260,
        rgba: 0x00_ff_00_e5,
      }),
    ])
    expect(network.peers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: 'alice-key',
          name: 'alice',
          ip: '10.0.1.10',
          subnetId: '10.0.1.0/24',
          public: true,
          host: true,
          publicKey: 'alice-key',
          presharedKey: 'alice-psk',
          rx: 100,
          tx: 200,
          lastHandshake: 300,
        }),
        expect.objectContaining({
          id: 'bob-key',
          name: 'bob',
          ip: '10.0.1.11',
          subnetId: '10.0.1.0/24',
          public: false,
          host: false,
        }),
      ]),
    )
    expect(network.links).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          fromId: 'alice-key',
          toId: '10.0.1.0/24',
          kind: 'membership',
        }),
        expect.objectContaining({
          fromId: 'alice-key',
          toId: 'bob-key',
          kind: 'p2p',
        }),
        expect.objectContaining({
          fromId: 'alice-key',
          toId: 'bob-key',
          kind: 'service',
          serviceName: 'ssh',
        }),
      ]),
    )
    expect(topologyUpdated).toHaveBeenCalledTimes(1)
    expect(backend.hasFetchedOnce).toBe(true)
    expect(backend.lastError).toBeNull()
  })

  it('builds backend payloads from the editable network topology', () => {
    const { backend, network } = resetStores()
    network.subnets = [
      {
        id: 'subnet-a',
        cidr: '10.0.1.0/24',
        name: 'Office',
        description: 'Office subnet',
        x: 500,
        y: 300,
        width: 420,
        height: 260,
        rgba: 0x00_ff_00_e5,
      },
    ]
    network.peers = [
      {
        id: 'host-id',
        name: 'host',
        ip: '10.0.1.10',
        subnetId: 'subnet-a',
        x: 530,
        y: 310,
        publicKey: 'host-key',
        presharedKey: 'host-psk',
        public: true,
        host: true,
        services: {
          ssh: {
            name: 'ssh',
            port: 22,
            protocol: 'tcp',
            department: 'ops',
            description: 'Shell',
          },
        },
        rx: 0,
        tx: 0,
        lastHandshake: 0,
      },
      {
        id: 'client-id',
        name: 'client',
        ip: '10.0.1.11',
        subnetId: 'subnet-a',
        x: 560,
        y: 330,
        publicKey: 'client-key',
        public: true,
        host: false,
        services: {},
        rx: 0,
        tx: 0,
        lastHandshake: 0,
      },
    ]
    network.links = [
      {
        id: 'membership',
        fromId: 'host-id',
        toId: 'subnet-a',
        kind: 'membership',
      },
      { id: 'p2p', fromId: 'client-id', toId: 'host-id', kind: 'p2p' },
      {
        id: 'service',
        fromId: 'host-id',
        toId: 'client-id',
        kind: 'service',
        serviceName: 'ssh',
      },
    ]

    const payload = backend.buildCurrentTopologyPayload()

    expect(payload.subnets['10.0.1.0/24']).toMatchObject({
      subnet: '10.0.1.0/24',
      name: 'Office',
      description: 'Office subnet',
      x: 500,
      y: 300,
      width: 420,
      height: 260,
      rgba: 0x00_ff_00_e5,
    })
    expect(payload.peers['10.0.1.10']).toMatchObject({
      username: 'host',
      address: '10.0.1.10',
      public_key: 'host-key',
      preshared_key: 'host-psk',
      services: { ssh: expect.objectContaining({ port: 22 }) },
    })
    expect(payload.peers['10.0.1.11'].services).toEqual({})
    expect(payload.services.ssh).toMatchObject({
      name: 'ssh',
      department: 'ops',
      port: 22,
      description: 'Shell',
    })
    expect(payload.subnet_links['10.0.1.0/24']).toEqual([
      expect.objectContaining({ username: 'host', public_key: 'host-key' }),
    ])
    expect(payload.p2p_links['10.0.1.10']).toEqual([
      expect.objectContaining({ username: 'client', public_key: 'client-key' }),
    ])
    expect(payload.service_links.ssh).toEqual([
      expect.objectContaining({ username: 'client', public_key: 'client-key' }),
    ])
  })
})
