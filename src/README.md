# Overview

This charm provides the Aodh Alarming service for an OpenStack Cloud.

# Usage

Aodh relies on services from the mongodb, rabbitmq-server and keystone charms:

    juju deploy aodh
    juju deploy keystone
    juju deploy mongodb | mysql
    juju deploy rabbitmq-server
    juju add-relation aodh rabbitmq-server
    juju add-relation aodh mongodb | mysql
    juju add-relation aodh keystone

# Configuration Options

TODO
