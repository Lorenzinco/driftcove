from .models import Peer,Service,Subnet
import ipaddress, sqlite3, logging


class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path,check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()

    def create_peer(self,peer:Peer):
        """
        It creates a peer inside the database.
        The fuction returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.cursor.execute("""
                INSERT INTO users (username, public_key, preshared_key, address)
                VALUES (?, ?, ?, ?)
            """, (peer.username, peer.public_key, peer.preshared_key, peer.address))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

        return
    
    def remove_peer(self,peer:Peer):
        """
        Removes a peer from the database.
        This action is permanent, if you wish to disable a peer, use the update_peer function with null values.
        The function returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.cursor.execute("""
                DELETE FROM users WHERE public_key = ?
            """, (peer.public_key,))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return
    
    def get_avaliable_ip(self, subnet: Subnet) -> str|None:
        """
        This function returns an available IP address from the subnet.
        It will return the first available IP address that is not already in use.
        """
        try:
            self.cursor.execute("""
                SELECT address FROM users
            """)
            all_addresses = [row[0] for row in self.cursor.fetchall()]
            net = ipaddress.ip_network(subnet.subnet, strict=False)
            used_ips = {ip for ip in all_addresses if ipaddress.ip_address(ip) in net}

            for ip in net.hosts():
                if str(ip) not in used_ips:
                    return str(ip)
            logging.warning(f"No available IPs found in subnet {subnet.subnet}")
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return None
    
    def get_avaliable_username_for_service(self)->str|None:
        """
        This function returns an available username for a service.
        It will return the first available username that is not already in use.
        """
        try:
            self.cursor.execute("""
                SELECT username FROM users
            """)
            all_usernames = {row[0] for row in self.cursor.fetchall()}
            for i in range(1, 10000):  # Arbitrary limit to avoid infinite loop
                username = f"service_{i}"
                if username not in all_usernames:
                    return username
            logging.warning("No available usernames found.")
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
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
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error has occurred: {e}")
        return
    
    def get_peer_by_username(self, username: str) -> Peer:
        """
        This function returns a Peer object by its username.
        If the peer does not exist, it will return None.
        """
        try:
            self.cursor.execute("""
                SELECT username, public_key, preshared_key, address
                FROM users WHERE username = ?
            """, (username,))
            row = self.cursor.fetchone()
            if row:
                return Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3])
            else:
                return None
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
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
            logging.basicConfig(level=logging.INFO)
            logging.info(f"Found {len(subnets_rows)} subnets in the database.")
            logging.info(f"Subnets rows: {subnets_rows}")
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0],name=row[1],description=row[2]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
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
            else:
                return None
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            return None
    

    def add_peer_to_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function adds a peer to a subnet.
        It will create the entry in the user_subnets table, which is a many-to-many relationship between users and subnets.
        """
        try:
            self.cursor.execute("""
                INSERT INTO user_subnets (user_id, subnet)
                VALUES ((SELECT id FROM users WHERE public_key = ?), ?)
                ON CONFLICT(user_id, subnet) DO NOTHING
            """, (peer.public_key, subnet.subnet))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return
    
    def remove_peer_from_subnet(self, peer: Peer, subnet: Subnet):
        """
        This function removes a peer from a subnet.
        It will delete the entry in the user_subnets table.
        """
        try:
            self.cursor.execute("""
                DELETE FROM user_subnets WHERE user_id = (SELECT id FROM users WHERE public_key = ?) AND subnet = ?
            """, (peer.public_key, subnet.subnet))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return
    
    def get_peers_subnets(self,peer:Peer)->list[Subnet]:
        """
        This function returns a list of subnets that a peer is part of.
        It will return a list of Subnet objects.
        """
        subnets = []
        try:
            self.cursor.execute("""
                SELECT s.subnet, s.name, s.description
                FROM subnets s
                JOIN user_subnets us ON s.subnet = us.subnet
                JOIN users u ON us.user_id = u.id
                WHERE u.public_key = ?
            """, (peer.public_key,))
            subnets_rows = self.cursor.fetchall()
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0], name=row[1], description=row[2]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return subnets
    
    def get_peers_in_subnet(self, subnet: Subnet) -> list[Peer]:
        """
        This function returns a list of peers in a subnet.
        It will return a list of Peer objects.
        """
        peers = []
        try:
            self.cursor.execute("""
                SELECT u.username, u.public_key, u.preshared_key, u.address
                FROM users u
                JOIN user_subnets us ON u.id = us.user_id
                WHERE us.subnet = ?
            """, (subnet.subnet,))
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return peers
    
    def create_service(self, service: Service):
        try:
            # Insert into users table
            self.cursor.execute("""
                INSERT INTO users (username, address, public_key, preshared_key)
                VALUES (?, ?, ?, ?)
            """, (service.username, service.address, service.public_key, service.preshared_key))

            # Get the user ID (auto-incremented primary key)
            user_id = self.cursor.lastrowid

            # Insert into services table using the same ID
            self.cursor.execute("""
                INSERT INTO services (id, name, department)
                VALUES (?, ?, ?)
            """, (user_id, service.name, service.department))

            self.conn.commit()
            return user_id

        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Failed to create service user: {e}")
        
    def add_peer_service_link(self, user: Peer, service: Service):
        """
        This function adds a link between a user and a service.
        It will create the entry in the user_services table, which is a many-to-many relationship between users and services.
        """
        try:
            self.cursor.execute("""
                INSERT INTO user_services (user_id, service_id)
                VALUES ((SELECT id FROM users WHERE public_key = ?), (SELECT id FROM services WHERE name = ?))
                ON CONFLICT(user_id, service_id) DO NOTHING
            """, (user.public_key, service.name))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

    def remove_peer_service_link(self, user: Peer, service: Service):
        """
        This function removes a link between a user and a service.
        It will delete the entry in the user_services table.
        """
        try:
            self.cursor.execute("""
                DELETE FROM user_services WHERE user_id = (SELECT id FROM users WHERE public_key = ?) AND service_id = (SELECT id FROM services WHERE name = ?)
            """, (user.public_key, service.name))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        
    def delete_service(self, service: Service):
        """
        This function deletes a service from the database.
        It will delete the entry in the services table and the corresponding user in the users table.
        """
        try:
            self.cursor.execute("""
                DELETE FROM users WHERE public_key = ?
            """, (service.public_key))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

    def get_peers_services(self, user: Peer) -> list[Service]:
        """
        This function returns a list of services that a user is part of.
        It will return a list of Service objects.
        """
        services = []
        try:
            self.cursor.execute("""
                SELECT s.name, s.department, u.public_key, u.preshared_key, u.address
                FROM services s
                JOIN user_services us ON s.id = us.service_id
                JOIN users u ON us.user_id = u.id
                WHERE u.public_key = ?
            """, (user.public_key,))
            services_rows = self.cursor.fetchall()
            for row in services_rows:
                services.append(Service(username=user.username, public_key=row[2], preshared_key=row[3], address=row[4], name=row[0], department=row[1]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return services
        
        
    def get_all_services(self) -> list[Service]:
        """
        This function returns a list of all services in the database.
        It will return a list of Service objects.
        """
        services = []
        try:
            self.cursor.execute("""
                SELECT u.username, u.public_key, u.preshared_key, u.address, s.name, s.department
                FROM users u
                JOIN services s ON u.id = s.id
            """)
            services_rows = self.cursor.fetchall()
            for row in services_rows:
                services.append(Service(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], name=row[4], department=row[5]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return services
        
    def get_service_by_name(self, name: str) -> Service|None:
        """
        This function returns a Service object by its name.
        If the service does not exist, it will return None.
        """
        try:
            self.cursor.execute("""
                SELECT u.username, u.public_key, u.preshared_key, u.address, s.name, s.department
                FROM users u
                JOIN services s ON u.id = s.id
                WHERE s.name = ?
            """, (name,))
            row = self.cursor.fetchone()
            if row:
                return Service(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3], name=row[4], department=row[5])
            else:
                return None
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            return None
        
    def get_service_peers(self, service: Service) -> list[Peer]:
        """
        This function returns a list of peers that are linked to a service.
        It will return a list of Peer objects.
        """
        peers = []
        try:
            self.cursor.execute("""
                SELECT u.username, u.public_key, u.preshared_key, u.address
                FROM users u
                JOIN user_services us ON u.id = us.user_id
                JOIN services s ON us.service_id = s.id
                WHERE s.name = ?
            """, (service.name,))
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], preshared_key=row[2], address=row[3]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return peers


    def close(self):
        self.conn.close()

