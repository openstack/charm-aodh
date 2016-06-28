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

import charm.openstack.aodh as aodh


class Helper(unittest.TestCase):

    def setUp(self):
        self._patches = {}
        self._patches_start = {}

    def tearDown(self):
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch(self, obj, attr, return_value=None, **kwargs):
        mocked = mock.patch.object(obj, attr, **kwargs)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)


class TestOpenStackAodh(Helper):

    def test_install(self):
        self.patch(aodh.AodhCharm,
                   'set_config_defined_certs_and_keys')
        self.patch(aodh.AodhCharm.singleton, 'install')
        aodh.install()
        self.install.assert_called_once_with()

    def test_setup_endpoint(self):
        self.patch(aodh.AodhCharm,
                   'set_config_defined_certs_and_keys')
        self.patch(aodh.AodhCharm, 'service_name',
                   new_callable=mock.PropertyMock)
        self.patch(aodh.AodhCharm, 'region',
                   new_callable=mock.PropertyMock)
        self.patch(aodh.AodhCharm, 'public_url',
                   new_callable=mock.PropertyMock)
        self.patch(aodh.AodhCharm, 'internal_url',
                   new_callable=mock.PropertyMock)
        self.patch(aodh.AodhCharm, 'admin_url',
                   new_callable=mock.PropertyMock)
        self.service_name.return_value = 'type1'
        self.region.return_value = 'region1'
        self.public_url.return_value = 'public_url'
        self.internal_url.return_value = 'internal_url'
        self.admin_url.return_value = 'admin_url'
        keystone = mock.MagicMock()
        aodh.setup_endpoint(keystone)
        keystone.register_endpoints.assert_called_once_with(
            'type1', 'region1', 'public_url', 'internal_url', 'admin_url')

    def test_render_configs(self):
        self.patch(aodh.AodhCharm,
                   'set_config_defined_certs_and_keys')
        self.patch(aodh.AodhCharm.singleton, 'render_with_interfaces')
        aodh.render_configs('interfaces-list')
        self.render_with_interfaces.assert_called_once_with(
            'interfaces-list')


class TestAodhAdapters(Helper):

    @mock.patch('charmhelpers.core.hookenv.config')
    def test_aodh_adapters(self, config):
        reply = {
            'keystone-api-version': '2',
        }
        config.side_effect = lambda: reply
        self.patch(aodh.charms_openstack.adapters.APIConfigurationAdapter,
                   'get_network_addresses')
        amqp_relation = mock.MagicMock()
        amqp_relation.relation_name = 'amqp'
        shared_db_relation = mock.MagicMock()
        shared_db_relation.relation_name = 'shared_db'
        other_relation = mock.MagicMock()
        other_relation.relation_name = 'other'
        other_relation.thingy = 'help'
        # verify that the class is created with a AodhConfigurationAdapter
        b = aodh.AodhAdapters([amqp_relation,
                               shared_db_relation,
                               other_relation])
        # ensure that the relevant things got put on.
        self.assertTrue(
            isinstance(
                b.other,
                aodh.charms_openstack.adapters.OpenStackRelationAdapter))
        self.assertTrue(
            isinstance(
                b.options,
                aodh.charms_openstack.adapters.APIConfigurationAdapter))


class TestAodhCharm(Helper):

    def test__init__(self):
        self.patch(aodh.AodhCharm,
                   'set_config_defined_certs_and_keys')
        self.patch(aodh.ch_utils, 'os_release')
        aodh.AodhCharm()
        self.os_release.assert_called_once_with('python-keystonemiddleware')

    def test_install(self):
        self.patch(aodh.AodhCharm,
                   'set_config_defined_certs_and_keys')
        b = aodh.AodhCharm()
        self.patch(aodh.charms_openstack.charm.OpenStackCharm,
                   'configure_source')
        self.patch(aodh.charms_openstack.charm.OpenStackCharm,
                   'install')
        b.install()
        self.configure_source.assert_called_once_with()
        self.install.assert_called_once_with()
