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

import os_client_config

from ironicclient import client
from os_client_config import config as cloud_config


def make_client():
    return Ironic().get_client()


class Ironic(object):
    def __init__(self):
        self.conf = cloud_config.OpenStackConfig().get_one_cloud(
            cloud="takeover").config
        ironic_config = os_client_config.get_config('ironic', cloud='takeover')
        self.session = ironic_config.get_session()
        self.client = None

    def get_client(self):
        if self.client:
            return client

        auth_config = self.conf['auth']
        return client.get_client(
            1, os_project_name=auth_config['project_name'],
            os_auth_url=auth_config['auth_url'],
            project_name=auth_config['username'],
            user_domain_name=auth_config['user_domain_name'],
            project_domain_name=auth_config['project_domain_name'],
            os_ironic_api_version='1.22',
            session=self.session
        )
