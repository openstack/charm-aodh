import os

import charmhelpers.contrib.openstack.utils as ch_utils

import charms_openstack.charm
import charms_openstack.adapters
import charms_openstack.ip as os_ip

AODH_DIR = '/etc/aodh'
AODH_CONF = os.path.join(AODH_DIR, 'aodh.conf')


class AodhCharm(charms_openstack.charm.OpenStackCharm):

    service_name = 'aodh'
    release = 'mitaka'

    # Packages the service needs installed
    packages = ['aodh-api', 'aodh-evaluator',
                'aodh-expirer', 'aodh-notifier',
                'aodh-listener']

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

    # Aodh requires a message queue, database and keystone to work,
    # so these are the 'required' relationships for the service to
    # have an 'active' workload status.  'required_relations' is used in
    # the assess_status() functionality to determine what the current
    # workload status of the charm is.
    required_relations = ['amqp', 'shared-db', 'identity-service']

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
