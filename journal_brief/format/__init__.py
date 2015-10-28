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


class RegisteredFormatter(type):
    """
    Metaclass for EntryFormatter, registering for use with get_formatter()
    """
    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        FORMATTERS[class_dict['FORMAT_NAME']] = cls
        return cls


class EntryFormatter(object, metaclass=RegisteredFormatter):
    # Base class for output format implementations

    # Class docstring is used for help output to describe the output
    # format:
    """
    Only display MESSAGE field
    """

    # This is the name used to select the output format, collected
    # automatically by the metaclass and used by list_formatters(),
    # get_formatter(), and the CLI '-o' parameter:
    FORMAT_NAME = 'cat'

    # The formatter can either use the inclusions and exclusions
    # listed in the config file:
    FILTER_INCLUSIONS = None
    FILTER_EXCLUSIONS = None
    # or else it can set its own rules. If FILTER_INCLUSIONS is not
    # None, this formatter will only receive those entries it has
    # asked for.
    #   FILTER_INCLUSIONS = [{'field': ['values', ...]}, ...]
    # The PRIORITY field is allowed to be a single value rather than a
    # list, just like in the config file.

    def format(self, entry):
        """
        Format a single journal entry.

        :param entry: dict, entry to format
        :return: str, formatted entry including any newline required
        """
        return entry['MESSAGE'] + '\n'

    def flush(self):
        """
        Return any closing formatting required.

        This is called when there are no more
        entries to format and can be used to
        eg. display analysis of the logs.
        """
        return ''
