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

## Policy Overrides

Policy overrides is an **advanced** feature that allows an operator to override
the default policy of an OpenStack service. The policies that the service
supports, the defaults it implements in its code, and the defaults that a charm
may include should all be clearly understood before proceeding.

> **Caution**: It is possible to break the system (for tenants and other
  services) if policies are incorrectly applied to the service.

Policy statements are placed in a YAML file. This file (or files) is then (ZIP)
compressed into a single file and used as an application resource. The override
is then enabled via a Boolean charm option.

Here are the essential commands (filenames are arbitrary):

    zip overrides.zip override-file.yaml
    juju attach-resource aodh policyd-override=overrides.zip
    juju config aodh use-policyd-override=true

See appendix [Policy Overrides][cdg-appendix-n] in the [OpenStack Charms
Deployment Guide][cdg] for a thorough treatment of this feature.

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-aodh/+filebug).

For general questions please refer to the OpenStack [Charm Guide](https://docs.openstack.org/charm-guide/latest/).

<!-- LINKS -->

[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[cdg-appendix-n]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-policy-overrides.html