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
from journal_brief.constants import PRIORITY_MAP
from logging import getLogger
import re
import yaml


log = getLogger(__name__)
ExclusionStatistics = namedtuple('ExclusionStatistics', ['hits', 'exclusion'])


class FilterRule(dict):
    """
    A mapping of field names to values that are significant for that field
    """

    def __init__(self, mapping):
        assert isinstance(mapping, dict)

        # Make sure everything is interpreted as a string
        str_mapping = {}
        for field, matches in mapping.items():
            if field == 'PRIORITY':
                try:
                    level = int(PRIORITY_MAP[matches])
                except (AttributeError, TypeError):
                    str_mapping[field] = [PRIORITY_MAP[match]
                                          for match in matches]
                else:
                    str_mapping[field] = list(range(level + 1))
            else:
                str_mapping[field] = [str(match) for match in matches]

        super(FilterRule, self).__init__(str_mapping)

    def __str__(self):
        return yaml.dump([dict(self)],
                         indent=2,
                         default_flow_style=False)

    def value_matches(self, field, index, match, value):
        return match == value

    def matches(self, entry):
        for field, matches in self.items():
            is_match = False
            for index, match in enumerate(matches):
                if self.value_matches(field, index, match, entry.get(field)):
                    is_match = True
                    break

            if not is_match:
                return False

        return True


class Inclusion(FilterRule):
    """
    Filter rule for including entries
    """

    def __repr__(self):
        return "Inclusion(%s)" % super(Inclusion, self).__repr__()


class Exclusion(FilterRule):
    """
    Filter rule for excluding entries
    """

    def __init__(self, mapping, comment=None):
        super(Exclusion, self).__init__(mapping)

        # Make sure everything is interpreted as a string
        log.debug("new exclusion rule:")
        for field, matches in mapping.items():
            log.debug("%s=%r", field, matches)

        self.hits = 0
        self.regexp = {}  # field -> index -> compiled regexp
        self.comment = comment

    def __repr__(self):
        return "Exclusion(%s)" % super(Exclusion, self).__repr__()

    def __str__(self):
        ret = ''
        if self.comment:
            ret += '# {0}\n'.format(self.comment)

        ret += super(Exclusion, self).__str__()
        return ret

    def value_matches(self, field, index, match, value):
        try:
            regexp = self.regexp[field][index]
            if regexp is not None:
                log.debug('using cached regexp for %s[%d]:%s',
                          field, index, match)
        except KeyError:
            try:
                if match.startswith('/') and match.endswith('/'):
                    pattern = match[1:-1]
                    log.debug('compiling pattern %r', pattern)
                    regexp = re.compile(pattern)
                else:
                    regexp = None
                    log.debug('%r is not a regex', match)
            except AttributeError:
                regexp = None
                log.debug('%r is not a regex', match)

            self.regexp.setdefault(field, {})
            self.regexp[field][index] = regexp

        if regexp is not None:
            return regexp.match(value)

        return match == value

    def matches(self, entry):
        matched = super(Exclusion, self).matches(entry)
        if matched:
            log.debug("excluding entry")
            self.hits += 1

        return matched


class JournalFilter(Iterator):
    """
    Exclude certain journal entries

    Provide a list of exclusions. Each exclusion is a dict whose keys
    are fields which must all match an entry to be excluded.

    The dict value for each field is a list of possible match values,
    any of which may match.

    Regular expressions are indicated with '/' at the beginning and
    end of the match string. Regular expressions are matched at the
    start of the journal field value (i.e. it's a match not a search).
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
        """
        Get filter statistics

        :return: list, ExclusionStatistics instances in reverse order
        """

        stats = [ExclusionStatistics(excl.hits, excl)
                 for excl in self.exclusions]
        stats.sort(reverse=True, key=lambda stat: stat.hits)
        return stats
