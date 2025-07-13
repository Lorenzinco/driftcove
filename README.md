# Driftcove

![GitHub License](https://img.shields.io/github/license/lorenzinco/driftcove?style=for-the-badge&link=https%3A%2F%2Fgithub.com%2FLorenzinco%2Fdriftcove%3Ftab%3DMIT)

A docker image used to create and customize a vpn server

![Driftcove Logo](https://raw.githubusercontent.com/lorenzinco/driftcove/main/assets/driftcove.png)

## Features

With driftcove you can create, manage and customize your VPN like never before, Driftcove allows for dynamic routing to happen in your network, you can define subnetworks and allow peers to reach them dynamically by making calls to the api.

Driftcove also makes the distinction between subnetworks and services, if for example in your network everybody needs to be able to access a service, you can place the service within a subnetwork and then allow everybody in the subnetwork to reach it, but if you need more granularity driftcove can also allow for single peers to reach the service.