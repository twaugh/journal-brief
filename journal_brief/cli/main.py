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

import argparse
import logging
import os
import sys
from systemd import journal

from journal_brief import LatestJournalEntries, EntryFormatter, JournalFilter
from journal_brief.filter import Config
from journal_brief.constants import CONFIG_DIR


class InstanceConfig(object):
    def __init__(self, config, args):
        self.config = config
        self.args = args

    def get(self, key):
        config_key = key.replace('_', '-')
        try:
            value = getattr(self.args, key)
        except AttributeError:
            value = None
        finally:
            if value is None:
                value = self.config.get(config_key)

        return value


class CLI(object):
    def __init__(self, args=None):
        args = self.get_args(args or sys.argv[1:])
        config = Config(config_file=args.conf)
        self.config = InstanceConfig(config, args)

    def get_args(self, args):
        description = 'Show new journal entries since last run'
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('-p', '--priority', metavar='PRI',
                            help='show entries at priority PRI and lower',
                            choices=['emerg', 'alert', 'crit', 'err',
                                     'warning', 'notice', 'info', 'debug'])
        parser.add_argument('--conf', metavar='FILE',
                            help='use FILE as config file')
        return parser.parse_args(args)

    def run(self):
        cursor_file = self.config.get('cursor_file')
        if not cursor_file.startswith('/'):
            cursor_file = os.path.join(CONFIG_DIR, cursor_file)

        log_level = None
        priority = self.config.get('priority')
        if priority:
            attr = 'LOG_' + priority.upper()
            log_level = getattr(journal, attr)

        formatter = EntryFormatter()
        with LatestJournalEntries(cursor_file=cursor_file,
                                  log_level=log_level) as entries:
            for entry in JournalFilter(entries, config=config):
                print(formatter.format(entry))


def run():
    CLI().run()


if __name__ == '__main__':
    run()
