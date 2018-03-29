# Copyright 2016 Huawei Technologies Co.,LTD.
# All Rights Reserved.

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

import base64
import gzip
import shutil
import tempfile
import traceback

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
import six
import taskflow.engines
from taskflow.patterns import linear_flow

from takeoverclient.common import exceptions
from takeoverclient.common import flow_utils

LOG = logging.getLogger(__name__)

ACTION = 'validate:instance'
CONF = cfg.CONF


class ListVirtInstancesTask(flow_utils.TakeoverTask):
    """Get all vmware instances from vCenter Server"""
    def __init__(self, virt_driver):
        super(ListVirtInstancesTask, self).__init__('list_instances',
                                                    provides='virt_instances')
        self.driver = virt_driver

    def execute(self):
        instances = self.driver.list_instances()
        LOG.debug("The virt instances in the cluster are %s", instances)
        return {'virt_instances': instances}

    def revert(self, result, flow_failures):
        pass


class ListVirtNetworksTask(flow_utils.TakeoverTask):
    """Get all vmware networks from vCenter Server"""
    def __init__(self, virt_driver):
        super(ListVirtNetworksTask, self).__init__('list_networks',
                                                    provides='virt_networks')
        self.driver = virt_driver

    def execute(self):
        networks = self.driver.get_networks()
        return {'virt_networks': networks}

    def revert(self, result, flow_failures):
        pass


class GetVirtInstanceTask(flow_utils.TakeoverTask):
    """Get all vmware instances from vCenter Server"""
    def __init__(self, virt_driver):
        super(GetVirtInstanceTask, self).__init__('list_instances',
                                                    provides='virt_instances')

    def execute(self):
        return self.driver.list_instances()

    def revert(self, result, flow_failures):
        pass


class ValidateNetworksTask(flow_utils.TakeoverTask):
    """Validate whether takeover networks or not"""
    def __init__(self):
        requires=['virt_instances', 'virt_networks']
        super(ValidateNetworksTask, self).__init__('validate_networks',
                                                   requires=requires)
        pass

    def execute(self, virt_instances, virt_networks):
        pass

    def revert(self, virt_instances, virt_networks, result, flow_failures):
        pass


class ValidateInstancesTask(flow_utils.TakeoverTask):
    """Validate whether takeover instances or not"""
    def __init__(self):
        super(ValidateInstancesTask, self).__init__('validate_instances',
                                                    requires=['virt_instances'])
        pass

    def execute(self, virt_instances):
        pass

    def revert(self, virt_instances, result, flow_failures):
        pass


class ManageFlavorsTask(flow_utils.TakeoverTask):
    """Manage instance flavors in a cluster"""
    def __init__(self, client):
        super(ManageFlavorsTask, self).__init__('manage_instances',
                                                requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, virt_instances, result, flow_failures):
        pass


class ManageNetworksTask(flow_utils.TakeoverTask):
    """Manage networks in a cluster"""
    def __init__(self, client):
        super(ManageNetworksTask, self).__init__('manage_networks',
                                                requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, result, flow_failures):
        pass


class ManageImagesTask(flow_utils.TakeoverTask):
    """Manage images in a cluster"""
    def __init__(self, client):
        super(ManageImagesTask, self).__init__('manage_networkss',
                                              requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, result, flow_failures):
        pass


class ManageInstancesTask(flow_utils.TakeoverTask):
    """Manage instances in a cluster"""
    def __init__(self, client):
        super(ManageInstancesTask, self).__init__('manage_instances',
                                                  requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, result, flow_failures):
        pass


class ManageFlavorTask(flow_utils.TakeoverTask):
    """Manage a flavor in a cluster"""
    def __init__(self, client):
        super(ManageFlavorTask, self).__init__('validate_instances',
                                                requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, result, flow_failures):
        pass


class ManageNetworkTask(flow_utils.TakeoverTask):
    """Manage a network in a cluster"""
    def __init__(self, client):
        super(ManageNetworkTask, self).__init__('validate_instances',
                                                requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, result, flow_failures):
        pass


