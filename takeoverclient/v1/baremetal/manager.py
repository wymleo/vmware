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

from os_client_config import config as cloud_config
from oslo_log import log

from takeoverclient.common import exceptions
from takeoverclient.common import flow_utils
from takeoverclient.virt import driver
from takeoverclient.flows import baremetal_flows as bm_flows

BAREMETAL_DRIVER = 'baremetal.driver.BareMetalDriver'

LOG = log.getLogger(__name__)


class BareMetalManager(object):
    def __init__(self):
        self.bm_driver = None
        self.conf = cloud_config.OpenStackConfig().get_one_cloud(
            cloud="takeover").config

    def adopt(self, client, host_list_file, network_id):
        if not self.bm_driver:
            self.bm_driver = driver.load_virt_driver(BAREMETAL_DRIVER, self.conf)
        adopt_flow = bm_flows.adopt_hosts_flow(
            self.bm_driver, self.conf, client, host_list_file, network_id)

        with flow_utils.DynamicLogListener(adopt_flow, logger=LOG):
            adopt_flow.run()


class NovaAdoptManager(object):
    def __init__(self, api_client):
        super(NovaAdoptManager, self).__init__()
        self.client = api_client.client
        self.conf = cloud_config.OpenStackConfig().get_one_cloud(
            cloud="takeover").config

    def adopt(self, host):
        tags = ['baremetal', 'manage']
        if not host.ipmi_ip:
            tags.append('without_ipmi')

        kwargs = {'body': {
            'managed_baremetal': {
                'name': host.node_name,
                'node_id': host.node_id,
                'imageRef': self.conf['baremetal']['image_source'],
                'flavorRef': host.flavor_id,
                'availability_zone': self.conf['baremetal']['adopt_az'],
                'metadata': {},
                'tags': tags,
                'project_id': self.conf['baremetal']['adopt_user_id'],
                'user_id': self.conf['baremetal']['adopt_project_id'],
                'networks': [{
                    'uuid': host.network_id,
                    'fixed_ip': host.ip,
                    'macs': host.mac
                }]
            }
        }}

        rsp, body = self.client.post('/managedbaremetal', **kwargs)
        if rsp.status_code != 202:
            raise exceptions.AdoptError(rsp.status, rsp.reason)
