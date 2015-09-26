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
import os
from systemd import journal


class LatestJournalEntries(Iterator):
    DEFAULT_CURSOR_FILE = "{0}/.config/journal-brief/cursor"

    def __init__(self, cursor_file=None, log_level=None, **kwargs):
        super(LatestJournalEntries, self).__init__()

        if cursor_file:
            self.cursor_file = cursor_file
        else:
            home = os.environ['HOME']
            self.cursor_file = self.DEFAULT_CURSOR_FILE.format(home)
        try:
            with open(self.cursor_file, "rt") as fp:
                self.cursor = fp.read()
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                self.cursor = None
            else:
                raise

        reader = journal.Reader(**kwargs)
        if log_level is not None:
            reader.log_level(log_level)

        if self.cursor:
            reader.seek_cursor(self.cursor)
            reader.get_next()
        else:
            reader.this_boot()

        self.reader = reader

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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
    FORMAT = '{__REALTIME_TIMESTAMP} {MESSAGE}'
    TIMESTAMP_FORMAT = '%b %d %T'

    def format_timestamp(self, entry):
        field = '__REALTIME_TIMESTAMP'
        if field in entry:
            dt = entry[field]
            entry[field] = dt.strftime(self.TIMESTAMP_FORMAT)

    def format(self, entry):
        self.format_timestamp(entry)
        return self.FORMAT.format(**entry)
