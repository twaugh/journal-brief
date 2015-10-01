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

from collections.abc import Iterator
import errno
from journal_brief.constants import CONFIG_DIR, PRIORITY_MAP
from logging import getLogger
import os
from systemd import journal


log = getLogger(__name__)


class SelectiveReader(journal.Reader):
    """
    A Reader instance with matches applied
    """

    def __init__(self, log_level=None, this_boot=None, inclusions=None):
        super(SelectiveReader, self).__init__()

        if inclusions:
            assert isinstance(inclusions, list)
            for inclusion in inclusions:
                assert isinstance(inclusion, dict)
                for field, matches in inclusion.items():
                    if field == 'PRIORITY':
                        try:
                            this_log_level = PRIORITY_MAP[matches]
                        except (AttributeError, TypeError):
                            pass
                        else:
                            # These are equivalent:
                            # - PRIORITY: 3
                            # - PRIORITY: err
                            # - PRIORITY: [0, 1, 2, 3]
                            # - PRIORITY: [emerg, alert, crit, err]
                            this_log_level = PRIORITY_MAP[matches]
                            self.log_level(int(this_log_level))
                            continue

                    assert isinstance(matches, list)
                    for match in matches:
                        if field == 'PRIORITY':
                            try:
                                match = PRIORITY_MAP[match]
                            except (AttributeError, TypeError):
                                pass

                        self.add_match(**{str(field): str(match)})

                if this_boot:
                    self.this_boot()

                if log_level is not None:
                    self.log_level(log_level)

                self.add_disjunction()
        else:
            if this_boot:
                self.this_boot()

            if log_level is not None:
                self.log_level(log_level)


class LatestJournalEntries(Iterator):
    """
    Iterate over new journal entries since last time
    """

    def __init__(self, cursor_file=None, reader=None, dry_run=False,
                 seek_cursor=True):
        """
        Constructor

        :param cursor_file: str, filename of cursor bookmark file
        :param reader: systemd.journal.Reader instance
        :param dry_run: bool, whether to update the cursor file
        :param seek_cursor: bool, whether to seek to bookmark first
        """
        super(LatestJournalEntries, self).__init__()

        self.cursor_file = cursor_file
        try:
            with open(self.cursor_file, "rt") as fp:
                self.cursor = fp.read()
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                self.cursor = None
            else:
                raise

        if reader is None:
            reader = journal.Reader()

        if seek_cursor and self.cursor:
            log.debug("Seeking to %s", self.cursor)
            reader.seek_cursor(self.cursor)
            reader.get_next()

        self.reader = reader
        self.dry_run = dry_run

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.dry_run:
            return

        path = os.path.dirname(self.cursor_file)
        try:
            os.makedirs(path)
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

        with open(self.cursor_file, "wt") as fp:
            fp.write(self.cursor)

    def __next__(self):
        fields = self.reader.get_next()
        if not fields:
            raise StopIteration

        if '__CURSOR' in fields:
            self.cursor = fields['__CURSOR']

        return fields


class EntryFormatter(object):
    """
    Convert a journal entry into a string
    """

    FORMAT = '{__REALTIME_TIMESTAMP} {_HOSTNAME} {SYSLOG_IDENTIFIER}: {MESSAGE}'
    TIMESTAMP_FORMAT = '%b %d %T'

    def format_timestamp(self, entry, field):
        """
        Convert entry field from datetime.datetime instance to string

        Uses strftime() and TIMESTAMP_FORMAT
        """

        if field in entry:
            dt = entry[field]
            entry[field] = dt.strftime(self.TIMESTAMP_FORMAT)

    def format(self, entry):
        """
        Format a journal entry using FORMAT

        :param entry: dict, journal entry
        :return: str, formatted string
        """

        self.format_timestamp(entry, '__REALTIME_TIMESTAMP')

        if '_HOSTNAME' not in entry:
            entry['_HOSTNAME'] = 'localhost'

        if 'SYSLOG_IDENTIFIER' not in entry:
            entry['SYSLOG_IDENTIFIER'] = entry.get('_COMM', '?')

        if '_PID' in entry:
            entry['SYSLOG_IDENTIFIER'] += '[{0}]'.format(entry['_PID'])
        elif 'SYSLOG_PID' in entry:
            entry['SYSLOG_IDENTIFIER'] += '[{0}]'.format(entry['SYSLOG_PID'])

        return self.FORMAT.format(**entry)
