import sqlite3
from main import Peer,Service

db_path = "/etc/wireguard/user_configs.db"

class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def update_peer(self,peer:Peer):
        """
        Updates the table regarding the peer within the database, the allowed IPS are updated.
        If the updated peers do not exist, they will be put to null, it is the equivalent of disabling this config without deleting it.
        """

        return
    
    def remove_peer(self,peer:Peer):
        """
        Removes a peer from the database.
        """
        return
    
    def add_service(self, peer: Service):
        """
        Adds a service to the database, this is used to add a service to the database.
        """
        return

    def load_peers(self):
        return



    def close(self):
        self.conn.close()

