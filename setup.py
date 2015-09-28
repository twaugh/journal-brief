#!/usr/bin/python3
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

from setuptools import setup, find_packages

setup(
    name='journal-brief',
    version='0.0.1',
    description='Show new journal entries since last run',
    author='Tim Waugh',
    author_email='tim@cyberelk.net',
    url='https://github.com/twaugh/journal-brief',
    license="GPLv2+",
    entry_points={
        'console_scripts': ['journal-brief=journal_brief.cli.main:run'],
    },
    packages=find_packages(),
    package_data={'': ['conf/journal-brief.conf']},
)

