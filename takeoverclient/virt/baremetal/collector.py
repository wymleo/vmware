import os
import paramiko
import time

from oslo_log import log as logging
from oslo_serialization import jsonutils
from takeoverclient.common import exceptions


LOG = logging.getLogger(__name__)


def init_confs(conf_file='/etc/openstack/baremetal/hosts_detail.json'):
    with open(conf_file, 'w') as f:
        f.write('{}')


def check_hosts_conf(conf_file):
    if not os.path.exists(conf_file):
        LOG.error('Config file %s is not exsit.', conf_file)
        raise exceptions.InvalidConfigFile(conf_file)

    with open(conf_file) as f:
        for line in f.readlines():
            line = line.strip('\r\n').strip('\n\r').strip('\n').strip(' ')
            if not line:
                continue
            parts = line.split(';')
            if len(parts) != 6:
                raise exceptions.HostFormatInvalid(line)


def load_hosts_detail(hosts_detail='/etc/openstack/baremetal/hosts_detail.json'):
    if not os.path.exists(hosts_detail):
        LOG.error('Host detail file not exist.')
        raise exceptions.HostFormatInvalid(hosts_detail)

    hosts = {}
    with open(hosts_detail) as f:
        hosts = jsonutils.load(f)

    hosts_info = []
    for v in hosts.values():
        hosts_info.append(Host(**v))

    return hosts_info


def record_failed(ip, step, msg):
    with open('/etc/openstack/baremetal/hosts_faied', 'a+') as f:
        f.write('%(time)s %(ip)s %(step)s FAILED %(msg)s\n' %
                ({'time': time.asctime(time.localtime(time.time())),
                  'ip': ip, 'step': step, 'msg': msg}))


class Host(object):
    def __init__(self, *args, **kwargs):
        self.ip = kwargs.get('ip')
        self.user = kwargs.get('user')
        self.passwd = kwargs.get('passwd')
        self.ipmi_ip = kwargs.get('ipmi_ip')
        self.ipmi_user = kwargs.get('ipmi_user')
        self.ipmi_passwd = kwargs.get('ipmi_passwd')
        self.cpu = kwargs.get('cpu')
        self.memory = kwargs.get('memory')
        self.mac = kwargs.get('mac')
        self.disk = kwargs.get('disk')
        self.host_name = kwargs.get('hostname')
        self.node_id = kwargs.get('node_id')
        self.node_name = kwargs.get('node_name')
        self.flavor_id = kwargs.get('flavor_id')
        self.port_id = kwargs.get('port_id')
        self.ipmi_terminal_port = kwargs.get('ipmi_terminal_port')
        self.network_id = kwargs.get('network_id')

        # record progress
        self.info_collected = kwargs.get('info_collected') or False
        self.flavor_created = kwargs.get('flavor_created') or False
        self.ironic_created = kwargs.get('ironic_created') or False
        self.port_created  = kwargs.get('port_created') or False
        self.ironic_info_set = kwargs.get('ironic_info_set') or False
        self.ironic_managed = kwargs.get('ironic_managed') or False
        self.node_adopted = kwargs.get('node_adopted') or False
        self.nova_adopted = kwargs.get('nova_adopted') or False

        self.hosts_detail = kwargs.get('hosts_detail')

    def __repr__(self):
        return 'Host(%s)' % self.ip

    def record(self):
        if not os.path.exists(self.hosts_detail):
            init_confs(self.hosts_detail)

        hosts = {}
        with open(self.hosts_detail) as f:
            hosts = jsonutils.load(f)
            hosts.update(self.to_dict())

        with open(self.hosts_detail, 'w') as f:
            jsonutils.dump(hosts, f)

    def get_info(self):
        def set_value(values):
            for k, v in values.items():
                if k == 'mac':
                    self.mac = v
                if k == 'cpu':
                    self.cpu = v
                if k == 'disk':
                    self.disk = v
                if k == 'memory':
                    self.memory = v
                if k == 'hostname':
                    self.host_name = v

            if all([self.mac, self.cpu, self.disk, self.memory]):
                self.info_collected = True

        info_list = [CPU, Memory, Disk, Mac, HostName]
        info_dict = {}
        for info in info_list:
            try:
                ret = info(self.ip, self.user, self.passwd)()
                info_dict.update(ret)
            except Exception as e:
                record_failed(self.ip, self.__class__.__name__, e.message)

        set_value(info_dict)
        self.record()

    @staticmethod
    def load(*args, **kwargs):
        return Host(kwargs.get('ip'), kwargs.get('user'), kwargs.get('passwd'),
                    kwargs.get('ipmi_ip'), kwargs.get('ipmi_user'),
                    kwargs.get('ipmi_passwd'), None, **kwargs)

    def to_dict(self):
        return {self.ip: {
            'hostname': self.host_name,
            'cpu': self.cpu,
            'memory': self.memory,
            'mac': self.mac,
            'disk': self.disk,
            'ip': self.ip,
            'user': self.user,
            'passwd': self.passwd,
            'ipmi_ip': self.ipmi_ip,
            'ipmi_user': self.ipmi_user,
            'ipmi_passwd': self.ipmi_passwd,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'flavor_id': self.flavor_id,
            'port_id': self.port_id,
            'ipmi_terminal_port': self.ipmi_terminal_port,
            'network_id': self.network_id,

            'info_collected': self.info_collected,
            'flavor_created': self.flavor_created,
            'ironic_created': self.ironic_created,
            'port_created': self.port_created,
            'ironic_info_set': self.ironic_info_set,
            'ironic_managed': self.ironic_managed,
            'node_adopted': self.node_adopted,
            'nova_adopted': self.nova_adopted,

            'hosts_detail': self.hosts_detail
        }}

    def clear(self):
        self.node_id = None
        self.ironic_created = False
        self.port_created = False
        self.ironic_info_set = False
        self.ironic_managed = False
        self.node_adopted = False

        self.record()


