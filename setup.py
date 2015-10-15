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


long_description="""
This can be run from cron to get a daily or hourly
briefing of interesting new systemd journal entries.

Inclusion and exclusion criteria define what an "interesting" journal
entry is, and exclusion rules can be built automatically.
""".strip()

setup(
    name='journal-brief',
    version='1.1.1',  # also update journal_brief/__init__.py
    description='Show interesting new systemd journal entries since last run',
    long_description=long_description,
    author='Tim Waugh',
    author_email='tim@cyberelk.net',
    url='https://github.com/twaugh/journal-brief',
    license="GPLv2+",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Logging',
        'Topic :: System :: Monitoring',
    ],
    keywords='systemd journal journalctl log monitor watch',
    entry_points={
        'console_scripts': ['journal-brief=journal_brief.cli.main:run'],
    },
    install_requires=['PyYAML'],
    packages=find_packages(exclude=['tests',
                                    'tests.cli',
                                    'tests.missing',
                                    'tests.missing.systemd',
                                    'tests.missing.systemd.journal']),
    package_data={'': ['conf/journal-brief.conf']},
)

