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
from io import StringIO
from journal_brief.format import get_formatter
import journal_brief.format.json  # registers class; # flake8: noqa
import json
import pytest
import uuid

from tests.util import maybe_mock_systemd
maybe_mock_systemd()

from systemd import journal


class TestJSONEntryFormatter(object):
    def test_uuid(self):
        """
        Should be string representation of UUID
        """

        entry = {'_BOOT_ID': uuid.uuid1()}
        formatter = get_formatter('json')
        out = json.loads(formatter.format(entry))
        assert out['_BOOT_ID'] == str(entry['_BOOT_ID'])

    def test_timestamp(self):
        """
        Should output microseconds since the epoch
        """

        dt = datetime.fromtimestamp(5, tz=timezone(timedelta(hours=1)))
        entry = {'__REALTIME_TIMESTAMP': dt}
        formatter = get_formatter('json')
        out = json.loads(formatter.format(entry))
        assert out['__REALTIME_TIMESTAMP'] == 5000000

    def test_monotonic(self):
        """
        Should be in microseconds
        """

        us = 700
        elapsed = timedelta(microseconds=us)
        boot_id = uuid.uuid1()
        timestamp = journal.Monotonic((elapsed, boot_id))
        entry = {'__MONOTONIC_TIMESTAMP': timestamp}
        formatter = get_formatter('json')
        out = json.loads(formatter.format(entry))
        assert out['__MONOTONIC_TIMESTAMP'] == us

    @pytest.mark.parametrize(('bdata', 'brepr'), [
        (b'abc', 'abc'),
        (b'\x82\xac', [0x82, 0xac]),
    ])
    def test_bytes(self, bdata, brepr):
        """
        Should decode to unicode or a number array
        """

        entry = {'BDATA': bdata}
        formatter = get_formatter('json')
        out = json.loads(formatter.format(entry))
        assert out['BDATA'] == brepr

    def test_multiline(self):
        """
        Check each entry is formatted as a single output line
        """

        count = 5
        output = StringIO()
        formatter = get_formatter('json')
        for n in range(count):
            output.write(formatter.format({'MESSAGE': 'entry'}))

        output.write(formatter.flush())

        output.seek(0)
        assert len(output.read().splitlines()) == count
