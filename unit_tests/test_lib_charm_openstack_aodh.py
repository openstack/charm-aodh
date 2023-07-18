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

from unittest import mock

import charm.openstack.aodh as aodh

import charms_openstack.test_utils as test_utils


class Helper(test_utils.PatchHelper):

    def setUp(self):
        super().setUp()
        self.patch('charmhelpers.core.hookenv.is_subordinate',
                   return_value=False)
        self.patch_release(aodh.AodhCharm.release)


class TestOpenStackAodh(Helper):

    def test_install(self):
        self.patch_object(aodh.AodhCharm.singleton, 'install')
        aodh.install()
        self.install.assert_called_once_with()

    def test_setup_endpoint(self):
        self.patch_object(aodh.AodhCharm, 'service_name',
                          new_callable=mock.PropertyMock)
        self.patch_object(aodh.AodhCharm, 'region',
                          new_callable=mock.PropertyMock)
        self.patch_object(aodh.AodhCharm, 'public_url',
                          new_callable=mock.PropertyMock)
        self.patch_object(aodh.AodhCharm, 'internal_url',
                          new_callable=mock.PropertyMock)
        self.patch_object(aodh.AodhCharm, 'admin_url',
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
        self.patch_object(aodh.AodhCharm.singleton, 'render_with_interfaces')
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
        self.patch_object(
            aodh.charms_openstack.adapters.APIConfigurationAdapter,
            'get_network_addresses')
        cluster_relation = mock.MagicMock()
        cluster_relation.endpoint_name = 'cluster'
        amqp_relation = mock.MagicMock()
        amqp_relation.endpoint_name = 'amqp'
        shared_db_relation = mock.MagicMock()
        shared_db_relation.endpoint_name = 'shared_db'
        other_relation = mock.MagicMock()
        other_relation.endpoint_name = 'other'
        other_relation.thingy = 'help'
        # verify that the class is created with a AodhConfigurationAdapter
        b = aodh.AodhAdapters([amqp_relation,
                               cluster_relation,
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

    def test_install(self):
        b = aodh.AodhCharm()
        self.patch_object(aodh.charms_openstack.charm.OpenStackCharm,
                          'configure_source')
        self.patch_object(aodh.charms_openstack.charm.OpenStackCharm,
                          'install')
        b.install()
        self.configure_source.assert_called_once_with()
        self.install.assert_called_once_with()

    def test_reload_and_restart(self):
        self.patch('subprocess.check_call', name='check_call')
        self.patch_object(aodh.ch_host, 'service_restart')
        self.patch_object(aodh.ch_host, 'init_is_systemd', return_value=False)
        aodh.AodhCharm.reload_and_restart()
        self.init_is_systemd.assert_called_once_with()
        self.check_call.assert_not_called()
        self.service_restart.assert_not_called()
        # now say it is systemd.
        self.init_is_systemd.return_value = True
        aodh.AodhCharm.reload_and_restart()
        self.check_call.assert_called_once_with(['systemctl', 'daemon-reload'])
        self.service_restart.assert_called_once_with('aodh-api')

    def test_render_nrpe(self):
        """Test NRPE renders correctly pre Ocata."""
        self.patch_object(aodh.nrpe, 'NRPE')
        self.patch_object(aodh.nrpe, 'add_init_service_checks')
        services = ['aodh-api',
                    'aodh-evaluator',
                    'aodh-notifier',
                    'aodh-listener',
                    ]
        target = aodh.AodhCharmNewton()
        target.render_nrpe_checks()
        # Note that this list is valid for Ussuri
        self.add_init_service_checks.assert_has_calls([
            mock.call().add_init_service_checks(
                mock.ANY,
                services,
                mock.ANY
            ),
        ])
        self.NRPE.assert_has_calls([
            mock.call().write(),
        ])


class TestAodhCharmOcata(Helper):

    def test_reload_and_restart(self):
        self.patch('subprocess.check_call', name='check_call')
        self.patch_object(aodh.ch_host, 'init_is_systemd', return_value=False)
        aodh.AodhCharmOcata.reload_and_restart()
        self.init_is_systemd.assert_called_once_with()
        self.check_call.assert_not_called()
        # now say it is systemd.
        self.init_is_systemd.return_value = True
        aodh.AodhCharmOcata.reload_and_restart()
        self.check_call.assert_called_once_with(['systemctl', 'daemon-reload'])

    def test_render_nrpe(self):
        """Test NRPE renders correctly in Ocata."""
        self.patch_object(aodh.nrpe, 'NRPE')
        self.patch_object(aodh.nrpe, 'add_init_service_checks')
        services = ['aodh-evaluator', 'aodh-notifier',
                    'aodh-listener', 'apache2']
        target = aodh.AodhCharmOcata()
        target.render_nrpe_checks()
        # Note that this list is valid for Ussuri
        self.add_init_service_checks.assert_has_calls([
            mock.call().add_init_service_checks(
                mock.ANY,
                services,
                mock.ANY
            ),
        ])
        self.NRPE.assert_has_calls([
            mock.call().write(),
        ])
