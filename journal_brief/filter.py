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
from collections import namedtuple
from journal_brief.config import Config
from logging import getLogger
import os
from systemd import journal
import yaml


log = getLogger(__name__)
ExclusionStatistics = namedtuple('ExclusionStatistics', ['hits', 'exclusion'])


# dict, field -> list of values
class Exclusion(dict):
    """
    str (field) -> list (str values)
    """

    def __init__(self, mapping):
        assert isinstance(mapping, dict)
        super(Exclusion, self).__init__(mapping)
        self.hits = 0

    def matches(self, entry):
        for key, values in self.items():
            if not any(entry.get(key) == value for value in values):
                return False

        self.hits += 1
        return True


class JournalFilter(Iterator):
    """
    Exclude certain journal entries
    """

    def __init__(self, iterator, exclusions=None):
        """
        Constructor

        :param iterator: iterator, providing journal entries
        :param exclusions: list, dicts of str(field) -> [str(match), ...]
        """
        super(JournalFilter, self).__init__()
        self.iterator = iterator
        if exclusions:
            self.exclusions = [Exclusion(excl) for excl in exclusions]
        else:
            self.exclusions = []

    def __next__(self):
        for entry in self.iterator:
            if not any(exclusion.matches(entry)
                       for exclusion in self.exclusions):
                return entry

        raise StopIteration

    def get_statistics(self):
        log.debug("Exclusions: %r", self.exclusions)
        hits = [ExclusionStatistics(excl.hits, excl)
                for excl in self.exclusions]
        hits.sort(reverse=True)
        return hits
