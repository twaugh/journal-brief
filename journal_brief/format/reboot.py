"""
Copyright (c) 2015 Tim Waugh <tim@cyberelk.net>

## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

from journal_brief.format import EntryFormatter
import logging


log = logging.getLogger(__name__)


class RebootFormatter(EntryFormatter):
    """
    Display a message on each reboot

    Only shows reboots between entries that are to be shown.
    """

    FORMAT_NAME = 'reboot'

    def __init__(self, *args, **kwargs):
        super(RebootFormatter, self).__init__(*args, **kwargs)
        self.this_boot_id = None

    def format(self, entry):
        try:
            boot_id = entry['_BOOT_ID']
        except KeyError:
            return ''
        else:
            reboot = (self.this_boot_id is not None and
                      self.this_boot_id != boot_id)
            self.this_boot_id = boot_id

            if reboot:
                return '-- Reboot --\n'

        return ''
