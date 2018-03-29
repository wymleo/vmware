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

from osc_lib import utils

LOG = logging.getLogger(__name__)

DEFAULT_API_VERSION = '1'
API_VERSION_OPTION = 'os_takeover_tool_version'
API_NAME = 'takeover_tool'
API_VERSIONS = {
    '1': 'takeoverclient.v1.client.Client',
}


def make_client(instance):
    """Returns an baremetal service client"""
    takeover_client = utils.get_client_class(
        API_NAME,
        instance._api_version[API_NAME],
        API_VERSIONS)
    LOG.debug('Instantiating takeover-tool client: %s', takeover_client)

    kwargs = {}

    client = takeover_client(instance, **kwargs)

    return client


def build_option_parser(parser):
    """Hook to add global options"""

    return parser
