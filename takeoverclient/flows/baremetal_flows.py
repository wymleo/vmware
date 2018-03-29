#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import taskflow.engines
import time
import uuid

from ironicclient.common.apiclient import exceptions as iro_except
from novaclient import exceptions as nc_except
from oslo_log import log as logging
from takeoverclient.common import exceptions
from takeoverclient.common import flow_utils
from taskflow.patterns import linear_flow


LOG = logging.getLogger(__name__)


def record_failed(ip, step, msg):
    with open('/etc/openstack/baremetal/hosts_faied', 'a+') as f:
        f.write('%(time)s %(ip)s %(step)s FAILED %(msg)s\n' %
                ({'time': time.asctime( time.localtime(time.time()) ),
                  'ip': ip, 'step': step, 'msg': msg}))


def get_ipmi_terminal_port(hosts_detail, port_min, port_max):
    port_min = int(port_min)
    port_max = int(port_max)

    exist_ports = []
    for host in hosts_detail:
        exist_ports.append(host.ipmi_terminal_port)

    for port in range(port_min, port_max):
        if port not in exist_ports:
            return port


class ListHostsTask(flow_utils.TakeoverTask):
    """Get all vmware instances from vCenter Server"""
    def __init__(self, bm_driver):
        super(ListHostsTask, self).__init__('get_hosts_configs',
                                            provides='hosts')
        self.driver = bm_driver

    def execute(self, hosts_conf, hosts_detail, network_id):
        LOG.debug('Begin ListHostsTask...')

        hosts = self.driver.get_hosts_configs(hosts_conf,
                                              hosts_detail,
                                              network_id)

        LOG.debug("End ListHostsTask.")
        return {'hosts': hosts}

    def revert(self, result, flow_failures):
        pass


class AdoptFlavorTask(flow_utils.TakeoverTask):
    def __init__(self):
        super(AdoptFlavorTask, self).__init__('load_hosts_detail',
                                              provides='hosts',
                                              requires=['hosts'])

    def _get_flavor_name(self, cpu, memory, disk):
        return 'adopt.flavor.%sU%sG%sG' % (cpu, memory, disk)

    def execute(self, client, hosts=None, hosts_detail=None):
        LOG.debug('Begin AdoptFlavorTask...')
        if not hosts and not hosts_detail:
            LOG.error('No hosts or hosts_detail found.')
            raise exceptions.HostFormatInvalid(None)

        hosts = hosts['hosts'] or []
        for host in hosts:
            if not host.info_collected or host.flavor_created:
                # if flavor created, skip this host.
                continue

            try:
                flavor_name = self._get_flavor_name(host.cpu,
                                                    host.memory,
                                                    host.disk)
                try:
                    flavor = client.compute.flavors.find(name=flavor_name)
                except nc_except.NotFound:
                    flavor = client.compute.flavors.create(
                        flavor_name, host.memory, host.cpu, host.disk
                    )

                host.flavor_id = flavor.id
                host.flavor_created = True

                host.record()
            except Exception as e:
                LOG.error('%s\t%s\tFAILED\t%s', host.ip,
                          self.__class__.__name__, e.message)
                record_failed(host.ip, self.__class__.__name__, e.message)

        LOG.debug("End AdoptFlavorTask.")
        return {'hosts': hosts}

    def revert(self, hosts, result, flow_failures):
        pass


