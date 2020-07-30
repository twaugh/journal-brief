[![Code Health](https://landscape.io/github/twaugh/journal-brief/master/landscape.svg?style=flat)](https://landscape.io/github/twaugh/journal-brief/master)
[![Build Status](https://travis-ci.org/twaugh/journal-brief.svg?branch=master)](https://travis-ci.org/twaugh/journal-brief) 
[![Coverage Status](https://coveralls.io/repos/twaugh/journal-brief/badge.svg?branch=master&service=github)](https://coveralls.io/github/twaugh/journal-brief?branch=master)

# journal-brief
Show interesting new systemd journal entries since last run.

This can be run from cron to get a briefing of journal entries sent by
email.  Example:

```
$ cat /etc/cron.daily/journal-brief
#!/bin/sh
exec journal-brief -p err
```

By maintaining a bookmark of the last journal entry processed,
journal-brief is able to carry on processing journal entries from
where it left off last time, ensuring no duplicates and no missed
journal entries.

## Install

### From git
```
python3 setup.py install
```

### From PyPI
```
pip3 install journal-brief
```

### On Fedora
```
dnf install journal-brief
```

## Quick start

One useful feature of journal-brief is that it can generate its own
configuration of which journal entries to ignore. Most of the messages
you are likely to want to ignore will come from booting or shutting
down. Here is the procedure for ignoring those messages:

#### 1. Run journal-brief for the first time, ignoring its output:

```
journal-brief -b >/dev/null
```

This will cause the journal bookmark to be updated to the end of the
journal.

#### 2. Reboot

#### 3. Run journal-brief in debrief mode, to generate configuration:

```
journal-brief -p err debrief > ~/.config/journal-brief/journal-brief.conf
```

#### 4. Adjust to taste

Look through `~/.config/journal-brief/journal-brief.conf` to check
that the exclusions make sense and remove any that do not.

## Configuration

A YAML configuration in `~/.config/journal-brief/journal-brief.conf`
defines which journal entries should be shown.

### Inclusions

Each inclusion is defined by a list of journal fields and their
possible matches. All fields defined in an inclusion must match at
least one of their possible match values for an entry to be included.

For example, the configuration below matches all entries of priority 3
(err) or lower (like `journalctl -p err`), but also includes entries
of priority 6 or lower from the specified systemd unit (like
`journalctl -p info -u myservice.service`):

```yaml
inclusions:
  - PRIORITY: [0, 1, 2, 3]
  - PRIORITY: [4, 5, 6]
    _SYSTEMD_UNIT: [myservice.service]
```

The `priority` configuration parameter sets the log level to add to
all inclusions, and if the PRIORITY field match is not a list it is
matched as a maximum value so the above could be written as:

```yaml
priority: err
inclusions:
  - PRIORITY: info
    _SYSTEMD_UNIT: [myservice.service]
```

### Exclusions

Each exclusion is defined by a list of journal fields and their
possible matches. All fields in an exclusion must match at least one
of their possible match values for an entry to be excluded.

For example:

```yaml
exclusions:
  - MESSAGE:
      - exclude this
      - exclude this too
    SYSLOG_IDENTIFIER:
      - from here
  - MESSAGE_ID: [c7a787079b354eaaa9e77b371893cd27]
  - MESSAGE: ["/Normal exit (.*run)/"]
```

This would cause `journal-brief` to ignore journal entries that
satisfy both conditions: `SYSLOG_IDENTIFIER` is `from here`, and
`MESSAGE` is either `exclude this` or `exclude this too`.

It will also ignore any entries with the specified `MESSAGE_ID`.

In addition, any entries whose `MESSAGE` matches the (Python) regular
expression `Normal exit (.*run)` will be excluded. Regular expressions
are indicated with `/` at the beginning and end of the match string,
and are used for matching (not searching) against the field in
question at the beginning of the field's string value.

The available journal fields are described in the
systemd.journal-fields(7) manual page.

#### Test exclusion rules

You can run `journal-brief --dry-run -b stats` to see how many times
each exclusion rule has excluded messages, based on all messages from
the current boot. The `--dry-run` parameter skips updating the
bookmark, so you can edit the exclusion rules and try again, comparing
output.

#### Automatically create exclusion rules

To create exclusion rules, rather than showing journal entries, run
`journal-brief --dry-run debrief`.

## Email

The standard behavior of journal-brief is to send the desired journal
entries to the standard output, but if desired it can be configured to
send them via email instead. To do this, add an `email` section to the
configuration file. There are two ways that email can be sent: through
a command which implements the normal `mail` interface, or directly
via SMTP.

### Configuration keys

* `suppress_empty`: if true, no email will be sent unless matching journal
entries are found (defaults to `true`)

* `from`: RFC-5322 format address to be used as the sender address (required)

* `to`: RFC-5322 format address to be used as the recipient address, or a list
of such addresses (required)

* `cc`: RFC-5322 format address to be used as a carbon-copy address,
or a list of such addresses

* `bcc`: RFC-5322 format address to be used as a blind-carbon-copy address,
or a list of such addresses

* `subject`: string to be used as the email message subject

* `headers`: dictionary of string keys and string values to be added as
custom headers; the dictionary cannot include 'From', 'To', 'Cc', or 'Bcc'

Either command-based or SMTP-based delivery must be specified (but not both).

### Email via command

Example:
```yaml
email:
  from: "journal sender" <journal@example.com>
  to: "system admin" <admin@example.com>
  command: "sendmail -i -t"
```

This will cause journal-brief to execute the specified command in a
child process and pipe the formatted email message to it. The supplied
command string will be executed via the shell (typically identified in the
`SHELL` environment variable) so it can make use of shell expansions and
other features.

### Email via SMTP

Example:
```yaml
email:
  from: "journal sender" <journal@example.com>
  to: "system admin" <admin@example.com>
  smtp: {}
```

This will cause journal-brief to use the Python `smtplib` module to send
the formatted email message.

Note the usage of YAML 'flow' style to specify an empty mapping for the
'smtp' configuration, allowing all of the defaults to be used. This is only
necessary when no SMTP-specific configuration keys are specified.

#### Email SMTP configuration keys

* `host`: hostname or address of the SMTP server to use for sending email
(defaults to `localhost`)

* `port`: port number to connect to on the SMTP server (defaults to `25`)

* `starttls`: boolean value indicating whether STARTTLS should be used to
secure the connection to the SMTP server (defaults to `false`)

* `user`: username to be used to authenticate to the SMTP server

* `password`: password to be used to authenticate to the SMTP server (only
used if `user` is specified)
