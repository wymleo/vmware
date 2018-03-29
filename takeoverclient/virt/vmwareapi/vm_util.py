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
The VMware API VM utility module to build SOAP object specs.
"""

import collections
import functools

from oslo_log import log as logging
from oslo_utils import units
from oslo_vmware.objects import datastore as ds_obj
from oslo_vmware import vim_util as vutil


from takeoverclient.virt.vmwareapi import constants
from takeoverclient.virt.vmwareapi import vim_util
from takeoverclient.common import exceptions

LOG = logging.getLogger(__name__)


ALL_SUPPORTED_NETWORK_DEVICES = ['VirtualE1000', 'VirtualE1000e',
                                 'VirtualPCNet32', 'VirtualSriovEthernetCard',
                                 'VirtualVmxnet', 'VirtualVmxnet3']

# A simple cache for storing inventory folder references.
# Format: {inventory_path: folder_ref}
_FOLDER_PATH_REF_MAPPING = {}

# A cache for VM references. The key will be the VM name
# and the value is the VM reference. The VM name is unique. This
# is either the UUID of the instance or UUID-rescue in the case
# that this is a rescue VM. This is in order to prevent
# unnecessary communication with the backend.

# the config key which stores the VNC port
VNC_CONFIG_KEY = 'config.extraConfig["RemoteDisplay.vnc.port"]'

VmdkInfo = collections.namedtuple('VmdkInfo', ['path', 'adapter_type',
                                               'disk_type',
                                               'capacity_in_bytes',
                                               'device'])


def _get_device_capacity(device):
    # Devices pre-vSphere-5.5 only reports capacityInKB, which has
    # rounding inaccuracies. Use that only if the more accurate
    # attribute is absent.
    if hasattr(device, 'capacityInBytes'):
        return device.capacityInBytes
    else:
        return device.capacityInKB * units.Ki


def _get_device_disk_type(device):
    if getattr(device.backing, 'thinProvisioned', False):
        return constants.DISK_TYPE_THIN
    else:
        if getattr(device.backing, 'eagerlyScrub', False):
            return constants.DISK_TYPE_EAGER_ZEROED_THICK
        else:
            return constants.DEFAULT_DISK_TYPE


def get_vmdk_info(session, vm_ref, uuid=None):
    """Returns information for the primary VMDK attached to the given VM."""
    hardware_devices = session._call_method(vutil,
                                            "get_object_property",
                                            vm_ref,
                                            "config.hardware.device")
    if hardware_devices.__class__.__name__ == "ArrayOfVirtualDevice":
        hardware_devices = hardware_devices.VirtualDevice
    vmdk_file_path = None
    vmdk_controller_key = None
    disk_type = None
    capacity_in_bytes = 0

    # Determine if we need to get the details of the root disk
    root_disk = None
    root_device = None
    if uuid:
        root_disk = '%s.vmdk' % uuid
    vmdk_device = None

    adapter_type_dict = {}
    for device in hardware_devices:
        if device.__class__.__name__ == "VirtualDisk":
            if device.backing.__class__.__name__ == \
                    "VirtualDiskFlatVer2BackingInfo":
                path = ds_obj.DatastorePath.parse(device.backing.fileName)
                if root_disk and path.basename == root_disk:
                    root_device = device
                vmdk_device = device
        elif device.__class__.__name__ == "VirtualLsiLogicController":
            adapter_type_dict[device.key] = constants.DEFAULT_ADAPTER_TYPE
        elif device.__class__.__name__ == "VirtualBusLogicController":
            adapter_type_dict[device.key] = constants.ADAPTER_TYPE_BUSLOGIC
        elif device.__class__.__name__ == "VirtualIDEController":
            adapter_type_dict[device.key] = constants.ADAPTER_TYPE_IDE
        elif device.__class__.__name__ == "VirtualLsiLogicSASController":
            adapter_type_dict[device.key] = constants.ADAPTER_TYPE_LSILOGICSAS
        elif device.__class__.__name__ == "ParaVirtualSCSIController":
            adapter_type_dict[device.key] = constants.ADAPTER_TYPE_PARAVIRTUAL

    if root_disk:
        vmdk_device = root_device

    if vmdk_device:
        vmdk_file_path = vmdk_device.backing.fileName
        capacity_in_bytes = _get_device_capacity(vmdk_device)
        vmdk_controller_key = vmdk_device.controllerKey
        disk_type = _get_device_disk_type(vmdk_device)

    adapter_type = adapter_type_dict.get(vmdk_controller_key)
    return VmdkInfo(vmdk_file_path, adapter_type, disk_type,
                    capacity_in_bytes, vmdk_device)


def get_rdm_disk(hardware_devices, uuid):
    """Gets the RDM disk key."""
    if hardware_devices.__class__.__name__ == "ArrayOfVirtualDevice":
        hardware_devices = hardware_devices.VirtualDevice

    for device in hardware_devices:
        if (device.__class__.__name__ == "VirtualDisk" and
            device.backing.__class__.__name__ ==
                "VirtualDiskRawDiskMappingVer1BackingInfo" and
                device.backing.lunUuid == uuid):
            return device


def _get_object_for_value(results, value):
    for object in results.objects:
        if object.propSet[0].val == value:
            return object.obj


def _get_object_for_optionvalue(results, value):
    for object in results.objects:
        if hasattr(object, "propSet") and object.propSet:
            if object.propSet[0].val.value == value:
                return object.obj


def _get_object_from_results(session, results, value, func):
    while results:
        object = func(results, value)
        if object:
            session._call_method(vutil, 'cancel_retrieval',
                                 results)
            return object
        results = session._call_method(vutil, 'continue_retrieval',
                                       results)


def _get_vm_ref_from_name(session, vm_name):
    """Get reference to the VM with the name specified.

    This method reads all of the names of the VM's that are running
    on the backend, then it filters locally the matching vm_name.
    It is far more optimal to use _get_vm_ref_from_vm_uuid.
    """
    vms = session._call_method(vim_util, "get_objects",
                "VirtualMachine", ["name"])
    return _get_object_from_results(session, vms, vm_name,
                                    _get_object_for_value)


def get_vm_ref_from_name(session, vm_name):
    return (_get_vm_ref_from_vm_uuid(session, vm_name) or
            _get_vm_ref_from_name(session, vm_name))


def _get_vm_ref_from_vm_uuid(session, instance_uuid):
    """Get reference to the VM.

    The method will make use of FindAllByUuid to get the VM reference.
    This method finds all VM's on the backend that match the
    instance_uuid, more specifically all VM's on the backend that have
    'config_spec.instanceUuid' set to 'instance_uuid'.
    """
    vm_refs = session._call_method(
        session.vim,
        "FindAllByUuid",
        session.vim.service_content.searchIndex,
        uuid=instance_uuid,
        vmSearch=True,
        instanceUuid=True)
    if vm_refs:
        return vm_refs[0]


def _get_vm_ref_from_extraconfig(session, instance_uuid):
    """Get reference to the VM with the uuid specified."""
    vms = session._call_method(vim_util, "get_objects",
                "VirtualMachine", ['config.extraConfig["nvp.vm-uuid"]'])
    return _get_object_from_results(session, vms, instance_uuid,
                                     _get_object_for_optionvalue)


def get_vm_ref(session, instance):
    """Get reference to the VM through uuid or vm name."""
    uuid = instance.uuid
    vm_ref = (search_vm_ref_by_identifier(session, uuid) or
              _get_vm_ref_from_name(session, instance.name))
    if vm_ref is None:
        raise exceptions.InstanceNotFound(instance_id=uuid)
    return vm_ref


def search_vm_ref_by_identifier(session, identifier):
    """Searches VM reference using the identifier.

    This method is primarily meant to separate out part of the logic for
    vm_ref search that could be use directly in the special case of
    migrating the instance. For querying VM linked to an instance always
    use get_vm_ref instead.
    """
    vm_ref = (_get_vm_ref_from_vm_uuid(session, identifier) or
              _get_vm_ref_from_extraconfig(session, identifier) or
              _get_vm_ref_from_name(session, identifier))
    return vm_ref


def get_vm_state(session, instance):
    vm_ref = get_vm_ref(session, instance)
    vm_state = session._call_method(vutil, "get_object_property",
                                    vm_ref, "runtime.powerState")
    return constants.POWER_STATES[vm_state]


def get_vmdk_backed_disk_device(hardware_devices, uuid):
    if hardware_devices.__class__.__name__ == "ArrayOfVirtualDevice":
        hardware_devices = hardware_devices.VirtualDevice

    for device in hardware_devices:
        if (device.__class__.__name__ == "VirtualDisk" and
                device.backing.__class__.__name__ ==
                "VirtualDiskFlatVer2BackingInfo" and
                device.backing.uuid == uuid):
            return device


def get_vmdk_volume_disk(hardware_devices, path=None):
    if hardware_devices.__class__.__name__ == "ArrayOfVirtualDevice":
        hardware_devices = hardware_devices.VirtualDevice

    for device in hardware_devices:
        if (device.__class__.__name__ == "VirtualDisk"):
            if not path or path == device.backing.fileName:
                return device


def get_res_pool_ref(session, cluster):
    """Get the resource pool."""
    # Get the root resource pool of the cluster
    res_pool_ref = session._call_method(vutil,
                                        "get_object_property",
                                        cluster,
                                        "resourcePool")
    return res_pool_ref


def get_all_cluster_mors(session):
    """Get all the clusters in the vCenter."""
    try:
        results = session._call_method(vim_util, "get_objects",
                                        "ClusterComputeResource", ["name"])
        session._call_method(vutil, 'cancel_retrieval',
                             results)
        if results.objects is None:
            return []
        else:
            return results.objects

    except Exception as excep:
        LOG.warning("Failed to get cluster references %s", excep)


def get_cluster_ref_by_name(session, cluster_name):
    """Get reference to the vCenter cluster with the specified name."""
    all_clusters = get_all_cluster_mors(session)
    for cluster in all_clusters:
        if (hasattr(cluster, 'propSet') and
                    cluster.propSet[0].val == cluster_name):
            return cluster.obj


def get_vmdk_adapter_type(adapter_type):
    """Return the adapter type to be used in vmdk descriptor.

    Adapter type in vmdk descriptor is same for LSI-SAS, LSILogic & ParaVirtual
    because Virtual Disk Manager API does not recognize the newer controller
    types.
    """
    if adapter_type in [constants.ADAPTER_TYPE_LSILOGICSAS,
                        constants.ADAPTER_TYPE_PARAVIRTUAL]:
        vmdk_adapter_type = constants.DEFAULT_ADAPTER_TYPE
    else:
        vmdk_adapter_type = adapter_type
    return vmdk_adapter_type


def _get_vm_port_indices(session, vm_ref):
    extra_config = session._call_method(vutil,
                                        'get_object_property',
                                        vm_ref,
                                        'config.extraConfig')
    ports = []
    if extra_config is not None:
        options = extra_config.OptionValue
        for option in options:
            if (option.key.startswith('nvp.iface-id.') and
                    option.value != 'free'):
                ports.append(int(option.key.split('.')[2]))
    return ports


def get_ephemerals(session, vm_ref):
    devices = []
    hardware_devices = session._call_method(vutil,
                                            "get_object_property",
                                            vm_ref,
                                            "config.hardware.device")

    if hardware_devices.__class__.__name__ == "ArrayOfVirtualDevice":
        hardware_devices = hardware_devices.VirtualDevice

    for device in hardware_devices:
        if device.__class__.__name__ == "VirtualDisk":
            if (device.backing.__class__.__name__ ==
                    "VirtualDiskFlatVer2BackingInfo"):
                if 'ephemeral' in device.backing.fileName:
                    devices.append(device)
    return devices


def get_swap(session, vm_ref):
    hardware_devices = session._call_method(vutil, "get_object_property",
                                            vm_ref, "config.hardware.device")

    if hardware_devices.__class__.__name__ == "ArrayOfVirtualDevice":
        hardware_devices = hardware_devices.VirtualDevice

    for device in hardware_devices:
        if (device.__class__.__name__ == "VirtualDisk" and
                device.backing.__class__.__name__ ==
                    "VirtualDiskFlatVer2BackingInfo" and
                'swap' in device.backing.fileName):
            return device







