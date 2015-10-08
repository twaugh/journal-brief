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

from datetime import datetime, timezone, timedelta
from journal_brief.format import get_formatter
import pytest


class TestShortEntryFormatter(object):
    def test_timestamp(self):
        dt = datetime.fromtimestamp(0, tz=timezone(timedelta(hours=1)))
        entry = {'__REALTIME_TIMESTAMP': dt,
                 'MESSAGE': 'epoch'}

        formatter = get_formatter('short')

        # Should output in local time
        expected = 'Jan 01 01:00:00'

        assert expected in formatter.format(entry)

    @pytest.mark.parametrize(('entry', 'expected'), [
        ({'MESSAGE': 'message'},
         'localhost ?: message\n'),

        ({'_HOSTNAME': 'host',
          'MESSAGE': 'message'},
         'host ?: message\n'),

        ({'_HOSTNAME': 'host',
          '_COMM': 'comm',
          'MESSAGE': 'message'},
         'host comm: message\n'),

        ({'_HOSTNAME': 'host',
          '_COMM': 'comm',
          '_PID': '1',
          'MESSAGE': 'message'},
         'host comm[1]: message\n'),

        ({'_HOSTNAME': 'host',
          'SYSLOG_IDENTIFIER': 'syslogid',
          '_COMM': 'comm',
          'MESSAGE': 'message'},
         'host syslogid: message\n'),

        ({'_HOSTNAME': 'host',
          'SYSLOG_IDENTIFIER': 'syslogid',
          '_PID': '1',
          'MESSAGE': 'message'},
         'host syslogid[1]: message\n'),
    ])
    def test_format(self, entry, expected):
        entry['__REALTIME_TIMESTAMP'] = datetime.fromtimestamp(0,
                                                               tz=timezone.utc)
        formatter = get_formatter('short')
        formatted = formatter.format(entry)
        date = 'Jan 01 00:00:00 '
        assert formatted.startswith(date)
        assert formatted[len(date):] == expected
