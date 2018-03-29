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
Class for VM tasks like spawn, snapshot, suspend, resume etc.
"""

import collections
import os
import time

import decorator
from oslo_concurrency import lockutils
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import excutils
from oslo_utils import strutils
from oslo_utils import units
from oslo_utils import uuidutils
from oslo_vmware import exceptions as vexc
from oslo_vmware.objects import datastore as ds_obj
from oslo_vmware import vim_util as vutil

from nova.api.metadata import base as instance_metadata
from nova import compute
from nova.compute import power_state
from nova.compute import task_states
import nova.conf
from nova.console import type as ctype
from nova import context as nova_context
from nova import exception
from nova.i18n import _
from nova import network
from nova import objects
from nova import utils
from nova import version
from nova.virt import configdrive
from nova.virt import driver
from nova.virt import hardware
from nova.virt.vmwareapi import constants
from nova.virt.vmwareapi import ds_util
from nova.virt.vmwareapi import error_util
from nova.virt.vmwareapi import imagecache
from nova.virt.vmwareapi import images
from nova.virt.vmwareapi import vif as vmwarevif
from nova.virt.vmwareapi import vim_util
from nova.virt.vmwareapi import vm_util


CONF = nova.conf.CONF

LOG = logging.getLogger(__name__)

RESIZE_TOTAL_STEPS = 6


class VirtualMachineInstanceConfigInfo(object):
    """Parameters needed to create and configure a new instance."""

    def __init__(self, instance, image_info, datastore, dc_info, image_cache,
                 extra_specs=None):

        # Some methods called during spawn take the instance parameter purely
        # for logging purposes.
        # TODO(vui) Clean them up, so we no longer need to keep this variable
        self.instance = instance

        self.ii = image_info
        self.root_gb = instance.flavor.root_gb
        self.datastore = datastore
        self.dc_info = dc_info
        self._image_cache = image_cache
        self._extra_specs = extra_specs

    @property
    def cache_image_folder(self):
        if self.ii.image_id is None:
            return
        return self._image_cache.get_image_cache_folder(
                   self.datastore, self.ii.image_id)

    @property
    def cache_image_path(self):
        if self.ii.image_id is None:
            return
        cached_image_file_name = "%s.%s" % (self.ii.image_id,
                                            self.ii.file_type)
        return self.cache_image_folder.join(cached_image_file_name)


# Note(vui): See https://bugs.launchpad.net/nova/+bug/1363349
# for cases where mocking time.sleep() can have unintended effects on code
# not under test. For now, unblock the affected test cases by providing
# a wrapper function to work around needing to mock time.sleep()
def _time_sleep_wrapper(delay):
    time.sleep(delay)


@decorator.decorator
def retry_if_task_in_progress(f, *args, **kwargs):
    retries = max(CONF.vmware.api_retry_count, 1)
    delay = 1
    for attempt in range(1, retries + 1):
        if attempt != 1:
            _time_sleep_wrapper(delay)
            delay = min(2 * delay, 60)
        try:
            f(*args, **kwargs)
            return
        except vexc.TaskInProgress:
            pass


class VMwareVMOps(object):
    """Management class for VM-related tasks."""

    def __init__(self, session, cluster=None):
        """Initializer."""
        self._session = session
        self._cluster = cluster
        self._root_resource_pool = vm_util.get_res_pool_ref(self._session,
                                                            self._cluster)

    def _get_extra_specs(self, flavor, image_meta=None):
        image_meta = image_meta or objects.ImageMeta.from_dict({})
        extra_specs = vm_util.ExtraSpecs()
        for resource in ['cpu', 'memory', 'disk_io', 'vif']:
            for (key, type) in (('limit', int),
                                ('reservation', int),
                                ('shares_level', str),
                                ('shares_share', int)):
                value = flavor.extra_specs.get('quota:' + resource + '_' + key)
                if value:
                    setattr(getattr(extra_specs, resource + '_limits'),
                            key, type(value))
        extra_specs.cpu_limits.validate()
        extra_specs.memory_limits.validate()
        extra_specs.disk_io_limits.validate()
        extra_specs.vif_limits.validate()
        hw_version = flavor.extra_specs.get('vmware:hw_version')
        extra_specs.hw_version = hw_version
        if CONF.vmware.pbm_enabled:
            storage_policy = flavor.extra_specs.get('vmware:storage_policy',
                    CONF.vmware.pbm_default_policy)
            extra_specs.storage_policy = storage_policy
        topology = hardware.get_best_cpu_topology(flavor, image_meta,
                                                  allow_threads=False)
        extra_specs.cores_per_socket = topology.cores
        return extra_specs

    def get_info(self, instance):
        """Return data about the VM instance."""
        vm_ref = vm_util.get_vm_ref(self._session, instance)

        lst_properties = ["runtime.powerState"]
        try:
            vm_props = self._session._call_method(vutil,
                                                  "get_object_properties_dict",
                                                  vm_ref,
                                                  lst_properties)
        except vexc.ManagedObjectNotFoundException:
            raise exception.InstanceNotFound(instance_id=instance.uuid)
        return hardware.InstanceInfo(
            state=constants.POWER_STATES[vm_props['runtime.powerState']])

    def _get_valid_vms_from_retrieve_result(self, retrieve_result):
        """Returns list of valid vms from RetrieveResult object."""
        lst_vm_names = {}

        while retrieve_result:
            for vm in retrieve_result.objects:
                vm_uuid = None
                conn_state = None
                guest_status = None
                power_state = None
                recent_task = None
                for prop in vm.propSet:
                    if prop.name == "runtime.connectionState":
                        conn_state = prop.val
                    elif prop.name == 'config.extraConfig["nvp.vm-uuid"]':
                        vm_uuid = prop.val.value
                    elif prop.name == 'config.guestHeartbeatStatus':
                        guest_status = prop.val.value
                    elif prop.name == 'runtime.powerState':
                        power_state = prop.val.value
                    elif prop.name == 'network':
                        network = prop.val
                    elif prop.name == 'recentTask':
                        recent_task = prop.val

                # Ignore VM's that do not have nvp.vm-uuid defined
                if not vm_uuid:
                    continue
                # Ignoring the orphaned or inaccessible VMs
                if conn_state not in ["orphaned", "inaccessible"]:
                    lst_vm_names.update(vm_uuid=vm_uuid,
                                        guest_status=guest_status,
                                        power_state=power_state,
                                        network=network,
                                        recent_task=recent_task)
            retrieve_result = self._session._call_method(vutil,
                                                         'continue_retrieval',
                                                         retrieve_result)
        return lst_vm_names

    def list_instances(self):
        """Lists the VM instances that are registered with vCenter cluster."""
        properties = ['runtime.connectionState',
                      'config.extraConfig["nvp.vm-uuid"]',
                      'guestHeartbeatStatus',
                      'runtime.powerState',
                      'network',
                      'recentTask']
        LOG.debug("Getting list of instances from cluster %s",
                  self._cluster)
        vms = []
        if self._root_resource_pool:
            vms = self._session._call_method(
                vim_util, 'get_inner_objects', self._root_resource_pool, 'vm',
                'VirtualMachine', properties)
        lst_vm_names = self._get_valid_vms_from_retrieve_result(vms)

        LOG.debug("Got total of %s instances", str(len(lst_vm_names)))
        return lst_vm_names
