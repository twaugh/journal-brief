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
import journal_brief.format.systemd  # registers class; # noqa: F401
import locale


class TestSystemdEntryFormatter(object):
    def test_no_failed_units(self):
        formatter = get_formatter('systemd')
        assert formatter.flush() == ''

    def test_systemd(self):
        # check locale-aware sorting
        for lc in ('en_US.UTF.8', 'en_US'):
            try:
                locale.setlocale(locale.LC_ALL, lc)
                break
            except locale.Error:
                pass

        formatter = get_formatter('systemd')
        base = formatter.FILTER_INCLUSIONS[0].copy()
        for unit in ['unit1', 'unit2', 'unit1', 'Unit3']:
            entry = base.copy()
            entry.update({
                'MESSAGE': 'Unit %s.service entered failed state.' % unit,
                'UNIT': '%s.service' % unit,
            })
            assert formatter.format(entry) == ''

        assert formatter.flush().splitlines() == [
            '',
            'Failed systemd units:',
            '',
            '    2 x unit1.service',
            '    1 x unit2.service',
            '    1 x Unit3.service',
        ]
