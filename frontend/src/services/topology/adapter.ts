import type { Link, Peer, ServiceInfo, Subnet } from "@/types/network";
import { pairKey } from "@/utils/networkTopology";

export interface AdaptedPeer {
  id: string;
  name: string;
  ip: string;
  subnetId: string | null;
  x?: number;
  y?: number;
  services?: Record<string, ServiceInfo>;
  host?: boolean;
  presharedKey?: string;
  publicKey?: string;
  rx: number;
  tx: number;
  lastHandshake: number;
}

export interface AdaptedSubnet extends Subnet {
  name: string;
}

export interface AdaptedTopology {
  peers: AdaptedPeer[];
  subnets: AdaptedSubnet[];
  links: Link[];
}

function isNumber (value: unknown): value is number {
  return typeof value === "number" && !Number.isNaN(value);
}

function hasServicePort (services: Record<string, any>) {
  return Object.values(services || {}).some((service: any) =>
    isNumber(service?.port),
  );
}

function rawTargetCidr (value: any) {
  return (
    value?.subnet || value?.cidr || (typeof value === "string" ? value : null)
  );
}

export function adaptBackendTopology (raw: any): AdaptedTopology {
  const topo = raw?.topology || raw || {};
  const subnetsDict = topo.subnets || {};
  const peersDict = topo.peers || {};
  const serviceLinksDict: Record<string, any[]> = topo.service_links || {};
  const p2pLinksDict: Record<string, any[]> = topo.p2p_links || {};
  const subnetLinksDict: Record<string, any[]> = topo.subnet_links || {};
  const subnetToSubnetDict: Record<string, any[]>
    = topo.subnet_to_subnet_links || {};
  const subnetToServiceDict: Record<string, any[]>
    = topo.subnet_to_service_links || {};
  const adminPeerToPeer: Record<string, any[]>
    = topo.admin_peer_to_peer_links || {};
  const adminPeerToSubnet: Record<string, any[]>
    = topo.admin_peer_to_subnet_links || {};
  const adminSubnetToSubnet: Record<string, any[]>
    = topo.admin_subnet_to_subnet_links || {};
  const networkDict: Record<string, any[]> = topo.network || {};

  const subnets: AdaptedTopology["subnets"] = Object.keys(subnetsDict)
    .map(cidr => {
      const subnet = subnetsDict[cidr];
      if (!subnet) {
        return null;
      }
      return {
        id: cidr,
        name: subnet.name || cidr,
        cidr,
        description: subnet.description,
        x: subnet.x,
        y: subnet.y,
        width: subnet.width,
        height: subnet.height,
        rgba: subnet.rgba,
      } as AdaptedSubnet;
    })
    .filter(Boolean) as AdaptedSubnet[];

  const contained: Record<string, string> = {};
  for (const cidr of Object.keys(networkDict)) {
    for (const peer of networkDict[cidr] || []) {
      if (peer?.public_key) {
        contained[peer.public_key] = cidr;
      }
    }
  }

  const peers: AdaptedPeer[] = [];
  for (const address of Object.keys(peersDict)) {
    const peer = peersDict[address];
    if (!peer?.public_key) {
      continue;
    }
    const services = { ...peer.services };
    peers.push({
      id: peer.public_key,
      name: peer.username,
      ip: peer.address,
      subnetId: contained[peer.public_key] || null,
      x: peer.x,
      y: peer.y,
      services: services as Record<string, ServiceInfo>,
      host: hasServicePort(services),
      presharedKey: peer.preshared_key,
      publicKey: peer.public_key,
      rx: isNumber(peer.rx) ? peer.rx : 0,
      tx: isNumber(peer.tx) ? peer.tx : 0,
      lastHandshake: isNumber(peer.last_handshake) ? peer.last_handshake : 0,
    });
  }

  const peerByPublic: Record<string, AdaptedTopology["peers"][number]> = {};
  for (const peer of peers) {
    peerByPublic[peer.publicKey!] = peer;
  }

  const links: Link[] = [];
  let linkCounter = 0;
  const addLink = (link: Omit<Link, "id">) =>
    links.push({ id: `link_${linkCounter++}`, ...link });

  for (const cidr of Object.keys(subnetLinksDict)) {
    for (const peerObj of subnetLinksDict[cidr] || []) {
      if (peerObj?.public_key && peerByPublic[peerObj.public_key]) {
        addLink({ fromId: peerObj.public_key, toId: cidr, kind: "membership" });
      }
    }
  }

  const seenPeerPairs = new Set<string>();
  for (const baseAddress of Object.keys(p2pLinksDict)) {
    const basePeer = peers.find(peer => peer.ip === baseAddress);
    if (!basePeer) {
      continue;
    }
    for (const neighbor of p2pLinksDict[baseAddress] || []) {
      const neighborPeer = neighbor?.public_key
        ? peerByPublic[neighbor.public_key]
        : null;
      if (!neighborPeer || neighborPeer.publicKey === basePeer.publicKey) {
        continue;
      }
      const key = pairKey(basePeer.publicKey!, neighborPeer.publicKey!);
      if (seenPeerPairs.has(key)) {
        continue;
      }
      seenPeerPairs.add(key);
      addLink({
        fromId: basePeer.publicKey!,
        toId: neighborPeer.publicKey!,
        kind: "p2p",
      });
    }
  }

  for (const serviceName of Object.keys(serviceLinksDict)) {
    const hostPeer = peers.find(
      peer => peer.services && peer.services[serviceName],
    );
    if (!hostPeer) {
      continue;
    }
    for (const consumer of serviceLinksDict[serviceName] || []) {
      if (
        consumer?.public_key
        && consumer.public_key !== hostPeer.publicKey
        && peerByPublic[consumer.public_key]
      ) {
        addLink({
          fromId: hostPeer.id,
          toId: consumer.public_key,
          kind: "service",
          serviceName,
        });
      }
    }
  }

  const seenSubnetPairs = new Set<string>();
  for (const cidrA of Object.keys(subnetToSubnetDict)) {
    for (const subnet of subnetToSubnetDict[cidrA] || []) {
      const cidrB = rawTargetCidr(subnet);
      if (!cidrB || cidrA === cidrB) {
        continue;
      }
      const key = pairKey(cidrA, cidrB);
      if (seenSubnetPairs.has(key)) {
        continue;
      }
      seenSubnetPairs.add(key);
      addLink({ fromId: cidrA, toId: cidrB, kind: "subnet-subnet" });
    }
  }

  for (const cidr of Object.keys(subnetToServiceDict)) {
    for (const service of subnetToServiceDict[cidr] || []) {
      const serviceName
        = service
        && (service.name || (typeof service === "string" ? service : ""));
      if (!serviceName) {
        continue;
      }
      const hostPeer = peers.find(
        peer => peer.services && peer.services[serviceName],
      );
      if (hostPeer) {
        addLink({
          fromId: hostPeer.id,
          toId: cidr,
          kind: "subnet-service",
          serviceName,
        });
      }
    }
  }

  for (const sourceAddress of Object.keys(adminPeerToPeer)) {
    const sourcePeer = peers.find(peer => peer.ip === sourceAddress);
    if (!sourcePeer) {
      continue;
    }
    for (const target of adminPeerToPeer[sourceAddress] || []) {
      const targetPeer = target?.public_key
        ? peers.find(peer => peer.publicKey === target.public_key)
        : null;
      if (targetPeer) {
        addLink({
          fromId: sourcePeer.id,
          toId: targetPeer.id,
          kind: "admin-p2p",
        });
      }
    }
  }

  for (const sourceAddress of Object.keys(adminPeerToSubnet)) {
    const sourcePeer = peers.find(peer => peer.ip === sourceAddress);
    if (!sourcePeer) {
      continue;
    }
    for (const target of adminPeerToSubnet[sourceAddress] || []) {
      const targetCidr = rawTargetCidr(target);
      if (targetCidr) {
        addLink({
          fromId: sourcePeer.id,
          toId: targetCidr,
          kind: "admin-peer-subnet",
        });
      }
    }
  }

  for (const sourceCidr of Object.keys(adminSubnetToSubnet)) {
    for (const target of adminSubnetToSubnet[sourceCidr] || []) {
      const targetCidr = rawTargetCidr(target);
      if (targetCidr && targetCidr !== sourceCidr) {
        addLink({
          fromId: sourceCidr,
          toId: targetCidr,
          kind: "admin-subnet-subnet",
        });
      }
    }
  }

  return { peers, subnets, links };
}

