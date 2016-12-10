import redis_collections
import threading
import time
import __main__


class RedisDict(redis_collections.Dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.die = False
        self.thread = threading.Thread(target=self.update_loop, daemon=True, name=kwargs['key'])
        self.thread.start()
        self.prev = None

    def update_loop(self):
        time.sleep(2)
        while not self.die:
            if self.prev != repr(self):
                self.prev = repr(self)
                self.sync()
                time.sleep(0.1)
            else:
                self.cache.clear()
                time.sleep(0.1)


class dataIO:
    @staticmethod
    def save_json(filename, content):
        pass  # "oops"

    @staticmethod
    def load_json(filename):
        return RedisDict(key=filename, redis=__main__.redis_conn, writeback=True)