class HostManager(object):
    def __init__(self, conf, hosts_conf, hosts_detail, network_id):
        self.hosts_conf = hosts_conf or conf.get('baremetal').get(
            'hosts_conf', '/etc/openstack/baremetal/hosts.conf')
        self.hosts_detail = hosts_detail or conf('baremetal')(
            'hosts_detail', '/etc/openstack/baremetal/hosts_detail.json')
        self.network_id = network_id
        check_hosts_conf(self.hosts_conf)

    def _get_terminal_port(self):
        pass

    def _parse_hosts_info(self):
        hosts = []
        hosts_detail = self._parse_hosts_detail()
        with open(self.hosts_conf) as f:
            for line in f.readlines():
                line = line.strip('\r\n').strip('\n\r').strip('\n').strip(' ')
                if not line:
                    continue

                if line.startswith('#'):
                    continue

                parts = line.split(';')
                if len(parts) != 6:
                    LOG.error('Invalid host format: %s', line)
                    raise exceptions.HostFormatInvalid(
                        'Invalid host format: %s' % line)

                ip = parts[3]
                if ip in hosts_detail:
                    hosts.append(Host(**hosts_detail.get(ip)))
                else:
                    hosts.append(Host(**{
                        'ipmi_ip': parts[0],
                        'ipmi_user': parts[1],
                        'ipmi_passwd': parts[2],
                        'ip': ip,
                        'user': parts[4],
                        'passwd': parts[5],
                        'network_id': self.network_id,
                        'hosts_detail': self.hosts_detail
                    }))

        return hosts

    def _parse_hosts_detail(self):
        hosts_dict = {}
        if not os.path.exists(self.hosts_detail):
            init_confs(self.hosts_detail)
            return hosts_dict

        with open(self.hosts_detail) as f:
            hosts_dict = jsonutils.load(f)

        return hosts_dict

    def execute(self):
        if (not os.path.isfile(self.hosts_conf) and
                not os.path.isfile(self.hosts_detail)):
            LOG.error('Invalid config file path: %s and %s',
                      self.hosts_conf, self.hosts_detail)
            raise exceptions.InvalidConfigFile(self.hosts_conf)

        hosts = self._parse_hosts_info()

        for host in hosts:
            if host.info_collected:
                host.network_id = self.network_id
                host.record()
                continue

            host.get_info()

        return hosts


