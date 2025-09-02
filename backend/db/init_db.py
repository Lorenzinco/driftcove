import sqlite3,os,ipaddress
from backend.core.config import settings

def init_db(db_path):
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        cursor.executescript(f.read())

    PRESHARED_KEY = os.getenv("PRESHARED_KEY", "X2RHVZ+j12IDqxq8HaKOp77+MRprFo7XxO8LrE9BhxE=")

    cursor.execute("""
    INSERT OR IGNORE INTO subnets (subnet, name, description)
    VALUES (?, ?, ?)
    """, (settings.wg_default_subnet, "Wireguard Subnet", "This is the subnet for the WireGuard configuration."))

    # fetch for the master peer 
    cursor.execute("SELECT * FROM peers WHERE username = ?", ("master",))
    master_peer = cursor.fetchone()
    if not master_peer:
        net = ipaddress.ip_network(settings.wg_default_subnet, strict=False)
        # pick the first usable IP address in the subnet
        first_ip = str(next(net.hosts()))
        # if the master peer does not exist, create it
        cursor.execute("""
        INSERT INTO peers (username, address, public_key, preshared_key)
        VALUES (?, ?, ?, ?)
        """, ("master", first_ip, settings.public_key, PRESHARED_KEY))

        cursor.execute("""
                    INSERT OR IGNORE INTO peers_subnets (peer_id, subnet)
                        SELECT id, ? FROM peers WHERE username = ?
                        """, (settings.wg_default_subnet, "master"))
    # Commit changes and close connection
    conn.commit()
    conn.close()