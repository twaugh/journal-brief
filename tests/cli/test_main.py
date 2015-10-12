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
from tests.util import Watcher
from journal_brief.cli.main import CLI
from journal_brief.filter import JournalFilter
import json
import logging
import os
from systemd import journal
from tempfile import NamedTemporaryFile
from tests.test_filter import MySpecialFormatter


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

    def test_normal_run(self, capsys):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message1'})
            .and_return({'__CURSOR': '2',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message2'})
            .and_return({}))

        with NamedTemporaryFile(mode='wt') as configfile:
            with NamedTemporaryFile(mode='rt') as cursorfile:
                configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert len(out.splitlines()) == 2

    def test_dry_run(self):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
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
        flexmock(journal.Reader, add_match=None, add_disjunction=None)
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

    def test_log_level(self):
        flexmock(journal.Reader, add_match=None, add_disjunction=None)
        (flexmock(journal.Reader)
            .should_receive('log_level')
            .with_args(journal.LOG_ERR)
            .once())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))

        with NamedTemporaryFile(mode='wt') as configfile:
            with NamedTemporaryFile(mode='rt') as cursorfile:
                configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, '-p', 'err'])
                cli.run()

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
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
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
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, 'stats'])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out == "\n".join([" FREQUENCY  EXCLUSION",
                                 "         1  {'MESSAGE': ['exclude']}",
                                 ""])

    def test_debrief(self, capsys):
        entries = [
            {'__CURSOR': '1',
             'MESSAGE': 'message 1',
             'KEY': 'multiple',
             '__REALTIME_TIMESTAMP': datetime.now()},
            {'__CURSOR': '2',
             'MESSAGE': 'message 1',
             'KEY': 'multiple',
             '__REALTIME_TIMESTAMP': datetime.now()},
            {'__CURSOR': '3',
             'MESSAGE': 'message 1',
             '__REALTIME_TIMESTAMP': datetime.now()},
            {'__CURSOR': '4',
             'MESSAGE': 'message 1',
             '__REALTIME_TIMESTAMP': datetime.now()},
            {'__CURSOR': '5',
             'MESSAGE': 'message 2',
             'KEY': 'multiple',
             '__REALTIME_TIMESTAMP': datetime.now()},
            {'__CURSOR': '6',
             'MESSAGE': 'message 2',
             'KEY': 'single',
             '__REALTIME_TIMESTAMP': datetime.now()},
        ]
        expectation = (flexmock(journal.Reader).should_receive('get_next'))
        for entry in entries:
            expectation = expectation.and_return(entry)

        expectation.and_return({})

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("cursor-file: {0}".format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, 'debrief'])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out == "\n".join([
            "exclusions:",
            "  # 4 occurrences (out of 6)",
            "  - MESSAGE:",
            "    - message 1",
            "  # 2 occurrences (out of 2)",
            "  - MESSAGE:",
            "    - message 2",
            ''])

    def test_debrief_no_input(self, capsys):
        """
        Check it handles there being no input
        """
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("cursor-file: {0}".format(cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name, 'debrief'])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert not out

    def test_exclusions_yaml(self, capsys):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("""
cursor-file: {cursor}
exclusions:
- MESSAGE: [1]
""".format(cursor=cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert 'message' in out

    def test_inclusions_yaml(self):
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))
        watcher = Watcher()
        (flexmock(journal.Reader)
            .should_receive('add_match')
            .replace_with(watcher.watch_call('add_match')))
        (flexmock(journal.Reader)
            .should_receive('add_conjunction')
            .replace_with(watcher.watch_call('add_conjunction')))
        (flexmock(journal.Reader)
            .should_receive('add_disjunction')
            .replace_with(watcher.watch_call('add_disjunction')))

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("""
cursor-file: {cursor}
inclusions:
- PRIORITY: [0, 1, 2, 3]
- PRIORITY: [4, 5, 6]
  _SYSTEMD_UNIT: [myservice.service]
""".format(cursor=cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name])
                cli.run()

        # Should add matches for all of the first group
        assert set(watcher.calls[:4]) == set([
            ('add_match', (), "{'PRIORITY': '0'}"),
            ('add_match', (), "{'PRIORITY': '1'}"),
            ('add_match', (), "{'PRIORITY': '2'}"),
            ('add_match', (), "{'PRIORITY': '3'}"),
        ])

        # Then a disjunction
        assert watcher.calls[4] == ('add_disjunction', (), '{}')

        # Then matches for all of the second group
        assert set(watcher.calls[5:9]) == set([
            ('add_match', (), "{'PRIORITY': '4'}"),
            ('add_match', (), "{'PRIORITY': '5'}"),
            ('add_match', (), "{'PRIORITY': '6'}"),
            ('add_match', (), "{'_SYSTEMD_UNIT': 'myservice.service'}"),
        ])

        # And a final disjuction
        assert watcher.calls[9] == ('add_disjunction', (), '{}')

    def test_multiple_output_formats(self, capsys):
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'MESSAGE': 'message',
        }

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("""
cursor-file: {cursor}
""".format(cursor=cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name,
                                '-o', 'cat,cat,json'])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        lines = out.splitlines()
        assert len(lines) == 3
        assert lines[0] == lines[1] == 'message'
        output = json.loads(lines[2])
        del entry['__REALTIME_TIMESTAMP']
        del output['__REALTIME_TIMESTAMP']
        assert output == entry

    def test_formatter_filter(self, capsys):
        """
        Just a coverage test
        """
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'TEST': 'test',
            'MESSAGE': 'message',
        }

        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        with NamedTemporaryFile(mode='rt') as cursorfile:
            with NamedTemporaryFile(mode='wt') as configfile:
                configfile.write("""
cursor-file: {cursor}
""".format(cursor=cursorfile.name))
                configfile.flush()
                cli = CLI(args=['--conf', configfile.name,
                                '-o', 'test'])
                cli.run()

        (out, err) = capsys.readouterr()
        assert not err

    def test_help_output(self, capsys):
        cli = CLI(args=['--help-output'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out
