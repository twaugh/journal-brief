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
import journal_brief.format.login  # registers class; # flake8: noqa
from uuid import UUID


class TestLoginEntryFormatter(object):
    def test_no_logins(self):
        formatter = get_formatter('login')
        assert formatter.flush() == ''

    def test_login(self):
        formatter = get_formatter('login')
        base = formatter.FILTER_INCLUSIONS[0].copy()
        base['MESSAGE_ID'] = [UUID(uuid) for uuid in base['MESSAGE_ID']]
        for user in ['user1', 'user2', 'user1']:
            entry = base.copy()
            entry['USER_ID'] = user
            assert formatter.format(entry) == ''

        assert formatter.flush().splitlines() == [
            '',
            'User logins:',
            '',
            '    2 x user1',
            '    1 x user2',
        ]
