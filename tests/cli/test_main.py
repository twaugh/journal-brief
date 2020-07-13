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

from datetime import datetime
import email.mime.text
from flexmock import flexmock
from journal_brief.cli.constants import (EMAIL_SUPPRESS_EMPTY_TEXT,
                                         EMAIL_DRY_RUN_SEPARATOR)
from journal_brief.cli.main import CLI
import json
import logging
import os
import pytest
import smtplib
import ssl
import subprocess
from systemd import journal
from tempfile import NamedTemporaryFile
from tests.test_filter import MySpecialFormatter  # registers class; # noqa: F401
from tests.util import Watcher
import uuid
import yaml


logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def config_and_cursor(tmp_path):
    with NamedTemporaryFile(mode='wt', dir=tmp_path) as configfile:
        with NamedTemporaryFile(mode='w+t', dir=tmp_path) as cursorfile:
            configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
            configfile.flush()
            yield (configfile, cursorfile)


@pytest.fixture
def missing_or_empty_cursor():
    (flexmock(journal.Reader)
        .should_receive('seek_tail')
        .once())
    (flexmock(journal.Reader)
        .should_receive('get_previous')
        .and_return({'__CURSOR': '0'}))


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

    def test_normal_run(self, capsys, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message1'})
            .and_return({'__CURSOR': '2',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message2'})
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert len(out.splitlines()) == 2

    def test_dry_run(self, config_and_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        cli = CLI(args=['--conf', configfile.name, '--dry-run'])
        cli.run()
        assert not cursorfile.read()

    def test_this_boot(self, config_and_cursor):
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

        (configfile, cursorfile) = config_and_cursor
        cursorfile.write(final_cursor)
        cursorfile.flush()
        cli = CLI(args=['--conf', configfile.name, '-b'])
        cli.run()
        cursorfile.seek(0)
        assert cursorfile.read() == final_cursor

    def test_log_level(self, config_and_cursor, missing_or_empty_cursor):
        flexmock(journal.Reader, add_match=None, add_disjunction=None)
        (flexmock(journal.Reader)
            .should_receive('log_level')
            .with_args(journal.LOG_ERR)
            .once())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        cli = CLI(args=['--conf', configfile.name, '-p', 'err'])
        cli.run()

    def test_reset(self, config_and_cursor):
        (configfile, cursorfile) = config_and_cursor
        with cursorfile:  # force the cursorfile context to be exited at the right time
            cli = CLI(args=['--conf', configfile.name, 'reset'])
            cli.run()
            # Cursor file is deleted
            assert not os.access(cursorfile.name, os.F_OK)
            open(cursorfile.name, mode='w').close()

        # No errors when the cursor file doesn't exist
        cli = CLI(args=['--conf', configfile.name, 'reset'])
        cli.run()
        assert not os.access(cursorfile.name, os.F_OK)

    def test_stats(self, capsys, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'exclude'})
            .and_return({'__CURSOR': '2',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'include'})
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        configfile.write("""
exclusions:
- MESSAGE: [exclude]
""")
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name, 'stats'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out == "\n".join([" FREQUENCY  EXCLUSION",
                                 "         1  {'MESSAGE': ['exclude']}",
                                 ""])

    def test_debrief(self, capsys, config_and_cursor, missing_or_empty_cursor):
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

        (configfile, cursorfile) = config_and_cursor
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

    def test_debrief_no_input(self, capsys, config_and_cursor, missing_or_empty_cursor):
        """
        Check it handles there being no input
        """
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        cli = CLI(args=['--conf', configfile.name, 'debrief'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert not out

    def test_exclusions_yaml(self, capsys, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        configfile.write("""
exclusions:
- MESSAGE: [1]
""")
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert 'message' in out

    def test_inclusions_yaml(self, config_and_cursor, missing_or_empty_cursor):
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

        (configfile, cursorfile) = config_and_cursor
        configfile.write("""
inclusions:
- PRIORITY: [0, 1, 2, 3]
- PRIORITY: [4, 5, 6]
  _SYSTEMD_UNIT: [myservice.service]
""")
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

        # And nothing else
        assert len(watcher.calls) == 9

    def test_multiple_output_formats_cli(self, capsys, config_and_cursor, missing_or_empty_cursor):
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'MESSAGE': 'message',
        }

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
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

    def test_multiple_output_formats_conf(self, capsys, config_and_cursor, missing_or_empty_cursor):
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'MESSAGE': 'message',
        }

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        configfile.write("""
output:
- cat
- cat
- json
""")
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
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

    def test_formatter_filter(self, capsys, config_and_cursor, missing_or_empty_cursor):
        """
        Just a coverage test
        """
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'PRIORITY': 6,
            'MESSAGE': 'login session started',
            'MESSAGE_ID': uuid.UUID('8d45620c1a4348dbb17410da57c60c66'),
            '_COMM': 'systemd-logind',
            'USER_ID': 'abc',
        }

        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        (configfile, cursorfile) = config_and_cursor
        cli = CLI(args=['--conf', configfile.name,
                        '-p', 'err', '-o', 'login'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out

    def test_help_output(self, capsys):
        cli = CLI(args=['--help-output'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out


class TestCLIEmailCommand(object):
    TEST_COMMAND = 'foo'

    def test(self, config_and_cursor, missing_or_empty_cursor):
        entry = {
            '__CURSOR': '1',
            'TEST': 'yes',
            'OUTPUT': 'message',
        }

        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return(entry)
         .and_return({}))

        (flexmock(subprocess)
         .should_receive('run')
         .with_args(self.TEST_COMMAND, shell=True, check=True, text=True,
                    input=entry['OUTPUT'])
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'output': 'test',
            'email': {
                'command': self.TEST_COMMAND,
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_dry_run(self, capsys, config_and_cursor):
        entry = {
            '__CURSOR': '1',
            'TEST': 'yes',
            'OUTPUT': 'message',
        }

        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return(entry)
         .and_return({}))

        (flexmock(subprocess)
         .should_receive('run')
         .never())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'output': 'test',
            'email': {
                'command': self.TEST_COMMAND,
            },
        }))
        configfile.flush()
        cli = CLI(args=['--dry-run', '--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        lines = out.splitlines()
        assert len(lines) == 3
        assert lines[0] == "Email to be delivered via '{0}'".format(self.TEST_COMMAND)
        assert lines[1] == EMAIL_DRY_RUN_SEPARATOR

    def test_allow_empty(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(subprocess)
         .should_receive('run')
         .with_args(self.TEST_COMMAND, shell=True, check=True, text=True,
                    input=EMAIL_SUPPRESS_EMPTY_TEXT)
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_suppress_empty(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(subprocess)
         .should_receive('run')
         .never())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'command': self.TEST_COMMAND,
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()


class TestCLIEmailSMTP(object):
    TEST_USER = 'zork'
    TEST_PASSWORD = 'xyzzy'
    TEST_HOST = 'example'
    TEST_PORT = 1234
    TEST_SUBJECT = 'subj'

    @pytest.fixture(autouse=True)
    def smtp_mock_fixer(self):
        # ensure that no attempt is made to make a connection
        (flexmock(smtplib.SMTP)
         .should_receive('connect')
         .with_args(str, int))
        # in Python versions before 3.8, the `close` method will fail if
        # no connection was opened; because the object has been mocked,
        # that will always be the case
        (flexmock(smtplib.SMTP)
         .should_receive('close')
         .and_return(None))

    def test(self, capsys, config_and_cursor, missing_or_empty_cursor):
        entry = {
            '__CURSOR': '1',
            'TEST': 'yes',
            'OUTPUT': 'message',
        }

        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return(entry)
         .and_return({}))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__init__')
         .with_args(entry['OUTPUT'], _charset='utf-8'))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('From', 'F'))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('To', 'T'))

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'output': 'test',
            'email': {
                'smtp': {
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_dry_run(self, capsys, config_and_cursor):
        entry = {
            '__CURSOR': '1',
            'TEST': 'yes',
            'OUTPUT': 'message',
        }

        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return(entry)
         .and_return({}))

        (flexmock(smtplib)
         .should_receive('SMTP')
         .never())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'output': 'test',
            'email': {
                'smtp': {
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--dry-run', '--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        lines = out.splitlines()
        assert len(lines) == 9
        assert lines[0] == 'Email to be delivered via SMTP to localhost port 25'
        assert lines[1] == EMAIL_DRY_RUN_SEPARATOR

    def test_allow_empty(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__init__')
         .with_args(EMAIL_SUPPRESS_EMPTY_TEXT, _charset='utf-8'))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('From', 'F'))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('To', 'T'))

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_suppress_empty(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(smtplib)
         .should_receive('SMTP')
         .never())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'smtp': {
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_host(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(smtplib.SMTP)
         .should_receive('__init__')
         .with_args(self.TEST_HOST, 0)
         .once())

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'host': self.TEST_HOST,
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_port(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(smtplib.SMTP)
         .should_receive('__init__')
         .with_args(self.TEST_HOST, self.TEST_PORT)
         .once())

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'host': self.TEST_HOST,
                    'port': self.TEST_PORT,
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_starttls(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(smtplib.SMTP)
         .should_receive('starttls')
         .with_args(context=ssl.SSLContext)
         .once()
         .ordered())

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once()
         .ordered())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'starttls': True,
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_user(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(smtplib.SMTP)
         .should_receive('login')
         .with_args(self.TEST_USER, None)
         .once()
         .ordered())

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once()
         .ordered())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'user': self.TEST_USER,
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_password(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(smtplib.SMTP)
         .should_receive('login')
         .with_args(self.TEST_USER, self.TEST_PASSWORD)
         .once()
         .ordered())

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once()
         .ordered())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'user': self.TEST_USER,
                    'password': self.TEST_PASSWORD,
                    'from': 'F',
                    'to': 'T',
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

    def test_subject(self, config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
         .should_receive('get_next')
         .and_return({}))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__init__')
         .with_args(EMAIL_SUPPRESS_EMPTY_TEXT, _charset='utf-8'))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('Subject', self.TEST_SUBJECT))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('From', 'F'))

        (flexmock(email.mime.text.MIMEText)
         .should_receive('__setitem__')
         .with_args('To', 'T'))

        (flexmock(smtplib.SMTP)
         .should_receive('send_message')
         .once())

        (configfile, cursorfile) = config_and_cursor
        configfile.write(yaml.dump({
            'email': {
                'suppress_empty': False,
                'smtp': {
                    'from': 'F',
                    'to': 'T',
                    'subject': self.TEST_SUBJECT,
                },
            },
        }))
        configfile.flush()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()
