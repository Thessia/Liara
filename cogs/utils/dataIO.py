# noinspection PyUnresolvedReferences
import __main__
from cogs.utils.storage import RedisDict


class dataIO:
    @staticmethod
    def save_json(filename, content):
        if isinstance(content, RedisDict):
            content.commit()

    @staticmethod
    def load_json(filename: str) -> RedisDict:
        return RedisDict(key=filename, redis=__main__.redis_conn)

    @staticmethod
    def is_valid_json(filename):
        return True  # redis saves atomically, yay


load_json = dataIO.load_json
load = load_json
