# noinspection PyUnresolvedReferences
import __main__
from cogs.utils.storage import RedisDict


class dataIO:
    @staticmethod
    def save_json(filename, content):
        pass  # "oops"

    @staticmethod
    def load_json(filename):
        return RedisDict(key=filename, redis=__main__.redis_conn)


load_json = dataIO.load_json
load = load_json
