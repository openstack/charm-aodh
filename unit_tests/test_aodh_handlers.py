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

from __future__ import absolute_import
from __future__ import print_function

import unittest

import mock

import reactive.aodh_handlers as handlers


_when_args = {}
_when_not_args = {}


def mock_hook_factory(d):

    def mock_hook(*args, **kwargs):

        def inner(f):
            # remember what we were passed.  Note that we can't actually
            # determine the class we're attached to, as the decorator only gets
            # the function.
            try:
                d[f.__name__].append(dict(args=args, kwargs=kwargs))
            except KeyError:
                d[f.__name__] = [dict(args=args, kwargs=kwargs)]
            return f
        return inner
    return mock_hook


class TestAodhHandlers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._patched_when = mock.patch('charms.reactive.when',
                                       mock_hook_factory(_when_args))
        cls._patched_when_started = cls._patched_when.start()
        cls._patched_when_not = mock.patch('charms.reactive.when_not',
                                           mock_hook_factory(_when_not_args))
        cls._patched_when_not_started = cls._patched_when_not.start()
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
        cls._patched_when.stop()
        cls._patched_when_started = None
        cls._patched_when = None
        cls._patched_when_not.stop()
        cls._patched_when_not_started = None
        cls._patched_when_not = None
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

    def patch(self, obj, attr, return_value=None):
        mocked = mock.patch.object(obj, attr)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)

    def test_registered_hooks(self):
        # test that the hooks actually registered the relation expressions that
        # are meaningful for this interface: this is to handle regressions.
        # The keys are the function names that the hook attaches to.
        when_patterns = {
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
        }
        when_not_patterns = {
            'install_packages': ('charm.installed', ),
            'render_unclustered': ('cluster.available', ),
            'run_db_migration': ('db.synced', ),
        }
        # check the when hooks are attached to the expected functions
        for t, p in [(_when_args, when_patterns),
                     (_when_not_args, when_not_patterns)]:
            for f, args in t.items():
                # check that function is in patterns
                self.assertTrue(f in p.keys(),
                                "{} not found".format(f))
                # check that the lists are equal
                l = []
                for a in args:
                    l += a['args'][:]
                self.assertEqual(sorted(l), sorted(p[f]),
                                 "{}: incorrect state registration".format(f))

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
        self.patch(handlers.hookenv, 'unit_private_ip', 'private_ip')
        self.patch(handlers.aodh, 'assess_status')
        handlers.setup_database(database)
        database.configure.assert_called_once_with(
            'aodh', 'aodh', 'private_ip')

    def test_setup_endpoint(self):
        self.patch(handlers.aodh, 'setup_endpoint')
        self.patch(handlers.aodh, 'assess_status')
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
