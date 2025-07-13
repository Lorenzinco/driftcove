import sqlite3
import os
import ipaddress


def init_db(db_path):
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    WIREGUARD_SUBNET = os.getenv("WIREGUARD_SUBNET","10.128.0.0/9")
    PUBLIC_KEY = os.getenv("PUBLIC_KEY", "default_public_key")
    PRESHARED_KEY = os.getenv("PRESHARED_KEY", "X2RHVZ+j12IDqxq8HaKOp77+MRprFo7XxO8LrE9BhxE=")
    net = ipaddress.ip_network(WIREGUARD_SUBNET, strict=False)

    # pick the first usable IP address in the subnet
    first_ip = str(next(net.hosts()))

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS peers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        address TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        public_key TEXT NOT NULL UNIQUE,
        preshared_key TEXT
    )""")

    cursor.execute("""            
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        department TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id) REFERENCES peers(id) ON DELETE CASCADE
    )""")

    cursor.execute("""        
    CREATE TABLE IF NOT EXISTS subnets(
        subnet TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT
    )""")

    cursor.execute("""        
    CREATE TABLE IF NOT EXISTS peers_subnets(
        peer_id INTEGER,
        subnet TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (peer_id, subnet),
        FOREIGN KEY (peer_id) REFERENCES peers(id),
        FOREIGN KEY (subnet) REFERENCES subnets(subnet)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS peers_services (
        peer_id INTEGER,
        service_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (peer_id, service_id),
        FOREIGN KEY (peer_id) REFERENCES peers(id),
        FOREIGN KEY (service_id) REFERENCES services(id),
        CHECK (peer_id != service_id)
    )""")

    cursor.execute("""
    INSERT OR IGNORE INTO subnets (subnet, name, description)
    VALUES (?, ?, ?)
    """, (WIREGUARD_SUBNET, "Wireguard Subnet", "This is the subnet for the WireGuard configuration."))
    cursor.execute("""
    INSERT OR IGNORE INTO peers (username, address, public_key, preshared_key)
    VALUES (?, ?, ?, ?)
    """, ("master", first_ip, PUBLIC_KEY, PRESHARED_KEY))

    cursor.execute("""
                   INSERT OR IGNORE INTO peers_subnets (peer_id, subnet)
                     SELECT id, ? FROM peers WHERE username = ?
                     """, (WIREGUARD_SUBNET, "master"))
    # Commit changes and close connection
    conn.commit()
    conn.close()