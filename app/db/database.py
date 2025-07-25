import ipaddress, sqlite3
from app.core.models import Peer, Subnet, Service
from app.core.logger import logging


class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path,check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()

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
            self.cursor.execute("""
                INSERT INTO peers (username, public_key, preshared_key, address)
                VALUES (?, ?, ?, ?)
            """, (peer.username, peer.public_key, peer.preshared_key, peer.address))
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
            self.cursor.execute("""
                DELETE FROM peers WHERE public_key = ?
            """, (peer.public_key,))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing peer: {e}")
    
    def get_all_peers(self) -> list[Peer]:
        """
        Returns a list of all peers in the database.
        """
        peers = []
        try:
            self.cursor.execute("""
                SELECT username, public_key, preshared_key, address
                FROM peers
            """)
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting all peers: {e}")
        return peers
    
    def get_avaliable_ip(self, subnet: Subnet) -> str|None:
        """
        This function returns an available IP address from the subnet.
        It will return the first available IP address that is not already in use.
        """
        try:
            self.cursor.execute("""
                SELECT address FROM peers
            """)
            all_addresses = [row[0] for row in self.cursor.fetchall()]
            net = ipaddress.ip_network(subnet.subnet, strict=False)
            used_ips = {ip for ip in all_addresses if ipaddress.ip_address(ip) in net}

            for ip in net.hosts():
                if str(ip) not in used_ips:
                    return str(ip)
            logging.warning(f"No available IPs found in subnet {subnet.subnet}")
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting available IP: {e}")
        return None
    
    def get_avaliable_username_for_service(self)->str|None:
        """
        This function returns an available username for a service.
        It will return the first available username that is not already in use.
        """
        try:
            self.cursor.execute("""
                SELECT username FROM peers
            """)
            all_usernames = {row[0] for row in self.cursor.fetchall()}
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
            self.cursor.execute("""
                INSERT INTO subnets (name, subnet, description)
                VALUES (?, ?, ?)
            """, (subnet.name,subnet.subnet,subnet.description))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while creating subnet: {e}")
        return
        

    def delete_subnet(self, subnet: Subnet):
        """
        This function deletes a subnet from the database.
        """
        try:
            self.cursor.execute("""
                DELETE FROM subnets WHERE subnet = ?
            """, (subnet.subnet,))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while deleting subnet: {e}")
        return
    
    def get_peer_by_username(self, username: str) -> Peer:
        """
        This function returns a Peer object by its username.
        If the peer does not exist, it will return None.
        """
        try:
            self.cursor.execute("""
                SELECT username, public_key, preshared_key, address
                FROM peers WHERE username = ?
            """, (username,))
            row = self.cursor.fetchone()
            if row:
                return Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3])
            
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peer by username: {e}")
        return None

    def get_subnets(self)->list[Subnet]:
        """
        Returns a list of subnets inside the database.
        """
        subnets = []
        try:
            self.cursor.execute("""
                SELECT subnet, name, description
                FROM subnets
            """)
            subnets_rows = self.cursor.fetchall()
            # Use logging instead of print for Docker/container environments
            logging.info(f"Found {len(subnets_rows)} subnets in the database.")
            logging.info(f"Subnets rows: {subnets_rows}")
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0],name=row[1],description=row[2]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting all subnets: {e}")
        return subnets
    
    def get_subnet_by_address(self, address: str) -> Subnet|None:
        """
        This function returns a Subnet object by its address.
        If the subnet does not exist, it will return None.
        """
        try:
            self.cursor.execute("""
                SELECT subnet, name, description
                FROM subnets WHERE subnet = ?
            """, (address,))
            row = self.cursor.fetchone()
            if row:
                return Subnet(subnet=row[0], name=row[1], description=row[2])

        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting subnet by address: {e}")
        return None
    

    def add_link_from_peer_to_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function adds a peer to a subnet.
        It will create the entry in the peer_subnets table, which is a many-to-many relationship between peers and subnets.
        """
        try:
            self.cursor.execute("""
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
            self.cursor.execute("""
                DELETE FROM peers_subnets WHERE peer_id = (SELECT id FROM peers WHERE public_key = ?) AND subnet = ?
            """, (peer.public_key, subnet.subnet))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link from peer to subnet: {e}")
        return
    
    def get_peers_subnet(self,peer:Peer)->Subnet|None:
        """
        This function returns a subnet that a peer is part of.
        It will return a Subnet object.
        """
        try:
            subnets = self.get_subnets()
            for subnet in subnets:
                peer_ip_address = ipaddress.ip_address(peer.address)
                if peer_ip_address in ipaddress.ip_network(subnet.subnet, strict=False):
                    return subnet
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
            self.cursor.execute("""
                SELECT s.subnet, s.name, s.description
                FROM subnets s
                JOIN peers_subnets ps ON s.subnet = ps.subnet
                JOIN peers p ON ps.peer_id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            subnets_rows = self.cursor.fetchall()
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0], name=row[1], description=row[2]))
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
            self.cursor.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address
                FROM peers p
                LEFT JOIN services s ON p.id = s.id
                WHERE s.id IS NULL
            """)
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                address = row[3]
                address_ip = ipaddress.ip_address(address)
                if address_ip in ipaddress.ip_network(subnet.subnet, strict=False):
                    peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3]))
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
            self.cursor.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, s.name, s.department
                FROM peers p
                JOIN services s ON p.id = s.id
            """)
            services_rows = self.cursor.fetchall()
            for row in services_rows:
                address = row[3]
                address_ip = ipaddress.ip_address(address)
                if address_ip in ipaddress.ip_network(subnet.subnet, strict=False):
                    services.append(Service(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], name=row[4], department=row[5]))
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
            self.cursor.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address
                FROM peers p
                JOIN peers_subnets ps ON p.id = ps.peer_id
                WHERE ps.subnet = ?
            """, (subnet.subnet,))
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peers linked to subnet: {e}")
        return peers
    
    def create_service(self, service: Service):
        try:
            # Insert into peers table
            self.cursor.execute("""
                INSERT INTO peers (username, address, public_key, preshared_key)
                VALUES (?, ?, ?, ?)
            """, (service.username, service.address, service.public_key, service.preshared_key))

            # Get the user ID (auto-incremented primary key)
            peer_id = self.cursor.lastrowid

            # Insert into services table using the same ID
            self.cursor.execute("""
                INSERT INTO services (id, name, department)
                VALUES (?, ?, ?)
            """, (peer_id, service.name, service.department))

            return peer_id

        except sqlite3.Error as e:
            raise Exception(f"Failed to create service peer: {e}")
        
    def add_peer_service_link(self, peer: Peer, service: Service):
        """
        This function adds a link between a peer and a service.
        It will create the entry in the peers_services table, which is a many-to-many relationship between peers and services.
        """
        try:
            self.cursor.execute("""
                INSERT INTO peers_services (peer_id, service_id)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), (SELECT id FROM services WHERE name = ?))
                ON CONFLICT(peer_id, service_id) DO NOTHING
            """, (peer.public_key, service.name))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link from peer to service: {e}")

    def remove_peer_service_link(self, peer: Peer, service: Service):
        """
        This function removes a link between a peer and a service.
        It will delete the entry in the peer_services table.
        """
        try:
            self.cursor.execute("""
                DELETE FROM peers_services WHERE peer_id = (SELECT id FROM peers WHERE public_key = ?) AND service_id = (SELECT id FROM services WHERE name = ?)
            """, (peer.public_key, service.name))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link from peer to service: {e}")

    def delete_service(self, service: Service):
        """
        This function deletes a service from the database.
        It will delete the entry in the services table and the corresponding peer in the peers table.
        """
        try:
            self.cursor.execute("""
                DELETE FROM peers WHERE public_key = ?
            """, (service.public_key,))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while deleting service: {e}")

    def get_peers_services_links(self, peer: Peer) -> list[Service]:
        """
        This function returns a list of services that a user is connected to.
        It will return a list of Service objects.
        """
        services = []
        try:
            self.cursor.execute("""
                SELECT s.name, s.department, p.public_key, p.preshared_key, p.address
                FROM services s
                JOIN peers_services ps ON s.id = ps.service_id
                JOIN peers p ON ps.peer_id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            services_rows = self.cursor.fetchall()
            for row in services_rows:
                services.append(Service(username=peer.username, public_key=row[2], preshared_key=row[3], address=row[4], name=row[0], department=row[1]))
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
            self.cursor.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, s.name, s.department
                FROM peers p
                JOIN services s ON p.id = s.id
            """)
            services_rows = self.cursor.fetchall()
            for row in services_rows:
                services.append(Service(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], name=row[4], department=row[5]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting all services: {e}")
        return services
        
    def get_service_by_name(self, name: str) -> Service|None:
        """
        This function returns a Service object by its name.
        If the service does not exist, it will return None.
        """
        try:
            self.cursor.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address, s.name, s.department
                FROM peers p
                JOIN services s ON p.id = s.id
                WHERE s.name = ?
            """, (name,))
            row = self.cursor.fetchone()
            if row:
                return Service(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], name=row[4], department=row[5])
            
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting service by name: {e}")
        return None

    def get_service_peers(self, service: Service) -> list[Peer]:
        """
        This function returns a list of peers that are linked to a service.
        It will return a list of Peer objects.
        """
        peers = []
        try:
            self.cursor.execute("""
                SELECT p.username, p.public_key, p.preshared_key, p.address
                FROM peers p
                JOIN peers_services ps ON p.id = ps.peer_id
                JOIN services s ON ps.service_id = s.id
                WHERE s.name = ?
            """, (service.name,))
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3]))
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
            self.cursor.execute("""
                SELECT s.name, s.department, p.public_key, p.preshared_key, p.address
                FROM services s
                JOIN peers_services ps ON s.id = ps.service_id
                JOIN peers p ON ps.peer_id = p.id
                WHERE p.public_key = ?
            """, (peer.public_key,))
            services_rows = self.cursor.fetchall()
            for row in services_rows:
                services.append(Service(username=peer.username, public_key=row[2], preshared_key=row[3], address=row[4], name=row[0], department=row[1]))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting peer's services: {e}")
        return services
    
    def add_link_between_two_peers(self, peer1: Peer, peer2: Peer):
        """
        This function adds a link between two peers.
        It will create the entry in the links table, which is a many-to-many relationship between peers.
        """
        try:
            self.cursor.execute("""
                INSERT INTO peers_peers (peer_one_id, peer_two_id)
                VALUES ((SELECT id FROM peers WHERE public_key = ?), (SELECT id FROM peers WHERE public_key = ?))
            """, (peer1.public_key, peer2.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while adding link between peers: {e}")

    def remove_link_between_two_peers(self, peer1: Peer, peer2: Peer):
        """
        This function removes a link between two peers.
        It will delete the entry in the links table.
        """
        try:
            self.cursor.execute("""
                DELETE FROM peers_peers WHERE peer_one_id = (SELECT id FROM peers WHERE public_key = ?) AND peer_two_id = (SELECT id FROM peers WHERE public_key = ?)
            """, (peer1.public_key, peer2.public_key))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while removing link between peers: {e}")

    def get_links_between_peers(self)->list[tuple[Peer, Peer]]:
        """
        This function returns a list of links between peers.
        It will return a list of tuples, each containing two Peer objects.
        """
        links = []
        try:
            self.cursor.execute("""
                SELECT p1.username, p1.public_key, p1.preshared_key, p1.address, p2.username, p2.public_key, p2.preshared_key, p2.address
                FROM peers_peers pp
                JOIN peers p1 ON pp.peer_one_id = p1.id
                JOIN peers p2 ON pp.peer_two_id = p2.id
            """)
            links_rows = self.cursor.fetchall()
            for row in links_rows:
                peer1 = Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3])
                peer2 = Peer(username=row[4], public_key=row[5], preshared_key=row[6], address=row[7])
                links.append((peer1, peer2))
        except sqlite3.Error as e:
            raise Exception(f"An error occurred while getting links between peers: {e}")
        return links


    def close(self):
        self.conn.close()

