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

import charms.reactive as reactive

import charms_openstack.charm as charm

# This charm's library contains all of the handler code associated with
# aodh
import charm.openstack.aodh as aodh

charm.use_defaults(
    'certificates.available',
    'cluster.available',
)


# Minimal inferfaces required for operation
MINIMAL_INTERFACES = [
    'shared-db.available',
    'identity-service.available',
    'amqp.available',
]


# use a synthetic state to ensure that it get it to be installed independent of
# the install hook.
@reactive.when_not('charm.installed')
def install_packages():
    aodh.install()
    reactive.set_state('charm.installed')


@reactive.when('amqp.connected')
def setup_amqp_req(amqp):
    """Use the amqp interface to request access to the amqp broker using our
    local configuration.
    """
    amqp.request_access(username='aodh',
                        vhost='openstack')
    aodh.assess_status()


@reactive.when('shared-db.connected')
def setup_database(database):
    """On receiving database credentials, configure the database on the
    interface.
    """
    database.configure('aodh', 'aodh')
    aodh.assess_status()


@reactive.when('identity-service.connected')
def setup_endpoint(keystone):
    aodh.setup_endpoint(keystone)
    aodh.configure_ssl()
    aodh.assess_status()


def render(*args):
    aodh.render_configs(args)
    reactive.set_state('config.complete')
    aodh.assess_status()


@reactive.when('charm.installed')
@reactive.when_not('cluster.available')
@reactive.when(*MINIMAL_INTERFACES)
def render_unclustered(*args):
    aodh.upgrade_if_available(args)
    aodh.configure_ssl()
    render(*args)


@reactive.when('charm.installed')
@reactive.when('cluster.available',
               *MINIMAL_INTERFACES)
def render_clustered(*args):
    aodh.upgrade_if_available(args)
    render(*args)


@reactive.when('charm.installed')
@reactive.when('config.complete')
@reactive.when_not('db.synced')
def run_db_migration():
    aodh.db_sync()
    aodh.restart_all()
    reactive.set_state('db.synced')
    aodh.assess_status()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    aodh.configure_ha_resources(hacluster)


@reactive.when_none('charm.paused', 'is-update-status-hook')
@reactive.when('config.complete')
@reactive.when_any('config.changed.nagios_context',
                   'config.changed.nagios_servicegroups',
                   'endpoint.nrpe-external-master.changed',
                   'nrpe-external-master.available')
def configure_nrpe():
    """Handle config-changed for NRPE options."""
    aodh.render_nrpe()
