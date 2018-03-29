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

from osc_lib.command import command
from takeoverclient.common.i18n import _


LOG = logging.getLogger(__name__)

RESOURCES = ['host']


class BareMentalAdopt(command.Command):
    """Adopt baremetal host."""
    log = logging.getLogger(__name__ + '.BareMentalAdopt')

    def get_parser(self, prog_name):
        parser = super(BareMentalAdopt, self).get_parser(prog_name)

        parser.add_argument(
            '--host-list-file',
            metavar='<hosts-list-file>',
            required=True,
            help=_('Hosts list spec file.')
        )

        parser.add_argument(
            '--network-id',
            metavar='<network-id>',
            required=True,
            help=_('Hosts network ID')
        )

        return parser

    def take_action(self, parsed_args):
        self.log.debug('take_action (%s)', parsed_args)
        takeover_client = self.app.client_manager.takeover_tool
        takeover_client.baremetal_manager.adopt(takeover_client,
                                                parsed_args.host_list_file,
                                                parsed_args.network_id)