class RemoteExecutor(object):
    cmd = ''

    def __init__(self, host, user, passwd):
        self.host = host
        self.user = user
        self.passwd = passwd

    def __call__(self, *args, **kwargs):
        '''Get info from hosted OS by running command on remote host
        :return: dict
        '''
        self.pre_run()

        return self.post_run(self._run_cmd())

    def _run_cmd(self):
        ssh = None
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.host, 22, self.user, self.passwd, timeout=50)
            stdin, stdout, stderr = ssh.exec_command(self.cmd)
            return stdout.read().strip('\n').strip(' ')
        except Exception:
            LOG.exception('Error when execute command (%s) on host (%s)',
                          self.cmd, self.host)
            raise
        finally:
            if ssh:
                ssh.close()

    def pre_run(self):
        # record information about this command
        LOG.info('Remote host: %(host)s, cmd: %(cmd)s',
                 {'host': self.host, 'cmd': self.cmd})

    def post_run(self, value):
        LOG.info('Cmd return: %s', value)


class CPU(RemoteExecutor):
    cmd = 'cat /proc/cpuinfo | grep "processor" | wc -l'

    def __init__(self, *args, **kwargs):
        super(CPU, self).__init__(*args, **kwargs)

    def pre_run(self):
        pass

    def post_run(self, value):
        return {'cpu': int(value)}


class Memory(RemoteExecutor):
    cmd = ("cat /proc/meminfo | grep 'MemTotal' | "
           "awk -F : '{print $2}' | sed 's/^[ \t]*//g'")

    def __init__(self, *args, **kwargs):
        super(Memory, self).__init__(*args, **kwargs)

    def pre_run(self):
        pass

    def post_run(self, value):
        parts = value.split(' ')
        value = int(parts[0].strip(' '))
        unit = parts[1].strip('\n').strip(' ')
        if unit == 'kB' or unit == 'KB':
            value /= 1024
        if unit == 'gB' or unit == 'GB':
            value *= 1024

        return {'memory': value}


class Disk(RemoteExecutor):
    cmd = ("fdisk -l | grep Disk | grep '/dev/sda' | "
           "awk -F , '{print $1}' | awk -F : '{print $2}'")

    def __init__(self, *args, **kwargs):
        super(Disk, self).__init__(*args, **kwargs)

    def pre_run(self):
        pass

    def post_run(self, value):
        LOG.info('%s Mac: %s', self.host, value)
        parts = value.split(' ')
        return {'disk': int(float(parts[0]))}


class Mac(RemoteExecutor):
    #cmd = "ping -c 1 %s; arp -n %s | sed -n '2p' | awk '{print $3}'"
    cmd = "ip addr |grep -B1 %s | grep ether | awk '{print $2}'"

    def __init__(self, *args, **kwargs):
        super(Mac, self).__init__(*args, **kwargs)

    def pre_run(self):
        self.cmd = self.cmd % self.host

    def post_run(self, value):
        LOG.info('%s Mac: %s', self.host, value)
        return {'mac': value}

    # def _run_cmd(self):
    #     from subprocess import Popen, PIPE
    #     import re
    #     Popen(["ping", "-c 1", self.host], stdout=PIPE)
    #     pid = Popen(["arp", "-n", self.host], stdout=PIPE)
    #     s = pid.communicate()[0]
    #     try:
    #         return re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})", s).groups()[0]
    #     except Exception:
    #         LOG.error('Get %s MAC error', self.host)
    #         raise


class HostName(RemoteExecutor):
    cmd = 'hostname'

    def __init__(self, *args, **kwargs):
        super(HostName, self).__init__(*args, **kwargs)

    def pre_run(self):
        pass

    def post_run(self, value):
        LOG.info('%s Hostname: %s', self.host, value)
        return {'hostname': value}
