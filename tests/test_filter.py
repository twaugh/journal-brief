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

from flexmock import flexmock
from journal_brief import JournalFilter
from journal_brief.filter import Exclusion
import logging
from systemd import journal


logging.basicConfig(level=logging.DEBUG)


class TestExclusion(object):
    def test_and(self):
        exclusion = Exclusion({'MESSAGE': ['exclude this'],
                               'SYSLOG_IDENTIFIER': ['from this']})
        assert exclusion.matches({'MESSAGE': 'exclude this',
                                  'SYSLOG_IDENTIFIER': 'from this',
                                  'IGNORE': 'ignore this'})
        assert not exclusion.matches({'MESSAGE': 'exclude this'})

    def test_or(self):
        exclusion = Exclusion({'MESSAGE': ['exclude this', 'or this']})
        assert exclusion.matches({'MESSAGE': 'exclude this',
                                  'IGNORE': 'ignore this'})
        assert not exclusion.matches({'MESSAGE': 'not this',
                                      'IGNORE': 'ignore this'})

    def test_and_or(self):
        exclusion = Exclusion({'MESSAGE': ['exclude this', 'or this'],
                               'SYSLOG_IDENTIFIER': ['from this']})
        assert exclusion.matches({'MESSAGE': 'exclude this',
                                  'SYSLOG_IDENTIFIER': 'from this',
                                  'IGNORE': 'ignore this'})
        assert not exclusion.matches({'MESSAGE': 'exclude this',
                                      'SYSLOG_IDENTIFIER': 'at your peril',
                                      'IGNORE': 'ignore this'})


class TestJournalFilter(object):
    def test_no_exclusions(self):
        entries = [{'MESSAGE': 'message 1'},
                   {'MESSAGE': 'message 2'}]
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entries[0])
            .and_return(entries[1])
            .and_return({}))

        filter = JournalFilter(journal.Reader())
        assert list(filter) == entries

    def test_exclusion(self):
        entries = [{'MESSAGE': 'exclude this',
                    'SYSLOG_IDENTIFIER': 'from here'},

                   {'MESSAGE': 'message 1',
                    'SYSLOG_IDENTIFIER': 'foo'},

                   {'MESSAGE': 'exclude this',
                    'SYSLOG_IDENTIFIER': 'at your peril'},

                   {'MESSAGE': 'message 2'}]

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entries[0])
            .and_return(entries[1])
            .and_return(entries[2])
            .and_return(entries[3])
            .and_return({}))
        exclusions = [{'MESSAGE': ['exclude this',
                                   'and this'],
                       'SYSLOG_IDENTIFIER': ['from here']}]
        filter = JournalFilter(journal.Reader(), exclusions=exclusions)
        assert list(filter) == entries[1:]
