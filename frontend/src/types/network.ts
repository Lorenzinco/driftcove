export type ID = string;

export type Tool = 'select' | 'connect' | 'add-subnet' | 'cut';

export interface Peer {
  id: ID;
  name: string;
  x: number; y: number;
  ip?: string;
  subnetId?: ID | null;
  allowed?: boolean; // derived from presence in links
  host?: boolean; // computed if services present
  services?: Record<string, { port: number; name: string; department?: string; description?: string }>;
  presharedKey?: string;
  publicKey?: string;
}

export type ServiceInfo = { 
    port: number; 
    name: string; 
    department?: string; 
    description?: string 
}


export interface Subnet {
  id: ID;
  cidr: string;
  name?: string;
  description?: string;
  x: number; y: number; width: number; height: number;
  rgba?: number; // 0xRRGGBBAA from backend
}

export interface Link {
  id: ID;
  fromId: ID;
  toId: ID;
  kind: 'p2p' | 'service' | 'membership' | 'subnet-subnet' | 'subnet-service';
  serviceName?: string;
}

export type EdgeDir = '' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

export interface PanZoom {
  x: number; y: number; zoom: number;
}

export function uid(prefix='id'): string {
  return prefix + Math.random().toString(36).slice(2,9);
}