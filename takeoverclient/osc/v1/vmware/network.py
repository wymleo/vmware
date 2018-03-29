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


"""Mogan v1 Baremetal server action implementations"""

import io
import json
import logging
import os

from osc_lib.cli import parseractions
from osc_lib.command import command
from osc_lib import utils as oscutils
from osc_lib import exceptions
from osc_lib import utils

from takeoverclient.common.i18n import _

LOG = logging.getLogger(__name__)

RESOURCES = ['portgroup', 'flavor', 'instance']


class TakeOverNetwork(command.Command):
    """Takeover a vCenter Server cluster"""

    log = logging.getLogger(__name__ + ".TakeoverVmwareNetwork")

    def get_parser(self, prog_name):
        parser = super(TakeOverNetwork, self).get_parser(prog_name)

        parser.add_argument(
            'cluster',
            metavar='<cluster>',
            help=_("Name of the cluster.")
        )

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        takeover_client = self.app.client_manager.takeover_tool
        takeover_client.vmware_cluster_manager.takeover(takeover_client,
                                                        parsed_args.cluster)


class ValidateNetwork(command.Command):
    log = logging.getLogger(__name__ + ".ValidateVmwareNetwork")

    def get_parser(self, prog_name):
        parser = super(ValidateNetwork, self).get_parser(prog_name)

        parser.add_argument(
            'cluster',
            metavar='<cluster>',
            help=_("Name of the cluster.")
        )

        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        takeover_client = self.app.client_manager.takeover_tool
        takeover_client.vmware_cluster_manager.validate(takeover_client,
                                                        parsed_args.cluster)