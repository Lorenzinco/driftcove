import ipaddress, sqlite3
from backend.core.models import Peer, Subnet, Service
from backend.core.logger import logging


class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path,check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.row_factory = None

    def clear_database(self):
        """
        This function clears the entire database.
        """
        try:
            self.conn.execute("DELETE FROM subnets")
            self.conn.execute("DELETE FROM peers")
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while clearing database: {e}")

    def begin_transaction(self):
        """
        This function initiates a transaction, which is used to ensure that the database operations are atomic.
        It will raise an error if the database operation fails.
        """
        try:
            self.conn.execute("BEGIN")
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while starting transaction: {e}")

    def commit_transaction(self):
        """
        This function commits the transaction, which is used to ensure that the database operations are atomic.
        It will raise an error if the database operation fails.
        """
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while committing transaction: {e}")

    def rollback_transaction(self):
        """
        This function rolls back the transaction, which is used to ensure that the database operations are atomic.
        It will raise an error if the database operation fails.
        """
        try:
            self.conn.rollback()
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while rolling back transaction: {e}")

    def create_peer(self,peer:Peer):
        """
        It creates a peer inside the database.
        The fuction returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.conn.execute("""
                INSERT INTO peers (username, public_key, preshared_key, address, x, y)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (peer.username, peer.public_key, peer.preshared_key, peer.address, peer.x, peer.y))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while creating peer: {e}")

        return
    
    def remove_peer(self,peer:Peer):
        """
        Removes a peer from the database.
        This action is permanent, if you wish to disable a peer, use the update_peer function with null values.
        The function returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.conn.execute("""
                DELETE FROM peers WHERE public_key = ?
            """, (peer.public_key,))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing peer: {e}")
        
    def update_peer(self,peer:Peer):
        """
        Updates a peer inside the database.
        The function returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.conn.execute("""
                UPDATE peers
                SET username = ?, public_key = ?, preshared_key = ?, address = ?, x = ?, y = ?
                WHERE username = ?
            """, (peer.username, peer.public_key, peer.preshared_key, peer.address, peer.x, peer.y, peer.username))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while updating peer: {e}")
        
        return
    
    def update_peer_coordinates(self,peer:Peer):
        """
        Updates a peer's coordinates inside the database.
        The function returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.conn.execute("""
                UPDATE peers
                SET x = ?, y = ?
                WHERE public_key = ?
            """, (peer.x, peer.y, peer.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while updating peer coordinates: {e}")

    def get_all_peers(self) -> list[Peer]:
        """
        Returns a list of all peers in the database.
        """
        peers = []
        try:
            cur = self.conn.execute("""
                SELECT username, public_key, preshared_key, address, x, y
                FROM peers
            """)
            peers_rows = cur.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5]))
            for peer in peers:
                hosted_services = self.get_services_by_host(peer)
                peer.services.update({service.name: service for service in hosted_services})

        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting all peers: {e}")
        return peers
    
    def get_avaliable_ip(self, subnet: Subnet) -> str|None:
        """
        This function returns an available IP address from the subnet.
        It will return the first available IP address that is not already in use.
        """
        try:
            cur = self.conn.execute("""
                SELECT address FROM peers
            """)
            all_addresses = [row[0] for row in cur.fetchall()]
            net = ipaddress.ip_network(subnet.subnet, strict=False)
            used_ips = {ip for ip in all_addresses if ipaddress.ip_address(ip) in net}

            for ip in net.hosts():
                if str(ip) not in used_ips:
                    return str(ip)
            logging.warning(f"No available IPs found in subnet {subnet.subnet}")
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting available IP: {e}")
        return None

    def is_ip_in_subnet(self, ip: str, subnet: Subnet) -> bool:
        """
        This function checks if an IP address is in a given subnet.
        """
        try:
            ip_addr = ipaddress.ip_address(ip)
            net = ipaddress.ip_network(subnet.subnet, strict=False)
            return ip_addr in net
        except ValueError:
            return False

    def is_ip_already_assigned(self, ip: str) -> bool:
        """
        This function checks if an IP address is already assigned to a peer.
        """
        try:
            cur = self.conn.execute("""
                SELECT COUNT(*) FROM peers WHERE address = ?
            """, (ip,))
            count = cur.fetchone()[0]
            return count > 0
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while checking if IP is already assigned: {e}")

    def get_avaliable_username_for_service(self)->str|None:
        """
        This function returns an available username for a service.
        It will return the first available username that is not already in use.
        """
        try:
            cur = self.conn.execute("""
                SELECT username FROM peers
            """)
            all_usernames = {row[0] for row in cur.fetchall()}
            for i in range(1, 10000):  # Arbitrary limit to avoid infinite loop
                username = f"service_{i}"
                if username not in all_usernames:
                    return username
            logging.warning("No available usernames found.")
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting available username: {e}")
        return None
    
    def create_subnet(self,subnet: Subnet):
        """
        This function creates an entry in the database for this specific subnet.
        """
        try:
            self.conn.execute("""
                INSERT INTO subnets (name, subnet, description, x, y, width, height, rgba)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (subnet.name,subnet.subnet,subnet.description,subnet.x,subnet.y,subnet.width,subnet.height,subnet.rgba))
            logging.error(f"Created subnet {subnet} in database.")
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while creating subnet: {e}")
        return
        

    def delete_subnet(self, subnet: Subnet):
        """
        This function deletes a subnet from the database.
        """
        try:
            self.conn.execute("""
                DELETE FROM subnets WHERE subnet = ?
            """, (subnet.subnet,))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while deleting subnet: {e}")
        return
    
    def update_subnet_coordinates_size_and_color(self,subnet:Subnet):
        """
        This function updates a subnet's coordinates, size and color inside the database.
        The function returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.conn.execute("""
                UPDATE subnets
                SET x = ?, y = ?, width = ?, height = ?, rgba = ?
                WHERE subnet = ?
            """, (subnet.x, subnet.y, subnet.width, subnet.height, subnet.rgba, subnet.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while updating subnet coordinates, size and color: {e}")
        return
    
    def get_peer_by_username(self, username: str) -> Peer:
        """
        This function returns a Peer object by its username.
        If the peer does not exist, it will return None.
        """
        try:
            cur = self.conn.execute("""
                SELECT username, public_key, preshared_key, address, x, y
                FROM peers WHERE username = ?
            """, (username,))
            row = cur.fetchone()
            if row:
                peer = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                hosted_services = self.get_services_by_host(peer)
                peer.services.update({service.name: service for service in hosted_services})
                return peer

        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peer by username: {e}")
        return None
    
    def get_peer_by_address(self, address: str) -> Peer|None:
        """
        This function returns a Peer object by its address.
        If the peer does not exist, it will return None.
        """
        try:
            cur = self.conn.execute("""
                SELECT username, public_key, preshared_key, address, x, y
                FROM peers WHERE address = ?
            """, (address,))
            row = cur.fetchone()
            if row:
                peer = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                hosted_services = self.get_services_by_host(peer)
                peer.services.update({service.name: service for service in hosted_services})
                return peer

        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peer by address: {e}")
        return None

    def get_subnets(self)->list[Subnet]:
        """
        Returns a list of subnets inside the database.
        """
        subnets = []
        try:
            cur = self.conn.execute("""
                SELECT subnet, name, description, x, y, width, height, rgba
                FROM subnets
            """)
            subnets_rows = cur.fetchall()
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0],name=row[1],description=row[2],x=row[3],y=row[4],width=row[5],height=row[6],rgba=row[7]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting all subnets: {e}")
        return subnets
    
    def get_subnet_by_address(self, address: str) -> Subnet|None:
        """
        This function returns a Subnet object by its address.
        If the subnet does not exist, it will return None.
        """
        try:
            cur = self.conn.execute("""
                SELECT subnet, name, description, x, y, width, height, rgba
                FROM subnets WHERE subnet = ?
            """, (address,))
            row = cur.fetchone()
            if row:
                return Subnet(subnet=row[0], name=row[1], description=row[2], x=row[3], y=row[4], width=row[5], height=row[6], rgba=row[7])

        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting subnet by address: {e}")
        return None
    

    def add_link_from_peer_to_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function adds a peer to a subnet.
        It will create the entry in the peer_subnets table, which is a many-to-many relationship between peers and subnets.
        """
        try:
            self.conn.execute("""
                INSERT INTO peers_subnets (peer_id, subnet)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), ?)
                ON CONFLICT(peer_id, subnet) DO NOTHING
            """, (peer.public_key, subnet.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link from peer to subnet: {e}")
        return
    
    def remove_link_from_peer_from_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function removes a peer from a subnet.
        It will delete the entry in the peer_subnets table.
        """
        try:
            self.conn.execute("""
                DELETE FROM peers_subnets WHERE peer_id = (SELECT id FROM peers WHERE public_key = ?) AND subnet = ?
            """, (peer.public_key, subnet.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link from peer to subnet: {e}")
        return
    
    def get_peers_subnets(self,peer:Peer)->list[Subnet]:
        """
        This function returns a list of subnets that a peer is part of.
        """
        try:
            subnets = self.get_subnets()
            peer_subnets = []
            for subnet in subnets:
                peer_ip_address = ipaddress.ip_address(peer.address)
                if peer_ip_address in ipaddress.ip_network(subnet.subnet, strict=False):
                    peer_subnets.append(subnet)
            return peer_subnets
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peers subnet: {e}")
        return None
    
    def get_peers_links_to_subnets(self,peer:Peer)->list[Subnet]:
        """
        This function returns a list of subnets that a peer is part of.
        It will return a list of Subnet objects.
        """
        subnets = []
        try:
            cur = self.conn.execute("""
                SELECT s.subnet, s.name, s.description, s.x, s.y, s.width, s.height, s.rgba
                FROM subnets s
                JOIN peers_subnets ps ON s.subnet = ps.subnet
                JOIN peers p ON ps.peer_id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            subnets_rows = cur.fetchall()
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0], name=row[1], description=row[2], x=row[3], y=row[4], width=row[5], height=row[6], rgba=row[7]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peers subnets: {e}")
        return subnets
    
    def get_peers_in_subnet(self, subnet: Subnet) -> list[Peer]:
        """
        This function returns a list of peers in a subnet.
        It will return a list of Peer objects.
        """
        peers = []
        try:
            cur = self.conn.execute("""
                SELECT username, public_key, preshared_key, address, x, y
                FROM peers
            """)
            peers_rows = cur.fetchall()
            for row in peers_rows:
                peer = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                address = row[3]
                address_ip = ipaddress.ip_address(address)
                if address_ip in ipaddress.ip_network(subnet.subnet, strict=False):
                    hosted_services = self.get_services_by_host(peer)
                    peer.services.update({service.name: service for service in hosted_services})
                    if peer not in peers:
                        peers.append(peer)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peers in subnet: {e}")
        return peers
    
    def get_services_in_subnet(self, subnet: Subnet) -> list[Service]:
        """
        This function returns a list of services in a subnet.
        It will return a list of Service objects.
        """
        services = []
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y, s.name, s.department, s.port
                FROM peers p
                JOIN services s ON p.id = s.id
            """)
            services_rows = cur.fetchall()
            for row in services_rows:
                address = row[3]
                address_ip = ipaddress.ip_address(address)
                if address_ip in ipaddress.ip_network(subnet.subnet, strict=False):
                    host = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                    hosted_services = self.get_services_by_host(host)
                    services.extend(hosted_services)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting services in subnet: {e}")
        return services
    
    def get_peers_linked_to_subnet(self, subnet: Subnet) -> list[Peer]:
        """
        This function returns a list of peers that are linked to a subnet.
        It will return a list of Peer objects.
        """
        peers = []
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y
                FROM peers p
                JOIN peers_subnets ps ON p.id = ps.peer_id
                WHERE ps.subnet = ?
            """, (subnet.subnet,))
            peers_rows = cur.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peers linked to subnet: {e}")
        return peers

    def create_service(self, peer: Peer, service: Service):
        """
        Adds a service to the peer's hosted services
        """
        try:
            # Check that the peer exists
            cur = self.conn.execute("""
                SELECT id FROM peers WHERE public_key = ?
            """, (peer.public_key,))
            row = cur.fetchone()
            if row is None:
                raise Exception("Peer not found, to create a service you must first create a peer and then link the service to the peer.")
            peer_id = row[0]

            # Insert into services table using the same ID
            self.conn.execute("""
                INSERT INTO services (id, name, department, port, description)
                VALUES (?, ?, ?, ?, ?)
            """, (peer_id, service.name, service.department, service.port, service.description))

            return service.name

        except sqlite3.Error as e:
            raise Exception(f"Database error, {e}")
        
    def add_peer_service_link(self, peer: Peer, service: Service):
        """
        This function adds a link between a peer and a service.
        It will create the entry in the peers_services table, which is a many-to-many relationship between peers and services.
        """
        try:
            self.conn.execute("""
                INSERT INTO peers_services (peer_id, service_id, service_port)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), (SELECT id FROM services WHERE name = ?), ?)
                ON CONFLICT(peer_id, service_id, service_port) DO NOTHING
            """, (peer.public_key, service.name, service.port))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link from peer {peer} to service {service}: {e}")

    def remove_peer_service_link(self, peer: Peer, service: Service):
        """
        This function removes a link between a peer and a service.
        It will delete the entry in the peer_services table.
        """
        try:
            self.conn.execute("""
                DELETE FROM peers_services WHERE peer_id = (SELECT id FROM peers WHERE public_key = ?) AND service_id = (SELECT id FROM services WHERE name = ?) AND service_port = ?
            """, (peer.public_key, service.name, service.port))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link from peer to service: {e}")

    def delete_service(self, service: Service):
        """
        This function deletes a service from the database.
        """
        try:
            self.conn.execute("""
                DELETE FROM services WHERE name = ? AND port = ?
            """, (service.name, service.port))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while deleting service: {e}")

    def get_peers_services_links(self, peer: Peer) -> list[Service]:
        """
        This function returns a list of services that a user is connected to.
        It will return a list of Service objects.
        """
        services = []
        try:
            cur = self.conn.execute("""
                SELECT s.name, s.department, s.description, s.port
                FROM services s
                JOIN peers_services ps ON s.id = ps.service_id
                JOIN peers p ON ps.peer_id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            services_rows = cur.fetchall()
            for row in services_rows:
                services.append(Service(name=row[0], department=row[1], description=row[2], port=row[3]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peer's services: {e}")
        return services
        
        
    def get_all_services(self) -> list[Service]:
        """
        This function returns a list of all services in the database.
        It will return a list of Service objects.
        """
        services = []
        try:
            cur = self.conn.execute("""
                SELECT name, department, port, description
                FROM Services
            """)
            services_rows = cur.fetchall()
            for row in services_rows:
                services.append(Service(name=row[0], department=row[1], port=row[2], description=row[3]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting all services: {e}")
        return services
        
    def get_service_by_name(self, name: str) -> Service|None:
        """
        This function returns a Service object by its name.
        If the service does not exist, it will return None.
        """
        try:
            cur = self.conn.execute("""
                SELECT name, department, port, description
                FROM Services
                WHERE name = ?
            """, (name,))
            row = cur.fetchone()
            if row:
                return Service(name=row[0], department=row[1], port=row[2], description=row[3])

        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting service by name: {e}")
        return None
    
    def get_service_host(self, service: Service) -> Peer:
        """
        This function returns the peer that is hosting the service.
        It will return a Peer object.
        """
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y
                FROM peers p
                JOIN services s ON p.id = s.id
                WHERE s.name = ?
            """, (service.name,))
            row = cur.fetchone()
            if row:
                return Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting service host: {e}")
        return None
    
    def get_services_by_host(self, peer:Peer) -> list[Service]:
        """
        This function returns a list of services that the peer is hosting, empty list if none
        """
        services = []
        try:
            cur = self.conn.execute("""
                SELECT s.name, s.department, s.port, s.description
                FROM services s
                JOIN peers p ON s.id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            services_rows = cur.fetchall()
            for row in services_rows:
                services.append(Service(name=row[0], department=row[1], port=row[2], description=row[3]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting services by host: {e}")
        return services

    def get_service_peers(self, service: Service) -> list[Peer]:
        """
        This function returns a list of peers that are linked to a service.
        It will return a list of Peer objects.
        """
        peers = []
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y
                FROM peers p
                JOIN peers_services ps ON p.id = ps.peer_id
                JOIN services s ON ps.service_id = s.id AND ps.service_port = s.port
                WHERE s.name = ?
            """, (service.name,))
            peers_rows = cur.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peers linked to service: {e}")
        return peers
    
    def get_peer_services(self, peer: Peer) -> list[Service]:
        """
        This function returns a list of services that a peer is linked to.
        It will return a list of Service objects.
        """
        services = []
        try:
            cur = self.conn.execute("""
                SELECT s.name, s.department, s.port, s.description
                FROM services s
                JOIN peers_services ps ON s.id = ps.service_id AND s.port = ps.service_port
                JOIN peers p ON ps.peer_id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            services_rows = cur.fetchall()
            for row in services_rows:
                services.append(Service(name=row[0], department=row[1], port=row[2], description=row[3]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peer's services: {e}")
        return services
    
    def add_link_between_two_peers(self, peer1: Peer, peer2: Peer):
        """
        This function adds a link between two peers.
        It will create the entry in the links table, which is a many-to-many relationship between peers.
        """
        try:
            self.conn.execute("""
                INSERT INTO peers_peers (peer_one_id, peer_two_id)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), (SELECT id FROM peers WHERE public_key = ?))
            """, (peer1.public_key, peer2.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link between peers: {e}")

    def remove_link_between_two_peers(self, peer1: Peer, peer2: Peer):
        """
        Remove an undirected link between two peers (order-agnostic).
        """
        try:
            self.conn.execute("""
                DELETE FROM peers_peers 
                WHERE (peer_one_id = (SELECT id FROM peers WHERE public_key = ?) AND peer_two_id = (SELECT id FROM peers WHERE public_key = ?))
                   OR (peer_one_id = (SELECT id FROM peers WHERE public_key = ?) AND peer_two_id = (SELECT id FROM peers WHERE public_key = ?))
            """, (peer1.public_key, peer2.public_key, peer2.public_key, peer1.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link between peers: {e}")

    def get_links_between_peers(self)->dict[str, list[Peer]]:
        """
        This function returns a list of links between peers.
        It will return a dictionary with the peer's address as key and all the connected Peers inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT p1.username, p1.public_key, p1.preshared_key, p1.address, p1.x, p1.y, p2.username, p2.public_key, p2.preshared_key, p2.address, p2.x, p2.y
                FROM peers_peers pp
                JOIN peers p1 ON pp.peer_one_id = p1.id
                JOIN peers p2 ON pp.peer_two_id = p2.id
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                peer1 = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                peer2 = Peer(username=row[6], public_key=row[7], preshared_key=row[8], address=row[9], x=row[10], y=row[11])
                if peer1.address not in links:
                    links[peer1.address] = []
                links[peer1.address].append(peer2)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting links between peers: {e}")
        return links
    
    def get_links_between_peers_and_services(self)->dict[str,list[Peer]]:
        """
        This function returns dictionary with the service name as key and all the connected Peers inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y, s.name, s.department, s.port, s.description
                FROM peers_services ps
                JOIN peers p ON ps.peer_id = p.id
                JOIN services s ON ps.service_id = s.id AND ps.service_port = s.port
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                peer = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                service = Service(name=row[6], department=row[7], port=row[8], description=row[9])
                if service.name not in links:
                    links[service.name] = []
                if peer not in links[service.name]:
                    links[service.name].append(peer)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting links between peers and services: {e}")
        return links

    def get_links_between_subnets_and_peers(self)->dict[str,list[Peer]]:
        """
        This function returns dictionary with the subnet address as key and all the connected Peers inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y, s.subnet, s.name, s.description, s.x, s.y, s.width, s.height, s.rgba
                FROM peers_subnets ps
                JOIN peers p ON ps.peer_id = p.id
                JOIN subnets s ON ps.subnet = s.subnet
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                peer = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                subnet = Subnet(subnet=row[6], name=row[7], description=row[8], x=row[9], y=row[10], width=row[11], height=row[12], rgba=row[13])
                if subnet.subnet not in links:
                    links[subnet.subnet] = []
                links[subnet.subnet].append(peer)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting links between subnets and peers: {e}")
        return links
    
    def add_link_between_subnets(self, subnet1: Subnet, subnet2: Subnet):
        """
        This function adds a link between two subnets.
        It will create the entry in the subnets_subnets table, which is a many-to-many relationship between subnets.
        """
        try:
            self.conn.execute("""
                INSERT INTO subnets_subnets (subnet_one, subnet_two)
                VALUES (?, ?)
                ON CONFLICT(subnet_one, subnet_two) DO NOTHING
            """, (subnet1.subnet, subnet2.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link between subnets: {e}")
        
    def remove_link_between_subnets(self, subnet1: Subnet, subnet2: Subnet):
        """
        This function removes a link between two subnets.
        It will delete the entry in the subnets_subnets table.
        """
        try:
            self.conn.execute("""
                DELETE FROM subnets_subnets 
                WHERE (subnet_one = ? AND subnet_two = ?)
                   OR (subnet_one = ? AND subnet_two = ?)
            """, (subnet1.subnet, subnet2.subnet, subnet2.subnet, subnet1.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link between subnets: {e}")
        
    def get_links_between_subnets(self)->dict[str, list[Subnet]]:
        """
        This function returns a list of links between subnets.
        It will return a dictionary with the subnet's address as key and all the connected Subnets inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT s1.subnet, s1.name, s1.description, s1.x, s1.y, s1.width, s1.height, s1.rgba,
                       s2.subnet, s2.name, s2.description, s2.x, s2.y, s2.width, s2.height, s2.rgba
                FROM subnets_subnets ss
                JOIN subnets s1 ON ss.subnet_one = s1.subnet
                JOIN subnets s2 ON ss.subnet_two = s2.subnet
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                subnet1 = Subnet(subnet=row[0], name=row[1], description=row[2], x=row[3], y=row[4], width=row[5], height=row[6], rgba=row[7])
                subnet2 = Subnet(subnet=row[8], name=row[9], description=row[10], x=row[11], y=row[12], width=row[13], height=row[14], rgba=row[15])
                if subnet1.subnet not in links:
                    links[subnet1.subnet] = []
                links[subnet1.subnet].append(subnet2)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting links between subnets: {e}")
        return links
    
    def get_links_from_subnets_to_subnets(self, subnet: Subnet) -> list[Subnet]:
        """
        This function returns a list of subnets that are linked to a subnet.
        It will return a list of Subnet objects.
        """
        subnets = []
        try:
            cur = self.conn.execute("""
                SELECT s2.subnet, s2.name, s2.description, s2.x, s2.y, s2.width, s2.height, s2.rgba
                FROM subnets_subnets ss
                JOIN subnets s1 ON ss.subnet_one = s1.subnet
                JOIN subnets s2 ON ss.subnet_two = s2.subnet
                WHERE s1.subnet = ?
            """, (subnet.subnet,))
            subnets_rows = cur.fetchall()
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0], name=row[1], description=row[2], x=row[3], y=row[4], width=row[5], height=row[6], rgba=row[7]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting subnet links to subnets: {e}")
        return subnets
    
    def add_link_from_subnet_to_service(self, subnet: Subnet, service: Service):
        """
        This function adds a link between a subnet and a service.
        It will create the entry in the subnets_services table, which is a many-to-many relationship between subnets and services.
        """
        try:
            self.conn.execute("""
                INSERT INTO subnets_services (subnet, service_id, service_port)
                VALUES (?, (SELECT id FROM services WHERE name = ?), ?)
                ON CONFLICT(subnet, service_id, service_port) DO NOTHING
            """, (subnet.subnet, service.name, service.port))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link from subnet to service: {e}")
        
    def remove_link_from_subnet_to_service(self, subnet: Subnet, service: Service):
        """
        This function removes a link between a subnet and a service.
        It will delete the entry in the subnets_services table.
        """
        try:
            self.conn.execute("""
                DELETE FROM subnets_services WHERE subnet = ? AND service_id = (SELECT id FROM services WHERE name = ?) AND service_port = ?
            """, (subnet.subnet, service.name, service.port))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link from subnet to service: {e}")
    
    def get_links_from_subnets_to_services(self) -> dict[str, list[Service]]:
        """
        This function returns dictionary with the subnet address as key and all the connected Services inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT s.subnet, s.name, s.description, s.x, s.y, s.width, s.height, s.rgba,
                       sv.name, sv.department, sv.port, sv.description
                FROM subnets_services ss
                JOIN subnets s ON ss.subnet = s.subnet
                JOIN services sv ON ss.service_id = sv.id AND ss.service_port = sv.port
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                subnet = Subnet(subnet=row[0], name=row[1], description=row[2], x=row[3], y=row[4], width=row[5], height=row[6], rgba=row[7])
                service = Service(name=row[8], department=row[9], port=row[10], description=row[11])
                if subnet.subnet not in links:
                    links[subnet.subnet] = []
                if service not in links[subnet.subnet]:
                    links[subnet.subnet].append(service)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting links between subnets and services: {e}")
        return links

    def close(self):
        self.conn.close()


    def add_admin_link_from_peer_to_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function adds an admin link between a peer and a subnet.
        It will create the entry in the admin_peers_subnets table, which is a many-to-many relationship between admin peers and subnets.
        """
        try:
            self.conn.execute("""
                INSERT INTO admin_peers_subnets (peer_id, subnet)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), ?)
                ON CONFLICT(peer_id, subnet) DO NOTHING
            """, (peer.public_key, subnet.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding admin link from peer to subnet: {e}")
        return
    
    def remove_admin_link_from_peer_to_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function removes an admin link between a peer and a subnet.
        It will delete the entry in the admin_peers_subnets table.
        """
        try:
            self.conn.execute("""
                DELETE FROM admin_peers_subnets WHERE peer_id = (SELECT id FROM peers WHERE public_key = ?) AND subnet = ?
            """, (peer.public_key, subnet.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing admin link from peer to subnet: {e}")
        return

    def get_admin_links_from_peer_to_subnets(self)->dict[str,list[Subnet]]:
        """
        This function returns dictionary with the peer's address as key and all the connected Subnets inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, p.x, p.y, s.subnet, s.name, s.description, s.x, s.y, s.width, s.height, s.rgba
                FROM admin_peers_subnets ps
                JOIN peers p ON ps.peer_id = p.id
                JOIN subnets s ON ps.subnet = s.subnet
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                peer = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                subnet = Subnet(subnet=row[6], name=row[7], description=row[8], x=row[9], y=row[10], width=row[11], height=row[12], rgba=row[13])
                if peer.address not in links:
                    links[peer.address] = []
                links[peer.address].append(subnet)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting admin links between peers and subnets: {e}")
        return links
    
    def add_admin_subnet_to_subnet_link(self, subnet1: Subnet, subnet2: Subnet):
        """
        This function adds an admin link between two subnets.
        It will create the entry in the admin_subnets_subnets table, which is a many-to-many relationship between admin subnets.
        """
        try:
            self.conn.execute("""
                INSERT INTO admin_subnets_subnets (subnet_one, subnet_two)
                VALUES (?, ?)
                ON CONFLICT(subnet_one, subnet_two) DO NOTHING
            """, (subnet1.subnet, subnet2.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding admin link between subnets: {e}")

    def remove_admin_subnet_to_subnet_link(self, subnet1: Subnet, subnet2: Subnet):
        """
        This function removes an admin link between two subnets.
        It will delete the entry in the admin_subnets_subnets table.
        """
        try:
            self.conn.execute("""
                DELETE FROM admin_subnets_subnets WHERE subnet_one = ? AND subnet_two = ?
            """, (subnet1.subnet, subnet2.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing admin link between subnets: {e}")
        
    def get_admin_links_from_subnet_to_subnet(self)->dict[str, list[Subnet]]:
        """
        This function returns a list of admin links between subnets.
        It will return a dictionary with the subnet's address as key and all the connected Subnets inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT s1.subnet, s1.name, s1.description, s1.x, s1.y, s1.width, s1.height, s1.rgba,
                       s2.subnet, s2.name, s2.description, s2.x, s2.y, s2.width, s2.height, s2.rgba
                FROM admin_subnets_subnets ss
                JOIN subnets s1 ON ss.subnet_one = s1.subnet
                JOIN subnets s2 ON ss.subnet_two = s2.subnet
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                subnet1 = Subnet(subnet=row[0], name=row[1], description=row[2], x=row[3], y=row[4], width=row[5], height=row[6], rgba=row[7])
                subnet2 = Subnet(subnet=row[8], name=row[9], description=row[10], x=row[11], y=row[12], width=row[13], height=row[14], rgba=row[15])
                if subnet1.subnet not in links:
                    links[subnet1.subnet] = []
                links[subnet1.subnet].append(subnet2)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting admin links between subnets: {e}")
        return links
    
    def add_admin_link_from_peer_to_peer(self, peer1: Peer, peer2: Peer):
        """
        This function adds an admin link between two peers.
        It will create the entry in the admin_peers_peers table, which is a many-to-many relationship between admin peers.
        """
        try:
            self.conn.execute("""
                INSERT INTO admin_peers_peers (peer_one_id, peer_two_id)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), (SELECT id FROM peers WHERE public_key = ?))
                ON CONFLICT(peer_one_id, peer_two_id) DO NOTHING
            """, (peer1.public_key, peer2.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding admin link between peers: {e}")
        
    def remove_admin_link_from_peer_to_peer(self, peer1: Peer, peer2: Peer):
        """
        This function removes an admin link between two peers.
        It will delete the entry in the admin_peers_peers table.
        """
        try:
            self.conn.execute("""
                DELETE FROM admin_peers_peers 
                WHERE (peer_one_id = (SELECT id FROM peers WHERE public_key = ?) AND peer_two_id = (SELECT id FROM peers WHERE public_key = ?))
                   OR (peer_one_id = (SELECT id FROM peers WHERE public_key = ?) AND peer_two_id = (SELECT id FROM peers WHERE public_key = ?))
            """, (peer1.public_key, peer2.public_key, peer2.public_key, peer1.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing admin link between peers: {e}")
        
    def get_admin_links_from_peer_to_peers(self)->dict[str, list[Peer]]:
        """
        This function returns a list of admin links between peers.
        It will return a dictionary with the admin's address as key and all the connected Peers inside a list as value.
        """
        links = {}
        try:
            cur = self.conn.execute("""
                SELECT p1.username, p1.public_key, p1.preshared_key, p1.address, p1.x, p1.y, 
                       p2.username, p2.public_key, p2.preshared_key, p2.address, p2.x, p2.y
                FROM admin_peers_peers pp
                JOIN peers p1 ON pp.peer_one_id = p1.id
                JOIN peers p2 ON pp.peer_two_id = p2.id
            """)
            links_rows = cur.fetchall()
            for row in links_rows:
                peer1 = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], x=row[4], y=row[5])
                peer2 = Peer(username=row[6], public_key=row[7], preshared_key=row[8], address=row[9], x=row[10], y=row[11])
                if peer1.address not in links:
                    links[peer1.address] = []
                links[peer1.address].append(peer2)
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting admin links between peers: {e}")
        return links
