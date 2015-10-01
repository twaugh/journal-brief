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
import functools
from inspect import getsourcefile
import journal_brief
from journal_brief import SelectiveReader, LatestJournalEntries, EntryFormatter
from systemd import journal
import os
import pytest
import re


class Watcher(object):
    def __init__(self):
        self.calls = []

    @property
    def calls_args_only(self):
        return [call[:-1] for call in self.calls]

    def watch_call(self, func):
        return functools.partial(self.called, func)

    def called(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))


class TestSelectiveReader(object):
    @pytest.mark.xfail
    def test_inclusions(self):
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))
        watcher = Watcher()
        (flexmock(journal.Reader)
            .should_receive('add_match')
            .replace_with(watcher.watch_call('add_match')))
        (flexmock(journal.Reader)
            .should_receive('add_conjunction')
            .replace_with(watcher.watch_call('add_conjunction')))
        (flexmock(journal.Reader)
            .should_receive('add_disjunction')
            .replace_with(watcher.watch_call('add_disjunction')))

        inclusions = [{'PRIORITY': ['0', '1', '2', '3']},
                      {'PRIORITY': ['4', '5', '6'],
                       '_SYSTEMD_UNIT': ['myservice.service']}]
        reader = SelectiveReader(inclusions=inclusions)

        # Should add matches for all of the first group
        assert set(watcher.calls_args_only[:4]) == set([
            ('add_match', ('PRIORITY=0',)),
            ('add_match', ('PRIORITY=1',)),
            ('add_match', ('PRIORITY=2',)),
            ('add_match', ('PRIORITY=3',)),
        ])

        # Then a disjunction
        assert watcher.calls[4] == ('add_disjunction', (), {})

        # Then matches for all of the second group
        assert set(watcher.calls_args_only[5:9]) == set([
            ('add_match', ('PRIORITY=4',)),
            ('add_match', ('PRIORITY=5',)),
            ('add_match', ('PRIORITY=6',)),
            ('add_match', ('_SYSTEMD_UNIT=myservice.service',)),
        ])

        # And a final disjunction
        assert watcher.calls[9] == ('add_disjunction', (), {})


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

    def test_this_boot(self, tmpdir):
        last_cursor = '2'
        final_cursor = '3'
        results = [{'__CURSOR': '1'},
                   {'__CURSOR': last_cursor},
                   {'__CURSOR': final_cursor}]

        (flexmock(journal.Reader)
            .should_receive('seek_cursor')
            .never())
        (flexmock(journal.Reader)
            .should_receive('this_boot')
            .once())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(results[0])
            .and_return(results[1])
            .and_return(results[2])
            .and_return({}))

        cursor_file = os.path.join(str(tmpdir), 'cursor')
        with open(cursor_file, 'wt') as fp:
            fp.write(last_cursor)

        with LatestJournalEntries(cursor_file=cursor_file,
                                  this_boot=True) as entries:
            e = list(entries)

        assert e == results
        with open(cursor_file, 'rt') as fp:
            fp.read() == final_cursor


class TestEntryFormatter(object):
    def test_timestamp(self):
        dt = datetime.fromtimestamp(0, tz=timezone(timedelta(hours=1)))
        entry = {'__REALTIME_TIMESTAMP': dt,
                 'MESSAGE': 'epoch'}

        formatter = EntryFormatter()

        # Should output in local time
        expected = 'Jan 01 01:00:00'

        assert expected in formatter.format(entry)

    @pytest.mark.parametrize(('entry', 'expected'), [
        ({'MESSAGE': 'message'},
         'localhost ?: message'),

        ({'_HOSTNAME': 'host',
          'MESSAGE': 'message'},
         'host ?: message'),

        ({'_HOSTNAME': 'host',
          '_COMM': 'comm',
          'MESSAGE': 'message'},
         'host comm: message'),

        ({'_HOSTNAME': 'host',
          '_COMM': 'comm',
          '_PID': '1',
          'MESSAGE': 'message'},
         'host comm[1]: message'),

        ({'_HOSTNAME': 'host',
          'SYSLOG_IDENTIFIER': 'syslogid',
          '_COMM': 'comm',
          'MESSAGE': 'message'},
         'host syslogid: message'),

        ({'_HOSTNAME': 'host',
          'SYSLOG_IDENTIFIER': 'syslogid',
          '_PID': '1',
          'MESSAGE': 'message'},
         'host syslogid[1]: message'),
    ])
    def test_format(self, entry, expected):
        entry['__REALTIME_TIMESTAMP'] = datetime.fromtimestamp(0,
                                                               tz=timezone.utc)
        formatter = EntryFormatter()
        formatted = formatter.format(entry)
        date = 'Jan 01 00:00:00 '
        assert formatted.startswith(date)
        assert formatted[len(date):] == expected


def test_version():
    """
    Check the version numbers agree
    """
    this_file = getsourcefile(test_version)
    regexp = re.compile(r"\s+version='([0-9.]+)',  # also update")
    with open(os.path.join(os.path.dirname(this_file), '../setup.py')) as fp:
        matches = map(regexp.match, fp.readlines())
        matches = [match for match in matches if match]
        assert len(matches) == 1
        assert matches[0].groups()[0] == journal_brief.__version__
