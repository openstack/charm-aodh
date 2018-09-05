import amulet
import subprocess
import json
import time

import aodhclient.client as aodh_client

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG,
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(DEBUG)


class AodhBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic aodh deployment."""

    no_origin = ['memcached', 'percona-cluster', 'rabbitmq-server',
                 'ceph-mon', 'ceph-osd']

    def __init__(self, series, openstack=None, source=None, stable=True):
        """Deploy the entire test environment."""
        super(AodhBasicDeployment, self).__init__(series, openstack,
                                                  source, stable)
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()

        u.log.info('Waiting on extended status checks...')
        exclude_services = ['mongodb', 'memcached']
        self._auto_wait_for_status(exclude_services=exclude_services)

        self.d.sentry.wait()
        self._initialize_tests()

    def _add_services(self):
        """Add services

           Add the services that we're testing, where aodh is local,
           and the rest of the service are from lp branches that are
           compatible with the local charm (e.g. stable or next).
           """
        this_service = {'name': 'aodh'}
        other_services = [
            {'name': 'percona-cluster'},
            {'name': 'rabbitmq-server'},
            {'name': 'keystone'},
            {'name': 'ceilometer'}
        ]
        if self._get_openstack_release() >= self.xenial_queens:
            other_services.extend([
                {'name': 'gnocchi'},
                {'name': 'memcached', 'location': 'cs:memcached'},
                {'name': 'ceph-mon', 'units': 3},
                {'name': 'ceph-osd', 'units': 3,
                 'storage': {'osd-devices': 'cinder,10G'}}])
        else:
            other_services.append({
                'name': 'mongodb',
                'location': 'cs:~1chb1n/{}/mongodb'.format(self.series)})
        super(AodhBasicDeployment, self)._add_services(
            this_service,
            other_services,
            no_origin=self.no_origin)

    def _add_relations(self):
        """Add all of the relations for the services."""
        relations = {
            'aodh:shared-db': 'percona-cluster:shared-db',
            'aodh:amqp': 'rabbitmq-server:amqp',
            'aodh:identity-service': 'keystone:identity-service',
            'keystone:shared-db': 'percona-cluster:shared-db',
            'ceilometer:amqp': 'rabbitmq-server:amqp',
        }
        if self._get_openstack_release() >= self.xenial_queens:
            additional_relations = {
                'ceilometer:identity-credentials': 'keystone:'
                                                   'identity-credentials',
                'ceilometer:identity-notifications': 'keystone:'
                                                     'identity-notifications',
                'ceilometer:metric-service': 'gnocchi:metric-service',
                'ceph-mon:osd': 'ceph-osd:mon',
                'gnocchi:identity-service': 'keystone:identity-service',
                'gnocchi:shared-db': 'percona-cluster:shared-db',
                'gnocchi:storage-ceph': 'ceph-mon:client',
                'gnocchi:coordinator-memcached': 'memcached:cache',
            }
        else:
            additional_relations = {
                'ceilometer:shared-db': 'mongodb:database',
                'ceilometer:identity-service': 'keystone:identity-service'}
        relations.update(additional_relations)
        super(AodhBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        keystone_config = {
            'admin-password': 'openstack',
            'admin-token': 'ubuntutesting'
        }
        pxc_config = {
            'max-connections': 1000,
        }
        configs = {
            'keystone': keystone_config,
            'percona-cluster': pxc_config,
        }
        super(AodhBasicDeployment, self)._configure_services(configs)

    def _get_token(self):
        return self.keystone.service_catalog.catalog['token']['id']

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.aodh_sentry = self.d.sentry['aodh'][0]
        self.pxc_sentry = self.d.sentry['percona-cluster'][0]
        self.keystone_sentry = self.d.sentry['keystone'][0]
        self.rabbitmq_sentry = self.d.sentry['rabbitmq-server'][0]
        self.ceil_sentry = self.d.sentry['ceilometer'][0]
        u.log.debug('openstack release val: {}'.format(
            self._get_openstack_release()))
        u.log.debug('openstack release str: {}'.format(
            self._get_openstack_release_string()))

        # Authenticate admin with keystone endpoint
        self.keystone_session, self.keystone = u.get_default_keystone_session(
            self.keystone_sentry,
            openstack_release=self._get_openstack_release())

        # Authenticate admin with aodh endpoint
        aodh_ep = self.keystone.service_catalog.url_for(
            service_type='alarming',
            interface='publicURL')

        self.aodh = aodh_client.Client(
            version=2,
            session=self.keystone_session,
            endpoint_override=aodh_ep)

    def _run_action(self, unit_id, action, *args):
        command = ["juju", "action", "do", "--format=json", unit_id, action]
        command.extend(args)
        print("Running command: %s\n" % " ".join(command))
        output = subprocess.check_output(command)
        output_json = output.decode(encoding="UTF-8")
        data = json.loads(output_json)
        action_id = data[u'Action queued with id']
        return action_id

    def _wait_on_action(self, action_id):
        command = ["juju", "action", "fetch", "--format=json", action_id]
        while True:
            try:
                output = subprocess.check_output(command)
            except Exception as e:
                print(e)
                return False
            output_json = output.decode(encoding="UTF-8")
            data = json.loads(output_json)
            if data[u"status"] == "completed":
                return True
            elif data[u"status"] == "failed":
                return False
            time.sleep(2)

    def test_100_services(self):
        """Verify the expected services are running on the corresponding
           service units."""
        u.log.debug('Checking system services on units...')

        aodh_svcs = ['aodh-evaluator', 'aodh-notifier', 'aodh-listener']
        if self._get_openstack_release() >= self.xenial_ocata:
            aodh_svcs.append('apache2')
        else:
            aodh_svcs.append('aodh-api')
        if self._get_openstack_release() < self.trusty_mitaka:
            aodh_svcs.append('aodh-alarm-evaluator')
            aodh_svcs.append('aodh-alarm-notifier')

        service_names = {
            self.aodh_sentry: aodh_svcs,
        }

        ret = u.validate_services_by_name(service_names)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

        u.log.debug('OK')

    def test_110_service_catalog(self):
        """Verify that the service catalog endpoint data is valid."""
        u.log.debug('Checking keystone service catalog data...')
        endpoint_check = {
            'adminURL': u.valid_url,
            'id': u.not_null,
            'region': 'RegionOne',
            'publicURL': u.valid_url,
            'internalURL': u.valid_url
        }
        expected = {
            'alarming': [endpoint_check],
        }
        actual = self.keystone.service_catalog.get_endpoints()

        ret = u.validate_svc_catalog_endpoint_data(
            expected,
            actual,
            openstack_release=self._get_openstack_release())
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

        u.log.debug('OK')

    def test_114_aodh_api_endpoint(self):
        """Verify the aodh api endpoint data."""
        u.log.debug('Checking aodh api endpoint data...')
        endpoints = self.keystone.endpoints.list()
        u.log.debug(endpoints)
        admin_port = internal_port = public_port = '8042'
        expected = {'id': u.not_null,
                    'region': 'RegionOne',
                    'adminurl': u.valid_url,
                    'internalurl': u.valid_url,
                    'publicurl': u.valid_url,
                    'service_id': u.not_null}

        ret = u.validate_endpoint_data(
            endpoints,
            admin_port,
            internal_port,
            public_port,
            expected,
            openstack_release=self._get_openstack_release())
        if ret:
            message = 'Aodh endpoint: {}'.format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_200_aodh_identity_relation(self):
        """Verify the aodh to keystone identity-service relation data"""
        u.log.debug('Checking aodh to keystone identity-service '
                    'relation data...')
        unit = self.aodh_sentry
        relation = ['identity-service', 'keystone:identity-service']
        aodh_ip = unit.relation('identity-service',
                                'keystone:identity-service')['private-address']
        aodh_endpoint = "http://%s:8042" % (aodh_ip)

        expected = {
            'admin_url': aodh_endpoint,
            'internal_url': aodh_endpoint,
            'private-address': aodh_ip,
            'public_url': aodh_endpoint,
            'region': 'RegionOne',
            'service': 'aodh',
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('aodh identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_201_keystone_aodh_identity_relation(self):
        """Verify the keystone to aodh identity-service relation data"""
        u.log.debug('Checking keystone:aodh identity relation data...')
        unit = self.keystone_sentry
        relation = ['identity-service', 'aodh:identity-service']
        id_relation = unit.relation('identity-service',
                                    'aodh:identity-service')
        id_ip = id_relation['private-address']
        expected = {
            'admin_token': 'ubuntutesting',
            'auth_host': id_ip,
            'auth_port': "35357",
            'auth_protocol': 'http',
            'private-address': id_ip,
            'service_host': id_ip,
            'service_password': u.not_null,
            'service_port': "5000",
            'service_protocol': 'http',
            'service_tenant': 'services',
            'service_tenant_id': u.not_null,
            'service_username': 'aodh',
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('keystone identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_203_aodh_amqp_relation(self):
        """Verify the aodh to rabbitmq-server amqp relation data"""
        u.log.debug('Checking aodh:rabbitmq amqp relation data...')
        unit = self.aodh_sentry
        relation = ['amqp', 'rabbitmq-server:amqp']
        expected = {
            'username': 'aodh',
            'private-address': u.valid_ip,
            'vhost': 'openstack'
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('aodh amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

    def test_204_amqp_aodh_relation(self):
        """Verify the rabbitmq-server to aodh amqp relation data"""
        u.log.debug('Checking rabbitmq:aodh amqp relation data...')
        unit = self.rabbitmq_sentry
        relation = ['amqp', 'aodh:amqp']
        expected = {
            'hostname': u.valid_ip,
            'private-address': u.valid_ip,
            'password': u.not_null,
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('rabbitmq amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

        u.log.debug('OK')

        u.log.debug('OK')

    def test_400_api_connection(self):
        """Simple api calls to check service is up and responding"""
        u.log.debug('Checking api functionality...')
        assert(self.aodh.capabilities.list() != [])
        u.log.debug('OK')

    def test_900_restart_on_config_change(self):
        """Verify that the specified services are restarted when the config
           is changed.
           """
        sentry = self.aodh_sentry
        juju_service = 'aodh'

        # Expected default and alternate values
        set_default = {'debug': 'False'}
        set_alternate = {'debug': 'True'}

        # Services which are expected to restart upon config change,
        # and corresponding config files affected by the change
        conf_file = '/etc/aodh/aodh.conf'
        if self._get_openstack_release() >= self.xenial_ocata:
            services = {
                'apache2': conf_file,
                'aodh-evaluator: AlarmEvaluationService worker(0)': conf_file,
                'aodh-notifier: AlarmNotifierService worker(0)': conf_file,
                'aodh-listener: EventAlarmEvaluationService'
                ' worker(0)': conf_file,
            }
        elif self._get_openstack_release() >= self.xenial_newton:
            services = {
                ('/usr/bin/python /usr/bin/aodh-api --port 8032 -- '
                 '--config-file=/etc/aodh/aodh.conf '
                 '--log-file=/var/log/aodh/aodh-api.log'): conf_file,
                'aodh-evaluator - AlarmEvaluationService(0)': conf_file,
                'aodh-notifier - AlarmNotifierService(0)': conf_file,
                'aodh-listener - EventAlarmEvaluationService(0)': conf_file,
            }
        else:
            services = {
                'aodh-api': conf_file,
                'aodh-evaluator': conf_file,
                'aodh-notifier': conf_file,
                'aodh-listener': conf_file,
            }

        # Make config change, check for service restarts
        u.log.debug('Making config change on {}...'.format(juju_service))
        mtime = u.get_sentry_time(sentry)
        self.d.configure(juju_service, set_alternate)

        sleep_time = 40
        for s, conf_file in services.iteritems():
            u.log.debug("Checking that service restarted: {}".format(s))
            if not u.validate_service_config_changed(sentry, mtime, s,
                                                     conf_file,
                                                     retry_count=4,
                                                     retry_sleep_time=20,
                                                     sleep_time=sleep_time):
                self.d.configure(juju_service, set_default)
                msg = "service {} didn't restart after config change".format(s)
                amulet.raise_status(amulet.FAIL, msg=msg)
            sleep_time = 0

        self.d.configure(juju_service, set_default)
        u.log.debug('OK')

    def _test_910_pause_and_resume(self):
        """The services can be paused and resumed. """
        u.log.debug('Checking pause and resume actions...')
        unit_name = "aodh/0"
        unit = self.d.sentry['aodh'][0]
        juju_service = 'aodh'

        assert u.status_get(unit)[0] == "active"

        action_id = self._run_action(unit_name, "pause")
        assert self._wait_on_action(action_id), "Pause action failed."
        assert u.status_get(unit)[0] == "maintenance"

        # trigger config-changed to ensure that services are still stopped
        u.log.debug("Making config change on aodh ...")
        self.d.configure(juju_service, {'debug': 'True'})
        assert u.status_get(unit)[0] == "maintenance"
        self.d.configure(juju_service, {'debug': 'False'})
        assert u.status_get(unit)[0] == "maintenance"

        action_id = self._run_action(unit_name, "resume")
        assert self._wait_on_action(action_id), "Resume action failed."
        assert u.status_get(unit)[0] == "active"
        u.log.debug('OK')
