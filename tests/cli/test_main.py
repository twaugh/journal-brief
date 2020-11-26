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
from flexmock import flexmock
from journal_brief.cli.constants import (EMAIL_SUPPRESS_EMPTY_TEXT,
                                         EMAIL_DRY_RUN_SEPARATOR)
from journal_brief.cli.main import CLI
import json
import logging
import os
import pytest
from systemd import journal
from tempfile import NamedTemporaryFile
from tests.test_filter import MySpecialFormatter  # registers class; # noqa: F401
from tests.util import Watcher
import uuid
import yaml


logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def build_config_and_cursor(tmp_path):
    with NamedTemporaryFile(mode='wt', dir=tmp_path) as configfile:
        with NamedTemporaryFile(mode='w+t', dir=tmp_path) as cursorfile:
            def write_config(config=None):
                configfile.write('cursor-file: {0}\n'.format(cursorfile.name))
                if isinstance(config, dict):
                    configfile.write(yaml.dump(config))
                elif config:
                    configfile.write(config)
                configfile.flush()
                return (configfile, cursorfile)

            yield write_config


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

    def test_normal_run(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message1'})
            .and_return({'__CURSOR': '2',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message2'})
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor()
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert len(out.splitlines()) == 2

    def test_dry_run(self, build_config_and_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor()
        cli = CLI(args=['--conf', configfile.name, '--dry-run'])
        cli.run()
        assert not cursorfile.read()

    def test_this_boot(self, build_config_and_cursor):
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

        (configfile, cursorfile) = build_config_and_cursor()
        cursorfile.write(final_cursor)
        cursorfile.flush()
        cli = CLI(args=['--conf', configfile.name, '-b'])
        cli.run()
        cursorfile.seek(0)
        assert cursorfile.read() == final_cursor

    def test_log_level(self, build_config_and_cursor, missing_or_empty_cursor):
        flexmock(journal.Reader, add_match=None, add_disjunction=None)
        (flexmock(journal.Reader)
            .should_receive('log_level')
            .with_args(journal.LOG_ERR)
            .once())
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor()
        cli = CLI(args=['--conf', configfile.name, '-p', 'err'])
        cli.run()

    def test_reset(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor()
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

    def test_stats(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'exclude'})
            .and_return({'__CURSOR': '2',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'include'})
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor("""
exclusions:
- MESSAGE: [exclude]
""")
        cli = CLI(args=['--conf', configfile.name, 'stats'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert out == "\n".join([" FREQUENCY  EXCLUSION",
                                 "         1  {'MESSAGE': ['exclude']}",
                                 ""])

    def test_debrief(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
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

        (configfile, cursorfile) = build_config_and_cursor()
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

    def test_debrief_no_input(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
        """
        Check it handles there being no input
        """
        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor()
        cli = CLI(args=['--conf', configfile.name, 'debrief'])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert not out

    def test_exclusions_yaml(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
        (flexmock(journal.Reader, add_match=None, add_disjunction=None)
            .should_receive('get_next')
            .and_return({'__CURSOR': '1',
                         '__REALTIME_TIMESTAMP': datetime.now(),
                         'MESSAGE': 'message'})
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor("""
exclusions:
- MESSAGE: [1]
""")
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        assert 'message' in out

    def test_inclusions_yaml(self, build_config_and_cursor, missing_or_empty_cursor):
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

        (configfile, cursorfile) = build_config_and_cursor("""
inclusions:
- PRIORITY: [0, 1, 2, 3]
- PRIORITY: [4, 5, 6]
  _SYSTEMD_UNIT: [myservice.service]
""")
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

    def test_multiple_output_formats_cli(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'MESSAGE': 'message',
        }

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor()
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

    def test_multiple_output_formats_conf(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
        entry = {
            '__CURSOR': '1',
            '__REALTIME_TIMESTAMP': datetime.now(),
            'MESSAGE': 'message',
        }

        (flexmock(journal.Reader)
            .should_receive('get_next')
            .and_return(entry)
            .and_return({}))

        (configfile, cursorfile) = build_config_and_cursor("""
output:
- cat
- cat
- json
""")
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

    def test_formatter_filter(self, capsys, build_config_and_cursor, missing_or_empty_cursor):
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

        (configfile, cursorfile) = build_config_and_cursor()
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


class TestCLIEmailBase(object):
    @pytest.fixture(autouse=True)
    def mock_journal(self, mocker):
        # mock SelectiveReader to ensure that systemd.journal.Reader is never used
        self.reader_class = mocker.patch('journal_brief.cli.main.SelectiveReader', autospec=True)

        self.entries_class = mocker.patch('journal_brief.cli.main.LatestJournalEntries', autospec=True)
        self.entries_object = self.entries_class.return_value.__enter__.return_value
        # don't provide any journal entries unless test function calls mock_entries()
        self.entries_object.__iter__.return_value = []

        def mock_entries(entries):
            self.entries_object.__iter__.return_value = entries

        yield mock_entries


class TestCLIEmailMIME(TestCLIEmailBase):
    TEST_COMMAND = 'foo'
    TEST_SUBJECT = 'subj'

    @pytest.fixture(autouse=True)
    def mock_mime(self, mocker):
        self.mimetext_class = mocker.patch('journal_brief.cli.main.MIMEText', autospec=True)
        self.mimetext_object = self.mimetext_class.return_value

    @pytest.fixture(autouse=True)
    def mock_subprocess(self, mocker):
        self.subprocess_module = mocker.patch('journal_brief.cli.main.subprocess', autospec=True)

    def test(self, capsys, mocker, build_config_and_cursor, mock_journal):
        entries = [
            {
                '__CURSOR': '1',
                'TEST': 'yes',
                'OUTPUT': 'message',
            }
        ]

        mock_journal(entries)

        (configfile, cursorfile) = build_config_and_cursor({
            'output': 'test',
            'email': {
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_class.assert_called_once_with(entries[0]['OUTPUT'], _charset=mocker.ANY)

        self.mimetext_object.__setitem__.assert_any_call('From', 'F')
        self.mimetext_object.__setitem__.assert_any_call('To', 'T')

    def test_allow_empty(self, mocker, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_class.assert_called_once_with(EMAIL_SUPPRESS_EMPTY_TEXT, _charset=mocker.ANY)

    def test_subject(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
                'subject': self.TEST_SUBJECT,
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_object.__setitem__.assert_any_call('Subject', self.TEST_SUBJECT)

    def test_to_list(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': ['A', 'B'],
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_object.__setitem__.assert_any_call('To', 'A, B')

    def test_cc_list(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
                'cc': ['A', 'B'],
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_object.__setitem__.assert_any_call('Cc', 'A, B')

    def test_bcc_list(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
                'bcc': ['A', 'B'],
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_object.__setitem__.assert_any_call('Bcc', 'A, B')

    def test_headers(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
                'headers': {
                    'X-Header-1': '1',
                    'X-Header-4': '4',
                },
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.mimetext_object.__setitem__.assert_any_call('X-Header-1', '1')
        self.mimetext_object.__setitem__.assert_any_call('X-Header-4', '4')


class TestCLIEmailCommand(TestCLIEmailBase):
    TEST_COMMAND = 'foo'

    @pytest.fixture(autouse=True)
    def mock_subprocess(self, mocker):
        self.subprocess_module = mocker.patch('journal_brief.cli.main.subprocess', autospec=True)

    def test(self, build_config_and_cursor, mock_journal, mocker):
        entries = [
            {
                '__CURSOR': '1',
                'TEST': 'yes',
                'OUTPUT': 'message',
            }
        ]

        mock_journal(entries)

        (configfile, cursorfile) = build_config_and_cursor({
            'output': 'test',
            'email': {
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
            }
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.subprocess_module.run.assert_called_once_with(self.TEST_COMMAND, shell=True, check=True, text=True, input=mocker.ANY)
        assert isinstance(self.subprocess_module.run.call_args[1]['input'], str), "subprocess.run 'input' argument must be a string"

    def test_non_mime(self, build_config_and_cursor, mock_journal, mocker):
        entries = [
            {
                '__CURSOR': '1',
                'TEST': 'yes',
                'OUTPUT': 'message',
            }
        ]

        mock_journal(entries)

        (configfile, cursorfile) = build_config_and_cursor({
            'output': 'test',
            'email': {
                'command': self.TEST_COMMAND,
            }
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.subprocess_module.run.assert_called_once_with(self.TEST_COMMAND, shell=True, check=True, text=True, input=entries[0]['OUTPUT'])

    def test_dry_run(self, capsys, build_config_and_cursor, mock_journal):
        entries = [
            {
                '__CURSOR': '1',
                'TEST': 'yes',
                'OUTPUT': 'message',
            }
        ]

        mock_journal(entries)

        (configfile, cursorfile) = build_config_and_cursor({
            'output': 'test',
            'email': {
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
            },
        })
        cli = CLI(args=['--dry-run', '--conf', configfile.name])
        cli.run()

        (out, err) = capsys.readouterr()
        assert not err
        lines = out.splitlines()
        assert len(lines) == 10
        assert lines[0] == "Email to be delivered via '{0}'".format(self.TEST_COMMAND)
        assert lines[1] == EMAIL_DRY_RUN_SEPARATOR

        self.subprocess_module.run.assert_not_called()

    def test_suppress_empty(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'command': self.TEST_COMMAND,
                'from': 'F',
                'to': 'T',
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.subprocess_module.run.assert_not_called()


class TestCLIEmailSMTP(TestCLIEmailBase):
    TEST_USER = 'zork'
    TEST_PASSWORD = 'xyzzy'
    TEST_HOST = 'example'
    TEST_PORT = 1234
    TEST_SUBJECT = 'subj'

    @pytest.fixture(autouse=True)
    def mock_smtp(self, mocker):
        self.smtp_class = mocker.patch('journal_brief.cli.main.SMTP', autospec=True)
        self.smtp_object = self.smtp_class.return_value
        self.smtp_context = self.smtp_object.__enter__.return_value

    def test(self, capsys, mocker, build_config_and_cursor, mock_journal):
        entries = [
            {
                '__CURSOR': '1',
                'TEST': 'yes',
                'OUTPUT': 'message',
            }
        ]

        mock_journal(entries)

        (configfile, cursorfile) = build_config_and_cursor({
            'output': 'test',
            'email': {
                'from': 'F',
                'to': 'T',
                'smtp': {},
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.smtp_context.send_message.assert_called_once()

    def test_dry_run(self, capsys, build_config_and_cursor, mock_journal):
        entries = [
            {
                '__CURSOR': '1',
                'TEST': 'yes',
                'OUTPUT': 'message',
            }
        ]

        mock_journal(entries)

        (configfile, cursorfile) = build_config_and_cursor({
            'output': 'test',
            'email': {
                'from': 'F',
                'to': 'T',
                'smtp': {},
            },
        })
        cli = CLI(args=['--dry-run', '--conf', configfile.name])
        cli.run()

        self.smtp_class.assert_not_called()

        (out, err) = capsys.readouterr()
        assert not err
        lines = out.splitlines()
        assert len(lines) == 10
        assert lines[0] == 'Email to be delivered via SMTP to localhost port 25'
        assert lines[1] == EMAIL_DRY_RUN_SEPARATOR

    def test_suppress_empty(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'from': 'F',
                'to': 'T',
                'smtp': {},
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.smtp_class.assert_not_called()

    def test_host(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'from': 'F',
                'to': 'T',
                'smtp': {
                    'host': self.TEST_HOST,
                },
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.smtp_class.assert_called_once_with(self.TEST_HOST, 0)

    def test_port(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'from': 'F',
                'to': 'T',
                'smtp': {
                    'host': self.TEST_HOST,
                    'port': self.TEST_PORT,
                },
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        self.smtp_class.assert_called_once_with(self.TEST_HOST, self.TEST_PORT)

    def test_starttls(self, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'from': 'F',
                'to': 'T',
                'smtp': {
                    'starttls': True,
                },
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        assert 'starttls' == self.smtp_context.method_calls[0][0]
        assert 'send_message' == self.smtp_context.method_calls[1][0]

    def test_user(self, mocker, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'from': 'F',
                'to': 'T',
                'smtp': {
                    'user': self.TEST_USER,
                },
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        assert mocker.call.login(self.TEST_USER, None) == self.smtp_context.method_calls[0]
        assert 'send_message' == self.smtp_context.method_calls[1][0]

    def test_password(self, mocker, build_config_and_cursor):
        (configfile, cursorfile) = build_config_and_cursor({
            'email': {
                'suppress_empty': False,
                'from': 'F',
                'to': 'T',
                'smtp': {
                    'user': self.TEST_USER,
                    'password': self.TEST_PASSWORD,
                },
            },
        })
        cli = CLI(args=['--conf', configfile.name])
        cli.run()

        assert mocker.call.login(self.TEST_USER, self.TEST_PASSWORD) == self.smtp_context.method_calls[0]
        assert 'send_message' == self.smtp_context.method_calls[1][0]
