PRAGMA foreign_keys = ON;

 
CREATE TABLE IF NOT EXISTS peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    public_key TEXT NOT NULL UNIQUE,
    preshared_key TEXT
);

        
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    department TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id) REFERENCES peers(id) ON DELETE CASCADE
);

    
CREATE TABLE IF NOT EXISTS subnets(
    subnet TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

    
CREATE TABLE IF NOT EXISTS peers_subnets(
    peer_id INTEGER,
    subnet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_id, subnet),
    FOREIGN KEY (peer_id) REFERENCES peers(id),
    FOREIGN KEY (subnet) REFERENCES subnets(subnet) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS peers_services (
    peer_id INTEGER,
    service_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_id, service_id),
    FOREIGN KEY (peer_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
    CHECK (peer_id != service_id)
);

CREATE TABLE IF NOT EXISTS peers_peers (
    peer_one_id INTEGER,
    peer_two_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_one_id, peer_two_id),
    FOREIGN KEY (peer_one_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (peer_two_id) REFERENCES peers(id) ON DELETE CASCADE
    CHECK (peer_one_id != peer_two_id)
);