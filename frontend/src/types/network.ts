export type ID = string;

export type Tool = "select" | "connect" | "add-subnet" | "cut";

export interface Peer {
  id: ID;
  name: string;
  x: number;
  y: number;
  ip?: string;
  subnetId?: ID | null;
  public?: boolean;
  host?: boolean;
  services?: Record<
    string,
    {
      port: number;
      name: string;
      protocol: "tcp" | "udp" | "both";
      department?: string;
      description?: string;
    }
  >;
  presharedKey?: string;
  publicKey?: string;
  rx: number;
  tx: number;
  lastHandshake: number;
}

export interface ServiceInfo {
  port: number;
  name: string;
  protocol: "tcp" | "udp" | "both";
  department?: string;
  description?: string;
}

export interface Subnet {
  id: ID;
  cidr: string;
  name?: string;
  description?: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rgba?: number; // 0xRRGGBBAA from backend
}

export interface Link {
  id: ID;
  fromId: ID;
  toId: ID;
  kind:
    | "p2p"
    | "service"
    | "membership"
    | "subnet-subnet"
    | "subnet-service"
    | "admin-p2p"
    | "admin-peer-subnet"
    | "admin-subnet-subnet";
  serviceName?: string;
}

export type EdgeDir = "" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

export interface PanZoom {
  x: number;
  y: number;
  zoom: number;
}

export function uid(prefix = "id"): string {
  return prefix + Math.random().toString(36).slice(2, 9);
}
