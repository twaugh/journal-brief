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

import logging


log = logging.getLogger(__name__)
FORMATTERS = {}


def list_formatters():
    return list(FORMATTERS.keys())


def get_formatter(name, *args, **kwargs):
    """
    Get a new formatter instance by name
    """
    return FORMATTERS[name](*args, **kwargs)


class ReadableTimestampMixIn(object):
    TIMESTAMP_FORMAT = '%b %d %T'

    def format_timestamp(self, entry, field):
        """
        Convert entry field from datetime.datetime instance to string

        Uses strftime() and TIMESTAMP_FORMAT
        """

        if field in entry:
            dt = entry[field]
            entry[field] = dt.strftime(self.TIMESTAMP_FORMAT)


class RegisteredFormatter(type):
    """
    Metaclass for EntryFormatter, registering for use with get_formatter()
    """
    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        FORMATTERS[class_dict['NAME']] = cls
        return cls


class EntryFormatter(object, metaclass=RegisteredFormatter):
    NAME = 'cat'  # for use with get_formatter()

    def format(self, entry):
        """
        Return a formatted entry
        """
        return entry['MESSAGE']


class ShortEntryFormatter(EntryFormatter, ReadableTimestampMixIn):
    """
    Convert a journal entry into a string
    """

    NAME = 'short'
    FORMAT = '{__REALTIME_TIMESTAMP} {_HOSTNAME} {SYSLOG_IDENTIFIER}: {MESSAGE}'

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
