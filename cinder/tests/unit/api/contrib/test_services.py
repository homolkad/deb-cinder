# Copyright 2012 IBM Corp.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import datetime

import ddt
from iso8601 import iso8601
import mock
from six.moves import http_client
import webob.exc

from cinder.api.contrib import services
from cinder.api import extensions
from cinder.api.openstack import api_version_request as api_version
from cinder import context
from cinder import exception
from cinder import test
from cinder.tests.unit.api import fakes
from cinder.tests.unit import fake_constants as fake


fake_services_list = [
    {'binary': 'cinder-scheduler',
     'host': 'host1',
     'cluster_name': None,
     'availability_zone': 'cinder',
     'id': 1,
     'disabled': True,
     'updated_at': datetime.datetime(2012, 10, 29, 13, 42, 2),
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 27),
     'disabled_reason': 'test1',
     'modified_at': ''},
    {'binary': 'cinder-volume',
     'host': 'host1',
     'cluster_name': None,
     'availability_zone': 'cinder',
     'id': 2,
     'disabled': True,
     'updated_at': datetime.datetime(2012, 10, 29, 13, 42, 5),
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 27),
     'disabled_reason': 'test2',
     'modified_at': ''},
    {'binary': 'cinder-scheduler',
     'host': 'host2',
     'cluster_name': 'cluster1',
     'availability_zone': 'cinder',
     'id': 3,
     'disabled': False,
     'updated_at': datetime.datetime(2012, 9, 19, 6, 55, 34),
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 28),
     'disabled_reason': '',
     'modified_at': ''},
    {'binary': 'cinder-volume',
     'host': 'host2',
     'cluster_name': 'cluster1',
     'availability_zone': 'cinder',
     'id': 4,
     'disabled': True,
     'updated_at': datetime.datetime(2012, 9, 18, 8, 3, 38),
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 28),
     'disabled_reason': 'test4',
     'modified_at': ''},
    {'binary': 'cinder-volume',
     'host': 'host2',
     'cluster_name': 'cluster2',
     'availability_zone': 'cinder',
     'id': 5,
     'disabled': True,
     'updated_at': datetime.datetime(2012, 9, 18, 8, 3, 38),
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 28),
     'disabled_reason': 'test5',
     'modified_at': datetime.datetime(2012, 10, 29, 13, 42, 5)},
    {'binary': 'cinder-volume',
     'host': 'host2',
     'cluster_name': 'cluster2',
     'availability_zone': 'cinder',
     'id': 6,
     'disabled': False,
     'updated_at': datetime.datetime(2012, 9, 18, 8, 3, 38),
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 28),
     'disabled_reason': '',
     'modified_at': datetime.datetime(2012, 9, 18, 8, 1, 38)},
    {'binary': 'cinder-scheduler',
     'host': 'host2',
     'cluster_name': None,
     'availability_zone': 'cinder',
     'id': 7,
     'disabled': False,
     'updated_at': None,
     'created_at': datetime.datetime(2012, 9, 18, 2, 46, 28),
     'disabled_reason': '',
     'modified_at': None},
]


class FakeRequest(object):
    environ = {"cinder.context": context.get_admin_context()}

    def __init__(self, version='3.0', **kwargs):
        self.GET = kwargs
        self.headers = {'OpenStack-API-Version': 'volume ' + version}
        self.api_version_request = api_version.APIVersionRequest(version)


# NOTE(uni): deprecating service request key, binary takes precedence
# Still keeping service key here for API compatibility sake.
class FakeRequestWithService(FakeRequest):
    def __init__(self, **kwargs):
        kwargs.setdefault('service', 'cinder-volume')
        super(FakeRequestWithService, self).__init__(**kwargs)


class FakeRequestWithBinary(FakeRequest):
    def __init__(self, **kwargs):
        kwargs.setdefault('binary', 'cinder-volume')
        super(FakeRequestWithBinary, self).__init__(**kwargs)


class FakeRequestWithHost(FakeRequest):
    def __init__(self, **kwargs):
        kwargs.setdefault('host', 'host1')
        super(FakeRequestWithHost, self).__init__(**kwargs)


# NOTE(uni): deprecating service request key, binary takes precedence
# Still keeping service key here for API compatibility sake.
class FakeRequestWithHostService(FakeRequestWithService):
    def __init__(self, **kwargs):
        kwargs.setdefault('host', 'host1')
        super(FakeRequestWithHostService, self).__init__(**kwargs)


