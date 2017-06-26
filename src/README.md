# Overview

This charm provides the Aodh Alarming service for an OpenStack Cloud.

# Usage

Aodh relies on services from the mongodb, rabbitmq-server and keystone charms:

    juju deploy aodh
    juju deploy keystone
    juju deploy mysql
    juju deploy rabbitmq-server
    juju add-relation aodh rabbitmq-server
    juju add-relation aodh mysql
    juju add-relation aodh keystone

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-aodh/+filebug).

For general questions please refer to the OpenStack [Charm Guide](http://docs.openstack.org/developer/charm-guide/).
