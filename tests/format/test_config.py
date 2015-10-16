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
from journal_brief.format import get_formatter
from journal_brief.format.config import EntryCounter
import logging


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class TestEntryCounter(object):
    def test_get_counts(self):
        reader = [{'MESSAGE': 'message 1',
                   'KEY': 'multiple'},
                  {'MESSAGE': 'message 1',
                   'KEY': 'multiple'},
                  {'MESSAGE': 'message 1'},
                  {'MESSAGE': 'message 1'},
                  {'MESSAGE': 'message 2',
                   'KEY': 'multiple'},
                  {'MESSAGE': 'message 2',
                   'KEY': 'single'}]
        counter = EntryCounter(reader)
        counts = counter.get_counts()
        assert counter.total_entries == len(reader)

        expected = [('MESSAGE', 'message 1', 4),
                    ('KEY', 'multiple', 3),
                    ('MESSAGE', 'message 2', 2),
                    ('KEY', 'single', 1)]
        for exp_field, exp_value, exp_count in expected:
            count = counts.pop(0)
            log.debug("%r: expect %s=%r x %s",
                      count, exp_field, exp_value, exp_count)
            assert count.field == exp_field
            assert len(count.entries) == exp_count
            values = set([entry[exp_field] for entry in count.entries])
            assert len(values) == 1


class TestDebriefer(object):
    def test_get_exclusions(self):
        reader = [{'MESSAGE': 'message 1',
                   'MESSAGE1': 'x',
                   'KEY': 'multiple'},
                  {'MESSAGE': 'message 1',
                   'MESSAGE1': 'x',
                   'KEY': 'multiple'},
                  {'MESSAGE': 'message 1',
                   'MESSAGE1': 'x'},
                  {'MESSAGE': 'message 1',
                   'MESSAGE1': 'x'},
                  {'MESSAGE': 'message 2',
                   'KEY': 'multiple'},
                  {'MESSAGE': 'message 2',
                   'KEY': 'single'}]
        dbr = get_formatter('config')
        formatted = ''
        for entry in reader:
            formatted += dbr.format(entry)

        formatted += dbr.flush()
        assert formatted == '\n'.join([
            "exclusions:",
            "  # 4 occurrences (out of 6)",
            "  - MESSAGE:",
            "    - message 1",
            "    MESSAGE1:",
            "    - x",
            "  # 2 occurrences (out of 2)",
            "  - MESSAGE:",
            "    - message 2",
            ''
        ])