class FakeRequestWithHostBinary(FakeRequestWithBinary):
    def __init__(self, **kwargs):
        kwargs.setdefault('host', 'host1')
        super(FakeRequestWithHostBinary, self).__init__(**kwargs)


def fake_service_get_all(context, **filters):
    result = []
    host = filters.pop('host', None)
    for service in fake_services_list:
        if (host and service['host'] != host and
                not service['host'].startswith(host + '@')):
            continue

        if all(v is None or service.get(k) == v for k, v in filters.items()):
            result.append(service)
    return result


def fake_service_get(context, service_id=None, **filters):
    result = fake_service_get_all(context, id=service_id, **filters)
    if not result:
        raise exception.ServiceNotFound(service_id=service_id)
    return result[0]


def fake_service_get_by_id(value):
    for service in fake_services_list:
        if service['id'] == value:
            return service
    return None


def fake_service_update(context, service_id, values):
    service = fake_service_get_by_id(service_id)
    if service is None:
        raise exception.ServiceNotFound(service_id=service_id)
    else:
        {'host': 'host1', 'service': 'cinder-volume',
         'disabled': values['disabled']}


def fake_policy_enforce(context, action, target):
    pass


def fake_utcnow(with_timezone=False):
    tzinfo = iso8601.Utc() if with_timezone else None
    return datetime.datetime(2012, 10, 29, 13, 42, 11, tzinfo=tzinfo)


