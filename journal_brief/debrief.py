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

from collections import namedtuple
from journal_brief.filter import Exclusion
from logging import getLogger


log = getLogger(__name__)
CountedEntryField = namedtuple('CountedEntryField',
                               ['field',
                                'entries'])


class Entry(dict):
    """
    Journal entry that can be represented as a set of key=pair strings
    """
    def as_strings(self, ignore_fields=None):
        """
        Convert to strings

        :return: list, key=pair strings
        """
        if ignore_fields is None:
            ignore_fields = []

        strings = ["{0}={1}".format(field, value)
                   for field, value in self.items()
                   if field not in ignore_fields]
        return set(strings)


class EntryCounter(object):
    """
    Count occurrences of particular key=value pairs, maintaining context
    """

    # Fields to ignore
    IGNORE = {
        '__CURSOR',
        '__REALTIME_TIMESTAMP',
        '_SOURCE_REALTIME_TIMESTAMP',
        '__MONOTONIC_TIMESTAMP',
        '_SOURCE_MONOTONIC_TIMESTAMP',
        '_BOOT_ID',
        '_PID',
        'SYSLOG_PID',
        '_MACHINE_ID',
        '_TRANSPORT',
        '_HOSTNAME',
        '_SYSTEMD_OWNER_UID',
        '_UID',
        '_AUDIT_LOGINUID',
        '_GID',
        '_CAP_EFFECTIVE',
        'PRIORITY',
        'SYSLOG_FACILITY',
        '_AUDIT_SESSION',
        '_SYSTEMD_SESSION',
        '_SYSTEMD_CGROUP',
        '_SYSTEMD_SLICE',
    }

    def __init__(self, reader, ignore_fields=None):
        """
        Constructor

        :param reader: iterator, providing entry dicts
        :param ignore_fields: sequence, set of field names to ignore
        """
        self.reader = reader
        self.counts = {}
        self.total_entries = 0
        self.ignore_fields = self.IGNORE.copy()
        if ignore_fields:
            self.ignore_fields.update(ignore_fields)

    def read(self):
        """
        Read all entries and count occurrences of field values
        """
        for entry_dict in self.reader:
            entry = Entry(entry_dict)
            self.total_entries += 1
            for entry_str in entry.as_strings(ignore_fields=self.ignore_fields):
                try:
                    counted = self.counts[entry_str]
                    counted.entries.append(entry)
                except KeyError:
                    field = entry_str.split('=', 1)[0]
                    self.counts[entry_str] = CountedEntryField(field=field,
                                                               entries=[entry])

    def get_counts(self):
        """
        Get the list of counted entries, sorted with most frequent first

        :return: list, CountedEntryField instances
        """
        if not self.counts:
            self.read()

        counts = list(self.counts.values())
        counts.sort(key=lambda count: len(count.entries), reverse=True)
        return counts


class Debriefer(object):
    """
    Build exclusions list covering all entries.
    """

    # One of these must be included in each rule
    DEFINITIVE_FIELDS = {
        'MESSAGE_ID',
        'MESSAGE',
        'CODE_FILE',
        'CODE_FUNCTION',
    }

    def __init__(self, reader, ignore_fields=None, definitive_fields=None):
        """
        Constructor

        :param reader: iterable, providing entry dicts
        :param ignore_fields: sequence, field names to ignore
        """

        self.all_entries = list(reader)
        self.ignore_fields = set(ignore_fields or [])
        self.definitive_fields = (definitive_fields or
                                  self.DEFINITIVE_FIELDS.copy())

        self.exclusions = []

    def get_top(self, entries=None):
        """
        Find the most frequently occurring set of key=value pairs

        :param entries: iterable, providing entry dicts
        """
        if entries is None:
            entries = self.all_entries

        ignore_fields = self.ignore_fields or set([])
        counter = EntryCounter(entries, ignore_fields=ignore_fields)
        counts = counter.get_counts()
        top = next(count for count in counts
                   if count.field in self.definitive_fields)
        field = top.field
        value = top.entries[0][field]
        freq = len(top.entries)
        log.debug("Top: %s=%r x %s/%s", field, value, freq,
                  counter.total_entries)
        comment = '{0} occurrences (out of {1})'.format(freq,
                                                        counter.total_entries)
        excl = {field: [value]}

        # Anything else common to all of them?
        ignore_fields.add(field)
        while True:
            counter = EntryCounter([entry for entry in entries
                                    if entry.get(field) == value],
                                   ignore_fields=ignore_fields)
            counts = counter.get_counts()
            if not counts:
                break

            top = counts.pop(0)
            if len(top.entries) < freq:
                break

            field = top.field
            excl[field] = [top.entries[0][field]]
            ignore_fields.add(field)

        self.exclusions.append(Exclusion(excl, comment=comment))
        remaining = []
        for entry in entries:
            if all(entry.get(key) in value for key, value in excl.items()):
                # Excluded
                pass
            else:
                remaining.append(entry)

        log.debug("%s entries remaining", len(remaining))
        assert len(remaining) < len(entries)
        try:
            return self.get_top(remaining)
        except StopIteration:
            return top

    def get_exclusions(self):
        """
        Get the exclusions list

        :return: list, Exclusion instances
        """
        try:
            self.get_top()
        except StopIteration:
            pass
        finally:
            return self.exclusions
