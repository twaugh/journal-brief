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
from journal_brief.constants import PRIORITY_MAP
from logging import getLogger
import re
from systemd import journal
from uuid import UUID
import yaml


log = getLogger(__name__)

# Statistics about an exclusion filter rule
ExclusionStatistics = namedtuple('ExclusionStatistics', ['hits', 'exclusion'])

# A set of inclusion and exclusion filter rules
FilterRules = namedtuple('FilterRules', ['inclusions', 'exclusions'])


def coerce_to_UUID(x):
    if isinstance(x, UUID):
        return x
    return UUID(x)


DEFAULT_CONVERTERS = journal.DEFAULT_CONVERTERS.copy()
DEFAULT_CONVERTERS.update({
    '_BOOT_ID': coerce_to_UUID,
    '_MACHINE_ID': coerce_to_UUID,
    'MESSAGE_ID': coerce_to_UUID,
})


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
                converter = DEFAULT_CONVERTERS.get(field, str)
                str_mapping[field] = [converter(match) for match in matches]

        super(FilterRule, self).__init__(str_mapping)

    def __str__(self):
        rdict = {}
        for field, matches in self.items():
            if any(isinstance(match, UUID) for match in matches):
                # Convert UUID to str for representation
                rdict[field] = [str(match) for match in matches]
            else:
                rdict[field] = matches

        return yaml.dump([rdict],
                         indent=2,
                         default_flow_style=False)

    def value_matches(self, field, index, match, value):
        return match == value

    def matches(self, entry):
        for field, matches in self.items():
            if not any(self.value_matches(field, index, match, entry.get(field))
                       for index, match in enumerate(matches)):
                # No match for this field
                return False

        return True


class Inclusion(FilterRule):
    """
    Filter rule for including entries

    Initialise it with a mapping of field names to possible values.

      >>> rule = {'FIELD': ['VALUE'], 'FIELD1': ['VALUE1', 'VALUE2']}
      >>> incl = Inclusion(rule)

    All fields must match one of their possible values.

      >>> assert not incl.matches({'FIELD': 'VALUE'})
      >>> assert incl.matches({'FIELD': 'VALUE', 'FIELD1': 'VALUE1'})
      >>> assert incl.matches({'FIELD': 'VALUE', 'FIELD1': 'VALUE2'})
    """

    def __repr__(self):
        return "Inclusion(%s)" % super(Inclusion, self).__repr__()


class Exclusion(FilterRule):
    """
    Filter rule for excluding entries

    Initialise it with a mapping of field names to possible values.

      >>> rule = {'FIELD': ['VALUE'], 'FIELD1': ['VALUE1', 'VALUE2']}
      >>> excl = Exclusion(rule)

    All fields must match one of their possible values.

      >>> assert not excl.matches({'FIELD': 'VALUE'})
      >>> assert excl.matches({'FIELD': 'VALUE', 'FIELD1': 'VALUE1'})
      >>> assert excl.matches({'FIELD': 'VALUE', 'FIELD1': 'VALUE2'})

    Regular expressions are allowed.

      >>> excl = Exclusion({'MESSAGE': ['/exclude/']})
      >>> assert excl.matches({'MESSAGE': 'exclude this'})

    Regular expressions are matched at the beginning of the string.

      >>> assert not excl.matches({'MESSAGE': "don't exclude this"})
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
            try:
                return regexp.match(value)
            except TypeError:
                # Can't regexp match against a non-string value
                return False

        return super(Exclusion, self).value_matches(field, index, match, value)

    def matches(self, entry):
        matched = super(Exclusion, self).matches(entry)
        if matched:
            log.debug("excluding entry")
            self.hits += 1

        return matched


class JournalFilter(object):
    """
    Apply filter rules to journal entries for a list of formatters

    Provide a list of default filter rules for inclusion and
    exclusion. Each filter rule is a dict whose keys are fields which
    must all match an entry to be excluded.

    The dict value for each field is a list of possible match values,
    any of which may match.

    For exclusions, regular expressions are indicated with '/' at the
    beginning and end of the match string. Regular expressions are
    matched at the start of the journal field value (i.e. it's a match
    not a search).
    """

    def __init__(self,
                 iterator,
                 formatters,
                 default_inclusions=None,
                 default_exclusions=None):
        """
        Constructor

        :param iterator: iterator, providing journal entries
        :param formatters: list, EntryFormatter instances
        :param default_inclusions: list, dicts of field -> values for inclusion
        :param default_exclusions: list, dicts of field -> values for exclusion
        """
        super(JournalFilter, self).__init__()
        self.iterator = iterator
        self.formatters = formatters
        self.filter_rules = {}

        default_inclusions = [Inclusion(incl)
                              for incl in default_inclusions or []]
        self.default_exclusions = [Exclusion(excl)
                                   for excl in default_exclusions or []]

        # Initialise filters
        for formatter in formatters:
            name = formatter.FORMAT_NAME
            if formatter.FILTER_INCLUSIONS or formatter.FILTER_EXCLUSIONS:
                inclusions = [Inclusion(incl)
                              for incl in formatter.FILTER_INCLUSIONS or []]
                exclusions = [Exclusion(excl)
                              for excl in formatter.FILTER_EXCLUSIONS or []]
            else:
                inclusions = default_inclusions
                exclusions = self.default_exclusions

            rules = FilterRules(inclusions=inclusions,
                                exclusions=exclusions)
            self.filter_rules[name] = rules

    def format(self, stream):
        try:
            for entry in self.iterator:
                default_excl = None
                for formatter in self.formatters:
                    rules = self.filter_rules[formatter.FORMAT_NAME]
                    inclusions = rules.inclusions
                    if inclusions and not any(inclusion.matches(entry)
                                              for inclusion in inclusions):
                        # Doesn't match an inclusion rule
                        continue

                    if default_excl is None:
                        # Only match against the default exclusions
                        # once per message, for efficiency and for
                        # better statistics gathering
                        default_excl = any(excl.matches(entry)
                                           for excl in self.default_exclusions)

                    exclusions = rules.exclusions
                    if exclusions is self.default_exclusions and default_excl:
                        # No special rules, matches a default exclusion rule
                        continue

                    if any(excl.matches(entry) for excl in exclusions):
                        # Matches one of the formatter's exclusion rules
                        continue

                    stream.write(formatter.format(entry) or '')
        finally:
            for formatter in self.formatters:
                stream.write(formatter.flush() or '')

    def get_statistics(self):
        """
        Get filter statistics

        :return: list, ExclusionStatistics instances in reverse order
        """

        stats = [ExclusionStatistics(excl.hits, excl)
                 for excl in self.default_exclusions]
        stats.sort(reverse=True, key=lambda stat: stat.hits)
        return stats
