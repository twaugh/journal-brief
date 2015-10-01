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

import os
from systemd import journal

CONFIG_DIR = '{0}/.config/journal-brief'.format(os.path.expanduser('~'))
PACKAGE = 'journal-brief'

PRIORITY_MAP = {}
for attr in dir(journal):
    if attr.startswith('LOG_'):
        value = getattr(journal, attr)
        svalue = str(value)
        for key in [value, svalue, attr[4:].lower()]:
            PRIORITY_MAP[key] = svalue
