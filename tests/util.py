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

import functools


class Watcher(object):
    def __init__(self):
        self.calls = []

    @property
    def calls_args_only(self):
        return [call[:-1] for call in self.calls]

    def watch_call(self, func):
        return functools.partial(self.called, func)

    def called(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
