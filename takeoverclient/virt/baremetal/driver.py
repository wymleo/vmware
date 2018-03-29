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
from takeoverclient.virt import driver
from takeoverclient.virt.baremetal import collector


class BareMetalDriver(driver.VirtDriver):
    def __init__(self, conf):
        super(BareMetalDriver, self).__init__()
        self.conf = conf

    def get_hosts_configs(self, hosts_conf, hosts_detail, network_id):
        host_manager = collector.HostManager(self.conf,
                                             hosts_conf,
                                             hosts_detail,
                                             network_id)
        return host_manager.execute()