class IronicCreateTask(flow_utils.TakeoverTask):
    def __init__(self):
        super(IronicCreateTask, self).__init__(provides='hosts',
                                               requires=['hosts'])

    def _node_name(self, host):
        node_name = '%s-%s' % (host.host_name, str(uuid.uuid4())[:7])
        host.node_name = node_name
        return node_name

    def execute(self, client, deploy_kernel, deploy_ramdisk,
                ipmi_terminal_port_min, ipmi_terminal_port_max,
                hosts=None, hosts_detail=None):
        LOG.debug('Begin IronicCreateTask...')
        if not hosts and not hosts_detail:
            LOG.error('No hosts or hosts_detail found.')
            raise exceptions.HostFormatInvalid(None)

        hosts = hosts['hosts'] or []
        for host in hosts:
            if not host.flavor_created or host.ironic_created:
                # if ironic node created, skip this node
                continue

            host.ipmi_terminal_port = (host.ipmi_terminal_port or
                                       get_ipmi_terminal_port(
                                           hosts,
                                           ipmi_terminal_port_min,
                                           ipmi_terminal_port_max))
            kwargs = {
                'name': self._node_name(host),
                'driver': 'pxe_ipmitool',
                'driver_info': {
                    'ipmi_username': host.ipmi_user,
                    'ipmi_password': host.ipmi_passwd,
                    'ipmi_address': host.ipmi_ip,
                    'ipmi_terminal_port': host.ipmi_terminal_port,
                    'deploy_ramdisk': deploy_ramdisk,
                    'deploy_kernel': deploy_kernel
                },
                'extra': {'is_tookover': 'true'}
            }

            if not host.ipmi_ip:
                kwargs.update({'extra': {
                    'ipmi_info': 'with_out',
                    'is_tookover': 'true'
                }})

            try:
                node = client.ironic.node.create(**kwargs)

                host.node_id = node.uuid
                host.ironic_created = True

                host.record()
            except Exception as e:
                LOG.error('%s\t%s\tFAILED\t%s', host.ip,
                          self.__class__.__name__, e.message)
                record_failed(host.ip, self.__class__.__name__, e.message)

        LOG.debug("End IronicCreateTask.")
        return {'hosts': hosts}

    def revert(self, client, hosts, hosts_detail, result, flow_failures):
        # recheck node status
        LOG.debug('Begin recheck failed hosts...')
        hosts = hosts['hosts'] or []
        for host in hosts:
            if host.nova_adopted:
                continue

            if not host.node_id:
                continue

            try:
                client.ironic.node.delete(host.node_id)
            except:
                pass
        LOG.debug('End recheck failed hosts.')
        return True


class IronicPortCreate(flow_utils.TakeoverTask):
    def __init__(self):
        super(IronicPortCreate, self).__init__(provides='hosts',
                                               requires=['hosts'])

    def execute(self, client, hosts=None, hosts_detail=None):
        LOG.debug('Begin IronicPortCreate...')
        if not hosts and not hosts_detail:
            LOG.error('No hosts or hosts_detail found.')
            raise exceptions.HostFormatInvalid(None)

        hosts = hosts['hosts'] or []
        for host in hosts:
            if not host.ironic_created or host.port_created:
                # if port created, skip this host.
                continue

            kwargs = {
                'node_uuid': host.node_id,
                'address': host.mac
            }

            try:
                port = client.ironic.port.create(**kwargs)

                host.port_id = port.uuid
                host.port_created = True

                host.record()
            except Exception as e:
                LOG.error('%s\t%s\tFAILED\t%s', host.ip,
                          self.__class__.__name__, e.message)
                record_failed(host.ip, self.__class__.__name__, e.message)

        LOG.debug("End IronicPortCreate.")
        return {'hosts': hosts}

    def revert(self, hosts, result, flow_failures):
        pass


class IronicUpdateTask(flow_utils.TakeoverTask):
    def __init__(self):
        super(IronicUpdateTask, self).__init__(provides='hosts',
                                               requires=['hosts'])

    def execute(self, client, hosts, hosts_detail, image_source):
        LOG.debug('Begin IronicUpdateTask...')
        if not hosts and not hosts_detail:
            LOG.error('No hosts or hosts_detail found.')
            raise exceptions.HostFormatInvalid(None)

        hosts = hosts['hosts'] or []
        for host in hosts:
            if not host.port_created or host.ironic_info_set:
                continue

            patch = [{
                'path': '/properties/memory_gb',
                'value': host.memory,
                'op': 'add'
            }, {
                'path': '/properties/local_gb',
                'value': host.disk,
                'op': 'add'
            }, {
                'path': '/properties/cpus',
                'value': host.cpu,
                'op': 'add'
            }, {
                'path': '/instance_info/image_source',
                'value': image_source,
                'op': 'add'
            }, {
                'path': '/instance_info/capabilities',
                'value': {'boot_option': 'local'},
                'op': 'add'
            }]

            try:
                client.ironic.node.update(host.node_id, patch=patch)

                host.ironic_info_set = True
                host.record()
            except Exception as e:
                LOG.error('%s\t%s\tFAILED\t%s', host.ip,
                          self.__class__.__name__, e.message)
                record_failed(host.ip, self.__class__.__name__, e.message)

        LOG.debug("End IronicUpdateTask.")
        return {'hosts': hosts}

    def revert(self, hosts, result, flow_failures):
        pass


