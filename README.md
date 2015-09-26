# journal-brief
Show new journal entries since last run.

This can be run from cron to get journal entries sent by email.
Example:

```
$ cat /etc/cron.daily/journal-brief
#!/bin/sh
exec journal-brief -p err
```

## Install

### From git
```
python3 setup.py install
```

### From PyPI
```
pip3 install journal-brief
```
