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

from oslo_log import log

from takeoverclient.common import base
from takeoverclient.common import flow_utils
from takeoverclient.flows import vmware_flows
from takeoverclient.virt import driver

VMWARE_VIRT_DRIVER = 'vmwareapi.VMwareVCDriver'

LOG = log.getLogger(__name__)


class Server(base.Resource):
    pass


class ClusterManager(object):
    def __init__(self):
        self.virt_driver = None

    def validate(self, cluster):
        if not self.virt_driver:
            self.virt_driver = driver.load_virt_driver(VMWARE_VIRT_DRIVER,
                                                       cluster=cluster)
        validate_flow = vmware_flows.get_validate_cluster_flow(
            self.virt_driver)

        with flow_utils.DynamicLogListener(validate_flow, logger=LOG):
            validate_flow.run()

    def takeover(self, client, cluster):
        if not self.virt_driver:
            self.virt_driver = driver.load_virt_driver(VMWARE_VIRT_DRIVER,
                                                       cluster=cluster)
        validate_flow = vmware_flows.get_takeover_cluster_flow(
            self.virt_driver, client)

        with flow_utils.DynamicLogListener(validate_flow, logger=LOG):
            validate_flow.run()


class InstanceManager(object):
    def __init__(self):
        self.virt_driver = None

    def validate(self, cluster, instance):
        if not self.virt_driver:
            self.virt_driver = driver.load_virt_driver(VMWARE_VIRT_DRIVER,
                                                       cluster=cluster)
        validate_flow = vmware_flows.get_validate_cluster_flow(self.virt_driver)
        with flow_utils.DynamicLogListener(validate_flow, logger=LOG):
            validate_flow.run()

    def takeover(self, client, cluster, instance):
        if not self.virt_driver:
            self.virt_driver = driver.load_virt_driver(VMWARE_VIRT_DRIVER,
                                                       cluster=cluster)
        validate_flow = vmware_flows.get_takeover_instance_flow(
            self.virt_driver, client)
        with flow_utils.DynamicLogListener(validate_flow, logger=LOG):
            validate_flow.run()