class IronicManageTask(flow_utils.TakeoverTask):
    def __init__(self, state):
        super(IronicManageTask, self).__init__(provides='hosts',
                                               requires=['hosts'])
        self.state = state

    def _wait(self, client, node_id, state=None):
        _LONG_ACTION_POLL_INTERVAL = 10
        _SHORT_ACTION_POLL_INTERVAL = 2
        _PROVISION_ACTIONS = {
            'active': {'expected_state': 'active',
                       'poll_interval': _LONG_ACTION_POLL_INTERVAL},
            'deleted': {'expected_state': 'available',
                        'poll_interval': _LONG_ACTION_POLL_INTERVAL},
            'rebuild': {'expected_state': 'active',
                        'poll_interval': _LONG_ACTION_POLL_INTERVAL},
            'inspect': {'expected_state': 'manageable',
                        # This is suboptimal for in-band inspection,
                        # but it's probably not worth making people
                        # wait 10 seconds for OOB inspection
                        'poll_interval': _SHORT_ACTION_POLL_INTERVAL},
            'provide': {'expected_state': 'available',
                        # This assumes cleaning is in place
                        'poll_interval': _LONG_ACTION_POLL_INTERVAL},
            'manage': {'expected_state': 'manageable',
                       'poll_interval': _SHORT_ACTION_POLL_INTERVAL},
            'clean': {'expected_state': 'manageable',
                      'poll_interval': _LONG_ACTION_POLL_INTERVAL},
            'adopt': {'expected_state': 'active',
                      'poll_interval': _SHORT_ACTION_POLL_INTERVAL},
            'abort': None,  # no support for --wait in abort
        }
        wait_args = _PROVISION_ACTIONS.get(state or self.state)
        if wait_args is None:
            raise iro_except.CommandError(
                "Wait is not supported for provision state '%s'"
                % self.state)

        client.ironic.node.wait_for_provision_state(
            node_id, timeout=10, **wait_args)

    def _record(self, host):
        if self.state == 'manage':
            host.ironic_managed = True
        if self.state == 'adopt':
            host.node_adopted = True

        host.record()

    def execute(self, client, hosts, hosts_detail):
        LOG.debug("Begin IronicManageTask...")
        if not hosts and not hosts_detail:
            LOG.error('No hosts or hosts_detail found.')
            raise exceptions.HostFormatInvalid(None)

        hosts = hosts['hosts'] or []
        for host in hosts:
            if (self.state == 'manage' and
                    (not host.ironic_info_set or host.ironic_managed)):
                continue

            if (self.state == 'adopt' and
                    (not host.ironic_managed or host.node_adopted)):
                continue

            try:
                client.ironic.node.set_provision_state(host.node_id,
                                                       self.state)
                self._wait(client, host.node_id)

                self._record(host)
            except Exception as e:
                LOG.error('%s\t%s\tFAILED\t%s', host.ip,
                          self.__class__.__name__, e.message)
                record_failed(host.ip, self.__class__.__name__, e.message)

        LOG.debug("End IronicManageTask.")
        return {'hosts': hosts}

    def revert(self, client, hosts, result, flow_failures):
        pass


