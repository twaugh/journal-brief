#!/usr/bin/python3
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
from flexmock import flexmock
from journal_brief import LatestJournalEntries, EntryFormatter
from systemd import journal
import os


class TestLatestJournalEntries(object):
    def test_without_cursor(self, tmpdir):
        final_cursor = '2'
        (flexmock(journal.Reader)
            .should_receive('seek_cursor')
            .never())
        (flexmock(journal.Reader)
            .should_receive('this_boot')
            .once())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1'})
            .and_return({'__CURSOR': final_cursor})
            .and_return({}))

        cursor_file = os.path.join(str(tmpdir), 'cursor')
        with LatestJournalEntries(cursor_file=cursor_file) as entries:
            e = list(entries)

        assert len(e) == 2
        with open(cursor_file, 'rt') as fp:
            assert fp.read() == final_cursor

    def test_with_cursor(self, tmpdir):
        last_cursor = '2'
        final_cursor = '4'
        results = [{'__CURSOR': last_cursor},
                   {'__CURSOR': '3'},
                   {'__CURSOR': final_cursor}]
        (flexmock(journal.Reader)
            .should_receive('seek_cursor')
            .with_args(last_cursor)
            .once())
        (flexmock(journal.Reader)
            .should_receive('this_boot')
            .never())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(results[0])
            .and_return(results[1])
            .and_return(results[2])
            .and_return({}))

        cursor_file = os.path.join(str(tmpdir), 'cursor')
        with open(cursor_file, 'wt') as fp:
            fp.write(last_cursor)

        with LatestJournalEntries(cursor_file=cursor_file) as entries:
            e = list(entries)

        assert e == results[1:]
        with open(cursor_file, 'rt') as fp:
            assert fp.read() == final_cursor        


class TestEntryFormatter(object):
    def test_timestamp(self):
        dt = datetime.fromtimestamp(0, tz=timezone(timedelta(hours=1)))
        entry = {'__REALTIME_TIMESTAMP': dt,
                 'MESSAGE': 'epoch'}

        formatter = EntryFormatter()

        # Should output in local time
        expected = 'Jan 01 01:00:00 epoch'

        assert formatter.format(entry) == expected
