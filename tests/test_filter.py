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

import tests.util
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

        jfilter = JournalFilter(journal.Reader())
        assert list(jfilter) == entries

    def test_exclusion(self):
        entries = [{'MESSAGE': 'exclude this',
                    'SYSLOG_IDENTIFIER': 'from here'},

                   {'PRIORITY': '6',
                    'MESSAGE': 'exclude this too'},

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
            .and_return(entries[4])
            .and_return({}))
        exclusions = [{'MESSAGE': ['exclude this',
                                   'and this'],
                       'SYSLOG_IDENTIFIER': ['from here']},
                      {'PRIORITY': ['info']}]
        jfilter = JournalFilter(journal.Reader(), exclusions=exclusions)
        assert list(jfilter) == entries[2:]

    def test_exclusion_regexp(self):
        entries = [{'MESSAGE': 'exclude this'},
                   {'MESSAGE': 'message 1'},
                   {'MESSAGE': 'exclude that'},
                   {'MESSAGE': 'message 2'}]

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entries[0])
            .and_return(entries[1])
            .and_return(entries[2])
            .and_return(entries[3])
            .and_return({}))
        exclusions = [{'MESSAGE': ['/1/']},  # shouldn't exclude anything
                      {'MESSAGE': ['/exclude th/']},
                      {'MESSAGE': ['/exclude/']}]
        jfilter = JournalFilter(journal.Reader(), exclusions=exclusions)
        assert list(jfilter) == [entries[1]] + [entries[3]]
        stats = jfilter.get_statistics()
        for stat in stats:
            if stat.exclusion['MESSAGE'] == ['/1/']:
                assert stat.hits == 0
                break

    def test_statistics(self):
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({'MESSAGE': 'exclude'})
            .and_return({'MESSAGE': 'include'})
            .and_return({}))

        exclusions = [{'MESSAGE': ['exclude']}]
        jfilter = JournalFilter(journal.Reader(), exclusions=exclusions)
        list(jfilter)
        statistics = jfilter.get_statistics()
        assert len(statistics) == 1
        assert statistics[0].hits == 1
