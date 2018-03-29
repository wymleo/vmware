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


class VdsOps(object):
    """sss"""

    def __init__(self, session):
        self._session = session
        self._dvs_name = self.get_dvs_name()
        self._dvs_moref = self._get_dvs_moref(self._session, self._dvs_name)


    def _get_dvs_moref(self, session, dvs_name):
        """Get the moref of the configured DVS."""
        results = session.invoke_api(vim_util,
                                     'get_objects',
                                     session.vim,
                                     'DistributedVirtualSwitch',
                                     100)
        return results
        # zhushi: error
        # raise nsx_exc.DvsNotFound(dvs=dvs_name)

    def get_dvs_name(self):
        dvs_name_list = self._session.invoke_api(vim_util,
                                                 'get_objects',
                                                 self._session.vim,
                                                 'DistributedVirtualSwitch',
                                                 100)
        # zhushi:need modify
        dvs_name = dvs_name_list[0][1][1][0].val
        if dvs_name is not None:
            return dvs_name

    def get_port_groups(self):
        pg_configs = []
        pgs = self._session.invoke_api(vim_util,
                                       'get_object_properties',
                                       self._session.vim,
                                       self._dvs_moref.objects[0].obj,
                                       ['portgroup'])

        for pg_obj in pgs['portgroup'].ManagedObjectReference:
            pg_config = self._session.invoke_api(vim_util,
                                                 'get_object_properties_dict',
                                                 self._session.vim,
                                                 pg_obj,
                                                 'config')
            pg_configs.append(pg_config)

        return pg_configs

    def list_networks(self):
        pg_configs = self.get_port_groups()
        networks = []

        for pgc in pg_configs:
            portgroup_key = pgc['config'].key
            name = pgc['config'].name
            dvs_id = pgc['config'].distributedVirtualSwitch.value
            vlan_id = pgc['config'].defaultPortConfig.vlan.vlanId

            network = {"portgroup_key": portgroup_key,
                       "name": name,
                       "dvs_id": dvs_id,
                       "vlan_id": vlan_id}
            networks.append(network)

        return networks

    def get_cidr(self):
        pass

    class NetworkValidate(object):
        def ip_check(self):
            pass

        def mac_chack(self):
            pass

        def vlan_check(self):
            pass

        


