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
from io import StringIO
from journal_brief import JournalFilter
from journal_brief.filter import Inclusion, Exclusion
from journal_brief.format import EntryFormatter
import logging
import pytest
from systemd import journal
import yaml

try:
    import pytest_benchmark
except ImportError:
    HAVE_BENCHMARK = False
else:
    HAVE_BENCHMARK = True
    del pytest_benchmark


logging.basicConfig(level=logging.DEBUG)


@pytest.mark.skipif(not HAVE_BENCHMARK,
                    reason="install pytest-benchmark to run this test")
class TestFilterProfile(object):
    def test_inclusion(self, benchmark):
        matches = ['never matched {0}'.format(n) for n in range(100)]
        rule = {'MESSAGE': matches}
        for x in range(100):
            rule['FIELD{0}'.format(x)] = 'never matched'

        inclusion = Inclusion(rule)

        entry = {
            'MESSAGE': 'message',
            '__CURSOR': '1',
        }

        for x in range(100):
            entry['FIELD{0}'.format(x)] = x

        assert not benchmark(inclusion.matches, entry)

    def test_exclusion(self, benchmark):
        matches = ['never matched {0}'.format(n) for n in range(100)]
        rule = {'MESSAGE': matches}
        for x in range(100):
            rule['FIELD{0}'.format(x)] = '/never matched/'

        exclusion = Exclusion(rule)

        entry = {
            'MESSAGE': 'message',
            '__CURSOR': '1',
        }

        for x in range(100):
            entry['FIELD{0}'.format(x)] = x

        assert not benchmark(exclusion.matches, entry)


class TestInclusion(object):
    def test_and(self):
        inclusion = Inclusion({'MESSAGE': ['include this'],
                               'SYSLOG_IDENTIFIER': ['from this']})
        assert inclusion.matches({'MESSAGE': 'include this',
                                  'SYSLOG_IDENTIFIER': 'from this',
                                  'IGNORE': 'ignore this'})
        assert not inclusion.matches({'MESSAGE': 'include this'})

    def test_or(self):
        inclusion = Inclusion({'MESSAGE': ['include this', 'or this']})
        assert inclusion.matches({'MESSAGE': 'include this',
                                  'IGNORE': 'ignore this'})
        assert not inclusion.matches({'MESSAGE': 'not this',
                                      'IGNORE': 'ignore this'})

    def test_and_or(self):
        inclusion = Inclusion({'MESSAGE': ['include this', 'or this'],
                               'SYSLOG_IDENTIFIER': ['from this']})
        assert inclusion.matches({'MESSAGE': 'include this',
                                  'SYSLOG_IDENTIFIER': 'from this',
                                  'IGNORE': 'ignore this'})
        assert not inclusion.matches({'MESSAGE': 'include this',
                                      'SYSLOG_IDENTIFIER': 'at your peril',
                                      'IGNORE': 'ignore this'})

    def test_priority(self):
        inclusion = Inclusion({'PRIORITY': 'err'})
        assert inclusion.matches({'PRIORITY': 3})

    def test_repr(self):
        incl = {'MESSAGE': ['include this']}
        assert repr(Inclusion(incl))


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

    def test_regexp(self):
        exclusion = Exclusion({'MESSAGE': ['/exclude/'],
                               'FIELD': ['/exclude/']})
        assert exclusion.matches({'MESSAGE': 'exclude this',
                                  'FIELD': 'exclude this'})
        assert not exclusion.matches({'MESSAGE': 'do not exclude',
                                      'FIELD': 'do not exclude'})
        assert not exclusion.matches({'MESSAGE': 'exclude',
                                      'FIELD': 1})

    def test_priority(self):
        exclusion = Exclusion({'PRIORITY': 'err'})
        assert exclusion.matches({'PRIORITY': 3})

    def test_str_without_comment(self):
        excl = {'MESSAGE': ['exclude this']}
        unyaml = StringIO()
        excl_str = str(Exclusion(excl))
        assert '#' not in excl_str
        unyaml.write(excl_str)
        unyaml.seek(0)
        assert yaml.load(unyaml) == [excl]

    def test_str_with_comment(self):
        excl = {'MESSAGE': ['exclude this']}
        unyaml = StringIO()
        excl_str = str(Exclusion(excl, comment='comment'))
        assert excl_str.startswith('# comment\n')
        unyaml.write(excl_str)
        unyaml.seek(0)
        assert yaml.load(unyaml) == [excl]


class MySpecialFormatter(EntryFormatter):
    """
    Only for testing
    """

    FORMAT_NAME = 'test'
    FILTER_INCLUSIONS = [{'TEST': ['yes']}]
    FILTER_EXCLUSIONS = [{'MESSAGE': ['ignore']}]

    def __init__(self, *args, **kwargs):
        super(MySpecialFormatter, self).__init__(*args, **kwargs)
        self.entries_received = []

    def format(self, entry):
        self.entries_received.append(entry)
        return entry.get('OUTPUT', '')

    def flush(self):
        # format() should handle None here
        return None


class TestJournalFilter(object):
    def test_no_exclusions(self):
        entries = [{'MESSAGE': 'message 1'},
                   {'MESSAGE': 'message 2'}]
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entries[0])
            .and_return(entries[1])
            .and_return({}))

        formatter = EntryFormatter()
        jfilter = JournalFilter(journal.Reader(), [formatter])
        output = StringIO()
        jfilter.format(output)
        output.seek(0)
        lines = output.read().splitlines()
        assert lines == [entry['MESSAGE'] for entry in entries]

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
        formatter = EntryFormatter()
        jfilter = JournalFilter(journal.Reader(), [formatter],
                                default_exclusions=exclusions)
        output = StringIO()
        jfilter.format(output)
        output.seek(0)
        lines = output.read().splitlines()
        assert lines == [entry['MESSAGE'] for entry in entries[2:]]

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
        formatter = EntryFormatter()
        jfilter = JournalFilter(journal.Reader(), [formatter],
                                default_exclusions=exclusions)
        output = StringIO()
        jfilter.format(output)
        output.seek(0)
        lines = output.read().splitlines()
        assert lines == [entry['MESSAGE']
                         for entry in [entries[1]] + [entries[3]]]
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
        formatter = EntryFormatter()
        jfilter = JournalFilter(journal.Reader(), [formatter],
                                default_exclusions=exclusions)
        output = StringIO()
        jfilter.format(output)
        statistics = jfilter.get_statistics()
        assert len(statistics) == 1
        assert statistics[0].hits == 1

    def test_formatter_filters(self):
        incl_entries = [
            {
                'TEST': 'yes',
                'MESSAGE': 'message',
            },
            {
                'TEST': 'yes',
                'MESSAGE': 'message',
                'OUTPUT': None,  # Test returning None from format()
            },
        ]
        excl_entries = [
            {
                'TEST': 'no',
                'MESSAGE': 'message',
            },
            {
                'TEST': 'yes',
                'MESSAGE': 'ignore',
            },
        ]
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return(incl_entries[0])
            .and_return(incl_entries[1])
            .and_return(excl_entries[0])
            .and_return(excl_entries[1])
            .and_return({}))

        formatter = MySpecialFormatter()
        jfilter = JournalFilter(journal.Reader(), [formatter])
        jfilter.format(StringIO())
        assert formatter.entries_received == incl_entries
