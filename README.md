# journal-brief
Show new journal entries since last run.

This can be run from cron to get a briefing of journal entries sent by
email.  Example:

```
$ cat /etc/cron.daily/journal-brief
#!/bin/sh
exec journal-brief -p err
```

## Configuration

A YAML configuration in `~/.config/journal-brief.conf` defines which
journal entries should be ignored.  For example:

```yaml
exclusions:
- MESSAGE:
  - exclude this
  - exclude this too
  SYSLOG_IDENTIFIER:
  - from here
- MESSAGE_ID: [c7a787079b354eaaa9e77b371893cd27]
```

This would cause `journal-brief` to ignore journal entries that
satisfy both conditions: `SYSLOG_IDENTIFIER` is `from here`, and
`MESSAGE` is either `exclude this` or `exclude this too`.

It will also ignore any entries with the specified `MESSAGE_ID`.

## Install

### From git
```
python3 setup.py install
```

### From PyPI
```
pip3 install journal-brief
```
