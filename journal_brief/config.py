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

import errno
from journal_brief import list_formatters
from journal_brief.constants import CONFIG_DIR, PACKAGE, PRIORITY_MAP
from logging import getLogger
import os
import re
import sre_constants
import yaml


log = getLogger(__name__)


class ConfigError(Exception):
    pass


class SyntaxError(ConfigError):
    def __init__(self, config_file, scanner_error):
        super(SyntaxError, self).__init__(scanner_error.problem)
        self.scanner_error = scanner_error
        with open(config_file, 'rt') as cfp:
            self.config_lines = cfp.readlines()

    def __str__(self):
        mark = self.scanner_error.problem_mark
        ret = ('{sev}: {problem}\n'
               '  in "{file}", line {line}, column {column}:\n'.format(
                   sev='error',
                   problem=self.scanner_error.problem,
                   file=mark.name,
                   line=mark.line,
                   column=mark.column))
        assert mark.line > 0
        index = mark.line - 1
        assert index < len(self.config_lines)
        ret += self.config_lines[index]
        assert mark.column > 0
        ret += ' ' * (mark.column - 1) + '^'
        return ret


class SemanticError(ConfigError):
    def __init__(self, message, item, conf, index=None):
        super(SemanticError, self).__init__(message)
        self.message = message
        self.item = item
        self.conf = conf
        self.index = index

    def __str__(self):
        conf = yaml.dump(self.conf,
                         indent=2,
                         default_flow_style=False)
        if self.index is None:
            at = ''
        else:
            at = 'at item {index}, '.format(index=self.index)
            if self.index > 0:
                conflines = conf.split('\n')
                conflines.insert(1, '(...)')
                conf = '\n'.join(conflines)

        return "{sev}: {item}: {message}\n  {at}in:\n{conf}".format(
            sev='error',
            item=self.item,
            message=self.message,
            at=at,
            conf=conf
        )


def load_config(config_file):
    try:
        with open(config_file) as config_fp:
            try:
                config = yaml.safe_load(config_fp)
            except yaml.scanner.ScannerError as scanner_error:
                err = SyntaxError(config_file,
                                  scanner_error)
                log.error(err)
                raise err from scanner_error

        if not config:
            config = {}

        return config
    except IOError as ex:
        if ex.errno != errno.ENOENT:
            raise

        return {}