function serializeSubnet (subnet: Subnet) {
  let rgba: any = subnet.rgba;
  if (rgba == null || Number.isNaN(rgba)) {
    rgba = 0x00_ff_00_25;
  }
  rgba = (Number(rgba) >>> 0) & 0xff_ff_ff_ff;
  return {
    subnet: subnet.cidr,
    name: subnet.name,
    description: subnet.description,
    x: subnet.x,
    y: subnet.y,
    width: subnet.width,
    height: subnet.height,
    rgba,
  };
}

function serializePeer (peer: Peer) {
  return {
    username: peer.name,
    address: peer.ip,
    public_key: peer.publicKey || `placeholder_${peer.id}`,
    preshared_key: peer.presharedKey || "",
    x: peer.x,
    y: peer.y,
    services: peer.host ? peer.services || {} : {},
  };
}

function serializeService (name: string, service: ServiceInfo) {
  return {
    name,
    department: service.department,
    port: service.port,
    description: service.description || "",
  };
}

export function buildCurrentTopologyPayload (netStore: {
  subnets: Subnet[];
  peers: Peer[];
  links: Link[];
}) {
  const subnets: Record<string, any> = {};
  const peers: Record<string, any> = {};
  const services: Record<string, any> = {};
  const subnetMembers: Record<string, any[]> = {};
  const peerObjById: Record<string, any> = {};

  for (const subnet of netStore.subnets) {
    subnets[subnet.cidr] = serializeSubnet(subnet);
  }

  for (const peer of netStore.peers) {
    const peerObj = serializePeer(peer);
    peers[peer.ip || peer.name] = peerObj;
    peerObjById[peer.id] = peerObj;
    for (const [serviceName, service] of Object.entries(peer.services || {})) {
      services[serviceName] = serializeService(
        serviceName,
        service as ServiceInfo,
      );
    }
  }

  for (const link of netStore.links.filter(
    link => link.kind === "membership",
  )) {
    const peer = netStore.peers.find(p => p.id === link.fromId);
    const subnet = netStore.subnets.find(s => s.id === link.toId);
    const peerObj = peer ? peerObjById[peer.id] : null;
    if (!peer || !subnet || !peerObj) {
      continue;
    }
    const members
      = subnetMembers[subnet.cidr] || (subnetMembers[subnet.cidr] = []);
    if (!members.some(member => member.public_key === peerObj.public_key)) {
      members.push(peerObj);
    }
  }

  const p2p_links: Record<string, any[]> = {};
  const seenP2p = new Set<string>();
  for (const link of netStore.links.filter(link => link.kind === "p2p")) {
    const a = netStore.peers.find(peer => peer.id === link.fromId);
    const b = netStore.peers.find(peer => peer.id === link.toId);
    if (!a?.ip || !b?.ip) {
      continue;
    }
    const aObj = peerObjById[a.id];
    const bObj = peerObjById[b.id];
    if (!aObj || !bObj) {
      continue;
    }
    const key = pairKey(a.ip, b.ip);
    if (seenP2p.has(key)) {
      continue;
    }
    seenP2p.add(key);
    const baseAddress = a.ip < b.ip ? a.ip : b.ip;
    const neighbor = a.ip < b.ip ? bObj : aObj;
    const entries = p2p_links[baseAddress] || (p2p_links[baseAddress] = []);
    if (!entries.some(peer => peer.public_key === neighbor.public_key)) {
      entries.push(neighbor);
    }
  }

  const service_links: Record<string, any[]> = {};
  for (const link of netStore.links.filter(link => link.kind === "service")) {
    if (!link.serviceName) {
      continue;
    }
    const consumer = netStore.peers.find(peer => peer.id === link.toId);
    const consumerObj = consumer ? peerObjById[consumer.id] : null;
    if (!consumerObj) {
      continue;
    }
    const entries
      = service_links[link.serviceName] || (service_links[link.serviceName] = []);
    if (!entries.some(peer => peer.public_key === consumerObj.public_key)) {
      entries.push(consumerObj);
    }
  }

  const subnet_links = { ...subnetMembers };
  const subnet_to_subnet_links: Record<string, any[]> = {};
  const seenSubnetPairs = new Set<string>();
  for (const link of netStore.links.filter(
    link => link.kind === "subnet-subnet",
  )) {
    const a = netStore.subnets.find(subnet => subnet.id === link.fromId);
    const b = netStore.subnets.find(subnet => subnet.id === link.toId);
    if (!a || !b) {
      continue;
    }
    const key = pairKey(a.cidr, b.cidr);
    if (seenSubnetPairs.has(key)) {
      continue;
    }
    seenSubnetPairs.add(key);
    (subnet_to_subnet_links[a.cidr] ||= []).push(serializeSubnet(b));
    (subnet_to_subnet_links[b.cidr] ||= []).push(serializeSubnet(a));
  }

  const subnet_to_service_links: Record<string, any[]> = {};
  for (const link of netStore.links.filter(
    link => link.kind === "subnet-service",
  )) {
    const subnet
      = netStore.subnets.find(s => s.id === link.toId)
      || netStore.subnets.find(s => s.id === link.fromId);
    const serviceName = link.serviceName;
    if (!subnet || !serviceName) {
      continue;
    }
    const serviceDef
      = services[serviceName]
      || (() => {
        const host = netStore.peers.find(
          peer => peer.services?.[serviceName],
        );
        const service = host?.services?.[serviceName];
        return service ? serializeService(serviceName, service) : undefined;
      })();
    if (!serviceDef) {
      continue;
    }
    const entries
      = subnet_to_service_links[subnet.cidr]
      || (subnet_to_service_links[subnet.cidr] = []);
    if (!entries.some((service: any) => service?.name === serviceDef.name)) {
      entries.push(serviceDef);
    }
  }

  return {
    subnets,
    peers,
    services,
    p2p_links,
    service_links,
    subnet_links,
    subnet_to_subnet_links,
    subnet_to_service_links,
  };
}
