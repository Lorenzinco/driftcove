import requests

BASE_URL = "http://localhost:8000"
HEADERS = {"Authorization": "Bearer supersecuretoken"}

def test_create_subnet(subnet:str ="10.42.0.0/24"):
    print("\033[94mCreating subnet...\033[0m")
    data = {"subnet": subnet, "name": "Test Subnet", "description": "This is a test subnet."}
    r = requests.post(f"{BASE_URL}/subnet/create", json=data, headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print("\033[92mSuccessfully created subnet\033[0m")
        return True
    else:
        print(f"\033[91mFailed to create subnet {r.status_code}: {r.text}\033[0m")
        return False

def test_delete_subnet(subnet="10.42.0.0/24"):
    print(f"\033[94mDeleting subnet {subnet}...\033[0m")
    r = requests.delete(f"{BASE_URL}/subnet/", params={"subnet": subnet}, headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print("\033[92mSuccessfully deleted subnet\033[0m")
        return True
    else:
        print(f"\033[91mFailed to delete subnet {r.status_code}: {r.text}\033[0m")
        return False

def test_create_peer(username="testuser", subnet="10.128.0.0/9"):
    print(f"\033[94mCreating peer {username}...\033[0m")
    params = {"username": username, "subnet": subnet}
    r = requests.post(f"{BASE_URL}/peer/create", params=params, headers=HEADERS)
    print(r.status_code)
    config = r.json().get("configuration", "")
    print(config)
    if r.status_code == 200:
        print("\033[92mSuccessfully created peer\033[0m")
        return True
    else:
        print(f"\033[91mFailed to create peer {r.status_code}: {r.text}\033[0m")
        return False

def test_remove_peer(username="testuser"):
    print(f"\033[94mDeleting peer {username}...\033[0m")
    r = requests.delete(f"{BASE_URL}/peer/", params={"username": username}, headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print("\033[92mSuccessfully removed peer\033[0m")
        return True
    else:
        print(f"\033[91mFailed to remove peer {r.status_code}: {r.text}\033[0m")
        return False

def test_peer_get_info(username="testuser"):
    print(f"\033[94mGetting info for peer {username}...\033[0m")
    r = requests.get(f"{BASE_URL}/peer/info", params={"username": username}, headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print("\033[92mSuccessfully retrieved peer info\033[0m")
        return True
    else:
        print(f"\033[91mFailed to retrieve peer info {r.status_code}: {r.text}\033[0m")
        return False

def test_connect_peer_to_subnet(username="testuser", subnet = "10.42.0.0/24"):
    print("\033[94mConnecting peer to subnet...\033[0m")
    r = requests.post(f"{BASE_URL}/subnet/connect", params={"username": username, "subnet": subnet}, headers=HEADERS)
    if r.status_code == 200:
        print("\033[92mSuccessfully connected peer to subnet\033[0m")
        return True
    else:
        print(f"\033[91mFailed to connect peer to subnet {r.status_code}: {r.text}\033[0m")
        return False

def test_disconnect_peer_from_subnet(username="testuser", address= "10.42.0.0/24"):
    print(f"\033[94mDisconnecting peer {username} from subnet {address}...\033[0m")
    r = requests.delete(f"{BASE_URL}/subnet/disconnect", params={"username": username, "subnet": address}, headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print("\033[92mSuccessfully disconnected peer from subnet\033[0m")
        return True
    else:
        print(f"\033[91mFailed to disconnect peer from subnet {r.status_code}: {r.text}\033[0m")
        return False

def test_get_topology():
    print("\033[94mGetting topology...\033[0m")
    r = requests.get(f"{BASE_URL}/network/topology", headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print("\033[92mSuccessfully retrieved topology\033[0m")
        return True
    else:
        print(f"\033[91mFailed to retrieve topology {r.status_code}: {r.text}\033[0m")
        return False

def test_get_subnets():
    print("\033[94mGetting subnets...\033[0m")
    r = requests.get(f"{BASE_URL}/network/subnets", headers=HEADERS)
    print(r.text)
    if r.status_code == 200:
        print("\033[92mSuccessfully retrieved subnets\033[0m")
        return True
    else:
        print(f"\033[91mFailed to retrieve subnets {r.status_code}: {r.text}\033[0m")
        return False


def test_status():
    print("\033[94mGetting wg status...\033[0m")
    r = requests.get(f"{BASE_URL}/status", headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print("\033[92mStatus check successful\033[0m")
        return True
    else:
        print(f"\033[91mStatus check failed {r.status_code}: {r.text}\033[0m")
        return False

def test_create_service(name="Https server", department="IT", peer_username="Test", port: int=443, description: str="This is a test service."):
    print(f"\033[94mCreating service {name}...\033[0m")
    data = {"service_name": name, "department": department, "username": peer_username, "port": port, "description": description}
    r = requests.post(f"{BASE_URL}/service/create", params=data, headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print(f"\033[92mSuccessfully created service {name}\033[0m")
        return True
    else:
        print(f"\033[91mFailed to create service {name} {r.status_code}: {r.text}\033[0m")
        return False
    return r.json()

def test_connect_service(service_name="Test Service", peer_username="testuser"):
    print(f"\033[94mConnecting service {service_name} to peer {peer_username}...\033[0m")
    r = requests.post(f"{BASE_URL}/service/connect", params={"service_name": service_name, "username": peer_username}, headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print(f"\033[92mSuccessfully connected {peer_username} to {service_name}\033[0m")
        return True
    else:
        print(f"\033[91mFailed to connect {peer_username} to {service_name} {r.status_code}: {r.text}\033[0m")
        return False

def test_disconnect_service(service_name="Test Service", peer_username="testuser"):
    print(f"\033[94mDisconnecting service {service_name} from peer {peer_username}...\033[0m")
    r = requests.delete(f"{BASE_URL}/service/disconnect", params={"service_name": service_name, "username": peer_username}, headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print(f"\033[92mSuccessfully disconnected {peer_username} from {service_name}\033[0m")
        return True
    else:
        print(f"\033[91mFailed to disconnect {peer_username} from {service_name} {r.status_code}: {r.text}\033[0m")
        return False

def test_delete_service(service_name="Test Service"):
    print(f"\033[94mDeleting service {service_name}...\033[0m")
    r = requests.delete(f"{BASE_URL}/service/delete", params={"service_name": service_name}, headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print(f"\033[92mSuccessfully deleted service {service_name}\033[0m")
        return True
    else:
        print(f"\033[91mFailed to delete service {service_name} {r.status_code}: {r.text}\033[0m")
    return False

def test_add_link_between_peers(peer1_username="testuser", peer2_username="testuser2"):
    print(f"\033[94mConnecting peers {peer1_username} and {peer2_username}...\033[0m")
    r = requests.post(f"{BASE_URL}/peer/connect", params={"peer1_username": peer1_username, "peer2_username": peer2_username}, headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print(f"\033[92mSuccessfully connected {peer1_username} and {peer2_username}\033[0m")
        return True
    else:
        print(f"\033[91mFailed to connect {peer1_username} and {peer2_username} {r.status_code}: {r.text}\033[0m")
        return False

def test_disconnect_link_between_peers(peer1_username="testuser", peer2_username="testuser2"):
    print(f"\033[94mDisconnecting peers {peer1_username} and {peer2_username}...\033[0m")
    r = requests.delete(f"{BASE_URL}/peer/disconnect", params={"peer1_username": peer1_username, "peer2_username": peer2_username}, headers=HEADERS)
    print(r.status_code, r.text)
    if r.status_code == 200:
        print(f"\033[92mSuccessfully disconnected {peer1_username} and {peer2_username}\033[0m")
        return True
    else:
        print(f"\033[91mFailed to disconnect {peer1_username} and {peer2_username} {r.status_code}: {r.text}\033[0m")
        return False

def test_get_all_peers():
    print("\033[94mGetting all peers...\033[0m")
    r = requests.get(f"{BASE_URL}/peer/all", headers=HEADERS)
    print(r.status_code, r.json())
    if r.status_code == 200:
        print("\033[92mSuccessfully retrieved all peers\033[0m")
        return True
    else:
        print(f"\033[91mFailed to retrieve all peers {r.status_code}: {r.text}\033[0m")
        return False




if __name__ == "__main__":
    # test_create_peer("peer1")
    # test_create_peer("peer2")
    # test_add_link_between_peers("peer1", "peer2")
    # exit(0)

    # test_get_subnets()
    #test_get_topology()
    test_create_service()
    exit(0)

    assert(test_create_peer() is True)
    assert(test_create_subnet() is True)
    assert(test_connect_peer_to_subnet() is True)
    assert(test_get_topology() is True)
    assert(test_disconnect_peer_from_subnet() is True)
    assert(test_delete_subnet() is True)

    # this should fail
    assert( test_create_peer(subnet="10.42.0.0/24") is False)

    assert(test_get_all_peers() is True)
    assert(test_remove_peer() is True)
    assert(test_get_all_peers() is True)

    assert(test_create_peer("peer1") is True)
    assert(test_create_peer("peer2") is True)
    assert(test_add_link_between_peers("peer1", "peer2") is True)
    assert(test_get_topology() is True)
    assert(test_disconnect_link_between_peers("peer1", "peer2") is True)
    assert(test_remove_peer("peer1") is True)
    assert(test_remove_peer("peer2") is True)
    assert(test_get_topology() is True)

    assert(test_create_peer() is True)
    assert(test_create_subnet() is True)
    assert(test_create_service() is True)
    assert(test_connect_service() is True)
    assert(test_get_topology() is True)
    assert(test_disconnect_service() is True)
    assert(test_delete_service() is True)
    assert(test_delete_subnet() is True)
    assert(test_get_topology() is True)
    assert(test_remove_peer() is True)

    print("\033[92mAll tests passed successfully!\033[0m")