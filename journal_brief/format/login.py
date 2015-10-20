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

from collections import defaultdict
from journal_brief.format import EntryFormatter
import logging


log = logging.getLogger(__name__)


class LoginFormatter(EntryFormatter):
    """
    Show a summary of login sessions
    """

    FORMAT_NAME = "login"
    FILTER_INCLUSIONS = [
        {
            # New session
            'MESSAGE_ID': ['8d45620c1a4348dbb17410da57c60c66'],
            '_COMM': ['systemd-logind'],
        },
    ]

    def __init__(self, *args, **kwargs):
        super(LoginFormatter, self).__init__(*args, **kwargs)
        self.login = defaultdict(int)

    def format(self, entry):
        if 'USER_ID' not in entry:
            return ''

        self.login[entry['USER_ID']] += 1
        return ''

    def flush(self):
        if not self.login:
            return ''

        ret = '\nUser logins:\n\n'
        logins = list(self.login.items())
        logins.sort()
        for user, count in logins:
            ret += '{count:>5} x {user}\n'.format(user=user, count=count)

        return ret
