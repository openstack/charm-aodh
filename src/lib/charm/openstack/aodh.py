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

import collections
import os
import subprocess

import charmhelpers.core.host as ch_host

import charms_openstack.charm
import charms_openstack.adapters
import charms_openstack.ip as os_ip

AODH_DIR = '/etc/aodh'
AODH_CONF = os.path.join(AODH_DIR, 'aodh.conf')
AODH_API_SYSTEMD_CONF = (
    '/etc/systemd/system/aodh-api.service.d/override.conf'
)
AODH_WSGI_CONF = '/etc/apache2/sites-available/aodh-api.conf'


charms_openstack.charm.use_defaults(
    'charm.default-select-release',
    'upgrade-charm'
)


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
        AODH_API_SYSTEMD_CONF: ['aodh-api'],
    }

    # Resource when in HA mode
    ha_resources = ['vips', 'haproxy', 'dnsha']

    # Aodh requires a message queue, database and keystone to work,
    # so these are the 'required' relationships for the service to
    # have an 'active' workload status.  'required_relations' is used in
    # the assess_status() functionality to determine what the current
    # workload status of the charm is.
    required_relations = ['amqp', 'shared-db', 'identity-service']

    # Set the adapters class to on specific to Aodh
    # NOTE: review this seems odd as not doing anything off piste here
    adapters_class = AodhAdapters

    release_pkg = 'aodh-common'
    package_codenames = {
        'aodh-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'newton'),
            ('4', 'ocata'),
            ('5', 'pike'),
            ('6', 'queens'),
            ('7', 'rocky'),
            ('8', 'stein'),
            ('9', 'train'),
            ('10', 'ussuri'),
        ]),
    }

    group = 'aodh'

    @staticmethod
    def reload_and_restart():
        if ch_host.init_is_systemd():
            subprocess.check_call(['systemctl', 'daemon-reload'])
            ch_host.service_restart('aodh-api')


class AodhCharmNewton(AodhCharm):
    """Newton uses the aodh-api standalone systemd. If the systemd definition
       changes the a systemctl daemon-reload is needed.
    """
    release = 'newton'

    def render_with_interfaces(self, interface_list):
        if os.path.exists(AODH_API_SYSTEMD_CONF):
            old_hash = ch_host.file_hash(AODH_API_SYSTEMD_CONF)
        else:
            old_hash = ''
        super(AodhCharmNewton, self).render_with_interfaces(interface_list)
        new_hash = ch_host.file_hash(AODH_API_SYSTEMD_CONF)
        if old_hash != new_hash:
            self.reload_and_restart()


class AodhCharmOcata(AodhCharm):
    """From ocata onwards there is no aodh-api service, as this is handled via
    apache2 with a wsgi handler.  Therefore, these specialisations are simple
    to switch out the aodh-api.
    """

    # This charms support Ocata and onward
    release = 'ocata'

    # Init services the charm manages
    # Ocata onwards uses apache2 rather than aodh-api
    services = ['aodh-evaluator', 'aodh-notifier',
                'aodh-listener', 'apache2']

    # The restart map defines which services should be restarted when a given
    # file changes
    # Ocata onwards doesn't require aodh-api and the AODH_API_SYSTEMD_CONF
    # file.
    restart_map = {
        AODH_CONF: services,
        AODH_WSGI_CONF: services,
    }

    @staticmethod
    def reload_and_restart():
        if ch_host.init_is_systemd():
            subprocess.check_call(['systemctl', 'daemon-reload'])
        # no need to restart aodh-api in ocata and onwards


class AodhCharmRocky(AodhCharmOcata):

    release = 'rocky'

    # Switch to Python 3 for Rocky onwards
    packages = [
        'aodh-api',
        'aodh-evaluator',
        'aodh-expirer',
        'aodh-notifier',
        'aodh-listener',
        'python3-aodh',
        'libapache2-mod-wsgi-py3',
        'python-apt',  # NOTE: workaround for hacluster suboridinate
    ]

    purge_packages = [
        'python-aodh',
        'python-memcache',
    ]

    python_version = 3


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


def upgrade_if_available(interfaces_list):
    """Just call the AodhCharm.singleton.upgrade_if_available() command to
    update OpenStack package if upgrade is available

    @returns: None
    """
    AodhCharm.singleton.upgrade_if_available(interfaces_list)


def reload_and_restart():
    """Reload systemd and restart aodh API when override file changes
    """
    AodhCharm.singleton.reload_and_restart()
