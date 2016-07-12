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

import datetime
from journal_brief.format import EntryFormatter
import json
import logging
from systemd import journal
import uuid


log = logging.getLogger(__name__)


class JSONEntryFormatter(EntryFormatter):
    """
    JSON format
    """

    FORMAT_NAME = 'json'
    JSON_DUMPS_KWARGS = {}

    def format(self, entry):
        serializable = {}
        for field, value in entry.items():
            if isinstance(value, uuid.UUID):
                log.debug("Converting %s", field)
                value = str(value)
            elif isinstance(value, datetime.datetime):
                log.debug("Converting %s", field)
                value = value.timestamp() * 1000000  # microseconds
            elif isinstance(value, journal.Monotonic):
                log.debug("Converting %s", field)
                value = value.timestamp.microseconds
            elif isinstance(value, datetime.timedelta):
                log.debug("Converting %s", field)
                value = value.total_seconds() * 1000000  # microseconds
            elif isinstance(value, bytes):
                log.debug("Converting %s", field)
                try:
                    value = value.decode()
                except UnicodeDecodeError:
                    value = [int(byte) for byte in value]

            serializable[field] = value

        log.debug("%r", serializable)
        return json.dumps(serializable, **self.JSON_DUMPS_KWARGS) + '\n'


class JSONPrettyEntryFormatter(JSONEntryFormatter):
    """
    Pretty JSON format
    """

    FORMAT_NAME = 'json-pretty'
    JSON_DUMPS_KWARGS = {'indent': 8}