class ManageInstanceTask(flow_utils.TakeoverTask):
    """Manage a instance in a cluster"""
    def __init__(self, client):
        super(ManageInstanceTask, self).__init__('manage_instances',
                                                  requires=['virt_instances'])

        pass

    def execute(self, virt_instances):
        pass

    def revert(self, result, flow_failures):
        pass


def get_validate_cluster_flow(driver):

    """Constructs and returns the manager entrypoint flow

    This flow will do the following:

    1. Get all vms from a cluster of vCenter server.
    2. validate the policy of .
    3. Do node deploy and handle errors.
    4. Reschedule if the tasks are on failure.
    """

    flow_name = "validate_cluster_flow"
    server_flow = linear_flow.Flow(flow_name)

    # This injects the initial starting flow values into the workflow so that
    # the dependency order of the tasks provides/requires can be correctly
    # determined.
    create_what = {

    }

    server_flow.add(ListVirtInstancesTask(driver),
                    ListVirtNetworksTask(driver),
                    ValidateNetworksTask(),
                    ValidateInstancesTask())

    # Now load (but do not run) the flow using the provided initial data.
    return taskflow.engines.load(server_flow, store=create_what)


def get_takeover_cluster_flow(driver, client):

    """Constructs and returns the manager entrypoint flow

    This flow will do the following:

    1. Get all vms from a cluster of vCenter server.
    2. validate the policy of .
    3. Do node deploy and handle errors.
    4. Reschedule if the tasks are on failure.
    """

    flow_name = "takeover_cluster_flow"
    server_flow = linear_flow.Flow(flow_name)

    # This injects the initial starting flow values into the workflow so that
    # the dependency order of the tasks provides/requires can be correctly
    # determined.
    create_what = {

    }

    server_flow.add(ListVirtInstancesTask(driver),
                    ListVirtNetworksTask(driver),
                    ManageFlavorsTask(client),
                    ManageImagesTask(client),
                    ManageNetworksTask(client),
                    ManageInstancesTask(client))

    # Now load (but do not run) the flow using the provided initial data.
    return taskflow.engines.load(server_flow, store=create_what)


def get_validate_instance_flow(driver, client):

    """Constructs and returns the manager entrypoint flow

    This flow will do the following:

    1. Get all vms from a cluster of vCenter server.
    2. validate the policy of .
    3. Do node deploy and handle errors.
    4. Reschedule if the tasks are on failure.
    """

    flow_name = "takeover_cluster_flow"
    server_flow = linear_flow.Flow(flow_name)

    # This injects the initial starting flow values into the workflow so that
    # the dependency order of the tasks provides/requires can be correctly
    # determined.
    create_what = {

    }

    server_flow.add(ListVirtInstancesTask(driver),
                    ListVirtNetworksTask(driver),
                    ManageFlavorsTask(client),
                    ManageImagesTask(client),
                    ManageNetworksTask(client),
                    ManageInstancesTask(client))

    # Now load (but do not run) the flow using the provided initial data.
    return taskflow.engines.load(server_flow, store=create_what)


def get_takeover_instance_flow(driver, client):

    """Constructs and returns the manager entrypoint flow

    This flow will do the following:

    1. Get all vms from a cluster of vCenter server.
    2. validate the policy of .
    3. Do node deploy and handle errors.
    4. Reschedule if the tasks are on failure.
    """

    flow_name = "takeover_instance_flow"
    server_flow = linear_flow.Flow(flow_name)

    # This injects the initial starting flow values into the workflow so that
    # the dependency order of the tasks provides/requires can be correctly
    # determined.
    create_what = {

    }

    server_flow.add(GetVirtInstanceTask(driver),
                    ListVirtNetworksTask(driver),
                    ManageFlavorsTask(client),
                    ManageImagesTask(client),
                    ManageNetworksTask(client),
                    ManageInstancesTask(client))

    # Now load (but do not run) the flow using the provided initial data.
    return taskflow.engines.load(server_flow, store=create_what)