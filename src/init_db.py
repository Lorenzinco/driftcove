import sqlite3
import os

db_path = "/etc/wireguard/user_configs.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
WIREGUARD_SUBNET = os.getenv("WIREGUARD_SUBNET","10.128.0.0/9")

# Create a table (example: users)
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    public_key TEXT NOT NULL UNIQUE
);
               
CREATE TABLE IF NOT EXISTS services(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    public_key TEXT NOT NULL UNIQUE,
    subnet TEXT,
    FOREIGN KEY (subnet) REFERENCES subnets(subnet) ON DELETE SET NULL,
);
               
CREATE TABLE IF NOT EXISTS subnets(
    subnet TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
               
CREATE TABLE IF NOT EXISTS user_subnets(
    user_id INTEGER,
    subnet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, subnet),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (subnet) REFERENCES subnets(subnet) ON DELETE CASCADE
);
               
""")

cursor.execute("""
INSERT OR IGNORE INTO subnets (subnet, name, description)
VALUES (?, ?, ?)
""", (WIREGUARD_SUBNET, "Wireguard Subnet", "This is the subnet for the WireGuard configuration."))
# Commit changes and close connection
conn.commit()
conn.close()