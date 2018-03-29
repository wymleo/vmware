#   Copyright 2016 Huawei, Inc. All rights reserved.
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

import logging

import os_client_config

from takeoverclient.virt.baremetal import ironic
from takeoverclient.v1.vmware import manager
from takeoverclient.v1.baremetal import manager as bm_manager

LOG = logging.getLogger(__name__)


class Client(object):
    """Client for the Takeover v1 API."""

    def __init__(self, instance, *args, **kwargs):
        """Initialize a new client for the Mogan v1 API."""
        self.compute = os_client_config.make_client('compute', cloud='takeover')
        self.network = os_client_config.make_client('network', cloud='takeover')
        self.image = os_client_config.make_client('image', cloud='takeover')
        self.ironic = ironic.make_client()
        self.vmware_cluster_manager = manager.ClusterManager()
        self.vmware_instance_manager = manager.InstanceManager()
        self.baremetal_manager = bm_manager.BareMetalManager()
        self.nova_adopt_manager = bm_manager.NovaAdoptManager(self.compute)
