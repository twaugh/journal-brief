from collections.abc import Iterator


LOG_EMERG = 0
LOG_ALERT = 1
LOG_CRIT = 2
LOG_ERR = 3
LOG_WARNING = 4
LOG_NOTICE = 5
LOG_INFO = 6
LOG_DEBUG = 7

DEFAULT_CONVERTERS = {}


class Reader(Iterator):
    """
    Mock systemd.journal.Reader so we can run tests in its absence
    """

    def get_next(self):
        raise RuntimeError

    def get_previous(self):
        return {'__CURSOR': '0'}

    def __next__(self):
        entry = self.get_next()
        if not entry:
            raise StopIteration

        return entry

    def this_boot(self):
        raise RuntimeError

    def log_level(self, level):
        raise RuntimeError

    def add_disjunction(self):
        raise RuntimeError

    def add_conjunction(self):
        raise RuntimeError

    def add_match(self, *args, **kwargs):
        raise RuntimeError

    def seek_cursor(self, cursor):
        raise RuntimeError

    def seek_tail(self):
        pass

    def close(self):
        pass

class Monotonic(object):
    def __init__(self, init_tuple):
        self.timestamp = init_tuple[0]
