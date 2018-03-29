# Copyright 2011 Justin Santa Barbara
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

"""
Driver base-classes:

    (Beginning of) the contract that compute drivers must follow, and shared
    types that support that contract
"""

import sys

from os_client_config import config as cloud_config
from oslo_log import log as logging
from oslo_utils import importutils
from takeoverclient.common.i18n import _

LOG = logging.getLogger(__name__)


class VirtDriver(object):
    """Base class for compute drivers.

    The interface to this class talks in terms of 'instances' (Amazon EC2 and
    internal Nova terminology), by which we mean 'running virtual machine'
    (XenAPI terminology) or domain (Xen or libvirt terminology).

    An instance has an ID, which is the identifier chosen by Nova to represent
    the instance further up the stack.  This is unfortunately also called a
    'name' elsewhere.  As far as this layer is concerned, 'instance ID' and
    'instance name' are synonyms.

    Note that the instance ID or name is not human-readable or
    customer-controlled -- it's an internal ID chosen by Nova.  At the
    nova.virt layer, instances do not have human-readable names at all -- such
    things are only known higher up the stack.

    Most virtualization platforms will also have their own identity schemes,
    to uniquely identify a VM or domain.  These IDs must stay internal to the
    platform-specific layer, and never escape the connection interface.  The
    platform-specific layer is responsible for keeping track of which instance
    ID maps to which platform-specific ID, and vice versa.

    Some methods here take an instance of nova.compute.service.Instance.  This
    is the data structure used by nova.compute to store details regarding an
    instance, and pass them into this layer.  This layer is responsible for
    translating that generic data structure into terms that are specific to the
    virtualization platform.

    """

    def list_instances(self):
        """Return the names of all the instances known to the virtualization
        layer, as a list.
        """
        # TODO(Vek): Need to pass context in for access to auth_token
        raise NotImplementedError()

    def get_networks(self):
        """Return the UUIDS of all the instances known to the virtualization
        layer, as a list.
        """
        raise NotImplementedError()

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


def load_virt_driver(virt_driver=None, *args, **kwargs):
    """Load a virt driver module.

    Load the virt driver module specified by the virt_driver
    configuration option or, if supplied, the driver name supplied as an
    argument.

    :param virt_driver: a virt driver name to override the config opt
    :returns: a VirtDriver instance
    """
    if not virt_driver:
        conf = cloud_config.OpenStackConfig().get_one_cloud(
            cloud="takeover").config
        virt_driver = conf['default'].get("virt_driver",
                                          "vmwareapi.VMwareVCDriver")

    if not virt_driver:
        LOG.error("Virt driver option required, but not specified")
        sys.exit(1)

    LOG.info("Loading virt driver '%s'", virt_driver)
    try:
        driver = importutils.import_object(
            'takeoverclient.virt.%s' % virt_driver, *args, **kwargs)
        if isinstance(driver, VirtDriver):
            return driver
        raise ValueError()
    except ImportError:
        LOG.exception(_("Unable to load the virtualization driver"))
        sys.exit(1)
    except ValueError:
        LOG.exception("Virt driver '%s' from 'takeoverclient.virt' is not of "
                      "type '%s'", virt_driver, str(VirtDriver))
        sys.exit(1)