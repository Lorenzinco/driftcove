import sqlite3

db_path = "/etc/wireguard/user_configs.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create a table (example: users)
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    public_key TEXT NOT NULL UNIQUE,
    allowed_ips TEXT NOT NULL
);
               
CREATE TABLE IF NOT EXISTS services(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    public_key TEXT NOT NULL UNIQUE,
    allowed_ips TEXT
)
""")

# Commit changes and close connection
conn.commit()
conn.close()