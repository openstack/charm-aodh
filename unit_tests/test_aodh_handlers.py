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

import unittest

import charms_openstack.test_utils as test_utils
from unittest import mock

import reactive.aodh_handlers as handlers


class TestRegisteredHooks(test_utils.TestRegisteredHooks):
    """Run tests to ensure hooks are registered."""

    def test_registered_hooks(self):
        """Test that the correct hooks are registered."""
        defaults = [
            'charm.installed',
            'config.changed',
            'charm.default-select-release',
            'update-status',
            'upgrade-charm',
        ]
        hook_set = {
            'when': {
                'setup_amqp_req': ('amqp.connected', ),
                'setup_database': ('shared-db.connected', ),
                'setup_endpoint': ('identity-service.connected', ),
                'render_unclustered': ('charm.installed',
                                       'shared-db.available',
                                       'identity-service.available',
                                       'amqp.available',),
                'render_clustered': ('charm.installed',
                                     'shared-db.available',
                                     'identity-service.available',
                                     'amqp.available',
                                     'cluster.available',),
                'run_db_migration': ('charm.installed',
                                     'config.complete', ),
                'cluster_connected': ('ha.connected', ),
                'configure_nrpe': ('config.complete', ),
            },
            'when_not': {
                'install_packages': ('charm.installed', ),
                'render_unclustered': ('cluster.available', ),
                'run_db_migration': ('db.synced', ),
            },
            'when_none': {
                'configure_nrpe': ('charm.paused', 'is-update-status-hook', ),
            },
            'when_any': {
                'configure_nrpe': ('config.changed.nagios_context',
                                   'config.changed.nagios_servicegroups',
                                   'endpoint.nrpe-external-master.changed',
                                   'nrpe-external-master.available', ),
            },
        }
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestAodhHandlers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # force requires to rerun the mock_hook decorator:
        # try except is Python2/Python3 compatibility as Python3 has moved
        # reload to importlib.
        try:
            reload(handlers)
        except NameError:
            import importlib
            importlib.reload(handlers)

    @classmethod
    def tearDownClass(cls):
        # and fix any breakage we did to the module
        try:
            reload(handlers)
        except NameError:
            import importlib
            importlib.reload(handlers)

    def setUp(self):
        self._patches = {}
        self._patches_start = {}

    def tearDown(self):
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch(self, obj, attr, return_value=None, side_effect=None):
        mocked = mock.patch.object(obj, attr)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        started.side_effect = side_effect
        self._patches_start[attr] = started
        setattr(self, attr, started)

    def test_install_packages(self):
        self.patch(handlers.aodh, 'install')
        self.patch(handlers.reactive, 'set_state')
        handlers.install_packages()
        self.install.assert_called_once_with()
        self.set_state.assert_called_once_with('charm.installed')

    def test_setup_amqp_req(self):
        self.patch(handlers.aodh, 'assess_status')
        amqp = mock.MagicMock()
        handlers.setup_amqp_req(amqp)
        amqp.request_access.assert_called_once_with(
            username='aodh', vhost='openstack')

    def test_database(self):
        database = mock.MagicMock()
        self.patch(handlers.aodh, 'assess_status')
        handlers.setup_database(database)
        database.configure.assert_called_once_with('aodh', 'aodh')

    def test_setup_endpoint(self):
        self.patch(handlers.aodh, 'setup_endpoint')
        self.patch(handlers.aodh, 'assess_status')
        self.patch(handlers.aodh, 'configure_ssl')
        handlers.setup_endpoint('endpoint_object')
        self.setup_endpoint.assert_called_once_with('endpoint_object')

    def test_render(self):
        self.patch(handlers.aodh, 'render_configs')
        self.patch(handlers.aodh, 'assess_status')
        self.patch(handlers.aodh, 'configure_ssl')
        self.patch(handlers.aodh, 'upgrade_if_available')
        handlers.render_unclustered('arg1', 'arg2')
        self.render_configs.assert_called_once_with(('arg1', 'arg2', ))
        self.assess_status.assert_called_once()
        self.configure_ssl.assert_called_once()
        self.upgrade_if_available.assert_called_once_with(('arg1', 'arg2', ))
