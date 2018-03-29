# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
# Copyright (c) 2012 VMware, Inc.
# Copyright (c) 2011 Citrix Systems, Inc.
# Copyright 2011 OpenStack Foundation
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

"""
A connection to the VMware vCenter platform.
"""

import re

from os_client_config import config as cloud_config
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import versionutils as v_utils
from oslo_vmware import api
from oslo_vmware import exceptions as vexc
from oslo_vmware import pbm
from oslo_vmware import vim
from oslo_vmware import vim_util

from takeoverclient.common import exceptions
from takeoverclient.common.i18n import _
from takeoverclient.virt import driver
from takeoverclient.virt.vmwareapi import constants
from takeoverclient.virt.vmwareapi import vim_util as nova_vim_util
from takeoverclient.virt.vmwareapi import vm_util
from takeoverclient.virt.vmwareapi import vmops
from takeoverclient.virt.vmwareapi import vdsops

LOG = logging.getLogger(__name__)

TIME_BETWEEN_API_CALL_RETRIES = 1.0


class VMwareVCDriver(driver.VirtDriver):
    """The VC host connection object."""

    # The vCenter driver includes API that acts on ESX hosts or groups
    # of ESX hosts in clusters or non-cluster logical-groupings.
    #
    # vCenter is not a hypervisor itself, it works with multiple
    # hypervisor host machines and their guests. This fact can
    # subtly alter how vSphere and OpenStack interoperate.
    def __init__(self, scheme="https", cluster=None):
        super(VMwareVCDriver, self).__init__()

        conf = cloud_config.OpenStackConfig().get_one_cloud(
            cloud="takeover").config

        vm_conf = conf['vmware']
        host_ip = vm_conf.get("host_ip")
        host_username = vm_conf.get("host_username")
        host_password = vm_conf.get("host_password")
        if (host_ip is None or
            host_username is None or
            host_password is None):
            raise Exception(_("Must specify host_ip, host_username and "
                              "host_password to use vmwareapi.VMwareVCDriver"))

        if not cluster:
            self._cluster_name = vm_conf.get("cluster_name")
        else:
            self._cluster_name = cluster

        self._session = VMwareAPISession(
            host_ip=host_ip,
            host_port=vm_conf.get("host_port", 443),
            username=host_username,
            password=host_password,
            retry_count=vm_conf.get("api_retry_count", 10),
            cacert=vm_conf.get("ca_file", None),
            insecure=vm_conf.get("insecure", True),
            pool_size=vm_conf.get("connection_pool_size", 10),
            scheme=scheme)

        self._check_min_version()

        self._cluster_ref = vm_util.get_cluster_ref_by_name(self._session,
                                                            self._cluster_name)
        if self._cluster_ref is None:
            raise exceptions.NotFound(_("The specified cluster '%s' was not "
                                        "found in vCenter")
                                      % self._cluster_name)
        self._vmops = vmops.VMwareVMOps(self._session,
                                        self._cluster_ref)
        self._vdsops = vdsops.VdsOps(self._session)

    def _check_min_version(self):
        min_version = v_utils.convert_version_to_int(constants.MIN_VC_VERSION)
        next_min_ver = v_utils.convert_version_to_int(
            constants.NEXT_MIN_VC_VERSION)
        vc_version = vim_util.get_vc_version(self._session)
        LOG.info("VMware vCenter version: %s", vc_version)
        if v_utils.convert_version_to_int(vc_version) < min_version:
            raise exceptions.Unauthorized(
                _('Detected vCenter version %(version)s. Nova requires VMware '
                  'vCenter version %(min_version)s or greater.') % {
                    'version': vc_version,
                    'min_version': constants.MIN_VC_VERSION})
        elif v_utils.convert_version_to_int(vc_version) < next_min_ver:
            LOG.warning('Running Nova with a VMware vCenter version less '
                        'than %(version)s is deprecated. The required '
                        'minimum version of vCenter will be raised to '
                        '%(version)s in the 16.0.0 release.',
                        {'version': constants.NEXT_MIN_VC_VERSION})

    def _get_vcenter_uuid(self):
        """Retrieves the vCenter UUID."""

        about = self._session._call_method(nova_vim_util, 'get_about_info')
        return about.instanceUuid

    def list_instances(self):
        """Return the names of all the instances known to the virtualization
        layer, as a list.
        """
        # TODO(Vek): Need to pass context in for access to auth_token
        return self._vmops.list_instances()

    def get_networks(self):
        """Return the UUIDS of all the instances known to the virtualization
        layer, as a list.
        """
        return self._vdsops.list_networks()

    def get_instance_cpus(self, instance=None):
        """Get the number of a instance

        :param instance: The instance object.
        :return: An integer number
        """
        raise NotImplementedError()

    def get_instance_memory(self, instance=None):
        """Get the memory size of a instance

        :param instance: The instance object.
        :return: An integer number, unit is MB
        """
        raise NotImplementedError()

    def get_instance_swap(self, instance=None):
        """Get the swap size of a instance

        :param instance: The instance object.
        :return: An integer number, unit is MB
        """
        raise NotImplementedError()

    def get_instance_disk_size(self, instance=None):
        """Get the disk size of a instance

        :param instance: The instance object.
        :return: An integer number, unit is GB
        """
        raise NotImplementedError()

    def get_instance_flavor(self, instance=None):
        """Return the flavor information from instance or other information

        :param instance: The instance object.
        :return: A dict includes cpu,memory,disk.,etc
        """
        raise NotImplementedError()

    def get_instance_nics(self, instance=None):
        """Get the instance

        :param instance:
        :return:
        """
        raise NotImplementedError()


class VMwareAPISession(api.VMwareAPISession):
    """Sets up a session with the VC/ESX host and handles all
    the calls made to the host.
    """
    def __init__(self, host_ip,
                 host_port,
                 username,
                 password,
                 retry_count=10,
                 scheme="https",
                 cacert=None,
                 insecure=True,
                 pool_size=10):
        super(VMwareAPISession, self).__init__(
                host=host_ip,
                port=host_port,
                server_username=username,
                server_password=password,
                api_retry_count=retry_count,
                task_poll_interval=0.5,
                scheme=scheme,
                create_session=True,
                cacert=cacert,
                insecure=insecure,
                pool_size=pool_size)

    def _is_vim_object(self, module):
        """Check if the module is a VIM Object instance."""
        return isinstance(module, vim.Vim)

    def _call_method(self, module, method, *args, **kwargs):
        """Calls a method within the module specified with
        args provided.
        """
        if not self._is_vim_object(module):
            return self.invoke_api(module, method, self.vim, *args, **kwargs)
        else:
            return self.invoke_api(module, method, *args, **kwargs)

    def _wait_for_task(self, task_ref):
        """Return a Deferred that will give the result of the given task.
        The task is polled until it completes.
        """
        return self.wait_for_task(task_ref)
