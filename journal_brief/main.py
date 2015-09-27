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
from os.path import basename
import sys
from systemd import journal

from journal_brief import LatestJournalEntries, EntryFormatter, JournalFilter


def get_args():
    parser = argparse.ArgumentParser(description='Show new journal entries since last run')
    parser.add_argument('-p', '--priority', metavar='PRI',
                        help='show entries at priority PRI and lower',
                        choices=['emerg', 'alert', 'crit', 'err', 'warning',
                                 'notice', 'info', 'debug'])
    parser.add_argument('--cursor-file', metavar='FILE',
                        help='use FILE as cursor bookmark file')
    return parser.parse_args(sys.argv[1:])


def run():
    kwargs = {}
    args = get_args()
    if args.priority:
        attr = 'LOG_' + args.priority.upper()
        kwargs['log_level'] = getattr(journal, attr)

    if args.cursor_file:
        kwargs['cursor_file'] = args.cursor_file

    formatter = EntryFormatter()
    with LatestJournalEntries(**kwargs) as entries:
        for entry in JournalFilter(entries):
            print(formatter.format(entry))


if __name__ == '__main__':
    run()