class IronicAdoptTask(IronicManageTask):
    def __init__(self, state):
        super(IronicAdoptTask, self).__init__(state)

    def _undeploy(self, client, node_id, ip):
        try:
            client.ironic.node.set_provision_state(node_id,
                                                   'deleted')
            self._wait(client, node_id)
        except Exception as e:
            LOG.error('%s\t%s\tFAILED\t%s', ip,
                      self.__class__.__name__ + '.undeploy', e.message)
            record_failed(ip, self.__class__.__name__ + '.undeploy',
                          e.message)

        return True

    def _delete_node(self, client, node_id, ip):
        try:
            client.ironic.node.delete(node_id)
        except Exception as e:
            LOG.error('%s\t%s\tFAILED\t%s', ip,
                      self.__class__.__name__ + '.delete_node', e.message)
            record_failed(ip, self.__class__.__name__ + '.delete_node',
                          e.message)

        return True

    def revert(self, client, hosts, result, flow_failures):
        # in this section, we need to delete ironic node directly.
        LOG.debug('Begin to revert hosts in failed status.')
        hosts = hosts['hosts'] or []
        for host in hosts:
            if host.nova_adopted:
                continue

            if not host.node_id:
                continue

            if (self._undeploy(client, host.node_id, host.ip) and
                    self._delete_node(client, host.node_id, host.ip)):
                host.clear()

        LOG.debug('End revert failed hosts.')
        return True


class NovaAdoptTask(flow_utils.TakeoverTask):
    def __init__(self):
        super(NovaAdoptTask, self).__init__(requires=['hosts'])

    def execute(self, client, hosts, hosts_detail):
        LOG.debug("End NovaAdoptTask.")
        if not hosts and not hosts_detail:
            LOG.error('No hosts or hosts_detail found.')
            raise exceptions.HostFormatInvalid(None)

        hosts = hosts['hosts'] or []
        for host in hosts:
            if not host.node_adopted or host.nova_adopted:
                continue

            try:
                client.nova_adopt_manager.adopt(host)

                host.nova_adopted = True
                host.record()
            except Exception as e:
                LOG.error('%s\t%s\tFAILED\t%s', host.ip,
                          self.__class__.__name__, e.message)
                record_failed(host.ip, self.__class__.__name__, e.message)

        LOG.debug("End NovaAdoptTask.")
        # raise exception for revert host which created failed.
        raise exceptions.RevertException('revert failed hosts.')

    def revert(self, hosts, result, flow_failures):
        # if Nova adopt error, the instance info will not be record, so
        # it's unnecessary to revert Nova instance info.
        pass


def adopt_hosts_flow(driver, conf, client, host_list_file, network_id):
    flow_name = "baremetal_adopt_flow"
    server_flow = linear_flow.Flow(flow_name)

    # This injects the initial starting flow values into the workflow so that
    # the dependency order of the tasks provides/requires can be correctly
    # determined.
    bm_config = conf['baremetal']
    create_what = {
        'hosts_conf': host_list_file or
                      bm_config.get('hosts_conf',
                                    '/etc/openstack/baremetal/hosts.conf'),
        'hosts_detail': bm_config.get(
            'hosts_detail',
            '/etc/openstack/baremetal/hosts_detail.json'),
        'deploy_kernel': bm_config.get('deploy_kernel'),
        'deploy_ramdisk': bm_config.get('deploy_ramdisk'),
        'image_source': bm_config.get('image_source'),
        'client': client,
        'network_id': network_id,
        'ipmi_terminal_port_min': bm_config.get(
            'ipmi_terminal_port_min', 7500),
        'ipmi_terminal_port_max': bm_config.get(
            'ipmi_terminal_port_max', 7999)
    }

    server_flow.add(ListHostsTask(driver),
                    AdoptFlavorTask(),
                    IronicCreateTask(),
                    IronicPortCreate(),
                    IronicUpdateTask(),
                    IronicManageTask('manage'),
                    IronicAdoptTask('adopt'),
                    NovaAdoptTask())

    # Now load (but do not run) the flow using the provided initial data.
    return taskflow.engines.load(server_flow, store=create_what)
