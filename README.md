
<picture>
  <source
    media="(prefers-color-scheme: dark)"
    srcset="backend/assets/driftcove_dark.svg"
    type="image/svg+xml"
  />
  <img
    src="backend/assets/driftcove_light.svg"
    alt="Driftcove Logo"
    style="height: 80px;"
  />
</picture>
A docker image used to create and customize a vpn server

![GitHub License](https://img.shields.io/github/license/lorenzinco/driftcove?style=for-the-badge&link=https%3A%2F%2Fgithub.com%2FLorenzinco%2Fdriftcove%3Ftab%3DMIT) ![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/lorenzinco/driftcove/test_wireguard.yml?style=for-the-badge)



## Features

With driftcove you can create, manage and customize your VPN like never before, Driftcove allows for dynamic routing to happen in your network, you can define subnetworks and allow peers to reach them dynamically by making calls to the api.


Inside driftcove's frontend you will able to manage your network from the ground up, you can create peers, assigne them to subnetworks, make subnetworks access provided services and much more.
![Overview](https://raw.githubusercontent.com/lorenzinco/driftcove/main/backend/assets/overview.png)

### Create Subnetworks and customize them
You can create subnetworks and customize them to your needs, you can define which peers can access them and which services are provided inside them.
![Subnetworks](https://raw.githubusercontent.com/lorenzinco/driftcove/main/backend/assets/create_and_customize_subnets.png)

Subnetworks also have a built in DHCP server that will assign IPs to peers that are connected to them, this way you don't have to worry about IP conflicts.

### Create peers
You can create peers configurations and download them directly from the frontend, each peer is either public in his subnet or public into subnets to which he is guest, being "public" means that everybody in the subnetwork can reach him on whatever port. 
#### Hosting
A peer can also be a host and provide services for peers or entier subnetworks, driftcove will allow under the hood only the traffic that is allowed by you, so you can be sure that your network is secure.
![Peers](https://raw.githubusercontent.com/lorenzinco/driftcove/main/backend/assets/peerInfo.png)

## Installation
To install driftcove, you need to have docker and docker-compose installed on your machine.

1. Clone the repository
```bash
git clone https://github.com/Lorenzinco/driftcove.git
```

2. Navigate to the project directory
```bash
cd driftcove
``` 

3. Review the dockerfile where the image is built, you can customize it to your needs. VERY IMPORTANT: make sure to change API_TOKEN in the dockerfile to a secure one.
```compose
services:
  driftcove-backend:
    ...
    environment:
      ...
      - API_TOKEN=supersecuretoken <--- CHANGE THIS TO A SECURE ONE
    sysctls:
    ...
```

4. Run the containers with compose
```bash
docker-compose up --build -d
```

## Contributing
Feel free to contribute to this project by opening issues or pull requests on GitHub, any help is appreciated!