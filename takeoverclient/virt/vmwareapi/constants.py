# Copyright (c) 2014 VMware, Inc.
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
Shared constants across the VMware driver
"""

from nova.compute import power_state

MIN_VC_VERSION = '5.1.0'
NEXT_MIN_VC_VERSION = '5.5.0'
# The minimum VC version for Neutron 'ovs' port type support
MIN_VC_OVS_VERSION = '5.5.0'

DISK_FORMAT_ISO = 'iso'
DISK_FORMAT_VMDK = 'vmdk'
DISK_FORMAT_ISCSI = 'iscsi'
DISK_FORMATS_ALL = [DISK_FORMAT_ISO, DISK_FORMAT_VMDK]

DISK_TYPE_THIN = 'thin'
CONTAINER_FORMAT_BARE = 'bare'
CONTAINER_FORMAT_OVA = 'ova'
CONTAINER_FORMATS_ALL = [CONTAINER_FORMAT_BARE, CONTAINER_FORMAT_OVA]

DISK_TYPE_SPARSE = 'sparse'
DISK_TYPE_PREALLOCATED = 'preallocated'
DISK_TYPE_STREAM_OPTIMIZED = 'streamOptimized'
DISK_TYPE_EAGER_ZEROED_THICK = 'eagerZeroedThick'

DATASTORE_TYPE_VMFS = 'VMFS'
DATASTORE_TYPE_NFS = 'NFS'
DATASTORE_TYPE_NFS41 = 'NFS41'
DATASTORE_TYPE_VSAN = 'vsan'

DEFAULT_OS_TYPE = "otherGuest"
DEFAULT_ADAPTER_TYPE = "lsiLogic"
DEFAULT_DISK_TYPE = DISK_TYPE_PREALLOCATED
DEFAULT_DISK_FORMAT = DISK_FORMAT_VMDK
DEFAULT_CONTAINER_FORMAT = CONTAINER_FORMAT_BARE

IMAGE_VM_PREFIX = "OSTACK_IMG"
SNAPSHOT_VM_PREFIX = "OSTACK_SNAP"

ADAPTER_TYPE_BUSLOGIC = "busLogic"
ADAPTER_TYPE_IDE = "ide"
ADAPTER_TYPE_LSILOGICSAS = "lsiLogicsas"
ADAPTER_TYPE_PARAVIRTUAL = "paraVirtual"

SCSI_ADAPTER_TYPES = [DEFAULT_ADAPTER_TYPE, ADAPTER_TYPE_LSILOGICSAS,
                      ADAPTER_TYPE_BUSLOGIC, ADAPTER_TYPE_PARAVIRTUAL]

SUPPORTED_FLAT_VARIANTS = ["thin", "preallocated", "thick", "eagerZeroedThick"]

EXTENSION_KEY = 'org.openstack.compute'
EXTENSION_TYPE_INSTANCE = 'instance'

# The max number of devices that can be connected to one adapter
# One adapter has 16 slots but one reserved for controller
SCSI_MAX_CONNECT_NUMBER = 15

# The max number of SCSI adaptors that could be created on one instance.
SCSI_MAX_CONTROLLER_NUMBER = 4

SHUTDOWN = "shutdown"
RUNNING = "running"
SUSPENDED = "suspended"

POWER_STATES = {'poweredOff': SHUTDOWN,
                'poweredOn': RUNNING,
                'suspended': SUSPENDED}