@ddt.ddt
@mock.patch('cinder.db.service_get_all', fake_service_get_all)
@mock.patch('cinder.db.service_get', fake_service_get)
@mock.patch('oslo_utils.timeutils.utcnow', fake_utcnow)
@mock.patch('cinder.db.sqlalchemy.api.service_update', fake_service_update)
@mock.patch('cinder.policy.enforce', fake_policy_enforce)
class ServicesTest(test.TestCase):

    def setUp(self):
        super(ServicesTest, self).setUp()

        self.context = context.get_admin_context()
        self.ext_mgr = extensions.ExtensionManager()
        self.ext_mgr.extensions = {}
        self.controller = services.ServiceController(self.ext_mgr)

    def test_services_list(self):
        req = FakeRequest()
        res_dict = self.controller.index(req)

        response = {'services': [{'binary': 'cinder-scheduler',
                                  'host': 'host1', 'zone': 'cinder',
                                  'status': 'disabled', 'state': 'up',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 2)},
                                 {'binary': 'cinder-volume',
                                  'host': 'host1', 'zone': 'cinder',
                                  'status': 'disabled', 'state': 'up',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 5)},
                                 {'binary': 'cinder-scheduler',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 19, 6, 55, 34)},
                                 {'binary': 'cinder-volume',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'disabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 18, 8, 3, 38)},
                                 {'binary': 'cinder-volume',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'disabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 5)},
                                 {'binary': 'cinder-volume',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 18, 8, 3, 38)},
                                 {'binary': 'cinder-scheduler',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': None},
                                 ]}
        self.assertEqual(response, res_dict)

    def test_failover_old_version(self):
        req = FakeRequest(version='3.18')
        self.assertRaises(exception.InvalidInput, self.controller.update, req,
                          'failover', {'cluster': 'cluster1'})

    def test_failover_no_values(self):
        req = FakeRequest(version='3.26')
        self.assertRaises(exception.InvalidInput, self.controller.update, req,
                          'failover', {'backend_id': 'replica1'})

    @ddt.data({'host': 'hostname'}, {'cluster': 'mycluster'})
    @mock.patch('cinder.volume.api.API.failover')
    def test_failover(self, body, failover_mock):
        req = FakeRequest(version='3.26')
        body['backend_id'] = 'replica1'
        res = self.controller.update(req, 'failover', body)
        self.assertEqual(202, res.status_code)
        failover_mock.assert_called_once_with(req.environ['cinder.context'],
                                              body.get('host'),
                                              body.get('cluster'), 'replica1')

    @ddt.data({}, {'host': 'hostname', 'cluster': 'mycluster'})
    @mock.patch('cinder.volume.api.API.failover')
    def test_failover_invalid_input(self, body, failover_mock):
        req = FakeRequest(version='3.26')
        body['backend_id'] = 'replica1'
        self.assertRaises(exception.InvalidInput,
                          self.controller.update, req, 'failover', body)
        failover_mock.assert_not_called()

    def test_services_list_with_cluster_name(self):
        req = FakeRequest(version='3.7')
        res_dict = self.controller.index(req)

        response = {'services': [{'binary': 'cinder-scheduler',
                                  'cluster': None,
                                  'host': 'host1', 'zone': 'cinder',
                                  'status': 'disabled', 'state': 'up',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 2)},
                                 {'binary': 'cinder-volume',
                                  'cluster': None,
                                  'host': 'host1', 'zone': 'cinder',
                                  'status': 'disabled', 'state': 'up',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 5)},
                                 {'binary': 'cinder-scheduler',
                                  'cluster': 'cluster1',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 19, 6, 55, 34)},
                                 {'binary': 'cinder-volume',
                                  'cluster': 'cluster1',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'disabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 18, 8, 3, 38)},
                                 {'binary': 'cinder-volume',
                                  'cluster': 'cluster2',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'disabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 5)},
                                 {'binary': 'cinder-volume',
                                  'cluster': 'cluster2',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 18, 8, 3, 38)},
                                 {'binary': 'cinder-scheduler',
                                  'cluster': None,
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': None},
                                 ]}
        self.assertEqual(response, res_dict)

    def test_services_detail(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = FakeRequest()
        res_dict = self.controller.index(req)

        response = {'services': [{'binary': 'cinder-scheduler',
                                  'host': 'host1', 'zone': 'cinder',
                                  'status': 'disabled', 'state': 'up',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 2),
                                  'disabled_reason': 'test1'},
                                 {'binary': 'cinder-volume',
                                  'replication_status': None,
                                  'active_backend_id': None,
                                  'frozen': False,
                                  'host': 'host1', 'zone': 'cinder',
                                  'status': 'disabled', 'state': 'up',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 5),
                                  'disabled_reason': 'test2'},
                                 {'binary': 'cinder-scheduler',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 19, 6, 55, 34),
                                  'disabled_reason': ''},
                                 {'binary': 'cinder-volume',
                                  'replication_status': None,
                                  'active_backend_id': None,
                                  'frozen': False,
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'disabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 18, 8, 3, 38),
                                  'disabled_reason': 'test4'},
                                 {'binary': 'cinder-volume',
                                  'replication_status': None,
                                  'active_backend_id': None,
                                  'frozen': False,
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'disabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 10, 29, 13, 42, 5),
                                  'disabled_reason': 'test5'},
                                 {'binary': 'cinder-volume',
                                  'replication_status': None,
                                  'active_backend_id': None,
                                  'frozen': False,
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': datetime.datetime(
                                      2012, 9, 18, 8, 3, 38),
                                  'disabled_reason': ''},
                                 {'binary': 'cinder-scheduler',
                                  'host': 'host2',
                                  'zone': 'cinder',
                                  'status': 'enabled', 'state': 'down',
                                  'updated_at': None,
                                  'disabled_reason': ''},
                                 ]}
        self.assertEqual(response, res_dict)

    def test_services_list_with_host(self):
        req = FakeRequestWithHost()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-scheduler',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled', 'state': 'up',
             'updated_at': datetime.datetime(2012, 10,
                                             29, 13, 42, 2)},
            {'binary': 'cinder-volume',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled', 'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)}]}
        self.assertEqual(response, res_dict)

    def test_services_detail_with_host(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = FakeRequestWithHost()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-scheduler',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled', 'state': 'up',
             'updated_at': datetime.datetime(2012, 10,
                                             29, 13, 42, 2),
             'disabled_reason': 'test1'},
            {'binary': 'cinder-volume',
             'frozen': False,
             'replication_status': None,
             'active_backend_id': None,
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled', 'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test2'}]}
        self.assertEqual(response, res_dict)

    def test_services_list_with_service(self):
        req = FakeRequestWithService()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)},
            {'binary': 'cinder-volume',
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38)},
            {'binary': 'cinder-volume',
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)},
            {'binary': 'cinder-volume',
             'host': 'host2',
             'zone': 'cinder',
             'status': 'enabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38)}]}
        self.assertEqual(response, res_dict)

    def test_services_detail_with_service(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = FakeRequestWithService()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'frozen': False,
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test2'},
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'frozen': False,
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38),
             'disabled_reason': 'test4'},
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'frozen': False,
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test5'},
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'frozen': False,
             'host': 'host2',
             'zone': 'cinder',
             'status': 'enabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38),
             'disabled_reason': ''}]}
        self.assertEqual(response, res_dict)

    def test_services_list_with_binary(self):
        req = FakeRequestWithBinary()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)},
            {'binary': 'cinder-volume',
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38)},
            {'binary': 'cinder-volume',
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)},
            {'binary': 'cinder-volume',
             'host': 'host2',
             'zone': 'cinder',
             'status': 'enabled',
             'state': 'down',
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38)}]}
        self.assertEqual(response, res_dict)

    def test_services_detail_with_binary(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = FakeRequestWithBinary()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'frozen': False,
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test2'},
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'frozen': False,
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38),
             'disabled_reason': 'test4'},
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'host': 'host2',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'down',
             'frozen': False,
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test5'},
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'host': 'host2',
             'zone': 'cinder',
             'status': 'enabled',
             'state': 'down',
             'frozen': False,
             'updated_at': datetime.datetime(2012, 9, 18,
                                             8, 3, 38),
             'disabled_reason': ''}]}
        self.assertEqual(response, res_dict)

    def test_services_list_with_host_service(self):
        req = FakeRequestWithHostService()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)}]}
        self.assertEqual(response, res_dict)

    def test_services_detail_with_host_service(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = FakeRequestWithHostService()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test2',
             'frozen': False}]}
        self.assertEqual(response, res_dict)

    def test_services_list_with_host_binary(self):
        req = FakeRequestWithHostBinary()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5)}]}
        self.assertEqual(response, res_dict)

    def test_services_detail_with_host_binary(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = FakeRequestWithHostBinary()
        res_dict = self.controller.index(req)

        response = {'services': [
            {'binary': 'cinder-volume',
             'replication_status': None,
             'active_backend_id': None,
             'frozen': False,
             'host': 'host1',
             'zone': 'cinder',
             'status': 'disabled',
             'state': 'up',
             'updated_at': datetime.datetime(2012, 10, 29,
                                             13, 42, 5),
             'disabled_reason': 'test2'}]}
        self.assertEqual(response, res_dict)

    def test_services_enable_with_service_key(self):
        body = {'host': 'host1', 'service': 'cinder-volume'}
        req = fakes.HTTPRequest.blank(
            '/v2/%s/os-services/enable' % fake.PROJECT_ID)
        res_dict = self.controller.update(req, "enable", body)

        self.assertEqual('enabled', res_dict['status'])

    def test_services_enable_with_binary_key(self):
        body = {'host': 'host1', 'binary': 'cinder-volume'}
        req = fakes.HTTPRequest.blank(
            '/v2/%s/os-services/enable' % fake.PROJECT_ID)
        res_dict = self.controller.update(req, "enable", body)

        self.assertEqual('enabled', res_dict['status'])

    def test_services_disable_with_service_key(self):
        req = fakes.HTTPRequest.blank(
            '/v2/%s/os-services/disable' % fake.PROJECT_ID)
        body = {'host': 'host1', 'service': 'cinder-volume'}
        res_dict = self.controller.update(req, "disable", body)

        self.assertEqual('disabled', res_dict['status'])

    def test_services_disable_with_binary_key(self):
        req = fakes.HTTPRequest.blank(
            '/v2/%s/os-services/disable' % fake.PROJECT_ID)
        body = {'host': 'host1', 'binary': 'cinder-volume'}
        res_dict = self.controller.update(req, "disable", body)

        self.assertEqual('disabled', res_dict['status'])

    def test_services_disable_log_reason(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = (
            fakes.HTTPRequest.blank('v1/fake/os-services/disable-log-reason'))
        body = {'host': 'host1',
                'binary': 'cinder-scheduler',
                'disabled_reason': 'test-reason',
                }
        res_dict = self.controller.update(req, "disable-log-reason", body)

        self.assertEqual('disabled', res_dict['status'])
        self.assertEqual('test-reason', res_dict['disabled_reason'])

    def test_services_disable_log_reason_unicode(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = (
            fakes.HTTPRequest.blank('v1/fake/os-services/disable-log-reason'))
        body = {'host': 'host1',
                'binary': 'cinder-scheduler',
                'disabled_reason': u'test-reason',
                }
        res_dict = self.controller.update(req, "disable-log-reason", body)

        self.assertEqual('disabled', res_dict['status'])
        self.assertEqual('test-reason', res_dict['disabled_reason'])

    def test_services_disable_log_reason_none(self):
        self.ext_mgr.extensions['os-extended-services'] = True
        self.controller = services.ServiceController(self.ext_mgr)
        req = (
            fakes.HTTPRequest.blank('v1/fake/os-services/disable-log-reason'))
        body = {'host': 'host1',
                'binary': 'cinder-scheduler',
                'disabled_reason': None,
                }
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update,
                          req, "disable-log-reason", body)

    def test_invalid_reason_field(self):
        # Check that empty strings are not allowed
        reason = ' ' * 10
        self.assertFalse(self.controller._is_valid_as_reason(reason))
        reason = 'a' * 256
        self.assertFalse(self.controller._is_valid_as_reason(reason))
        # Check that spaces at the end are also counted
        reason = 'a' * 255 + ' '
        self.assertFalse(self.controller._is_valid_as_reason(reason))
        reason = 'it\'s a valid reason.'
        self.assertTrue(self.controller._is_valid_as_reason(reason))
        reason = None
        self.assertFalse(self.controller._is_valid_as_reason(reason))

    def test_services_failover_host(self):
        url = '/v2/%s/os-services/failover_host' % fake.PROJECT_ID
        req = fakes.HTTPRequest.blank(url)
        body = {'host': mock.sentinel.host,
                'backend_id': mock.sentinel.backend_id}
        with mock.patch.object(self.controller.volume_api, 'failover') \
                as failover_mock:
            res = self.controller.update(req, 'failover_host', body)
        failover_mock.assert_called_once_with(req.environ['cinder.context'],
                                              mock.sentinel.host,
                                              None,
                                              mock.sentinel.backend_id)
        self.assertEqual(http_client.ACCEPTED, res.status_code)

    @ddt.data(('failover_host', {'host': mock.sentinel.host,
                                 'backend_id': mock.sentinel.backend_id}),
              ('freeze', {'host': mock.sentinel.host}),
              ('thaw', {'host': mock.sentinel.host}))
    @ddt.unpack
    @mock.patch('cinder.objects.ServiceList.get_all')
    def test_services_action_host_not_found(self, method, body,
                                            mock_get_all_services):
        url = '/v2/%s/os-services/%s' % (fake.PROJECT_ID, method)
        req = fakes.HTTPRequest.blank(url)
        mock_get_all_services.return_value = []
        msg = 'No service found with host=%s' % mock.sentinel.host
        result = self.assertRaises(exception.InvalidInput,
                                   self.controller.update,
                                   req, method, body)
        self.assertEqual(msg, result.msg)

    @ddt.data(('failover', {'cluster': mock.sentinel.cluster,
                            'backend_id': mock.sentinel.backend_id}),
              ('freeze', {'cluster': mock.sentinel.cluster}),
              ('thaw', {'cluster': mock.sentinel.cluster}))
    @ddt.unpack
    @mock.patch('cinder.objects.ServiceList.get_all')
    def test_services_action_cluster_not_found(self, method, body,
                                               mock_get_all_services):
        url = '/v3/%s/os-services/%s' % (fake.PROJECT_ID, method)
        req = fakes.HTTPRequest.blank(url, version='3.26')
        mock_get_all_services.return_value = []
        msg = 'No service found with cluster=%s' % mock.sentinel.cluster
        result = self.assertRaises(exception.InvalidInput,
                                   self.controller.update, req,
                                   method, body)
        self.assertEqual(msg, result.msg)

    def test_services_freeze(self):
        url = '/v2/%s/os-services/freeze' % fake.PROJECT_ID
        req = fakes.HTTPRequest.blank(url)
        body = {'host': mock.sentinel.host}
        with mock.patch.object(self.controller.volume_api, 'freeze_host') \
                as freeze_mock:
            res = self.controller.update(req, 'freeze', body)
        freeze_mock.assert_called_once_with(req.environ['cinder.context'],
                                            mock.sentinel.host, None)
        self.assertEqual(freeze_mock.return_value, res)

    def test_services_thaw(self):
        url = '/v2/%s/os-services/thaw' % fake.PROJECT_ID
        req = fakes.HTTPRequest.blank(url)
        body = {'host': mock.sentinel.host}
        with mock.patch.object(self.controller.volume_api, 'thaw_host') \
                as thaw_mock:
            res = self.controller.update(req, 'thaw', body)
        thaw_mock.assert_called_once_with(req.environ['cinder.context'],
                                          mock.sentinel.host, None)
        self.assertEqual(thaw_mock.return_value, res)

    @ddt.data('freeze', 'thaw', 'failover_host')
    def test_services_replication_calls_no_host(self, method):
        url = '/v2/%s/os-services/%s' % (fake.PROJECT_ID, method)
        req = fakes.HTTPRequest.blank(url)
        self.assertRaises(exception.InvalidInput,
                          self.controller.update, req, method, {})
