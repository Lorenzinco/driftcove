from main import Peer,Service,Subnet
import sqlite3

db_path = "/etc/wireguard/user_configs.db"

class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def create_peer(self,peer:Peer):
        """
        It creates a peer inside the database.
        The fuction returns nothing, but will raise an error if the database operation fails.
        """
        try:
            self.cursor.execute("""
                INSERT INTO users (username, public_key)
                VALUES (?, ?, ?)
                ON CONFLICT(public_key) DO UPDATE SET
                allowed_ips = excluded.allowed_ips
            """, (peer.username, peer.public_key))
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
                SELECT username, public_key, allowed_ips 
                FROM users WHERE username = ?
            """, (username,))
            row = self.cursor.fetchone()
            if row:
                return Peer(username=row[0], public_key=row[1], allowed_ips=row[2])
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
                SELECT (subnet, name, description) 
                FROM subnets
            """)
            subnets_rows = self.cursor.fetchall()
            for row in subnets_rows:
                subnets.append(Subnet(subnet=row[0],name=row[1],description=row[2]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return subnets
    
    def update_service(self, peer: Service):
        """
        This function can be seen as an abstraction for the update and creation of a service, it will update the service if it exists, or create it if it does not.
        Input fields are the service's name, department, public key and allowed IPs.
        """
        try:
            self.cursor.execute("""
                INSERT INTO services (name, department, public_key, allowed_ips)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(public_key) DO UPDATE SET
                allowed_ips = excluded.allowed_ips
            """, (peer.name, peer.department, peer.public_key, peer.allowed_ips))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return

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
                SELECT u.username, u.public_key, u.allowed_ips
                FROM users u
                JOIN user_subnets us ON u.id = us.user_id
                WHERE us.subnet = ?
            """, (subnet.subnet,))
            peers_rows = self.cursor.fetchall()
            for row in peers_rows:
                peers.append(Peer(username=row[0], public_key=row[1], allowed_ips=row[2]))
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
        return peers

    def close(self):
        self.conn.close()

