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

from journal_brief.format import get_formatter
import journal_brief.format.reboot  # registers class; # flake8: noqa


class TestRebootEntryFormatter(object):
    def test_reboot(self):
        formatter = get_formatter('reboot')
        assert formatter.format({'_BOOT_ID': '1'}) == ''
        assert formatter.format({'_BOOT_ID': '2'}) == '-- Reboot --\n'
        assert formatter.format({'_BOOT_ID': '2'}) == ''
        assert formatter.flush() == ''
