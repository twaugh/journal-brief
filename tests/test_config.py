"""
Copyright (c) 2015, 2020 Tim Waugh <tim@cyberelk.net>

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

from tests.util import maybe_mock_systemd
maybe_mock_systemd()

from journal_brief.config import Config, ConfigError
import logging
import os
import pytest
from tempfile import NamedTemporaryFile
import yaml


logging.basicConfig(level=logging.DEBUG)


class TestConfig(object):
    def test_no_config_file(self, tmpdir):
        Config(config_file=os.path.join(str(tmpdir), 'nonexistent'))

    @pytest.mark.parametrize('badyaml', [
        """
exclusions
  - MESSAGE: [foo]
        """,
    ])
    def test_validation_bad_yaml(self, badyaml):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(badyaml.strip())
            cfp.flush()
            with pytest.raises(ConfigError):
                try:
                    Config(config_file=cfp.name)
                except ConfigError as ex:
                    # Test the exception can be represented as a string
                    str(ex)
                    raise

    @pytest.mark.parametrize('badconfig', [
        "- not a map",
        "disallowed: 1",
        "cursor-file: [1]",
        "debug: [1]",
        "debug: debug",
        "output: none",
        "priority: -1",
        "priority: [0, 1, 2, error, 2]",

        # Test multiple errors
        """
disallowed: 1
cursor-file: [1]
debug: [1]
        """,
    ])
    def test_validation_bad(self, badconfig):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(badconfig.strip())
            cfp.flush()
            with pytest.raises(ConfigError):
                try:
                    Config(config_file=cfp.name)
                except ConfigError as ex:
                    # Test the exception can be represented as a string
                    str(ex)
                    raise

    @pytest.mark.parametrize('badconfig', [
        "{key}: 1",
        """
{key}:
  map: 1
        """,
        """
{key}:
  - 1
        """,
        """
{key}:
  - PRIORITY: [-1]
        """,
        """
{key}:
  - PRIORITY: -1
        """,
        """
{key}:
  - PRIORITY:
      map: 1
        """,
        """
{key}:
  - MESSAGE: 1
        """,
        """
{key}:
  - MESSAGE: [baz]
  - MESSAGE:
      - foo
      - [bar]
        """,
    ])
    @pytest.mark.parametrize('key', ['inclusions', 'exclusions'])
    def test_validation_bad_inclusion_exclusion(self, key, badconfig):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(badconfig.format(key=key).strip())
            cfp.flush()
            with pytest.raises(ConfigError):
                Config(config_file=cfp.name)

            # Test the exception can be represented as a string
            try:
                Config(config_file=cfp.name)
            except ConfigError as ex:
                str(ex)

    @pytest.mark.parametrize('badconfig', [
        """
exclusions:
  - MESSAGE: [/(mismatched parenth/]
        """,
    ])
    def test_validation_bad_regex(self, badconfig):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(badconfig.strip())
            cfp.flush()
            with pytest.raises(ConfigError):
                try:
                    Config(config_file=cfp.name)
                except ConfigError as ex:
                    # Test the exception can be represented as a string
                    str(ex)
                    raise

    @pytest.mark.parametrize('goodconfig, num_outputs', [
        ("output: [json-pretty, config]", 2),
        ("output: [cat]", 1),
        ("output: cat", 1),
    ])
    def test_validation_good(self, goodconfig, num_outputs):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(goodconfig.strip())
            cfp.flush()
            c = Config(config_file=cfp.name)
            assert len(c['output']) == num_outputs

    @pytest.mark.parametrize('badconfig', [
        {
            'from': 'foo',
            'to': 'bar',
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'disallowed': '1',
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'suppress_empty': 'foo',
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': [],
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': [],
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'foo',
            'smtp': 'bar',
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': {'disallowed': '1'},
        },
        {
            'from': 'foo',
            'command': 'baz',
        },
        {
            'to': 'bar',
            'command': 'baz',
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'subject': [],
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': {
                'host': [],
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': {
                'port': [],
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': {
                'starttls': 'baz',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': {
                'user': [],
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'smtp': {
                'password': [],
            },
        },
        {
            'from': 'foo',
            'to': {},
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'cc': {},
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'bcc': {},
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': [],
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': 'baz',
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'From': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'To': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'Cc': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'Bcc': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'from': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'TO': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'cC': 'foo',
            },
        },
        {
            'from': 'foo',
            'to': 'bar',
            'command': 'baz',
            'headers': {
                'BcC': 'foo',
            },
        },
    ])
    def test_validation_email(self, badconfig):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(yaml.dump({'email': badconfig}))
            cfp.flush()
            with pytest.raises(ConfigError):
                try:
                    Config(config_file=cfp.name)
                except ConfigError as ex:
                    # Test the exception can be represented as a string
                    str(ex)
                    raise

    @pytest.mark.parametrize('oldconfig', [
        {
            'command': 'foo',
        },
        {
            'smtp': {
                'from': 'foo',
                'to': 'bar',
                'cc': 'baz',
                'bcc': 'bat',
                'subject': 'subj',
                'headers': {
                    'blah': 'bluh',
                },
            },
        },
    ])
    def test_oldconfig_email(self, oldconfig):
        with NamedTemporaryFile(mode='wt') as cfp:
            cfp.write(yaml.dump({'email': oldconfig}))
            cfp.flush()
            Config(config_file=cfp.name)
