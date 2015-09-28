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

import errno
from journal_brief.constants import CONFIG_DIR, PACKAGE
from logging import getLogger
import os
import yaml


log = getLogger(__name__)


class Config(dict):
    def __init__(self, config_file=None):
        if not config_file:
            conf_filename = '{0}.conf'.format(PACKAGE)
            config_file = os.path.join(CONFIG_DIR, conf_filename)

        default_config = {'cursor-file': 'cursor'}

        try:
            with open(config_file) as config_fp:
                config = yaml.safe_load(config_fp)
                if not config:
                    config = {}
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                config = {}
            else:
                raise

        assert isinstance(config, dict)
        default_config.update(config)
        super(Config, self).__init__(default_config)
        self.validate()

    def validate(self):
        if 'exclusions' in self:
            assert isinstance(self['exclusions'], list)
            log.debug("Exclusions:")
            for exclusion in self['exclusions']:
                assert isinstance(exclusion, dict)
                log.debug('-')
                for key, values in exclusion.items():
                    log.debug("%s: %r", key, values)
                    assert isinstance(values, list)
