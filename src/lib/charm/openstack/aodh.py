# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import charmhelpers.contrib.openstack.utils as ch_utils

import charms_openstack.charm
import charms_openstack.adapters
import charms_openstack.ip as os_ip

AODH_DIR = '/etc/aodh'
AODH_CONF = os.path.join(AODH_DIR, 'aodh.conf')


class AodhAdapters(charms_openstack.adapters.OpenStackAPIRelationAdapters):
    """
    Adapters class for the Aodh charm.
    """
    def __init__(self, relations, charm_instance=None):
        super(AodhAdapters, self).__init__(
            relations,
            options_instance=charms_openstack.adapters.APIConfigurationAdapter(
                service_name='aodh',
                port_map=AodhCharm.api_ports),
            charm_instance=charm_instance)


class AodhCharm(charms_openstack.charm.HAOpenStackCharm):

    # Internal name of charm + keystone endpoint
    service_name = name = 'aodh'

    # First release supported
    release = 'mitaka'

    # Packages the service needs installed
    # LY Hacluster depends on python-apt so fixing it here is a temporary
    # tactical fix. Bug #1606906
    packages = ['aodh-api', 'aodh-evaluator',
                'aodh-expirer', 'aodh-notifier',
                'aodh-listener', 'python-apt']

    # Init services the charm manages
    services = ['aodh-api', 'aodh-evaluator',
                'aodh-notifier', 'aodh-listener']

    # Standard interface adapters class to use.
    adapters_class = charms_openstack.adapters.OpenStackRelationAdapters

    # Ports that need exposing.
    default_service = 'aodh-api'
    api_ports = {
        'aodh-api': {
            os_ip.PUBLIC: 8042,
            os_ip.ADMIN: 8042,
            os_ip.INTERNAL: 8042,
        }
    }

    # Database sync command used to initalise the schema.
    sync_cmd = ['aodh-dbsync']

    # The restart map defines which services should be restarted when a given
    # file changes
    restart_map = {
        AODH_CONF: services,
    }

    # Resource when in HA mode
    ha_resources = ['vips', 'haproxy']

    # Aodh requires a message queue, database and keystone to work,
    # so these are the 'required' relationships for the service to
    # have an 'active' workload status.  'required_relations' is used in
    # the assess_status() functionality to determine what the current
    # workload status of the charm is.
    required_relations = ['amqp', 'shared-db', 'identity-service']

    # Set the adapters class to on specific to Aodh
    # NOTE: review this seems odd as not doing anything off piste here
    adapters_class = AodhAdapters

    def __init__(self, release=None, **kwargs):
        """Custom initialiser for class
        If no release is passed, then the charm determines the release from the
        ch_utils.os_release() function.
        """
        if release is None:
            release = ch_utils.os_release('python-keystonemiddleware')
        super(AodhCharm, self).__init__(release=release, **kwargs)

    def install(self):
        """Customise the installation, configure the source and then call the
        parent install() method to install the packages
        """
        self.configure_source()
        # and do the actual install
        super(AodhCharm, self).install()


def install():
    """Use the singleton from the AodhCharm to install the packages on the
    unit
    """
    AodhCharm.singleton.install()


def restart_all():
    """Use the singleton from the AodhCharm to restart services on the
    unit
    """
    AodhCharm.singleton.restart_all()


def db_sync():
    """Use the singleton from the AodhCharm to run db migration
    """
    AodhCharm.singleton.db_sync()


def setup_endpoint(keystone):
    """When the keystone interface connects, register this unit in the keystone
    catalogue.
    """
    charm = AodhCharm.singleton
    keystone.register_endpoints(charm.service_name,
                                charm.region,
                                charm.public_url,
                                charm.internal_url,
                                charm.admin_url)


def render_configs(interfaces_list):
    """Using a list of interfaces, render the configs and, if they have
    changes, restart the services on the unit.
    """
    AodhCharm.singleton.render_with_interfaces(interfaces_list)


def assess_status():
    """Just call the AodhCharm.singleton.assess_status() command to update
    status on the unit.
    """
    AodhCharm.singleton.assess_status()


def configure_ha_resources(hacluster):
    """Use the singleton from the AodhCharm to run configure_ha_resources
    """
    AodhCharm.singleton.configure_ha_resources(hacluster)


def configure_ssl():
    """Use the singleton from the AodhCharm to run configure_ssl
    """
    AodhCharm.singleton.configure_ssl()
