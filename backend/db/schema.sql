PRAGMA foreign_keys = ON;

 
CREATE TABLE IF NOT EXISTS peers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    public_key TEXT NOT NULL UNIQUE,
    preshared_key TEXT,
    x FLOAT,
    y FLOAT
);

        
CREATE TABLE IF NOT EXISTS services (
    id INTEGER,
    name TEXT NOT NULL UNIQUE,
    department TEXT,
    port INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id) REFERENCES peers(id) ON DELETE CASCADE,
    PRIMARY KEY (id, port)
);

    
CREATE TABLE IF NOT EXISTS subnets(
    subnet TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    x FLOAT,
    y FLOAT,
    width FLOAT,
    height FLOAT,
    rgba INTEGER DEFAULT 0x00FF00E5
);

    
CREATE TABLE IF NOT EXISTS peers_subnets(
    peer_id INTEGER,
    subnet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_id, subnet),
    FOREIGN KEY (peer_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (subnet) REFERENCES subnets(subnet) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS peers_services (
    peer_id INTEGER,
    service_id INTEGER,
    service_port INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_id, service_id, service_port),
    FOREIGN KEY (peer_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id, service_port) REFERENCES services(id, port) ON DELETE CASCADE,
    CHECK (peer_id != service_id)
);

CREATE TABLE IF NOT EXISTS peers_peers (
    peer_one_id INTEGER,
    peer_two_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_one_id, peer_two_id),
    FOREIGN KEY (peer_one_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (peer_two_id) REFERENCES peers(id) ON DELETE CASCADE,
    CHECK (peer_one_id != peer_two_id)
);

CREATE TABLE IF NOT EXISTS subnets_subnets (
    subnet_one TEXT,
    subnet_two TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subnet_one, subnet_two),
    FOREIGN KEY (subnet_one) REFERENCES subnets(subnet) ON DELETE CASCADE,
    FOREIGN KEY (subnet_two) REFERENCES subnets(subnet) ON DELETE CASCADE,
    CHECK (subnet_one != subnet_two)
);

CREATE TABLE IF NOT EXISTS subnets_services (
    service_id INTEGER,
    service_port INTEGER,
    subnet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (service_id, service_port, subnet),
    FOREIGN KEY (service_id, service_port) REFERENCES services(id, port) ON DELETE CASCADE,
    FOREIGN KEY (subnet) REFERENCES subnets(subnet) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_subnets_subnets (
    subnet_one TEXT,
    subnet_two TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subnet_one, subnet_two),
    FOREIGN KEY (subnet_one) REFERENCES subnets(subnet) ON DELETE CASCADE,
    FOREIGN KEY (subnet_two) REFERENCES subnets(subnet) ON DELETE CASCADE,
    CHECK (subnet_one != subnet_two)
);

CREATE TABLE IF NOT EXISTS admin_peers_peers (
    peer_one_id INTEGER,
    peer_two_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_one_id, peer_two_id),
    FOREIGN KEY (peer_one_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (peer_two_id) REFERENCES peers(id) ON DELETE CASCADE,
    CHECK (peer_one_id != peer_two_id)
);

CREATE TABLE IF NOT EXISTS admin_peers_subnets (
    peer_id INTEGER,
    subnet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (peer_id, subnet),
    FOREIGN KEY (peer_id) REFERENCES peers(id) ON DELETE CASCADE,
    FOREIGN KEY (subnet) REFERENCES subnets(subnet) ON DELETE CASCADE
);