import sqlite3
import os
import ipaddress


def init_db(db_path):
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    WIREGUARD_SUBNET = os.getenv("WIREGUARD_SUBNET","10.128.0.0/9")
    PUBLIC_KEY = os.getenv("PUBLIC_KEY", "default_public_key")
    net = ipaddress.ip_network(WIREGUARD_SUBNET, strict=False)

    # pick the first usable IP address in the subnet
    first_ip = str(next(net.hosts()))

    # Create a table (example: users)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        address TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        public_key TEXT NOT NULL UNIQUE
    )""")

    cursor.execute("""            
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        department TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    cursor.execute("""        
    CREATE TABLE IF NOT EXISTS subnets(
        subnet TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT
    )""")

    cursor.execute("""        
    CREATE TABLE IF NOT EXISTS user_subnets(
        user_id INTEGER,
        subnet TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, subnet),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (subnet) REFERENCES subnets(subnet)
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_services (
        user_id INTEGER,
        service_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, service_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (service_id) REFERENCES services(id),
        CHECK (user_id != service_id)
    )""")

    cursor.execute("""
    INSERT OR IGNORE INTO subnets (subnet, name, description)
    VALUES (?, ?, ?)
    """, (WIREGUARD_SUBNET, "Wireguard Subnet", "This is the subnet for the WireGuard configuration."))
    cursor.execute("""
    INSERT OR IGNORE INTO users (username, address, public_key)
    VALUES (?, ?, ?)
    """, ("master", first_ip, PUBLIC_KEY))

    cursor.execute("""
                   INSERT OR IGNORE INTO user_subnets (user_id, subnet)
                     SELECT id, ? FROM users WHERE username = ?
                     """, (WIREGUARD_SUBNET, "master"))
    # Commit changes and close connection
    conn.commit()
    conn.close()