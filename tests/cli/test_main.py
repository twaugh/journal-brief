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

from datetime import datetime
from flexmock import flexmock
from journal_brief.cli.main import CLI
from journal_brief.filter import JournalFilter
import logging
import os
from systemd import journal
from tempfile import NamedTemporaryFile


logging.basicConfig(level=logging.DEBUG)


class TestCLI(object):
    def test_param_override(self):
        with NamedTemporaryFile(mode='wt') as configfile:
            configfile.write('priority: err')
            configfile.flush()
            cli = CLI(args=['--conf', configfile.name])

            # Default value
            assert cli.config.get('cursor_file') == 'cursor'

            # Specified in config
            assert cli.config.get('priority') == 'err'

            # Specified on command-line
            cli = CLI(args=['--conf', configfile.name,
                            '-p', 'debug'])
            assert cli.config.get('priority') == 'debug'

    def test_dry_run(self):
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        with NamedTemporaryFile(mode='wt') as configfile:
            with NamedTemporaryFile(mode='rt') as cursorfile:
                configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, '--dry-run'])
                cli.run()
                assert not cursorfile.read()

    def test_this_boot(self):
        final_cursor = '1'
        (flexmock(journal.Reader)
            .should_receive('this_boot')
            .once())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({'__CURSOR': final_cursor,
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        with NamedTemporaryFile(mode='wt') as configfile:
            with NamedTemporaryFile(mode='w+t') as cursorfile:
                configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
                configfile.flush()
                cursorfile.write(final_cursor)
                cursorfile.flush()
                cli = CLI(args=['--conf', configfile.name, '-b'])
                cli.run()
                cursorfile.seek(0)
                assert cursorfile.read() == final_cursor

    def test_reset(self):
        with NamedTemporaryFile(mode='wt') as configfile:
            with NamedTemporaryFile(mode='rt') as cursorfile:
                configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, 'reset'])
                cli.run()
                # Cursor file is deleted
                assert not os.access(cursorfile.name, os.F_OK)
                open(cursorfile.name, mode='w').close()

            # No errors when the cursor file doesn't exist
            cli = CLI(args=['--conf', configfile.name, 'reset'])
            cli.run()
            assert not os.access(cursorfile.name, os.F_OK)

    def test_stats(self, capsys):
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'exclude'})
            .and_return({'__CURSOR': '2',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'include'})
            .and_return({}))

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("""
cursor-file: {cursor}
exclusions:
- MESSAGE: [exclude]
""".format(cursor=cursorfile.name))
                configfile.write('cursor: {0}\n'.format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, 'stats'])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out == "\n".join([" FREQUENCY  EXCLUSION",
                                 "         1  {'MESSAGE': ['exclude']}",
                                 ""])