class Config(dict):
    ALLOWED_KEYWORDS = {
        'cursor-file',
        'debug',
        'exclusions',
        'inclusions',
        'output',
        'priority',
        'email',
    }

    def __init__(self, config_file=None):
        if not config_file:
            conf_filename = '{0}.conf'.format(PACKAGE)
            config_file = os.path.join(CONFIG_DIR, conf_filename)

        default_config = {'cursor-file': 'cursor'}
        config = load_config(config_file)

        if not isinstance(config, dict):
            error = SemanticError('must be a map', 'top level', config)
            log.error(error)
            raise error

        default_config.update(config)
        super(Config, self).__init__(default_config)
        exceptions = list(self.validate())
        for exception in exceptions:
            log.error("%s", exception)
        if exceptions:
            raise exceptions[0]

    def validate(self):
        valid_prios = [prio for prio in PRIORITY_MAP.keys()
                       if isinstance(prio, str)]
        valid_prios.sort()
        for errors in [self.validate_allowed_keywords(),
                       self.validate_cursor_file(),
                       self.validate_debug(),
                       self.validate_inclusions_or_exclusions(valid_prios,
                                                              'exclusions'),
                       self.validate_inclusions_or_exclusions(valid_prios,
                                                              'inclusions'),
                       self.validate_output(),
                       self.validate_priority(valid_prios),
                       self.validate_email()]:
            for error in errors:
                yield error

    def validate_allowed_keywords(self):
        for unexpected_key in set(self) - self.ALLOWED_KEYWORDS:
            yield SemanticError('unexpected keyword', unexpected_key,
                                {unexpected_key: self[unexpected_key]})

    def validate_cursor_file(self):
        if 'cursor-file' not in self:
            return

        if not (isinstance(self['cursor-file'], str) or
                isinstance(self['cursor-file'], int)):
            yield SemanticError('expected string', 'cursor-file',
                                {'cursor-file': self['cursor-file']})

    def validate_debug(self):
        if 'debug' not in self:
            return

        if not (isinstance(self['debug'], bool) or
                isinstance(self['debug'], int)):
            yield SemanticError('expected bool', 'debug',
                                {'debug': self['debug']})

    def validate_email(self):
        ALLOWED_EMAIL_KEYWORDS = {
            'bcc',
            'cc',
            'command',
            'from',
            'headers',
            'smtp',
            'subject',
            'suppress_empty',
            'to',
        }

        ALLOWED_SMTP_KEYWORDS = {
            'host',
            'password',
            'port',
            'starttls',
            'user',
        }

        DISALLOWED_HEADERS = {
            'From'.casefold(),
            'To'.casefold(),
            'Cc'.casefold(),
            'Bcc'.casefold(),
        }

        if 'email' not in self:
            return

        email = self.get('email')
        self['mime-email'] = True

        if not isinstance(email, dict):
            yield SemanticError('must be a map', 'email',
                                {'email': email})
            return

        for unexpected_key in set(email) - ALLOWED_EMAIL_KEYWORDS:
            yield SemanticError('unexpected \'email\' keyword', unexpected_key,
                                {unexpected_key: email[unexpected_key]})

        if 'suppress_empty' in email:
            if not (isinstance(email['suppress_empty'], bool)
                    or isinstance(email['suppress_empty'], int)):
                yield SemanticError('expected bool', 'suppress_empty',
                                    {'email': {'suppress_empty': email['suppress_empty']}})
        else:
            email['suppress_empty'] = True

        if ('smtp' in email and 'command' in email):
            yield SemanticError('cannot specify both smtp and command', 'email',
                                {'email':
                                 {'command': email['command'],
                                  'smtp': email['smtp']}})

        if not ('smtp' in email or 'command' in email):
            yield SemanticError('either smtp or command must be specified', 'email',
                                {'email': email})

        if 'command' in email:
            if not isinstance(email['command'], str):
                yield SemanticError('expected string', 'command',
                                    {'email': {'command': email['command']}})

            # allow old-style non-MIME configuration for command delivery
            if not ('from' in email or 'to' in email):
                self['mime-email'] = False

        if 'smtp' in email:
            smtp = email['smtp']

            # convert old-style configuration to new-style
            for key in ['from', 'to', 'cc', 'bcc', 'subject', 'headers']:
                if key in smtp:
                    email[key] = smtp.pop(key)

            if not isinstance(smtp, dict):
                yield SemanticError('must be a map', 'smtp',
                                    {'email': {'smtp': smtp}})
                return

            for unexpected_key in set(smtp) - ALLOWED_SMTP_KEYWORDS:
                yield SemanticError('unexpected \'smtp\' keyword', unexpected_key,
                                    {unexpected_key: smtp[unexpected_key]})

            if ('host' in smtp and
                    not isinstance(smtp['host'], str)):
                yield SemanticError('expected string', 'host',
                                    {'smtp': {'host': smtp['host']}})

            if ('port' in smtp and
                    not isinstance(smtp['port'], int)):
                yield SemanticError('expected int', 'port',
                                    {'smtp': {'port': smtp['port']}})

            if ('starttls' in smtp and
                not (isinstance(smtp['starttls'], bool) or
                     isinstance(smtp['starttls'], int))):
                yield SemanticError('expected bool', 'starttls',
                                    {'smtp': {'starttls': smtp['starttls']}})

            if ('user' in smtp and
                    not isinstance(smtp['user'], str)):
                yield SemanticError('expected string', 'user',
                                    {'smtp': {'user': smtp['user']}})

            if ('password' in smtp and
                    not isinstance(smtp['password'], str)):
                yield SemanticError('expected string', 'password',
                                    {'smtp': {'password': smtp['password']}})

        if not self['mime-email']:
            return

        if 'from' not in email:
            yield SemanticError('\'email\' map must include \'from\'', 'email',
                                {'email': email})
        else:
            if not isinstance(email['from'], str):
                yield SemanticError('expected string', 'from',
                                    {'email': {'from': email['from']}})

        if 'to' not in email:
            yield SemanticError('\'email\' map must include \'to\'', 'email',
                                {'email': email})
        else:
            if isinstance(email['to'], list):
                pass
            elif isinstance(email['to'], str):
                email['to'] = [email['to']]
            else:
                yield SemanticError('expected list or string', 'to',
                                    {'email': {'to': email['to']}})

        if 'cc' in email:
            if isinstance(email['cc'], list):
                pass
            elif isinstance(email['cc'], str):
                email['cc'] = [email['cc']]
            else:
                yield SemanticError('expected list or string', 'cc',
                                    {'email': {'cc': email['cc']}})

        if 'bcc' in email:
            if isinstance(email['bcc'], list):
                pass
            elif isinstance(email['bcc'], str):
                email['bcc'] = [email['bcc']]
            else:
                yield SemanticError('expected list or string', 'bcc',
                                    {'email': {'bcc': email['bcc']}})

        if ('subject' in email and
                not isinstance(email['subject'], str)):
            yield SemanticError('expected string', 'subject',
                                {'email': {'subject': email['subject']}})

        if 'headers' in email:
            if not isinstance(email['headers'], dict):
                yield SemanticError('expected dict', 'headers',
                                    {'email': {'headers': email['headers']}})
            else:
                for key in email['headers'].keys():
                    if key.casefold() in DISALLOWED_HEADERS:
                        yield SemanticError("Header " + key + " cannot not be specified here", 'headers',
                                            {'email': {'headers': email['headers']}})

    def validate_output(self):
        if 'output' not in self:
            return

        formatters = list_formatters()
        output = self['output']
        if isinstance(output, list):
            outputs = output
        else:
            outputs = [output]
            self['output'] = outputs

        for output in outputs:
            if output not in formatters:
                yield SemanticError('invalid output format, must be in %s' %
                                    formatters, output,
                                    {'output': self['output']})

    def validate_priority(self, valid_prios):
        if 'priority' not in self:
            return

        try:
            valid = self['priority'] in PRIORITY_MAP
        except TypeError:
            valid = False
        finally:
            if not valid:
                yield SemanticError('invalid priority, must be in %s' %
                                    valid_prios, 'priority',
                                    {'priority': self['priority']})

    def validate_inclusions_or_exclusions(self, valid_prios, key):
        if key not in self:
            return

        if not isinstance(self[key], list):
            yield SemanticError('must be a list', key,
                                {key: self[key]})
            return

        for error in self.find_bad_rules(valid_prios, key):
            yield error

    def priority_rule_is_valid(self, values):
        try:
            if isinstance(values, list):
                valid = all(value in PRIORITY_MAP
                            for value in values)
            else:
                valid = values in PRIORITY_MAP
        except TypeError:
            valid = False
        return valid

    def find_bad_rule_values(self, key, index, field, values):
        for value in values:
            if isinstance(value, list) or isinstance(value, dict):
                yield SemanticError('must be a string', value,
                                    {key: [{field: values}]},
                                    index=index)
                continue

            if (key == 'exclusions' and
                    isinstance(value, str) and
                    value.startswith('/') and
                    value.endswith('/')):
                try:
                    # TODO: use this computed value
                    re.compile(value[1:-1])
                except sre_constants.error as ex:
                    yield SemanticError(ex.args[0], value,
                                        {key: [{field: values}]},
                                        index=index)

    def find_bad_rules(self, valid_prios, key):
        log.debug("%s:", key)
        for index, rule in enumerate(self[key]):
            if not isinstance(rule, dict):
                yield SemanticError('must be a map', key, {key: [rule]}, index)
                continue

            log.debug('-')
            for field, values in rule.items():
                log.debug("%s: %r", field, values)
                if field == 'PRIORITY':
                    if not self.priority_rule_is_valid(values):
                        message = ('must be list or priority (%s)' %
                                   valid_prios)
                        yield SemanticError(message, field,
                                            {key: [{field: values}]},
                                            index=index)

                    continue

                if not isinstance(values, list):
                    yield SemanticError('must be a list', field,
                                        {key: [{field: values}]},
                                        index=index)
                    continue

                for error in self.find_bad_rule_values(key, index,
                                                       field, values):
                    yield error
